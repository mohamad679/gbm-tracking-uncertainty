# Stage C v2 sampler implementation

Date: 2026-09-20. Status: **IMPLEMENTATION COMPLETE — DEVELOPMENT RUN PENDING**.

This step implements the registered localization and proposal-recovery layers
for Stage C v2. It is an API and invariant-test step only; it does not fit or
evaluate on T98G and does not read the consumed U373 sequence-`02` test.

## Implemented components

- `fit_localization_model` fits the frozen non-negative affine localization
  scale from development residual rows and truth-blind graph diagnostics.
- `perturb_localization` applies deterministic isotropic coordinate noise while
  stripping reference/truth fields from application observations.
- `build_recovery_graph` retains the frozen adjacent primary graph and adds
  truth-blind adjacent shell proposals plus `delta_t=2` bridge proposals with
  explicit virtual-node identifiers.
- `sample_exact_predictive_matchings` enumerates and samples the combined
  primary/recovery graph under global one-to-one constraints, with the
  approved 18-target exact-inference resource bound.
- `sample_stage_c_v2_ensemble` composes these layers into a deterministic,
  truth-blind predictive ensemble and preserves per-member diagnostics.

## Tests and boundary checks

`tests/test_stage_c_v2_sampler.py` verifies deterministic localization,
truth-field invariance, recovery-shell and bridge construction, global
competition between adjacent and bridge proposals, and explicit resource
bound failure. The full repository suite passes (`106` tests).

No sequence-`02` or T98G observation, reference, metric, or performance
result is included in this implementation artifact. The next execution step
is the registered U373 sequence-`01` development fit and cross-validation;
only after that artifact is frozen may the locked T98G evaluation run.

