# Gated research roadmap — human-independent revision

Decision date: 2026-09-19. The project is not restarting. Stage 0 artifacts and the GlioTrace pilot are retained, but the quantitative core now uses existing public reference annotations and controlled corruptions. No machine or LLM review is treated as human ground truth.

No gate passes on generated code alone. Every stage ends in a dated evidence report and a GO / REVISE / STOP decision.

| Stage | Output | Gate |
| --- | --- | --- |
| 0. Source and data audit | Reproducible inventories, small real samples from both mice, time and crop diagnostics, hardware and data-rights assessment | GO only to a limited annotation pilot if real brain-slice frames are accessible and some cells are visually trackable. |
| 1. Reference benchmark | Freeze U373 sequences and parse images, tracking masks and lineage tables; add T98G only after its schema is audited | GO when reference identities, centroids and lineage intervals reproduce deterministically and tests pass. |
| 2. Controlled error benchmark | Generate seeded missed detections, localization noise, fragments, ID swaps, false positives and wrong links from held-out reference tracks | GO when each corruption has a known truth record, monotonic severity and leakage-free configuration. |
| 3. Tracking baseline | Evaluate a deterministic tracker and an oracle-corruption baseline on frozen sequence-level splits | Continue if metrics recover injected errors and failure modes are documented. |
| 4. Uncertainty | Calibrate confidence/abstention and compatible track hypotheses on validation sequences | Continue only if uncertainty predicts held-out errors better than simple baselines. |
| 5. Downstream dynamics | Compare migration summaries and image-derived states using fixed, corrupted and uncertainty-aware tracks; start with HMM | Report sensitivity curves, effect sizes and interval coverage even for a null result. |
| 6. Operator extension | Add SLDS or a constrained Koopman/linear operator only if Stage 5 diagnostics justify complexity | Continue only with held-out improvement, stability checks and no leakage. |
| 7. GlioTrace case study | Apply the frozen pipeline to real brain-slice ROIs; publish code and aggregate diagnostics, not unlicensed images | Qualitative/exploratory only; no tracking-accuracy or validated-phenotype claim without reference labels. |
| 8. Reproduction and write-up | Reproducible environment, provenance, tests, model cards and limitations | Public claims must match reference-backed evidence and distinguish technical benchmarking from brain-tissue biology. |

The original GlioTrace group already uses morphological classification and HMM. Those are reproduction/baseline components. Novelty must come from measured uncertainty propagation and its effect on conclusions.

The main claim is technical: how known tracking errors propagate into migration and latent-state inference, and whether calibrated uncertainty reduces that damage. U373/T98G do not validate brain-slice biology. Use different mice as independent biological units in any future biological comparison; many cells inside two mice do not create a large biological sample size.

## Current research-stage progression

Research Stage A, the adaptive candidate-recall breakthrough, is complete and
passed its locked U373 evaluation. Research Stage B is also complete and passed
its one-time locked U373 evaluation: it replaces independent or sampled link
frequencies with exact graph-context marginalized posterior probabilities while
preserving the frozen Stage A candidate graph. Its final evidence is
[`stage-b-final-report.md`](stage-b-final-report.md).

Research Stage C completed its one-time locked evaluation with a `REVISE`
decision. Exact trajectory ensembles passed invariant, accuracy
non-inferiority and completeness gates, but their mean-speed intervals covered
the sequence-`02` reference in 0/17 scenarios. The result and required revision
boundary are documented in [`stage-c-final-report.md`](stage-c-final-report.md).

Stage C v2 is active under the pre-development protocol in
[`stage-c-v2-protocol.md`](stage-c-v2-protocol.md). It adds explicit
localization and proposal-recovery uncertainty plus development-only predictive
calibration. U373 sequence `01` is the sole development source; sequence `02`
may not be reused for selection. The T98G data-only audit passed and its sole
qualifying human-curated sequence is now `LOCKED_UNEVALUATED`; see
[`stage-c-v2-step2-t98g-audit.md`](stage-c-v2-step2-t98g-audit.md).

Stage C v2 passed its locked T98G gate. Stage D v1 then ended with a technical
`HOLD` because no new independent operator-evaluation source was available.
The official CTC Huh7 archive subsequently passed a data-only audit. Its
zero-shot sequence-`01` evaluation improved velocity RMSE but remained `HOLD`
because mean speed was strongly underestimated.

Stage D v3 used the consumed Huh7 sequence `01` for a bounded blend calibration
and evaluated the frozen result once on previously locked sequence `02`. The
blend passed every pre-registered predictive, non-inferiority, calibration,
stability, leakage and reproducibility gate, producing a qualified technical
`GO`. The supported scope is within-Huh7 sequence generalization after
one-sequence calibration. U373 sequence `02` and T98G were not reused, the
zero-shot result remains `HOLD`, and no Stage B, C or D result is biological
validation. See [`stage-d-v3-final-report.md`](stage-d-v3-final-report.md).
