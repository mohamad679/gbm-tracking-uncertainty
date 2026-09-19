# Stage 9 raw-image appearance proposal report

Date: 2026-09-19. Status: **COMPLETED; REJECT appearance proposal for operator learning.**

## Purpose

Unlike the previous morphology proxy, this stage uses the raw U373 phase-contrast images contained in the audited 43.5 MB training ZIP. For each observation, a small frame-local patch is standardized and reduced to a deterministic 5×5 intensity grid plus local mean, standard deviation and gradient magnitude. A constant-velocity link proposal is then weighted by the patch distance between consecutive observations.

The descriptor is truth-blind. It uses only image pixels, frame, and candidate coordinates. It is not a phenotype classifier.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.uncertainty \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --proposal-model motion_appearance \
  --archive data/raw/PhC-C2DH-U373.zip \
  --max-distance-px 8 \
  --output results/u373-uncertainty-motion-appearance-evaluation.json

PYTHONPATH=src python3 -m gbm_audit.soft_dynamics \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  results/u373-uncertainty-motion-appearance-evaluation.json \
  results/u373-dynamics-evaluation.json \
  --output results/u373-soft-dynamics-motion-appearance-evaluation.json
```

Calibration is still fit only on development sequence 01 and evaluated unchanged on sequence 02.

## Results

| Metric | Distance-only | Raw appearance | Interpretation |
|---|---:|---:|---|
| Clean speed delta, sequence 01 | -2.316 | -2.212 | slightly better |
| Clean speed delta, sequence 02 | -1.443 | -1.372 | slightly better |
| Mean absolute speed delta, sequence 01 | 2.032 | 1.923 | better, but insufficient |
| Mean absolute speed delta, sequence 02 | 1.309 | 1.266 | better, but insufficient |
| Clean calibrated Brier, sequence 01 | 0.016 | 0.275 | much worse |
| Clean calibrated ECE, sequence 01 | 0.048 | 0.523 | much worse |
| Clean p50 recall, sequence 01 | 0.781 | 0.162 | confidence collapse |
| σ=5 p50 recall, sequence 02 | 0.401 | 0.007 | confidence collapse |

The appearance proposal improves a few aggregate speed numbers by assigning much less link mass, but its posterior probabilities are poorly calibrated. The p50 recall collapse means it is discarding true links rather than reliably resolving ambiguity. The apparent speed improvement is therefore not evidence of better tracking.

## Gate decision

**Reject this descriptor for downstream operator learning.** Keep distance-only as the primary technical baseline and retain raw appearance as a documented negative control. A future appearance model would need a larger, explicitly calibrated image-level training/validation protocol; this small handcrafted descriptor is not sufficient.

## Scope and limitations

- U373 is a 2D technical benchmark, not brain-slice glioblastoma biology.
- The patch descriptor is a simple engineering feature, not a validated cell-identity embedding.
- No phenotype, invasion, treatment, or clinical conclusion is supported.
