"""Hardened local Dryad inventory and normalization wrapper.

The deposited Dryad archive contains macOS AppleDouble/metadata members such as
``__MACOSX/.../._name.xlsx``. Those files inherit the suffix of the original
file but are not real workbooks. Treating them as candidate tables causes
``openpyxl`` to raise ``BadZipFile`` even though the outer Dryad ZIP is valid.

The archive also contains legitimate highly-compressible image assets (for
example TIFF deformation maps). A blanket compression-ratio guard therefore
produces false positives on the frozen, digest-verified source bundle. This
wrapper preserves path, per-member-size, total-uncompressed-size and candidate-
table compression-ratio checks, while allowing non-table assets after the
source bundle identity has already been verified against the frozen manifest.

The deposited tumour tracking matrices use four columns: elapsed time, cell/
track identifier, x and y. Acquisition timing is irregular in places, so a
single fixed frame interval would be incorrect. For the locked Dryad schema the
canonical frame is reconstructed deterministically as the rank of each unique
global elapsed-time value within an experiment. This preserves the source time
values for motion calculations while supplying the discrete frame index needed
for consecutive-frame association evaluation. No method-performance outcome is
used in this reconstruction.

Schema-only preview failures are recorded; they never silently become
normalization inputs. Normalization remains fail-closed and uses the same safe
member validator so the real archive can pass through unchanged once the
schema lock is committed.
"""

from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

from gbm_audit import dryad_local as base


_BASE_NORMALIZE_RECORDS = base._normalize_records


def _is_macos_metadata(name: str) -> bool:
    path = PurePosixPath(name)
    return "__MACOSX" in path.parts or path.name.startswith("._") or path.name == ".DS_Store"


def _validate_member(info: zipfile.ZipInfo) -> None:
    """Validate a member without rejecting trusted high-ratio non-table assets.

    The outer source identity is checked before inventory/normalization, and the
    total uncompressed archive size is still bounded. Compression-ratio checks
    remain active for candidate table formats because those are the only member
    classes that the schema pipeline may parse into memory.
    """

    path = PurePosixPath(info.filename)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe archive member path: {info.filename}")
    if info.file_size > base.MAX_MEMBER_UNCOMPRESSED:
        raise ValueError(f"archive member exceeds size limit: {info.filename}")

    suffix = Path(info.filename).suffix.lower()
    metadata_only = _is_macos_metadata(info.filename)
    candidate_table = suffix in base.TABLE_SUFFIXES and not metadata_only and not info.is_dir()
    if (
        candidate_table
        and info.compress_size > 0
        and info.file_size / info.compress_size > base.MAX_COMPRESSION_RATIO
    ):
        raise ValueError(f"candidate table exceeds compression-ratio limit: {info.filename}")


def inspect_bundle(bundle_path: Path) -> dict:
    members: list[dict] = []
    candidate_tables: list[dict] = []
    ignored_metadata_members = 0
    high_ratio_non_table_members = 0

    with zipfile.ZipFile(bundle_path) as archive:
        infos = archive.infolist()
        if len(infos) > base.MAX_MEMBERS:
            raise ValueError(f"archive has too many members: {len(infos)}")

        total = 0
        for info in infos:
            _validate_member(info)
            total += info.file_size
            if total > base.MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("archive exceeds total uncompressed-size limit")

            suffix = Path(info.filename).suffix.lower()
            metadata_only = _is_macos_metadata(info.filename)
            if metadata_only:
                ignored_metadata_members += 1

            is_candidate = suffix in base.TABLE_SUFFIXES and not metadata_only and not info.is_dir()
            ratio = None
            if info.compress_size > 0:
                ratio = info.file_size / info.compress_size
                if not is_candidate and ratio > base.MAX_COMPRESSION_RATIO:
                    high_ratio_non_table_members += 1

            row = {
                "path": info.filename,
                "suffix": suffix,
                "uncompressed_bytes": info.file_size,
                "compressed_bytes": info.compress_size,
                "compression_ratio": ratio,
                "crc32": f"{info.CRC:08x}",
                "candidate_tracking_table": is_candidate,
                "ignored_macos_metadata": metadata_only,
            }
            members.append(row)

            if not is_candidate:
                continue

            preview: dict = {"path": info.filename, "suffix": suffix}
            if not (0 < info.file_size <= base.MAX_PREVIEW_BYTES):
                preview["inspection"] = "metadata only: member exceeds schema-preview byte limit"
                candidate_tables.append(preview)
                continue

            try:
                data = archive.read(info)
                if suffix in base.TEXT_SUFFIXES:
                    preview.update(base._text_preview(data, suffix))
                elif suffix == ".xlsx":
                    preview.update(base._xlsx_preview(data))
                elif suffix == ".mat":
                    preview.update(base._mat_preview(data))
                elif suffix == ".xls":
                    preview.update({"kind": "xls", "inspection": "legacy XLS; mapping will require xlrd"})
            except Exception as exc:  # schema inventory records preview failure; normalization remains fail-closed
                preview.update(
                    {
                        "inspection": "schema preview failed; member retained for explicit review",
                        "inspection_error": f"{type(exc).__name__}: {exc}",
                    }
                )
            candidate_tables.append(preview)

    return {
        "member_count": len(members),
        "ignored_macos_metadata_members": ignored_metadata_members,
        "high_ratio_non_table_members": high_ratio_non_table_members,
        "total_uncompressed_bytes": sum(item["uncompressed_bytes"] for item in members),
        "members": members,
        "candidate_tables": candidate_tables,
    }


def inventory(source_dir: Path, source_manifest_path: Path) -> dict:
    identity = base.verify_source_dir(source_dir, source_manifest_path, require_readme=True)
    schema = inspect_bundle(source_dir / base.REQUIRED_BUNDLE)
    return {
        "schema_version": 1,
        "status": "SCHEMA_ONLY_INVENTORY_COMPLETE_NO_METHOD_OUTCOMES",
        "boundary": "No tracking-method performance metrics are computed by this command.",
        "source_identity": identity,
        "archive": schema,
        "next_gate": "Review this inventory and commit docs/dryad-confirmatory-schema-lock.json with status LOCKED before normalization/evaluation.",
    }


def _normalize_records_with_frame_strategy(records: list, experiment_id: str, spec: dict):
    """Normalize records using the schema-locked frame reconstruction strategy.

    ``global_time_rank`` maps each distinct source elapsed-time value, after the
    frozen time-unit conversion, to its sorted global rank. It is intentionally
    deterministic and uses no method-performance information. Exact source time
    remains in ``time_min`` and therefore continues to determine pairwise dt.
    """

    strategy = spec.get("frame_derivation")
    if strategy in (None, "source_or_fixed_interval"):
        return _BASE_NORMALIZE_RECORDS(records, experiment_id, spec)
    if strategy != "global_time_rank":
        raise ValueError(f"unsupported frame_derivation for {experiment_id}: {strategy!r}")

    mapping = spec.get("column_map", {})
    if mapping.get("frame") is not None:
        raise ValueError(f"global_time_rank requires no source frame mapping for {experiment_id}")
    time_selector = mapping.get("time_min")
    if time_selector is None:
        raise ValueError(f"global_time_rank requires a source time mapping for {experiment_id}")

    time_scale = float(spec.get("time_scale_to_min", 1.0))
    if time_scale <= 0:
        raise ValueError(f"time_scale_to_min must be positive for {experiment_id}")

    scaled_times: list[float] = []
    for record in records:
        raw_time = base._value(record, time_selector, "time_min")
        if raw_time in (None, ""):
            raise ValueError(f"global_time_rank found missing source time in {experiment_id}")
        scaled_times.append(base._finite_float(raw_time, "time_min") * time_scale)

    unique_times = sorted(set(scaled_times))
    if len(unique_times) < 2:
        raise ValueError(f"global_time_rank requires at least two distinct times in {experiment_id}")
    frame_for_time = {value: index for index, value in enumerate(unique_times)}

    patched_records = []
    patched_spec = copy.deepcopy(spec)
    patched_mapping = dict(mapping)
    if records and isinstance(records[0], dict):
        frame_key = "__derived_global_frame__"
        patched_mapping["frame"] = frame_key
        for record, time_min in zip(records, scaled_times):
            copied = dict(record)
            if frame_key in copied:
                raise ValueError(f"reserved derived-frame field already exists in {experiment_id}")
            copied[frame_key] = frame_for_time[time_min]
            patched_records.append(copied)
    else:
        frame_index = max((len(record) for record in records), default=0)
        patched_mapping["frame"] = frame_index
        for record, time_min in zip(records, scaled_times):
            copied = list(record)
            if len(copied) != frame_index:
                raise ValueError(f"ragged MAT rows are not supported in {experiment_id}")
            copied.append(frame_for_time[time_min])
            patched_records.append(copied)

    patched_spec["column_map"] = patched_mapping
    patched_spec["frame_interval_min_if_time_absent"] = None
    rows, summary = _BASE_NORMALIZE_RECORDS(patched_records, experiment_id, patched_spec)
    summary = {
        **summary,
        "frame_derivation": "global_time_rank",
        "global_frame_count": len(unique_times),
        "time_min_min": unique_times[0],
        "time_min_max": unique_times[-1],
    }
    return rows, summary


def normalize(source_dir: Path, source_manifest_path: Path, schema_lock_path: Path, output_dir: Path) -> dict:
    """Run base normalization with trusted-archive and locked-frame adapters.

    Source digests, schema-lock status, exact source-member mapping and all base
    normalization invariants remain enforced. The only schema adaptation is the
    explicitly frozen ``global_time_rank`` frame reconstruction where requested
    by the committed Dryad schema lock.
    """

    original_validator = base._validate_member
    original_normalizer = base._normalize_records
    base._validate_member = _validate_member
    base._normalize_records = _normalize_records_with_frame_strategy
    try:
        return base.normalize(source_dir, source_manifest_path, schema_lock_path, output_dir)
    finally:
        base._validate_member = original_validator
        base._normalize_records = original_normalizer


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory_parser = subparsers.add_parser("inventory", help="Verify deposited hashes and create schema-only inventory")
    inventory_parser.add_argument("--source-dir", type=Path, required=True)
    inventory_parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("docs/external-biological-context-source-manifest.json"),
    )
    inventory_parser.add_argument("--output", type=Path, required=True)

    normalize_parser = subparsers.add_parser(
        "normalize", help="Normalize all three experiments after the schema lock is committed"
    )
    normalize_parser.add_argument("--source-dir", type=Path, required=True)
    normalize_parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("docs/external-biological-context-source-manifest.json"),
    )
    normalize_parser.add_argument(
        "--schema-lock", type=Path, default=Path("docs/dryad-confirmatory-schema-lock.json")
    )
    normalize_parser.add_argument("--output-dir", type=Path, required=True)

    args = parser.parse_args(argv)
    try:
        if args.command == "inventory":
            result = inventory(args.source_dir, args.source_manifest)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            print(f"Wrote schema-only inventory: {args.output}")
        else:
            result = normalize(args.source_dir, args.source_manifest, args.schema_lock, args.output_dir)
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"Dryad local pipeline failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
