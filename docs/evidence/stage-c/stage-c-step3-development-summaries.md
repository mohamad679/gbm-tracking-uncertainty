# Stage C, Step 3 — development migration and state summaries

Date: 2026-09-19. Status: **COMPLETED — development only**.

## Delivered procedure

The evaluator creates 256 trajectory realizations per scenario from both the
exact Stage B component posterior and the Stage A sampled-posterior comparator.
For every realization it reports speed, net displacement, track length,
directional persistence, MSD at lags 1–3, and frozen two-state speed-HMM
occupancy, transitions, switch probability and dwell length. It aggregates
scalars as posterior median with 5th/95th percentile intervals and reports
undefined short-trajectory quantities explicitly.

The HMM was fitted exactly once using the uncorrupted reference trajectories of
development sequence `01` (757 speed observations across 8 trajectories). Its
low/high speed means are 0.199786 and 6.541016 pixels per frame. The fitted
parameters are saved in the development artifact and are not fit from any
corrupted sequence or from sequence `02`.

## Development result

All 17 development scenarios completed with 256 realizations for each method.
Exact and sampled trajectory invariants passed throughout. On the clean
development scenario, the exact posterior produced:

| Summary | Posterior median | 5th–95th percentile |
| --- | ---: | ---: |
| Mean speed (px/frame) | 3.17162 | 3.03583–3.30872 |
| Directional persistence | 0.48536 | 0.44319–0.53042 |
| MSD lag 1 (px²) | 21.62051 | 19.77602–23.59610 |
| HMM switch probability | 0.26920 | 0.24292–0.29674 |

The clean sampled-posterior mean-speed median was 3.16185 pixels per frame.
These development values select no model or threshold and do not constitute a
Stage C decision.

## Artifact and boundary

[`stage-c-development-summaries.json`](stage-c-development-summaries.json)
contains the frozen HMM parameters, all scenario-level posterior summaries,
provenance and the explicit `locked_test_sequence_evaluated: false` marker.

The next step freezes this output schema and performs the one-time sequence-`02`
evaluation against the registered coverage, non-inferiority, completeness and
invariant gates.
