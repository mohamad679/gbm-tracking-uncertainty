"""Exact graph-context marginals for one-to-one candidate-link matchings."""

from collections import defaultdict, deque
import math
import random


MAX_EXACT_COMPONENT_TARGETS = 18
DEFAULT_TRAJECTORY_ENSEMBLE_COUNT = 256
DEFAULT_TRAJECTORY_ENSEMBLE_SEED = 20260919


class ExactInferenceResourceError(ValueError):
    """Raised when a graph component exceeds the approved exact bound."""


def _positive_finite(value: float, name: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be finite and > 0")
    return number


def _index_observations(observations: list[dict]) -> dict[str, dict]:
    indexed = {}
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            raise ValueError(f"observation {index} must be an object")
        observation_id = row.get("observation_id")
        frame = row.get("frame")
        if not isinstance(observation_id, str) or not observation_id:
            raise ValueError(f"observation {index} has an invalid observation_id")
        if observation_id in indexed:
            raise ValueError(f"duplicate observation_id {observation_id!r}")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError(f"observation {observation_id!r} has an invalid frame")
        indexed[observation_id] = row
    return indexed


def _index_edges(candidate_edges: list[dict], observations: dict[str, dict]) -> dict:
    scores = {}
    for index, edge in enumerate(candidate_edges):
        if not isinstance(edge, dict):
            raise ValueError(f"candidate edge {index} must be an object")
        pair = (edge.get("from_observation_id"), edge.get("to_observation_id"))
        if pair[0] not in observations or pair[1] not in observations:
            raise ValueError(f"candidate edge {pair!r} references an unknown observation")
        if pair in scores:
            raise ValueError(f"duplicate candidate edge {pair!r}")
        if observations[pair[1]]["frame"] != observations[pair[0]]["frame"] + 1:
            raise ValueError(f"candidate edge {pair!r} is not consecutive")
        try:
            score = float(edge["proposal_score_px"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"candidate edge {pair!r} has no valid proposal_score_px") from exc
        if not math.isfinite(score) or score < 0:
            raise ValueError(f"candidate edge {pair!r} has an invalid proposal score")
        scores[pair] = score
    return scores


def _components(source_ids: list[str], target_ids: list[str], edge_scores: dict):
    """Return bipartite components, including isolated nodes."""
    adjacent = defaultdict(set)
    for source_id, target_id in edge_scores:
        adjacent[("source", source_id)].add(("target", target_id))
        adjacent[("target", target_id)].add(("source", source_id))
    seen, components = set(), []
    nodes = [("source", item) for item in source_ids] + [("target", item) for item in target_ids]
    for node in nodes:
        if node in seen:
            continue
        seen.add(node)
        queue = deque([node])
        sources, targets = set(), set()
        while queue:
            kind, observation_id = queue.popleft()
            (sources if kind == "source" else targets).add(observation_id)
            for neighbor in adjacent[(kind, observation_id)]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append((sorted(sources), sorted(targets)))
    return components


def _component_marginals(source_ids: list[str], target_ids: list[str], edge_scores: dict,
                         temperature_px: float, new_track_score_px: float) -> dict:
    if len(target_ids) > MAX_EXACT_COMPONENT_TARGETS:
        raise ExactInferenceResourceError(
            f"exact context component has {len(target_ids)} targets; approved limit is "
            f"{MAX_EXACT_COMPONENT_TARGETS}"
        )
    incoming = {target_id: [] for target_id in target_ids}
    for source_id in source_ids:
        for target_id in target_ids:
            score = edge_scores.get((source_id, target_id))
            if score is not None:
                incoming[target_id].append((source_id, math.exp(-score / temperature_px)))
    birth_weight = math.exp(-new_track_score_px / temperature_px)
    partition, count = 0.0, 0
    link_weight, birth_weight_sum = defaultdict(float), defaultdict(float)

    def visit(index: int, used_sources: set[str], matching: list[tuple[str, str]], weight: float):
        nonlocal partition, count
        if index == len(target_ids):
            partition += weight
            count += 1
            matched_targets = {target_id for _, target_id in matching}
            for pair in matching:
                link_weight[pair] += weight
            for target_id in target_ids:
                if target_id not in matched_targets:
                    birth_weight_sum[target_id] += weight
            return
        target_id = target_ids[index]
        visit(index + 1, used_sources, matching, weight * birth_weight)
        for source_id, weight_value in incoming[target_id]:
            if source_id not in used_sources:
                used_sources.add(source_id)
                matching.append((source_id, target_id))
                visit(index + 1, used_sources, matching, weight * weight_value)
                matching.pop()
                used_sources.remove(source_id)

    visit(0, set(), [], 1.0)
    if not math.isfinite(partition) or partition <= 0:
        raise RuntimeError("exact matching partition function is not finite and positive")
    return {
        "partition_function": partition,
        "enumerated_matching_count": count,
        "links": {pair: value / partition for pair, value in link_weight.items()},
        "births": {target_id: birth_weight_sum[target_id] / partition for target_id in target_ids},
    }


def _component_matching_states(source_ids: list[str], target_ids: list[str], edge_scores: dict,
                               temperature_px: float, new_track_score_px: float) -> dict:
    """Enumerate weighted matching states for one exact connected component."""
    if len(target_ids) > MAX_EXACT_COMPONENT_TARGETS:
        raise ExactInferenceResourceError(
            f"exact context component has {len(target_ids)} targets; approved limit is "
            f"{MAX_EXACT_COMPONENT_TARGETS}"
        )
    incoming = {target_id: [] for target_id in target_ids}
    for source_id in source_ids:
        for target_id in target_ids:
            score = edge_scores.get((source_id, target_id))
            if score is not None:
                incoming[target_id].append((source_id, math.exp(-score / temperature_px)))
    birth_weight = math.exp(-new_track_score_px / temperature_px)
    states = []

    def visit(index: int, used_sources: set[str], matching: list[tuple[str, str]], weight: float):
        if index == len(target_ids):
            states.append({"links": tuple(matching), "weight": weight})
            return
        target_id = target_ids[index]
        visit(index + 1, used_sources, matching, weight * birth_weight)
        for source_id, weight_value in incoming[target_id]:
            if source_id not in used_sources:
                used_sources.add(source_id)
                matching.append((source_id, target_id))
                visit(index + 1, used_sources, matching, weight * weight_value)
                matching.pop()
                used_sources.remove(source_id)

    visit(0, set(), [], 1.0)
    partition = sum(state["weight"] for state in states)
    if not math.isfinite(partition) or partition <= 0:
        raise RuntimeError("exact matching partition function is not finite and positive")
    return {"partition_function": partition, "states": states}


def _weighted_state_choice(rng: random.Random, states: list[dict], partition: float) -> dict:
    point = rng.random() * partition
    for state in states:
        point -= state["weight"]
        if point <= 0:
            return state
    return states[-1]


def trajectories_from_links(observation_ids: list[str], links: list[tuple[str, str]]) -> tuple[list[dict], dict]:
    """Build a partition of observations into frame-monotone trajectories."""
    successor, predecessor = {}, {}
    duplicate_sources, duplicate_targets = [], []
    for source_id, target_id in links:
        if source_id in successor:
            duplicate_sources.append(source_id)
        if target_id in predecessor:
            duplicate_targets.append(target_id)
        successor[source_id] = target_id
        predecessor[target_id] = source_id
    trajectories, seen = [], set()
    for start_id in sorted(observation_id for observation_id in observation_ids
                           if observation_id not in predecessor):
        path, current = [], start_id
        while current not in seen:
            seen.add(current)
            path.append(current)
            if current not in successor:
                break
            current = successor[current]
        trajectories.append({"observation_ids": path})
    missing = sorted(set(observation_ids) - seen)
    return trajectories, {
        "one_to_one_pass": not duplicate_sources and not duplicate_targets,
        "trajectory_partition_pass": not missing,
        "duplicate_source_observation_ids": sorted(set(duplicate_sources)),
        "duplicate_target_observation_ids": sorted(set(duplicate_targets)),
        "unassigned_observation_ids": missing,
    }


def _positive_integer(value: int, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer")
    return value


def sample_exact_context_matchings(
        observations: list[dict], candidate_edges: list[dict], *,
        count: int = DEFAULT_TRAJECTORY_ENSEMBLE_COUNT,
        seed: int = DEFAULT_TRAJECTORY_ENSEMBLE_SEED,
        temperature_px: float = 4.0,
        new_track_score_px: float = 10.0) -> dict:
    """Sample compatible exact matching states and convert them to trajectories.

    Only observations and candidate scores are read.  Every component state is
    sampled from its enumerated exact distribution; candidate links are never
    sampled independently.
    """
    count = _positive_integer(count, "count")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    temperature_px = _positive_finite(temperature_px, "temperature_px")
    new_track_score_px = _positive_finite(new_track_score_px, "new_track_score_px")
    by_id = _index_observations(observations)
    edge_scores = _index_edges(candidate_edges, by_id)
    by_frame = defaultdict(list)
    for observation_id, row in by_id.items():
        by_frame[row["frame"]].append(observation_id)

    component_models = []
    for frame in sorted(by_frame):
        sources, targets = sorted(by_frame[frame]), sorted(by_frame.get(frame + 1, []))
        if not targets:
            continue
        transition_edges = {
            pair: score for pair, score in edge_scores.items()
            if by_id[pair[0]]["frame"] == frame
        }
        for component_sources, component_targets in _components(sources, targets, transition_edges):
            distribution = _component_matching_states(
                component_sources, component_targets, transition_edges,
                temperature_px, new_track_score_px,
            )
            component_models.append({
                "source_frame": frame,
                "source_observation_ids": component_sources,
                "target_observation_ids": component_targets,
                "candidate_edge_count": sum(
                    (source_id, target_id) in transition_edges
                    for source_id in component_sources for target_id in component_targets
                ),
                "partition_function": distribution["partition_function"],
                "enumerated_matching_count": len(distribution["states"]),
                "states": distribution["states"],
            })

    candidate_pairs = set(edge_scores)
    observation_ids = sorted(by_id)
    samples, one_to_one_violations, partition_violations, graph_violations = [], [], [], []
    sampled_counts = defaultdict(int)
    for sample_index in range(count):
        rng = random.Random(seed + sample_index)
        links = []
        for component in component_models:
            chosen = _weighted_state_choice(
                rng, component["states"], component["partition_function"]
            )
            links.extend(chosen["links"])
        links = sorted(links)
        trajectories, trajectory_invariants = trajectories_from_links(observation_ids, links)
        if not trajectory_invariants["one_to_one_pass"]:
            one_to_one_violations.append(sample_index)
        if not trajectory_invariants["trajectory_partition_pass"]:
            partition_violations.append(sample_index)
        outside_graph = sorted(set(links) - candidate_pairs)
        if outside_graph:
            graph_violations.append({"sample_index": sample_index, "links": outside_graph})
        for pair in links:
            sampled_counts[pair] += 1
        samples.append({
            "sample_index": sample_index,
            "links": [
                {"from_observation_id": source_id, "to_observation_id": target_id}
                for source_id, target_id in links
            ],
            "trajectories": trajectories,
            "trajectory_count": len(trajectories),
            "link_count": len(links),
        })

    return {
        "schema_version": 1,
        "method": "exact_component_matching_trajectory_ensemble_v1",
        "sample_count": count,
        "seed": seed,
        "temperature_px": temperature_px,
        "new_track_score_px": new_track_score_px,
        "max_exact_component_targets": MAX_EXACT_COMPONENT_TARGETS,
        "components": [
            {key: value for key, value in component.items() if key != "states"}
            for component in component_models
        ],
        "sampled_link_marginals": [
            {
                "from_observation_id": source_id,
                "to_observation_id": target_id,
                "probability": sampled_counts[(source_id, target_id)] / count,
            }
            for source_id, target_id in sorted(candidate_pairs)
        ],
        "samples": samples,
        "invariants": {
            "one_to_one_pass": not one_to_one_violations,
            "trajectory_partition_pass": not partition_violations,
            "candidate_graph_pass": not graph_violations,
            "one_to_one_violation_sample_indices": one_to_one_violations,
            "trajectory_partition_violation_sample_indices": partition_violations,
            "candidate_graph_violations": graph_violations,
        },
    }


def exact_context_marginals(observations: list[dict], candidate_edges: list[dict], *,
                            temperature_px: float = 4.0,
                            new_track_score_px: float = 10.0) -> dict:
    """Marginalize every compatible matching without reading reference truth."""
    temperature_px = _positive_finite(temperature_px, "temperature_px")
    new_track_score_px = _positive_finite(new_track_score_px, "new_track_score_px")
    by_id = _index_observations(observations)
    edge_scores = _index_edges(candidate_edges, by_id)
    by_frame = defaultdict(list)
    for observation_id, row in by_id.items():
        by_frame[row["frame"]].append(observation_id)

    links, births, components = {}, {}, []
    all_sources = set()
    for frame in sorted(by_frame):
        sources, targets = sorted(by_frame[frame]), sorted(by_frame.get(frame + 1, []))
        if not targets:
            continue
        all_sources.update(sources)
        transition_edges = {
            pair: score for pair, score in edge_scores.items()
            if by_id[pair[0]]["frame"] == frame
        }
        for component_sources, component_targets in _components(sources, targets, transition_edges):
            result = _component_marginals(
                component_sources, component_targets, transition_edges,
                temperature_px, new_track_score_px,
            )
            links.update(result["links"])
            births.update(result["births"])
            components.append({
                "source_frame": frame,
                "source_observation_ids": component_sources,
                "target_observation_ids": component_targets,
                "candidate_edge_count": sum(
                    (source_id, target_id) in transition_edges
                    for source_id in component_sources for target_id in component_targets
                ),
                "enumerated_matching_count": result["enumerated_matching_count"],
                "partition_function": result["partition_function"],
            })

    outgoing = defaultdict(float)
    incoming = defaultdict(float)
    for (source_id, target_id), probability in links.items():
        outgoing[source_id] += probability
        incoming[target_id] += probability
    tolerance = 1e-12
    target_total = {target_id: births[target_id] + incoming[target_id] for target_id in births}
    source_violations = {key: value for key, value in outgoing.items() if value > 1 + tolerance}
    target_violations = {
        key: value for key, value in target_total.items()
        if not math.isclose(value, 1.0, rel_tol=tolerance, abs_tol=tolerance)
    }
    return {
        "schema_version": 1,
        "method": "exact_component_one_to_one_matching_v1",
        "temperature_px": temperature_px,
        "new_track_score_px": new_track_score_px,
        "max_exact_component_targets": MAX_EXACT_COMPONENT_TARGETS,
        "components": components,
        "link_marginals": [
            {"from_observation_id": source_id, "to_observation_id": target_id, "probability": probability}
            for (source_id, target_id), probability in sorted(links.items())
        ],
        "new_track_marginals": [
            {"to_observation_id": target_id, "probability": probability}
            for target_id, probability in sorted(births.items())
        ],
        "source_unmatched_marginals": [
            {"from_observation_id": source_id, "probability": 1.0 - outgoing[source_id]}
            for source_id in sorted(all_sources)
        ],
        "invariants": {
            "target_conservation_pass": not target_violations,
            "source_capacity_pass": not source_violations,
            "target_conservation_violations": target_violations,
            "source_capacity_violations": source_violations,
        },
    }
