# Stage D formal closure

Date: 2026-09-21. Decision: **CLOSED — qualified technical GO**.

## Closure basis

Stage D v1 stopped with `HOLD_NO_INDEPENDENT_EVALUATION_SOURCE`. Stage D v2
then introduced the independently audited CTC Huh7 source and produced an
honest zero-shot `HOLD`: velocity RMSE improved, but mean-speed non-inferiority
failed. Neither result is overwritten.

Stage D v3 used Huh7 sequence `01` only for a bounded blend calibration and
evaluated the frozen candidate once on previously locked sequence `02`. On
1481 transitions, the candidate achieved:

| Measure | Result | Gate |
| --- | ---: | --- |
| Velocity RMSE | 5.270002844 px/frame | Better than both frozen baselines |
| Best baseline RMSE | 5.436030433 px/frame | Comparator |
| Mean-speed absolute error | 0.099033078 px/frame | Non-inferior within 0.10 px/frame |
| 90% interval coverage | 0.942606347 | Inside 0.80-0.98 |
| Ten-step rollout | Finite and bounded | Pass |
| Artifact reproduction | Exact | Pass |

All seven registered gates passed: provenance/split integrity, leakage
boundary, predictive improvement, mean-speed non-inferiority, interval
coverage, rollout stability, and exact reproducibility.

## Final supported claim

The project supports a calibrated within-Huh7 sequence-generalization claim:
a blend calibrated on Huh7 sequence `01` generalized to locked sequence `02`.

It does not support calibration-free zero-shot transfer, brain-slice or
glioblastoma biological validity, a GBM-wide phenotype, or clinical utility.
Those claims require later real-GBM and biological validation stages.

## Repository closure checklist

- Stage D v1, v2, and v3 protocols and machine-readable evidence are retained.
- The v3 result is the current Stage D decision; earlier `HOLD` results remain
  historical evidence for their narrower protocols.
- README, roadmap, project report, portfolio summary, changelog, and package
  version are aligned with the current decision.
- Stage D implementation and artifact-contract tests remain in the standard
  test suite.
- Release `v0.2.0` represents the completed Stage A-D technical research line.
  Release `v1.0.0` supersedes it as the final A-E technical project closure.

No further model selection or evaluation belongs to Stage D. Subsequent work
starts at Stage E and requires real GBM reference evidence.
