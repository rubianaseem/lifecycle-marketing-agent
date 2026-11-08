#!/usr/bin/env python3
"""End-to-end demo on the synthetic sample data. No API key, no network, no CRM.

Approvals in this demo are SIMULATED: the script plays the part of Rubia approving a specific
file by its hash, exactly as a person would with `agent.py approve`. It exists to show which
actions the gate allows and refuses. It is not permission to touch a real CRM.
"""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

from lifecycle_agent.approval import ApprovalError, approve, release
from lifecycle_agent.audit import verify
from lifecycle_agent.pipeline import SimulatedCrash, StaleSnapshot, load_policy, run
from lifecycle_agent.util import parse_dt, sha256_file

ROOT = Path(__file__).resolve().parent
AS_OF = parse_dt("2026-11-08T12:00:00Z")
LINES: list[str] = []


def say(text=""):
    print(text)
    LINES.append(text)


def attempt(label, fn):
    try:
        out = fn()
        say(f"  {label:<52} ALLOWED  {out if isinstance(out, str) else ''}".rstrip())
    except (ApprovalError, StaleSnapshot) as exc:
        say(f"  {label:<52} REFUSED  {exc}")


def copy_data(dst: Path, exported_at: str, extra_event: str = ""):
    dst.mkdir(parents=True, exist_ok=True)
    for f in ROOT.glob("sample_*.csv"):
        shutil.copyfile(f, dst / f.name)
    if extra_event:
        with open(dst / "sample_engagement.csv", "a") as fh:
            fh.write(extra_event + "\n")
    m = json.loads((ROOT / "sample_export_manifest.json").read_text())
    m["exported_at"] = exported_at
    (dst / "sample_export_manifest.json").write_text(json.dumps(m, indent=2))


def main() -> int:
    policy = load_policy(ROOT / "config/policy.json")
    approvers = json.loads((ROOT / "config/approvers.json").read_text())
    tmp = Path(tempfile.mkdtemp(prefix="lma-demo-"))
    state, out = tmp / "state", tmp / "outputs"

    say("1. Run on the sample snapshot (offline rules and templates, as of 2026-11-08 12:00 UTC)")
    res = run(ROOT, out, state, AS_OF, policy)
    rd = Path(res["run_dir"])
    s = res["summary"]
    say(f"  contacts {s['contacts']} | proposed {s['by_status'].get('PROPOSED', 0)} | held for eligibility {s['email_plays_blocked_by_consent']}"
        f" | deferred by caps {s['deferred_by_frequency_cap']} | review {s['by_status'].get('REVIEW', 0)}"
        f" | quarantined text {s['quarantined_texts']} | import rows {s['import_rows']}")
    say("  plays proposed: " + ", ".join(f"{k} {v}" for k, v in s["by_play_proposed"].items()))

    say("\n2. Approval gate (SIMULATED approvals on synthetic data)")
    imp = "hubspot_import_proposed.csv"
    h = sha256_file(rd / imp)
    now = AS_OF + timedelta(hours=1)
    attempt("release import before any approval", lambda: str(release(rd, imp, now, policy)))
    attempt("content reviewer approves the import", lambda: approve(rd, imp, h, "content-reviewer", now, approvers, policy) and "")
    attempt("approve with a 12-character hash prefix", lambda: approve(rd, imp, h[:12], "rubia", now, approvers, policy) and "")
    attempt("approve with the hash of a different file", lambda: approve(rd, imp, sha256_file(rd / "brief.md"), "rubia", now, approvers, policy) and "")
    attempt("Rubia approves the import with its full hash", lambda: approve(rd, imp, h, "rubia", now, approvers, policy) and "")
    attempt("release the approved import", lambda: "-> released/" + release(rd, imp, now, policy).name)
    crit = "list_criteria.json"
    approve(rd, crit, sha256_file(rd / crit), "rubia", now, approvers, policy)
    original = (rd / crit).read_bytes()
    with open(rd / crit, "a") as fh:
        fh.write(" ")  # one byte added after approval
    attempt("release list criteria edited after approval", lambda: str(release(rd, crit, now, policy)))
    (rd / crit).write_bytes(original)  # put the reviewed file back for the example folder
    attempt("release the import 4 days later (expired)", lambda: str(release(rd, imp, AS_OF + timedelta(days=4), policy)))

    say("\n3. Re-run the next day on a fresh export (idempotency)")
    day2 = tmp / "day2"
    copy_data(day2, "2026-11-09T07:30:00Z", "E-0040,1033,,Demo Request,2026-11-09 09:00,")
    say("  the new export adds one event: contact 1033 requests a demo")
    res2 = run(day2, out, state, AS_OF + timedelta(days=1), policy)
    s2 = res2["summary"]
    say(f"  plays already proposed yesterday, skipped: {s2['duplicates_skipped']} | new import rows: {s2['import_rows']}"
        f" ({', '.join(f'{k} {v}' for k, v in s2['by_play_proposed'].items())})")

    say("\n4. Crash after planning, then resume")
    state3 = tmp / "state3"
    try:
        run(ROOT, tmp / "out3", state3, AS_OF, policy, fail_after="plan")
    except SimulatedCrash as exc:
        say(f"  first attempt: {exc}")
    res3 = run(ROOT, tmp / "out3", state3, AS_OF, policy)
    same = sha256_file(Path(res3["run_dir"]) / imp) == h
    say(f"  second attempt: {res3['status']}; import identical to the uninterrupted run: {same}")
    res3b = run(ROOT, tmp / "out3", state3, AS_OF, policy)
    say(f"  third attempt with the same inputs: {res3b['status']} (nothing rewritten)")

    say("\n5. Stale snapshot (the same export used 40 hours later)")
    try:
        run(ROOT, tmp / "out4", tmp / "state4", AS_OF + timedelta(hours=40), policy)
    except StaleSnapshot as exc:
        say(f"  run refused: {exc}")
    res4 = run(ROOT, tmp / "out4", tmp / "state4", AS_OF + timedelta(hours=40), policy, allow_stale=True)
    rd4 = Path(res4["run_dir"])
    attempt("approve import from a --allow-stale run", lambda: approve(rd4, imp, sha256_file(rd4 / imp), "rubia",
                                                                      AS_OF + timedelta(hours=40), approvers, policy) and "")

    say("\n6. Audit trail")
    ok, why = verify(state / "audit.jsonl")
    say(f"  run audit log: {'intact' if ok else 'BROKEN'} ({why})")
    ok, why = verify(rd / "decisions.jsonl")
    say(f"  decision trace: {'intact' if ok else 'BROKEN'} ({why})")
    forged = tmp / "forged.jsonl"
    text = (rd / "decisions.jsonl").read_text().replace('"play": "SUPPRESS"', '"play": "NURTURE_EDUCATION"', 1)
    forged.write_text(text)
    ok, why = verify(forged)
    say(f"  decision trace with one SUPPRESS edited to NURTURE: {'intact' if ok else 'BROKEN'} ({why})")

    # Keep the main run as the committed example (overwrite previous example files).
    dest = ROOT / "outputs" / "sample_run"
    shutil.copytree(rd, dest, dirs_exist_ok=True)
    (ROOT / "outputs" / "demo_transcript.txt").write_text("\n".join(LINES) + "\n")
    say(f"\nExample run copied to outputs/sample_run/. Scratch files in {tmp}. Nothing was sent or written to a CRM.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
