import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CommandTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "vertex_cover", *args], cwd=ROOT,
                              capture_output=True, text=True, timeout=10)

    def test_triangle_is_optimal(self):
        completed = self.run_cli("examples/triangle.json")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertTrue(result["valid_cover"] and result["optimal"])
        self.assertEqual(result["cover_size"], 2)

    def test_interrupted_run_has_distinct_exit_code(self):
        completed = self.run_cli("examples/star.json", "--node-limit", "0")
        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["status"], "node_limit")
        self.assertTrue(result["valid_cover"])
        self.assertFalse(result["optimal"])

    def test_invalid_input_is_reported_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            for contents in ["not json", "[]", '{}', '{"num_vertices":2,"edges":[[0,0]]}']:
                path.write_text(contents, encoding="utf-8")
                completed = self.run_cli(str(path))
                self.assertEqual(completed.returncode, 2)
                self.assertIn("Error:", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)

    def test_missing_file(self):
        completed = self.run_cli("examples/does-not-exist.json")
        self.assertEqual(completed.returncode, 2)


if __name__ == "__main__":
    unittest.main()
