"""Generate deterministic, truth-known corruptions of reference tracks."""

import argparse
import copy
import hashlib
import json
from pathlib import Path
import random
import sys

from gbm_audit.config import DEFAULT_RANDOM_SEED


def _manifest_digest(manifest: dict) -> str:
    payload = json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _reference_records(sequence: dict) -> list[dict]:
    records = []
    for track in sequence["tracks"]:
        for point in track["observations"]:
            observation_id = f"ref_{track['track_id']:04d}_{point['frame']:04d}"
            records.append({
                "observation_id": observation_id,
                "frame": point["frame"],
                "observed_track_id": track["track_id"],
                "x_px": point["x_px"],
                "y_px": point["y_px"],
                "area_px": point["area_px"],
            })
    return sorted(records, key=lambda row: (row["frame"], row["observed_track_id"]))


def _truth(reference: list[dict], observed: list[dict]) -> list[dict]:
    observed_ids = {row["observation_id"] for row in observed}
    result = []
    for row in reference:
        result.append({
            "observation_id": row["observation_id"],
            "frame": row["frame"],
            "true_track_id": row["observed_track_id"],
            "observed": row["observation_id"] in observed_ids,
        })
    for row in observed:
        if not row["observation_id"].startswith("ref_"):
            result.append({
                "observation_id": row["observation_id"],
                "frame": row["frame"],
                "true_track_id": 0,
                "observed": True,
            })
    return sorted(result, key=lambda row: (row["frame"], row["observation_id"]))


def _association_pairs(reference: list[dict]) -> list[tuple[int, int, list[int]]]:
    """Return track pairs with their overlapping frames, in deterministic order."""
    track_ids = sorted({row["observed_track_id"] for row in reference})
    result = []
    for index in range(0, len(track_ids) - 1, 2):
        left, right = track_ids[index], track_ids[index + 1]
        left_frames = {row["frame"] for row in reference if row["observed_track_id"] == left}
        right_frames = {row["frame"] for row in reference if row["observed_track_id"] == right}
        overlap = sorted(left_frames & right_frames)
        if overlap:
            result.append((left, right, overlap))
    return result


def _scenario(sequence: dict, corruption: str, severity, seed: int) -> dict:
    reference = _reference_records(sequence)
    observed = copy.deepcopy(reference)
    rng = random.Random(seed)
    shape_y, shape_x = sequence["shape_pixels"]
    parameters = {"severity": severity}

    if corruption == "clean":
        pass
    elif corruption == "missed_detection":
        rate = float(severity)
        parameters["removal_rate"] = rate
        kept = []
        for track_id in sorted({row["observed_track_id"] for row in reference}):
            track_rows = [row for row in observed if row["observed_track_id"] == track_id]
            remove_count = min(max(0, int(round(len(track_rows) * rate))), max(0, len(track_rows) - 1))
            removed = set(rng.sample([row["observation_id"] for row in track_rows], remove_count))
            kept.extend(row for row in track_rows if row["observation_id"] not in removed)
        observed = kept
    elif corruption == "localization_noise":
        sigma = float(severity)
        parameters["sigma_px"] = sigma
        for row in observed:
            row["x_px"] = round(min(max(0.0, row["x_px"] + rng.gauss(0, sigma)), shape_x - 1), 6)
            row["y_px"] = round(min(max(0.0, row["y_px"] + rng.gauss(0, sigma)), shape_y - 1), 6)
    elif corruption == "fragmentation":
        gap = int(severity)
        parameters["gap_frames"] = gap
        for track_id in sorted({row["observed_track_id"] for row in reference}):
            rows = [row for row in observed if row["observed_track_id"] == track_id]
            if gap <= 0 or len(rows) <= gap + 2:
                continue
            start = rows[len(rows) // 2]["frame"]
            removed_frames = set(range(start, start + gap))
            for row in rows:
                if row["frame"] in removed_frames:
                    observed.remove(row)
                elif row["frame"] >= start + gap:
                    row["observed_track_id"] = track_id * 100 + 1
    elif corruption == "id_switch":
        events = int(severity)
        parameters["events"] = events
        for left, right, overlap in _association_pairs(reference)[:events]:
            boundary = overlap[len(overlap) // 2]
            for row in observed:
                if row["frame"] > boundary and row["observed_track_id"] == left:
                    row["observed_track_id"] = right
                elif row["frame"] > boundary and row["observed_track_id"] == right:
                    row["observed_track_id"] = left
    elif corruption == "wrong_link":
        events = int(severity)
        parameters["events"] = events
        # A local one-frame association error: swap the paired identities only
        # at the selected boundary frame, without a persistent downstream switch.
        for left, right, overlap in _association_pairs(reference)[:events]:
            boundary = overlap[len(overlap) // 2]
            for row in observed:
                if row["frame"] != boundary:
                    continue
                if row["observed_track_id"] == left:
                    row["observed_track_id"] = right
                elif row["observed_track_id"] == right:
                    row["observed_track_id"] = left
    elif corruption == "false_positive":
        count = int(severity)
        parameters["count"] = count
        for index in range(count):
            frame = rng.randrange(sequence["frames"])
            observed.append({
                "observation_id": f"fp_{index:04d}",
                "frame": frame,
                "observed_track_id": 100000 + index,
                "x_px": round(rng.uniform(0, shape_x - 1), 6),
                "y_px": round(rng.uniform(0, shape_y - 1), 6),
                "area_px": 1,
            })
    else:
        raise ValueError(f"Unknown corruption: {corruption}")

    observed = sorted(observed, key=lambda row: (row["frame"], row["observed_track_id"], row["observation_id"]))
    return {
        "sequence_id": sequence["sequence_id"],
        "split": sequence["split"],
        "frames": sequence["frames"],
        "shape_pixels": sequence["shape_pixels"],
        "observations": observed,
        "evaluation_truth": _truth(reference, observed),
        "parameters": parameters,
    }


def build_corruption_benchmark(manifest: dict, seed: int = DEFAULT_RANDOM_SEED) -> dict:
    """Create all fixed-seed corruption scenarios from a reference manifest."""
    levels = [
        ("clean", [0]),
        ("missed_detection", [0.10, 0.25, 0.50]),
        ("localization_noise", [1.0, 3.0, 5.0]),
        ("fragmentation", [1, 3, 5]),
        ("id_switch", [1, 2]),
        ("wrong_link", [1, 2]),
        ("false_positive", [5, 10, 20]),
    ]
    scenarios = []
    scenario_index = 0
    for corruption, severities in levels:
        for severity in severities:
            sequence_results = {}
            for sequence_id in sorted(manifest["sequences"]):
                scenario_seed = seed + scenario_index * 1000 + int(sequence_id)
                sequence_results[sequence_id] = _scenario(
                    manifest["sequences"][sequence_id], corruption, severity, scenario_seed)
            scenarios.append({
                "scenario_id": f"{corruption}_{str(severity).replace('.', 'p')}",
                "corruption": corruption,
                "severity": severity,
                "seed": seed + scenario_index * 1000,
                "input_kind": "track_table_with_observed_ids",
                "truth_policy": "evaluation_truth is held out from tracker input",
                "sequences": sequence_results,
            })
            scenario_index += 1
    return {
        "schema_version": 1,
        "dataset": manifest["dataset"],
        "reference_manifest_sha256": _manifest_digest(manifest),
        "seed": seed,
        "severity_policy": "Higher severity means more removals, larger localization sigma, longer gaps, more association events, or more false positives within each corruption family.",
        "scenarios": scenarios,
        "warning": "Synthetic corruptions have known truth and benchmark robustness; they do not replace biological validation or human review of GlioTrace.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_RANDOM_SEED)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        result = build_corruption_benchmark(manifest, args.seed)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Corruption benchmark failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['scenarios'])} scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
