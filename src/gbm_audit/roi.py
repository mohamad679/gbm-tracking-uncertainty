"""Check real GlioTrace ROI shape, crop stability, and channel signal."""

import argparse
import json
from pathlib import Path

import numpy as np

from gbm_audit.cli import sha256_file


def describe_roi(path: Path, expected_frames: int | None = None) -> dict:
    with np.load(path, allow_pickle=False) as content:
        tumor = content["Tstack"]
        vessel = content["Vstack"]
        if tumor.ndim != 3 or tumor.shape != vessel.shape:
            raise ValueError("Tstack and Vstack must have matching 3D shape")
        time, height, width = tumor.shape
        if expected_frames is not None and time != expected_frames:
            raise ValueError(f"First axis {time} differs from metadata frame count {expected_frames}")
        delta = float(content["delta"]) if "delta" in content else None
        b_nonzero = int(np.count_nonzero(content["Bstack"])) if "Bstack" in content else None
        extent = []
        signal = []
        for frame in range(time):
            # Vstack is zero in black padded regions. An active row/column has
            # at least one nonzero pixel; this is a geometric crop diagnostic.
            rows = np.flatnonzero(np.any(vessel[frame] != 0, axis=1))
            cols = np.flatnonzero(np.any(vessel[frame] != 0, axis=0))
            if not len(rows) or not len(cols):
                raise ValueError(f"Vstack frame {frame} is entirely zero")
            top, bottom = int(rows[0]), int(rows[-1]) + 1
            left, right = int(cols[0]), int(cols[-1]) + 1
            extent.append([top, bottom, left, right])
            tissue = tumor[frame, top:bottom, left:right]
            signal.append({"frame": frame, "tumor_max": int(tissue.max()),
                           "tumor_p99": round(float(np.percentile(tissue, 99)), 2),
                           "tumor_pixels_over_100": int(np.count_nonzero(tissue > 100))})
    common = [max(x[0] for x in extent), min(x[1] for x in extent),
              max(x[2] for x in extent), min(x[3] for x in extent)]
    common_area = max(0, common[1] - common[0]) * max(0, common[3] - common[2])
    return {
        "file_name": path.name, "sha256": sha256_file(path),
        "shape_time_height_width": [time, height, width],
        "delta_from_file": delta, "delta_unit": "unverified in source CSV",
        "Bstack_nonzero_pixels": b_nonzero,
        "active_vessel_bbox_first_middle_last": [extent[k] for k in (0, time // 2, time - 1)],
        "common_bbox_all_frames": common,
        "common_rectangular_area_fraction": round(common_area / (height * width), 4),
        "tumor_signal_first_middle_last": [signal[k] for k in (0, time // 2, time - 1)],
        "warning": "Bounding rectangles diagnose black padding, not true tissue coverage or cell track quality."
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("roi", type=Path)
    parser.add_argument("--expected-frames", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = describe_roi(args.roi, args.expected_frames)
    rendered = json.dumps(result, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()
