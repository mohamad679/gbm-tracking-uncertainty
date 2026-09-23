# Stage E-Final locked evaluator freeze

Date: 2026-09-22. Status: **SUPERSEDED BY ONE-TIME LOCKED EVALUATION**.

The sequence-`02` evaluator has been implemented before any locked-test
coordinate, metric or outcome access. It consumes only the frozen
sequence-`01` configuration recorded in `stage-e-development-fit.json` and
cannot fit a temperature, select a radius, tune a threshold or replace data.

The separate execution lock
[`stage-e-sequence02-evaluation-lock.json`](stage-e-sequence02-evaluation-lock.json)
records one permitted attempt, the exact development-artifact SHA-256, the
clean decision scenario, the association-error AUPRC direction, and the fixed
0.5 calibrated-posterior compatible-link rule.

The evaluator reports every registered corruption scenario. The formal GO
decision uses `clean_0` on the two real domains for the registered primary
endpoints and the four motion-error comparisons per domain. SIM+ remains a
diagnostic only. Official CTC `LNK` and `TRA` executables are not bundled, so
the artifact records them as not computed rather than substituting a different
metric under those names.

The evaluator freeze was merged after all CI checks passed. The permitted
single locked sequence-`02` run then occurred and is reported in
[`stage-e-final-report.md`](stage-e-final-report.md).
