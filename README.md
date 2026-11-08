# Lifecycle Marketing Agent

An agent that segments HubSpot contacts by lifecycle stage, engagement and fit, picks one next play per person, drafts nurture emails and segment criteria, and queues everything for review. Nothing is released until I approve the exact file by its hash.

Built by Rubia Naseem, GTM Engineer (12+ yrs CRM/RevOps, HubSpot & Salesforce).

## The problem

Lifecycle programmes break in the gaps between tools. The nurture workflow doesn't know a deal is open. The re-engagement email goes to someone who wrote "please stop emailing me" in a form. Two rules shape this repo:

> "You must not send marketing emails or texts to individuals without specific consent. There is a limited exception for your own previous customers, often called the ‘soft opt-in’."
> [ICO, Electronic mail marketing](https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/electronic-mail-marketing/)

> "The default Lifecycle stage property can only be moved forward by HubSpot tools (e.g., import, form submission, API, Salesforce integration, and workflows)."
> [HubSpot, Use contact and company lifecycle stages](https://knowledge.hubspot.com/records/use-lifecycle-stages)

I've built product activation and signal-triggered routing in production at Speechmatics and Six & Flow. Picking the play is the easy part. Knowing who must not get it is the hard part. My [lifecycle-stage-audit-agent](https://github.com/rubianaseem/lifecycle-stage-audit-agent) fixes the stage property. This repo decides what happens next.

## What it does

- Reads five exports (contacts, engagement, deals, suppression, prior plays), merges duplicates keeping the most restrictive consent, and scores fit and engagement. Opens score zero, because privacy features and scanners trigger them.
- Chooses one of 14 plays per contact, such as nurture, re-engage, onboard, expand, sales hand-raise, owner alert, sunset or suppress. Each play has reason codes and evidence event IDs.
- Applies hard controls in code: suppression and opt-outs, consent basis, marketing contact status, open-deal protection, frequency caps, a 48-hour MQL SLA and forward-only stage changes capped at MQL.
- Screens contact notes and form text. Opt-out requests suppress the contact. Text that matches instruction patterns is quarantined and never reaches a model.
- Writes a segment report, play assignments, review queue, nurture drafts, segment criteria, a proposed import, a brief and a hash-chained decision trace.

## Where each step runs

1. GitHub stores the code. You run it from Terminal, Mac Terminal or the Cursor terminal.
2. `agent.py run` reads CSV exports from HubSpot and writes to a local `outputs/run_<id>/` folder.
3. With `ANTHROPIC_API_KEY` set, the code calls Claude for owner summaries and one extra draft variant per play, then validates the output. Without a key, everything comes from rules and templates and says so.
4. You review the files, approve one artifact by its SHA-256, and release it. Then you import the CSV and build the segments in HubSpot yourself.
5. The agent writes nothing else: no CRM updates, no sends, no Clay calls, no deletes.

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

From `python run_demo.py` (synthetic contacts, offline):

```
  contacts 34 | proposed 24 | held for consent 3 | deferred by caps 2 | review 5 | quarantined text 2 | import rows 24
  release import before any approval                   REFUSED  hubspot_import_proposed.csv has not been approved
  Rubia approves the import with its full hash         ALLOWED
  release list criteria edited after approval          REFUSED  file changed after approval (hash mismatch); approval is void
  plays already proposed yesterday, skipped: 23 | new import rows: 1 (SALES_HAND_RAISE 1)
```

## Evaluation (measured locally, synthetic data)

`python run_evals.py` scores 50 hand-labelled cases against a stage-and-recency baseline like a typical nurture workflow:

| Measure | Baseline | This agent |
|---|---|---|
| Exact play and status | 0.26 | 0.96 |
| Emails without usable consent or on suppression | 13 | 0 |
| Nurture while a deal is open | 2 | 0 |
| Emails past a frequency cap | 3 | 0 |
| Injection texts quarantined (of 4) | 0 | 3 |
| Free-text opt-outs caught (of 2) | 0 | 1 |

Both play misses are held-out phrasings: a polite opt-out the patterns miss, and a product question mentioning "unsubscribe" that gets wrongly suppressed. A paraphrased injection also slipped through screening, but it could not change any play. The failure suite passes 24 of 24. This is my own labelled set, not production data. See [docs/EVALUATION.md](docs/EVALUATION.md).

## Guardrails and human in the loop

- Approvable files start as PENDING_APPROVAL. Approval needs a named approver and the full hash of the reviewed file. Any later edit voids it. There is no auto-approve flag.
- Snapshots over 24 hours old are refused, and forced stale runs can't be approved.
- Email segments re-check consent and suppression inside HubSpot, so a later unsubscribe still wins.
- Demo approvals are simulated on synthetic data, not permission to touch a real portal.

## More

- [Architecture and data contracts](docs/ARCHITECTURE.md)
- [Costs, stack swaps and production gaps](docs/DETAILS.md)
- [Sources and inspiration](docs/SOURCES.md)
- Related: [lifecycle-stage-audit-agent](https://github.com/rubianaseem/lifecycle-stage-audit-agent), [webinar-follow-up-agent](https://github.com/rubianaseem/webinar-follow-up-agent), [hubspot-mcp-slack-approval-agent](https://github.com/rubianaseem/hubspot-mcp-slack-approval-agent)
