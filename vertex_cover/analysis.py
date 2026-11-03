"""Rebuild summaries from validated raw data; never turn timeout incumbents into optima."""

from collections import defaultdict
import csv
import json
from math import isfinite
from pathlib import Path
import statistics

from .datasets import canonical_bytes, digest, new_directory, write_json


def median(values):
    return statistics.median(values) if values else None


def quartile(values, fraction):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * fraction
    low = int(position)
    return values[low] + (values[min(low + 1, len(values) - 1)] - values[low]) * (position - low)


def write_csv(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarise_run(run):
    run = Path(run)
    metadata = json.loads((run / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("schema_version") != 1 or metadata.get("completed") is not True:
        raise ValueError("analysis requires a completed schema-1 run; partial raw data must be inspected separately")
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    for name, recorded in [("raw.csv", "raw_sha256"), ("details.jsonl", "details_sha256"),
                           ("predictions.md", "predictions_sha256")]:
        if digest((run / name).read_bytes()) != metadata[recorded]:
            raise ValueError(f"run integrity check failed: {name}")
    if digest(canonical_bytes(manifest)) != metadata["manifest_sha256"]:
        raise ValueError("run manifest hash mismatch")
    with (run / "raw.csv").open(newline="", encoding="utf-8") as file:
        raw = list(csv.DictReader(file))
    repetitions = metadata["config"]["repetitions"]
    expected = len(manifest["instances"]) * repetitions * 2
    if len(raw) != expected or len(raw) != metadata["measured_rows"]:
        raise ValueError("raw row count does not match the completed run")
    grouped, seen = defaultdict(list), set()
    ids = {e["id"] for e in manifest["instances"]}
    for row in raw:
        key = (row["instance_id"], row["algorithm"], int(row["repetition"]))
        if (key in seen or key[0] not in ids or key[1] not in {"exact", "approximation"}
                or not 0 <= key[2] < repetitions or row["valid_cover"] != "True"):
            raise ValueError("duplicate or invalid benchmark row")
        seen.add(key)
        seconds = float(row["seconds_per_call"])
        if not isfinite(seconds) or seconds < 0:
            raise ValueError("invalid measured runtime")
        grouped[row["instance_id"]].append(row)
    instances = []
    for entry in manifest["instances"]:
        rows = grouped[entry["id"]]
        exact = [r for r in rows if r["algorithm"] == "exact"]
        approx = [r for r in rows if r["algorithm"] == "approximation"]
        if len(exact) != repetitions or len(approx) != repetitions:
            raise ValueError("unpaired algorithm measurements")
        if any(r["status"] != "completed" or r["cover_size"] == "" for r in approx):
            raise ValueError("incomplete approximation result")
        approx_sizes = {int(r["cover_size"]) for r in approx}
        if len(approx_sizes) != 1:
            raise ValueError("deterministic approximation changed cover size between calls")
        certified = {int(r["certified_optimum"]) for r in exact if r["certified_optimum"] != ""}
        if len(certified) > 1:
            raise ValueError("conflicting certified optima")
        optimum = next(iter(certified)) if certified else None
        approximation_size = next(iter(approx_sizes))
        if optimum is not None and not optimum <= approximation_size <= 2 * optimum:
            raise ValueError("approximation violates the bound against a certified optimum")
        fully_complete = all(r["status"] == "optimal" and r["optimal"] == "True" for r in exact)
        exact_time = median([float(r["seconds_per_call"]) for r in exact]) if fully_complete else None
        approx_time = median([float(r["seconds_per_call"]) for r in approx])
        instances.append({
            "instance_id": entry["id"], "family": entry["family"], "n": entry["n"], "m": entry["m"],
            "density": entry["density"], "probability": entry["probability"], "seed": entry["seed"],
            "base_id": entry["base_id"], "permutation_seed": entry["permutation_seed"],
            "is_relabelled": entry["permutation_seed"] is not None,
            "analytic_optimum": entry["analytic_optimum"], "certified_optimum": optimum,
            "exact_all_repetitions_optimal": fully_complete,
            "exact_completed_repetitions": sum(r["status"] == "optimal" for r in exact),
            "exact_total_repetitions": repetitions,
            "exact_median_complete_seconds": exact_time,
            "exact_median_observed_seconds": median([float(r["seconds_per_call"]) for r in exact]),
            "approximation_median_seconds": approx_time, "approximation_cover_size": approximation_size,
            "approximation_ratio": approximation_size / optimum if optimum is not None and optimum > 0 else None,
            "paired_speedup": exact_time / approx_time if exact_time is not None and approx_time > 0 else None,
            "exact_median_visited_nodes": median([float(r["nodes_visited"]) for r in exact]),
            "exact_median_expanded_nodes": median([float(r["nodes_expanded"]) for r in exact]),
            "exact_median_bound_prunes": median([float(r["pruned_by_bound"]) for r in exact]),
        })
    group_rows, buckets = [], defaultdict(list)
    for row in instances:
        if not row["is_relabelled"]:
            buckets[(row["family"], row["n"], row["probability"])].append(row)
    for (family, n, probability), items in sorted(buckets.items(), key=lambda t: str(t[0])):
        exact = [r["exact_median_complete_seconds"] for r in items if r["exact_all_repetitions_optimal"]]
        paired_approx = [r["approximation_median_seconds"] for r in items if r["exact_all_repetitions_optimal"]]
        approx = [r["approximation_median_seconds"] for r in items]
        ratios = [r["approximation_ratio"] for r in items if r["approximation_ratio"] is not None]
        group_rows.append({"family": family, "n": n, "probability": probability,
                           "instances": len(items), "exact_complete_instances": len(exact),
                           "exact_complete_fraction": len(exact) / len(items),
                           "exact_median_complete_seconds": median(exact),
                           "exact_q1_complete_seconds": quartile(exact, .25),
                           "exact_q3_complete_seconds": quartile(exact, .75),
                           "approximation_median_all_seconds": median(approx),
                           "approximation_median_paired_seconds": median(paired_approx),
                           "approximation_q1_paired_seconds": quartile(paired_approx, .25),
                           "approximation_q3_paired_seconds": quartile(paired_approx, .75),
                           "known_optimum_instances": len(ratios),
                           "approximation_median_ratio": median(ratios)})
    return {"schema_version": 1, "purpose": metadata["purpose"], "metadata": metadata,
            "instances": instances, "groups": group_rows,
            "notes": ["Primary group summaries exclude relabellings to avoid counting them as independent random graphs.",
                      "Completed exact runtimes and paired approximation runtimes use identical fully completed instance subsets.",
                      "Interrupted runtimes are observed work, not time-to-optimality. Completion fractions expose censoring.",
                      "Quality ratios require a measured certified optimum greater than zero; empty and unproved cases are null.",
                      "Timing batches retain results and include common wrapper overhead; this is not a memory benchmark."]}


def analyse_run(run, output):
    summary = summarise_run(run)
    output = new_directory(output)
    write_json(output / "summary.json", summary)
    write_csv(output / "instances.csv", summary["instances"])
    write_csv(output / "groups.csv", summary["groups"])
    items = summary["instances"]
    complete = sum(r["exact_all_repetitions_optimal"] for r in items)
    ratio_count = sum(r["approximation_ratio"] is not None for r in items)
    lines = ["# Generated comparison summary", "", f"Run purpose: **{summary['purpose']}**.", "",
             f"Instances: {len(items)}. Exact finished every measured repetition on {complete} instances.",
             f"Quality ratios with a measured certified positive optimum: {ratio_count} instances.", "",
             "Pipeline-validation measurements must not be presented as a final empirical study.", "",
             "## Interpretation rules", "", *[f"- {note}" for note in summary["notes"]], "",
             "## Reproduction", "", "Source hashes, interpreter, platform, timer, limits, batch selection and predictions",
             "are preserved in the run metadata. Inspect raw.csv and details.jsonl before drawing conclusions.", "",
             "The program does not invent a surprising result or a causal explanation; those require analysis."]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
