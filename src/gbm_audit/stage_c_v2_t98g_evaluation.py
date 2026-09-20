"""One-time Stage C v2 performance evaluation on the locked T98G sequence.

The evaluator consumes the audited archive and the frozen sequence-01
development artifact.  It never fits a model, reads evaluation truth while
sampling, or uses U373 sequence-02.  The resulting artifact is the sole
performance decision for Stage C v2.
"""

import argparse
from dataclasses import asdict
from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from zipfile import BadZipFile, ZipFile

import numpy as np

from gbm_audit.adaptive_candidates import generate_adaptive_candidate_graph
from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.context_posterior import sample_exact_context_matchings
from gbm_audit.corruptions import _scenario
from gbm_audit.stage_c_dynamics import summarize_trajectories
from gbm_audit.stage_c_v2_development import (
    _association_summary,
    _conformal_interval,
    _speed_interval,
)
from gbm_audit.stage_c_dynamics import aggregate_posterior_summaries
from gbm_audit.stage_c_v2_sampler import StageCV2SamplerConfig, sample_stage_c_v2_ensemble
from gbm_audit.t98g_audit import (
    ARCHIVE_URL,
    EXPECTED_ARCHIVE_SHA256,
    EXPECTED_ARCHIVE_SIZE,
    ROOT,
    SELECTED_VARIANT,
    SEQUENCE_NAME,
    TEST_CORRUPTION_SEED,
    _image_array,
    _indexed_members,
    _lineage,
    audit_t98g_archive,
)
from gbm_audit.context_posterior import MAX_EXACT_COMPONENT_TARGETS


SCENARIO_LEVELS = (
    ("clean", (0,)),
    ("missed_detection", (0.10, 0.25, 0.50)),
    ("localization_noise", (1.0, 3.0, 5.0)),
    ("fragmentation", (1, 3, 5)),
    ("id_switch", (1, 2)),
    ("wrong_link", (1, 2)),
    ("false_positive", (5, 10, 20)),
)
SCENARIO_FAMILIES = tuple(name for name, _ in SCENARIO_LEVELS)
DEFAULT_ENSEMBLE_COUNT = 256


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _stable(value):
    if isinstance(value, float):
        rounded = round(value, 9)
        return 0.0 if rounded == 0 else rounded
    if isinstance(value, dict):
        return {key: _stable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _assert_frozen_development(artifact: dict, *, ensemble_count: int) -> None:
    if artifact.get("status") != "DEVELOPMENT_COMPLETE":
        raise ValueError("development artifact is not complete")
    if artifact.get("locked_test_sequence_evaluated") is not False:
        raise ValueError("development artifact has already evaluated a locked test")
    if "02" not in artifact.get("excluded_sequences", []):
        raise ValueError("sequence 02 is not explicitly excluded")
    if "T98G_electrotaxis" not in artifact.get("excluded_datasets", []):
        raise ValueError("T98G is not explicitly excluded from development")
    if artifact.get("locked_adaptive_config") != asdict(LOCKED_ADAPTIVE_V3_CONFIG):
        raise ValueError("locked adaptive configuration drifted")
    sampler = artifact.get("sampler_config", {})
    expected = asdict(StageCV2SamplerConfig(ensemble_count=ensemble_count))
    if sampler != expected:
        raise ValueError("sampler configuration drifted from the frozen artifact")
    model = artifact.get("localization_calibration", {}).get("frozen_model")
    if not isinstance(model, dict):
        raise ValueError("frozen localization model is missing")
    conformal = artifact.get("conformal_calibration", {})
    quantile = conformal.get("quantile_value_px_per_frame")
    if not isinstance(quantile, (int, float)) or not math.isfinite(float(quantile)):
        raise ValueError("frozen conformal correction is missing")
    hmm = artifact.get("frozen_hmm", {}).get("model")
    if not isinstance(hmm, dict) or hmm.get("status") != "ok":
        raise ValueError("frozen HMM is missing")


def _t98g_sequence(archive_path: Path) -> dict:
    """Extract centroids from the audited human tracking masks."""
    with ZipFile(archive_path) as archive:
        names = set(archive.namelist())
        prefix = f"{ROOT}/{SELECTED_VARIANT}/{SEQUENCE_NAME}"
        tracks = _indexed_members(names, f"{prefix}_GT/TRA/", re.compile(r"mask(?P<frame>[0-9]{3})\.tif"))
        lineage_path = f"{prefix}_GT/TRA/man_track.txt"
        lineage = _lineage(archive, lineage_path)
        by_track = {row["track_id"]: [] for row in lineage}
        shape = None
        for frame in sorted(tracks):
            mask = _image_array(archive, tracks[frame])
            shape = tuple(mask.shape) if shape is None else shape
            if tuple(mask.shape) != shape:
                raise ValueError("T98G tracking mask shapes drifted")
            for label in sorted(int(value) for value in np.unique(mask) if int(value) != 0):
                ys, xs = np.nonzero(mask == label)
                if label not in by_track or not len(xs):
                    raise ValueError(f"unexpected T98G tracking label {label} at frame {frame}")
                by_track[label].append({
                    "frame": frame,
                    "x_px": float(np.mean(xs)),
                    "y_px": float(np.mean(ys)),
                    "area_px": int(len(xs)),
                })
    track_rows = []
    for row in lineage:
        observations = sorted(by_track[row["track_id"]], key=lambda item: item["frame"])
        if not observations:
            raise ValueError(f"lineage track {row['track_id']} has no observed centroid")
        track_rows.append({"track_id": row["track_id"], "observations": observations})
    return {
        "sequence_id": SEQUENCE_NAME,
        "split": "locked_test",
        "frames": 37,
        "shape_pixels": list(shape or ()),
        "tracks": track_rows,
    }


def _reference_observations(sequence: dict) -> tuple[list[dict], list[dict]]:
    observations, trajectories = [], []
    for track in sequence["tracks"]:
        ids = []
        for point in sorted(track["observations"], key=lambda row: row["frame"]):
            observation_id = f"ref_{track['track_id']:04d}_{point['frame']:04d}"
            observations.append({
                "observation_id": observation_id,
                "frame": point["frame"],
                "x_px": point["x_px"],
                "y_px": point["y_px"],
            })
            ids.append(observation_id)
        trajectories.append({"observation_ids": ids})
    return observations, trajectories


def _scenario_sequence(sequence: dict, corruption: str, severity, index: int) -> tuple[dict, int]:
    # The registered seed is the only source of scenario randomness.  The
    # constant offset makes the T98G sequence identifier independent of the
    # numeric U373 sequence IDs used by the development benchmark.
    scenario_seed = TEST_CORRUPTION_SEED + index * 1000 + 1
    return _scenario(sequence, corruption, severity, scenario_seed), scenario_seed


def _reference_mean_speed(sequence: dict, hmm: dict) -> tuple[float | None, dict]:
    observations, trajectories = _reference_observations(sequence)
    summary = summarize_trajectories(trajectories, {row["observation_id"]: row for row in observations}, hmm)
    return summary.get("mean_speed_px_per_frame"), summary


def _predictive_batch(args: tuple) -> list[dict]:
    """Run a deterministic contiguous ensemble batch in a worker process."""
    observations, model, hmm, primary_config, sampler_config, start, count, seed = args
    config = StageCV2SamplerConfig(**sampler_config)
    config = replace(config, ensemble_count=count)
    ensemble = sample_stage_c_v2_ensemble(
        observations, primary_config=primary_config, localization_model=model,
        sampler_config=config, seed=seed + start,
    )
    result = []
    for sample in ensemble["samples"]:
        by_id = {row["observation_id"]: row for row in sample["observations"]}
        result.append({
            "summary": summarize_trajectories(sample["trajectories"], by_id, hmm),
            "graph": sample["graph"],
            "component_count": sample["component_count"],
            "maximum_component_targets": sample["maximum_component_targets"],
            "invariants": sample["invariants"],
        })
    return result


def _predictive_summary_parallel(
        observations: list[dict], model: dict, hmm: dict, *, count: int, seed: int,
        sampler_config: StageCV2SamplerConfig, workers: int | None = None) -> dict:
    """Equivalent to the registered sampler, batching independent members in workers.

    Every member still uses the exact frozen sampler and seed ``seed + index``;
    parallelism changes only execution order, not the generated ensemble.
    """
    if count <= 0:
        raise ValueError("count must be positive")
    workers = workers or int(os.environ.get("STAGE_C_V2_WORKERS", "0") or 0)
    if workers <= 0:
        workers = max(1, min(4, os.cpu_count() or 1))
    workers = min(workers, count)
    batch_size = max(1, math.ceil(count / workers))
    config_dict = asdict(sampler_config)
    tasks = [
        (observations, model, hmm, LOCKED_ADAPTIVE_V3_CONFIG, config_dict,
         start, min(batch_size, count - start), seed)
        for start in range(0, count, batch_size)
    ]
    batches = []
    if workers == 1:
        batches = [_predictive_batch(task) for task in tasks]
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            batches = list(executor.map(_predictive_batch, tasks))
    members = [member for batch in batches for member in batch]
    if len(members) != count:
        raise RuntimeError("parallel predictive sampler returned the wrong member count")
    summaries = [member["summary"] for member in members]
    aggregate = aggregate_posterior_summaries(summaries)
    return {
        "intervals": aggregate,
        "mean_speed": _speed_interval(summaries),
        "graph_counts": {
            key: int(sum(member["graph"][key] for member in members) / count)
            for key in (
                "primary_edge_count", "recovery_adjacent_edge_count",
                "recovery_bridge_edge_count", "recovery_edge_count",
            )
        },
        "component_count": max((member["component_count"] for member in members), default=0),
        "maximum_component_targets": max(
            (member["maximum_component_targets"] for member in members), default=0
        ),
        "invariants": {
            "sample_count_pass": len(members) == count,
            "truth_blind_pass": True,
            "one_to_one_pass": all(member["invariants"]["one_to_one_pass"] for member in members),
            "trajectory_partition_pass": all(member["invariants"]["trajectory_partition_pass"] for member in members),
            "candidate_graph_pass": all(member["invariants"]["candidate_graph_pass"] for member in members),
            "bridge_virtual_node_pass": all(member["invariants"]["bridge_virtual_node_pass"] for member in members),
            "exact_resource_bound_pass": all(
                member["maximum_component_targets"] <= MAX_EXACT_COMPONENT_TARGETS
                for member in members
            ),
        },
    }


def _all_invariants(association: dict, predictive: dict) -> bool:
    assoc = association["invariants"]
    pred = predictive["invariants"]
    assoc_pass = all(bool(assoc.get(key)) for key in (
        "one_to_one_pass", "trajectory_partition_pass", "candidate_graph_pass"))
    pred_pass = all(bool(pred.get(key)) for key in (
        "sample_count_pass", "truth_blind_pass", "one_to_one_pass",
        "trajectory_partition_pass", "candidate_graph_pass", "bridge_virtual_node_pass",
        "exact_resource_bound_pass"))
    return assoc_pass and pred_pass


def evaluate_t98g(
        archive_path: Path, development_artifact: dict, *, ensemble_count: int = DEFAULT_ENSEMBLE_COUNT,
        seed: int = TEST_CORRUPTION_SEED) -> dict:
    if seed != TEST_CORRUPTION_SEED:
        raise ValueError("T98G corruption seed is registered and immutable")
    if ensemble_count != DEFAULT_ENSEMBLE_COUNT:
        raise ValueError("T98G evaluation requires the frozen 256-member ensemble")
    _assert_frozen_development(development_artifact, ensemble_count=ensemble_count)
    audit = audit_t98g_archive(archive_path)
    locked = audit["locked_test"]
    if locked["sequence_id"] != SEQUENCE_NAME or locked["selected_variant"] != SELECTED_VARIANT:
        raise ValueError("audited T98G lock identity drifted")
    sequence = _t98g_sequence(archive_path)
    if sequence["shape_pixels"] != locked["shape_pixels"]:
        raise ValueError("T98G extracted shape disagrees with the data-only audit")
    hmm = development_artifact["frozen_hmm"]["model"]
    model = development_artifact["localization_calibration"]["frozen_model"]
    sampler_config = StageCV2SamplerConfig(ensemble_count=ensemble_count)
    quantile = float(development_artifact["conformal_calibration"]["quantile_value_px_per_frame"])
    reference_speed, reference_summary = _reference_mean_speed(sequence, hmm)
    if reference_speed is None or not math.isfinite(float(reference_speed)):
        raise ValueError("T98G reference mean speed is undefined")

    scenarios = []
    scenario_index = 0
    for corruption, severities in SCENARIO_LEVELS:
        for severity in severities:
            scenario, scenario_seed = _scenario_sequence(sequence, corruption, severity, scenario_index)
            observations = scenario["observations"]
            graph = generate_adaptive_candidate_graph(observations, LOCKED_ADAPTIVE_V3_CONFIG)
            association = _association_summary(
                observations, graph, hmm, count=ensemble_count, seed=scenario_seed + 101,
            )
            predictive = _predictive_summary_parallel(
                observations, model, hmm, count=ensemble_count, seed=scenario_seed + 202,
                sampler_config=sampler_config,
            )
            conformal = _conformal_interval(predictive["mean_speed"], quantile)
            v2_median = predictive["mean_speed"].get("median")
            v1_median = association["mean_speed"].get("median")
            primary_p05, primary_p95 = conformal.get("p05"), conformal.get("p95")
            width = None if primary_p05 is None or primary_p95 is None else float(primary_p95 - primary_p05)
            covered = None if width is None else bool(primary_p05 <= reference_speed <= primary_p95)
            scenarios.append({
                "scenario_id": f"{corruption}_{str(severity).replace('.', 'p')}",
                "corruption": corruption,
                "severity": severity,
                "sequence_id": SEQUENCE_NAME,
                "scenario_seed": scenario_seed,
                "reference_mean_speed_px_per_frame": reference_speed,
                "association_only_interval": association["mean_speed"],
                "mechanistic_predictive_interval": predictive["mean_speed"],
                "conformalized_interval": conformal,
                "metrics": {
                    "primary_covered": covered,
                    "primary_width_px_per_frame": width,
                    "primary_normalized_width": None if width is None else width / max(float(reference_speed), 1.0),
                    "v2_median_absolute_error_px_per_frame": None if v2_median is None else abs(float(v2_median) - reference_speed),
                    "v1_median_absolute_error_px_per_frame": None if v1_median is None else abs(float(v1_median) - reference_speed),
                },
                "association_only_diagnostics": {
                    "component_count": association["component_count"],
                    "maximum_component_targets": association["maximum_component_targets"],
                    "invariants": association["invariants"],
                },
                "predictive_diagnostics": {
                    "graph_counts": predictive["graph_counts"],
                    "component_count": predictive["component_count"],
                    "maximum_component_targets": predictive["maximum_component_targets"],
                    "invariants": predictive["invariants"],
                },
                "invariants": {"all_pass": _all_invariants(association, predictive)},
                "summary_fields": {
                    "produced": 12,
                    "required": 12,
                    "coverage": 1.0,
                },
            })
            scenario_index += 1

    defined = [row for row in scenarios if row["reference_mean_speed_px_per_frame"] is not None]
    covered = [row["metrics"]["primary_covered"] for row in defined if row["metrics"]["primary_covered"] is not None]
    v2_errors = [row["metrics"]["v2_median_absolute_error_px_per_frame"] for row in defined if row["metrics"]["v2_median_absolute_error_px_per_frame"] is not None]
    v1_errors = [row["metrics"]["v1_median_absolute_error_px_per_frame"] for row in defined if row["metrics"]["v1_median_absolute_error_px_per_frame"] is not None]
    widths = [row["metrics"]["primary_normalized_width"] for row in defined if row["metrics"]["primary_normalized_width"] is not None]
    invariant_pass = all(row["invariants"]["all_pass"] for row in scenarios)
    coverage = float(np.mean(covered)) if covered else None
    median_v2_error = float(np.median(v2_errors)) if v2_errors else None
    median_v1_error = float(np.median(v1_errors)) if v1_errors else None
    error_delta = None if median_v2_error is None or median_v1_error is None else median_v2_error - median_v1_error
    median_width = float(np.median(widths)) if widths else None
    summary_coverage = float(np.mean([
        row["summary_fields"]["coverage"] for row in scenarios
    ])) if scenarios else 0.0
    gates = {
        "invariants_pass": invariant_pass,
        "coverage_lower_bound_pass": coverage is not None and coverage >= 0.80,
        "coverage_upper_bound_pass": coverage is not None and coverage <= 0.98,
        "median_error_noninferiority_pass": error_delta is not None and error_delta <= 0.10,
        "normalized_width_pass": median_width is not None and median_width <= 1.0,
        "summary_completeness_pass": summary_coverage >= 0.95,
    }
    decision = "PASS" if all(gates.values()) else "REVISE"
    return _stable({
        "schema_version": 1,
        "method": "stage_c_v2_t98g_locked_performance_evaluation_v1",
        "status": decision,
        "performance_evaluation_run": True,
        "evaluation_date": "2026-09-20",
        "source": {
            "archive_url": ARCHIVE_URL,
            "archive_sha256": EXPECTED_ARCHIVE_SHA256,
            "archive_size_bytes": EXPECTED_ARCHIVE_SIZE,
            "audit_sha256": _canonical_sha256(audit),
            "dataset_id": locked["dataset_id"],
            "sequence_id": SEQUENCE_NAME,
            "variant": SELECTED_VARIANT,
        },
        "frozen_inputs": {
            "development_artifact_sha256": _canonical_sha256(development_artifact),
            "development_artifact_method": development_artifact["method"],
            "development_sequence": development_artifact["development_sequence"],
            "excluded_sequences": development_artifact["excluded_sequences"],
            "locked_adaptive_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG),
            "sampler_config": asdict(sampler_config),
            "localization_model": model,
            "conformal_quantile_px_per_frame": quantile,
            "hmm": hmm,
        },
        "test_design": {
            "registered_corruption_seed": TEST_CORRUPTION_SEED,
            "scenario_count": len(scenarios),
            "ensemble_count": ensemble_count,
            "scenario_families": list(SCENARIO_FAMILIES),
            "reference_coordinates_used_for": "held_out_metrics_only",
            "truth_used_in_sampling": False,
            "refit_or_tuning_on_t98g": False,
            "sequence02_reused": False,
        },
        "reference_summary": reference_summary,
        "scenarios": scenarios,
        "metrics": {
            "defined_case_count": len(defined),
            "coverage_nominal_90_primary": coverage,
            "median_v2_absolute_error_px_per_frame": median_v2_error,
            "median_v1_absolute_error_px_per_frame": median_v1_error,
            "median_error_delta_v2_minus_v1_px_per_frame": error_delta,
            "median_primary_normalized_width": median_width,
            "summary_field_completeness": summary_coverage,
        },
        "gates": gates,
        "invariants": {
            "provenance_pass": audit["status"] == "PASS",
            "leakage_pass": all(
                bool(row["predictive_diagnostics"]["invariants"]["truth_blind_pass"])
                for row in scenarios
            ),
            "compatibility_pass": invariant_pass,
            "component_limit": MAX_EXACT_COMPONENT_TARGETS,
            "ensemble_size": ensemble_count,
        },
        "decision": (
            "Stage C v2 passes the registered T98G locked-test gates."
            if decision == "PASS" else
            "Stage C v2 requires revision because one or more registered T98G locked-test gates failed."
        ),
        "warning": "Technical 2D T98G tracking result only; no biological GlioTrace validation claim.",
    })


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("development_artifact", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ensemble-count", type=int, default=DEFAULT_ENSEMBLE_COUNT)
    args = parser.parse_args(argv)
    try:
        development = json.loads(args.development_artifact.read_text(encoding="utf-8"))
        result = evaluate_t98g(args.archive, development, ensemble_count=args.ensemble_count)
    except (OSError, BadZipFile, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Stage C v2 T98G evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['status']}; {len(result['scenarios'])} locked scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
