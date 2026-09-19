"""Propagate calibrated link probabilities into soft migration and HMM summaries."""

import argparse
import json
import math
from pathlib import Path
import sys

import numpy as np

from gbm_audit.uncertainty import _temperature_transform


def _emission(values: np.ndarray, means: np.ndarray, stds: np.ndarray) -> np.ndarray:
    output = np.empty((len(values), 2), dtype=float)
    for state in range(2):
        variance = max(stds[state] ** 2, 1e-6)
        output[:, state] = np.exp(-0.5 * (values - means[state]) ** 2 / variance) / math.sqrt(2 * math.pi * variance)
    return np.maximum(output, 1e-300)


def _weighted_mixture(speeds: np.ndarray, weights: np.ndarray, iterations: int = 30) -> tuple[np.ndarray, np.ndarray, np.ndarray] | None:
    if len(speeds) < 4 or float(weights.sum()) <= 0:
        return None
    means = np.asarray(np.quantile(speeds, [0.25, 0.75]), dtype=float)
    if abs(means[1] - means[0]) < 1e-6:
        means = np.asarray([float(np.average(speeds, weights=weights) - 0.5),
                            float(np.average(speeds, weights=weights) + 0.5)])
    weighted_mean = float(np.average(speeds, weights=weights))
    weighted_std = max(float(np.sqrt(np.average((speeds - weighted_mean) ** 2, weights=weights))), 0.1)
    stds = np.asarray([weighted_std, weighted_std])
    prior = np.asarray([0.5, 0.5])
    for _ in range(iterations):
        likelihood = _emission(speeds, means, stds) * prior
        responsibilities = likelihood / np.maximum(likelihood.sum(axis=1, keepdims=True), 1e-300)
        effective = (weights[:, None] * responsibilities).sum(axis=0)
        prior = effective / max(effective.sum(), 1e-300)
        means = (weights[:, None] * responsibilities * speeds[:, None]).sum(axis=0) / np.maximum(effective, 1e-300)
        variances = (weights[:, None] * responsibilities * (speeds[:, None] - means) ** 2).sum(axis=0) / np.maximum(effective, 1e-300)
        stds = np.sqrt(np.maximum(variances, 0.01))
    if means[0] > means[1]:
        means, stds, prior = means[::-1], stds[::-1], prior[::-1]
        responsibilities = responsibilities[:, ::-1]
    return means, stds, responsibilities


def _stationary(transition: np.ndarray) -> np.ndarray:
    values, vectors = np.linalg.eig(transition.T)
    vector = vectors[:, np.argmin(abs(values - 1))].real
    vector = np.abs(vector)
    return vector / max(vector.sum(), 1e-300)


def soft_summary(observations: list[dict], posterior_links: list[dict], calibration_temperature: float) -> dict:
    """Compute probability-weighted migration and two-state transition summaries."""
    row_by_id = {row["observation_id"]: row for row in observations}
    edges = []
    for edge in posterior_links:
        left, right = edge["from_observation_id"], edge["to_observation_id"]
        if left not in row_by_id or right not in row_by_id:
            continue
        probability = _temperature_transform(edge["probability"], calibration_temperature)
        edges.append({"left": left, "right": right, "frame": row_by_id[right]["frame"],
                      "speed": float(edge["distance_px"]), "weight": probability})
    speeds = np.asarray([edge["speed"] for edge in edges], dtype=float)
    weights = np.asarray([edge["weight"] for edge in edges], dtype=float)
    effective_links = float(weights.sum()) if len(weights) else 0.0
    summary = {
        "candidate_edges": len(edges),
        "expected_link_mass": effective_links,
        "mean_speed_px_per_frame": float(np.dot(speeds, weights) / effective_links) if effective_links else 0.0,
        "median_candidate_speed_px_per_frame": float(np.median(speeds)) if len(speeds) else 0.0,
    }
    mixture = _weighted_mixture(speeds, weights)
    if mixture is None:
        summary["hmm_2state_soft"] = {"status": "insufficient_weighted_edges", "speed_observations": len(edges)}
        return summary
    means, stds, responsibilities = mixture
    transition_counts = np.zeros((2, 2), dtype=float)
    for index, first in enumerate(edges):
        for second_index in range(index, len(edges)):
            second = edges[second_index]
            if first["right"] != second["left"] or second["frame"] != first["frame"] + 1:
                continue
            transition_counts += first["weight"] * second["weight"] * np.outer(responsibilities[index], responsibilities[second_index])
    if transition_counts.sum() <= 0:
        transition = np.eye(2)
    else:
        transition = transition_counts / np.maximum(transition_counts.sum(axis=1, keepdims=True), 1e-300)
    stationary = _stationary(transition)
    summary["hmm_2state_soft"] = {
        "status": "ok", "speed_observations": len(edges),
        "state_means_px_per_frame": [round(float(value), 6) for value in means],
        "state_stds_px_per_frame": [round(float(value), 6) for value in stds],
        "transition_matrix": [[round(float(value), 6) for value in row] for row in transition],
        "stationary_state_probability": [round(float(value), 6) for value in stationary],
        "expected_state_switch_probability": round(float(np.dot(stationary, 1 - np.diag(transition))), 6),
    }
    return summary


def _transition_l1(left: dict, right: dict) -> float | None:
    if left.get("status") != "ok" or right.get("status") != "ok":
        return None
    return float(sum(abs(left["transition_matrix"][i][j] - right["transition_matrix"][i][j])
                     for i in range(2) for j in range(2)))


def evaluate_soft_dynamics(manifest: dict, corruptions: dict, uncertainty: dict,
                           hard_dynamics: dict) -> dict:
    results = []
    for scenario, uncertainty_scenario, hard_scenario in zip(
            corruptions["scenarios"], uncertainty["scenarios"], hard_dynamics["scenarios"]):
        sequence_results = {}
        for sequence_id, scenario_sequence in scenario["sequences"].items():
            posterior = uncertainty_scenario["sequence_results"][sequence_id]["posterior_links"]
            soft = soft_summary(scenario_sequence["observations"], posterior, uncertainty["calibration"]["temperature"])
            reference_hmm = hard_scenario["sequence_results"][sequence_id]["representations"]["reference"]["hmm_2state"]
            hard = hard_scenario["sequence_results"][sequence_id]
            soft_hmm = soft["hmm_2state_soft"]
            soft["mean_speed_delta_vs_reference"] = soft["mean_speed_px_per_frame"] - hard_scenario["sequence_results"][sequence_id]["representations"]["reference"]["mean_speed_px_per_frame"]
            soft["hmm_transition_l1_vs_reference"] = _transition_l1(soft_hmm, reference_hmm)
            soft["hmm_switch_probability_delta_vs_reference"] = (
                soft_hmm["expected_state_switch_probability"] - reference_hmm["expected_state_switch_probability"]
                if soft_hmm.get("status") == reference_hmm.get("status") == "ok" else None)
            soft["hard_uncertainty_p50_speed_delta"] = hard["deltas_vs_reference"]["uncertainty_p50"]["mean_speed_delta_px_per_frame"]
            soft["hard_uncertainty_p90_speed_delta"] = hard["deltas_vs_reference"]["uncertainty_p90"]["mean_speed_delta_px_per_frame"]
            soft["hard_uncertainty_p50_hmm_l1"] = hard["deltas_vs_reference"]["uncertainty_p50"]["hmm_transition_l1"]
            soft["hard_uncertainty_p90_hmm_l1"] = hard["deltas_vs_reference"]["uncertainty_p90"]["hmm_transition_l1"]
            sequence_results[sequence_id] = soft
        results.append({"scenario_id": scenario["scenario_id"], "corruption": scenario["corruption"],
                        "severity": scenario["severity"], "sequence_results": sequence_results})
    return {
        "schema_version": 1,
        "method": "soft_probability_weighted_migration_and_transition_summary",
        "reference_manifest_sha256": corruptions["reference_manifest_sha256"],
        "corruption_seed": corruptions["seed"],
        "calibration_temperature": uncertainty["calibration"]["temperature"],
        "scenarios": results,
        "warning": "Technical U373 sensitivity analysis; soft states are latent/morphological summaries, not validated phenotypes.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("uncertainty", type=Path)
    parser.add_argument("hard_dynamics", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruptions = json.loads(args.corruptions.read_text(encoding="utf-8"))
        uncertainty = json.loads(args.uncertainty.read_text(encoding="utf-8"))
        hard_dynamics = json.loads(args.hard_dynamics.read_text(encoding="utf-8"))
        result = evaluate_soft_dynamics(manifest, corruptions, uncertainty, hard_dynamics)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Soft dynamics evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['scenarios'])} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
