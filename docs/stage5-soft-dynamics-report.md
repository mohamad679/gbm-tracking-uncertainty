# Stage 5 soft-weighted downstream dynamics report

Date: 2026-09-19. Status: **COMPLETED; HOLD before SLDS/Koopman.**

## Purpose

The first Stage 5 analysis converted calibrated association posteriors into hard tracks using p50 and p90 thresholds. This revision keeps every candidate link and propagates its calibrated probability as a weight. Migration speed is summarized by an expected weighted link mass, and HMM transition counts are weighted by the product of adjacent link probabilities.

This is a technical sensitivity analysis on the public U373 benchmark. The latent states are image-derived speed regimes, not validated biological phenotypes.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.soft_dynamics \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  results/u373-uncertainty-evaluation.json \
  results/u373-dynamics-evaluation.json \
  --output results/u373-soft-dynamics-evaluation.json
```

The uncertainty calibration temperature is fit on development sequence 01 and held fixed for sequence 02. The corrected coverage denominator counts all consecutive reference links, including links outside the 8-pixel candidate gate.

## Candidate coverage limitation

On the clean input, the 8-pixel candidate gate contains 599/757 (79.1%) of reference links in sequence 01 and 606/680 (89.1%) in sequence 02. Soft weighting can express uncertainty among candidate links, but it cannot recover a true link that was never proposed. This is a gate-recall limitation, not evidence that the biological motion is absent.

## Representative results

| Scenario / sequence | Reference mean speed | Soft weighted speed | Soft speed delta | Hard p50 speed delta | Soft HMM transition L1 |
|---|---:|---:|---:|---:|---:|
| clean / 01 | 4.624 | 2.308 | -2.316 | -2.187 | 0.154 |
| clean / 02 | 3.630 | 2.187 | -1.443 | -1.367 | 1.216 |
| σ=5 px noise / 01 | 4.624 | 4.845 | +0.220 | +0.351 | 0.812 |
| σ=5 px noise / 02 | 3.630 | 4.730 | +1.100 | +1.242 | 0.818 |

The soft representation avoids the arbitrary p50/p90 cutoff and preserves an interpretable expected link mass. However, it does not consistently improve held-out speed or transition error relative to hard p50: the clean sequences remain biased low because of candidate-gate recall, while high-noise sequences remain biased high. Therefore the soft formulation is a useful diagnostic and a safer reporting layer, but it is not yet a sufficient basis for claiming reliable phenotype dynamics.

## Gate decision

**Do not start SLDS or Koopman learning yet.** The project remains executable, but the next required step is to improve the candidate proposal stage (or introduce a gap-aware probabilistic path model) and re-run this soft evaluation. An operator learned before that correction would learn proposal/gate artifacts as if they were migration dynamics.

## Limitations

- U373 is a 2D technical benchmark, not brain-slice glioblastoma biology.
- Speeds are pixels per frame; no physical time or spatial scale is inferred.
- HMM states are latent image-derived regimes, not validated phenotypes.
- No treatment-effect, invasion-rate, or clinical conclusion is supported.
