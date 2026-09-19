import unittest

import numpy as np

from gbm_audit.soft_dynamics import _transition_counts_indexed, soft_summary


class TestSoftDynamics(unittest.TestCase):
    def test_weighted_speed_uses_probabilities_not_hard_threshold(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "a1", "frame": 1, "x_px": 1.0, "y_px": 0.0},
            {"observation_id": "b1", "frame": 1, "x_px": 5.0, "y_px": 0.0},
        ]
        posterior = [
            {"from_observation_id": "a0", "to_observation_id": "a1", "distance_px": 1.0, "probability": 0.6},
            {"from_observation_id": "a0", "to_observation_id": "b1", "distance_px": 5.0, "probability": 0.4},
        ]
        result = soft_summary(observations, posterior, calibration_temperature=1.0)
        self.assertGreater(result["expected_link_mass"], 0)
        self.assertGreater(result["mean_speed_px_per_frame"], 1.0)
        self.assertLess(result["mean_speed_px_per_frame"], 5.0)

    def test_soft_summary_is_deterministic(self):
        observations = [{"observation_id": f"a{i}", "frame": i, "x_px": float(i), "y_px": 0.0} for i in range(5)]
        posterior = [{"from_observation_id": f"a{i}", "to_observation_id": f"a{i+1}", "distance_px": 1.0, "probability": 0.8} for i in range(4)]
        self.assertEqual(soft_summary(observations, posterior, 0.25), soft_summary(observations, posterior, 0.25))

    def test_indexed_transition_counts_match_quadratic_reference(self):
        edges = [
            {"left": "a0", "right": "a1", "frame": 1, "weight": 0.7},
            {"left": "b0", "right": "b1", "frame": 1, "weight": 0.5},
            {"left": "a1", "right": "a2", "frame": 2, "weight": 0.8},
            {"left": "b1", "right": "b2", "frame": 2, "weight": 0.6},
        ]
        responsibilities = np.asarray([[0.9, 0.1], [0.2, 0.8], [0.7, 0.3], [0.4, 0.6]])
        expected = np.zeros((2, 2), dtype=float)
        for index, first in enumerate(edges):
            for second_index in range(index, len(edges)):
                second = edges[second_index]
                if first["right"] != second["left"] or second["frame"] != first["frame"] + 1:
                    continue
                expected += first["weight"] * second["weight"] * np.outer(
                    responsibilities[index], responsibilities[second_index]
                )
        np.testing.assert_allclose(_transition_counts_indexed(edges, responsibilities), expected)


if __name__ == "__main__":
    unittest.main()
