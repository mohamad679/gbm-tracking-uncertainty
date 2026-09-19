# Reproduction guide

This repository is a technical feasibility audit. It does not claim validated glioblastoma biology. Raw archives stay outside Git; only hashes and reproducible commands are tracked.

## Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests -q
```

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
PYTHONPATH=src python3 -m gbm_audit.final_audit results/u373-reference-manifest.json results/u373-corruption-benchmark.json results/u373-uncertainty-evaluation.json results/u373-dynamics-evaluation.json results/u373-soft-dynamics-evaluation.json results/u373-gate-sensitivity.json results/u373-uncertainty-motion-appearance-evaluation.json --tests-passed 28 --output results/final-audit.json
```

## Interpretation

The final audit should report `technical_benchmark_complete: true`, `operator_learning_ready: false`, and `biological_validation_claim_supported: false`. A future operator extension requires a new proposal model with held-out calibration and a stable gate/sensitivity trade-off.
