import unittest

from lifecycle_agent.ingest import build_dataset, norm_consent, norm_stage
from lifecycle_agent.util import parse_dt, read_csv
from tests.helpers import AS_OF, ROOT, sample_dataset


class IngestTests(unittest.TestCase):
    def test_stage_aliases_and_unknown(self):
        self.assertEqual(norm_stage("MQL"), "marketingqualifiedlead")
        self.assertEqual(norm_stage("Sales Qualified Lead"), "salesqualifiedlead")
        self.assertEqual(norm_stage("Trial User"), "unknown")
        self.assertEqual(norm_stage(""), "none")

    def test_consent_aliases_default_unknown(self):
        self.assertEqual(norm_consent("Explicit opt-in"), "explicit_opt_in")
        self.assertEqual(norm_consent("soft opt-in"), "soft_opt_in")
        self.assertEqual(norm_consent("opted out"), "withdrawn")
        self.assertEqual(norm_consent("maybe"), "unknown")

    def test_dates_day_first_and_invalid(self):
        self.assertEqual(parse_dt("01/10/2026").month, 10)
        self.assertIsNone(parse_dt("31/02/2025"))
        self.assertEqual(parse_dt("2026-11-01T09:00:00.000Z").hour, 9)

    def test_comment_line_skipped_and_marked_synthetic(self):
        first = (ROOT / "sample_contacts.csv").read_text().splitlines()[0]
        self.assertTrue(first.startswith("# SYNTHETIC"))
        self.assertEqual(read_csv(ROOT / "sample_contacts.csv")[0]["Record ID"], "1001")

    def test_duplicate_merge_keeps_most_restrictive_consent(self):
        ds = sample_dataset()
        self.assertNotIn("1002", ds["contacts"])
        c = ds["contacts"]["1001"]
        self.assertEqual(c["merged_ids"], ["1002"])
        self.assertEqual(c["consent"], "unknown")
        self.assertEqual(c["stage"], "marketingqualifiedlead")

    def test_event_hygiene_counts(self):
        ds = sample_dataset()
        self.assertEqual(ds["counts"]["events_duplicate"], 1)
        self.assertEqual(ds["counts"]["events_future"], 1)
        self.assertEqual(ds["counts"]["events_bad_date"], 1)
        self.assertEqual(ds["counts"]["events_orphan"], 1)
        self.assertIn("E-0034", [e["event_id"] for e in ds["events"]["1003"]])  # matched by email

    def test_deal_closed_inferred_from_stage(self):
        ds = sample_dataset()
        self.assertFalse(ds["deals"]["1012"][0]["open"])

    def test_suppression_domain_and_case(self):
        ds = sample_dataset()
        self.assertIn("chris.doyle@meadow.example", ds["suppression"]["emails"])
        self.assertIn("oldco.example", ds["suppression"]["domains"])

    def test_minimal_build(self):
        row = {"Record ID": "1", "Email": "A@B.example", "Lifecycle Stage": "lead"}
        ds = build_dataset([row], [], [], [], [], AS_OF, AS_OF)
        self.assertEqual(ds["contacts"]["1"]["email"], "a@b.example")
        self.assertEqual(ds["contacts"]["1"]["consent"], "unknown")


if __name__ == "__main__":
    unittest.main()
