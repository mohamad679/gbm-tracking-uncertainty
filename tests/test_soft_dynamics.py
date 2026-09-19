import unittest

from gbm_audit.soft_dynamics import soft_summary


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


if __name__ == "__main__":
    unittest.main()
