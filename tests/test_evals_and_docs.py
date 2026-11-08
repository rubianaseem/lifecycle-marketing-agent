import json
import re
import unittest

from evals.failure_suite import scenarios
from evals.harness import load_cases
from tests.helpers import ROOT


class EvalTests(unittest.TestCase):
    def test_eval_set_versioned_and_labelled(self):
        doc = load_cases()
        self.assertEqual(doc["version"], "v1")
        self.assertGreaterEqual(len(doc["cases"]), 50)
        self.assertEqual(len({c["id"] for c in doc["cases"]}), len(doc["cases"]))

    def test_run_evals_zero_hard_violations(self):
        import run_evals
        self.assertEqual(run_evals.main(quiet=True), 0)
        r = json.loads((ROOT / "evals/results.json").read_text())
        self.assertTrue(all(v == 0 for v in r["system"]["violations"].values()))
        self.assertGreater(r["system"]["exact_accuracy"], r["baseline"]["exact_accuracy"])

    def test_failure_suite_all_pass(self):
        res = scenarios()
        self.assertTrue(all(x["passed"] for x in res), [x for x in res if not x["passed"]])


class DocTests(unittest.TestCase):
    def test_readme_length_and_bio(self):
        text = (ROOT / "README.md").read_text()
        self.assertLessEqual(len(text.split()), 900)
        self.assertIn("Built by Rubia Naseem, GTM Engineer (12+ yrs CRM/RevOps, HubSpot & Salesforce).", text)

    def test_no_emojis_anywhere(self):
        emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2705]")
        for p in ROOT.rglob("*"):
            if p.is_file() and p.suffix in {".md", ".py", ".csv", ".json", ".txt"} and ".venv" not in p.parts:
                self.assertIsNone(emoji.search(p.read_text(encoding="utf-8")), str(p))


if __name__ == "__main__":
    unittest.main()
