# Stage B Step 2: exact context matching engine

Date: 2026-09-19. Status: **COMPLETED; EVALUATION NOT YET RUN**

## Delivered

`context_posterior.py` implements an exact, deterministic enumerator for
one-to-one matchings in every adjacent-frame connected component of a candidate
graph. It consumes only observation IDs, frames, candidate-edge endpoints and
`proposal_score_px`; reference identities are not read.

For each target, the enumerator considers every compatible incoming candidate
link and its new-track alternative. It sums matching weights to produce link
marginals, new-track marginals and source-unmatched marginals. Competing links
therefore directly reduce one another through the same matching distribution.

## Invariants and bound

- incoming link mass plus new-track mass equals one for every target;
- outgoing link mass is at most one for every source;
- all components are exact; no independent-probability or Monte Carlo fallback
  is present;
- the approved initial resource limit is 18 targets per connected component.
  A larger component raises an explicit resource error and cannot silently
  produce an approximate result.

Five new unit tests cover analytic competing-link marginals, score sensitivity,
isolated targets, the resource bound and invalid parameters. The existing suite
is also run unchanged.

## Development-only structural audit

The frozen Stage A graph was generated on sequence `01` across all 17 seeded
scenarios and passed the new exact-inference invariants. It produced 13,361
independent components; the largest contained two targets, well below the
18-target exact bound. Sequence `02` was not inspected in this step.

## Boundary

This step does not fit calibration, compare against the Stage A sampled
posterior, or evaluate the locked test sequence. Those actions belong to the
next Stage B evaluator step.
