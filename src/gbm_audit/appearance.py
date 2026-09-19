"""Small, deterministic image-patch descriptors for truth-blind proposals."""

from io import BytesIO
from zipfile import ZipFile

import numpy as np
from PIL import Image

from gbm_audit.archive import read_member_bytes


_DESCRIPTOR_LENGTH = 28


def load_frames(archive: ZipFile, image_paths: list[str]) -> dict[int, np.ndarray]:
    """Decode the indexed image frames needed by one U373 sequence."""
    frames = {}
    for frame, path in enumerate(image_paths):
        with Image.open(BytesIO(read_member_bytes(archive, path))) as image:
            frames[frame] = np.asarray(image.convert("L"), dtype=np.float32) / 255.0
    return frames


def patch_descriptor(image: np.ndarray, x_px: float, y_px: float, radius: int = 6) -> list[float]:
    """Return a fixed-length local standardized 5x5 intensity/texture descriptor."""
    if image.ndim != 2:
        raise ValueError("patch_descriptor expects a 2D grayscale image")
    if radius < 0:
        raise ValueError("radius must be non-negative")
    if not np.isfinite(x_px) or not np.isfinite(y_px):
        raise ValueError("descriptor coordinates must be finite")

    height, width = image.shape
    x = int(round(x_px))
    y = int(round(y_px))
    x0, x1 = max(0, x - radius), min(width, x + radius + 1)
    y0, y1 = max(0, y - radius), min(height, y + radius + 1)
    patch = image[y0:y1, x0:x1]
    if patch.size == 0:
        return [0.0] * _DESCRIPTOR_LENGTH
    mean = float(patch.mean())
    std = max(float(patch.std()), 1e-4)
    normalized = (patch - mean) / std
    ys = np.linspace(0, normalized.shape[0] - 1, 5).round().astype(int)
    xs = np.linspace(0, normalized.shape[1] - 1, 5).round().astype(int)
    coarse = normalized[np.ix_(ys, xs)].reshape(-1)
    gy, gx = np.gradient(normalized)
    gradient = float(np.hypot(gx, gy).mean())
    descriptor = [round(float(value), 6) for value in coarse] + [
        round(mean, 6), round(std, 6), round(gradient, 6)
    ]
    if len(descriptor) != _DESCRIPTOR_LENGTH:
        raise RuntimeError(f"unexpected appearance descriptor length: {len(descriptor)}")
    return descriptor


def add_descriptors(observations: list[dict], frames: dict[int, np.ndarray], radius: int = 6) -> list[dict]:
    """Copy observations and add descriptors from their frame-local patches."""
    enriched = []
    for row in observations:
        descriptor = patch_descriptor(frames[int(row["frame"])], row["x_px"], row["y_px"], radius)
        enriched.append({**row, "appearance_descriptor": descriptor})
    return enriched
