# Stage 3 tracking-baseline report

Date: 2026-09-19. Status: **GO** to uncertainty calibration and hypothesis evaluation.

## Frozen protocol

The baseline is a greedy frame-to-frame nearest-neighbour tracker. It uses only `frame`, `x_px`, `y_px` and `area_px`; it ignores the corruption generator's `observed_track_id` and the `evaluation_truth` sidecar. The maximum association distance is fixed at 8 px, and gaps are never bridged. No test-sequence tuning was performed.

Command:

```bash
PYTHONPATH=src python3 -m gbm_audit.baseline \
  results/u373-reference-manifest.json \
  results/u373-corruption-benchmark.json \
  --output results/u373-baseline-evaluation.json \
  --max-distance-px 8
```

## Representative results

| Scenario | Sequence | Detection recall | Link precision | Link recall | ID switches | Fragmentation errors | Complete-track fraction | Mean speed error (px/frame) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| clean | 01 development | 1.000 | 1.000 | 0.791 | 158 | 158 | 0.000 | 0.000 |
| clean | 02 test | 1.000 | 1.000 | 0.891 | 74 | 74 | 0.333 | 0.000 |
| 50% missed detections | 01 development | 0.497 | 1.000 | 0.786 | 40 | 225 | 0.000 | 0.000 |
| 50% missed detections | 02 test | 0.497 | 1.000 | 0.915 | 14 | 182 | 0.000 | 0.000 |
| σ=5 px localization noise | 01 development | 1.000 | 1.000 | 0.382 | 468 | 468 | 0.000 | 6.822 |
| σ=5 px localization noise | 02 test | 1.000 | 0.997 | 0.424 | 392 | 392 | 0.000 | 6.866 |
| 5-frame fragmentation | 01 development | 0.948 | 1.000 | 0.790 | 149 | 157 | 0.000 | 0.000 |
| 5-frame fragmentation | 02 test | 0.929 | 1.000 | 0.891 | 68 | 77 | 0.167 | 0.000 |

The clean result already shows the main technical limitation: all detections are present, but a simple association rule produces many identity switches and fragmented tracks. Higher localization noise sharply reduces link recall and increases speed error. The sequence-level test result is reported without changing the fixed threshold.

## Interpretation boundaries

- These are technical U373 benchmark results, not brain-slice or treatment claims.
- `id_switch` and `wrong_link` corruption scenarios intentionally leave positions unchanged. A position-only tracker cannot detect an upstream label error; those scenarios are reserved for downstream track-table sensitivity analysis.
- False positives are counted in the detection table. The current nearest-neighbour rule often starts isolated tracks for them, so link precision alone does not describe false-positive burden.
- The baseline is a comparator, not the final tracker.

## Gate decision

**GO** to Stage 4 uncertainty evaluation. The baseline is reproducible, has measurable failure modes on clean data, and degrades predictably under controlled noise and missing observations. The next stage must compare confidence/abstention and multiple compatible track hypotheses against this frozen baseline using the held-out sequence.
