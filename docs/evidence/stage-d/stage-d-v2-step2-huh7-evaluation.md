# Stage D v2 Step 2: locked Huh7 sequence-01 evaluation

Date: 2026-09-21. Status: **COMPLETE — HOLD**.

The frozen Stage D v2 evaluator ran exactly once on the previously locked
Huh7 sequence `01`. It evaluated all 883 structurally registered velocity
transitions. U373 sequence `02` and T98G were not used. No selection or tuning
was performed after the held-out result became visible.

| Model | Velocity RMSE (px/frame) | Mean-speed absolute error (px/frame) | 90% coverage | Stable |
| --- | ---: | ---: | ---: | --- |
| Frozen HMM speed baseline | 6.674608300 | 3.285798624 | 0.951302378 | yes |
| Weighted empirical baseline | 5.894248138 | 0.039145471 | 0.962627407 | yes |
| Stable linear Koopman | **4.604620330** | 1.346679053 | 0.961494904 | yes |

The Koopman candidate passed provenance, leakage, predictive improvement,
interval calibration, stability and reproducibility. It failed the frozen
state-summary non-inferiority gate: its mean-speed error was `1.346679053`,
while the permitted ceiling was `0.139145471` (`0.039145471 + 0.10`). The
candidate therefore remains `HOLD`; the lower RMSE is real but insufficient to
promote an operator that strongly shrinks mean migration speed.

The complete result is
[`stage-d-v2-huh7-locked-evaluation.json`](stage-d-v2-huh7-locked-evaluation.json).
Huh7 sequence `01` is now consumed and cannot serve as an independent test
again. Sequence `02` has not been evaluated and remains outcome-blind. A later
revision may use sequence `01` only as calibration/development data and must
lock sequence `02` before fitting. Such a result would establish
within-Huh7 post-calibration generalization, not zero-shot cross-dataset
generalization and not biological validation.
