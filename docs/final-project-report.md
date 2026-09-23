# Consolidated technical project report

Original closure date: 2026-09-22. Post-release evidence update: 2026-09-23.

Status: **Project closed at v1.0.0 as a reproducible technical/research-engineering artifact. Stage E-Final remains a valid technical `REVISE`. A bounded post-closure Dryad external technical-transfer extension is complete. Human GBM-wide biological or clinical validation is not supported.**

## What the repository demonstrates

The repository provides a reproducible audit of how known tracking errors and association uncertainty propagate into migration summaries and latent-state dynamics. Public expert annotations are technical references; they are not a substitute for human glioblastoma brain-slice ground truth.

The completed technical line contains:

- deterministic U373 reference data and 17 known-truth corruption scenarios;
- a truth-blind adaptive candidate model evaluated on locked U373 data;
- exact graph-context marginalized link posteriors;
- uncertainty-aware trajectory ensembles and downstream dynamics;
- locked independent T98G validation for Stage C v2;
- a stable operator extension audited on independent CTC Huh7 data;
- schema, provenance, leakage, stability and reproducibility checks;
- automated tests, package builds and real-data GitHub Actions workflows;
- final multi-domain Stage E validation on locked GOWT1 and HeLa sequence `02` data, with SIM+ as a diagnostic-only exact-truth source;
- a post-closure external technical-transfer evaluation in three independent rat PDGFB-glioma brain-slice experiments under a pre-outcome schema lock and frozen method.

## Stage decisions

| Research stage | Final decision | Supported result |
| --- | --- | --- |
| A | GO | Adaptive candidate-recall gate passed on locked U373 evaluation |
| B | GO | Exact graph-context posterior passed its locked U373 evaluation |
| C v2 | GO | Revised uncertainty propagation passed the locked T98G gate |
| D v1 | HOLD | No eligible independent operator-evaluation source |
| D v2 | HOLD | Zero-shot Huh7 RMSE improved, but mean-speed bias failed the gate |
| D v3 | GO | Calibrated Huh7 sequence `01` to locked sequence `02` generalization |
| E-Final | REVISE | Valid locked multi-domain run; calibration/selective risk passed, AUPRC and motion-win gates failed |

Stage D v3 evaluated 1481 locked sequence-`02` transitions. The calibrated blend achieved velocity RMSE 5.270002844 px/frame versus 5.436030433 for the best frozen baseline, mean-speed absolute error 0.099033078 px/frame, 90% interval coverage 0.942606347, finite bounded ten-step rollouts and exact artifact reproduction. All seven pre-registered gates passed.

## Stage E closure

Stage E-Final is closed: the pre-registered one-time sequence-`02` evaluation returned `REVISE`. The run was valid and leakage-controlled, but calibrated association-error AUPRC did not beat the distance baseline on both real tests, and uncertainty won only four of eight registered motion comparisons.

This decision is immutable. The later external-context work does not retune Stage E, replace its datasets, or convert `REVISE` to `GO`.

The final Stage E artifact and report are [`stage-e-sequence02-evaluation.json`](stage-e-sequence02-evaluation.json) and [`evidence/stage-e/stage-e-final-report.md`](evidence/stage-e/stage-e-final-report.md).

## Post-closure Dryad external technical transfer

After the v1.0.0 closure, the originally selected Dryad source (`doi:10.5061/dryad.s4d28`) was resumed locally because GitHub-hosted download routes had returned authorization errors. The deposited source hashes were verified, archive/schema/documentation evidence was inspected without outcome calculation, and the exact three-experiment tumour-cell mapping was committed as `LOCKED` before normalization and evaluation.

The final biological unit is the experiment, with three independent rat glioma brain-slice experiments:

- experiment 1: 100 tracks, 7,399 observations;
- experiment 2: 190 tracks, 19,189 observations;
- experiment 3: 50 tracks, 2,499 observations.

The same frozen configuration was applied without Dryad-specific parameter fitting: max speed `1.5 µm/min`, 64 hypotheses, pairwise proposal temperature rule, calibration temperature `0.25`, posterior threshold `0.5`, seed `20260922`.

The result is mixed and scientifically useful:

- association-error AUPRC uncertainty-minus-distance was positive in 3/3 experiments; mean effect `+0.596419`, descriptive bootstrap 95% CI `[0.391480, 0.890369]`;
- selective-risk benefit was positive in 3/3 experiments; mean effect `+0.079359`, descriptive bootstrap 95% CI `[0.005930, 0.127315]`;
- frozen uncertainty-compatible `p >= 0.5` link-F1 effect versus hard nearest-neighbour tracking was negative in 3/3 experiments; mean `-0.012764`, descriptive bootstrap 95% CI `[-0.027504, -0.001036]`;
- mean-speed, path-length and net-displacement fidelity also favoured hard NN; directionality was mixed.

Candidate-graph reference-link coverage was about 99.6%, 97.6% and 99.7%. The pre-frozen `1.5 µm/min` gate was not changed after outcomes were observed.

The supported conclusion is therefore narrow and explicit: frozen calibrated uncertainty transfers strongly as an association-error ranking, calibration and selective-risk mechanism in these three external rat glioma brain-slice experiments, but the frozen posterior-to-hard-track rule does not outperform the hard nearest-neighbour baseline.

See [`dryad-confirmatory-final-report.md`](dryad-confirmatory-final-report.md) and [`evidence/dryad/dryad-confirmatory-result.json.gz`](evidence/dryad/dryad-confirmatory-result.json.gz).

## Interpretation boundary

The current evidence supports technical/methodological claims about reproducible uncertainty auditing, locked validation, selective review and bounded external transfer.

The repository does **not** establish:

- human GBM-wide validation;
- patient-level generalization;
- clinical utility;
- a validated glioblastoma migration phenotype or cell state;
- precise population-level biological inference from the Dryad `n=3`;
- calibration-free cross-dataset generalization;
- superiority of the frozen uncertainty-compatible hard tracker.

The legacy U373 audit field `operator_learning_ready = false` remains correct for that original gate and artifact; Stage D v3 is a later, separate registered evaluation and does not retroactively alter historical evidence.

## Reproducibility state

- Python 3.11-3.13 CI and the package coverage gate are enforced.
- Huh7 audit, zero-shot evaluation, calibration and locked v3 evaluation have machine-readable artifacts and dedicated reproduction workflows.
- Stage E development/final artifact validation has dedicated regression tests and workflow coverage.
- The Dryad local pipeline verifies frozen hashes, inspects schema before outcomes, normalizes from a committed lock, and records a frozen one-time result.
- Raw third-party datasets are not redistributed.

The formal Stage D closure record is [`evidence/stage-d/stage-d-closure-report.md`](evidence/stage-d/stage-d-closure-report.md). The original final closure record and release notes are [`project-closure-report.md`](project-closure-report.md) and [`release-notes-v1.0.0.md`](release-notes-v1.0.0.md). The combined external-context chronology is [`evidence/external-context/external-biological-context-final-report.md`](evidence/external-context/external-biological-context-final-report.md).
