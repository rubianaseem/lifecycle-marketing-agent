# Details: costs, stack swaps, customising and production gaps

## How this runs today (and what production would add)

| Part | Status |
|---|---|
| Ingest, normalisation, duplicate merge, event hygiene | Implemented, tested locally on synthetic data |
| Fit and engagement scoring, 14 plays, hard controls | Implemented, tested locally, evaluated on 58 synthetic cases (evals/cases_v2.json; v1 kept) |
| Free-text screening (opt-out and injection patterns) | Implemented, tested locally. Pattern based, so paraphrases get through (see EVALUATION.md) |
| Output validator and template fallback | Implemented, tested with scripted model doubles |
| Claude calls (`AnthropicClient`) | Implemented. Error path checked once against the real endpoint with an invalid key (401, not retried, templates used). Successful live calls not tested and not part of any reported number |
| Retry, backoff, Retry-After handling | Implemented, tested with scripted 429, 500 and 400 errors |
| Checkpoint resume, replay, ledger idempotency, stale-snapshot refusal | Implemented, tested locally |
| Hash-bound approval, release, hash-chained logs | Implemented, tested locally |
| HubSpot segment criteria | Proposed specification. Not built in a portal; property names must be checked in yours |
| HubSpot API export, scheduling, hosting | Not built (designed only, see below) |
| Integrated with a live HubSpot portal | No |
| Production-proven | No |

## API cost assumptions

I have no access to anyone's billing, so this is a sizing method, not a price. Offline mode makes no model calls. In Claude mode the agent makes one call per owner-task contact (PROPOSED or REVIEW), each a short system prompt plus a few hundred tokens of facts and screened note, and one call per email play for a draft variant (aggregate facts only). Failed calls retry up to three times. Calls = owner-task contacts + email plays used (+ retries). Multiply by your token sizes and check current per-token prices on Anthropic's pricing page.

## Stack swaps

| This repo | Swap for | What changes |
|---|---|---|
| CSV exports | HubSpot CRM v3 search API (read-only private app) | A loader that writes the same columns; nothing downstream changes |
| HubSpot | Salesforce | Map lifecycle to Lead Status / Contact fields, campaigns for segments, `HasOptedOutOfEmail` for unsubscribed |
| Consent Basis property | Your consent platform export | Map values in `CONSENT_ALIASES` |
| JSON ledger | Postgres table | Same key; unique constraint on `play_key` |
| Local approval CLI | Slack approval bound to the hash | Reuse the pattern from hubspot-mcp-slack-approval-agent |
| Templates | Your approved copy library | Edit `TEMPLATES` in `drafts.py` |
| Claude | Another model | Implement `complete(system, user)`; keep the validator |
| Manual weekly run | n8n or cron | Schedule `agent.py run`; approval stays manual |

## Customise for your stack

- `config/policy.json`: consent bases you accept, frequency caps, cooldown, dormant days, fit points, ICP industries and seniority words, internal and competitor domains, snapshot age, approval TTL. `mql_follow_up.sla_hours` is null and `auto_escalate` is false; the code does not read them as a timer. `email_eligibility` holds the demo defaults for unverified corporate legitimate interests.
- `config/approvers.json`: who may approve which artifact.
- `lifecycle_agent/plays.py`: precedence and new plays. Add the play to `PLAY_CHANNEL`, `criteria.PLAY_SPECS` and, if email, `controls.EMAIL_PLAYS` and `drafts.TEMPLATES`.
- `lifecycle_agent/untrusted.py`: pattern lists for opt-out and injection.

## Decisions recorded on 8 Nov 2026

Rubia answered the open policy questions on 8 Nov 2026. These are the rules in code. They are not a claim that every personal or company policy is known, and they are not legal advice. Citations and the limits of the research are in [SOURCES.md](SOURCES.md).

- Low-fit demo and contact-sales requests go to human review first. They are not in the proposed import. After `low_fit_sales_tasks.csv` is approved by its full hash, that file is a local sales-task plan. The low-fit label and the reasons stay in the approved bytes. Editing the label voids the approval.
- Creating an MQL proposes one local sales follow-up task for that creation event (`MQL_FOLLOW_UP`). The same event is not proposed again on a later snapshot. A missing owner goes to review. There is no SLA and no automatic escalation. `mql_follow_up.sla_hours` is null on purpose. If sales was already contacted after that creation, or a prior play already records the task, a second task is not opened. Removing the old 48-hour hold does not itself send marketing email. Eligibility, suppression and frequency still decide any later email play.
- An open deal proposes one sales task with the deal id, stage and resolved owner (deal owner, otherwise contact owner, otherwise review). The same deal set and owner are not tasked again. The task text does not invent per-deal instructions. Marketing email stays off. No exception flag was added.
- A suppressed or unsubscribed contact is SUPPRESS even if they also have an open deal or a recorded opt-in.
- Email eligibility holds unknown or unverified subscriber type, PECR consent and lawful basis. Subscriber type is an explicit column. It is not inferred from the email domain or the company name. Legitimate interests is a UK GDPR lawful basis, not PECR consent, and the reason codes say so. Recorded explicit opt-in can still pass, including when subscriber type is blank, because that is the stricter individual-subscriber rule. Soft opt-in still passes only for customer or evangelist stage, and that check does not prove the other soft-opt-in conditions. A recorded corporate subscriber with only an unassessed legitimate-interests label is held. That hold is this repo's demo default (`accept_corporate_legitimate_interests_without_lia` is false). ICO guidance does not say that legitimate interests is unlawful for every corporate subscriber.
- Opens score zero.

Still not decided here: the rest of a live portal's consent taxonomy, who may rely on a finished legitimate-interests assessment, and whether any future open-deal marketing exception should exist. Those need a later decision. Nothing in this repo sends mail.

## Real HubSpot export by API (design only)

- Private app with `crm.objects.contacts.read`, `crm.objects.deals.read` and read access to whatever stores consent. No write scopes.
- Page contacts with the CRM search endpoint, request only the properties in the contract, and write `exported_at` when the export starts.
- Respect rate-limit headers and back off on 429 (the same `call_with_retry` pattern).

## Production gaps

- Pattern screening misses paraphrases. A classifier would help, but the controls never read free text for anything except suppression, and missed injections cannot change plays. That is what keeps a miss survivable.
- Free-text opt-out detection has false positives. They suppress, which is the safe direction, but they still need review.
- One JSON ledger and local files suit one operator. A team needs a database and locking.
- No alerting, no scheduler, no portal integration.
