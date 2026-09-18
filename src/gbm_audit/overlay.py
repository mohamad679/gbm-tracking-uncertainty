"""Render private diagnostic contact sheets of unverified machine candidates."""

import argparse
import csv
import json
from pathlib import Path

from PIL import Image, ImageDraw


def render(input_dir: Path, proposals_csv: Path, output_dir: Path) -> list[Path]:
    manifest = json.loads((input_dir / "manifest.json").read_text(encoding="utf-8"))
    with proposals_csv.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    if any(row.get("reviewer_id") != "machine_proposal" for row in rows):
        raise ValueError("Overlay accepts only machine proposals, not human labels")
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = []
    for window in manifest["windows"]:
        frames = window["frames"]
        chosen = [frames[0], frames[len(frames) // 2], frames[-1]]
        tiles = []
        top, left, _, _ = window["crop_top_left_bottom_right"]
        for entry in chosen:
            with Image.open(input_dir / entry["images"]["T"]) as opened:
                tile = opened.convert("RGB")
            draw = ImageDraw.Draw(tile)
            for row in rows:
                if row["window_id"] != window["window_id"] or int(row["frame"]) != entry["frame"]:
                    continue
                if row["source_sha256"] != window["source_sha256"]:
                    raise ValueError("Image and candidate CSV have different source hashes")
                x = int(row["x_px"]) - left
                y = int(row["y_px"]) - top
                draw.ellipse((x-7, y-7, x+7, y+7), outline="red", width=2)
                draw.text((x+9, y-9), row["local_cell_id"].replace("candidate_", "c"), fill="yellow")
            tiles.append(tile)
        contact = Image.new("RGB", (sum(tile.width for tile in tiles), max(tile.height for tile in tiles) + 24))
        draw = ImageDraw.Draw(contact)
        offset = 0
        for entry, tile in zip(chosen, tiles):
            contact.paste(tile, (offset, 24))
            draw.text((offset + 5, 5), f'frame {entry["frame"]} — unverified proposals', fill="yellow")
            offset += tile.width
        target = output_dir / f'{window["window_id"]}.png'
        contact.save(target)
        outputs.append(target)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("results/stage1-viewer"))
    parser.add_argument("--csv", type=Path, default=Path("results/stage1-machine-proposals.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/stage1-machine-review"))
    args = parser.parse_args()
    for path in render(args.input_dir, args.csv, args.output_dir):
        print(path)


if __name__ == "__main__":
    main()
