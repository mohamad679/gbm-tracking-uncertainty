# Stage B protocol: context-aware posterior

Date: 2026-09-19. Status: **FROZEN — PASSED 2026-09-19**

## Research question

Given the Stage A locked, truth-blind adaptive candidate graph, can exact
graph-context marginalization produce globally compatible link probabilities
without degrading held-out probability calibration relative to the existing
sampled one-to-one posterior?

Stage B changes uncertainty inference only. It does not change the Stage A
candidate graph, its locked configuration, the corruption suite, or downstream
biological interpretation.

## Fixed input and comparators

- The Stage A configuration is fixed as `m2.75-d0-c4-n10-p0.7`.
- Candidate edges are generated exactly as in Stage A and remain truth-blind.
- Link potential for a candidate edge `(i, j)` is
  `exp(-proposal_score_px / 4.0)`.
- The unmatched-target (new-track) potential is `exp(-10.0 / 4.0)`.
- The primary comparator is the Stage A sampled one-to-one posterior using the
  same candidate graph, link scores and new-track score.

No reference identity, reference link, corruption label or downstream metric
may be read while constructing candidate graphs or uncalibrated potentials.

## Context-aware posterior definition

Each adjacent-frame candidate graph is partitioned into independent connected
bipartite components. Within each component, the posterior is the normalized
distribution over all one-to-one matchings plus unmatched-target choices. A
candidate-link marginal is the summed probability of every compatible matching
that contains that edge.

This replaces independent or finite-sample link frequencies with graph-level
marginals: competing links to the same source or target reduce one another's
probability through the shared matching distribution.

The implementation must be exact for every evaluated component. It may not
silently fall back to independent probabilities or Monte Carlo sampling. The
initial exact-computation resource bound is 18 targets per connected component.
A component that exceeds this bound yields `REVISE` until a separately versioned
inference method is approved.

## Leakage control and evaluation roles

- Sequence `01` is the development sequence. Only it may fit one scalar
  probability-temperature calibration after raw context marginals are made.
- Sequence `02` is the locked test sequence. It is evaluated once after the
  implementation, resource bound and calibration procedure are frozen.
- All 17 seeded corruption scenarios are retained. Their truth is evaluation
  material, never an inference input.
- Stage B does not tune the Stage A candidate configuration or posterior floor.

## Required artifact contract

For every scenario and sequence, the Stage B artifact records:

1. the fixed Stage A configuration and candidate-graph method;
2. context posterior link marginals and the component partition;
3. exact partition-function diagnostics and maximum component size;
4. invariant checks: each target has incoming-link mass plus new-track mass of
   one (within numerical tolerance), and every source has outgoing-link mass
   no greater than one;
5. raw and development-calibrated Brier score, expected calibration error and
   negative log likelihood, alongside the sampled-posterior comparator.

## Frozen Stage B decision rule

Stage B is `PASS` only when all conditions hold on both sequences:

- every exactness and marginal-conservation invariant passes;
- no resource-bound violation or hidden approximation occurs;
- calibrated context-posterior Brier score is no greater than the sampled
  comparator plus `0.005` on each sequence; and
- calibrated context-posterior ECE is no greater than the sampled comparator
  plus `0.02` on each sequence.

The tolerances allow finite precision and make the gate a non-inferiority
test, not a post-hoc demand for a particular numerical improvement. A failed
condition is `REVISE`; Stage C downstream propagation and any operator work
remain unchanged.

## Implementation sequence

1. Implement an exact component-level matching enumerator and invariant tests.
2. Add a Stage B evaluator that compares exact context marginals with the
   existing sampled posterior using the fixed Stage A graph.
3. Fit calibration on sequence `01`, freeze it, then run one locked evaluation
   on sequence `02`.
4. Publish the machine-readable artifact, report and `PASS`/`REVISE` decision.

## Scope boundary

Stage B establishes graph-level association uncertainty. Propagating that
uncertainty into speed, persistence and state transitions belongs to Stage C.
It remains a controlled U373 technical benchmark and does not validate
biological claims for GlioTrace brain-slice data.

## Final decision

The one-time locked sequence-`02` evaluation was run after the development
calibration temperature of `0.55` was frozen. All registered invariants,
resource-bound and calibrated Brier/ECE non-inferiority gates passed on both
sequences. Stage B therefore passed. The complete result is in
[`stage-b-final-report.md`](stage-b-final-report.md).
