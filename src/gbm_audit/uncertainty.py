"""Estimate association uncertainty with sampled, globally compatible hypotheses."""

import argparse
import json
import math
from pathlib import Path
import random
import sys
from zipfile import ZipFile

import numpy as np

from gbm_audit.adaptive_candidates import (
    AdaptiveCandidateConfig,
    generate_adaptive_candidate_graph,
)
from gbm_audit.appearance import add_descriptors, load_frames
from gbm_audit.archive import validate_zip_archive
from gbm_audit.calibration import temperature_transform
from gbm_audit.config import (
    DEFAULT_APPEARANCE_TEMPERATURE,
    DEFAULT_AREA_TEMPERATURE,
    DEFAULT_HYPOTHESIS_COUNT,
    DEFAULT_MAX_DISTANCE_PX,
    DEFAULT_RANDOM_SEED,
    DEFAULT_TEMPERATURE_PX,
)


def _validate_sampling_parameters(count: int, max_distance_px: float,
                                  temperature_px: float,
                                  *, area_temperature: float | None = None,
                                  appearance_temperature: float | None = None) -> None:
    if count <= 0:
        raise ValueError("hypothesis count must be a positive integer")
    if not math.isfinite(max_distance_px) or max_distance_px <= 0:
        raise ValueError("max_distance_px must be finite and > 0")
    if not math.isfinite(temperature_px) or temperature_px <= 0:
        raise ValueError("temperature_px must be finite and > 0")
    if area_temperature is not None and (not math.isfinite(area_temperature) or area_temperature <= 0):
        raise ValueError("area_temperature must be finite and > 0")
    if appearance_temperature is not None and (
            not math.isfinite(appearance_temperature) or appearance_temperature <= 0):
        raise ValueError("appearance_temperature must be finite and > 0")


def _candidate_edges(observations: list[dict], max_distance_px: float) -> list[tuple[str, str, float]]:
    by_frame: dict[int, list[dict]] = {}
    for row in observations:
        by_frame.setdefault(int(row["frame"]), []).append(row)
    edges = []
    for frame in sorted(by_frame):
        previous = by_frame.get(frame - 1, [])
        current = by_frame[frame]
        for left in previous:
            for right in current:
                distance = float(np.hypot(right["x_px"] - left["x_px"], right["y_px"] - left["y_px"]))
                if distance <= max_distance_px:
                    edges.append((left["observation_id"], right["observation_id"], distance))
    return edges


def _weighted_choice(rng: random.Random, choices: list[tuple[object, float]]) -> object:
    total = sum(weight for _, weight in choices)
    if total <= 0:
        return choices[-1][0]
    point = rng.random() * total
    for choice, weight in choices:
        point -= weight
        if point <= 0:
            return choice
    return choices[-1][0]


def sample_link_hypotheses(observations: list[dict], count: int = DEFAULT_HYPOTHESIS_COUNT,
                           max_distance_px: float = DEFAULT_MAX_DISTANCE_PX,
                           temperature_px: float = DEFAULT_TEMPERATURE_PX,
                           seed: int = DEFAULT_RANDOM_SEED) -> list[set[tuple[str, str]]]:
    """Sample one-to-one frame-to-frame link sets; no truth fields are read."""
    _validate_sampling_parameters(count, max_distance_px, temperature_px)
    by_frame: dict[int, list[dict]] = {}
    for row in observations:
        by_frame.setdefault(int(row["frame"]), []).append(row)
    hypotheses = []
    for repeat in range(count):
        rng = random.Random(seed + repeat)
        active: dict[int, tuple[int, str, float, float]] = {}
        next_track = 1
        links: set[tuple[str, str]] = set()
        for frame in sorted(by_frame):
            active = {track_id: state for track_id, state in active.items() if state[0] == frame - 1}
            rows = list(by_frame[frame])
            rng.shuffle(rows)
            used_tracks: set[int] = set()
            current_active = {}
            for row in rows:
                choices: list[tuple[object, float]] = []
                for track_id, (_, previous_id, x, y) in active.items():
                    if track_id in used_tracks:
                        continue
                    distance = float(np.hypot(row["x_px"] - x, row["y_px"] - y))
                    if distance <= max_distance_px:
                        weight = math.exp(-distance / temperature_px)
                        choices.append(((track_id, previous_id), weight))
                choices.append(((None, None), math.exp(-max_distance_px / temperature_px)))
                track_choice, previous_id = _weighted_choice(rng, choices)
                if track_choice is None:
                    track_choice = next_track
                    next_track += 1
                else:
                    used_tracks.add(track_choice)
                    links.add((previous_id, row["observation_id"]))
                current_active[track_choice] = (frame, row["observation_id"], row["x_px"], row["y_px"])
            active = current_active
        hypotheses.append(links)
    return hypotheses


def sample_candidate_graph_hypotheses(
        observations: list[dict], candidate_edges: list[dict],
        count: int = DEFAULT_HYPOTHESIS_COUNT,
        temperature_px: float = DEFAULT_TEMPERATURE_PX,
        new_track_score_px: float = DEFAULT_MAX_DISTANCE_PX,
        seed: int = DEFAULT_RANDOM_SEED) -> list[set[tuple[str, str]]]:
    """Sample one-to-one links using only an explicit candidate graph."""
    _validate_sampling_parameters(count, new_track_score_px, temperature_px)
    by_frame: dict[int, list[dict]] = {}
    observation_by_id = {}
    for row in observations:
        observation_id = row["observation_id"]
        if observation_id in observation_by_id:
            raise ValueError(f"duplicate observation_id {observation_id!r}")
        observation_by_id[observation_id] = row
        by_frame.setdefault(int(row["frame"]), []).append(row)
    edge_by_pair = {}
    for edge in candidate_edges:
        pair = (edge["from_observation_id"], edge["to_observation_id"])
        if pair in edge_by_pair:
            raise ValueError(f"duplicate candidate edge {pair!r}")
        if pair[0] not in observation_by_id or pair[1] not in observation_by_id:
            raise ValueError(f"candidate edge {pair!r} references an unknown observation")
        left_frame = int(observation_by_id[pair[0]]["frame"])
        right_frame = int(observation_by_id[pair[1]]["frame"])
        if right_frame != left_frame + 1:
            raise ValueError(f"candidate edge {pair!r} is not consecutive")
        score = float(edge["proposal_score_px"])
        if not math.isfinite(score) or score < 0:
            raise ValueError(f"candidate edge {pair!r} has an invalid proposal score")
        edge_by_pair[pair] = score
    hypotheses = []
    for repeat in range(count):
        rng = random.Random(seed + repeat)
        active: dict[int, tuple[int, str]] = {}
        next_track = 1
        links: set[tuple[str, str]] = set()
        for frame in sorted(by_frame):
            active = {
                track_id: state for track_id, state in active.items()
                if state[0] == frame - 1
            }
            rows = sorted(by_frame[frame], key=lambda row: row["observation_id"])
            rng.shuffle(rows)
            used_tracks: set[int] = set()
            current_active = {}
            for row in rows:
                target_id = row["observation_id"]
                choices: list[tuple[object, float]] = []
                for track_id, (_, previous_id) in active.items():
                    if track_id in used_tracks:
                        continue
                    score = edge_by_pair.get((previous_id, target_id))
                    if score is not None:
                        choices.append(
                            ((track_id, previous_id), math.exp(-score / temperature_px))
                        )
                choices.append(((None, None), math.exp(-new_track_score_px / temperature_px)))
                track_choice, previous_id = _weighted_choice(rng, choices)
                if track_choice is None:
                    track_choice = next_track
                    next_track += 1
                else:
                    used_tracks.add(track_choice)
                    links.add((previous_id, target_id))
                current_active[track_choice] = (frame, target_id)
            active = current_active
        hypotheses.append(links)
    return hypotheses


def _sample_motion_link_hypotheses(observations: list[dict], count: int = DEFAULT_HYPOTHESIS_COUNT,
                                   max_distance_px: float = DEFAULT_MAX_DISTANCE_PX,
                                   temperature_px: float = DEFAULT_TEMPERATURE_PX,
                                   seed: int = DEFAULT_RANDOM_SEED,
                                   area_temperature: float | None = None,
                                   appearance_temperature: float | None = None,
                                   allowed_edges: set[tuple[str, str]] | None = None
                                   ) -> list[set[tuple[str, str]]]:
    """Sample links using a constant-velocity prediction for each active path."""
    _validate_sampling_parameters(
        count, max_distance_px, temperature_px,
        area_temperature=area_temperature,
        appearance_temperature=appearance_temperature,
    )
    by_frame: dict[int, list[dict]] = {}
    for row in observations:
        by_frame.setdefault(int(row["frame"]), []).append(row)
    hypotheses = []
    for repeat in range(count):
        rng = random.Random(seed + repeat)
        active: dict[int, tuple] = {}
        next_track = 1
        links: set[tuple[str, str]] = set()
        for frame in sorted(by_frame):
            active = {track_id: state for track_id, state in active.items() if state[0] == frame - 1}
            rows = list(by_frame[frame])
            rng.shuffle(rows)
            used_tracks: set[int] = set()
            current_active = {}
            for row in rows:
                choices: list[tuple[object, float]] = []
                for track_id, state in active.items():
                    if track_id in used_tracks:
                        continue
                    _, previous_id, last_x, last_y, prior_x, prior_y, last_area, last_appearance = state
                    if allowed_edges is not None and (previous_id, row["observation_id"]) not in allowed_edges:
                        continue
                    if prior_x is None or prior_y is None:
                        predicted_x, predicted_y = last_x, last_y
                    else:
                        predicted_x = last_x + (last_x - prior_x)
                        predicted_y = last_y + (last_y - prior_y)
                    residual = float(np.hypot(row["x_px"] - predicted_x, row["y_px"] - predicted_y))
                    if residual <= max_distance_px:
                        area_penalty = 0.0
                        if area_temperature is not None:
                            area_penalty = abs(math.log((float(row.get("area_px", 0.0)) + 1.0)
                                                       / (last_area + 1.0))) / area_temperature
                        appearance_penalty = 0.0
                        descriptor = row.get("appearance_descriptor")
                        if appearance_temperature is not None and descriptor is not None and last_appearance is not None:
                            vector = np.asarray(descriptor, dtype=float)
                            previous_vector = np.asarray(last_appearance, dtype=float)
                            if vector.shape != previous_vector.shape:
                                raise ValueError("appearance descriptors must have matching dimensions")
                            appearance_distance = float(
                                np.linalg.norm(vector - previous_vector) / max(np.sqrt(len(vector)), 1.0)
                            )
                            appearance_penalty = appearance_distance / appearance_temperature
                        weight = math.exp(-residual / temperature_px - area_penalty - appearance_penalty)
                        choices.append(((track_id, previous_id), weight))
                choices.append(((None, None), math.exp(-max_distance_px / temperature_px)))
                track_choice, previous_id = _weighted_choice(rng, choices)
                if track_choice is None:
                    track_choice = next_track
                    next_track += 1
                    prior_x, prior_y = None, None
                else:
                    used_tracks.add(track_choice)
                    links.add((previous_id, row["observation_id"]))
                    prior_state = active[track_choice]
                    prior_x, prior_y = prior_state[2], prior_state[3]
                current_active[track_choice] = (
                    frame, row["observation_id"], row["x_px"], row["y_px"], prior_x, prior_y,
                    float(row.get("area_px", 0.0)), row.get("appearance_descriptor")
                )
            active = current_active
        hypotheses.append(links)
    return hypotheses


def sample_motion_link_hypotheses(observations: list[dict], count: int = DEFAULT_HYPOTHESIS_COUNT,
                                  max_distance_px: float = DEFAULT_MAX_DISTANCE_PX,
                                  temperature_px: float = DEFAULT_TEMPERATURE_PX,
                                  seed: int = DEFAULT_RANDOM_SEED) -> list[set[tuple[str, str]]]:
    allowed_edges = {edge[:2] for edge in _candidate_edges(observations, max_distance_px)}
    return _sample_motion_link_hypotheses(
        observations, count, max_distance_px, temperature_px, seed, None,
        allowed_edges=allowed_edges,
    )


def sample_motion_area_link_hypotheses(observations: list[dict], count: int = DEFAULT_HYPOTHESIS_COUNT,
                                       max_distance_px: float = DEFAULT_MAX_DISTANCE_PX,
                                       temperature_px: float = DEFAULT_TEMPERATURE_PX,
                                       seed: int = DEFAULT_RANDOM_SEED,
                                       area_temperature: float = DEFAULT_AREA_TEMPERATURE) -> list[set[tuple[str, str]]]:
    allowed_edges = {edge[:2] for edge in _candidate_edges(observations, max_distance_px)}
    return _sample_motion_link_hypotheses(
        observations, count, max_distance_px, temperature_px, seed, area_temperature,
        allowed_edges=allowed_edges,
    )


def sample_motion_appearance_link_hypotheses(observations: list[dict], count: int = DEFAULT_HYPOTHESIS_COUNT,
                                             max_distance_px: float = DEFAULT_MAX_DISTANCE_PX,
                                             temperature_px: float = DEFAULT_TEMPERATURE_PX,
                                             seed: int = DEFAULT_RANDOM_SEED,
                                             appearance_temperature: float = DEFAULT_APPEARANCE_TEMPERATURE) -> list[set[tuple[str, str]]]:
    allowed_edges = {edge[:2] for edge in _candidate_edges(observations, max_distance_px)}
    return _sample_motion_link_hypotheses(
        observations, count, max_distance_px, temperature_px, seed, None,
        appearance_temperature, allowed_edges,
    )


def _calibration(probabilities: list[float], labels: list[int], bins: int = 10) -> dict:
    if not probabilities:
        return {"brier": 0.0, "ece": 0.0, "count": 0}
    brier = float(np.mean([(p - y) ** 2 for p, y in zip(probabilities, labels)]))
    ece = 0.0
    bin_rows = []
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [i for i, p in enumerate(probabilities) if lower <= p < upper or (index == bins - 1 and p == upper)]
        if not selected:
            continue
        mean_probability = float(np.mean([probabilities[i] for i in selected]))
        frequency = float(np.mean([labels[i] for i in selected]))
        ece += len(selected) / len(probabilities) * abs(mean_probability - frequency)
        bin_rows.append({"lower": lower, "upper": upper, "count": len(selected),
                         "mean_probability": mean_probability, "empirical_frequency": frequency})
    return {"brier": brier, "ece": float(ece), "count": len(probabilities), "bins": bin_rows}


def _distance_baseline_probabilities(edges: list[tuple[str, str, float]],
                                     max_distance_px: float, temperature_px: float) -> list[float]:
    by_target: dict[str, list[tuple[int, float]]] = {}
    for index, (_, target, distance) in enumerate(edges):
        by_target.setdefault(target, []).append((index, distance))
    new_weight = math.exp(-max_distance_px / temperature_px)
    probabilities = [0.0] * len(edges)
    for candidates in by_target.values():
        denominator = new_weight + sum(math.exp(-distance / temperature_px) for _, distance in candidates)
        for index, distance in candidates:
            probabilities[index] = math.exp(-distance / temperature_px) / denominator
    return probabilities


def _fit_temperature(sequence_results: list[dict]) -> float:
    pairs = [(link["probability"], int(link["true_link"]))
             for result in sequence_results for link in result["posterior_links"]]
    if not pairs:
        return 1.0
    candidates = [0.25 + index * 0.05 for index in range(316)]

    def loss(temperature):
        return float(np.mean([(temperature_transform(probability, temperature) - label) ** 2
                              for probability, label in pairs]))

    return min(candidates, key=loss)


def evaluate_sequence(sequence: dict, scenario_sequence: dict, count: int,
                      max_distance_px: float, temperature_px: float, seed: int,
                      proposal_model: str = "distance",
                      adaptive_config: AdaptiveCandidateConfig | None = None) -> dict:
    _validate_sampling_parameters(count, max_distance_px, temperature_px)
    observations = scenario_sequence["observations"]
    truth = {row["observation_id"]: row["true_track_id"] for row in scenario_sequence["evaluation_truth"]}
    adaptive_graph = None
    edge_metadata = {}
    baseline_new_track_score = max_distance_px
    if proposal_model == "adaptive_v1":
        adaptive_config = adaptive_config or AdaptiveCandidateConfig()
        adaptive_graph = generate_adaptive_candidate_graph(observations, adaptive_config)
        edges = [
            (edge["from_observation_id"], edge["to_observation_id"], edge["distance_px"])
            for edge in adaptive_graph["candidate_edges"]
        ]
        score_edges = [
            (edge["from_observation_id"], edge["to_observation_id"], edge["proposal_score_px"])
            for edge in adaptive_graph["candidate_edges"]
        ]
        edge_metadata = {
            (edge["from_observation_id"], edge["to_observation_id"]): edge
            for edge in adaptive_graph["candidate_edges"]
        }
        candidate_target_observations = adaptive_graph["candidate_target_observations"]
        baseline_new_track_score = adaptive_config.max_radius_px
        hypotheses = sample_candidate_graph_hypotheses(
            observations, adaptive_graph["candidate_edges"], count,
            temperature_px, adaptive_config.max_radius_px, seed,
        )
    else:
        edges = _candidate_edges(observations, max_distance_px)
        score_edges = edges
        first_frame = min(sequence.get("frame_indices", [0]))
        candidate_target_observations = sum(
            int(row["frame"]) > first_frame for row in observations
        )
    if proposal_model == "distance":
        hypotheses = sample_link_hypotheses(observations, count, max_distance_px, temperature_px, seed)
    elif proposal_model == "motion":
        hypotheses = sample_motion_link_hypotheses(observations, count, max_distance_px, temperature_px, seed)
    elif proposal_model == "motion_area":
        hypotheses = sample_motion_area_link_hypotheses(observations, count, max_distance_px, temperature_px, seed)
    elif proposal_model == "motion_appearance":
        hypotheses = sample_motion_appearance_link_hypotheses(observations, count, max_distance_px, temperature_px, seed)
    elif proposal_model != "adaptive_v1":
        raise ValueError(f"Unknown proposal model: {proposal_model}")
    candidate_pairs = {edge[:2] for edge in edges}
    sampled_pairs = set().union(*hypotheses) if hypotheses else set()
    outside_candidate_graph = sampled_pairs - candidate_pairs
    if outside_candidate_graph:
        raise RuntimeError(
            f"sampled links outside candidate graph: {sorted(outside_candidate_graph)[:5]}"
        )
    edge_counts = {edge[:2]: sum(edge[:2] in hypothesis for hypothesis in hypotheses) for edge in edges}
    probabilities = [edge_counts[(left, right)] / count for left, right, _ in edges]
    labels = [int(truth.get(left, 0) > 0 and truth.get(left) == truth.get(right, 0)) for left, right, _ in edges]
    truth_by_track_frame: dict[tuple[int, int], str] = {}
    for row in scenario_sequence["evaluation_truth"]:
        if row["true_track_id"] > 0 and row["observed"]:
            truth_by_track_frame[(row["true_track_id"], row["frame"])] = row["observation_id"]
    total_reference_links = sum((track_id, frame + 1) in truth_by_track_frame
                                for track_id, frame in truth_by_track_frame)
    baseline_probabilities = _distance_baseline_probabilities(
        score_edges, baseline_new_track_score, temperature_px
    )
    candidate_true_links = sum(labels)
    selective = {}
    for threshold in (0.5, 0.7, 0.9):
        accepted = [i for i, probability in enumerate(probabilities) if probability >= threshold]
        tp = sum(labels[i] for i in accepted)
        selective[str(threshold)] = {
            "accepted_edges": len(accepted),
            "precision": tp / len(accepted) if accepted else 1.0,
            "recall_over_candidate_edges": tp / candidate_true_links if candidate_true_links else 1.0,
            "recall_over_all_reference_links": tp / total_reference_links if total_reference_links else 1.0,
            "coverage": len(accepted) / len(edges) if edges else 0.0,
        }
    posterior_links = []
    for (left, right, distance), probability, label in zip(edges, probabilities, labels):
        row = {
            "from_observation_id": left,
            "to_observation_id": right,
            "distance_px": round(distance, 6),
            "probability": round(probability, 6),
            "true_link": bool(label),
        }
        if adaptive_graph is not None:
            metadata = edge_metadata[(left, right)]
            row.update({
                "predicted_residual_px": metadata["predicted_residual_px"],
                "proposal_score_px": metadata["proposal_score_px"],
                "adaptive_radius_px": metadata["adaptive_radius_px"],
                "candidate_inclusion": metadata["inclusion"],
            })
        posterior_links.append(row)
    return {
        "scenario_id": scenario_sequence["sequence_id"],
        "observations": len(observations),
        "candidate_edges": len(edges),
        "candidate_target_observations": candidate_target_observations,
        "candidate_burden_edges_per_target": (
            len(edges) / candidate_target_observations
            if candidate_target_observations else 0.0
        ),
        "reference_links_present": total_reference_links,
        "hypothesis_count": count,
        "unique_hypothesis_count": len({frozenset(hypothesis) for hypothesis in hypotheses}),
        "sampled_links_outside_candidate_graph": 0,
        "posterior_links": posterior_links,
        "hypothesis_calibration": _calibration(probabilities, labels),
        "deterministic_baseline_calibration": _calibration(baseline_probabilities, labels),
        "candidate_true_link_count": candidate_true_links,
        "candidate_true_link_coverage": candidate_true_links / total_reference_links if total_reference_links else 1.0,
        "candidate_graph_method": (
            adaptive_graph["method"] if adaptive_graph is not None
            else f"fixed_distance_{max_distance_px:g}px"
        ),
        "candidate_source_gates": (
            adaptive_graph["source_gates"] if adaptive_graph is not None else []
        ),
        "selective": selective,
        "temperature_px": temperature_px,
        "max_distance_px": (
            adaptive_config.max_radius_px if adaptive_graph is not None else max_distance_px
        ),
    }


def evaluate_benchmark(manifest: dict, corruption_benchmark: dict,
                       count: int = DEFAULT_HYPOTHESIS_COUNT,
                       max_distance_px: float = DEFAULT_MAX_DISTANCE_PX,
                       temperature_px: float = DEFAULT_TEMPERATURE_PX,
                       proposal_model: str = "distance", archive_path: Path | None = None,
                       adaptive_config: AdaptiveCandidateConfig | None = None) -> dict:
    _validate_sampling_parameters(count, max_distance_px, temperature_px)
    if proposal_model == "adaptive_v1":
        adaptive_config = adaptive_config or AdaptiveCandidateConfig()
        adaptive_config.validate()
    appearance_frames = {}
    if proposal_model == "motion_appearance":
        if archive_path is None:
            raise ValueError("motion_appearance requires --archive")
        with ZipFile(archive_path) as archive:
            validate_zip_archive(archive)
            for sequence_id, sequence in manifest["sequences"].items():
                appearance_frames[sequence_id] = load_frames(archive, sequence["image_paths"])
    results = []
    for scenario_index, scenario in enumerate(corruption_benchmark["scenarios"]):
        sequence_results = {}
        scenario_seed = scenario.get(
            "seed", corruption_benchmark["seed"] + scenario_index * 1000
        )
        for sequence_id, scenario_sequence in scenario["sequences"].items():
            if proposal_model == "motion_appearance":
                scenario_sequence = {**scenario_sequence,
                                     "observations": add_descriptors(
                                         scenario_sequence["observations"], appearance_frames[sequence_id])}
            sequence_results[sequence_id] = evaluate_sequence(
                manifest["sequences"][sequence_id], scenario_sequence, count,
                max_distance_px, temperature_px,
                scenario_seed + int(sequence_id),
                proposal_model, adaptive_config)
        results.append({"scenario_id": scenario["scenario_id"], "corruption": scenario["corruption"],
                        "severity": scenario["severity"], "sequence_results": sequence_results})
    calibration_temperature = _fit_temperature([result["sequence_results"]["01"] for result in results])
    for result in results:
        for sequence_result in result["sequence_results"].values():
            calibrated_probabilities = [
                temperature_transform(link["probability"], calibration_temperature)
                for link in sequence_result["posterior_links"]
            ]
            labels = [int(link["true_link"]) for link in sequence_result["posterior_links"]]
            sequence_result["calibrated_hypothesis_calibration"] = _calibration(calibrated_probabilities, labels)
            sequence_result["calibration_temperature"] = calibration_temperature
            sequence_result["calibration_fit_sequence"] = "01"
    return {
        "schema_version": 1,
        "method": f"sampled_one_to_one_{proposal_model}_hypotheses",
        "proposal_model": proposal_model,
        "hypothesis_count": count,
        "temperature_px": temperature_px,
        "calibration": {"method": "development_sequence_temperature_scaling",
                         "fit_sequence": "01", "temperature": calibration_temperature},
        "max_distance_px": (
            adaptive_config.max_radius_px
            if proposal_model == "adaptive_v1" and adaptive_config is not None
            else max_distance_px
        ),
        "adaptive_candidate_config": (
            adaptive_config.__dict__
            if proposal_model == "adaptive_v1" and adaptive_config is not None
            else None
        ),
        "reference_manifest_sha256": corruption_benchmark["reference_manifest_sha256"],
        "corruption_seed": corruption_benchmark["seed"],
        "scenarios": results,
        "warning": "Technical uncertainty calibration on U373 reference-derived scenarios; not biological validation of GlioTrace.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hypotheses", type=int, default=DEFAULT_HYPOTHESIS_COUNT)
    parser.add_argument("--max-distance-px", type=float, default=DEFAULT_MAX_DISTANCE_PX)
    parser.add_argument("--temperature-px", type=float, default=DEFAULT_TEMPERATURE_PX)
    parser.add_argument(
        "--proposal-model",
        choices=("distance", "motion", "motion_area", "motion_appearance", "adaptive_v1"),
        default="distance",
    )
    parser.add_argument("--archive", type=Path, default=None,
                        help="U373 ZIP required by motion_appearance")
    parser.add_argument("--adaptive-min-radius-px", type=float, default=8.0)
    parser.add_argument("--adaptive-max-radius-px", type=float, default=16.0)
    parser.add_argument("--adaptive-motion-weight", type=float, default=1.0)
    parser.add_argument("--adaptive-density-weight-px", type=float, default=4.0)
    parser.add_argument("--adaptive-density-radius-px", type=float, default=16.0)
    parser.add_argument("--adaptive-density-saturation-count", type=int, default=6)
    parser.add_argument("--adaptive-cold-start-uncertainty-px", type=float, default=4.0)
    parser.add_argument("--adaptive-history-length", type=int, default=4)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruptions = json.loads(args.corruptions.read_text(encoding="utf-8"))
        adaptive_config = None
        if args.proposal_model == "adaptive_v1":
            adaptive_config = AdaptiveCandidateConfig(
                min_radius_px=args.adaptive_min_radius_px,
                max_radius_px=args.adaptive_max_radius_px,
                motion_uncertainty_weight=args.adaptive_motion_weight,
                density_weight_px=args.adaptive_density_weight_px,
                density_radius_px=args.adaptive_density_radius_px,
                density_saturation_count=args.adaptive_density_saturation_count,
                cold_start_uncertainty_px=args.adaptive_cold_start_uncertainty_px,
                history_length=args.adaptive_history_length,
            )
        result = evaluate_benchmark(manifest, corruptions, args.hypotheses,
                                    args.max_distance_px, args.temperature_px,
                                    args.proposal_model, args.archive, adaptive_config)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Uncertainty evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['scenarios'])} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
