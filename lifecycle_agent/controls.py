"""Deterministic hard controls. No model output and no free text can change these results.

Order matters and is tested:
  hard suppression (stop all marketing) -> soft blocks (cannot email yet) -> frequency caps.
Stage rules limit what lifecycle change the agent may ever propose.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from .ingest import stage_rank
from .segment import marketing_emails_in
from .untrusted import screen

EMAIL_PLAYS = {"NURTURE_WELCOME", "NURTURE_EDUCATION", "RE_ENGAGE", "ONBOARD", "EXPAND"}


def screen_free_text(contact: dict, events: list) -> list[dict]:
    """Screen the note and every event detail. Returns one record per non-empty text."""
    out = []
    s = screen(contact.get("notes", ""))
    if s["status"] != "empty":
        out.append({"source": "contact_note", "ref": contact["contact_id"], **s})
    for ev in events:
        s = screen(ev.get("detail", ""))
        if s["status"] != "empty":
            out.append({"source": f"event:{ev['type']}", "ref": ev["event_id"], **s})
    return out


def hard_suppression(contact: dict, dataset: dict, screens: list[dict], policy: dict) -> list[str]:
    """Reasons that stop ALL marketing email for this contact."""
    reasons = []
    email = contact["email"]
    domain = email.split("@")[-1] if "@" in email else ""
    sup = dataset["suppression"]
    if email in sup["emails"]:
        reasons.append(f"suppression_list:{sup['emails'][email]}")
    if domain in sup["domains"]:
        reasons.append(f"suppressed_domain:{sup['domains'][domain]}")
    if contact["unsubscribed"]:
        reasons.append("unsubscribed_from_all")
    if contact["hard_bounced"]:
        reasons.append("hard_bounced")
    if contact["consent"] == "withdrawn":
        reasons.append("consent_withdrawn")
    if any(s.get("opt_out") for s in screens):
        reasons.append("opt_out_request_in_free_text")
    if domain in policy.get("internal_domains", []):
        reasons.append("internal_domain")
    if domain in policy.get("competitor_domains", []):
        reasons.append("competitor_domain")
    return reasons


def soft_email_blocks(contact: dict, policy: dict) -> list[str]:
    """Reasons the contact cannot receive marketing email now, though they are not suppressed."""
    blocks = []
    consent = contact["consent"]
    is_customer = contact["stage"] in {"customer", "evangelist"}
    if consent in policy["allowed_consent_bases"]:
        pass
    elif consent in policy.get("customer_only_consent_bases", []) and is_customer:
        pass
    elif consent in policy.get("customer_only_consent_bases", []):
        blocks.append("soft_opt_in_only_valid_for_customers")
    elif consent == "legitimate_interest":
        blocks.append("legitimate_interest_not_accepted_for_marketing_email")
    else:
        blocks.append("consent_unknown")
    if not contact["marketing_contact"]:
        blocks.append("non_marketing_contact")
    return blocks


def frequency_block(contact_events: list, prior_plays: list, as_of: datetime, policy: dict) -> tuple[list[str], str]:
    """Frequency caps. Returns (reasons, next_eligible_date ISO or '')."""
    fc = policy["frequency_cap"]
    reasons, next_dates = [], []
    sent = marketing_emails_in(contact_events, as_of, 7)
    if sent >= fc["max_marketing_emails_7d"]:
        reasons.append(f"frequency_cap:{sent}_marketing_emails_in_7d")
        recent = sorted(ev["at"] for ev in contact_events if ev["type"] == "email_sent")
        if recent:
            next_dates.append(recent[-fc["max_marketing_emails_7d"]] + timedelta(days=7))
    cooldown = timedelta(days=fc["play_cooldown_days"])
    for p in prior_plays:
        if p["play"] in EMAIL_PLAYS and as_of - p["at"] < cooldown:
            reasons.append(f"play_cooldown:{p['play']}_proposed_{p['at'].date().isoformat()}")
            next_dates.append(p["at"] + cooldown)
    nxt = max(next_dates).date().isoformat() if next_dates else ""
    return reasons, nxt


def stage_change_allowed(current: str, proposed: str, policy: dict) -> tuple[bool, str]:
    """The agent may only propose forward moves, and never beyond agent_max_stage."""
    max_stage = policy["stage_rules"]["agent_max_stage"]
    if stage_rank(proposed) < 0:
        return False, "unknown_target_stage"
    if stage_rank(proposed) > stage_rank(max_stage):
        return False, f"beyond_agent_max_stage:{max_stage}"
    if current in {"none", "unknown", "other"}:
        return False, "current_stage_not_comparable"
    if stage_rank(proposed) <= stage_rank(current):
        return False, "not_forward"
    return True, "ok"
