# Reproduction guide

This repository is a technical feasibility audit. It does not claim validated glioblastoma biology. Raw archives stay outside Git; only hashes and reproducible commands are tracked.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

Test success is established by the test command and GitHub Actions. It is not copied manually into the scientific audit artifact, so the audit cannot become stale when the test suite changes.

## Pipeline

Run from the repository root. The reference and corruption JSON files are generated locally under ignored `results/` paths.

```bash
PYTHONPATH=src python3 -m gbm_audit.benchmark data/raw/PhC-C2DH-U373.zip --output results/u373-reference-manifest.json
PYTHONPATH=src python3 -m gbm_audit.corruptions results/u373-reference-manifest.json --output results/u373-corruption-benchmark.json
PYTHONPATH=src python3 -m gbm_audit.uncertainty results/u373-reference-manifest.json results/u373-corruption-benchmark.json --proposal-model distance --output results/u373-uncertainty-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json --output results/u373-dynamics-evaluation.json --max-distance-px 8
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json results/u373-dynamics-evaluation.json --output results/u373-soft-dynamics-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.gate_sensitivity results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-dynamics-evaluation.json --gates 8 12 16 --output results/u373-gate-sensitivity.json
PYTHONPATH=src python3 -m gbm_audit.uncertainty results/u373-reference-manifest.json results/u373-corruption-benchmark.json --proposal-model motion_appearance --archive data/raw/PhC-C2DH-U373.zip --output results/u373-uncertainty-motion-appearance-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-motion-appearance-evaluation.json results/u373-dynamics-evaluation.json --output results/u373-soft-dynamics-motion-appearance-evaluation.json
PYTHONPATH=src python3 -m gbm_audit.final_audit results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json results/u373-dynamics-evaluation.json results/u373-soft-dynamics-evaluation.json results/u373-gate-sensitivity.json results/u373-uncertainty-motion-appearance-evaluation.json --output results/final-audit.json
```

Every downstream stage validates schema version, reference-manifest identity, corruption seed, scenario IDs, scenario metadata, and sequence IDs before combining artifacts. Reordered scenarios therefore remain safe, while stale or mismatched artifacts fail explicitly.

## Interpretation

The final audit derives its gates from the validated artifacts. The current operator-readiness rule requires at least one candidate radius to achieve at least 95% clean true-link coverage on every sequence without worsening the absolute held-out `localization_noise_5p0` soft-speed error by more than 1.0 px/frame relative to the smallest tested gate. The existing benchmark is expected to keep operator learning on HOLD because no tested radius satisfies both conditions.

Biological validation remains false unless the reference manifest explicitly declares a biological validation reference. A future operator extension therefore still requires a proposal model with held-out calibration and a stable candidate-recall/robustness trade-off.
