"""Small shared helpers: dates, hashing, CSV reading."""
from __future__ import annotations

import csv
import hashlib
import io
import json
from datetime import datetime, timezone
from pathlib import Path

DATE_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S%z",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
)


def parse_dt(value: str | None) -> datetime | None:
    """Parse the date formats seen in HubSpot exports and spreadsheets. Returns UTC or None.

    Slash dates are read as day/month/year (UK exports). Unparseable values return None
    and the caller records a data-quality note rather than guessing.
    """
    if value is None:
        return None
    v = str(value).strip()
    if not v:
        return None
    if v.endswith("Z") and "T" in v and len(v) > 20:  # e.g. 2026-11-01T09:00:00.000Z
        v = v[:19] + "Z"
    for fmt in DATE_FORMATS:
        try:
            dt = datetime.strptime(v, fmt)
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    return None


def iso(dt: datetime | None) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if dt else ""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path) -> str:
    return sha256_bytes(Path(path).read_bytes())


def canonical_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_csv(path: str | Path) -> list[dict]:
    """Read a CSV, skipping leading comment lines that start with '#'.

    The sample files start with a '# SYNTHETIC DATA' line so nobody mistakes them for real contacts.
    """
    text = Path(path).read_text(encoding="utf-8-sig")
    lines = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    reader = csv.DictReader(io.StringIO("\n".join(lines)))
    rows = []
    for row in reader:
        rows.append({(k or "").strip(): (v if v is not None else "") for k, v in row.items()})
    return rows


def write_csv(path: str | Path, rows: list[dict], fields: list[str]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def truthy(value: str | None) -> bool | None:
    """Messy yes/no values. Returns None when the value is blank or unrecognised."""
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in {"true", "yes", "y", "1", "x", "opted out", "unsubscribed"}:
        return True
    if v in {"false", "no", "n", "0"}:
        return False
    return None
