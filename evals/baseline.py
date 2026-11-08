"""Deterministic baseline: the stage-and-recency rules a typical nurture workflow uses.

It honours 'Unsubscribed from all email' (HubSpot does that at send time anyway) but ignores
consent basis, suppression lists, open deals, frequency caps, MQL SLAs and free text. It counts
opens as engagement. Its prompt for owner summaries includes raw notes (no screening).
"""
from __future__ import annotations

from lifecycle_agent.controls import EMAIL_PLAYS


def baseline_play(ds: dict) -> dict:
    as_of = ds["as_of"]
    c = sorted(ds["contacts"].values(), key=lambda x: x["contact_id"])[0]
    evs = ds["events"][c["contact_id"]]
    last = max((e["at"] for e in evs if e["type"] != "email_sent"), default=None)
    dormant = last is None or (as_of - last).days >= 90
    stage = c["stage"]
    new = c["create_date"] is not None and (as_of - c["create_date"]).days <= 30
    if c["unsubscribed"]:
        play = "SUPPRESS"
    elif stage in {"customer", "evangelist"}:
        play = "ONBOARD" if c["customer_date"] and (as_of - c["customer_date"]).days <= 60 else "NO_ACTION"
    elif stage in {"salesqualifiedlead", "opportunity"}:
        play = "NO_ACTION"
    elif dormant and not new:
        play = "RE_ENGAGE"
    elif new and stage in {"subscriber", "lead"}:
        play = "NURTURE_WELCOME"
    else:
        play = "NURTURE_EDUCATION"
    status = "NO_ACTION" if play == "NO_ACTION" else "PROPOSED"
    return {"play": play, "status": status, "proposed_stage": "", "reason_codes": [],
            "prompt_text": c["notes"] + " " + " ".join(e["detail"] for e in evs)}


__all__ = ["baseline_play", "EMAIL_PLAYS"]
