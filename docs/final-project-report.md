# Consolidated technical project report

Date: 2026-09-22. Status: **Stages A-E complete; Stage E-Final closed with a
valid technical REVISE. Biological validation is not supported.**

## What the repository demonstrates

The repository provides a reproducible audit of how known tracking errors and
association uncertainty propagate into migration summaries and latent-state
dynamics. Public expert annotations are technical references; they are not a
substitute for glioblastoma brain-slice ground truth.

The completed technical line contains:

- deterministic U373 reference data and 17 known-truth corruption scenarios;
- a truth-blind adaptive candidate model evaluated on locked U373 data;
- exact graph-context marginalized link posteriors;
- uncertainty-aware trajectory ensembles and downstream dynamics;
- locked independent T98G validation for Stage C v2;
- a stable operator extension audited on independent CTC Huh7 data;
- schema, provenance, leakage, stability, and reproducibility checks;
- automated tests, package builds, and real-data GitHub Actions workflows.
- final multi-domain Stage E validation on locked GOWT1 and HeLa sequence `02`
  data, with SIM+ as a diagnostic-only exact-truth source.

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

Stage D v3 evaluated 1481 locked sequence-`02` transitions. The calibrated
blend achieved velocity RMSE 5.270002844 px/frame versus 5.436030433 for the
best frozen baseline, mean-speed absolute error 0.099033078 px/frame, 90%
interval coverage 0.942606347, finite bounded ten-step rollouts, and exact
artifact reproduction. All seven pre-registered gates passed.

## Interpretation boundary

The current evidence supports the technical statement that bounded calibration
on one Huh7 sequence produced a stable improvement on a separately locked Huh7
sequence. The Stage D v2 zero-shot result remains `HOLD` and is not converted
into a positive claim by the v3 result.

The repository does not establish calibration-free cross-dataset transfer,
brain-slice tracking accuracy, a glioblastoma migration phenotype, GBM-wide
generalization, or clinical utility. The legacy U373 audit field
`operator_learning_ready = false` remains correct for that original gate and
artifact; Stage D v3 is a later, separate registered evaluation and does not
retroactively alter historical evidence.

## Reproducibility state

- 133 tests pass in the Stage D closure suite.
- Python 3.11-3.13 CI and a 65% package-coverage gate are enforced.
- Huh7 audit, zero-shot evaluation, calibration, and locked v3 evaluation each
  have machine-readable artifacts and dedicated reproduction workflows.
- Raw third-party datasets are not redistributed.

The formal Stage D closure record is
[`stage-d-closure-report.md`](stage-d-closure-report.md). Stage E-Final is also
closed: the pre-registered one-time sequence-`02` evaluation returned `REVISE`.
The run was valid and leakage-controlled, but calibrated association-error
AUPRC did not beat the distance baseline on both real tests, and uncertainty
won only four of eight registered motion comparisons. The final artifact and
report are [`stage-e-sequence02-evaluation.json`](stage-e-sequence02-evaluation.json)
and [`stage-e-final-report.md`](stage-e-final-report.md).
