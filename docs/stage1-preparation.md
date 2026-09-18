# Stage 1 preparation record

Date: 2026-09-18. Status: **PREPARED; human annotation not yet performed.**

The repository now contains a deterministic, local-only viewer for four fixed ten-frame windows. The viewer was generated from two already verified GlioTrace ROI files, one from each mouse. It displays the tumour channel and optional vessel channel, records approximate centers in original pixel coordinates, captures visibility and uncertainty reasons, and exports one CSV per reviewer.

## Fixed windows

| Window | Frames | Shared crop fraction | Source SHA256 |
| --- | ---: | ---: | --- |
| Set 67, exp 333, ROI 84, early | 5–14 | 0.8670 | `7878bdb3541d365e96f504be1e7958f2e3b3cca68783f253a2672e264f718b57` |
| Set 67, exp 333, ROI 84, late | 50–59 | 0.7906 | `7878bdb3541d365e96f504be1e7958f2e3b3cca68783f253a2672e264f718b57` |
| Set 68, exp 337, ROI 63, early | 5–14 | 0.6891 | `1c40f8519930e023530b4912c826e7e231f2270aa2c15023c21461783e86a265` |
| Set 68, exp 337, ROI 63, late | 53–62 | 0.5653 | `1c40f8519930e023530b4912c826e7e231f2270aa2c15023c21461783e86a265` |

The crop fraction is a geometric diagnostic, not a tissue-coverage measurement. Set 68 has substantial border loss and must be flagged during annotation. Both sampled ROIs are thapsigargin-treated; they cannot support a treatment comparison. Time and pixel units remain unverified.

## Checks completed

- `python -m gbm_audit.pilot --output-dir results/stage1-viewer` generated all 40 frame pairs and a manifest.
- Six unit tests pass: four Stage 0 checks and two Stage 1 preparation checks.
- No automatic cell detector, tracker, or model-generated identity is included.

## Gate still open

Two independent human reviewers must annotate the four windows without seeing each other’s CSVs. A third pass must adjudicate identity links and preserve disagreements. The operational pilot gate is at least three adjudicated tracklets of at least six consecutive observed frames per window, with blind inter-rater link F1 at least 0.80 on mutually visible opportunities; these are feasibility criteria, not powered biological validation thresholds. If the criteria fail, revise or stop before automatic tracking.
