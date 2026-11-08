"""Enforced human approval.

Rules enforced in code (each has a test):
  - Only artifacts marked approvable in manifest.json can be approved or released.
  - The approver must be listed in config/approvers.json for that artifact.
  - The approver must supply the full SHA-256 of the file they reviewed. It must match the file
    on disk AND the hash the run generated. There is no flag that approves without a hash.
  - Runs built on a stale snapshot cannot be approved.
  - release() re-hashes the file. Any change after approval (one byte) refuses the release.
  - Approvals expire after approval_ttl_hours and are written to a hash-chained approvals.jsonl.
Release only copies the file into released/. Uploading it to HubSpot stays a manual step.
"""
from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from .audit import AuditLog, verify
from .util import parse_dt, sha256_file


class ApprovalError(Exception):
    pass


def _manifest(run_dir: Path) -> dict:
    p = run_dir / "manifest.json"
    if not p.exists():
        raise ApprovalError("no manifest.json in run directory")
    return json.loads(p.read_text())


def snapshot_age_hours(manifest: dict, now: datetime) -> float | None:
    exported = parse_dt(manifest.get("exported_at"))
    return None if exported is None else round((now - exported).total_seconds() / 3600, 1)


def approve(run_dir, artifact: str, sha256: str, approver_id: str, now: datetime,
            approvers: dict, policy: dict) -> dict:
    run_dir = Path(run_dir)
    m = _manifest(run_dir)
    art = m["artifacts"].get(artifact)
    if not art or not art.get("approvable"):
        raise ApprovalError(f"{artifact} is not an approvable artifact")
    who = approvers.get("approvers", {}).get(approver_id)
    if not who:
        raise ApprovalError(f"unknown approver '{approver_id}'")
    if artifact not in who["artifacts"]:
        raise ApprovalError(f"approver '{approver_id}' may not approve {artifact}")
    if not re.fullmatch(r"[0-9a-f]{64}", sha256 or ""):
        raise ApprovalError("approval needs the full 64-character SHA-256 shown by `agent.py show`")
    current = sha256_file(run_dir / artifact)
    if sha256 != current:
        raise ApprovalError("hash does not match the file on disk; review the current file and use its hash")
    if current != art["sha256"]:
        raise ApprovalError("file differs from what this run generated; re-run the agent instead of editing outputs")
    if m.get("stale"):
        raise ApprovalError("run was built on a stale snapshot; re-export from HubSpot and re-run")
    age = snapshot_age_hours(m, now)
    if age is None or age > policy["snapshot_max_age_hours"]:
        raise ApprovalError(f"snapshot is {age} hours old (limit {policy['snapshot_max_age_hours']}); re-export and re-run")
    log = AuditLog(run_dir / "approvals.jsonl", clock=lambda: now)
    rec = log.append({"event": "approved", "artifact": artifact, "sha256": sha256, "approver": approver_id,
                      "approver_name": who["name"], "run_id": m["run_id"],
                      "expires_at": (now + timedelta(hours=policy["approval_ttl_hours"])).strftime("%Y-%m-%dT%H:%M:%SZ")})
    return rec


def release(run_dir, artifact: str, now: datetime, policy: dict) -> Path:
    run_dir = Path(run_dir)
    m = _manifest(run_dir)
    art = m["artifacts"].get(artifact)
    if not art or not art.get("approvable"):
        raise ApprovalError(f"{artifact} is not a releasable artifact")
    ap = run_dir / "approvals.jsonl"
    if not ap.exists():
        raise ApprovalError(f"{artifact} has not been approved")
    ok, why = verify(ap)
    if not ok:
        raise ApprovalError(f"approvals log failed verification: {why}")
    recs = [json.loads(l) for l in ap.read_text().splitlines() if l.strip()]
    mine = [r for r in recs if r.get("artifact") == artifact and r.get("event") == "approved"]
    if not mine:
        raise ApprovalError(f"{artifact} has not been approved")
    last = mine[-1]
    current = sha256_file(run_dir / artifact)
    if current != last["sha256"]:
        raise ApprovalError("file changed after approval (hash mismatch); approval is void")
    if now > parse_dt(last["expires_at"]):
        raise ApprovalError("approval expired; review and approve again")
    age = snapshot_age_hours(m, now)
    if age is None or age > policy["snapshot_max_age_hours"]:
        raise ApprovalError(f"snapshot is now {age} hours old; re-export and re-run before releasing")
    out = run_dir / "released" / artifact
    out.parent.mkdir(exist_ok=True)
    shutil.copyfile(run_dir / artifact, out)
    if sha256_file(out) != last["sha256"]:
        raise ApprovalError("copy verification failed")
    (out.parent / f"{artifact}.release.json").write_text(json.dumps({
        "artifact": artifact, "sha256": current, "approved_by": last["approver_name"],
        "approved_at": last["ts"], "released_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "next_step": "Manual: import or build this in HubSpot yourself. The agent performs no CRM writes."}, indent=2))
    AuditLog(ap, clock=lambda: now).append({"event": "released", "artifact": artifact, "sha256": current,
                                            "run_id": m["run_id"]})
    return out
