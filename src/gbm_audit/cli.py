"""Inspect archive inventories and NPZ array headers without loading image volumes."""

import argparse
import hashlib
import json
from pathlib import Path
import sys
from zipfile import BadZipFile, ZipFile

from numpy.lib import format as npformat


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_npz(path: Path, expected_frames: int | None = None) -> dict:
    arrays = []
    with ZipFile(path) as archive:
        for member in archive.infolist():
            if not member.filename.endswith(".npy"):
                continue
            with archive.open(member) as stream:
                major, minor = npformat.read_magic(stream)
                if major == 1:
                    shape, fortran, dtype = npformat.read_array_header_1_0(stream)
                elif major in (2, 3):
                    shape, fortran, dtype = npformat.read_array_header_2_0(stream)
                else:
                    raise ValueError(f"Unsupported NPY version {major}.{minor}")
            arrays.append({
                "name": member.filename,
                "shape": list(shape),
                "dtype": str(dtype),
                "fortran_order": bool(fortran),
                "uncompressed_bytes": member.file_size,
            })
    three_dimensional = [a for a in arrays if len(a["shape"]) == 3]
    same_shape = len(three_dimensional) >= 2 and len({tuple(a["shape"]) for a in three_dimensional}) == 1
    axes = "unverified"
    if expected_frames is not None and three_dimensional:
        shapes = [a["shape"] for a in three_dimensional]
        first = all(shape[0] == expected_frames for shape in shapes)
        last = all(shape[2] == expected_frames for shape in shapes)
        if first != last:
            axes = "time,height,width" if first else "height,width,time"
    return {
        "kind": "npz_headers",
        "arrays": arrays,
        "two_or_more_3d_channels_same_shape": same_shape,
        "axis_interpretation": axes,
        "axis_note": "Compare the frame count with acquisition metadata; never assume axis order from dataset prose.",
        "loaded_pixels": False,
    }


def inspect_zip(path: Path) -> dict:
    with ZipFile(path) as archive:
        items = [m for m in archive.infolist() if not m.is_dir()]
    all_names = [m.filename for m in items]
    names = [n for n in all_names if not n.startswith("__MACOSX/") and not Path(n).name.startswith("._")]
    return {
        "kind": "zip_inventory",
        "files": len(items),
        "data_files_excluding_macos_sidecars": len(names),
        "macos_sidecars": len(items) - len(names),
        "uncompressed_bytes": sum(m.file_size for m in items),
        "npz_files": sum(name.lower().endswith(".npz") for name in names),
        "image_files": sum(name.lower().endswith((".tif", ".tiff")) for name in names),
        "segmentation_reference_paths": [n for n in names if "/SEG/" in "/" + n.replace("\\", "/")],
        "tracking_reference_paths": [n for n in names if "/TRA/" in "/" + n.replace("\\", "/")],
        "csv_files": [n for n in names if n.lower().endswith(".csv")],
        "first_30_paths": names[:30],
        "note": "Path names show availability only; reference completeness and image quality need manual review.",
    }


def inspect(path: Path, expected_frames: int | None = None) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in (".zip", ".npz"):
        raise ValueError("Only .zip and .npz input files are supported")
    result = inspect_npz(path, expected_frames) if path.suffix.lower() == ".npz" else inspect_zip(path)
    return {"file_name": path.name, "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path), **result}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path, help="Existing ZIP or NPZ file")
    parser.add_argument("--output", type=Path, help="JSON output path")
    parser.add_argument("--expected-frames", type=int, help="Frames from independent experimental metadata, for NPZ axis check")
    args = parser.parse_args(argv)
    try:
        result = inspect(args.path, args.expected_frames)
    except (OSError, BadZipFile, ValueError) as exc:
        print(f"Audit failed: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
