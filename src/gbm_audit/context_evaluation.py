"""Development-only comparison of exact context and sampled link posteriors."""

import argparse
import copy
from dataclasses import asdict
import json
import math
from pathlib import Path
import sys

from gbm_audit.adaptive_candidates import generate_adaptive_candidate_graph
from gbm_audit.adaptive_tuning import DEVELOPMENT_SEQUENCE_ID, LOCKED_TEST_SEQUENCE_ID
from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.calibration import temperature_transform
from gbm_audit.context_posterior import exact_context_marginals
from gbm_audit.uncertainty import _calibration, _fit_temperature, evaluate_benchmark
from gbm_audit.validation import (
    ArtifactValidationError,
    canonical_sha256,
    validate_corruptions,
    validate_manifest,
)


def development_only_artifacts(manifest: dict, corruptions: dict) -> tuple[dict, dict]:
    """Retain sequence 01 and every predeclared scenario, failing closed on drift."""
    validate_manifest(manifest)
    validate_corruptions(corruptions, manifest)
    development_ids = sorted(
        sequence_id for sequence_id, sequence in manifest["sequences"].items()
        if sequence["split"] == "development"
    )
    if development_ids != [DEVELOPMENT_SEQUENCE_ID]:
        raise ArtifactValidationError(
            f"context evaluation requires development sequence ['{DEVELOPMENT_SEQUENCE_ID}']; "
            f"found {development_ids}"
        )
    if LOCKED_TEST_SEQUENCE_ID in manifest["sequences"] and (
            manifest["sequences"][LOCKED_TEST_SEQUENCE_ID]["split"] != "test"):
        raise ArtifactValidationError(
            f"locked sequence {LOCKED_TEST_SEQUENCE_ID} must have split='test'"
        )

    development_manifest = copy.deepcopy(manifest)
    development_manifest["sequences"] = {
        DEVELOPMENT_SEQUENCE_ID: copy.deepcopy(
            manifest["sequences"][DEVELOPMENT_SEQUENCE_ID]
        )
    }
    development_corruptions = copy.deepcopy(corruptions)
    development_corruptions["reference_manifest_sha256"] = canonical_sha256(development_manifest)
    for scenario in development_corruptions["scenarios"]:
        if DEVELOPMENT_SEQUENCE_ID not in scenario["sequences"]:
            raise ArtifactValidationError(
                f"scenario {scenario['scenario_id']!r} is missing development sequence"
            )
        scenario["sequences"] = {
            DEVELOPMENT_SEQUENCE_ID: scenario["sequences"][DEVELOPMENT_SEQUENCE_ID]
        }
    validate_corruptions(development_corruptions, development_manifest)
    leaked = {
        sequence_id
        for scenario in development_corruptions["scenarios"]
        for sequence_id in scenario["sequences"]
        if sequence_id != DEVELOPMENT_SEQUENCE_ID
    }
    if leaked:
        raise ArtifactValidationError(f"locked-test leakage detected: {sorted(leaked)}")
    return development_manifest, development_corruptions


def _true_link_pairs(evaluation_truth: list[dict]) -> set[tuple[str, str]]:
    by_track_frame = {
        (row["true_track_id"], row["frame"]): row["observation_id"]
        for row in evaluation_truth
        if row["true_track_id"] > 0 and row["observed"]
    }
    return {
        (observation_id, by_track_frame[(track_id, frame + 1)])
        for (track_id, frame), observation_id in by_track_frame.items()
        if (track_id, frame + 1) in by_track_frame
    }


def _negative_log_likelihood(probabilities: list[float], labels: list[int]) -> float:
    if not probabilities:
        return 0.0
    epsilon = 1e-12
    return sum(
        -(label * math.log(max(probability, epsilon))
          + (1 - label) * math.log(max(1 - probability, epsilon)))
        for probability, label in zip(probabilities, labels)
    ) / len(probabilities)


def _metrics(probabilities: list[float], labels: list[int]) -> dict:
    return {
        **_calibration(probabilities, labels),
        "negative_log_likelihood": _negative_log_likelihood(probabilities, labels),
    }


def _posterior_metrics(posterior_links: list[dict], temperature: float) -> dict:
    probabilities = [float(link["probability"]) for link in posterior_links]
    labels = [int(link["true_link"]) for link in posterior_links]
    calibrated = [temperature_transform(probability, temperature) for probability in probabilities]
    return {
        "raw": _metrics(probabilities, labels),
        "calibrated": _metrics(calibrated, labels),
    }


def _aggregate_components(components: list[dict]) -> dict:
    return {
        "component_count": len(components),
        "maximum_component_targets": max(
            (len(component["target_observation_ids"]) for component in components), default=0
        ),
        "maximum_enumerated_matching_count": max(
            (component["enumerated_matching_count"] for component in components), default=0
        ),
    }


def evaluate_development(manifest: dict, corruptions: dict) -> dict:
    """Compare exact and sampled posteriors using only the development split."""
    development_manifest, development_corruptions = development_only_artifacts(
        manifest, corruptions
    )
    sampled = evaluate_benchmark(
        development_manifest,
        development_corruptions,
        proposal_model="adaptive_v1",
        adaptive_config=LOCKED_ADAPTIVE_V3_CONFIG,
    )
    sampled_by_scenario = {row["scenario_id"]: row for row in sampled["scenarios"]}
    exact_rows, all_components = [], []

    for scenario in development_corruptions["scenarios"]:
        scenario_id = scenario["scenario_id"]
        scenario_sequence = scenario["sequences"][DEVELOPMENT_SEQUENCE_ID]
        graph = generate_adaptive_candidate_graph(
            scenario_sequence["observations"], LOCKED_ADAPTIVE_V3_CONFIG
        )
        exact = exact_context_marginals(
            scenario_sequence["observations"], graph["candidate_edges"],
            temperature_px=4.0,
            new_track_score_px=LOCKED_ADAPTIVE_V3_CONFIG.new_track_score_px,
        )
        true_pairs = _true_link_pairs(scenario_sequence["evaluation_truth"])
        posterior_links = [
            {
                **link,
                "true_link": (
                    (link["from_observation_id"], link["to_observation_id"]) in true_pairs
                ),
            }
            for link in exact["link_marginals"]
        ]
        exact_pairs = {
            (link["from_observation_id"], link["to_observation_id"])
            for link in posterior_links
        }
        sampled_links = sampled_by_scenario[scenario_id]["sequence_results"][
            DEVELOPMENT_SEQUENCE_ID
        ]["posterior_links"]
        sampled_pairs = {
            (link["from_observation_id"], link["to_observation_id"])
            for link in sampled_links
        }
        graph_pairs = {
            (edge["from_observation_id"], edge["to_observation_id"])
            for edge in graph["candidate_edges"]
        }
        if exact_pairs != graph_pairs or sampled_pairs != graph_pairs:
            raise RuntimeError(
                f"candidate graph mismatch for scenario {scenario_id!r}"
            )
        if not (
            exact["invariants"]["target_conservation_pass"]
            and exact["invariants"]["source_capacity_pass"]
        ):
            raise RuntimeError(f"context posterior invariants failed for scenario {scenario_id!r}")
        all_components.extend(exact["components"])
        exact_rows.append({
            "scenario_id": scenario_id,
            "corruption": scenario["corruption"],
            "severity": scenario["severity"],
            "sequence_id": DEVELOPMENT_SEQUENCE_ID,
            "candidate_edges": len(posterior_links),
            "context_components": _aggregate_components(exact["components"]),
            "components": exact["components"],
            "exact_context_posterior_links": posterior_links,
            "sampled_stage_a_posterior_links": sampled_links,
        })

    exact_temperature = _fit_temperature([
        {"posterior_links": row["exact_context_posterior_links"]}
        for row in exact_rows
    ])
    exact_links = [
        link for row in exact_rows for link in row["exact_context_posterior_links"]
    ]
    sampled_links = [
        link for scenario in sampled["scenarios"]
        for link in scenario["sequence_results"][DEVELOPMENT_SEQUENCE_ID]["posterior_links"]
    ]
    scenario_results = []
    sampled_temperature = sampled["calibration"]["temperature"]
    for exact_row in exact_rows:
        sampled_result = sampled_by_scenario[exact_row["scenario_id"]]["sequence_results"][
            DEVELOPMENT_SEQUENCE_ID
        ]
        scenario_results.append({
            **exact_row,
            "exact_context": _posterior_metrics(
                exact_row["exact_context_posterior_links"], exact_temperature
            ),
            "sampled_stage_a": _posterior_metrics(
                sampled_result["posterior_links"], sampled_temperature
            ),
        })
    return {
        "schema_version": 1,
        "method": "stage_b_development_context_evaluation_v1",
        "status": "DEVELOPMENT_COMPLETE",
        "development_sequence": DEVELOPMENT_SEQUENCE_ID,
        "locked_test_sequence_evaluated": False,
        "scenario_ids": [row["scenario_id"] for row in development_corruptions["scenarios"]],
        "locked_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG),
        "candidate_graph_method": "adaptive_v1_locked_stage_a_config",
        "reference_manifest_sha256": development_corruptions["reference_manifest_sha256"],
        "corruption_seed": development_corruptions["seed"],
        "exact_context": {
            "invariants_pass": True,
            "components": _aggregate_components(all_components),
            "calibration": {
                "method": "development_sequence_temperature_scaling",
                "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
                "temperature": exact_temperature,
            },
            "aggregate_metrics": _posterior_metrics(exact_links, exact_temperature),
        },
        "sampled_stage_a": {
            "hypothesis_count": sampled["hypothesis_count"],
            "calibration": sampled["calibration"],
            "aggregate_metrics": _posterior_metrics(sampled_links, sampled_temperature),
        },
        "scenario_results": scenario_results,
        "warning": (
            "Development-only technical comparison on U373-derived scenarios. "
            "Sequence 02 is excluded and has not been evaluated for Stage B."
        ),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("corruptions", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        corruptions = json.loads(args.corruptions.read_text(encoding="utf-8"))
        result = evaluate_development(manifest, corruptions)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, ArtifactValidationError) as exc:
        print(f"Stage B development evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({len(result['scenario_results'])} development scenarios)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
