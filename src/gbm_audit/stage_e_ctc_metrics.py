"""Supplementary CTC TRA/LNK evaluation for the frozen Stage E linkers.

The exporter deliberately reuses the public CTC gold tracking masks as fixed
object detections and changes only their track identities according to the
frozen hard or uncertainty-aware links.  Therefore LNK is the primary metric;
TRA is interpreted as tracking-graph accuracy under fixed perfect detections,
not as an end-to-end segmentation-and-tracking score.

This is a post-closure supplementary evaluation.  It performs no fitting,
threshold selection, or decision retuning and never changes the published
Stage E REVISE/GO decision.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import json
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile

import numpy as np
from PIL import Image

from gbm_audit.archive import read_member_bytes, validate_zip_archive
from gbm_audit.baseline import nearest_neighbor
from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.stage_e_data import _dataset_entry, build_locked_test_manifest, load_stage_e_contract
from gbm_audit.stage_e_evaluation import (
    HYPOTHESIS_COUNT,
    _assignment_links,
    _compatible_posterior_links,
    _dataset_seed,
    _frozen_dataset_config,
)
from gbm_audit.uncertainty import evaluate_sequence


REAL_CONFIRMATORY_DATASETS = (
    "CTC_Fluo-N2DH-GOWT1_training",
    "CTC_DIC-C2DH-HeLa_training",
)


def _track_assignments(observations: list[dict], links: set[tuple[str, str]]) -> tuple[dict[str, int], list[dict]]:
    """Convert a one-to-one forward link set into deterministic CTC track IDs."""
    rows = {row["observation_id"]: row for row in observations}
    outgoing: dict[str, str] = {}
    incoming: dict[str, str] = {}
    for left, right in sorted(links):
        if left not in rows or right not in rows:
            raise ValueError("link references an unknown observation")
        if int(rows[right]["frame"]) <= int(rows[left]["frame"]):
            raise ValueError("CTC export requires forward-in-time links")
        if left in outgoing or right in incoming:
            raise ValueError("CTC export requires one-to-one links")
        outgoing[left] = right
        incoming[right] = left

    order = sorted(rows, key=lambda observation_id: (int(rows[observation_id]["frame"]), observation_id))
    starts = [observation_id for observation_id in order if observation_id not in incoming]
    assignments: dict[str, int] = {}
    tracks: list[dict] = []

    def consume(start: str, track_id: int) -> None:
        chain = []
        current = start
        while current not in assignments:
            assignments[current] = track_id
            chain.append(current)
            if current not in outgoing:
                break
            current = outgoing[current]
        frames = [int(rows[observation_id]["frame"]) for observation_id in chain]
        tracks.append({
            "track_id": track_id,
            "start_frame": min(frames),
            "end_frame": max(frames),
            "parent_id": 0,
            "observation_count": len(chain),
        })

    next_track_id = 1
    for start in starts:
        if start in assignments:
            continue
        consume(start, next_track_id)
        next_track_id += 1
    for observation_id in order:
        if observation_id not in assignments:
            consume(observation_id, next_track_id)
            next_track_id += 1
    return assignments, tracks


def _extract_gt_tra(archive_path: Path, sequence_id: str, gt_dir: Path) -> dict[int, str]:
    """Extract the CTC gold TRA directory and return frame-to-member paths."""
    if gt_dir.exists():
        shutil.rmtree(gt_dir)
    (gt_dir / "TRA").mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path) as archive:
        validate_zip_archive(archive)
        names = archive.namelist()
        suffix = f"/{sequence_id}_GT/TRA/man_track.txt"
        lineage = [name for name in names if name.endswith(suffix)]
        if len(lineage) != 1:
            raise ValueError(f"expected exactly one lineage table for sequence {sequence_id}")
        prefix = lineage[0][:-len("man_track.txt")]
        frame_members: dict[int, str] = {}
        for name in names:
            if not name.startswith(prefix):
                continue
            relative = name[len(prefix):]
            if relative == "man_track.txt":
                (gt_dir / "TRA" / relative).write_bytes(read_member_bytes(archive, name))
                continue
            if relative.startswith("man_track") and relative.endswith(".tif"):
                frame_text = relative[len("man_track"):-4]
                if not frame_text.isdigit():
                    continue
                frame = int(frame_text)
                frame_members[frame] = name
                (gt_dir / "TRA" / relative).write_bytes(read_member_bytes(archive, name))
        if not frame_members:
            raise ValueError(f"no gold tracking masks found for sequence {sequence_id}")
    return frame_members


def export_fixed_detection_ctc_result(archive_path: Path, sequence_id: str,
                                      observations: list[dict], links: set[tuple[str, str]],
                                      output_root: Path, method_name: str) -> tuple[Path, Path, dict]:
    """Export predicted links in CTC format using unchanged gold object masks."""
    gt_dir = output_root / f"{sequence_id}_GT"
    res_dir = output_root / f"{sequence_id}_{method_name}_RES"
    frame_members = _extract_gt_tra(archive_path, sequence_id, gt_dir)
    if res_dir.exists():
        shutil.rmtree(res_dir)
    res_dir.mkdir(parents=True, exist_ok=True)

    assignments, tracks = _track_assignments(observations, links)
    with ZipFile(archive_path) as archive:
        for frame, member in sorted(frame_members.items()):
            with Image.open(BytesIO(read_member_bytes(archive, member))) as image:
                reference_mask = np.asarray(image)
            result_mask = np.zeros(reference_mask.shape, dtype=np.uint16)
            for label in np.unique(reference_mask):
                label = int(label)
                if label == 0:
                    continue
                observation_id = f"ref_{label:04d}_{frame:04d}"
                predicted_track = assignments.get(observation_id)
                if predicted_track is not None:
                    result_mask[reference_mask == label] = predicted_track
            Image.fromarray(result_mask).save(res_dir / f"mask{frame:03d}.tif")

    track_lines = [
        f"{row['track_id']} {row['start_frame']} {row['end_frame']} {row['parent_id']}"
        for row in tracks
    ]
    (res_dir / "res_track.txt").write_text("\n".join(track_lines) + "\n", encoding="utf-8")
    return gt_dir, res_dir, {
        "predicted_track_count": len(tracks),
        "observation_count": len(observations),
        "link_count": len(links),
        "division_model": "none; all exported parent IDs are zero",
        "detection_policy": "gold CTC tracking masks relabeled only; object shapes and detections are fixed",
    }


def _jsonable(value):
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _ctc_scores(gt_dir: Path, res_dir: Path) -> dict:
    try:
        from ctc_metrics.scripts.evaluate import evaluate_sequence as ctc_evaluate_sequence
    except ImportError as exc:  # pragma: no cover - optional scientific evaluator
        raise RuntimeError(
            "py-ctcmetrics is required for CTC TRA/LNK scoring; install py-ctcmetrics"
        ) from exc
    result = ctc_evaluate_sequence(
        str(res_dir), str(gt_dir), metrics=["Valid", "TRA", "LNK"], threads=1
    )
    result = _jsonable(result)
    if result.get("Valid") != 1:
        raise ValueError(f"CTC result failed format validation: {res_dir}")
    return {key: result[key] for key in result if key in {
        "Valid", "TRA", "LNK", "AOGM", "AOGM_0",
        "AOGM_NS", "AOGM_FN", "AOGM_FP", "AOGM_ED", "AOGM_EA", "AOGM_EC"
    }}


def evaluate_stage_e_ctc_metrics(manifest: dict, development: dict,
                                 archives: dict[str, Path], output_root: Path) -> dict:
    """Score frozen clean-sequence-02 hard and uncertainty-aware links with CTC metrics."""
    dataset_ids = sorted(archives)
    expected = set(REAL_CONFIRMATORY_DATASETS)
    if set(dataset_ids) != expected:
        raise ValueError(f"CTC metric panel requires exactly the two real confirmatory datasets: {sorted(expected)}")

    results = {}
    for dataset_id in dataset_ids:
        dataset = _dataset_entry(manifest, dataset_id)
        test_manifest = build_locked_test_manifest(archives[dataset_id], dataset)
        sequence = test_manifest["sequences"]["02"]
        config = _frozen_dataset_config(development, dataset_id)
        seed = _dataset_seed(dataset_id, list(REAL_CONFIRMATORY_DATASETS) + ["CTC_Fluo-N2DH-SIM+_training"])
        corruptions = build_corruption_benchmark(test_manifest, seed)
        clean = next(row for row in corruptions["scenarios"] if row["scenario_id"] == "clean_0")
        clean_sequence = clean["sequences"]["02"]

        hard_assignments = nearest_neighbor(clean_sequence["observations"], config["max_distance_px"])
        hard_links = _assignment_links(clean_sequence["observations"], hard_assignments)
        uncertainty = evaluate_sequence(
            sequence,
            clean_sequence,
            HYPOTHESIS_COUNT,
            config["max_distance_px"],
            config["temperature_px"],
            clean["seed"] + 2,
            proposal_model="distance",
        )
        uncertainty_links = _compatible_posterior_links(
            clean_sequence["observations"],
            uncertainty["posterior_links"],
            config["calibration_temperature"],
        )

        dataset_root = output_root / dataset_id
        hard_gt, hard_res, hard_export = export_fixed_detection_ctc_result(
            archives[dataset_id], "02", clean_sequence["observations"], hard_links,
            dataset_root / "hard", "hard"
        )
        soft_gt, soft_res, soft_export = export_fixed_detection_ctc_result(
            archives[dataset_id], "02", clean_sequence["observations"], uncertainty_links,
            dataset_root / "uncertainty", "uncertainty"
        )
        results[dataset_id] = {
            "sequence": "02",
            "scenario": "clean_0",
            "frozen_configuration": config,
            "hard_nearest_neighbor": {
                "export": hard_export,
                "ctc": _ctc_scores(hard_gt, hard_res),
            },
            "uncertainty_compatible_p50": {
                "export": soft_export,
                "ctc": _ctc_scores(soft_gt, soft_res),
            },
        }

    return {
        "schema_version": 1,
        "method": "stage_e_clean_fixed_detection_ctc_tra_lnk_v1",
        "evaluation_scope": "post-closure supplementary metric evaluation of the frozen clean sequence-02 linkers",
        "decision_effect": "none; the published Stage E decision remains unchanged",
        "primary_interpretation": "LNK isolates association quality under fixed gold detections",
        "tra_interpretation": "TRA is reported under fixed gold detections and must not be described as end-to-end tracking performance",
        "evaluator": "CellTrackingChallenge/py-ctcmetrics",
        "results": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/stage-e-dataset-manifest.json"))
    parser.add_argument("--split", type=Path, default=Path("docs/stage-e-split-lock.json"))
    parser.add_argument("--development", type=Path, default=Path("docs/stage-e-development-fit.json"))
    parser.add_argument("--gowt1", type=Path, required=True)
    parser.add_argument("--hela", type=Path, required=True)
    parser.add_argument("--workdir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, _ = load_stage_e_contract(args.manifest, args.split)
        development = json.loads(args.development.read_text(encoding="utf-8"))
        result = evaluate_stage_e_ctc_metrics(
            manifest,
            development,
            {
                "CTC_Fluo-N2DH-GOWT1_training": args.gowt1,
                "CTC_DIC-C2DH-HeLa_training": args.hela,
            },
            args.workdir,
        )
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Stage E CTC metric evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; supplementary CTC scoring does not change Stage E decision")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
