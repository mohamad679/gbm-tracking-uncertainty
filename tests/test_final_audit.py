import unittest

from gbm_audit.final_audit import build_final_audit


def _scenario(scenario_id, brier=0.1):
    return {"scenario_id": scenario_id, "sequence_results": {
        "01": {"candidate_true_link_coverage": 0.8,
                "mean_speed_delta_vs_reference": -1.0,
                "calibrated_hypothesis_calibration": {"brier": brier}},
        "02": {"candidate_true_link_coverage": 0.9,
                "mean_speed_delta_vs_reference": -2.0,
                "calibrated_hypothesis_calibration": {"brier": brier}},
    }}


class TestFinalAudit(unittest.TestCase):
    def test_final_audit_makes_operator_hold_explicit(self):
        manifest = {"dataset": "test", "split_policy": "sequence split"}
        corruptions = {"reference_manifest_sha256": "abc", "scenarios": [{"scenario_id": "x"}]}
        uncertainty = {"proposal_model": "distance", "calibration": {"temperature": 1.0},
                       "scenarios": [_scenario("clean_0"), _scenario("localization_noise_5p0")]}
        dynamics = {"scenarios": []}
        soft = {"scenarios": [_scenario("clean_0"), _scenario("localization_noise_5p0")]}
        gates = {"results": [{"max_distance_px": 8}]}
        appearance = {"scenarios": [_scenario("clean_0", 0.3), _scenario("localization_noise_5p0", 0.4)]}
        result = build_final_audit(manifest, corruptions, uncertainty, dynamics, soft,
                                   gates, appearance, test_count=27)
        self.assertFalse(result["operator_learning_ready"])
        self.assertEqual(result["tests_passed"], 27)
        self.assertEqual(result["decisions"][2]["status"], "HOLD")


if __name__ == "__main__":
    unittest.main()
