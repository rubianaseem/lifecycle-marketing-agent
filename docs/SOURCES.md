# Sources and inspiration

Read on 8 Nov 2026. Quotes in the README are copied from the pages as fetched. No code or text from any repository or post was reused.

## Primary sources

- ICO, Electronic mail marketing (guide to PECR): https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/electronic-mail-marketing/
  Used for: consent as the default for marketing email to individuals, and soft opt-in limited to existing customers. This shapes `allowed_consent_bases` and `customer_only_consent_bases`. It is a design input, not legal advice.
- HubSpot Knowledge Base, Use contact and company lifecycle stages: https://knowledge.hubspot.com/records/use-lifecycle-stages
  Used for: default stage order, and the fact that HubSpot tools only move the default property forward. That is why the agent only proposes forward moves, capped at MQL.
- HubSpot Knowledge Base, Set contacts as marketing: https://knowledge.hubspot.com/records/set-contacts-as-marketing
  Used for: marketing contact status as a separate gate from consent. Its quote: "If you don’t specify a marketing status when importing new contacts, they’ll be set as non-marketing by default." This is why non-marketing contacts are held, not emailed, and why the agent never sets marketing status itself.

## Public posts and projects checked for patterns (not copied)

- X, @Suryana2291, 8 Nov 2026: https://x.com/Suryana2291/status/2119409216460922987
  Their point was that "lapsed" is a consent state, not just a segment, so store consent source and check it before an AI builds a win-back flow. My version: consent is a hard gate in code before any play, and duplicates keep the most restrictive value.
- X, @getaudryo (vendor posts, Oct 2026), for example https://x.com/getaudryo/status/2113275690183487611
  Their pattern: an AI agent builds lifecycle journeys, and "nothing sends without your approval". My version: approval is bound to a file hash, edits void it, and the agent has no send path at all.
- GitHub, RonaldDavenport/tim (description and metadata only; no licence listed, so nothing reused): "Autonomous lifecycle marketing agent for PLG B2B SaaS with operator controls".
  My version is deliberately not autonomous.
- GitHub, jayush016/nba-ai-agents (description only; no licence listed): next-best-action multi-agent framing. My version uses a single deterministic play chooser with reason codes, so every decision can be replayed.

## Starter spec

My own `marketing-agents/lifecycle-marketing-agent/AGENT.md` and its context files (lifecycle definitions, plays, review learnings) set the scope: segment, recommend plays, draft emails and list criteria, and queue everything for approval without sending.

LinkedIn was not searched for this repo; I have no connector for it.
