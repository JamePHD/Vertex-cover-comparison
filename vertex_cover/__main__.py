"""Small JSON interface for Derek's exact solver."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from .exact import solve_exact
from .graph import Graph, is_vertex_cover


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Exact minimum vertex cover (branch-and-bound)")
    parser.add_argument("graph", type=Path, help="JSON with num_vertices and edges")
    parser.add_argument("--time-limit", type=float, default=10.0,
                        help="cooperative time limit in seconds (default: 10)")
    parser.add_argument("--node-limit", type=int, default=None)
    args = parser.parse_args(argv)
    try:
        payload = json.loads(args.graph.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("graph JSON must be an object")
        graph = Graph(payload["num_vertices"], payload["edges"])
        result = solve_exact(graph, time_limit=args.time_limit, node_limit=args.node_limit)
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
