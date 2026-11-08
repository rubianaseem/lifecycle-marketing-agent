"""Decisions recorded from Rubia on 8 Nov 2026. Local artifacts only."""
import csv
import io
import json
import unittest
from datetime import timedelta
from pathlib import Path

from lifecycle_agent.approval import ApprovalError, approve, release
from lifecycle_agent.controls import soft_email_blocks
from lifecycle_agent.ingest import build_dataset, norm_subscriber
from lifecycle_agent.pipeline import run
from lifecycle_agent.plays import choose_play
from lifecycle_agent.util import sha256_file, write_csv
from tests.helpers import AS_OF, ROOT, policy, tmpdir

APPROVERS = json.loads((ROOT / "config/approvers.json").read_text())
LOW = "low_fit_sales_tasks.csv"


def _contact(**over):
    row = {
        "Record ID": "T1", "Email": "person@evalco.example", "First Name": "Pat",
        "Company Name": "EvalCo", "Job Title": "Director", "Company Size": "200",
        "Industry": "software", "Lifecycle Stage": "lead", "Marketing contact status": "Marketing contact",
        "Consent Basis": "explicit", "Contact owner": "Owner One", "Create Date": "2026-03-01",
        "Date entered current stage": "2026-03-01",
    }
    row.update(over)
    return row


def _one(contact, events=None, deals=None, prior=None, suppression=None):
    return build_dataset([contact], events or [], deals or [], suppression or [], prior or [], AS_OF, AS_OF)


def _play(ds, p=None):
    p = p or policy()
    c = next(iter(ds["contacts"].values()))
    return choose_play(c, ds, p)


class EligibilityTests(unittest.TestCase):
    def setUp(self):
        self.p = policy()

    def test_subscriber_type_is_not_inferred(self):
        self.assertEqual(norm_subscriber(""), "unknown")
        self.assertEqual(norm_subscriber("gmail.com"), "unknown")
        self.assertEqual(norm_subscriber("Acme Ltd"), "unknown")
        self.assertEqual(norm_subscriber("corporate"), "corporate")
        ds = _one(_contact(**{
            "Email": "student@gmail.com", "Company Name": "Acme Ltd",
            "Consent Basis": "legitimate interest", "Job Title": "Student", "Company Size": "",
            "Industry": "education",
        }))
        c = ds["contacts"]["T1"]
        self.assertEqual(c["subscriber_type"], "unknown")
        blocks = soft_email_blocks(c, self.p)
        self.assertIn("eligibility_unverified", blocks)
        self.assertIn("legitimate_interests_is_not_consent", blocks)

    def test_individual_legitimate_interests_is_not_pecr_consent(self):
        ds = _one(_contact(**{
            "Subscriber type": "sole trader", "Consent Basis": "legitimate interest",
            "Lifecycle Stage": "lead",
        }))
        blocks = soft_email_blocks(ds["contacts"]["T1"], self.p)
        self.assertIn("legitimate_interests_is_not_pecr_consent", blocks)
        self.assertNotIn("explicit_opt_in", blocks)

    def test_corporate_without_assessment_is_held_as_demo_policy(self):
        ds = _one(_contact(**{"Subscriber type": "corporate", "Consent Basis": "legitimate interest"}))
        blocks = soft_email_blocks(ds["contacts"]["T1"], self.p)
        self.assertIn("legitimate_interests_assessment_not_recorded", blocks)
        self.assertIn("legitimate_interests_is_not_consent", blocks)
        self.assertFalse(self.p["email_eligibility"]["accept_corporate_legitimate_interests_without_lia"])

    def test_recorded_explicit_opt_in_stays_eligible(self):
        ds = _one(_contact(**{"Subscriber type": "individual", "Consent Basis": "explicit"}))
        self.assertEqual(soft_email_blocks(ds["contacts"]["T1"], self.p), [])

    def test_suppression_and_opt_out_beat_consent(self):
        suppressed = _one(_contact(), suppression=[{"Email or Domain": "person@evalco.example", "Reason": "list", "Added At": "2026-01-01"}])
        a = _play(suppressed)
        self.assertEqual(a["play"], "SUPPRESS")
        self.assertTrue(any(r.startswith("suppression_list") for r in a["reason_codes"]))
        opted = _one(_contact(**{"Unsubscribed from all email": "Yes", "Subscriber type": "corporate", "Consent Basis": "explicit"}))
        self.assertEqual(_play(opted)["play"], "SUPPRESS")
        self.assertIn("unsubscribed_from_all", _play(opted)["reason_codes"])


class RoutingTests(unittest.TestCase):
    def test_mql_creation_is_one_task_with_no_sla(self):
        p = policy()
        self.assertIsNone(p["mql_follow_up"]["sla_hours"])
        self.assertFalse(p["mql_follow_up"]["auto_escalate"])
        recent = _play(_one(_contact(**{
            "Lifecycle Stage": "MQL", "Date entered current stage": "2026-11-07 09:00", "Last Contacted": "",
        })))
        old = _play(_one(_contact(**{
            "Record ID": "T2", "Lifecycle Stage": "MQL", "Date entered current stage": "2026-10-01", "Last Contacted": "",
        })))
        self.assertEqual(recent["play"], "MQL_FOLLOW_UP")
        self.assertEqual(old["play"], "MQL_FOLLOW_UP")
        self.assertEqual(recent["status"], "PROPOSED")
        self.assertTrue(any(r.startswith("mql_created:") for r in recent["reason_codes"]))
        self.assertFalse(any("48" in r or "escalat" in r for r in recent["reason_codes"] + old["reason_codes"]))
        self.assertNotEqual(recent["task_event_key"], old["task_event_key"])

    def test_mql_event_id_and_prior_task_and_missing_owner(self):
        event = [{"Event ID": "M1", "Contact Record ID": "T1", "Email": "", "Event Type": "mql_created",
                  "Occurred At": "2026-11-04T09:00:00Z", "Detail": ""}]
        created = _play(_one(_contact(**{"Lifecycle Stage": "MQL", "Date entered current stage": "2026-10-01"}), event))
        self.assertEqual(created["play"], "MQL_FOLLOW_UP")
        self.assertIn("M1", created["evidence_event_ids"])
        self.assertIn("mql_created:event:M1", created["reason_codes"])
        prior = [{"Contact Record ID": "T1", "Play": "MQL_FOLLOW_UP", "Proposed At": "2026-11-04T10:00:00Z", "Outcome": "proposed"}]
        again = _play(_one(_contact(**{
            "Lifecycle Stage": "MQL", "Date entered current stage": "2026-10-01", "Consent Basis": "",
        }), event, prior=prior))
        self.assertNotEqual(again["play"], "MQL_FOLLOW_UP")
        self.assertEqual(again["status"], "HOLD")
        missing = _play(_one(_contact(**{
            "Lifecycle Stage": "MQL", "Date entered current stage": "2026-11-02", "Contact owner": "", "Last Contacted": "",
        })))
        self.assertEqual((missing["play"], missing["status"]), ("MQL_FOLLOW_UP", "REVIEW"))
        self.assertIn("no_owner_to_route_to", missing["review_flags"])

    def test_open_deal_task_uses_deal_owner_and_blocks_nurture(self):
        deal = [{"Deal ID": "D-9", "Associated Contact ID": "T1", "Deal Stage": "qualifiedtobuy",
                 "Is Closed": "false", "Is Closed Won": "false", "Deal Owner": "AE One", "Close Date": ""}]
        a = _play(_one(_contact(**{"Lifecycle Stage": "lead"}), deals=deal))
        self.assertEqual(a["play"], "OWNER_ALERT")
        self.assertEqual(a["route_to"], "AE One")
        self.assertEqual(a["task_owner_source"], "deal_owner")
        self.assertEqual(a["task_deal_id"], "D-9")
        self.assertEqual(a["dedupe"], "event")
        self.assertNotIn(a["play"], {"NURTURE_WELCOME", "NURTURE_EDUCATION", "RE_ENGAGE"})
        bare = _play(_one(_contact(**{"Lifecycle Stage": "lead", "Contact owner": ""}), deals=[{**deal[0], "Deal Owner": ""}]))
        self.assertEqual(bare["status"], "REVIEW")
        self.assertIn("no_owner_to_route_to", bare["review_flags"])

    def test_low_fit_label_and_approval_do_not_bypass(self):
        t = tmpdir()
        res = run(ROOT, t / "out", t / "state", AS_OF, policy())
        rd = Path(res["run_dir"])
        assigns = {r["contact_id"]: r for r in csv.DictReader(io.StringIO((rd / "play_assignments.csv").read_text()))}
        imported = list(csv.DictReader(io.StringIO((rd / "hubspot_import_proposed.csv").read_text())))
        self.assertEqual(assigns["1027"]["status"], "REVIEW")
        self.assertEqual(assigns["1027"]["fit_label"], "low_fit")
        self.assertNotIn("1027", {r["Record ID"] for r in imported})
        low = (rd / LOW).read_text()
        self.assertIn("1027", low)
        self.assertIn("low_fit", low)
        self.assertIn("low_fit_hand_raise", low)
        now = AS_OF + timedelta(hours=1)
        with self.assertRaises(ApprovalError):
            release(rd, LOW, now, policy())
        h = sha256_file(rd / LOW)
        with self.assertRaises(ApprovalError):
            approve(rd, LOW, h[:-1] + ("0" if h[-1] != "0" else "1"), "rubia", now, APPROVERS, policy())
        approve(rd, LOW, h, "rubia", now, APPROVERS, policy())
        released = release(rd, LOW, now, policy())
        released_text = released.read_text()
        self.assertIn("low_fit", released_text)
        self.assertIn("low_fit_hand_raise", released_text)
        original = (rd / LOW).read_text()
        (rd / LOW).write_text(original.replace("low_fit", "standard", 1))
        with self.assertRaises(ApprovalError):
            release(rd, LOW, now, policy())

    def test_mql_and_open_deal_tasks_are_not_recreated(self):
        t = tmpdir()
        data = t / "day1"
        data.mkdir()
        contacts = [
            _contact(**{"Record ID": "M1", "Email": "m1@evalco.example", "Lifecycle Stage": "MQL",
                        "Date entered current stage": "2026-11-02T08:00:00Z", "Last Contacted": ""}),
            _contact(**{"Record ID": "M2", "Email": "m2@evalco.example", "Lifecycle Stage": "MQL",
                        "Date entered current stage": "2026-11-02T08:00:00Z", "Last Contacted": "",
                        "Consent Basis": ""}),
            _contact(**{"Record ID": "D1", "Email": "d1@evalco.example", "Lifecycle Stage": "lead"}),
        ]
        deals = [{"Deal ID": "D-1", "Associated Contact ID": "D1", "Deal Stage": "qualifiedtobuy",
                  "Is Closed": "false", "Is Closed Won": "false", "Deal Owner": "AE One", "Close Date": ""}]
        fields_c = list(contacts[0].keys())
        write_csv(data / "sample_contacts.csv", contacts, fields_c)
        write_csv(data / "sample_engagement.csv", [
            {"Event ID": "E1", "Contact Record ID": "M1", "Email": "", "Event Type": "webinar attended",
             "Occurred At": "2026-11-01", "Detail": ""},
            {"Event ID": "E2", "Contact Record ID": "M2", "Email": "", "Event Type": "webinar attended",
             "Occurred At": "2026-11-01", "Detail": ""},
        ], ["Event ID", "Contact Record ID", "Email", "Event Type", "Occurred At", "Detail"])
        write_csv(data / "sample_deals.csv", deals, list(deals[0].keys()))
        write_csv(data / "sample_suppression.csv", [], ["Email or Domain", "Reason", "Added At"])
        write_csv(data / "sample_prior_plays.csv", [], ["Contact Record ID", "Play", "Proposed At", "Outcome"])
        (data / "sample_export_manifest.json").write_text(json.dumps({"exported_at": "2026-11-08T07:30:00Z"}))
        first = run(data, t / "out", t / "state", AS_OF, policy())
        rows = list(csv.DictReader(io.StringIO((Path(first["run_dir"]) / "hubspot_import_proposed.csv").read_text())))
        plays = {(r["Record ID"], r["lifecycle_next_play"]) for r in rows}
        self.assertIn(("M1", "MQL_FOLLOW_UP"), plays)
        self.assertIn(("M2", "MQL_FOLLOW_UP"), plays)
        self.assertIn(("D1", "OWNER_ALERT"), plays)
        day2 = t / "day2"
        day2.mkdir()
        for name in ["sample_contacts.csv", "sample_engagement.csv", "sample_deals.csv",
                     "sample_suppression.csv", "sample_prior_plays.csv"]:
            (day2 / name).write_bytes((data / name).read_bytes())
        (day2 / "sample_export_manifest.json").write_text(json.dumps({"exported_at": "2026-11-09T07:30:00Z"}))
        second = run(day2, t / "out", t / "state", AS_OF + timedelta(days=1), policy())
        assigns = {r["contact_id"]: r for r in csv.DictReader(io.StringIO((Path(second["run_dir"]) / "play_assignments.csv").read_text()))}
        imported = list(csv.DictReader(io.StringIO((Path(second["run_dir"]) / "hubspot_import_proposed.csv").read_text())))
        self.assertNotIn("MQL_FOLLOW_UP", {r["lifecycle_next_play"] for r in imported})
        self.assertEqual(assigns["M1"]["status"], "DUPLICATE")
        self.assertEqual(assigns["M2"]["status"], "DUPLICATE")
        self.assertNotIn(assigns["M1"]["play"], {"NURTURE_WELCOME", "NURTURE_EDUCATION", "RE_ENGAGE"})
        self.assertNotIn("M1", {r["Record ID"] for r in imported})
        self.assertNotIn("M2", {r["Record ID"] for r in imported})
        self.assertNotIn("D1", {r["Record ID"] for r in imported})
        self.assertEqual(assigns["D1"]["status"], "DUPLICATE")
        self.assertNotIn(assigns["D1"]["play"], {"NURTURE_WELCOME", "NURTURE_EDUCATION", "RE_ENGAGE", "ONBOARD", "EXPAND"})


if __name__ == "__main__":
    unittest.main()
