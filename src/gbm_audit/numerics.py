"""Shared numerical helpers used by hard and soft dynamics evaluators."""

import math

import numpy as np


def gaussian_emission(values: np.ndarray, means: np.ndarray, stds: np.ndarray) -> np.ndarray:
    """Return numerically floored Gaussian emission densities for each state."""
    output = np.empty((len(values), len(means)), dtype=float)
    for state in range(len(means)):
        variance = max(float(stds[state]) ** 2, 1e-6)
        output[:, state] = np.exp(-0.5 * (values - means[state]) ** 2 / variance) / math.sqrt(
            2 * math.pi * variance
        )
    return np.maximum(output, 1e-300)


def normalize_transition_rows(candidate: np.ndarray, fallback: np.ndarray) -> np.ndarray:
    """Normalize transition rows, preserving a valid fallback when evidence is absent."""
    if candidate.shape != fallback.shape or candidate.ndim != 2:
        raise ValueError("candidate and fallback transition matrices must have matching 2D shapes")
    normalized = np.empty_like(candidate, dtype=float)
    for row_index in range(candidate.shape[0]):
        total = float(candidate[row_index].sum())
        if math.isfinite(total) and total > 0:
            normalized[row_index] = candidate[row_index] / total
            continue
        fallback_total = float(fallback[row_index].sum())
        if math.isfinite(fallback_total) and fallback_total > 0:
            normalized[row_index] = fallback[row_index] / fallback_total
        else:
            normalized[row_index] = np.full(candidate.shape[1], 1.0 / candidate.shape[1])
    return normalized


def stationary_distribution(transition: np.ndarray) -> np.ndarray:
    """Return a normalized stationary distribution for a square transition matrix."""
    if transition.ndim != 2 or transition.shape[0] != transition.shape[1] or transition.shape[0] == 0:
        raise ValueError("transition matrix must be non-empty and square")
    if not np.all(np.isfinite(transition)):
        raise ValueError("transition matrix must be finite")
    if not np.allclose(transition.sum(axis=1), 1.0, atol=1e-9):
        raise ValueError("transition matrix must be row-stochastic")
    values, vectors = np.linalg.eig(transition.T)
    vector = vectors[:, np.argmin(abs(values - 1))].real
    vector = np.abs(vector)
    total = float(vector.sum())
    if not math.isfinite(total) or total <= 0:
        return np.full(transition.shape[0], 1.0 / transition.shape[0])
    return vector / total
