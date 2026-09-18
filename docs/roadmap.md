# Gated research roadmap

No gate passes on generated code alone. Every stage ends in a dated evidence report and a GO / REVISE / STOP decision.

| Stage | Output | Gate |
| --- | --- | --- |
| 0. Source and data audit | Reproducible inventories, small real samples from both mice, time and crop diagnostics, hardware and data-rights assessment | GO only to a limited annotation pilot if real brain-slice frames are accessible and some cells are visually trackable. |
| 1. Manual pilot | Easy and difficult short windows from both mice, reviewed identity links, annotation disagreements, missing/cropped pixels | GO to a baseline only if enough unambiguous tracks survive and reference construction is reproducible. |
| 2. Baseline | Frozen mouse/sequence split; simple segmentation, deterministic tracker, quantitative errors vs manual tracks | Continue if basic tracking is viable and failure modes are documented. |
| 3. Uncertainty | Multiple globally compatible track hypotheses and calibration on held-out data | Continue only if uncertainty identifies errors better than a simple confidence/abstention baseline. |
| 4. Downstream effect | Migration features and image-defined states, HMM on fixed tracks and uncertain tracks | Report effect size and interval coverage even for a null result. |
| 5. Extension | SLDS or constrained linear operator if baseline diagnostics justify additional complexity | Continue only with improvement on held-out sequences and no leakage. |
| 6. Reproduction and write-up | Reproducible code, provenance, independent test and limitations | Public claims must match the actual evidence and biological sampling. |

The original GlioTrace group already uses morphological classification and HMM. Those are reproduction/baseline components. Novelty must come from measured uncertainty propagation and its effect on conclusions.

Use different mice as independent biological units. A large number of cells inside two mice does not give a large biological sample size.
