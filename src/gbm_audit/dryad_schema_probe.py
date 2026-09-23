"""Schema-only evidence probe for the frozen Dryad confirmatory source.

This command is intentionally pre-outcome. It verifies the deposited source identity,
inspects legacy XLS headers/sample rows, records small numeric samples from the two
MATLAB ``StoreData`` tracking matrices, extracts schema-relevant MATLAB source-code
contexts, and extracts the deposited README text. It does not compute association,
tracking, calibration, motion, or any other method-performance metric.
"""

from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from gbm_audit import dryad_local as base


TRACKING_XLS_MEMBERS = [
    "To Generate Figures/Data/AllCombined/3-14-11_Tumor_Tracking_Data.xls",
    "To Generate Figures/Data/AllCombined/5-16-11_Tumor_Tracking_Data.xls",
]
TRACKING_MAT_MEMBERS = [
    "To Generate Figures/Data/AllCombined/3-14-11_Tumor_Tracking_Data.mat",
    "To Generate Figures/Data/AllCombined/6-6-11_Tumor_Tracking_Data.mat",
]
README_NAME = base.REQUIRED_README
CODE_PREFIX = "To Generate Figures/Code/"
CODE_TERMS = re.compile(r"StoreData|Tracking_Data|xlsread|readtable|load\s*\(|frame|time", re.IGNORECASE)


def _xls_preview(data: bytes) -> dict[str, Any]:
    try:
        import xlrd  # type: ignore
    except ImportError as exc:
        raise ValueError("legacy XLS schema probe requires `pip install xlrd>=2.0,<3`") from exc

    workbook = xlrd.open_workbook(file_contents=data, on_demand=True)
    sheets = []
    for sheet_name in workbook.sheet_names()[:20]:
        sheet = workbook.sheet_by_name(sheet_name)
        rows = []
        for row_index in range(min(sheet.nrows, 12)):
            values = []
            for col_index in range(min(sheet.ncols, 20)):
                value = sheet.cell_value(row_index, col_index)
                values.append(value)
            rows.append(values)
        sheets.append(
            {
                "name": sheet_name,
                "nrows": int(sheet.nrows),
                "ncols": int(sheet.ncols),
                "sample_rows": rows,
            }
        )
    workbook.release_resources()
    return {"kind": "xls", "sheets": sheets}


def _mat_preview(data: bytes) -> dict[str, Any]:
    try:
        import scipy.io  # type: ignore
    except ImportError as exc:
        raise ValueError("MAT schema probe requires scipy") from exc

    payload = scipy.io.loadmat(io.BytesIO(data), squeeze_me=False)
    if "StoreData" not in payload:
        raise ValueError("expected StoreData variable is absent")
    array = payload["StoreData"]
    if getattr(array, "ndim", None) != 2:
        raise ValueError("StoreData is not a 2D matrix")
    rows = array[: min(int(array.shape[0]), 12), : min(int(array.shape[1]), 12)].tolist()
    return {
        "kind": "mat",
        "variable": "StoreData",
        "shape": [int(value) for value in array.shape],
        "dtype": str(array.dtype),
        "sample_rows": rows,
    }


def _context_matches(text: str, *, context: int = 2, max_matches: int = 80) -> list[dict[str, Any]]:
    lines = text.splitlines()
    matches = []
    for index, line in enumerate(lines):
        if not CODE_TERMS.search(line):
            continue
        start = max(0, index - context)
        end = min(len(lines), index + context + 1)
        matches.append(
            {
                "line_number": index + 1,
                "context_start": start + 1,
                "context_end": end,
                "lines": lines[start:end],
            }
        )
        if len(matches) >= max_matches:
            break
    return matches


def _docx_text(path: Path) -> str:
    if not path.is_file():
        raise ValueError(f"README file missing: {path}")
    with zipfile.ZipFile(path) as archive:
        try:
            xml_bytes = archive.read("word/document.xml")
        except KeyError as exc:
            raise ValueError("deposited README is not a readable DOCX document") from exc
    root = ET.fromstring(xml_bytes)
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(ns + "p"):
        parts = [node.text or "" for node in paragraph.iter(ns + "t")]
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return "\n".join(paragraphs)


def probe(source_dir: Path, source_manifest_path: Path) -> dict[str, Any]:
    identity = base.verify_source_dir(source_dir, source_manifest_path, require_readme=True)
    bundle_path = source_dir / base.REQUIRED_BUNDLE
    xls = {}
    mat = {}
    code_evidence = []

    with zipfile.ZipFile(bundle_path) as archive:
        names = set(archive.namelist())
        for member in TRACKING_XLS_MEMBERS:
            if member not in names:
                raise ValueError(f"required schema-evidence XLS missing: {member}")
            xls[member] = _xls_preview(archive.read(member))

        for member in TRACKING_MAT_MEMBERS:
            if member not in names:
                raise ValueError(f"required schema-evidence MAT missing: {member}")
            mat[member] = _mat_preview(archive.read(member))

        for info in archive.infolist():
            if info.is_dir() or not info.filename.startswith(CODE_PREFIX) or not info.filename.lower().endswith(".m"):
                continue
            if info.file_size <= 0 or info.file_size > 2_000_000:
                continue
            text = archive.read(info).decode("utf-8", errors="replace")
            matches = _context_matches(text)
            if matches:
                code_evidence.append({"path": info.filename, "matches": matches})

    readme_text = _docx_text(source_dir / README_NAME)
    return {
        "schema_version": 1,
        "status": "SCHEMA_EVIDENCE_COMPLETE_NO_METHOD_OUTCOMES",
        "boundary": (
            "Schema/documentation inspection only. No association, calibration, tracking, motion, "
            "or method-comparison metric is computed."
        ),
        "source_identity": identity,
        "tracking_xls": xls,
        "tracking_mat": mat,
        "matlab_code_schema_evidence": code_evidence,
        "deposited_readme_text": readme_text,
        "next_gate": (
            "Review this evidence together with source-inventory.json; only then may the exact "
            "three-experiment schema mapping be committed as LOCKED."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("docs/external-biological-context-source-manifest.json"),
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    try:
        result = probe(args.source_dir, args.source_manifest)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Wrote Dryad schema-only evidence: {args.output}")
    except (OSError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print(f"Dryad schema probe failed: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
