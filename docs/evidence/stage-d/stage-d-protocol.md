# Stage D protocol: uncertainty-aware operator learning

Date: 2026-09-21. Status: **STEP 4 COMPLETE — HOLD; NO INDEPENDENT EVALUATION SOURCE**.

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
3. **Fit development models and check stability.** **Complete.** Fit only on
   sequence `01`, use leave-one-track-out diagnostics inside that development
   source, and record calibration, spectral/stability diagnostics, rollout
   bounds and exact reproducibility.
4. **Run the one-time held-out evaluation.** **Complete as HOLD.** No newly
   audited independent operator-evaluation sequence is available. U373
   sequence `02` and T98G are already-consumed locked sources and cannot be
   reused; no held-out metric was fabricated or inferred.

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

Step 2 added the declarative candidate registry, truth/source-boundary checks,
the frozen-HMM speed baseline, the uncertainty-weighted empirical transition
baseline, and the stable linear Koopman operator. Step 3 fit all candidates on
749 truth-blind velocity transitions from U373 sequence `01`, evaluated
leave-one-track-out stability and nominal 90% residual coverage, and found
finite bounded rollouts for every candidate and fold. No candidate was selected
from these development diagnostics; performance remains HOLD until Step 4.
The complete machine-readable result is
[`stage-d-development-fit.json`](stage-d-development-fit.json).

## Final Step 4 decision

Step 4 produced [`stage-d-heldout-decision.json`](stage-d-heldout-decision.json).
The evaluation was attempted zero times and no candidate was selected. The
decision is **HOLD**, exactly as required when an independent held-out source
is unavailable. A future continuation requires a new dataset to pass a
data-only provenance/schema audit and be locked before any operator fitting or
one-time evaluation. Stage D therefore ends here with a technical HOLD, not a
performance success or biological claim.

## Later continuation

This v1 artifact remains immutable historical evidence. Stage D v2 added the
independent CTC Huh7 source and recorded an honest zero-shot `HOLD`. Stage D v3
then calibrated a bounded blend on consumed Huh7 sequence `01` and obtained a
qualified `GO` on previously locked sequence `02`. See
[`stage-d-v3-final-report.md`](stage-d-v3-final-report.md). The later result has
a narrower post-calibration claim and does not overwrite this v1 decision.
