# Stage E-Final one-time locked evaluation report

Date: 2026-09-22. Decision: **REVISE**.

Stage E-Final was executed once on the pre-registered sequence-`02` split after
the evaluator, development artifact and one-time execution lock were committed
and merged with passing CI. No sequence-`02` result was used for parameter
selection, temperature fitting, threshold tuning, manual exception handling or
dataset replacement.

The machine-readable result is
[`stage-e-sequence02-evaluation.json`](stage-e-sequence02-evaluation.json).
Its SHA-256 is
`514fae28860f51d57cdda3453ffe6639687f753a7e2ac0ed48d9a1f9d0faa545`.

## Decision gates

| Registered gate | Result |
| --- | --- |
| Provenance and split integrity | PASS |
| Leakage boundary | PASS |
| Calibrated error AUPRC beats distance baseline on both real tests | FAIL |
| Selective risk improves over full-coverage risk on both real tests | PASS |
| Calibration improves under the registered rule | PASS |
| Motion endpoint wins at least 5 of 8 comparisons | FAIL: 4 of 8 |
| Reproducibility fields present | PASS |

Because the run was valid but two pre-registered GO gates failed, the correct
scientific decision is `REVISE`. This result does not authorize tuning on
sequence `02` or replacing the locked test set.

## Clean-scenario primary endpoints

| Dataset | Distance error AUPRC | Calibrated error AUPRC | Full risk | Selective risk | Raw Brier | Calibrated Brier | Raw ECE | Calibrated ECE |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| GOWT1 real | 0.006971 | 0.002921 | 0.000813 | 0.000508 | 0.025139 | 0.000917 | 0.147361 | 0.001905 |
| HeLa real | 0.975046 | 0.990229 | 0.152082 | 0.002123 | 0.034790 | 0.008344 | 0.151391 | 0.006394 |
| SIM+ diagnostic | 0.997835 | 0.996454 | 0.160494 | 0.000643 | 0.034216 | 0.006975 | 0.152267 | 0.008535 |

HeLa passed the error-ranking comparison; GOWT1 did not. Both real tests passed
the selective-risk and calibration requirements. SIM+ is reported as a
diagnostic only and cannot rescue or satisfy a real-data GO gate.

## Motion endpoint summary

| Dataset | Endpoint | Hard error | Uncertainty-compatible error | Winner |
| --- | --- | ---: | ---: | --- |
| GOWT1 real | Mean speed | 0.003198 | 0.003198 | Tie |
| GOWT1 real | Total path length | 0.019160 | 0.019160 | Tie |
| GOWT1 real | Net displacement | 0.017567 | 0.017567 | Tie |
| GOWT1 real | Directionality | 0.012322 | 0.012322 | Tie |
| HeLa real | Mean speed | 0.156599 | 0.033970 | Uncertainty |
| HeLa real | Total path length | 0.450237 | 0.114698 | Uncertainty |
| HeLa real | Net displacement | 0.395378 | 0.019503 | Uncertainty |
| HeLa real | Directionality | 0.023237 | 0.014210 | Uncertainty |

The registered rule required uncertainty to win at least five of eight real
dataset-endpoint comparisons. It won four and tied four, so the motion gate
fails.

## Claim boundary

Stage E-Final is a multi-domain technical validation using existing Cell
Tracking Challenge references. It is not GBM brain-slice validation, does not
create biological replicates, and does not support a clinical or treatment
claim. Official CTC `LNK` and `TRA` executable scores are recorded as not
computed because the executable is not bundled; no substitute metric is
reported under those names.

Project completion remains scientifically defensible as a bounded technical
portfolio result: the pipeline is reproducible, its positive and negative
findings are locked, and the final Stage E result is a valid `REVISE` rather
than a failed or hidden test.
