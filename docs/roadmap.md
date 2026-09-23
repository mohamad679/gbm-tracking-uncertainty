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

Research Stage A, the adaptive candidate-recall breakthrough, is complete and passed its locked U373 evaluation. Research Stage B is also complete and passed its one-time locked U373 evaluation: it replaces independent or sampled link frequencies with exact graph-context marginalized posterior probabilities while preserving the frozen Stage A candidate graph. Its final evidence is [`evidence/stage-b/stage-b-final-report.md`](evidence/stage-b/stage-b-final-report.md).

Research Stage C completed its one-time locked evaluation with a `REVISE` decision. Exact trajectory ensembles passed invariant, accuracy non-inferiority and completeness gates, but their mean-speed intervals covered the sequence-`02` reference in 0/17 scenarios. This superseded v1 result is retained in [`archive/stage-c/stage-c-final-report.md`](archive/stage-c/stage-c-final-report.md).

Stage C v2 was executed under the pre-development protocol in [`evidence/stage-c/stage-c-v2-protocol.md`](evidence/stage-c/stage-c-v2-protocol.md). It adds explicit localization and proposal-recovery uncertainty plus development-only predictive calibration. U373 sequence `01` is the sole development source; sequence `02` may not be reused for selection. The T98G data-only audit passed and its sole qualifying human-curated sequence was locked before evaluation; see [`evidence/stage-c/stage-c-v2-step2-t98g-audit.md`](evidence/stage-c/stage-c-v2-step2-t98g-audit.md).

Stage C v2 passed its locked T98G gate. Stage D v1 then ended with a technical `HOLD` because no new independent operator-evaluation source was available. The official CTC Huh7 archive subsequently passed a data-only audit. Its zero-shot sequence-`01` evaluation improved velocity RMSE but remained `HOLD` because mean speed was strongly underestimated. Those historical v1/v2 artifacts are preserved under [`archive/stage-d/`](archive/stage-d/).

Stage D v3 used the consumed Huh7 sequence `01` for a bounded blend calibration and evaluated the frozen result once on previously locked sequence `02`. The blend passed every pre-registered predictive, non-inferiority, calibration, stability, leakage and reproducibility gate, producing a qualified technical `GO`. The supported scope is within-Huh7 sequence generalization after one-sequence calibration. U373 sequence `02` and T98G were not reused, the zero-shot result remains `HOLD`, and no Stage B, C or D result is biological validation. See [`evidence/stage-d/stage-d-v3-final-report.md`](evidence/stage-d/stage-d-v3-final-report.md).

Stage D was formally closed on 2026-09-21. Its historical v1 and v2 `HOLD` artifacts remain immutable evidence, while the current decision is the qualified v3 `GO`. See [`evidence/stage-d/stage-d-closure-report.md`](evidence/stage-d/stage-d-closure-report.md).

The final project stage was re-scoped because no independent annotator is available and no public source supplies complete reference tracks for the GlioTrace brain-slice example. Stage E-Final became a reference-backed multi-domain technical validation using previously unused CTC GOWT1 and HeLa data, with SIM+ as an exact-truth diagnostic. Sequence `01` was assigned to development/calibration and sequence `02` locked for one-time evaluation. The question, claims, endpoints, gates, verified archive manifest and split were frozen before outcome evaluation on 2026-09-22. Stage E-Final was then executed once on sequence `02` and closed with a valid `REVISE`: provenance, leakage, selective-risk, calibration and reproducibility gates passed, while the real-data AUPRC gate and motion-win gate failed. See [`evidence/stage-e/stage-e-protocol.md`](evidence/stage-e/stage-e-protocol.md), [`evidence/stage-e/stage-e-steps1-3-report.md`](evidence/stage-e/stage-e-steps1-3-report.md), and [`evidence/stage-e/stage-e-final-report.md`](evidence/stage-e/stage-e-final-report.md).

Stage F biological inference and Stage G perturbation testing remain deferred future studies requiring independent biological replicates and purpose-specific biological hypotheses. They are not completion requirements for the current technical project and cannot be claimed from the Stage E-Final benchmark or the later Dryad transfer exercise.

The project was formally closed at `v1.0.0` as a technical/research-engineering portfolio artifact. The original closure and release scope are recorded in [`project-closure-report.md`](project-closure-report.md) and [`evidence/release/release-notes-v1.0.0.md`](evidence/release/release-notes-v1.0.0.md).

## Post-closure external technical-transfer extension — complete

After the `v1.0.0` technical closure, the repository added a bounded external glioma-context validation extension without reopening or retuning Stage E.

An initial fallback evaluation used an independent TrackMate reference from one mouse glioma explant example. It produced mixed evidence: uncertainty transferred strongly as a confidence/error-ranking and calibration signal, while hard nearest-neighbour tracking retained better hard-reconstruction F1 and motion fidelity. The fallback chronology is preserved under [`evidence/external/`](evidence/external/).

The originally selected Dryad arm (`doi:10.5061/dryad.s4d28`) was subsequently resumed locally after GitHub-hosted download authorization failures. Deposited hashes were verified, the archive was inspected schema-only, and the exact three-experiment tumour-track mapping was committed as `LOCKED` before any Dryad method-performance calculation.

The one-time frozen Dryad evaluation is now complete across three independent rat PDGFB-glioma brain-slice experiments (`100`, `190`, and `50` tumour tracks; biological `n=3`). The result is again deliberately mixed:

- association-error AUPRC improvement over distance confidence is positive in 3/3 experiments; mean effect `+0.596419`;
- selective-risk benefit is positive in 3/3 experiments; mean effect `+0.079359`;
- uncertainty-compatible `p >= 0.5` link-F1 effect versus hard NN is negative in 3/3 experiments; mean effect `-0.012764`;
- mean-speed, path-length and net-displacement fidelity are worse for the frozen uncertainty-compatible hard reconstruction; directionality is mixed;
- the pre-frozen `1.5 µm/min` candidate gate was not retuned despite reference-link coverage below 100% in each experiment.

This completes the planned post-closure external technical-transfer evidence. It supports calibrated uncertainty as an audit/ranking/selective-review layer in three independent rat glioma brain-slice experiments, but not superiority of the frozen hard tracker. It does **not** constitute human GBM-wide validation, clinical validation, or precise population-level biological inference.

See [`dryad-confirmatory-final-report.md`](dryad-confirmatory-final-report.md), [`evidence/dryad/dryad-confirmatory-schema-lock.json`](evidence/dryad/dryad-confirmatory-schema-lock.json), and the frozen result [`evidence/dryad/dryad-confirmatory-result.json.gz`](evidence/dryad/dryad-confirmatory-result.json.gz).
