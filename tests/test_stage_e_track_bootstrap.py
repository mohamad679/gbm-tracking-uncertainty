import unittest

from gbm_audit.stage_e_track_bootstrap import bootstrap_clustered_link_effects


class TestStageETrackBootstrap(unittest.TestCase):
    def test_cluster_bootstrap_is_deterministic_and_track_level(self):
        probabilities = [0.95, 0.85, 0.20, 0.10, 0.90, 0.15]
        distance = [0.80, 0.70, 0.40, 0.30, 0.75, 0.35]
        labels = [1, 1, 0, 0, 1, 0]
        raw = [0.75, 0.70, 0.35, 0.30, 0.72, 0.32]
        clusters = [1, 1, 1, 2, 2, 2]
        first = bootstrap_clustered_link_effects(
            probabilities, distance, labels, raw, clusters, seed=17, iterations=200
        )
        second = bootstrap_clustered_link_effects(
            probabilities, distance, labels, raw, clusters, seed=17, iterations=200
        )
        self.assertEqual(first, second)
        self.assertEqual(first["track_cluster_count"], 2)
        self.assertEqual(first["link_count"], 6)
        self.assertIn("bootstrap_95pct_ci", first["effects"]["calibrated_error_auprc_minus_distance"])

    def test_better_calibration_has_positive_brier_delta(self):
        result = bootstrap_clustered_link_effects(
            [0.95, 0.05, 0.9, 0.1],
            [0.7, 0.3, 0.65, 0.35],
            [1, 0, 1, 0],
            [0.7, 0.3, 0.65, 0.35],
            [1, 1, 2, 2],
            seed=3,
            iterations=200,
        )
        self.assertGreater(
            result["effects"]["uncalibrated_brier_minus_calibrated_brier"]["point_delta"],
            0,
        )

    def test_rejects_edge_level_or_invalid_cluster_inputs(self):
        with self.assertRaisesRegex(ValueError, "same non-zero length"):
            bootstrap_clustered_link_effects([0.5], [0.5], [], [0.5], [1], iterations=100)
        with self.assertRaisesRegex(ValueError, "positive true-track"):
            bootstrap_clustered_link_effects([0.5, 0.5], [0.5, 0.5], [1, 0], [0.5, 0.5], [1, 0], iterations=100)
        with self.assertRaisesRegex(ValueError, "at least two true tracks"):
            bootstrap_clustered_link_effects([0.8, 0.2], [0.7, 0.3], [1, 0], [0.6, 0.4], [1, 1], iterations=100)


if __name__ == "__main__":
    unittest.main()
