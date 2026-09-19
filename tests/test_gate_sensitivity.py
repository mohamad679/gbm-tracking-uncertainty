import unittest

from gbm_audit.gate_sensitivity import summarize_gate


class TestGateSensitivity(unittest.TestCase):
    def test_summary_reports_coverage_and_speed_deltas(self):
        uncertainty = {"scenarios": [{"scenario_id": "clean_0", "sequence_results": {
            "01": {"candidate_true_link_coverage": 0.8}, "02": {"candidate_true_link_coverage": 0.9}
        }}]}
        def soft_scenario(scenario_id, d1, d2):
            return {"scenario_id": scenario_id, "sequence_results": {
                "01": {"mean_speed_px_per_frame": 3.0, "mean_speed_delta_vs_reference": d1},
                "02": {"mean_speed_px_per_frame": 4.0, "mean_speed_delta_vs_reference": d2},
            }}
        soft = {"scenarios": [soft_scenario("clean_0", -1.0, -2.0),
                              soft_scenario("localization_noise_5p0", 0.5, 1.5)]}
        result = summarize_gate(uncertainty, soft, 12.0)
        self.assertEqual(result["max_distance_px"], 12.0)
        self.assertEqual(result["clean_candidate_true_link_coverage"]["01"], 0.8)
        self.assertEqual(result["clean_soft_speed_delta_px_per_frame"]["02"], -2.0)
        self.assertEqual(result["mean_absolute_soft_speed_delta_px_per_frame"]["01"], 0.75)


if __name__ == "__main__":
    unittest.main()
