# Stage D v3 Step 2: Huh7 sequence-01 calibration

Date: 2026-09-21. Status: **DEVELOPMENT COMPLETE — PROCEED**.

The frozen 20-value blend grid was evaluated only on the already consumed
Huh7 sequence `01`. Two configurations passed all development gates. The
pre-registered minimum-RMSE rule selected `λ = 0.10`, meaning 10% stable
Koopman prediction and 90% weighted empirical prediction.

The selected development values are:

- velocity RMSE: `5.715863361 px/frame`;
- mean-speed absolute error: `0.101166524 px/frame`;
- calibrated p90 residual radius: `8.970659236 px/frame`;
- ten-step maximum absolute state: `27.201160457 px/frame`;
- development interval coverage: `0.899207248`.

The blend improved RMSE over both frozen baselines, remained within the
`0.10 px/frame` non-inferiority margin relative to the best baseline, and
passed stability. The complete grid and selected configuration are recorded in
[`stage-d-v3-development-fit.json`](stage-d-v3-development-fit.json).

Huh7 sequence `02` was not read by this fit. The selected `λ`, interval radius
and all thresholds are now frozen before the one-time sequence-02 evaluation.
