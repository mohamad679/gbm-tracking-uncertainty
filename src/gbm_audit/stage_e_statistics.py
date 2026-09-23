"""Deterministic post-evaluation statistics for the frozen Stage E artifact.

This module never changes the Stage E decision.  It quantifies the stability and
magnitude of paired method differences across the already-published corruption
scenarios.  Scenario resampling is a technical sensitivity analysis, not
animal-level or biological inference and not a substitute for the separately
registered track-cluster bootstrap requirement.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np


MOTION_ENDPOINTS = (
    "mean_speed_absolute_error",
    "total_path_length_relative_absolute_error",
    "net_displacement_relative_absolute_error",
    "directionality_absolute_error",
)

DEFAULT_BOOTSTRAP_SEED = 20260923
DEFAULT_BOOTSTRAP_ITERATIONS = 10_000


def _ci(values: np.ndarray) -> list[float]:
    return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def _paired_summary(deltas: list[float], *, rng: np.random.Generator,
                    iterations: int) -> dict:
    """Summarize paired deltas where positive values favor uncertainty-aware tracking."""
    values = np.asarray(deltas, dtype=float)
    if values.ndim != 1 or len(values) == 0 or not np.all(np.isfinite(values)):
        raise ValueError("paired deltas must be a non-empty finite one-dimensional sequence")
    if iterations < 100:
        raise ValueError("bootstrap iterations must be at least 100")
    indices = rng.integers(0, len(values), size=(iterations, len(values)))
    means = values[indices].mean(axis=1)
    return {
        "n_pairs": int(len(values)),
        "mean_delta": float(values.mean()),
        "median_delta": float(np.median(values)),
        "win_fraction": float(np.mean(values > 0)),
        "tie_fraction": float(np.mean(values == 0)),
        "bootstrap_95pct_ci_mean_delta": _ci(means),
        "direction": "positive_favors_uncertainty_aware_method",
    }


def _macro_bootstrap(domain_values: list[list[float]], *, rng: np.random.Generator,
                     iterations: int) -> dict:
    """Macro-average paired deltas while preserving fixed-domain identity."""
    arrays = [np.asarray(values, dtype=float) for values in domain_values]
    if not arrays or any(len(values) == 0 for values in arrays):
        raise ValueError("macro bootstrap requires at least one non-empty domain")
    point = float(np.mean([values.mean() for values in arrays]))
    replicates = np.empty(iterations, dtype=float)
    for iteration in range(iterations):
        domain_means = []
        for values in arrays:
            sampled = values[rng.integers(0, len(values), size=len(values))]
            domain_means.append(float(sampled.mean()))
        replicates[iteration] = float(np.mean(domain_means))
    return {
        "domain_count": len(arrays),
        "macro_mean_delta": point,
        "bootstrap_95pct_ci_macro_mean_delta": _ci(replicates),
        "direction": "positive_favors_uncertainty_aware_method",
    }


def analyze_stage_e_statistics(evaluation: dict, protocol: dict, *,
                               seed: int = DEFAULT_BOOTSTRAP_SEED,
                               iterations: int = DEFAULT_BOOTSTRAP_ITERATIONS) -> dict:
    """Analyze paired Stage E method differences without altering the locked decision."""
    if evaluation.get("evaluation_count") != 1 or not evaluation.get("evaluation_attempted"):
        raise ValueError("expected the published one-time Stage E evaluation artifact")
    real_domains = protocol.get("evaluation_panel", {}).get("real_confirmatory_domains", [])
    if not isinstance(real_domains, list) or not real_domains:
        raise ValueError("protocol does not define real confirmatory domains")
    missing = [dataset_id for dataset_id in real_domains if dataset_id not in evaluation.get("results", {})]
    if missing:
        raise ValueError(f"evaluation is missing registered real domains: {missing}")

    rng = np.random.default_rng(seed)
    per_dataset: dict[str, dict] = {}
    macro_motion_inputs: dict[str, list[list[float]]] = {name: [] for name in MOTION_ENDPOINTS}
    macro_association_inputs = {
        "calibrated_error_auprc_minus_distance": [],
        "full_coverage_risk_minus_selective_risk": [],
        "uncalibrated_brier_minus_calibrated_brier": [],
    }

    for dataset_id in real_domains:
        dataset = evaluation["results"][dataset_id]
        scenarios = dataset.get("scenarios", [])
        if not scenarios:
            raise ValueError(f"dataset {dataset_id} has no scenarios")

        motion: dict[str, dict] = {}
        for endpoint in MOTION_ENDPOINTS:
            deltas = [
                float(row["motion"]["hard_nearest_neighbor"]["errors"][endpoint])
                - float(row["motion"]["uncertainty_compatible_p50"]["errors"][endpoint])
                for row in scenarios
            ]
            motion[endpoint] = _paired_summary(deltas, rng=rng, iterations=iterations)
            macro_motion_inputs[endpoint].append(deltas)

        auprc_deltas = [
            float(row["association"]["calibrated_uncertainty"]["association_error_auprc"])
            - float(row["association"]["distance_confidence"]["association_error_auprc"])
            for row in scenarios
        ]
        risk_deltas = [
            float(row["association"]["calibrated_full_coverage_risk"])
            - float(row["association"]["calibrated_uncertainty"]["selective_link_risk"]["risk"])
            for row in scenarios
        ]
        brier_deltas = [
            float(row["association"]["uncalibrated_uncertainty"]["calibration"]["brier"])
            - float(row["association"]["calibrated_uncertainty"]["calibration"]["brier"])
            for row in scenarios
        ]
        association = {
            "calibrated_error_auprc_minus_distance": _paired_summary(
                auprc_deltas, rng=rng, iterations=iterations
            ),
            "full_coverage_risk_minus_selective_risk": _paired_summary(
                risk_deltas, rng=rng, iterations=iterations
            ),
            "uncalibrated_brier_minus_calibrated_brier": _paired_summary(
                brier_deltas, rng=rng, iterations=iterations
            ),
        }
        macro_association_inputs["calibrated_error_auprc_minus_distance"].append(auprc_deltas)
        macro_association_inputs["full_coverage_risk_minus_selective_risk"].append(risk_deltas)
        macro_association_inputs["uncalibrated_brier_minus_calibrated_brier"].append(brier_deltas)

        clean = next((row for row in scenarios if row.get("scenario_id") == "clean_0"), None)
        if clean is None:
            raise ValueError(f"dataset {dataset_id} lacks clean_0")
        clean_motion = {
            endpoint: (
                float(clean["motion"]["hard_nearest_neighbor"]["errors"][endpoint])
                - float(clean["motion"]["uncertainty_compatible_p50"]["errors"][endpoint])
            )
            for endpoint in MOTION_ENDPOINTS
        }
        per_dataset[dataset_id] = {
            "scenario_count": len(scenarios),
            "paired_motion_error_reduction": motion,
            "association_and_calibration_effects": association,
            "registered_clean_motion_deltas": clean_motion,
            "registered_clean_motion_wins": sum(value > 0 for value in clean_motion.values()),
        }

    macro_motion = {
        endpoint: _macro_bootstrap(values, rng=rng, iterations=iterations)
        for endpoint, values in macro_motion_inputs.items()
    }
    macro_association = {
        name: _macro_bootstrap(values, rng=rng, iterations=iterations)
        for name, values in macro_association_inputs.items()
    }

    return {
        "schema_version": 1,
        "method": "stage_e_fixed_domain_paired_scenario_bootstrap_v1",
        "source_evaluation_method": evaluation.get("method"),
        "source_decision": evaluation.get("decision"),
        "source_decision_unchanged": True,
        "bootstrap_seed": seed,
        "bootstrap_iterations": iterations,
        "resampling_unit": "registered corruption scenario within each fixed real domain",
        "inference_scope": (
            "technical robustness of the frozen benchmark under scenario resampling; "
            "not animal-level, patient-level, or population-level biological inference"
        ),
        "track_cluster_bootstrap_status": (
            "not satisfied by this summary-level analysis; requires a separate per-track reconstruction "
            "from the registered archives"
        ),
        "real_domains": real_domains,
        "per_dataset": per_dataset,
        "macro_across_fixed_real_domains": {
            "motion_error_reduction": macro_motion,
            "association_and_calibration_effects": macro_association,
        },
        "interpretation": (
            "Positive deltas indicate improvement by the uncertainty-aware method. "
            "Intervals quantify sensitivity to the finite registered corruption panel only."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evaluation", type=Path)
    parser.add_argument("protocol", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=DEFAULT_BOOTSTRAP_SEED)
    parser.add_argument("--iterations", type=int, default=DEFAULT_BOOTSTRAP_ITERATIONS)
    args = parser.parse_args(argv)
    try:
        evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
        protocol = json.loads(args.protocol.read_text(encoding="utf-8"))
        result = analyze_stage_e_statistics(
            evaluation, protocol, seed=args.seed, iterations=args.iterations
        )
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"Stage E statistical sensitivity analysis failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; Stage E decision remains {result['source_decision']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
