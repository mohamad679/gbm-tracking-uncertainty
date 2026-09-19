# Final project audit

Date: 2026-09-19. Status: **technical feasibility package complete.**

## What this repository demonstrates

This project measures how known tracking errors propagate into migration summaries and image-derived latent-state dynamics. It uses the public Cell Tracking Challenge PhC-C2DH-U373 dataset as a technical reference, not as a substitute for glioblastoma brain-slice ground truth.

The completed pipeline contains:

- a frozen sequence-level expert reference benchmark;
- 17 deterministic corruptions with held-out evaluation truth;
- a distance-only probabilistic tracker and a constant-velocity proposal;
- soft posterior-weighted migration and two-state HMM summaries;
- gate-radius, morphology, and raw-image appearance sensitivity analyses;
- a final machine-readable audit and automated unit-test CI.

## Final gate status

| Gate | Status | Meaning |
|---|---|---|
| Reference and controlled corruptions | GO | The technical benchmark is deterministic and reproducible. |
| Uncertainty and downstream dynamics | REVISE | Candidate recall and proposal sensitivity materially affect conclusions. |
| SLDS / Koopman operator | HOLD | Learning an operator now would confound motion with proposal artifacts. |
| GlioTrace biological claim | STOP | U373 is 2D technical data and no brain-slice reference labels are available. |

The exact machine-readable decision is in `results/final-audit.json` after reproduction. It records `technical_benchmark_complete: true`, `operator_learning_ready: false`, and `biological_validation_claim_supported: false`.

## Reproduction and integrity

See [reproduction.md](reproduction.md) for the complete command sequence. Raw archives are excluded from Git; the benchmark manifest records the source archive hash and the final audit records hashes of all generated inputs. GitHub Actions runs the complete unit-test suite on pushes and pull requests.

## Honest portfolio claim

This repository demonstrates reproducible data auditing, controlled-error design, uncertainty propagation, downstream sensitivity analysis, and scientific stopping criteria. It does not claim a validated invasion phenotype, clinical result, or reliable learned operator.

## Appropriate next research step

If a future project adds a new proposal model, it must first pass held-out calibration, candidate-recall, corruption robustness, and stability gates before any SLDS or Koopman analysis is interpreted.
