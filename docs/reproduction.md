# Reproduction guide

This repository is a technical feasibility audit. It does not claim validated glioblastoma biology. Raw archives stay outside Git; only hashes, reproducible commands, and a compact result snapshot are tracked.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Test success is established by the test command and GitHub Actions. It is not copied manually into the scientific audit artifact, so the audit cannot become stale when the test suite changes.

## Automated full reproduction

`.github/workflows/reproduce-benchmark.yml` reproduces the full U373 technical benchmark on GitHub Actions. It downloads the official Cell Tracking Challenge training archive, records its SHA-256, runs the unit/integration tests, executes the benchmark/corruption/baseline/uncertainty/dynamics/gate/proposal stages, generates the final audit, and uploads the full `results/` directory as a workflow artifact.

The correctness-hardened reference run completed successfully as GitHub Actions run `35439231472` from source commit `982c1c23619ce0955e1267dc8da36ab3280e5c3c`. The uploaded artifact digest is `sha256:c30c04ebd4ac6e1414682ed4851845536126d59b9675514ef9ff61cd0be3e579`. A compact permanent numerical record is versioned at `docs/reproduced-results-2026-09-19.json`.

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

The final audit derives its gates from the validated artifacts. The current operator-readiness rule requires at least one candidate radius to achieve at least 95% clean true-link coverage on every sequence without worsening the absolute held-out `localization_noise_5p0` soft-speed error by more than 1.0 px/frame relative to the smallest tested gate.

The reproduced result remains `operator_learning_ready = false`: 8 px fails clean coverage, 12 px fails coverage and robustness, and 16 px passes coverage but fails the robustness criterion. Biological validation also remains false because the reference manifest does not declare brain-slice biological ground truth.
