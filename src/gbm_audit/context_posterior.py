"""Exact graph-context marginals for one-to-one candidate-link matchings."""

from collections import defaultdict, deque
import math


MAX_EXACT_COMPONENT_TARGETS = 18


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
