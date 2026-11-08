"""Orchestrates the run: ingest -> plan -> write (summaries, drafts, artifacts).

Each step checkpoints to state/runs/<run_id>/. If a run crashes, running the same command again
resumes from the last completed step. The run_id is a hash of the input files, as-of time and
policy version, so the same inputs always map to the same run.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path

from . import __version__
from .approval import snapshot_age_hours
from .audit import AuditLog
from .controls import EMAIL_PLAYS, stage_change_allowed
from .criteria import build_criteria, criteria_markdown
from .drafts import build_drafts, owner_summary
from .ingest import load_dataset
from .ledger import Ledger, play_key
from .plays import plan
from .untrusted import screen
from .util import iso, sha256_bytes, sha256_file, write_csv

STEPS = ["ingest", "plan", "write"]
APPROVABLE = ["hubspot_import_proposed.csv", "list_criteria.json", "nurture_drafts.md", "low_fit_sales_tasks.csv"]


class StaleSnapshot(Exception):
    pass


class SimulatedCrash(Exception):
    pass


def load_policy(path="config/policy.json") -> dict:
    return json.loads(Path(path).read_text())


def compute_run_id(files: dict, as_of: datetime, policy: dict) -> str:
    h = b""
    for k in sorted(files):
        p = files[k]
        h += k.encode() + (Path(p).read_bytes() if Path(p).exists() else b"")
    h += iso(as_of).encode() + policy["policy_version"].encode()
    return sha256_bytes(h)[:12]


def _serialisable(a: dict) -> dict:
    return {k: v for k, v in a.items() if not k.startswith("_")}


def run(data_dir, out_root, state_dir, as_of: datetime, policy: dict, *, client=None,
        allow_stale=False, fail_after: str | None = None, prefix="sample_", clock=None) -> dict:
    fail_after = fail_after or os.environ.get("LMA_FAIL_AFTER")
    clock = clock or (lambda: as_of)
    ds, files = load_dataset(data_dir, as_of, prefix)
    run_id = compute_run_id(files, as_of, policy)
    run_dir = Path(out_root) / f"run_{run_id}"
    sdir = Path(state_dir) / "runs" / run_id
    sdir.mkdir(parents=True, exist_ok=True)
    ckpt_path = sdir / "checkpoint.json"
    ckpt = json.loads(ckpt_path.read_text()) if ckpt_path.exists() else {"completed": []}
    audit = AuditLog(Path(state_dir) / "audit.jsonl", clock=clock)
    mode = "claude" if client is not None else "offline"
    resumed = bool(ckpt["completed"]) and "write" not in ckpt["completed"]
    if "write" in ckpt["completed"]:
        audit.append({"event": "replay_noop", "run_id": run_id})
        return {"run_id": run_id, "run_dir": str(run_dir), "status": "already_complete",
                "summary": json.loads((run_dir / "manifest.json").read_text())["summary"]}
    audit.append({"event": "run_resumed" if resumed else "run_started", "run_id": run_id, "mode": mode,
                  "as_of": iso(as_of), "policy_version": policy["policy_version"],
                  "completed_steps": ckpt["completed"]})

    def done(step, payload=None):
        ckpt["completed"].append(step)
        if payload is not None:
            (sdir / f"{step}.json").write_text(json.dumps(payload, default=str))
        ckpt_path.write_text(json.dumps(ckpt))
        audit.append({"event": "step_completed", "run_id": run_id, "step": step})
        if fail_after == step:
            audit.append({"event": "simulated_crash", "run_id": run_id, "after_step": step})
            raise SimulatedCrash(f"simulated crash after step '{step}'")

    # Step 1: ingest + snapshot freshness
    age = snapshot_age_hours({"exported_at": iso(ds["exported_at"])}, as_of) if ds["exported_at"] else None
    stale = age is None or age > policy["snapshot_max_age_hours"]
    if "ingest" not in ckpt["completed"]:
        audit.append({"event": "snapshot_checked", "run_id": run_id, "age_hours": age, "stale": stale,
                      "counts": ds["counts"], "contacts": len(ds["contacts"])})
        if stale and not allow_stale:
            audit.append({"event": "run_refused", "run_id": run_id, "reason": "stale_snapshot"})
            raise StaleSnapshot(f"snapshot age {age} hours exceeds {policy['snapshot_max_age_hours']}; re-export or pass --allow-stale (outputs will be unapprovable)")
        done("ingest", {"age_hours": age, "stale": stale})

    # Step 2: plan (deterministic) + ledger dedupe + decision trace
    if "plan" not in ckpt["completed"]:
        dec_path = run_dir / "decisions.jsonl"
        if dec_path.exists():  # partial trace from a crashed attempt: keep it, start a clean one
            dec_path.rename(run_dir / f"decisions.partial-{len(list(run_dir.glob('decisions.partial-*')))}.jsonl")
        decisions = AuditLog(dec_path, clock=clock)
        ledger = Ledger(Path(state_dir) / "ledger.json")
        assignments = [_dedupe_assignment(a, policy, ledger, run_id, as_of) for a in plan(ds, policy)]
        for a in assignments:
            decisions.append({"run_id": run_id, "contact_id": a["contact_id"], "play": a["play"],
                              "status": a["status"], "channel": a["channel"], "segment": a["segment"],
                              "reason_codes": a["reason_codes"], "evidence_event_ids": a["evidence_event_ids"],
                              "proposed_stage": a["proposed_stage"], "route_to": a["route_to"],
                              "review_flags": a["review_flags"], "play_key": a["play_key"],
                              "screens": [{"source": s["source"], "ref": s["ref"], "status": s["status"]} for s in a["screens"]]})
        done("plan", [_serialisable(a) for a in assignments])
    assignments = json.loads((sdir / "plan.json").read_text())

    # Step 3: summaries, drafts, artifacts, manifest; ledger committed last
    log = lambda rec: audit.append({"run_id": run_id, **rec})
    for a in assignments:
        cid = a["contact_id"]
        evs = ds["events"].get(cid, [])
        c = ds["contacts"][cid]
        a["_quarantined_raw"] = [t for t in [c["notes"]] + [e["detail"] for e in evs] if screen(t)["status"] == "quarantined"]
        if a["channel"] == "owner_task" and a["status"] in {"PROPOSED", "REVIEW"}:
            a["why_now"], a["why_now_source"] = owner_summary(a, evs, client, log)
        else:
            a["why_now"], a["why_now_source"] = "", ""
    drafts = build_drafts(assignments, client, log)
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {"run_id": run_id, "as_of": iso(as_of), "exported_at": iso(ds["exported_at"]), "age_hours": age,
            "stale": stale, "mode": mode, "policy_version": policy["policy_version"]}
    write_artifacts(run_dir, assignments, drafts, ds, policy, meta)
    ledger = Ledger(Path(state_dir) / "ledger.json")
    for a in assignments:
        if a["status"] == "PROPOSED" and a["channel"] != "none":
            ledger.record(a["play_key"], run_id, as_of, a["contact_id"], a["play"])
    ledger.save()
    manifest = json.loads((run_dir / "manifest.json").read_text())
    done("write")
    audit.append({"event": "run_completed", "run_id": run_id, "summary": manifest["summary"]})
    return {"run_id": run_id, "run_dir": str(run_dir), "status": "resumed_and_completed" if resumed else "completed",
            "summary": manifest["summary"]}


ASSIGN_FIELDS = ["contact_id", "merged_ids", "email", "first_name", "company", "stage", "fit_tier", "engagement_tier",
                 "engagement_score", "days_since_engagement", "segment", "play", "channel", "status",
                 "reason_codes", "proposed_stage", "route_to", "next_eligible", "why_now", "why_now_source",
                 "review_flags", "evidence_event_ids", "play_key", "fit_label", "task_deal_id",
                 "task_deal_stage", "task_owner_source", "sales_route"]
IMPORT_FIELDS = ["Record ID", "Email", "lifecycle_next_play", "lifecycle_play_reason", "lifecycle_play_run_id",
                 "Lifecycle Stage", "Route to", "Task deal id", "Task deal stage", "Fit label", "Owner source"]
LOW_FIT_FIELDS = ["Record ID", "Email", "Company", "lifecycle_next_play", "fit_label", "fit_reasons",
                  "reason_codes", "route_to", "sales_route", "label_note"]
LOW_FIT_NOTE = ("low fit; human review before any sales routing; after approval this file may be "
                "used as a local sales-task plan; the low-fit label and reasons stay in the approved bytes")


def _dedupe_assignment(a: dict, policy: dict, ledger: Ledger, run_id: str, as_of: datetime) -> dict:
    """Apply the ledger. The same MQL creation or open-deal task is not proposed again.

    A duplicate is left out of the import. It is not replaced by a marketing email.
    A later run only selects an email play when the inputs themselves say the creation
    was already tasked (prior plays) and the normal eligibility rules pass.
    """
    _stamp_play_key(a, policy)
    if a["status"] == "PROPOSED" and a["channel"] != "none":
        cooldown = None if a.get("dedupe") == "event" else policy["frequency_cap"]["play_cooldown_days"]
        if ledger.check(a["play_key"], run_id, as_of, cooldown) == "duplicate":
            a["status"] = "DUPLICATE"
            note = "already_proposed_for_this_event" if cooldown is None else "already_proposed_by_earlier_run_within_cooldown"
            a["reason_codes"] = list(a["reason_codes"]) + [note]
    return a


def _stamp_play_key(a: dict, policy: dict) -> None:
    if a.get("dedupe") == "event" and a.get("task_event_key"):
        a["play_key"] = a["task_event_key"]
    else:
        a["play_key"] = play_key(a["contact_id"], a["play"], policy["policy_version"])


def _flat(a):
    r = dict(a)
    for k in ("reason_codes", "review_flags", "evidence_event_ids", "merged_ids"):
        r[k] = "; ".join(r.get(k) or [])
    return r


def write_artifacts(run_dir: Path, assignments, drafts, ds, policy, meta) -> None:
    write_csv(run_dir / "play_assignments.csv", [_flat(a) for a in assignments], ASSIGN_FIELDS)

    # review queue: every item a human must decide or should know about
    rq = []
    for a in assignments:
        items = list(a["review_flags"])
        if a["status"] in {"REVIEW"} and not items:
            items.append(a["reason_codes"][0] if a["reason_codes"] else "review")
        if a["play"] == "DATA_REVIEW":
            items = [f"data:{r}" for r in a["reason_codes"]] + list(a["review_flags"])
        items += [f"data:{i}" for i in a.get("data_issues", []) if i.startswith(("unparseable_date", "duplicate_merged"))]
        for it in dict.fromkeys(items):
            rq.append({"contact_id": a["contact_id"], "email": a["email"], "play": a["play"], "status": a["status"],
                       "item": it, "what_to_check": WHAT_TO_CHECK.get(it.split(":")[0], "Check the record and decide."),
                       "decision": "", "decided_by": ""})
    write_csv(run_dir / "review_queue.csv", rq, ["contact_id", "email", "play", "status", "item", "what_to_check",
                                                 "decision", "decided_by"])

    # proposed import: PROPOSED only; stage change re-validated here (defence in depth)
    rows = []
    for a in assignments:
        if a["status"] != "PROPOSED" or a["channel"] == "none":
            continue
        stage = a["proposed_stage"]
        if stage:
            ok, _ = stage_change_allowed(a["stage"], stage, policy)
            if not ok:
                stage = ""
        if a["play"] in EMAIL_PLAYS:
            assert a["status"] == "PROPOSED"
        rows.append({"Record ID": a["contact_id"], "Email": a["email"], "lifecycle_next_play": a["play"],
                     "lifecycle_play_reason": "; ".join(a["reason_codes"])[:250],
                     "lifecycle_play_run_id": meta["run_id"], "Lifecycle Stage": stage,
                     "Route to": (a.get("route_to") or "") if a["channel"] == "owner_task" else "",
                     "Task deal id": a.get("task_deal_id") or "",
                     "Task deal stage": a.get("task_deal_stage") or "",
                     "Fit label": a.get("fit_label") or "",
                     "Owner source": a.get("task_owner_source") or ""})
    write_csv(run_dir / "hubspot_import_proposed.csv", rows, IMPORT_FIELDS)

    low_rows = []
    for a in assignments:
        if a.get("fit_label") != "low_fit":
            continue
        low_rows.append({
            "Record ID": a["contact_id"], "Email": a["email"], "Company": a.get("company") or "",
            "lifecycle_next_play": a["play"], "fit_label": "low_fit",
            "fit_reasons": "; ".join(a.get("fit_reasons") or []),
            "reason_codes": "; ".join(a.get("reason_codes") or []),
            "route_to": a.get("route_to") or "", "sales_route": a.get("sales_route") or "pending_human_review",
            "label_note": LOW_FIT_NOTE})
    write_csv(run_dir / "low_fit_sales_tasks.csv", low_rows, LOW_FIT_FIELDS)

    spec = build_criteria(assignments, meta["run_id"], meta["policy_version"])
    (run_dir / "list_criteria.json").write_text(json.dumps(spec, indent=2) + "\n")
    (run_dir / "list_criteria.md").write_text(criteria_markdown(spec) + "\n")
    (run_dir / "nurture_drafts.md").write_text(drafts_markdown(drafts, meta) + "\n")
    (run_dir / "segment_report.md").write_text(segment_report(assignments, ds, meta) + "\n")
    summary = {
        "contacts": len(assignments),
        "by_status": dict(sorted(Counter(a["status"] for a in assignments).items())),
        "by_play_proposed": dict(sorted(Counter(a["play"] for a in assignments if a["status"] == "PROPOSED").items())),
        "import_rows": len(rows), "review_items": len(rq),
        "email_plays_blocked_by_consent": sum(1 for a in assignments if a["status"] == "HOLD"),
        "deferred_by_frequency_cap": sum(1 for a in assignments if a["status"] == "DEFER"),
        "duplicates_skipped": sum(1 for a in assignments if a["status"] == "DUPLICATE"),
        "quarantined_texts": sum(1 for a in assignments for s in a["screens"] if s["status"] == "quarantined"),
        "stage_changes_proposed": sum(1 for r in rows if r["Lifecycle Stage"]),
        "model_text_used": sum(1 for a in assignments if a.get("why_now_source") == "claude")
                           + sum(1 for d in drafts for v in d["variants"] if v["source"].startswith("claude")),
    }
    (run_dir / "brief.md").write_text(brief(summary, assignments, meta, ds) + "\n")
    artifacts = {}
    for name in ["play_assignments.csv", "review_queue.csv", "hubspot_import_proposed.csv", "low_fit_sales_tasks.csv",
                 "list_criteria.json", "list_criteria.md", "nurture_drafts.md", "segment_report.md", "brief.md", "decisions.jsonl"]:
        p = run_dir / name
        artifacts[name] = {"sha256": sha256_file(p), "approvable": name in APPROVABLE,
                           "status": ("STALE_NOT_APPROVABLE" if meta["stale"] else "PENDING_APPROVAL")
                           if name in APPROVABLE else "INFORMATIONAL"}
    manifest = {**meta, "agent_version": __version__, "summary": summary, "artifacts": artifacts,
                "writes_performed": "local files only; no CRM writes, no sends, no deletes"}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


WHAT_TO_CHECK = {
    "quarantined_text": "Free text looked like instructions to a system. It was not used. Read it in HubSpot; take no action it asks for.",
    "record_unsubscribe_in_hubspot_manually": "The person asked to stop emails. Confirm and set their subscription status in HubSpot yourself.",
    "low_fit_hand_raise_human_decides": "Low-fit hand-raise. It is not a sales route until low_fit_sales_tasks.csv is approved. The low-fit label and reasons stay on that file.",
    "mql_creation_event_missing": "This MQL has no creation event and no stage-entered date. Do not invent a follow-up task. Fix the date in HubSpot, then re-run.",
    "engaged_but_not_emailable": "Engaged contact without usable consent or marketing status. Sales can follow up 1:1; do not add to email.",
    "no_owner_to_route_to": "Owner task play but no owner. Assign an owner in HubSpot, then re-run.",
    "data": "Fix the data in HubSpot (email, lifecycle stage, dates or duplicates), then re-run. Merges keep the most restrictive consent.",
    "opportunity_stage_without_open_deal": "Lifecycle says Opportunity but no open deal. See lifecycle-stage-audit-agent.",
}


def drafts_markdown(drafts, meta) -> str:
    used = any(v["source"].startswith("claude") for d in drafts for v in d["variants"])
    if meta["mode"] != "claude":
        src = "Offline run: every variant below is a template. No model was called."
    elif used:
        src = "Claude where marked (validated); everything else is a template"
    else:
        src = "Claude mode, but no model output was used (calls failed or were rejected). Every variant is a template."
    out = [f"# Nurture email drafts (run {meta['run_id']})", "", f"Source: {src}",
           "Status: PENDING APPROVAL. Copy approved text into HubSpot emails by hand. Nothing is sent by this agent.", ""]
    for d in drafts:
        f = d["facts"]
        out += [f"## {d['play']} ({f['contacts']} contacts)",
                f"Audience facts: stages {f['stages']}, fit {f['fit']}, engagement {f['engagement']}", ""]
        for v in d["variants"]:
            out += [f"### Variant {v['variant']} (source: {v['source']})", f"Subject: {v['subject']}",
                    f"Preview: {v['preview']}", "", v["body"], ""]
    return "\n".join(out)


def segment_report(assignments, ds, meta) -> str:
    seg = Counter(a["segment"] for a in assignments)
    out = [f"# Segment report (run {meta['run_id']})", "",
           f"As of {meta['as_of']}. Snapshot exported {meta['exported_at']} ({meta['age_hours']} hours old, stale: {meta['stale']}).", "",
           "## Contacts by lifecycle stage, engagement and fit", "", "| Segment | Contacts |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in sorted(seg.items())]
    out += ["", "## Plays", "", "| Play | Proposed | Hold (consent) | Defer (cap) | Review | Duplicate |", "|---|---|---|---|---|---|"]
    plays = sorted({a["play"] for a in assignments})
    for p in plays:
        c = Counter(a["status"] for a in assignments if a["play"] == p)
        out.append(f"| {p} | {c['PROPOSED']} | {c['HOLD']} | {c['DEFER']} | {c['REVIEW']} | {c['DUPLICATE']} |")
    out += ["", "## Data quality", ""]
    out += [f"- {k}: {v}" for k, v in ds["counts"].items()]
    merged = [a for a in assignments if a.get("merged_ids")]
    out.append(f"- duplicate contacts merged (restrictive consent kept): {sum(len(a['merged_ids']) for a in merged)}")
    out += [f"- {n}" for n in ds["notes"]]
    return "\n".join(out)


def brief(summary, assignments, meta, ds) -> str:
    if meta["mode"] == "offline":
        mode = "Offline (rules and templates; no model called)"
    elif summary["model_text_used"]:
        mode = f"Claude mode: {summary['model_text_used']} validated model texts used, the rest are templates (see why_now_source)"
    else:
        mode = "Claude mode, but no model output was used (calls failed or were rejected); all text is template"
    bs = summary["by_status"]
    out = [f"# Lifecycle run brief ({meta['as_of'][:10]})", "",
           f"- Run {meta['run_id']}, policy {meta['policy_version']}, mode: {mode}",
           f"- {summary['contacts']} contacts after de-duplication. {bs.get('PROPOSED', 0)} plays proposed, "
           f"{bs.get('HOLD', 0)} held for email eligibility, {bs.get('DEFER', 0)} deferred by frequency caps, "
           f"{bs.get('REVIEW', 0)} need a decision, {bs.get('DUPLICATE', 0)} already proposed by an earlier run.",
           f"- Proposed import: {summary['import_rows']} rows, {summary['stage_changes_proposed']} forward stage changes (to MQL only).",
           f"- Free text quarantined: {summary['quarantined_texts']}. Review queue items: {summary['review_items']}.", "",
           "## Owner tasks", ""]
    for a in assignments:
        if a["channel"] == "owner_task" and a["status"] in {"PROPOSED", "REVIEW"}:
            if a.get("fit_label") == "low_fit":
                prefix = "LOW FIT, HUMAN REVIEW BEFORE SALES"
            else:
                prefix = a["play"]
            out.append(f"- {prefix} for {a['contact_id']} ({a['company'] or 'no company'}) -> {a['route_to'] or 'UNASSIGNED'}: {a['why_now']}")
    out += ["", "## Next steps", "",
            "1. Work through review_queue.csv.",
            "2. Run `python agent.py show --run-dir <this folder>` and review each pending artifact.",
            "3. Approve with the exact hash, then release. Import and build segments in HubSpot by hand."]
    return "\n".join(out)
