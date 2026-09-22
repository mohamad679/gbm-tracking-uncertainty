# Stage E-Final protocol: multi-domain tracking-uncertainty validation

Date: 2026-09-22. Freeze status: **STEPS 1-3 LOCKED; NO OUTCOMES EVALUATED
AT THE TIME OF THIS PRE-TEST CONTRACT**.

Post-evaluation note: the one-time sequence-`02` evaluation was later executed
under this contract and closed as `REVISE`; see
[`stage-e-final-report.md`](stage-e-final-report.md).

## Scope change

The original Stage E required independently annotated real GBM brain-slice data.
No person is available to create that reference set, and the public GlioTrace
example data do not provide a complete independent tracking reference. Stage E
is therefore closed as a reference-backed **technical** validation study using
existing Cell Tracking Challenge annotations. Stage F biological inference and
Stage G perturbation testing are deferred rather than simulated with
insufficient evidence.

The machine-readable contract is
[`stage-e-protocol.json`](stage-e-protocol.json). It is binding if prose and
machine-readable artifacts ever diverge.

## Registered question and claims

Primary question:

> Does the frozen uncertainty-aware tracking pipeline rank association errors
> and protect downstream motion summaries after bounded sequence-`01`
> calibration when evaluated once on separately locked sequence-`02` data from
> two previously unused real CTC domains?

A `GO` supports only calibrated, sequence-held-out technical generalization
within the GOWT1 fluorescence and HeLa DIC domains. It does not support
calibration-free zero-shot transfer, brain-slice GBM validity, animal-level
biology, a migratory phenotype, treatment effects, or clinical utility.

## Registered data panel

| Dataset | Origin | Sequence `01` | Sequence `02` | Decision role |
| --- | --- | --- | --- | --- |
| Fluo-N2DH-GOWT1 | Real fluorescence | Development/calibration | Locked test | Confirmatory |
| DIC-C2DH-HeLa | Real DIC | Development/calibration | Locked test | Confirmatory |
| Fluo-N2DH-SIM+ | Computer-generated fluorescence | Parser/metric development | Locked diagnostic test | Diagnostic only |

The exact source URLs, archive sizes, SHA-256 identities, acquisition metadata,
annotation types and structural counts are frozen in
[`stage-e-dataset-manifest.json`](stage-e-dataset-manifest.json). U373, T98G
and Huh7 are explicitly excluded from new confirmation because they were
consumed in earlier stages.

## Leakage boundary

Sequence `01` may be used for implementation debugging, registered baselines,
bounded uncertainty calibration and threshold selection. Before the evaluator
and all sequence-`01` fitted values are committed with passing CI, sequence
`02` may be inspected only structurally: names, counts, shapes, archive identity
and schema validity. Coordinates, motion summaries, tracking outcomes and
performance metrics remain forbidden.

The immutable assignment and unlock conditions are in
[`stage-e-split-lock.json`](stage-e-split-lock.json). A locked sequence cannot
be replaced after an outcome is observed. SIM+ cannot satisfy or rescue a
real-data gate.

## Development implementation addendum

Before any Sequence `02` coordinate or outcome access, the generic CTC
implementation evaluates only Sequence `01` using the fixed maximum-speed grid
`0.20, 0.35, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00` µm/min. It selects the value
with highest clean nearest-neighbour link F1; exact ties select the lower speed.
The registered uncertainty model uses 64 one-to-one hypothesis samples and a
proposal temperature of `max(radius / 2, 0.5)` pixels. Temperature scaling is
fit only on Sequence `01` corrupted-development scenarios. This addendum is
part of the pre-test implementation freeze and does not alter the question,
endpoints, split or decision gates.

For the registered association-error AUPRC, an error is the positive class:
the score is `1 - correct-link confidence` and the label is `1 - true_link`.
This direction is fixed before test access. The one-time sequence-`02` command
uses the frozen configuration in `stage-e-development-fit.json`, the clean
registered scenario `clean_0`, and a calibrated posterior-link threshold of
`0.5`; links are retained greedily only when one-to-one compatible. The
execution lock is [`stage-e-sequence02-evaluation-lock.json`](stage-e-sequence02-evaluation-lock.json).

## Registered comparisons and endpoints

Comparators:

1. nearest-neighbour hard linking;
2. distance-derived confidence;
3. frozen uncalibrated uncertainty pipeline;
4. sequence-`01`-calibrated uncertainty pipeline.

Primary endpoints are association-error AUPRC and selective link risk at 80%
coverage. Secondary endpoints include Brier score, ECE, NLL, LNK, TRA,
complete-track fraction, fragmentation and four motion-summary errors: mean
speed, total path length, net displacement and directionality.

## Frozen decision rule

`GO` requires every provenance, leakage, compatibility and reproducibility
requirement plus all of the following:

1. calibrated error-detection AUPRC is strictly above the distance-confidence
   baseline on both real locked tests;
2. link risk at 80% coverage is strictly below full-coverage risk on both real
   locked tests;
3. calibrated Brier score is no worse on either real test and mean ECE across
   the two tests improves;
4. uncertainty-aware motion summaries beat hard tracking in at least five of
   the eight registered dataset-endpoint comparisons.

`REVISE` is a valid mixed or negative result when the run is valid but a GO gate
fails. It does not authorize tuning on sequence `02`. `STOP` applies to leakage,
provenance, compatibility, exact-reproduction or required-output failure.

Every decision leaves the biological claim unsupported.

## Execution order frozen before outcome access

1. implement the generic CTC parser, registered baselines and metrics without
   reading locked outcomes;
2. audit all three archives structurally and freeze sequence-`01` fitted values;
3. require green CI and commit the complete evaluator;
4. run each sequence-`02` evaluation once;
5. publish all outcomes, issue `GO`, `REVISE` or `STOP`, and prepare the final
   reproducible release.
