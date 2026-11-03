# Predictions before comparative timing

Recorded before this workflow's first benchmark run on 3 November 2026.
These are AI-assisted proposed predictions from the report discussion, not a
claim that either student independently endorsed them. Both students should
review this file and commit their accepted predictions before the final study.
The runner snapshots this text and its SHA256 before any warm-up or measured
solver call. Do not retrospectively rewrite a completed run's prediction record.

1. The approximation should usually be faster on nontrivial paired instances;
   tiny cases may be dominated by measurement overhead. No systematic crossover
   favouring exact search as size increases is predicted.
2. Low-confidence estimate: some random graphs of roughly 30–50 vertices with
   edge probability 0.3–0.7 may reach a two-second cooperative exact-search limit.
   A different observed boundary is a finding, not a reason to rewrite this guess.
3. Approximation scan cost should increase with edge count. Exact runtime may
   vary non-monotonically with density because bounds and branching also change.
4. Known mathematical controls: stars and disjoint edges have approximation
   ratio 2; a clique on n >= 2 vertices has ratio 2*floor(n/2)/(n-1).
   Confirming these is a correctness check, not an unexpected empirical result.
5. Vertex relabelling can change greedy matching quality and exact search effort.
   Shuffling constructor input cannot: Graph canonicalises and sorts its edges.

Smoke runs validate the pipeline and are not the final empirical study. Record
the actual final machine, accepted predictions, configuration, and source state
with the final measurements. Keep genuine surprises and follow-up explanations
in the report after examining raw results.
