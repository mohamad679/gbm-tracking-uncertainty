# Portfolio Summary

## Problem

Tracking errors in time-lapse microscopy can alter downstream migration and latent-state estimates. This project asks whether those effects can be measured reproducibly and whether calibrated association uncertainty is sufficient to support more advanced operator-learning models.

## Engineering approach

The repository builds a deterministic technical benchmark from expert U373 tracking masks and lineages, injects controlled tracking corruptions, evaluates a frozen baseline, samples one-to-one association hypotheses, calibrates posterior link probabilities, and propagates those representations into migration and two-state dynamics summaries.

The implementation treats intermediate JSON artifacts as explicit contracts. Reference identity, schema version, corruption seed, scenario IDs, and sequence IDs are validated across stages. Reproducibility is enforced with pinned constraints, Python 3.11-3.13 CI, package-build smoke tests, runtime provenance, and a full real-data reproduction workflow.

## Correctness work

The audit found and fixed several classes of defect:

- a local `wrong_link` corruption incorrectly behaved like a persistent ID switch;
- downstream stages relied on positional scenario order instead of IDs;
- an empty appearance descriptor violated its fixed dimensionality contract;
- HMM transition estimation could produce invalid zero rows when evidence was absent;
- final decision gates and test counts contained hard-coded reporting logic.

Each correctness fix was paired with regression or contract tests and followed by a real-data U373 rerun when numerical behavior could be affected.

## Architecture and performance

Shared configuration, calibration, numerical utilities, artifact validation, and ZIP safety were separated into focused modules. The main soft-dynamics transition hotspot was changed from an all-pairs O(E^2) scan to indexed adjacency traversal. An equivalence test compares the optimized accumulation directly with the previous quadratic definition.

## Evidence

At the v0.2.0 Stage D closure state:

- 133 tests pass locally, with Python 3.11-3.13 CI and a 65% coverage gate;
- the wheel builds and reinstalls successfully;
- the complete pinned U373 reproduction succeeds;
- the technical benchmark is complete;
- Stage D v3 passes all seven locked gates on 1481 Huh7 sequence-`02`
  transitions after bounded calibration on sequence `01`;
- no biological validation claim is supported.

The earlier zero-shot Stage D v2 `HOLD` remains part of the evidence: its
Koopman candidate improved velocity RMSE but underestimated mean speed. The
current `GO` is deliberately narrower and supports within-Huh7 sequence
generalization after one-sequence calibration. It does not support zero-shot,
brain-slice biological, GBM-wide, or clinical generalization.

## Why this project is portfolio-relevant

The work demonstrates software-engineering and research-engineering skills together: code review, failure-mode analysis, deterministic benchmarking, uncertainty calibration, scientific safeguards, contract validation, performance optimization, CI/CD, packaging, reproducibility, provenance, and evidence-based scope control.
