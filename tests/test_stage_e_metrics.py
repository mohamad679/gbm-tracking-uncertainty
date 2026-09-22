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
        self.assertEqual(report["selective_link_risk"]["coverage"], 0.8)


if __name__ == "__main__":
    unittest.main()
