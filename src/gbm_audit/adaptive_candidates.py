"""Generate deterministic, truth-blind adaptive candidate graphs.

Version 1 uses narrow-gate seed histories, constant-velocity prediction,
motion uncertainty and local source density.  It intentionally does not read
reference identities or evaluate scientific performance; those responsibilities
belong to the Stage A benchmark and later integration steps.
"""

from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class AdaptiveCandidateConfig:
    """Configuration exposed for development-sequence tuning in a later step."""

    min_radius_px: float = 8.0
    max_radius_px: float = 16.0
    motion_uncertainty_weight: float = 1.0
    density_weight_px: float = 4.0
    density_radius_px: float = 16.0
    density_saturation_count: int = 6
    cold_start_uncertainty_px: float = 4.0
    history_length: int = 4

    def validate(self) -> None:
        finite_nonnegative = {
            "min_radius_px": self.min_radius_px,
            "max_radius_px": self.max_radius_px,
            "motion_uncertainty_weight": self.motion_uncertainty_weight,
            "density_weight_px": self.density_weight_px,
            "density_radius_px": self.density_radius_px,
            "cold_start_uncertainty_px": self.cold_start_uncertainty_px,
        }
        for name, value in finite_nonnegative.items():
            if not math.isfinite(value) or value < 0:
                raise ValueError(f"{name} must be finite and >= 0")
        if self.min_radius_px <= 0:
            raise ValueError("min_radius_px must be > 0")
        if self.max_radius_px < self.min_radius_px:
            raise ValueError("max_radius_px must be >= min_radius_px")
        if self.density_radius_px <= 0:
            raise ValueError("density_radius_px must be > 0")
        if (isinstance(self.density_saturation_count, bool)
                or not isinstance(self.density_saturation_count, int)
                or self.density_saturation_count <= 0):
            raise ValueError("density_saturation_count must be a positive integer")
        if (isinstance(self.history_length, bool)
                or not isinstance(self.history_length, int)
                or self.history_length < 3):
            raise ValueError("history_length must be an integer >= 3")


def _distance(left: dict, right: dict) -> float:
    return float(math.hypot(
        float(right["x_px"]) - float(left["x_px"]),
        float(right["y_px"]) - float(left["y_px"]),
    ))


def _validate_observations(observations: list[dict]) -> dict[int, list[dict]]:
    by_frame: dict[int, list[dict]] = {}
    seen_ids = set()
    for index, row in enumerate(observations):
        if not isinstance(row, dict):
            raise ValueError(f"observation {index} must be an object")
        missing = [key for key in ("observation_id", "frame", "x_px", "y_px") if key not in row]
        if missing:
            raise ValueError(f"observation {index} missing required keys: {', '.join(missing)}")
        observation_id = row["observation_id"]
        if not isinstance(observation_id, str) or not observation_id:
            raise ValueError(f"observation {index} has an invalid observation_id")
        if observation_id in seen_ids:
            raise ValueError(f"duplicate observation_id {observation_id!r}")
        seen_ids.add(observation_id)
        frame = row["frame"]
        if isinstance(frame, bool) or not isinstance(frame, int) or frame < 0:
            raise ValueError(f"observation {observation_id!r} has an invalid frame")
        for coordinate in ("x_px", "y_px"):
            try:
                value = float(row[coordinate])
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"observation {observation_id!r} has an invalid {coordinate}"
                ) from exc
            if not math.isfinite(value):
                raise ValueError(f"observation {observation_id!r} has a non-finite {coordinate}")
        by_frame.setdefault(frame, []).append(row)
    for rows in by_frame.values():
        rows.sort(key=lambda row: row["observation_id"])
    return by_frame


def _seed_histories(by_frame: dict[int, list[dict]], config: AdaptiveCandidateConfig) -> dict[str, list[dict]]:
    """Build deterministic past-only tracklets with the conservative base gate."""
    histories: dict[str, list[dict]] = {}
    for frame in sorted(by_frame):
        current = by_frame[frame]
        previous = by_frame.get(frame - 1, [])
        pairs = []
        for left in previous:
            for right in current:
                distance = _distance(left, right)
                if distance <= config.min_radius_px:
                    pairs.append((distance, left["observation_id"], right["observation_id"]))
        used_left, used_right = set(), set()
        predecessor = {}
        for _, left_id, right_id in sorted(pairs):
            if left_id in used_left or right_id in used_right:
                continue
            predecessor[right_id] = left_id
            used_left.add(left_id)
            used_right.add(right_id)
        for row in current:
            observation_id = row["observation_id"]
            left_id = predecessor.get(observation_id)
            if left_id is None:
                history = [row]
            else:
                history = [*histories[left_id], row]
            histories[observation_id] = history[-config.history_length:]
    return histories


def _motion_state(history: list[dict], config: AdaptiveCandidateConfig) -> tuple[float, float, float]:
    current = history[-1]
    current_x, current_y = float(current["x_px"]), float(current["y_px"])
    if len(history) < 2:
        return current_x, current_y, config.cold_start_uncertainty_px
    previous = history[-2]
    velocity_x = current_x - float(previous["x_px"])
    velocity_y = current_y - float(previous["y_px"])
    predicted_x, predicted_y = current_x + velocity_x, current_y + velocity_y
    if len(history) < 3:
        return predicted_x, predicted_y, config.cold_start_uncertainty_px
    velocities = [
        (
            float(right["x_px"]) - float(left["x_px"]),
            float(right["y_px"]) - float(left["y_px"]),
        )
        for left, right in zip(history, history[1:])
    ]
    accelerations = [
        math.hypot(right[0] - left[0], right[1] - left[1])
        for left, right in zip(velocities, velocities[1:])
    ]
    uncertainty = math.sqrt(sum(value * value for value in accelerations) / len(accelerations))
    return predicted_x, predicted_y, uncertainty


def _density_score(source: dict, source_frame: list[dict], config: AdaptiveCandidateConfig) -> tuple[int, float]:
    neighbor_count = sum(
        other["observation_id"] != source["observation_id"]
        and _distance(source, other) <= config.density_radius_px
        for other in source_frame
    )
    return neighbor_count, min(neighbor_count / config.density_saturation_count, 1.0)


def generate_adaptive_candidate_graph(
        observations: list[dict], config: AdaptiveCandidateConfig | None = None) -> dict:
    """Return a deterministic candidate graph without consulting truth fields."""
    config = config or AdaptiveCandidateConfig()
    config.validate()
    by_frame = _validate_observations(observations)
    histories = _seed_histories(by_frame, config)
    candidate_edges = []
    source_gates = []
    for frame in sorted(by_frame):
        sources = by_frame[frame]
        targets = by_frame.get(frame + 1, [])
        if not targets:
            continue
        for source in sources:
            source_id = source["observation_id"]
            history = histories[source_id]
            predicted_x, predicted_y, motion_uncertainty = _motion_state(history, config)
            neighbor_count, density_score = _density_score(source, sources, config)
            radius = min(
                max(
                    config.min_radius_px
                    + config.motion_uncertainty_weight * motion_uncertainty
                    + config.density_weight_px * density_score,
                    config.min_radius_px,
                ),
                config.max_radius_px,
            )
            source_gates.append({
                "source_observation_id": source_id,
                "source_frame": frame,
                "history_length": len(history),
                "predicted_x_px": round(predicted_x, 6),
                "predicted_y_px": round(predicted_y, 6),
                "motion_uncertainty_px": round(motion_uncertainty, 6),
                "local_neighbor_count": neighbor_count,
                "local_density_score": round(density_score, 6),
                "adaptive_radius_px": round(radius, 6),
            })
            for target in targets:
                direct_distance = _distance(source, target)
                predicted_residual = float(math.hypot(
                    float(target["x_px"]) - predicted_x,
                    float(target["y_px"]) - predicted_y,
                ))
                in_base_gate = direct_distance <= config.min_radius_px
                in_adaptive_gate = predicted_residual <= radius
                if not (in_base_gate or in_adaptive_gate):
                    continue
                inclusion = "both" if in_base_gate and in_adaptive_gate else (
                    "base" if in_base_gate else "adaptive"
                )
                candidate_edges.append({
                    "from_observation_id": source_id,
                    "to_observation_id": target["observation_id"],
                    "source_frame": frame,
                    "distance_px": round(direct_distance, 6),
                    "predicted_residual_px": round(predicted_residual, 6),
                    "proposal_score_px": round(min(direct_distance, predicted_residual), 6),
                    "adaptive_radius_px": round(radius, 6),
                    "inclusion": inclusion,
                })
    candidate_edges.sort(key=lambda row: (
        row["source_frame"], row["from_observation_id"], row["to_observation_id"]
    ))
    source_gates.sort(key=lambda row: (row["source_frame"], row["source_observation_id"]))
    first_frame = min(by_frame, default=0)
    target_observations = sum(
        len(rows) for frame, rows in by_frame.items() if frame > first_frame
    )
    return {
        "schema_version": 1,
        "method": "adaptive_motion_uncertainty_density_v1",
        "truth_blind": True,
        "config": asdict(config),
        "observation_count": len(observations),
        "candidate_target_observations": target_observations,
        "candidate_edge_count": len(candidate_edges),
        "candidate_burden_edges_per_target": (
            len(candidate_edges) / target_observations if target_observations else 0.0
        ),
        "source_gates": source_gates,
        "candidate_edges": candidate_edges,
    }
