# Details: costs, stack swaps, customising and production gaps

## How this runs today (and what production would add)

| Part | Status |
|---|---|
| Ingest, normalisation, duplicate merge, event hygiene | Implemented, tested locally on synthetic data |
| Fit and engagement scoring, 14 plays, hard controls | Implemented, tested locally, evaluated on 50 synthetic cases (evals/cases_v1.json) |
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

- `config/policy.json`: consent bases you accept, frequency caps, cooldown, SLA hours, dormant days, fit points, ICP industries and seniority words, internal and competitor domains, snapshot age, approval TTL.
- `config/approvers.json`: who may approve which artifact.
- `lifecycle_agent/plays.py`: precedence and new plays. Add the play to `PLAY_CHANNEL`, `criteria.PLAY_SPECS` and, if email, `controls.EMAIL_PLAYS` and `drafts.TEMPLATES`.
- `lifecycle_agent/untrusted.py`: pattern lists for opt-out and injection.

## Defaults that need a business decision

These are my defaults, written down so they can be changed deliberately:

- Legitimate interest is not accepted for marketing email (most restrictive). Some B2B teams email corporate subscribers under legitimate interest; that is a legal call for your DPO.
- Soft opt-in counts only for customers (stage customer or evangelist).
- Opens score zero.
- Any open deal blocks marketing email and routes to the deal owner. A team may prefer customer-marketing emails to continue during expansion deals.
- A suppressed contact with an open deal is SUPPRESS, not OWNER_ALERT; the owner already owns the deal.
- New MQLs inside the 48-hour SLA get no marketing email while sales works them.
- Hand-raises from fit C go to review rather than straight to sales.

## Real HubSpot export by API (design only)

- Private app with `crm.objects.contacts.read`, `crm.objects.deals.read` and read access to whatever stores consent. No write scopes.
- Page contacts with the CRM search endpoint, request only the properties in the contract, and write `exported_at` when the export starts.
- Respect rate-limit headers and back off on 429 (the same `call_with_retry` pattern).

## Production gaps

- Pattern screening misses paraphrases. A classifier would help, but the controls never read free text for anything except suppression, and missed injections cannot change plays. That is what keeps a miss survivable.
- Free-text opt-out detection has false positives. They suppress, which is the safe direction, but they still need review.
- One JSON ledger and local files suit one operator. A team needs a database and locking.
- No alerting, no scheduler, no portal integration.
