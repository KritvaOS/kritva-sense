"""status/status.json must agree with planning/TASKS.md (reports facts only; never review or acceptance)."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TASK_KEYS = {"task_id", "execution", "git_sync", "readiness", "evidence"}
EVIDENCE_KEYS = {"type", "uri", "description", "commit", "ci_run", "report_sha256", "result"}
# execution COMPLETE means the implementation is finished and submitted for review. It is not acceptance.
EXECUTION = {"NOT_STARTED": "NOT_STARTED", "READY": "NOT_STARTED", "IN_PROGRESS": "IN_PROGRESS", "BLOCKED": "BLOCKED",
             "IN_REVIEW": "COMPLETE", "CHANGES_REQUESTED": "IN_PROGRESS", "ACCEPTED": "COMPLETE"}


def tasks_md():
    rows = {}
    for line in (ROOT / "planning" / "TASKS.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (KOS-SENSE-\d+) \| [^|]+ \| ([A-Z_]+)", line)
        if m:
            rows[m.group(1)] = m.group(2)
    return rows


class StatusReport(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / "status" / "status.json").read_text(encoding="utf-8"))

    def test_identity_and_schema(self):
        self.assertEqual(self.doc["schema_version"], "2.0")
        self.assertEqual(self.doc["workstream_id"], "SENSE")
        self.assertEqual(self.doc["repo"], "KritvaOS/kritva-sense")
        self.assertEqual(self.doc["source"]["branch"], "main")
        self.assertRegex(self.doc["source"]["commit"], r"^[0-9a-f]{40}$")
        self.assertRegex(self.doc["updated_at"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_one_row_per_task_in_tasks_md(self):
        listed = tasks_md()
        self.assertEqual(sorted(t["task_id"] for t in self.doc["tasks"]), sorted(listed))

    def test_execution_follows_tasks_md_status(self):
        listed = tasks_md()
        for t in self.doc["tasks"]:
            with self.subTest(t["task_id"]):
                self.assertEqual(t["execution"], EXECUTION[listed[t["task_id"]]])

    def test_rows_report_facts_only(self):
        for t in self.doc["tasks"]:
            with self.subTest(t["task_id"]):
                self.assertEqual(set(t), TASK_KEYS)  # no review or acceptance fields
                self.assertIn(t["git_sync"], {"NOT_COMMITTED", "COMMITTED", "NOT_SYNCED", "SYNCED"})
                self.assertIn(t["readiness"], {"PLANNABLE", "IMPLEMENTABLE", "HARDWARE-BLOCKED"})
                for ev in t["evidence"]:
                    self.assertEqual(set(ev), EVIDENCE_KEYS)
                    self.assertIn(ev["type"], {"software", "simulation", "physical"})
                    if ev["commit"]:
                        self.assertRegex(ev["commit"], r"^[0-9a-f]{40}$")
                    if ev["result"]:
                        self.assertTrue(ev["ci_run"] and ev["commit"], "a result needs a commit and a CI run")

    def test_software_only_no_physical_evidence(self):
        for t in self.doc["tasks"]:
            self.assertFalse([e for e in t["evidence"] if e["type"] == "physical"])


if __name__ == "__main__":
    unittest.main()
