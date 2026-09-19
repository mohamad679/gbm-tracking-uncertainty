"""Measure how candidate-gate radius changes uncertainty-aware dynamics."""

import argparse
import json
from pathlib import Path
import sys

from gbm_audit.soft_dynamics import evaluate_soft_dynamics
from gbm_audit.uncertainty import evaluate_benchmark


def summarize_gate(uncertainty: dict, soft: dict, gate: float) -> dict:
    by_id = {scenario["scenario_id"]: scenario for scenario in soft["scenarios"]}
    clean_uncertainty = next(scenario for scenario in uncertainty["scenarios"] if scenario["scenario_id"] == "clean_0")
    clean_soft = by_id["clean_0"]
    noise_soft = by_id["localization_noise_5p0"]
    coverage = {sequence_id: result["candidate_true_link_coverage"]
                for sequence_id, result in clean_uncertainty["sequence_results"].items()}
    burden = {sequence_id: result["candidate_burden_edges_per_target"]
              for sequence_id, result in clean_uncertainty["sequence_results"].items()}
    clean_speed = {sequence_id: result["mean_speed_px_per_frame"]
                   for sequence_id, result in clean_soft["sequence_results"].items()}
    clean_delta = {sequence_id: result["mean_speed_delta_vs_reference"]
                   for sequence_id, result in clean_soft["sequence_results"].items()}
    noise_delta = {sequence_id: result["mean_speed_delta_vs_reference"]
                   for sequence_id, result in noise_soft["sequence_results"].items()}
    absolute_deltas = {
        sequence_id: sum(abs(scenario["sequence_results"][sequence_id]["mean_speed_delta_vs_reference"])
                         for scenario in soft["scenarios"]) / len(soft["scenarios"])
        for sequence_id in ("01", "02")
    }
    return {
        "max_distance_px": gate,
        "clean_candidate_true_link_coverage": coverage,
        "clean_candidate_burden_edges_per_target": burden,
        "clean_soft_mean_speed_px_per_frame": clean_speed,
        "clean_soft_speed_delta_px_per_frame": clean_delta,
        "noise_sigma_5_soft_speed_delta_px_per_frame": noise_delta,
        "mean_absolute_soft_speed_delta_px_per_frame": absolute_deltas,
    }


def evaluate_gate_sensitivity(manifest: dict, corruptions: dict, hard_dynamics: dict,
                              gates: list[float], count: int = 64,
                              temperature_px: float = 4.0) -> dict:
    rows = []
    for gate in gates:
        uncertainty = evaluate_benchmark(manifest, corruptions, count, gate, temperature_px)
        soft = evaluate_soft_dynamics(manifest, corruptions, uncertainty, hard_dynamics)
        rows.append(summarize_gate(uncertainty, soft, gate))
    return {
        "schema_version": 1,
        "method": "candidate_gate_sensitivity_for_soft_dynamics",
        "gates_px": gates,
        "hypothesis_count": count,
        "temperature_px": temperature_px,
        "reference_manifest_sha256": corruptions["reference_manifest_sha256"],
        "corruption_seed": corruptions["seed"],
        "results": rows,
        "warning": "Technical U373 gate sensitivity; this does not validate biological phenotypes.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("hard_dynamics", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gates", type=float, nargs="+", default=[8.0, 12.0, 16.0])
    parser.add_argument("--hypotheses", type=int, default=64)
    parser.add_argument("--temperature-px", type=float, default=4.0)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruptions = json.loads(args.corruptions.read_text(encoding="utf-8"))
        hard_dynamics = json.loads(args.hard_dynamics.read_text(encoding="utf-8"))
        result = evaluate_gate_sensitivity(manifest, corruptions, hard_dynamics,
                                           args.gates, args.hypotheses, args.temperature_px)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Gate sensitivity evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['results'])} gates)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
