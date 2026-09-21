# Stage D v3 final report: calibrated Huh7 operator

Date: 2026-09-21. Final decision: **GO**.

## Result

Stage D is no longer blocked by the absence of an independent source. The
official CTC Huh7 archive passed a data-only audit and was split by sequence
before the revision fit. Sequence `01` was used for the bounded calibration;
sequence `02` was locked first and evaluated once afterward.

The selected candidate blends 10% of the U373-fitted stable Koopman prediction
with 90% of the U373-fitted weighted empirical prediction. On all 1481 locked
sequence-02 transitions it produced:

| Model | Velocity RMSE (px/frame) | Mean-speed absolute error (px/frame) | 90% coverage | Stable |
| --- | ---: | ---: | ---: | --- |
| Frozen HMM speed baseline | 6.748608824 | 3.059063510 | 0.966914247 | yes |
| Weighted empirical baseline | 5.436030433 | 0.055851444 | 0.972991222 | yes |
| Calibrated Koopman/empirical blend | **5.270002844** | 0.099033078 | 0.942606347 | yes |

All pre-registered gates passed:

- provenance and split integrity;
- leakage boundary;
- predictive improvement over both baselines;
- mean-speed non-inferiority within `0.10 px/frame` of the best baseline;
- 90% interval coverage inside the accepted `0.80–0.98` range;
- finite bounded ten-step rollouts;
- exact artifact reproducibility.

The machine-readable result is
[`stage-d-v3-huh7-sequence02-evaluation.json`](stage-d-v3-huh7-sequence02-evaluation.json).

## Interpretation boundary

The uncalibrated zero-shot Koopman result from Stage D v2 remains `HOLD`: it
improved RMSE but substantially underestimated mean speed. The v3 `GO` is a
narrower and honest result: one Huh7 sequence was sufficient to calibrate a
bounded blend that generalized to a separate locked Huh7 sequence. It does not
establish zero-shot cross-dataset generalization, glioblastoma biology,
brain-slice validity or clinical utility.
