import copy
import unittest

from gbm_audit.adaptive_candidates import AdaptiveCandidateConfig, generate_adaptive_candidate_graph
from gbm_audit.context_posterior import MAX_EXACT_COMPONENT_TARGETS
from gbm_audit.stage_c_v2_sampler import (
    StageCV2SamplerConfig,
    build_recovery_graph,
    fit_localization_model,
    localization_diagnostics,
    perturb_localization,
    sample_exact_predictive_matchings,
    sample_stage_c_v2_ensemble,
)


def _observations():
    rows = []
    for frame in range(3):
        rows.extend([
            {"observation_id": f"a{frame}", "frame": frame, "x_px": float(frame), "y_px": 0.0},
            {"observation_id": f"b{frame}", "frame": frame, "x_px": 20.0 + frame, "y_px": 0.0},
        ])
    return rows


def _model():
    return fit_localization_model([
        {"residual_dx_px": 1.0, "residual_dy_px": 0.0,
         "median_proposal_distance_px": 1.0, "candidate_degree": 1},
        {"residual_dx_px": 2.0, "residual_dy_px": 0.0,
         "median_proposal_distance_px": 2.0, "candidate_degree": 2},
        {"residual_dx_px": 3.0, "residual_dy_px": 0.0,
         "median_proposal_distance_px": 3.0, "candidate_degree": 3},
    ])


class TestStageCV2Sampler(unittest.TestCase):
    def test_localization_fit_and_perturbation_are_deterministic(self):
        observations = _observations()
        graph = generate_adaptive_candidate_graph(observations)
        diagnostics = localization_diagnostics(observations, graph["candidate_edges"])
        first = perturb_localization(observations, diagnostics, _model(), seed=5)
        second = perturb_localization(observations, diagnostics, _model(), seed=5)
        self.assertEqual(first, second)
        self.assertTrue(first[1]["truth_blind"])
        self.assertNotIn("true_track_id", str(first))

    def test_application_is_invariant_to_truth_fields(self):
        base = _observations()
        with_truth = [
            {
                **row,
                "true_track_id": 1000 + index,
                "observed_track_id": -index,
                "reference_track_id": f"ref-{index}",
                "evaluation_truth": {"is_reference": True},
                "truth": "forbidden",
                "parent_id": f"parent-{index}",
                "start_frame": 0,
                "end_frame": 2,
            }
            for index, row in enumerate(base)
        ]
        first = sample_stage_c_v2_ensemble(
            base, primary_config=AdaptiveCandidateConfig(), localization_model=_model(),
            sampler_config=StageCV2SamplerConfig(ensemble_count=8), seed=9,
        )
        second = sample_stage_c_v2_ensemble(
            with_truth, primary_config=AdaptiveCandidateConfig(), localization_model=_model(),
            sampler_config=StageCV2SamplerConfig(ensemble_count=8), seed=9,
        )
        self.assertEqual(first, second)
        self.assertTrue(first["invariants"]["truth_blind_pass"])
        for forbidden in (
                "true_track_id", "observed_track_id", "reference_track_id",
                "evaluation_truth", "parent_id", "start_frame", "end_frame"):
            self.assertNotIn(forbidden, str(first))

    def test_recovery_graph_contains_shell_and_gap_edges(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "b1", "frame": 1, "x_px": 1.0, "y_px": 0.0},
            {"observation_id": "shell1", "frame": 1, "x_px": 0.0, "y_px": 24.0},
            {"observation_id": "d0", "frame": 0, "x_px": 100.0, "y_px": 0.0},
            {"observation_id": "c2", "frame": 2, "x_px": 148.0, "y_px": 0.0},
        ]
        primary = generate_adaptive_candidate_graph(observations, AdaptiveCandidateConfig())
        recovery = build_recovery_graph(observations, primary)
        types = {edge["proposal_type"] for edge in recovery["candidate_edges"]}
        self.assertIn("primary", types)
        self.assertIn("recovery_adjacent", types)
        self.assertIn("recovery_bridge", types)
        bridges = [edge for edge in recovery["candidate_edges"] if edge["delta_t"] == 2]
        self.assertTrue(all(edge["proposal_score_px"] == edge["distance_px"] / 2 for edge in bridges))
        self.assertTrue(recovery["truth_blind"])

    def test_exact_sampler_competes_bridge_and_adjacent_edges_globally(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "b1", "frame": 1, "x_px": 1.0, "y_px": 0.0},
            {"observation_id": "c2", "frame": 2, "x_px": 2.0, "y_px": 0.0},
        ]
        edges = [
            {"from_observation_id": "a0", "to_observation_id": "b1", "delta_t": 1,
             "proposal_score_px": 0.0, "proposal_type": "primary",
             "interpolated_observation_id": None},
            {"from_observation_id": "a0", "to_observation_id": "c2", "delta_t": 2,
             "proposal_score_px": 0.0, "proposal_type": "recovery_bridge",
             "interpolated_frame": 1, "interpolated_observation_id": "bridge:a0:c2"},
        ]
        result = sample_exact_predictive_matchings(observations, edges, count=128, seed=7)
        self.assertTrue(result["invariants"]["one_to_one_pass"])
        self.assertTrue(result["invariants"]["candidate_graph_pass"])
        for sample in result["samples"]:
            selected = {(row["from_observation_id"], row["to_observation_id"]) for row in sample["links"]}
            self.assertFalse({("a0", "b1"), ("a0", "c2")} <= selected)

    def test_exact_resource_bound_is_explicit(self):
        observations = [{"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0}]
        observations.extend(
            {"observation_id": f"b{index}", "frame": 1, "x_px": float(index), "y_px": 0.0}
            for index in range(MAX_EXACT_COMPONENT_TARGETS + 1)
        )
        edges = [
            {"from_observation_id": "a0", "to_observation_id": f"b{index}", "delta_t": 1,
             "proposal_score_px": 1.0, "proposal_type": "primary",
             "interpolated_observation_id": None}
            for index in range(MAX_EXACT_COMPONENT_TARGETS + 1)
        ]
        with self.assertRaisesRegex(ValueError, "approved limit"):
            sample_exact_predictive_matchings(observations, edges, count=1)


if __name__ == "__main__":
    unittest.main()

