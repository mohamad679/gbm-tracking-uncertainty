# Stage A Step 4 v3: noise-robust posterior lock

Date: 2026-09-19. Status: **COMPLETED; DEVELOPMENT CONFIGURATION LOCKED**

## Revision

The v2 spatial burden metric made clean recall and spatial efficiency jointly
feasible, but all 15 screen-passing configurations still failed the σ=5
robustness gate. v3 adds a calibrated posterior-probability floor to the
adaptive configuration. The candidate graph is unchanged; only links whose
calibrated probability is below the locked floor are excluded from the soft
downstream summary.

The v3 grid crosses the v2 graph/search parameters and posterior floors
`{0.3, 0.4, 0.5, 0.6, 0.7}` for 375 development-only configurations.

## Locked development configuration

```json
{
  "min_radius_px": 8.0,
  "max_radius_px": 16.0,
  "motion_uncertainty_weight": 2.75,
  "density_weight_px": 0.0,
  "density_radius_px": 16.0,
  "density_saturation_count": 6,
  "cold_start_uncertainty_px": 4.0,
  "history_length": 4,
  "new_track_score_px": 10.0,
  "posterior_probability_floor": 0.7
}
```

The configuration ID is `m2.75-d0-c4-n10-p0.7` and is asserted in source and
tests so that a later accidental re-tuning cannot silently change it.

## Development result

| Metric on sequence 01 | Locked result | Gate |
|---|---:|---:|
| Clean true-link recall | 0.95244 | ≥ 0.95000 |
| Spatial search-area reduction vs fixed-16 | 0.15085 | ≥ 0.15000 |
| σ=5 noise deterioration vs fixed-8 | -0.03746 px/frame | ≤ 1.00000 |

Twenty-four of the 75 evaluated configurations passed all three gates. The
selection rule chose the lowest σ=5 soft-speed error, then clean error, then
spatial area, with a deterministic configuration-ID tie-break.

## Leakage boundary

Only development sequence `01` and `clean_0`/`localization_noise_5p0` were used.
The v3 artifact records `locked_test_sequence_evaluated: false`; sequence `02`
has not been inspected by this tuner.

## Decision

Development tuning passes and one configuration is locked. The next step is
the single locked evaluation on sequence `02`, followed by the final Stage A
comparison and PASS/REVISE publication. No further parameter changes are
allowed before that evaluation.

Reproduce the tuning run with:

```bash
gbm-adaptive-tuning-v3 \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --output results/stage-a-development-tuning-v3.json
```
