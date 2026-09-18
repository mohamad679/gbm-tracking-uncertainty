"""Prepare private, fixed-window images for blinded human track annotation.

Generated images and annotations stay in results/ (ignored by Git).  This tool
does not detect cells or create ground-truth identity links.
"""

import argparse
import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
from PIL import Image


SAMPLES = (
    ("Set_67", 333, 84, (5, 14), (50, 59)),
    ("Set_68", 337, 63, (5, 14), (53, 62)),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _frame_bbox(frame: np.ndarray) -> tuple[int, int, int, int]:
    rows = np.flatnonzero(np.any(frame != 0, axis=1))
    cols = np.flatnonzero(np.any(frame != 0, axis=0))
    if not len(rows) or not len(cols):
        raise ValueError("Blank Vstack frame: cannot estimate visible rectangle")
    return int(rows[0]), int(rows[-1]) + 1, int(cols[0]), int(cols[-1]) + 1


def prepare_window(source: Path, dest: Path, mouse: str, exp: int, roi: int,
                   label: str, first: int, last: int) -> dict:
    """Build a frame viewer from a stable Vstack bounding rectangle."""
    with np.load(source, allow_pickle=False) as data:
        tumor, vessel = data["Tstack"], data["Vstack"]
        if tumor.ndim != 3 or tumor.shape != vessel.shape or last >= tumor.shape[0]:
            raise ValueError("Invalid channel shapes or selected frame interval")
        if first < 0 or first >= last:
            raise ValueError("Select consecutive, increasing frame numbers")
        boxes = [_frame_bbox(vessel[frame]) for frame in range(first, last + 1)]
        top = max(box[0] for box in boxes)
        bottom = min(box[1] for box in boxes)
        left = max(box[2] for box in boxes)
        right = min(box[3] for box in boxes)
        if bottom - top < 128 or right - left < 128:
            raise ValueError("Shared rectangle is too small for this pilot")
        window_id = f"{mouse.lower()}-exp{exp}-roi{roi}-{label}"
        frames_dir = dest / "frames" / window_id
        frames_dir.mkdir(parents=True, exist_ok=True)
        slices = np.s_[first:last + 1, top:bottom, left:right]
        # One channel range per window avoids artificial frame-to-frame flicker.
        limits = {
            "T": max(1.0, float(np.percentile(tumor[slices], 99.9))),
            "V": max(1.0, float(np.percentile(vessel[slices], 99.9))),
        }
        files = []
        for frame in range(first, last + 1):
            paths = {}
            for name, channel in (("T", tumor), ("V", vessel)):
                cropped = channel[frame, top:bottom, left:right]
                scaled = np.uint8(np.clip(cropped.astype(np.float32) *
                                          (255.0 / limits[name]), 0, 255))
                filename = f"{name}_{frame:03d}.png"
                Image.fromarray(scaled, mode="L").save(frames_dir / filename)
                paths[name] = f"frames/{window_id}/{filename}"
            files.append({"frame": frame, "images": paths})
    return {
        "window_id": window_id, "mouse": mouse, "experiment": exp, "roi": roi,
        "label": label, "source_filename": source.name, "source_sha256": _sha256(source),
        "first_frame": first, "last_frame_inclusive": last,
        "image_shape_time_height_width": list(tumor.shape),
        "crop_top_left_bottom_right": [top, left, bottom, right],
        "crop_fraction_of_original_frame": round((bottom-top)*(right-left)/
                                                 (tumor.shape[1]*tumor.shape[2]), 4),
        "display_p999_raw": limits,
        "frames": files,
        "note": "Vstack bounding rectangle is a crop diagnostic, not proof all enclosed pixels show tissue. Check black edges by eye."
    }


def prepare(raw_dir: Path, output: Path) -> dict:
    if output.resolve() == raw_dir.resolve() or raw_dir.resolve() in output.resolve().parents:
        raise ValueError("Output cannot be inside the raw data directory")
    output.mkdir(parents=True, exist_ok=True)
    windows = []
    for mouse, exp, roi, early, late in SAMPLES:
        source = raw_dir / mouse / f"exp_{exp}_roi_{roi}_stack.npz"
        if not source.is_file():
            raise FileNotFoundError(f"Missing {source}; run scripts/fetch_pilot_rois.py")
        for label, interval in (("early", early), ("late", late)):
            windows.append(prepare_window(source, output, mouse, exp, roi,
                                          label, *interval))
    manifest = {
        "schema_version": 1, "status": "prepared_only_not_annotated",
        "window_selection": "Four ten-frame intervals fixed before model evaluation; zero-based frames.",
        "coordinate_system": "x/y in original 501x501 source frame; crop offset is recorded per window.",
        "time_and_pixel_units": "unverified; use frames and pixels only",
        "windows": windows,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    viewer = Path(__file__).with_name("annotation_viewer.html")
    html = viewer.read_text(encoding="utf-8").replace("__MANIFEST_JSON__", json.dumps(manifest).replace("<", "\\u003c"))
    (output / "index.html").write_text(html, encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw/glio_trace"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/stage1-viewer"))
    args = parser.parse_args()
    manifest = prepare(args.raw_dir, args.output_dir)
    print("Prepared", len(manifest["windows"]), "windows; open", args.output_dir / "index.html")
    for item in manifest["windows"]:
        print(item["window_id"], f'{item["first_frame"]}-{item["last_frame_inclusive"]}',
              "shared rectangle fraction", item["crop_fraction_of_original_frame"])


if __name__ == "__main__":
    main()
