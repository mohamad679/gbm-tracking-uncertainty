"""Frozen no-retuning external glioma-explant tracking transfer evaluation."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import random
import sys

import numpy as np

from gbm_audit.calibration import temperature_transform
from gbm_audit.stage_e_metrics import distance_confidence, link_score_report, selective_link_risk


SOURCE_COMMIT = "265285a03d87f3bf3275a0e78db1336570126bf4"
SOURCE_INFO_SHA256 = "7f1e2cbf4101e2c86535fffa146a8b7d2a7a6e54584d593558ca0535d2b08d31"
SOURCE_SPOTS_SHA256 = "329296edb5392151e9b6b1602f043e21a355afd27567bc3f06536f8abf1cdc94"
SOURCE_TRACKS_SHA256 = "76d9b02fe7672cf55bddfba13185f3929b81c628741e88de74b4564f0c38ef09"
HYPOTHESIS_COUNT = 64
MAX_SPEED_UM_PER_MIN = 1.5
CALIBRATION_TEMPERATURE = 0.25
POSTERIOR_TRACK_THRESHOLD = 0.5
RANDOM_SEED = 20260922


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_source(info_path: Path, spots_path: Path, tracks_path: Path) -> None:
    expected = {
        info_path: SOURCE_INFO_SHA256,
        spots_path: SOURCE_SPOTS_SHA256,
        tracks_path: SOURCE_TRACKS_SHA256,
    }
    for path, digest in expected.items():
        if _sha256(path) != digest:
            raise ValueError(f"external source hash mismatch: {path.name}")


def _finite(value: str, field: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"non-finite {field}")
    return result


def load_trackmate_reference(info_path: Path, spots_path: Path, tracks_path: Path) -> dict:
    """Parse the immutable NPA TrackMate export without outcome-guided exclusions."""
    _verify_source(info_path, spots_path, tracks_path)
    info = json.loads(info_path.read_text(encoding="utf-8"))
    frame_interval_s = float(info["Frame interval (s)"])
    if not math.isfinite(frame_interval_s) or frame_interval_s <= 0:
        raise ValueError("invalid frame interval")

    track_meta: dict[int, int] = {}
    with tracks_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"TRACK_ID", "NUMBER_SPOTS"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("tracks CSV schema drifted")
        for row in reader:
            track_id = int(row["TRACK_ID"])
            if track_id in track_meta:
                raise ValueError(f"duplicate track metadata id {track_id}")
            track_meta[track_id] = int(row["NUMBER_SPOTS"])

    observations: list[dict] = []
    counts: Counter[int] = Counter()
    seen_track_frame: set[tuple[int, int]] = set()
    with spots_path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"ID", "TRACK_ID", "POSITION_X", "POSITION_Y", "POSITION_T", "FRAME"}
        if reader.fieldnames is None or not required.issubset(reader.fieldnames):
            raise ValueError("spots CSV schema drifted")
        for row in reader:
            track_id = int(row["TRACK_ID"])
            if track_id not in track_meta:
                continue
            frame = int(row["FRAME"])
            key = (track_id, frame)
            if key in seen_track_frame:
                raise ValueError(f"multiple reference spots for track/frame {key}")
            seen_track_frame.add(key)
            source_id = int(row["ID"])
            observations.append({
                "observation_id": f"ext_{source_id}",
                "source_spot_id": source_id,
                "true_track_id": track_id,
                "frame": frame,
                "x_um": _finite(row["POSITION_X"], "POSITION_X"),
                "y_um": _finite(row["POSITION_Y"], "POSITION_Y"),
                "time_s": _finite(row["POSITION_T"], "POSITION_T"),
            })
            counts[track_id] += 1

    if set(counts) != set(track_meta):
        missing = sorted(set(track_meta) - set(counts))[:10]
        extra = sorted(set(counts) - set(track_meta))[:10]
        raise ValueError(f"track/spots identity mismatch: missing={missing}, extra={extra}")
    mismatch = [track_id for track_id, expected in track_meta.items() if counts[track_id] != expected]
    if mismatch:
        raise ValueError(f"NUMBER_SPOTS mismatch for tracks {mismatch[:10]}")

    observations.sort(key=lambda row: (row["frame"], row["observation_id"]))
    frame_values = [row["frame"] for row in observations]
    return {
        "source_commit": SOURCE_COMMIT,
        "frame_interval_s": frame_interval_s,
        "frame_interval_min": frame_interval_s / 60.0,
        "observations": observations,
        "track_count": len(track_meta),
        "observation_count": len(observations),
        "frame_min": min(frame_values),
        "frame_max": max(frame_values),
        "source_hashes": {
            "info_sha256": SOURCE_INFO_SHA256,
            "spots_sha256": SOURCE_SPOTS_SHA256,
            "tracks_sha256": SOURCE_TRACKS_SHA256,
        },
    }


def _grid_candidates(observations: list[dict], max_distance_um: float) -> list[tuple[str, str, float]]:
    if max_distance_um <= 0 or not math.isfinite(max_distance_um):
        raise ValueError("max_distance_um must be finite and positive")
    by_frame: dict[int, list[dict]] = defaultdict(list)
    for row in observations:
        by_frame[int(row["frame"])].append(row)
    cell = max_distance_um
    edges: list[tuple[str, str, float]] = []
    for frame in sorted(by_frame):
        previous = by_frame.get(frame - 1)
        if not previous:
            continue
        buckets: dict[tuple[int, int], list[dict]] = defaultdict(list)
        for row in previous:
            buckets[(math.floor(row["x_um"] / cell), math.floor(row["y_um"] / cell))].append(row)
        for right in by_frame[frame]:
            gx, gy = math.floor(right["x_um"] / cell), math.floor(right["y_um"] / cell)
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for left in buckets.get((gx + dx, gy + dy), ()):
                        distance = float(np.hypot(right["x_um"] - left["x_um"], right["y_um"] - left["y_um"]))
                        if distance <= max_distance_um:
                            edges.append((left["observation_id"], right["observation_id"], distance))
    return sorted(edges, key=lambda row: (row[1], row[0]))


def _true_links(observations: list[dict]) -> set[tuple[str, str]]:
    by_track_frame = {(row["true_track_id"], row["frame"]): row["observation_id"] for row in observations}
    return {
        (observation_id, by_track_frame[(track_id, frame + 1)])
        for (track_id, frame), observation_id in by_track_frame.items()
        if (track_id, frame + 1) in by_track_frame
    }


def _weighted_choice(rng: random.Random, choices: list[tuple[tuple[int | None, str | None], float]]) -> tuple[int | None, str | None]:
    total = sum(weight for _, weight in choices)
    point = rng.random() * total
    for choice, weight in choices:
        point -= weight
        if point <= 0:
            return choice
    return choices[-1][0]


def _sample_probabilities(observations: list[dict], edges: list[tuple[str, str, float]],
                          max_distance_um: float, temperature_um: float) -> dict[tuple[str, str], float]:
    """Efficient equivalent of the frozen distance-hypothesis sampler for a dense external movie."""
    by_frame: dict[int, list[dict]] = defaultdict(list)
    for row in observations:
        by_frame[int(row["frame"])].append(row)
    distance_by_pair = {(left, right): distance for left, right, distance in edges}
    candidates_by_target: dict[str, list[str]] = defaultdict(list)
    for left, right, _ in edges:
        candidates_by_target[right].append(left)

    counts: Counter[tuple[str, str]] = Counter()
    new_track_weight = math.exp(-max_distance_um / temperature_um)
    for repeat in range(HYPOTHESIS_COUNT):
        rng = random.Random(RANDOM_SEED + repeat)
        active_by_observation: dict[str, tuple[int, int]] = {}
        next_track = 1
        for frame in sorted(by_frame):
            rows = list(by_frame[frame])
            rng.shuffle(rows)
            previous_active = active_by_observation
            previous_rank = {obs_id: rank for rank, obs_id in enumerate(previous_active)}
            current_active: dict[str, tuple[int, int]] = {}
            used_tracks: set[int] = set()
            for row in rows:
                target = row["observation_id"]
                prior_ids = [source for source in candidates_by_target.get(target, ()) if source in previous_active]
                prior_ids.sort(key=lambda source: previous_rank[source])
                choices: list[tuple[tuple[int | None, str | None], float]] = []
                for source in prior_ids:
                    track_id, source_frame = previous_active[source]
                    if source_frame != frame - 1 or track_id in used_tracks:
                        continue
                    distance = distance_by_pair[(source, target)]
                    choices.append(((track_id, source), math.exp(-distance / temperature_um)))
                choices.append(((None, None), new_track_weight))
                track_id, source = _weighted_choice(rng, choices)
                if track_id is None:
                    track_id = next_track
                    next_track += 1
                else:
                    used_tracks.add(track_id)
                    counts[(source, target)] += 1
                current_active[target] = (track_id, frame)
            active_by_observation = current_active
    return {pair: counts[pair] / HYPOTHESIS_COUNT for pair in distance_by_pair}


def _nearest_neighbor_links(observations: list[dict], edges: list[tuple[str, str, float]]) -> set[tuple[str, str]]:
    by_frame: dict[int, list[dict]] = defaultdict(list)
    for row in observations:
        by_frame[int(row["frame"])].append(row)
    edges_by_target: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for left, right, distance in edges:
        edges_by_target[right].append((left, distance))
    active_by_observation: dict[str, tuple[int, int]] = {}
    next_track = 1
    links: set[tuple[str, str]] = set()
    for frame in sorted(by_frame):
        candidates = []
        for row in by_frame[frame]:
            target = row["observation_id"]
            for source, distance in edges_by_target.get(target, ()):
                state = active_by_observation.get(source)
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
        current_active: dict[str, tuple[int, int]] = {}
        for row in sorted(by_frame[frame], key=lambda item: item["observation_id"]):
            target = row["observation_id"]
            if target not in assignment:
                assignment[target] = next_track
                next_track += 1
            else:
                links.add((source_for_target[target], target))
            current_active[target] = (assignment[target], frame)
        active_by_observation = current_active
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


def _motion_summary(observations: list[dict], links: set[tuple[str, str]], frame_interval_min: float) -> dict:
    rows = {row["observation_id"]: row for row in observations}
    outgoing = {left: right for left, right in links}
    incoming = set(outgoing.values())
    chains, visited = [], set()
    for start in sorted(set(rows) - incoming):
        chain, current = [start], start
        while current in outgoing and outgoing[current] not in visited:
            current = outgoing[current]
            chain.append(current)
        visited.update(chain)
        chains.append(chain)
    chains.extend([[item] for item in sorted(set(rows) - visited)])
    speeds, paths, nets, directionality = [], [], [], []
    for chain in chains:
        points = [rows[item] for item in chain]
        steps = [
            float(np.hypot(b["x_um"] - a["x_um"], b["y_um"] - a["y_um"]))
            for a, b in zip(points, points[1:]) if b["frame"] == a["frame"] + 1
        ]
        if not steps:
            continue
        path = float(sum(steps))
        net = float(np.hypot(points[-1]["x_um"] - points[0]["x_um"], points[-1]["y_um"] - points[0]["y_um"]))
        speeds.extend(step / frame_interval_min for step in steps)
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


def evaluate_external_reference(reference: dict) -> dict:
    observations = reference["observations"]
    frame_interval_min = reference["frame_interval_min"]
    max_distance_um = MAX_SPEED_UM_PER_MIN * frame_interval_min
    temperature_um = max_distance_um / 2.0
    edges = _grid_candidates(observations, max_distance_um)
    truth = _true_links(observations)
    probabilities = _sample_probabilities(observations, edges, max_distance_um, temperature_um)
    labels = [int((left, right) in truth) for left, right, _ in edges]
    raw = [probabilities[(left, right)] for left, right, _ in edges]
    calibrated = [temperature_transform(value, CALIBRATION_TEMPERATURE) for value in raw]
    distance = distance_confidence([value for _, _, value in edges], max_distance_um)
    hard_links = _nearest_neighbor_links(observations, edges)
    uncertainty_links = _posterior_links(probabilities)
    reference_motion = _motion_summary(observations, truth, frame_interval_min)
    hard_motion = _motion_summary(observations, hard_links, frame_interval_min)
    uncertainty_motion = _motion_summary(observations, uncertainty_links, frame_interval_min)
    return {
        "schema_version": 1,
        "status": "COMPLETE_SINGLE_EXTERNAL_GLIOMA_EXPLANT_TRANSFER",
        "source": {
            "repository": "smotsch/analysis_glioma",
            "commit": reference["source_commit"],
            "dataset": "NPA_stich_3",
            "reference_kind": "independent TrackMate trajectories; not manual gold-standard labels",
            "biological_n": 1,
            "track_count": reference["track_count"],
            "observation_count": reference["observation_count"],
            "frame_range": [reference["frame_min"], reference["frame_max"]],
            "frame_interval_s": reference["frame_interval_s"],
            "source_hashes": reference["source_hashes"],
        },
        "frozen_transfer_configuration": {
            "max_speed_um_per_min": MAX_SPEED_UM_PER_MIN,
            "max_link_distance_um": max_distance_um,
            "proposal_temperature_um": temperature_um,
            "hypothesis_count": HYPOTHESIS_COUNT,
            "calibration_temperature": CALIBRATION_TEMPERATURE,
            "posterior_track_threshold": POSTERIOR_TRACK_THRESHOLD,
            "seed": RANDOM_SEED,
            "external_parameter_fitting": False,
        },
        "candidate_graph": {
            "candidate_edges": len(edges),
            "reference_links": len(truth),
            "reference_link_coverage": sum(label for label in labels) / len(truth) if truth else 1.0,
        },
        "association": {
            "distance_confidence": link_score_report(distance, labels),
            "uncalibrated_uncertainty": link_score_report(raw, labels),
            "calibrated_uncertainty": link_score_report(calibrated, labels),
            "calibrated_full_coverage_risk": selective_link_risk(calibrated, labels, coverage=1.0)["risk"],
        },
        "tracking": {
            "hard_nearest_neighbor": _link_summary(hard_links, truth),
            "uncertainty_compatible_p50": _link_summary(uncertainty_links, truth),
        },
        "motion": {
            "reference": reference_motion,
            "hard_nearest_neighbor": {"summary": hard_motion, "errors": _motion_errors(hard_motion, reference_motion)},
            "uncertainty_compatible_p50": {"summary": uncertainty_motion, "errors": _motion_errors(uncertainty_motion, reference_motion)},
        },
        "interpretation_boundary": {
            "supported_scope": "single independent mouse glioma explant technical-transfer example",
            "biological_population_inference": False,
            "manual_ground_truth_validation": False,
            "dryad_three_experiment_confirmatory_arm_completed": False,
            "stage_e_decision_changed": False,
        },
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--info", type=Path, required=True)
    parser.add_argument("--spots", type=Path, required=True)
    parser.add_argument("--tracks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        reference = load_trackmate_reference(args.info, args.spots, args.tracks)
        result = evaluate_external_reference(reference)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"External biological-context evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
