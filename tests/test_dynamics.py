import unittest

from gbm_audit.dynamics import fit_hmm, posterior_labels, summarize_tracks


class TestDynamics(unittest.TestCase):
    def test_hmm_recovers_two_speed_regimes(self):
        result = fit_hmm([[1.0, 1.1, 0.9, 1.0], [5.0, 5.1, 4.9, 5.0]])
        self.assertEqual(result["status"], "ok")
        self.assertLess(result["state_means_px_per_frame"][0], result["state_means_px_per_frame"][1])

    def test_posterior_labels_ignore_truth_fields(self):
        rows = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "a1", "frame": 1, "x_px": 1.0, "y_px": 0.0},
            {"observation_id": "b1", "frame": 1, "x_px": 8.0, "y_px": 8.0},
        ]
        links = [{"from_observation_id": "a0", "to_observation_id": "a1", "probability": 1.0, "true_link": False},
                 {"from_observation_id": "a0", "to_observation_id": "b1", "probability": 0.1, "true_link": True}]
        labels = posterior_labels(rows, links, 0.5, 1.0)
        self.assertEqual(labels["a0"], labels["a1"])
        self.assertNotEqual(labels["a0"], labels["b1"])

    def test_summary_contains_hmm_and_migration_features(self):
        tracks = [[{"frame": i, "x_px": float(i), "y_px": 0.0} for i in range(5)]]
        summary = summarize_tracks(tracks)
        self.assertEqual(summary["consecutive_steps"], 4)
        self.assertEqual(summary["hmm_2state"]["status"], "ok")


if __name__ == "__main__":
    unittest.main()
