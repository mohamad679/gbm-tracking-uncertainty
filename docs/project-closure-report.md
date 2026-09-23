# Final project closure report

Date: 2026-09-22. Release target: **v1.0.0**.

Status: **closed as a reproducible technical/research-engineering project**.

## Final decision

The project is complete at the technical portfolio scope. It demonstrates a full, auditable pipeline for measuring how cell-tracking association uncertainty propagates into migration and latent-state summaries, with explicit leakage controls, locked evaluations, real-data reproduction workflows, and machine-readable evidence.

The final A-E scientific state is mixed and therefore credible:

| Stage | Decision | Meaning |
| --- | --- | --- |
| A | GO | Adaptive candidate recall passed the locked U373 gate. |
| B | GO | Exact graph-context posterior passed the locked U373 gate. |
| C v2 | GO | Revised uncertainty propagation passed the locked T98G gate. |
| D v3 | GO | Bounded Huh7 sequence-`01` calibration generalized to locked sequence `02`. |
| E-Final | REVISE | The one-time multi-domain locked run was valid, but AUPRC and motion-win GO gates failed. |

## Release scope

Release `v1.0.0` packages the final code, protocols, artifacts, reports and tests for the completed A-E technical project. It supersedes the Stage D `v0.2.0` state by adding the final Stage E locked evaluation and closure documentation.

Included release evidence is now indexed under [`README.md`](README.md), with the historical release artifacts preserved under `evidence/`:

- [`evidence/stage-d/stage-d-closure-report.md`](evidence/stage-d/stage-d-closure-report.md) for the qualified Stage D technical `GO`;
- [`evidence/stage-e/stage-e-final-report.md`](evidence/stage-e/stage-e-final-report.md) for the valid Stage E technical `REVISE`;
- [`evidence/stage-e/stage-e-sequence02-evaluation.json`](evidence/stage-e/stage-e-sequence02-evaluation.json) for the complete locked Stage E result artifact;
- [`final-project-report.md`](final-project-report.md) for the consolidated interpretation;
- [`reproduction.md`](reproduction.md) for local and GitHub Actions reproduction guidance;
- Python 3.11–3.13 tests, coverage gate, wheel build and release automation.

## Claim boundary

The repository supports a technical and methodological claim: known tracking errors and calibrated association uncertainty can be audited reproducibly, and their downstream effects can be measured under locked protocols.

The repository does not support:

- validated human GBM brain-slice tracking accuracy;
- animal-level or patient-level population inference;
- treatment or perturbation effects;
- calibration-free cross-domain generalization;
- clinical utility.

Stage F biological hypothesis testing and Stage G perturbation testing remain future studies requiring purpose-specific hypotheses, independent biological replicates and reference labels. They are not part of the v1.0.0 claim.

## Closure checklist

- Stage D historical `HOLD` artifacts and final v3 `GO` artifact are retained.
- Stage E development artifact, one-time execution lock, final artifact and final report are retained.
- README, roadmap, changelog, final report, reproduction guide and portfolio summary are aligned with the final A-E state.
- Package version is `1.0.0`.
- Final release notes are retained at [`evidence/release/release-notes-v1.0.0.md`](evidence/release/release-notes-v1.0.0.md).
- Raw third-party datasets remain excluded from source control.

No further Stage E model selection, threshold tuning or replacement evaluation belongs to the original project closure.

## Post-release evidence amendment — 2026-09-23

The original `v1.0.0` closure above remains historical and unchanged in meaning. A bounded post-release external glioma-context technical-transfer extension was subsequently completed without reopening or retuning Stage E.

The originally selected Dryad source (`doi:10.5061/dryad.s4d28`) was resumed locally after GitHub-hosted download authorization failures. The deposited source files were verified against the pre-frozen hashes, inspected schema-only, and mapped in a committed `LOCKED` schema before any Dryad method-performance outcome was calculated.

The final one-time evaluation used three independent rat PDGFB-glioma brain-slice experiments (100, 190 and 50 tumour tracks; biological `n=3`). It produced a deliberately mixed result:

- calibrated uncertainty improved association-error AUPRC over distance confidence in 3/3 experiments; mean effect `+0.596419`;
- selective-risk benefit was positive in 3/3 experiments; mean effect `+0.079359`;
- frozen uncertainty-compatible `p >= 0.5` tracking had lower link F1 than hard nearest-neighbour tracking in 3/3 experiments; mean effect `-0.012764`;
- mean-speed, path-length and net-displacement fidelity also favoured hard NN; directionality was mixed.

The completed Dryad arm therefore strengthens the project's confidence/audit-layer claim while explicitly rejecting a stronger hard-tracker superiority claim. The experiment remains the biological replicate, and `n=3` bootstrap intervals are descriptive/sensitivity evidence rather than precise population-level inference.

This post-release extension supports **external technical transfer in three rat glioma brain-slice experiments**. It does not support human GBM-wide validation, patient-level inference or clinical utility, and it does not change Stage E from `REVISE`.

Final extension evidence:

- [`evidence/dryad/dryad-confirmatory-schema-lock.json`](evidence/dryad/dryad-confirmatory-schema-lock.json);
- [`dryad-confirmatory-final-report.md`](dryad-confirmatory-final-report.md);
- [`evidence/dryad/dryad-confirmatory-result.json.gz`](evidence/dryad/dryad-confirmatory-result.json.gz);
- [`evidence/external/external-biological-context-final-report.md`](evidence/external/external-biological-context-final-report.md).

With this amendment, the planned post-closure external technical-transfer work is complete. Any future biological mechanism or perturbation study is a new project rather than unfinished work from this closure.
