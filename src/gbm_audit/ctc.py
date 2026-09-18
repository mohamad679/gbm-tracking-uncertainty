"""Profile the real U373 reference tracks without claiming brain-slice validity."""

import argparse
from io import BytesIO
import json
from pathlib import Path
import re
import statistics
from zipfile import ZipFile

import numpy as np
from PIL import Image

from gbm_audit.cli import sha256_file


def profile(path: Path) -> dict:
    with ZipFile(path) as archive:
        files = set(archive.namelist())
        images = {}
        for name in files:
            match = re.fullmatch(r"([^/]+)/([0-9]+)/t([0-9]+)\.tif", name)
            if match:
                root, seq, time = match.groups()
                images.setdefault((root, seq), {})[int(time)] = name
        if not images:
            raise ValueError("No CTC sequence images found")

        sequences = {}
        for (root, seq), time_to_path in sorted(images.items()):
            centers = {}
            for time, img_path in sorted(time_to_path.items()):
                mask_path = f"{root}/{seq}_GT/TRA/man_track{time:03d}.tif"
                if mask_path not in files:
                    raise ValueError(f"Missing gold tracking mask: {mask_path}")
                with Image.open(BytesIO(archive.read(img_path))) as im:
                    image_shape = np.asarray(im).shape
                with Image.open(BytesIO(archive.read(mask_path))) as im:
                    mask = np.asarray(im)
                if image_shape != mask.shape:
                    raise ValueError(f"Image/mask shape mismatch at {seq}:{time}")
                for label in np.unique(mask):
                    if label == 0:
                        continue
                    ys, xs = np.where(mask == label)
                    centers.setdefault(int(label), []).append((time, float(xs.mean()), float(ys.mean())))

            displacements = []
            lengths = []
            for track in centers.values():
                lengths.append(len(track))
                for a, b in zip(track, track[1:]):
                    if b[0] - a[0] == 1:
                        displacements.append(float(np.hypot(b[1] - a[1], b[2] - a[2])))
            seg_prefix = f"{root}/{seq}_GT/SEG/man_seg"
            lineage_path = f"{root}/{seq}_GT/TRA/man_track.txt"
            if lineage_path not in files:
                raise ValueError(f"Missing lineage table for sequence {seq}")
            sequences[seq] = {
                "frames": len(time_to_path),
                "shape_pixels": list(image_shape),
                "gold_tracking_masks": len(time_to_path),
                "gold_segmentation_masks": sum(n.startswith(seg_prefix) and n.endswith(".tif") for n in files),
                "lineage_rows": len(archive.read(lineage_path).splitlines()),
                "tracked_ids": len(centers),
                "median_observed_track_frames": statistics.median(lengths),
                "consecutive_steps": len(displacements),
                "median_step_pixels_per_frame": round(statistics.median(displacements), 3),
            }
    return {"dataset": "CTC PhC-C2DH-U373 training", "sha256": sha256_file(path),
            "source": "https://celltrackingchallenge.net/2d-datasets/", "sequences": sequences,
            "warning": "A technical tracking benchmark in 2D phase contrast, not a brain-slice biological validation."}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = profile(args.archive)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
