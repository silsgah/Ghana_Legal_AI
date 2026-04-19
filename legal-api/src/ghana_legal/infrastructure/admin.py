"""Admin API endpoints for pipeline monitoring.

Protected by role-based auth: only users with role "admin" in their
Clerk publicMetadata can access these endpoints.
"""

import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel
from loguru import logger

from ghana_legal.infrastructure.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

# ─── Ingestion job state (in-memory, resets on restart) ───────────────────────
_ingestion_state = {
    "status": "idle",       # idle | running | completed | failed
    "started_at": None,
    "completed_at": None,
    "result": None,         # summary dict on completion
    "error": None,
}


# Resolve manifest path
_PROJECT_ROOT = Path(__file__).resolve().parents[4]
MANIFEST_PATH = _PROJECT_ROOT / "data" / "pipeline_manifest.json"
REPORTS_DIR = _PROJECT_ROOT / "data" / "pipeline_reports"
CASES_DIR = _PROJECT_ROOT / "data" / "cases"

# Admin Clerk user IDs — add your Clerk user ID here
# You can also check publicMetadata.role == "admin" from Clerk
ADMIN_CLERK_IDS = {
    "user_3Bclg9FZMJHFCx7xNcirHbbYGbd",
}


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Dependency that ensures the user is an admin.

    Checks:
    1. Clerk publicMetadata.role == "admin"
    2. Or clerk_id is in ADMIN_CLERK_IDS allowlist
    """
    clerk_id = user.get("sub", "")

    # Check allowlist
    if ADMIN_CLERK_IDS and clerk_id in ADMIN_CLERK_IDS:
        return user

    # Log the full JWT payload for debugging (remove after confirming)
    from loguru import logger
    logger.info(f"Admin check — JWT keys: {list(user.keys())}")
    logger.info(f"Admin check — JWT payload: {user}")

    # Clerk includes publicMetadata under "metadata" or "publicMetadata" or
    # as top-level custom claims depending on JWT template config
    for key in ("metadata", "publicMetadata", "public_metadata"):
        metadata = user.get(key, {})
        if isinstance(metadata, dict) and metadata.get("role") == "admin":
            return user

    # Check top-level role claim (Clerk custom JWT templates)
    if user.get("role") == "admin":
        return user

    # Check Clerk org role
    if user.get("org_role") == "admin":
        return user

    raise HTTPException(status_code=403, detail="Admin access required")


def _load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        return {"cases": {}}
    return json.loads(MANIFEST_PATH.read_text())


@router.get("/pipeline/stats")
async def pipeline_stats(user: dict = Depends(require_admin)):
    """Overview stats for the admin dashboard."""
    data = _load_manifest()
    cases = data.get("cases", {})

    by_status = {}
    by_court = {}
    for rec in cases.values():
        status = rec.get("status", "unknown")
        court = rec.get("court_id", "unknown")
        by_status[status] = by_status.get(status, 0) + 1
        by_court[court] = by_court.get(court, 0) + 1

    # Count PDFs on disk
    pdf_count = 0
    total_size_mb = 0.0
    if CASES_DIR.exists():
        for pdf in CASES_DIR.rglob("*.pdf"):
            pdf_count += 1
            total_size_mb += pdf.stat().st_size / (1024 * 1024)

    return {
        "total_cases": len(cases),
        "by_status": by_status,
        "by_court": by_court,
        "pdfs_on_disk": pdf_count,
        "total_size_mb": round(total_size_mb, 1),
    }


@router.get("/pipeline/cases")
async def pipeline_cases(
    user: dict = Depends(require_admin),
    status: Optional[str] = Query(None),
    court_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """List cases with optional filtering and pagination."""
    data = _load_manifest()
    cases = list(data.get("cases", {}).values())

    if status:
        cases = [c for c in cases if c.get("status") == status]
    if court_id:
        cases = [c for c in cases if c.get("court_id") == court_id]

    # Sort by discovered_at descending
    cases.sort(key=lambda c: c.get("discovered_at", ""), reverse=True)

    total = len(cases)
    start = (page - 1) * per_page
    page_cases = cases[start:start + per_page]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "cases": page_cases,
    }


@router.get("/pipeline/reports")
async def pipeline_reports(user: dict = Depends(require_admin)):
    """List recent pipeline run reports."""
    if not REPORTS_DIR.exists():
        return {"reports": []}

    reports = []
    for f in sorted(REPORTS_DIR.glob("report_*.json"), reverse=True)[:20]:
        try:
            reports.append(json.loads(f.read_text()))
        except Exception:
            pass

    return {"reports": reports}


# ─────────────────────────────────────────────────────────────────────────────
# User Management Endpoints
# ─────────────────────────────────────────────────────────────────────────────

class PlanUpdateRequest(BaseModel):
    plan: str  # "free" | "professional" | "enterprise"


class PlatformConfigUpdateRequest(BaseModel):
    free_tier_daily_limit: Optional[int] = None
    pro_monthly_price_ghs: Optional[float] = None
    enterprise_monthly_price_ghs: Optional[float] = None


@router.get("/users")
async def list_users(
    user: dict = Depends(require_admin),
    search: str = Query("", description="Filter by email or clerk_id"),
    page: int = Query(1, ge=1),
    per_page: int = Query(30, ge=1, le=100),
):
    """List all users with their plan tier and today's usage count.

    For users with placeholder emails, attempts to enrich from the Clerk API
    if CLERK_SECRET_KEY is configured.
    """
    import asyncio
    from ghana_legal.infrastructure.usage import list_users_with_usage, clerk_fetch_user

    result = await list_users_with_usage(search=search, page=page, per_page=per_page)

    # Enrich placeholder users with real Clerk data in parallel
    async def enrich(u: dict) -> dict:
        if u["email"].endswith("@placeholder.local"):
            clerk_data = await clerk_fetch_user(u["clerk_id"])
            if clerk_data:
                u["email"] = clerk_data["email"] or u["email"]
                u["display_name"] = clerk_data["display_name"]
            else:
                u["display_name"] = u["clerk_id"]
        else:
            u["display_name"] = u["email"]
        return u

    result["users"] = await asyncio.gather(*[enrich(u) for u in result["users"]])
    return result


@router.post("/users/enrich")
async def enrich_all_users(
    user: dict = Depends(require_admin),
):
    """Bulk-backfill real emails from Clerk for all placeholder users.

    Runs in the background — returns a count of how many users were updated.
    Requires CLERK_SECRET_KEY to be set in .env.
    """
    import asyncio
    from ghana_legal.infrastructure.usage import clerk_fetch_user
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import User
    from sqlalchemy import select
    from datetime import datetime, timezone

    async with get_session() as session:
        result = await session.execute(
            select(User).where(User.email.like("%@placeholder.local"))
        )
        placeholder_users = result.scalars().all()

        updated = 0
        for u in placeholder_users:
            clerk_data = await clerk_fetch_user(u.clerk_id)
            if clerk_data and clerk_data["email"]:
                u.email = clerk_data["email"]
                u.updated_at = datetime.now(timezone.utc)
                updated += 1

    return {
        "success": True,
        "total_placeholder_users": len(placeholder_users),
        "updated": updated,
        "message": f"Updated {updated} of {len(placeholder_users)} placeholder users.",
    }


@router.get("/users/{clerk_id}")
async def get_user_detail(
    clerk_id: str,
    user: dict = Depends(require_admin),
):
    """Get detailed info for a single user."""
    from ghana_legal.infrastructure.usage import get_user, check_quota
    target = await get_user(clerk_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    quota = await check_quota(clerk_id)
    return {
        "clerk_id": target.clerk_id,
        "email": target.email,
        "plan": target.plan.value,
        "created_at": target.created_at.isoformat() if target.created_at else None,
        "updated_at": target.updated_at.isoformat() if target.updated_at else None,
        "quota": quota,
    }


@router.patch("/users/{clerk_id}/plan")
async def update_user_plan_admin(
    clerk_id: str,
    body: PlanUpdateRequest,
    user: dict = Depends(require_admin),
):
    """Switch a user's plan tier (admin override, no Paystack involved).

    When downgrading to free, existing subscription records are marked cancelled.
    Payment history is preserved for audit.
    """
    from ghana_legal.infrastructure.usage import switch_user_plan
    from ghana_legal.domain.models import PlanType

    try:
        new_plan = PlanType(body.plan.lower())
    except ValueError:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid plan '{body.plan}'. Must be one of: free, professional, enterprise",
        )

    try:
        updated_user = await switch_user_plan(clerk_id=clerk_id, new_plan=new_plan)
        return {
            "success": True,
            "clerk_id": updated_user.clerk_id,
            "email": updated_user.email,
            "plan": updated_user.plan.value,
            "message": f"Plan updated to '{new_plan.value}' successfully.",
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/users/{clerk_id}/usage")
async def wipe_user_usage(
    clerk_id: str,
    user: dict = Depends(require_admin),
):
    """Wipe today's free-tier usage for a user (admin reset).

    Gives the user a full fresh daily allocation immediately.
    Only deletes today's rows — historical usage is preserved.
    """
    from ghana_legal.infrastructure.usage import wipe_user_daily_usage, get_user
    target = await get_user(clerk_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = await wipe_user_daily_usage(clerk_id)
    return {
        "success": True,
        "clerk_id": clerk_id,
        "rows_deleted": deleted,
        "message": f"Wiped {deleted} usage log entries for today.",
    }


# ─────────────────────────────────────────────────────────────────────────────
# Platform Configuration Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/config")
async def get_config(user: dict = Depends(require_admin)):
    """Get current platform configuration (pricing and quotas)."""
    from ghana_legal.infrastructure.usage import get_platform_config
    return await get_platform_config()


@router.put("/config")
async def update_config(
    body: PlatformConfigUpdateRequest,
    user: dict = Depends(require_admin),
):
    """Update platform configuration. Only provided fields are changed.

    Changes take effect immediately — no restart required.
    """
    from ghana_legal.infrastructure.usage import set_platform_config

    updates = {}
    if body.free_tier_daily_limit is not None:
        if body.free_tier_daily_limit < 1:
            raise HTTPException(status_code=422, detail="free_tier_daily_limit must be ≥ 1")
        updates["free_tier_daily_limit"] = body.free_tier_daily_limit
    if body.pro_monthly_price_ghs is not None:
        if body.pro_monthly_price_ghs < 0:
            raise HTTPException(status_code=422, detail="Price cannot be negative")
        updates["pro_monthly_price_ghs"] = body.pro_monthly_price_ghs
    if body.enterprise_monthly_price_ghs is not None:
        if body.enterprise_monthly_price_ghs < 0:
            raise HTTPException(status_code=422, detail="Price cannot be negative")
        updates["enterprise_monthly_price_ghs"] = body.enterprise_monthly_price_ghs

    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update")

    updated = await set_platform_config(updates)
    return {"success": True, "config": updated}


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Ingestion Trigger
# ─────────────────────────────────────────────────────────────────────────────

def _run_ingestion_sync():
    """Run the constitution ingestion script synchronously (called in background)."""
    global _ingestion_state
    import subprocess
    import sys

    try:
        _ingestion_state["status"] = "running"
        _ingestion_state["started_at"] = datetime.now(timezone.utc).isoformat()
        _ingestion_state["error"] = None
        _ingestion_state["result"] = None

        logger.info("Admin-triggered ingestion starting...")

        # Run the ingestion script as a subprocess
        src_dir = Path(__file__).resolve().parents[1]
        script_path = src_dir.parent / "scripts" / "ingest_constitution_to_qdrant.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--no-prompt"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max
            cwd=str(src_dir.parent),
        )

        _ingestion_state["completed_at"] = datetime.now(timezone.utc).isoformat()

        if result.returncode == 0:
            _ingestion_state["status"] = "completed"
            # Extract summary from output
            output_lines = result.stdout.strip().split("\n")
            summary_lines = [l for l in output_lines if "Chunks" in l or "ingested" in l or "Success" in l or "✓" in l]
            _ingestion_state["result"] = {
                "exit_code": 0,
                "summary": "\n".join(summary_lines[-5:]) if summary_lines else "Completed successfully",
            }
            logger.success("Admin-triggered ingestion completed successfully")
        else:
            _ingestion_state["status"] = "failed"
            _ingestion_state["error"] = result.stderr[-500:] if result.stderr else "Unknown error"
            logger.error(f"Admin-triggered ingestion failed: {result.stderr[-200:]}")

    except subprocess.TimeoutExpired:
        _ingestion_state["status"] = "failed"
        _ingestion_state["error"] = "Ingestion timed out after 10 minutes"
        _ingestion_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.error("Admin-triggered ingestion timed out")
    except Exception as e:
        _ingestion_state["status"] = "failed"
        _ingestion_state["error"] = str(e)
        _ingestion_state["completed_at"] = datetime.now(timezone.utc).isoformat()
        logger.error(f"Admin-triggered ingestion error: {e}")


@router.post("/pipeline/trigger-ingestion")
async def trigger_ingestion(
    background_tasks: BackgroundTasks,
    user: dict = Depends(require_admin),
):
    """Trigger constitution ingestion as a background task.

    Returns immediately — poll GET /api/admin/pipeline/ingestion-status for progress.
    Only one ingestion can run at a time.
    """
    if _ingestion_state["status"] == "running":
        raise HTTPException(
            status_code=409,
            detail="Ingestion is already running. Please wait for it to complete.",
        )

    background_tasks.add_task(_run_ingestion_sync)
    return {
        "success": True,
        "message": "Ingestion triggered. Poll /api/admin/pipeline/ingestion-status for progress.",
    }


@router.get("/pipeline/ingestion-status")
async def ingestion_status(user: dict = Depends(require_admin)):
    """Get the current ingestion job status."""
    return _ingestion_state
