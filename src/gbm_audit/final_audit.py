"""Assemble a compact, honest end-to-end project audit."""

import argparse
import hashlib
import json
from pathlib import Path
import sys


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _scenario(payload: dict, scenario_id: str) -> dict:
    return next(item for item in payload["scenarios"] if item["scenario_id"] == scenario_id)


def build_final_audit(manifest: dict, corruptions: dict, uncertainty: dict,
                     dynamics: dict, soft: dict, gates: dict,
                     appearance_uncertainty: dict, test_count: int = 0,
                     input_hashes: dict | None = None) -> dict:
    clean = _scenario(uncertainty, "clean_0")
    clean_coverage = {
        sequence_id: result["candidate_true_link_coverage"]
        for sequence_id, result in clean["sequence_results"].items()
    }
    clean_soft = _scenario(soft, "clean_0")
    noise_soft = _scenario(soft, "localization_noise_5p0")
    appearance_clean = _scenario(appearance_uncertainty, "clean_0")
    appearance_noise = _scenario(appearance_uncertainty, "localization_noise_5p0")
    return {
        "schema_version": 1,
        "project": "uncertainty-aware glioblastoma tracking feasibility pilot",
        "date": "2026-09-19",
        "technical_benchmark_complete": True,
        "operator_learning_ready": False,
        "biological_validation_claim_supported": False,
        "tests_passed": test_count,
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
            {"gate": "reference_and_corruption", "status": "GO", "reason": "deterministic expert-backed benchmark and 17 seeded corruptions"},
            {"gate": "uncertainty_and_downstream_dynamics", "status": "REVISE", "reason": "candidate recall and proposal sensitivity remain material"},
            {"gate": "SLDS_or_Koopman_operator", "status": "HOLD", "reason": "operator would learn proposal artifacts before a stable proposal regime exists"},
            {"gate": "GlioTrace_biological_claim", "status": "STOP", "reason": "U373 is a technical 2D benchmark and no biological reference labels are present"},
        ],
        "input_sha256": input_hashes or {},
        "warning": "This is a portfolio-grade technical feasibility audit, not a validated biological or clinical study.",
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
    parser.add_argument("--tests-passed", type=int, default=0)
    args = parser.parse_args(argv)
    paths = [args.manifest, args.corruptions, args.uncertainty, args.dynamics,
             args.soft, args.gates, args.appearance_uncertainty]
    try:
        payloads = [_read(path) for path in paths]
        hashes = {path.name: _sha256(path) for path in paths}
        result = build_final_audit(*payloads, test_count=args.tests_passed, input_hashes=hashes)
    except (OSError, KeyError, StopIteration, ValueError, json.JSONDecodeError) as exc:
        print(f"Final audit failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
