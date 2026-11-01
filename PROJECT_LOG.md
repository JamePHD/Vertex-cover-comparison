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
