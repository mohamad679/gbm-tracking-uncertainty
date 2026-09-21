"""Stage D operator candidates and frozen transition baselines.

This module defines the models used by the later Stage D development fit.  It
does not load a dataset or choose a model.  All fitting APIs require explicit
sequence provenance and reject the already-consumed locked-test sources.
"""

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np


FORBIDDEN_SEQUENCE_IDS = frozenset({
    "02", "T98G_sample", "T98G_electrotaxis_human_v2",
})
TRUTH_KEYS = frozenset({
    "evaluation_truth", "true_track_id", "observed_track_id", "reference_track_id",
    "truth", "parent_id", "start_frame", "end_frame",
})


def _contains_forbidden_truth(value) -> bool:
    if isinstance(value, dict):
        if any(key in TRUTH_KEYS for key in value):
            return True
        return any(_contains_forbidden_truth(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_forbidden_truth(item) for item in value)
    return False


def _vector(value, name: str) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    if array.ndim != 1 or array.size == 0:
        raise ValueError(f"{name} must be a non-empty one-dimensional vector")
    if not np.all(np.isfinite(array)):
        raise ValueError(f"{name} must contain only finite values")
    return array


def validate_transition_rows(
        rows: Iterable[dict], *, allowed_sequence_ids: tuple[str, ...] = ("01",),
) -> list[dict]:
    """Validate truth-blind state transitions for development fitting only."""
    if not isinstance(allowed_sequence_ids, tuple) or not allowed_sequence_ids:
        raise ValueError("allowed_sequence_ids must be a non-empty tuple")
    normalized = []
    dimension = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"transition row {index} must be an object")
        if _contains_forbidden_truth(row):
            raise ValueError(f"transition row {index} contains reference/truth fields")
        sequence_id = row.get("sequence_id")
        if sequence_id in FORBIDDEN_SEQUENCE_IDS:
            raise ValueError(f"sequence {sequence_id!r} is forbidden for Stage D fitting")
        if sequence_id not in allowed_sequence_ids:
            raise ValueError(f"sequence {sequence_id!r} is outside the allowed development set")
        state = _vector(row.get("state"), "state")
        next_state = _vector(row.get("next_state"), "next_state")
        if state.shape != next_state.shape:
            raise ValueError(f"transition row {index} state dimensions disagree")
        if dimension is None:
            dimension = state.size
        elif state.size != dimension:
            raise ValueError("all transition rows must have the same state dimension")
        weight = float(row.get("uncertainty_weight", 1.0))
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("uncertainty_weight must be finite and > 0")
        normalized.append({
            "sequence_id": sequence_id,
            "state": state,
            "next_state": next_state,
            "uncertainty_weight": weight,
        })
    if not normalized:
        raise ValueError("at least one transition row is required")
    return normalized


@dataclass(frozen=True)
class StageDOperatorConfig:
    """Frozen numerical controls for Step 2 candidate operators."""

    ridge: float = 1e-6
    max_spectral_radius: float = 0.98
    forecast_horizon: int = 10

    def validate(self) -> None:
        if not math.isfinite(float(self.ridge)) or self.ridge < 0:
            raise ValueError("ridge must be finite and >= 0")
        if not math.isfinite(float(self.max_spectral_radius)) or not 0 < self.max_spectral_radius <= 1:
            raise ValueError("max_spectral_radius must be in (0, 1]")
        if isinstance(self.forecast_horizon, bool) or not isinstance(self.forecast_horizon, int):
            raise ValueError("forecast_horizon must be a positive integer")
        if self.forecast_horizon <= 0:
            raise ValueError("forecast_horizon must be a positive integer")


@dataclass(frozen=True)
class FrozenHMMSpeedBaseline:
    """Predictive speed baseline using the already-frozen Stage C HMM."""

    model: dict
    name: str = "frozen_hmm_speed_baseline_v1"

    def _validated_arrays(self):
        if not isinstance(self.model, dict) or self.model.get("status") != "ok":
            raise ValueError("frozen HMM must have status=ok")
        means = np.asarray(self.model.get("state_means_px_per_frame"), dtype=float)
        stds = np.asarray(self.model.get("state_stds_px_per_frame"), dtype=float)
        transition = np.asarray(self.model.get("transition_matrix"), dtype=float)
        initial = np.asarray(self.model.get("initial_state_probability"), dtype=float)
        if means.ndim != 1 or stds.shape != means.shape:
            raise ValueError("HMM state means/stds have incompatible shapes")
        if transition.shape != (means.size, means.size) or initial.shape != means.shape:
            raise ValueError("HMM transition/initial arrays have incompatible shapes")
        if not all(np.all(np.isfinite(array)) for array in (means, stds, transition, initial)):
            raise ValueError("HMM arrays must be finite")
        if np.any(stds < 0) or np.any(transition < 0) or np.any(initial < 0):
            raise ValueError("HMM probabilities and standard deviations must be non-negative")
        return means, stds, transition, initial

    def predict_speed(self, state_probability: Iterable[float] | None = None) -> dict:
        means, stds, transition, initial = self._validated_arrays()
        probabilities = initial if state_probability is None else np.asarray(state_probability, dtype=float)
        if probabilities.shape != initial.shape or not np.all(np.isfinite(probabilities)):
            raise ValueError("state_probability has the wrong shape or non-finite values")
        if np.any(probabilities < 0) or float(np.sum(probabilities)) <= 0:
            raise ValueError("state_probability must be non-negative with positive mass")
        probabilities = probabilities / np.sum(probabilities)
        next_probability = probabilities @ transition
        next_probability = next_probability / np.sum(next_probability)
        mean = float(next_probability @ means)
        variance = float(next_probability @ (stds ** 2 + (means - mean) ** 2))
        return {
            "baseline": self.name,
            "expected_speed_px_per_frame": mean,
            "std_speed_px_per_frame": math.sqrt(max(variance, 0.0)),
            "state_probability": [float(value) for value in next_probability],
        }


@dataclass(frozen=True)
class WeightedEmpiricalTransitionBaseline:
    """Weighted persistence-plus-drift baseline for uncertainty-aware states."""

    mean_delta: tuple[float, ...]
    covariance: tuple[tuple[float, ...], ...]
    fit_sequence_id: str
    row_count: int
    name: str = "weighted_empirical_transition_baseline_v1"

    @classmethod
    def fit(cls, rows: Iterable[dict], *, fit_sequence_id: str = "01"):
        if fit_sequence_id in FORBIDDEN_SEQUENCE_IDS:
            raise ValueError("fit_sequence_id is a forbidden locked-test source")
        validated = validate_transition_rows(rows, allowed_sequence_ids=(fit_sequence_id,))
        states = np.asarray([row["state"] for row in validated])
        deltas = np.asarray([row["next_state"] - row["state"] for row in validated])
        weights = np.asarray([row["uncertainty_weight"] for row in validated])
        mean = np.average(deltas, axis=0, weights=weights)
        centered = deltas - mean
        covariance = (centered * weights[:, None]).T @ centered / float(np.sum(weights))
        return cls(
            mean_delta=tuple(float(value) for value in mean),
            covariance=tuple(tuple(float(value) for value in row) for row in covariance),
            fit_sequence_id=fit_sequence_id,
            row_count=len(validated),
        )

    def predict(self, state: Iterable[float]) -> np.ndarray:
        value = _vector(state, "state")
        delta = np.asarray(self.mean_delta, dtype=float)
        if value.shape != delta.shape:
            raise ValueError("state dimension disagrees with fitted baseline")
        return value + delta

    def rollout(self, state: Iterable[float], horizon: int) -> np.ndarray:
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
            raise ValueError("horizon must be a positive integer")
        current = _vector(state, "state")
        values = [current.copy()]
        for _ in range(horizon):
            current = self.predict(current)
            values.append(current.copy())
        return np.asarray(values)


@dataclass(frozen=True)
class StableLinearKoopmanOperator:
    """Affine linear operator with an explicit spectral-radius constraint."""

    matrix: tuple[tuple[float, ...], ...]
    offset: tuple[float, ...]
    pre_constraint_spectral_radius: float
    spectral_radius: float
    fit_sequence_id: str
    row_count: int
    config: StageDOperatorConfig
    name: str = "stable_linear_koopman_operator_v1"

    @classmethod
    def fit(cls, rows: Iterable[dict], *, fit_sequence_id: str = "01",
            config: StageDOperatorConfig | None = None):
        if fit_sequence_id in FORBIDDEN_SEQUENCE_IDS:
            raise ValueError("fit_sequence_id is a forbidden locked-test source")
        config = config or StageDOperatorConfig()
        config.validate()
        validated = validate_transition_rows(rows, allowed_sequence_ids=(fit_sequence_id,))
        states = np.asarray([row["state"] for row in validated])
        next_states = np.asarray([row["next_state"] for row in validated])
        weights = np.sqrt(np.asarray([row["uncertainty_weight"] for row in validated]))
        design = np.column_stack([states, np.ones(len(states))])
        regularizer = np.eye(design.shape[1]) * float(config.ridge)
        regularizer[-1, -1] = 0.0
        weighted_design = design * weights[:, None]
        weighted_targets = next_states * weights[:, None]
        coefficients = np.linalg.solve(
            weighted_design.T @ weighted_design + regularizer,
            weighted_design.T @ weighted_targets,
        )
        matrix = coefficients[:-1].T
        offset = coefficients[-1]
        eigenvalues = np.linalg.eigvals(matrix)
        pre_radius = float(np.max(np.abs(eigenvalues))) if eigenvalues.size else 0.0
        if not math.isfinite(pre_radius):
            raise ValueError("unconstrained operator has a non-finite spectral radius")
        if pre_radius > config.max_spectral_radius:
            matrix = matrix * (config.max_spectral_radius / pre_radius)
        post_radius = float(np.max(np.abs(np.linalg.eigvals(matrix)))) if matrix.size else 0.0
        return cls(
            matrix=tuple(tuple(float(value) for value in row) for row in matrix),
            offset=tuple(float(value) for value in offset),
            pre_constraint_spectral_radius=pre_radius,
            spectral_radius=post_radius,
            fit_sequence_id=fit_sequence_id,
            row_count=len(validated),
            config=config,
        )

    def predict(self, state: Iterable[float]) -> np.ndarray:
        value = _vector(state, "state")
        matrix = np.asarray(self.matrix, dtype=float)
        offset = np.asarray(self.offset, dtype=float)
        if matrix.shape != (value.size, value.size) or offset.shape != value.shape:
            raise ValueError("state dimension disagrees with fitted operator")
        result = matrix @ value + offset
        if not np.all(np.isfinite(result)):
            raise FloatingPointError("operator prediction is non-finite")
        return result

    def rollout(self, state: Iterable[float], horizon: int | None = None) -> np.ndarray:
        horizon = self.config.forecast_horizon if horizon is None else horizon
        if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
            raise ValueError("horizon must be a positive integer")
        current = _vector(state, "state")
        values = [current.copy()]
        for _ in range(horizon):
            current = self.predict(current)
            values.append(current.copy())
        return np.asarray(values)

    def stability_report(self) -> dict:
        matrix = np.asarray(self.matrix, dtype=float)
        eigenvalues = np.linalg.eigvals(matrix)
        radius = float(np.max(np.abs(eigenvalues))) if eigenvalues.size else 0.0
        return {
            "operator": self.name,
            "finite_matrix": bool(np.all(np.isfinite(matrix))),
            "spectral_radius": radius,
            "max_spectral_radius": self.config.max_spectral_radius,
            "stability_pass": bool(math.isfinite(radius) and radius <= self.config.max_spectral_radius + 1e-10),
        }


def candidate_registry() -> dict[str, str]:
    """Return the Step 2 candidate registry without fitting any model."""
    return {
        "frozen_hmm_speed_baseline_v1": "Frozen Stage C HMM speed prediction",
        "weighted_empirical_transition_baseline_v1": "Uncertainty-weighted persistence plus drift",
        "stable_linear_koopman_operator_v1": "Affine linear operator with constrained spectral radius",
    }
