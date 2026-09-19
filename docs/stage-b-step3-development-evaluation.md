# Stage B, Step 3 — development evaluator and comparator

Date: 2026-09-19. Status: **COMPLETED — development only**.

## Frozen inputs

- Stage A candidate configuration: `m2.75-d0-c4-n10-p0.7`.
- All 17 fixed-seed corruption scenarios.
- Development sequence: `01` only.
- Exact link potential: `exp(-proposal_score_px / 4.0)`.
- New-track potential: `exp(-10.0 / 4.0)`.
- Comparator: the Stage A sampled, one-to-one posterior with 64 hypotheses on
  the identical candidate graph.

The evaluator rejects split drift, filters the locked sequence before either
posterior method is called, and asserts that the exact, sampled and generated
candidate-edge sets are identical for each scenario.

## Development result

The evaluator completed all 17 scenarios on sequence `01`. It recorded 13,361
exact connected components, 11,037 candidate-link marginals and 11,037 sampled
comparator probabilities. Every target-conservation and source-capacity
invariant passed. The largest component had two targets (within the frozen
limit of 18); its largest enumerated matching set had three members.

| Method | Calibration temperature | Calibrated Brier | Calibrated ECE | Calibrated NLL |
| --- | ---: | ---: | ---: | ---: |
| Exact context posterior | 0.55 | 0.06743 | 0.14010 | 0.21856 |
| Stage A sampled posterior | 0.55 | 0.06978 | 0.14254 | 0.22784 |

The exact posterior has lower development Brier, ECE and NLL in this comparison.
This is a development observation only, not a Stage B decision and not a
biological claim.

## Artifacts and boundary

[`stage-b-development-context-evaluation.json.gz`](stage-b-development-context-evaluation.json.gz)
contains the compressed full per-scenario exact component partitions, exact
link marginals, sampled comparator probabilities, calibration metrics and
provenance. The reproducibility workflow also publishes the uncompressed JSON
as a run artifact. Both contain only sequence `01`; the output contract
explicitly records `locked_test_sequence_evaluated: false`.

The calibration procedure is now implemented and fixed. The next step is a
single locked evaluation of sequence `02`, followed by the pre-registered
non-inferiority decision in the Stage B protocol.
