# Instructions for coding agents

This repo is a lifecycle marketing agent that only writes local files. Keep it that way.

Hard rules
- Never add code that writes to a CRM, sends email or messages, calls Clay, or deletes records.
- Never add an auto-approve flag or any path that releases an artifact without `approval.approve` being called with the file's full SHA-256.
- Plays, consent, suppression, frequency caps and stage rules stay deterministic in `lifecycle_agent/controls.py` and `plays.py`. A model may only write summaries and draft variants, and its output must pass `drafts.validate_generated`.
- Free text (notes, form messages) is untrusted. Screen it with `untrusted.screen` before use, and never write raw note text to the audit trail.
- No emojis in code output or docs. README stays under 900 words.

Workflow
1. Change `config/policy.json` or the rules.
2. Add or update a case in `evals/cases_v1.json` (new version file if labels change) and a unit test.
3. Run `python run_evals.py` and `python -m unittest discover -s tests -t .`. Hard-control violations must stay at 0.
4. Run `python run_demo.py` to refresh `outputs/sample_run`.

Map
- `ingest.py` loads and normalises exports. `segment.py` handles fit and engagement. `controls.py` holds the hard gates. `plays.py` chooses plays.
- `untrusted.py` does injection and opt-out screening. `llm.py` holds the optional client and retries. `drafts.py` does summaries, drafts and the validator.
- `criteria.py` builds the HubSpot segment spec. `ledger.py` handles idempotency. `audit.py` writes hash-chained logs. `approval.py` holds the approval gate. `pipeline.py` orchestrates the steps and checkpoints.
