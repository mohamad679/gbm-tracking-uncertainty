"""Public calibration helpers shared by uncertainty consumers."""

import math


def temperature_transform(probability: float, temperature: float) -> float:
    """Apply binary-logit temperature scaling to a probability."""
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be finite and in [0, 1]")
    if not math.isfinite(temperature) or temperature <= 0:
        raise ValueError("temperature must be finite and > 0")
    epsilon = 1e-6
    clipped = min(max(probability, epsilon), 1 - epsilon)
    logit = math.log(clipped / (1 - clipped))
    return 1 / (1 + math.exp(-logit / temperature))
