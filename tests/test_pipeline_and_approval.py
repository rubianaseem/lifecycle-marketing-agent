import csv
import io
import json
import re
import unittest
from datetime import timedelta
from pathlib import Path

from lifecycle_agent.approval import ApprovalError, approve, release
from lifecycle_agent.audit import verify
from lifecycle_agent.pipeline import APPROVABLE, SimulatedCrash, StaleSnapshot, run
from lifecycle_agent.util import sha256_file
from tests.helpers import AS_OF, ROOT, policy, tmpdir

APPROVERS = json.loads((ROOT / "config/approvers.json").read_text())
IMP = "hubspot_import_proposed.csv"


class PipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tmpdir()
        cls.p = policy()
        cls.res = run(ROOT, cls.tmp / "out", cls.tmp / "state", AS_OF, cls.p)
        cls.rd = Path(cls.res["run_dir"])

    def test_all_artifacts_and_pending_status(self):
        m = json.loads((self.rd / "manifest.json").read_text())
        for name in APPROVABLE:
            self.assertEqual(m["artifacts"][name]["status"], "PENDING_APPROVAL")
        for name in ["segment_report.md", "play_assignments.csv", "review_queue.csv", "brief.md", "list_criteria.md", "decisions.jsonl"]:
            self.assertTrue((self.rd / name).exists(), name)
        self.assertEqual(m["mode"], "offline")

    def test_import_contains_only_proposed_and_safe_rows(self):
        rows = list(csv.DictReader(io.StringIO((self.rd / IMP).read_text())))
        assigns = {r["contact_id"]: r for r in csv.DictReader(io.StringIO((self.rd / "play_assignments.csv").read_text()))}
        self.assertTrue(rows)
        for r in rows:
            self.assertEqual(assigns[r["Record ID"]]["status"], "PROPOSED")
            self.assertIn(r["Lifecycle Stage"], {"", "marketingqualifiedlead"})
        held = [k for k, a in assigns.items() if a["status"] in {"HOLD", "DEFER", "REVIEW"}]
        self.assertFalse(set(held) & {r["Record ID"] for r in rows})

    def test_email_segments_recheck_consent_in_hubspot(self):
        spec = json.loads((self.rd / "list_criteria.json").read_text())
        for s in spec["segments"]:
            if s["email_play"]:
                props = [f.get("property") for f in s["filters_all_of"]]
                self.assertIn("hs_email_optout", props)
                self.assertIn("hs_marketable_status", props)

    def test_offline_drafts_are_labelled_templates(self):
        text = (self.rd / "nurture_drafts.md").read_text()
        self.assertIn("No model was called", text)
        self.assertNotIn("source: claude", text)
        self.assertIn("{{unsubscribe_link}}", text)

    def test_traces_verify(self):
        self.assertTrue(verify(self.rd / "decisions.jsonl")[0])
        self.assertTrue(verify(self.tmp / "state" / "audit.jsonl")[0])

    def test_trace_does_not_store_note_text(self):
        self.assertNotIn("IGNORE PREVIOUS", (self.rd / "decisions.jsonl").read_text())
        self.assertNotIn("IGNORE PREVIOUS", (self.tmp / "state" / "audit.jsonl").read_text())

    def test_no_emojis_in_outputs(self):
        emoji = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
        for f in self.rd.iterdir():
            if f.is_file():
                self.assertIsNone(emoji.search(f.read_text()), f.name)

    def test_crash_resume_and_idempotency(self):
        t = tmpdir()
        with self.assertRaises(SimulatedCrash):
            run(ROOT, t / "o", t / "s", AS_OF, self.p, fail_after="plan")
        r = run(ROOT, t / "o", t / "s", AS_OF, self.p)
        self.assertEqual(r["status"], "resumed_and_completed")
        self.assertEqual(sha256_file(Path(r["run_dir"]) / IMP), sha256_file(self.rd / IMP))
        self.assertEqual(run(ROOT, t / "o", t / "s", AS_OF, self.p)["status"], "already_complete")

    def test_stale_refused(self):
        t = tmpdir()
        with self.assertRaises(StaleSnapshot):
            run(ROOT, t / "o", t / "s", AS_OF + timedelta(days=2), self.p)


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        t = tmpdir()
        self.p = policy()
        self.rd = Path(run(ROOT, t / "o", t / "s", AS_OF, self.p)["run_dir"])
        self.now = AS_OF + timedelta(hours=1)

    def test_full_flow(self):
        with self.assertRaises(ApprovalError):
            release(self.rd, IMP, self.now, self.p)
        approve(self.rd, IMP, sha256_file(self.rd / IMP), "rubia", self.now, APPROVERS, self.p)
        out = release(self.rd, IMP, self.now, self.p)
        self.assertEqual(sha256_file(out), sha256_file(self.rd / IMP))
        self.assertTrue(verify(self.rd / "approvals.jsonl")[0])

    def test_tamper_after_approval_blocks_release(self):
        approve(self.rd, IMP, sha256_file(self.rd / IMP), "rubia", self.now, APPROVERS, self.p)
        with open(self.rd / IMP, "a") as fh:
            fh.write("9,x@y.example,NURTURE_EDUCATION,,,\n")
        with self.assertRaises(ApprovalError):
            release(self.rd, IMP, self.now, self.p)

    def test_edited_before_approval_refused(self):
        with open(self.rd / IMP, "a") as fh:
            fh.write("9,x@y.example,NURTURE_EDUCATION,,,\n")
        with self.assertRaises(ApprovalError):
            approve(self.rd, IMP, sha256_file(self.rd / IMP), "rubia", self.now, APPROVERS, self.p)

    def test_wrong_approver_and_partial_hash(self):
        h = sha256_file(self.rd / IMP)
        for who, hh in [("content-reviewer", h), ("nobody", h), ("rubia", h[:16])]:
            with self.assertRaises(ApprovalError):
                approve(self.rd, IMP, hh, who, self.now, APPROVERS, self.p)

    def test_no_auto_approve_path_exists(self):
        src = "\n".join(p.read_text() for p in (ROOT / "lifecycle_agent").glob("*.py")) + (ROOT / "agent.py").read_text()
        self.assertNotRegex(src.lower(), r"auto_approve|--yes|skip_approval|--force")


class SafetyTests(unittest.TestCase):
    def test_package_has_no_network_or_send_code(self):
        for p in (ROOT / "lifecycle_agent").glob("*.py"):
            text = p.read_text()
            for bad in ("import requests", "urllib.request", "http.client", "smtplib", "import socket", "hubspot"):
                if bad == "hubspot":
                    self.assertNotRegex(text, r"import hubspot|from hubspot")
                else:
                    self.assertNotIn(bad, text, f"{p.name} contains {bad}")


if __name__ == "__main__":
    unittest.main()
