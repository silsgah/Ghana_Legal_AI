#!/usr/bin/env python3
"""
Scratch script: Reset all 'indexed' entries in pipeline_manifest.json back to 'pending'.

When switching embedding models, all previously indexed documents must be re-processed.
This script resets the manifest status so the pipeline will re-embed every PDF file
using the new voyage-law-2 model on the next run.

Usage (from project root):
    python legal-api/src/scratch/reset_pipeline_manifest.py
"""
import json
import shutil
from pathlib import Path
from datetime import datetime

MANIFEST_PATH = Path(__file__).resolve().parents[3] / "data" / "pipeline_manifest.json"


def main():
    if not MANIFEST_PATH.exists():
        print(f"❌  Manifest not found at: {MANIFEST_PATH}")
        return

    print(f"Loading manifest: {MANIFEST_PATH}")

    with open(MANIFEST_PATH, "r") as f:
        manifest = json.load(f)

    # Count current statuses
    cases = manifest.get("cases", {})
    status_counts: dict = {}
    for case in cases.values():
        s = case.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    print(f"\nCurrent status distribution across {len(cases)} cases:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")

    indexed_count = status_counts.get("indexed", 0)
    if indexed_count == 0:
        print("\n✅  No 'indexed' entries found — nothing to reset.")
        return

    confirm = input(f"\n⚠️  Reset {indexed_count} 'indexed' entries to 'pending'? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted — manifest unchanged.")
        return

    # Backup the manifest first
    backup_path = MANIFEST_PATH.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    shutil.copy2(MANIFEST_PATH, backup_path)
    print(f"\n📦  Backup saved to: {backup_path.name}")

    # Reset all 'indexed' -> 'pending'
    reset_count = 0
    for case_id, case in cases.items():
        if case.get("status") == "indexed":
            case["status"] = "pending"
            case["updated_at"] = datetime.now().isoformat()
            reset_count += 1

    manifest["cases"] = cases

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"✅  Reset {reset_count} cases from 'indexed' → 'pending'.")
    print(f"\nNext step: run the pipeline ingestion to re-embed with voyage-law-2.")

if __name__ == "__main__":
    main()
