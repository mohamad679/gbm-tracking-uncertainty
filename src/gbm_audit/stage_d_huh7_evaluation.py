"""Run the frozen one-time Stage D v2 evaluation on locked Huh7 sequence 01."""

import argparse
from io import BytesIO
import json
import math
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.archive import read_member_bytes, validate_zip_archive
from gbm_audit.stage_d_development import (
    _artifact_sha256,
    _fit_models,
    _flatten,
    _predict,
    _rollout_report,
    _stable_artifact,
    _track_transition_groups,
    fit_development_and_check_stability,
)
from gbm_audit.stage_d_huh7_audit import (
    DATASET_ID,
    EXPECTED_ARCHIVE_SHA256,
    EXPECTED_ARCHIVE_SIZE,
    ROOT,
    _digest_members,
)
from gbm_audit.stage_d_operators import StageDOperatorConfig
from gbm_audit.validation import ArtifactValidationError, canonical_sha256


CANDIDATE = "stable_linear_koopman_operator_v1"
BASELINES = (
    "frozen_hmm_speed_baseline_v1",
    "weighted_empirical_transition_baseline_v1",
)
NONINFERIORITY_MARGIN = 0.10
COVERAGE_RANGE = (0.80, 0.98)
MAX_ROLLOUT_NORM = 1_000.0
_TRACK_RE = re.compile(
    rf"^{ROOT}/(?P<sequence>[0-9]+)_GT/TRA/man_track(?P<frame>[0-9]+)\.tif$"
)


def _validated_inputs(
        protocol: dict, audit: dict, u373_manifest: dict,
        stage_c_development: dict, stage_d_development: dict) -> StageDOperatorConfig:
    if protocol.get("status") != "FROZEN_BEFORE_OUTCOME_INSPECTION":
        raise ArtifactValidationError("Stage D v2 protocol is not frozen")
    source = protocol.get("source", {})
    if source.get("expected_size_bytes") != EXPECTED_ARCHIVE_SIZE:
        raise ArtifactValidationError("protocol Huh7 archive size drift")
    if source.get("expected_sha256") != EXPECTED_ARCHIVE_SHA256:
        raise ArtifactValidationError("protocol Huh7 archive hash drift")
    if audit.get("status") != "LOCKED_UNEVALUATED":
        raise ArtifactValidationError("Huh7 audit is not locked and unevaluated")
    if audit.get("dataset_id") != DATASET_ID:
        raise ArtifactValidationError("Huh7 audit dataset identity drift")
    invariants = audit.get("data_only_invariants", {})
    expected_invariants = {
        "coordinates_extracted": False,
        "motion_values_computed": False,
        "models_fitted": False,
        "outcome_metrics_exposed": False,
        "locked_before_evaluation": True,
    }
    if invariants != expected_invariants:
        raise ArtifactValidationError("Huh7 data-only lock invariants failed")
    if audit.get("locked_sequence_id") != "01":
        raise ArtifactValidationError("unexpected Huh7 locked sequence")
    expected_stage_d = _stable_artifact(
        fit_development_and_check_stability(u373_manifest, stage_c_development)
    )
    if expected_stage_d != stage_d_development:
        raise ArtifactValidationError("frozen Stage D development artifact does not reproduce")
    if stage_d_development.get("decision") != "HOLD_PENDING_STEP_4_HELD_OUT_EVALUATION":
        raise ArtifactValidationError("Stage D development artifact is not awaiting held-out evaluation")
    config = StageDOperatorConfig(**stage_d_development["operator_config"])
    config.validate()
    return config


def _heldout_rows(path: Path, audit: dict) -> list[dict]:
    if path.stat().st_size != EXPECTED_ARCHIVE_SIZE:
        raise ArtifactValidationError("Huh7 archive size differs from the locked audit")
    from gbm_audit.cli import sha256_file
    if sha256_file(path) != EXPECTED_ARCHIVE_SHA256:
        raise ArtifactValidationError("Huh7 archive SHA-256 differs from the locked audit")
    sequence = audit["locked_sequence_id"]
    with ZipFile(path) as archive:
        validate_zip_archive(archive)
        track_paths = {}
        for name in archive.namelist():
            match = _TRACK_RE.fullmatch(name)
            if match and match["sequence"] == sequence:
                track_paths[int(match["frame"])] = name
        lineage_path = f"{ROOT}/{sequence}_GT/TRA/man_track.txt"
        selected_paths = list(track_paths.values()) + [
            f"{ROOT}/{sequence}/t{frame:03d}.tif" for frame in sorted(track_paths)
        ] + [lineage_path]
        if _digest_members(archive, selected_paths) != audit.get(
                "locked_sequence_member_set_sha256"):
            raise ArtifactValidationError("Huh7 locked member-set hash mismatch")
        observations: dict[int, list[tuple[int, float, float]]] = {}
        for frame, member in sorted(track_paths.items()):
            with Image.open(BytesIO(read_member_bytes(archive, member))) as image:
                mask = np.asarray(image)
            for label in np.unique(mask):
                label = int(label)
                if label == 0:
                    continue
                ys, xs = np.where(mask == label)
                observations.setdefault(label, []).append(
                    (frame, float(xs.mean()), float(ys.mean()))
                )
    rows = []
    for points in observations.values():
        for previous, current, following in zip(points, points[1:], points[2:]):
            if current[0] - previous[0] != 1 or following[0] - current[0] != 1:
                continue
            rows.append({
                "state": [current[1] - previous[1], current[2] - previous[2]],
                "next_state": [following[1] - current[1], following[2] - current[2]],
            })
    expected_slots = next(
        item["structural_velocity_transition_slots"]
        for item in audit["sequence_audits"] if item["sequence_id"] == sequence
    )
    if len(rows) != expected_slots:
        raise ArtifactValidationError(
            f"Huh7 transition count differs from lock: expected {expected_slots}, found {len(rows)}"
        )
    return rows


def _candidate_metrics(name: str, model, rows: list[dict], radius: float,
                       config: StageDOperatorConfig) -> dict:
    residuals = []
    predicted_speeds = []
    observed_speeds = []
    rollout_rows = []
    for row in rows:
        state = np.asarray(row["state"], dtype=float)
        target = np.asarray(row["next_state"], dtype=float)
        prediction = _predict(name, model, state)
        residuals.append(float(np.linalg.norm(prediction - target)))
        predicted_speeds.append(float(np.linalg.norm(prediction)))
        observed_speeds.append(float(np.linalg.norm(target)))
        rollout_rows.append({"state": row["state"]})
    residuals_array = np.asarray(residuals)
    observed_mean = float(np.mean(observed_speeds))
    predicted_mean = float(np.mean(predicted_speeds))
    return {
        "candidate": name,
        "evaluation_row_count": len(rows),
        "one_step_velocity_rmse_px_per_frame": float(
            np.sqrt(np.mean(residuals_array ** 2))
        ),
        "one_step_velocity_mae_px_per_frame": float(np.mean(residuals_array)),
        "observed_mean_next_speed_px_per_frame": observed_mean,
        "predicted_mean_next_speed_px_per_frame": predicted_mean,
        "mean_next_speed_absolute_error_px_per_frame": abs(predicted_mean - observed_mean),
        "frozen_development_p90_radius_px_per_frame": float(radius),
        "nominal_90_interval_coverage": float(np.mean(residuals_array <= radius)),
        "stability": _rollout_report(
            name, model, rollout_rows, config.forecast_horizon, MAX_ROLLOUT_NORM
        ),
    }


def _decision(metrics: dict) -> tuple[dict, str]:
    candidate = metrics[CANDIDATE]
    baseline_values = [metrics[name] for name in BASELINES]
    primary = all(
        candidate["one_step_velocity_rmse_px_per_frame"]
        < baseline["one_step_velocity_rmse_px_per_frame"]
        for baseline in baseline_values
    )
    best_summary_error = min(
        baseline["mean_next_speed_absolute_error_px_per_frame"]
        for baseline in baseline_values
    )
    noninferiority = (
        candidate["mean_next_speed_absolute_error_px_per_frame"]
        <= best_summary_error + NONINFERIORITY_MARGIN
    )
    coverage = candidate["nominal_90_interval_coverage"]
    interval = COVERAGE_RANGE[0] <= coverage <= COVERAGE_RANGE[1]
    stability = candidate["stability"]["stability_pass"]
    gates = {
        "provenance_and_split_integrity": True,
        "leakage_boundary": True,
        "primary_predictive_improvement": bool(primary),
        "state_summary_noninferiority": bool(noninferiority),
        "interval_calibration": bool(interval),
        "stability": bool(stability),
        "reproducibility": True,
    }
    return gates, "GO" if all(gates.values()) else "HOLD"


def evaluate_huh7(
        protocol: dict, audit: dict, u373_manifest: dict,
        stage_c_development: dict, stage_d_development: dict,
        huh7_archive: Path) -> dict:
    """Evaluate the pre-registered candidate once on the locked Huh7 sequence."""
    config = _validated_inputs(
        protocol, audit, u373_manifest, stage_c_development, stage_d_development
    )
    fit_rows = _flatten(_track_transition_groups(u373_manifest))
    hmm_model = stage_c_development["frozen_hmm"]["model"]
    models = _fit_models(fit_rows, hmm_model, config)
    heldout_rows = _heldout_rows(huh7_archive, audit)
    metrics = {
        name: _candidate_metrics(
            name, model, heldout_rows,
            stage_d_development["full_development_fit"][name][
                "calibration_radius_p90_px_per_frame"
            ],
            config,
        )
        for name, model in models.items()
    }
    gates, decision = _decision(metrics)
    return _stable_artifact({
        "schema_version": 1,
        "method": "stage_d_v2_huh7_one_time_evaluation_v1",
        "status": f"COMPLETE_{decision}",
        "stage": "D-v2",
        "evaluation_count": 1,
        "evaluation_attempted": True,
        "selection_performed_after_heldout_inspection": False,
        "protocol_sha256": canonical_sha256(protocol),
        "audit_sha256": canonical_sha256(audit),
        "u373_development_manifest_sha256": canonical_sha256(u373_manifest),
        "stage_c_development_artifact_sha256": _artifact_sha256(stage_c_development),
        "stage_d_development_artifact_sha256": _artifact_sha256(stage_d_development),
        "evaluation_dataset_id": DATASET_ID,
        "evaluation_sequence_id": audit["locked_sequence_id"],
        "evaluation_member_set_sha256": audit["locked_sequence_member_set_sha256"],
        "state_definition": "velocity_xy_px_per_frame",
        "evaluation_row_count": len(heldout_rows),
        "fit_row_count": len(fit_rows),
        "metrics": metrics,
        "gates": gates,
        "decision": decision,
        "decision_reason": (
            "All pre-registered independent Huh7 gates passed."
            if decision == "GO" else
            "The valid independent Huh7 evaluation failed one or more pre-registered gates; "
            "operator complexity is not promoted."
        ),
        "forbidden_sources_not_used": [
            "U373_sequence_02_archival_v1_test",
            "T98G_locked_stage_c_v2_test",
        ],
        "biological_claim": "not supported",
    })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("audit", type=Path)
    parser.add_argument("u373_manifest", type=Path)
    parser.add_argument("stage_c_development", type=Path)
    parser.add_argument("stage_d_development", type=Path)
    parser.add_argument("huh7_archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        inputs = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in (
                args.protocol, args.audit, args.u373_manifest,
                args.stage_c_development, args.stage_d_development,
            )
        ]
        result = evaluate_huh7(*inputs, args.huh7_archive)
    except (OSError, BadZipFile, ValueError, RuntimeError,
            ArtifactValidationError, json.JSONDecodeError, KeyError) as exc:
        print(f"Stage D v2 Huh7 evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {args.output} ({result['decision']}; "
        f"{result['evaluation_row_count']} locked Huh7 rows)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
