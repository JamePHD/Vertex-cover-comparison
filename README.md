# Vertex-cover-comparison
vertex cover comparison

Theme 1: exact branch-and-bound versus a maximal-matching 2-approximation.
Both solvers are implemented; comparative experiments and the report remain.

## Run without installation

Requires Python 3.11 or newer. No third-party runtime or test packages.
Open a terminal **inside this folder**, where this README and `vertex_cover/`
are directly visible. On Windows:

```powershell
py -3.11 -m vertex_cover examples/triangle.json
py -3.11 -m vertex_cover examples/triangle.json --algorithm approximation
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
- Approximation: maximal-matching 2-approximation for the other group member.
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

The default algorithm is `exact`. Its JSON output and exit codes remain:

- `0`: optimality proved (including an empty graph).
- `1`: limit reached; the returned cover is valid but not proved optimal.
- `2`: invalid input or arguments, or an unreadable file.

The exact CLI defaults to a 10-second time limit. The exact library API defaults
to no limit. Both accept an optional search-node limit. `--algorithm exact`
explicitly selects the same mode.

With `--algorithm approximation`, the JSON includes `algorithm` set to
`maximal_matching_2_approximation`, sorted `cover`, `cover_size`, `valid_cover`,
`status: "completed"`, `optimal: null`, `matching`, `matching_size`, and
`lower_bound`. Completion does not establish optimality; `null` means not
assessed, even if this particular cover happens to be optimal. Exit code 0
means successful construction; invalid input or arguments return 2.
Approximation mode rejects explicitly supplied `--time-limit` or `--node-limit`
options, including zero and the exact mode's default value of ten seconds.

## Shared API for both group members

```python
from vertex_cover import Graph, is_vertex_cover, solve_exact, solve_approximation

graph = Graph(3, [(0, 1), (1, 2), (0, 2)])
approximation = solve_approximation(graph)
assert is_vertex_cover(graph, approximation.cover)
result = solve_exact(graph, time_limit=10.0)
assert is_vertex_cover(graph, result.cover)
if result.optimal:
    print("Proved optimum:", result.cover_size)
else:
    print("Not proved:", result.lower_bound, "<= optimum <=", result.cover_size)
```

`solve_approximation(graph)` accepts the same immutable `Graph` and returns a
frozen `ApproximationResult`: `cover` is a `frozenset[int]` and `matching` is a
tuple of selected edges. Properties expose `cover_size`, `matching_size`, and
`lower_bound` (the matching size). It has no exact-search status or statistics.
Both solvers reject a non-`Graph` argument with `TypeError`.

`Graph.edges` has canonical sorted order. The approximation always follows
that order: shuffling constructor input cannot change its answer. Vertex
relabelling can change its selected matching and cover size.

## How the approximation works

Scan every edge once, selecting it only if neither endpoint is already marked.
Mark both endpoints when selecting an edge and return all marked vertices.
This constructs a **maximal** matching (one that cannot be extended), rather
than necessarily a maximum matching (one of largest size).

Selected edges have disjoint endpoints. Each skipped edge already touches a
marked endpoint, and marks are never removed, so every edge is covered. Every
vertex cover must include a distinct vertex for each disjoint matching edge.
Consequently `matching_size <= OPT <= cover_size = 2 * matching_size`, proving
the factor-two guarantee, including for edgeless graphs.

The Boolean vertex array, single edge scan, and final cover construction take
O(n + m) time and O(n) space, including the result. Graph normalisation is
outside this bound. Each call uses fresh local state and leaves the graph
unchanged. The baseline performs no redundant-vertex removal or randomisation.

For the path `(0,1), (1,2), (2,3)`, the matching is `(0,1), (2,3)` and the cover
contains all four vertices, while OPT is two. Relabelling the path to edges
`(0,1), (0,2), (1,3)` yields only matching edge `(0,1)` and a cover of size two.
On a triangle the cover size is two, which is optimal. On a nonempty star it
is two, while OPT is one.

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

Both solver suites use a shared independent subset-enumeration oracle. Each
checks all **1,100 labelled simple graphs with 0–5 vertices** and 300 seeded
random graphs with 0–11 vertices. Approximation checks cover feasibility,
matching membership, disjoint endpoints, maximality, exact endpoint union,
the factor-two bound, determinism, and unchanged input. Structured tests cover
empty graphs, isolates, single and disjoint edges, stars, cliques, paths,
cycles, disconnected graphs, and label sensitivity. A 100,000-vertex sparse
case checks large vertex identifiers and iterative construction.

The suite also checks frozen results, invalid arguments, exact interruptions,
both solvers on the same graph, and CLI subprocesses including rejected
approximation limits and unchanged exact output. All **33 test methods** passed
on Python 3.14 on Windows. Python 3.11 is the declared minimum; that interpreter
was not available for this validation. If the environment blocks the default
temporary folder, run from this project folder with writable temporary paths:

```powershell
$env:TEMP = (Get-Location).Path
$env:TMP = (Get-Location).Path
python -m unittest discover -s tests -v
```

These are correctness checks, not performance experiments or evidence of a
runtime crossover.

## Before performance experiments

Write and commit your own theoretical predictions first. Agree on graph
families, sizes, repetitions, seeds, timeout policy, timing boundaries, and the
same immutable graph instances for both algorithms. Use comparable tuning
effort; report the exact solver's matching bound and initial incumbent openly.
Preserve raw measurements and censored timeout status. Keep a project log of
actual bugs, design decisions, AI failures, and each person's contributions.

Do not describe unrun experiments or fabricated surprises as completed work.

For the future benchmark adapter, time each complete solver call externally
with `time.perf_counter`, using the same preconstructed `Graph` for both.
Include allocation and result construction; exclude graph generation,
validation, JSON serialisation, and plotting. Keep separate result types and
record approximation completion separately from exact optimality. Do not
change the exact solver's initial incumbent for the baseline comparison.

Compute `approximation.cover_size / exact.cover_size` only when
`exact.optimal` is true and `exact.cover_size > 0`. Record edgeless ratios as
not applicable and retain timeout/node-limit results without treating their
incumbents as certified optima. If agreed for the study, pass
`time_limit=2.0` explicitly to the exact solver; its CLI default is ten seconds.
The full comparative runner, measurements, and plots are still pending.

## Research starting point

Carnegie Mellon, *Design & Analysis of Algorithms, Lecture 18: Approximation
Algorithms* (2017), includes vertex-cover matching bounds and exact branching:
https://www.cs.cmu.edu/~15451-s17/lectures/lec18-approx.pdf

Read the original material and cite what you actually consult in your report.
