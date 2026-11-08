# Lifecycle Marketing Agent

An agent that segments HubSpot contacts, picks one next play, drafts nurture emails and segment criteria, and queues every file for review. Nothing is released until a person approves that exact file by its hash.

Built by Rubia Naseem, GTM Engineer (12+ yrs CRM/RevOps, HubSpot & Salesforce).

## The problem

The nurture workflow doesn't know a deal is open, and a re-engagement email can still go to someone who asked to stop. Two published rules shape the design:

> "You must not send marketing emails or texts to individuals without specific consent. There is a limited exception for your own previous customers, often called the ‘soft opt-in’."
> [ICO, Electronic mail marketing](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/electronic-mail-marketing/)

> "The default Lifecycle stage property can only be moved forward by HubSpot tools (e.g., import, form submission, API, Salesforce integration, and workflows)."
> [HubSpot, Use contact and company lifecycle stages](https://knowledge.hubspot.com/records/use-lifecycle-stages)

My [lifecycle-stage-audit-agent](https://github.com/rubianaseem/lifecycle-stage-audit-agent) fixes the stage property. This repo decides what happens next.

## What it does

- Reads five exports, merges duplicates keeping the most restrictive value, and scores fit and engagement. Opens score zero. One of 14 plays is chosen, with reason codes and evidence event ids.
- Hard controls stay in code: suppression, opt-outs, email eligibility, marketing-contact status, open-deal protection, frequency caps, and forward-only stage changes capped at MQL.
- Decisions recorded on 8 Nov 2026 ([docs/DETAILS.md](docs/DETAILS.md), [docs/SOURCES.md](docs/SOURCES.md)): low-fit demos wait for human review and stay labelled low fit after approval; one local sales task per MQL creation, with no SLA; one sales task per open deal, and no marketing nurture; unknown email eligibility is held. Legitimate interests is not called consent.
- Opt-out language suppresses the contact. Instruction-like text is quarantined and never reaches a model. Outputs are a report, assignments, a review queue, drafts, segment criteria, a proposed import, a low-fit task file, a brief and a hash-chained trace.

## Where each step runs

1. You run `agent.py run` from a terminal. It reads CSV exports and writes a local `outputs/run_<id>/` folder.
2. With `ANTHROPIC_API_KEY` set, Claude writes owner summaries and one extra draft variant per email play, then the validator checks them. Without a key, rules and templates are used and the files say so.
3. You approve one artifact by its full SHA-256 and release it, then import the CSV and build the segments in HubSpot yourself. There is no CRM write, send, Clay call or delete.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt     # standard library only
python run_demo.py                  # full scenario on synthetic data
python run_evals.py                 # writes evals/report.md
python -m unittest discover -s tests -t .
```

See [SETUP.md](SETUP.md) for real HubSpot exports, the optional Claude mode and troubleshooting.

## Example output

From `python run_demo.py` on synthetic contacts, offline. Approvals in that script are simulated.

```
  contacts 34 | proposed 24 | held for eligibility 3 | deferred by caps 2 | review 5 | quarantined text 2 | import rows 24
  release import before any approval                   REFUSED  hubspot_import_proposed.csv has not been approved
  Rubia approves the import with its full hash         ALLOWED
  release list criteria edited after approval          REFUSED  file changed after approval (hash mismatch); approval is void
  plays already proposed yesterday, skipped: 23 | new import rows: 1 (SALES_HAND_RAISE 1)
```

## Evaluation (measured locally, synthetic data)

`python run_evals.py` scores 58 hand-labelled cases in `evals/cases_v2.json` against a stage-and-recency baseline. v1 is kept unchanged.

| Measure | Baseline | This agent |
|---|---|---|
| Exact play and status | 0.241 | 0.966 |
| Emails without usable consent or on suppression | 17 | 0 |
| Nurture while a deal is open | 4 | 0 |
| Emails past a frequency cap | 3 | 0 |
| Injection texts quarantined (of 4) | 0 | 3 |
| Free-text opt-outs caught (of 2) | 0 | 1 |

Both misses are held-out phrasings. One paraphrased injection reached a prompt and could not change the play. The failure suite passes 24 of 24. See [docs/EVALUATION.md](docs/EVALUATION.md).

## Guardrails

- Approval needs a named approver and the full hash. Any later edit voids it. There is no auto-approve flag. Snapshots over 24 hours old cannot be approved.
- Low-fit demos are not in the import. They sit in `low_fit_sales_tasks.csv` until that file is approved. The low-fit label is part of the hash.
- Email segments re-check consent and suppression in HubSpot. Demo approvals are simulated on synthetic data and are not permission to touch a real portal.

## More

- [Architecture and data contracts](docs/ARCHITECTURE.md)
- [Decisions, costs and production gaps](docs/DETAILS.md)
- [Sources](docs/SOURCES.md)
- Related: [lifecycle-stage-audit-agent](https://github.com/rubianaseem/lifecycle-stage-audit-agent), [webinar-follow-up-agent](https://github.com/rubianaseem/webinar-follow-up-agent), [hubspot-mcp-slack-approval-agent](https://github.com/rubianaseem/hubspot-mcp-slack-approval-agent)
