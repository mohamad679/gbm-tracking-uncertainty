"""Frozen three-experiment Dryad confirmatory evaluation on normalized glioma trajectories."""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np

from gbm_audit.calibration import temperature_transform
from gbm_audit.stage_e_metrics import link_score_report, selective_link_risk


HYPOTHESIS_COUNT = 64
MAX_SPEED_UM_PER_MIN = 1.5
CALIBRATION_TEMPERATURE = 0.25
POSTERIOR_TRACK_THRESHOLD = 0.5
RANDOM_SEED = 20260922
TRACK_BOOTSTRAP_REPS = 1000
EXPERIMENT_BOOTSTRAP_REPS = 10000
EXPECTED_EXPERIMENTS = ("experiment_1", "experiment_2", "experiment_3")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: str, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite {field}")
    return result


def load_normalized_reference(normalized_dir: Path, schema_lock_path: Path) -> dict[str, list[dict]]:
    manifest_path = normalized_dir / "normalized-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("status") != "NORMALIZED_THREE_EXPERIMENT_DRYAD_REFERENCE":
        raise ValueError("normalized Dryad manifest status is invalid")
    if manifest.get("biological_n") != 3:
        raise ValueError("normalized Dryad manifest must preserve biological n=3")
    if manifest.get("schema_lock_sha256") != _sha256(schema_lock_path):
        raise ValueError("normalized data were not produced from the committed schema lock")
    if sorted(manifest.get("experiments", {})) != list(EXPECTED_EXPERIMENTS):
        raise ValueError("normalized manifest must contain exactly three experiments")

    experiments: dict[str, list[dict]] = {}
    for experiment_id in EXPECTED_EXPERIMENTS:
        meta = manifest["experiments"][experiment_id]
        path = normalized_dir / meta["path"]
        if _sha256(path) != meta.get("sha256"):
            raise ValueError(f"normalized file hash mismatch for {experiment_id}")
        rows = []
        seen = set()
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            required = {"experiment_id", "cell_type", "track_id", "frame", "time_min", "x_um", "y_um"}
            if reader.fieldnames is None or not required.issubset(reader.fieldnames):
                raise ValueError(f"normalized schema drifted for {experiment_id}")
            for index, row in enumerate(reader):
                if row["experiment_id"] != experiment_id or row["cell_type"] != "glioma":
                    raise ValueError(f"normalized identity drifted in {experiment_id}")
                track_id = row["track_id"].strip()
                frame = int(row["frame"])
                key = (track_id, frame)
                if key in seen:
                    raise ValueError(f"duplicate track/frame in {experiment_id}: {key}")
                seen.add(key)
                rows.append({
                    "observation_id": f"{experiment_id}_{index:07d}",
                    "track_id": track_id,
                    "frame": frame,
                    "time_min": _finite(row["time_min"], "time_min"),
                    "x_um": _finite(row["x_um"], "x_um"),
                    "y_um": _finite(row["y_um"], "y_um"),
                })
        if not rows:
            raise ValueError(f"normalized experiment is empty: {experiment_id}")
        by_track: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            by_track[row["track_id"]].append(row)
        for track_id, track_rows in by_track.items():
            track_rows.sort(key=lambda item: item["frame"])
            for left, right in zip(track_rows, track_rows[1:]):
                if right["time_min"] <= left["time_min"]:
                    raise ValueError(f"non-increasing time in {experiment_id} track {track_id}")
        rows.sort(key=lambda item: (item["frame"], item["track_id"], item["observation_id"]))
        experiments[experiment_id] = rows
    return experiments


def _grid_candidates(observations: list[dict]) -> list[dict]:
    by_frame: dict[int, list[dict]] = defaultdict(list)
    for row in observations:
        by_frame[row["frame"]].append(row)
    edges = []
    for frame in sorted(by_frame):
        previous = by_frame.get(frame - 1)
        if not previous:
            continue
        for right in by_frame[frame]:
            for left in previous:
                dt = right["time_min"] - left["time_min"]
                if dt <= 0:
                    continue
                max_distance = MAX_SPEED_UM_PER_MIN * dt
                distance = float(np.hypot(right["x_um"] - left["x_um"], right["y_um"] - left["y_um"]))
                if distance <= max_distance:
                    edges.append({
                        "left": left["observation_id"],
                        "right": right["observation_id"],
                        "distance_um": distance,
                        "dt_min": dt,
                        "max_distance_um": max_distance,
                    })
    return sorted(edges, key=lambda row: (row["right"], row["left"]))


def _true_links(observations: list[dict]) -> set[tuple[str, str]]:
    by_track_frame = {(row["track_id"], row["frame"]): row["observation_id"] for row in observations}
    return {
        (observation_id, by_track_frame[(track_id, frame + 1)])
        for (track_id, frame), observation_id in by_track_frame.items()
        if (track_id, frame + 1) in by_track_frame
    }


def _weighted_choice(rng: random.Random, choices: list[tuple[tuple[int | None, str | None], float]]) -> tuple[int | None, str | None]:
    total = sum(weight for _, weight in choices)
    if total <= 0 or not math.isfinite(total):
        raise ValueError("invalid hypothesis weights")
    point = rng.random() * total
    for choice, weight in choices:
        point -= weight
        if point <= 0:
            return choice
    return choices[-1][0]


def _sample_probabilities(observations: list[dict], edges: list[dict], seed: int) -> dict[tuple[str, str], float]:
    by_frame: dict[int, list[dict]] = defaultdict(list)
    for row in observations:
        by_frame[row["frame"]].append(row)
    edge_by_pair = {(edge["left"], edge["right"]): edge for edge in edges}
    candidates_by_target: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        candidates_by_target[edge["right"]].append(edge["left"])

    counts: Counter[tuple[str, str]] = Counter()
    new_track_weight = math.exp(-2.0)
    for repeat in range(HYPOTHESIS_COUNT):
        rng = random.Random(seed + repeat)
        active: dict[str, tuple[int, int]] = {}
        next_track = 1
        for frame in sorted(by_frame):
            rows = list(by_frame[frame])
            rng.shuffle(rows)
            previous = active
            previous_rank = {obs_id: rank for rank, obs_id in enumerate(previous)}
            current: dict[str, tuple[int, int]] = {}
            used_tracks: set[int] = set()
            for row in rows:
                target = row["observation_id"]
                source_ids = [source for source in candidates_by_target.get(target, ()) if source in previous]
                source_ids.sort(key=lambda source: previous_rank[source])
                choices: list[tuple[tuple[int | None, str | None], float]] = []
                for source in source_ids:
                    track_id, source_frame = previous[source]
                    if source_frame != frame - 1 or track_id in used_tracks:
                        continue
                    edge = edge_by_pair[(source, target)]
                    temperature = edge["max_distance_um"] / 2.0
                    choices.append(((track_id, source), math.exp(-edge["distance_um"] / temperature)))
                choices.append(((None, None), new_track_weight))
                track_id, source = _weighted_choice(rng, choices)
                if track_id is None:
                    track_id = next_track
                    next_track += 1
                else:
                    used_tracks.add(track_id)
                    counts[(source, target)] += 1
                current[target] = (track_id, frame)
            active = current
    return {pair: counts[pair] / HYPOTHESIS_COUNT for pair in edge_by_pair}


def _nearest_neighbor_links(observations: list[dict], edges: list[dict]) -> set[tuple[str, str]]:
    by_frame: dict[int, list[dict]] = defaultdict(list)
    for row in observations:
        by_frame[row["frame"]].append(row)
    edges_by_target: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for edge in edges:
        edges_by_target[edge["right"]].append((edge["left"], edge["distance_um"]))
    active: dict[str, tuple[int, int]] = {}
    next_track = 1
    links = set()
    for frame in sorted(by_frame):
        candidates = []
        for row in by_frame[frame]:
            target = row["observation_id"]
            for source, distance in edges_by_target.get(target, ()):
                state = active.get(source)
                if state is not None and state[1] == frame - 1:
                    candidates.append((distance, target, state[0], source))
        used_targets, used_tracks = set(), set()
        assignment: dict[str, int] = {}
        source_for_target: dict[str, str] = {}
        for _, target, track_id, source in sorted(candidates):
            if target in used_targets or track_id in used_tracks:
                continue
            used_targets.add(target)
            used_tracks.add(track_id)
            assignment[target] = track_id
            source_for_target[target] = source
        current = {}
        for row in sorted(by_frame[frame], key=lambda item: item["observation_id"]):
            target = row["observation_id"]
            if target not in assignment:
                assignment[target] = next_track
                next_track += 1
            else:
                links.add((source_for_target[target], target))
            current[target] = (assignment[target], frame)
        active = current
    return links


def _posterior_links(probabilities: dict[tuple[str, str], float]) -> set[tuple[str, str]]:
    candidates = [
        (temperature_transform(probability, CALIBRATION_TEMPERATURE), left, right)
        for (left, right), probability in probabilities.items()
    ]
    used_left, used_right, selected = set(), set(), set()
    for probability, left, right in sorted(candidates, key=lambda row: (-row[0], row[1], row[2])):
        if probability < POSTERIOR_TRACK_THRESHOLD:
            continue
        if left not in used_left and right not in used_right:
            used_left.add(left)
            used_right.add(right)
            selected.add((left, right))
    return selected


def _link_summary(predicted: set[tuple[str, str]], truth: set[tuple[str, str]]) -> dict:
    tp = len(predicted & truth)
    precision = tp / len(predicted) if predicted else 1.0
    recall = tp / len(truth) if truth else 1.0
    return {
        "true_positive": tp,
        "predicted": len(predicted),
        "reference": len(truth),
        "precision": precision,
        "recall": recall,
        "f1": 2 * precision * recall / (precision + recall) if precision + recall else 0.0,
    }


def _motion_summary(observations: list[dict], links: set[tuple[str, str]]) -> dict:
    rows = {row["observation_id"]: row for row in observations}
    outgoing = {left: right for left, right in links if left in rows and right in rows}
    incoming = set(outgoing.values())
    chains, visited = [], set()
    for start in sorted(set(rows) - incoming):
        chain, current = [start], start
        while current in outgoing and outgoing[current] not in visited:
            current = outgoing[current]
            chain.append(current)
        visited.update(chain)
        chains.append(chain)
    chains.extend([[obs_id] for obs_id in sorted(set(rows) - visited)])
    speeds, paths, nets, directionality = [], [], [], []
    for chain in chains:
        points = [rows[item] for item in chain]
        steps = []
        for left, right in zip(points, points[1:]):
            if right["frame"] != left["frame"] + 1:
                continue
            dt = right["time_min"] - left["time_min"]
            if dt <= 0:
                continue
            distance = float(np.hypot(right["x_um"] - left["x_um"], right["y_um"] - left["y_um"]))
            steps.append((distance, dt))
        if not steps:
            continue
        path = float(sum(distance for distance, _ in steps))
        net = float(np.hypot(points[-1]["x_um"] - points[0]["x_um"], points[-1]["y_um"] - points[0]["y_um"]))
        speeds.extend(distance / dt for distance, dt in steps)
        paths.append(path)
        nets.append(net)
        directionality.append(net / path if path else 0.0)
    return {
        "trajectory_segments": len(chains),
        "consecutive_links": len(speeds),
        "mean_speed_um_per_min": float(np.mean(speeds)) if speeds else 0.0,
        "mean_total_path_length_um": float(np.mean(paths)) if paths else 0.0,
        "mean_net_displacement_um": float(np.mean(nets)) if nets else 0.0,
        "mean_directionality": float(np.mean(directionality)) if directionality else 0.0,
    }


def _motion_errors(summary: dict, reference: dict) -> dict:
    def relative(key: str) -> float:
        return abs(summary[key] - reference[key]) / max(abs(reference[key]), 1e-12)
    return {
        "mean_speed_absolute_error_um_per_min": abs(summary["mean_speed_um_per_min"] - reference["mean_speed_um_per_min"]),
        "total_path_length_relative_absolute_error": relative("mean_total_path_length_um"),
        "net_displacement_relative_absolute_error": relative("mean_net_displacement_um"),
        "directionality_absolute_error": abs(summary["mean_directionality"] - reference["mean_directionality"]),
    }


def _percentile_interval(values: list[float], level: float = 0.95) -> list[float]:
    if not values:
        return [float("nan"), float("nan")]
    alpha = (1.0 - level) / 2.0
    return [float(np.quantile(values, alpha)), float(np.quantile(values, 1.0 - alpha))]


def _f1(tp: int, predicted: int, reference: int) -> float:
    precision = tp / predicted if predicted else 1.0
    recall = tp / reference if reference else 1.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _track_cluster_bootstrap(
    observations: list[dict], edges: list[dict], labels: list[int], distance_scores: list[float],
    calibrated_scores: list[float], hard_links: set[tuple[str, str]], uncertainty_links: set[tuple[str, str]],
    truth: set[tuple[str, str]], seed: int,
) -> tuple[dict, dict[str, list[float]]]:
    obs_to_track = {row["observation_id"]: row["track_id"] for row in observations}
    clusters: dict[str, list[int]] = defaultdict(list)
    for index, edge in enumerate(edges):
        clusters[obs_to_track[edge["right"]]].append(index)
    track_ids = sorted(clusters)
    if not track_ids:
        raise ValueError("no target-track clusters available for bootstrap")

    ref_by_track: Counter[str] = Counter()
    hard_pred_by_track: Counter[str] = Counter()
    hard_tp_by_track: Counter[str] = Counter()
    unc_pred_by_track: Counter[str] = Counter()
    unc_tp_by_track: Counter[str] = Counter()
    for left, right in truth:
        ref_by_track[obs_to_track[right]] += 1
    for pair in hard_links:
        track_id = obs_to_track[pair[1]]
        hard_pred_by_track[track_id] += 1
        if pair in truth:
            hard_tp_by_track[track_id] += 1
    for pair in uncertainty_links:
        track_id = obs_to_track[pair[1]]
        unc_pred_by_track[track_id] += 1
        if pair in truth:
            unc_tp_by_track[track_id] += 1

    samples = {"auprc_effect": [], "selective_risk_benefit": [], "link_f1_effect": []}
    rng = random.Random(seed)
    for _ in range(TRACK_BOOTSTRAP_REPS):
        sampled_tracks = [rng.choice(track_ids) for _ in track_ids]
        indexes = [index for track_id in sampled_tracks for index in clusters[track_id]]
        sampled_labels = [labels[index] for index in indexes]
        sampled_distance = [distance_scores[index] for index in indexes]
        sampled_calibrated = [calibrated_scores[index] for index in indexes]
        distance_report = link_score_report(sampled_distance, sampled_labels)
        calibrated_report = link_score_report(sampled_calibrated, sampled_labels)
        full_risk = selective_link_risk(sampled_calibrated, sampled_labels, coverage=1.0)["risk"]
        samples["auprc_effect"].append(
            calibrated_report["association_error_auprc"] - distance_report["association_error_auprc"]
        )
        samples["selective_risk_benefit"].append(full_risk - calibrated_report["selective_link_risk"]["risk"])
        ref = sum(ref_by_track[track_id] for track_id in sampled_tracks)
        hard_pred = sum(hard_pred_by_track[track_id] for track_id in sampled_tracks)
        hard_tp = sum(hard_tp_by_track[track_id] for track_id in sampled_tracks)
        unc_pred = sum(unc_pred_by_track[track_id] for track_id in sampled_tracks)
        unc_tp = sum(unc_tp_by_track[track_id] for track_id in sampled_tracks)
        samples["link_f1_effect"].append(_f1(unc_tp, unc_pred, ref) - _f1(hard_tp, hard_pred, ref))

    public = {
        "unit": "target/reference track within experiment",
        "repetitions": TRACK_BOOTSTRAP_REPS,
        "confidence_level": 0.95,
        "auprc_effect_uncertainty_minus_distance_ci": _percentile_interval(samples["auprc_effect"]),
        "selective_risk_benefit_full_minus_selective_ci": _percentile_interval(samples["selective_risk_benefit"]),
        "link_f1_effect_uncertainty_minus_hard_ci": _percentile_interval(samples["link_f1_effect"]),
    }
    return public, samples


def evaluate_experiment(experiment_id: str, observations: list[dict], seed: int) -> tuple[dict, dict[str, list[float]]]:
    edges = _grid_candidates(observations)
    truth = _true_links(observations)
    probabilities = _sample_probabilities(observations, edges, seed)
    labels = [int((edge["left"], edge["right"]) in truth) for edge in edges]
    raw = [probabilities[(edge["left"], edge["right"])] for edge in edges]
    calibrated = [temperature_transform(value, CALIBRATION_TEMPERATURE) for value in raw]
    distance = [max(0.0, min(1.0, 1.0 - edge["distance_um"] / edge["max_distance_um"])) for edge in edges]
    hard_links = _nearest_neighbor_links(observations, edges)
    uncertainty_links = _posterior_links(probabilities)
    reference_motion = _motion_summary(observations, truth)
    hard_motion = _motion_summary(observations, hard_links)
    uncertainty_motion = _motion_summary(observations, uncertainty_links)
    distance_report = link_score_report(distance, labels)
    calibrated_report = link_score_report(calibrated, labels)
    full_risk = selective_link_risk(calibrated, labels, coverage=1.0)["risk"]
    hard_tracking = _link_summary(hard_links, truth)
    uncertainty_tracking = _link_summary(uncertainty_links, truth)
    track_bootstrap, bootstrap_samples = _track_cluster_bootstrap(
        observations, edges, labels, distance, calibrated, hard_links, uncertainty_links, truth, seed + 500000,
    )
    track_count = len({row["track_id"] for row in observations})
    return {
        "experiment_id": experiment_id,
        "track_count": track_count,
        "observation_count": len(observations),
        "candidate_graph": {
            "candidate_edges": len(edges),
            "reference_links": len(truth),
            "reference_link_coverage": sum(labels) / len(truth) if truth else 1.0,
        },
        "association": {
            "distance_confidence": distance_report,
            "uncalibrated_uncertainty": link_score_report(raw, labels),
            "calibrated_uncertainty": calibrated_report,
            "calibrated_full_coverage_risk": full_risk,
        },
        "tracking": {
            "hard_nearest_neighbor": hard_tracking,
            "uncertainty_compatible_p50": uncertainty_tracking,
        },
        "motion": {
            "reference": reference_motion,
            "hard_nearest_neighbor": {"summary": hard_motion, "errors": _motion_errors(hard_motion, reference_motion)},
            "uncertainty_compatible_p50": {"summary": uncertainty_motion, "errors": _motion_errors(uncertainty_motion, reference_motion)},
        },
        "paired_effects": {
            "association_error_auprc_uncertainty_minus_distance": calibrated_report["association_error_auprc"] - distance_report["association_error_auprc"],
            "selective_risk_benefit_full_minus_selective": full_risk - calibrated_report["selective_link_risk"]["risk"],
            "link_f1_uncertainty_minus_hard": uncertainty_tracking["f1"] - hard_tracking["f1"],
            "mean_speed_error_benefit_hard_minus_uncertainty": _motion_errors(hard_motion, reference_motion)["mean_speed_absolute_error_um_per_min"] - _motion_errors(uncertainty_motion, reference_motion)["mean_speed_absolute_error_um_per_min"],
            "path_length_error_benefit_hard_minus_uncertainty": _motion_errors(hard_motion, reference_motion)["total_path_length_relative_absolute_error"] - _motion_errors(uncertainty_motion, reference_motion)["total_path_length_relative_absolute_error"],
            "net_displacement_error_benefit_hard_minus_uncertainty": _motion_errors(hard_motion, reference_motion)["net_displacement_relative_absolute_error"] - _motion_errors(uncertainty_motion, reference_motion)["net_displacement_relative_absolute_error"],
            "directionality_error_benefit_hard_minus_uncertainty": _motion_errors(hard_motion, reference_motion)["directionality_absolute_error"] - _motion_errors(uncertainty_motion, reference_motion)["directionality_absolute_error"],
        },
        "track_cluster_bootstrap": track_bootstrap,
    }, bootstrap_samples


def _experiment_bootstrap(results: dict[str, dict], nested_samples: dict[str, dict[str, list[float]]]) -> dict:
    experiment_ids = list(EXPECTED_EXPERIMENTS)
    effect_names = list(next(iter(results.values()))["paired_effects"])
    nested_map = {
        "association_error_auprc_uncertainty_minus_distance": "auprc_effect",
        "selective_risk_benefit_full_minus_selective": "selective_risk_benefit",
        "link_f1_uncertainty_minus_hard": "link_f1_effect",
    }
    rng = random.Random(RANDOM_SEED + 900000)
    distributions = {name: [] for name in effect_names}
    for _ in range(EXPERIMENT_BOOTSTRAP_REPS):
        sampled = [rng.choice(experiment_ids) for _ in experiment_ids]
        for name in effect_names:
            values = []
            for experiment_id in sampled:
                nested_name = nested_map.get(name)
                if nested_name:
                    source = nested_samples[experiment_id][nested_name]
                    values.append(source[rng.randrange(len(source))])
                else:
                    values.append(results[experiment_id]["paired_effects"][name])
            distributions[name].append(float(np.mean(values)))
    summaries = {}
    for name in effect_names:
        observed = [results[experiment_id]["paired_effects"][name] for experiment_id in experiment_ids]
        summaries[name] = {
            "experiment_values": observed,
            "mean_effect": float(np.mean(observed)),
            "median_effect": float(np.median(observed)),
            "positive_experiments": sum(value > 0 for value in observed),
            "negative_experiments": sum(value < 0 for value in observed),
            "zero_experiments": sum(value == 0 for value in observed),
            "bootstrap_95_ci_of_mean": _percentile_interval(distributions[name]),
        }
    return {
        "biological_unit": "experiment",
        "biological_n": 3,
        "repetitions": EXPERIMENT_BOOTSTRAP_REPS,
        "hierarchical_for_primary_association_and_link_endpoints": True,
        "motion_endpoints_use_top_level_experiment_resampling_only": True,
        "small_n_warning": "With n=3 experiments, intervals are descriptive/sensitivity evidence, not precise population-level inference.",
        "effects": summaries,
    }


def evaluate_all(normalized_dir: Path, schema_lock_path: Path) -> dict:
    lock = json.loads(schema_lock_path.read_text(encoding="utf-8"))
    if lock.get("status") != "LOCKED":
        raise ValueError("confirmatory evaluation refused: schema lock is not LOCKED")
    experiments = load_normalized_reference(normalized_dir, schema_lock_path)
    results = {}
    nested = {}
    for index, experiment_id in enumerate(EXPECTED_EXPERIMENTS):
        result, bootstrap_samples = evaluate_experiment(
            experiment_id, experiments[experiment_id], RANDOM_SEED + index * 100000,
        )
        results[experiment_id] = result
        nested[experiment_id] = bootstrap_samples
    statistics = _experiment_bootstrap(results, nested)
    return {
        "schema_version": 1,
        "status": "COMPLETE_DRYAD_THREE_EXPERIMENT_CONFIRMATORY_EVALUATION",
        "source": {
            "doi": "10.5061/dryad.s4d28",
            "model": "PDGFB-driven rat glioma",
            "preparation": "living acute brain slices at infiltrative tumour margin",
            "reference_kind": "manual frame-by-frame source trajectories after frozen schema conversion",
            "biological_n": 3,
        },
        "frozen_configuration": {
            "max_speed_um_per_min": MAX_SPEED_UM_PER_MIN,
            "hypothesis_count": HYPOTHESIS_COUNT,
            "proposal_temperature_rule": "pairwise max link distance / 2",
            "calibration_temperature": CALIBRATION_TEMPERATURE,
            "posterior_track_threshold": POSTERIOR_TRACK_THRESHOLD,
            "random_seed": RANDOM_SEED,
            "dryad_specific_parameter_fitting": False,
        },
        "schema_lock_sha256": _sha256(schema_lock_path),
        "experiments": results,
        "replicate_aware_statistics": statistics,
        "interpretation_boundary": {
            "supported_scope_if_source_mapping_is_unambiguous": "technical transfer in three independent rat glioma brain-slice experiments",
            "human_gbm_wide_validation": False,
            "clinical_utility": False,
            "stage_e_decision_changed": False,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--normalized-dir", type=Path, required=True)
    parser.add_argument("--schema-lock", type=Path, default=Path("docs/dryad-confirmatory-schema-lock.json"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = evaluate_all(args.normalized_dir, args.schema_lock)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Dryad confirmatory evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote Dryad confirmatory result: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
