"""Development-only fitting and stability checks for Stage D.

The input is the already-audited U373 reference manifest and the frozen
Stage C development HMM artifact.  This module deliberately uses only
sequence ``01``.  It performs leave-one-track-out diagnostics inside that
development sequence, but it never reads a locked-test sequence, labels from
an evaluation artifact, or a held-out performance summary.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from gbm_audit.stage_d_operators import (
    FORBIDDEN_SEQUENCE_IDS,
    FrozenHMMSpeedBaseline,
    StageDOperatorConfig,
    StableLinearKoopmanOperator,
    WeightedEmpiricalTransitionBaseline,
    candidate_registry,
    validate_transition_rows,
)
from gbm_audit.validation import ArtifactValidationError, canonical_sha256, validate_manifest


DEVELOPMENT_SEQUENCE_ID = "01"
DEFAULT_FORECAST_HORIZON = 10
DEFAULT_MAX_ROLLOUT_NORM = 1_000.0
CALIBRATION_QUANTILE = 0.90
STATE_DEFINITION = "velocity_xy_px_per_frame"


def _stable_artifact(value):
    """Normalize floating-point serialization for reproducible JSON artifacts."""
    if isinstance(value, float):
        rounded = round(value, 9)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, dict):
        return {key: _stable_artifact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable_artifact(item) for item in value]
    if isinstance(value, tuple):
        return [_stable_artifact(item) for item in value]
    return value


def _artifact_sha256(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _development_sequence(manifest: dict) -> dict:
    validate_manifest(manifest)
    sequence = manifest["sequences"].get(DEVELOPMENT_SEQUENCE_ID)
    if sequence is None:
        raise ArtifactValidationError("reference manifest has no development sequence 01")
    if sequence.get("split") != "development":
        raise ArtifactValidationError("sequence 01 must be marked development")
    for sequence_id, candidate in manifest["sequences"].items():
        if sequence_id in FORBIDDEN_SEQUENCE_IDS or sequence_id == "02":
            if candidate.get("split") != "test":
                raise ArtifactValidationError(
                    f"forbidden sequence {sequence_id!r} must remain outside development"
                )
    return sequence


def _track_transition_groups(manifest: dict) -> list[list[dict]]:
    """Build truth-blind velocity transitions grouped for development CV.

    Track identity is used only to define the cross-validation unit.  It is not
    included in a transition row and therefore cannot become a model feature.
    The weight is a deterministic motion-noise proxy derived from the current
    observed step; it is not a fitted or evaluation-derived quantity.
    """
    sequence = _development_sequence(manifest)
    groups: list[list[dict]] = []
    for track in sequence["tracks"]:
        points = sorted(track.get("observations", []), key=lambda item: item["frame"])
        rows = []
        for previous, current, following in zip(points, points[1:], points[2:]):
            if current["frame"] - previous["frame"] != 1:
                continue
            if following["frame"] - current["frame"] != 1:
                continue
            velocity = np.asarray([
                float(current["x_px"]) - float(previous["x_px"]),
                float(current["y_px"]) - float(previous["y_px"]),
            ])
            next_velocity = np.asarray([
                float(following["x_px"]) - float(current["x_px"]),
                float(following["y_px"]) - float(current["y_px"]),
            ])
            # Lower-confidence, faster steps receive less influence.  This
            # proxy is fixed before fitting and does not inspect any truth.
            uncertainty_weight = 1.0 / (1.0 + float(np.linalg.norm(velocity)))
            rows.append({
                "sequence_id": DEVELOPMENT_SEQUENCE_ID,
                "state": [float(value) for value in velocity],
                "next_state": [float(value) for value in next_velocity],
                "uncertainty_weight": uncertainty_weight,
            })
        if rows:
            groups.append(rows)
    if len(groups) < 2:
        raise ValueError("at least two development tracks with two transitions are required")
    return groups


def _flatten(groups: list[list[dict]]) -> list[dict]:
    return [row for group in groups for row in group]


def _hmm_speed_prediction(baseline: FrozenHMMSpeedBaseline, state: np.ndarray) -> np.ndarray:
    """Keep the observed heading while using the frozen HMM for speed."""
    value = np.asarray(state, dtype=float)
    speed = float(np.linalg.norm(value))
    direction = value / speed if speed > 1e-12 else np.asarray([1.0, 0.0])
    result = baseline.predict_speed()
    return direction * float(result["expected_speed_px_per_frame"])


def _fit_models(rows: list[dict], hmm_model: dict, config: StageDOperatorConfig) -> dict:
    validate_transition_rows(rows)
    return {
        "frozen_hmm_speed_baseline_v1": FrozenHMMSpeedBaseline(hmm_model),
        "weighted_empirical_transition_baseline_v1": WeightedEmpiricalTransitionBaseline.fit(rows),
        "stable_linear_koopman_operator_v1": StableLinearKoopmanOperator.fit(rows, config=config),
    }


def _predict(name: str, model, state: np.ndarray) -> np.ndarray:
    if name == "frozen_hmm_speed_baseline_v1":
        return _hmm_speed_prediction(model, state)
    return model.predict(state)


def _residuals(name: str, model, rows: list[dict]) -> np.ndarray:
    values = []
    for row in rows:
        prediction = _predict(name, model, np.asarray(row["state"], dtype=float))
        target = np.asarray(row["next_state"], dtype=float)
        values.append(float(np.linalg.norm(prediction - target)))
    return np.asarray(values, dtype=float)


def _rollout_report(name: str, model, rows: list[dict], horizon: int, max_norm: float) -> dict:
    maxima = []
    finite = True
    for row in rows:
        state = np.asarray(row["state"], dtype=float)
        current = state.copy()
        for _ in range(horizon):
            if name == "frozen_hmm_speed_baseline_v1":
                current = _hmm_speed_prediction(model, current)
            else:
                current = model.predict(current)
            if not np.all(np.isfinite(current)):
                finite = False
                break
            maxima.append(float(np.max(np.abs(current))))
        if not finite:
            break
    max_value = max(maxima, default=0.0)
    stable = finite and math.isfinite(max_value) and max_value <= max_norm
    return {
        "finite_rollout": bool(finite),
        "max_abs_state": max_value,
        "forecast_horizon": horizon,
        "max_abs_state_bound": max_norm,
        "stability_pass": bool(stable),
    }


def _model_summary(name: str, model, rows: list[dict], config: StageDOperatorConfig,
                   *, calibration_radius: float | None = None) -> dict:
    residuals = _residuals(name, model, rows)
    radius = float(np.quantile(residuals, CALIBRATION_QUANTILE)) if residuals.size else None
    if calibration_radius is not None:
        radius = float(calibration_radius)
    report = _rollout_report(
        name, model, rows, config.forecast_horizon, DEFAULT_MAX_ROLLOUT_NORM
    )
    result = {
        "candidate": name,
        "row_count": len(rows),
        "in_sample_rmse_px_per_frame": float(np.sqrt(np.mean(residuals ** 2))) if residuals.size else None,
        "in_sample_mae_px_per_frame": float(np.mean(residuals)) if residuals.size else None,
        "calibration_radius_p90_px_per_frame": radius,
        "stability": report,
    }
    if hasattr(model, "stability_report"):
        result["operator_stability"] = model.stability_report()
    return result


def _cross_validate(groups: list[list[dict]], hmm_model: dict, config: StageDOperatorConfig) -> dict:
    fold_rows = []
    candidate_results = {name: [] for name in candidate_registry()}
    for fold_index, validation_rows in enumerate(groups):
        training_rows = _flatten(groups[:fold_index] + groups[fold_index + 1:])
        models = _fit_models(training_rows, hmm_model, config)
        fold_result = {
            "fold": fold_index,
            "validation_unit": "development_track",
            "training_row_count": len(training_rows),
            "validation_row_count": len(validation_rows),
            "candidates": {},
        }
        for name, model in models.items():
            training_residuals = _residuals(name, model, training_rows)
            radius = float(np.quantile(training_residuals, CALIBRATION_QUANTILE))
            validation_residuals = _residuals(name, model, validation_rows)
            stability = _rollout_report(
                name, model, validation_rows, config.forecast_horizon, DEFAULT_MAX_ROLLOUT_NORM
            )
            report = {
                "candidate": name,
                "validation_rmse_px_per_frame": float(np.sqrt(np.mean(validation_residuals ** 2))),
                "validation_mae_px_per_frame": float(np.mean(validation_residuals)),
                "calibration_radius_p90_px_per_frame": radius,
                "nominal_90_interval_coverage": float(
                    np.mean(validation_residuals <= radius)
                ),
                "validation_row_count": len(validation_rows),
                "stability": stability,
            }
            if hasattr(model, "stability_report"):
                report["operator_stability"] = model.stability_report()
            fold_result["candidates"][name] = report
            candidate_results[name].append(report)
        fold_rows.append(fold_result)
    aggregate = {}
    for name, reports in candidate_results.items():
        aggregate[name] = {
            "fold_count": len(reports),
            "mean_validation_rmse_px_per_frame": float(np.mean([
                report["validation_rmse_px_per_frame"] for report in reports
            ])),
            "mean_validation_mae_px_per_frame": float(np.mean([
                report["validation_mae_px_per_frame"] for report in reports
            ])),
            "mean_nominal_90_interval_coverage": float(np.mean([
                report["nominal_90_interval_coverage"] for report in reports
            ])),
            "all_stability_pass": all(report["stability"]["stability_pass"] for report in reports),
        }
    return {"folds": fold_rows, "aggregate": aggregate}


def fit_development_and_check_stability(
        manifest: dict, stage_c_development: dict, *,
        config: StageDOperatorConfig | None = None) -> dict:
    """Fit every registered candidate on development data and report diagnostics."""
    config = config or StageDOperatorConfig(forecast_horizon=DEFAULT_FORECAST_HORIZON)
    config.validate()
    sequence = _development_sequence(manifest)
    manifest_hash = canonical_sha256(manifest)
    if stage_c_development.get("reference_manifest_sha256") != manifest_hash:
        raise ArtifactValidationError(
            "Stage C development artifact manifest hash does not match the supplied manifest"
        )
    if stage_c_development.get("development_sequence") != DEVELOPMENT_SEQUENCE_ID:
        raise ArtifactValidationError("Stage C development artifact must be for sequence 01")
    if stage_c_development.get("locked_test_sequence_evaluated"):
        raise ArtifactValidationError("Stage C input must remain development-only")
    hmm_model = stage_c_development.get("frozen_hmm", {}).get("model")
    if not isinstance(hmm_model, dict) or hmm_model.get("status") != "ok":
        raise ArtifactValidationError("Stage C development artifact has no frozen HMM model")
    groups = _track_transition_groups(manifest)
    rows = _flatten(groups)
    models = _fit_models(rows, hmm_model, config)
    full_fit = {
        name: _model_summary(name, model, rows, config)
        for name, model in models.items()
    }
    cross_validation = _cross_validate(groups, hmm_model, config)
    all_stable = all(
        summary["stability"]["stability_pass"] for summary in full_fit.values()
    ) and all(
        values["all_stability_pass"] for values in cross_validation["aggregate"].values()
    )
    return {
        "schema_version": 1,
        "method": "stage_d_development_fit_and_stability_v1",
        "status": "DEVELOPMENT_COMPLETE" if all_stable else "REVISE",
        "development_sequence": DEVELOPMENT_SEQUENCE_ID,
        "locked_test_sequence_evaluated": False,
        "excluded_sequences": ["02"],
        "excluded_datasets": ["T98G_electrotaxis"],
        "reference_manifest_sha256": manifest_hash,
        "stage_c_development_artifact_sha256": _artifact_sha256(stage_c_development),
        "state_definition": STATE_DEFINITION,
        "uncertainty_weight_definition": "1 / (1 + norm(current_velocity)); fixed proxy before fitting",
        "operator_config": asdict(config),
        "candidate_registry": candidate_registry(),
        "development_track_count": len(groups),
        "transition_row_count": len(rows),
        "full_development_fit": full_fit,
        "cross_validation": cross_validation,
        "stability": {
            "all_candidates_and_folds_pass": bool(all_stable),
            "forecast_horizon": config.forecast_horizon,
            "max_abs_state_bound": DEFAULT_MAX_ROLLOUT_NORM,
        },
        "selection": {
            "performed": False,
            "reason": "Step 3 records development diagnostics only; no held-out performance is visible.",
        },
        "decision": "HOLD_PENDING_STEP_4_HELD_OUT_EVALUATION",
        "invariants": {
            "development_only_pass": True,
            "sequence02_evaluated": False,
            "t98g_evaluated": False,
            "truth_blind_transition_rows": True,
            "finite_and_stable_pass": bool(all_stable),
            "selection_performed": False,
        },
        "warning": (
            "Technical development artifact on U373 sequence 01 only. This step does not "
            "evaluate sequence 02 or T98G and does not support a biological claim."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("stage_c_development", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--forecast-horizon", type=int, default=DEFAULT_FORECAST_HORIZON)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        stage_c_development = json.loads(args.stage_c_development.read_text(encoding="utf-8"))
        result = fit_development_and_check_stability(
            manifest,
            stage_c_development,
            config=StageDOperatorConfig(forecast_horizon=args.forecast_horizon),
        )
    except (OSError, ValueError, RuntimeError, ArtifactValidationError, json.JSONDecodeError) as exc:
        print(f"Stage D development fit failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_stable_artifact(result), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {args.output} ({result['status']}; "
        f"{result['transition_row_count']} development rows; held-out evaluation not run)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
