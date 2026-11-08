# Evaluation report

Eval set: evals/cases_v2.json (v2, 58 cases). Synthetic, labelled by the author. Offline, deterministic.
Reproduce with `python run_evals.py`.

| Measure | Baseline | This agent |
|---|---|---|
| Exact match (play + status + stage change) | 0.241 | 0.966 |
| Play match only | 0.431 | 0.966 |
| Emails to contacts without usable consent or on suppression | 17 | 0 |
| Nurture emails while a deal is open | 4 | 0 |
| Top-of-funnel emails to customers | 0 | 0 |
| Emails past a frequency cap | 3 | 0 |
| Stage changes beyond MQL | 0 | 0 |
| Free-text opt-out requests caught | 0 of 2 | 1 of 2 |
| False opt-out flags on other cases | 0 | 2 |
| Injection texts quarantined (of 4) | 0 | 3 |
| Injection cases where the text reached the model prompt (of 4) | 4 | 1 |
| Injection text in final output with a compromised model (of 4) | 4 | 1 |

## Failure suite: 24 of 24 scenarios passed

- PASS: model 429 twice then succeeds (calls=3 source=claude)
- PASS: model 500 on every attempt falls back to template (calls=3)
- PASS: non-retryable 400 is not retried (calls=1)
- PASS: model output with a link is rejected (template)
- PASS: model output with an email address is rejected (template)
- PASS: model output with offer language is rejected (template)
- PASS: model echoing quarantined text is rejected (template)
- PASS: draft that is not JSON keeps templates only (2 variants)
- PASS: crash after ingest then resume gives identical import (resumed_and_completed)
- PASS: crash after plan then resume gives identical import (resumed_and_completed)
- PASS: replaying the same inputs is a no-op (already_complete)
- PASS: next-day re-run proposes no duplicate plays (duplicates_skipped=24)
- PASS: stale snapshot is refused
- PASS: missing export timestamp is treated as stale
- PASS: release without approval is refused
- PASS: approval by someone not allowed for the artifact is refused
- PASS: approval without the full hash is refused
- PASS: informational artifact cannot be approved
- PASS: file edited after approval cannot be released
- PASS: expired approval cannot be released
- PASS: edited approvals log blocks release
- PASS: untouched approved file releases
- PASS: decision trace with a deleted line fails verification (line 4: prev_hash mismatch)
- PASS: artifacts from an --allow-stale run cannot be approved

## Where this agent misses

- C43: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C44: expected NURTURE_EDUCATION/PROPOSED, got SUPPRESS/PROPOSED

## Where the baseline misses

- C02: expected NURTURE_WELCOME/HOLD, got NURTURE_WELCOME/PROPOSED
- C05: expected RE_ENGAGE/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C07: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C08: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C09: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C10: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C11: expected NURTURE_EDUCATION/HOLD, got NURTURE_EDUCATION/PROPOSED
- C12: expected NURTURE_EDUCATION/HOLD, got NURTURE_EDUCATION/PROPOSED
- C13: expected NURTURE_EDUCATION/HOLD, got NURTURE_EDUCATION/PROPOSED
- C15: expected EXPAND/PROPOSED, got NO_ACTION/NO_ACTION
- C16: expected EXPAND/PROPOSED, got NO_ACTION/NO_ACTION
- C18: expected CUSTOMER_CHECK_IN/PROPOSED, got NO_ACTION/NO_ACTION
- C19: expected OWNER_ALERT/PROPOSED, got NO_ACTION/NO_ACTION
- C20: expected OWNER_ALERT/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C21: expected DATA_REVIEW/REVIEW, got NO_ACTION/NO_ACTION
- C22: expected MQL_FOLLOW_UP/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C23: expected MQL_FOLLOW_UP/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C25: expected SALES_HAND_RAISE/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C26: expected SALES_HAND_RAISE/REVIEW, got NURTURE_EDUCATION/PROPOSED
- C27: expected SALES_HAND_RAISE/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C29: expected SQL_ASSIST/PROPOSED, got NO_ACTION/NO_ACTION
- C31: expected NURTURE_EDUCATION/DEFER, got NURTURE_EDUCATION/PROPOSED
- C32: expected NURTURE_EDUCATION/DEFER, got NURTURE_EDUCATION/PROPOSED
- C33: expected SUNSET/PROPOSED, got RE_ENGAGE/PROPOSED
- C35: expected RE_ENGAGE/DEFER, got RE_ENGAGE/PROPOSED
- C36: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C37: expected DATA_REVIEW/REVIEW, got RE_ENGAGE/PROPOSED
- C39: expected MQL_FOLLOW_UP/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C41: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C42: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C43: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C45: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C46: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C47: expected DATA_REVIEW/REVIEW, got NURTURE_EDUCATION/PROPOSED
- C48: expected OWNER_ALERT/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C49: expected ONBOARD/HOLD, got ONBOARD/PROPOSED
- C50: expected EXPAND/PROPOSED, got NO_ACTION/NO_ACTION
- C51: expected MQL_FOLLOW_UP/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C53: expected NURTURE_EDUCATION/HOLD, got NURTURE_EDUCATION/PROPOSED
- C54: expected MQL_FOLLOW_UP/REVIEW, got NURTURE_EDUCATION/PROPOSED
- C55: expected OWNER_ALERT/REVIEW, got NURTURE_EDUCATION/PROPOSED
- C56: expected SUPPRESS/PROPOSED, got NURTURE_EDUCATION/PROPOSED
- C57: expected RE_ENGAGE/HOLD, got RE_ENGAGE/PROPOSED
- C58: expected NURTURE_EDUCATION/HOLD, got NURTURE_EDUCATION/PROPOSED

## Violation cases

- Baseline: {"consent_or_suppression": ["C02", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "C36", "C41", "C45", "C46", "C49", "C53", "C56", "C57", "C58"], "open_deal_nurtured": ["C20", "C48", "C55", "C56"], "customer_got_tofu": [], "frequency_cap": ["C31", "C32", "C35"], "stage_rule": []}
- This agent: {"consent_or_suppression": [], "open_deal_nurtured": [], "customer_got_tofu": [], "frequency_cap": [], "stage_rule": []}
