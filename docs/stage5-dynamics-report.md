# Stage 5 downstream dynamics sensitivity report

Date: 2026-09-19. Status: **COMPLETED; REVISE before operator extension. Reproduced after `wrong_link` correction.**

## Protocol

For every corruption scenario and sequence, the pipeline compared:

1. `reference`: frozen expert U373 tracks;
2. `raw_track_table`: the corrupted observed labels;
3. `nearest_neighbor`: the Stage 3 deterministic tracker;
4. `uncertainty_p50` and `uncertainty_p90`: connected tracks formed from calibrated posterior links above 0.5 and 0.9.

For each representation, migration features were computed in pixels per frame: track count, track length, consecutive steps, mean/median speed and net displacement. A two-state Gaussian HMM on speed was fit as the first dynamics baseline. States are latent image-derived states, not validated biological phenotypes.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.dynamics \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  results/u373-uncertainty-evaluation.json \
  --output results/u373-dynamics-evaluation.json \
  --max-distance-px 8
```

The corrected dynamics artifact SHA-256 is `cbb360a680960d40778629a0ff2bb44d3cd739a19f205bdb69881a23c791d5c5` from GitHub Actions run `35439231472`.

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

## Corrected `wrong_link` sensitivity

The regenerated run now measures the intended one-frame local association error rather than the previous persistent-switch behavior. The position-only tracker is still insensitive to the observed label itself, but the `raw_track_table` dynamics correctly show the downstream effect of the local identity corruption:

| Scenario | Sequence | Raw mean-speed delta (px/frame) | Raw HMM transition L1 | HMM switch-probability delta |
|---|---|---:|---:|---:|
| wrong_link_1 | 01 | +0.548 | 1.846 | -0.124 |
| wrong_link_1 | 02 | +2.176 | 0.756 | -0.105 |
| wrong_link_2 | 01 | +2.025 | 1.837 | -0.193 |
| wrong_link_2 | 02 | +2.211 | 0.699 | -0.102 |

This confirms why the corruption semantics mattered: a local upstream identity error can strongly alter track-table-derived speed and latent transition summaries even when the underlying detection coordinates are unchanged.

## Gate decision

The HMM sensitivity analysis is complete and reproducible. **REVISE before SLDS/Koopman.** The soft-weighted analysis and proposal-gate sweep remain necessary because hard association produces fragmented tracks and the corrected identity-corruption results reinforce the need to keep label errors separate from coordinate errors.

## Limitations

- U373 is a 2D technical benchmark, not brain-slice biology.
- Speed uses pixels per frame; no physical time or spatial scale is inferred.
- HMM states are image-derived latent states, not experimentally validated phenotypes.
- This stage does not support treatment-effect or invasion claims for GlioTrace.
