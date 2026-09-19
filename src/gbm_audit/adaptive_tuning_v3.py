"""Development-only v3 tuning with calibrated posterior pruning."""

import argparse
from dataclasses import asdict
import json
from itertools import product
from pathlib import Path
import sys

from gbm_audit.adaptive_candidates import AdaptiveCandidateConfig
from gbm_audit.adaptive_tuning import (
    DEVELOPMENT_SEQUENCE_ID,
    TUNING_SCENARIO_IDS,
    _fixed_baseline_run,
    development_only_artifacts,
)
from gbm_audit.adaptive_tuning_v2 import (
    DENSITY_WEIGHTS_PX,
    FIXED_16_RADIUS_PX,
    MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16,
    MOTION_UNCERTAINTY_WEIGHTS,
    COLD_START_UNCERTAINTIES_PX,
    _candidate_metrics,
    _score,
    select_configuration_v2,
)
from gbm_audit.candidate_benchmark import (
    MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME,
    MIN_CLEAN_TRUE_LINK_RECALL,
    summarize_run,
)
from gbm_audit.soft_dynamics import evaluate_soft_dynamics
from gbm_audit.uncertainty import evaluate_benchmark
from gbm_audit.validation import ArtifactValidationError, canonical_sha256


POSTERIOR_PROBABILITY_FLOORS = (0.3, 0.4, 0.5, 0.6, 0.7)

LOCKED_ADAPTIVE_V3_CONFIG = AdaptiveCandidateConfig(
    min_radius_px=8.0,
    max_radius_px=16.0,
    motion_uncertainty_weight=2.75,
    density_weight_px=0.0,
    density_radius_px=16.0,
    density_saturation_count=6,
    cold_start_uncertainty_px=4.0,
    history_length=4,
    new_track_score_px=10.0,
    posterior_probability_floor=0.7,
)


def predefined_grid_v3() -> list[AdaptiveCandidateConfig]:
    """Return 375 configurations: v2 graph grid crossed with five floors."""
    configs = []
    for motion_weight, density_weight, cold_start, new_track, floor in product(
        MOTION_UNCERTAINTY_WEIGHTS,
        DENSITY_WEIGHTS_PX,
        COLD_START_UNCERTAINTIES_PX,
        (8.0, 9.0, 10.0, 11.0, 12.0),
        POSTERIOR_PROBABILITY_FLOORS,
    ):
        configs.append(AdaptiveCandidateConfig(
            min_radius_px=8.0,
            max_radius_px=FIXED_16_RADIUS_PX,
            motion_uncertainty_weight=motion_weight,
            density_weight_px=density_weight,
            density_radius_px=16.0,
            density_saturation_count=6,
            cold_start_uncertainty_px=cold_start,
            history_length=4,
            new_track_score_px=new_track,
            posterior_probability_floor=floor,
        ))
    return configs


def config_id_v3(config: AdaptiveCandidateConfig) -> str:
    return (
        f"m{config.motion_uncertainty_weight:g}"
        f"-d{config.density_weight_px:g}"
        f"-c{config.cold_start_uncertainty_px:g}"
        f"-n{config.new_track_score_px:g}"
        f"-p{config.posterior_probability_floor:g}"
    )


def tune_development_v3(manifest: dict, corruptions: dict) -> dict:
    dev_manifest, dev_corruptions = development_only_artifacts(manifest, corruptions)
    fixed_8_uncertainty, fixed_8_soft, hard = _fixed_baseline_run(
        dev_manifest, dev_corruptions, 8.0
    )
    fixed_8_summary = summarize_run("fixed_8", fixed_8_uncertainty, fixed_8_soft)
    clean_sequence = dev_corruptions["scenarios"][0]["sequences"][DEVELOPMENT_SEQUENCE_ID]
    screening = []
    shortlisted = []
    for config in predefined_grid_v3():
        metrics = _candidate_metrics(clean_sequence, config)
        row = {
            "config_id": config_id_v3(config),
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
        soft = evaluate_soft_dynamics(dev_manifest, dev_corruptions, uncertainty, hard)
        summary = summarize_run("adaptive_v1", uncertainty, soft)
        evaluated.append({
            "config_id": config_id_v3(config),
            "config": asdict(config),
            "metrics": _score(
                summary, fixed_8_summary, screening_by_id[config_id_v3(config)]
            ),
        })
    selected = select_configuration_v2(evaluated)
    if selected and selected["config_id"] != config_id_v3(LOCKED_ADAPTIVE_V3_CONFIG):
        raise RuntimeError(
            "development selection changed; update the locked configuration only "
            "through a new protocol revision"
        )
    return {
        "schema_version": 1,
        "method": "stage_a_development_only_adaptive_tuning_v3",
        "status": "LOCKED" if selected else "REVISE",
        "development_sequence": DEVELOPMENT_SEQUENCE_ID,
        "locked_test_sequence_evaluated": False,
        "scenario_ids": list(TUNING_SCENARIO_IDS),
        "grid": {
            "size": len(predefined_grid_v3()),
            "posterior_probability_floors": list(POSTERIOR_PROBABILITY_FLOORS),
            "motion_uncertainty_weights": list(MOTION_UNCERTAINTY_WEIGHTS),
            "density_weights_px": list(DENSITY_WEIGHTS_PX),
            "cold_start_uncertainties_px": list(COLD_START_UNCERTAINTIES_PX),
            "new_track_scores_px": [8.0, 9.0, 10.0, 11.0, 12.0],
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
        "baselines": {"fixed_8": fixed_8_summary},
        "screening_total": len(screening),
        "screening_pass_count": len(shortlisted),
        "screening": [row for row in screening if row["screen_pass"]],
        "evaluated": evaluated,
        "selected": selected,
        "locked_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG) if selected else None,
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
        result = tune_development_v3(manifest, corruptions)
    except (OSError, ValueError, json.JSONDecodeError, ArtifactValidationError) as exc:
        print(f"Adaptive v3 tuning failed: {exc}", file=sys.stderr)
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
