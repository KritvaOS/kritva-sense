"""CLI exit codes of python3 -m kritva_sense (KOS-SENSE-002)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parent / "fixtures"


def run(*args):
    return subprocess.run([sys.executable, "-m", "kritva_sense", *args], cwd=ROOT / "src",
                          capture_output=True, text=True)


def sample_file(group, name):
    import json
    doc = json.loads((FIX / group / (name + ".json")).read_text(encoding="utf-8"))
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    tmp.write(json.dumps(doc["sample"]))
    tmp.close()
    return tmp.name


class Cli(unittest.TestCase):
    def test_conformant_exits_zero(self):
        r = run(sample_file("valid", "imu_valid"))
        self.assertEqual(r.returncode, 0)
        self.assertIn("conformant", r.stdout)

    def test_nonconformant_exits_one_and_names_the_code(self):
        r = run(sample_file("invalid", "unknown_frame"))
        self.assertEqual(r.returncode, 1)
        self.assertIn("UNKNOWN_FRAME frame_id", r.stdout)

    def test_usage_and_read_errors_exit_two(self):
        self.assertEqual(run().returncode, 2)
        self.assertEqual(run("/nonexistent/sample.json").returncode, 2)


if __name__ == "__main__":
    unittest.main()
