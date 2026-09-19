"""Tune adaptive candidate generation on the development sequence only.

The search space and selection rule are deliberately fixed in source.  This
module refuses to expose locked-test observations to either screening or
downstream scoring.
"""

import argparse
import copy
from dataclasses import asdict
from itertools import product
import json
import math
from pathlib import Path
import sys

from gbm_audit.adaptive_candidates import (
    AdaptiveCandidateConfig,
    generate_adaptive_candidate_graph,
)
from gbm_audit.candidate_benchmark import (
    MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME,
    MIN_BURDEN_REDUCTION_VS_FIXED_16,
    MIN_CLEAN_TRUE_LINK_RECALL,
    summarize_run,
)
from gbm_audit.dynamics import evaluate_dynamics
from gbm_audit.soft_dynamics import evaluate_soft_dynamics
from gbm_audit.uncertainty import evaluate_benchmark
from gbm_audit.validation import (
    ArtifactValidationError,
    canonical_sha256,
    validate_corruptions,
    validate_manifest,
)


DEVELOPMENT_SEQUENCE_ID = "01"
LOCKED_TEST_SEQUENCE_ID = "02"
TUNING_SCENARIO_IDS = ("clean_0", "localization_noise_5p0")

# Pre-registered before the U373 development run.  Structural parameters stay
# fixed; the 3 x 3 x 3 grid changes only uncertainty expansion terms.
MOTION_UNCERTAINTY_WEIGHTS = (0.0, 1.0, 2.0)
DENSITY_WEIGHTS_PX = (0.0, 2.0, 4.0)
COLD_START_UNCERTAINTIES_PX = (0.0, 2.0, 4.0)


def predefined_grid() -> list[AdaptiveCandidateConfig]:
    """Return the deterministic 27-member development grid."""
    return [
        AdaptiveCandidateConfig(
            min_radius_px=8.0,
            max_radius_px=16.0,
            motion_uncertainty_weight=motion_weight,
            density_weight_px=density_weight,
            density_radius_px=16.0,
            density_saturation_count=6,
            cold_start_uncertainty_px=cold_start,
            history_length=4,
        )
        for motion_weight, density_weight, cold_start in product(
            MOTION_UNCERTAINTY_WEIGHTS,
            DENSITY_WEIGHTS_PX,
            COLD_START_UNCERTAINTIES_PX,
        )
    ]


def config_id(config: AdaptiveCandidateConfig) -> str:
    return (
        f"m{config.motion_uncertainty_weight:g}"
        f"-d{config.density_weight_px:g}"
        f"-c{config.cold_start_uncertainty_px:g}"
    )


def development_only_artifacts(manifest: dict, corruptions: dict) -> tuple[dict, dict]:
    """Return two-scenario development artifacts or fail closed on split drift."""
    validate_manifest(manifest)
    validate_corruptions(corruptions, manifest)
    development_ids = sorted(
        sequence_id for sequence_id, sequence in manifest["sequences"].items()
        if sequence["split"] == "development"
    )
    if development_ids != [DEVELOPMENT_SEQUENCE_ID]:
        raise ArtifactValidationError(
            f"tuning requires development sequence ['{DEVELOPMENT_SEQUENCE_ID}']; "
            f"found {development_ids}"
        )
    if LOCKED_TEST_SEQUENCE_ID in manifest["sequences"]:
        locked_split = manifest["sequences"][LOCKED_TEST_SEQUENCE_ID]["split"]
        if locked_split != "test":
            raise ArtifactValidationError(
                f"locked sequence {LOCKED_TEST_SEQUENCE_ID} must have split='test'"
            )

    development_manifest = copy.deepcopy(manifest)
    development_manifest["sequences"] = {
        DEVELOPMENT_SEQUENCE_ID: copy.deepcopy(
            manifest["sequences"][DEVELOPMENT_SEQUENCE_ID]
        )
    }
    development_hash = canonical_sha256(development_manifest)

    scenarios_by_id = {
        scenario["scenario_id"]: scenario for scenario in corruptions["scenarios"]
    }
    missing = [scenario_id for scenario_id in TUNING_SCENARIO_IDS
               if scenario_id not in scenarios_by_id]
    if missing:
        raise ArtifactValidationError(f"tuning scenarios are missing: {missing}")

    development_corruptions = copy.deepcopy(corruptions)
    development_corruptions["reference_manifest_sha256"] = development_hash
    development_corruptions["scenarios"] = []
    for scenario_id in TUNING_SCENARIO_IDS:
        scenario = copy.deepcopy(scenarios_by_id[scenario_id])
        if DEVELOPMENT_SEQUENCE_ID not in scenario["sequences"]:
            raise ArtifactValidationError(
                f"scenario {scenario_id!r} is missing development sequence"
            )
        scenario["sequences"] = {
            DEVELOPMENT_SEQUENCE_ID: scenario["sequences"][DEVELOPMENT_SEQUENCE_ID]
        }
        development_corruptions["scenarios"].append(scenario)

    validate_corruptions(development_corruptions, development_manifest)
    leaked = {
        sequence_id
        for scenario in development_corruptions["scenarios"]
        for sequence_id in scenario["sequences"]
        if sequence_id != DEVELOPMENT_SEQUENCE_ID
    }
    if leaked:
        raise ArtifactValidationError(f"locked-test leakage detected: {sorted(leaked)}")
    return development_manifest, development_corruptions


def _candidate_truth_metrics(scenario_sequence: dict, config: AdaptiveCandidateConfig) -> dict:
    graph = generate_adaptive_candidate_graph(scenario_sequence["observations"], config)
    truth_by_track_frame = {
        (row["true_track_id"], row["frame"]): row["observation_id"]
        for row in scenario_sequence["evaluation_truth"]
        if row["true_track_id"] > 0 and row["observed"]
    }
    true_pairs = {
        (observation_id, truth_by_track_frame[(track_id, frame + 1)])
        for (track_id, frame), observation_id in truth_by_track_frame.items()
        if (track_id, frame + 1) in truth_by_track_frame
    }
    candidate_pairs = {
        (edge["from_observation_id"], edge["to_observation_id"])
        for edge in graph["candidate_edges"]
    }
    true_link_count = len(candidate_pairs & true_pairs)
    return {
        "candidate_edges": graph["candidate_edge_count"],
        "candidate_target_observations": graph["candidate_target_observations"],
        "candidate_burden_edges_per_target": graph["candidate_burden_edges_per_target"],
        "reference_links": len(true_pairs),
        "candidate_true_links": true_link_count,
        "candidate_true_link_recall": (
            true_link_count / len(true_pairs) if true_pairs else 1.0
        ),
    }


def _fixed_baseline_run(manifest: dict, corruptions: dict, radius: float,
                        hard_dynamics: dict | None = None) -> tuple[dict, dict, dict]:
    uncertainty = evaluate_benchmark(
        manifest, corruptions, max_distance_px=radius, proposal_model="distance"
    )
    hard = hard_dynamics or evaluate_dynamics(
        manifest, corruptions, uncertainty, max_distance_px=8.0
    )
    soft = evaluate_soft_dynamics(manifest, corruptions, uncertainty, hard)
    return uncertainty, soft, hard


def _score(summary: dict, fixed_8: dict, fixed_16: dict) -> dict:
    row = summary["sequence_results"][DEVELOPMENT_SEQUENCE_ID]
    narrow = fixed_8["sequence_results"][DEVELOPMENT_SEQUENCE_ID]
    wide = fixed_16["sequence_results"][DEVELOPMENT_SEQUENCE_ID]
    burden_reduction = 1.0 - (
        row["clean_candidate_burden_edges_per_target"]
        / wide["clean_candidate_burden_edges_per_target"]
    )
    noise_deterioration = (
        row["noise_sigma_5_soft_speed_error_px_per_frame"]
        - narrow["noise_sigma_5_soft_speed_error_px_per_frame"]
    )
    gates = {
        "clean_recall": row["clean_true_link_recall"] >= MIN_CLEAN_TRUE_LINK_RECALL,
        "candidate_burden": burden_reduction >= MIN_BURDEN_REDUCTION_VS_FIXED_16,
        "noise_robustness": (
            noise_deterioration
            <= MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME
        ),
    }
    return {
        **row,
        "burden_reduction_vs_fixed_16_fraction": burden_reduction,
        "noise_deterioration_vs_fixed_8_px_per_frame": noise_deterioration,
        "gates": gates,
        "development_pass": all(gates.values()),
    }


def select_configuration(evaluated: list[dict]) -> dict | None:
    """Select robust passing config, then clean accuracy, burden and ID."""
    passing = [row for row in evaluated if row["metrics"]["development_pass"]]
    if not passing:
        return None
    return min(passing, key=lambda row: (
        row["metrics"]["noise_sigma_5_soft_speed_error_px_per_frame"],
        row["metrics"]["clean_soft_speed_error_px_per_frame"],
        row["metrics"]["clean_candidate_burden_edges_per_target"],
        row["config_id"],
    ))


def feasibility_bound(reference_links: int, fixed_16_candidate_edges: int,
                      target_observations: int) -> dict:
    """Return the best burden reduction compatible with the recall threshold."""
    minimum_true_edges = math.ceil(MIN_CLEAN_TRUE_LINK_RECALL * reference_links)
    minimum_burden = minimum_true_edges / target_observations
    maximum_reduction = 1.0 - minimum_true_edges / fixed_16_candidate_edges
    return {
        "reference_links": reference_links,
        "minimum_candidate_edges_for_recall_gate": minimum_true_edges,
        "fixed_16_candidate_edges": fixed_16_candidate_edges,
        "target_observations": target_observations,
        "minimum_possible_burden_at_recall_gate": minimum_burden,
        "maximum_possible_burden_reduction_vs_fixed_16_fraction": maximum_reduction,
        "recall_and_burden_gates_jointly_feasible": (
            maximum_reduction >= MIN_BURDEN_REDUCTION_VS_FIXED_16
        ),
    }


def tune_development(manifest: dict, corruptions: dict) -> dict:
    """Run the frozen grid without evaluating the locked test sequence."""
    dev_manifest, dev_corruptions = development_only_artifacts(manifest, corruptions)

    baseline_artifacts = {}
    fixed_8_uncertainty, fixed_8_soft, hard = _fixed_baseline_run(
        dev_manifest, dev_corruptions, 8.0
    )
    baseline_artifacts["fixed_8"] = (fixed_8_uncertainty, fixed_8_soft)
    for run_id, radius in (("fixed_12", 12.0), ("fixed_16", 16.0)):
        uncertainty, soft, _ = _fixed_baseline_run(
            dev_manifest, dev_corruptions, radius, hard
        )
        baseline_artifacts[run_id] = (uncertainty, soft)
    baseline_summaries = {
        run_id: summarize_run(run_id, *artifacts)
        for run_id, artifacts in baseline_artifacts.items()
    }

    clean_sequence = dev_corruptions["scenarios"][0]["sequences"][DEVELOPMENT_SEQUENCE_ID]
    wide_burden = baseline_summaries["fixed_16"]["sequence_results"][
        DEVELOPMENT_SEQUENCE_ID
    ]["clean_candidate_burden_edges_per_target"]
    screening = []
    shortlisted = []
    for config in predefined_grid():
        metrics = _candidate_truth_metrics(clean_sequence, config)
        burden_reduction = 1.0 - metrics["candidate_burden_edges_per_target"] / wide_burden
        row = {
            "config_id": config_id(config),
            "config": asdict(config),
            **metrics,
            "burden_reduction_vs_fixed_16_fraction": burden_reduction,
            "screen_pass": (
                metrics["candidate_true_link_recall"] >= MIN_CLEAN_TRUE_LINK_RECALL
                and burden_reduction >= MIN_BURDEN_REDUCTION_VS_FIXED_16
            ),
        }
        screening.append(row)
        if row["screen_pass"]:
            shortlisted.append(config)

    evaluated = []
    for config in shortlisted:
        uncertainty = evaluate_benchmark(
            dev_manifest,
            dev_corruptions,
            proposal_model="adaptive_v1",
            adaptive_config=config,
        )
        soft = evaluate_soft_dynamics(dev_manifest, dev_corruptions, uncertainty, hard)
        summary = summarize_run("adaptive_v1", uncertainty, soft)
        evaluated.append({
            "config_id": config_id(config),
            "config": asdict(config),
            "metrics": _score(
                summary, baseline_summaries["fixed_8"], baseline_summaries["fixed_16"]
            ),
        })

    selected = select_configuration(evaluated)
    wide = baseline_summaries["fixed_16"]["sequence_results"][DEVELOPMENT_SEQUENCE_ID]
    bound = feasibility_bound(
        screening[0]["reference_links"],
        wide["clean_candidate_edges"],
        wide["clean_target_observations"],
    )
    return {
        "schema_version": 1,
        "method": "stage_a_development_only_adaptive_tuning_v1",
        "status": "LOCKED" if selected else "REVISE",
        "development_sequence": DEVELOPMENT_SEQUENCE_ID,
        "locked_test_sequence_evaluated": False,
        "scenario_ids": list(TUNING_SCENARIO_IDS),
        "grid": {
            "size": len(predefined_grid()),
            "motion_uncertainty_weights": list(MOTION_UNCERTAINTY_WEIGHTS),
            "density_weights_px": list(DENSITY_WEIGHTS_PX),
            "cold_start_uncertainties_px": list(COLD_START_UNCERTAINTIES_PX),
            "fixed_parameters": {
                "min_radius_px": 8.0,
                "max_radius_px": 16.0,
                "density_radius_px": 16.0,
                "density_saturation_count": 6,
                "history_length": 4,
            },
        },
        "selection_rule": [
            "require all frozen development gates",
            "minimize sigma=5 soft speed error",
            "minimize clean soft speed error",
            "minimize clean candidate burden",
            "lexicographic config_id tie-break",
        ],
        "thresholds": {
            "minimum_clean_true_link_recall": MIN_CLEAN_TRUE_LINK_RECALL,
            "minimum_burden_reduction_vs_fixed_16_fraction": (
                MIN_BURDEN_REDUCTION_VS_FIXED_16
            ),
            "maximum_noise_deterioration_vs_fixed_8_px_per_frame": (
                MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME
            ),
        },
        "development_reference_manifest_sha256": canonical_sha256(dev_manifest),
        "corruption_seed": dev_corruptions["seed"],
        "baselines": baseline_summaries,
        "feasibility_bound": bound,
        "screening": screening,
        "evaluated": evaluated,
        "selected": selected,
        "warning": (
            "Development-only technical selection; sequence 02 remains locked and "
            "no biological generalization claim is made."
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
        result = tune_development(manifest, corruptions)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Adaptive tuning failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {args.output} ({len(result['screening'])} screened; "
        f"{len(result['evaluated'])} evaluated; {result['status']})"
    )
    return 0 if result["status"] == "LOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
