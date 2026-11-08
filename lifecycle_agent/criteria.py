"""Proposed HubSpot segment (active list) criteria, one per play.

Design choice: the import only sets a custom property `lifecycle_next_play`. Every email segment
then RE-CHECKS consent and suppression inside HubSpot, so if someone unsubscribes after the run,
HubSpot drops them from the active segment before anything is sent. The property names below are
HubSpot defaults where they exist; check them against your portal (Settings > Properties) before
building. `lifecycle_next_play` and `lifecycle_play_run_id` are custom properties you create.
"""
from __future__ import annotations

SAFETY_FILTERS = [
    {"property": "hs_marketable_status", "operator": "is", "value": "Marketing contact"},
    {"property": "hs_email_optout", "operator": "is not", "value": "true", "label": "Unsubscribed from all email"},
    {"property": "hs_email_hard_bounce_reason_enum", "operator": "is unknown", "label": "Hard bounce reason"},
    {"segment_membership": "Lifecycle agent - suppress", "operator": "is not member"},
    {"segment_membership": "Global suppression (your existing list)", "operator": "is not member"},
]
NO_OPEN_DEAL = {"association": "deal", "property": "dealstage", "operator": "none of open stages",
                "label": "No associated deal in an open stage"}

PLAY_SPECS = {
    "NURTURE_WELCOME": {"lifecyclestage": ["subscriber", "lead"], "extra": [NO_OPEN_DEAL],
                        "use": "Enrol in the welcome sequence or workflow (3 emails over 2 weeks)."},
    "NURTURE_EDUCATION": {"lifecyclestage": ["subscriber", "lead", "marketingqualifiedlead"], "extra": [NO_OPEN_DEAL],
                          "use": "Enrol in the education nurture."},
    "RE_ENGAGE": {"lifecyclestage": ["subscriber", "lead", "marketingqualifiedlead", "other"], "extra": [NO_OPEN_DEAL],
                  "use": "Send the two-email re-engagement. Non-responders become SUNSET on a later run."},
    "ONBOARD": {"lifecyclestage": ["customer"], "extra": [],
                "use": "Enrol in onboarding. Customers never enter top-of-funnel nurture."},
    "EXPAND": {"lifecyclestage": ["customer", "evangelist"], "extra": [],
               "use": "Send expansion content and notify the account owner."},
    "SUPPRESS": {"lifecyclestage": None, "extra": [], "email": False,
                 "use": "Static exclusion list 'Lifecycle agent - suppress'. Use it as an exclusion on every marketing send."},
    "SUNSET": {"lifecyclestage": None, "extra": [], "email": False,
               "use": "Review, then add to the suppress list or set as non-marketing contacts. Do not email."},
    "OWNER_ALERT": {"lifecyclestage": None, "extra": [], "email": False,
                    "use": "One sales task for the open deal, carrying the deal id, stage and resolved owner. No marketing email. Do not create another task for the same open deal and owner."},
    "MQL_FOLLOW_UP": {"lifecyclestage": ["marketingqualifiedlead"], "extra": [], "email": False,
                      "use": "One sales follow-up task for the contact owner when an MQL is created. No SLA and no automatic escalation. Do not send marketing email because this task exists."},
    "SALES_HAND_RAISE": {"lifecyclestage": None, "extra": [], "email": False,
                         "use": "Workflow: create an owner task. The import also moves Lifecycle Stage forward to MQL where allowed."},
    "SQL_ASSIST": {"lifecyclestage": ["salesqualifiedlead"], "extra": [], "email": False,
                   "use": "Owner task: send a relevant case study 1:1 and suggest a meeting."},
    "CUSTOMER_CHECK_IN": {"lifecyclestage": ["customer", "evangelist"], "extra": [], "email": False,
                          "use": "Owner (CSM) task: personal check-in. No automated email."},
}


def build_criteria(assignments: list[dict], run_id: str, policy_version: str) -> dict:
    counts: dict[str, int] = {}
    for a in assignments:
        if a["status"] == "PROPOSED":
            counts[a["play"]] = counts.get(a["play"], 0) + 1
    segments = []
    for play, spec in PLAY_SPECS.items():
        if not counts.get(play):
            continue
        email = spec.get("email", True)
        filters = [{"property": "lifecycle_next_play", "operator": "is", "value": play},
                   {"property": "lifecycle_play_run_id", "operator": "is", "value": run_id}]
        if spec["lifecyclestage"]:
            filters.append({"property": "lifecyclestage", "operator": "is any of", "value": spec["lifecyclestage"]})
        filters += spec["extra"]
        if email:
            filters += SAFETY_FILTERS
        segments.append({"name": f"Lifecycle agent - {play.replace('_', ' ').title()}",
                         "type": "active" if email else ("static" if play in {"SUPPRESS", "SUNSET"} else "active"),
                         "object": "contact", "expected_members": counts[play], "email_play": email,
                         "filters_all_of": filters, "how_to_use": spec["use"]})
    return {"run_id": run_id, "policy_version": policy_version,
            "custom_properties_needed": [
                {"name": "lifecycle_next_play", "type": "dropdown", "options": sorted(PLAY_SPECS)},
                {"name": "lifecycle_play_reason", "type": "single-line text"},
                {"name": "lifecycle_play_run_id", "type": "single-line text"}],
            "segments": segments,
            "note": "Specification only. Build these by hand in HubSpot (CRM > Segments). The agent never creates lists."}


def criteria_markdown(spec: dict) -> str:
    lines = [f"# Proposed HubSpot segments (run {spec['run_id']})", "",
             "Specification only. Nothing here has been created in HubSpot. Build by hand after approval.", ""]
    for s in spec["segments"]:
        lines += [f"## {s['name']}", f"- Type: {s['type']} contact segment; expected members from this run: {s['expected_members']}",
                  f"- How to use: {s['how_to_use']}", "- Filters (all must be true):"]
        for f in s["filters_all_of"]:
            target = f.get("property") or f.get("segment_membership") or f.get("association")
            label = f.get("label", "")
            val = f.get("value", "")
            val = ", ".join(val) if isinstance(val, list) else val
            lines.append(f"  - `{target}` {f['operator']} {val} {('(' + label + ')') if label else ''}".rstrip())
        lines.append("")
    return "\n".join(lines)
