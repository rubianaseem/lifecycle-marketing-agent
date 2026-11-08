# Proposed HubSpot segments (run 3019d79ab3f2)

Specification only. Nothing here has been created in HubSpot. Build by hand after approval.

## Lifecycle agent - Nurture Welcome
- Type: active contact segment; expected members from this run: 1
- How to use: Enrol in the welcome sequence or workflow (3 emails over 2 weeks).
- Filters (all must be true):
  - `lifecycle_next_play` is NURTURE_WELCOME
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of subscriber, lead
  - `dealstage` none of open stages  (No associated deal in an open stage)
  - `hs_marketable_status` is Marketing contact
  - `hs_email_optout` is not true (Unsubscribed from all email)
  - `hs_email_hard_bounce_reason_enum` is unknown  (Hard bounce reason)
  - `Lifecycle agent - suppress` is not member
  - `Global suppression (your existing list)` is not member

## Lifecycle agent - Nurture Education
- Type: active contact segment; expected members from this run: 1
- How to use: Enrol in the education nurture.
- Filters (all must be true):
  - `lifecycle_next_play` is NURTURE_EDUCATION
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of subscriber, lead, marketingqualifiedlead
  - `dealstage` none of open stages  (No associated deal in an open stage)
  - `hs_marketable_status` is Marketing contact
  - `hs_email_optout` is not true (Unsubscribed from all email)
  - `hs_email_hard_bounce_reason_enum` is unknown  (Hard bounce reason)
  - `Lifecycle agent - suppress` is not member
  - `Global suppression (your existing list)` is not member

## Lifecycle agent - Re Engage
- Type: active contact segment; expected members from this run: 2
- How to use: Send the two-email re-engagement. Non-responders become SUNSET on a later run.
- Filters (all must be true):
  - `lifecycle_next_play` is RE_ENGAGE
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of subscriber, lead, marketingqualifiedlead, other
  - `dealstage` none of open stages  (No associated deal in an open stage)
  - `hs_marketable_status` is Marketing contact
  - `hs_email_optout` is not true (Unsubscribed from all email)
  - `hs_email_hard_bounce_reason_enum` is unknown  (Hard bounce reason)
  - `Lifecycle agent - suppress` is not member
  - `Global suppression (your existing list)` is not member

## Lifecycle agent - Onboard
- Type: active contact segment; expected members from this run: 1
- How to use: Enrol in onboarding. Customers never enter top-of-funnel nurture.
- Filters (all must be true):
  - `lifecycle_next_play` is ONBOARD
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of customer
  - `hs_marketable_status` is Marketing contact
  - `hs_email_optout` is not true (Unsubscribed from all email)
  - `hs_email_hard_bounce_reason_enum` is unknown  (Hard bounce reason)
  - `Lifecycle agent - suppress` is not member
  - `Global suppression (your existing list)` is not member

## Lifecycle agent - Expand
- Type: active contact segment; expected members from this run: 1
- How to use: Send expansion content and notify the account owner.
- Filters (all must be true):
  - `lifecycle_next_play` is EXPAND
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of customer, evangelist
  - `hs_marketable_status` is Marketing contact
  - `hs_email_optout` is not true (Unsubscribed from all email)
  - `hs_email_hard_bounce_reason_enum` is unknown  (Hard bounce reason)
  - `Lifecycle agent - suppress` is not member
  - `Global suppression (your existing list)` is not member

## Lifecycle agent - Suppress
- Type: static contact segment; expected members from this run: 8
- How to use: Static exclusion list 'Lifecycle agent - suppress'. Use it as an exclusion on every marketing send.
- Filters (all must be true):
  - `lifecycle_next_play` is SUPPRESS
  - `lifecycle_play_run_id` is 3019d79ab3f2

## Lifecycle agent - Sunset
- Type: static contact segment; expected members from this run: 1
- How to use: Review, then add to the suppress list or set as non-marketing contacts. Do not email.
- Filters (all must be true):
  - `lifecycle_next_play` is SUNSET
  - `lifecycle_play_run_id` is 3019d79ab3f2

## Lifecycle agent - Owner Alert
- Type: active contact segment; expected members from this run: 2
- How to use: One sales task for the open deal, carrying the deal id, stage and resolved owner. No marketing email. Do not create another task for the same open deal and owner.
- Filters (all must be true):
  - `lifecycle_next_play` is OWNER_ALERT
  - `lifecycle_play_run_id` is 3019d79ab3f2

## Lifecycle agent - Mql Follow Up
- Type: active contact segment; expected members from this run: 2
- How to use: One sales follow-up task for the contact owner when an MQL is created. No SLA and no automatic escalation. Do not send marketing email because this task exists.
- Filters (all must be true):
  - `lifecycle_next_play` is MQL_FOLLOW_UP
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of marketingqualifiedlead

## Lifecycle agent - Sales Hand Raise
- Type: active contact segment; expected members from this run: 3
- How to use: Workflow: create an owner task. The import also moves Lifecycle Stage forward to MQL where allowed.
- Filters (all must be true):
  - `lifecycle_next_play` is SALES_HAND_RAISE
  - `lifecycle_play_run_id` is 3019d79ab3f2

## Lifecycle agent - Sql Assist
- Type: active contact segment; expected members from this run: 1
- How to use: Owner task: send a relevant case study 1:1 and suggest a meeting.
- Filters (all must be true):
  - `lifecycle_next_play` is SQL_ASSIST
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of salesqualifiedlead

## Lifecycle agent - Customer Check In
- Type: active contact segment; expected members from this run: 1
- How to use: Owner (CSM) task: personal check-in. No automated email.
- Filters (all must be true):
  - `lifecycle_next_play` is CUSTOMER_CHECK_IN
  - `lifecycle_play_run_id` is 3019d79ab3f2
  - `lifecyclestage` is any of customer, evangelist

