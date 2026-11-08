"""Play ledger: makes re-runs idempotent.

Email plays use key = sha256(contact_id | play | policy_version) and a cooldown window.
A sales task that belongs to one real event (an MQL creation, or one set of open deals)
uses key = sha256(contact_id | play | event identity) with no cooldown and no policy version.
The same event is not proposed again on a later snapshot. A different event gets a new key.
Replaying the SAME run_id reproduces the same artifacts instead of being treated as a duplicate.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from .util import parse_dt, sha256_bytes


def play_key(contact_id: str, play: str, policy_version: str) -> str:
    return sha256_bytes(f"{contact_id}|{play}|{policy_version}".encode())[:24]


def task_event_key(contact_id: str, play: str, identity: str) -> str:
    """Stable key for one task event. Policy version is not included, so a wording change does not create a second task."""
    return sha256_bytes(f"{contact_id}|{play}|{identity}".encode())[:24]


class Ledger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: dict[str, dict] = json.loads(self.path.read_text()) if self.path.exists() else {}

    def check(self, key: str, run_id: str, as_of: datetime, cooldown_days: int | None) -> str:
        """Returns 'new', 'same_run' or 'duplicate'.

        cooldown_days None means the key is an event: any earlier run already proposed it,
        and a later snapshot must not propose it again.
        """
        e = self.entries.get(key)
        if not e:
            return "new"
        if e["run_id"] == run_id:
            return "same_run"
        if cooldown_days is None:
            return "duplicate"
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
