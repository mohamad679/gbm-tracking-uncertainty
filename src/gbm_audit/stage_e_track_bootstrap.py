"""Track-cluster bootstrap intervals for frozen Stage E clean association endpoints.

The Stage E protocol requested 95% track-cluster bootstrap intervals as technical
uncertainty only.  This module reconstructs the frozen clean sequence-02
candidate links from the registered CTC archives and resamples *true tracks*,
never individual candidate edges, so repeated link decisions from one cell
trajectory remain clustered.

This is post-evaluation inference only: it does not refit calibration, tune
thresholds, or alter the locked Stage E decision.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import numpy as np

from gbm_audit.calibration import temperature_transform
from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.stage_e_data import _dataset_entry, build_locked_test_manifest, load_stage_e_contract
from gbm_audit.stage_e_evaluation import HYPOTHESIS_COUNT, _dataset_seed, _frozen_dataset_config
from gbm_audit.stage_e_metrics import distance_confidence, link_score_report, selective_link_risk
from gbm_audit.uncertainty import evaluate_sequence


ALL_STAGE_E_DATASETS = (
    "CTC_DIC-C2DH-HeLa_training",
    "CTC_Fluo-N2DH-GOWT1_training",
    "CTC_Fluo-N2DH-SIM+_training",
)
REAL_CONFIRMATORY_DATASETS = (
    "CTC_Fluo-N2DH-GOWT1_training",
    "CTC_DIC-C2DH-HeLa_training",
)
DEFAULT_SEED = 20260923
DEFAULT_ITERATIONS = 10_000


def _percentile_interval(values: np.ndarray) -> list[float]:
    return [float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))]


def _bootstrap_indices_by_cluster(cluster_ids: list[int], *, rng: np.random.Generator) -> np.ndarray:
    clusters = np.asarray(cluster_ids, dtype=int)
    unique = np.unique(clusters)
    if len(unique) < 2:
        raise ValueError("track-cluster bootstrap requires at least two true tracks")
    sampled = rng.choice(unique, size=len(unique), replace=True)
    pieces = [np.flatnonzero(clusters == cluster_id) for cluster_id in sampled]
    return np.concatenate(pieces)


def _effect_values(probabilities: list[float], distance_scores: list[float], labels: list[int],
                   raw_probabilities: list[float]) -> dict[str, float]:
    calibrated_report = link_score_report(probabilities, labels)
    distance_report = link_score_report(distance_scores, labels)
    raw_report = link_score_report(raw_probabilities, labels)
    full_risk = selective_link_risk(probabilities, labels, coverage=1.0)["risk"]
    return {
        "calibrated_error_auprc_minus_distance": float(
            calibrated_report["association_error_auprc"]
            - distance_report["association_error_auprc"]
        ),
        "full_coverage_risk_minus_selective_risk": float(
            full_risk - calibrated_report["selective_link_risk"]["risk"]
        ),
        "uncalibrated_brier_minus_calibrated_brier": float(
            raw_report["calibration"]["brier"]
            - calibrated_report["calibration"]["brier"]
        ),
    }


def bootstrap_clustered_link_effects(probabilities: list[float], distance_scores: list[float],
                                     labels: list[int], raw_probabilities: list[float],
                                     cluster_ids: list[int], *, seed: int = DEFAULT_SEED,
                                     iterations: int = DEFAULT_ITERATIONS) -> dict:
    """Bootstrap paired link-score effects by true source-track cluster."""
    lengths = {len(probabilities), len(distance_scores), len(labels), len(raw_probabilities), len(cluster_ids)}
    if len(lengths) != 1 or not probabilities:
        raise ValueError("all link vectors must have the same non-zero length")
    if iterations < 100:
        raise ValueError("bootstrap iterations must be at least 100")
    if any(cluster_id <= 0 for cluster_id in cluster_ids):
        raise ValueError("cluster IDs must be positive true-track identifiers")

    point = _effect_values(probabilities, distance_scores, labels, raw_probabilities)
    rng = np.random.default_rng(seed)
    replicates = {name: np.empty(iterations, dtype=float) for name in point}
    arrays = {
        "probabilities": np.asarray(probabilities, dtype=float),
        "distance": np.asarray(distance_scores, dtype=float),
        "labels": np.asarray(labels, dtype=int),
        "raw": np.asarray(raw_probabilities, dtype=float),
    }
    for iteration in range(iterations):
        indices = _bootstrap_indices_by_cluster(cluster_ids, rng=rng)
        effect = _effect_values(
            arrays["probabilities"][indices].tolist(),
            arrays["distance"][indices].tolist(),
            arrays["labels"][indices].tolist(),
            arrays["raw"][indices].tolist(),
        )
        for name, value in effect.items():
            replicates[name][iteration] = value

    return {
        "link_count": len(probabilities),
        "track_cluster_count": len(set(cluster_ids)),
        "cluster_definition": "true track ID of the source observation for each candidate link",
        "bootstrap_seed": seed,
        "bootstrap_iterations": iterations,
        "effects": {
            name: {
                "point_delta": value,
                "bootstrap_95pct_ci": _percentile_interval(replicates[name]),
                "positive_bootstrap_fraction": float(np.mean(replicates[name] > 0)),
                "direction": "positive_favors_registered_uncertainty_aware_analysis",
            }
            for name, value in point.items()
        },
    }


def _dataset_link_vectors(dataset_id: str, archive: Path, dataset: dict,
                          development: dict) -> dict:
    manifest = build_locked_test_manifest(archive, dataset)
    sequence = manifest["sequences"]["02"]
    config = _frozen_dataset_config(development, dataset_id)
    corruption_seed = _dataset_seed(dataset_id, list(ALL_STAGE_E_DATASETS))
    corruptions = build_corruption_benchmark(manifest, corruption_seed)
    clean = next(row for row in corruptions["scenarios"] if row["scenario_id"] == "clean_0")
    scenario_sequence = clean["sequences"]["02"]
    uncertainty = evaluate_sequence(
        sequence,
        scenario_sequence,
        HYPOTHESIS_COUNT,
        config["max_distance_px"],
        config["temperature_px"],
        clean["seed"] + 2,
        proposal_model="distance",
    )
    truth_by_observation = {
        row["observation_id"]: int(row["true_track_id"])
        for row in scenario_sequence["evaluation_truth"]
        if row.get("observed") and int(row["true_track_id"]) > 0
    }
    links = [
        link for link in uncertainty["posterior_links"]
        if link["from_observation_id"] in truth_by_observation
    ]
    if not links:
        raise ValueError(f"{dataset_id} has no candidate links available for track bootstrap")
    raw = [float(link["probability"]) for link in links]
    calibrated = [temperature_transform(value, config["calibration_temperature"]) for value in raw]
    labels = [int(bool(link["true_link"])) for link in links]
    distances = [float(link["distance_px"]) for link in links]
    return {
        "probabilities": calibrated,
        "raw_probabilities": raw,
        "distance_scores": distance_confidence(distances, config["max_distance_px"]),
        "labels": labels,
        "cluster_ids": [truth_by_observation[link["from_observation_id"]] for link in links],
        "frozen_configuration": config,
        "corruption_seed": corruption_seed,
    }


def evaluate_stage_e_track_bootstrap(manifest: dict, development: dict,
                                     archives: dict[str, Path], *, seed: int = DEFAULT_SEED,
                                     iterations: int = DEFAULT_ITERATIONS) -> dict:
    if set(archives) != set(REAL_CONFIRMATORY_DATASETS):
        raise ValueError("track bootstrap requires exactly the two registered real confirmatory datasets")
    results = {}
    for index, dataset_id in enumerate(REAL_CONFIRMATORY_DATASETS):
        vectors = _dataset_link_vectors(
            dataset_id, archives[dataset_id], _dataset_entry(manifest, dataset_id), development
        )
        summary = bootstrap_clustered_link_effects(
            vectors["probabilities"],
            vectors["distance_scores"],
            vectors["labels"],
            vectors["raw_probabilities"],
            vectors["cluster_ids"],
            seed=seed + index * 100_000,
            iterations=iterations,
        )
        results[dataset_id] = {
            "sequence": "02",
            "scenario": "clean_0",
            "frozen_configuration": vectors["frozen_configuration"],
            "corruption_seed": vectors["corruption_seed"],
            **summary,
        }
    return {
        "schema_version": 1,
        "method": "stage_e_clean_true_track_cluster_bootstrap_v1",
        "source_decision": "REVISE",
        "source_decision_unchanged": True,
        "resampling_unit": "true cell track; candidate links are clustered by source-track identity",
        "inference_scope": "technical uncertainty only; not animal-level, biological-population, or clinical inference",
        "datasets": results,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("docs/stage-e-dataset-manifest.json"))
    parser.add_argument("--split", type=Path, default=Path("docs/stage-e-split-lock.json"))
    parser.add_argument("--development", type=Path, default=Path("docs/stage-e-development-fit.json"))
    parser.add_argument("--gowt1", type=Path, required=True)
    parser.add_argument("--hela", type=Path, required=True)
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest, _ = load_stage_e_contract(args.manifest, args.split)
        development = json.loads(args.development.read_text(encoding="utf-8"))
        result = evaluate_stage_e_track_bootstrap(
            manifest,
            development,
            {
                "CTC_Fluo-N2DH-GOWT1_training": args.gowt1,
                "CTC_DIC-C2DH-HeLa_training": args.hela,
            },
            seed=args.seed,
            iterations=args.iterations,
        )
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError) as exc:
        print(f"Stage E track-cluster bootstrap failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output}; Stage E decision remains REVISE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
