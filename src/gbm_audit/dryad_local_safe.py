"""Hardened local Dryad inventory wrapper.

The deposited Dryad archive contains macOS AppleDouble/metadata members such as
``__MACOSX/.../._name.xlsx``.  Those files inherit the suffix of the original
file but are not real workbooks.  Treating them as candidate tables causes
``openpyxl`` to raise ``BadZipFile`` even though the outer Dryad ZIP is valid.

This wrapper keeps the original fail-closed normalization logic, while making
schema-only inventory robust to known archive metadata and to individual table
preview failures.  Preview failures are recorded; they never silently become
normalization inputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath
import sys
import zipfile

from gbm_audit import dryad_local as base


def _is_macos_metadata(name: str) -> bool:
    path = PurePosixPath(name)
    return "__MACOSX" in path.parts or path.name.startswith("._") or path.name == ".DS_Store"


def inspect_bundle(bundle_path: Path) -> dict:
    members: list[dict] = []
    candidate_tables: list[dict] = []
    ignored_metadata_members = 0

    with zipfile.ZipFile(bundle_path) as archive:
        infos = archive.infolist()
        if len(infos) > base.MAX_MEMBERS:
            raise ValueError(f"archive has too many members: {len(infos)}")

        total = 0
        for info in infos:
            base._validate_member(info)
            total += info.file_size
            if total > base.MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("archive exceeds total uncompressed-size limit")

            suffix = Path(info.filename).suffix.lower()
            metadata_only = _is_macos_metadata(info.filename)
            if metadata_only:
                ignored_metadata_members += 1

            is_candidate = suffix in base.TABLE_SUFFIXES and not metadata_only and not info.is_dir()
            row = {
                "path": info.filename,
                "suffix": suffix,
                "uncompressed_bytes": info.file_size,
                "compressed_bytes": info.compress_size,
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
            result = base.normalize(args.source_dir, args.source_manifest, args.schema_lock, args.output_dir)
            print(json.dumps(result, indent=2, ensure_ascii=False))
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"Dryad local pipeline failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
