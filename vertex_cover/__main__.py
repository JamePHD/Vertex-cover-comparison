"""Shared JSON interface for exact and approximate vertex cover."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .approximation import solve_approximation
from .exact import solve_exact
from .graph import Graph, is_vertex_cover


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exact or approximate minimum vertex cover")
    parser.add_argument("graph", type=Path, help="JSON with num_vertices and edges")
    parser.add_argument("--algorithm", choices=("exact", "approximation"), default="exact")
    parser.add_argument("--time-limit", type=float, default=None,
                        help="exact only: cooperative seconds limit (default: 10)")
    parser.add_argument("--node-limit", type=int, default=None,
                        help="exact only: maximum search nodes")
    args = parser.parse_args(argv)
    if args.algorithm == "approximation" and (args.time_limit is not None
                                               or args.node_limit is not None):
        parser.error("--time-limit and --node-limit apply only to --algorithm exact")
    try:
        payload = json.loads(args.graph.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("graph JSON must be an object")
        graph = Graph(payload["num_vertices"], payload["edges"])
        if args.algorithm == "approximation":
            approximation = solve_approximation(graph)
            print(json.dumps({
                "algorithm": "maximal_matching_2_approximation",
                "cover": sorted(approximation.cover),
                "cover_size": approximation.cover_size,
                "valid_cover": is_vertex_cover(graph, approximation.cover),
                "status": "completed",
                "optimal": None,
                "matching": approximation.matching,
                "matching_size": approximation.matching_size,
                "lower_bound": approximation.lower_bound,
            }, indent=2))
            return 0
        time_limit = 10.0 if args.time_limit is None else args.time_limit
        result = solve_exact(graph, time_limit=time_limit, node_limit=args.node_limit)
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "algorithm": "branch_and_bound",
        "cover": sorted(result.cover),
        "cover_size": result.cover_size,
        "valid_cover": is_vertex_cover(graph, result.cover),
        "status": result.status,
        "optimal": result.optimal,
        "lower_bound": result.lower_bound,
        "stats": asdict(result.stats),
    }, indent=2))
    return 0 if result.optimal else 1


if __name__ == "__main__":
    raise SystemExit(main())
