# Stage C v2 Step 5: locked T98G evaluation

Date: 2026-09-20. Status: **PASS**.

The registered T98G human-curated variant was evaluated once after the
sequence-01 development artifact was frozen. The evaluator loaded the frozen
localization model, two-state HMM, adaptive graph configuration, 256-member
ensemble configuration, and split-conformal correction. It performed no
refitting or tuning on T98G and did not reuse U373 sequence-02.

The evaluation contains the seven registered corruption families and 17
scenario/severity cases. Each case has 256 exact predictive members. The
parallel execution is only a deterministic batching of members: member `i`
uses the same registered seed `20260920 + scenario_index*1000 + 1 + i` as the
serial sampler would use.

## Decision metrics

| Gate | Result | Requirement |
| --- | ---: | ---: |
| Defined cases | 17 | all cases defined |
| Primary nominal 90% coverage | 16/17 = 0.941176471 | 0.80–0.98 |
| Median v2 absolute error | 1.014881020 px/frame | comparator + 0.10 maximum |
| Median v1 absolute error | 1.136706163 px/frame | frozen comparator |
| v2 − v1 error delta | −0.121825143 px/frame | ≤ 0.10 |
| Median normalized primary width | 0.497254808 | ≤ 1.0 |
| Summary completeness | 1.0 | ≥ 0.95 |
| Provenance/leakage/compatibility/resource invariants | PASS | all pass |

The complete per-scenario artifact is
[`stage-c-v2-t98g-locked-evaluation.json`](stage-c-v2-t98g-locked-evaluation.json).
The archive identity remains the audited Zenodo record and SHA-256
`1b80d50f61efca6729af4ef691adab77d06c358fbda7a73744eb4e9b252abd6c`.

This is a technical 2D T98G tracking uncertainty result, not a biological
validation claim for GlioTrace brain-slice data. Stage C v2 is complete with
PASS; Stage D may now be considered under the roadmap gates.
