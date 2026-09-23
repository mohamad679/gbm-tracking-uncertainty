# Portfolio Summary

## Problem

Tracking errors in time-lapse microscopy can alter downstream migration and latent-state estimates. This project asks whether those effects can be measured reproducibly and whether calibrated association uncertainty can support reliable confidence auditing and more advanced downstream models.

## Engineering approach

The repository builds a deterministic technical benchmark from expert U373 tracking masks and lineages, injects controlled tracking corruptions, evaluates frozen baselines, samples one-to-one association hypotheses, calibrates posterior link probabilities, and propagates those representations into migration and two-state dynamics summaries.

The implementation treats intermediate artifacts as explicit contracts. Reference identity, schema version, corruption seed, scenario IDs and sequence IDs are validated across stages. Reproducibility is enforced with pinned constraints, Python 3.11-3.13 CI, package-build smoke tests, runtime provenance and real-data reproduction workflows.

The post-closure external-transfer arm applies the same principles to a difficult third-party biological-context source: deposited hashes are frozen, ZIP/archive hazards are handled explicitly, schema evidence is inspected without outcomes, the exact three-experiment mapping is committed before evaluation, and the frozen method is then run once without external retuning.

## Correctness work

The audit found and fixed several classes of defect:

- a local `wrong_link` corruption incorrectly behaved like a persistent ID switch;
- downstream stages relied on positional scenario order instead of IDs;
- an empty appearance descriptor violated its fixed dimensionality contract;
- HMM transition estimation could produce invalid zero rows when evidence was absent;
- final decision gates and test counts contained hard-coded reporting logic;
- macOS AppleDouble files inside the Dryad archive mimicked workbook suffixes and initially broke schema inventory;
- a blanket compression-ratio guard incorrectly rejected legitimate highly compressible TIFF assets in the hash-verified Dryad archive.

Each correctness fix was paired with regression or contract tests and followed by real-data verification when numerical behavior could be affected.

## Architecture and performance

Shared configuration, calibration, numerical utilities, artifact validation and ZIP safety are separated into focused modules. The main soft-dynamics transition hotspot was changed from an all-pairs O(E^2) scan to indexed adjacency traversal, with an equivalence test against the previous quadratic definition.

The Dryad extension adds a separate local acquisition/schema-audit layer, a hardened archive wrapper, a schema-only evidence probe, deterministic canonical normalization, and a frozen replicate-aware confirmatory evaluator.

## Evidence

At the v1.0.0 technical closure state:

- Python 3.11-3.13 CI and the package coverage gate pass;
- the wheel builds and reinstalls successfully;
- the complete pinned U373 reproduction succeeds;
- Stage D v3 passes all seven locked gates on 1481 Huh7 sequence-`02` transitions after bounded calibration on sequence `01`;
- Stage E-Final completes one locked multi-domain sequence-`02` run and returns a valid `REVISE` because the AUPRC and motion-win gates fail.

The earlier zero-shot Stage D v2 `HOLD` remains part of the evidence: its Koopman candidate improved velocity RMSE but underestimated mean speed. The Stage D v3 `GO` is deliberately narrower and supports within-Huh7 sequence generalization after one-sequence calibration.

Post-release, the originally selected Dryad external glioma arm was completed across three independent rat PDGFB-glioma brain-slice experiments (100, 190 and 50 tumour tracks; biological `n=3`) under a pre-outcome schema lock and the unchanged frozen method.

The external result is intentionally mixed:

- association-error AUPRC uncertainty-minus-distance is positive in 3/3 experiments; mean effect `+0.596419`;
- selective-risk benefit is positive in 3/3 experiments; mean `+0.079359`;
- uncertainty-compatible `p >= 0.5` link-F1 effect versus hard NN is negative in 3/3 experiments; mean `-0.012764`;
- downstream mean-speed, path-length and net-displacement fidelity also favour hard NN; directionality is mixed.

This supports calibrated uncertainty as a confidence/error-ranking and selective-review layer in the external rat glioma context, while rejecting the stronger claim that the frozen uncertainty-compatible hard reconstruction is superior.

No human GBM-wide biological or clinical validation claim is supported, and historical Stage E remains `REVISE`.

## Why this project is portfolio-relevant

The work demonstrates software-engineering and research-engineering skills together: code review, failure-mode analysis, deterministic benchmarking, uncertainty calibration, scientific safeguards, preregistration-style leakage control, third-party archive hardening, schema/provenance locking, replicate-aware statistics, performance optimization, CI/CD, packaging, reproducibility, and evidence-based scope control.
