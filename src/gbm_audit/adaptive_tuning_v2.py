"""Stage A v2 tuning with a truth-blind spatial search-area burden.

Version 1 compared total candidate-edge counts with fixed-16.  On sparse
sequence 01 that count is nearly identical to the number of true links, making
the old 20% gate mathematically impossible.  Version 2 measures the spatial
area searched by each source instead, while retaining the recall and noise
robustness gates.
"""

import argparse
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
from gbm_audit.adaptive_tuning import (
    DEVELOPMENT_SEQUENCE_ID,
    TUNING_SCENARIO_IDS,
    development_only_artifacts,
    _fixed_baseline_run,
)
from gbm_audit.candidate_benchmark import (
    MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME,
    MIN_CLEAN_TRUE_LINK_RECALL,
    summarize_run,
)
from gbm_audit.soft_dynamics import evaluate_soft_dynamics
from gbm_audit.uncertainty import evaluate_benchmark
from gbm_audit.validation import ArtifactValidationError, canonical_sha256


MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16 = 0.15
FIXED_16_RADIUS_PX = 16.0
BASE_RADIUS_PX = 8.0
MOTION_UNCERTAINTY_WEIGHTS = (2.0, 2.25, 2.5, 2.75, 3.0)
DENSITY_WEIGHTS_PX = (0.0, 2.0, 4.0)
COLD_START_UNCERTAINTIES_PX = (4.0,)
NEW_TRACK_SCORES_PX = (8.0, 9.0, 10.0, 11.0, 12.0)


def predefined_grid_v2() -> list[AdaptiveCandidateConfig]:
    """Return the deterministic 75-member v2 grid."""
    return [
        AdaptiveCandidateConfig(
            min_radius_px=BASE_RADIUS_PX,
            max_radius_px=FIXED_16_RADIUS_PX,
            motion_uncertainty_weight=motion_weight,
            density_weight_px=density_weight,
            density_radius_px=16.0,
            density_saturation_count=6,
            cold_start_uncertainty_px=cold_start,
            history_length=4,
            new_track_score_px=new_track_score,
        )
        for motion_weight, density_weight, cold_start, new_track_score in product(
            MOTION_UNCERTAINTY_WEIGHTS,
            DENSITY_WEIGHTS_PX,
            COLD_START_UNCERTAINTIES_PX,
            NEW_TRACK_SCORES_PX,
        )
    ]


def config_id_v2(config: AdaptiveCandidateConfig) -> str:
    return (
        f"m{config.motion_uncertainty_weight:g}"
        f"-d{config.density_weight_px:g}"
        f"-c{config.cold_start_uncertainty_px:g}"
        f"-n{config.new_track_score_px:g}"
    )


def _circle_union_area(radius_a: float, radius_b: float, center_distance: float) -> float:
    """Exact area of two circles, used as a truth-blind spatial-work proxy."""
    if center_distance >= radius_a + radius_b:
        return math.pi * (radius_a ** 2 + radius_b ** 2)
    if center_distance <= abs(radius_a - radius_b):
        return math.pi * max(radius_a, radius_b) ** 2
    cosine_a = (center_distance ** 2 + radius_a ** 2 - radius_b ** 2) / (
        2 * center_distance * radius_a
    )
    cosine_b = (center_distance ** 2 + radius_b ** 2 - radius_a ** 2) / (
        2 * center_distance * radius_b
    )
    cosine_a = max(-1.0, min(1.0, cosine_a))
    cosine_b = max(-1.0, min(1.0, cosine_b))
    triangle = math.sqrt(max(0.0, (
        -center_distance + radius_a + radius_b
    ) * (
        center_distance + radius_a - radius_b
    ) * (
        center_distance - radius_a + radius_b
    ) * (
        center_distance + radius_a + radius_b
    )))
    intersection = (
        radius_a ** 2 * math.acos(cosine_a)
        + radius_b ** 2 * math.acos(cosine_b)
        - 0.5 * triangle
    )
    return math.pi * (radius_a ** 2 + radius_b ** 2) - intersection


def _spatial_metrics(observations: list[dict], graph: dict) -> dict:
    by_id = {row["observation_id"]: row for row in observations}
    areas = []
    for gate in graph["source_gates"]:
        source = by_id[gate["source_observation_id"]]
        distance = math.hypot(
            float(source["x_px"]) - gate["predicted_x_px"],
            float(source["y_px"]) - gate["predicted_y_px"],
        )
        areas.append(_circle_union_area(
            BASE_RADIUS_PX, gate["adaptive_radius_px"], distance
        ))
    area = sum(areas) / len(areas) if areas else 0.0
    fixed_area = math.pi * FIXED_16_RADIUS_PX ** 2
    return {
        "source_gate_count": len(areas),
        "search_area_burden_px2_per_source": area,
        "fixed_16_search_area_px2_per_source": fixed_area,
        "search_area_reduction_vs_fixed_16_fraction": (
            1.0 - area / fixed_area if fixed_area else 0.0
        ),
    }


def _candidate_metrics(scenario_sequence: dict, config: AdaptiveCandidateConfig) -> dict:
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
    true_links = len(candidate_pairs & true_pairs)
    return {
        "candidate_edges": graph["candidate_edge_count"],
        "candidate_target_observations": graph["candidate_target_observations"],
        "candidate_burden_edges_per_target": graph["candidate_burden_edges_per_target"],
        "reference_links": len(true_pairs),
        "candidate_true_links": true_links,
        "candidate_true_link_recall": true_links / len(true_pairs) if true_pairs else 1.0,
        **_spatial_metrics(scenario_sequence["observations"], graph),
    }


def _score(summary: dict, fixed_8: dict, spatial: dict) -> dict:
    row = summary["sequence_results"][DEVELOPMENT_SEQUENCE_ID]
    narrow = fixed_8["sequence_results"][DEVELOPMENT_SEQUENCE_ID]
    noise_deterioration = (
        row["noise_sigma_5_soft_speed_error_px_per_frame"]
        - narrow["noise_sigma_5_soft_speed_error_px_per_frame"]
    )
    gates = {
        "clean_recall": row["clean_true_link_recall"] >= MIN_CLEAN_TRUE_LINK_RECALL,
        "spatial_search_area": (
            spatial["search_area_reduction_vs_fixed_16_fraction"]
            >= MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16
        ),
        "noise_robustness": (
            noise_deterioration
            <= MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME
        ),
    }
    return {
        **row,
        **spatial,
        "noise_deterioration_vs_fixed_8_px_per_frame": noise_deterioration,
        "gates": gates,
        "development_pass": all(gates.values()),
    }


def select_configuration_v2(evaluated: list[dict]) -> dict | None:
    passing = [row for row in evaluated if row["metrics"]["development_pass"]]
    if not passing:
        return None
    return min(passing, key=lambda row: (
        row["metrics"]["noise_sigma_5_soft_speed_error_px_per_frame"],
        row["metrics"]["clean_soft_speed_error_px_per_frame"],
        row["metrics"]["search_area_burden_px2_per_source"],
        row["config_id"],
    ))


def tune_development_v2(manifest: dict, corruptions: dict) -> dict:
    """Run v2 tuning on development sequence 01 only."""
    dev_manifest, dev_corruptions = development_only_artifacts(manifest, corruptions)
    fixed_8_uncertainty, fixed_8_soft, hard = _fixed_baseline_run(
        dev_manifest, dev_corruptions, 8.0
    )
    fixed_16_uncertainty, fixed_16_soft, _ = _fixed_baseline_run(
        dev_manifest, dev_corruptions, 16.0, hard
    )
    baseline_summaries = {
        "fixed_8": summarize_run("fixed_8", fixed_8_uncertainty, fixed_8_soft),
        "fixed_16": summarize_run("fixed_16", fixed_16_uncertainty, fixed_16_soft),
    }
    clean_sequence = dev_corruptions["scenarios"][0]["sequences"][DEVELOPMENT_SEQUENCE_ID]
    screening = []
    shortlisted = []
    for config in predefined_grid_v2():
        metrics = _candidate_metrics(clean_sequence, config)
        row = {
            "config_id": config_id_v2(config),
            "config": asdict(config),
            **metrics,
            "screen_pass": (
                metrics["candidate_true_link_recall"] >= MIN_CLEAN_TRUE_LINK_RECALL
                and metrics["search_area_reduction_vs_fixed_16_fraction"]
                >= MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16
            ),
        }
        screening.append(row)
        if row["screen_pass"]:
            shortlisted.append(config)

    screening_by_id = {row["config_id"]: row for row in screening}
    evaluated = []
    for config in shortlisted:
        uncertainty = evaluate_benchmark(
            dev_manifest, dev_corruptions,
            proposal_model="adaptive_v1", adaptive_config=config,
        )
        soft = evaluate_soft_dynamics(
            dev_manifest, dev_corruptions, uncertainty, hard
        )
        summary = summarize_run("adaptive_v1", uncertainty, soft)
        evaluated.append({
            "config_id": config_id_v2(config),
            "config": asdict(config),
            "metrics": _score(
                summary, baseline_summaries["fixed_8"],
                screening_by_id[config_id_v2(config)],
            ),
        })

    selected = select_configuration_v2(evaluated)
    return {
        "schema_version": 1,
        "method": "stage_a_development_only_adaptive_tuning_v2",
        "status": "LOCKED" if selected else "REVISE",
        "development_sequence": DEVELOPMENT_SEQUENCE_ID,
        "locked_test_sequence_evaluated": False,
        "scenario_ids": list(TUNING_SCENARIO_IDS),
        "grid": {
            "size": len(predefined_grid_v2()),
            "motion_uncertainty_weights": list(MOTION_UNCERTAINTY_WEIGHTS),
            "density_weights_px": list(DENSITY_WEIGHTS_PX),
            "cold_start_uncertainties_px": list(COLD_START_UNCERTAINTIES_PX),
            "new_track_scores_px": list(NEW_TRACK_SCORES_PX),
            "fixed_parameters": {
                "min_radius_px": BASE_RADIUS_PX,
                "max_radius_px": FIXED_16_RADIUS_PX,
                "density_radius_px": 16.0,
                "density_saturation_count": 6,
                "history_length": 4,
            },
        },
        "selection_rule": [
            "require clean recall >= 0.95",
            "require spatial search-area reduction >= 0.15",
            "require sigma=5 speed-error deterioration <= 1 px/frame",
            "minimize sigma=5 soft speed error",
            "minimize clean soft speed error",
            "minimize spatial search area",
            "lexicographic config_id tie-break",
        ],
        "burden_metric": {
            "name": "union_of_base_and_adaptive_source_gate_area",
            "units": "px2 per source with a following frame",
            "truth_blind": True,
            "fixed_16_reference_area_px2": math.pi * FIXED_16_RADIUS_PX ** 2,
            "minimum_reduction_fraction": MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16,
        },
        "thresholds": {
            "minimum_clean_true_link_recall": MIN_CLEAN_TRUE_LINK_RECALL,
            "minimum_spatial_search_area_reduction_vs_fixed_16_fraction": (
                MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16
            ),
            "maximum_noise_deterioration_vs_fixed_8_px_per_frame": (
                MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME
            ),
        },
        "development_reference_manifest_sha256": canonical_sha256(dev_manifest),
        "corruption_seed": dev_corruptions["seed"],
        "baselines": baseline_summaries,
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
        result = tune_development_v2(manifest, corruptions)
    except (OSError, ValueError, json.JSONDecodeError, ArtifactValidationError) as exc:
        print(f"Adaptive v2 tuning failed: {exc}", file=sys.stderr)
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
