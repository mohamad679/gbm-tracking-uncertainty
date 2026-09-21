"""Fit the frozen Stage D v3 Huh7 sequence-01 blend calibration."""

import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.archive import read_member_bytes, validate_zip_archive
from gbm_audit.cli import sha256_file
from gbm_audit.stage_d_development import (
    _artifact_sha256,
    _fit_models,
    _flatten,
    _predict,
    _stable_artifact,
    _track_transition_groups,
    fit_development_and_check_stability,
)
from gbm_audit.stage_d_huh7_audit import (
    EXPECTED_ARCHIVE_SHA256,
    EXPECTED_ARCHIVE_SIZE,
    ROOT,
    _digest_members,
)
from gbm_audit.stage_d_huh7_evaluation import BASELINES, CANDIDATE, MAX_ROLLOUT_NORM
from gbm_audit.stage_d_operators import StageDOperatorConfig
from gbm_audit.validation import ArtifactValidationError, canonical_sha256


BLEND_CANDIDATE = "huh7_calibrated_koopman_empirical_blend_v1"
_TRACK_RE = re.compile(
    rf"^{ROOT}/(?P<sequence>[0-9]+)_GT/TRA/man_track(?P<frame>[0-9]+)\.tif$"
)


def sequence_rows(
        path: Path, *, sequence_id: str, member_set_sha256: str,
        expected_transition_slots: int) -> list[dict]:
    """Extract evaluation rows only after the caller has locked the sequence."""
    if path.stat().st_size != EXPECTED_ARCHIVE_SIZE:
        raise ArtifactValidationError("Huh7 archive size mismatch")
    if sha256_file(path) != EXPECTED_ARCHIVE_SHA256:
        raise ArtifactValidationError("Huh7 archive SHA-256 mismatch")
    with ZipFile(path) as archive:
        validate_zip_archive(archive)
        track_paths = {}
        for name in archive.namelist():
            match = _TRACK_RE.fullmatch(name)
            if match and match["sequence"] == sequence_id:
                track_paths[int(match["frame"])] = name
        lineage_path = f"{ROOT}/{sequence_id}_GT/TRA/man_track.txt"
        selected_paths = list(track_paths.values()) + [
            f"{ROOT}/{sequence_id}/t{frame:03d}.tif" for frame in sorted(track_paths)
        ] + [lineage_path]
        if _digest_members(archive, selected_paths) != member_set_sha256:
            raise ArtifactValidationError("Huh7 sequence member-set hash mismatch")
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
    if len(rows) != expected_transition_slots:
        raise ArtifactValidationError("Huh7 transition count differs from the data-only lock")
    return rows


def _blend_prediction(models: dict, state: np.ndarray, lambda_value: float) -> np.ndarray:
    koopman = _predict(CANDIDATE, models[CANDIDATE], state)
    empirical = _predict(BASELINES[1], models[BASELINES[1]], state)
    return lambda_value * koopman + (1.0 - lambda_value) * empirical


def blend_metrics(models: dict, rows: list[dict], lambda_value: float,
                  config: StageDOperatorConfig, *, radius: float | None = None) -> dict:
    residuals = []
    predicted_speeds = []
    observed_speeds = []
    maxima = []
    finite = True
    for row in rows:
        state = np.asarray(row["state"], dtype=float)
        target = np.asarray(row["next_state"], dtype=float)
        prediction = _blend_prediction(models, state, lambda_value)
        residuals.append(float(np.linalg.norm(prediction - target)))
        predicted_speeds.append(float(np.linalg.norm(prediction)))
        observed_speeds.append(float(np.linalg.norm(target)))
        current = state.copy()
        for _ in range(config.forecast_horizon):
            current = _blend_prediction(models, current, lambda_value)
            if not np.all(np.isfinite(current)):
                finite = False
                break
            maxima.append(float(np.max(np.abs(current))))
        if not finite:
            break
    residuals_array = np.asarray(residuals)
    calibration_radius = (
        float(np.quantile(residuals_array, 0.90)) if radius is None else float(radius)
    )
    observed_mean = float(np.mean(observed_speeds))
    predicted_mean = float(np.mean(predicted_speeds))
    max_abs = max(maxima, default=0.0)
    return {
        "candidate": BLEND_CANDIDATE,
        "lambda": float(lambda_value),
        "evaluation_row_count": len(rows),
        "one_step_velocity_rmse_px_per_frame": float(
            np.sqrt(np.mean(residuals_array ** 2))
        ),
        "one_step_velocity_mae_px_per_frame": float(np.mean(residuals_array)),
        "observed_mean_next_speed_px_per_frame": observed_mean,
        "predicted_mean_next_speed_px_per_frame": predicted_mean,
        "mean_next_speed_absolute_error_px_per_frame": abs(predicted_mean - observed_mean),
        "calibration_radius_p90_px_per_frame": calibration_radius,
        "nominal_90_interval_coverage": float(
            np.mean(residuals_array <= calibration_radius)
        ),
        "stability": {
            "finite_rollout": bool(finite),
            "max_abs_state": max_abs,
            "forecast_horizon": config.forecast_horizon,
            "max_abs_state_bound": MAX_ROLLOUT_NORM,
            "stability_pass": bool(finite and max_abs <= MAX_ROLLOUT_NORM),
        },
    }


def _baseline_metrics(models: dict, rows: list[dict], name: str,
                      config: StageDOperatorConfig) -> dict:
    residuals = []
    predicted_speeds = []
    observed_speeds = []
    for row in rows:
        state = np.asarray(row["state"], dtype=float)
        target = np.asarray(row["next_state"], dtype=float)
        prediction = _predict(name, models[name], state)
        residuals.append(float(np.linalg.norm(prediction - target)))
        predicted_speeds.append(float(np.linalg.norm(prediction)))
        observed_speeds.append(float(np.linalg.norm(target)))
    residuals_array = np.asarray(residuals)
    observed_mean = float(np.mean(observed_speeds))
    predicted_mean = float(np.mean(predicted_speeds))
    return {
        "candidate": name,
        "evaluation_row_count": len(rows),
        "one_step_velocity_rmse_px_per_frame": float(
            np.sqrt(np.mean(residuals_array ** 2))
        ),
        "observed_mean_next_speed_px_per_frame": observed_mean,
        "predicted_mean_next_speed_px_per_frame": predicted_mean,
        "mean_next_speed_absolute_error_px_per_frame": abs(predicted_mean - observed_mean),
    }


def development_gate(metric: dict, baselines: dict) -> dict:
    primary = all(
        metric["one_step_velocity_rmse_px_per_frame"]
        < baselines[name]["one_step_velocity_rmse_px_per_frame"]
        for name in BASELINES
    )
    best_summary = min(
        baselines[name]["mean_next_speed_absolute_error_px_per_frame"]
        for name in BASELINES
    )
    noninferiority = (
        metric["mean_next_speed_absolute_error_px_per_frame"] <= best_summary + 0.10
    )
    return {
        "primary_predictive_improvement": bool(primary),
        "state_summary_noninferiority": bool(noninferiority),
        "stability": bool(metric["stability"]["stability_pass"]),
        "pass": bool(primary and noninferiority and metric["stability"]["stability_pass"]),
    }


def fit_huh7_calibration(
        protocol: dict, audit: dict, v2_evaluation: dict, u373_manifest: dict,
        stage_c_development: dict, stage_d_development: dict,
        huh7_archive: Path) -> dict:
    if protocol.get("status") != "SEQUENCE_02_LOCKED_BEFORE_DEVELOPMENT_FIT":
        raise ArtifactValidationError("Stage D v3 protocol is not frozen")
    if protocol.get("source_audit_sha256") != canonical_sha256(audit):
        raise ArtifactValidationError("Stage D v3 source-audit hash mismatch")
    if protocol.get("v2_consumed_evaluation_sha256") != canonical_sha256(v2_evaluation):
        raise ArtifactValidationError("Stage D v3 consumed-v2 hash mismatch")
    if v2_evaluation.get("evaluation_sequence_id") != "01":
        raise ArtifactValidationError("Huh7 sequence 01 was not the consumed v2 evaluation")
    if v2_evaluation.get("evaluation_count") != 1:
        raise ArtifactValidationError("unexpected Stage D v2 evaluation count")
    reproduced = _stable_artifact(
        fit_development_and_check_stability(u373_manifest, stage_c_development)
    )
    if reproduced != stage_d_development:
        raise ArtifactValidationError("frozen Stage D development artifact does not reproduce")
    sequence01 = next(
        item for item in audit["sequence_audits"] if item["sequence_id"] == "01"
    )
    rows = sequence_rows(
        huh7_archive, sequence_id="01",
        member_set_sha256=sequence01["selected_member_set_sha256"],
        expected_transition_slots=sequence01["structural_velocity_transition_slots"],
    )
    config = StageDOperatorConfig(**stage_d_development["operator_config"])
    fit_rows = _flatten(_track_transition_groups(u373_manifest))
    models = _fit_models(fit_rows, stage_c_development["frozen_hmm"]["model"], config)
    baselines = {
        name: _baseline_metrics(models, rows, name, config) for name in BASELINES
    }
    grid_results = []
    for lambda_value in protocol["candidate"]["lambda_grid"]:
        metric = blend_metrics(models, rows, float(lambda_value), config)
        grid_results.append({**metric, "gates": development_gate(metric, baselines)})
    passing = [item for item in grid_results if item["gates"]["pass"]]
    selected = min(
        passing,
        key=lambda item: (item["one_step_velocity_rmse_px_per_frame"], -item["lambda"]),
        default=None,
    )
    return _stable_artifact({
        "schema_version": 1,
        "method": "stage_d_v3_huh7_sequence01_calibration_v1",
        "status": "DEVELOPMENT_COMPLETE" if selected else "HOLD_NO_PASSING_CONFIGURATION",
        "protocol_sha256": canonical_sha256(protocol),
        "source_audit_sha256": canonical_sha256(audit),
        "v2_consumed_evaluation_sha256": canonical_sha256(v2_evaluation),
        "u373_development_manifest_sha256": canonical_sha256(u373_manifest),
        "stage_c_development_artifact_sha256": _artifact_sha256(stage_c_development),
        "stage_d_development_artifact_sha256": _artifact_sha256(stage_d_development),
        "development_sequence": "Huh7_01_consumed_v2",
        "evaluation_sequence": "Huh7_02_locked_unevaluated",
        "evaluation_sequence_evaluated": False,
        "selection_performed": True,
        "development_row_count": len(rows),
        "fit_row_count": len(fit_rows),
        "baselines": baselines,
        "grid_results": grid_results,
        "selected_configuration": selected,
        "decision": "PROCEED_TO_LOCKED_EVALUATION" if selected else "HOLD",
        "biological_claim": "not supported",
    })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "protocol", "audit", "v2_evaluation", "u373_manifest",
        "stage_c_development", "stage_d_development",
    ):
        parser.add_argument(name, type=Path)
    parser.add_argument("huh7_archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        values = [
            json.loads(getattr(args, name).read_text(encoding="utf-8"))
            for name in (
                "protocol", "audit", "v2_evaluation", "u373_manifest",
                "stage_c_development", "stage_d_development",
            )
        ]
        result = fit_huh7_calibration(*values, args.huh7_archive)
    except (OSError, BadZipFile, ValueError, RuntimeError,
            ArtifactValidationError, json.JSONDecodeError, KeyError) as exc:
        print(f"Stage D v3 development failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['decision']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
