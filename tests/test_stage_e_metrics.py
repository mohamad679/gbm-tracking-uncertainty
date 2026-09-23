import unittest

from gbm_audit.stage_e_metrics import (
    average_precision,
    distance_confidence,
    link_score_report,
    probability_metrics,
    selective_link_risk,
)


class TestStageEMetrics(unittest.TestCase):
    def test_perfect_ranking_and_selective_risk(self):
        scores = [0.9, 0.8, 0.2, 0.1]
        labels = [1, 1, 0, 0]
        self.assertEqual(average_precision(scores, labels), 1.0)
        self.assertEqual(selective_link_risk(scores, labels, 0.5)["risk"], 0.0)

    def test_distance_confidence_is_monotone_and_bounded(self):
        values = distance_confidence([0.0, 4.0, 8.0, 16.0], 8.0)
        self.assertEqual(values, [1.0, 0.5, 0.0, 0.0])

    def test_probability_metrics_and_report_have_registered_fields(self):
        probabilities = [0.9, 0.1]
        labels = [1, 0]
        metrics = probability_metrics(probabilities, labels)
        self.assertLess(metrics["brier"], 0.02)
        self.assertGreater(metrics["nll"], 0.0)
        report = link_score_report(probabilities, labels)
        self.assertIn("association_error_auprc", report)
        self.assertEqual(report["association_error_auprc"], 1.0)
        self.assertEqual(report["selective_link_risk"]["coverage"], 0.8)

    def test_error_auprc_uses_inverse_of_correct_link_probability(self):
        report = link_score_report([0.95, 0.8, 0.15, 0.05], [1, 1, 0, 0])
        self.assertEqual(report["association_error_auprc"], 1.0)

    def test_metric_contracts_reject_mismatched_lengths_and_bad_coverage(self):
        with self.assertRaisesRegex(ValueError, "same length"):
            average_precision([0.5], [])
        with self.assertRaisesRegex(ValueError, "same length"):
            selective_link_risk([0.5], [])
        with self.assertRaisesRegex(ValueError, "coverage"):
            selective_link_risk([0.5], [1], 0.0)
        with self.assertRaisesRegex(ValueError, "same length"):
            probability_metrics([0.5], [])

    def test_empty_and_degenerate_metric_inputs_are_explicit(self):
        self.assertEqual(average_precision([0.9, 0.1], [0, 0]), 0.0)
        self.assertEqual(selective_link_risk([], [], 0.8), {"coverage": 0.8, "accepted": 0, "risk": 0.0})
        self.assertEqual(probability_metrics([], []), {"brier": 0.0, "ece": 0.0, "nll": 0.0, "count": 0})
        with self.assertRaisesRegex(ValueError, "positive"):
            distance_confidence([1.0], 0.0)

    def test_probability_metrics_clip_extreme_values_and_populate_bins(self):
        metrics = probability_metrics([-1.0, 0.25, 0.75, 2.0], [0, 0, 1, 1], bins=4)
        self.assertEqual(metrics["count"], 4)
        self.assertGreaterEqual(metrics["brier"], 0.0)
        self.assertGreaterEqual(metrics["ece"], 0.0)
        self.assertGreater(metrics["nll"], 0.0)


if __name__ == "__main__":
    unittest.main()
