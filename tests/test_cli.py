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

    def test_explicit_exact_preserves_default_output(self):
        default = self.run_cli("examples/triangle.json")
        explicit = self.run_cli("examples/triangle.json", "--algorithm", "exact")
        self.assertEqual(explicit.returncode, default.returncode)
        a, b = json.loads(default.stdout), json.loads(explicit.stdout)
        a["stats"].pop("elapsed_seconds")
        b["stats"].pop("elapsed_seconds")
        self.assertEqual(a, b)

    def test_approximation_examples(self):
        for name in ("triangle", "star"):
            with self.subTest(name=name):
                completed = self.run_cli(f"examples/{name}.json", "--algorithm", "approximation")
                self.assertEqual(completed.returncode, 0, completed.stderr)
                result = json.loads(completed.stdout)
                self.assertEqual(result["algorithm"], "maximal_matching_2_approximation")
                self.assertEqual(result["cover"], [0, 1])
                self.assertEqual(result["cover_size"], 2)
                self.assertTrue(result["valid_cover"])
                self.assertEqual(result["status"], "completed")
                self.assertIsNone(result["optimal"])
                self.assertEqual(result["matching"], [[0, 1]])
                self.assertEqual(result["matching_size"], 1)
                self.assertEqual(result["lower_bound"], 1)
                self.assertNotIn("stats", result)

    def test_approximation_empty_graph(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "empty.json"
            path.write_text('{"num_vertices": 0, "edges": []}', encoding="utf-8")
            completed = self.run_cli(str(path), "--algorithm", "approximation")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["cover"], [])
            self.assertEqual(result["matching"], [])
            self.assertEqual(result["lower_bound"], 0)
            self.assertIsNone(result["optimal"])

    def test_approximation_rejects_explicit_search_limits(self):
        for option in ("--time-limit=10", "--time-limit=0", "--node-limit=0",
                       "--time-limit=-1", "--time-limit=nan", "--node-limit=100"):
            with self.subTest(option=option):
                completed = self.run_cli("examples/star.json", "--algorithm", "approximation", option)
                self.assertEqual(completed.returncode, 2)
                self.assertIn("apply only", completed.stderr)
                self.assertEqual(completed.stdout, "")

    def test_approximation_invalid_input_and_missing_file(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bad.json"
            for contents in ("not json", "[]", "{}", '{"num_vertices":2,"edges":[[0,0]]}'):
                path.write_text(contents, encoding="utf-8")
                completed = self.run_cli(str(path), "--algorithm", "approximation")
                self.assertEqual(completed.returncode, 2)
                self.assertIn("Error:", completed.stderr)
                self.assertNotIn("Traceback", completed.stderr)
        completed = self.run_cli("examples/missing.json", "--algorithm", "approximation")
        self.assertEqual(completed.returncode, 2)

    def test_invalid_algorithm(self):
        completed = self.run_cli("examples/triangle.json", "--algorithm", "unknown")
        self.assertEqual(completed.returncode, 2)

    def test_explicit_exact_zero_time_limit_and_invalid_limits(self):
        completed = self.run_cli("examples/star.json", "--time-limit", "0")
        self.assertEqual(completed.returncode, 1, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["status"], "timeout")
        for option in ("--time-limit=-1", "--time-limit=nan", "--time-limit=inf", "--node-limit=-1"):
            with self.subTest(option=option):
                completed = self.run_cli("examples/star.json", option)
                self.assertEqual(completed.returncode, 2)
                self.assertNotIn("Traceback", completed.stderr)


if __name__ == "__main__":
    unittest.main()
