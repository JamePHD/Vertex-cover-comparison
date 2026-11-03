"""Independent generator checks and end-to-end measurement integrity tests."""

from copy import deepcopy
import csv
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tests.helpers import brute_force_optimum
from vertex_cover import Graph, solve_exact
from vertex_cover.analysis import analyse_run, summarise_run
from vertex_cover.benchmark import run_benchmarks
from vertex_cover.datasets import (canonical_bytes, digest, generate_dataset, graph_digest,
                                   known_optimum, load_dataset, make_graph, relabel, validate_config)

ROOT = Path(__file__).resolve().parents[1]


def tiny_config():
    data = json.loads((ROOT / "configs/smoke.json").read_text(encoding="utf-8"))
    data.update(random_sizes=[5], probabilities=[.4], seeds=[1], structured_sizes=[4],
                families=["path", "star", "clique"], relabel_sizes=[4],
                relabel_families=["path"], permutation_seeds=[100], repetitions=2,
                warmups=1, exact_time_limit=1.0, exact_node_limit=None,
                batch_threshold_ns=1_000_000_000, batch_size=3, predictions_file="predictions.md")
    return data


class WorkspaceTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def config(self, updates=None):
        config = tiny_config()
        config.update(updates or {})
        (self.folder / "predictions.md").write_text("Predictions recorded before any timing.\n", encoding="utf-8")
        path = self.folder / "config.json"
        path.write_text(json.dumps(config), encoding="utf-8")
        return path

    def run_pipeline(self, updates=None):
        generate_dataset(self.config(updates), self.folder / "inputs")
        metadata = run_benchmarks(self.folder / "inputs", self.folder / "run")
        return metadata, analyse_run(self.folder / "run", self.folder / "analysis")


class GeneratorTests(WorkspaceTest):
    def test_structured_families_have_independently_verified_optima(self):
        for family in ["path", "cycle", "star", "clique", "disjoint_edges", "complete_bipartite"]:
            for n in range(3 if family == "cycle" else 0, 9):
                with self.subTest(family=family, n=n):
                    graph = make_graph(family, n)
                    self.assertEqual(known_optimum(family, n), brute_force_optimum(n, graph.edges))

    def test_random_extremes_and_repeatability(self):
        self.assertEqual(make_graph("gnp", 8, probability=0).edges, ())
        self.assertEqual(len(make_graph("gnp", 8, probability=1).edges), 28)
        self.assertEqual(make_graph("gnp", 20, probability=.4, seed=1),
                         make_graph("gnp", 20, probability=.4, seed=1))
        self.assertNotEqual(make_graph("gnp", 20, probability=.4, seed=1),
                            make_graph("gnp", 20, probability=.4, seed=2))

    def test_relabelling_preserves_optimum_and_does_not_mutate_input(self):
        graph = Graph(4, [(0, 1), (1, 2), (2, 3)])
        before = graph_digest(graph)
        mapped = relabel(graph, [2, 0, 1, 3])
        self.assertNotEqual(graph.edges, mapped.edges)
        self.assertEqual(brute_force_optimum(4, mapped.edges), 2)
        self.assertEqual(graph_digest(graph), before)
        for bad in [[0], [0, 0, 1, 2], [False, 1, 2, 3]]:
            with self.assertRaises(ValueError):
                relabel(graph, bad)

    def test_generated_graphs_are_reproducible_and_self_contained(self):
        config = self.config()
        a = generate_dataset(config, self.folder / "a")
        b = generate_dataset(config, self.folder / "b")
        self.assertEqual(a["instances"], b["instances"])
        self.assertEqual(len(a["instances"]), 5)
        self.assertEqual(a["predictions_sha256"], b["predictions_sha256"])
        _, instances = load_dataset(self.folder / "a")
        self.assertEqual(len(instances), 5)
        config.unlink()
        (self.folder / "predictions.md").unlink()
        self.assertEqual(len(load_dataset(self.folder / "a")[1]), 5)

    def test_existing_output_is_never_overwritten(self):
        path = self.config()
        generate_dataset(path, self.folder / "inputs")
        with self.assertRaises(FileExistsError):
            generate_dataset(path, self.folder / "inputs")

    def test_graph_and_prediction_tampering_are_detected(self):
        manifest = generate_dataset(self.config(), self.folder / "inputs")
        file = self.folder / "inputs" / manifest["instances"][0]["file"]
        graph = json.loads(file.read_text())
        graph["num_vertices"] += 1
        file.write_text(json.dumps(graph), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "integrity"):
            load_dataset(self.folder / "inputs")
        (self.folder / "inputs/predictions.md").write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "prediction"):
            load_dataset(self.folder / "inputs")

    def test_manifest_rejects_duplicate_ids_and_path_escape(self):
        generate_dataset(self.config(), self.folder / "inputs")
        path = self.folder / "inputs/manifest.json"
        original = json.loads(path.read_text())
        changed = deepcopy(original)
        changed["instances"][1]["id"] = changed["instances"][0]["id"]
        path.write_text(json.dumps(changed), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            load_dataset(self.folder / "inputs")
        original["instances"][0]["file"] = "../config.json"
        path.write_text(json.dumps(original), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "escapes"):
            load_dataset(self.folder / "inputs")

    def test_config_rejects_ambiguous_or_invalid_settings(self):
        cases = [{"probabilities": [float("nan")]}, {"exact_time_limit": -1},
                 {"repetitions": 0}, {"batch_size": 1000}, {"warmups": True},
                 {"seeds": [1, 1]}, {"families": ["unknown"]}, {"exact_node_limit": True},
                 {"extra_unknown_key": 1}, {"relabel_sizes": [999]},
                 {"structured_sizes": [0], "families": ["cycle"]}]
        for update in cases:
            config = tiny_config()
            config.update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                validate_config(config)


class BenchmarkTests(WorkspaceTest):
    def test_paired_run_saves_all_details_and_summary_denominators(self):
        metadata, summary = self.run_pipeline()
        self.assertTrue(metadata["completed"])
        self.assertEqual(metadata["measured_rows"], 20)
        with (self.folder / "run/raw.csv").open(newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 20)
        self.assertTrue(all(int(r["batch_calls"]) == 3 for r in rows))
        for index in range(0, len(rows), 2):
            self.assertEqual({r["algorithm"] for r in rows[index:index + 2]}, {"exact", "approximation"})
            self.assertEqual(rows[index]["instance_id"], rows[index + 1]["instance_id"])
        self.assertEqual(rows[0]["algorithm"], "exact")
        self.assertEqual(rows[2]["algorithm"], "approximation")
        details = [json.loads(line) for line in (self.folder / "run/details.jsonl").read_text().splitlines()]
        self.assertTrue(all(len(row["calls"]) == 3 for row in details))
        self.assertEqual(len(summary["instances"]), 5)
        self.assertEqual(sum(r["instances"] for r in summary["groups"]), 4)
        self.assertEqual(sum(r["is_relabelled"] for r in summary["instances"]), 1)
        for row in summary["instances"]:
            self.assertTrue(row["exact_all_repetitions_optimal"])
            self.assertTrue(1 <= row["approximation_ratio"] <= 2)
        self.assertTrue((self.folder / "run/predictions.md").exists())
        self.assertIn("source_sha256", metadata["source"])

    def test_interruption_and_empty_graph_never_create_false_ratios(self):
        _, summary = self.run_pipeline({"random_sizes": [], "families": ["star"],
                                        "structured_sizes": [0, 4], "relabel_sizes": [],
                                        "relabel_families": [], "exact_node_limit": 0, "warmups": 0})
        empty, interrupted = sorted(summary["instances"], key=lambda r: r["n"])
        self.assertTrue(empty["exact_all_repetitions_optimal"])
        self.assertIsNone(empty["approximation_ratio"])
        self.assertFalse(interrupted["exact_all_repetitions_optimal"])
        self.assertIsNone(interrupted["certified_optimum"])
        self.assertIsNone(interrupted["approximation_ratio"])
        self.assertIsNone(interrupted["paired_speedup"])
        self.assertIsNone(interrupted["exact_median_complete_seconds"])
        self.assertGreater(interrupted["exact_median_observed_seconds"], 0)
        group = next(r for r in summary["groups"] if r["n"] == 4)
        self.assertEqual(group["exact_complete_fraction"], 0)
        self.assertIsNone(group["approximation_median_paired_seconds"])
        self.assertGreater(group["approximation_median_all_seconds"], 0)

    def test_mixed_status_batches_keep_proof_without_claiming_completion(self):
        from vertex_cover.benchmark import timed_calls as real_timing
        config = self.config({"random_sizes": [], "families": ["path"], "structured_sizes": [4],
                              "relabel_sizes": [], "relabel_families": [], "repetitions": 1})
        generate_dataset(config, self.folder / "inputs")
        graph = make_graph("path", 4)
        finished, interrupted = solve_exact(graph), solve_exact(graph, node_limit=0)
        def mixed_timing(actual_graph, algorithm, settings, calls):
            if algorithm == "exact" and calls > 1:
                return 3_000_000, [finished, interrupted, finished]
            return real_timing(actual_graph, algorithm, settings, calls)
        with patch("vertex_cover.benchmark.timed_calls", side_effect=mixed_timing):
            run_benchmarks(self.folder / "inputs", self.folder / "run")
        summary = summarise_run(self.folder / "run")
        row = summary["instances"][0]
        self.assertFalse(row["exact_all_repetitions_optimal"])
        self.assertIsNone(row["paired_speedup"])
        self.assertEqual(row["certified_optimum"], 2)
        self.assertEqual(row["approximation_ratio"], 2)
        calls = [json.loads(line) for line in (self.folder / "run/details.jsonl").read_text().splitlines()]
        exact = next(r for r in calls if r["algorithm"] == "exact")
        self.assertEqual([r["status"] for r in exact["calls"]], ["optimal", "node_limit", "optimal"])

    def test_raw_tampering_and_incomplete_run_are_rejected(self):
        self.run_pipeline()
        file = self.folder / "run/raw.csv"
        original = file.read_bytes()
        file.write_bytes(original + b"\n")
        with self.assertRaisesRegex(ValueError, "integrity"):
            summarise_run(self.folder / "run")
        file.write_bytes(original)
        path = self.folder / "run/metadata.json"
        metadata = json.loads(path.read_text())
        metadata["completed"] = False
        path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "completed"):
            summarise_run(self.folder / "run")

    def test_invalid_solver_output_leaves_explicit_incomplete_artifacts(self):
        generate_dataset(self.config({"warmups": 0}), self.folder / "inputs")
        graph = make_graph("star", 4)
        invalid = replace(solve_exact(graph), cover=frozenset())
        with patch("vertex_cover.benchmark.solve_exact", return_value=invalid):
            with self.assertRaisesRegex(ValueError, "invalid vertex cover"):
                run_benchmarks(self.folder / "inputs", self.folder / "run")
        metadata = json.loads((self.folder / "run/metadata.json").read_text())
        self.assertFalse(metadata["completed"])
        self.assertIn("invalid vertex cover", metadata["error"])
        with self.assertRaisesRegex(ValueError, "completed"):
            analyse_run(self.folder / "run", self.folder / "analysis")

    def test_duplicate_measurement_rows_cannot_be_summarised(self):
        self.run_pipeline()
        raw = self.folder / "run/raw.csv"
        with raw.open(newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames
            rows = list(reader)
        rows[1] = dict(rows[0])
        with raw.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader(); writer.writerows(rows)
        path = self.folder / "run/metadata.json"
        metadata = json.loads(path.read_text())
        metadata["raw_sha256"] = digest(raw.read_bytes())
        path.write_text(json.dumps(metadata), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate"):
            summarise_run(self.folder / "run")

    def test_cli_pipeline_and_no_overwrite(self):
        config = self.config({"warmups": 0, "batch_size": 1})
        args = [sys.executable, "-m", "vertex_cover", "experiment", "--config", str(config),
                "--output", str(self.folder / "pipeline")]
        first = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30)
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue((self.folder / "pipeline/analysis/summary.json").exists())
        again = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=10)
        self.assertEqual(again.returncode, 2)
        self.assertNotIn("Traceback", again.stderr)

    @unittest.skipUnless(importlib.util.find_spec("matplotlib"), "optional Matplotlib is not installed")
    def test_plots_rebuild_from_saved_summary(self):
        self.run_pipeline()
        from vertex_cover.plots import plot_summary
        files = plot_summary(self.folder / "analysis", self.folder / "plots")
        self.assertEqual(len(files), 15)
        self.assertIn("quality.svg", files)
        self.assertTrue(all((self.folder / "plots" / name).stat().st_size > 100 for name in files))


if __name__ == "__main__":
    unittest.main()
