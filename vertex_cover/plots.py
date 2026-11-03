"""Standalone report plots from saved summaries; optional Matplotlib dependency."""

from collections import defaultdict
import json
from pathlib import Path

from .datasets import digest, new_directory, write_json


def plot_summary(analysis, output):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise ValueError('Plotting needs Matplotlib: install with python -m pip install ".[plots]"') from exc
    summary = json.loads((Path(analysis) / "summary.json").read_text(encoding="utf-8"))
    if summary.get("schema_version") != 1:
        raise ValueError("unsupported summary schema")
    output = new_directory(output)
    base = [r for r in summary["instances"] if not r["is_relabelled"]]
    label = "PIPELINE VALIDATION" if summary["purpose"] == "pipeline_validation" else "Comparative study"
    written = []

    def save(fig, name, caption):
        fig.suptitle(label, fontsize=10, color="#555555")
        fig.text(.02, .015, caption, fontsize=8, color="#555555")
        fig.tight_layout(rect=(0, .07, 1, .93))
        for extension in ["png", "svg", "pdf"]:
            path = output / f"{name}.{extension}"
            fig.savefig(path, dpi=180)
            written.append(path.name)
        plt.close(fig)

    # Keep each probability/family in its own panel, rather than pooling unlike graphs.
    panels = defaultdict(list)
    for row in summary["groups"]:
        panels[(row["family"], row["probability"])].append(row)
    keys = sorted(panels, key=str)
    columns = min(3, len(keys))
    rows = (len(keys) + columns - 1) // columns
    fig, axes = plt.subplots(rows, columns, figsize=(4.3 * columns, 3.3 * rows), squeeze=False)
    for ax, key in zip(axes.flat, keys):
        values = sorted(panels[key], key=lambda r: r["n"])
        for algorithm, field, color in [("Exact", "exact_median_complete_seconds", "#2563a6"),
                                          ("Approximation paired", "approximation_median_paired_seconds", "#d97518")]:
            selected = [r for r in values if r[field] is not None and r[field] > 0]
            ax.plot([r["n"] for r in selected], [r[field] * 1000 for r in selected], "o-", label=algorithm, color=color)
            prefix = "exact" if algorithm == "Exact" else "approximation"
            q1field = "exact_q1_complete_seconds" if prefix == "exact" else "approximation_q1_paired_seconds"
            q3field = "exact_q3_complete_seconds" if prefix == "exact" else "approximation_q3_paired_seconds"
            ax.fill_between([r["n"] for r in selected], [r[q1field] * 1000 for r in selected],
                            [r[q3field] * 1000 for r in selected], color=color, alpha=.15)
        incomplete = [r for r in base if (r["family"], r["probability"]) == key and not r["exact_all_repetitions_optimal"]]
        if incomplete:
            ax.scatter([r["n"] for r in incomplete], [max(r["exact_median_observed_seconds"] * 1000, 1e-9) for r in incomplete],
                       marker="x", color="#b52025", label="Exact interrupted (observed)")
        ax.set_title(key[0] + (f" p={key[1]}" if key[1] is not None else ""))
        ax.set_xlabel("Vertices n"); ax.set_ylabel("Milliseconds per call (log)")
        ax.set_yscale("log"); ax.grid(alpha=.2); ax.legend(fontsize=7)
    for ax in list(axes.flat)[len(keys):]:
        ax.set_visible(False)
    save(fig, "runtime", "Base graphs only. Lines use paired fully-completed instances; bands show across-instance IQR. Red crosses are not completion times.")

    fig, ax = plt.subplots(figsize=(10, 5))
    families = sorted({r["family"] for r in base})
    for index, family in enumerate(families):
        points = [r for r in base if r["family"] == family and r["approximation_ratio"] is not None]
        ax.scatter([index + (j % 7 - 3) * .035 for j in range(len(points))],
                   [r["approximation_ratio"] for r in points], alpha=.55, s=25)
    ax.axhline(1, color="grey", linestyle=":"); ax.axhline(2, color="#b52025", linestyle="--", label="Factor-two guarantee")
    ax.set_xticks(range(len(families)), families, rotation=20, ha="right")
    ax.set_ylabel("Approximation size / certified optimum"); ax.set_ylim(.9, 2.1)
    ax.set_title("Solution quality"); ax.legend(); ax.grid(axis="y", alpha=.2)
    save(fig, "quality", "One point per base graph with measured certified positive optimum. Empty and unproved instances are excluded, not assigned ratio 1.")

    fig, ax = plt.subplots(figsize=(10, 5))
    grouped = defaultdict(list)
    for row in summary["groups"]:
        grouped[(row["family"], row["probability"])].append(row)
    for (family, probability), values in sorted(grouped.items(), key=lambda t: str(t[0])):
        values = sorted(values, key=lambda r: r["n"])
        ax.plot([r["n"] for r in values], [100 * r["exact_complete_fraction"] for r in values], "o-",
                label=family + (f" p={probability}" if probability is not None else ""))
    ax.set_xlabel("Vertices n"); ax.set_ylabel("Exact fully-completed instances (%)")
    ax.set_ylim(-3, 103); ax.set_title("Exact completion under configured limits")
    ax.grid(alpha=.2); ax.legend(fontsize=7, ncol=2)
    save(fig, "completion", "An instance is fully completed only if every measured exact repetition proves optimality. Base graphs only.")

    fig, ax = plt.subplots(figsize=(8, 5))
    for family in families:
        values = [r for r in base if r["family"] == family and r["exact_all_repetitions_optimal"]
                  and r["exact_median_visited_nodes"] > 0 and r["exact_median_complete_seconds"] > 0]
        if values:
            ax.scatter([r["exact_median_visited_nodes"] for r in values],
                       [r["exact_median_complete_seconds"] * 1000 for r in values], label=family, alpha=.65)
    ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlabel("Median visited search states")
    ax.set_ylabel("Median completed milliseconds per call"); ax.set_title("Search effort and runtime")
    ax.grid(alpha=.2)
    if ax.collections:
        ax.legend(fontsize=8)
    save(fig, "search_effort", "Completed base instances only. State-processing costs differ with remaining edge count; correlation is not a causal proof.")

    relabels = [r for r in summary["instances"] if r["is_relabelled"]]
    if relabels:
        fig, ax = plt.subplots(figsize=(10, 5))
        ids = sorted({r["base_id"] for r in relabels})
        for index, identifier in enumerate(ids):
            values = [r for r in summary["instances"] if r["base_id"] == identifier and r["approximation_ratio"] is not None]
            ax.scatter([index + (j % 7 - 3) * .04 for j in range(len(values))],
                       [r["approximation_ratio"] for r in values], alpha=.7)
        ax.set_xticks(range(len(ids)), ids, rotation=20, ha="right")
        ax.set_xlim(-.5, len(ids) - .5)
        ax.set_ylabel("Approximation size / certified optimum"); ax.set_ylim(.9, 2.1)
        ax.set_title("Quality sensitivity on isomorphic relabellings")
        save(fig, "labelling", "Baseline and relabelled graphs share a base ID. They are related observations, not additional independent random graphs.")
    (output / "README.md").write_text("# Rebuilt plots\n\n" + "\n".join(f"- {f}" for f in written) +
                                      "\n\nGenerated only from saved analysis/summary.json.\n", encoding="utf-8")
    write_json(output / "plot_metadata.json", {"matplotlib_version": matplotlib.__version__,
               "plot_source_sha256": digest(Path(__file__).read_bytes()),
               "summary_sha256": digest((Path(analysis) / "summary.json").read_bytes()),
               "files": written})
    return written
