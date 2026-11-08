"""Step 1: load and normalise the five exports into one in-memory dataset.

Data contract (column names follow a HubSpot contact export, so a real export maps easily):
  contacts:    Record ID, Email, First Name, Company Name, Job Title, Company Size, Industry,
               Country/Region, Lifecycle Stage, Lead Status, Marketing contact status,
               Consent Basis, Unsubscribed from all email, Hard bounced, Create Date,
               Became a Customer Date, Date entered current stage, Last Contacted,
               Contact owner, Notes
  engagement:  Event ID, Contact Record ID, Email, Event Type, Occurred At, Detail
  deals:       Deal ID, Associated Contact ID, Deal Stage, Is Closed, Is Closed Won, Deal Owner, Close Date
  suppression: Email or Domain, Reason, Added At
  prior plays: Contact Record ID, Play, Proposed At, Outcome
Free text (Notes, event Detail) is UNTRUSTED. Nothing in this module interprets it.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .util import parse_dt, read_csv, truthy

STAGE_ORDER = ["subscriber", "lead", "marketingqualifiedlead", "salesqualifiedlead",
               "opportunity", "customer", "evangelist"]
STAGE_ALIASES = {
    "subscriber": "subscriber",
    "lead": "lead",
    "mql": "marketingqualifiedlead",
    "marketingqualifiedlead": "marketingqualifiedlead",
    "marketing qualified lead": "marketingqualifiedlead",
    "sql": "salesqualifiedlead",
    "salesqualifiedlead": "salesqualifiedlead",
    "sales qualified lead": "salesqualifiedlead",
    "opportunity": "opportunity",
    "customer": "customer",
    "evangelist": "evangelist",
    "other": "other",
}
CONSENT_ALIASES = {
    "explicit_opt_in": "explicit_opt_in", "explicit": "explicit_opt_in", "explicit opt-in": "explicit_opt_in",
    "opt-in": "explicit_opt_in", "opt in": "explicit_opt_in", "yes": "explicit_opt_in", "consented": "explicit_opt_in",
    "soft_opt_in": "soft_opt_in", "soft opt-in": "soft_opt_in", "soft opt in": "soft_opt_in", "soft": "soft_opt_in",
    "legitimate_interest": "legitimate_interest", "legitimate interest": "legitimate_interest", "li": "legitimate_interest",
    "withdrawn": "withdrawn", "no": "withdrawn", "opted out": "withdrawn", "opt-out": "withdrawn",
}
# Most restrictive first. When duplicates disagree, the most restrictive value wins.
CONSENT_RESTRICTIVENESS = ["withdrawn", "unknown", "legitimate_interest", "soft_opt_in", "explicit_opt_in"]
EVENT_ALIASES = {
    "pricing page view": "pricing_page_view", "page_view_pricing": "pricing_page_view",
    "demo request": "demo_request", "contact sales": "contact_sales",
    "marketing email sent": "email_sent", "email sent": "email_sent",
    "email open": "email_open", "email opened": "email_open",
    "email click": "email_click", "email clicked": "email_click",
    "webinar attended": "webinar_attended", "form submission": "form_submit",
    "meeting booked": "meeting_booked", "usage limit reached": "product_usage_limit",
}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def norm_email(value: str | None) -> str:
    return (value or "").strip().lower()


def norm_stage(value: str | None) -> str:
    v = (value or "").strip().lower()
    if not v:
        return "none"
    return STAGE_ALIASES.get(v, STAGE_ALIASES.get(v.replace("_", " "), "unknown"))


def stage_rank(stage: str) -> int:
    return STAGE_ORDER.index(stage) if stage in STAGE_ORDER else -1


def norm_consent(value: str | None) -> str:
    v = (value or "").strip().lower()
    if not v:
        return "unknown"
    return CONSENT_ALIASES.get(v, "unknown")


def norm_event(value: str | None) -> str:
    v = (value or "").strip().lower()
    return EVENT_ALIASES.get(v, v.replace(" ", "_"))


def parse_size(value: str | None) -> int | None:
    v = (value or "").strip().replace(",", "")
    if not v:
        return None
    m = re.match(r"^(\d+)\s*-\s*(\d+)$", v)
    if m:
        return int(m.group(2))
    m = re.match(r"^(\d+)\+?$", v)
    return int(m.group(1)) if m else None


def _contact(row: dict, notes: list) -> dict:
    email = norm_email(row.get("Email"))
    raw_stage = row.get("Lifecycle Stage", "")
    mstat = (row.get("Marketing contact status") or "").strip().lower()
    c = {
        "contact_id": (row.get("Record ID") or "").strip(),
        "email": email,
        "email_valid": bool(EMAIL_RE.match(email)),
        "first_name": (row.get("First Name") or "").strip().title(),
        "company": (row.get("Company Name") or "").strip(),
        "job_title": (row.get("Job Title") or "").strip(),
        "company_size": parse_size(row.get("Company Size")),
        "industry": (row.get("Industry") or "").strip().lower(),
        "country": (row.get("Country/Region") or "").strip(),
        "stage_raw": raw_stage.strip(),
        "stage": norm_stage(raw_stage),
        "lead_status": (row.get("Lead Status") or "").strip(),
        "marketing_contact": mstat == "marketing contact" or truthy(mstat) is True,
        "consent": norm_consent(row.get("Consent Basis")),
        "unsubscribed": truthy(row.get("Unsubscribed from all email")) is True,
        "hard_bounced": truthy(row.get("Hard bounced")) is True,
        "create_date": parse_dt(row.get("Create Date")),
        "customer_date": parse_dt(row.get("Became a Customer Date")),
        "stage_entered": parse_dt(row.get("Date entered current stage")),
        "last_contacted": parse_dt(row.get("Last Contacted")),
        "owner": (row.get("Contact owner") or "").strip(),
        "notes": row.get("Notes") or "",
        "merged_ids": [],
        "data_issues": [],
    }
    for field in ("Create Date", "Became a Customer Date", "Date entered current stage", "Last Contacted"):
        if (row.get(field) or "").strip() and parse_dt(row.get(field)) is None:
            c["data_issues"].append(f"unparseable_date:{field}")
    if not c["email_valid"]:
        c["data_issues"].append("invalid_email")
    if c["stage"] == "unknown":
        c["data_issues"].append(f"unknown_stage:{raw_stage.strip()}")
    return c


def _merge(primary: dict, dup: dict) -> dict:
    """Merge a duplicate into the primary record. Restrictive values always win."""
    primary["merged_ids"].append(dup["contact_id"])
    primary["unsubscribed"] = primary["unsubscribed"] or dup["unsubscribed"]
    primary["hard_bounced"] = primary["hard_bounced"] or dup["hard_bounced"]
    primary["marketing_contact"] = primary["marketing_contact"] and dup["marketing_contact"]
    ranks = CONSENT_RESTRICTIVENESS
    primary["consent"] = min(primary["consent"], dup["consent"], key=ranks.index)
    if stage_rank(dup["stage"]) > stage_rank(primary["stage"]):
        primary["stage"], primary["stage_raw"] = dup["stage"], dup["stage_raw"]
    for key in ("customer_date", "last_contacted", "stage_entered"):
        if dup[key] and (not primary[key] or dup[key] > primary[key]):
            primary[key] = dup[key]
    if not primary["owner"] and dup["owner"]:
        primary["owner"] = dup["owner"]
    if dup["notes"].strip():
        primary["notes"] = (primary["notes"] + "\n" + dup["notes"]).strip()
    primary["data_issues"].append(f"duplicate_merged:{dup['contact_id']}")
    return primary


def build_dataset(contacts_rows, event_rows, deal_rows, suppression_rows, prior_rows,
                  exported_at: datetime | None, as_of: datetime) -> dict:
    notes: list[str] = []
    contacts: dict[str, dict] = {}
    by_email: dict[str, str] = {}
    id_alias: dict[str, str] = {}
    for row in contacts_rows:
        c = _contact(row, notes)
        if not c["contact_id"]:
            notes.append("contact row without Record ID skipped")
            continue
        if c["email_valid"] and c["email"] in by_email:
            pid = by_email[c["email"]]
            _merge(contacts[pid], c)
            id_alias[c["contact_id"]] = pid
            continue
        contacts[c["contact_id"]] = c
        id_alias[c["contact_id"]] = c["contact_id"]
        if c["email_valid"]:
            by_email[c["email"]] = c["contact_id"]

    events: dict[str, list] = {cid: [] for cid in contacts}
    seen_ids = set()
    counts = {"events_loaded": 0, "events_duplicate": 0, "events_future": 0,
              "events_bad_date": 0, "events_orphan": 0}
    for row in event_rows:
        eid = (row.get("Event ID") or "").strip()
        if eid and eid in seen_ids:
            counts["events_duplicate"] += 1
            continue
        seen_ids.add(eid)
        when = parse_dt(row.get("Occurred At"))
        if when is None:
            counts["events_bad_date"] += 1
            continue
        if when > as_of:
            counts["events_future"] += 1
            continue
        cid = id_alias.get((row.get("Contact Record ID") or "").strip()) or by_email.get(norm_email(row.get("Email")))
        if not cid:
            counts["events_orphan"] += 1
            continue
        events[cid].append({"event_id": eid, "type": norm_event(row.get("Event Type")),
                            "at": when, "detail": row.get("Detail") or ""})
        counts["events_loaded"] += 1
    for lst in events.values():
        lst.sort(key=lambda e: (e["at"], e["event_id"]))

    deals: dict[str, list] = {cid: [] for cid in contacts}
    for row in deal_rows:
        cid = id_alias.get((row.get("Associated Contact ID") or "").strip())
        if not cid:
            notes.append(f"deal {row.get('Deal ID','?')} has no matching contact")
            continue
        stage = (row.get("Deal Stage") or "").strip().lower()
        closed = truthy(row.get("Is Closed"))
        if closed is None:
            closed = stage in {"closedwon", "closed won", "closedlost", "closed lost"}
        won = truthy(row.get("Is Closed Won")) is True or stage in {"closedwon", "closed won"}
        deals[cid].append({"deal_id": (row.get("Deal ID") or "").strip(), "stage": stage,
                           "open": not closed, "won": won,
                           "owner": (row.get("Deal Owner") or "").strip(),
                           "close_date": parse_dt(row.get("Close Date"))})

    sup_emails, sup_domains = {}, {}
    for row in suppression_rows:
        key = norm_email(row.get("Email or Domain"))
        reason = (row.get("Reason") or "unspecified").strip()
        if not key:
            continue
        if key.startswith("@"):
            sup_domains[key[1:]] = reason
        else:
            sup_emails[key] = reason

    prior: dict[str, list] = {cid: [] for cid in contacts}
    for row in prior_rows:
        cid = id_alias.get((row.get("Contact Record ID") or "").strip())
        when = parse_dt(row.get("Proposed At"))
        if not cid or not when:
            notes.append("prior play row skipped (unknown contact or bad date)")
            continue
        prior[cid].append({"play": (row.get("Play") or "").strip().upper(), "at": when,
                           "outcome": (row.get("Outcome") or "").strip().lower()})

    return {"contacts": contacts, "events": events, "deals": deals,
            "suppression": {"emails": sup_emails, "domains": sup_domains},
            "prior_plays": prior, "exported_at": exported_at, "as_of": as_of,
            "counts": counts, "notes": notes}


def load_dataset(data_dir: str | Path, as_of: datetime, prefix: str = "sample_") -> tuple[dict, dict]:
    """Load the five CSVs and the export manifest. Returns (dataset, file_paths)."""
    d = Path(data_dir)
    files = {
        "contacts": d / f"{prefix}contacts.csv",
        "engagement": d / f"{prefix}engagement.csv",
        "deals": d / f"{prefix}deals.csv",
        "suppression": d / f"{prefix}suppression.csv",
        "prior_plays": d / f"{prefix}prior_plays.csv",
        "manifest": d / f"{prefix}export_manifest.json",
    }
    manifest = json.loads(files["manifest"].read_text()) if files["manifest"].exists() else {}
    ds = build_dataset(read_csv(files["contacts"]), read_csv(files["engagement"]),
                       read_csv(files["deals"]), read_csv(files["suppression"]),
                       read_csv(files["prior_plays"]) if files["prior_plays"].exists() else [],
                       parse_dt(manifest.get("exported_at")), as_of)
    return ds, files
