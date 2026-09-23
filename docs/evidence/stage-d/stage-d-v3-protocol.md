# Stage D v3 protocol: Huh7-calibrated operator validation

Date: 2026-09-21. Status: **SEQUENCE 02 LOCKED BEFORE DEVELOPMENT FIT**.

Stage D v2 established a genuine zero-shot result: the stable Koopman operator
improved velocity RMSE on Huh7 sequence `01` but failed mean-speed
non-inferiority, so v2 correctly remained `HOLD`. This revision treats the now
consumed Huh7 sequence `01` only as domain-calibration development data and
locks the still unseen Huh7 sequence `02` as the one-time evaluation source.

This changes the claim. A v3 `GO` would mean that a bounded one-sequence Huh7
calibration generalizes to a separate Huh7 sequence. It would not rescue the
v2 zero-shot claim and would not constitute biological or clinical validation.

## Frozen revision

The U373-fitted stable Koopman prediction is blended with the U373-fitted
weighted empirical prediction:

`prediction = λ × Koopman + (1 − λ) × empirical`

The registered grid is `λ = 0.05, 0.10, …, 1.00`. Huh7 sequence `01` selects
the passing value with minimum velocity RMSE; exact ties select the larger
`λ`. A value passes development only when it:

- improves one-step velocity RMSE over both frozen baselines;
- has mean-speed absolute error no more than `0.10 px/frame` above the best
  frozen baseline;
- has finite ten-step rollouts bounded by `1000 px/frame`.

The selected blend's p90 residual radius is then calibrated on Huh7 sequence
`01` and frozen. No sequence-02 coordinate, motion value or outcome may enter
selection or calibration.

## Locked sequence-02 evaluation

Sequence `02` is pinned by member-set SHA-256
`84cb1f20c08574224a773e94b8bf1f745f4bd8139616f33a46566cb8c7658183`.
Its structural audit contains 30 frames, 69 lineage tracks and 1481 available
velocity transitions. These counts were obtained without extracting centroids
or calculating motion.

The one-time sequence-02 `GO` gates remain:

1. blended candidate RMSE strictly below both frozen baselines;
2. mean-speed absolute error within `0.10 px/frame` of the best baseline;
3. frozen sequence-01 p90 interval coverage between `0.80` and `0.98`;
4. finite bounded ten-step rollouts;
5. exact provenance, leakage-boundary and artifact reproducibility.

`GO` requires all gates. Valid failure is `HOLD`. `REVISE` is reserved for a
pre-specified implementation defect and cannot authorize sequence-02 tuning.
