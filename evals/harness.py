"""Turn eval cases into datasets and score predictions. Shared by run_evals.py and the tests."""
from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path

from lifecycle_agent.controls import EMAIL_PLAYS
from lifecycle_agent.ingest import build_dataset, norm_email, stage_rank
from lifecycle_agent.util import parse_dt

ROOT = Path(__file__).resolve().parent
TOFU = {"NURTURE_WELCOME", "NURTURE_EDUCATION", "RE_ENGAGE"}


def load_cases(path=None) -> dict:
    path = Path(path) if path else ROOT / "cases_v2.json"
    return json.loads(path.read_text())


def case_dataset(doc: dict, case: dict) -> dict:
    base = dict(doc["base_contact"])
    base.update(case["contact"])
    contacts = [base]
    for extra in case["extra_contacts"]:
        row = dict(doc["base_contact"])
        row.update(extra)
        contacts.append(row)
    events = [{"Event ID": f"{case['id']}-E{i}", "Contact Record ID": base["Record ID"], "Email": "",
               "Event Type": e["type"], "Occurred At": e["at"], "Detail": e.get("detail", "")}
              for i, e in enumerate(case["events"], 1)]
    deals = [{**d, "Associated Contact ID": base["Record ID"]} for d in case["deals"]]
    prior = [{**p, "Contact Record ID": base["Record ID"]} for p in case["prior_plays"]]
    return build_dataset(contacts, events, deals, case["suppression"], prior,
                         parse_dt(doc["exported_at"]), parse_dt(doc["as_of"]))


def structured_must_not_email(doc: dict, case: dict) -> bool:
    """Independent re-statement of the consent policy from structured fields only (no free text)."""
    rows = [dict(doc["base_contact"], **case["contact"])] + [dict(doc["base_contact"], **x) for x in case["extra_contacts"]]
    email = norm_email(rows[0]["Email"])
    sup = {norm_email(s["Email or Domain"]) for s in case["suppression"]}
    if email in sup or ("@" + email.split("@")[-1]) in sup:
        return True
    if email.endswith(("@rivalcrm.example", "@rubia-demo.example")):
        return True
    for r in rows:
        if norm_email(r["Email"]) != email and r is not rows[0]:
            continue
        consent = (r["Consent Basis"] or "").strip().lower()
        stage = (r["Lifecycle Stage"] or "").strip().lower()
        if str(r["Unsubscribed from all email"]).strip().lower() in {"true", "yes"}:
            return True
        if str(r["Hard bounced"]).strip().lower() in {"true", "yes"}:
            return True
        if r["Marketing contact status"] != "Marketing contact":
            return True
        if consent in {"explicit", "explicit opt-in", "opt-in", "yes"}:
            continue
        if consent in {"soft opt-in", "soft"} and stage in {"customer", "evangelist"}:
            continue
        return True
    return False


def cap_hit(doc: dict, case: dict) -> bool:
    as_of = parse_dt(doc["as_of"])
    sent = [e for e in case["events"] if e["type"] == "email_sent" and (as_of - parse_dt(e["at"])).days < 7]
    recent_play = [p for p in case["prior_plays"] if p["Play"] in EMAIL_PLAYS
                   and as_of - parse_dt(p["Proposed At"]) < timedelta(days=14)]
    return len(sent) >= 2 or bool(recent_play)


def score(doc: dict, preds: dict) -> dict:
    """preds: case_id -> {play, status, proposed_stage, reason_codes}."""
    n = len(doc["cases"])
    exact = play_only = 0
    v = {"consent_or_suppression": [], "open_deal_nurtured": [], "customer_got_tofu": [], "frequency_cap": [],
         "stage_rule": []}
    misses = []
    for c in doc["cases"]:
        p = preds[c["id"]]
        g = c["gold"]
        sends = p["play"] in EMAIL_PLAYS and p["status"] == "PROPOSED"
        if p["play"] == g["play"]:
            play_only += 1
        if p["play"] == g["play"] and p["status"] == g["status"] and (p.get("proposed_stage") or "") == g["proposed_stage"]:
            exact += 1
        else:
            misses.append(f"{c['id']}: expected {g['play']}/{g['status']}, got {p['play']}/{p['status']}")
        if sends and structured_must_not_email(doc, c):
            v["consent_or_suppression"].append(c["id"])
        if sends and any(str(d.get("Is Closed")).lower() in {"false", "no"} for d in c["deals"]):
            v["open_deal_nurtured"].append(c["id"])
        stage = dict(doc["base_contact"], **c["contact"])["Lifecycle Stage"].lower()
        if p["play"] in TOFU and p["status"] == "PROPOSED" and stage in {"customer", "evangelist"}:
            v["customer_got_tofu"].append(c["id"])
        if sends and cap_hit(doc, c):
            v["frequency_cap"].append(c["id"])
        ps = p.get("proposed_stage") or ""
        if ps and (stage_rank(ps) > stage_rank("marketingqualifiedlead")):
            v["stage_rule"].append(c["id"])
    opt = [c for c in doc["cases"] if "opt_out" in c["tags"]]
    non_opt = [c for c in doc["cases"] if "opt_out" not in c["tags"]]
    return {"cases": n, "exact_accuracy": round(exact / n, 3), "play_accuracy": round(play_only / n, 3),
            "violations": {k: len(x) for k, x in v.items()}, "violation_cases": v,
            "opt_out_caught": f"{sum(1 for c in opt if preds[c['id']]['play'] == 'SUPPRESS')} of {len(opt)}",
            "opt_out_false_positives": sum(1 for c in non_opt if "opt_out_request_in_free_text" in preds[c["id"]].get("reason_codes", [])),
            "misses": misses}
