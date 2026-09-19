# Stage 2 controlled error benchmark report

Date: 2026-09-19. Status: **GO** to tracking-baseline evaluation after regeneration.

## Correctness update

The implementation was hardened after the original Stage 2 run. `wrong_link` is now explicitly a one-frame local identity swap, while `id_switch` remains a persistent identity swap after the deterministic boundary. The previous implementation shared the persistent-switch branch before applying the local wrong-link edit, so previously generated `wrong_link_1` and `wrong_link_2` artifacts do not have the intended semantics.

`results/` is intentionally not versioned. Regenerate the corruption benchmark and every downstream Stage 3+ artifact with the current source before treating downstream numeric tables as current. Regression tests now verify that `wrong_link` changes only the selected boundary frame and that `id_switch` remains persistent.

## Purpose

This stage creates known, reproducible tracking failures from the frozen U373 reference manifest. It measures robustness and uncertainty calibration without treating a machine or LLM review as ground truth and without requiring new human annotation.

## Input and separation

- Input: `results/u373-reference-manifest.json` from Stage 1.
- Reference manifest digest: `ce4d1dfc805eba0ab15b12de7e3ebef3eab2b23cf2f35ebed59d18a6cd1e0d47`
- Fixed seed: `20260919`.
- Tracker input: `observations` only. It contains frame, position, area and an observed track label; it does not contain `true_track_id`.
- Evaluation sidecar: `evaluation_truth`, containing the original reference identity and whether each reference observation was observed. False positives have `true_track_id=0`.

## Corruption families

| Family | Levels | Controlled effect |
|---|---|---|
| clean | 0 | Frozen reference tracks |
| missed detection | 10%, 25%, 50% | Removes observations per track while retaining at least one observation |
| localization noise | σ=1, 3, 5 px | Perturbs and clips coordinates; reference identity remains known |
| fragmentation | gaps of 1, 3, 5 frames | Removes a central interval and relabels the later fragment |
| ID switch | 1, 2 events | Swaps observed labels persistently after deterministic overlap boundaries |
| wrong link | 1, 2 events | Swaps paired observed labels at one deterministic boundary frame only |
| false positive | 5, 10, 20 per sequence | Adds detections with truth label 0 |

The output contains 17 scenarios across both sequence-level roles. Higher severity is monotonic within each corruption family: removal/gap/event/false-positive counts increase, or localization σ increases. The generated JSON is ignored by Git because it is a derived artifact from the local reference archive.

## Reproduction

```bash
PYTHONPATH=src python3 -m gbm_audit.corruptions \
  results/u373-reference-manifest.json \
  --output results/u373-corruption-benchmark.json \
  --seed 20260919
```

The command is deterministic for the same manifest and seed. Unit tests verify deterministic generation, truth/input separation, known missed-detection and false-positive effects, and the distinct local-versus-persistent association corruptions.

## Gate decision

**GO** to Stage 3 tracking-baseline evaluation after regenerating Stage 2 with the current source. The next stage may run a deterministic association tracker on the observation tables, compare its inferred links with `evaluation_truth`, and report ID switches, fragmentation, link precision/recall, speed error and abstention behavior. Do not tune on the test sequence; sequence 01 is development and sequence 02 is held-out test.

## Limitations

- These are controlled technical perturbations, not a model of every segmentation failure in brain tissue.
- The benchmark evaluates fixed reference detections and track tables; full segmentation-plus-tracking uncertainty remains a later extension.
- U373 remains a 2D technical benchmark and does not validate GlioTrace biology.
