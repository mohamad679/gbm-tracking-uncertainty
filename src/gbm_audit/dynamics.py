"""Propagate fixed, corrupted and uncertainty-aware tracks into HMM dynamics."""

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

from gbm_audit.baseline import nearest_neighbor
from gbm_audit.uncertainty import _temperature_transform


def _reference_rows(sequence: dict) -> list[dict]:
    rows = []
    for track in sequence["tracks"]:
        for point in track["observations"]:
            rows.append({
                "observation_id": f"ref_{track['track_id']:04d}_{point['frame']:04d}",
                "frame": point["frame"], "x_px": point["x_px"], "y_px": point["y_px"],
                "area_px": point["area_px"], "track_id": track["track_id"],
            })
    return rows


def _label_rows(rows: list[dict], labels: dict[str, object]) -> dict[object, list[dict]]:
    grouped: dict[object, list[dict]] = {}
    for row in rows:
        grouped.setdefault(labels[row["observation_id"]], []).append(row)
    return {label: sorted(points, key=lambda point: point["frame"])
            for label, points in grouped.items()}


def _track_rows(rows: list[dict], labels: dict[str, object]) -> list[list[dict]]:
    return list(_label_rows(rows, labels).values())


def posterior_labels(rows: list[dict], posterior_links: list[dict], threshold: float,
                    calibration_temperature: float) -> dict[str, int]:
    """Turn posterior edges into deterministic components without reading truth labels."""
    parent = {row["observation_id"]: row["observation_id"] for row in rows}
    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item
    def union(left, right):
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)
    row_by_id = {row["observation_id"]: row for row in rows}
    used_left: set[str] = set()
    used_right: set[str] = set()
    candidates = []
    for edge in posterior_links:
        probability = _temperature_transform(edge["probability"], calibration_temperature)
        if probability >= threshold:
            candidates.append((probability, edge["from_observation_id"], edge["to_observation_id"]))
    for probability, left, right in sorted(candidates, key=lambda item: (-item[0], item[1], item[2])):
        if left not in row_by_id or right not in row_by_id or left in used_left or right in used_right:
            continue
        used_left.add(left)
        used_right.add(right)
        union(left, right)
    roots = {}
    labels = {}
    for observation_id in sorted(parent):
        root = find(observation_id)
        roots.setdefault(root, len(roots) + 1)
        labels[observation_id] = roots[root]
    return labels


def _migration_summary(track_sequences: list[list[dict]]) -> tuple[dict, list[list[float]]]:
    speeds = []
    speed_sequences = []
    net_displacements = []
    for track in track_sequences:
        steps = []
        for previous, current in zip(track, track[1:]):
            if current["frame"] - previous["frame"] != 1:
                continue
            steps.append(float(np.hypot(current["x_px"] - previous["x_px"], current["y_px"] - previous["y_px"])))
        if steps:
            speed_sequences.append(steps)
            speeds.extend(steps)
        if len(track) >= 2:
            net_displacements.append(float(np.hypot(track[-1]["x_px"] - track[0]["x_px"],
                                                   track[-1]["y_px"] - track[0]["y_px"])))
    summary = {
        "track_count": len(track_sequences),
        "observation_count": sum(len(track) for track in track_sequences),
        "mean_track_length": float(np.mean([len(track) for track in track_sequences])) if track_sequences else 0.0,
        "median_track_length": float(np.median([len(track) for track in track_sequences])) if track_sequences else 0.0,
        "consecutive_steps": len(speeds),
        "mean_speed_px_per_frame": float(np.mean(speeds)) if speeds else 0.0,
        "median_speed_px_per_frame": float(np.median(speeds)) if speeds else 0.0,
        "mean_net_displacement_px": float(np.mean(net_displacements)) if net_displacements else 0.0,
    }
    return summary, speed_sequences


def _emission(values: np.ndarray, means: np.ndarray, stds: np.ndarray) -> np.ndarray:
    output = np.empty((len(values), 2), dtype=float)
    for state in range(2):
        variance = max(stds[state] ** 2, 1e-6)
        output[:, state] = np.exp(-0.5 * (values - means[state]) ** 2 / variance) / math.sqrt(2 * math.pi * variance)
    return np.maximum(output, 1e-300)


def fit_hmm(speed_sequences: list[list[float]], iterations: int = 30) -> dict:
    """Fit a small two-state Gaussian HMM with normalized forward-backward EM."""
    values = np.asarray([value for sequence in speed_sequences for value in sequence], dtype=float)
    if len(values) < 4:
        return {"status": "insufficient_speed_observations", "speed_observations": int(len(values))}
    quantiles = np.quantile(values, [0.25, 0.75])
    means = np.asarray(quantiles, dtype=float)
    if abs(means[1] - means[0]) < 1e-6:
        means = np.asarray([float(values.mean() - 0.5), float(values.mean() + 0.5)])
    stds = np.asarray([max(float(values.std()), 0.1)] * 2)
    transition = np.asarray([[0.85, 0.15], [0.15, 0.85]], dtype=float)
    initial = np.asarray([0.5, 0.5], dtype=float)
    for _ in range(iterations):
        initial_sum = np.zeros(2)
        transition_sum = np.zeros((2, 2))
        gamma_sum = np.zeros(2)
        value_sum = np.zeros(2)
        value_sq_sum = np.zeros(2)
        for sequence in speed_sequences:
            values_seq = np.asarray(sequence, dtype=float)
            if len(values_seq) == 0:
                continue
            emission = _emission(values_seq, means, stds)
            alpha = np.zeros_like(emission)
            scales = np.zeros(len(values_seq))
            alpha[0] = initial * emission[0]
            scales[0] = max(alpha[0].sum(), 1e-300)
            alpha[0] /= scales[0]
            for time in range(1, len(values_seq)):
                alpha[time] = emission[time] * (alpha[time - 1] @ transition)
                scales[time] = max(alpha[time].sum(), 1e-300)
                alpha[time] /= scales[time]
            beta = np.ones_like(emission)
            for time in range(len(values_seq) - 2, -1, -1):
                beta[time] = (transition @ (emission[time + 1] * beta[time + 1])) / scales[time + 1]
            gamma = alpha * beta
            gamma /= np.maximum(gamma.sum(axis=1, keepdims=True), 1e-300)
            initial_sum += gamma[0]
            gamma_sum += gamma.sum(axis=0)
            value_sum += gamma.T @ values_seq
            value_sq_sum += gamma.T @ (values_seq ** 2)
            for time in range(len(values_seq) - 1):
                xi = alpha[time][:, None] * transition * (emission[time + 1] * beta[time + 1])[None, :]
                xi /= max(xi.sum(), 1e-300)
                transition_sum += xi
        initial = initial_sum / max(initial_sum.sum(), 1e-300)
        transition = transition_sum / np.maximum(transition_sum.sum(axis=1, keepdims=True), 1e-300)
        means = value_sum / np.maximum(gamma_sum, 1e-300)
        variances = value_sq_sum / np.maximum(gamma_sum, 1e-300) - means ** 2
        stds = np.sqrt(np.maximum(variances, 0.01))
    if means[0] > means[1]:
        means = means[::-1]
        stds = stds[::-1]
        transition = transition[::-1, ::-1]
        initial = initial[::-1]
    stationary = np.linalg.eig(transpose := transition.T)[1][:, np.argmin(abs(np.linalg.eig(transpose)[0] - 1))].real
    stationary = np.abs(stationary) / max(np.abs(stationary).sum(), 1e-300)
    return {
        "status": "ok", "speed_observations": int(len(values)), "sequences": len(speed_sequences),
        "state_means_px_per_frame": [round(float(value), 6) for value in means],
        "state_stds_px_per_frame": [round(float(value), 6) for value in stds],
        "transition_matrix": [[round(float(value), 6) for value in row] for row in transition],
        "initial_state_probability": [round(float(value), 6) for value in initial],
        "stationary_state_probability": [round(float(value), 6) for value in stationary],
        "expected_state_switch_probability": round(float(np.dot(stationary, 1 - np.diag(transition))), 6),
    }


def summarize_tracks(track_sequences: list[list[dict]]) -> dict:
    summary, speed_sequences = _migration_summary(track_sequences)
    summary["hmm_2state"] = fit_hmm(speed_sequences)
    return summary


def _representation(rows: list[dict], labels: dict[str, object]) -> dict:
    return summarize_tracks(_track_rows(rows, labels))


def _delta(summary: dict, reference: dict) -> dict:
    result = {
        "mean_speed_delta_px_per_frame": summary["mean_speed_px_per_frame"] - reference["mean_speed_px_per_frame"],
        "mean_net_displacement_delta_px": summary["mean_net_displacement_px"] - reference["mean_net_displacement_px"],
        "mean_track_length_delta": summary["mean_track_length"] - reference["mean_track_length"],
    }
    left, right = summary["hmm_2state"], reference["hmm_2state"]
    if left.get("status") == right.get("status") == "ok":
        result["hmm_transition_l1"] = float(sum(abs(left["transition_matrix"][i][j] - right["transition_matrix"][i][j])
                                                 for i in range(2) for j in range(2)))
        result["hmm_switch_probability_delta"] = left["expected_state_switch_probability"] - right["expected_state_switch_probability"]
    else:
        result["hmm_transition_l1"] = None
        result["hmm_switch_probability_delta"] = None
    return result


def evaluate_dynamics(manifest: dict, corruption_benchmark: dict, uncertainty: dict,
                      max_distance_px: float = 8.0, thresholds: tuple[float, ...] = (0.5, 0.9)) -> dict:
    calibration_temperature = uncertainty["calibration"]["temperature"]
    scenarios = []
    for scenario, uncertainty_scenario in zip(corruption_benchmark["scenarios"], uncertainty["scenarios"]):
        sequence_results = {}
        for sequence_id, scenario_sequence in scenario["sequences"].items():
            reference_sequence = manifest["sequences"][sequence_id]
            rows = scenario_sequence["observations"]
            reference_rows = _reference_rows(reference_sequence)
            reference = _representation(reference_rows, {row["observation_id"]: row["track_id"] for row in reference_rows})
            representations = {
                "reference": reference,
                "raw_track_table": _representation(rows, {row["observation_id"]: row["observed_track_id"] for row in rows}),
                "nearest_neighbor": _representation(rows, nearest_neighbor(rows, max_distance_px)),
            }
            posterior_links = uncertainty_scenario["sequence_results"][sequence_id]["posterior_links"]
            for threshold in thresholds:
                labels = posterior_labels(rows, posterior_links, threshold, calibration_temperature)
                representations[f"uncertainty_p{int(threshold * 100)}"] = _representation(rows, labels)
            sequence_results[sequence_id] = {
                "representations": representations,
                "deltas_vs_reference": {name: _delta(summary, reference)
                                         for name, summary in representations.items() if name != "reference"},
            }
        scenarios.append({"scenario_id": scenario["scenario_id"], "corruption": scenario["corruption"],
                          "severity": scenario["severity"], "sequence_results": sequence_results})
    return {
        "schema_version": 1,
        "hmm": {"states": 2, "emission": "Gaussian speed", "model": "first baseline; no SLDS or Koopman"},
        "uncertainty_thresholds": list(thresholds),
        "calibration_temperature": calibration_temperature,
        "reference_manifest_sha256": corruption_benchmark["reference_manifest_sha256"],
        "corruption_seed": corruption_benchmark["seed"],
        "scenarios": scenarios,
        "warning": "Technical U373 sensitivity analysis; image-derived states are latent/morphological, not validated biological phenotypes.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("uncertainty", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-distance-px", type=float, default=8.0)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruptions = json.loads(args.corruptions.read_text(encoding="utf-8"))
        uncertainty = json.loads(args.uncertainty.read_text(encoding="utf-8"))
        result = evaluate_dynamics(manifest, corruptions, uncertainty, args.max_distance_px)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Dynamics evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['scenarios'])} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
