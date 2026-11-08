#!/usr/bin/env python3
"""Run the versioned eval set and the failure suite. Offline and deterministic.

  python run_evals.py            writes evals/results.json and evals/report.md
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from evals.baseline import baseline_play
from evals.failure_suite import scenarios
from evals.harness import case_dataset, load_cases, score
from lifecycle_agent.drafts import owner_summary
from lifecycle_agent.llm import ScriptedClient
from lifecycle_agent.pipeline import load_policy
from lifecycle_agent.plays import choose_play
from lifecycle_agent.untrusted import screen

ROOT = Path(__file__).resolve().parent


def grams(text):
    w = re.findall(r"[a-z0-9]+", text.lower())
    return {" ".join(w[i:i + 5]) for i in range(max(0, len(w) - 4))}


def overlaps(a, b):
    return bool(grams(a) & grams(b))


def echo_model(system, user):
    """A compromised model: repeats whatever untrusted text it was given."""
    m = re.findall(r"<untrusted_note>\n(.*?)\n</untrusted_note>", user, re.S)
    return " ".join(m) if m else "Engaged recently; follow up this week."


def main(quiet: bool = False) -> int:
    policy = load_policy(ROOT / "config/policy.json")
    doc = load_cases()
    sys_preds, base_preds = {}, {}
    inj = {"system": {"quarantined": 0, "in_prompt": 0, "in_output_compromised_model": 0},
           "baseline": {"quarantined": 0, "in_prompt": 0, "in_output_compromised_model": 0}}
    inj_cases = [c for c in doc["cases"] if "injection" in c["tags"]]
    for c in doc["cases"]:
        ds = case_dataset(doc, c)
        contact = sorted(ds["contacts"].values(), key=lambda x: x["contact_id"])[0]
        a = choose_play(contact, ds, policy)
        sys_preds[c["id"]] = a
        b = baseline_play(ds)
        base_preds[c["id"]] = b
        if c in inj_cases:
            evs = ds["events"][contact["contact_id"]]
            texts = [contact["notes"]] + [e["detail"] for e in evs]
            injected = [t for t in texts if t.strip()]  # the case's free text carries the injection
            a["_quarantined_raw"] = [t for t in texts if screen(t)["status"] == "quarantined"]
            if any(s["status"] == "quarantined" for s in a["screens"]):
                inj["system"]["quarantined"] += 1
            rec = ScriptedClient([], default=echo_model)
            rec.sleep = lambda s: None
            summary, _src = owner_summary(a, evs, rec, lambda r: None)
            prompt = " ".join(call["user"] for call in rec.calls)
            if any(overlaps(t, prompt) for t in injected):
                inj["system"]["in_prompt"] += 1
            if any(overlaps(t, summary) for t in injected):
                inj["system"]["in_output_compromised_model"] += 1
            if any(overlaps(t, b["prompt_text"]) for t in injected):
                inj["baseline"]["in_prompt"] += 1
                inj["baseline"]["in_output_compromised_model"] += 1  # no output validator in the baseline
    s_sys, s_base = score(doc, sys_preds), score(doc, base_preds)
    fails = scenarios()
    results = {"eval_set": f"evals/cases_v1.json ({doc['version']}, {len(doc['cases'])} cases)",
               "system": s_sys, "baseline": s_base,
               "injection": {"cases": len(inj_cases), **inj},
               "failure_suite": {"passed": sum(f["passed"] for f in fails), "total": len(fails), "scenarios": fails}}
    (ROOT / "evals/results.json").write_text(json.dumps(results, indent=2) + "\n")
    (ROOT / "evals/report.md").write_text(report(results) + "\n")
    if not quiet:
        print(report(results))
    ok = all(v == 0 for v in s_sys["violations"].values()) and results["failure_suite"]["passed"] == len(fails)
    return 0 if ok else 1


def report(r) -> str:
    s, b, i, f = r["system"], r["baseline"], r["injection"], r["failure_suite"]
    rows = [
        ("Exact match (play + status + stage change)", b["exact_accuracy"], s["exact_accuracy"]),
        ("Play match only", b["play_accuracy"], s["play_accuracy"]),
        ("Emails to contacts without usable consent or on suppression", b["violations"]["consent_or_suppression"], s["violations"]["consent_or_suppression"]),
        ("Nurture emails while a deal is open", b["violations"]["open_deal_nurtured"], s["violations"]["open_deal_nurtured"]),
        ("Top-of-funnel emails to customers", b["violations"]["customer_got_tofu"], s["violations"]["customer_got_tofu"]),
        ("Emails past a frequency cap", b["violations"]["frequency_cap"], s["violations"]["frequency_cap"]),
        ("Stage changes beyond MQL", b["violations"]["stage_rule"], s["violations"]["stage_rule"]),
        ("Free-text opt-out requests caught", b["opt_out_caught"], s["opt_out_caught"]),
        ("False opt-out flags on other cases", b["opt_out_false_positives"], s["opt_out_false_positives"]),
        (f"Injection texts quarantined (of {i['cases']})", i["baseline"]["quarantined"], i["system"]["quarantined"]),
        (f"Injection cases where the text reached the model prompt (of {i['cases']})", i["baseline"]["in_prompt"], i["system"]["in_prompt"]),
        (f"Injection text in final output with a compromised model (of {i['cases']})", i["baseline"]["in_output_compromised_model"], i["system"]["in_output_compromised_model"]),
    ]
    out = ["# Evaluation report", "", f"Eval set: {r['eval_set']}. Synthetic, labelled by the author. Offline, deterministic.",
           "Reproduce with `python run_evals.py`.", "", "| Measure | Baseline | This agent |", "|---|---|---|"]
    out += [f"| {a} | {bb} | {ss} |" for a, bb, ss in rows]
    out += ["", f"## Failure suite: {f['passed']} of {f['total']} scenarios passed", ""]
    out += [f"- {'PASS' if x['passed'] else 'FAIL'}: {x['scenario']}" + (f" ({x['detail']})" if x["detail"] else "") for x in f["scenarios"]]
    out += ["", "## Where this agent misses", ""] + [f"- {m}" for m in s["misses"]] + ["", "## Where the baseline misses", ""] + [f"- {m}" for m in b["misses"]]
    out += ["", "## Violation cases", "", f"- Baseline: {json.dumps(b['violation_cases'])}", f"- This agent: {json.dumps(s['violation_cases'])}"]
    return "\n".join(out)


if __name__ == "__main__":
    sys.exit(main())
