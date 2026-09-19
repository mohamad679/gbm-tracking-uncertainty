import unittest

from gbm_audit.final_audit import build_final_audit
from gbm_audit.validation import canonical_sha256


def _manifest():
    def sequence(sequence_id, split):
        return {"sequence_id": sequence_id, "split": split, "frames": 2,
                "shape_pixels": [10, 10], "tracks": []}
    return {
        "schema_version": 1,
        "dataset": "technical-test",
        "split_policy": "01 development, 02 test",
        "sequences": {"01": sequence("01", "development"), "02": sequence("02", "test")},
    }


def _scenario(scenario_id, corruption, severity, brier=0.1):
    return {"scenario_id": scenario_id, "corruption": corruption, "severity": severity,
            "sequence_results": {
                "01": {"candidate_true_link_coverage": 0.8,
                       "mean_speed_delta_vs_reference": -1.0,
                       "calibrated_hypothesis_calibration": {"brier": brier}},
                "02": {"candidate_true_link_coverage": 0.9,
                       "mean_speed_delta_vs_reference": -2.0,
                       "calibrated_hypothesis_calibration": {"brier": brier}},
            }}


def _stage(reference_hash, seed, scenarios, **extra):
    return {"schema_version": 1, "reference_manifest_sha256": reference_hash,
            "corruption_seed": seed, "scenarios": scenarios, **extra}


class TestFinalAudit(unittest.TestCase):
    def _inputs(self):
        manifest = _manifest()
        reference_hash = canonical_sha256(manifest)
        seed = 7
        corruptions = {
            "schema_version": 1,
            "dataset": manifest["dataset"],
            "reference_manifest_sha256": reference_hash,
            "seed": seed,
            "scenarios": [
                {"scenario_id": "clean_0", "corruption": "clean", "severity": 0,
                 "sequences": {"01": {}, "02": {}}},
                {"scenario_id": "localization_noise_5p0", "corruption": "localization_noise", "severity": 5.0,
                 "sequences": {"01": {}, "02": {}}},
            ],
        }
        uncertainty_scenarios = [
            _scenario("clean_0", "clean", 0),
            _scenario("localization_noise_5p0", "localization_noise", 5.0),
        ]
        uncertainty = _stage(reference_hash, seed, uncertainty_scenarios,
                             proposal_model="distance", calibration={"temperature": 1.0})
        dynamics = _stage(reference_hash, seed, [
            _scenario("clean_0", "clean", 0),
            _scenario("localization_noise_5p0", "localization_noise", 5.0),
        ])
        soft = _stage(reference_hash, seed, [
            _scenario("clean_0", "clean", 0),
            _scenario("localization_noise_5p0", "localization_noise", 5.0),
        ])
        appearance = _stage(reference_hash, seed, [
            _scenario("clean_0", "clean", 0, 0.3),
            _scenario("localization_noise_5p0", "localization_noise", 5.0, 0.4),
        ])
        gates = {
            "schema_version": 1,
            "reference_manifest_sha256": reference_hash,
            "corruption_seed": seed,
            "results": [
                {"max_distance_px": 8.0,
                 "clean_candidate_true_link_coverage": {"01": 0.80, "02": 0.90},
                 "noise_sigma_5_soft_speed_delta_px_per_frame": {"01": 0.2, "02": 1.1}},
                {"max_distance_px": 16.0,
                 "clean_candidate_true_link_coverage": {"01": 0.96, "02": 0.97},
                 "noise_sigma_5_soft_speed_delta_px_per_frame": {"01": 3.8, "02": 4.3}},
            ],
        }
        return manifest, corruptions, uncertainty, dynamics, soft, gates, appearance

    def test_final_audit_derives_operator_hold_from_gate_metrics(self):
        result = build_final_audit(*self._inputs())
        self.assertTrue(result["technical_benchmark_complete"])
        self.assertFalse(result["operator_learning_ready"])
        self.assertFalse(result["biological_validation_claim_supported"])
        self.assertEqual(result["decisions"][2]["status"], "HOLD")
        self.assertNotIn("tests_passed", result)

    def test_operator_gate_can_pass_when_coverage_and_robustness_both_pass(self):
        inputs = list(self._inputs())
        gates = inputs[5]
        gates["results"][1]["noise_sigma_5_soft_speed_delta_px_per_frame"] = {"01": 0.6, "02": 1.5}
        result = build_final_audit(*inputs)
        self.assertTrue(result["operator_learning_ready"])
        self.assertEqual(result["decisions"][2]["status"], "GO")


if __name__ == "__main__":
    unittest.main()
