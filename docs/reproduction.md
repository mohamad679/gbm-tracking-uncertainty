# Reproduction guide

This repository is a technical feasibility audit. It does not claim validated human glioblastoma biology. Raw archives stay outside Git; only hashes, reproducible commands, environment constraints, and compact result snapshots are tracked.

## Supported environment

Release `1.0.0` supports CPython 3.11, 3.12, and 3.13. Runtime dependency ranges live in `pyproject.toml`; exact versions for the validated environment live in `constraints.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt -e .
coverage run --source=gbm_audit -m unittest discover -s tests -q
coverage report --show-missing --fail-under=65
```

The CI matrix executes the same pinned installation on Python 3.11, 3.12, and 3.13. It also builds the wheel and reinstalls it as a package smoke test. Test success is established by the commands and GitHub Actions; it is not manually copied into scientific output fields.

### Exact dependency pins

The validated constraints are interpreter-aware:

- Python 3.11: `numpy==2.4.2`
- Python 3.12–3.13: `numpy==2.5.3`
- `Pillow==12.3.0`
- `certifi==2026.7.22`
- CI coverage tool: `coverage==7.16.1`

## Automated full U373 reproduction

`.github/workflows/reproduce-benchmark.yml` reproduces the full U373 technical benchmark on GitHub Actions. It installs through `constraints.txt`, downloads the official Cell Tracking Challenge training archive, records its SHA-256, runs the unit/integration tests, executes the benchmark/corruption/baseline/uncertainty/dynamics/gate/proposal stages, generates the final audit, and uploads the full `results/` directory as a workflow artifact.

The workflow supplies `GBM_AUDIT_GIT_SHA=${{ github.sha }}` to the numerical pipeline. `results/final-audit.json` records package/runtime provenance, source Git commit SHA, and SHA-256 hashes of audit inputs.

A compact permanent numerical record is versioned at [`evidence/engineering/reproduced-results-2026-09-19.json`](evidence/engineering/reproduced-results-2026-09-19.json). Full generated JSON remains an Actions artifact rather than committed bulk output.

## Local U373 pipeline

Run from the repository root. Generated artifacts stay under ignored `results/` paths.

```bash
PYTHONPATH=src python3 -m gbm_audit.benchmark data/raw/PhC-C2DH-U373.zip --output results/u373-reference-manifest.json
PYTHONPATH=src python3 -m gbm_audit.corruptions results/u373-reference-manifest.json --output results/u373-corruption-benchmark.json --seed 20260919
PYTHONPATH=src python3 -m gbm_audit.baseline results/u373-reference-manifest.json results/u373-corruption-benchmark.json --max-distance-px 8 --output results/u373-baseline-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.uncertainty results/u373-reference-manifest.json results/u373-corruption-benchmark.json --proposal-model distance --max-distance-px 8 --output results/u373-uncertainty-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json --output results/u373-dynamics-evaluation.json --max-distance-px 8
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json results/u373-dynamics-evaluation.json --output results/u373-soft-dynamics-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.gate_sensitivity results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-dynamics-evaluation.json --gates 8 12 16 --output results/u373-gate-sensitivity.json
PYTHONPATH=src python3 -m gbm_audit.final_audit results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json results/u373-dynamics-evaluation.json results/u373-soft-dynamics-evaluation.json results/u373-gate-sensitivity.json --output results/final-audit.json
```

Every downstream stage validates schema version, reference-manifest identity, corruption seed, scenario IDs, scenario metadata, and sequence IDs before combining artifacts.

## Reproduce the T98G data-only audit

`.github/workflows/audit-t98g.yml` reproduces the structural-only T98G audit and compares it with the committed lock under `docs/evidence/stage-c/`.

```bash
curl --fail --location --retry 3 \
  --output data/raw/T98G_electrotaxis.zip \
  https://zenodo.org/api/records/19026908/files/T98G_electrotaxis.zip/content
PYTHONPATH=src python3 -m gbm_audit.t98g_audit \
  data/raw/T98G_electrotaxis.zip \
  --output /tmp/stage-c-v2-t98g-locked-manifest.json
diff -u docs/evidence/stage-c/stage-c-v2-t98g-locked-manifest.json \
  /tmp/stage-c-v2-t98g-locked-manifest.json
```

The structural audit itself does not run tracking performance.

## Stage C/D/E reproduction workflows

The repository retains dedicated workflows for the frozen stage evidence:

- `.github/workflows/reproduce-stage-c-v2-development.yml`
- `.github/workflows/reproduce-stage-c-v2-t98g.yml`
- `.github/workflows/reproduce-stage-d-v3.yml`
- `.github/workflows/reproduce-stage-e-development.yml`
- `.github/workflows/validate-stage-e-locked-evaluator.yml`
- `.github/workflows/reproduce-stage-e-statistics.yml`
- `.github/workflows/reproduce-stage-e-track-bootstrap.yml`
- `.github/workflows/reproduce-stage-e-ctc-metrics.yml`

Current frozen stage artifacts are under `docs/evidence/stage-*`; superseded development/HOLD-era material required for historical reproduction is under `docs/archive/stage-*`.

## Reproduce the local Dryad three-experiment arm

The raw Dryad archive is intentionally not redistributed. Use the exact source files and hashes described in [`evidence/dryad/dryad-confirmatory-local-runbook.md`](evidence/dryad/dryad-confirmatory-local-runbook.md). The local workflow is deliberately gated:

1. verify the deposited source hashes and create schema-only inventory;
2. inspect schema evidence without method outcomes;
3. use the committed [`evidence/dryad/dryad-confirmatory-schema-lock.json`](evidence/dryad/dryad-confirmatory-schema-lock.json);
4. normalize all three experiments;
5. execute the frozen confirmatory evaluator once.

Install the optional source-inspection dependencies with:

```bash
python -m pip install -c constraints.txt -e '.[dryad]'
```

The final machine-readable one-time result is preserved as [`evidence/dryad/dryad-confirmatory-result.json.gz`](evidence/dryad/dryad-confirmatory-result.json.gz), and its interpretation is in [`dryad-confirmatory-final-report.md`](dryad-confirmatory-final-report.md).

## Reproduced interpretation

The original U373 final audit remains `operator_learning_ready = false`; later staged work does not retroactively alter that historical field. Stage D v3 later demonstrated a bounded calibrated within-Huh7 technical `GO`, while Stage E-Final produced a valid locked `REVISE`.

The subsequent Dryad `n=3` rat glioma brain-slice arm provides external **technical-transfer** evidence for uncertainty as an association-error ranking, calibration and selective-risk mechanism. It does not show superiority of the frozen `p >= 0.5` hard tracker, and it does not establish human-GBM-wide biological validation, a validated migration phenotype, patient-level inference, or clinical utility.

## Licensing

Repository source code is distributed under the MIT License in `LICENSE`. That license does not grant redistribution rights for external datasets. T98G, Cell Tracking Challenge datasets, GlioTrace and Dryad retain their own terms and must be cited/redistributed accordingly.
