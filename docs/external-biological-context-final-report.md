# External biological-context validation — final report

Date: 2026-09-23

Status: **bounded external glioma-explant transfer evaluation complete**. The original three-experiment Dryad confirmatory arm remains technically blocked by public file-download authorization and is therefore **not** claimed as completed biological validation.

## 1. Pre-outcome integrity

The initially selected source was Dryad `doi:10.5061/dryad.s4d28`, containing three independent rat PDGFB-driven glioma brain-slice experiments. Public metadata were available, but both tested public file-download routes returned authorization errors in GitHub Actions (HTTP 403 and HTTP 401). No Dryad file content or method-performance outcome was accessed before the fallback decision.

Before any fallback method-performance calculation, the repository froze an access amendment, source commit, file hashes, parser rules, physical-unit conversion, candidate-speed rule, hypothesis count, posterior threshold, calibration temperature and seed in `external-biological-context-protocol-amendment.json`. A separate schema-only workflow verified the source structure before scoring.

## 2. Reproducible fallback source

The accessible fallback is the public `NPA_stich_3` TrackMate example from `smotsch/analysis_glioma`, fixed at commit `265285a03d87f3bf3275a0e78db1336570126bf4`. The associated biological context is a mouse NPA glioma explant-slice time-lapse model.

The reference is an **independent TrackMate trajectory set, not manual gold-standard tracking**. It therefore supports a technical transfer/agreement analysis in an independent glioma-explant context, not a definitive tracking-accuracy or population-level biological validation.

Source scale:

- 3,759 source trajectories;
- 173,456 trajectory observations;
- frames 0–292;
- frame interval 598.54199 s;
- 168,116 consecutive reference links.

All source files are SHA-256 pinned by the evaluator.

## 3. Frozen no-retuning transfer configuration

No parameter was fit on the external outcome.

- maximum speed gate: `1.5 µm/min`;
- resulting link radius: `14.96354975 µm`;
- proposal temperature: `7.481774875 µm`;
- sampled hypotheses: `64`;
- frozen calibration temperature: `0.25`;
- posterior-compatible tracking threshold: `0.5`;
- random seed: `20260922`.

The candidate graph contained 180,929 edges and retained 99.9958% of consecutive reference links.

## 4. Association uncertainty results

| Endpoint | Distance confidence | Frozen uncertainty |
| --- | ---: | ---: |
| Association-error AUPRC | 0.925169 | **0.997292** |
| Selective risk at 80% coverage | 0.000705 | **0.000000** |
| Brier score | 0.025894 | **0.004479** after frozen calibration |
| ECE | 0.082355 | **0.009541** after frozen calibration |
| NLL | 0.126012 | **0.017868** after frozen calibration |

The uncertainty score transferred strongly as an **error-ranking and calibration signal**. Frozen temperature scaling also improved calibration relative to both the distance comparator and the uncalibrated posterior.

The calibrated full-coverage risk was 0.070857, while risk among the top 80% most confident links was 0.0. This supports the selective-risk use case: confidence can identify a lower-risk subset of associations in this external example.

## 5. Hard tracking reconstruction

The same external example does **not** show that the posterior-threshold tracker is superior to the hard nearest-neighbour reconstruction.

| Tracker | Precision | Recall | Link F1 |
| --- | ---: | ---: | ---: |
| Hard nearest neighbour | 0.999679 | 0.999518 | **0.999598** |
| Uncertainty compatible, calibrated p ≥ 0.5 | 0.999391 | 0.995015 | 0.997198 |

The hard baseline therefore retained the better link-reconstruction F1 under the frozen no-retuning comparison.

## 6. Downstream motion fidelity

Hard nearest-neighbour reconstruction also had lower error on all four registered motion summaries:

| Error endpoint | Hard NN | Frozen uncertainty |
| --- | ---: | ---: |
| Mean-speed absolute error (µm/min) | **0.000214** | 0.003011 |
| Total-path-length relative error | **0.003469** | 0.093968 |
| Net-displacement relative error | **0.002276** | 0.069318 |
| Directionality absolute error | **0.002799** | 0.021701 |

Thus the external result is deliberately mixed: uncertainty is highly informative for association-error ranking, calibration and selective review, but the frozen p=0.5 reconstruction loses recall and degrades motion summaries relative to the already very strong nearest-neighbour baseline.

## 7. Scientific interpretation

This external glioma-explant result strengthens one specific scientific conclusion: **association uncertainty transfers as a useful calibrated confidence/error-ranking signal in an independent glioma biological context without external retuning**.

It does **not** support the stronger conclusion that uncertainty-thresholded reconstruction improves tracking or migration estimates. In this example, hard nearest-neighbour tracking remains better on link F1 and all registered motion-error endpoints.

That mixed pattern is compatible with the previously frozen Stage E `REVISE` conclusion rather than overturning it. Stage E remains immutable.

## 8. Claim boundary

Supported:

- reproducible no-retuning technical transfer to one independent mouse glioma explant example;
- external evidence that the uncertainty score is useful for ranking association errors and selective-risk filtering;
- external evidence that frozen calibration remains effective in this example.

Not supported:

- completion of the originally planned three-independent-experiment Dryad confirmatory arm;
- manual-ground-truth validation on this fallback source;
- population-level biological inference from biological `n = 1`;
- human GBM-wide generalization;
- clinical utility;
- changing the historical Stage E decision from `REVISE`.

The machine-readable frozen result is `external-biological-context-result.json`. The evaluation is reproduced by `.github/workflows/evaluate-external-biological-context.yml`.
