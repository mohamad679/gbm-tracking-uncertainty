# Stage D Step 4: one-time held-out evaluation and decision

Date: 2026-09-21. Status: **COMPLETE — HOLD; NO INDEPENDENT EVALUATION SOURCE**.

The frozen Stage D protocol requires one newly audited, independent operator-
evaluation sequence. U373 sequence `02` was already consumed by the earlier
locked U373 test, and T98G was already consumed by the locked Stage C v2 test.
The protocol explicitly forbids reusing either source for Stage D fitting,
selection, or evaluation. No other eligible operator-evaluation source is
currently present in the repository.

## One-time boundary result

- Evaluation attempts: `0`
- Eligible independent sources: `0`
- Candidate selection after held-out inspection: `false`
- Held-out predictive, non-inferiority, and interval-calibration metrics:
  `NOT_RUN`
- Development stability: retained from Step 3 only; it is not a held-out pass.

The two known locked sources were explicitly rejected by the decision contract:

| Source | Rejection |
| --- | --- |
| U373 sequence `02` | Already consumed; not an independent new operator source |
| T98G locked Stage C v2 test | Already consumed locked source |

## Final decision

The final Stage D decision is **HOLD**, not `GO` or `REVISE`. This is the
pre-registered outcome when no independent held-out sequence is available. No
performance number was fabricated, and no model was promoted from development
cross-validation. A future continuation must first pass a data-only
provenance/schema audit for a genuinely new dataset and lock it before any
operator fit or one-time evaluation.

The complete machine-readable decision is
[`stage-d-heldout-decision.json`](stage-d-heldout-decision.json). This technical
HOLD does not support a biological or clinical claim.
