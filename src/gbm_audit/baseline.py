"""Evaluate a frozen nearest-neighbour tracking baseline on corruption scenarios."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from gbm_audit.config import DEFAULT_MAX_DISTANCE_PX


def nearest_neighbor(observations: list[dict], max_distance_px: float = DEFAULT_MAX_DISTANCE_PX) -> dict[str, int]:
    """Assign observations to tracks using greedy frame-to-frame nearest-neighbour matching."""
    by_frame: dict[int, list[dict]] = {}
    for row in observations:
        by_frame.setdefault(int(row["frame"]), []).append(row)
    active: dict[int, tuple[int, float, float]] = {}
    assignments: dict[str, int] = {}
    next_track = 1
    for frame in sorted(by_frame):
        # Only consecutive frames can be linked; no silent gap bridging.
        active = {track_id: state for track_id, state in active.items() if state[0] == frame - 1}
        candidates = []
        for row in by_frame[frame]:
            for track_id, (_, x, y) in active.items():
                distance = float(np.hypot(row["x_px"] - x, row["y_px"] - y))
                if distance <= max_distance_px:
                    candidates.append((distance, row["observation_id"], track_id))
        used_rows: set[str] = set()
        used_tracks: set[int] = set()
        for _, observation_id, track_id in sorted(candidates):
            if observation_id in used_rows or track_id in used_tracks:
                continue
            used_rows.add(observation_id)
            used_tracks.add(track_id)
            assignments[observation_id] = track_id
        for row in sorted(by_frame[frame], key=lambda item: item["observation_id"]):
            if row["observation_id"] not in assignments:
                assignments[row["observation_id"]] = next_track
                next_track += 1
        active = {
            assignments[row["observation_id"]]: (frame, row["x_px"], row["y_px"])
            for row in by_frame[frame]
        }
    return assignments


def _pair_links(rows: list[dict], identity: dict[str, int], truth: bool = False) -> set[tuple[str, str]]:
    by_id_frame: dict[tuple[int, int], str] = {}
    for row in rows:
        key = identity.get(row["observation_id"], 0)
        if truth and key == 0:
            continue
        by_id_frame[(key, int(row["frame"]))] = row["observation_id"]
    links = set()
    for (track_id, frame), first in by_id_frame.items():
        second = by_id_frame.get((track_id, frame + 1))
        if second is not None:
            links.add((first, second))
    return links


def _metrics(sequence: dict, observations: list[dict], truth_rows: list[dict], assignments: dict[str, int]) -> dict:
    truth_by_obs = {row["observation_id"]: row["true_track_id"] for row in truth_rows}
    observed_reference = [row for row in observations if truth_by_obs.get(row["observation_id"], 0) > 0]
    reference_count = sum(row["true_track_id"] > 0 for row in truth_rows)
    true_identity = {row["observation_id"]: truth_by_obs[row["observation_id"]] for row in observed_reference}
    true_links = _pair_links(observed_reference, true_identity, truth=True)
    predicted_links = _pair_links(observations, assignments)
    true_positive = len(true_links & predicted_links)
    link_precision = true_positive / len(predicted_links) if predicted_links else 1.0
    link_recall = true_positive / len(true_links) if true_links else 1.0

    by_true: dict[int, list[dict]] = {}
    for row in observed_reference:
        by_true.setdefault(truth_by_obs[row["observation_id"]], []).append(row)
    id_switches = 0
    fragmentation_errors = 0
    complete = 0
    complete_denominator = len(sequence["tracks"])
    reference_by_id = {
        f"ref_{track['track_id']:04d}_{point['frame']:04d}": point
        for track in sequence["tracks"] for point in track["observations"]
    }
    speed_errors = []
    for track in sequence["tracks"]:
        track_id = track["track_id"]
        rows = sorted(by_true.get(track_id, []), key=lambda row: row["frame"])
        if not rows:
            continue
        segments = 1
        consistent = True
        for previous, current in zip(rows, rows[1:]):
            previous_assignment = assignments[previous["observation_id"]]
            current_assignment = assignments[current["observation_id"]]
            if current["frame"] != previous["frame"] + 1 or current_assignment != previous_assignment:
                segments += 1
                if current["frame"] == previous["frame"] + 1:
                    id_switches += 1
                consistent = False
            if current["frame"] == previous["frame"] + 1:
                ref_previous = reference_by_id[previous["observation_id"]]
                ref_current = reference_by_id[current["observation_id"]]
                observed_speed = float(np.hypot(current["x_px"] - previous["x_px"], current["y_px"] - previous["y_px"]))
                reference_speed = float(np.hypot(ref_current["x_px"] - ref_previous["x_px"], ref_current["y_px"] - ref_previous["y_px"]))
                speed_errors.append(abs(observed_speed - reference_speed))
        fragmentation_errors += max(0, segments - 1)
        expected_count = len(track["observations"])
        if len(rows) == expected_count and consistent:
            complete += 1

    false_positive_count = sum(truth_by_obs.get(row["observation_id"], 0) == 0 for row in observations)
    return {
        "observations": len(observations),
        "reference_observations": reference_count,
        "observed_reference_observations": len(observed_reference),
        "detection_recall": len(observed_reference) / reference_count if reference_count else 1.0,
        "false_positive_count": false_positive_count,
        "predicted_track_count": len(set(assignments.values())),
        "id_switches": id_switches,
        "fragmentation_errors": fragmentation_errors,
        "complete_track_fraction": complete / complete_denominator if complete_denominator else 1.0,
        "link_true_positive": true_positive,
        "link_predicted": len(predicted_links),
        "link_reference": len(true_links),
        "link_precision": link_precision,
        "link_recall": link_recall,
        "mean_speed_error_px_per_frame": float(np.mean(speed_errors)) if speed_errors else 0.0,
    }


def evaluate_benchmark(manifest: dict, corruption_benchmark: dict,
                       max_distance_px: float = DEFAULT_MAX_DISTANCE_PX) -> dict:
    """Evaluate every scenario without using the supplied observed IDs or truth."""
    results = []
    for scenario in corruption_benchmark["scenarios"]:
        sequence_results = {}
        for sequence_id, scenario_sequence in scenario["sequences"].items():
            assignments = nearest_neighbor(scenario_sequence["observations"], max_distance_px)
            sequence_results[sequence_id] = _metrics(
                manifest["sequences"][sequence_id], scenario_sequence["observations"],
                scenario_sequence["evaluation_truth"], assignments)
        results.append({
            "scenario_id": scenario["scenario_id"],
            "corruption": scenario["corruption"],
            "severity": scenario["severity"],
            "sequence_results": sequence_results,
        })
    return {
        "schema_version": 1,
        "tracker": {"name": "greedy_nearest_neighbor", "max_distance_px": max_distance_px, "gap_bridging": False,
                    "uses": ["frame", "x_px", "y_px"],
                    "ignores": ["area_px", "observed_track_id", "evaluation_truth"]},
        "reference_manifest_sha256": corruption_benchmark["reference_manifest_sha256"],
        "corruption_seed": corruption_benchmark["seed"],
        "scenarios": results,
        "warning": "Technical baseline on U373 reference-derived scenarios; not a biological validation of GlioTrace.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-distance-px", type=float, default=DEFAULT_MAX_DISTANCE_PX)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruption_benchmark = json.loads(args.corruptions.read_text(encoding="utf-8"))
        result = evaluate_benchmark(manifest, corruption_benchmark, args.max_distance_px)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Baseline evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['scenarios'])} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
