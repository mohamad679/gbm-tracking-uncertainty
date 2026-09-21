"""Issue the one-time Stage D held-out decision without reusing locked data.

Stage D Step 4 requires a newly audited independent operator-evaluation
sequence.  U373 sequence 02 and T98G were already consumed by earlier locked
tests, so this module refuses to treat either as a new Stage D evaluation
source.  When no eligible source is available it emits an explicit HOLD
artifact rather than inventing a performance result or silently reusing data.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from gbm_audit.stage_d_operators import FORBIDDEN_SEQUENCE_IDS
from gbm_audit.validation import ArtifactValidationError


FORBIDDEN_OPERATOR_EVALUATION_SOURCES = frozenset({
    "U373_sequence_02_archival_v1_test",
    "02",
    "T98G_locked_stage_c_v2_test",
    "T98G_sample",
    "T98G_electrotaxis_human_v2",
})
DEFAULT_KNOWN_LOCKED_SOURCES = (
    {
        "source_id": "U373_sequence_02_archival_v1_test",
        "independent": False,
        "data_only_audit_pass": True,
        "locked": True,
    },
    {
        "source_id": "T98G_locked_stage_c_v2_test",
        "independent": True,
        "data_only_audit_pass": True,
        "locked": True,
    },
)


def _artifact_sha256(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validate_development_artifact(development_artifact: dict) -> None:
    if development_artifact.get("status") != "DEVELOPMENT_COMPLETE":
        raise ArtifactValidationError("Stage D Step 3 artifact is not complete")
    if development_artifact.get("development_sequence") != "01":
        raise ArtifactValidationError("Stage D Step 3 artifact must use sequence 01")
    if development_artifact.get("locked_test_sequence_evaluated"):
        raise ArtifactValidationError("Stage D Step 3 artifact already evaluated a locked test")
    invariants = development_artifact.get("invariants", {})
    if invariants.get("selection_performed"):
        raise ArtifactValidationError("Step 4 cannot consume a development artifact with selection")


def _audit_candidate_source(source: dict) -> dict:
    if not isinstance(source, dict):
        raise ValueError("candidate source must be an object")
    source_id = source.get("source_id")
    if not isinstance(source_id, str) or not source_id:
        raise ValueError("candidate source requires a non-empty source_id")
    reasons = []
    if source_id in FORBIDDEN_OPERATOR_EVALUATION_SOURCES or source_id in FORBIDDEN_SEQUENCE_IDS:
        reasons.append("already_consumed_locked_source")
    if not source.get("independent", False):
        reasons.append("not_independent")
    if not source.get("data_only_audit_pass", False):
        reasons.append("data_only_audit_missing_or_failed")
    if not source.get("locked", False):
        reasons.append("source_not_locked_before_evaluation")
    return {
        "source_id": source_id,
        "eligible_for_stage_d": not reasons,
        "rejection_reasons": reasons,
    }


def build_step4_decision(development_artifact: dict, *, candidate_sources=()) -> dict:
    """Create the final Step 4 decision while enforcing one-time boundaries."""
    _validate_development_artifact(development_artifact)
    audited_sources = [_audit_candidate_source(source) for source in candidate_sources]
    eligible = [source for source in audited_sources if source["eligible_for_stage_d"]]
    if eligible:
        raise ArtifactValidationError(
            "an eligible source exists; Step 4 requires a separately reviewed one-time evaluator, "
            "not automatic execution or selection"
        )
    return {
        "schema_version": 1,
        "method": "stage_d_one_time_held_out_decision_v1",
        "status": "HOLD_NO_INDEPENDENT_EVALUATION_SOURCE",
        "stage": "D",
        "step": 4,
        "development_artifact_sha256": _artifact_sha256(development_artifact),
        "evaluation_attempted": False,
        "evaluation_count": 0,
        "selection_performed": False,
        "audited_candidate_sources": audited_sources,
        "eligible_source_count": 0,
        "gate_results": {
            "provenance_and_split_integrity": "NOT_AVAILABLE_NO_ELIGIBLE_SOURCE",
            "leakage": "PASS_NO_EVALUATION_PERFORMED",
            "held_out_predictive_improvement": "NOT_RUN",
            "noninferiority": "NOT_RUN",
            "interval_calibration": "NOT_RUN",
            "stability": "DEVELOPMENT_ONLY_NOT_HELD_OUT",
            "reproducibility": "PASS_ARTIFACT_DETERMINISTIC",
        },
        "decision": "HOLD",
        "decision_reason": (
            "No newly audited independent operator-evaluation sequence is available. "
            "U373 sequence 02 and T98G are already-consumed locked sources and cannot be reused."
        ),
        "forbidden_reuse": sorted(FORBIDDEN_OPERATOR_EVALUATION_SOURCES),
        "next_action": (
            "Audit and lock one genuinely independent operator-evaluation sequence before any "
            "future evaluation; do not refit or select from this HOLD artifact."
        ),
        "biological_claim": "not supported",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("development_artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        development_artifact = json.loads(args.development_artifact.read_text(encoding="utf-8"))
        result = build_step4_decision(
            development_artifact, candidate_sources=DEFAULT_KNOWN_LOCKED_SOURCES
        )
    except (OSError, ValueError, ArtifactValidationError, json.JSONDecodeError) as exc:
        print(f"Stage D Step 4 decision failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['decision']}; no held-out evaluation performed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
