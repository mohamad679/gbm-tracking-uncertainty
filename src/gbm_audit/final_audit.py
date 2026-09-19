"""Assemble a compact, validated end-to-end project audit."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from gbm_audit.provenance import runtime_provenance
from gbm_audit.validation import (
    ArtifactValidationError,
    scenario_map,
    validate_corruptions,
    validate_manifest,
    validate_schema_version,
    validate_stage_artifact,
)


MIN_CLEAN_CANDIDATE_COVERAGE = 0.95
MAX_NOISE_DETERIORATION_PX_PER_FRAME = 1.0


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scenario(payload: dict, scenario_id: str) -> dict:
    try:
        return scenario_map(payload, "audit input")[scenario_id]
    except KeyError as exc:
        raise ArtifactValidationError(f"required scenario {scenario_id!r} is missing") from exc


def _validate_gate_artifact(gates: dict, corruptions: dict) -> None:
    validate_schema_version(gates, "gate sensitivity artifact")
    required = ("reference_manifest_sha256", "corruption_seed", "results")
    missing = [key for key in required if key not in gates]
    if missing:
        raise ArtifactValidationError(
            f"gate sensitivity artifact missing required keys: {', '.join(missing)}"
        )
    if gates["reference_manifest_sha256"] != corruptions["reference_manifest_sha256"]:
        raise ArtifactValidationError("gate sensitivity artifact reference hash does not match corruptions")
    if gates["corruption_seed"] != corruptions["seed"]:
        raise ArtifactValidationError("gate sensitivity artifact seed does not match corruptions")
    if not isinstance(gates["results"], list) or not gates["results"]:
        raise ArtifactValidationError("gate sensitivity artifact must contain at least one gate result")
    seen = set()
    for row in gates["results"]:
        if not isinstance(row, dict) or "max_distance_px" not in row:
            raise ArtifactValidationError("gate sensitivity result is missing max_distance_px")
        gate = float(row["max_distance_px"])
        if gate in seen:
            raise ArtifactValidationError(f"duplicate gate sensitivity radius {gate}")
        seen.add(gate)
        for key in ("clean_candidate_true_link_coverage", "noise_sigma_5_soft_speed_delta_px_per_frame"):
            if not isinstance(row.get(key), dict) or not row[key]:
                raise ArtifactValidationError(f"gate {gate} missing {key}")


def _operator_gate(gates: dict) -> tuple[bool, list[dict]]:
    """Evaluate explicit proposal-readiness criteria across candidate radii."""
    ordered = sorted(gates["results"], key=lambda row: float(row["max_distance_px"]))
    baseline = ordered[0]
    baseline_noise = baseline["noise_sigma_5_soft_speed_delta_px_per_frame"]
    evaluations = []
    for row in ordered:
        coverage = row["clean_candidate_true_link_coverage"]
        noise = row["noise_sigma_5_soft_speed_delta_px_per_frame"]
        sequence_ids = sorted(set(coverage) & set(noise) & set(baseline_noise))
        if not sequence_ids:
            raise ArtifactValidationError("gate sensitivity rows have no common sequence IDs")
        coverage_pass = all(float(coverage[sequence_id]) >= MIN_CLEAN_CANDIDATE_COVERAGE
                            for sequence_id in sequence_ids)
        deterioration = {
            sequence_id: abs(float(noise[sequence_id])) - abs(float(baseline_noise[sequence_id]))
            for sequence_id in sequence_ids
        }
        robustness_pass = all(value <= MAX_NOISE_DETERIORATION_PX_PER_FRAME
                              for value in deterioration.values())
        eligible = coverage_pass and robustness_pass
        evaluations.append({
            "max_distance_px": float(row["max_distance_px"]),
            "coverage_pass": coverage_pass,
            "robustness_pass": robustness_pass,
            "eligible_for_operator_learning": eligible,
            "noise_deterioration_vs_smallest_gate_px_per_frame": deterioration,
        })
    return any(row["eligible_for_operator_learning"] for row in evaluations), evaluations


def build_final_audit(manifest: dict, corruptions: dict, uncertainty: dict,
                     dynamics: dict, soft: dict, gates: dict,
                     appearance_uncertainty: dict,
                     input_hashes: dict | None = None) -> dict:
    validate_manifest(manifest)
    validate_corruptions(corruptions, manifest)
    validate_stage_artifact(uncertainty, "uncertainty artifact", corruptions)
    validate_stage_artifact(dynamics, "dynamics artifact", corruptions)
    validate_stage_artifact(soft, "soft dynamics artifact", corruptions)
    validate_stage_artifact(appearance_uncertainty, "appearance uncertainty artifact", corruptions)
    _validate_gate_artifact(gates, corruptions)

    clean = _scenario(uncertainty, "clean_0")
    clean_coverage = {
        sequence_id: result["candidate_true_link_coverage"]
        for sequence_id, result in clean["sequence_results"].items()
    }
    clean_soft = _scenario(soft, "clean_0")
    noise_soft = _scenario(soft, "localization_noise_5p0")
    appearance_clean = _scenario(appearance_uncertainty, "clean_0")
    appearance_noise = _scenario(appearance_uncertainty, "localization_noise_5p0")

    technical_benchmark_complete = bool(corruptions["scenarios"]) and bool(gates["results"])
    operator_learning_ready, gate_evaluations = _operator_gate(gates)
    operator_learning_ready = technical_benchmark_complete and operator_learning_ready
    biological_validation_claim_supported = bool(manifest.get("biological_validation_reference", False))

    operator_reason = (
        "at least one proposal radius meets the declared clean-coverage and held-out-noise robustness gates"
        if operator_learning_ready
        else "no proposal radius simultaneously meets the declared clean-coverage and held-out-noise robustness gates"
    )
    biological_reason = (
        "the reference manifest declares an explicit biological validation reference"
        if biological_validation_claim_supported
        else "the reference manifest does not declare brain-slice biological ground truth"
    )

    return {
        "schema_version": 1,
        "project": "uncertainty-aware glioblastoma tracking feasibility pilot",
        "date": "2026-09-19",
        "provenance": runtime_provenance(),
        "technical_benchmark_complete": technical_benchmark_complete,
        "operator_learning_ready": operator_learning_ready,
        "biological_validation_claim_supported": biological_validation_claim_supported,
        "gate_criteria": {
            "minimum_clean_candidate_coverage_per_sequence": MIN_CLEAN_CANDIDATE_COVERAGE,
            "maximum_noise_deterioration_vs_smallest_gate_px_per_frame": MAX_NOISE_DETERIORATION_PX_PER_FRAME,
            "gate_evaluations": gate_evaluations,
        },
        "reference": {
            "dataset": manifest["dataset"],
            "split_policy": manifest["split_policy"],
            "manifest_sha256": corruptions["reference_manifest_sha256"],
            "corruption_scenarios": len(corruptions["scenarios"]),
        },
        "uncertainty": {
            "proposal_model": uncertainty.get("proposal_model", "distance"),
            "calibration_temperature": uncertainty["calibration"]["temperature"],
            "clean_candidate_true_link_coverage": clean_coverage,
        },
        "soft_dynamics": {
            "clean_speed_delta_px_per_frame": {
                sequence_id: result["mean_speed_delta_vs_reference"]
                for sequence_id, result in clean_soft["sequence_results"].items()
            },
            "noise_sigma_5_speed_delta_px_per_frame": {
                sequence_id: result["mean_speed_delta_vs_reference"]
                for sequence_id, result in noise_soft["sequence_results"].items()
            },
        },
        "gate_sensitivity": gates["results"],
        "appearance_negative_control": {
            "clean_calibrated_brier": {
                sequence_id: result["calibrated_hypothesis_calibration"]["brier"]
                for sequence_id, result in appearance_clean["sequence_results"].items()
            },
            "noise_sigma_5_calibrated_brier": {
                sequence_id: result["calibrated_hypothesis_calibration"]["brier"]
                for sequence_id, result in appearance_noise["sequence_results"].items()
            },
        },
        "decisions": [
            {"gate": "reference_and_corruption", "status": "GO" if technical_benchmark_complete else "STOP",
             "reason": "validated expert-backed benchmark and aligned deterministic corruption artifacts"},
            {"gate": "uncertainty_and_downstream_dynamics", "status": "GO" if operator_learning_ready else "REVISE",
             "reason": operator_reason},
            {"gate": "SLDS_or_Koopman_operator", "status": "GO" if operator_learning_ready else "HOLD",
             "reason": operator_reason},
            {"gate": "GlioTrace_biological_claim", "status": "GO" if biological_validation_claim_supported else "STOP",
             "reason": biological_reason},
        ],
        "input_sha256": input_hashes or {},
        "warning": "This is a portfolio-grade technical feasibility audit, not a validated biological or clinical study unless an explicit biological validation reference is supplied.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("uncertainty", type=Path)
    parser.add_argument("dynamics", type=Path)
    parser.add_argument("soft", type=Path)
    parser.add_argument("gates", type=Path)
    parser.add_argument("appearance_uncertainty", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    paths = [args.manifest, args.corruptions, args.uncertainty, args.dynamics,
             args.soft, args.gates, args.appearance_uncertainty]
    try:
        payloads = [_read(path) for path in paths]
        hashes = {path.name: _sha256(path) for path in paths}
        result = build_final_audit(*payloads, input_hashes=hashes)
    except (OSError, KeyError, StopIteration, ValueError, json.JSONDecodeError) as exc:
        print(f"Final audit failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
