"""Propagate exact and sampled association ensembles into Stage C summaries."""

import argparse
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys

import numpy as np

from gbm_audit.adaptive_candidates import generate_adaptive_candidate_graph
from gbm_audit.adaptive_tuning import DEVELOPMENT_SEQUENCE_ID
from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.context_evaluation import development_only_artifacts
from gbm_audit.context_posterior import (
    DEFAULT_TRAJECTORY_ENSEMBLE_COUNT,
    sample_exact_context_matchings,
    trajectories_from_links,
)
from gbm_audit.dynamics import fit_hmm
from gbm_audit.numerics import gaussian_emission, normalize_transition_rows, stationary_distribution
from gbm_audit.uncertainty import sample_candidate_graph_hypotheses


MIGRATION_SCALAR_FIELDS = (
    "mean_speed_px_per_frame",
    "median_speed_px_per_frame",
    "mean_net_displacement_px",
    "mean_track_length",
    "median_track_length",
    "directional_persistence",
)
MSD_LAGS = (1, 2, 3)

# Fitted once on the uncorrupted Stage C development reference (sequence 01)
# and recorded in docs/stage-c-development-summaries.json.  Locked evaluation
# imports this value and never calls fit_hmm on sequence 02.
LOCKED_DEVELOPMENT_HMM_MODEL = {
    "status": "ok",
    "speed_observations": 757,
    "sequences": 8,
    "state_means_px_per_frame": [0.199786, 6.541016],
    "state_stds_px_per_frame": [0.404617, 5.092416],
    "transition_matrix": [[0.626064, 0.373936], [0.165722, 0.834278]],
    "initial_state_probability": [0.0, 1.0],
    "stationary_state_probability": [0.307088, 0.692912],
    "expected_state_switch_probability": 0.229662,
}


def _reference_trajectories(sequence: dict) -> tuple[dict[str, dict], list[dict]]:
    observations, trajectories = {}, []
    for track in sequence["tracks"]:
        observation_ids = []
        for point in sorted(track["observations"], key=lambda item: item["frame"]):
            observation_id = f"ref_{track['track_id']:04d}_{point['frame']:04d}"
            observations[observation_id] = {
                "observation_id": observation_id,
                "frame": point["frame"],
                "x_px": point["x_px"],
                "y_px": point["y_px"],
            }
            observation_ids.append(observation_id)
        trajectories.append({"observation_ids": observation_ids})
    return observations, trajectories


def fit_development_speed_hmm(manifest: dict) -> dict:
    """Fit the registered state model from uncorrupted sequence-01 reference only."""
    observations, trajectories = _reference_trajectories(
        manifest["sequences"][DEVELOPMENT_SEQUENCE_ID]
    )
    speed_sequences = []
    for trajectory in trajectories:
        points = [observations[item] for item in trajectory["observation_ids"]]
        speed_sequences.append([
            float(np.hypot(current["x_px"] - previous["x_px"],
                           current["y_px"] - previous["y_px"]))
            for previous, current in zip(points, points[1:])
            if current["frame"] - previous["frame"] == 1
        ])
    return {
        "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
        "fit_input": "uncorrupted_reference_trajectories",
        "model": fit_hmm(speed_sequences),
    }


def _viterbi_states(speeds: list[float], hmm: dict) -> list[int]:
    if not speeds or hmm.get("status") != "ok":
        return []
    values = np.asarray(speeds, dtype=float)
    means = np.asarray(hmm["state_means_px_per_frame"], dtype=float)
    stds = np.asarray(hmm["state_stds_px_per_frame"], dtype=float)
    transition = np.asarray(hmm["transition_matrix"], dtype=float)
    initial = np.asarray(hmm["initial_state_probability"], dtype=float)
    log_emission = np.log(gaussian_emission(values, means, stds))
    log_transition = np.log(np.maximum(transition, 1e-300))
    scores = np.empty((len(values), 2), dtype=float)
    backpointers = np.zeros((len(values), 2), dtype=int)
    scores[0] = np.log(np.maximum(initial, 1e-300)) + log_emission[0]
    for index in range(1, len(values)):
        candidates = scores[index - 1][:, None] + log_transition
        backpointers[index] = np.argmax(candidates, axis=0)
        scores[index] = candidates[backpointers[index], np.arange(2)] + log_emission[index]
    states = [int(np.argmax(scores[-1]))]
    for index in range(len(values) - 1, 0, -1):
        states.append(int(backpointers[index, states[-1]]))
    return list(reversed(states))


def _trajectory_features(trajectory: dict, observations: dict[str, dict], hmm: dict) -> dict:
    points = [observations[item] for item in trajectory["observation_ids"]]
    steps = []
    for previous, current in zip(points, points[1:]):
        if current["frame"] - previous["frame"] != 1:
            continue
        dx = float(current["x_px"] - previous["x_px"])
        dy = float(current["y_px"] - previous["y_px"])
        steps.append((dx, dy, float(np.hypot(dx, dy))))
    persistence = []
    for (left_x, left_y, left_speed), (right_x, right_y, right_speed) in zip(steps, steps[1:]):
        if left_speed > 0 and right_speed > 0:
            persistence.append((left_x * right_x + left_y * right_y) / (left_speed * right_speed))
    msd = {lag: [] for lag in MSD_LAGS}
    for lag in MSD_LAGS:
        for left, right in zip(points, points[lag:]):
            if right["frame"] - left["frame"] == lag:
                msd[lag].append(float((right["x_px"] - left["x_px"]) ** 2
                                      + (right["y_px"] - left["y_px"]) ** 2))
    speeds = [step[2] for step in steps]
    return {
        "track_length": len(points),
        "speeds": speeds,
        "net_displacement": (
            float(np.hypot(points[-1]["x_px"] - points[0]["x_px"],
                           points[-1]["y_px"] - points[0]["y_px"]))
            if len(points) >= 2 else None
        ),
        "persistence": persistence,
        "msd": msd,
        "states": _viterbi_states(speeds, hmm),
    }


def summarize_trajectories(trajectories: list[dict], observations: dict[str, dict], hmm: dict) -> dict:
    """Summarize migration and frozen-HMM state dynamics for one realization."""
    features = [_trajectory_features(trajectory, observations, hmm) for trajectory in trajectories]
    speeds = [speed for feature in features for speed in feature["speeds"]]
    net_displacements = [feature["net_displacement"] for feature in features
                         if feature["net_displacement"] is not None]
    persistence = [value for feature in features for value in feature["persistence"]]
    msd = {
        str(lag): [value for feature in features for value in feature["msd"][lag]]
        for lag in MSD_LAGS
    }
    state_sequences = [feature["states"] for feature in features if feature["states"]]
    summary = {
        "track_count": len(trajectories),
        "observation_count": sum(feature["track_length"] for feature in features),
        "mean_track_length": float(np.mean([feature["track_length"] for feature in features])) if features else None,
        "median_track_length": float(np.median([feature["track_length"] for feature in features])) if features else None,
        "consecutive_steps": len(speeds),
        "mean_speed_px_per_frame": float(np.mean(speeds)) if speeds else None,
        "median_speed_px_per_frame": float(np.median(speeds)) if speeds else None,
        "mean_net_displacement_px": float(np.mean(net_displacements)) if net_displacements else None,
        "directional_persistence": float(np.mean(persistence)) if persistence else None,
        "mean_squared_displacement_px2": {
            lag: float(np.mean(values)) if values else None for lag, values in msd.items()
        },
    }
    if hmm.get("status") != "ok" or not state_sequences:
        summary["hmm_2state"] = {"status": "insufficient_speed_observations"}
        return summary
    occupancy_counts = np.zeros(2, dtype=float)
    transition_counts = np.zeros((2, 2), dtype=float)
    dwell = [[], []]
    for states in state_sequences:
        occupancy_counts += np.bincount(states, minlength=2)
        for left, right in zip(states, states[1:]):
            transition_counts[left, right] += 1
        start, current = 0, states[0]
        for index, state in enumerate(states[1:], start=1):
            if state != current:
                dwell[current].append(index - start)
                start, current = index, state
        dwell[current].append(len(states) - start)
    transition = normalize_transition_rows(
        transition_counts, np.asarray(hmm["transition_matrix"], dtype=float)
    )
    stationary = stationary_distribution(transition)
    summary["hmm_2state"] = {
        "status": "ok",
        "state_occupancy": [float(value / occupancy_counts.sum()) for value in occupancy_counts],
        "transition_matrix": [[float(value) for value in row] for row in transition],
        "expected_state_switch_probability": float(np.dot(stationary, 1 - np.diag(transition))),
        "mean_dwell_length_steps": [float(np.mean(values)) if values else None for values in dwell],
    }
    return summary


def _interval(values: list[float | None]) -> dict:
    defined = [value for value in values if value is not None and math.isfinite(value)]
    if not defined:
        return {
            "defined_samples": 0,
            "mean": None,
            "median": None,
            "p05": None,
            "p95": None,
        }
    return {
        "defined_samples": len(defined),
        "mean": float(np.mean(defined)),
        "median": float(np.quantile(defined, 0.5)),
        "p05": float(np.quantile(defined, 0.05)),
        "p95": float(np.quantile(defined, 0.95)),
    }


def aggregate_posterior_summaries(sample_summaries: list[dict]) -> dict:
    """Return registered posterior intervals without imputing undefined metrics."""
    scalar_intervals = {
        field: _interval([summary[field] for summary in sample_summaries])
        for field in MIGRATION_SCALAR_FIELDS
    }
    msd_intervals = {
        str(lag): _interval([
            summary["mean_squared_displacement_px2"][str(lag)] for summary in sample_summaries
        ])
        for lag in MSD_LAGS
    }
    hmm_summaries = [summary["hmm_2state"] for summary in sample_summaries
                     if summary["hmm_2state"].get("status") == "ok"]
    if not hmm_summaries:
        state_dynamics = {"defined_samples": 0, "status": "insufficient_speed_observations"}
    else:
        state_dynamics = {
            "defined_samples": len(hmm_summaries),
            "status": "ok",
            "state_occupancy": [
                _interval([summary["state_occupancy"][state] for summary in hmm_summaries])
                for state in range(2)
            ],
            "transition_matrix": [
                [
                    _interval([summary["transition_matrix"][left][right]
                               for summary in hmm_summaries])
                    for right in range(2)
                ]
                for left in range(2)
            ],
            "expected_state_switch_probability": _interval([
                summary["expected_state_switch_probability"] for summary in hmm_summaries
            ]),
            "mean_dwell_length_steps": [
                _interval([summary["mean_dwell_length_steps"][state]
                           for summary in hmm_summaries])
                for state in range(2)
            ],
        }
    return {
        "sample_count": len(sample_summaries),
        "migration": scalar_intervals,
        "mean_squared_displacement_px2": msd_intervals,
        "hmm_2state": state_dynamics,
    }


def sample_stage_a_ensemble(observations: list[dict], candidate_edges: list[dict], *, count: int,
                            seed: int) -> dict:
    link_sets = sample_candidate_graph_hypotheses(
        observations, candidate_edges, count=count, temperature_px=4.0,
        new_track_score_px=10.0, seed=seed,
    )
    observation_ids = sorted(row["observation_id"] for row in observations)
    samples, violations = [], []
    candidate_pairs = {
        (edge["from_observation_id"], edge["to_observation_id"])
        for edge in candidate_edges
    }
    for sample_index, link_set in enumerate(link_sets):
        trajectories, invariants = trajectories_from_links(observation_ids, sorted(link_set))
        outside = sorted(link_set - candidate_pairs)
        if not all((invariants["one_to_one_pass"], invariants["trajectory_partition_pass"], not outside)):
            violations.append(sample_index)
        samples.append({
            "sample_index": sample_index,
            "links": sorted(link_set),
            "trajectories": trajectories,
        })
    return {"samples": samples, "invariants_pass": not violations, "violation_sample_indices": violations}


def summarize_ensemble(ensemble: dict, observations: list[dict], hmm: dict) -> dict:
    by_id = {row["observation_id"]: row for row in observations}
    summaries = [
        summarize_trajectories(sample["trajectories"], by_id, hmm)
        for sample in ensemble["samples"]
    ]
    return {
        "invariants_pass": ensemble["invariants_pass"],
        "violation_sample_indices": ensemble["violation_sample_indices"],
        "posterior_summary": aggregate_posterior_summaries(summaries),
    }


def evaluate_development(manifest: dict, corruptions: dict, *,
                         ensemble_count: int = DEFAULT_TRAJECTORY_ENSEMBLE_COUNT) -> dict:
    """Run Stage C summary diagnostics on development sequence 01 only."""
    if isinstance(ensemble_count, bool) or not isinstance(ensemble_count, int) or ensemble_count <= 0:
        raise ValueError("ensemble_count must be a positive integer")
    development_manifest, development_corruptions = development_only_artifacts(manifest, corruptions)
    frozen_hmm = fit_development_speed_hmm(development_manifest)
    if frozen_hmm["model"].get("status") != "ok":
        raise RuntimeError("development reference cannot fit the required two-state speed HMM")
    reference_observations, reference_trajectories = _reference_trajectories(
        development_manifest["sequences"][DEVELOPMENT_SEQUENCE_ID]
    )
    reference_summary = summarize_trajectories(
        reference_trajectories, reference_observations, frozen_hmm["model"]
    )
    scenarios = []
    for scenario_index, scenario in enumerate(development_corruptions["scenarios"]):
        sequence = scenario["sequences"][DEVELOPMENT_SEQUENCE_ID]
        graph = generate_adaptive_candidate_graph(
            sequence["observations"], LOCKED_ADAPTIVE_V3_CONFIG
        )
        seed = scenario.get("seed", development_corruptions["seed"] + scenario_index * 1000) + 1
        exact = sample_exact_context_matchings(
            sequence["observations"], graph["candidate_edges"], count=ensemble_count,
            seed=seed, temperature_px=4.0,
            new_track_score_px=LOCKED_ADAPTIVE_V3_CONFIG.new_track_score_px,
        )
        sampled = sample_stage_a_ensemble(
            sequence["observations"], graph["candidate_edges"], count=ensemble_count, seed=seed
        )
        exact_summary = summarize_ensemble(
            {"samples": exact["samples"], "invariants_pass": all((
                exact["invariants"]["one_to_one_pass"],
                exact["invariants"]["trajectory_partition_pass"],
                exact["invariants"]["candidate_graph_pass"],
            )), "violation_sample_indices": sorted(set(
                exact["invariants"]["one_to_one_violation_sample_indices"]
                + exact["invariants"]["trajectory_partition_violation_sample_indices"]
                + [row["sample_index"] for row in exact["invariants"]["candidate_graph_violations"]]
            ))},
            sequence["observations"], frozen_hmm["model"],
        )
        sampled_summary = summarize_ensemble(sampled, sequence["observations"], frozen_hmm["model"])
        scenarios.append({
            "scenario_id": scenario["scenario_id"],
            "corruption": scenario["corruption"],
            "severity": scenario["severity"],
            "sequence_id": DEVELOPMENT_SEQUENCE_ID,
            "candidate_edges": graph["candidate_edge_count"],
            "exact_context": {
                **exact_summary,
                "component_count": len(exact["components"]),
                "maximum_component_targets": max(
                    (len(component["target_observation_ids"]) for component in exact["components"]), default=0
                ),
            },
            "sampled_stage_a": sampled_summary,
        })
    return {
        "schema_version": 1,
        "method": "stage_c_development_trajectory_summary_v1",
        "status": "DEVELOPMENT_COMPLETE",
        "development_sequence": DEVELOPMENT_SEQUENCE_ID,
        "locked_test_sequence_evaluated": False,
        "ensemble": {"count": ensemble_count, "seed_policy": "scenario_seed_plus_sequence_id"},
        "locked_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG),
        "stage_b_calibration_temperature": 0.55,
        "frozen_hmm": frozen_hmm,
        "reference_summary": reference_summary,
        "reference_manifest_sha256": development_corruptions["reference_manifest_sha256"],
        "corruption_seed": development_corruptions["seed"],
        "scenarios": scenarios,
        "warning": (
            "Development-only technical summary. Sequence 02 is excluded; image-derived "
            "speed states are not validated biological phenotypes."
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
        result = evaluate_development(manifest, corruptions)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Stage C development summary failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['scenarios'])} development scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
