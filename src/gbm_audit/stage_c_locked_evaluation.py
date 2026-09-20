"""One-time locked Stage C evaluation of posterior migration summaries."""

import argparse
import copy
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import sys

from gbm_audit.adaptive_candidates import generate_adaptive_candidate_graph
from gbm_audit.adaptive_tuning import DEVELOPMENT_SEQUENCE_ID, LOCKED_TEST_SEQUENCE_ID
from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.context_posterior import (
    DEFAULT_TRAJECTORY_ENSEMBLE_COUNT,
    sample_exact_context_matchings,
)
from gbm_audit.stage_c_dynamics import (
    LOCKED_DEVELOPMENT_HMM_MODEL,
    MIGRATION_SCALAR_FIELDS,
    MSD_LAGS,
    _reference_trajectories,
    sample_stage_a_ensemble,
    summarize_ensemble,
    summarize_trajectories,
)
from gbm_audit.validation import (
    ArtifactValidationError,
    canonical_sha256,
    validate_corruptions,
    validate_manifest,
)


MIN_COVERAGE = 0.80
MAX_COVERAGE = 0.98
MAX_MEDIAN_ABSOLUTE_ERROR_DETERIORATION = 0.10
MIN_REQUIRED_FIELD_COMPLETENESS = 0.95


def locked_test_artifacts(manifest: dict, corruptions: dict) -> tuple[dict, dict]:
    """Filter to the registered test split after validating the full contract."""
    validate_manifest(manifest)
    validate_corruptions(corruptions, manifest)
    if set(manifest["sequences"]) != {DEVELOPMENT_SEQUENCE_ID, LOCKED_TEST_SEQUENCE_ID}:
        raise ArtifactValidationError("Stage C requires exactly sequences 01 and 02")
    if manifest["sequences"][DEVELOPMENT_SEQUENCE_ID]["split"] != "development":
        raise ArtifactValidationError("sequence 01 must have split='development'")
    if manifest["sequences"][LOCKED_TEST_SEQUENCE_ID]["split"] != "test":
        raise ArtifactValidationError("sequence 02 must have split='test'")
    test_manifest = copy.deepcopy(manifest)
    test_manifest["sequences"] = {
        LOCKED_TEST_SEQUENCE_ID: copy.deepcopy(manifest["sequences"][LOCKED_TEST_SEQUENCE_ID])
    }
    test_corruptions = copy.deepcopy(corruptions)
    test_corruptions["reference_manifest_sha256"] = canonical_sha256(test_manifest)
    for scenario in test_corruptions["scenarios"]:
        if LOCKED_TEST_SEQUENCE_ID not in scenario["sequences"]:
            raise ArtifactValidationError(
                f"scenario {scenario['scenario_id']!r} is missing locked test sequence"
            )
        scenario["sequences"] = {
            LOCKED_TEST_SEQUENCE_ID: scenario["sequences"][LOCKED_TEST_SEQUENCE_ID]
        }
    validate_corruptions(test_corruptions, test_manifest)
    return test_manifest, test_corruptions


def _exact_ensemble_summary(exact: dict, observations: list[dict]) -> dict:
    invariant_pass = all((
        exact["invariants"]["one_to_one_pass"],
        exact["invariants"]["trajectory_partition_pass"],
        exact["invariants"]["candidate_graph_pass"],
    ))
    violations = sorted(set(
        exact["invariants"]["one_to_one_violation_sample_indices"]
        + exact["invariants"]["trajectory_partition_violation_sample_indices"]
        + [row["sample_index"] for row in exact["invariants"]["candidate_graph_violations"]]
    ))
    result = summarize_ensemble({
        "samples": exact["samples"],
        "invariants_pass": invariant_pass,
        "violation_sample_indices": violations,
    }, observations, LOCKED_DEVELOPMENT_HMM_MODEL)
    return {
        **result,
        "component_count": len(exact["components"]),
        "maximum_component_targets": max(
            (len(component["target_observation_ids"]) for component in exact["components"]),
            default=0,
        ),
    }


def _reference_is_defined(reference: dict, field: str) -> bool:
    if field in MIGRATION_SCALAR_FIELDS:
        return reference[field] is not None
    if field.startswith("msd_"):
        return reference["mean_squared_displacement_px2"][field.removeprefix("msd_")] is not None
    return reference["hmm_2state"].get("status") == "ok"


def _posterior_is_defined(posterior: dict, field: str) -> bool:
    if field in MIGRATION_SCALAR_FIELDS:
        return posterior["migration"][field]["defined_samples"] > 0
    if field.startswith("msd_"):
        return posterior["mean_squared_displacement_px2"][field.removeprefix("msd_")]["defined_samples"] > 0
    hmm = posterior["hmm_2state"]
    if hmm.get("status") != "ok":
        return False
    return all(
        interval["defined_samples"] > 0
        for interval in (
            hmm["state_occupancy"]
            + [entry for row in hmm["transition_matrix"] for entry in row]
            + [hmm["expected_state_switch_probability"]]
            + hmm["mean_dwell_length_steps"]
        )
    )


def _required_field_completeness(scenarios: list[dict], reference: dict) -> dict:
    fields = list(MIGRATION_SCALAR_FIELDS) + [f"msd_{lag}" for lag in MSD_LAGS] + ["hmm_2state"]
    eligible = produced = 0
    missing = []
    for scenario in scenarios:
        posterior = scenario["exact_context"]["posterior_summary"]
        for field in fields:
            if not _reference_is_defined(reference, field):
                continue
            eligible += 1
            if _posterior_is_defined(posterior, field):
                produced += 1
            else:
                missing.append({"scenario_id": scenario["scenario_id"], "field": field})
    return {
        "eligible_cases": eligible,
        "produced_cases": produced,
        "fraction": produced / eligible if eligible else 1.0,
        "missing": missing,
    }


def evaluate_locked(manifest: dict, corruptions: dict) -> dict:
    """Apply the frozen Stage C procedure to sequence 02 once, without refitting."""
    test_manifest, test_corruptions = locked_test_artifacts(manifest, corruptions)
    scenarios = []
    for scenario_index, scenario in enumerate(test_corruptions["scenarios"]):
        sequence = scenario["sequences"][LOCKED_TEST_SEQUENCE_ID]
        graph = generate_adaptive_candidate_graph(
            sequence["observations"], LOCKED_ADAPTIVE_V3_CONFIG
        )
        seed = scenario.get("seed", test_corruptions["seed"] + scenario_index * 1000) + 2
        exact = sample_exact_context_matchings(
            sequence["observations"], graph["candidate_edges"],
            count=DEFAULT_TRAJECTORY_ENSEMBLE_COUNT, seed=seed,
            temperature_px=4.0,
            new_track_score_px=LOCKED_ADAPTIVE_V3_CONFIG.new_track_score_px,
        )
        sampled = sample_stage_a_ensemble(
            sequence["observations"], graph["candidate_edges"],
            count=DEFAULT_TRAJECTORY_ENSEMBLE_COUNT, seed=seed,
        )
        scenarios.append({
            "scenario_id": scenario["scenario_id"],
            "corruption": scenario["corruption"],
            "severity": scenario["severity"],
            "sequence_id": LOCKED_TEST_SEQUENCE_ID,
            "candidate_edges": graph["candidate_edge_count"],
            "exact_context": _exact_ensemble_summary(exact, sequence["observations"]),
            "sampled_stage_a": summarize_ensemble(
                sampled, sequence["observations"], LOCKED_DEVELOPMENT_HMM_MODEL
            ),
        })

    reference_observations, reference_trajectories = _reference_trajectories(
        test_manifest["sequences"][LOCKED_TEST_SEQUENCE_ID]
    )
    reference_summary = summarize_trajectories(
        reference_trajectories, reference_observations, LOCKED_DEVELOPMENT_HMM_MODEL
    )
    covered, eligible, exact_errors, sampled_errors = 0, 0, [], []
    for scenario in scenarios:
        reference_speed = reference_summary["mean_speed_px_per_frame"]
        exact_speed = scenario["exact_context"]["posterior_summary"]["migration"]["mean_speed_px_per_frame"]
        sampled_speed = scenario["sampled_stage_a"]["posterior_summary"]["migration"]["mean_speed_px_per_frame"]
        if reference_speed is None or exact_speed["median"] is None or sampled_speed["median"] is None:
            continue
        eligible += 1
        covered += int(exact_speed["p05"] <= reference_speed <= exact_speed["p95"])
        exact_errors.append(abs(exact_speed["median"] - reference_speed))
        sampled_errors.append(abs(sampled_speed["median"] - reference_speed))
    coverage = {"covered": covered, "eligible": eligible, "fraction": covered / eligible if eligible else 0.0}
    accuracy = {
        "exact_median_absolute_error_px_per_frame": statistics.median(exact_errors) if exact_errors else None,
        "sampled_median_absolute_error_px_per_frame": statistics.median(sampled_errors) if sampled_errors else None,
    }
    completeness = _required_field_completeness(scenarios, reference_summary)
    invariants_pass = all(
        scenario["exact_context"]["invariants_pass"]
        and scenario["sampled_stage_a"]["invariants_pass"]
        and scenario["exact_context"]["maximum_component_targets"] <= 18
        for scenario in scenarios
    )
    gates = {
        "ensemble_and_component_invariants": invariants_pass,
        "mean_speed_interval_coverage": MIN_COVERAGE <= coverage["fraction"] <= MAX_COVERAGE,
        "mean_speed_error_noninferiority": (
            accuracy["exact_median_absolute_error_px_per_frame"] is not None
            and accuracy["exact_median_absolute_error_px_per_frame"]
            <= accuracy["sampled_median_absolute_error_px_per_frame"]
            + MAX_MEDIAN_ABSOLUTE_ERROR_DETERIORATION
        ),
        "required_summary_completeness": completeness["fraction"] >= MIN_REQUIRED_FIELD_COMPLETENESS,
    }
    return {
        "schema_version": 1,
        "method": "stage_c_locked_trajectory_evaluation_v1",
        "status": "PASS" if all(gates.values()) else "REVISE",
        "one_time_locked_test_evaluation": True,
        "locked_test_sequence": LOCKED_TEST_SEQUENCE_ID,
        "ensemble": {
            "count": DEFAULT_TRAJECTORY_ENSEMBLE_COUNT,
            "seed_policy": "scenario_seed_plus_sequence_id",
        },
        "locked_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG),
        "stage_b_calibration_temperature": 0.55,
        "frozen_hmm": {
            "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
            "fit_input": "uncorrupted_reference_trajectories",
            "model": LOCKED_DEVELOPMENT_HMM_MODEL,
        },
        "thresholds": {
            "minimum_mean_speed_interval_coverage": MIN_COVERAGE,
            "maximum_mean_speed_interval_coverage": MAX_COVERAGE,
            "maximum_median_absolute_error_deterioration_px_per_frame": (
                MAX_MEDIAN_ABSOLUTE_ERROR_DETERIORATION
            ),
            "minimum_required_summary_completeness": MIN_REQUIRED_FIELD_COMPLETENESS,
            "maximum_exact_component_targets": 18,
        },
        "gates": gates,
        "coverage": coverage,
        "accuracy": accuracy,
        "required_summary_completeness": completeness,
        "reference_summary": reference_summary,
        "reference_manifest_sha256": test_corruptions["reference_manifest_sha256"],
        "corruption_seed": test_corruptions["seed"],
        "scenarios": scenarios,
        "warning": (
            "Technical U373 benchmark only. The frozen HMM states are image-derived speed "
            "regimes, not validated biological phenotypes."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruptions = json.loads(args.corruptions.read_text(encoding="utf-8"))
        result = evaluate_locked(manifest, corruptions)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, ArtifactValidationError) as exc:
        print(f"Stage C locked evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
