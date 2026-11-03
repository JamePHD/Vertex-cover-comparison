"""Sequential paired timing with immutable inputs and auditable result records."""

import csv
from dataclasses import asdict
import gc
import json
import os
from pathlib import Path
import platform
import statistics
import subprocess
import sys
from time import get_clock_info, perf_counter_ns

from .approximation import solve_approximation
from .datasets import canonical_bytes, digest, graph_digest, load_dataset, new_directory, utc_now, write_json
from .exact import solve_exact
from .graph import is_vertex_cover

COUNTERS = ["nodes_visited", "nodes_expanded", "pruned_by_size", "pruned_by_bound",
            "leaves", "incumbent_updates", "max_stack_size"]
FIELDS = ["instance_id", "family", "n", "m", "probability", "seed", "base_id", "permutation_seed",
          "algorithm", "repetition", "order", "batch_calls", "batch_elapsed_ns", "seconds_per_call",
          "status", "optimal", "cover_size", "cover_size_min", "cover_size_max", "lower_bound",
          "certified_optimum", "valid_cover", *COUNTERS]


def source_state():
    root = Path(__file__).resolve().parents[1]
    hashes = {str(p.relative_to(root)).replace("\\", "/"): digest(p.read_bytes())
              for p in sorted((root / "vertex_cover").glob("*.py"))}
    commit = None
    try:
        completed = subprocess.run(["git", "-c", f"safe.directory={root.as_posix()}",
                                    "-C", str(root), "rev-parse", "HEAD"],
                                   capture_output=True, text=True, timeout=5)
        if completed.returncode == 0:
            commit = completed.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return {"git_commit": commit, "source_sha256": hashes,
            "note": "Source hashes identify executed files even when changes are uncommitted."}


def environment():
    ram = None
    if os.name == "nt":
        try:
            import ctypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong),
                            *[(name, ctypes.c_ulonglong) for name in
                              ["total_physical", "available_physical", "total_page", "available_page",
                               "total_virtual", "available_virtual", "available_extended"]]]
            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
                ram = memory.total_physical
        except (AttributeError, OSError):
            pass
    clock = get_clock_info("perf_counter")
    return {"python": sys.version, "implementation": platform.python_implementation(),
            "platform": platform.platform(), "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(), "physical_ram_bytes": ram,
            "gc_enabled": gc.isenabled(), "gc_thresholds": gc.get_threshold(),
            "clock": {"implementation": clock.implementation, "resolution_seconds": clock.resolution,
                      "monotonic": clock.monotonic, "adjustable": clock.adjustable},
            "power_settings": "Not detected; record manually for the final study."}


def verify_result(graph, algorithm, result, analytic_optimum=None):
    if not is_vertex_cover(graph, result.cover):
        raise ValueError(f"{algorithm} returned an invalid vertex cover")
    lower = result.lower_bound
    if not 0 <= lower <= result.cover_size:
        raise ValueError(f"{algorithm} returned inconsistent bounds")
    if analytic_optimum is not None:
        if not lower <= analytic_optimum <= result.cover_size:
            raise ValueError("solver bounds contradict the structured graph's known optimum")
    if algorithm == "approximation":
        endpoints = set()
        edges = set(graph.edges)
        for u, v in result.matching:
            if (u, v) not in edges or u in endpoints or v in endpoints:
                raise ValueError("invalid matching certificate")
            endpoints.update((u, v))
        if endpoints != result.cover or result.cover_size != 2 * len(result.matching):
            raise ValueError("cover does not equal the matching endpoints")
        return {"cover": sorted(result.cover), "cover_size": result.cover_size,
                "status": "completed", "optimal": None, "lower_bound": lower,
                "matching": [list(e) for e in result.matching]}
    if result.status not in {"optimal", "timeout", "node_limit"}:
        raise ValueError("unknown exact solver status")
    if result.optimal and (lower != result.cover_size or
                          analytic_optimum is not None and result.cover_size != analytic_optimum):
        raise ValueError("invalid exact optimality claim")
    return {"cover": sorted(result.cover), "cover_size": result.cover_size,
            "status": result.status, "optimal": result.optimal, "lower_bound": lower,
            "stats": asdict(result.stats)}


def timed_calls(graph, algorithm, config, calls):
    # Both methods pay the same wrapper/list retention overhead. Validation,
    # serialisation, input construction and file I/O occur after the timer.
    def invoke():
        if algorithm == "exact":
            return solve_exact(graph, time_limit=config["exact_time_limit"],
                               node_limit=config["exact_node_limit"])
        return solve_approximation(graph)
    started = perf_counter_ns()
    results = [invoke() for _ in range(calls)]
    elapsed = perf_counter_ns() - started
    return elapsed, results


def run_benchmarks(dataset, output, progress=None):
    manifest, instances = load_dataset(dataset)
    config = manifest["config"]
    output = new_directory(output)
    write_json(output / "manifest.json", manifest)
    predictions = (Path(dataset) / "predictions.md").read_bytes()
    (output / "predictions.md").write_bytes(predictions)
    overhead = []
    for _ in range(101):
        a = perf_counter_ns()
        overhead.append(perf_counter_ns() - a)
    metadata = {"schema_version": 1, "started_utc": utc_now(), "completed": False,
                "purpose": config["purpose"], "config": config, "environment": environment(),
                "source": source_state(), "manifest_sha256": digest(canonical_bytes(manifest)),
                "predictions_sha256": digest(predictions),
                "prediction_endorsement": "AI-assisted proposals; student endorsement not verified by the runner.",
                "timer": "perf_counter_ns", "median_back_to_back_timer_ns": statistics.median(overhead),
                "timing_scope": "Complete solver calls, common wrapper and result list retention; excludes validation and I/O.",
                "batch_rule": "Batch up to configured size only after a completed warm-up below threshold; warmups=0 means one call.",
                "timeout_policy": "Cooperative, not a hard deadline. Mixed-status batches retained and excluded from completed timing.",
                "warmups": [], "measured_rows": 0}
    write_json(output / "metadata.json", metadata)
    try:
        with (output / "raw.csv").open("w", newline="", encoding="utf-8") as raw, \
                (output / "details.jsonl").open("w", encoding="utf-8") as details:
            writer = csv.DictWriter(raw, fieldnames=FIELDS)
            writer.writeheader()
            for index, (entry, graph) in enumerate(instances):
                before = graph_digest(graph)
                batches = {"exact": 1, "approximation": 1}
                for algorithm in ["exact", "approximation"]:
                    for warmup in range(config["warmups"]):
                        elapsed, results = timed_calls(graph, algorithm, config, 1)
                        result = verify_result(graph, algorithm, results[0], entry["analytic_optimum"])
                        metadata["warmups"].append({"instance_id": entry["id"], "algorithm": algorithm,
                                                    "warmup": warmup, "elapsed_ns": elapsed,
                                                    "status": result["status"]})
                        completed = algorithm == "approximation" or result["optimal"]
                        batches[algorithm] = config["batch_size"] if (
                            completed and elapsed < config["batch_threshold_ns"]) else 1
                for repetition in range(config["repetitions"]):
                    order = ["exact", "approximation"] if (index + repetition) % 2 == 0 else ["approximation", "exact"]
                    for position, algorithm in enumerate(order):
                        elapsed, results = timed_calls(graph, algorithm, config, batches[algorithm])
                        checked = [verify_result(graph, algorithm, r, entry["analytic_optimum"]) for r in results]
                        statuses = {r["status"] for r in checked}
                        sizes = {r["cover_size"] for r in checked}
                        certified = {r["cover_size"] for r in checked if r["optimal"] is True}
                        if len(certified) > 1:
                            raise ValueError("exact solver produced conflicting certified optima")
                        row = {"instance_id": entry["id"], "family": entry["family"], "n": entry["n"],
                               "m": entry["m"], "probability": entry["probability"], "seed": entry["seed"],
                               "base_id": entry["base_id"], "permutation_seed": entry["permutation_seed"],
                               "algorithm": algorithm, "repetition": repetition, "order": position,
                               "batch_calls": len(checked), "batch_elapsed_ns": elapsed,
                               "seconds_per_call": elapsed / len(checked) / 1e9,
                               "status": next(iter(statuses)) if len(statuses) == 1 else "mixed",
                               "optimal": all(r["optimal"] is True for r in checked) if algorithm == "exact" else None,
                               "cover_size": next(iter(sizes)) if len(sizes) == 1 else None,
                               "cover_size_min": min(sizes), "cover_size_max": max(sizes),
                               "lower_bound": min(r["lower_bound"] for r in checked),
                               "certified_optimum": next(iter(certified)) if certified else None, "valid_cover": True}
                        for counter in COUNTERS:
                            row[counter] = statistics.mean(r["stats"][counter] for r in checked) if algorithm == "exact" else None
                        writer.writerow(row)
                        details.write(json.dumps({"instance_id": entry["id"], "algorithm": algorithm,
                                                  "repetition": repetition, "batch_elapsed_ns": elapsed,
                                                  "calls": checked}, allow_nan=False) + "\n")
                        raw.flush()
                        details.flush()
                        metadata["measured_rows"] += 1
                if graph_digest(graph) != before:
                    raise ValueError("a solver mutated its input graph")
                if progress:
                    progress(index + 1, len(instances), entry["id"])
        metadata["completed"] = True
    except BaseException as exc:
        metadata["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        metadata["finished_utc"] = utc_now()
        metadata["raw_sha256"] = digest((output / "raw.csv").read_bytes()) if (output / "raw.csv").exists() else None
        metadata["details_sha256"] = digest((output / "details.jsonl").read_bytes()) if (output / "details.jsonl").exists() else None
        write_json(output / "metadata.json", metadata)
    return metadata
