# Stage 6 candidate-gate sensitivity report

Date: 2026-09-19. Status: **COMPLETED; retain 8 px for the baseline, do not promote an operator.**

## Purpose

Stage 5 showed that soft probability weighting cannot recover links omitted by the candidate proposal gate. Stage 6 sweeps the spatial candidate radius while keeping the hypothesis count, distance temperature and development-only calibration protocol fixed. It measures whether a larger proposal gate improves clean reference-link coverage without creating an unstable downstream speed estimate.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.gate_sensitivity \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  results/u373-dynamics-evaluation.json \
  --gates 8 12 16 \
  --output results/u373-gate-sensitivity.json
```

The report is deliberately compact; full per-link posteriors remain in the ignored uncertainty outputs generated for each gate during the run.

## Results

| Gate | Clean coverage 01 / 02 | Clean soft speed delta 01 / 02 | σ=5 speed delta 01 / 02 | Mean absolute delta 01 / 02 |
|---:|---:|---:|---:|---:|
| 8 px | 79.1% / 89.1% | -2.316 / -1.443 | +0.220 / +1.100 | 2.032 / 1.309 |
| 12 px | 91.7% / 95.0% | -1.314 / -0.909 | +2.137 / +3.073 | 1.300 / 1.032 |
| 16 px | 95.9% / 97.1% | -0.783 / -0.651 | +3.828 / +4.353 | 0.978 / 0.917 |

The larger gates recover more clean reference links and reduce average clean speed bias, but they admit many more ambiguous high-noise links. The σ=5 held-out speed error rises by roughly 1.9–2.0 px/frame at 12 px and 3.3–3.6 px/frame at 16 px relative to the 8-pixel baseline. On this benchmark there is no single radius that dominates both clean recall and corruption robustness.

## Interpretation rule

The gate is not selected by clean speed alone. A candidate radius is eligible only if it materially increases reference-link coverage and does not introduce a large deterioration in held-out noise sensitivity. Even an eligible radius supports only a technical benchmark decision; it does not establish a biological invasion phenotype.

## Current decision

The gate sweep is complete. Retain 8 px as the conservative baseline and expose the 12/16 px alternatives as sensitivity analyses. **Do not start SLDS or Koopman learning yet:** the proposal-radius trade-off is unresolved, so an operator would confound motion with gate-induced ambiguity. The next improvement should be a gap-aware or appearance-aware candidate score, followed by the same sweep.
