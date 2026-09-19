# Stage 4 uncertainty and hypothesis report

Date: 2026-09-19. Status: **GO** to downstream dynamics sensitivity analysis.

## Frozen uncertainty protocol

For each adjacent-frame candidate edge within 8 px, 64 one-to-one track hypotheses are sampled. Each hypothesis uses the same frame-local distance likelihood, a 4 px sampling temperature, a new-track option, and a deterministic seed derived from the corruption seed, scenario and sequence. The tracker input contains no reference identity fields.

The posterior link probability is the fraction of hypotheses containing the edge. A local distance-only probability is retained as the simple confidence baseline. A single scalar temperature is then fit on development sequence 01 only, using all controlled corruption scenarios, and applied unchanged to held-out sequence 02.

## Held-out results

| Sequence | Raw hypothesis Brier | Calibrated hypothesis Brier | Distance baseline Brier | Raw hypothesis ECE | Calibrated hypothesis ECE | Baseline ECE |
|---|---:|---:|---:|---:|---:|---:|
| 01 development | 0.0696 | 0.0213 | 0.0670 | 0.2334 | 0.0622 | 0.2332 |
| 02 test | 0.0636 | 0.0168 | 0.0612 | 0.2243 | 0.0498 | 0.2246 |

The calibrated hypothesis posterior has lower Brier score than the distance baseline in all 17 held-out scenarios. It also lowers mean ECE on the held-out sequence. Every scenario produced 64 unique sampled hypotheses, so the posterior is not a duplicate deterministic track in this benchmark.

Representative held-out cases:

| Scenario | Calibrated Brier | Baseline Brier | Calibrated ECE | Baseline ECE |
|---|---:|---:|---:|---:|
| clean | 0.0125 | 0.0529 | 0.0388 | 0.2091 |
| 50% missed detections | 0.0104 | 0.0600 | 0.0378 | 0.2225 |
| σ=5 px localization noise | 0.0535 | 0.1219 | 0.1354 | 0.3276 |
| 5-frame fragmentation | 0.0140 | 0.0522 | 0.0408 | 0.2080 |
| 20 false positives | 0.0099 | 0.0529 | 0.0347 | 0.2091 |

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.uncertainty \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --output results/u373-uncertainty-evaluation.json \
  --hypotheses 64 --max-distance-px 8 --temperature-px 4
```

The output stores posterior link probabilities, truth labels in the evaluation section, calibration bins, selective thresholds and the fitted development-only temperature. Its SHA-256 in this run is `05211644b18f1392920a1bf8b40a3ca754f3c43fe7525a723d876f3587584c9c`.

## Interpretation boundaries

- This is a controlled U373 technical benchmark. The result does not establish calibrated probabilities for unlabelled GlioTrace brain-slice tracks.
- The temperature fit uses sequence 01, so sequence 02 remains held out for the reported generalization check. The two sequences are still a small technical sample.
- The current hypotheses condition on fixed detections and candidate edges. Full segmentation uncertainty and learned global operators remain future stages.
- ID-switch and wrong-link perturbations do not change positions; a position-only tracker cannot observe an upstream label error. Those perturbations remain relevant for downstream track-table sensitivity.

## Gate decision

**GO** to Stage 5 downstream dynamics sensitivity. Use the calibrated posterior and the frozen deterministic baseline to estimate migration summaries and latent-state transitions under clean, corrupted and uncertainty-aware tracks. Keep HMM as the first dynamics model; defer SLDS/Koopman until sensitivity results justify them.
