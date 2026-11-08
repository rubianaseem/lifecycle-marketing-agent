"""Step 3: choose exactly one next play per contact, then apply the hard controls.

Rules are evaluated top to bottom; the first match wins. Every decision carries reason codes
and the event IDs it relied on, so the audit trail can replay it.
"""
from __future__ import annotations

from datetime import timedelta

from .controls import (EMAIL_PLAYS, frequency_block, hard_suppression, screen_free_text,
                       soft_email_blocks, stage_change_allowed)
from .segment import engagement, fit, segment_key

PLAY_CHANNEL = {
    "SUPPRESS": "list", "SUNSET": "list", "DATA_REVIEW": "review", "NO_ACTION": "none",
    "OWNER_ALERT": "owner_task", "MQL_SLA_ALERT": "owner_task", "SALES_HAND_RAISE": "owner_task",
    "SQL_ASSIST": "owner_task", "CUSTOMER_CHECK_IN": "owner_task",
    "ONBOARD": "email", "EXPAND": "email", "RE_ENGAGE": "email",
    "NURTURE_WELCOME": "email", "NURTURE_EDUCATION": "email",
}
EARLY_STAGES = {"subscriber", "lead", "marketingqualifiedlead", "other"}


def _recent(events, as_of, days, types):
    start = as_of - timedelta(days=days)
    return [e for e in events if e["type"] in types and start <= e["at"] <= as_of]


def choose_play(c: dict, ds: dict, policy: dict) -> dict:
    as_of = ds["as_of"]
    cid = c["contact_id"]
    events = ds["events"].get(cid, [])
    deals = ds["deals"].get(cid, [])
    prior = ds["prior_plays"].get(cid, [])
    p = policy["plays"]
    f = fit(c, policy)
    e = engagement(events, as_of, policy)
    screens = screen_free_text(c, events)
    reasons: list[str] = []
    evidence: list[str] = []
    stage_change = ""
    route_to = c["owner"]
    review: list[str] = [f"quarantined_text:{s['ref']}" for s in screens if s["status"] == "quarantined"]

    def result(play, status="PROPOSED"):
        return {"contact_id": cid, "email": c["email"], "first_name": c["first_name"],
                "company": c["company"], "stage": c["stage"], "fit_tier": f["fit_tier"],
                "engagement_tier": e["engagement_tier"], "engagement_score": e["engagement_score"],
                "days_since_engagement": e["days_since_engagement"],
                "segment": segment_key(c["stage"], e["engagement_tier"], f["fit_tier"]),
                "play": play, "channel": PLAY_CHANNEL[play], "status": status,
                "reason_codes": reasons, "evidence_event_ids": evidence,
                "proposed_stage": stage_change, "route_to": route_to, "next_eligible": "",
                "review_flags": review, "fit_reasons": f["fit_reasons"], "screens": screens,
                "merged_ids": c["merged_ids"], "data_issues": c["data_issues"]}

    blocking_issues = [i for i in c["data_issues"] if i == "invalid_email" or i.startswith("unknown_stage")]
    if c["stage"] == "none":
        blocking_issues.append("missing_lifecycle_stage")
    if blocking_issues:
        reasons.extend(blocking_issues)
        return result("DATA_REVIEW", "REVIEW")

    hard = hard_suppression(c, ds, screens, policy)
    if hard:
        reasons.extend(hard)
        if "opt_out_request_in_free_text" in hard:
            review.append("record_unsubscribe_in_hubspot_manually")
        return result("SUPPRESS")

    open_deals = [d for d in deals if d["open"]]
    if open_deals:
        d = sorted(open_deals, key=lambda x: x["deal_id"])[0]
        reasons.append(f"open_deal:{d['deal_id']}:{d['stage']}")
        route_to = d["owner"] or c["owner"]
        return _route_check(result("OWNER_ALERT"))

    stage = c["stage"]
    if stage == "opportunity":
        reasons.append("opportunity_stage_without_open_deal")
        return result("DATA_REVIEW", "REVIEW")

    if stage in {"customer", "evangelist"}:
        cust = c["customer_date"]
        if cust and (as_of - cust).days <= p["onboard_days"]:
            reasons.append(f"customer_since_{cust.date().isoformat()}")
            return _gate(result("ONBOARD"), c, events, prior, ds, policy)
        usage = _recent(events, as_of, 30, {"product_usage_limit"})
        if usage or (e["engagement_tier"] in {"hot", "warm"} and f["fit_tier"] == "A"):
            reasons.append("usage_limit_signal" if usage else "engaged_high_fit_customer")
            evidence.extend(x["event_id"] for x in usage)
            return _gate(result("EXPAND"), c, events, prior, ds, policy)
        if e["engagement_tier"] == "dormant":
            reasons.append("dormant_customer_route_to_owner")
            return _route_check(result("CUSTOMER_CHECK_IN"))
        reasons.append("customer_no_trigger")
        return result("NO_ACTION", "NO_ACTION")

    if stage == "salesqualifiedlead":
        entered = c["stage_entered"]
        meetings = _recent(events, as_of, p["stalled_sql_days"], {"meeting_booked"})
        if entered and (as_of - entered).days >= p["stalled_sql_days"] and not meetings:
            reasons.append(f"sql_since_{entered.date().isoformat()}_no_meeting")
            return _route_check(result("SQL_ASSIST"))
        reasons.append("sql_owned_by_sales")
        return result("NO_ACTION", "NO_ACTION")

    if stage == "marketingqualifiedlead":
        entered = c["stage_entered"]
        lc = c["last_contacted"]
        if entered and (as_of - entered).total_seconds() > p["mql_sla_hours"] * 3600 and (lc is None or lc < entered):
            reasons.append(f"mql_not_contacted_within_{p['mql_sla_hours']}h")
            return _route_check(result("MQL_SLA_ALERT"))
        if entered and (as_of - entered).total_seconds() <= p["mql_sla_hours"] * 3600 and (lc is None or lc < entered):
            hr0 = policy["hand_raise"]
            if not _recent(events, as_of, hr0["window_days"], set(hr0["events"])):
                reasons.append("new_mql_inside_sla_waiting_for_sales")
                return result("NO_ACTION", "NO_ACTION")

    hr = policy["hand_raise"]
    hand = _recent(events, as_of, hr["window_days"], set(hr["events"]))
    pricing = _recent(events, as_of, hr["window_days"], {"pricing_page_view"})
    if stage in EARLY_STAGES and (hand or len(pricing) >= hr["pricing_views_needed"]):
        evidence.extend(x["event_id"] for x in hand + pricing)
        reasons.append("hand_raise_" + ("form" if hand else "repeat_pricing_views"))
        if f["fit_tier"] == "C":
            reasons.append("low_fit_hand_raise")
            review.append("low_fit_hand_raise_human_decides")
            return result("SALES_HAND_RAISE", "REVIEW")
        ok, why = stage_change_allowed(stage, "marketingqualifiedlead", policy)
        if ok:
            stage_change = "marketingqualifiedlead"
        else:
            reasons.append(f"no_stage_change:{why}")
        return _route_check(result("SALES_HAND_RAISE"))

    re_eng = [x for x in prior if x["play"] == "RE_ENGAGE"]
    if re_eng:
        last = max(re_eng, key=lambda x: x["at"])
        since = (as_of - last["at"]).days
        later = e["days_since_engagement"] is not None and e["days_since_engagement"] < since
        if since >= p["sunset_after_reengage_days"] and not later:
            reasons.append(f"no_engagement_since_re_engage_{last['at'].date().isoformat()}")
            return result("SUNSET")

    created = c["create_date"]
    is_new = created is not None and (as_of - created).days <= p["new_lead_days"]
    dormant = e["days_since_engagement"] is None or e["days_since_engagement"] >= p["dormant_days"]
    if dormant and not is_new:
        reasons.append("no_meaningful_engagement_90d" if e["days_since_engagement"] is None
                       else f"last_engagement_{e['days_since_engagement']}d_ago")
        return _gate(result("RE_ENGAGE"), c, events, prior, ds, policy)
    if is_new and stage in {"subscriber", "lead", "other"}:
        reasons.append(f"created_{created.date().isoformat()}")
        return _gate(result("NURTURE_WELCOME"), c, events, prior, ds, policy)
    if stage in EARLY_STAGES:
        reasons.append(f"{e['engagement_tier']}_{stage}")
        evidence.extend(e["engagement_event_ids"][-3:])
        return _gate(result("NURTURE_EDUCATION"), c, events, prior, ds, policy)
    reasons.append("no_rule_matched")
    return result("NO_ACTION", "NO_ACTION")


def _route_check(r: dict) -> dict:
    if not r["route_to"]:
        r["status"] = "REVIEW"
        r["review_flags"].append("no_owner_to_route_to")
    return r


def _gate(r: dict, c: dict, events: list, prior: list, ds: dict, policy: dict) -> dict:
    """Consent and frequency gates for email plays."""
    assert r["play"] in EMAIL_PLAYS
    blocks = soft_email_blocks(c, policy)
    if blocks:
        r["status"] = "HOLD"
        r["reason_codes"].extend(blocks)
        if r["engagement_tier"] in {"hot", "warm"}:
            r["review_flags"].append("engaged_but_not_emailable")
        return r
    freq, nxt = frequency_block(events, prior, ds["as_of"], policy)
    if freq:
        r["status"] = "DEFER"
        r["reason_codes"].extend(freq)
        r["next_eligible"] = nxt
    return r


def plan(ds: dict, policy: dict) -> list[dict]:
    return [choose_play(c, ds, policy) for c in sorted(ds["contacts"].values(), key=lambda x: x["contact_id"])]
