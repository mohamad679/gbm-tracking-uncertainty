# Stage C v2 development fit and cross-validation

Date: 2026-09-20. Status: **DEVELOPMENT COMPLETE — VALUES FROZEN**.

This execution step fits the registered Stage C v2 values using only U373
sequence `01`. U373 sequence `02` remains the consumed v1 test and T98G remains
the locked-but-unevaluated independent test. No locked-test performance metric
was calculated.

## Reproduction inputs

- Official U373 training archive SHA-256:
  `b18185c18fce54e8eeb93e4bbb9b201d757add9409bbf2283b8114185a11bc9e`.
- Corruption benchmark seed: `20260919`.
- Seven registered corruption families and 17 sequence-`01` scenarios.
- Frozen Stage A configuration: `m2.75-d0-c4-n10-p0.7`.
- Predictive ensemble size: 256 members per scenario.
- Exact component resource limit: 18 target observations.

## Frozen localization fit

The fit uses 12,276 sequence-`01` observation/reference residual rows. The
truth-bearing coordinates are used only during this development calibration;
test-time sampler inputs remain reference-free.

| Parameter | Frozen value |
|---|---:|
| Intercept (px) | 0.0 |
| Median proposal-distance weight | 0.14713462466450963 |
| Candidate-degree weight | 0.0 |
| Training residual SSE | 26480.743294747055 |

Leave-one-family-out fits are retained in the machine-readable artifact, and
each held-out family contributes its out-of-fold mean-speed residuals to the
fixed split-conformal correction. The frozen 90% correction is
`1.3234006723487588` px/frame from 17 out-of-fold scenario residuals.

## Development result

All 17 sequence-`01` scenarios produced 256 defined predictive members. The
development artifact reports association-only, mechanistic predictive and
conformalized mean-speed intervals for every scenario. All truth-blind,
one-to-one, trajectory-partition, candidate-graph, bridge-virtual-node and
exact-resource invariants pass.

The complete compact artifact is
[`stage-c-v2-development-fit.json`](stage-c-v2-development-fit.json). It
contains fitted values, cross-validation summaries, scenario intervals,
configuration, seeds and provenance hashes; raw images and expanded ensemble
members are not committed.

## Boundary and next step

This is a technical U373 development result, not biological validation. The
next and final Stage C v2 execution step is the one-time registered T98G
evaluation. It may use only the frozen values in this artifact and must not
refit, tune, or inspect U373 sequence `02` performance.

