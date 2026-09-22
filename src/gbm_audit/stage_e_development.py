"""Fit the registered Stage E development-only configuration on CTC sequence 01."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from gbm_audit.baseline import evaluate_benchmark as evaluate_nearest_neighbour
from gbm_audit.calibration import temperature_transform
from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.stage_e_data import (
    _dataset_entry,
    audit_ctc_archive,
    build_development_manifest,
    load_stage_e_contract,
)
from gbm_audit.stage_e_metrics import distance_confidence, link_score_report
from gbm_audit.uncertainty import evaluate_benchmark as evaluate_uncertainty


SPEED_GATE_GRID_UM_PER_MIN = (0.20, 0.35, 0.50, 0.75, 1.00, 1.25, 1.50, 2.00)
HYPOTHESIS_COUNT = 64


def _radius_px(speed_um_per_min: float, dataset: dict) -> float:
    pixel_size = float(dataset["pixel_size_um"][0])
    return speed_um_per_min * float(dataset["time_step_min"]) / pixel_size


def _clean_f1(baseline: dict) -> float:
    clean = next(item for item in baseline["scenarios"] if item["scenario_id"] == "clean_0")
    metrics = clean["sequence_results"]["01"]
    precision, recall = metrics["link_precision"], metrics["link_recall"]
    return 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0


def _select_radius(development_manifest: dict, *, seed: int, dataset: dict) -> tuple[dict, dict]:
    corruptions = build_corruption_benchmark(development_manifest, seed)
    candidates = []
    for speed in SPEED_GATE_GRID_UM_PER_MIN:
        radius = _radius_px(speed, dataset)
        baseline = evaluate_nearest_neighbour(development_manifest, corruptions, radius)
        candidates.append({
            "max_speed_um_per_min": speed,
            "max_distance_px": radius,
            "clean_link_f1": _clean_f1(baseline),
            "clean_link_precision": next(item for item in baseline["scenarios"] if item["scenario_id"] == "clean_0")["sequence_results"]["01"]["link_precision"],
            "clean_link_recall": next(item for item in baseline["scenarios"] if item["scenario_id"] == "clean_0")["sequence_results"]["01"]["link_recall"],
        })
    selected = min(candidates, key=lambda row: (-row["clean_link_f1"], row["max_speed_um_per_min"]))
    return selected, corruptions


def _uncertainty_summary(uncertainty: dict, max_distance_px: float) -> dict:
    raw_scores, calibrated_scores, distance_scores, labels = [], [], [], []
    temperature = float(uncertainty["calibration"]["temperature"])
    for scenario in uncertainty["scenarios"]:
        for link in scenario["sequence_results"]["01"]["posterior_links"]:
            raw_scores.append(float(link["probability"]))
            calibrated_scores.append(temperature_transform(float(link["probability"]), temperature))
            distance_scores.extend(distance_confidence([float(link["distance_px"])], max_distance_px))
            labels.append(int(bool(link["true_link"])))
    return {
        "edge_count": len(labels),
        "calibration_temperature": temperature,
        "distance_confidence": link_score_report(distance_scores, labels),
        "uncalibrated_uncertainty": link_score_report(raw_scores, labels),
        "calibrated_uncertainty": link_score_report(calibrated_scores, labels),
    }


def build_stage_e_development(
    manifest_path: Path,
    split_path: Path,
    archives: dict[str, Path],
    *,
    seed: int = 20260922,
) -> dict:
    """Run all registered development work without reading sequence-02 outcomes."""
    contract, split = load_stage_e_contract(manifest_path, split_path)
    expected_ids = {entry["dataset_id"] for entry in contract["datasets"]}
    if set(archives) != expected_ids:
        raise ValueError("Stage E development requires exactly the three registered archives")
    results = {}
    for offset, dataset_id in enumerate(sorted(archives)):
        dataset = _dataset_entry(contract, dataset_id)
        structural_audit = audit_ctc_archive(archives[dataset_id], dataset)
        development_manifest = build_development_manifest(archives[dataset_id], dataset)
        selected, corruptions = _select_radius(
            development_manifest, seed=seed + offset * 100000, dataset=dataset
        )
        uncertainty = evaluate_uncertainty(
            development_manifest,
            corruptions,
            count=HYPOTHESIS_COUNT,
            max_distance_px=selected["max_distance_px"],
            temperature_px=max(selected["max_distance_px"] / 2.0, 0.5),
            proposal_model="distance",
        )
        results[dataset_id] = {
            "structural_audit": structural_audit,
            "development_sequence": "01",
            "locked_test_sequence": "02",
            "development_manifest_summary": {
                "frames": development_manifest["sequences"]["01"]["frames"],
                "tracks": development_manifest["sequences"]["01"]["tracked_ids"],
                "consecutive_links": development_manifest["sequences"]["01"]["consecutive_links"],
                "pixel_size_um": development_manifest["pixel_size_um"],
                "time_step_min": development_manifest["time_step_min"],
            },
            "candidate_selection": {
                "rule": "maximize clean nearest-neighbour link F1; exact ties select the lower max-speed gate",
                "grid_max_speed_um_per_min": list(SPEED_GATE_GRID_UM_PER_MIN),
                "selected": selected,
            },
            "uncertainty_configuration": {
                "method": uncertainty["method"],
                "hypothesis_count": HYPOTHESIS_COUNT,
                "temperature_px": uncertainty["temperature_px"],
                "calibration_fit_sequence": "01",
                "metric_summary": _uncertainty_summary(uncertainty, selected["max_distance_px"]),
            },
        }
    return {
        "schema_version": 1,
        "method": "stage_e_development_only_multidomain_v1",
        "status": "DEVELOPMENT_CONFIGURATION_FROZEN_PENDING_CI",
        "dataset_manifest_sha256": split["dataset_manifest_sha256"],
        "split_lock_sha256": hashlib.sha256(split_path.read_bytes()).hexdigest(),
        "seed": seed,
        "registered_access_boundary": {
            "decoded_sequences": ["01"],
            "structurally_audited_locked_sequences": ["02"],
            "locked_test_coordinates_extracted": False,
            "locked_test_metrics_computed": False,
            "locked_test_outcomes_evaluated": False,
        },
        "datasets": results,
        "warning": "Development-only technical artifact. It supports no locked-test, biological, brain-slice or clinical claim.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/stage-e-dataset-manifest.json"))
    parser.add_argument("--split", type=Path, default=Path("docs/stage-e-split-lock.json"))
    parser.add_argument("--gowt1", type=Path, required=True)
    parser.add_argument("--hela", type=Path, required=True)
    parser.add_argument("--sim", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260922)
    args = parser.parse_args(argv)
    archives = {
        "CTC_Fluo-N2DH-GOWT1_training": args.gowt1,
        "CTC_DIC-C2DH-HeLa_training": args.hela,
        "CTC_Fluo-N2DH-SIM+_training": args.sim,
    }
    try:
        result = build_stage_e_development(args.manifest, args.split, archives, seed=args.seed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Stage E development failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['datasets'])} development datasets; sequence 02 remains locked)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
