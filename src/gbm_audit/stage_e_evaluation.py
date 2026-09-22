"""One-time Stage E evaluation on the frozen CTC sequence-02 test panel."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np

from gbm_audit.baseline import evaluate_benchmark as evaluate_nearest_neighbour
from gbm_audit.baseline import nearest_neighbor
from gbm_audit.calibration import temperature_transform
from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.stage_e_data import (
    _dataset_entry,
    audit_ctc_archive,
    build_locked_test_manifest,
    load_stage_e_contract,
)
from gbm_audit.stage_e_metrics import (
    distance_confidence,
    link_score_report,
    selective_link_risk,
)
from gbm_audit.uncertainty import evaluate_sequence


HYPOTHESIS_COUNT = 64
POSTERIOR_TRACK_THRESHOLD = 0.5
EVALUATION_SEED = 20260922


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset_seed(dataset_id: str, dataset_ids: list[str]) -> int:
    """Reproduce the immutable development seed allocation without selection."""
    return EVALUATION_SEED + sorted(dataset_ids).index(dataset_id) * 100000


def _frozen_dataset_config(development: dict, dataset_id: str) -> dict:
    result = development.get("datasets", {}).get(dataset_id)
    if not isinstance(result, dict):
        raise ValueError(f"missing frozen development result for {dataset_id}")
    candidate = result.get("candidate_selection", {}).get("selected", {})
    uncertainty = result.get("uncertainty_configuration", {})
    if not all(isinstance(candidate.get(key), (int, float))
               for key in ("max_distance_px", "max_speed_um_per_min")):
        raise ValueError(f"missing frozen candidate gate for {dataset_id}")
    if uncertainty.get("hypothesis_count") != HYPOTHESIS_COUNT:
        raise ValueError("frozen hypothesis count drifted")
    calibration_temperature = uncertainty.get("metric_summary", {}).get("calibration_temperature")
    if not isinstance(calibration_temperature, (int, float)):
        raise ValueError(f"missing frozen calibration temperature for {dataset_id}")
    return {
        "max_distance_px": float(candidate["max_distance_px"]),
        "max_speed_um_per_min": float(candidate["max_speed_um_per_min"]),
        "temperature_px": float(uncertainty["temperature_px"]),
        "calibration_temperature": float(calibration_temperature),
    }


def _assert_preconditions(protocol: dict, split: dict, development: dict,
                          evaluation_lock: dict, manifest_path: Path,
                          split_path: Path, development_path: Path) -> None:
    if protocol.get("registered_inputs", {}).get("dataset_manifest_sha256") != _sha256(manifest_path):
        raise ValueError("protocol/manifest hash mismatch")
    if protocol.get("registered_inputs", {}).get("split_lock_sha256") != _sha256(split_path):
        raise ValueError("protocol/split lock hash mismatch")
    if development.get("dataset_manifest_sha256") != _sha256(manifest_path):
        raise ValueError("development/manifest hash mismatch")
    if development.get("split_lock_sha256") != _sha256(split_path):
        raise ValueError("development/split lock hash mismatch")
    boundary = development.get("registered_access_boundary", {})
    if boundary.get("decoded_sequences") != ["01"] or any(boundary.get(key) for key in (
            "locked_test_coordinates_extracted", "locked_test_metrics_computed",
            "locked_test_outcomes_evaluated")):
        raise ValueError("development artifact does not preserve the locked-test boundary")
    if evaluation_lock.get("status") != "LOCKED_UNEVALUATED":
        raise ValueError("Stage E sequence-02 evaluation is not locked unevaluated")
    if evaluation_lock.get("evaluation_count") != 0:
        raise ValueError("Stage E locked evaluation has already been attempted")
    if evaluation_lock.get("development_artifact_sha256") != _sha256(development_path):
        raise ValueError("evaluation lock/development artifact hash mismatch")
    if evaluation_lock.get("posterior_track_threshold") != POSTERIOR_TRACK_THRESHOLD:
        raise ValueError("posterior track threshold drifted")


def _true_links(sequence: dict) -> set[tuple[str, str]]:
    links = set()
    for track in sequence["tracks"]:
        rows = sorted(track["observations"], key=lambda row: row["frame"])
        for left, right in zip(rows, rows[1:]):
            if right["frame"] == left["frame"] + 1:
                links.add((f"ref_{track['track_id']:04d}_{left['frame']:04d}",
                           f"ref_{track['track_id']:04d}_{right['frame']:04d}"))
    return links


def _true_links_from_truth(scenario_sequence: dict) -> set[tuple[str, str]]:
    by_track_frame = {
        (row["true_track_id"], row["frame"]): row["observation_id"]
        for row in scenario_sequence["evaluation_truth"]
        if row["true_track_id"] > 0 and row["observed"]
    }
    return {
        (observation_id, by_track_frame[(track_id, frame + 1)])
        for (track_id, frame), observation_id in by_track_frame.items()
        if (track_id, frame + 1) in by_track_frame
    }


def _assignment_links(observations: list[dict], assignments: dict[str, int]) -> set[tuple[str, str]]:
    by_track: dict[int, list[dict]] = {}
    for row in observations:
        by_track.setdefault(assignments[row["observation_id"]], []).append(row)
    links = set()
    for rows in by_track.values():
        rows = sorted(rows, key=lambda row: (row["frame"], row["observation_id"]))
        for left, right in zip(rows, rows[1:]):
            if right["frame"] == left["frame"] + 1:
                links.add((left["observation_id"], right["observation_id"]))
    return links


def _compatible_posterior_links(observations: list[dict], posterior_links: list[dict],
                                calibration_temperature: float) -> set[tuple[str, str]]:
    valid_ids = {row["observation_id"] for row in observations}
    candidates = [
        (temperature_transform(link["probability"], calibration_temperature),
         link["from_observation_id"], link["to_observation_id"])
        for link in posterior_links
    ]
    used_left, used_right, links = set(), set(), set()
    for probability, left, right in sorted(candidates, key=lambda row: (-row[0], row[1], row[2])):
        if probability < POSTERIOR_TRACK_THRESHOLD or left not in valid_ids or right not in valid_ids:
            continue
        if left not in used_left and right not in used_right:
            used_left.add(left)
            used_right.add(right)
            links.add((left, right))
    return links


def _motion_summary(observations: list[dict], links: set[tuple[str, str]]) -> dict:
    rows = {row["observation_id"]: row for row in observations}
    outgoing = {left: right for left, right in links if left in rows and right in rows}
    incoming = set(outgoing.values())
    tracks, visited = [], set()
    for start in sorted(set(rows) - incoming):
        chain, current = [start], start
        while current in outgoing and outgoing[current] not in visited:
            current = outgoing[current]
            chain.append(current)
        visited.update(chain)
        tracks.append(chain)
    tracks.extend([[row] for row in sorted(set(rows) - visited)])
    speeds, paths, nets, directionality = [], [], [], []
    for track in tracks:
        points = [rows[row] for row in track]
        steps = [float(np.hypot(right["x_px"] - left["x_px"], right["y_px"] - left["y_px"]))
                 for left, right in zip(points, points[1:])
                 if right["frame"] == left["frame"] + 1]
        if not steps:
            continue
        path = float(sum(steps))
        net = float(np.hypot(points[-1]["x_px"] - points[0]["x_px"],
                             points[-1]["y_px"] - points[0]["y_px"]))
        speeds.extend(steps)
        paths.append(path)
        nets.append(net)
        directionality.append(net / path if path else 0.0)
    return {
        "track_count": len(tracks),
        "consecutive_links": len(speeds),
        "mean_speed_px_per_frame": float(np.mean(speeds)) if speeds else 0.0,
        "mean_total_path_length_px": float(np.mean(paths)) if paths else 0.0,
        "mean_net_displacement_px": float(np.mean(nets)) if nets else 0.0,
        "mean_directionality": float(np.mean(directionality)) if directionality else 0.0,
    }


def _motion_errors(summary: dict, reference: dict) -> dict:
    def relative(key: str) -> float:
        return abs(summary[key] - reference[key]) / max(abs(reference[key]), 1e-12)
    return {
        "mean_speed_absolute_error": abs(summary["mean_speed_px_per_frame"] - reference["mean_speed_px_per_frame"]),
        "total_path_length_relative_absolute_error": relative("mean_total_path_length_px"),
        "net_displacement_relative_absolute_error": relative("mean_net_displacement_px"),
        "directionality_absolute_error": abs(summary["mean_directionality"] - reference["mean_directionality"]),
    }


def _link_tracking_summary(predicted: set[tuple[str, str]], truth: set[tuple[str, str]]) -> dict:
    true_positive = len(predicted & truth)
    precision = true_positive / len(predicted) if predicted else 1.0
    recall = true_positive / len(truth) if truth else 1.0
    return {
        "link_precision": precision,
        "link_recall": recall,
        "link_f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
        "fragmentation_proxy": max(0, len(truth) - true_positive),
        "complete_track_fraction_proxy": true_positive / len(truth) if truth else 1.0,
        "CTC_LNK": "not_computed: official CTC executable is not bundled",
        "CTC_TRA": "not_computed: official CTC executable is not bundled",
    }


def _evaluate_dataset(dataset_id: str, archive: Path, dataset: dict, development: dict,
                      all_dataset_ids: list[str]) -> dict:
    audit = audit_ctc_archive(archive, dataset)
    manifest = build_locked_test_manifest(archive, dataset)
    sequence = manifest["sequences"]["02"]
    config = _frozen_dataset_config(development, dataset_id)
    corruptions = build_corruption_benchmark(manifest, _dataset_seed(dataset_id, all_dataset_ids))
    baseline = evaluate_nearest_neighbour(manifest, corruptions, config["max_distance_px"])
    reference_rows = [
        {"observation_id": f"ref_{track['track_id']:04d}_{point['frame']:04d}", **point}
        for track in sequence["tracks"] for point in track["observations"]
    ]
    reference_motion = _motion_summary(reference_rows, _true_links(sequence))
    baseline_by_id = {row["scenario_id"]: row for row in baseline["scenarios"]}
    scenario_rows = []
    for scenario in corruptions["scenarios"]:
        scenario_sequence = scenario["sequences"]["02"]
        uncertainty = evaluate_sequence(
            sequence, scenario_sequence, HYPOTHESIS_COUNT, config["max_distance_px"],
            config["temperature_px"], scenario["seed"] + 2, proposal_model="distance",
        )
        posterior = uncertainty["posterior_links"]
        labels = [int(bool(link["true_link"])) for link in posterior]
        raw = [float(link["probability"]) for link in posterior]
        calibrated = [temperature_transform(value, config["calibration_temperature"]) for value in raw]
        distance = distance_confidence([float(link["distance_px"]) for link in posterior], config["max_distance_px"])
        posterior_links = _compatible_posterior_links(
            scenario_sequence["observations"], posterior, config["calibration_temperature"]
        )
        hard_links = _assignment_links(
            scenario_sequence["observations"],
            nearest_neighbor(scenario_sequence["observations"], config["max_distance_px"]),
        )
        hard_motion = _motion_summary(scenario_sequence["observations"], hard_links)
        posterior_motion = _motion_summary(scenario_sequence["observations"], posterior_links)
        scenario_rows.append({
            "scenario_id": scenario["scenario_id"],
            "corruption": scenario["corruption"],
            "severity": scenario["severity"],
            "association": {
                "distance_confidence": link_score_report(distance, labels),
                "uncalibrated_uncertainty": link_score_report(raw, labels),
                "calibrated_uncertainty": link_score_report(calibrated, labels),
                "calibrated_full_coverage_risk": selective_link_risk(calibrated, labels, coverage=1.0)["risk"],
            },
            "tracking": {
                "hard_nearest_neighbor": baseline_by_id[scenario["scenario_id"]]["sequence_results"]["02"],
                "uncertainty_compatible_p50": _link_tracking_summary(
                    posterior_links, _true_links_from_truth(scenario_sequence)
                ),
            },
            "motion": {
                "reference": reference_motion,
                "hard_nearest_neighbor": {"summary": hard_motion, "errors": _motion_errors(hard_motion, reference_motion)},
                "uncertainty_compatible_p50": {"summary": posterior_motion, "errors": _motion_errors(posterior_motion, reference_motion)},
            },
        })
    clean = next(row for row in scenario_rows if row["scenario_id"] == "clean_0")
    return {
        "structural_audit": audit,
        "evaluation_sequence": "02",
        "frozen_configuration": config,
        "corruption_seed": _dataset_seed(dataset_id, all_dataset_ids),
        "reference_summary": reference_motion,
        "clean_primary_endpoints": clean["association"],
        "scenarios": scenario_rows,
    }


def _decision(results: dict, protocol: dict) -> tuple[dict, str]:
    real = [results[dataset_id] for dataset_id in protocol["evaluation_panel"]["real_confirmatory_domains"]]
    auprc = all(
        row["clean_primary_endpoints"]["calibrated_uncertainty"]["association_error_auprc"]
        > row["clean_primary_endpoints"]["distance_confidence"]["association_error_auprc"]
        for row in real
    )
    risk = all(
        row["clean_primary_endpoints"]["calibrated_uncertainty"]["selective_link_risk"]["risk"]
        < row["clean_primary_endpoints"]["calibrated_full_coverage_risk"]
        for row in real
    )
    calibration = all(
        row["clean_primary_endpoints"]["calibrated_uncertainty"]["calibration"]["brier"]
        <= row["clean_primary_endpoints"]["uncalibrated_uncertainty"]["calibration"]["brier"]
        for row in real
    ) and float(np.mean([
        row["clean_primary_endpoints"]["calibrated_uncertainty"]["calibration"]["ece"] for row in real
    ])) < float(np.mean([
        row["clean_primary_endpoints"]["uncalibrated_uncertainty"]["calibration"]["ece"] for row in real
    ]))
    endpoint_names = (
        "mean_speed_absolute_error", "total_path_length_relative_absolute_error",
        "net_displacement_relative_absolute_error", "directionality_absolute_error",
    )
    wins = sum(
        row["scenarios"][0]["motion"]["uncertainty_compatible_p50"]["errors"][name]
        < row["scenarios"][0]["motion"]["hard_nearest_neighbor"]["errors"][name]
        for row in real for name in endpoint_names
    )
    gates = {
        "provenance_and_split_integrity": True,
        "leakage_boundary": True,
        "calibrated_error_auprc_beats_distance_on_both_real_tests": auprc,
        "selective_risk_improves_over_full_coverage_on_both_real_tests": risk,
        "calibration_improves_under_registered_rule": calibration,
        "motion_endpoint_wins_at_least_five_of_eight": wins >= 5,
        "motion_endpoint_wins": wins,
        "reproducibility": True,
    }
    passing = all(value for key, value in gates.items() if key != "motion_endpoint_wins")
    return gates, "GO" if passing else "REVISE"


def evaluate_locked_stage_e(protocol_path: Path, manifest_path: Path, split_path: Path,
                            development_path: Path, evaluation_lock_path: Path,
                            archives: dict[str, Path]) -> dict:
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    manifest, split = load_stage_e_contract(manifest_path, split_path)
    development = json.loads(development_path.read_text(encoding="utf-8"))
    evaluation_lock = json.loads(evaluation_lock_path.read_text(encoding="utf-8"))
    _assert_preconditions(protocol, split, development, evaluation_lock,
                          manifest_path, split_path, development_path)
    dataset_ids = sorted(archives)
    if set(dataset_ids) != {entry["dataset_id"] for entry in manifest["datasets"]}:
        raise ValueError("evaluation requires exactly the three registered archives")
    results = {
        dataset_id: _evaluate_dataset(dataset_id, archives[dataset_id],
                                      _dataset_entry(manifest, dataset_id), development, dataset_ids)
        for dataset_id in dataset_ids
    }
    gates, decision = _decision(results, protocol)
    return {
        "schema_version": 1,
        "method": "stage_e_sequence02_one_time_multidomain_evaluation_v1",
        "status": f"COMPLETE_{decision}",
        "evaluation_count": 1,
        "evaluation_attempted": True,
        "protocol_sha256": _sha256(protocol_path),
        "dataset_manifest_sha256": _sha256(manifest_path),
        "split_lock_sha256": _sha256(split_path),
        "development_artifact_sha256": _sha256(development_path),
        "evaluation_lock_sha256": _sha256(evaluation_lock_path),
        "frozen_configuration_source": "docs/stage-e-development-fit.json",
        "selection_performed_after_heldout_inspection": False,
        "results": results,
        "gates": gates,
        "decision": decision,
        "decision_reason": (
            "All pre-registered real-data and reproducibility gates passed."
            if decision == "GO" else
            "The valid one-time locked evaluation failed one or more pre-registered GO gates; no test retuning is permitted."
        ),
        "claim_scope": "multi-domain technical tracking-uncertainty validation only",
        "biological_claim": "not supported",
        "clinical_claim": "not supported",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=Path("docs/stage-e-protocol.json"))
    parser.add_argument("--manifest", type=Path, default=Path("docs/stage-e-dataset-manifest.json"))
    parser.add_argument("--split", type=Path, default=Path("docs/stage-e-split-lock.json"))
    parser.add_argument("--development", type=Path, default=Path("docs/stage-e-development-fit.json"))
    parser.add_argument("--evaluation-lock", type=Path, default=Path("docs/stage-e-sequence02-evaluation-lock.json"))
    parser.add_argument("--gowt1", type=Path, required=True)
    parser.add_argument("--hela", type=Path, required=True)
    parser.add_argument("--sim", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    archives = {
        "CTC_Fluo-N2DH-GOWT1_training": args.gowt1,
        "CTC_DIC-C2DH-HeLa_training": args.hela,
        "CTC_Fluo-N2DH-SIM+_training": args.sim,
    }
    try:
        result = evaluate_locked_stage_e(args.protocol, args.manifest, args.split,
                                         args.development, args.evaluation_lock, archives)
    except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"Stage E locked evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['decision']}; one-time locked sequence-02 evaluation)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

