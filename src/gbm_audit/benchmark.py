"""Build a deterministic, reference-backed U373 benchmark manifest.

The manifest contains expert tracking-mask centroids and lineage metadata,
not copied image data. It is a technical cell-tracking benchmark and must not
be interpreted as brain-slice biological validation.
"""

import argparse
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


_IMAGE_RE = re.compile(r"^(?P<root>.+)/(?P<sequence>[0-9]+)/t(?P<frame>[0-9]+)\.tif$")
_TRACK_RE = re.compile(r"^(?P<root>.+)/(?P<sequence>[0-9]+)_GT/TRA/man_track(?P<frame>[0-9]+)\.tif$")
_SEG_RE = re.compile(r"^(?P<root>.+)/(?P<sequence>[0-9]+)_GT/SEG/man_seg(?P<frame>[0-9]+)\.tif$")


def _lineage(archive: ZipFile, path: str) -> list[dict]:
    rows = []
    for line_number, line in enumerate(read_member_bytes(archive, path).decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) != 4:
            raise ValueError(f"Invalid lineage row {path}:{line_number}: expected 4 integers")
        try:
            track_id, start, end, parent = (int(value) for value in fields)
        except ValueError as exc:
            raise ValueError(f"Invalid lineage row {path}:{line_number}") from exc
        if track_id <= 0 or start < 0 or end < start or parent < 0:
            raise ValueError(f"Invalid lineage values {path}:{line_number}")
        rows.append({"track_id": track_id, "start_frame": start,
                     "end_frame": end, "parent_id": parent})
    if not rows:
        raise ValueError(f"Empty lineage table: {path}")
    ids = {row["track_id"] for row in rows}
    if len(ids) != len(rows):
        raise ValueError(f"Duplicate track ID in lineage table: {path}")
    if any(row["parent_id"] and row["parent_id"] not in ids for row in rows):
        raise ValueError(f"Lineage references an unknown parent: {path}")
    return sorted(rows, key=lambda row: row["track_id"])


def _observations(archive: ZipFile, mask_paths: dict[int, str]) -> dict[int, list[dict]]:
    tracks: dict[int, list[dict]] = {}
    for frame, path in sorted(mask_paths.items()):
        with Image.open(BytesIO(read_member_bytes(archive, path))) as image:
            mask = np.asarray(image)
        if mask.ndim != 2:
            raise ValueError(f"Tracking mask is not 2D: {path}")
        for label in np.unique(mask):
            label = int(label)
            if label == 0:
                continue
            ys, xs = np.where(mask == label)
            tracks.setdefault(label, []).append({
                "frame": frame,
                "x_px": round(float(xs.mean()), 6),
                "y_px": round(float(ys.mean()), 6),
                "area_px": int(xs.size),
            })
    return tracks


def build_manifest(path: Path) -> dict:
    """Read U373 reference files from *path* and return a frozen manifest."""
    if not path.is_file():
        raise FileNotFoundError(path)
    with ZipFile(path) as archive:
        validate_zip_archive(archive)
        names = set(archive.namelist())
        image_paths: dict[str, dict[int, str]] = {}
        track_paths: dict[str, dict[int, str]] = {}
        seg_paths: dict[str, dict[int, str]] = {}
        for name in names:
            if (match := _IMAGE_RE.fullmatch(name)):
                image_paths.setdefault(match["sequence"], {})[int(match["frame"])] = name
            elif (match := _TRACK_RE.fullmatch(name)):
                track_paths.setdefault(match["sequence"], {})[int(match["frame"])] = name
            elif (match := _SEG_RE.fullmatch(name)):
                seg_paths.setdefault(match["sequence"], {})[int(match["frame"])] = name

        sequences = {}
        for sequence in sorted(image_paths):
            images = image_paths[sequence]
            tracks = track_paths.get(sequence, {})
            if sorted(images) != sorted(tracks):
                raise ValueError(f"Image/tracking frame mismatch for sequence {sequence}")
            if sorted(images) != list(range(len(images))):
                raise ValueError(f"Sequence {sequence} does not have a contiguous 0-based frame index")
            root = next(iter(images.values())).rsplit(f"/{sequence}/", 1)[0]
            lineage_path = f"{root}/{sequence}_GT/TRA/man_track.txt"
            if lineage_path not in names:
                raise ValueError(f"Missing lineage table: {lineage_path}")
            lineage = _lineage(archive, lineage_path)
            observations = _observations(archive, tracks)
            image_shape = None
            for frame in sorted(images):
                with Image.open(BytesIO(read_member_bytes(archive, images[frame]))) as image:
                    current_image_shape = tuple(np.asarray(image).shape)
                with Image.open(BytesIO(read_member_bytes(archive, tracks[frame]))) as mask_image:
                    current_mask_shape = tuple(np.asarray(mask_image).shape)
                if len(current_image_shape) != 2 or current_image_shape != current_mask_shape:
                    raise ValueError(f"Image/tracking mask shape mismatch for {sequence}:{frame}")
                if image_shape is None:
                    image_shape = list(current_image_shape)
                elif list(current_image_shape) != image_shape:
                    raise ValueError(f"Inconsistent image shape for sequence {sequence}:{frame}")
            for frame, seg_path in seg_paths.get(sequence, {}).items():
                with Image.open(BytesIO(read_member_bytes(archive, seg_path))) as segmentation:
                    if tuple(np.asarray(segmentation).shape) != tuple(image_shape):
                        raise ValueError(f"Image/segmentation shape mismatch for {sequence}:{frame}")
            lineage_ids = {row["track_id"] for row in lineage}
            if set(observations) != lineage_ids:
                raise ValueError(f"Mask/lineage track IDs differ for sequence {sequence}")
            by_id = {row["track_id"]: row for row in lineage}
            frozen_tracks = []
            shape = None
            for track_id in sorted(observations):
                points = observations[track_id]
                shape = image_shape
                expected = by_id[track_id]
                observed_frames = [point["frame"] for point in points]
                if observed_frames[0] < expected["start_frame"] or observed_frames[-1] > expected["end_frame"]:
                    raise ValueError(f"Track {track_id} falls outside lineage interval in sequence {sequence}")
                frozen_tracks.append({**expected, "observations": points})
            sequence_root = f"{root}/{sequence}"
            sequences[sequence] = {
                "sequence_id": sequence,
                "split": "development" if sequence == "01" else "test",
                "frames": len(images),
                "frame_indices": sorted(images),
                "shape_pixels": shape,
                "image_paths": [images[frame] for frame in sorted(images)],
                "tracking_mask_paths": [tracks[frame] for frame in sorted(tracks)],
                "segmentation_mask_paths": [seg_paths.get(sequence, {}).get(frame) for frame in sorted(seg_paths.get(sequence, {}))],
                "lineage_path": lineage_path,
                "lineage_rows": len(lineage),
                "tracks": frozen_tracks,
                "tracked_ids": len(frozen_tracks),
                "consecutive_links": sum(sum(b["frame"] - a["frame"] == 1 for a, b in zip(t["observations"], t["observations"][1:])) for t in frozen_tracks),
                "sequence_root": sequence_root,
            }
    if set(sequences) != {"01", "02"}:
        raise ValueError(f"Expected U373 sequences 01 and 02; found {sorted(sequences)}")
    return {
        "schema_version": 1,
        "dataset": "CTC PhC-C2DH-U373 training",
        "reference_kind": "expert_tracking_masks_and_lineage",
        "source": "https://celltrackingchallenge.net/2d-datasets/",
        "archive": {"file_name": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)},
        "split_policy": "sequence-level: 01 development, 02 test; never split adjacent frames across roles",
        "warning": "Technical 2D phase-contrast benchmark; not brain-slice biological validation.",
        "sequences": sequences,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = build_manifest(args.archive)
    except (OSError, BadZipFile, ValueError) as exc:
        print(f"Benchmark build failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['sequences'])} sequences, "
          f"{sum(s['tracked_ids'] for s in result['sequences'].values())} tracks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
