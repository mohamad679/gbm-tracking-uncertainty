"""Build the pre-registered Stage A candidate-generation comparison table.

The benchmark consumes uncertainty and matching soft-dynamics artifacts.  It
does not tune a proposal model.  Its role is to keep metric definitions and
the Stage A decision rule fixed before adaptive-gate development begins.
"""

import argparse
import json
import math
from pathlib import Path
import sys

from gbm_audit.validation import ArtifactValidationError, align_scenarios


BASELINE_RUN_IDS = ("fixed_8", "fixed_12", "fixed_16")
MIN_CLEAN_TRUE_LINK_RECALL = 0.95
MIN_BURDEN_REDUCTION_VS_FIXED_16 = 0.20
MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME = 1.0


def _finite_nonnegative(value, label: str) -> float:
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ArtifactValidationError(f"{label} must be finite and >= 0")
    return number


def _probability(value, label: str) -> float:
    number = _finite_nonnegative(value, label)
    if number > 1:
        raise ArtifactValidationError(f"{label} must be <= 1")
    return number


def _nonnegative_integer(value, label: str) -> int:
    if isinstance(value, bool) or int(value) != value or int(value) < 0:
        raise ArtifactValidationError(f"{label} must be a non-negative integer")
    return int(value)


def _absolute_finite(value, label: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ArtifactValidationError(f"{label} must be finite")
    return abs(number)


def _validate_pair(run_id: str, uncertainty: dict, soft: dict) -> None:
    if uncertainty.get("reference_manifest_sha256") != soft.get("reference_manifest_sha256"):
        raise ArtifactValidationError(f"{run_id}: uncertainty/soft reference hashes differ")
    if uncertainty.get("corruption_seed") != soft.get("corruption_seed"):
        raise ArtifactValidationError(f"{run_id}: uncertainty/soft corruption seeds differ")
    align_scenarios(uncertainty, soft, f"{run_id} uncertainty", f"{run_id} soft dynamics")


def summarize_run(run_id: str, uncertainty: dict, soft: dict) -> dict:
    """Return the four frozen Stage A metrics for one proposal run."""
    _validate_pair(run_id, uncertainty, soft)
    uncertainty_by_id = {row["scenario_id"]: row for row in uncertainty["scenarios"]}
    soft_by_id = {row["scenario_id"]: row for row in soft["scenarios"]}
    for required in ("clean_0", "localization_noise_5p0"):
        if required not in uncertainty_by_id or required not in soft_by_id:
            raise ArtifactValidationError(f"{run_id}: required scenario {required!r} is missing")

    clean_uncertainty = uncertainty_by_id["clean_0"]["sequence_results"]
    clean_soft = soft_by_id["clean_0"]["sequence_results"]
    noise_soft = soft_by_id["localization_noise_5p0"]["sequence_results"]
    sequence_ids = sorted(set(clean_uncertainty) & set(clean_soft) & set(noise_soft))
    if not sequence_ids:
        raise ArtifactValidationError(f"{run_id}: no aligned sequence results")

    sequence_results = {}
    for sequence_id in sequence_ids:
        candidate = clean_uncertainty[sequence_id]
        required_candidate_keys = (
            "candidate_edges",
            "candidate_target_observations",
            "candidate_burden_edges_per_target",
            "candidate_true_link_coverage",
        )
        missing = [key for key in required_candidate_keys if key not in candidate]
        if missing:
            raise ArtifactValidationError(
                f"{run_id} sequence {sequence_id}: missing candidate metrics {missing}"
            )
        edge_count = _nonnegative_integer(candidate["candidate_edges"], "candidate edge count")
        target_count = _nonnegative_integer(
            candidate["candidate_target_observations"], "target observation count"
        )
        burden = _finite_nonnegative(
            candidate["candidate_burden_edges_per_target"], "candidate burden"
        )
        expected_burden = edge_count / target_count if target_count else 0.0
        if not math.isclose(burden, expected_burden, rel_tol=1e-12, abs_tol=1e-12):
            raise ArtifactValidationError(
                f"{run_id} sequence {sequence_id}: candidate burden is inconsistent with counts"
            )
        sequence_results[sequence_id] = {
            "clean_true_link_recall": _probability(
                candidate["candidate_true_link_coverage"], "clean true-link recall"
            ),
            "clean_candidate_edges": edge_count,
            "clean_target_observations": target_count,
            "clean_candidate_burden_edges_per_target": burden,
            "clean_soft_speed_error_px_per_frame": _absolute_finite(
                clean_soft[sequence_id]["mean_speed_delta_vs_reference"],
                "clean soft speed error",
            ),
            "noise_sigma_5_soft_speed_error_px_per_frame": _absolute_finite(
                noise_soft[sequence_id]["mean_speed_delta_vs_reference"],
                "noise soft speed error",
            ),
        }

    return {
        "run_id": run_id,
        "proposal_model": uncertainty.get("proposal_model", "unknown"),
        "max_distance_px": uncertainty.get("max_distance_px"),
        "reference_manifest_sha256": uncertainty["reference_manifest_sha256"],
        "corruption_seed": uncertainty["corruption_seed"],
        "sequence_results": sequence_results,
    }


def _validate_baselines(rows: dict[str, dict]) -> None:
    expected_radii = {"fixed_8": 8.0, "fixed_12": 12.0, "fixed_16": 16.0}
    for run_id, radius in expected_radii.items():
        if run_id not in rows:
            raise ArtifactValidationError(f"missing required baseline {run_id!r}")
        row = rows[run_id]
        if row["proposal_model"] != "distance":
            raise ArtifactValidationError(f"{run_id} must use the distance proposal model")
        if float(row["max_distance_px"]) != radius:
            raise ArtifactValidationError(f"{run_id} must use max_distance_px={radius}")


def _acceptance(adaptive: dict, fixed_8: dict, fixed_16: dict) -> dict:
    sequence_ids = sorted(
        set(adaptive["sequence_results"])
        & set(fixed_8["sequence_results"])
        & set(fixed_16["sequence_results"])
    )
    if not sequence_ids:
        raise ArtifactValidationError("adaptive and baseline runs have no common sequences")
    results = {}
    for sequence_id in sequence_ids:
        candidate = adaptive["sequence_results"][sequence_id]
        narrow = fixed_8["sequence_results"][sequence_id]
        wide = fixed_16["sequence_results"][sequence_id]
        wide_burden = wide["clean_candidate_burden_edges_per_target"]
        adaptive_burden = candidate["clean_candidate_burden_edges_per_target"]
        burden_reduction = (
            1.0 - adaptive_burden / wide_burden if wide_burden > 0 else 0.0
        )
        noise_deterioration = (
            candidate["noise_sigma_5_soft_speed_error_px_per_frame"]
            - narrow["noise_sigma_5_soft_speed_error_px_per_frame"]
        )
        recall_pass = candidate["clean_true_link_recall"] >= MIN_CLEAN_TRUE_LINK_RECALL
        burden_pass = burden_reduction >= MIN_BURDEN_REDUCTION_VS_FIXED_16
        robustness_pass = (
            noise_deterioration <= MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME
        )
        results[sequence_id] = {
            "clean_recall_pass": recall_pass,
            "burden_reduction_vs_fixed_16_fraction": burden_reduction,
            "burden_pass": burden_pass,
            "noise_deterioration_vs_fixed_8_px_per_frame": noise_deterioration,
            "robustness_pass": robustness_pass,
            "sequence_pass": recall_pass and burden_pass and robustness_pass,
        }
    return {
        "thresholds": {
            "minimum_clean_true_link_recall": MIN_CLEAN_TRUE_LINK_RECALL,
            "minimum_burden_reduction_vs_fixed_16_fraction": MIN_BURDEN_REDUCTION_VS_FIXED_16,
            "maximum_noise_deterioration_vs_fixed_8_px_per_frame": (
                MAX_NOISE_DETERIORATION_VS_FIXED_8_PX_PER_FRAME
            ),
        },
        "sequence_results": results,
        "stage_a_pass": all(row["sequence_pass"] for row in results.values()),
    }


def build_candidate_benchmark(runs: dict[str, tuple[dict, dict]]) -> dict:
    """Build a baseline-only or baseline-plus-adaptive Stage A artifact."""
    rows = {run_id: summarize_run(run_id, *artifacts)
            for run_id, artifacts in runs.items()}
    _validate_baselines(rows)
    hashes = {row["reference_manifest_sha256"] for row in rows.values()}
    seeds = {row["corruption_seed"] for row in rows.values()}
    sequence_sets = {tuple(sorted(row["sequence_results"])) for row in rows.values()}
    if len(hashes) != 1 or len(seeds) != 1 or len(sequence_sets) != 1:
        raise ArtifactValidationError("candidate benchmark runs do not share provenance and sequences")
    extra_run_ids = sorted(set(rows) - set(BASELINE_RUN_IDS))
    if extra_run_ids not in ([], ["adaptive_v1"]):
        raise ArtifactValidationError(
            "the frozen comparison accepts only the optional run 'adaptive_v1'"
        )
    acceptance = None
    status = "baseline_contract_complete"
    if extra_run_ids:
        acceptance = _acceptance(rows["adaptive_v1"], rows["fixed_8"], rows["fixed_16"])
        status = "stage_a_pass" if acceptance["stage_a_pass"] else "stage_a_revise"
    return {
        "schema_version": 1,
        "method": "stage_a_adaptive_candidate_benchmark",
        "status": status,
        "split_policy": "sequence 01 development; sequence 02 locked test",
        "baseline_run_ids": list(BASELINE_RUN_IDS),
        "reference_manifest_sha256": next(iter(hashes)),
        "corruption_seed": next(iter(seeds)),
        "runs": [rows[run_id] for run_id in runs],
        "acceptance": acceptance,
        "warning": "Internal technical decision rule; thresholds are not universal cell-tracking standards.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run", action="append", nargs=3, metavar=("RUN_ID", "UNCERTAINTY", "SOFT"),
        required=True, help="Repeat for fixed_8, fixed_12, fixed_16, and optionally adaptive_v1",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        runs = {}
        for run_id, uncertainty_path, soft_path in args.run:
            if run_id in runs:
                raise ArtifactValidationError(f"duplicate run ID {run_id!r}")
            runs[run_id] = (
                json.loads(Path(uncertainty_path).read_text(encoding="utf-8")),
                json.loads(Path(soft_path).read_text(encoding="utf-8")),
            )
        result = build_candidate_benchmark(runs)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Candidate benchmark failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['runs'])} runs; {result['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
