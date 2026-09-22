"""Dependency-free, deterministic metrics registered for Stage E."""

from __future__ import annotations

import math

import numpy as np


def average_precision(scores: list[float], labels: list[int]) -> float:
    """Compute ranking average precision with stable input-order tie handling."""
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    positives = sum(int(bool(label)) for label in labels)
    if not positives:
        return 0.0
    ordered = sorted(range(len(scores)), key=lambda index: (-float(scores[index]), index))
    true_positive = 0
    total = 0.0
    for rank, index in enumerate(ordered, 1):
        if labels[index]:
            true_positive += 1
            total += true_positive / rank
    return total / positives


def selective_link_risk(scores: list[float], labels: list[int], coverage: float = 0.8) -> dict:
    """Retain the most confident fraction of links and report their error risk."""
    if len(scores) != len(labels):
        raise ValueError("scores and labels must have the same length")
    if not 0 < coverage <= 1:
        raise ValueError("coverage must be in (0, 1]")
    if not scores:
        return {"coverage": coverage, "accepted": 0, "risk": 0.0}
    count = int(math.ceil(coverage * len(scores)))
    ordered = sorted(range(len(scores)), key=lambda index: (-float(scores[index]), index))[:count]
    risk = 1.0 - float(np.mean([int(bool(labels[index])) for index in ordered]))
    return {"coverage": coverage, "accepted": count, "risk": risk}


def probability_metrics(probabilities: list[float], labels: list[int], bins: int = 10) -> dict:
    """Return Brier, ECE and NLL for bounded probability predictions."""
    if len(probabilities) != len(labels):
        raise ValueError("probabilities and labels must have the same length")
    if not probabilities:
        return {"brier": 0.0, "ece": 0.0, "nll": 0.0, "count": 0}
    values = [min(1.0 - 1e-12, max(1e-12, float(value))) for value in probabilities]
    binary = [int(bool(label)) for label in labels]
    brier = float(np.mean([(value - label) ** 2 for value, label in zip(values, binary)]))
    nll = float(-np.mean([
        math.log(value) if label else math.log(1.0 - value)
        for value, label in zip(values, binary)
    ]))
    ece = 0.0
    for index in range(bins):
        lower, upper = index / bins, (index + 1) / bins
        selected = [position for position, value in enumerate(values)
                    if lower <= value < upper or (index == bins - 1 and value == upper)]
        if selected:
            ece += len(selected) / len(values) * abs(
                float(np.mean([values[position] for position in selected]))
                - float(np.mean([binary[position] for position in selected]))
            )
    return {"brier": brier, "ece": float(ece), "nll": nll, "count": len(values)}


def distance_confidence(distances_px: list[float], max_distance_px: float) -> list[float]:
    """Registered monotone distance-derived confidence comparator."""
    if max_distance_px <= 0:
        raise ValueError("max_distance_px must be positive")
    return [max(0.0, min(1.0, 1.0 - float(distance) / max_distance_px)) for distance in distances_px]


def link_score_report(probabilities: list[float], labels: list[int], *, coverage: float = 0.8) -> dict:
    """Report error-ranking, selective-risk and calibration metrics.

    Probabilities represent confidence that a candidate link is correct. The
    registered AUPRC endpoint instead ranks association errors, so it must use
    1 - probability and the inverse truth label. Selective risk and calibration
    deliberately retain the original correct-link orientation.
    """
    error_scores = [1.0 - float(value) for value in probabilities]
    error_labels = [1 - int(bool(label)) for label in labels]
    return {
        "association_error_auprc": average_precision(error_scores, error_labels),
        "selective_link_risk": selective_link_risk(probabilities, labels, coverage),
        "calibration": probability_metrics(probabilities, labels),
    }
