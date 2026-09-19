# Research project instructions

Objective: Determine whether uncertainty in segmentation and cell tracking changes estimates of migration and image-derived morphological-state dynamics in glioblastoma live-cell imaging.

## Workflow

- Work on exactly one research stage at a time.
- Delegate independent read-heavy tasks to at most three subagents. Assign one owner per file for write-heavy tasks; use separate Git branches or worktrees for overlapping changes.
- Each task must specify inputs, outputs, file ownership, a reproducible check, and a time budget.
- Stage 0 and the GlioTrace image-feasibility pilot are complete. From the 2026-09-19 pivot onward, quantitative claims must use existing public reference annotations or controlled perturbations. No new human annotation is required. GlioTrace remains an unlabeled exploratory case study and its machine tracks must never be called ground truth.
- At every gate, return the evidence, exact commands, unexpected failures, remaining unknowns, cost so far, and GO / REVISE / STOP recommendation.

## Scientific safeguards

- Record the data source, version, archive hash, acquisition time unit, pixel scale, mouse ID, sequence ID, and annotation provenance.
- Keep raw data outside Git. Do not change raw source files or publish them in this repository.
- Split train/validation/test by mouse or independent sequence; never randomly split adjacent frames of the same sequence.
- Never claim a probability distribution over tracks from uncalibrated association scores.
- Image-derived morphological states are not experimentally validated biological phenotype states.
- A passed software check does not establish a biological result.
- Differentiate tracking uncertainty conditional on fixed segmentation from full segmentation-plus-tracking uncertainty.
- Start with the U373 reference tracks, a simple tracker, and a frozen perturbation/evaluation protocol. Add T98G, SLDS, Koopman, and GL261 only after the preceding gate passes.
