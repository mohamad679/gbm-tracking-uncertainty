# Release notes — v1.0.0

Release date: 2026-09-22.

`v1.0.0` is the final technical project closure release for the GBM tracking
uncertainty audit.

## Highlights

- Closes the full A-E technical research line.
- Keeps the qualified Stage D v3 `GO`: calibrated Huh7 sequence-`01` blend
  generalizes to locked Huh7 sequence `02`.
- Publishes the Stage E-Final one-time locked `REVISE`: the run was valid, but
  calibrated error AUPRC did not beat the distance baseline on both real tests
  and uncertainty won only four of eight registered motion comparisons.
- Adds final closure documentation, release notes and project-level claim
  boundaries.
- Advances the Python package version to `1.0.0`.

## Evidence included in the release

- `docs/project-closure-report.md`
- `docs/final-project-report.md`
- `docs/stage-d-closure-report.md`
- `docs/stage-e-final-report.md`
- `docs/stage-e-sequence02-evaluation.json`
- `docs/stage-e-sequence02-evaluation-lock.json`
- `docs/reproduction.md`

## Supported claim

This release supports a reproducible technical audit claim: the repository
implements leakage-controlled cell-tracking uncertainty evaluation and documents
where uncertainty-aware methods pass, hold, or require revision under locked
technical benchmarks.

## Unsupported claims

This release does not support GBM biological validation, a migration phenotype,
perturbation effects, animal-level inference, patient-level inference, or
clinical utility.

## Validation

The release workflow validates the tagged commit by installing the pinned
environment, checking that `v1.0.0` matches `gbm_audit.__version__`, running the
unit/integration suite with the coverage gate, building a wheel, reinstalling
that wheel in a clean virtual environment, and creating a GitHub Release.
