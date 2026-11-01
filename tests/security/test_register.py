"""KOS-SENSE-008 AC-801, AC-806, AC-807: the threat model, the findings register and the final report are complete
and consistent with the code, the tests and the task status."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secutil import ROOT, table, task_status  # noqa: E402

TASK = ROOT / "tasks" / "KOS-SENSE-008"
REVIEW = (TASK / "SECURITY_REVIEW.md").read_text(encoding="utf-8")
MODEL = (TASK / "THREAT_MODEL.md").read_text(encoding="utf-8")
STATUSES = {"FIXED", "FIX_IN_OWNER_PR", "ACCEPTED_BY_OWNER", "OWNER_DISPOSITION_PENDING"}
SEVERITIES = ("Critical", "High", "Medium", "Low", "Info")
OPEN = {"FIX_IN_OWNER_PR", "OWNER_DISPOSITION_PENDING"}
SUBMITTED = ("IN_REVIEW", "ACCEPTED")


def register():
    rows = table(REVIEW, "2. Findings register")
    cols = ["id", "severity", "component", "evidence", "impact", "status", "commit", "retest", "owner"]
    return [dict(zip(cols, r)) for r in rows]


def test_names():
    names = {}
    for p in (ROOT / "tests" / "security").glob("test_*.py"):
        names[p.name] = set(re.findall(r"def (test_\w+)", p.read_text(encoding="utf-8")))
    return names


class ThreatModel(unittest.TestCase):
    def test_sections_and_identifiers(self):
        for heading in ("2. Assets", "3. Actors and trust boundaries", "4. Entry points", "5. Assumptions",
                        "6. Threats considered", "7. Out of scope"):
            self.assertIn("## " + heading, MODEL)
        self.assertEqual(len(table(MODEL, "2. Assets")), 7)
        self.assertGreaterEqual(len(table(MODEL, "4. Entry points")), 16)

    def test_every_entry_point_names_existing_code_or_workflow(self):
        for row in table(MODEL, "4. Entry points"):
            refs = re.findall(r"`([^`]+)`", row[2])
            paths = [r for r in refs if re.match(r"^(src|\.github|scripts|release|tests|pyproject|MANIFEST|SECURITY|Makefile)", r.split()[0])]
            self.assertTrue(paths, "%s names no file" % row[0])
            for r in paths:
                for token in re.split(r"[\s,]+", r):
                    path = token.split("`")[0]
                    if "*" in path:
                        self.assertTrue(list(ROOT.glob(path)), "%s: %s matches nothing" % (row[0], path))
                    elif "/" in path or path in ("pyproject.toml", "MANIFEST.in", "SECURITY.md", "Makefile"):
                        self.assertTrue((ROOT / path).exists(), "%s: %s does not exist" % (row[0], path))

    def test_entry_points_cover_every_command_and_workflow(self):
        cell = " ".join(r[2] for r in table(MODEL, "4. Entry points"))
        for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
            self.assertIn(wf.name, cell)
        for module in ("__main__.py", "frame_graph.py", "stream.py", "generator.py", "conformance.py", "version.py", "_entry.py"):
            self.assertIn(module, cell)

    def test_assumptions_state_the_sandbox_limit(self):
        self.assertIn("not a sandbox", MODEL)
        self.assertIn("only ends the process", MODEL)


class Register(unittest.TestCase):
    def setUp(self):
        self.rows = register()

    def test_unique_ids_and_complete_fields(self):
        ids = [r["id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(re.match(r"^F-\d{3}$", i) for i in ids))
        for r in self.rows:
            with self.subTest(finding=r["id"]):
                self.assertIn(r["severity"], SEVERITIES)
                self.assertIn(r["status"], STATUSES)
                for key in ("component", "evidence", "impact", "retest", "owner", "commit"):
                    self.assertTrue(r[key].strip(), key)
                self.assertGreater(len(r["evidence"]), 40)
                self.assertGreater(len(r["impact"]), 20)

    def test_retest_evidence_names_existing_tests(self):
        names = test_names()
        for r in self.rows:
            for fname, tname in re.findall(r"`(test_\w+\.py)` `(test_\w+)`", r["retest"]) or []:
                self.assertIn(tname, names.get(fname, set()), "%s: %s" % (r["id"], tname))
            for tname in re.findall(r"`(test_\w+)`", r["retest"]):
                self.assertTrue(any(tname in s for s in names.values()), "%s: test %s does not exist" % (r["id"], tname))
            if r["status"] == "FIXED" and "review (documentation)" not in r["retest"]:
                self.assertTrue(re.search(r"`test_\w+`", r["retest"]), "%s is fixed without a retest" % r["id"])

    def test_fixed_findings_name_a_remediation_commit_once_submitted(self):
        for r in self.rows:
            self.assertRegex(r["commit"], r"^(PENDING|not applicable|[0-9a-f]{40})$", r["id"])
            if r["status"] == "FIXED" and task_status("KOS-SENSE-008") in SUBMITTED:
                self.assertRegex(r["commit"], r"^[0-9a-f]{40}$", "%s needs its remediation commit" % r["id"])

    def test_no_critical_or_high_finding_is_open_without_an_owner_disposition(self):
        for r in self.rows:
            if r["severity"] in ("Critical", "High") and r["status"] != "FIXED":
                self.assertEqual(r["status"], "ACCEPTED_BY_OWNER", r["id"])
                self.assertIn("Dinesh", r["owner"])
                self.assertRegex(r["owner"].lower(), r"residual risk")

    def test_owner_dispositions_carry_rationale_risk_and_authority(self):
        for r in self.rows:
            if r["status"] == "ACCEPTED_BY_OWNER":
                low = r["owner"].lower()
                for needle in ("rationale", "residual risk", "dinesh"):
                    self.assertIn(needle, low, r["id"])

    def test_no_open_finding_once_the_task_is_submitted(self):
        if task_status("KOS-SENSE-008") in SUBMITTED:
            for r in self.rows:
                self.assertNotIn(r["status"], OPEN, "%s is still open; the task cannot be submitted" % r["id"])
                self.assertNotIn("PENDING", r["commit"] if r["status"] == "FIXED" else "")
                self.assertNotRegex(r["owner"], r"^PENDING")

    def test_owner_dispositions_have_an_explicit_authority_trace(self):
        """Approver, date, channel and durable record are named separately, so the chat approval, the relay and the
        owner-run script are not mixed up."""
        for r in self.rows:
            if r["status"] == "ACCEPTED_BY_OWNER":
                for needle in ("Approver: Dinesh", "Approval date: 2026-", "Channel:", "Durable record:"):
                    self.assertIn(needle, r["owner"], "%s: %s" % (r["id"], needle))
                self.assertNotIn("is the approval", r["owner"])

    def test_a_fixed_finding_with_an_unverified_part_says_so(self):
        f4 = [r for r in self.rows if r["id"] == "F-004"][0]
        self.assertIn("NOT verified", f4["owner"])
        self.assertIn("ruleset", f4["owner"])
        self.assertIn("**Not verified:**", REVIEW)

    def test_the_report_matches_the_final_workflow_and_gate_configuration(self):
        import json
        gate = json.loads((ROOT / ".github" / "kritva-gate.json").read_text(encoding="utf-8"))
        section = REVIEW[REVIEW.index("Gate configuration"):REVIEW.index("### Build and dependencies")]
        for check in gate["required_github_checks"]:
            self.assertIn("`%s`" % check, section)
        self.assertNotIn("tag-pinned", REVIEW.replace("not by tag", ""))
        self.assertNotIn("is not a required check", MODEL)

    def test_dispositions_are_never_invented(self):
        """A finding is marked ACCEPTED_BY_OWNER only with the owner's own words recorded; the register of the
        implementation pull request must not contain an accepted finding that no decision supports."""
        for r in self.rows:
            if r["status"] == "ACCEPTED_BY_OWNER":
                self.assertRegex(r["owner"], r"D-\d{3}|\d{4}-\d{2}-\d{2}", "%s: cite the decision or the date" % r["id"])


class Report(unittest.TestCase):
    def test_report_states_scope_method_limits_and_non_claims(self):
        for heading in ("1. Scope, method and limits", "6. Final report"):
            self.assertIn("## " + heading, REVIEW)
        low = REVIEW.lower()
        for needle in ("not a certification", "not a sandbox", "no safety claim", "a timeout does not make it one",
                       "not independent", "limits:"):
            self.assertIn(needle, low)

    def test_report_covers_each_area_and_the_release_artifacts(self):
        for heading in ("Input handling (AC-802)", "Consumer loading (AC-803)", "Workflows and the PR gate (AC-804)",
                        "Build and dependencies (AC-805)"):
            self.assertIn("### " + heading, REVIEW)
        self.assertIn("Wheel (21 files)", REVIEW)
        self.assertIn("Source distribution (27 files)", REVIEW)

    def test_every_workflow_is_reviewed_in_the_report(self):
        rows = {r[0].strip("`") for r in table(REVIEW.replace("### Workflows and the PR gate (AC-804)", "## W"), "W")}
        self.assertEqual(rows, {p.stem for p in (ROOT / ".github" / "workflows").glob("*.yml")})

    def test_report_does_not_claim_more_than_it_can(self):
        for banned in ("certified", "free of vulnerabilities and", "guarantee", "secure by"):
            self.assertNotRegex(REVIEW.replace("not a certification", ""), r"(?i)(?<!not )(?<!no )\b%s" % banned)

    def test_fixed_findings_are_listed_in_the_dispositions_section(self):
        fixed = sorted(r["id"] for r in register() if r["status"] == "FIXED")
        section = REVIEW[REVIEW.index("## 5. Dispositions"):REVIEW.index("## 6. Final report")]
        for fid in fixed:
            self.assertIn(fid, section)

    def test_the_package_version_and_release_statement_are_consistent(self):
        self.assertIn("0.2.0", REVIEW)
        self.assertIn("no tag exists or was published", REVIEW)


if __name__ == "__main__":
    unittest.main()
