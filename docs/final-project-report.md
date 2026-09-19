# Final project audit

Date: 2026-09-19. Status: **technical feasibility source package hardened; derived Stage 2+ artifacts must be regenerated with the current source.**

## What this repository demonstrates

This project measures how known tracking errors propagate into migration summaries and image-derived latent-state dynamics. It uses the public Cell Tracking Challenge PhC-C2DH-U373 dataset as a technical reference, not as a substitute for glioblastoma brain-slice ground truth.

The implemented pipeline contains:

- a frozen sequence-level expert reference benchmark;
- 17 deterministic corruption scenarios with held-out evaluation truth;
- a distance-only probabilistic tracker and a constant-velocity proposal;
- soft posterior-weighted migration and two-state HMM summaries;
- gate-radius, morphology, and raw-image appearance sensitivity analyses;
- schema/provenance checks across stage artifacts;
- scenario-ID alignment rather than positional joining;
- a derived final machine-readable audit and automated unit-test CI.

## Correctness hardening

A repository review found that the original `wrong_link` implementation reused the persistent `id_switch` branch before applying a local edit. The current implementation separates the semantics: `id_switch` is persistent after its boundary, while `wrong_link` swaps the paired labels only at one boundary frame. Regression tests cover this distinction.

Because generated files under `results/` are intentionally ignored, the repository does not pretend that the old numeric outputs were regenerated automatically. Stage 2 and every downstream Stage 3+ artifact should be reproduced with the current source before numeric tables from the earlier reports are treated as current.

The pipeline now also rejects stale or mismatched stage artifacts by validating schema version, reference-manifest hash, corruption seed, scenario identity/metadata and sequence IDs before combining outputs. Reordering scenario arrays is safe because downstream joins are keyed by `scenario_id`.

## Final gate policy

The final audit no longer receives a manually entered test count and no longer hard-codes operator readiness. Test status belongs to CI. The machine-readable audit derives proposal readiness from explicit gate criteria:

- at least 95% clean true-link candidate coverage on every sequence; and
- no more than 1.0 px/frame deterioration in absolute held-out `localization_noise_5p0` soft-speed error relative to the smallest tested gate.

Biological validation remains unsupported unless the reference manifest explicitly declares an appropriate biological validation reference.

## Reproduction and integrity

See [reproduction.md](reproduction.md) for the complete command sequence. Raw archives are excluded from Git; the benchmark manifest records the source archive hash and the final audit records hashes of all generated inputs. GitHub Actions runs the unit-test suite on pushes and pull requests.

## Honest portfolio claim

This repository demonstrates reproducible data auditing, controlled-error design, uncertainty propagation, downstream sensitivity analysis, explicit artifact contracts, and scientific stopping criteria. It does not claim a validated invasion phenotype, clinical result, or reliable learned operator.

## Appropriate next research step

First regenerate Stage 2 and all downstream artifacts with the corrected corruption semantics. If a future project adds a new proposal model, it must then pass held-out calibration, candidate-recall, corruption-robustness, and stability gates before any SLDS or Koopman analysis is interpreted.
