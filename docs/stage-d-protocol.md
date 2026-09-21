# Stage D protocol: uncertainty-aware operator learning

Date: 2026-09-21. Status: **STEP 2 COMPLETE — CANDIDATES IMPLEMENTED; PERFORMANCE HOLD**.

Stage D asks whether a constrained dynamical operator can learn useful state
transitions from the uncertainty-aware trajectory distributions produced by
Stage C v2. It is a technical forecasting and robustness test. It is not a
biological validation of GlioTrace or a clinical claim.

## Four-step execution plan

1. **Freeze protocol and inputs.** Lock the data boundary, baselines, candidate
   model families, leakage rules, stability checks and decision gates. This
   document and [`stage-d-protocol.json`](stage-d-protocol.json) are the frozen
   Step 1 output.
2. **Implement baselines and operator candidates.** **Complete.** Keep the frozen HMM and
   uncertainty-aware empirical transition model as mandatory comparators. Add
   a stable linear Koopman candidate with an explicit spectral-radius
   constraint; SLDS remains deferred until diagnostics justify that complexity.
3. **Fit development models and check stability.** Fit only on development
   sources, use sequence-level cross-validation, and record calibration,
   spectral/stability diagnostics, rollout bounds and exact reproducibility.
4. **Run the one-time held-out evaluation.** Use a newly audited independent
   operator-evaluation sequence. Publish every metric and issue `GO`, `REVISE`
   or `HOLD`; never tune after seeing the held-out result.

## Frozen data boundary

U373 sequence-01 is a development source. U373 sequence-02 is archival-only
because it was already consumed by the earlier v1 test. The T98G sequence is
also locked as the Stage C v2 test and cannot be reused for Stage D fitting or
model selection. Any new operator dataset must pass a data-only provenance and
schema audit before it is locked.

## Required gates

- provenance, sequence roles and hashes reproduce;
- no held-out coordinates, labels, corruption truth or evaluation summaries
  enter fitting or model selection;
- the operator improves the pre-registered primary held-out score over both
  mandatory baselines;
- migration/state-summary error is not more than `0.10 px/frame` worse than
  the best frozen baseline;
- nominal 90% predictive intervals cover `80%–98%` of defined cases;
- rollouts contain no NaN/Inf, unbounded growth, unstable spectral radius or
  compatibility violation over the registered horizon;
- the complete artifact and environment reproduce on CI.

`GO` requires every gate. A bounded, non-leaking correction is `REVISE`; lack
of justified complexity or an independent held-out sequence is `HOLD`.

Step 2 adds the declarative candidate registry, truth/source-boundary checks,
the frozen-HMM speed baseline, the uncertainty-weighted empirical transition
baseline, and the stable linear Koopman operator. No dataset was fit or
selected in this step; performance remains HOLD until Steps 3–4.
