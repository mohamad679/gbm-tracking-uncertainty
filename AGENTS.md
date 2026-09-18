# Research project instructions

Objective: Determine whether uncertainty in segmentation and cell tracking changes estimates of migration and image-derived morphological-state dynamics in glioblastoma live-cell imaging.

## Workflow

- Work on exactly one research stage at a time. Stage 0 is data feasibility only.
- Delegate independent read-heavy tasks to at most three subagents. Assign one owner per file for write-heavy tasks; use separate Git branches or worktrees for overlapping changes.
- Each task must specify inputs, outputs, file ownership, a reproducible check, and a time budget.
- Do not launch Stage 1 until the Stage 0 gate includes actual image inspection and a documented GO decision. Stage 1 must produce the independently reviewed manual track subset before any uncertainty or dynamics model. Continue work within the user's existing project authorization when gates pass; ask only when required account or independent human input is unavailable.
- At every gate, return the evidence, exact commands, unexpected failures, remaining unknowns, cost so far, and GO / REVISE / STOP recommendation.

## Scientific safeguards

- Record the data source, version, archive hash, acquisition time unit, pixel scale, mouse ID, sequence ID, and annotation provenance.
- Keep raw data outside Git. Do not change raw source files or publish them in this repository.
- Split train/validation/test by mouse or independent sequence; never randomly split adjacent frames of the same sequence.
- Never claim a probability distribution over tracks from uncalibrated association scores.
- Image-derived morphological states are not experimentally validated biological phenotype states.
- A passed software check does not establish a biological result.
- Differentiate tracking uncertainty conditional on fixed segmentation from full segmentation-plus-tracking uncertainty.
- Start with manual pilot annotations, a simple tracker, and a frozen evaluation protocol. Add SLDS, Koopman, and GL261 only after a measured need arises.
