# Dryad three-experiment confirmatory technical-transfer report

Date: 2026-09-23

Status: **complete**. The originally selected Dryad three-experiment arm was resumed locally after the public GitHub-hosted download routes returned authorization errors. The deposited files were acquired locally, verified against the frozen hashes, inspected schema-only, mapped in a committed `LOCKED` schema, normalized, and then evaluated exactly once with the frozen method.

This report is a post-closure evidence extension. It does not change the historical Stage E `REVISE` decision.

## 1. Source and pre-outcome boundary

Source: Dryad `doi:10.5061/dryad.s4d28`, PDGFB-driven rat glioma, living acute brain slices at the infiltrative tumour margin. The reference trajectories are the source study's manual frame-by-frame cell tracks after deterministic schema conversion.

Biological unit: **experiment**. Biological `n = 3`.

The frozen source identities were:

- `To Generate Figures.zip` — MD5 `2b70accfbb4d81d41dfb10fcefa60cbf`;
- `README_for_To Generate Figures.docx` — MD5 `fcbd2b285b860eb18d7ce600becda06d`.

Before any Dryad method-performance outcome was computed, the repository froze the exact source members, schema mapping, unit conversions, inclusion rules and evaluator configuration in [`evidence/dryad/dryad-confirmatory-schema-lock.json`](evidence/dryad/dryad-confirmatory-schema-lock.json).

The three tumour-cell experiments are:

1. `GFPOrlando.mat` / 5-16-11 — 100 tracks, 7,399 observations;
2. `6-6-11_Tumor_Tracking_Data.mat` — 190 tracks, 19,189 observations;
3. `3-14-11_Tumor_Tracking_Data.mat` — 50 tracks, 2,499 observations.

No observations were excluded by a post-outcome cell-type or performance rule.

## 2. Frozen configuration

No Dryad-specific parameter fitting or retuning was performed.

- maximum speed gate: `1.5 µm/min`;
- association hypotheses: `64`;
- proposal temperature: pairwise maximum link distance / 2;
- calibration temperature: `0.25`;
- posterior-compatible tracking threshold: `0.5`;
- random seed: `20260922`.

## 3. Candidate-graph coverage

The pre-frozen speed gate retained most, but not all, reference links:

| Experiment | Reference-link coverage |
| --- | ---: |
| 1 | 0.995753 |
| 2 | 0.976367 |
| 3 | 0.997142 |

This is a registered limitation. The speed gate was **not** changed after outcomes were observed.

## 4. Association uncertainty and selective risk

The calibrated uncertainty score transferred strongly as an association-error ranking signal in all three experiments.

| Experiment | Distance AUPRC | Calibrated uncertainty AUPRC | Difference |
| --- | ---: | ---: | ---: |
| 1 | 0.576155 | 0.976120 | +0.399965 |
| 2 | 0.040743 | 0.938978 | +0.898235 |
| 3 | 0.323096 | 0.814153 | +0.491056 |

At the experiment level, uncertainty-minus-distance AUPRC was positive in 3/3 experiments. Mean effect: `+0.596419`; descriptive bootstrap 95% CI of the mean: `[0.391480, 0.890369]`.

Selective-risk benefit was also positive in 3/3 experiments. The full-coverage minus 80%-coverage risk effects were `+0.108330`, `+0.005042`, and `+0.124705`. Mean effect: `+0.079359`; descriptive bootstrap 95% CI: `[0.005930, 0.127315]`.

Frozen calibration remained useful. Calibrated uncertainty Brier/ECE/NLL values were:

- experiment 1: `0.020950 / 0.028968 / 0.067071`;
- experiment 2: `0.003302 / 0.011801 / 0.015685`;
- experiment 3: `0.068852 / 0.057364 / 0.202361`.

## 5. Hard tracking reconstruction

The same result does **not** show superiority of the frozen posterior-threshold tracker over hard nearest-neighbour tracking.

| Experiment | Hard NN link F1 | Uncertainty-compatible p≥0.5 link F1 | Difference |
| --- | ---: | ---: | ---: |
| 1 | 0.993889 | 0.981405 | -0.012484 |
| 2 | 0.987616 | 0.986670 | -0.000947 |
| 3 | 0.960131 | 0.935270 | -0.024861 |

The uncertainty-minus-hard link-F1 effect was negative in 3/3 experiments. Mean effect: `-0.012764`; descriptive bootstrap 95% CI of the mean: `[-0.027504, -0.001036]`.

The key technical distinction is therefore preserved: uncertainty is valuable as a calibrated confidence/error-ranking layer, but the frozen `p >= 0.5` conversion is not a better hard tracker in this external source.

## 6. Downstream motion fidelity

The uncertainty-compatible reconstruction also did not improve the main downstream migration errors.

Experiment-level hard-minus-uncertainty error-benefit effects:

| Endpoint | Exp 1 | Exp 2 | Exp 3 | Mean |
| --- | ---: | ---: | ---: | ---: |
| Mean-speed error | -0.005217 | -0.001551 | -0.004645 | -0.003804 |
| Path-length relative error | -0.383046 | -0.015890 | -0.558676 | -0.319204 |
| Net-displacement relative error | -0.349934 | -0.015560 | -0.567929 | -0.311141 |
| Directionality error | -0.103354 | +0.002035 | -0.133645 | -0.078321 |

Negative values mean the hard nearest-neighbour reconstruction had the lower error. Mean-speed, path-length and net-displacement results were negative in all three experiments; directionality was mixed.

## 7. Replicate-aware interpretation

The experiment is the biological replicate; cells and tracks are nested observations. The final biological sample size is `n = 3`.

The experiment-level and hierarchical/bootstrap intervals are therefore **descriptive/sensitivity evidence**, not precise population-level inference. The result supports consistency of technical transfer across these three experiments, not a broad biological population claim.

## 8. Scientific conclusion

The final Dryad result is deliberately mixed:

> The frozen uncertainty model transfers strongly as an association-error ranking, calibration and selective-risk mechanism across three independent rat glioma brain-slice experiments, but the frozen `p >= 0.5` uncertainty-compatible tracking rule does not outperform hard nearest-neighbour tracking in link F1 or downstream motion fidelity.

This strengthens the project's audit-oriented uncertainty claim while rejecting a stronger hard-tracker superiority claim.

## 9. Claim boundary

Supported:

- confirmatory external **technical transfer** in three independent rat glioma brain-slice experiments;
- strong no-retuning association-error ranking by frozen uncertainty;
- useful frozen calibration and selective-risk filtering;
- a negative result for the frozen p≥0.5 hard reconstruction relative to hard nearest-neighbour tracking.

Not supported:

- human GBM-wide validation;
- patient-level generalization;
- clinical utility;
- validated biological cell-state discovery;
- precise population-level biological inference from `n = 3`;
- retrospective conversion of Stage E from `REVISE` to `GO`.

## 10. Reproducibility artifacts

- protocol: [`evidence/dryad/dryad-confirmatory-local-resumption-protocol.json`](evidence/dryad/dryad-confirmatory-local-resumption-protocol.json);
- schema lock: [`evidence/dryad/dryad-confirmatory-schema-lock.json`](evidence/dryad/dryad-confirmatory-schema-lock.json);
- local runbook: [`evidence/dryad/dryad-confirmatory-local-runbook.md`](evidence/dryad/dryad-confirmatory-local-runbook.md);
- evaluator: `src/gbm_audit/dryad_confirmatory.py`;
- frozen machine-readable result: [`evidence/dryad/dryad-confirmatory-result.json.gz`](evidence/dryad/dryad-confirmatory-result.json.gz).

The gzip artifact is a deterministic gzip (`gzip -n`) of the one-time local `confirmatory-result.json`. Its SHA-256 is `371e67c0ec026f4ea0ffa9e89748b9c55bcc612a3cee2ef7df9c0363261b1e31`; the uncompressed JSON SHA-256 is `7eb61dc829ad0eb7076dd46801d8e2f2a4863f6369494115ef0353be6ec6139f`.
