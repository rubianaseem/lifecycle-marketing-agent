"""Step 2: deterministic fit, engagement and lifecycle segmentation.

Email opens score zero by default: Apple Mail Privacy Protection and security scanners
pre-load images, so an open alone is not treated as engagement.
"""
from __future__ import annotations

from datetime import datetime, timedelta

PERSONAL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "proton.me"}


def fit(contact: dict, policy: dict) -> dict:
    f = policy["fit"]
    pts, why = 0, []
    size = contact.get("company_size")
    if size is not None:
        s = 3 if size >= 1000 else 2 if size >= 200 else 1 if size >= 50 else 0
        pts += s
        why.append(f"size {size} (+{s})")
    else:
        why.append("size unknown (+0)")
    if contact.get("industry") in f["icp_industries"]:
        pts += 2
        why.append(f"ICP industry {contact['industry']} (+2)")
    title = contact.get("job_title", "").lower()
    if any(k in title for k in f["seniority_high"]):
        pts += 2
        why.append("senior title (+2)")
    elif any(k in title for k in f["seniority_mid"]):
        pts += 1
        why.append("manager-level title (+1)")
    domain = contact.get("email", "").split("@")[-1]
    if domain in PERSONAL_DOMAINS:
        pts -= 1
        why.append("personal email domain (-1)")
    tier = "A" if pts >= f["a_min"] else "B" if pts >= f["b_min"] else "C"
    return {"fit_tier": tier, "fit_points": pts, "fit_reasons": why}


def engagement(events: list, as_of: datetime, policy: dict) -> dict:
    e = policy["engagement"]
    window_start = as_of - timedelta(days=e["window_days"])
    score, last_meaningful, counted = 0.0, None, []
    for ev in events:
        w = e["weights"].get(ev["type"], 0)
        if w <= 0:
            continue
        if last_meaningful is None or ev["at"] > last_meaningful:
            last_meaningful = ev["at"]
        if ev["at"] < window_start:
            continue
        age = (as_of - ev["at"]).total_seconds() / 86400
        decayed = w * 0.5 ** (age / e["half_life_days"])
        score += decayed
        counted.append(ev["event_id"])
    days_since = None if last_meaningful is None else (as_of - last_meaningful).days
    if score >= e["hot_min"]:
        tier = "hot"
    elif score >= e["warm_min"]:
        tier = "warm"
    elif score > 0:
        tier = "cooling"
    else:
        tier = "dormant"
    return {"engagement_tier": tier, "engagement_score": round(score, 2),
            "days_since_engagement": days_since, "engagement_event_ids": counted}


def marketing_emails_in(events: list, as_of: datetime, days: int) -> int:
    start = as_of - timedelta(days=days)
    return sum(1 for ev in events if ev["type"] == "email_sent" and start <= ev["at"] <= as_of)


def segment_key(stage: str, eng_tier: str, fit_tier: str) -> str:
    return f"{stage}|{eng_tier}|fit-{fit_tier}"
