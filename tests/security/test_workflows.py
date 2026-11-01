"""KOS-SENSE-008 AC-804: automated policy check of every CI workflow under .github/workflows (token permissions,
secrets, third-party actions and their pinning, untrusted pull request input). The workflow files are read as text
(no YAML library is needed or used). A new or changed workflow must be reviewed and added to POLICY below."""
import json
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secutil import ROOT  # noqa: E402

WF = ROOT / ".github" / "workflows"
# The reviewed state of every workflow (see tasks/KOS-SENSE-008/SECURITY_REVIEW.md, section Workflows).
POLICY = {
    "commit-message-check.yml": {"permissions": {"contents": "read"}, "actions": {"actions/checkout", "actions/setup-python"}},
    "pr-acceptance-gate.yml": {"permissions": {"contents": "read", "pull-requests": "write"},
                               "actions": {"actions/checkout", "actions/setup-python"}},
    "readme-check.yml": {"permissions": {"contents": "read"}, "actions": {"actions/checkout", "actions/setup-python"}},
    "secret-scan.yml": {"permissions": {"contents": "read"}, "actions": {"actions/checkout"}},
    "unit-tests.yml": {"permissions": {"contents": "read"}, "actions": {"actions/checkout", "actions/setup-python"}},
}
# Every action is pinned to a full commit SHA with the version tag in a comment (finding F-005, fixed).
SHA_PINNED = re.compile(r"^[\w.-]+/[\w.-]+@[0-9a-f]{40}$")


def text(name):
    return (WF / name).read_text(encoding="utf-8")


def permissions(src):
    m = re.search(r"(?m)^permissions:\n((?:  .+\n)+)", src)
    if not m:
        return None
    return dict(re.findall(r"^  ([\w-]+): (\w+)$", m.group(1), re.M))


def uses(src):
    return re.findall(r"(?m)^\s*-?\s*uses:\s*(\S+)", src)


def run_lines(src):
    """All shell text of `run:` steps (single line and block form)."""
    out = []
    lines = src.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", line)
        if not m:
            continue
        if m.group(2) in ("|", ">", "|-", ">-"):
            indent = len(m.group(1)) + 2
            for nxt in lines[i + 1:]:
                if nxt.strip() and len(nxt) - len(nxt.lstrip()) < indent:
                    break
                out.append(nxt)
        else:
            out.append(m.group(2))
    return "\n".join(out)


class Workflows(unittest.TestCase):
    def test_every_workflow_is_reviewed(self):
        self.assertEqual(sorted(p.name for p in WF.glob("*.y*ml")), sorted(POLICY),
                         "a workflow was added, removed or renamed: review it and update POLICY")

    def test_token_permissions_are_declared_and_minimal(self):
        for name, pol in POLICY.items():
            with self.subTest(workflow=name):
                self.assertEqual(permissions(text(name)), pol["permissions"])

    def test_no_write_permission_except_the_gate_comment(self):
        for name in POLICY:
            perms = permissions(text(name))
            writes = {k for k, v in perms.items() if v != "read"}
            self.assertEqual(writes, {"pull-requests"} if name == "pr-acceptance-gate.yml" else set(), name)
            self.assertNotIn("write-all", text(name))

    def test_no_privileged_triggers(self):
        for name in POLICY:
            src = text(name)
            for trigger in ("pull_request_target", "workflow_run", "issue_comment", "repository_dispatch"):
                self.assertNotRegex(src, r"(?m)^\s+%s\s*:|^\s*-\s*%s\b|\[.*%s.*\]" % (trigger, trigger, trigger), (name, trigger))

    def test_actions_are_the_reviewed_first_party_set_and_pinned(self):
        for name, pol in POLICY.items():
            with self.subTest(workflow=name):
                found = uses(text(name))
                self.assertEqual({u.split("@")[0] for u in found}, pol["actions"])
                for u in found:
                    self.assertTrue(SHA_PINNED.match(u), "%s is not pinned to a full commit SHA" % u)
                    self.assertTrue(u.startswith("actions/"), "third-party action %s needs review" % u)
                    self.assertNotRegex(u, r"@(main|master|latest|v\d+\.x)$")

    def test_every_pin_names_its_version_tag_and_the_same_sha_is_used_everywhere(self):
        shas = {}
        for name in POLICY:
            for line in text(name).splitlines():
                m = re.search(r"uses:\s*([\w.-]+/[\w.-]+)@([0-9a-f]{40})\s+# (v\d+)\s*$", line)
                if "uses:" in line:
                    self.assertTrue(m, "%s: pin without a version comment: %s" % (name, line.strip()))
                    shas.setdefault(m.group(1) + " " + m.group(3), set()).add(m.group(2))
        self.assertTrue(shas)
        for action, versions in shas.items():
            self.assertEqual(len(versions), 1, "%s is pinned to different commits" % action)

    def test_secrets_are_only_the_workflow_token(self):
        for name in POLICY:
            src = text(name)
            self.assertEqual(set(re.findall(r"secrets\.([A-Za-z0-9_]+)", src)) - {"GITHUB_TOKEN"}, set(), name)
            self.assertNotRegex(src, r"(?i)(password|api[_-]?key|private[_-]?key)\s*:", name)

    def test_every_job_has_a_timeout(self):
        for name in POLICY:
            jobs = len(re.findall(r"(?m)^  [\w-]+:\n    runs-on:", text(name)))
            self.assertGreaterEqual(jobs, 1, name)
            self.assertEqual(len(re.findall(r"(?m)^    timeout-minutes: \d+$", text(name))), jobs, name)

    def test_checkout_does_not_persist_credentials_where_the_gate_comments(self):
        """The gate checks out with default credentials (it needs `gh` for the comment): recorded, not asserted
        away. Every other workflow only needs contents: read."""
        for name in POLICY:
            if name != "pr-acceptance-gate.yml":
                self.assertEqual(permissions(text(name)).get("contents"), "read")

    def test_untrusted_pull_request_text_is_not_interpolated_into_shell(self):
        """Fields an author controls (title, body, head ref, branch names, commit messages) must not appear in a
        `run:` script as ${{ }} expressions. The base branch name and the head SHA are interpolated (finding F-006,
        owner route): the base ref names a branch of this repository that only a maintainer can create, and the SHA
        is hexadecimal. ALLOWED_INTERPOLATIONS lists exactly these and nothing may be added without review."""
        dangerous = re.compile(r"\$\{\{\s*github\.(event\.(pull_request\.(title|body|head\.ref|head\.label|user\.login)|"
                               r"head_commit\.message|comment\.body|issue\.(title|body)|review\.body|commits)|head_ref)")
        for name in POLICY:
            shell = run_lines(text(name))
            self.assertIsNone(dangerous.search(shell), name)
            found = set(re.findall(r"\$\{\{\s*([^}]+?)\s*\}\}", shell))
            self.assertLessEqual(found, ALLOWED_INTERPOLATIONS, (name, sorted(found - ALLOWED_INTERPOLATIONS)))

    def test_no_download_and_execute_pipes(self):
        for name in POLICY:
            self.assertNotRegex(run_lines(text(name)), r"(curl|wget)[^\n|]*\|\s*(ba|z)?sh", name)

    def test_secret_scan_checks_the_downloaded_scanner(self):
        src = run_lines(text("secret-scan.yml"))
        self.assertRegex(src, r"sha256sum|shasum")
        self.assertRegex(src, r"gitleaks")


ALLOWED_INTERPOLATIONS = set()          # every ${{ }} value reaches a script through env: (finding F-006)


class GateConfiguration(unittest.TestCase):
    def gate(self):
        return json.loads((ROOT / ".github" / "kritva-gate.json").read_text(encoding="utf-8"))

    def test_protected_paths_cover_the_security_relevant_files(self):
        protected = set(self.gate()["protected_paths"])
        for needed in (".github/", "SECURITY.md", "LICENSE", "ACCEPTANCE_CRITERIA.md", "Makefile",
                       "scripts/pipeline/", "scripts/security/"):
            self.assertIn(needed, protected)

    def test_required_checks_are_the_reviewed_set(self):
        """unit-tests is a required check (finding F-004, fixed). Removing a check from this set must be a deliberate,
        reviewed change."""
        required = set(self.gate()["required_github_checks"])
        self.assertTrue({"secret-scan", "commit-message-check", "pr-acceptance-gate", "unit-tests"} <= required)

    def test_every_required_check_has_a_workflow(self):
        names = set()
        for p in WF.glob("*.y*ml"):
            m = re.search(r"(?m)^name:\s*(\S+)", p.read_text(encoding="utf-8"))
            names.add(m.group(1) if m else p.stem)
            for j in re.findall(r"(?m)^  ([\w-]+):\n    runs-on:", p.read_text(encoding="utf-8")):
                names.add(j)
        for check in self.gate()["required_github_checks"]:
            self.assertIn(check, names)

    def test_codeowners_cover_workflows_and_security_files(self):
        co = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        owned = [l.split()[0] for l in co.splitlines() if l.strip() and not l.startswith("#")]
        self.assertTrue(owned)
        self.assertTrue(any(o in ("*", "/.github/", "/.github/**", ".github/") for o in owned))


if __name__ == "__main__":
    unittest.main()
