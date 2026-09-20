"""Audit and lock the T98G electrotaxis dataset without evaluating tracking.

This module validates source identity, archive safety, CTC-like structure and
reference consistency.  It intentionally emits no coordinates, trajectories,
tracking scores or migration summaries.
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


ZENODO_RECORD_ID = 19026908
ZENODO_CONCEPT_RECORD_ID = 18924852
ZENODO_DOI = "10.5281/zenodo.19026908"
ZENODO_CONCEPT_DOI = "10.5281/zenodo.18924852"
SOURCE_URL = "https://zenodo.org/records/19026908"
SOURCE_API_URL = "https://zenodo.org/api/records/19026908"
ARCHIVE_URL = (
    "https://zenodo.org/api/records/19026908/files/T98G_electrotaxis.zip/content"
)
EXPECTED_ARCHIVE_SIZE = 147_735_077
EXPECTED_ARCHIVE_MD5 = "5e89fc619d40e1e8f4aa8e733abc2f87"
EXPECTED_ARCHIVE_SHA256 = "1b80d50f61efca6729af4ef691adab77d06c358fbda7a73744eb4e9b252abd6c"
TEST_CORRUPTION_SEED = 20260920

ROOT = "T98G_electrotaxis"
SELECTED_VARIANT = "T98G_human"
EXCLUDED_VARIANT = "T98G_detectron2"
SEQUENCE_NAME = "T98G_sample"

_RAW_RE = re.compile(r"20180101ef002xy01t(?P<frame>[0-9]{2})\.tif")
_TRACK_RE = re.compile(r"mask(?P<frame>[0-9]{3})\.tif")
_SEG_RE = re.compile(r"man_seg(?P<frame>[0-9]{3})\.tif")


def _digest(data: bytes, algorithm: str = "sha256") -> str:
    return hashlib.new(algorithm, data).hexdigest()


def _archive_md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _indexed_members(names: set[str], prefix: str, pattern: re.Pattern) -> dict[int, str]:
    indexed = {}
    for name in names:
        if not name.startswith(prefix):
            continue
        relative = name.removeprefix(prefix)
        match = pattern.fullmatch(relative)
        if not match:
            continue
        frame = int(match["frame"])
        if frame in indexed:
            raise ValueError(f"duplicate frame {frame} under {prefix}")
        indexed[frame] = name
    return indexed


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
        rows.append({
            "track_id": track_id,
            "start_frame": start,
            "end_frame": end,
            "parent_id": parent,
        })
    if not rows:
        raise ValueError(f"empty lineage table: {path}")
    by_id = {row["track_id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError(f"duplicate track ID in lineage table: {path}")
    for row in rows:
        if not row["parent_id"]:
            continue
        if row["parent_id"] not in by_id:
            raise ValueError(f"lineage references an unknown parent: {path}")
        parent = by_id[row["parent_id"]]
        if parent["end_frame"] >= row["start_frame"]:
            raise ValueError(f"parent/child intervals overlap in lineage table: {path}")
    return sorted(rows, key=lambda row: row["track_id"])


def _image_array(archive: ZipFile, path: str) -> np.ndarray:
    with Image.open(BytesIO(read_member_bytes(archive, path))) as image:
        array = np.asarray(image)
    if array.ndim != 2:
        raise ValueError(f"image is not 2D: {path}")
    return array


def _content_series_sha256(archive: ZipFile, indexed: dict[int, str]) -> str:
    digest = hashlib.sha256()
    for frame, path in sorted(indexed.items()):
        data = read_member_bytes(archive, path)
        digest.update(str(frame).encode("ascii"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(data).digest())
    return digest.hexdigest()


def _selected_member_set_sha256(archive: ZipFile, paths: list[str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(hashlib.sha256(read_member_bytes(archive, path)).digest())
    return digest.hexdigest()


def _variant(archive: ZipFile, names: set[str], variant: str) -> dict:
    root = f"{ROOT}/{variant}"
    raw = _indexed_members(names, f"{root}/{SEQUENCE_NAME}/", _RAW_RE)
    tracks = _indexed_members(names, f"{root}/{SEQUENCE_NAME}_GT/TRA/", _TRACK_RE)
    segments = _indexed_members(names, f"{root}/{SEQUENCE_NAME}_GT/SEG/", _SEG_RE)
    lineage_path = f"{root}/{SEQUENCE_NAME}_GT/TRA/man_track.txt"
    if lineage_path not in names:
        raise ValueError(f"missing lineage table: {lineage_path}")

    source_frames = sorted(raw)
    if source_frames != list(range(1, 38)):
        raise ValueError(f"{variant} raw frames are not contiguous 1..37")
    reference_frames = sorted(tracks)
    if reference_frames != list(range(37)) or sorted(segments) != reference_frames:
        raise ValueError(f"{variant} reference frames are not contiguous 0..36")

    lineage = _lineage(archive, lineage_path)
    by_id = {row["track_id"]: row for row in lineage}
    image_shape = None
    image_dtypes = set()
    track_dtypes = set()
    segmentation_dtypes = set()
    observed_lineage_ids = set()
    expected_label_instances = 0
    observed_label_instances = 0
    missing_active_label_instances = 0
    for reference_frame in reference_frames:
        image = _image_array(archive, raw[reference_frame + 1])
        track_mask = _image_array(archive, tracks[reference_frame])
        segmentation = _image_array(archive, segments[reference_frame])
        if image.shape != track_mask.shape or image.shape != segmentation.shape:
            raise ValueError(f"image/reference shape mismatch in {variant}:{reference_frame}")
        if image_shape is None:
            image_shape = image.shape
        elif image.shape != image_shape:
            raise ValueError(f"inconsistent image shape in {variant}:{reference_frame}")
        image_dtypes.add(str(image.dtype))
        track_dtypes.add(str(track_mask.dtype))
        segmentation_dtypes.add(str(segmentation.dtype))
        actual = {int(label) for label in np.unique(track_mask) if int(label) != 0}
        expected = {
            track_id for track_id, row in by_id.items()
            if row["start_frame"] <= reference_frame <= row["end_frame"]
        }
        extra = sorted(actual - expected)
        if extra:
            raise ValueError(
                f"tracking mask contains labels outside lineage intervals in "
                f"{variant}:{reference_frame}; extra={extra}"
            )
        observed_lineage_ids.update(actual)
        expected_label_instances += len(expected)
        observed_label_instances += len(actual)
        missing_active_label_instances += len(expected - actual)

    missing_lineage_ids = sorted(set(by_id) - observed_lineage_ids)
    if missing_lineage_ids:
        raise ValueError(f"lineage IDs never observed in {variant}: {missing_lineage_ids}")

    selected_paths = list(raw.values()) + list(tracks.values()) + list(segments.values())
    selected_paths.append(lineage_path)
    return {
        "variant": variant,
        "raw_frames": len(raw),
        "tracking_mask_frames": len(tracks),
        "segmentation_mask_frames": len(segments),
        "source_frame_range": [source_frames[0], source_frames[-1]],
        "reference_frame_range": [reference_frames[0], reference_frames[-1]],
        "shape_pixels": list(image_shape),
        "image_dtypes": sorted(image_dtypes),
        "tracking_mask_dtypes": sorted(track_dtypes),
        "segmentation_mask_dtypes": sorted(segmentation_dtypes),
        "lineage_rows": len(lineage),
        "root_tracks": sum(row["parent_id"] == 0 for row in lineage),
        "child_tracks": sum(row["parent_id"] != 0 for row in lineage),
        "expected_active_label_instances": expected_label_instances,
        "observed_active_label_instances": observed_label_instances,
        "missing_active_label_instances": missing_active_label_instances,
        "raw_frame_series_sha256": _content_series_sha256(archive, raw),
        "lineage_sha256": _digest(read_member_bytes(archive, lineage_path)),
        "selected_member_set_sha256": _selected_member_set_sha256(archive, selected_paths),
        "schema_checks": {
            "contiguous_frame_indices": True,
            "two_dimensional_images": True,
            "consistent_shapes": True,
            "known_nonoverlapping_parents": True,
            "tracking_labels_stay_within_lineage_intervals": True,
            "every_lineage_id_is_observed": True,
        },
    }


def audit_t98g_archive(
        path: Path, *, expected_size: int = EXPECTED_ARCHIVE_SIZE,
        expected_md5: str = EXPECTED_ARCHIVE_MD5,
        expected_sha256: str = EXPECTED_ARCHIVE_SHA256) -> dict:
    """Return a deterministic, structural-only locked-test audit artifact."""
    if not path.is_file():
        raise FileNotFoundError(path)
    size = path.stat().st_size
    if size != expected_size:
        raise ValueError(f"archive size mismatch: expected {expected_size}, found {size}")
    md5 = _archive_md5(path)
    if md5 != expected_md5:
        raise ValueError(f"archive MD5 mismatch: expected {expected_md5}, found {md5}")
    sha256 = sha256_file(path)
    if sha256 != expected_sha256:
        raise ValueError(f"archive SHA-256 mismatch: expected {expected_sha256}, found {sha256}")

    with ZipFile(path) as archive:
        validate_zip_archive(archive)
        names = set(archive.namelist())
        human = _variant(archive, names, SELECTED_VARIANT)
        detectron2 = _variant(archive, names, EXCLUDED_VARIANT)
        if human["raw_frame_series_sha256"] != detectron2["raw_frame_series_sha256"]:
            raise ValueError("human and Detectron2 variants do not share identical raw frames")
        if human["lineage_sha256"] != detectron2["lineage_sha256"]:
            raise ValueError("human and Detectron2 variants do not share identical lineage tables")
        file_count = sum(not info.is_dir() for info in archive.infolist())
        uncompressed_bytes = sum(
            info.file_size for info in archive.infolist() if not info.is_dir()
        )

    return {
        "schema_version": 1,
        "audit": "stage_c_v2_t98g_data_only_audit_v1",
        "status": "PASS",
        "lock_state": "LOCKED_UNEVALUATED",
        "audit_date": "2026-09-20",
        "source": {
            "record_id": ZENODO_RECORD_ID,
            "concept_record_id": ZENODO_CONCEPT_RECORD_ID,
            "doi": ZENODO_DOI,
            "concept_doi": ZENODO_CONCEPT_DOI,
            "record_url": SOURCE_URL,
            "api_url": SOURCE_API_URL,
            "archive_url": ARCHIVE_URL,
            "publisher": "Zenodo",
            "publication_date": "2026-03-15",
            "access_right": "open",
            "license": "CC-BY-4.0",
            "creators": [
                {"name": "Chang, I-Ming", "affiliation": "Chang Gung University"},
                {"name": "Tsai, Hsieh-Fu", "affiliation": "Chang Gung University",
                 "orcid": "0000-0002-8652-4643"},
            ],
        },
        "archive": {
            "file_name": "T98G_electrotaxis.zip",
            "size_bytes": size,
            "zenodo_md5": md5,
            "sha256": sha256,
            "zip_integrity": "PASS",
            "file_count": file_count,
            "uncompressed_bytes": uncompressed_bytes,
        },
        "locked_test": {
            "dataset_id": "T98G_electrotaxis_human_v2",
            "sequence_id": SEQUENCE_NAME,
            "selected_variant": SELECTED_VARIANT,
            "reference_kind": "human_curated_segmentation_masks_and_lineage",
            "test_corruption_seed": TEST_CORRUPTION_SEED,
            **human,
        },
        "excluded_variant": {
            "variant": EXCLUDED_VARIANT,
            "reason": (
                "Automated Detectron2 segmentation of the same raw sequence and lineage; "
                "not an independent locked-test sequence."
            ),
            "structural_audit": detectron2,
        },
        "evaluation_boundary": {
            "u373_sequence_01_role": "development_only",
            "u373_sequence_02_role": "consumed_v1_test_archival_only",
            "tracking_metrics_computed": False,
            "migration_summaries_computed": False,
            "performance_evaluation_run": False,
            "reference_coordinates_exported": False,
        },
        "decision": (
            "T98G human-curated variant qualifies as the independent Stage C v2 locked test. "
            "It must remain unevaluated until all v2 development values are frozen."
        ),
        "warning": (
            "Technical 2D T98G electrotaxis benchmark only; this does not validate a "
            "GlioTrace brain-slice biological phenotype."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = audit_t98g_archive(args.archive)
    except (OSError, BadZipFile, ValueError) as exc:
        print(f"T98G audit failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"Wrote {args.output} ({result['status']}, "
        f"{result['locked_test']['raw_frames']} structural frames; no performance evaluation)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
