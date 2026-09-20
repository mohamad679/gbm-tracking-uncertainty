# Stage C v2 protocol: calibrated predictive trajectory uncertainty

Date: 2026-09-20. Status: **FROZEN — TEST MANIFEST LOCKED UNEVALUATED**.

## Reason for revision

Stage C v1 produced valid one-to-one association ensembles, but its nominal
90% mean-speed intervals covered the locked U373 sequence-`02` reference in
0/17 scenarios. The ensemble was conditional on the observed candidate graph:
it represented association ambiguity but not localization error, proposals
missing from that graph, or remaining downstream model discrepancy.

Stage C v2 tests whether adding those omitted uncertainty sources yields useful
predictive intervals without sacrificing central accuracy. It does not change
the completed Stage A or Stage B decisions and does not erase the v1 result.

## Immutable upstream inputs

- Stage A configuration `m2.75-d0-c4-n10-p0.7` remains the primary adjacent-
  frame candidate graph.
- Stage B link potentials, unmatched-target potential and probability
  temperature `0.55` remain frozen.
- The Stage C v1 exact component-matching sampler, 256-member ensemble,
  migration summaries and frozen two-state HMM remain the association-only
  comparator.
- The controlled corruption definitions and corruption-family names remain
  unchanged. A new benchmark instance may use a new registered seed, but its
  construction code may not be selected using test results.

## Development and test boundary

- U373 sequence `01` is the only fitting and model-selection source.
- U373 sequence `02` has already been consumed as the one-time Stage C v1
  locked test. Its observations, references, scenario results and aggregate
  metrics are excluded from every v2 fit, diagnostic threshold, design choice
  and acceptance decision. Its v1 artifact is retained only as historical
  evidence.
- T98G is the candidate independent test dataset named in the roadmap. Before
  any v2 fitting, a data-only audit must verify provenance, rights, checksums,
  parser determinism, sequence identifiers and reference-schema compatibility.
  That audit may report structural counts but may not run tracking, calculate
  migration summaries or inspect v2 performance.
- If the T98G audit passes, every qualifying T98G sequence and its controlled
  corruption benchmark are declared locked by identifier and checksum. The
  registered test corruption seed is `20260920`. If the audit fails, Stage C v2
  stops at `REVISE`; no substitute test set may be chosen after seeing v2
  performance.

## Predictive uncertainty model

The primary v2 output is a **posterior predictive** trajectory ensemble, not an
association posterior alone. Each member is generated in this order.

### 1. Localization layer

Observed coordinates are perturbed by a zero-mean isotropic residual kernel.
Its scale is a non-negative affine function of truth-blind local diagnostics:
the median admissible proposal distance and candidate degree. Coefficients and
the empirical standardized residual distribution are fit only from U373
sequence `01` observation-to-reference residuals. At application time the
layer reads observations and candidate diagnostics only; corruption labels and
reference coordinates are forbidden.

### 2. Proposal-recovery layer

The frozen Stage A graph is retained and marked as the primary graph. A
separate recovery graph may contain:

1. adjacent-frame pairs rejected by the primary spatial gate but lying within
   twice that gate; and
2. one-frame-gap (`delta_t = 2`) bridge pairs lying within twice the frozen
   per-frame gate, with the missing coordinate represented by linear
   interpolation.

Recovery-edge prior mass is estimated from sequence `01` with a fixed
Beta(1,1) estimator. The same Stage B distance potential is used after
normalizing distance per frame. Recovery edges must be labelled in artifacts
and their posterior contribution reported separately. No reference identity
or corruption label may be read while constructing a test recovery graph.

### 3. Compatible association and discrepancy calibration

Primary and recovery proposals are sampled jointly under global one-to-one
constraints. A detection may occur in at most one selected incoming and one
selected outgoing link; a bridge may not conflict with an adjacent link at its
endpoints or interpolated frame. Components above the exact limit of 18 target
nodes cause `REVISE`; there is no silent approximate fallback.

After trajectory summaries are computed, a fixed split-conformal correction
is applied to the nominal 5th/95th interval using absolute out-of-fold
mean-speed residuals from sequence `01`. The held-out units are the seven
corruption families (`clean`, `missed_detection`, `localization_noise`,
`fragmentation`, `id_switch`, `wrong_link`, and `false_positive`), so a family
never calibrates its own residual. The correction quantile is fixed at 90%.
The uncorrected association-only, mechanistic predictive and conformalized
intervals must all be retained; only the conformalized interval is primary.

After the leave-one-family-out artifact is frozen, model coefficients are
refit once on all sequence-`01` scenarios. No v2 parameter is fit or selected
from U373 sequence `02` or T98G.

## Required diagnostics and invariants

Every scenario artifact must retain the dataset/sequence checksum, seeds,
frozen upstream configuration, localization coefficients, recovery prior,
conformal quantile, component sizes, recovery-edge counts and mass, track
counts, effective ensemble size, and all three interval variants.

The run is invalid if any reference field enters test-time proposal generation
or sampling, if any trajectory violates the compatibility rules, if an exact
resource limit is exceeded, or if fewer than 256 valid members are produced.
Undefined short-track summaries remain explicit and are never imputed.

## Locked-test decision rule

Stage C v2 is `PASS` only when all of the following hold on the newly locked
T98G scenario-sequence cases with defined reference mean speed:

1. all provenance, leakage, compatibility, component and ensemble-size
   invariants pass;
2. the primary nominal 90% mean-speed interval covers the reference in at
   least 80% and at most 98% of cases;
3. the median absolute error of the v2 mean-speed median is no worse than the
   frozen v1 exact association-only comparator by more than `0.10` pixels per
   frame on the same cases;
4. the median primary interval width divided by
   `max(reference mean speed, 1.0)` is at most `1.0`; and
5. at least 95% of required summary fields are produced.

The upper coverage bound and normalized-width gate prevent a vacuous wide-
interval pass. Failure of any gate is `REVISE`. Passing is a technical tracking
uncertainty result on reference cell-tracking data, not validation of a
GlioTrace biological phenotype.

## Execution order

1. Audit T98G structure/provenance and publish the locked test manifest without
   running v2 performance evaluation.
2. Implement localization and proposal-recovery sampling with leakage and
   compatibility tests.
3. Fit and cross-validate the v2 model on U373 sequence `01`; publish the full
   development artifact and freeze all fitted values.
4. Run the registered T98G evaluation once, publish the complete artifact and
   issue `PASS` or `REVISE`.

Stage D remains blocked until Stage C v2 passes this gate.

## Execution status

Step 1 of the execution order passed the data-only audit. The human-curated
`T98G_sample` variant is frozen by archive and member hashes in
[`stage-c-v2-t98g-locked-manifest.json`](stage-c-v2-t98g-locked-manifest.json);
the Detectron2 variant is excluded because it is not an independent sequence.
No tracking or downstream performance was evaluated. Implementation may now
proceed to Step 2 while T98G remains locked and unevaluated.

The localization/proposal-recovery implementation in Step 2 is now complete;
its leakage, compatibility, and resource-bound tests pass. See
[`stage-c-v2-step3-sampler.md`](stage-c-v2-step3-sampler.md). The development-only
U373 sequence-`01` fit and cross-validation is also complete, with frozen values
and a compact artifact in
[`stage-c-v2-step4-development-fit.md`](stage-c-v2-step4-development-fit.md).
The only remaining execution step is the one-time registered T98G evaluation.

