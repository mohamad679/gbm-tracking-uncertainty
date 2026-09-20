# Stage C protocol: posterior propagation to migration and state summaries

Date: 2026-09-19. Status: **FROZEN — REVISE 2026-09-20**.

## Research question

Given the Stage B `PASS` context-aware association posterior, can globally
compatible posterior matching samples quantify uncertainty in migration and
latent-state summaries on the controlled U373 benchmark? Stage C changes only
the downstream representation of uncertainty. It does not retune tracking,
candidate generation, calibration, corruption construction or biological
interpretation.

## Frozen upstream inputs

- Stage A candidate graph configuration remains
  `m2.75-d0-c4-n10-p0.7`.
- Stage B exact component matching posterior remains the primary inference
  source, with link potential `exp(-proposal_score_px / 4.0)` and unmatched
  target potential `exp(-10.0 / 4.0)`.
- The Stage B probability-temperature calibration remains frozen at `0.55`.
- The comparator is the Stage A sampled one-to-one posterior, with the same
  graph, potentials, calibration and downstream propagation procedure.
- All 17 seeded corruption scenarios remain in scope.

No reference identity, reference track, reference state, corruption label or
downstream metric may be read while constructing matching samples. Reference
material is used only after summaries are produced, for benchmark scoring.

## Posterior trajectory ensemble

For every adjacent-frame bipartite component, Stage C will draw matching states
from the exact Stage B component distribution, not independent link Bernoulli
variables. Independent components and frame transitions are combined into one
globally one-to-one association realization. A fixed 256-member ensemble and
the benchmark seed `20260919` are pre-registered.

Each ensemble member yields connected trajectories. The artifact must retain
the matching seed, component diagnostics, link mass, track count and effective
sample count. A component over the Stage B exact limit of 18 targets, any
one-to-one violation, or any silent fallback to independent links or a
different sampler is a `REVISE` result.

## Downstream summaries

For each trajectory realization, calculate in pixels per frame:

1. mean speed, median speed, net displacement and track length;
2. directional persistence, defined as the mean cosine between consecutive
   displacement vectors for tracks with at least two steps;
3. mean-squared displacement at lags 1, 2 and 3 frames, when available; and
4. two-state speed-HMM occupancy, transition probabilities, switch probability
   and dwell length.

The HMM is a technical two-state Gaussian speed model. It is fitted once on
the uncorrupted reference trajectories from development sequence `01`, then
its parameters and low/high-speed state ordering are frozen before application
to every corrupted development and locked-test realization. The resulting
states are image-derived speed regimes, not biological phenotypes.

For every scalar summary, report the posterior median and 5th/95th percentile
interval across ensemble members. For HMM transitions and occupancy, report
posterior mean and 5th/95th percentile interval. No hard p50/p90 edge cutoff
is part of the Stage C primary method; prior hard and soft summaries remain
baselines only.

## Split discipline and decision rule

- Sequence `01` is the development sequence. It may fit the fixed speed-HMM
  and validate implementation invariants only.
- Sequence `02` remains locked until the ensemble size, HMM procedure, output
  schema and scoring code are frozen.
- The Stage B calibration is not refit in Stage C.

Stage C is `PASS` only when all of the following hold on sequence `02` across
all 17 scenarios:

1. every ensemble and component invariant passes, with no resource-bound or
   approximation violation;
2. the nominal 90% exact-posterior interval for mean speed covers the reference
   summary in at least 80% and at most 98% of scenarios with defined reference
   speed;
3. the median absolute error of exact-posterior mean speed is no worse than the
   sampled-posterior comparator by more than `0.10` pixels per frame; and
4. all required summary fields are produced for at least 95% of defined
   reference cases; undefined short-track persistence/MSD/dwell quantities are
   recorded explicitly rather than imputed.

The coverage requirement checks that intervals are useful rather than merely
available. The accuracy criterion is a pre-registered non-inferiority test;
Stage C does not require a post-hoc improvement. A failed condition is
`REVISE`. Neither outcome validates a biological migration phenotype.

## Implementation sequence

1. Implement exact component-state sampling and trajectory-ensemble invariants.
2. Implement fixed development-only HMM fitting and posterior migration/state
   summary aggregation.
3. Run development diagnostics on sequence `01`, freeze the output procedure
   and HMM parameters.
4. Run one locked sequence-`02` evaluation, publish the full artifact and issue
   `PASS` or `REVISE`.

## Scope boundary

Stage C establishes technical uncertainty propagation through migration and
image-derived state summaries on U373. It does not justify SLDS, Koopman or
other operator learning; those remain a separate Stage D decision after this
gate. It does not validate any claim about GlioTrace brain-slice biology.

## Final decision

The one-time locked sequence-`02` evaluation passed the invariant,
non-inferiority and completeness gates but failed the registered 90% mean-speed
interval-coverage gate (0/17 scenarios covered the reference). Stage C is
therefore `REVISE`; see [`stage-c-final-report.md`](stage-c-final-report.md).
