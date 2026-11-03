"""Experiment commands kept separate from the original single-graph solver CLI."""

import argparse
from pathlib import Path
import sys

from .analysis import analyse_run
from .benchmark import run_benchmarks
from .datasets import generate_dataset, new_directory

COMMANDS = {"generate", "benchmark", "analyse", "plot", "experiment"}


def main(argv):
    parser = argparse.ArgumentParser(description="Reproducible vertex cover comparison workflow")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ["generate", "experiment"]:
        p = sub.add_parser(command)
        p.add_argument("--config", type=Path, required=True)
        p.add_argument("--output", type=Path, required=True, help="new directory; existing data is never overwritten")
        if command == "experiment":
            p.add_argument("--plots", action="store_true", help="also build plots; requires the plots extra")
    p = sub.add_parser("benchmark")
    p.add_argument("--dataset", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("analyse")
    p.add_argument("--run", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = sub.add_parser("plot")
    p.add_argument("--analysis", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    def progress(done, total, identifier):
        print(f"[{done}/{total}] {identifier}", flush=True)

    try:
        if args.command == "generate":
            manifest = generate_dataset(args.config, args.output)
            print(f"Generated {len(manifest['instances'])} input graphs at {args.output}")
        elif args.command == "benchmark":
            result = run_benchmarks(args.dataset, args.output, progress)
            print(f"Saved {result['measured_rows']} measured rows at {args.output}")
        elif args.command == "analyse":
            summary = analyse_run(args.run, args.output)
            print(f"Summarised {len(summary['instances'])} instances at {args.output}")
        elif args.command == "plot":
            from .plots import plot_summary
            files = plot_summary(args.analysis, args.output)
            print(f"Saved {len(files)} plot files at {args.output}")
        elif args.command == "experiment":
            root = new_directory(args.output)
            generate_dataset(args.config, root / "inputs")
            run_benchmarks(root / "inputs", root / "run", progress)
            summary = analyse_run(root / "run", root / "analysis")
            print(f"Completed {len(summary['instances'])} instances; saved data and summaries in {root}")
            if args.plots:
                from .plots import plot_summary
                files = plot_summary(root / "analysis", root / "plots")
                print(f"Saved {len(files)} plot files")
    except KeyboardInterrupt:
        print("Interrupted. Preserve the partial output; it is not a completed experiment.", file=sys.stderr)
        return 130
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0
