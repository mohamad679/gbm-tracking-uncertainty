# Stage A Step 4 v2: spatial burden and noise robustness

Date: 2026-09-19. Status: **REVISE; NO PARAMETERS LOCKED**

## Why v2 exists

Step 4 v1 used total candidate edges as the burden metric. On sequence `01`,
that metric is almost the same as the number of true links: fixed-16 has 726
candidate edges, while 95% recall requires at least 720. A 20% edge reduction
was therefore impossible before any adaptive model could be judged.

Version 2 replaces that metric with a truth-blind spatial-work proxy. For each
source observation it computes the exact area of the union of the fixed 8-px
base gate and the predicted adaptive gate. The mean area is compared with the
fixed-16 circle area (`π × 16² = 804.248 px²` per source). A 15% reduction is
the new predeclared material-efficiency gate. The recall threshold (95%) and
the σ=5 localization-noise robustness threshold (at most 1 px/frame
deterioration versus fixed-8) are unchanged.

The v2 grid contains 75 configurations. It varies motion uncertainty weight,
density weight and posterior new-track score. The latter changes only
posterior sampling; it cannot alter the truth-blind candidate graph.

The complete frozen contract is [`stage-a-protocol-v2.md`](stage-a-protocol-v2.md).

## Leakage boundary

The tuner extracts only development sequence `01` and scenarios `clean_0` and
`localization_noise_5p0`. Sequence `02` is absent from every tuning artifact,
and `locked_test_sequence_evaluated` is `false`. Per-scenario random seeds are
preserved when the full corruption artifact is filtered.

## Result

| Quantity | Result |
|---|---:|
| Grid configurations screened | 75 |
| Configurations passing clean recall + spatial-area screen | 15 |
| Configurations evaluated with posterior + soft dynamics | 15 |
| Highest screened clean recall | 0.9524 |
| Spatial reduction for that configuration | 0.1509 |
| Best σ=5 noise deterioration among evaluated configurations | 2.2029 px/frame |
| Frozen robustness limit | 1.0000 px/frame |

The configuration `m2.75-d0-c4-n9` has the best observed robustness among the
screen-passing candidates, but its σ=5 deterioration is `2.2029 px/frame`.
Every evaluated configuration passes clean recall and spatial burden, and every
one fails the unchanged noise-robustness gate. No configuration is locked.

## Decision

Step 4 v2 returns **REVISE**. The metric replacement solved the v1
infeasibility: clean recall and spatial efficiency can be achieved together.
The remaining blocker is the adaptive-v1 association posterior under
localization noise, not candidate-edge counting. Sequence `02` must remain
locked until a noise-robust candidate/scoring revision passes development
sequence `01`.

Reproduce the run with:

```bash
gbm-adaptive-tuning-v2 \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --output results/stage-a-development-tuning-v2.json
```

Expected exit status is `1` for this scientific `REVISE` result; malformed
artifacts return `2`.
