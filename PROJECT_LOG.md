# Project log

## 2 November 2026 — initial exact-solver implementation

- Codex generated the initial exact solver, shared graph interface, CLI, tests,
  and documentation at Derek's request. This does not establish independent
  student authorship or understanding; Derek's review is still required.
- Correctness checks ran with the bundled Python interpreter: 16 test methods
  passed, including 1,100 exhaustive graph cases and 300 seeded random graphs.
- The Windows `py -3.11` launcher failed with access denied in this environment.
  Codex used the available bundled interpreter instead.
- Actual AI-code issue found during development: the first cover validator
  converted values to a set before validating identifiers. Python treats `True`
  and `1` as equal, so that could hide a Boolean value in a mixed input. Codex
  changed the order to validate every supplied value before constructing the
  set and added regression cases. Do not claim a student personally found this
  unless they independently did so.
- No performance comparison has been run. No empirical findings or surprises
  have been established. The partner's approximation is not implemented yet.

## To record as work proceeds

Each member should add their actual reviews, changes, questions, bugs,
algorithm explanations, AI tool use, and contributions. Write theoretical
predictions before performance experiments; retain their original wording.

## 3 November 2026 — comparison workflow

- At Derek's request, Codex added graph generation, saved input manifests,
  paired timing, integrity-checked summaries, Matplotlib plots, and workflow
  tests on a separate comparison-workflow branch. The original exact and
  approximation implementations are preserved.
- The prediction snapshot is AI-assisted and explicitly awaits student review;
  it must not be represented as independent student beliefs without review.
- Tests cover known generator optima, hashing, corruption, no-overwrite
  behaviour, interruption, mixed-status batches, quality denominators,
  relabelling, paired samples, subprocesses, and plot exports.
- Installation of the isolated plotting dependency initially failed because
  the restricted default temporary directory could not be used by the package
  installer. Retrying with a writable task-local temporary directory succeeded.
  This is an environment/setup issue, not an invented algorithmic AI failure.
- Smoke-run artifacts are labelled pipeline validation. Record final study
  execution and student interpretation separately when those are completed.
- The full suite passed all 49 tests on the actual repository with Python
  3.12.14 and Matplotlib 3.11.2. The 23-graph smoke run saved 138 measured
  rows and exercised interrupted exact searches. Both solver modules were
  kept byte-for-byte unchanged.
- A genuine AI-generated plotting issue was found during visual review:
  when there was only one relabelling category, automatic x-axis limits
  expanded its small display jitter across the whole chart. Codex fixed
  explicit categorical limits and regenerated the figure from saved data.
  This was tool-detected, not evidence that a student independently found it.

## 2 November 2026 — approximation implementation and integration

- Added the deterministic maximal-matching 2-approximation with immutable
  cover/matching results and a matching-size lower bound. It reuses `Graph`
  and canonical edge order; the exact solver and its initial incumbent remain
  unchanged.
- Added `--algorithm approximation`, retaining exact mode as the default and
  its existing JSON/exit-code behaviour. Approximation reports completion with
  optimality not assessed and rejects exact-only limits.
- Moved the existing brute-force oracle into a shared test helper. All 33 test
  methods passed on Python 3.14 on Windows, including 1,100 exhaustive and 300
  seeded random cases per solver, matching invariants, structured families,
  a 100,000-vertex sparse case, and CLI compatibility/error handling.
- The first full test run encountered temporary-folder permission errors in
  three CLI tests (including an existing exact test). Repeating with TEMP/TMP
  pointing inside the workspace passed. This was an environment issue; no
  solver defect was found by these checks.
- Python 3.11 compatibility follows the declared API/syntax requirements but
  was not tested on a Python 3.11 interpreter. No comparative performance
  experiments have been run; the report and benchmark runner remain pending.
