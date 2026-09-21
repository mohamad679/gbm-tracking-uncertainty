# Stage D Step 3: development fit and stability checks

Date: 2026-09-21. Status: **COMPLETE — DEVELOPMENT STABILITY PASS; PERFORMANCE HOLD**.

This step fits the registered Stage D candidates only on the audited U373
sequence `01` development source. U373 sequence `02`, T98G, and any held-out
operator-evaluation source remain excluded. The input transition rows contain
only the declared two-dimensional observed velocity state and next velocity
state; no track identity, truth label, evaluation-reference field, or
evaluation summary is a model feature.

## Frozen development procedure

- 749 transitions were formed from 8 development tracks.
- The state is `velocity_xy_px_per_frame`.
- The fixed uncertainty weight is
  `1 / (1 + norm(current_velocity))`; it is a pre-fit motion-noise proxy.
- Each candidate was fitted on the full development rows for the frozen
  artifact and in 8 leave-one-track-out development folds for diagnostics.
- The nominal 90% residual radius is calibrated inside each training fold and
  coverage is reported only on that fold's development validation track.
- Every rollout was checked for finite values and a maximum absolute state of
  `1000` over the registered 10-step horizon.

## Development diagnostics

| Candidate | Mean CV RMSE (px/frame) | Mean nominal 90% coverage | Stability |
| --- | ---: | ---: | --- |
| Frozen HMM speed baseline | 7.8632 | 0.8796 | PASS |
| Weighted empirical transition baseline | 8.3041 | 0.8921 | PASS |
| Stable linear Koopman operator | 6.6782 | 0.8910 | PASS |

The full-development Koopman fit has spectral radius `0.3899`, below the
registered `0.98` maximum. All three candidates and all eight folds had finite,
bounded rollouts. These are development diagnostics, not held-out evidence;
the apparent Koopman advantage cannot be promoted or used to tune Step 4.

## Decision and boundary

Step 3 is a technical **development pass**. No candidate selection or
performance decision was made. The Stage D decision remains
`HOLD_PENDING_STEP_4_HELD_OUT_EVALUATION`. Step 4 must use one newly audited
independent operator-evaluation sequence exactly once, publish all metrics, and
issue `GO`, `REVISE`, or `HOLD` without refitting after inspection.

The reproducible machine-readable artifact is
[`stage-d-development-fit.json`](stage-d-development-fit.json).
