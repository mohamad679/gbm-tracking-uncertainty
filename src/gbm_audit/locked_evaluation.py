"""Run the one-time locked Stage A v2 evaluation on both sequences."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sys

from gbm_audit.adaptive_candidates import generate_adaptive_candidate_graph
from gbm_audit.adaptive_tuning import _fixed_baseline_run
from gbm_audit.adaptive_tuning_v2 import _spatial_metrics
from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.candidate_benchmark import summarize_run
from gbm_audit.uncertainty import evaluate_benchmark
from gbm_audit.validation import (
    ArtifactValidationError,
    validate_corruptions,
    validate_manifest,
)


def _sequence_summary(adaptive: dict, fixed_8: dict, fixed_16: dict,
                      adaptive_area: dict, sequence_id: str) -> dict:
    candidate = adaptive["sequence_results"][sequence_id]
    narrow = fixed_8["sequence_results"][sequence_id]
    wide = fixed_16["sequence_results"][sequence_id]
    area_reduction = adaptive_area["search_area_reduction_vs_fixed_16_fraction"]
    noise_deterioration = (
        candidate["noise_sigma_5_soft_speed_error_px_per_frame"]
        - narrow["noise_sigma_5_soft_speed_error_px_per_frame"]
    )
    gates = {
        "clean_recall": candidate["clean_true_link_recall"] >= 0.95,
        "spatial_search_area": area_reduction >= 0.15,
        "noise_robustness": noise_deterioration <= 1.0,
    }
    return {
        "sequence_id": sequence_id,
        "split": "development" if sequence_id == "01" else "test",
        "clean_true_link_recall": candidate["clean_true_link_recall"],
        "clean_candidate_edges": candidate["clean_candidate_edges"],
        "clean_candidate_burden_edges_per_target": candidate[
            "clean_candidate_burden_edges_per_target"
        ],
        "clean_soft_speed_error_px_per_frame": candidate[
            "clean_soft_speed_error_px_per_frame"
        ],
        "noise_sigma_5_soft_speed_error_px_per_frame": candidate[
            "noise_sigma_5_soft_speed_error_px_per_frame"
        ],
        "fixed_8_noise_sigma_5_soft_speed_error_px_per_frame": narrow[
            "noise_sigma_5_soft_speed_error_px_per_frame"
        ],
        "fixed_16_clean_candidate_burden_edges_per_target": wide[
            "clean_candidate_burden_edges_per_target"
        ],
        **adaptive_area,
        "noise_deterioration_vs_fixed_8_px_per_frame": noise_deterioration,
        "gates": gates,
        "sequence_pass": all(gates.values()),
    }


def evaluate_locked(manifest: dict, corruptions: dict) -> dict:
    """Evaluate locked adaptive v3 and fixed comparators on both sequences."""
    validate_manifest(manifest)
    validate_corruptions(corruptions, manifest)
    sequence_ids = sorted(manifest["sequences"])
    if sequence_ids != ["01", "02"]:
        raise ArtifactValidationError(
            f"locked evaluation requires exactly sequences ['01', '02']; found {sequence_ids}"
        )
    if manifest["sequences"]["01"]["split"] != "development":
        raise ArtifactValidationError("sequence 01 must remain development")
    if manifest["sequences"]["02"]["split"] != "test":
        raise ArtifactValidationError("sequence 02 must remain test")

    fixed_8_uncertainty, fixed_8_soft, _ = _fixed_baseline_run(
        manifest, corruptions, 8.0
    )
    fixed_16_uncertainty, fixed_16_soft, _ = _fixed_baseline_run(
        manifest, corruptions, 16.0
    )
    adaptive_uncertainty = evaluate_benchmark(
        manifest,
        corruptions,
        proposal_model="adaptive_v1",
        adaptive_config=LOCKED_ADAPTIVE_V3_CONFIG,
    )
    from gbm_audit.dynamics import evaluate_dynamics
    from gbm_audit.soft_dynamics import evaluate_soft_dynamics

    hard = evaluate_dynamics(manifest, corruptions, fixed_8_uncertainty, max_distance_px=8.0)
    fixed_8_soft = evaluate_soft_dynamics(manifest, corruptions, fixed_8_uncertainty, hard)
    fixed_16_soft = evaluate_soft_dynamics(manifest, corruptions, fixed_16_uncertainty, hard)
    adaptive_soft = evaluate_soft_dynamics(manifest, corruptions, adaptive_uncertainty, hard)
    fixed_8_summary = summarize_run("fixed_8", fixed_8_uncertainty, fixed_8_soft)
    fixed_16_summary = summarize_run("fixed_16", fixed_16_uncertainty, fixed_16_soft)
    adaptive_summary = summarize_run("adaptive_v3", adaptive_uncertainty, adaptive_soft)

    clean = next(row for row in corruptions["scenarios"] if row["scenario_id"] == "clean_0")
    clean_areas = {}
    for sequence_id, scenario_sequence in clean["sequences"].items():
        graph = generate_adaptive_candidate_graph(
            scenario_sequence["observations"], LOCKED_ADAPTIVE_V3_CONFIG
        )
        clean_areas[sequence_id] = _spatial_metrics(
            scenario_sequence["observations"], graph
        )
    sequence_results = {
        sequence_id: _sequence_summary(
            adaptive_summary, fixed_8_summary, fixed_16_summary,
            clean_areas[sequence_id], sequence_id
        )
        for sequence_id in sequence_ids
    }
    return {
        "schema_version": 1,
        "method": "stage_a_locked_evaluation_v3",
        "status": "PASS" if all(row["sequence_pass"] for row in sequence_results.values()) else "REVISE",
        "locked_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG),
        "locked_config_id": "m2.75-d0-c4-n10-p0.7",
        "one_time_locked_test_evaluation": True,
        "sequence_ids": sequence_ids,
        "reference_manifest_sha256": corruptions["reference_manifest_sha256"],
        "corruption_seed": corruptions["seed"],
        "thresholds": {
            "minimum_clean_true_link_recall": 0.95,
            "minimum_spatial_search_area_reduction_vs_fixed_16_fraction": 0.15,
            "maximum_noise_deterioration_vs_fixed_8_px_per_frame": 1.0,
        },
        "baselines": {
            "fixed_8": fixed_8_summary,
            "fixed_16": fixed_16_summary,
        },
        "sequence_results": sequence_results,
        "warning": "Technical U373 Stage A decision; not biological validation or a claim of universal tracking performance.",
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
    except (OSError, ValueError, json.JSONDecodeError, ArtifactValidationError) as exc:
        print(f"Locked Stage A evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['status']})")
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
