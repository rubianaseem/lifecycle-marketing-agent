# Lifecycle run brief (2026-11-08)

- Run 3019d79ab3f2, policy 2026-11-08.2, mode: Offline (rules and templates; no model called)
- 34 contacts after de-duplication. 24 plays proposed, 3 held for email eligibility, 2 deferred by frequency caps, 5 need a decision, 0 already proposed by an earlier run.
- Proposed import: 24 rows, 1 forward stage changes (to MQL only).
- Free text quarantined: 2. Review queue items: 11.

## Owner tasks

- SALES_HAND_RAISE for 1001 (Northwind Logistics) -> Tom Becker: Asked for a demo or a sales call. Recent: webinar attended 14 Oct, pricing page view 04 Nov, demo request 05 Nov.
- OWNER_ALERT for 1006 (Brightwave) -> Ana Ruiz: Has an open deal, so marketing nurture stays off and one sales task is proposed (D-501). Recent: email click 02 Nov.
- MQL_FOLLOW_UP for 1007 (Quillstack) -> Sam Ortiz: Became an MQL; one sales follow-up task is proposed for that creation. Recent: demo request 01 Nov.
- SQL_ASSIST for 1008 (Kontor GmbH) -> Ana Ruiz: SQL since 2026-09-20 with no meeting booked. No recent meaningful engagement.
- CUSTOMER_CHECK_IN for 1011 (Pinegrove Retail) -> Sam Ortiz: Customer with no meaningful engagement in 90 days. No recent meaningful engagement.
- LOW FIT, HUMAN REVIEW BEFORE SALES for 1027 (no company) -> Tom Becker: Asked for a demo or a sales call, labelled low fit and held for human review before any sales routing. Recent: demo request 06 Nov.
- MQL_FOLLOW_UP for 1028 (Fjord Data) -> Ana Ruiz: Became an MQL; one sales follow-up task is proposed for that creation. Recent: form submission 03 Nov.
- OWNER_ALERT for 1029 (Cartograph) -> Tom Becker: Has an open deal, so marketing nurture stays off and one sales task is proposed (D-502). Recent: usage limit reached 30 Oct.
- SALES_HAND_RAISE for 1031 (Lattice Ops) -> Sam Ortiz: Asked for a demo or a sales call. Recent: pricing page view 02 Nov, contact-sales form 06 Nov.
- SALES_HAND_RAISE for 1032 (Beacon Freight) -> Tom Becker: Viewed pricing more than once in 14 days. Recent: pricing page view 01 Nov, pricing page view 06 Nov.
- CUSTOMER_CHECK_IN for 1035 (Kestrel) -> UNASSIGNED: Customer with no meaningful engagement in 90 days. No recent meaningful engagement.

## Next steps

1. Work through review_queue.csv.
2. Run `python agent.py show --run-dir <this folder>` and review each pending artifact.
3. Approve with the exact hash, then release. Import and build segments in HubSpot by hand.
