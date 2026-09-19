# Reproduction guide

This repository is a technical feasibility audit. It does not claim validated glioblastoma biology. Raw archives stay outside Git; only hashes, reproducible commands, environment constraints, and compact result snapshots are tracked.

## Supported environment

Release `0.1.0` supports CPython 3.11, 3.12, and 3.13. Runtime dependency ranges live in `pyproject.toml`; exact versions for the validated environment live in `constraints.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -c constraints.txt -e .
coverage run --source=gbm_audit -m unittest discover -s tests -q
coverage report --show-missing --fail-under=65
```

The CI matrix executes the same pinned installation on Python 3.11, 3.12, and 3.13. It also builds the wheel and reinstalls it as a package smoke test. Test success is established by the commands and GitHub Actions; it is not manually copied into scientific output fields.

### Exact dependency pins

The validated constraints are interpreter-aware because the newest NumPy line does not provide the same CPython 3.11 wheel support as 3.12/3.13:

- Python 3.11: `numpy==2.4.2`
- Python 3.12–3.13: `numpy==2.5.3`
- `Pillow==12.3.0`
- `certifi==2026.7.22`
- CI coverage tool: `coverage==7.16.1`

## Automated full reproduction

`.github/workflows/reproduce-benchmark.yml` reproduces the full U373 technical benchmark on GitHub Actions. It installs through `constraints.txt`, downloads the official Cell Tracking Challenge training archive, records its SHA-256, runs the unit/integration tests, executes the benchmark/corruption/baseline/uncertainty/dynamics/gate/proposal stages, generates the final audit, and uploads the full `results/` directory as a workflow artifact.

The workflow supplies `GBM_AUDIT_GIT_SHA=${{ github.sha }}` to the numerical pipeline. `results/final-audit.json` therefore records:

- package name and package version;
- Python version and implementation;
- NumPy, Pillow, and certifi versions;
- source Git commit SHA;
- SHA-256 hashes of every audit input artifact.

A compact permanent numerical record is versioned at `docs/reproduced-results-2026-09-19.json`. Full generated JSON remains an Actions artifact rather than committed bulk output.

## Local pipeline

Run from the repository root. The reference and corruption JSON files are generated locally under ignored `results/` paths.

```bash
PYTHONPATH=src python3 -m gbm_audit.benchmark data/raw/PhC-C2DH-U373.zip --output results/u373-reference-manifest.json
PYTHONPATH=src python3 -m gbm_audit.corruptions results/u373-reference-manifest.json --output results/u373-corruption-benchmark.json --seed 20260919
PYTHONPATH=src python3 -m gbm_audit.baseline results/u373-reference-manifest.json results/u373-corruption-benchmark.json --max-distance-px 8 --output results/u373-baseline-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.uncertainty results/u373-reference-manifest.json results/u373-corruption-benchmark.json --proposal-model distance --max-distance-px 8 --output results/u373-uncertainty-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json --output results/u373-dynamics-evaluation.json --max-distance-px 8
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json results/u373-dynamics-evaluation.json --output results/u373-soft-dynamics-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.gate_sensitivity results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-dynamics-evaluation.json --gates 8 12 16 --output results/u373-gate-sensitivity.json
PYTHONPATH=src python3 -m gbm_audit.uncertainty results/u373-reference-manifest.json results/u373-corruption-benchmark.json --proposal-model motion --max-distance-px 8 --output results/u373-uncertainty-motion-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-motion-evaluation.json results/u373-dynamics-evaluation.json --output results/u373-soft-dynamics-motion-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.uncertainty results/u373-reference-manifest.json results/u373-corruption-benchmark.json --proposal-model motion_area --max-distance-px 8 --output results/u373-uncertainty-motion-area-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-motion-area-evaluation.json results/u373-dynamics-evaluation.json --output results/u373-soft-dynamics-motion-area-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.uncertainty results/u373-reference-manifest.json results/u373-corruption-benchmark.json --proposal-model motion_appearance --archive data/raw/PhC-C2DH-U373.zip --max-distance-px 8 --output results/u373-uncertainty-motion-appearance-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-motion-appearance-evaluation.json results/u373-dynamics-evaluation.json --output results/u373-soft-dynamics-motion-appearance-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.final_audit results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json results/u373-dynamics-evaluation.json results/u373-soft-dynamics-evaluation.json results/u373-gate-sensitivity.json results/u373-uncertainty-motion-appearance-evaluation.json --output results/final-audit.json
```

Every downstream stage validates schema version, reference-manifest identity, corruption seed, scenario IDs, scenario metadata, and sequence IDs before combining artifacts. Reordered scenarios therefore remain safe, while stale or mismatched artifacts fail explicitly.

## Reproduced interpretation

The final audit derives its gates from the validated artifacts. The operator-readiness rule requires at least one candidate radius to achieve at least 95% clean true-link coverage on every sequence without worsening the absolute held-out `localization_noise_5p0` soft-speed error by more than 1.0 px/frame relative to the smallest tested gate.

The reproduced result remains `operator_learning_ready = false`: 8 px fails clean coverage, 12 px fails coverage and robustness, and 16 px passes coverage but fails the robustness criterion. Biological validation also remains false because the reference manifest does not declare brain-slice biological ground truth.

## Licensing

Repository source code is distributed under the MIT License in `LICENSE`. That license does not grant redistribution rights for external datasets. The U373/Cell Tracking Challenge and GlioTrace sources retain their own terms and should be cited and redistributed only according to those terms.
