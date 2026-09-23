# External biological-context validation — final report

Date: 2026-09-23

Status: **complete as a bounded external technical-transfer evidence package**. The project now contains two chronologically distinct external glioma-context evaluations:

1. an earlier `n=1` mouse glioma-explant fallback transfer evaluation using an independent TrackMate reference; and
2. the originally selected Dryad three-experiment rat glioma brain-slice arm, later resumed locally with hash-verified source files and completed under a pre-outcome schema lock.

Neither result changes the historical Stage E `REVISE` decision. Neither is human GBM-wide or clinical validation.

## 1. Historical fallback evaluation

The fallback source was the public `NPA_stich_3` TrackMate example from `smotsch/analysis_glioma`, fixed at commit `265285a03d87f3bf3275a0e78db1336570126bf4`. The biological context is a mouse NPA glioma explant-slice time-lapse model.

The reference is an **independent TrackMate trajectory set, not manual gold-standard tracking**. The source contained 3,759 trajectories, 173,456 observations, frames 0–292, a 598.54199 s frame interval and 168,116 consecutive reference links.

The frozen no-retuning configuration used a `1.5 µm/min` speed gate, 64 hypotheses, calibration temperature `0.25`, posterior threshold `0.5` and seed `20260922`.

This fallback result was mixed:

- association-error AUPRC: distance `0.925169`, frozen uncertainty `0.997292`;
- selective risk at 80% coverage: distance `0.000705`, frozen uncertainty `0.000000`;
- calibrated Brier/ECE/NLL: `0.004479 / 0.009541 / 0.017868` for frozen uncertainty;
- hard-NN link F1 `0.999598` versus uncertainty-compatible F1 `0.997198`;
- hard NN had lower error on all four registered motion summaries.

The fallback therefore supported transfer of the confidence/error-ranking layer, but not superiority of the p=0.5 hard reconstruction.

## 2. Why the original Dryad arm was resumed locally

The original source was Dryad `doi:10.5061/dryad.s4d28`, containing three independent rat PDGFB-driven glioma brain-slice experiments with manual frame-by-frame source trajectories. GitHub-hosted public file-download routes returned HTTP 403/401, so the repository froze a local-resumption protocol rather than changing scientific targets.

The deposited files were later acquired locally and verified against the already frozen identities:

- `To Generate Figures.zip` — MD5 `2b70accfbb4d81d41dfb10fcefa60cbf`;
- `README_for_To Generate Figures.docx` — MD5 `fcbd2b285b860eb18d7ce600becda06d`.

Before any Dryad performance outcome was computed, the archive was inspected schema-only and `docs/dryad-confirmatory-schema-lock.json` was committed as `LOCKED`. This froze the exact source members, `StoreData` column semantics, unit conversions, frame derivation and inclusion rules.

## 3. Dryad three-experiment source

The final tumour-cell reference contains:

| Experiment | Source | Tracks | Observations |
| --- | --- | ---: | ---: |
| 1 | `GFPOrlando.mat` / 5-16-11 | 100 | 7,399 |
| 2 | `6-6-11_Tumor_Tracking_Data.mat` | 190 | 19,189 |
| 3 | `3-14-11_Tumor_Tracking_Data.mat` | 50 | 2,499 |

Biological `n = 3`; the experiment is the biological replicate. Tracks/cells are nested observations.

The frozen evaluator retained the same `1.5 µm/min` speed gate, 64 hypotheses, proposal temperature rule, calibration temperature `0.25`, posterior threshold `0.5` and seed `20260922`. No Dryad-specific parameter fitting was performed.

## 4. Dryad association uncertainty result

The calibrated uncertainty score outperformed distance confidence for association-error ranking in all three experiments:

| Experiment | Distance AUPRC | Frozen uncertainty AUPRC | Difference |
| --- | ---: | ---: | ---: |
| 1 | 0.576155 | 0.976120 | +0.399965 |
| 2 | 0.040743 | 0.938978 | +0.898235 |
| 3 | 0.323096 | 0.814153 | +0.491056 |

Experiment-level mean uncertainty-minus-distance effect: `+0.596419`; descriptive bootstrap 95% CI `[0.391480, 0.890369]`; 3/3 experiments positive.

Selective-risk benefit was also positive in 3/3 experiments. Mean full-minus-selective risk benefit: `+0.079359`; descriptive bootstrap 95% CI `[0.005930, 0.127315]`.

Frozen calibration also transferred well, with calibrated Brier/ECE/NLL values:

- experiment 1: `0.020950 / 0.028968 / 0.067071`;
- experiment 2: `0.003302 / 0.011801 / 0.015685`;
- experiment 3: `0.068852 / 0.057364 / 0.202361`.

## 5. Dryad tracking and motion result

The frozen `p >= 0.5` uncertainty-compatible tracker did **not** outperform hard nearest-neighbour tracking.

| Experiment | Hard NN link F1 | Uncertainty-compatible link F1 | Difference |
| --- | ---: | ---: | ---: |
| 1 | 0.993889 | 0.981405 | -0.012484 |
| 2 | 0.987616 | 0.986670 | -0.000947 |
| 3 | 0.960131 | 0.935270 | -0.024861 |

Mean uncertainty-minus-hard link-F1 effect: `-0.012764`; descriptive bootstrap 95% CI `[-0.027504, -0.001036]`; all 3 experiments negative.

Mean-speed, path-length and net-displacement errors were also worse for the uncertainty-compatible reconstruction in all three experiments. Directionality was mixed: one experiment slightly favoured uncertainty and two favoured hard NN.

Candidate-graph reference-link coverage was approximately 99.6%, 97.6% and 99.7% across the three experiments. This is a limitation of the pre-frozen speed gate; the gate was not retuned after outcomes were observed.

## 6. Combined scientific interpretation

The fallback and Dryad results tell the same bounded technical story despite different species, reference mechanisms and sample sizes:

- calibrated uncertainty is useful for **association-error ranking, calibration and selective-risk review**;
- converting the frozen posterior to a hard tracker at `p >= 0.5` does not improve link F1 over the strong hard nearest-neighbour baseline;
- downstream migration fidelity is not improved by that frozen hard reconstruction.

The completed Dryad `n=3` arm is the stronger confirmatory external technical-transfer evidence because it uses three independent rat glioma brain-slice experiments and manual source trajectories. The earlier fallback remains historical evidence and is not erased or reinterpreted.

## 7. Claim boundary

Supported:

- no-retuning external technical transfer of calibrated association uncertainty to three independent rat glioma brain-slice experiments;
- consistency with the earlier `n=1` fallback for the uncertainty-ranking/selective-risk use case;
- explicit negative evidence against claiming superiority of the frozen p=0.5 hard reconstruction.

Not supported:

- human GBM-wide validation;
- patient-level generalization;
- clinical utility;
- validated biological cell-state discovery;
- precise population-level biological inference from `n=3`;
- retrospective conversion of Stage E `REVISE` to `GO`.

The detailed Dryad report is `dryad-confirmatory-final-report.md`. The frozen machine-readable Dryad output is `dryad-confirmatory-result.json.gz`; the historical fallback result remains `external-biological-context-result.json`.
