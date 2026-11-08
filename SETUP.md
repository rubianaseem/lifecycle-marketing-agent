# Setup

## 1. Install and run the sample

```bash
git clone https://github.com/rubianaseem/lifecycle-marketing-agent.git
cd lifecycle-marketing-agent
python3 -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt                          # nothing to install; standard library only
python agent.py run --as-of 2026-11-08T12:00:00Z         # the sample snapshot is dated 8 Nov 2026
python agent.py show --run-dir outputs/run_<id>
```

`--as-of` pins "now" so the sample is reproducible. On real data, leave it out and the current time is used.

Other commands:

```bash
python run_demo.py                          # approval, resume, stale and tamper scenarios
python run_evals.py                         # eval set + failure suite -> evals/report.md
python -m unittest discover -s tests -t .   # test suite
python agent.py verify --path state/audit.jsonl
```

## 2. Review, approve, release

1. Open `outputs/run_<id>/brief.md`, then `review_queue.csv`. Fix anything flagged in HubSpot and re-run if needed.
2. Read the three approvable files: `hubspot_import_proposed.csv`, `list_criteria.json` (human-readable copy in `list_criteria.md`) and `nurture_drafts.md`.
3. `python agent.py show --run-dir outputs/run_<id>` prints each file's SHA-256.
4. Approve one file at a time, using the hash you saw:
   `python agent.py approve --run-dir outputs/run_<id> --artifact hubspot_import_proposed.csv --sha256 <hash> --approver rubia`
5. `python agent.py release --run-dir outputs/run_<id> --artifact hubspot_import_proposed.csv` copies it to `released/` after re-checking the hash, expiry and snapshot age.
6. In HubSpot, by hand: create the three custom properties listed in `list_criteria.json`, import the released CSV (Contacts, update existing by Record ID), build the segments as specified and paste approved draft text into your emails. Lifecycle Stage cells are blank except forward moves to MQL; check in the import preview that blank cells will not overwrite existing values.

Approvers live in `config/approvers.json`. Edit names and allowed artifacts there.

## 3. Use your own HubSpot data

Export these as CSV and name them with a prefix, for example `mydata_contacts.csv`, then run `python agent.py run --data exports --prefix mydata_`.

| File | Where it comes from | Columns |
|---|---|---|
| `_contacts.csv` | Contacts view export | Record ID, Email, First Name, Company Name, Job Title, Company Size, Industry, Country/Region, Lifecycle Stage, Lead Status, Marketing contact status, Consent Basis, Unsubscribed from all email, Hard bounced, Create Date, Became a Customer Date, Date entered current stage, Last Contacted, Contact owner, Notes |
| `_engagement.csv` | Activity or event export, or your warehouse | Event ID, Contact Record ID, Email, Event Type, Occurred At, Detail |
| `_deals.csv` | Deals export with associated contact | Deal ID, Associated Contact ID, Deal Stage, Is Closed, Is Closed Won, Deal Owner, Close Date |
| `_suppression.csv` | Your suppression lists | Email or Domain (use `@domain` for domains), Reason, Added At |
| `_prior_plays.csv` | Previous runs or your own history | Contact Record ID, Play, Proposed At, Outcome |
| `_export_manifest.json` | You write it | `{"exported_at": "2026-11-08T07:30:00Z"}` |

Consent Basis is often a custom property. Map your values to explicit opt-in, soft opt-in, legitimate interest or withdrawn (see `CONSENT_ALIASES` in `lifecycle_agent/ingest.py`).

Pulling the exports by API instead (not built here): create a HubSpot private app with read-only scopes such as `crm.objects.contacts.read` and `crm.objects.deals.read`, and write the same CSV columns. Do not grant write scopes; this agent never needs them.

## 4. Optional: Claude

```bash
pip install -r requirements-claude.txt
export ANTHROPIC_API_KEY=...          # or put it in .env and load it yourself
python agent.py run
```

Claude writes owner why-now summaries and one extra draft variant per email play. Plays, controls and routing never depend on it. If calls fail after three attempts with backoff, or the output fails validation, the template is used and the audit log records why. Set `ANTHROPIC_MODEL` to change the model.

## 5. Extending with Cursor, Claude Code, Codex CLI or Grok

Open the folder and point the assistant at `AGENTS.md` (or `CLAUDE.md`). Good first tasks: add a play, change the fit model in `config/policy.json`, or add a consent alias. Ask it to add an eval case in `evals/cases_v1.json` (bump to v2 if you change labels) and a test for every rule change, then run the evals and tests.

## Troubleshooting

| Message | Fix |
|---|---|
| `REFUSED: snapshot age ... exceeds 24` | Re-export, update `exported_at`, re-run. `--allow-stale` runs but cannot be approved. |
| `APPROVAL REFUSED: hash does not match` | You reviewed a different version. Run `show` again and use the current hash. |
| `file differs from what this run generated` | Outputs were edited. Fix the source data or policy and re-run instead. |
| `RELEASE REFUSED: approval expired` | Approvals last 72 hours (`approval_ttl_hours`). Review and approve again. |
| `already_complete` | Same inputs as an earlier run. Change the export or `--as-of` for a new run. |
| Many `DATA_REVIEW` rows | Usually blank or custom lifecycle values. See lifecycle-stage-audit-agent. |
| `CRASHED: simulated crash` | `LMA_FAIL_AFTER` is set. Unset it and re-run to resume. |
