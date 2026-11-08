"""Hash-chained JSONL audit trail.

Each line holds prev_hash and hash = sha256(prev_hash + canonical JSON of the record without hash).
Editing, deleting or reordering any line breaks verify(). The trail records decisions, gate
results, model fallbacks, approvals and releases. It never stores note text.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .util import canonical_json, sha256_bytes

GENESIS = "0" * 64


class AuditLog:
    def __init__(self, path: str | Path, clock=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self._last, self._seq = self._tail()

    def _tail(self):
        if not self.path.exists():
            return GENESIS, 0
        last, seq = GENESIS, 0
        for line in self.path.read_text().splitlines():
            if line.strip():
                rec = json.loads(line)
                last, seq = rec["hash"], rec["seq"]
        return last, seq

    def append(self, record: dict) -> dict:
        self._seq += 1
        rec = {"seq": self._seq, "ts": self.clock().strftime("%Y-%m-%dT%H:%M:%SZ"), **record, "prev_hash": self._last}
        rec["hash"] = sha256_bytes((self._last + canonical_json(rec)).encode())
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True, ensure_ascii=False) + "\n")
        self._last = rec["hash"]
        return rec


def verify(path: str | Path) -> tuple[bool, str]:
    p = Path(path)
    if not p.exists():
        return False, "missing"
    prev, expected_seq = GENESIS, 1
    for n, line in enumerate(p.read_text().splitlines(), 1):
        if not line.strip():
            continue
        rec = json.loads(line)
        h = rec.pop("hash", None)
        if rec.get("prev_hash") != prev:
            return False, f"line {n}: prev_hash mismatch"
        if rec.get("seq") != expected_seq:
            return False, f"line {n}: sequence gap"
        if sha256_bytes((prev + canonical_json(rec)).encode()) != h:
            return False, f"line {n}: hash mismatch"
        prev, expected_seq = h, expected_seq + 1
    return True, f"ok ({expected_seq - 1} records)"
