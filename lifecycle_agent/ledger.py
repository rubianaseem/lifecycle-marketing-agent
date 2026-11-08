"""Play ledger: makes re-runs idempotent.

A play is identified by key = sha256(contact_id | play | policy_version). If the same play for the
same contact was already proposed by an earlier run inside the cooldown window, the new run marks
it DUPLICATE and leaves it out of the import. Replaying the SAME run_id reproduces the same
artifacts instead of being treated as a duplicate.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .util import parse_dt, sha256_bytes


def play_key(contact_id: str, play: str, policy_version: str) -> str:
    return sha256_bytes(f"{contact_id}|{play}|{policy_version}".encode())[:24]


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, dict] = json.loads(self.path.read_text()) if self.path.exists() else {}

    def check(self, key: str, run_id: str, as_of: datetime, cooldown_days: int) -> str:
        """Returns 'new', 'same_run' or 'duplicate'."""
        e = self.entries.get(key)
        if not e:
            return "new"
        if e["run_id"] == run_id:
            return "same_run"
        prev = parse_dt(e["as_of"])
        if prev and as_of - prev < timedelta(days=cooldown_days):
            return "duplicate"
        return "new"

    def record(self, key: str, run_id: str, as_of: datetime, contact_id: str, play: str) -> None:
        self.entries[key] = {"run_id": run_id, "as_of": as_of.strftime("%Y-%m-%dT%H:%M:%SZ"),
                             "contact_id": contact_id, "play": play}

    def save(self) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.entries, indent=1, sort_keys=True))
        tmp.replace(self.path)
