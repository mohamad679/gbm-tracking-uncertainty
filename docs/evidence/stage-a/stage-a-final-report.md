# Stage A final report: PASS

Date: 2026-09-19. Status: **COMPLETED**

## Locked configuration

The development-only v3 search locked `m2.75-d0-c4-n10-p0.7`:

- minimum/maximum radii: 8/16 px;
- motion uncertainty weight: 2.75;
- density weight: 0 px;
- cold-start uncertainty: 4 px;
- new-track score: 10 px;
- calibrated posterior probability floor: 0.7.

The candidate graph is truth-blind. The probability floor changes only the
soft downstream aggregation after candidate generation. No parameter was
changed after sequence `02` was evaluated.

## Final locked comparison

| Sequence | Split | Clean recall | Spatial reduction vs fixed-16 | σ=5 deterioration vs fixed-8 | Decision |
|---|---|---:|---:|---:|---|
| 01 | development | 0.95244 | 0.15085 | 0.45386 px/frame | PASS |
| 02 | locked test | 0.96471 | 0.17379 | 0.40167 px/frame | PASS |

Frozen gates were recall `≥0.95`, spatial search-area reduction `≥0.15`, and
σ=5 deterioration `≤1.0 px/frame`. All three pass independently on both
sequences, so the final Stage A decision is **PASS**.

The locked test was evaluated once by `gbm-stage-a-locked`. The machine-readable
artifact is [`stage-a-locked-evaluation-v3.json`](stage-a-locked-evaluation-v3.json).

## Reproduction

```bash
gbm-stage-a-locked \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --output results/stage-a-locked-evaluation-v3.json
```

The result is a technical U373 benchmark decision, not biological validation
or a claim that the tracker generalizes to other datasets. The next research
stage may compare broader datasets and human-reviewed biological endpoints;
Stage A itself is complete.
