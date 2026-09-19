# Stage 8 multi-feature proposal report

Date: 2026-09-19. Status: **COMPLETED; HOLD before SLDS/Koopman.**

## Purpose

Stage 7 used a constant-velocity proposal. Stage 8 adds the available segmentation-area feature to the motion score. For a candidate link, the sampler combines prediction residual with the absolute log-area ratio between the active path and the new observation. The model is truth-blind; `area_px` is the only appearance-like field available in the current track table.

This is not a raw-image appearance model. It tests whether a cheap morphology proxy is sufficient to stabilize downstream dynamics.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.uncertainty \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --proposal-model motion_area --max-distance-px 8 \
  --output results/u373-uncertainty-motion-area-evaluation.json

PYTHONPATH=src python3 -m gbm_audit.soft_dynamics \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  results/u373-uncertainty-motion-area-evaluation.json \
  results/u373-dynamics-evaluation.json \
  --output results/u373-soft-dynamics-motion-area-evaluation.json
```

The area temperature is fixed at 0.5 log-area units; it is not fit on the test sequence.

## Results

| Metric | Distance-only | Motion + area | Change |
|---|---:|---:|---:|
| Clean speed delta, sequence 01 | -2.316 | -2.511 | -0.195 |
| Clean speed delta, sequence 02 | -1.443 | -1.554 | -0.111 |
| σ=5 speed delta, sequence 01 | +0.220 | -0.009 | -0.229 |
| σ=5 speed delta, sequence 02 | +1.100 | +0.891 | -0.209 |
| Mean absolute speed delta, sequence 01 | 2.032 | 2.198 | +0.166 |
| Mean absolute speed delta, sequence 02 | 1.309 | 1.389 | +0.080 |
| Clean expected link mass, sequence 01 | 570.3 | 517.0 | -53.3 |
| False-positive expected link mass, sequence 01 | 567.5 | 518.1 | lower overall mass |

The area term lowers total expected link mass and worsens clean and aggregate speed error. Its small improvement in the σ=5 scenario is not robust: false-positive separation does not improve, and the model discards uncertain links rather than resolving them.

## Gate decision

**Do not promote the multi-feature proposal to operator learning.** Keep distance-only as the reference baseline and retain motion and motion+area as negative sensitivity controls. `area_px` is not a substitute for an image-derived appearance descriptor.

## Next technical step

If raw U373 images are available under a verified license, extract a small, reproducible patch descriptor (normalized intensity/texture) and test it without changing the held-out corruption protocol. If raw images are not available, stop at the technical benchmark rather than inventing a biological appearance signal.

## Limitations

- U373 is a 2D technical benchmark, not brain-slice glioblastoma biology.
- Area is segmentation morphology, not cell appearance or phenotype.
- Speeds are pixels per frame; no physical migration rate is inferred.
- No phenotype, invasion, treatment, or clinical conclusion is supported.
