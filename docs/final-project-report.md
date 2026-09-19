# Final project audit

Date: 2026-09-19. Status: **technical feasibility benchmark regenerated successfully after correctness hardening; HOLD before SLDS/Koopman.**

## What this repository demonstrates

This project measures how known tracking errors propagate into migration summaries and image-derived latent-state dynamics. It uses the public Cell Tracking Challenge PhC-C2DH-U373 dataset as a technical reference, not as a substitute for glioblastoma brain-slice ground truth.

The implemented pipeline contains:

- a frozen sequence-level expert reference benchmark;
- 17 deterministic corruption scenarios with held-out evaluation truth;
- a distance-only probabilistic tracker and constant-velocity/multi-feature proposal controls;
- soft posterior-weighted migration and two-state HMM summaries;
- gate-radius, morphology, and raw-image appearance sensitivity analyses;
- schema/provenance checks across stage artifacts;
- scenario-ID alignment rather than positional joining;
- a derived final machine-readable audit and automated unit-test CI.

## Correctness hardening and regeneration

A repository review found that the original `wrong_link` implementation reused the persistent `id_switch` branch before applying a local edit. The current implementation separates the semantics: `id_switch` is persistent after its boundary, while `wrong_link` swaps the paired labels only at one boundary frame. Regression tests cover this distinction.

The entire benchmark was then rerun from the current source against the official U373 training archive in GitHub Actions run `35439231472`, source commit `982c1c23619ce0955e1267dc8da36ab3280e5c3c`. Tests, dataset download, all numerical stages, final audit generation, and artifact upload completed successfully.

Reproduction provenance:

- U373 archive SHA-256: `b18185c18fce54e8eeb93e4bbb9b201d757add9409bbf2283b8114185a11bc9e`
- reference manifest semantic digest: `ce4d1dfc805eba0ab15b12de7e3ebef3eab2b23cf2f35ebed59d18a6cd1e0d47`
- corrected corruption artifact SHA-256: `dc39b52d7f7ced4ba8368af3b8366f66cba7b34bd039c408fde8a1e71ba53e1a`
- dynamics artifact SHA-256: `cbb360a680960d40778629a0ff2bb44d3cd739a19f205bdb69881a23c791d5c5`
- gate-sensitivity artifact SHA-256: `cb7809492cf8af19a88161f8e0af19f1a96ee098a74e2370cee65689feff7efc`
- Actions artifact SHA-256: `c30c04ebd4ac6e1414682ed4851845536126d59b9675514ef9ff61cd0be3e579`
- compact versioned result snapshot: `docs/reproduced-results-2026-09-19.json`

## Reproduced final gate

The final audit derives proposal readiness from explicit criteria:

- at least 95% clean true-link candidate coverage on every sequence; and
- no more than 1.0 px/frame deterioration in absolute held-out `localization_noise_5p0` soft-speed error relative to the smallest tested gate.

The reproduced gate sweep gives:

| Gate | Clean coverage 01 / 02 | σ=5 soft-speed delta 01 / 02 | Eligible for operator learning |
|---:|---:|---:|---|
| 8 px | 79.1% / 89.1% | +0.220 / +1.100 | No: coverage fails |
| 12 px | 91.7% / 95.0% | +2.137 / +3.073 | No: coverage and robustness fail |
| 16 px | 95.9% / 97.1% | +3.828 / +4.353 | No: robustness fails |

Therefore the regenerated final audit reports:

- `technical_benchmark_complete = true`
- `operator_learning_ready = false`
- `biological_validation_claim_supported = false`

The decision remains **REVISE** for uncertainty/downstream dynamics, **HOLD** for SLDS/Koopman, and **STOP** for any GlioTrace biological claim without an explicit biological reference.

## Corrected wrong-link result

The corrected local `wrong_link` semantics materially affect raw track-table dynamics. For example, `wrong_link_1` produces raw mean-speed deltas of `+0.548` px/frame on sequence 01 and `+2.176` px/frame on sequence 02; `wrong_link_2` produces `+2.025` and `+2.211` px/frame respectively. This is now separated from the persistent `id_switch` corruption rather than conflated with it.

## Reproduction and integrity

See [reproduction.md](reproduction.md) for the complete command sequence and the automated benchmark workflow. Raw archives remain excluded from Git. Bulk generated JSON remains a workflow artifact; the compact numerical snapshot and report-level numbers are versioned in the repository.

## Honest portfolio claim

This repository demonstrates reproducible data auditing, controlled-error design, uncertainty propagation, downstream sensitivity analysis, explicit artifact contracts, deterministic regeneration and scientific stopping criteria. It does not claim a validated invasion phenotype, clinical result, or reliable learned operator.

## Appropriate next research step

The correctness/regeneration task is complete. A future proposal model must improve candidate coverage without the observed held-out noise penalty, then pass calibration, corruption-robustness and stability gates before any SLDS or Koopman analysis is interpreted.
