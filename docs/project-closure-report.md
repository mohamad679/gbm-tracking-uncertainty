# Final project closure report

Date: 2026-09-22. Release target: **v1.0.0**.

Status: **closed as a reproducible technical/research-engineering project**.

## Final decision

The project is complete at the technical portfolio scope. It demonstrates a
full, auditable pipeline for measuring how cell-tracking association uncertainty
propagates into migration and latent-state summaries, with explicit leakage
controls, locked evaluations, real-data reproduction workflows, and
machine-readable evidence.

The final scientific state is mixed and therefore credible:

| Stage | Decision | Meaning |
| --- | --- | --- |
| A | GO | Adaptive candidate recall passed the locked U373 gate. |
| B | GO | Exact graph-context posterior passed the locked U373 gate. |
| C v2 | GO | Revised uncertainty propagation passed the locked T98G gate. |
| D v3 | GO | Bounded Huh7 sequence-`01` calibration generalized to locked sequence `02`. |
| E-Final | REVISE | The one-time multi-domain locked run was valid, but AUPRC and motion-win GO gates failed. |

## Release scope

Release `v1.0.0` packages the final code, protocols, artifacts, reports and
tests for the completed A-E technical project. It supersedes the Stage D
`v0.2.0` state by adding the final Stage E locked evaluation and closure
documentation.

Included evidence:

- `docs/stage-d-closure-report.md` for the qualified Stage D technical `GO`;
- `docs/stage-e-final-report.md` for the valid Stage E technical `REVISE`;
- `docs/stage-e-sequence02-evaluation.json` for the complete locked Stage E
  result artifact;
- `docs/final-project-report.md` for the consolidated interpretation;
- `docs/reproduction.md` for local and GitHub Actions reproduction guidance;
- Python 3.11-3.13 tests, coverage gate, wheel build, and release automation.

## Claim boundary

The repository supports a technical and methodological claim: known tracking
errors and calibrated association uncertainty can be audited reproducibly, and
their downstream effects can be measured under locked protocols.

The repository does not support:

- validated GBM brain-slice tracking accuracy;
- animal-level or patient-level biological inference;
- treatment or perturbation effects;
- calibration-free cross-domain generalization;
- clinical utility.

Stage F biological hypothesis testing and Stage G perturbation testing remain
future studies requiring independent biological replicates and reference labels.
They are not part of the v1.0.0 claim.

## Closure checklist

- Stage D historical `HOLD` artifacts and final v3 `GO` artifact are retained.
- Stage E development artifact, one-time execution lock, final artifact and
  final report are retained.
- README, roadmap, changelog, final report, reproduction guide and portfolio
  summary are aligned with the final A-E state.
- Package version is `1.0.0`.
- Final release notes are recorded in `docs/release-notes-v1.0.0.md`.
- Raw third-party datasets remain excluded from source control.

No further model selection, threshold tuning or replacement evaluation belongs
to this project closure. Any later biological claim must start as a new
pre-registered study.
