# Stage D v2 protocol: independent Huh7 operator evaluation

Date: 2026-09-21. Status: **FROZEN BEFORE OUTCOME INSPECTION**.

Stage D v1 ended with `HOLD_NO_INDEPENDENT_EVALUATION_SOURCE`. This revision
does not alter or overwrite that result. It registers the official CTC
`Fluo-C2DL-Huh7` training archive as a new independent operator-evaluation
source and defines the complete audit, lock, evaluation and decision procedure
before any Huh7 coordinates or predictive outcomes are inspected.

## Source and data-only lock

- Archive URL: `https://data.celltrackingchallenge.net/training-datasets/Fluo-C2DL-Huh7.zip`
- Expected archive size: `38151145` bytes
- Locked SHA-256: `1912658c1b3d8b38b314eb658b559e7b39c256917150e9b3dd8bfdc77347617d`
- Official acquisition metadata: `0.65 µm/pixel`, `15 min/frame`, matching the
  U373 operator units used by the frozen Stage D v1 development fit.
- Selection rule: lock the lexicographically first schema-valid sequence with
  at least two lineage tracks and 100 structural velocity-transition slots.
  The audit may inspect archive identity, dimensions, labels, lineage and
  presence of consecutive frames. It may not extract centroids, calculate
  motion, fit models or expose outcome metrics.

The archive and annotations remain local and ignored by Git. Only the source
URL, hashes, structural audit, code and aggregate evaluation result may be
committed.

## Frozen model and evaluation boundary

All three model families and hyperparameters remain exactly those registered
in Stage D v1. They are reconstructed from U373 sequence `01` and the frozen
Stage C v2 development HMM. Huh7 never enters fitting, calibration, threshold
choice or model selection. U373 sequence `02` and T98G remain forbidden.

The locked Huh7 sequence supplies only one-time evaluation rows. A row is one
pair of consecutive two-dimensional velocity states derived from three
consecutive gold tracking-marker centroids. The uncertainty weight is ignored
during evaluation. Every eligible row is evaluated; no track or row may be
dropped based on an outcome.

## Frozen metrics and decision gates

The sole operator candidate is `stable_linear_koopman_operator_v1`. The frozen
HMM speed baseline and weighted empirical transition baseline are mandatory
comparators.

1. **Primary predictive gate:** candidate one-step velocity RMSE must be
   strictly lower than the RMSE of both baselines.
2. **State-summary non-inferiority:** absolute error of the mean predicted
   next-step speed must be no more than `0.10 px/frame` worse than the best
   baseline.
3. **Interval calibration:** applying the frozen U373-development p90 residual
   radius to Huh7 residuals must yield coverage from `0.80` through `0.98`.
4. **Stability:** ten-step rollouts must be finite, bounded by `1000 px/frame`,
   and the Koopman spectral radius must remain at most `0.98`.
5. **Integrity:** archive, locked member set, development inputs, model
   parameters, counts and complete output must reproduce exactly.

`GO` requires every gate. `REVISE` is limited to a pre-specified implementation
or calibration defect and cannot be used to tune against Huh7. If the code is
valid but the operator fails to add predictive value, the result is `HOLD`.
This remains a technical cross-dataset benchmark, not biological or clinical
validation.
