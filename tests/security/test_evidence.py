"""KOS-SENSE-008 AC-807: an incomplete security check fails CI. Every security regression test that an acceptance
criterion relies on must still exist; removing or renaming one fails this test. A security test that cannot run in CI
fails (secutil.unavailable) instead of skipping."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from secutil import IN_CI, ROOT  # noqa: E402

REQUIRED = {
    "AC-802": {"test_input_handling.py": [
        "test_f001_deeply_nested_json_is_a_read_error_not_a_traceback", "test_malformed_and_non_object_documents_exit_cleanly",
        "test_invalid_utf8_and_binary_input_is_a_read_error", "test_missing_file_directory_and_wrong_argument_count",
        "test_standard_input_is_not_read", "test_validators_do_not_recurse_over_values",
        "test_large_stream_is_checked_in_bounded_time", "test_wide_object_is_handled", "test_f003_count_is_capped",
        "test_output_path_errors_are_exit_2", "test_output_overwrites_an_existing_file_and_follows_a_symbolic_link"]},
    "AC-803": {"test_consumer_loading.py": [
        "test_valid_consumer_object_class_and_factory", "test_import_executes_module_code_with_the_users_privileges",
        "test_load_errors_are_exit_2_with_a_message_and_no_traceback", "test_f002_import_time_exit_zero_is_not_a_pass",
        "test_invalid_specifications", "test_consumer_that_raises_when_invoked_fails_its_cases_only",
        "test_f002_consumer_that_exits_when_invoked_fails_and_does_not_end_the_run",
        "test_consumer_that_hangs_when_invoked_blocks_until_the_caller_times_out",
        "test_module_that_hangs_at_import_blocks_until_the_caller_times_out", "test_documentation_states_the_limit"]},
    "AC-804": {"test_workflows.py": [
        "test_every_workflow_is_reviewed", "test_token_permissions_are_declared_and_minimal", "test_no_privileged_triggers",
        "test_actions_are_the_reviewed_first_party_set_and_pinned", "test_secrets_are_only_the_workflow_token",
        "test_untrusted_pull_request_text_is_not_interpolated_into_shell", "test_protected_paths_cover_the_security_relevant_files",
        "test_required_checks_are_the_reviewed_set"]},
    "AC-805": {"test_build_dependencies.py": [
        "test_runtime_dependencies_are_empty", "test_runtime_code_imports_only_the_standard_library_and_itself",
        "test_build_requirements_are_exact_and_hash_pinned", "test_release_artifact_listing_is_verified_by_the_packaging_suite"],
        "test_offline.py": [
        "test_the_block_stops_connections_and_name_resolution", "test_non_packaging_suites_pass_offline",
        "test_packaging_suite_passes_offline_with_a_prepared_wheelhouse", "test_in_ci_a_missing_build_tool_fails_the_run",
        "test_every_network_test_is_listed_and_excluded_from_the_offline_suite"]},
    "AC-806": {"test_register.py": [
        "test_unique_ids_and_complete_fields", "test_no_critical_or_high_finding_is_open_without_an_owner_disposition",
        "test_no_open_finding_once_the_task_is_submitted", "test_fixed_findings_name_a_remediation_commit_once_submitted"]},
    "AC-807": {"test_register.py": ["test_report_states_scope_method_limits_and_non_claims"]},
}


class Evidence(unittest.TestCase):
    def test_every_required_security_test_exists(self):
        missing = []
        for ac, files in REQUIRED.items():
            for fname, tests in files.items():
                path = ROOT / "tests" / "security" / fname
                self.assertTrue(path.is_file(), "%s: %s is missing" % (ac, fname))
                have = set(re.findall(r"def (test_\w+)", path.read_text(encoding="utf-8")))
                missing += ["%s %s::%s" % (ac, fname, t) for t in tests if t not in have]
        self.assertEqual(missing, [])

    def test_no_security_test_is_unconditionally_skipped_or_disabled(self):
        for path in (ROOT / "tests" / "security").glob("test_*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotRegex(text, r"@unittest\.skip\(", path.name)
            self.assertNotRegex(text, r"@unittest\.expectedFailure", path.name)
            self.assertNotRegex(text, r"(?m)^\s*#\s*def test_", path.name)

    def test_make_test_unit_runs_the_security_suite(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        self.assertIn("python3 -m unittest discover -s tests/security", makefile)

    def test_ci_detection_matches_the_packaging_suite(self):
        packaging = (ROOT / "tests" / "packaging" / "test_packaging.py").read_text(encoding="utf-8")
        self.assertIn('IN_CI = "true" in (os.environ.get("CI", "").lower(), os.environ.get("GITHUB_ACTIONS", "").lower())', packaging)
        self.assertIsInstance(IN_CI, bool)


if __name__ == "__main__":
    unittest.main()
