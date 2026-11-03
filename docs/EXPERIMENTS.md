# Comparison protocol and reproduction

## What is implemented

Both original algorithms are retained. The additional modules generate graphs,
record paired timings and certificates, validate raw artifacts, build summaries,
and export standard Matplotlib figures. The program does not write invented
findings, personal reflections, or surprising results. Student ownership and
AI disclosures still apply to algorithm review, analysis, and presentation.

## Before final measurements

Review the AI-assisted hypotheses in `PREDICTIONS.md`, record the students'
actual accepted predictions, and commit them before any final-study warm-up.
The runner snapshots the file before timing and stores its SHA256. Snapshotting
does not establish that the students endorsed it. Smoke data is explicitly
labelled pipeline validation and must not silently become final study data.

`configs/study.json` is a runnable proposal, not a claim that the experiment
has already been conducted. The Word report's older methodology may differ:
update it to the settings and software actually used after the study. In
particular the implemented fast-call batch rule uses the last completed
warm-up, a 1 ms threshold, and at most 25 calls per measured batch.

## Inputs

Random graphs use independent edge inclusion for every unordered vertex pair
with probability p and a local `random.Random(seed)`. Ten seeds per (n,p)
configuration are recorded. Seeds are reused across configurations, so graphs
with the same n and seed at different probabilities have coupled/nested edge
sets; these configurations are not pooled as independent samples. Realised m
and density, rather than p alone, are preserved.

Structured graphs are paths, simple cycles, stars, cliques, disjoint edges,
and complete bipartite graphs with partitions floor(n/2) and ceil(n/2).
Their analytic optima are correctness checks. Quality ratios in the main
analysis still require a measured exact-solver certificate.

Relabelling maps old vertex v to permutation[v] and then passes through the
same canonical Graph constructor. OPT is unchanged. A changed matching is
possible; shuffling input edges alone has no effect. The manifest records
base IDs, permutation seeds, and the actual permutations. Primary grouped
summaries exclude relabellings to avoid pseudoreplication. The separate
labelling figure includes baseline and related relabelled observations.

## Timing

- Time complete library solver calls using `perf_counter_ns`. Input construction,
  graph normalisation, validation, JSON formatting and file I/O are outside it.
- Include each method's setup, result construction, and the same wrapper/list
  retention overhead. No algorithm receives the other's computed answer.
- Warm up each algorithm once per instance by default. Alternate measured
  execution order using instance index and repetition number.
- If the last warm-up completes below the configured threshold, time a batch
  of fresh calls and divide elapsed batch time by call count. With no warm-up,
  batch size is one. Store every result/certificate in details.jsonl.
- Keep garbage collection enabled as found; record its state and thresholds.
  Record interpreter, OS, CPU, RAM where available, timer resolution, source
  hashes, configuration, prediction hash and timer-call overhead.
- Power settings, competing background workloads, and thermal state are not
  reliably detected. Record/control them manually in the final methodology.
- Limits are cooperative. A timed batch or individual exact call can exceed
  the nominal timeout. There is no hard process kill or fabricated capped time.

## Analysis rules

Each measured batch produces a raw row. Median per-call batch times summarise
repetitions within a graph, then medians and linearly interpolated quartiles
summarise base instances within each family/size/probability group. Separate
timing repetitions from different random graphs and isomorphic relabellings.

An exact instance enters completed timing summaries only if every measured
repetition/batch call proves optimality. The paired approximation summary uses
that exact same subset, while a separate all-instance approximation summary
retains the broader sample. Completion fractions and red interrupted markers
expose censoring; never interpret the latter as time-to-optimality.

A certified optimum from any measured exact call can establish a denominator
for quality. Interrupted incumbents never do. Mixed completed/interrupted
batches retain all call details but are not declared completed runtime rows.
Zero-optimum graphs have null ratios, not ratio 1. Invalid covers, contradictory
bounds, invalid matching certificates, or conflicting optima abort a run and
leave metadata.completed false. Incomplete or tampered data cannot be passed
off by the normal analysis command as completed results.

The internal maximum stack size counts pending states; it is not bytes of RAM.
This baseline does not claim to measure peak memory. More sophisticated bounds,
component decomposition, or approximation post-processing would be separate
algorithm variants, not silent mid-experiment changes.

## Output tree

An `experiment` run creates:

```text
results/<run-name>/
  inputs/
    config.json
    predictions.md
    manifest.json
    graphs/*.json
  run/
    metadata.json
    manifest.json
    predictions.md
    raw.csv
    details.jsonl
  analysis/
    summary.json
    summary.md
    instances.csv
    groups.csv
  plots/                         # when --plots is requested
    runtime.{png,svg,pdf}
    quality.{png,svg,pdf}
    completion.{png,svg,pdf}
    search_effort.{png,svg,pdf}
    labelling.{png,svg,pdf}       # if relabelled instances exist
    plot_metadata.json
    README.md
```

Preserve raw data and configurations with the submission. Exact replay means
the same generated graphs, settings, and analysis; timing values naturally
vary with hardware and system activity. Existing folders are never overwritten.
After a failed run, keep its metadata and rerun into a fresh output folder.
Do not analyse only favourable rows or hide timeouts.

## Minimum checks before using final plots

1. Run the full correctness suite, including optional plot tests.
2. Review the accepted predictions and actual experiment configuration.
3. Check metadata.completed is true and the expected input and row counts match.
4. Inspect both the raw data and group denominators, not just plotted medians.
5. Investigate real deviations from predictions and explain them with algorithm
   behaviour; keep known mathematical controls out of the surprise section.
