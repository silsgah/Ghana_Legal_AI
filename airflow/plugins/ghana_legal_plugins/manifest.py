"""Pipeline manifest for tracking case processing state."""

import json
import os
import tempfile
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CaseRecord:
    case_id: str
    url: str
    pdf_url: str
    title: str
    court_id: str
    status: str = "discovered"  # discovered | downloaded | validated | indexed | failed
    discovered_at: str = ""
    updated_at: str = ""
    metadata: Dict = field(default_factory=dict)
    error: Optional[str] = None
    retry_count: int = 0

    def __post_init__(self):
        now = datetime.utcnow().isoformat()
        if not self.discovered_at:
            self.discovered_at = now
        if not self.updated_at:
            self.updated_at = now


class PipelineManifest:
    """Persistent JSON manifest for tracking case lifecycle.

    Case lifecycle: discovered -> downloaded -> validated -> indexed
                                    |              |
                                  failed         failed
    """

    def __init__(self, manifest_path: str):
        self.path = Path(manifest_path)
        self.cases: Dict[str, CaseRecord] = {}
        self._load()

    def _load(self):
        if self.path.exists():
            data = json.loads(self.path.read_text())
            for case_id, record in data.get("cases", {}).items():
                self.cases[case_id] = CaseRecord(**record)

    def _save(self):
        """Atomic save via tempfile + os.replace."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {"cases": {cid: asdict(rec) for cid, rec in self.cases.items()}}
        fd, tmp_path = tempfile.mkstemp(
            dir=str(self.path.parent), suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp_path, str(self.path))
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def add_case(self, record: CaseRecord) -> bool:
        """Add a case if not already tracked. Returns True if new."""
        if record.case_id in self.cases:
            return False
        self.cases[record.case_id] = record
        self._save()
        return True

    def update_case(self, case_id: str, **kwargs):
        """Update fields on an existing case record."""
        if case_id not in self.cases:
            return
        record = self.cases[case_id]
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        record.updated_at = datetime.utcnow().isoformat()
        self._save()

    def get_cases_by_status(self, status: str, court_id: Optional[str] = None) -> List[CaseRecord]:
        results = []
        for rec in self.cases.values():
            if rec.status == status:
                if court_id is None or rec.court_id == court_id:
                    results.append(rec)
        return results

    def get_failed_retriable(self, max_retries: int = 3) -> List[CaseRecord]:
        """Get failed cases that haven't exceeded retry limit."""
        return [
            rec for rec in self.cases.values()
            if rec.status == "failed" and rec.retry_count < max_retries
        ]

    def get_record(self, case_id: str) -> Optional[CaseRecord]:
        return self.cases.get(case_id)
