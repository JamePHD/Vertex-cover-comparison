# Vertex-cover-comparison
vertex cover comparison

Theme 1: exact branch-and-bound versus a maximal-matching 2-approximation.
This is the implementation starting point, not a completed assignment.

## Run without installation

Requires Python 3.11 or newer. No third-party runtime or test packages.
Open a terminal **inside this folder**, where this README and `vertex_cover/`
are directly visible. On Windows:

```powershell
py -3.11 -m vertex_cover examples/triangle.json
py -3.11 -m vertex_cover examples/star.json --time-limit 10 --node-limit 100000
py -3.11 -m unittest discover -s tests -v
```

On systems where `python` is the appropriate Python 3.11+ executable,
replace `py -3.11` with `python`. No PYTHONPATH setting is needed.
If the Windows Store Python alias or launcher reports "Access is denied",
use the full path to an accessible Python 3.11+ interpreter instead. During
development in Codex the launcher was blocked, so validation used Codex's
bundled Python executable; the documented `py` launcher was not verified in
that restricted environment.
The package metadata also supports installation with `python -m pip install .`
if desired; this is optional and the build backend may need downloading.

## Current scope and responsibility

- Exact solver: assigned student owner **Derek Song**.
- Approximation: assigned to the other group member; **not implemented here**.
- Shared graph model, feasibility checker, JSON CLI, and correctness tests included.
- Unified performance benchmarks, plots, report, and video remain future work.

This initial implementation and its tests/documentation were generated using
Codex. The assigned owner must review, understand, and take responsibility for
the implementation; the ownership label does not imply independent authorship.
Maintain accurate personal AI-use disclosures and contribution records.

## Input and output

Graphs are simple, unweighted, undirected. Vertices are integers `0..n-1`.
Isolated vertices are allowed. Repeated/reversed edges are deduplicated;
self-loops and invalid endpoints are rejected.

```json
{"num_vertices": 3, "edges": [[0, 1], [1, 2], [0, 2]]}
```

The command returns JSON: cover, cover size, validity, optimality status,
lower bound, and search statistics. Exit codes:

- `0`: optimality proved (including an empty graph).
- `1`: limit reached; the returned cover is valid but not proved optimal.
- `2`: invalid input or arguments, or an unreadable file.

The CLI defaults to a 10-second time limit. The library API defaults to no
limit. Both accept an optional search-node limit.

## Shared API for both group members

```python
from vertex_cover import Graph, is_vertex_cover, solve_exact

graph = Graph(3, [(0, 1), (1, 2), (0, 2)])
result = solve_exact(graph, time_limit=10.0)
assert is_vertex_cover(graph, result.cover)
if result.optimal:
    print("Proved optimum:", result.cover_size)
else:
    print("Not proved:", result.lower_bound, "<= optimum <=", result.cover_size)
```

Partner handoff: implement a separately attributed approximation module that
accepts the same immutable `Graph`, returns its selected vertices, and can be
checked by `is_vertex_cover`. Agree on the unified result format together
before building the benchmark runner. `Graph.edges` has canonical sorted order;
an edge-order experiment must explicitly supply a separate traversal order or
document a vertex relabelling policy, since shuffling constructor input alone
does not change this stored order.

## How the exact solver works

1. Start with all non-isolated vertices as a valid incumbent (current best cover).
2. Each search state stores the chosen vertices and all still-uncovered edges.
3. Pick an uncovered edge `(u, v)`. Every feasible completion must choose `u`
   or `v`, so explore both possibilities. Remove edges covered by that choice.
4. Prune if the chosen set already cannot improve the incumbent.
5. A greedy matching among remaining edges provides a lower bound: each
   disjoint matching edge needs a different selected vertex. Prune when
   chosen size plus this bound cannot improve the incumbent.
6. A complete cover improves the incumbent. If it reaches the initial global
   matching lower bound, optimality is established immediately. Otherwise
   exhaust all branches that could improve the answer.

The matching computation is an internal bound, not an implementation of the
partner's approximation solver. Branches prefer edges with high-degree
endpoints; ties and traversal are deterministic. An explicit stack avoids
Python's recursion-depth limit. Exhaustive branching is exponential in the
worst case; pruning improves some instances without eliminating that risk.

## Statistics and limits

- `nodes_visited`: states popped for processing; the node limit caps this.
- `nodes_expanded`: states that actually create two child branches.
- `pruned_by_size`, `pruned_by_bound`: states rejected by each bound.
- `leaves`: complete covers accepted as improvements.
- `incumbent_updates`: number of improvements to the initial cover.
- `max_stack_size`: largest number of pending states, not a byte-memory measure.
- `elapsed_seconds`: solver wall time, including its setup and result construction;
  excludes graph parsing and file I/O. Future benchmarks should additionally
  measure whole solver calls externally with the same timing boundaries.

Time limits are cooperative, checked between states. Setup and a single node
can run past the requested limit; this is not a hard process deadline.
On interruption, the lower bound is the initial matching bound, not a claim of
the tightest bound available. Never use the returned cover size as the optimum
unless `optimal` is true. Compute empirical approximation ratios only on
instances with an established optimum.

## Correctness validation

Tests use independent exhaustive subset enumeration, rather than reusing the
branch-and-bound logic. They compare all **1,100 labelled simple graphs with
0–5 vertices**, 300 seeded random graphs with 0–11 vertices, structured families,
disconnected graphs, isolated vertices, invalid inputs, interruption results,
and real command-line subprocess execution. These are correctness tests, not
performance experiments or evidence of a runtime crossover.

## Before performance experiments

Write and commit your own theoretical predictions first. Agree on graph
families, sizes, repetitions, seeds, timeout policy, timing boundaries, and the
same immutable graph instances for both algorithms. Use comparable tuning
effort; report the exact solver's matching bound and initial incumbent openly.
Preserve raw measurements and censored timeout status. Keep a project log of
actual bugs, design decisions, AI failures, and each person's contributions.

Do not describe unrun experiments or fabricated surprises as completed work.

## Research starting point

Carnegie Mellon, *Design & Analysis of Algorithms, Lecture 18: Approximation
Algorithms* (2017), includes vertex-cover matching bounds and exact branching:
https://www.cs.cmu.edu/~15451-s17/lectures/lec18-approx.pdf

Read the original material and cite what you actually consult in your report.
