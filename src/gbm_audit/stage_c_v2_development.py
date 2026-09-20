"""Fit and cross-validate Stage C v2 on U373 sequence 01 only.

This module materializes no locked-test result.  It uses the existing U373
manifest and corruption benchmark only to fit the registered localization
model, produce leave-one-corruption-family-out predictive residuals, freeze a
split-conformal correction, and summarize the final sequence-01 development
ensemble.
"""

import argparse
from dataclasses import asdict
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from gbm_audit.adaptive_candidates import generate_adaptive_candidate_graph
from gbm_audit.adaptive_tuning import DEVELOPMENT_SEQUENCE_ID
from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.context_posterior import sample_exact_context_matchings
from gbm_audit.stage_c_dynamics import (
    aggregate_posterior_summaries,
    fit_development_speed_hmm,
    summarize_trajectories,
)
from gbm_audit.stage_c_v2_sampler import (
    StageCV2SamplerConfig,
    fit_localization_model,
    localization_diagnostics,
    localization_sigma,
    sample_stage_c_v2_ensemble,
)
from gbm_audit.validation import ArtifactValidationError, validate_corruptions, validate_manifest


SCENARIO_FAMILIES = (
    "clean", "missed_detection", "localization_noise", "fragmentation",
    "id_switch", "wrong_link", "false_positive",
)
DEFAULT_ENSEMBLE_COUNT = 256
DEFAULT_SEED = 20260919


def _stable_artifact(value):
    """Normalize floating-point serialization across supported NumPy versions."""
    if isinstance(value, float):
        rounded = round(value, 9)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, dict):
        return {key: _stable_artifact(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable_artifact(item) for item in value]
    return value


def _canonical_sha256(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _development_inputs(manifest: dict, corruptions: dict) -> tuple[dict, dict]:
    """Validate the split and return deep-copy-free sequence-01 views."""
    validate_manifest(manifest)
    validate_corruptions(corruptions, manifest)
    if DEVELOPMENT_SEQUENCE_ID not in manifest["sequences"]:
        raise ArtifactValidationError("manifest has no development sequence 01")
    if manifest["sequences"][DEVELOPMENT_SEQUENCE_ID].get("split") != "development":
        raise ArtifactValidationError("sequence 01 must be marked development")
    if "02" in manifest["sequences"] and manifest["sequences"]["02"].get("split") != "test":
        raise ArtifactValidationError("sequence 02 must remain test and excluded")
    scenario_families = {scenario["corruption"] for scenario in corruptions["scenarios"]}
    if scenario_families != set(SCENARIO_FAMILIES):
        raise ArtifactValidationError(
            f"corruption families drifted: expected {SCENARIO_FAMILIES}, "
            f"found {sorted(scenario_families)}"
        )
    for scenario in corruptions["scenarios"]:
        if set(scenario["sequences"]) != {DEVELOPMENT_SEQUENCE_ID, "02"}:
            raise ArtifactValidationError(
                f"scenario {scenario['scenario_id']} does not contain exactly 01 and 02"
            )
    return manifest["sequences"][DEVELOPMENT_SEQUENCE_ID], corruptions


def _reference_coordinates(sequence: dict) -> dict[str, dict]:
    return {
        f"ref_{track['track_id']:04d}_{point['frame']:04d}": point
        for track in sequence["tracks"]
        for point in track["observations"]
    }


def _calibration_rows(sequence: dict, scenario_sequence: dict) -> list[dict]:
    """Build reference residual rows for one development scenario only."""
    reference = _reference_coordinates(sequence)
    observations = scenario_sequence["observations"]
    graph = generate_adaptive_candidate_graph(observations, LOCKED_ADAPTIVE_V3_CONFIG)
    diagnostics = localization_diagnostics(observations, graph["candidate_edges"])
    rows = []
    for observation in observations:
        reference_point = reference.get(observation["observation_id"])
        if reference_point is None:
            # False positives have no reference residual and do not enter the
            # development localization fit.
            continue
        rows.append({
            "residual_dx_px": float(observation["x_px"]) - float(reference_point["x_px"]),
            "residual_dy_px": float(observation["y_px"]) - float(reference_point["y_px"]),
            **diagnostics[observation["observation_id"]],
        })
    return rows


def _scenario_map(corruptions: dict) -> dict[str, dict]:
    result = {scenario["scenario_id"]: scenario for scenario in corruptions["scenarios"]}
    if len(result) != len(corruptions["scenarios"]):
        raise ArtifactValidationError("duplicate corruption scenario IDs")
    return result


def _fit_family_models(sequence: dict, corruptions: dict) -> tuple[dict[str, dict], dict[str, list[dict]]]:
    scenarios = _scenario_map(corruptions)
    rows_by_family = {
        family: [] for family in SCENARIO_FAMILIES
    }
    for scenario in scenarios.values():
        rows_by_family[scenario["corruption"]].extend(
            _calibration_rows(sequence, scenario["sequences"][DEVELOPMENT_SEQUENCE_ID])
        )
    all_rows = [row for rows in rows_by_family.values() for row in rows]
    if not all_rows:
        raise ValueError("no sequence-01 localization calibration rows")
    models = {}
    for held_out in SCENARIO_FAMILIES:
        training_rows = [
            row for family, family_rows in rows_by_family.items() if family != held_out
            for row in family_rows
        ]
        models[held_out] = fit_localization_model(
            training_rows, fit_sequence_id=DEVELOPMENT_SEQUENCE_ID
        )
    models["all"] = fit_localization_model(all_rows, fit_sequence_id=DEVELOPMENT_SEQUENCE_ID)
    return models, rows_by_family


def _reference_observations(sequence: dict) -> tuple[list[dict], list[dict]]:
    observations, trajectories = [], []
    for track in sequence["tracks"]:
        ids = []
        for point in sorted(track["observations"], key=lambda row: row["frame"]):
            observation_id = f"ref_{track['track_id']:04d}_{point['frame']:04d}"
            observations.append({
                "observation_id": observation_id,
                "frame": point["frame"],
                "x_px": point["x_px"],
                "y_px": point["y_px"],
            })
            ids.append(observation_id)
        trajectories.append({"observation_ids": ids})
    return observations, trajectories


def _speed_interval(summaries: list[dict]) -> dict:
    values = [
        summary["mean_speed_px_per_frame"]
        for summary in summaries
        if summary.get("mean_speed_px_per_frame") is not None
        and math.isfinite(summary["mean_speed_px_per_frame"])
    ]
    if not values:
        return {"defined_samples": 0, "mean": None, "median": None, "p05": None, "p95": None}
    return {
        "defined_samples": len(values),
        "mean": float(np.mean(values)),
        "median": float(np.quantile(values, 0.5)),
        "p05": float(np.quantile(values, 0.05)),
        "p95": float(np.quantile(values, 0.95)),
    }


def _association_summary(observations: list[dict], graph: dict, hmm: dict, *, count: int, seed: int) -> dict:
    exact = sample_exact_context_matchings(
        observations, graph["candidate_edges"], count=count, seed=seed,
        temperature_px=4.0, new_track_score_px=LOCKED_ADAPTIVE_V3_CONFIG.new_track_score_px,
    )
    by_id = {row["observation_id"]: row for row in observations}
    summaries = [summarize_trajectories(sample["trajectories"], by_id, hmm)
                 for sample in exact["samples"]]
    aggregate = aggregate_posterior_summaries(summaries)
    return {
        "intervals": aggregate,
        "mean_speed": _speed_interval(summaries),
        "component_count": len(exact["components"]),
        "maximum_component_targets": max(
            (len(component["target_observation_ids"]) for component in exact["components"]),
            default=0,
        ),
        "invariants": exact["invariants"],
    }


def _predictive_summary(observations: list[dict], model: dict, hmm: dict, *, count: int, seed: int,
                        sampler_config: StageCV2SamplerConfig) -> dict:
    ensemble = sample_stage_c_v2_ensemble(
        observations, primary_config=LOCKED_ADAPTIVE_V3_CONFIG,
        localization_model=model, sampler_config=sampler_config, seed=seed,
    )
    summaries = []
    for sample in ensemble["samples"]:
        by_id = {row["observation_id"]: row for row in sample["observations"]}
        summaries.append(summarize_trajectories(sample["trajectories"], by_id, hmm))
    aggregate = aggregate_posterior_summaries(summaries)
    return {
        "intervals": aggregate,
        "mean_speed": _speed_interval(summaries),
        "graph_counts": {
            key: int(sum(sample["graph"][key] for sample in ensemble["samples"]) / count)
            for key in (
                "primary_edge_count", "recovery_adjacent_edge_count",
                "recovery_bridge_edge_count", "recovery_edge_count",
            )
        },
        "component_count": max((sample["component_count"] for sample in ensemble["samples"]), default=0),
        "maximum_component_targets": max(
            (sample["maximum_component_targets"] for sample in ensemble["samples"]), default=0
        ),
        "invariants": ensemble["invariants"],
    }


def _conformal_interval(interval: dict, quantile: float) -> dict:
    if interval.get("p05") is None or interval.get("p95") is None:
        return {"defined": False, "p05": None, "p95": None, "half_width_correction": quantile}
    return {
        "defined": True,
        "p05": float(interval["p05"] - quantile),
        "p95": float(interval["p95"] + quantile),
        "half_width_correction": float(quantile),
    }


def fit_and_cross_validate(
        manifest: dict, corruptions: dict, *, ensemble_count: int = DEFAULT_ENSEMBLE_COUNT,
        seed: int = DEFAULT_SEED) -> dict:
    """Fit sequence-01 values and return a compact, reproducible dev artifact."""
    if isinstance(ensemble_count, bool) or not isinstance(ensemble_count, int) or ensemble_count <= 0:
        raise ValueError("ensemble_count must be a positive integer")
    sequence, development_corruptions = _development_inputs(manifest, corruptions)
    models, rows_by_family = _fit_family_models(sequence, development_corruptions)
    scenario_map = _scenario_map(development_corruptions)
    hmm = fit_development_speed_hmm({"sequences": {DEVELOPMENT_SEQUENCE_ID: sequence}})
    if hmm["model"].get("status") != "ok":
        raise RuntimeError("sequence-01 reference cannot fit the registered HMM")
    reference_observations, reference_trajectories = _reference_observations(sequence)
    reference_summary = summarize_trajectories(reference_trajectories,
                                               {row["observation_id"]: row for row in reference_observations},
                                               hmm["model"])
    sampler_config = StageCV2SamplerConfig(ensemble_count=ensemble_count)

    cross_validation = []
    out_of_fold_residuals = []
    for held_out in SCENARIO_FAMILIES:
        model = models[held_out]
        heldout_scenarios = [scenario for scenario in scenario_map.values()
                             if scenario["corruption"] == held_out]
        family_residuals = []
        for index, scenario in enumerate(heldout_scenarios):
            sequence_input = scenario["sequences"][DEVELOPMENT_SEQUENCE_ID]["observations"]
            predictive = _predictive_summary(
                sequence_input, model, hmm["model"], count=ensemble_count,
                seed=seed + index + 1000 * (SCENARIO_FAMILIES.index(held_out) + 1),
                sampler_config=sampler_config,
            )
            median = predictive["mean_speed"]["median"]
            if median is None or reference_summary["mean_speed_px_per_frame"] is None:
                continue
            residual = abs(float(median) - float(reference_summary["mean_speed_px_per_frame"]))
            family_residuals.append(residual)
            out_of_fold_residuals.append(residual)
        standardized = []
        for row in rows_by_family[held_out]:
            sigma = localization_sigma(model, row)
            radial = math.hypot(row["residual_dx_px"], row["residual_dy_px"])
            standardized.append(radial / max(sigma, 1e-12))
        cross_validation.append({
            "held_out_family": held_out,
            "training_rows": sum(len(rows) for family, rows in rows_by_family.items() if family != held_out),
            "held_out_rows": len(rows_by_family[held_out]),
            "model": model,
            "held_out_scenario_count": len(heldout_scenarios),
            "mean_speed_abs_residuals_px_per_frame": family_residuals,
            "standardized_localization_residual_p50": float(np.quantile(standardized, 0.5)) if standardized else None,
            "standardized_localization_residual_p90": float(np.quantile(standardized, 0.9)) if standardized else None,
        })

    if not out_of_fold_residuals:
        raise RuntimeError("no out-of-fold mean-speed residuals were produced")
    conformal_quantile = float(np.quantile(out_of_fold_residuals, 0.9))

    scenarios = []
    for index, scenario in enumerate(development_corruptions["scenarios"]):
        sequence_input = scenario["sequences"][DEVELOPMENT_SEQUENCE_ID]["observations"]
        graph = generate_adaptive_candidate_graph(sequence_input, LOCKED_ADAPTIVE_V3_CONFIG)
        association = _association_summary(
            sequence_input, graph, hmm["model"], count=ensemble_count, seed=seed + index + 1
        )
        predictive = _predictive_summary(
            sequence_input, models["all"], hmm["model"], count=ensemble_count,
            seed=seed + index + 5000, sampler_config=sampler_config,
        )
        primary_interval = predictive["mean_speed"]
        scenarios.append({
            "scenario_id": scenario["scenario_id"],
            "corruption": scenario["corruption"],
            "severity": scenario["severity"],
            "sequence_id": DEVELOPMENT_SEQUENCE_ID,
            "association_only_interval": association["mean_speed"],
            "mechanistic_predictive_interval": primary_interval,
            "conformalized_interval": _conformal_interval(primary_interval, conformal_quantile),
            "association_only_diagnostics": {
                "component_count": association["component_count"],
                "maximum_component_targets": association["maximum_component_targets"],
                "invariants": association["invariants"],
            },
            "predictive_diagnostics": {
                "graph_counts": predictive["graph_counts"],
                "component_count": predictive["component_count"],
                "maximum_component_targets": predictive["maximum_component_targets"],
                "invariants": predictive["invariants"],
            },
        })

    return {
        "schema_version": 1,
        "method": "stage_c_v2_development_fit_and_cross_validation_v1",
        "status": "DEVELOPMENT_COMPLETE",
        "development_sequence": DEVELOPMENT_SEQUENCE_ID,
        "locked_test_sequence_evaluated": False,
        "excluded_sequences": ["02"],
        "excluded_datasets": ["T98G_electrotaxis"],
        "reference_manifest_sha256": _canonical_sha256(manifest),
        "archive_sha256": manifest["archive"]["sha256"],
        "corruption_seed": development_corruptions["seed"],
        "locked_adaptive_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG),
        "sampler_config": asdict(sampler_config),
        "frozen_hmm": hmm,
        "reference_summary": reference_summary,
        "localization_calibration": {
            "family_row_counts": {family: len(rows) for family, rows in rows_by_family.items()},
            "total_rows": sum(len(rows) for rows in rows_by_family.values()),
            "frozen_model": models["all"],
            "leave_one_family_out": cross_validation,
        },
        "conformal_calibration": {
            "method": "split_conformal_abs_oof_mean_speed_residual_v1",
            "held_out_unit": "corruption_family",
            "quantile": 0.9,
            "quantile_value_px_per_frame": conformal_quantile,
            "out_of_fold_residual_count": len(out_of_fold_residuals),
        },
        "scenarios": scenarios,
        "invariants": {
            "development_only_pass": True,
            "sequence02_evaluated": False,
            "t98g_evaluated": False,
            "ensemble_size_pass": all(
                scenario["predictive_diagnostics"]["invariants"]["sample_count_pass"]
                for scenario in scenarios
            ),
            "truth_blind_pass": all(
                scenario["predictive_diagnostics"]["invariants"]["truth_blind_pass"]
                for scenario in scenarios
            ),
            "compatibility_pass": all(
                all(scenario["predictive_diagnostics"]["invariants"][key]
                    for key in ("one_to_one_pass", "trajectory_partition_pass",
                                "candidate_graph_pass", "bridge_virtual_node_pass",
                                "exact_resource_bound_pass"))
                for scenario in scenarios
            ),
        },
        "warning": (
            "Development-only technical artifact on U373 sequence 01. Sequence 02 and "
            "T98G remain excluded and unevaluated; no biological validation claim is made."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ensemble-count", type=int, default=DEFAULT_ENSEMBLE_COUNT)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruptions = json.loads(args.corruptions.read_text(encoding="utf-8"))
        result = fit_and_cross_validate(
            manifest, corruptions, ensemble_count=args.ensemble_count, seed=args.seed
        )
    except (OSError, ValueError, RuntimeError, ArtifactValidationError, json.JSONDecodeError) as exc:
        print(f"Stage C v2 development fit failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(_stable_artifact(result), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(
        f"Wrote {args.output} ({result['status']}; "
        f"{len(result['scenarios'])} sequence-01 scenarios; T98G unevaluated)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

