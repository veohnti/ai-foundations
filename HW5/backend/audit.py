"""Append-only audit trail at output/audit_trail.json.

The file is JSON Lines: one JSON object per line, one line per event. It is
only ever opened in append mode, so earlier runs are never rewritten or
erased; the file only grows.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

AUDIT_PATH = Path(__file__).resolve().parent.parent / "output" / "audit_trail.json"


class AuditTrail:
    def __init__(self, run_id: str, path: Path = AUDIT_PATH):
        self.run_id = run_id
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **data: Any) -> None:
        record = {"ts": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "run_id": self.run_id, "event": event, **data}
        with self.path.open("a", encoding="utf-8") as f:  # append only, never "w"
            f.write(json.dumps(record, default=str) + "\n")
