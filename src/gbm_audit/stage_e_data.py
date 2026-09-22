"""Stage E CTC archive handling with an explicit sequence-02 access boundary."""

from __future__ import annotations

from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
from zipfile import ZipFile

import numpy as np
from PIL import Image

from gbm_audit.archive import read_member_bytes, validate_zip_archive
from gbm_audit.benchmark import _lineage, _observations
from gbm_audit.cli import sha256_file


_IMAGE_RE = re.compile(r"^(?P<root>.+)/(?P<sequence>[0-9]+)/t(?P<frame>[0-9]+)\.tif$")
_TRACK_RE = re.compile(r"^(?P<root>.+)/(?P<sequence>[0-9]+)_GT/TRA/man_track(?P<frame>[0-9]+)\.tif$")
_SEG_RE = re.compile(r"^(?P<root>.+)/(?P<sequence>[0-9]+)_GT/SEG/man_seg(?P<frame>[0-9]+)\.tif$")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_stage_e_contract(manifest_path: Path, split_path: Path) -> tuple[dict, dict]:
    """Load and cross-check the committed Stage E manifest and split lock."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    split = json.loads(split_path.read_text(encoding="utf-8"))
    expected = split.get("dataset_manifest_sha256")
    actual = _file_sha256(manifest_path)
    if expected != actual:
        raise ValueError("Stage E dataset manifest hash does not match the split lock")
    if split.get("status") != "LOCKED_BEFORE_IMPLEMENTATION_OR_OUTCOME_EVALUATION":
        raise ValueError("Stage E split is not in its pre-outcome locked state")
    if not all(value is False for value in split.get("test_access_state", {}).values()):
        raise ValueError("Stage E split records prior locked-test outcome access")
    return manifest, split


def _dataset_entry(manifest: dict, dataset_id: str) -> dict:
    for entry in manifest.get("datasets", []):
        if entry.get("dataset_id") == dataset_id:
            return entry
    raise ValueError(f"Dataset {dataset_id!r} is absent from the Stage E manifest")


def _indexed_members(names: set[str], pattern: re.Pattern) -> tuple[dict[str, dict[int, str]], dict[str, str]]:
    paths: dict[str, dict[int, str]] = {}
    roots: dict[str, str] = {}
    for name in names:
        match = pattern.fullmatch(name)
        if match:
            sequence = match["sequence"]
            paths.setdefault(sequence, {})[int(match["frame"])] = name
            roots.setdefault(sequence, match["root"])
    return paths, roots


def audit_ctc_archive(path: Path, dataset: dict) -> dict:
    """Verify archive identity and sequence structure without decoding TIFF data."""
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.name != dataset["archive_file"]:
        raise ValueError(f"Unexpected archive file name: {path.name}")
    if path.stat().st_size != dataset["archive_size_bytes"]:
        raise ValueError("Archive size does not match the Stage E manifest")
    if sha256_file(path) != dataset["archive_sha256"]:
        raise ValueError("Archive SHA-256 does not match the Stage E manifest")

    with ZipFile(path) as archive:
        validate_zip_archive(archive)
        names = set(archive.namelist())
        images, image_roots = _indexed_members(names, _IMAGE_RE)
        tracks, track_roots = _indexed_members(names, _TRACK_RE)
        segmentations, _ = _indexed_members(names, _SEG_RE)
        expected_by_sequence = {entry["sequence_id"]: entry for entry in dataset["sequences"]}
        if set(images) != set(expected_by_sequence):
            raise ValueError(f"Unexpected image sequences: {sorted(images)}")
        details = {}
        for sequence_id, expected in sorted(expected_by_sequence.items()):
            image_frames = images.get(sequence_id, {})
            track_frames = tracks.get(sequence_id, {})
            if sorted(image_frames) != list(range(expected["raw_frame_count"])):
                raise ValueError(f"Non-contiguous or unexpected image frames in sequence {sequence_id}")
            if sorted(track_frames) != sorted(image_frames):
                raise ValueError(f"Image/tracking mask mismatch in sequence {sequence_id}")
            root = image_roots[sequence_id]
            if track_roots.get(sequence_id) != root:
                raise ValueError(f"Image/tracking roots differ in sequence {sequence_id}")
            lineage_path = f"{root}/{sequence_id}_GT/TRA/man_track.txt"
            if lineage_path not in names:
                raise ValueError(f"Missing lineage table for sequence {sequence_id}")
            lineage_rows = [line for line in read_member_bytes(archive, lineage_path).decode("utf-8").splitlines() if line.strip()]
            if len(lineage_rows) != expected["lineage_row_count"]:
                raise ValueError(f"Unexpected lineage row count in sequence {sequence_id}")
            for line in lineage_rows:
                if len(line.split()) != 4:
                    raise ValueError(f"Invalid lineage schema in sequence {sequence_id}")
            if len(segmentations.get(sequence_id, {})) != expected["gold_segmentation_mask_count"]:
                raise ValueError(f"Unexpected segmentation-mask count in sequence {sequence_id}")
            details[sequence_id] = {
                "raw_frame_count": len(image_frames),
                "tracking_mask_count": len(track_frames),
                "gold_segmentation_mask_count": len(segmentations.get(sequence_id, {})),
                "lineage_row_count": len(lineage_rows),
                "tiff_pixels_decoded": False,
            }
    return {
        "dataset_id": dataset["dataset_id"],
        "archive_file": path.name,
        "archive_size_bytes": path.stat().st_size,
        "archive_sha256": sha256_file(path),
        "sequences": details,
        "audit_kind": "structural_only",
        "locked_test_outcome_access": False,
    }


def build_development_manifest(path: Path, dataset: dict, sequence_id: str = "01") -> dict:
    """Decode only the registered development sequence into a reference manifest."""
    audit_ctc_archive(path, dataset)
    if sequence_id != "01":
        raise ValueError("Stage E development builder is restricted to sequence 01")

    with ZipFile(path) as archive:
        names = set(archive.namelist())
        images, image_roots = _indexed_members(names, _IMAGE_RE)
        tracks, _ = _indexed_members(names, _TRACK_RE)
        segmentations, _ = _indexed_members(names, _SEG_RE)
        image_paths = images[sequence_id]
        track_paths = tracks[sequence_id]
        root = image_roots[sequence_id]
        lineage_path = f"{root}/{sequence_id}_GT/TRA/man_track.txt"
        lineage = _lineage(archive, lineage_path)
        observations = _observations(archive, track_paths)
        image_shape = None
        for frame in sorted(image_paths):
            with Image.open(BytesIO(read_member_bytes(archive, image_paths[frame]))) as image:
                current_image_shape = tuple(np.asarray(image).shape)
            with Image.open(BytesIO(read_member_bytes(archive, track_paths[frame]))) as mask:
                current_mask_shape = tuple(np.asarray(mask).shape)
            if len(current_image_shape) != 2 or current_image_shape != current_mask_shape:
                raise ValueError(f"Image/tracking mask shape mismatch for {sequence_id}:{frame}")
            if image_shape is None:
                image_shape = list(current_image_shape)
            elif image_shape != list(current_image_shape):
                raise ValueError(f"Inconsistent image shape for sequence {sequence_id}:{frame}")
        for frame, segmentation_path in segmentations.get(sequence_id, {}).items():
            with Image.open(BytesIO(read_member_bytes(archive, segmentation_path))) as segmentation:
                if tuple(np.asarray(segmentation).shape) != tuple(image_shape):
                    raise ValueError(f"Image/segmentation shape mismatch for {sequence_id}:{frame}")
        by_id = {row["track_id"]: row for row in lineage}
        if set(observations) != set(by_id):
            raise ValueError("Tracking-mask IDs differ from lineage IDs")
        frozen_tracks = []
        for track_id in sorted(observations):
            track = by_id[track_id]
            points = observations[track_id]
            frames = [point["frame"] for point in points]
            if frames[0] < track["start_frame"] or frames[-1] > track["end_frame"]:
                raise ValueError(f"Track {track_id} falls outside its lineage interval")
            frozen_tracks.append({**track, "observations": points})
        sequence = {
            "sequence_id": sequence_id,
            "split": "development",
            "frames": len(image_paths),
            "frame_indices": sorted(image_paths),
            "shape_pixels": image_shape,
            "lineage_rows": len(lineage),
            "tracks": frozen_tracks,
            "tracked_ids": len(frozen_tracks),
            "consecutive_links": sum(
                sum(right["frame"] - left["frame"] == 1 for left, right in zip(track["observations"], track["observations"][1:]))
                for track in frozen_tracks
            ),
        }
    return {
        "schema_version": 1,
        "dataset": dataset["dataset_id"],
        "reference_kind": dataset["annotation_type"],
        "source": dataset["archive_url"],
        "archive": {
            "file_name": path.name,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        },
        "pixel_size_um": dataset["pixel_size_um"],
        "time_step_min": dataset["time_step_min"],
        "split_policy": "Stage E development only: sequence 01 is decoded; sequence 02 remains locked and omitted.",
        "stage_e_access_boundary": {
            "decoded_sequences": ["01"],
            "locked_sequences": ["02"],
            "locked_test_outcome_access": False,
        },
        "warning": "Reference-backed technical development artifact; not biological or clinical validation.",
        "sequences": {sequence_id: sequence},
    }
