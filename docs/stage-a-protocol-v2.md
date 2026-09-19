# Stage A protocol v2: spatial candidate burden

Date: 2026-09-19. Status: **FROZEN BEFORE v2 DOWNSTREAM TUNING**

## Reason for revision

Protocol v1 measured total candidate edges against fixed-16. On development
sequence `01`, 95% recall requires at least 720 edges while fixed-16 contains
726, so the 20% reduction gate is mathematically infeasible. The v1 result is
preserved as `REVISE`; this document defines a new, explicitly versioned rule.

## Frozen v2 rules

- Sequence `01` is development; sequence `02` remains locked test.
- Candidate generation remains truth-blind and uses only past observations.
- Clean true-link recall must be at least `0.95`.
- Spatial search-area burden must be at least 15% lower than fixed-16.
- Spatial burden is the mean exact area of the union of the 8-pixel base gate
  and each predicted adaptive source gate, in px² per source with a following
  frame. Reference identities are used only for recall, never for this area.
- The σ=5 localization-noise soft-speed error may deteriorate by at most
  `1.0 px/frame` relative to fixed-8.
- Parameters are selected only on sequence `01`, then frozen before sequence
  `02` is evaluated once.
- If no development configuration passes all three gates, the result is
  `REVISE` and sequence `02` is not evaluated.

The 15% area target is a material spatial-work reduction, chosen as a round
engineering threshold after the v1 edge-count infeasibility proof. It is not a
claim about biological tracking quality.
