# Stage A Step 3: candidate graph integration

Date: 2026-09-19. Status: **COMPLETED; AWAITING DEVELOPMENT-ONLY TUNING**

## Purpose

This step connects `adaptive_v1` to sampled one-to-one association
hypotheses, calibrated link posteriors and the existing soft-dynamics layer.
It also enforces one candidate-graph invariant across all proposal models:

> Every sampled or posterior link must belong to the same candidate graph used
> to calculate true-link recall and candidate burden.

## Integration design

The adaptive generator now supplies an explicit edge table. Each edge contains
direct distance, prediction residual, adaptive radius, inclusion source and a
proposal score defined as the smaller of direct distance and prediction
residual. The sampler accepts this table directly and never regenerates a
separate radius graph.

For every target observation, the sampler considers only active predecessor
observations present in the explicit graph. One-to-one constraints and the
seeded no-link/new-track option are retained. A runtime assertion rejects any
sample containing an edge outside the graph.

Posterior rows preserve the adaptive diagnostics, and `soft_dynamics.py`
continues to consume the resulting probability and physical link distance.

## Legacy proposal correction

The existing `motion`, `motion_area` and `motion_appearance` variants remain
scoring models on the fixed-distance candidate graph. They are now explicitly
restricted to that graph. A constant-velocity prediction can re-rank an
eligible fixed edge, but cannot silently create an edge that recall and burden
did not count.

## Configuration interface

`gbm-uncertainty --proposal-model adaptive_v1` exposes the v1 parameters:

- minimum and maximum radii;
- motion-uncertainty weight;
- density weight, radius and saturation count;
- cold-start uncertainty;
- seed-history length.

These parameters are exposed for Step 4. They have not yet been selected on
the development sequence.

## Leakage boundary

Integration tests use synthetic observations only. This step does not run
`adaptive_v1` on U373 sequence `02`, inspect its adaptive metrics or select any
parameter from it. The locked evaluation remains deferred until Step 5.

## Validation

- 63/63 package tests pass.
- Package statement coverage is 71%.
- Adaptive posterior recovery is tested on a synthetic link outside the fixed
  8-pixel gate.
- Explicit-graph sampling is tested to emit no unlisted edge.
- Legacy motion scoring is tested not to escape its fixed candidate graph.
- The resulting adaptive posterior is consumed by soft dynamics in an
  integration test.
