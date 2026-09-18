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
