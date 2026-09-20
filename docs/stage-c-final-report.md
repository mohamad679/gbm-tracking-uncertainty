# Stage C final report — uncertainty propagation

Date: 2026-09-20. Decision: **REVISE**.

## Locked evaluation

The registered Stage C procedure was applied once to all 17 corruption
scenarios of locked sequence `02`. The 256-member exact and sampled trajectory
ensembles used the unchanged Stage A graph, Stage B potentials and frozen
development HMM. No parameter, threshold, calibration value or HMM quantity was
fit from sequence `02`.

| Gate | Registered requirement | Result | Decision |
| --- | --- | ---: | --- |
| Ensemble/component invariants | All pass; component size ≤18 | All pass; maximum size 2 | PASS |
| Mean-speed 90% interval coverage | 80%–98% | 0/17 (0%) | FAIL |
| Mean-speed error non-inferiority | Exact ≤ sampled +0.10 px/frame | 1.04051 vs 1.02546 | PASS |
| Required-field completeness | ≥95% | 170/170 (100%) | PASS |

Because the pre-registered coverage gate failed, Stage C is `REVISE` even
though the other three gates passed.

## Failure interpretation

The reference mean speed for sequence `02` is 3.63028 pixels per frame. On the
clean scenario, the exact posterior median was 2.59541 with a 5th/95th interval
of 2.49451–2.69260, which does not cover the reference. Localization-noise
scenarios shifted the posterior in the opposite direction, but none of their
intervals covered the same reference target either.

The matching ensemble represents association ambiguity conditional on the
candidate observations. It does not currently represent candidate-proposal
misses, observation/localization uncertainty or systematic downstream bias.
The intervals are therefore much narrower than the total error relative to the
reference trajectory summary. This is a scientific-model limitation, not an
ensemble-invariant or implementation failure.

## Evidence and consequence

[`stage-c-locked-evaluation.json`](stage-c-locked-evaluation.json) contains all
scenario summaries, frozen parameters, thresholds, gate calculations and
provenance.

Stage D operator learning remains blocked. Any Stage C revision must be designed
and tuned only on development data and must add an uncertainty source capable
of representing proposal/localization error. Sequence `02` has now served its
one-time locked-test role and cannot be reused to select that revision; a new
independent locked test dataset or split is required for a subsequent claim.

This result remains a technical U373 benchmark and supports no biological
phenotype claim for GlioTrace.
