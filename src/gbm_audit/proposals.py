"""Produce conservative machine track proposals, NEVER reference annotations.

Uses fixed-window displayed tumour images, local maxima, and nearest-neighbour
links. A human must adjudicate identities; no biological conclusion follows.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter


FIELDS = ("reviewer_id", "window_id", "mouse", "experiment", "roi",
          "source_sha256", "frame", "local_cell_id", "x_px", "y_px",
          "visibility", "uncertain", "reason", "difficulty", "provenance")


def peaks(png: Path, max_peaks: int = 40) -> list[tuple[int, int, int]]:
    """Detect only isolated conspicuous peaks, not a cell segmentation mask."""
    with Image.open(png) as raw:
        smoothed = raw.convert("L").filter(ImageFilter.GaussianBlur(1.5))
        bright = np.asarray(smoothed)
        local_max = np.asarray(smoothed.filter(ImageFilter.MaxFilter(13)))
    threshold = max(45.0, float(np.percentile(bright, 99.7)))
    ys, xs = np.where((bright == local_max) & (bright > threshold))
    candidates = sorted(((int(bright[y, x]), int(x), int(y)) for y, x in zip(ys, xs)),
                        key=lambda item: (-item[0], item[2], item[1]))
    selected: list[tuple[int, int, int]] = []
    for intensity, x, y in candidates:
        if min(x, y, bright.shape[1] - 1 - x, bright.shape[0] - 1 - y) < 12:
            continue
        if all((x - sx) ** 2 + (y - sy) ** 2 >= 14 ** 2
               for sx, sy, _ in selected):
            selected.append((x, y, intensity))
            if len(selected) >= max_peaks:
                break
    return selected


def link_frames(detections: list[tuple[int, list[tuple[int, int, int]]]],
                max_step: float = 16.0) -> list[list[tuple[int, int, int, int]]]:
    """Greedy one-to-one association; never bridge a missing frame."""
    tracks: list[list[tuple[int, int, int, int]]] = []
    for frame, observed in detections:
        active = [i for i, track in enumerate(tracks) if track[-1][0] == frame - 1]
        pairs = []
        for index in active:
            _, px, py, _ = tracks[index][-1]
            for j, (x, y, _) in enumerate(observed):
                distance = float(np.hypot(px - x, py - y))
                if distance <= max_step:
                    pairs.append((distance, index, j))
        assigned_tracks, assigned_points = set(), set()
        for _, i, j in sorted(pairs):
            if i not in assigned_tracks and j not in assigned_points:
                x, y, score = observed[j]
                tracks[i].append((frame, x, y, score))
                assigned_tracks.add(i)
                assigned_points.add(j)
        for j, (x, y, score) in enumerate(observed):
            if j not in assigned_points:
                tracks.append([(frame, x, y, score)])
    return tracks


def propose(input_dir: Path, min_track_frames: int = 6) -> tuple[list[dict], dict]:
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "prepared_only_not_annotated":
        raise ValueError("Expected the unannotated four-window pilot manifest")
    rows, summary = [], {"origin": "machine_proposal_not_ground_truth", "windows": []}
    for window in manifest["windows"]:
        first, last = window["first_frame"], window["last_frame_inclusive"]
        if [item["frame"] for item in window["frames"]] != list(range(first, last + 1)):
            raise ValueError("Non-consecutive or incomplete window")
        detections = []
        for image in window["frames"]:
            name = input_dir / image["images"]["T"]
            detections.append((image["frame"], peaks(name)))
        tracks = [track for track in link_frames(detections) if len(track) >= min_track_frames]
        top, left, bottom, right = window["crop_top_left_bottom_right"]
        for track_id, track in enumerate(tracks, start=1):
            for frame, x, y, _ in track:
                if not (left <= x + left < right and top <= y + top < bottom):
                    raise ValueError("Proposed coordinate outside source crop")
                rows.append({
                    "reviewer_id": "machine_proposal", "window_id": window["window_id"],
                    "mouse": window["mouse"], "experiment": window["experiment"],
                    "roi": window["roi"], "source_sha256": window["source_sha256"],
                    "frame": frame, "local_cell_id": f"candidate_{track_id:03d}",
                    "x_px": x + left, "y_px": y + top, "visibility": "present",
                    "uncertain": "yes", "reason": "machine_unverified",
                    "difficulty": "unreviewed", "provenance": "PIL blur and local maxima; greedy nearest neighbour"
                })
        summary["windows"].append({"window_id": window["window_id"],
                                   "peaks_per_frame": [len(points) for _, points in detections],
                                   "tracks_reaching_minimum": len(tracks),
                                   "proposed_points": sum(map(len, tracks))})
    return rows, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("results/stage1-viewer"))
    parser.add_argument("--output", type=Path, default=Path("results/stage1-machine-proposals.csv"))
    args = parser.parse_args()
    rows, summary = propose(args.input_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))
    print(f"Saved {len(rows)} machine-only points to {args.output}")


if __name__ == "__main__":
    main()
