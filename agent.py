#!/usr/bin/env python3
"""Lifecycle marketing agent CLI.

  python agent.py run      --data . --as-of 2026-11-08T12:00:00Z
  python agent.py show     --run-dir outputs/run_<id>
  python agent.py approve  --run-dir outputs/run_<id> --artifact hubspot_import_proposed.csv --sha256 <hash> --approver rubia
  python agent.py release  --run-dir outputs/run_<id> --artifact hubspot_import_proposed.csv
  python agent.py verify   --path state/audit.jsonl

The agent only writes local files. It never writes to HubSpot, sends email or deletes records.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from lifecycle_agent.approval import ApprovalError, approve, release
from lifecycle_agent.audit import verify
from lifecycle_agent.llm import get_client
from lifecycle_agent.pipeline import SimulatedCrash, StaleSnapshot, load_policy, run
from lifecycle_agent.util import parse_dt, sha256_file


def _when(value):
    if not value:
        return datetime.now(timezone.utc)
    dt = parse_dt(value)
    if dt is None:
        sys.exit(f"could not parse time: {value}")
    return dt


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--data", default=".")
    r.add_argument("--prefix", default="sample_")
    r.add_argument("--out", default="outputs")
    r.add_argument("--state", default="state")
    r.add_argument("--policy", default="config/policy.json")
    r.add_argument("--as-of", help="UTC time to evaluate recency against (default: now)")
    r.add_argument("--allow-stale", action="store_true", help="run on an old snapshot; outputs cannot be approved")
    s = sub.add_parser("show")
    s.add_argument("--run-dir", required=True)
    a = sub.add_parser("approve")
    a.add_argument("--run-dir", required=True)
    a.add_argument("--artifact", required=True)
    a.add_argument("--sha256", required=True, help="full hash of the file you reviewed (from `show`)")
    a.add_argument("--approver", required=True)
    a.add_argument("--approvers", default="config/approvers.json")
    a.add_argument("--policy", default="config/policy.json")
    a.add_argument("--now")
    rl = sub.add_parser("release")
    rl.add_argument("--run-dir", required=True)
    rl.add_argument("--artifact", required=True)
    rl.add_argument("--policy", default="config/policy.json")
    rl.add_argument("--now")
    v = sub.add_parser("verify")
    v.add_argument("--path", required=True)
    args = ap.parse_args(argv)

    if args.cmd == "run":
        policy = load_policy(args.policy)
        client = get_client()
        print(f"Mode: {'Claude (ANTHROPIC_API_KEY set)' if client else 'offline rules and templates (no API key)'}")
        try:
            res = run(args.data, args.out, args.state, _when(args.as_of), policy, client=client,
                      allow_stale=args.allow_stale, prefix=args.prefix)
        except StaleSnapshot as exc:
            print(f"REFUSED: {exc}")
            return 3
        except SimulatedCrash as exc:
            print(f"CRASHED: {exc}. Run the same command again to resume.")
            return 4
        print(f"Run {res['run_id']} {res['status']} -> {res['run_dir']}")
        print(json.dumps(res["summary"], indent=2))
        print("Nothing was written to HubSpot. Review, then approve with `agent.py show` / `agent.py approve`.")
        return 0
    if args.cmd == "show":
        m = json.loads((Path(args.run_dir) / "manifest.json").read_text())
        print(f"Run {m['run_id']}  as of {m['as_of']}  snapshot age {m['age_hours']}h  stale={m['stale']}  mode={m['mode']}")
        for name, art in m["artifacts"].items():
            cur = sha256_file(Path(args.run_dir) / name)
            flag = "" if cur == art["sha256"] else "  CHANGED SINCE GENERATION"
            print(f"  {art['status']:<22} {name:<30} sha256={cur}{flag}")
        return 0
    if args.cmd == "approve":
        try:
            rec = approve(args.run_dir, args.artifact, args.sha256, args.approver, _when(args.now),
                          json.loads(Path(args.approvers).read_text()), load_policy(args.policy))
        except ApprovalError as exc:
            print(f"APPROVAL REFUSED: {exc}")
            return 2
        print(f"Approved {args.artifact} by {rec['approver_name']} (sha256 {rec['sha256'][:12]}..., expires {rec['expires_at']})")
        return 0
    if args.cmd == "release":
        try:
            out = release(args.run_dir, args.artifact, _when(args.now), load_policy(args.policy))
        except ApprovalError as exc:
            print(f"RELEASE REFUSED: {exc}")
            return 2
        print(f"Released {out}. Next step is manual: import or build it in HubSpot yourself.")
        return 0
    if args.cmd == "verify":
        ok, why = verify(args.path)
        print(("OK " if ok else "BROKEN ") + why)
        return 0 if ok else 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
