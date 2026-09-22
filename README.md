# Glioblastoma Tracking Uncertainty Audit

[![Tests](https://github.com/mohamad679/gbm-tracking-uncertainty/actions/workflows/tests.yml/badge.svg)](https://github.com/mohamad679/gbm-tracking-uncertainty/actions/workflows/tests.yml)
[![Reproduce benchmark](https://github.com/mohamad679/gbm-tracking-uncertainty/actions/workflows/reproduce-benchmark.yml/badge.svg)](https://github.com/mohamad679/gbm-tracking-uncertainty/actions/workflows/reproduce-benchmark.yml)
[![Release](https://github.com/mohamad679/gbm-tracking-uncertainty/actions/workflows/release.yml/badge.svg)](https://github.com/mohamad679/gbm-tracking-uncertainty/actions/workflows/release.yml)

A reproducible technical audit of how tracking errors and association uncertainty propagate into migration and latent-state estimates for cell-tracking pipelines.

The quantitative benchmark uses expert annotations from the Cell Tracking Challenge PhC-C2DH-U373 dataset. GlioTrace brain-slice data are retained as an exploratory application only. **This repository does not make a validated biological or clinical claim.**

## Current status

**Version:** `0.2.0`
**Python:** 3.11-3.13  
**License:** MIT  
**Tests:** 144 tests; CI enforced on all supported Python versions
**Coverage:** 71% package coverage, 65% enforced CI gate
**Technical benchmark:** complete  
**Operator learning:** Stage D v3 GO — calibrated blend passed locked Huh7 sequence `02`
**Research Stage D:** formally closed on 2026-09-21
**Research Stage E-Final:** locked evaluator and one-time execution lock prepared; sequence `02` remains unevaluated pending CI
**Biological validation claim:** not supported

The operator-learning decision is evidence-derived. The zero-shot Huh7
candidate remained HOLD because of mean-speed bias. A bounded blend calibrated
on Huh7 sequence `01` subsequently passed every pre-registered gate on locked
sequence `02`. This supports within-Huh7 sequence generalization after
calibration, not zero-shot or biological generalization.

## What this project demonstrates

- deterministic benchmark construction from expert tracking masks and lineages;
- 17 seeded known-truth corruption scenarios;
- baseline and uncertainty-aware association evaluation;
- calibrated link probabilities with development/test separation;
- hard and soft downstream dynamics sensitivity analysis;
- artifact schema/provenance validation across pipeline stages;
- reproducible, pinned environments and real-data GitHub Actions runs;
- regression testing for scientific-correctness bugs;
- archive safety limits for external ZIP inputs;
- performance refactoring with output-equivalence tests;
- explicit separation between technical evidence and biological interpretation.

## Architecture

```mermaid
flowchart TD
    A[U373 reference and corruptions] --> B[Stage A: adaptive candidates]
    B --> C[Stage B: graph-context posterior]
    C --> D[Stage C: uncertainty-aware dynamics]
    D --> E[T98G locked validation]
    E --> F[Stage D: operator extension]
    F --> G[Huh7 sequence 01 calibration]
    G --> H[Huh7 sequence 02 locked GO]
    H --> I[Stage E: multidomain protocol and split lock]
    I --> J[Sequence 01 development-only fit]
```

See [`docs/architecture.md`](docs/architecture.md) for the full module-level architecture, invariants, safety layer, and reproducibility boundaries.

## Reproducible installation

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt -e .
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -c constraints.txt -e .
```

The validated exact dependency environment is recorded in `constraints.txt`. Runtime provenance in the final audit records package version, Python version, dependency versions, and Git commit SHA.

## Validate the package

```bash
python -m pip install -c constraints.txt -e . coverage
coverage run --source=gbm_audit -m unittest discover -s tests -q
coverage report --show-missing --fail-under=65
```

GitHub Actions additionally builds and reinstalls the wheel as a packaging smoke test on every relevant push.

## Reproduce the U373 benchmark

The full pinned benchmark is automated by `.github/workflows/reproduce-benchmark.yml`. The workflow:

1. installs the pinned environment;
2. runs the tests;
3. downloads the official U373 training archive;
4. builds the reference manifest;
5. generates all corruption scenarios;
6. evaluates baseline and uncertainty stages;
7. evaluates hard/soft dynamics and gate sensitivity;
8. creates the final audit;
9. uploads the numeric results as a GitHub Actions artifact.

The latest frozen result summary is in [`docs/reproduced-results-2026-09-19.json`](docs/reproduced-results-2026-09-19.json).

## Pipeline modules

| Module | Responsibility |
|---|---|
| `benchmark.py` | Build deterministic U373 reference manifest |
| `t98g_audit.py` | Lock T98G provenance, archive identity and reference structure without performance evaluation |
| `stage_d_huh7_audit.py` | Audit and lock independent Huh7 sequences without exposing outcomes |
| `stage_d_huh7_evaluation.py` | Reproduce the frozen zero-shot Huh7 evaluation |
| `stage_d_v3_development.py` | Fit the bounded Huh7 sequence-01 blend calibration |
| `stage_d_v3_evaluation.py` | Evaluate the frozen blend on locked Huh7 sequence `02` |
| `stage_e_data.py` | Verify CTC archives and decode only registered development sequence `01` |
| `stage_e_metrics.py` | Dependency-free AUPRC, selective-risk and calibration metrics |
| `stage_e_development.py` | Reproduce the Stage E sequence-`01` fit while preserving the `02` lock |
| `stage_e_evaluation.py` | Execute exactly one frozen Stage E sequence-`02` evaluation after CI approval |
| `corruptions.py` | Generate 17 seeded known-truth scenarios |
| `baseline.py` | Frozen greedy nearest-neighbour comparator |
| `uncertainty.py` | Sample one-to-one association hypotheses and calibrate probabilities |
| `adaptive_candidates.py` | Build deterministic, truth-blind adaptive candidate graphs |
| `dynamics.py` | Hard migration and two-state HMM sensitivity |
| `soft_dynamics.py` | Probability-weighted migration and transition summaries |
| `gate_sensitivity.py` | Proposal-radius robustness sweep |
| `final_audit.py` | Evidence-derived project decision gates |
| `validation.py` | Cross-stage artifact contracts and provenance checks |
| `archive.py` | External ZIP safety limits and bounded reads |
| `config.py` | Shared benchmark defaults |
| `calibration.py`, `numerics.py` | Shared mathematical utilities |

## Exploratory GlioTrace pilot

The project also retains a small qualitative GlioTrace workflow for visual inspection. It is intentionally separate from the quantitative U373 benchmark.

```bash
python scripts/fetch_pilot_rois.py
python -m gbm_audit.roi data/raw/glio_trace/Set_67/exp_333_roi_84_stack.npz --output results/set67-roi.json
python -m gbm_audit.roi data/raw/glio_trace/Set_68/exp_337_roi_63_stack.npz --expected-frames 68 --output results/set68-roi.json
```

Raw data and generated `results/` outputs are not source-controlled.

## Evidence and reports

- [`docs/final-project-report.md`](docs/final-project-report.md) — overall technical conclusions
- [`docs/reproduction.md`](docs/reproduction.md) — detailed reproduction guide
- [`docs/architecture-performance-report.md`](docs/architecture-performance-report.md) — Stage 3 hardening/refactor evidence
- [`docs/reproducibility-packaging-report.md`](docs/reproducibility-packaging-report.md) — packaging/reproducibility evidence
- [`docs/engineering-hardening-report.md`](docs/engineering-hardening-report.md) — correctness/testing evidence
- [`docs/reproduced-results-2026-09-19.json`](docs/reproduced-results-2026-09-19.json) — frozen machine-readable result snapshot
- [`docs/stage-a-protocol.md`](docs/stage-a-protocol.md) — frozen adaptive-candidate benchmark contract
- [`docs/stage-a-step2-adaptive-generator.md`](docs/stage-a-step2-adaptive-generator.md) — adaptive v1 engineering design and scope
- [`docs/stage-a-step3-integration.md`](docs/stage-a-step3-integration.md) — candidate/posterior/downstream graph invariant
- [`docs/stage-c-v2-step2-t98g-audit.md`](docs/stage-c-v2-step2-t98g-audit.md) — independent T98G data-only audit and lock decision
- [`docs/stage-d-v3-final-report.md`](docs/stage-d-v3-final-report.md) — final calibrated Huh7 operator decision
- [`docs/stage-d-closure-report.md`](docs/stage-d-closure-report.md) — formal Stage D closure and claim boundary
- [`docs/stage-e-protocol.md`](docs/stage-e-protocol.md) — frozen final-stage question, endpoints, gates, and claim boundary
- [`docs/stage-e-dataset-manifest.json`](docs/stage-e-dataset-manifest.json) — verified GOWT1, HeLa, and SIM+ archive identities and structures
- [`docs/stage-e-split-lock.json`](docs/stage-e-split-lock.json) — immutable sequence-01 development and sequence-02 test assignment
- [`docs/stage-e-steps1-3-report.md`](docs/stage-e-steps1-3-report.md) — completion evidence for Stage E Steps 1-3
- [`docs/stage-e-step4-development.md`](docs/stage-e-step4-development.md) — development implementation, selected configuration and lock evidence
- [`docs/stage-e-development-fit.json`](docs/stage-e-development-fit.json) — frozen development-only fit artifact
- [`docs/stage-e-step5-evaluator-freeze.md`](docs/stage-e-step5-evaluator-freeze.md) — pre-outcome evaluator and execution-lock record
- [`CHANGELOG.md`](CHANGELOG.md) — release history

## Sources

- Technical benchmark: [Cell Tracking Challenge U373](https://celltrackingchallenge.net/2d-datasets/), phase-contrast cells on a substrate, not brain slices.
- Exploratory images: [GlioTrace example data, Zenodo 21981544](https://zenodo.org/records/21981544).
- Reference implementation: [Gliomethods/GlioTrace](https://github.com/Gliomethods/GlioTrace).
- Locked independent technical test: [T98G electrotaxis](https://zenodo.org/records/19026908), human-curated variant, `CC-BY-4.0`; performance remains unevaluated.
- Independent operator benchmark: [Cell Tracking Challenge Huh7](https://celltrackingchallenge.net/2d-datasets/); raw data and annotations are not redistributed.

Dataset licenses and redistribution terms are independent from this repository's MIT source-code license.

## Contributing and security

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for development and scientific-change requirements, and [`SECURITY.md`](SECURITY.md) for vulnerability reporting guidance.

## Release process

`v*` tags trigger `.github/workflows/release.yml`. The workflow verifies that the tag version matches the installed package version, runs the test/coverage gate, builds and reinstalls the wheel, and creates a GitHub Release only after validation succeeds.
