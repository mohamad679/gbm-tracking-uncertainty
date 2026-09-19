# Stage 5 downstream dynamics sensitivity report

Date: 2026-09-19. Status: **COMPLETED; REVISE before operator extension.**

## Protocol

For every corruption scenario and sequence, the pipeline compared:

1. `reference`: frozen expert U373 tracks;
2. `raw_track_table`: the corrupted observed labels;
3. `nearest_neighbor`: the Stage 3 deterministic tracker;
4. `uncertainty_p50` and `uncertainty_p90`: connected tracks formed from calibrated posterior links above 0.5 and 0.9.

For each representation, migration features were computed in pixels per frame: track count, track length, consecutive steps, mean/median speed and net displacement. A two-state Gaussian HMM on speed was fit as the first dynamics baseline. States are canonicalized by increasing speed mean; they are latent/morphological states, not validated biological phenotypes.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.dynamics \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  results/u373-uncertainty-evaluation.json \
  --output results/u373-dynamics-evaluation.json \
  --max-distance-px 8
```

## Representative results

| Scenario / sequence | Representation | Tracks | Mean speed (px/frame) | HMM switch probability |
|---|---|---:|---:|---:|
| clean / 01 | reference | 8 | 4.624 | 0.230 |
| clean / 01 | nearest-neighbor | 166 | 2.499 | 0.254 |
| clean / 01 | uncertainty p50 | 174 | 2.437 | 0.256 |
| clean / 01 | uncertainty p90 | 247 | 1.867 | 0.253 |
| clean / 02 | reference | 12 | 3.630 | 0.171 |
| clean / 02 | nearest-neighbor | 86 | 2.340 | 0.275 |
| clean / 02 | uncertainty p50 | 95 | 2.263 | 0.276 |
| clean / 02 | uncertainty p90 | 141 | 1.925 | 0.282 |
| σ=5 px noise / 01 | reference | 8 | 4.624 | 0.230 |
| σ=5 px noise / 01 | raw track table | 8 | 10.515 | 0.200 |
| σ=5 px noise / 01 | nearest-neighbor | 476 | 5.125 | 0.411 |
| σ=5 px noise / 01 | uncertainty p50 | 493 | 4.975 | 0.421 |
| σ=5 px noise / 01 | uncertainty p90 | 599 | 3.989 | 0.502 |

The clean result shows that a calibrated association posterior does not automatically produce a faithful hard track table: thresholding increases fragmentation and lowers apparent speed. The high-noise result shows the same trade-off from a different direction: raw labels preserve track count but inflate speed, while hard association produces many short tracks. The `id_switch` scenario also changes the raw track-table HMM while leaving a position-only tracker unchanged, confirming that upstream identity errors need a separate downstream treatment.

## Gate decision

The HMM sensitivity analysis is complete and reproducible. **REVISE before SLDS/Koopman.** The next technical step is a soft-weighted dynamics analysis that integrates posterior link probabilities directly into migration summaries and HMM transition counts instead of converting them to hard p50/p90 tracks. Only if that representation is stable and improves held-out sensitivity should a learned linear operator be added.

## Limitations

- U373 is a 2D technical benchmark, not brain-slice biology.
- Speed uses pixels per frame; no physical time or spatial scale is inferred.
- HMM states are image-derived latent states, not experimentally validated phenotypes.
- This stage does not support treatment-effect or invasion claims for GlioTrace.
