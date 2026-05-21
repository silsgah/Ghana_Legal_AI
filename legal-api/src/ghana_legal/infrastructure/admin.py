"""Admin API endpoints for pipeline monitoring.

Protected by role-based auth: only users with role "admin" in their
Clerk publicMetadata can access these endpoints.
"""

import json
import os
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from loguru import logger

from ghana_legal.infrastructure.auth import get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])

# A run still marked "running" past this age is treated as crashed so a new
# trigger can proceed. Must exceed the subprocess timeout in _run_ingestion.
INGESTION_STALE_AFTER = timedelta(minutes=15)


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


@router.get("/pipeline/stats")
async def pipeline_stats(user: dict = Depends(require_admin)):
    """Overview stats for the admin dashboard — backed by PostgreSQL."""
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import PipelineCase
    from sqlalchemy import select, func

    async with get_session() as session:
        # Count by status
        result = await session.execute(
            select(PipelineCase.status, func.count(PipelineCase.case_id))
            .group_by(PipelineCase.status)
        )
        by_status = {row[0]: row[1] for row in result.all()}

        # Count by court
        result = await session.execute(
            select(PipelineCase.court_id, func.count(PipelineCase.case_id))
            .group_by(PipelineCase.court_id)
        )
        by_court = {row[0]: row[1] for row in result.all()}

        total = sum(by_status.values())

    # Count PDFs on disk (works in both Modal /data/cases and local)
    pdf_count = 0
    total_size_mb = 0.0
    for cases_dir in [Path("/data/cases"), CASES_DIR]:
        if cases_dir.exists():
            for pdf in cases_dir.rglob("*.pdf"):
                pdf_count += 1
                total_size_mb += pdf.stat().st_size / (1024 * 1024)
            break  # use whichever path exists

    return {
        "total_cases": total,
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
    """List cases with optional filtering and pagination — backed by PostgreSQL."""
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import PipelineCase
    from sqlalchemy import select, func

    async with get_session() as session:
        query = select(PipelineCase)
        count_query = select(func.count(PipelineCase.case_id))

        if status:
            query = query.where(PipelineCase.status == status)
            count_query = count_query.where(PipelineCase.status == status)
        if court_id:
            query = query.where(PipelineCase.court_id == court_id)
            count_query = count_query.where(PipelineCase.court_id == court_id)

        total_result = await session.execute(count_query)
        total = total_result.scalar()

        offset = (page - 1) * per_page
        query = query.order_by(PipelineCase.updated_at.desc()).offset(offset).limit(per_page)

        result = await session.execute(query)
        cases = result.scalars().all()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "cases": [
            {
                "case_id": c.case_id,
                "url": c.url,
                "pdf_url": c.pdf_url,
                "title": c.title,
                "court_id": c.court_id,
                "status": c.status,
                "error": c.error,
                "retry_count": c.retry_count,
                "discovered_at": c.updated_at.isoformat() if c.updated_at else datetime.now(timezone.utc).isoformat(),
                "updated_at": c.updated_at.isoformat() if c.updated_at else datetime.now(timezone.utc).isoformat(),
            }
            for c in cases
        ],
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
    plan: str  # "free" | "student" | "professional" | "firm" | "institution" | "enterprise" (deprecated)


class PlatformConfigUpdateRequest(BaseModel):
    # Daily limits. -1 = unlimited.
    free_tier_daily_limit: Optional[int] = None
    student_daily_limit: Optional[int] = None
    professional_daily_limit: Optional[int] = None
    firm_daily_limit: Optional[int] = None
    institution_daily_limit: Optional[int] = None
    # Monthly prices (GHS)
    student_monthly_price_ghs: Optional[float] = None
    pro_monthly_price_ghs: Optional[float] = None
    firm_monthly_price_ghs: Optional[float] = None
    institution_monthly_price_ghs: Optional[float] = None
    # Yearly prices (GHS)
    student_yearly_price_ghs: Optional[float] = None
    pro_yearly_price_ghs: Optional[float] = None
    firm_yearly_price_ghs: Optional[float] = None
    institution_yearly_price_ghs: Optional[float] = None
    # Legacy
    enterprise_monthly_price_ghs: Optional[float] = None
    # Paystack plan codes (Stage 1.5) — empty string clears the slot.
    paystack_plan_student_monthly: Optional[str] = None
    paystack_plan_student_yearly: Optional[str] = None
    paystack_plan_pro_monthly: Optional[str] = None
    paystack_plan_pro_yearly: Optional[str] = None
    paystack_plan_firm_monthly: Optional[str] = None
    paystack_plan_firm_yearly: Optional[str] = None
    paystack_plan_institution_monthly: Optional[str] = None
    paystack_plan_institution_yearly: Optional[str] = None


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
        valid = ", ".join(p.value for p in PlanType)
        raise HTTPException(
            status_code=422,
            detail=f"Invalid plan '{body.plan}'. Must be one of: {valid}",
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

    updates: dict = {}

    # Daily-limit fields. -1 means unlimited; otherwise must be ≥ 1.
    limit_fields = {
        "free_tier_daily_limit": body.free_tier_daily_limit,
        "student_daily_limit": body.student_daily_limit,
        "professional_daily_limit": body.professional_daily_limit,
        "firm_daily_limit": body.firm_daily_limit,
        "institution_daily_limit": body.institution_daily_limit,
    }
    for key, value in limit_fields.items():
        if value is None:
            continue
        if value != -1 and value < 1:
            raise HTTPException(status_code=422, detail=f"{key} must be ≥ 1, or -1 for unlimited")
        updates[key] = value

    # Price fields. Must be non-negative.
    price_fields = {
        "student_monthly_price_ghs": body.student_monthly_price_ghs,
        "pro_monthly_price_ghs": body.pro_monthly_price_ghs,
        "firm_monthly_price_ghs": body.firm_monthly_price_ghs,
        "institution_monthly_price_ghs": body.institution_monthly_price_ghs,
        "student_yearly_price_ghs": body.student_yearly_price_ghs,
        "pro_yearly_price_ghs": body.pro_yearly_price_ghs,
        "firm_yearly_price_ghs": body.firm_yearly_price_ghs,
        "institution_yearly_price_ghs": body.institution_yearly_price_ghs,
        "enterprise_monthly_price_ghs": body.enterprise_monthly_price_ghs,
    }
    for key, value in price_fields.items():
        if value is None:
            continue
        if value < 0:
            raise HTTPException(status_code=422, detail=f"{key} cannot be negative")
        updates[key] = value

    # Paystack plan-code fields. Empty string is allowed (clears the slot).
    plan_code_fields = {
        "paystack_plan_student_monthly": body.paystack_plan_student_monthly,
        "paystack_plan_student_yearly": body.paystack_plan_student_yearly,
        "paystack_plan_pro_monthly": body.paystack_plan_pro_monthly,
        "paystack_plan_pro_yearly": body.paystack_plan_pro_yearly,
        "paystack_plan_firm_monthly": body.paystack_plan_firm_monthly,
        "paystack_plan_firm_yearly": body.paystack_plan_firm_yearly,
        "paystack_plan_institution_monthly": body.paystack_plan_institution_monthly,
        "paystack_plan_institution_yearly": body.paystack_plan_institution_yearly,
    }
    for key, value in plan_code_fields.items():
        if value is None:
            continue
        updates[key] = value.strip()

    if not updates:
        raise HTTPException(status_code=422, detail="No fields provided to update")

    updated = await set_platform_config(updates)
    return {"success": True, "config": updated}


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Ingestion Trigger
# ─────────────────────────────────────────────────────────────────────────────

def _serialize_run(run) -> dict:
    """Shape an IngestionRun row into the JSON the frontend expects."""
    return {
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
        "result": run.result,
        "error": run.error,
    }


async def _update_run(run_id: int, **fields) -> None:
    """Patch a single IngestionRun row by id."""
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import IngestionRun
    from sqlalchemy import update

    async with get_session() as session:
        await session.execute(
            update(IngestionRun).where(IngestionRun.id == run_id).values(**fields)
        )


async def _run_ingestion(run_id: int):
    """Execute the ingestion subprocess and persist status to PostgreSQL."""
    import subprocess
    import sys

    src_dir = Path(__file__).resolve().parents[1]
    script_path = src_dir.parent / "scripts" / "ingest_to_qdrant.py"

    logger.info(f"Admin-triggered ingestion starting: {script_path}")
    logger.info(f"Script exists: {script_path.exists()}")
    logger.info(f"DATABASE_URL configured: {bool(os.environ.get('DATABASE_URL'))}")

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=840,  # 14 min — leaves 1 min headroom before Modal's 900s limit
            cwd=str(src_dir.parent),
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n")[-30:]:
                logger.info(f"[ingestion] {line}")
        if result.stderr:
            for line in result.stderr.strip().split("\n")[-20:]:
                logger.warning(f"[ingestion-err] {line}")

        completed_at = datetime.now(timezone.utc)
        if result.returncode == 0:
            output_lines = result.stdout.strip().split("\n")
            summary_lines = [
                l for l in output_lines
                if "Chunks" in l or "ingested" in l or "Success" in l or "✓" in l or "Updated" in l or "indexed" in l
            ]
            await _update_run(
                run_id,
                status="completed",
                completed_at=completed_at,
                result={
                    "exit_code": 0,
                    "summary": "\n".join(summary_lines[-5:]) if summary_lines else "Completed successfully",
                },
            )
            logger.success("Admin-triggered ingestion completed successfully")
        else:
            await _update_run(
                run_id,
                status="failed",
                completed_at=completed_at,
                error=result.stderr[-500:] if result.stderr else "Unknown error",
            )
            logger.error(f"Admin-triggered ingestion FAILED (exit code {result.returncode})")

    except subprocess.TimeoutExpired:
        await _update_run(
            run_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error="Ingestion timed out after 14 minutes",
        )
        logger.error("Admin-triggered ingestion timed out after 840s")
    except Exception as e:
        await _update_run(
            run_id,
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error=str(e),
        )
        logger.error(f"Admin-triggered ingestion error: {e}")


@router.post("/pipeline/trigger-ingestion")
async def trigger_ingestion(
    user: dict = Depends(require_admin),
):
    """Trigger case ingestion as a dedicated Modal function.

    Returns immediately — poll GET /api/admin/pipeline/ingestion-status for progress.
    Only one ingestion can run at a time. State is persisted in PostgreSQL so it
    survives container replicas and restarts.

    Spawns the `run_ingestion` function in its own Modal container with a
    30-min timeout. If Modal dispatch fails, the run is immediately marked
    as failed (no unreliable subprocess fallback).
    """
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import IngestionRun
    from sqlalchemy import select, update

    now = datetime.now(timezone.utc)

    async with get_session() as session:
        latest = await session.execute(
            select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(1)
        )
        latest_run = latest.scalar_one_or_none()

        if latest_run and latest_run.status == "running":
            started = latest_run.started_at
            if started and (now - started) < INGESTION_STALE_AFTER:
                raise HTTPException(
                    status_code=409,
                    detail="Ingestion is already running. Please wait for it to complete.",
                )
            # Stale running row — mark it failed so a fresh run can proceed.
            await session.execute(
                update(IngestionRun)
                .where(IngestionRun.id == latest_run.id)
                .values(
                    status="failed",
                    completed_at=now,
                    error="Marked stale by trigger — process likely crashed.",
                )
            )

        new_run = IngestionRun(status="running", started_at=now)
        session.add(new_run)
        await session.flush()  # populate new_run.id before commit
        run_id = new_run.id

    # --- Spawn the dedicated Modal function ---
    dispatch_error = None
    dispatch_method = "failed"

    try:
        import modal

        # Try both Modal APIs (lookup = newer, from_name = older)
        fn = None
        for method_name, method in [
            ("lookup", getattr(modal.Function, "lookup", None)),
            ("from_name", getattr(modal.Function, "from_name", None)),
        ]:
            if method is None:
                continue
            try:
                fn = method("ghana-legal-ai", "run_ingestion")
                logger.info(f"Modal function resolved via {method_name}")
                break
            except Exception as lookup_err:
                logger.warning(f"Modal {method_name} failed: {lookup_err}")
                continue

        if fn is None:
            raise RuntimeError("Could not resolve Modal function via lookup or from_name")

        fn.spawn(run_id=run_id, max_cases=10)
        dispatch_method = "modal"
        logger.info(f"✓ Spawned Modal run_ingestion for run_id={run_id}")

    except Exception as e:
        dispatch_error = str(e)
        logger.error(f"✗ Modal dispatch FAILED: {e}")

        # Mark run as failed immediately — no unreliable subprocess fallback
        async with get_session() as session:
            await session.execute(
                update(IngestionRun)
                .where(IngestionRun.id == run_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    error=f"Modal dispatch failed: {e}",
                )
            )

    return {
        "success": dispatch_method == "modal",
        "message": (
            f"Ingestion triggered via {dispatch_method}. Poll /api/admin/pipeline/ingestion-status for progress."
            if dispatch_method == "modal"
            else f"Failed to spawn ingestion: {dispatch_error}"
        ),
        "run_id": run_id,
        "dispatch": dispatch_method,
    }


@router.get("/pipeline/ingestion-status")
async def ingestion_status(user: dict = Depends(require_admin)):
    """Get the current ingestion job status from PostgreSQL.

    If the latest run has been 'running' for longer than INGESTION_STALE_AFTER,
    it is auto-marked as failed (the process likely crashed or the container
    was recycled). This prevents the frontend from spinning forever.
    """
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import IngestionRun
    from sqlalchemy import select, update

    async with get_session() as session:
        result = await session.execute(
            select(IngestionRun).order_by(IngestionRun.created_at.desc()).limit(1)
        )
        run = result.scalar_one_or_none()

        # Auto-recover stale "running" rows
        if run and run.status == "running" and run.started_at:
            now = datetime.now(timezone.utc)
            if (now - run.started_at) > INGESTION_STALE_AFTER:
                logger.warning(
                    f"Ingestion run {run.id} has been running for >{INGESTION_STALE_AFTER}. "
                    f"Marking as failed (stale)."
                )
                await session.execute(
                    update(IngestionRun)
                    .where(IngestionRun.id == run.id)
                    .values(
                        status="failed",
                        completed_at=now,
                        error="Auto-recovered: process likely crashed or container was recycled.",
                    )
                )
                # Re-fetch after update
                result = await session.execute(
                    select(IngestionRun).where(IngestionRun.id == run.id)
                )
                run = result.scalar_one_or_none()

    if run is None:
        return {
            "status": "idle",
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
    return _serialize_run(run)


# ---------------------------------------------------------------------------
# Case Discovery (scraping ghalii.org)
# ---------------------------------------------------------------------------

DISCOVERY_STALE_AFTER = timedelta(minutes=35)


class TriggerDiscoveryBody(BaseModel):
    batch_size: Optional[int] = None  # one-off override of discovery_state.batch_size


async def _run_discovery_background(run_id: int, batch_size: Optional[int] = None):
    """Run discovery in-process as a background task.

    Fallback path when Modal dispatch fails (dev, outage, etc.) or the
    preferred path when we want discovery to run from the same container
    as the API — avoids IP-reputation differences between containers.
    """
    import json as _json
    from pathlib import Path as _Path

    logger.info(f"[discovery-bg] Starting in-process discovery for run_id={run_id}")

    def _update_discovery_run(**fields):
        """Sync helper to update discovery_runs row via psycopg."""
        try:
            import psycopg
            from psycopg.types.json import Json

            db_url = os.environ.get("DATABASE_URL", "")
            db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
            if "pooler.supabase.com" in db_url and ":5432" in db_url:
                db_url = db_url.replace(":5432", ":6543")

            set_parts = []
            values = []
            for key, val in fields.items():
                set_parts.append(f"{key} = %s")
                values.append(Json(val) if isinstance(val, dict) else val)
            values.append(run_id)

            with psycopg.connect(db_url, prepare_threshold=None) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        f"UPDATE discovery_runs SET {', '.join(set_parts)} WHERE id = %s",
                        values,
                    )
                conn.commit()
        except Exception as e:
            logger.error(f"[discovery-bg] Failed to update run {run_id}: {e}")

    try:
        import sys
        src_dir = Path(__file__).resolve().parents[1]
        scripts_dir = src_dir.parent / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        if str(src_dir.parent) not in sys.path:
            sys.path.insert(0, str(src_dir.parent))

        from scripts.discover_cases import run_discovery as _discover

        # Run blocking scraper in a thread to avoid blocking the event loop
        result = await asyncio.to_thread(
            _discover,
            batch_size_override=batch_size,
            data_dir=_Path(os.environ.get("PDF_UPLOAD_DIR", "/data")),
        )

        summary = result.get("summary") or (
            f"Scraped {result['scraped']} cases. "
            f"Found {result['new']} new. Inserted {result['inserted']}."
        )
        logger.info(f"[discovery-bg] Completed: {summary}")

        _update_discovery_run(
            status="completed",
            completed_at=datetime.now(timezone.utc),
            result={**result, "summary": summary},
        )

    except Exception as e:
        import traceback
        logger.error(f"[discovery-bg] Failed: {e}\n{traceback.format_exc()}")
        _update_discovery_run(
            status="failed",
            completed_at=datetime.now(timezone.utc),
            error=str(e)[:500],
        )


@router.post("/pipeline/trigger-discovery")
async def trigger_discovery(
    body: TriggerDiscoveryBody = TriggerDiscoveryBody(),
    user: dict = Depends(require_admin),
):
    """Trigger case discovery: scrape ghalii.org for new or archived cases.

    Returns immediately — poll GET /api/admin/pipeline/discovery-status.
    Tries to spawn a dedicated Modal function first. If that fails (dev mode,
    Modal outage, etc.), falls back to running discovery in-process as an
    ``asyncio`` background task in the current API container.

    Pipeline steps:
      1. Reads discovery_state for the current cursor + mode (backfill/incremental)
      2. Scrapes the appropriate page range from ghalii.org
      3. Filters out already-known cases
      4. Downloads PDFs for new cases
      5. Inserts new rows into pipeline_cases (status='pending')
      6. Advances the cursor (backfill) or flips to incremental at end of pagination

    Optional ``batch_size`` body field overrides the cursor's batch size for
    this run only — useful for kicking off a deeper one-off backfill.
    """
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import DiscoveryRun
    from sqlalchemy import select, update

    now = datetime.now(timezone.utc)

    async with get_session() as session:
        latest = await session.execute(
            select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(1)
        )
        latest_run = latest.scalar_one_or_none()

        if latest_run and latest_run.status == "running":
            started = latest_run.started_at
            if started and (now - started) < DISCOVERY_STALE_AFTER:
                raise HTTPException(
                    status_code=409,
                    detail="Discovery is already running. Please wait for it to complete.",
                )
            await session.execute(
                update(DiscoveryRun)
                .where(DiscoveryRun.id == latest_run.id)
                .values(
                    status="failed",
                    completed_at=now,
                    error="Marked stale by trigger — process likely crashed.",
                )
            )

        new_run = DiscoveryRun(status="running", started_at=now)
        session.add(new_run)
        await session.flush()
        run_id = new_run.id

    # --- Dispatch: try Modal first, fall back to in-process ---
    dispatch_method = "error"
    try:
        import modal
        fn = modal.Function.from_name("ghana-legal-ai", "run_discovery")
        fn.spawn(run_id=run_id, batch_size=body.batch_size)
        dispatch_method = "modal"
        logger.info(
            f"Spawned Modal run_discovery for run_id={run_id} "
            f"batch_size={body.batch_size}"
        )
    except Exception as e:
        logger.warning(f"Modal dispatch failed ({e}), falling back to in-process discovery")
        # Run discovery in-process as a background task
        asyncio.create_task(_run_discovery_background(run_id, batch_size=body.batch_size))
        dispatch_method = "in-process"

    return {
        "success": True,
        "message": f"Discovery triggered via {dispatch_method}. Poll /api/admin/pipeline/discovery-status for progress.",
        "run_id": run_id,
        "dispatch": dispatch_method,
    }


@router.get("/pipeline/discovery-status")
async def discovery_status(user: dict = Depends(require_admin)):
    """Get the current discovery job status from PostgreSQL.

    Auto-recovers stale 'running' rows after DISCOVERY_STALE_AFTER to
    prevent the frontend button from spinning forever.
    """
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import DiscoveryRun
    from sqlalchemy import select, update

    async with get_session() as session:
        result = await session.execute(
            select(DiscoveryRun).order_by(DiscoveryRun.created_at.desc()).limit(1)
        )
        run = result.scalar_one_or_none()

        # Auto-recover stale "running" rows
        if run and run.status == "running" and run.started_at:
            now = datetime.now(timezone.utc)
            if (now - run.started_at) > DISCOVERY_STALE_AFTER:
                logger.warning(
                    f"Discovery run {run.id} has been running for >{DISCOVERY_STALE_AFTER}. "
                    f"Marking as failed (stale)."
                )
                await session.execute(
                    update(DiscoveryRun)
                    .where(DiscoveryRun.id == run.id)
                    .values(
                        status="failed",
                        completed_at=now,
                        error="Auto-recovered: process likely crashed or container was recycled.",
                    )
                )
                result = await session.execute(
                    select(DiscoveryRun).where(DiscoveryRun.id == run.id)
                )
                run = result.scalar_one_or_none()

    if run is None:
        return {
            "status": "idle",
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
        }
    return _serialize_run(run)


@router.get("/pipeline/discovery-state")
async def discovery_state(user: dict = Depends(require_admin)):
    """Return the discovery cursor: mode, next page, batch size.

    Used by the admin UI to show progress through the ghalii.org backfill.
    """
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import DiscoveryState
    from sqlalchemy import select

    async with get_session() as session:
        result = await session.execute(
            select(DiscoveryState).where(DiscoveryState.id == 1)
        )
        state = result.scalar_one_or_none()

        if state is None:
            state = DiscoveryState(
                id=1,
                mode="backfill",
                backfill_next_page=1,
                batch_size=5,
            )
            session.add(state)
            await session.flush()

    return {
        "mode": state.mode,
        "backfill_next_page": state.backfill_next_page,
        "batch_size": state.batch_size,
        "backfill_completed_at": (
            state.backfill_completed_at.isoformat()
            if state.backfill_completed_at else None
        ),
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


class UpdateDiscoveryStateBody(BaseModel):
    mode: Optional[str] = None            # "backfill" or "incremental"
    backfill_next_page: Optional[int] = None  # reset cursor position
    batch_size: Optional[int] = None      # pages per discovery run


@router.put("/pipeline/discovery-state")
async def update_discovery_state_endpoint(
    body: UpdateDiscoveryStateBody,
    user: dict = Depends(require_admin),
):
    """Update discovery cursor: switch modes, reset page cursor, or change batch size.

    Use this to switch from incremental → backfill mode when there are older
    cases on ghalii.org that haven't been scraped yet. Set ``backfill_next_page``
    to control where the backfill starts (e.g. 1 to start from scratch).
    """
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import DiscoveryState
    from sqlalchemy import select

    if body.mode and body.mode not in ("backfill", "incremental"):
        raise HTTPException(status_code=422, detail="mode must be 'backfill' or 'incremental'")
    if body.backfill_next_page is not None and body.backfill_next_page < 1:
        raise HTTPException(status_code=422, detail="backfill_next_page must be ≥ 1")
    if body.batch_size is not None and (body.batch_size < 1 or body.batch_size > 50):
        raise HTTPException(status_code=422, detail="batch_size must be between 1 and 50")

    async with get_session() as session:
        result = await session.execute(
            select(DiscoveryState).where(DiscoveryState.id == 1)
        )
        state = result.scalar_one_or_none()

        if state is None:
            state = DiscoveryState(id=1, mode="backfill", backfill_next_page=1, batch_size=5)
            session.add(state)
            await session.flush()

        if body.mode:
            state.mode = body.mode
            # Clear backfill_completed_at when switching to backfill
            if body.mode == "backfill":
                state.backfill_completed_at = None
        if body.backfill_next_page is not None:
            state.backfill_next_page = body.backfill_next_page
        if body.batch_size is not None:
            state.batch_size = body.batch_size

        state.updated_at = datetime.now(timezone.utc)

    logger.info(
        f"Discovery state updated: mode={state.mode}, "
        f"next_page={state.backfill_next_page}, batch_size={state.batch_size}"
    )

    return {
        "success": True,
        "mode": state.mode,
        "backfill_next_page": state.backfill_next_page,
        "batch_size": state.batch_size,
        "backfill_completed_at": (
            state.backfill_completed_at.isoformat()
            if state.backfill_completed_at else None
        ),
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Manual Case Upload — bypass scraping by uploading downloaded PDFs directly
# ---------------------------------------------------------------------------
#
# Use case: ghalii.org's /judgments/all/ listing caps at 10 pages (~500 cases)
# and robots.txt disallows scraping the per-judgment paths and source.pdf files.
# But anyone can browse and save PDFs by hand. This endpoint lets an admin
# upload those PDFs along with the source URL, derives the canonical case_id
# from the URL with the same logic the scraper uses, persists the PDF to a
# Modal Volume, and inserts/updates a pipeline_cases row so the existing
# ingestion path picks it up automatically.

UPLOAD_DIR = Path(os.environ.get("PDF_UPLOAD_DIR", "/uploads/cases"))
MAX_UPLOAD_BYTES = 25 * 1024 * 1024  # 25 MB per PDF — generous; ghalii PDFs run 1-5 MB


def _classify_uploaded_pdf(url: str):
    """Parse a ghalii.org URL into (case_id, court_id, normalized_pdf_url).

    Mirrors the scraper logic in scripts.discover_cases so case_ids are stable
    whether a case arrived via discovery or manual upload.
    """
    from scripts.discover_cases import case_id_from_url, court_id_from_url, BASE_URL
    from urllib.parse import urljoin

    url = (url or "").strip()
    if not url:
        raise ValueError("URL is empty")

    if url.startswith("/"):
        url = urljoin(BASE_URL, url)

    # Reasonable shape check — the scraper expects /judgment/<slug>/<year>/<num>/
    if "/judgment/" not in url:
        raise ValueError(f"URL does not look like a ghalii judgment page: {url}")

    case_id = case_id_from_url(url)
    court_id = court_id_from_url(url)

    # The PDF URL is the page URL with /source.pdf appended (same convention
    # as the scraper). Stored as a fallback only — ingestion will prefer the
    # locally-saved PDF on the Modal Volume.
    pdf_url = urljoin(BASE_URL, url.rstrip("/") + "/source.pdf")

    return case_id, court_id, pdf_url


@router.post("/pipeline/upload-cases")
async def upload_cases(
    files: list[UploadFile] = File(..., description="One or more PDF files"),
    urls: str = Form(..., description="Newline- or comma-separated ghalii URLs (must match files in order)"),
    titles: Optional[str] = Form(None, description="Optional newline-separated titles, one per file"),
    user: dict = Depends(require_admin),
):
    """Bulk-upload manually-downloaded judgment PDFs paired with their URLs.

    Pairing is by upload order: file[i] is paired with url[i]. The endpoint
    derives ``case_id`` and ``court_id`` from each URL using the same logic
    the scraper uses, writes the PDF to a Modal Volume at
    ``/uploads/cases/{court_id}/{case_id}.pdf``, and upserts a
    ``pipeline_cases`` row with status='downloaded'. Run ingestion afterwards.
    """
    # --- Parse URLs / titles ---
    url_list = [u.strip() for u in urls.replace(",", "\n").splitlines() if u.strip()]
    title_list = (
        [t.strip() for t in titles.splitlines()]
        if titles is not None
        else [""] * len(url_list)
    )

    if len(url_list) != len(files):
        raise HTTPException(
            status_code=400,
            detail=f"Mismatch: got {len(files)} files but {len(url_list)} URLs.",
        )

    if titles is not None and len(title_list) != len(files):
        raise HTTPException(
            status_code=400,
            detail=f"Mismatch: {len(title_list)} titles but {len(files)} files.",
        )

    # --- Process pairs ---
    accepted: list[dict] = []
    errors: list[dict] = []

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    for idx, (upload, url) in enumerate(zip(files, url_list)):
        filename = upload.filename or f"upload_{idx}.pdf"
        title_hint = title_list[idx] if idx < len(title_list) else ""
        try:
            # Validate URL → derive metadata
            case_id, court_id, pdf_url = _classify_uploaded_pdf(url)

            # Read + validate PDF magic bytes + size cap
            content = await upload.read()
            if len(content) > MAX_UPLOAD_BYTES:
                raise ValueError(
                    f"File too large ({len(content)//1024} KB > {MAX_UPLOAD_BYTES//1024} KB)"
                )
            if not content[:4] == b"%PDF":
                raise ValueError("Not a valid PDF (missing %PDF header)")

            # Persist to volume
            court_dir = UPLOAD_DIR / court_id
            court_dir.mkdir(parents=True, exist_ok=True)
            dest = court_dir / f"{case_id}.pdf"
            dest.write_bytes(content)

            # UPSERT pipeline_cases via psycopg (sync — small batches, fine)
            await _upsert_uploaded_case(
                case_id=case_id,
                url=url,
                pdf_url=pdf_url,
                title=title_hint or filename.replace(".pdf", ""),
                court_id=court_id,
                pdf_path=str(dest),
            )

            accepted.append({
                "filename": filename,
                "case_id": case_id,
                "court_id": court_id,
                "pdf_path": str(dest),
                "size_kb": len(content) // 1024,
            })
            logger.info(f"✓ Uploaded {case_id} → {dest}")

        except Exception as e:
            errors.append({"filename": filename, "url": url, "error": str(e)})
            logger.error(f"✗ Upload failed for {filename}: {e}")
        finally:
            await upload.close()

    # Persist Modal Volume changes so the ingestion container sees them.
    try:
        import modal
        vol = modal.Volume.from_name("ghana-legal-pdfs", create_if_missing=True)
        vol.commit()
    except Exception as e:
        # In local dev (no Modal), commit isn't applicable — that's OK.
        logger.debug(f"Volume commit skipped: {e}")

    return {
        "accepted": accepted,
        "errors": errors,
        "accepted_count": len(accepted),
        "error_count": len(errors),
    }


async def _upsert_uploaded_case(
    *, case_id: str, url: str, pdf_url: str, title: str, court_id: str, pdf_path: str,
) -> None:
    """Insert the case as 'downloaded', or reset an existing row to
    'downloaded' so it gets re-ingested cleanly with the new PDF."""
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import PipelineCase
    from sqlalchemy import select, update as sql_update

    async with get_session() as session:
        existing = await session.execute(
            select(PipelineCase).where(PipelineCase.case_id == case_id)
        )
        row = existing.scalar_one_or_none()

        if row is None:
            session.add(PipelineCase(
                case_id=case_id,
                url=url,
                pdf_url=pdf_url,
                title=title,
                court_id=court_id,
                pdf_path=pdf_path,
                status="downloaded",
                error=None,
                retry_count=0,
            ))
        else:
            await session.execute(
                sql_update(PipelineCase)
                .where(PipelineCase.case_id == case_id)
                .values(
                    url=url,
                    pdf_url=pdf_url,
                    title=title or row.title,
                    court_id=court_id,
                    pdf_path=pdf_path,
                    status="downloaded",
                    error=None,
                )
            )

@router.get("/feedback")
async def get_all_feedback(user: dict = Depends(require_admin)):
    """Get all user feedback for the admin panel."""
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import UserFeedback
    from sqlalchemy import select

    try:
        async with get_session() as session:
            result = await session.execute(
                select(UserFeedback).order_by(UserFeedback.created_at.desc())
            )
            feedbacks = result.scalars().all()
            return {"feedbacks": [
                {
                    "id": f.id,
                    "clerk_id": f.clerk_id,
                    "name": f.name,
                    "content": f.content,
                    "created_at": f.created_at.isoformat()
                }
                for f in feedbacks
            ]}
    except Exception as e:
        logger.error(f"Failed to load all feedback: {e}")
        return {"feedbacks": []}


@router.get("/payments")
async def list_payments(
    user: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    status: Optional[str] = Query(None, description="Filter by payment status"),
    search: str = Query("", description="Filter by email, clerk_id, or reference"),
):
    """Paginated audit list of verified Paystack payments.

    Backs the admin Payments tab. Ordered newest-first by paid_at (falling
    back to created_at for legacy rows that pre-date paid_at being captured).
    """
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import Payment
    from sqlalchemy import select, func, or_

    async with get_session() as session:
        query = select(Payment)
        count_query = select(func.count(Payment.id))

        if status:
            query = query.where(Payment.status == status)
            count_query = count_query.where(Payment.status == status)

        if search:
            pattern = f"%{search.strip()}%"
            search_filter = or_(
                Payment.email.ilike(pattern),
                Payment.clerk_id.ilike(pattern),
                Payment.reference.ilike(pattern),
            )
            query = query.where(search_filter)
            count_query = count_query.where(search_filter)

        total_result = await session.execute(count_query)
        total = total_result.scalar() or 0

        offset = (page - 1) * per_page
        query = (
            query.order_by(Payment.paid_at.desc().nullslast(), Payment.created_at.desc())
            .offset(offset)
            .limit(per_page)
        )
        result = await session.execute(query)
        payments = result.scalars().all()

        # Aggregate totals (across all matching rows, not just this page)
        totals_result = await session.execute(
            select(
                func.coalesce(func.sum(Payment.amount_ghs), 0),
                func.count(Payment.id),
            ).where(Payment.status == "success")
        )
        total_amount, success_count = totals_result.one()

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_revenue_ghs": float(total_amount or 0),
        "successful_payments": int(success_count or 0),
        "payments": [
            {
                "id": p.id,
                "reference": p.reference,
                "clerk_id": p.clerk_id,
                "email": p.email,
                "amount_ghs": p.amount_ghs,
                "currency": p.currency,
                "status": p.status,
                "plan": p.plan.value if p.plan else None,
                "channel": p.channel,
                "source": p.source,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ],
    }


@router.delete("/feedback/{feedback_id}")
async def delete_feedback(feedback_id: int, user: dict = Depends(require_admin)):
    """Delete a user feedback entry."""
    from ghana_legal.infrastructure.database import get_session
    from ghana_legal.domain.models import UserFeedback
    from sqlalchemy import select

    try:
        async with get_session() as session:
            result = await session.execute(
                select(UserFeedback).where(UserFeedback.id == feedback_id)
            )
            feedback = result.scalar_one_or_none()
            if not feedback:
                raise HTTPException(status_code=404, detail="Feedback not found")
            
            await session.delete(feedback)
            # The session context manager handles commit
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete feedback {feedback_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
