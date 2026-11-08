import unittest
from datetime import timedelta

from lifecycle_agent.controls import EMAIL_PLAYS, frequency_block, soft_email_blocks, stage_change_allowed
from lifecycle_agent.plays import plan
from tests.helpers import AS_OF, policy, sample_dataset


class ControlTests(unittest.TestCase):
    def setUp(self):
        self.p = policy()

    def test_stage_rules(self):
        self.assertTrue(stage_change_allowed("lead", "marketingqualifiedlead", self.p)[0])
        self.assertFalse(stage_change_allowed("lead", "customer", self.p)[0])
        self.assertFalse(stage_change_allowed("marketingqualifiedlead", "lead", self.p)[0])
        self.assertFalse(stage_change_allowed("unknown", "marketingqualifiedlead", self.p)[0])

    def test_soft_opt_in_only_for_customers(self):
        c = {"consent": "soft_opt_in", "stage": "lead", "marketing_contact": True}
        self.assertIn("soft_opt_in_only_valid_for_customers", soft_email_blocks(c, self.p))
        c["stage"] = "customer"
        self.assertEqual(soft_email_blocks(c, self.p), [])

    def test_legitimate_interest_is_not_consent_and_non_marketing_blocked(self):
        c = {"consent": "legitimate_interest", "stage": "lead", "marketing_contact": False,
             "email": "person@gmail.com", "company": "Acme Ltd"}
        blocks = soft_email_blocks(c, self.p)
        self.assertIn("legitimate_interests_is_not_consent", blocks)
        self.assertIn("eligibility_unverified", blocks)
        self.assertIn("non_marketing_contact", blocks)
        self.assertNotIn("legitimate_interest_not_accepted_for_marketing_email", blocks)

    def test_frequency_cap_and_cooldown(self):
        evs = [{"type": "email_sent", "at": AS_OF - timedelta(days=d)} for d in (1, 3)]
        reasons, nxt = frequency_block(evs, [], AS_OF, self.p)
        self.assertTrue(reasons and nxt)
        prior = [{"play": "RE_ENGAGE", "at": AS_OF - timedelta(days=3)}]
        self.assertTrue(frequency_block([], prior, AS_OF, self.p)[0])
        self.assertFalse(frequency_block([], [{"play": "RE_ENGAGE", "at": AS_OF - timedelta(days=20)}], AS_OF, self.p)[0])


class PlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = {x["contact_id"]: x for x in plan(sample_dataset(), policy())}

    def check(self, cid, play, status="PROPOSED"):
        self.assertEqual((self.a[cid]["play"], self.a[cid]["status"]), (play, status), self.a[cid]["reason_codes"])

    def test_expected_sample_plays(self):
        self.check("1003", "NURTURE_WELCOME")
        self.check("1004", "NURTURE_WELCOME", "HOLD")
        self.check("1005", "SUPPRESS")
        self.check("1006", "OWNER_ALERT")
        self.check("1007", "MQL_FOLLOW_UP")
        self.check("1008", "SQL_ASSIST")
        self.check("1009", "ONBOARD")
        self.check("1010", "EXPAND")
        self.check("1012", "RE_ENGAGE")
        self.check("1013", "SUNSET")
        self.check("1014", "NURTURE_EDUCATION", "DEFER")
        self.check("1015", "NURTURE_EDUCATION", "DEFER")
        self.check("1018", "DATA_REVIEW", "REVIEW")
        self.check("1027", "SALES_HAND_RAISE", "REVIEW")
        self.check("1035", "CUSTOMER_CHECK_IN", "REVIEW")

    def test_injection_cannot_lift_suppression(self):
        self.check("1021", "SUPPRESS")
        self.assertIn("quarantined_text:1021", self.a["1021"]["review_flags"])

    def test_opt_out_in_form_text_suppresses(self):
        self.check("1022", "SUPPRESS")
        self.assertIn("record_unsubscribe_in_hubspot_manually", self.a["1022"]["review_flags"])

    def test_open_deal_beats_usage_signal_for_customer(self):
        self.check("1029", "OWNER_ALERT")
        self.assertEqual(self.a["1029"]["route_to"], "Tom Becker")
        self.assertEqual(self.a["1029"]["task_owner_source"], "deal_owner")
        self.assertTrue(self.a["1029"]["task_deal_id"])
        self.assertNotIn(self.a["1029"]["play"], EMAIL_PLAYS)

    def test_low_fit_demo_is_review_not_a_sales_route(self):
        a = self.a["1027"]
        self.check("1027", "SALES_HAND_RAISE", "REVIEW")
        self.assertEqual(a["fit_label"], "low_fit")
        self.assertEqual(a["sales_route"], "pending_human_review")
        self.assertEqual(a["proposed_stage"], "")
        self.assertIn("low_fit_hand_raise", a["reason_codes"])

    def test_customers_never_get_top_of_funnel(self):
        for a in self.a.values():
            if a["stage"] in {"customer", "evangelist"}:
                self.assertNotIn(a["play"], {"NURTURE_WELCOME", "NURTURE_EDUCATION", "RE_ENGAGE"})

    def test_email_plays_proposed_only_when_emailable(self):
        ds = sample_dataset()
        for a in self.a.values():
            if a["play"] in EMAIL_PLAYS and a["status"] == "PROPOSED":
                c = ds["contacts"][a["contact_id"]]
                self.assertTrue(c["marketing_contact"])
                self.assertIn(c["consent"], {"explicit_opt_in", "soft_opt_in"})
                self.assertFalse(c["unsubscribed"] or c["hard_bounced"])

    def test_only_one_forward_stage_change_to_mql(self):
        changes = {k: a["proposed_stage"] for k, a in self.a.items() if a["proposed_stage"]}
        self.assertEqual(changes, {"1032": "marketingqualifiedlead"})


if __name__ == "__main__":
    unittest.main()
