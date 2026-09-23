# Stage B final report — context-aware posterior

Date: 2026-09-19. Decision: **PASS**.

## Registered decision

The Stage A candidate graph and configuration `m2.75-d0-c4-n10-p0.7` remained
unchanged. Exact one-to-one component marginals used the registered link and
new-track potentials. Calibration was fitted on the 17 development scenarios of
sequence `01` and frozen at temperature `0.55` for both exact and sampled
posteriors before the single locked sequence-`02` evaluation.

| Sequence | Method | Brier | ECE | NLL |
| --- | --- | ---: | ---: | ---: |
| 01 (development) | Exact context | 0.06743 | 0.14010 | 0.21856 |
| 01 (development) | Stage A sampled | 0.06978 | 0.14254 | 0.22784 |
| 02 (locked test) | Exact context | 0.03859 | 0.09453 | 0.13872 |
| 02 (locked test) | Stage A sampled | 0.04163 | 0.09868 | 0.14889 |

All decision gates passed on both sequences:

- exact target-conservation and source-capacity invariants;
- exact resource bound (maximum component size: 2 targets, below the limit of
  18); and
- calibrated Brier non-inferiority (tolerance `0.005`) and ECE
  non-inferiority (tolerance `0.02`) relative to the sampled comparator.

The locked sequence had 11,781 exact components and a maximum of seven
enumerated matching states in a component. No approximation or resource-bound
violation occurred.

## Evidence and scope

[`stage-b-locked-evaluation.json.gz`](stage-b-locked-evaluation.json.gz) is the
compressed machine-readable final artifact with all component partitions, link
marginals, comparator probabilities, calibration metrics and gate decisions.
The reproducibility workflow publishes the uncompressed JSON as a run artifact.

Stage B is complete. It establishes technically calibrated, graph-consistent
association uncertainty on the U373 benchmark only. It does not validate any
biological claim about GlioTrace. The next research stage is Stage C:
propagating this uncertainty into migration and latent-state summaries.
