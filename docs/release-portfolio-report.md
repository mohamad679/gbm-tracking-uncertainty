# Release and Portfolio Polish Report

Date: 2026-09-19

## Scope

This stage turns the hardened research repository into a release-ready, reviewer-friendly project without changing scientific algorithms or benchmark gates.

## Added

- `CHANGELOG.md` with the `0.1.0` release history.
- `CONTRIBUTING.md` with development, test, reproduction, and scientific-change requirements.
- `SECURITY.md` with vulnerability-reporting and scope guidance.
- `CODE_OF_CONDUCT.md` with project-specific conduct and scientific-integrity expectations.
- `docs/architecture.md` with a Mermaid architecture diagram, module boundaries, invariants, and safety/reproducibility layers.
- `docs/portfolio-summary.md` with a concise engineering/research project narrative.
- GitHub pull-request template.
- Structured bug-report and feature-request issue forms.
- `.github/workflows/release.yml` for validated tag-based releases.

## README

The project README was rewritten as a release/portfolio landing page. It now surfaces:

- CI and reproduction badges;
- version, Python support, test count, coverage, and decision-gate status;
- a concise architecture diagram;
- reproducible installation and validation commands;
- the full U373 workflow contract;
- module responsibilities;
- evidence/report navigation;
- explicit technical-versus-biological scope boundaries;
- the release process.

## Release automation

Tags matching `v*` trigger the release workflow. Before a GitHub Release is created, the workflow:

1. checks out the tagged commit;
2. installs the pinned Python 3.11 validation environment;
3. verifies that the tag version matches `gbm_audit.__version__`;
4. runs the unit/integration suite and the 65% coverage gate;
5. builds the wheel;
6. installs the built wheel in a clean virtual environment;
7. uploads the wheel as a workflow artifact;
8. creates a GitHub Release with generated notes and the validated wheel.

A manual workflow dispatch runs the validation/build path without creating a release because no tag is present.

## Release state

The repository is prepared as a `0.1.0` release candidate. At the time this report was written, the repository had no published GitHub Release. The available repository connector does not expose Git tag/release creation, so no tag or release was fabricated. Pushing the `v0.1.0` tag through a normal Git client will trigger the validated release automation.

## Scientific state carried into the release candidate

- 50/50 tests pass on supported Python versions 3.11, 3.12, and 3.13.
- Package coverage is 69% with a 65% enforced gate.
- Wheel build and reinstall smoke tests pass.
- Full pinned U373 reproduction succeeds.
- `technical_benchmark_complete = true`.
- `operator_learning_ready = false`.
- `biological_validation_claim_supported = false`.

This release polish does not alter those scientific results.
