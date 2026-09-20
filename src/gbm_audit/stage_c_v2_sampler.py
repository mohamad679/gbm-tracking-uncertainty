"""Stage C v2 predictive sampling on development observations only.

The sampler adds two uncertainty sources around the frozen Stage C v1 exact
association sampler: truth-blind coordinate jitter and explicit adjacent/gap
recovery proposals.  Reference identities are accepted only by the separate
development calibration function; application functions reject/strip truth
fields and never consult them.
"""

from collections import defaultdict, deque
from dataclasses import asdict, dataclass
import math
import random

import numpy as np

from gbm_audit.adaptive_candidates import AdaptiveCandidateConfig, generate_adaptive_candidate_graph
from gbm_audit.context_posterior import (
    MAX_EXACT_COMPONENT_TARGETS,
    trajectories_from_links,
)


LOCALIZATION_DIAGNOSTIC_FIELDS = (
    "median_proposal_distance_px",
    "candidate_degree",
)
TRUTH_KEYS = frozenset({
    "true_track_id", "observed_track_id", "reference_track_id", "evaluation_truth",
    "truth", "parent_id", "start_frame", "end_frame",
})


@dataclass(frozen=True)
class StageCV2SamplerConfig:
    """Frozen sampler controls; values are not selected on T98G or sequence 02."""

    recovery_gate_multiplier: float = 2.0
    bridge_delta_t: int = 2
    temperature_px: float = 4.0
    new_track_score_px: float = 10.0
    ensemble_count: int = 256
    max_localization_sigma_px: float = 32.0

    def validate(self) -> None:
        for name in (
                "recovery_gate_multiplier", "temperature_px", "new_track_score_px",
                "max_localization_sigma_px"):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and > 0")
        if self.bridge_delta_t != 2:
            raise ValueError("bridge_delta_t is frozen at 2")
        if isinstance(self.ensemble_count, bool) or not isinstance(self.ensemble_count, int):
            raise ValueError("ensemble_count must be a positive integer")
        if self.ensemble_count <= 0:
            raise ValueError("ensemble_count must be a positive integer")


def _finite(value, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def fit_localization_model(calibration_rows: list[dict], *, fit_sequence_id: str = "01") -> dict:
    """Fit the registered non-negative affine localization scale on development rows.

    Each row is a development-only observation/reference residual.  Application
    code never calls this function and never receives the reference fields.
    The target converts radial residuals to an isotropic Gaussian scale using
    the Rayleigh mean factor.
    """
    if not isinstance(fit_sequence_id, str) or not fit_sequence_id:
        raise ValueError("fit_sequence_id must be a non-empty string")
    if not isinstance(calibration_rows, list) or not calibration_rows:
        raise ValueError("calibration_rows must be a non-empty list")
    design, targets = [], []
    for index, row in enumerate(calibration_rows):
        if not isinstance(row, dict):
            raise ValueError(f"calibration row {index} must be an object")
        missing = [
            key for key in ("residual_dx_px", "residual_dy_px", *LOCALIZATION_DIAGNOSTIC_FIELDS)
            if key not in row
        ]
        if missing:
            raise ValueError(f"calibration row {index} missing: {', '.join(missing)}")
        dx = _finite(row["residual_dx_px"], "residual_dx_px")
        dy = _finite(row["residual_dy_px"], "residual_dy_px")
        distance = _finite(row["median_proposal_distance_px"], "median_proposal_distance_px")
        degree = _finite(row["candidate_degree"], "candidate_degree")
        if distance < 0 or degree < 0:
            raise ValueError("localization diagnostics must be non-negative")
        design.append([1.0, distance, degree])
        targets.append(math.hypot(dx, dy) / math.sqrt(math.pi / 2.0))
    x = np.asarray(design, dtype=float)
    y = np.asarray(targets, dtype=float)
    # Enumerating active sets gives a small deterministic NNLS solver without a
    # new dependency.  The intercept, distance and degree slopes are all >= 0.
    best = None
    for mask in range(1, 1 << x.shape[1]):
        active = [column for column in range(x.shape[1]) if mask & (1 << column)]
        coefficients = np.zeros(x.shape[1], dtype=float)
        fit, _, _, _ = np.linalg.lstsq(x[:, active], y, rcond=None)
        if np.any(fit < -1e-10):
            continue
        coefficients[active] = np.maximum(fit, 0.0)
        residual_sse = float(np.sum((x @ coefficients - y) ** 2))
        candidate = (residual_sse, tuple(float(value) for value in coefficients))
        if best is None or candidate < best:
            best = candidate
    if best is None:
        raise RuntimeError("non-negative localization fit failed")
    coefficients = best[1]
    return {
        "schema_version": 1,
        "method": "development_nonnegative_affine_rayleigh_localization_v1",
        "fit_sequence": fit_sequence_id,
        "fit_rows": len(calibration_rows),
        "diagnostic_fields": list(LOCALIZATION_DIAGNOSTIC_FIELDS),
        "coefficients": {
            "intercept_px": coefficients[0],
            "median_proposal_distance_weight": coefficients[1],
            "candidate_degree_weight": coefficients[2],
        },
        "rayleigh_mean_factor": math.sqrt(math.pi / 2.0),
        "training_residual_sse": best[0],
    }


def _validate_localization_model(model: dict) -> None:
    if not isinstance(model, dict) or model.get("schema_version") != 1:
        raise ValueError("localization model schema_version must be 1")
    if model.get("method") != "development_nonnegative_affine_rayleigh_localization_v1":
        raise ValueError("unsupported localization model")
    coefficients = model.get("coefficients")
    if not isinstance(coefficients, dict):
        raise ValueError("localization model coefficients are required")
    for name in ("intercept_px", "median_proposal_distance_weight", "candidate_degree_weight"):
        value = _finite(coefficients.get(name), name)
        if value < 0:
            raise ValueError(f"{name} must be non-negative")


def localization_sigma(model: dict, diagnostics: dict, *, max_sigma_px: float = 32.0) -> float:
    """Calculate sigma from diagnostics only; no truth fields are accepted."""
    _validate_localization_model(model)
    max_sigma_px = _finite(max_sigma_px, "max_sigma_px")
    if max_sigma_px <= 0:
        raise ValueError("max_sigma_px must be > 0")
    distance = _finite(diagnostics.get("median_proposal_distance_px"), "median_proposal_distance_px")
    degree = _finite(diagnostics.get("candidate_degree"), "candidate_degree")
    if distance < 0 or degree < 0:
        raise ValueError("localization diagnostics must be non-negative")
    coefficients = model["coefficients"]
    value = (
        coefficients["intercept_px"]
        + coefficients["median_proposal_distance_weight"] * distance
        + coefficients["candidate_degree_weight"] * degree
    )
    return min(max(float(value), 0.0), max_sigma_px)


def _observation_rows(observations: list[dict]) -> dict[str, dict]:
    indexed = {}
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            raise ValueError(f"observation {index} must be an object")
        required = ("observation_id", "frame", "x_px", "y_px")
        missing = [key for key in required if key not in row]
        if missing:
            raise ValueError(f"observation {index} missing: {', '.join(missing)}")
        observation_id = row["observation_id"]
        frame = row["frame"]
        if not isinstance(observation_id, str) or not observation_id:
            raise ValueError(f"observation {index} has invalid observation_id")
        if observation_id in indexed:
            raise ValueError(f"duplicate observation_id {observation_id!r}")
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError(f"observation {observation_id!r} has invalid frame")
        _finite(row["x_px"], "x_px")
        _finite(row["y_px"], "y_px")
        indexed[observation_id] = row
    return indexed


def _contains_truth_fields(value) -> bool:
    """Detect forbidden reference-bearing keys recursively in an artifact."""
    if isinstance(value, dict):
        if any(key in TRUTH_KEYS for key in value):
            return True
        return any(_contains_truth_fields(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_truth_fields(item) for item in value)
    return False


def localization_diagnostics(observations: list[dict], candidate_edges: list[dict]) -> dict[str, dict]:
    """Return per-observation graph diagnostics without copying truth fields."""
    by_id = _observation_rows(observations)
    scores = defaultdict(list)
    for index, edge in enumerate(candidate_edges):
        if not isinstance(edge, dict):
            raise ValueError(f"candidate edge {index} must be an object")
        source_id = edge.get("from_observation_id")
        target_id = edge.get("to_observation_id")
        if source_id not in by_id or target_id not in by_id:
            raise ValueError("candidate edge references unknown observation")
        score = _finite(edge.get("proposal_score_px"), "proposal_score_px")
        if score < 0:
            raise ValueError("proposal_score_px must be non-negative")
        scores[source_id].append(score)
        scores[target_id].append(score)
    diagnostics = {}
    for observation_id in sorted(by_id):
        values = scores[observation_id]
        diagnostics[observation_id] = {
            "median_proposal_distance_px": float(np.median(values)) if values else 0.0,
            "candidate_degree": len(values),
        }
    return diagnostics


def perturb_localization(
        observations: list[dict], diagnostics: dict[str, dict], localization_model: dict,
        *, seed: int, max_sigma_px: float = 32.0) -> tuple[list[dict], dict]:
    """Draw truth-blind coordinate perturbations with deterministic Gaussian noise."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    by_id = _observation_rows(observations)
    if set(diagnostics) != set(by_id):
        raise ValueError("localization diagnostics IDs do not match observations")
    rng = random.Random(seed)
    perturbed, sigmas = [], []
    for observation_id in sorted(by_id, key=lambda key: (by_id[key]["frame"], key)):
        row = by_id[observation_id]
        sigma = localization_sigma(localization_model, diagnostics[observation_id], max_sigma_px=max_sigma_px)
        sigmas.append(sigma)
        copied = {
            key: value for key, value in row.items()
            if key not in TRUTH_KEYS and key not in {"x_px", "y_px"}
        }
        copied.update({
            "observation_id": observation_id,
            "frame": row["frame"],
            "x_px": float(row["x_px"]) + rng.gauss(0.0, sigma),
            "y_px": float(row["y_px"]) + rng.gauss(0.0, sigma),
            "localization_sigma_px": sigma,
        })
        perturbed.append(copied)
    return perturbed, {
        "seed": seed,
        "observation_count": len(perturbed),
        "sigma_min_px": min(sigmas, default=0.0),
        "sigma_median_px": float(np.median(sigmas)) if sigmas else 0.0,
        "sigma_max_px": max(sigmas, default=0.0),
        "truth_blind": True,
    }


def _distance(left: dict, right: dict) -> float:
    return math.hypot(float(right["x_px"]) - float(left["x_px"]),
                      float(right["y_px"]) - float(left["y_px"]))


def build_recovery_graph(
        observations: list[dict], primary_graph: dict, *,
        config: StageCV2SamplerConfig | None = None) -> dict:
    """Add truth-blind shell and one-frame-gap proposals around a primary graph."""
    config = config or StageCV2SamplerConfig()
    config.validate()
    by_id = _observation_rows(observations)
    if primary_graph.get("truth_blind") is not True:
        raise ValueError("primary graph must declare truth_blind=true")
    source_gates = {
        row["source_observation_id"]: row for row in primary_graph.get("source_gates", [])
    }
    primary_edges = []
    primary_pairs = set()
    for edge in primary_graph.get("candidate_edges", []):
        source_id = edge["from_observation_id"]
        target_id = edge["to_observation_id"]
        if source_id not in by_id or target_id not in by_id:
            raise ValueError("primary graph references unknown observation")
        if by_id[target_id]["frame"] != by_id[source_id]["frame"] + 1:
            raise ValueError("primary graph contains a non-adjacent edge")
        pair = (source_id, target_id)
        if pair in primary_pairs:
            raise ValueError("primary graph contains duplicate edge")
        primary_pairs.add(pair)
        primary_edges.append({
            **edge,
            "target_frame": by_id[target_id]["frame"],
            "delta_t": 1,
            "proposal_type": "primary",
            "interpolated_observation_id": None,
        })
    by_frame = defaultdict(list)
    for row in by_id.values():
        by_frame[row["frame"]].append(row)
    recovery_edges = []
    for frame in sorted(by_frame):
        sources = sorted(by_frame[frame], key=lambda row: row["observation_id"])
        gate_targets = by_frame.get(frame + 1, [])
        bridge_targets = by_frame.get(frame + config.bridge_delta_t, [])
        for source in sources:
            source_id = source["observation_id"]
            if not gate_targets and not bridge_targets:
                continue
            source_gate = source_gates.get(source_id)
            if source_gate is None:
                # The adaptive generator omits gates when the next frame is
                # empty. A bridge still needs a frozen per-frame bound, so use
                # the primary configuration's declared maximum radius rather
                # than inferring anything from reference identities.
                primary_config = primary_graph.get("config", {})
                fallback_radius = primary_config.get("max_radius_px")
                if fallback_radius is None:
                    raise ValueError(f"primary graph has no source gate for {source_id!r}")
                gate = config.recovery_gate_multiplier * _finite(
                    fallback_radius, "primary max_radius_px"
                )
            else:
                gate = config.recovery_gate_multiplier * float(source_gate["adaptive_radius_px"])
            for target in sorted(gate_targets, key=lambda row: row["observation_id"]):
                target_id = target["observation_id"]
                pair = (source_id, target_id)
                distance = _distance(source, target)
                if pair in primary_pairs or distance > gate:
                    continue
                recovery_edges.append({
                    "from_observation_id": source_id,
                    "to_observation_id": target_id,
                    "source_frame": frame,
                    "target_frame": frame + 1,
                    "delta_t": 1,
                    "distance_px": round(distance, 6),
                    "proposal_score_px": round(distance, 6),
                    "proposal_type": "recovery_adjacent",
                    "interpolated_observation_id": None,
                    "recovery_gate_px": round(gate, 6),
                })
            for target in sorted(bridge_targets, key=lambda row: row["observation_id"]):
                target_id = target["observation_id"]
                distance = _distance(source, target)
                per_frame_score = distance / config.bridge_delta_t
                if per_frame_score > gate:
                    continue
                # A bridge represents a likely missing detection, not a second
                # route through an already observed intermediate detection.
                # Suppress it when any intermediate observation lies inside
                # the same per-frame recovery gate of the linear midpoint.
                midpoint = {
                    "x_px": float(source["x_px"]) + (
                        float(target["x_px"]) - float(source["x_px"])
                    ) / config.bridge_delta_t,
                    "y_px": float(source["y_px"]) + (
                        float(target["y_px"]) - float(source["y_px"])
                    ) / config.bridge_delta_t,
                }
                if any(_distance(midpoint, intermediate) <= gate
                       for intermediate in by_frame.get(frame + 1, [])):
                    continue
                recovery_edges.append({
                    "from_observation_id": source_id,
                    "to_observation_id": target_id,
                    "source_frame": frame,
                    "target_frame": frame + config.bridge_delta_t,
                    "delta_t": config.bridge_delta_t,
                    "distance_px": round(distance, 6),
                    "proposal_score_px": round(per_frame_score, 6),
                    "proposal_type": "recovery_bridge",
                    "interpolated_frame": frame + 1,
                    "interpolated_observation_id": f"bridge:{source_id}:{target_id}",
                    "recovery_gate_px": round(gate, 6),
                })
    all_edges = primary_edges + recovery_edges
    seen = set()
    for edge in all_edges:
        pair = (edge["from_observation_id"], edge["to_observation_id"])
        if pair in seen:
            raise ValueError(f"duplicate predictive edge {pair!r}")
        seen.add(pair)
    all_edges.sort(key=lambda edge: (
        edge["source_frame"], edge["target_frame"], edge["from_observation_id"],
        edge["to_observation_id"], edge["proposal_type"],
    ))
    counts = defaultdict(int)
    for edge in all_edges:
        counts[edge["proposal_type"]] += 1
    return {
        "schema_version": 1,
        "method": "stage_c_v2_primary_plus_recovery_graph_v1",
        "truth_blind": True,
        "config": asdict(config),
        "primary_edge_count": counts["primary"],
        "recovery_adjacent_edge_count": counts["recovery_adjacent"],
        "recovery_bridge_edge_count": counts["recovery_bridge"],
        "recovery_edge_count": counts["recovery_adjacent"] + counts["recovery_bridge"],
        "candidate_edges": all_edges,
    }


def _predictive_components(by_id: dict[str, dict], edges: list[dict]) -> list[tuple[list[str], list[str], list[dict]]]:
    adjacency = defaultdict(set)
    for edge in edges:
        source_id, target_id = edge["from_observation_id"], edge["to_observation_id"]
        adjacency[("source", source_id)].add(("target", target_id))
        adjacency[("target", target_id)].add(("source", source_id))
    seen, components = set(), []
    nodes = [("source", edge["from_observation_id"]) for edge in edges]
    nodes += [("target", edge["to_observation_id"]) for edge in edges]
    for node in sorted(set(nodes)):
        if node in seen:
            continue
        seen.add(node)
        queue = deque([node])
        sources, targets = set(), set()
        while queue:
            kind, observation_id = queue.popleft()
            (sources if kind == "source" else targets).add(observation_id)
            for neighbor in adjacency[(kind, observation_id)]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        source_set, target_set = sorted(sources), sorted(targets)
        edge_set = [
            edge for edge in edges
            if edge["from_observation_id"] in sources and edge["to_observation_id"] in targets
        ]
        components.append((source_set, target_set, edge_set))
    return components


def _matching_states(source_ids: list[str], target_ids: list[str], edges: list[dict],
                     temperature_px: float, new_track_score_px: float) -> dict:
    if len(target_ids) > MAX_EXACT_COMPONENT_TARGETS:
        raise ValueError(
            f"exact predictive component has {len(target_ids)} targets; approved limit is "
            f"{MAX_EXACT_COMPONENT_TARGETS}"
        )
    incoming = defaultdict(list)
    for edge in edges:
        incoming[edge["to_observation_id"]].append(
            (edge["from_observation_id"], math.exp(-edge["proposal_score_px"] / temperature_px))
        )
    birth_weight = math.exp(-new_track_score_px / temperature_px)
    states = []

    def visit(index: int, used_sources: set[str], links: list[tuple[str, str]], weight: float):
        if index == len(target_ids):
            states.append({"links": tuple(links), "weight": weight})
            return
        target_id = target_ids[index]
        visit(index + 1, used_sources, links, weight * birth_weight)
        for source_id, link_weight in sorted(incoming[target_id]):
            if source_id in used_sources:
                continue
            used_sources.add(source_id)
            links.append((source_id, target_id))
            visit(index + 1, used_sources, links, weight * link_weight)
            links.pop()
            used_sources.remove(source_id)

    visit(0, set(), [], 1.0)
    partition = sum(state["weight"] for state in states)
    if not states or not math.isfinite(partition) or partition <= 0:
        raise RuntimeError("predictive matching partition function is not finite and positive")
    return {"partition_function": partition, "states": states}


def sample_exact_predictive_matchings(
        observations: list[dict], candidate_edges: list[dict], *, count: int = 256,
        seed: int = 20260919, temperature_px: float = 4.0,
        new_track_score_px: float = 10.0) -> dict:
    """Sample exact globally compatible primary/recovery matching states."""
    by_id = _observation_rows(observations)
    if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
        raise ValueError("count must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    temperature_px = _finite(temperature_px, "temperature_px")
    new_track_score_px = _finite(new_track_score_px, "new_track_score_px")
    if temperature_px <= 0 or new_track_score_px <= 0:
        raise ValueError("temperature_px and new_track_score_px must be > 0")
    indexed_edges = []
    pair_set = set()
    for index, edge in enumerate(candidate_edges):
        if not isinstance(edge, dict):
            raise ValueError(f"candidate edge {index} must be an object")
        source_id, target_id = edge.get("from_observation_id"), edge.get("to_observation_id")
        if source_id not in by_id or target_id not in by_id:
            raise ValueError("predictive edge references unknown observation")
        pair = (source_id, target_id)
        if pair in pair_set:
            raise ValueError(f"duplicate predictive edge {pair!r}")
        pair_set.add(pair)
        source_frame, target_frame = by_id[source_id]["frame"], by_id[target_id]["frame"]
        delta_t = target_frame - source_frame
        if delta_t not in (1, 2):
            raise ValueError("predictive edges must have delta_t 1 or 2")
        if int(edge.get("delta_t", delta_t)) != delta_t:
            raise ValueError("predictive edge delta_t disagrees with observation frames")
        score = _finite(edge.get("proposal_score_px"), "proposal_score_px")
        if score < 0:
            raise ValueError("proposal_score_px must be non-negative")
        proposal_type = edge.get("proposal_type")
        if proposal_type not in {"primary", "recovery_adjacent", "recovery_bridge"}:
            raise ValueError("unknown predictive proposal_type")
        if delta_t == 2 and proposal_type != "recovery_bridge":
            raise ValueError("delta_t=2 edges must be recovery bridges")
        if delta_t == 1 and proposal_type == "recovery_bridge":
            raise ValueError("recovery bridge must have delta_t=2")
        if proposal_type == "recovery_bridge":
            expected_virtual = f"bridge:{source_id}:{target_id}"
            if edge.get("interpolated_frame") != source_frame + 1:
                raise ValueError("recovery bridge has invalid interpolated frame")
            if edge.get("interpolated_observation_id") != expected_virtual:
                raise ValueError("recovery bridge has invalid virtual observation ID")
        indexed_edges.append({**edge, "delta_t": delta_t, "proposal_score_px": score})
    components = []
    for source_ids, target_ids, edges in _predictive_components(by_id, indexed_edges):
        model = _matching_states(source_ids, target_ids, edges, temperature_px, new_track_score_px)
        components.append({
            "source_observation_ids": source_ids,
            "target_observation_ids": target_ids,
            "candidate_edge_count": len(edges),
            "proposal_type_counts": {
                proposal_type: sum(edge["proposal_type"] == proposal_type for edge in edges)
                for proposal_type in ("primary", "recovery_adjacent", "recovery_bridge")
            },
            "maximum_component_targets": len(target_ids),
            "partition_function": model["partition_function"],
            "states": model["states"],
        })
    edge_types = {pair: edge["proposal_type"] for pair, edge in (
        ((edge["from_observation_id"], edge["to_observation_id"]), edge)
        for edge in indexed_edges
    )}
    observation_ids = sorted(by_id)
    samples = []
    violations = {"one_to_one": [], "trajectory_partition": [], "graph": [], "bridge_virtual": []}
    for sample_index in range(count):
        rng = random.Random(seed + sample_index)
        links = []
        for component in components:
            point = rng.random() * component["partition_function"]
            chosen = component["states"][-1]
            for state in component["states"]:
                point -= state["weight"]
                if point <= 0:
                    chosen = state
                    break
            links.extend(chosen["links"])
        links = sorted(links)
        trajectories, trajectory_invariants = trajectories_from_links(observation_ids, links)
        if not trajectory_invariants["one_to_one_pass"]:
            violations["one_to_one"].append(sample_index)
        if not trajectory_invariants["trajectory_partition_pass"]:
            violations["trajectory_partition"].append(sample_index)
        if any(pair not in edge_types for pair in links):
            violations["graph"].append(sample_index)
        virtual_ids = [
            f"bridge:{source_id}:{target_id}" for source_id, target_id in links
            if edge_types.get((source_id, target_id)) == "recovery_bridge"
        ]
        if len(virtual_ids) != len(set(virtual_ids)):
            violations["bridge_virtual"].append(sample_index)
        samples.append({
            "sample_index": sample_index,
            "links": [
                {
                    "from_observation_id": source_id,
                    "to_observation_id": target_id,
                    "proposal_type": edge_types[(source_id, target_id)],
                    "delta_t": by_id[target_id]["frame"] - by_id[source_id]["frame"],
                }
                for source_id, target_id in links
            ],
            "trajectories": trajectories,
            "trajectory_count": len(trajectories),
            "link_count": len(links),
        })
    return {
        "schema_version": 1,
        "method": "stage_c_v2_exact_predictive_matching_v1",
        "sample_count": count,
        "seed": seed,
        "temperature_px": temperature_px,
        "new_track_score_px": new_track_score_px,
        "max_exact_component_targets": MAX_EXACT_COMPONENT_TARGETS,
        "components": [
            {key: value for key, value in component.items() if key != "states"}
            for component in components
        ],
        "samples": samples,
        "invariants": {
            "one_to_one_pass": not violations["one_to_one"],
            "trajectory_partition_pass": not violations["trajectory_partition"],
            "candidate_graph_pass": not violations["graph"],
            "bridge_virtual_node_pass": not violations["bridge_virtual"],
            "one_to_one_violation_sample_indices": violations["one_to_one"],
            "trajectory_partition_violation_sample_indices": violations["trajectory_partition"],
            "candidate_graph_violation_sample_indices": violations["graph"],
            "bridge_virtual_node_violation_sample_indices": violations["bridge_virtual"],
        },
    }


def sample_stage_c_v2_ensemble(
        observations: list[dict], *, primary_config: AdaptiveCandidateConfig,
        localization_model: dict, sampler_config: StageCV2SamplerConfig | None = None,
        seed: int = 20260919) -> dict:
    """Generate a predictive ensemble; only observations and graph diagnostics enter it."""
    sampler_config = sampler_config or StageCV2SamplerConfig()
    sampler_config.validate()
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    clean_observations = []
    for row in observations:
        clean_observations.append({
            key: value for key, value in row.items() if key not in TRUTH_KEYS
        })
    primary = generate_adaptive_candidate_graph(clean_observations, primary_config)
    diagnostics = localization_diagnostics(clean_observations, primary["candidate_edges"])
    samples = []
    for sample_index in range(sampler_config.ensemble_count):
        localized, localization = perturb_localization(
            clean_observations, diagnostics, localization_model,
            seed=seed + sample_index, max_sigma_px=sampler_config.max_localization_sigma_px,
        )
        localized_primary = generate_adaptive_candidate_graph(localized, primary_config)
        graph = build_recovery_graph(localized, localized_primary, config=sampler_config)
        predictive = sample_exact_predictive_matchings(
            localized, graph["candidate_edges"], count=1, seed=seed + sample_index,
            temperature_px=sampler_config.temperature_px,
            new_track_score_px=sampler_config.new_track_score_px,
        )
        realization = predictive["samples"][0]
        samples.append({
            "sample_index": sample_index,
            "observations": localized,
            "localization": localization,
            "graph": {
                key: graph[key] for key in (
                    "primary_edge_count", "recovery_adjacent_edge_count",
                    "recovery_bridge_edge_count", "recovery_edge_count",
                )
            },
            "links": realization["links"],
            "trajectories": realization["trajectories"],
            "invariants": predictive["invariants"],
            "component_count": len(predictive["components"]),
            "maximum_component_targets": max(
                (component["maximum_component_targets"] for component in predictive["components"]),
                default=0,
            ),
        })
    return {
        "schema_version": 1,
        "method": "stage_c_v2_localization_recovery_predictive_ensemble_v1",
        "truth_blind": True,
        "seed": seed,
        "ensemble_count": sampler_config.ensemble_count,
        "primary_config": asdict(primary_config),
        "sampler_config": asdict(sampler_config),
        "localization_model": localization_model,
        "base_diagnostics": diagnostics,
        "samples": samples,
        "invariants": {
            "sample_count_pass": len(samples) == sampler_config.ensemble_count,
            "truth_blind_pass": not _contains_truth_fields(samples),
            "one_to_one_pass": all(
                sample["invariants"]["one_to_one_pass"] for sample in samples
            ),
            "trajectory_partition_pass": all(
                sample["invariants"]["trajectory_partition_pass"] for sample in samples
            ),
            "candidate_graph_pass": all(
                sample["invariants"]["candidate_graph_pass"] for sample in samples
            ),
            "bridge_virtual_node_pass": all(
                sample["invariants"]["bridge_virtual_node_pass"] for sample in samples
            ),
            "exact_resource_bound_pass": all(
                sample["maximum_component_targets"] <= MAX_EXACT_COMPONENT_TARGETS
                for sample in samples
            ),
        },
    }

