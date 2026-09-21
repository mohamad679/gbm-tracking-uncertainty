"""Evaluate the frozen Stage D v3 blend once on locked Huh7 sequence 02."""

import argparse
import json
from pathlib import Path
import sys
from zipfile import BadZipFile

from gbm_audit.stage_d_development import (
    _artifact_sha256,
    _fit_models,
    _flatten,
    _stable_artifact,
    _track_transition_groups,
)
from gbm_audit.stage_d_huh7_evaluation import (
    BASELINES,
    COVERAGE_RANGE,
    NONINFERIORITY_MARGIN,
    _candidate_metrics,
)
from gbm_audit.stage_d_operators import StageDOperatorConfig
from gbm_audit.stage_d_v3_development import (
    BLEND_CANDIDATE,
    blend_metrics,
    fit_huh7_calibration,
    sequence_rows,
)
from gbm_audit.validation import ArtifactValidationError, canonical_sha256


def evaluation_gates(candidate: dict, baselines: dict) -> dict:
    primary = all(
        candidate["one_step_velocity_rmse_px_per_frame"]
        < baselines[name]["one_step_velocity_rmse_px_per_frame"]
        for name in BASELINES
    )
    best_summary = min(
        baselines[name]["mean_next_speed_absolute_error_px_per_frame"]
        for name in BASELINES
    )
    noninferiority = (
        candidate["mean_next_speed_absolute_error_px_per_frame"]
        <= best_summary + NONINFERIORITY_MARGIN
    )
    coverage = candidate["nominal_90_interval_coverage"]
    calibrated = COVERAGE_RANGE[0] <= coverage <= COVERAGE_RANGE[1]
    stable = candidate["stability"]["stability_pass"]
    return {
        "provenance_and_split_integrity": True,
        "leakage_boundary": True,
        "primary_predictive_improvement": bool(primary),
        "state_summary_noninferiority": bool(noninferiority),
        "interval_calibration": bool(calibrated),
        "stability": bool(stable),
        "reproducibility": True,
    }


def evaluate_sequence02(
        protocol: dict, audit: dict, v2_evaluation: dict,
        development_artifact: dict, sequence02_lock: dict,
        u373_manifest: dict, stage_c_development: dict,
        stage_d_development: dict, huh7_archive: Path) -> dict:
    reproduced = fit_huh7_calibration(
        protocol, audit, v2_evaluation, u373_manifest,
        stage_c_development, stage_d_development, huh7_archive,
    )
    if reproduced != development_artifact:
        raise ArtifactValidationError("Stage D v3 development artifact does not reproduce")
    if development_artifact.get("status") != "DEVELOPMENT_COMPLETE":
        raise ArtifactValidationError("Stage D v3 has no passing frozen configuration")
    if development_artifact.get("evaluation_sequence_evaluated"):
        raise ArtifactValidationError("Stage D v3 development already read sequence 02")
    if sequence02_lock.get("status") != "LOCKED_UNEVALUATED":
        raise ArtifactValidationError("Huh7 sequence 02 is not locked unevaluated")
    if sequence02_lock.get("sequence_id") != "02":
        raise ArtifactValidationError("Stage D v3 lock is not for sequence 02")
    if sequence02_lock.get("source_audit_sha256") != canonical_sha256(audit):
        raise ArtifactValidationError("sequence-02 lock source-audit hash mismatch")
    if sequence02_lock.get("selected_member_set_sha256") != protocol.get(
            "evaluation_member_set_sha256"):
        raise ArtifactValidationError("sequence-02 protocol/member hash mismatch")
    rows = sequence_rows(
        huh7_archive,
        sequence_id="02",
        member_set_sha256=sequence02_lock["selected_member_set_sha256"],
        expected_transition_slots=sequence02_lock["structural_velocity_transition_slots"],
    )
    config = StageDOperatorConfig(**stage_d_development["operator_config"])
    fit_rows = _flatten(_track_transition_groups(u373_manifest))
    models = _fit_models(
        fit_rows, stage_c_development["frozen_hmm"]["model"], config
    )
    baselines = {
        name: _candidate_metrics(
            name, models[name], rows,
            stage_d_development["full_development_fit"][name][
                "calibration_radius_p90_px_per_frame"
            ],
            config,
        )
        for name in BASELINES
    }
    selected = development_artifact["selected_configuration"]
    candidate = blend_metrics(
        models, rows, selected["lambda"], config,
        radius=selected["calibration_radius_p90_px_per_frame"],
    )
    gates = evaluation_gates(candidate, baselines)
    decision = "GO" if all(gates.values()) else "HOLD"
    return _stable_artifact({
        "schema_version": 1,
        "method": "stage_d_v3_huh7_sequence02_one_time_evaluation_v1",
        "status": f"COMPLETE_{decision}",
        "stage": "D-v3",
        "evaluation_count": 1,
        "evaluation_attempted": True,
        "selection_performed_after_heldout_inspection": False,
        "protocol_sha256": canonical_sha256(protocol),
        "source_audit_sha256": canonical_sha256(audit),
        "v2_evaluation_sha256": canonical_sha256(v2_evaluation),
        "development_artifact_sha256": canonical_sha256(development_artifact),
        "sequence02_lock_sha256": canonical_sha256(sequence02_lock),
        "u373_development_manifest_sha256": canonical_sha256(u373_manifest),
        "stage_c_development_artifact_sha256": _artifact_sha256(stage_c_development),
        "stage_d_development_artifact_sha256": _artifact_sha256(stage_d_development),
        "evaluation_sequence": "Huh7_02",
        "evaluation_member_set_sha256": sequence02_lock["selected_member_set_sha256"],
        "evaluation_row_count": len(rows),
        "fit_row_count": len(fit_rows),
        "selected_lambda": selected["lambda"],
        "frozen_sequence01_p90_radius_px_per_frame": selected[
            "calibration_radius_p90_px_per_frame"
        ],
        "metrics": {**baselines, BLEND_CANDIDATE: candidate},
        "gates": gates,
        "decision": decision,
        "decision_reason": (
            "All pre-registered sequence-02 gates passed."
            if decision == "GO" else
            "The valid locked sequence-02 evaluation failed one or more pre-registered gates."
        ),
        "claim_scope": (
            "within-Huh7 sequence generalization after one-sequence calibration"
        ),
        "zero_shot_cross_dataset_claim": "not supported; Stage D v2 remains HOLD",
        "biological_claim": "not supported",
    })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "protocol", "audit", "v2_evaluation", "development_artifact",
        "sequence02_lock", "u373_manifest", "stage_c_development",
        "stage_d_development",
    ):
        parser.add_argument(name, type=Path)
    parser.add_argument("huh7_archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        values = [
            json.loads(getattr(args, name).read_text(encoding="utf-8"))
            for name in (
                "protocol", "audit", "v2_evaluation", "development_artifact",
                "sequence02_lock", "u373_manifest", "stage_c_development",
                "stage_d_development",
            )
        ]
        result = evaluate_sequence02(*values, args.huh7_archive)
    except (OSError, BadZipFile, ValueError, RuntimeError,
            ArtifactValidationError, json.JSONDecodeError, KeyError) as exc:
        print(f"Stage D v3 evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"Wrote {args.output} ({result['decision']}; "
        f"{result['evaluation_row_count']} locked Huh7 sequence-02 rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
