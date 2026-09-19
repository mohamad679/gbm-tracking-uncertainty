"""One-time locked Stage B evaluation of context-aware link posteriors."""

import argparse
import copy
from dataclasses import asdict
import json
from pathlib import Path
import sys

from gbm_audit.adaptive_candidates import generate_adaptive_candidate_graph
from gbm_audit.adaptive_tuning import DEVELOPMENT_SEQUENCE_ID, LOCKED_TEST_SEQUENCE_ID
from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.context_evaluation import (
    FROZEN_EXACT_CONTEXT_TEMPERATURE,
    FROZEN_SAMPLED_STAGE_A_TEMPERATURE,
    _aggregate_components,
    _posterior_metrics,
    _true_link_pairs,
    evaluate_development,
)
from gbm_audit.context_posterior import exact_context_marginals
from gbm_audit.uncertainty import evaluate_sequence
from gbm_audit.validation import ArtifactValidationError, canonical_sha256, validate_corruptions, validate_manifest


MAX_BRIER_DETERIORATION = 0.005
MAX_ECE_DETERIORATION = 0.02


def locked_test_artifacts(manifest: dict, corruptions: dict) -> tuple[dict, dict]:
    """Return test-only artifacts after proving the registered two-split contract."""
    validate_manifest(manifest)
    validate_corruptions(corruptions, manifest)
    if set(manifest["sequences"]) != {DEVELOPMENT_SEQUENCE_ID, LOCKED_TEST_SEQUENCE_ID}:
        raise ArtifactValidationError("Stage B requires exactly sequences 01 and 02")
    if manifest["sequences"][DEVELOPMENT_SEQUENCE_ID]["split"] != "development":
        raise ArtifactValidationError("sequence 01 must have split='development'")
    if manifest["sequences"][LOCKED_TEST_SEQUENCE_ID]["split"] != "test":
        raise ArtifactValidationError("sequence 02 must have split='test'")

    test_manifest = copy.deepcopy(manifest)
    test_manifest["sequences"] = {
        LOCKED_TEST_SEQUENCE_ID: copy.deepcopy(manifest["sequences"][LOCKED_TEST_SEQUENCE_ID])
    }
    test_corruptions = copy.deepcopy(corruptions)
    test_corruptions["reference_manifest_sha256"] = canonical_sha256(test_manifest)
    for scenario in test_corruptions["scenarios"]:
        if LOCKED_TEST_SEQUENCE_ID not in scenario["sequences"]:
            raise ArtifactValidationError(
                f"scenario {scenario['scenario_id']!r} is missing locked test sequence"
            )
        scenario["sequences"] = {
            LOCKED_TEST_SEQUENCE_ID: scenario["sequences"][LOCKED_TEST_SEQUENCE_ID]
        }
    validate_corruptions(test_corruptions, test_manifest)
    return test_manifest, test_corruptions


def _gates(exact_context: dict, sampled_stage_a: dict, *, resource_pass: bool) -> dict:
    exact_metrics = exact_context["aggregate_metrics"]["calibrated"]
    sampled_metrics = sampled_stage_a["aggregate_metrics"]["calibrated"]
    return {
        "exact_invariants": exact_context["invariants_pass"],
        "resource_bound": resource_pass,
        "calibrated_brier_noninferior": (
            exact_metrics["brier"] <= sampled_metrics["brier"] + MAX_BRIER_DETERIORATION
        ),
        "calibrated_ece_noninferior": (
            exact_metrics["ece"] <= sampled_metrics["ece"] + MAX_ECE_DETERIORATION
        ),
    }


def _evaluate_locked_test(manifest: dict, corruptions: dict) -> dict:
    """Evaluate sequence 02 using only frozen development calibration values."""
    test_manifest, test_corruptions = locked_test_artifacts(manifest, corruptions)
    exact_rows, all_components = [], []
    for scenario_index, scenario in enumerate(test_corruptions["scenarios"]):
        scenario_id = scenario["scenario_id"]
        scenario_sequence = scenario["sequences"][LOCKED_TEST_SEQUENCE_ID]
        scenario_seed = scenario.get("seed", test_corruptions["seed"] + scenario_index * 1000)
        sampled = evaluate_sequence(
            test_manifest["sequences"][LOCKED_TEST_SEQUENCE_ID],
            scenario_sequence,
            count=64,
            max_distance_px=8.0,
            temperature_px=4.0,
            seed=scenario_seed + int(LOCKED_TEST_SEQUENCE_ID),
            proposal_model="adaptive_v1",
            adaptive_config=LOCKED_ADAPTIVE_V3_CONFIG,
        )
        graph = generate_adaptive_candidate_graph(
            scenario_sequence["observations"], LOCKED_ADAPTIVE_V3_CONFIG
        )
        exact = exact_context_marginals(
            scenario_sequence["observations"], graph["candidate_edges"],
            temperature_px=4.0,
            new_track_score_px=LOCKED_ADAPTIVE_V3_CONFIG.new_track_score_px,
        )
        true_pairs = _true_link_pairs(scenario_sequence["evaluation_truth"])
        exact_links = [
            {
                **link,
                "true_link": (
                    (link["from_observation_id"], link["to_observation_id"]) in true_pairs
                ),
            }
            for link in exact["link_marginals"]
        ]
        graph_pairs = {
            (edge["from_observation_id"], edge["to_observation_id"])
            for edge in graph["candidate_edges"]
        }
        exact_pairs = {
            (link["from_observation_id"], link["to_observation_id"])
            for link in exact_links
        }
        sampled_pairs = {
            (link["from_observation_id"], link["to_observation_id"])
            for link in sampled["posterior_links"]
        }
        if graph_pairs != exact_pairs or graph_pairs != sampled_pairs:
            raise RuntimeError(f"candidate graph mismatch for scenario {scenario_id!r}")
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
            "sequence_id": LOCKED_TEST_SEQUENCE_ID,
            "candidate_edges": len(exact_links),
            "context_components": _aggregate_components(exact["components"]),
            "components": exact["components"],
            "exact_context_posterior_links": exact_links,
            "sampled_stage_a_posterior_links": sampled["posterior_links"],
        })
    exact_links = [
        link for row in exact_rows for link in row["exact_context_posterior_links"]
    ]
    sampled_links = [
        link for row in exact_rows for link in row["sampled_stage_a_posterior_links"]
    ]
    scenario_results = []
    for row in exact_rows:
        scenario_results.append({
            **row,
            "exact_context": _posterior_metrics(
                row["exact_context_posterior_links"], FROZEN_EXACT_CONTEXT_TEMPERATURE
            ),
            "sampled_stage_a": _posterior_metrics(
                row["sampled_stage_a_posterior_links"], FROZEN_SAMPLED_STAGE_A_TEMPERATURE
            ),
        })
    return {
        "sequence_id": LOCKED_TEST_SEQUENCE_ID,
        "evaluation_role": "one_time_locked_test",
        "reference_manifest_sha256": test_corruptions["reference_manifest_sha256"],
        "corruption_seed": test_corruptions["seed"],
        "scenario_ids": [row["scenario_id"] for row in test_corruptions["scenarios"]],
        "exact_context": {
            "invariants_pass": True,
            "components": _aggregate_components(all_components),
            "calibration": {
                "method": "frozen_development_temperature_scaling",
                "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
                "temperature": FROZEN_EXACT_CONTEXT_TEMPERATURE,
            },
            "aggregate_metrics": _posterior_metrics(
                exact_links, FROZEN_EXACT_CONTEXT_TEMPERATURE
            ),
        },
        "sampled_stage_a": {
            "hypothesis_count": 64,
            "calibration": {
                "method": "frozen_development_temperature_scaling",
                "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
                "temperature": FROZEN_SAMPLED_STAGE_A_TEMPERATURE,
            },
            "aggregate_metrics": _posterior_metrics(
                sampled_links, FROZEN_SAMPLED_STAGE_A_TEMPERATURE
            ),
        },
        "scenario_results": scenario_results,
    }


def evaluate_locked(manifest: dict, corruptions: dict) -> dict:
    """Run the final registered Stage B decision without recalibrating sequence 02."""
    development = evaluate_development(manifest, corruptions)
    locked_test = _evaluate_locked_test(manifest, corruptions)
    development_exact_links = [
        link
        for scenario in development["scenario_results"]
        for link in scenario["exact_context_posterior_links"]
    ]
    development_sampled_links = [
        link
        for scenario in development["scenario_results"]
        for link in scenario["sampled_stage_a_posterior_links"]
    ]
    development_summary = {
        "sequence_id": DEVELOPMENT_SEQUENCE_ID,
        "evaluation_role": "frozen_development_reference",
        "scenario_ids": development["scenario_ids"],
        "exact_context": {
            **development["exact_context"],
            "calibration": {
                "method": "frozen_development_temperature_scaling",
                "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
                "temperature": FROZEN_EXACT_CONTEXT_TEMPERATURE,
            },
            "aggregate_metrics": _posterior_metrics(
                development_exact_links, FROZEN_EXACT_CONTEXT_TEMPERATURE
            ),
        },
        "sampled_stage_a": {
            **development["sampled_stage_a"],
            "calibration": {
                "method": "frozen_development_temperature_scaling",
                "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
                "temperature": FROZEN_SAMPLED_STAGE_A_TEMPERATURE,
            },
            "aggregate_metrics": _posterior_metrics(
                development_sampled_links, FROZEN_SAMPLED_STAGE_A_TEMPERATURE
            ),
        },
    }
    gates_by_sequence = {
        DEVELOPMENT_SEQUENCE_ID: _gates(
            development_summary["exact_context"], development_summary["sampled_stage_a"],
            resource_pass=(
                development_summary["exact_context"]["components"]["maximum_component_targets"]
                <= 18
            ),
        ),
        LOCKED_TEST_SEQUENCE_ID: _gates(
            locked_test["exact_context"], locked_test["sampled_stage_a"],
            resource_pass=(
                locked_test["exact_context"]["components"]["maximum_component_targets"] <= 18
            ),
        ),
    }
    return {
        "schema_version": 1,
        "method": "stage_b_locked_context_evaluation_v1",
        "status": "PASS" if all(
            passed for gates in gates_by_sequence.values() for passed in gates.values()
        ) else "REVISE",
        "one_time_locked_test_evaluation": True,
        "sequence_ids": [DEVELOPMENT_SEQUENCE_ID, LOCKED_TEST_SEQUENCE_ID],
        "locked_config": asdict(LOCKED_ADAPTIVE_V3_CONFIG),
        "calibration": {
            "fit_sequence": DEVELOPMENT_SEQUENCE_ID,
            "exact_context_temperature": FROZEN_EXACT_CONTEXT_TEMPERATURE,
            "sampled_stage_a_temperature": FROZEN_SAMPLED_STAGE_A_TEMPERATURE,
        },
        "thresholds": {
            "maximum_calibrated_brier_deterioration_vs_sampled": MAX_BRIER_DETERIORATION,
            "maximum_calibrated_ece_deterioration_vs_sampled": MAX_ECE_DETERIORATION,
            "maximum_exact_component_targets": 18,
        },
        "gates_by_sequence": gates_by_sequence,
        "sequence_results": {
            DEVELOPMENT_SEQUENCE_ID: development_summary,
            LOCKED_TEST_SEQUENCE_ID: locked_test,
        },
        "warning": (
            "Technical U373 benchmark only. The locked-test result is a final Stage B "
            "decision, not biological validation of GlioTrace."
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
        result = evaluate_locked(manifest, corruptions)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError, ArtifactValidationError) as exc:
        print(f"Stage B locked evaluation failed: {exc}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({result['status']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
