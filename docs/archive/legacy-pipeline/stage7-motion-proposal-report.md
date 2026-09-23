# Stage 7 motion-consistent proposal report

> Historical pre-Stage-A-D report. Its `HOLD` status was superseded by the
> qualified Stage D v3 `GO`; see [`stage-d-closure-report.md`](stage-d-closure-report.md).

Date: 2026-09-19. Status: **COMPLETED; HOLD before SLDS/Koopman.**

## Purpose

Stage 6 showed that increasing the spatial gate improves clean recall but admits ambiguous noisy links. Stage 7 therefore adds a constant-velocity proposal model. Each active path stores its last two positions, predicts the next position by linear extrapolation, and assigns probability according to the residual to that prediction. The sampler remains one-to-one, seeded, and truth-blind.

This is a proposal model, not a biological motion model. It is evaluated only on the public U373 technical benchmark.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.uncertainty \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --proposal-model motion --max-distance-px 8 \
  --output results/u373-uncertainty-motion-evaluation.json

PYTHONPATH=src python3 -m gbm_audit.soft_dynamics \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  results/u373-uncertainty-motion-evaluation.json \
  results/u373-dynamics-evaluation.json \
  --output results/u373-soft-dynamics-motion-evaluation.json
```

The comparison baseline is the distance-only posterior from Stage 5 using the same 8-pixel gate and 64 hypotheses.

## Results

| Metric | Distance-only | Motion proposal | Change |
|---|---:|---:|---:|
| Clean speed delta, sequence 01 | -2.316 | -2.348 | -0.032 |
| Clean speed delta, sequence 02 | -1.443 | -1.457 | -0.014 |
| σ=5 speed delta, sequence 01 | +0.220 | +0.085 | -0.135 |
| σ=5 speed delta, sequence 02 | +1.100 | +0.969 | -0.131 |
| HMM transition L1, σ=5 sequence 01 | 0.812 | 0.835 | +0.023 |
| HMM transition L1, σ=5 sequence 02 | 0.818 | 1.072 | +0.254 |
| Mean absolute speed delta, sequence 01 | 2.032 | 2.052 | +0.020 |
| Mean absolute speed delta, sequence 02 | 1.309 | 1.312 | +0.003 |

Clean candidate coverage is unchanged at 79.1% for sequence 01 and 89.1% for sequence 02, because the 8-pixel proposal gate still excludes the same true links. The motion score slightly improves noisy speed estimates but does not improve the full downstream sensitivity profile; its held-out transition error is worse in sequence 02. Values above were reproduced after Stage A Step 3 restricted motion scoring to the declared fixed-distance candidate graph.

## Gate decision

**No promotion to SLDS or Koopman.** Constant-velocity scoring is a reproducible improvement to the proposal layer, but not a validated solution. The conservative distance-only model remains the reference baseline, while the motion proposal is retained as a sensitivity comparator.

## Next technical step

Use an appearance-aware or multi-frame path score. The current track table contains area and coordinate features, but no raw-image appearance descriptor; therefore any appearance model must first be audited on the image data and evaluated with the same fixed corruption suite.

## Limitations

- U373 is a 2D technical benchmark, not brain-slice glioblastoma biology.
- The constant-velocity prior can be wrong during turns, division, or abrupt phenotype changes.
- Speeds are pixels per frame and do not imply physical migration rates.
- No phenotype, invasion, treatment, or clinical conclusion is supported.
