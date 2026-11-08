# Sources and inspiration

Read on 8 Nov 2026. Quotes in the README are copied from the pages as fetched. No code or text from any repository or post was reused.

## Primary sources

- ICO, Electronic mail marketing (guide to PECR): https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guide-to-pecr/electronic-and-telephone-marketing/electronic-mail-marketing/
  Used for the README quote on consent for individuals and the soft opt-in. A direct fetch on 8 Nov 2026 returned 403, so the operational rules below come from the two ICO pages that did load, not from a guess about this page.
- ICO, How do we comply with the PECR electronic mail marketing rules? (read 8 Nov 2026): https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/guidance-on-direct-marketing-using-electronic-mail/how-do-we-comply-with-the-pecr-electronic-mail-marketing-rules/
  Unsolicited electronic mail to individual subscribers needs consent or every requirement of a soft opt-in. Corporate subscribers are not subject to that consent rule. Both types must be given a valid opt-out address, and the sender must not hide their identity. Consent, taken from the UK GDPR, is a freely given, specific, informed and unambiguous indication by a clear affirmative action. Silence, inactivity and pre-ticked boxes are not consent. The products-and-services soft opt-in needs all of: details obtained directly from the person; during a sale or negotiations for a sale; your own similar products and services only; an opt-out when the details were collected; an opt-out in every later message.
- ICO, Business-to-business marketing (read 8 Nov 2026): https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/business-to-business-marketing/
  Corporate subscribers include companies, LLPs, Scottish partnerships and some government bodies. Sole traders, some partnerships (including non-limited-liability partnerships in England, Wales and Northern Ireland) and other unincorporated bodies are individual subscribers. An employee address at a company can be a corporate subscriber because the subscriber is the employer. UK GDPR still applies to personal data of people in a business context, and those people can object or withdraw consent.
- ICO, Legitimate interests (read via ICO search snippet, 8 Nov 2026): https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/a-guide-to-lawful-basis/legitimate-interests/
  Legitimate interests is one of the UK GDPR lawful bases. It is not consent. It has a three-part test: purpose, necessity, and balancing against the person's rights. It can be used for direct marketing only where PECR does not require consent.
- ICO, Plan direct marketing (read 8 Nov 2026): https://ico.org.uk/for-organisations/direct-marketing-and-privacy-and-electronic-communications/direct-marketing-guidance/plan-direct-marketing/
  Same split: electronic-mail consent and soft opt-in protect individual subscribers, including sole traders and some partnerships, and do not apply to corporate subscribers. Where PECR does not require consent, legitimate interests may be the data-protection basis after the three-part test, with a clear opt-out.

- HubSpot Knowledge Base, Use contact and company lifecycle stages: https://knowledge.hubspot.com/records/use-lifecycle-stages
  Used for: default stage order, and the fact that HubSpot tools only move the default property forward. That is why the agent only proposes forward moves, capped at MQL.
- HubSpot Knowledge Base, Set contacts as marketing: https://knowledge.hubspot.com/records/set-contacts-as-marketing
  Used for: marketing contact status as a separate gate from consent. Its quote: "If you don’t specify a marketing status when importing new contacts, they’ll be set as non-marketing by default." This is why non-marketing contacts are held, not emailed, and why the agent never sets marketing status itself.

This is a design input, not legal advice. The agent does not send email.

## What the eligibility code assumes, and what it does not decide

- Unknown or unrecognised subscriber type, PECR consent or lawful basis is held. Company name and email domain are not used as a subscriber type. `gmail.com` and a name ending in "Ltd" stay unknown.
- A recorded explicit opt-in can clear the email gate, including when subscriber type is blank. That uses the stricter individual-subscriber rule. It does not decide that the person is an individual or a company.
- Soft opt-in clears the gate only for lifecycle stage customer or evangelist. That is a proxy for an existing customer. The other ICO conditions (direct collection, similar products, opt-out at collection and in every message) are not checked.
- A recorded `corporate` subscriber with only a legitimate-interests label, and no recorded assessment, is held. The switches `accept_corporate_legitimate_interests_without_lia` and `accept_recorded_lia_for_corporate` are false. ICO guidance allows legitimate interests for some corporate marketing where PECR does not require consent. This hold is the demo default, not a statement that the basis is always unlawful.
- Opt-out, unsubscribe, hard bounce and the suppression list win over consent and over legitimate interests.
- The charitable soft opt-in, and solicited mail that someone specifically asked to receive, are not separate paths.
- No legitimate-interests assessment is performed here. A partnership is not classified as Scottish, English, Welsh or Northern Irish from its name.

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
