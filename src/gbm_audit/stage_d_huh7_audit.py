"""Audit and lock an independent Huh7 operator-evaluation sequence.

This module is deliberately outcome blind.  It validates archive identity,
CTC schema, image/reference compatibility and the number of structurally
available velocity-transition slots.  It never extracts centroids, computes
motion values, fits a model or exposes an evaluation metric.
"""

import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import re
import sys
from zipfile import BadZipFile, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.archive import read_member_bytes, validate_zip_archive
from gbm_audit.cli import sha256_file


DATASET_ID = "CTC_Fluo-C2DL-Huh7_training_2021-01-14"
ROOT = "Fluo-C2DL-Huh7"
SOURCE_PAGE = "https://celltrackingchallenge.net/2d-datasets/"
ARCHIVE_URL = (
    "https://data.celltrackingchallenge.net/training-datasets/"
    "Fluo-C2DL-Huh7.zip"
)
EXPECTED_ARCHIVE_SIZE = 38_151_145
EXPECTED_ARCHIVE_SHA256 = (
    "1912658c1b3d8b38b314eb658b559e7b39c256917150e9b3dd8bfdc77347617d"
)
PIXEL_SIZE_UM = [0.65, 0.65]
TIME_STEP_MIN = 15
MIN_TRACKS = 2
MIN_TRANSITION_SLOTS = 100

_IMAGE_RE = re.compile(rf"^{ROOT}/(?P<sequence>[0-9]+)/t(?P<frame>[0-9]+)\.tif$")
_TRACK_RE = re.compile(
    rf"^{ROOT}/(?P<sequence>[0-9]+)_GT/TRA/man_track(?P<frame>[0-9]+)\.tif$"
)


def _digest_members(archive: ZipFile, paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(read_member_bytes(archive, path)).digest())
    return digest.hexdigest()


def _lineage(archive: ZipFile, path: str) -> list[dict]:
    rows = []
    for line_number, line in enumerate(
            read_member_bytes(archive, path).decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"invalid lineage row {path}:{line_number}")
        try:
            track_id, start, end, parent = (int(value) for value in fields)
        except ValueError as exc:
            raise ValueError(f"invalid lineage row {path}:{line_number}") from exc
        if track_id <= 0 or start < 0 or end < start or parent < 0:
            raise ValueError(f"invalid lineage values {path}:{line_number}")
        rows.append({"track_id": track_id, "start": start, "end": end, "parent": parent})
    if not rows:
        raise ValueError(f"empty lineage table: {path}")
    by_id = {row["track_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError(f"duplicate track ID in lineage table: {path}")
    for row in rows:
        if row["parent"] and row["parent"] not in by_id:
            raise ValueError(f"unknown parent in lineage table: {path}")
        if row["parent"] and by_id[row["parent"]]["end"] >= row["start"]:
            raise ValueError(f"overlapping parent/child intervals: {path}")
    return sorted(rows, key=lambda row: row["track_id"])


def _array(archive: ZipFile, path: str) -> np.ndarray:
    with Image.open(BytesIO(read_member_bytes(archive, path))) as image:
        value = np.asarray(image)
    if value.ndim != 2:
        raise ValueError(f"image is not 2D: {path}")
    return value


def _sequence_audit(
        archive: ZipFile, names: set[str], sequence: str, images: dict[int, str],
        tracks: dict[int, str], *, min_tracks: int, min_transition_slots: int) -> dict:
    frames = sorted(images)
    if frames != list(range(len(frames))):
        raise ValueError(f"sequence {sequence} frames are not contiguous from zero")
    if sorted(tracks) != frames:
        raise ValueError(f"sequence {sequence} image/tracking frames disagree")
    lineage_path = f"{ROOT}/{sequence}_GT/TRA/man_track.txt"
    if lineage_path not in names:
        raise ValueError(f"missing lineage table: {lineage_path}")
    lineage = _lineage(archive, lineage_path)
    by_id = {row["track_id"]: row for row in lineage}

    shape = None
    observed_frames: dict[int, list[int]] = {track_id: [] for track_id in by_id}
    for frame in frames:
        image = _array(archive, images[frame])
        mask = _array(archive, tracks[frame])
        if image.shape != mask.shape:
            raise ValueError(f"image/tracking shape mismatch in {sequence}:{frame}")
        if shape is None:
            shape = image.shape
        elif image.shape != shape:
            raise ValueError(f"inconsistent image shape in {sequence}:{frame}")
        labels = {int(label) for label in np.unique(mask) if int(label) != 0}
        unknown = labels - set(by_id)
        if unknown:
            raise ValueError(f"unknown tracking labels in {sequence}:{frame}: {sorted(unknown)}")
        for label in labels:
            row = by_id[label]
            if not row["start"] <= frame <= row["end"]:
                raise ValueError(f"label {label} outside lineage interval in {sequence}:{frame}")
            observed_frames[label].append(frame)

    never_observed = sorted(track_id for track_id, values in observed_frames.items() if not values)
    if never_observed:
        raise ValueError(f"lineage IDs never observed in {sequence}: {never_observed}")
    transition_slots = 0
    for values in observed_frames.values():
        available = set(values)
        transition_slots += sum(
            frame + 1 in available and frame + 2 in available for frame in values
        )
    eligible = len(lineage) >= min_tracks and transition_slots >= min_transition_slots
    selected_paths = list(images.values()) + list(tracks.values()) + [lineage_path]
    return {
        "sequence_id": sequence,
        "frame_count": len(frames),
        "frame_range": [frames[0], frames[-1]],
        "shape_pixels": list(shape),
        "lineage_track_count": len(lineage),
        "root_track_count": sum(row["parent"] == 0 for row in lineage),
        "child_track_count": sum(row["parent"] != 0 for row in lineage),
        "structural_velocity_transition_slots": transition_slots,
        "selected_member_set_sha256": _digest_members(archive, selected_paths),
        "eligible": eligible,
        "schema_checks": {
            "contiguous_zero_based_frames": True,
            "tracking_mask_for_every_frame": True,
            "two_dimensional_images_and_masks": True,
            "consistent_image_mask_shapes": True,
            "known_nonoverlapping_lineage_parents": True,
            "tracking_labels_within_lineage_intervals": True,
            "every_lineage_id_observed": True,
        },
    }


def audit_huh7_archive(
        path: Path, *, expected_size: int = EXPECTED_ARCHIVE_SIZE,
        expected_sha256: str = EXPECTED_ARCHIVE_SHA256,
        min_tracks: int = MIN_TRACKS,
        min_transition_slots: int = MIN_TRANSITION_SLOTS) -> dict:
    """Return a deterministic data-only audit and one locked sequence."""
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.stat().st_size != expected_size:
        raise ValueError(
            f"archive size mismatch: expected {expected_size}, found {path.stat().st_size}"
        )
    archive_sha256 = sha256_file(path)
    if archive_sha256 != expected_sha256:
        raise ValueError(
            f"archive SHA-256 mismatch: expected {expected_sha256}, found {archive_sha256}"
        )
    with ZipFile(path) as archive:
        validate_zip_archive(archive)
        names = set(archive.namelist())
        image_paths: dict[str, dict[int, str]] = {}
        track_paths: dict[str, dict[int, str]] = {}
        for name in names:
            if match := _IMAGE_RE.fullmatch(name):
                image_paths.setdefault(match["sequence"], {})[int(match["frame"])] = name
            elif match := _TRACK_RE.fullmatch(name):
                track_paths.setdefault(match["sequence"], {})[int(match["frame"])] = name
        if not image_paths:
            raise ValueError("no Huh7 CTC sequences found")
        sequence_audits = [
            _sequence_audit(
                archive, names, sequence, images, track_paths.get(sequence, {}),
                min_tracks=min_tracks, min_transition_slots=min_transition_slots,
            )
            for sequence, images in sorted(image_paths.items())
        ]
    eligible = [item for item in sequence_audits if item["eligible"]]
    if not eligible:
        raise ValueError("no sequence passes the pre-registered structural eligibility rule")
    locked = eligible[0]
    return {
        "schema_version": 1,
        "method": "stage_d_v2_huh7_data_only_audit_v1",
        "status": "LOCKED_UNEVALUATED",
        "dataset_id": DATASET_ID,
        "source_page": SOURCE_PAGE,
        "archive_url": ARCHIVE_URL,
        "archive": {
            "file_name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": archive_sha256,
        },
        "acquisition_metadata": {
            "pixel_size_um": PIXEL_SIZE_UM,
            "time_step_min": TIME_STEP_MIN,
            "matches_u373_operator_units": True,
        },
        "selection_rule": (
            "Lexicographically first schema-valid sequence with at least "
            f"{min_tracks} lineage tracks and {min_transition_slots} structural "
            "velocity-transition slots; no coordinate or outcome metric is inspected."
        ),
        "locked_sequence_id": locked["sequence_id"],
        "locked_sequence_member_set_sha256": locked["selected_member_set_sha256"],
        "sequence_audits": sequence_audits,
        "data_only_invariants": {
            "coordinates_extracted": False,
            "motion_values_computed": False,
            "models_fitted": False,
            "outcome_metrics_exposed": False,
            "locked_before_evaluation": True,
        },
        "repository_policy": "Do not commit or redistribute the archive or reference annotations.",
        "decision": "PASS_DATA_ONLY_AUDIT_AND_LOCK",
        "biological_claim": "not supported",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit_huh7_archive(args.archive)
    except (OSError, BadZipFile, ValueError) as exc:
        print(f"Stage D v2 Huh7 audit failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {args.output} (locked sequence {result['locked_sequence_id']}; "
        "no outcome metrics exposed)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
