# Stage A protocol: adaptive candidate generation

Date: 2026-09-19. Status: **FROZEN BEFORE ADAPTIVE MODEL DEVELOPMENT**

## Research question

Can a truth-blind, uncertainty-conditioned candidate generator retain at least
95% of clean reference links in each U373 sequence while reducing candidate
burden relative to a fixed 16-pixel gate and keeping localization-noise
sensitivity near the fixed 8-pixel baseline?

The 95% threshold is an internal engineering/scientific decision rule, not a
universal cell-tracking standard.

## Leakage control

- Sequence `01` is the development sequence. Adaptive-gate parameters may be
  selected only from this sequence.
- Sequence `02` is the locked test sequence. It is evaluated once after the
  implementation and all parameters are frozen.
- Reference identities may be used only to calculate metrics. Candidate
  generation, motion uncertainty, local density and scoring must not read
  truth fields.
- The corruption seed and existing 17-scenario suite remain unchanged.

## Fixed comparators

All runs use the same hypothesis count, temperature, corruption artifact and
downstream soft-dynamics implementation.

1. distance proposal, fixed radius 8 px (`fixed_8`)
2. distance proposal, fixed radius 12 px (`fixed_12`)
3. distance proposal, fixed radius 16 px (`fixed_16`)
4. one frozen adaptive model (`adaptive_v1`)

Motion, area and appearance may later rank candidate edges. They do not change
the Stage A baseline identities and are not permitted to redefine the metrics.

## Frozen metrics

Metrics are reported separately for every sequence.

1. **Clean true-link recall:** reference consecutive links present in the
   clean candidate graph divided by all clean reference consecutive links.
2. **Clean candidate burden:** candidate edges divided by observations in
   target frames (`frame > 0`).
3. **Localization-noise robustness:** absolute soft mean-speed error under
   `localization_noise_5p0`, plus its deterioration relative to `fixed_8`.
4. **Downstream error:** absolute soft mean-speed error on the clean sequence.

The candidate edge set used for recall, burden, posterior sampling and
downstream propagation must be the same set. The current motion samplers do not
yet satisfy that invariant because their sampled links are summarized against
a separately regenerated fixed-distance edge set. Stage A integration must
remove that mismatch before final evaluation.

## Frozen Stage A success rule

Stage A passes only if all conditions hold in **both** sequences:

- clean true-link recall is at least `0.95`;
- clean candidate burden is at least `20%` lower than `fixed_16`;
- absolute soft mean-speed error under `localization_noise_5p0` deteriorates by
  no more than `1.0 px/frame` relative to `fixed_8`.

A failed condition yields `REVISE`, not a post-hoc threshold change. Full
continuous metric values are reported even when the decision is negative.

## Approval-gated implementation sequence

1. Freeze this protocol and candidate-burden instrumentation.
2. Implement a deterministic, truth-blind adaptive candidate generator v1.
3. Make posterior sampling consume exactly the generated candidate graph.
4. Tune only on sequence `01`, then freeze parameters and code.
5. Run the fixed baselines and one final locked evaluation on sequence `02`.
6. Publish the machine-readable comparison, report and `PASS`/`REVISE` Stage A
   decision.

## Reproduction interface

After the four uncertainty and soft-dynamics pairs exist:

```bash
gbm-candidate-benchmark \
  --run fixed_8 results/uncertainty-8.json results/soft-8.json \
  --run fixed_12 results/uncertainty-12.json results/soft-12.json \
  --run fixed_16 results/uncertainty-16.json results/soft-16.json \
  --run adaptive_v1 results/uncertainty-adaptive-v1.json results/soft-adaptive-v1.json \
  --output results/stage-a-candidate-benchmark.json
```
