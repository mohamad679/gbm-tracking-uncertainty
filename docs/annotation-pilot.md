# Next controlled experiment: manual track feasibility

This is the next gate, not a claim of completed gold-standard validation.

## Frozen pilot selection

- Set 67: thapsigargin 4 µM, experiment 333, ROI 84, 65 actual image frames, delta 1.45.
- Set 68: thapsigargin 4 µM, experiment 337, ROI 63, 68 actual image frames, delta 1.35.
- Annotate at least one early and one late **consecutive** window of 8–12 frames for each ROI. Select easy and ambiguous cells in advance; record exclusions and why.
- Use the intersection of nonblack visible regions when analyzing each window. Mark cells leaving the image separately from tracking failure.
- Record `(set, experiment, ROI, frame, provisional_cell_id, x_px, y_px, visible, uncertain, reason)`.
- A second independent reviewer must reconcile ambiguous identities before the data are called a manual reference.
- Before any comparison of treatment effects or phenotype dynamics, inspect and add a control ROI from each mouse; the two currently pinned treated ROIs assess only whether annotation is possible.

## Gate

Report how many identities are unambiguous for at least six consecutive frames per window, how often the two annotations agree on identity, and which errors arise from cropped field, weak signal, or overlapping objects. Only then freeze the split and run the first tracker. A model reviewing its own auto-generated tracks does not supply an independent ground truth.

Do not use pixel coordinates as µm or `delta` as hours until spatial and temporal units have been verified from experimental documentation.

## Local viewer

After installing the package and fetching the two pinned ROI files, prepare the private reviewer package:

```bash
python -m gbm_audit.pilot --output-dir results/stage1-viewer
```

Open `results/stage1-viewer/index.html` in a browser. Each reviewer must use a different reviewer ID, select the tumour channel first, and independently click approximate cell centers. Use `Hard / crowded`, `Uncertain link`, `Mark occluded`, or `Mark left view` whenever appropriate. Download one CSV per reviewer. Do not place `results/stage1-viewer/` or annotation CSVs in Git; they contain derived image material and human labels.

The four fixed windows are Set 67 early frames 5–14 and late frames 50–59, and Set 68 early frames 5–14 and late frames 53–62. The viewer records original 501 × 501 pixel coordinates and the source SHA256. It is a recording aid, not a segmentation or tracking model.

Two people must submit independent CSVs before either sees the other's labels. A third adjudication pass records the final identity links and reasons for disagreements. If only one person is available, label the result intra-rater and keep the gate at **REVISE**; do not call it ground truth.

The user also requested that machine suggestions be prepared first. This is possible privately: run `python -m gbm_audit.proposals` followed by `python -m gbm_audit.overlay` after generating the viewer. The CSV and diagnostic PNGs remain ignored under `results/`. To limit anchoring, a specialist should still submit an **image-only** CSV before inspecting machine suggestions, then note and adjudicate disagreements. This machine-first preparation plus one human reviewer does not become two independent human raters; the original gate stays **REVISE**.
