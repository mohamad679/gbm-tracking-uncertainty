import unittest

import numpy as np

from gbm_audit.stage_d_operators import (
    FORBIDDEN_SEQUENCE_IDS,
    FrozenHMMSpeedBaseline,
    StageDOperatorConfig,
    StableLinearKoopmanOperator,
    WeightedEmpiricalTransitionBaseline,
    candidate_registry,
    validate_transition_rows,
)


def _rows():
    return [
        {"sequence_id": "01", "state": [0.0, 1.0], "next_state": [0.5, 1.0], "uncertainty_weight": 1.0},
        {"sequence_id": "01", "state": [1.0, 1.0], "next_state": [1.5, 0.9], "uncertainty_weight": 2.0},
        {"sequence_id": "01", "state": [2.0, 0.9], "next_state": [2.4, 0.8], "uncertainty_weight": 1.0},
    ]


class TestStageDOperators(unittest.TestCase):
    def test_registry_is_declarative_and_contains_required_candidates(self):
        registry = candidate_registry()
        self.assertEqual(set(registry), {
            "frozen_hmm_speed_baseline_v1",
            "weighted_empirical_transition_baseline_v1",
            "stable_linear_koopman_operator_v1",
        })

    def test_forbidden_sequence_and_truth_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_transition_rows([{**_rows()[0], "sequence_id": "02"}])
        with self.assertRaises(ValueError):
            validate_transition_rows([{**_rows()[0], "evaluation_truth": {"x": 1}}])
        self.assertIn("T98G_sample", FORBIDDEN_SEQUENCE_IDS)

    def test_weighted_empirical_baseline_is_deterministic(self):
        model = WeightedEmpiricalTransitionBaseline.fit(_rows())
        np.testing.assert_allclose(model.predict([1.0, 1.0]), [1.475, 0.925], atol=1e-12)
        self.assertEqual(model.fit_sequence_id, "01")
        self.assertEqual(model.row_count, 3)

    def test_koopman_operator_is_finite_and_stable(self):
        model = StableLinearKoopmanOperator.fit(
            _rows(), config=StageDOperatorConfig(max_spectral_radius=0.8, forecast_horizon=5)
        )
        report = model.stability_report()
        self.assertTrue(report["finite_matrix"])
        self.assertTrue(report["stability_pass"])
        self.assertLessEqual(report["spectral_radius"], 0.8 + 1e-10)
        self.assertEqual(model.rollout([0.0, 1.0]).shape, (6, 2))

    def test_frozen_hmm_baseline_does_not_fit(self):
        baseline = FrozenHMMSpeedBaseline({
            "status": "ok",
            "state_means_px_per_frame": [0.2, 2.0],
            "state_stds_px_per_frame": [0.4, 1.0],
            "transition_matrix": [[0.8, 0.2], [0.1, 0.9]],
            "initial_state_probability": [1.0, 0.0],
        })
        result = baseline.predict_speed()
        self.assertEqual(result["baseline"], "frozen_hmm_speed_baseline_v1")
        self.assertGreater(result["expected_speed_px_per_frame"], 0.0)


if __name__ == "__main__":
    unittest.main()
