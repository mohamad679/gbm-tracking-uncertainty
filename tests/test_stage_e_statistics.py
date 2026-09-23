import unittest

from gbm_audit.stage_e_statistics import analyze_stage_e_statistics


ENDPOINTS = (
    "mean_speed_absolute_error",
    "total_path_length_relative_absolute_error",
    "net_displacement_relative_absolute_error",
    "directionality_absolute_error",
)


def _scenario(scenario_id: str, hard: float, soft: float, auprc_soft: float,
              auprc_distance: float, full_risk: float, selective_risk: float,
              raw_brier: float, calibrated_brier: float) -> dict:
    hard_errors = {name: hard for name in ENDPOINTS}
    soft_errors = {name: soft for name in ENDPOINTS}
    return {
        "scenario_id": scenario_id,
        "motion": {
            "hard_nearest_neighbor": {"errors": hard_errors},
            "uncertainty_compatible_p50": {"errors": soft_errors},
        },
        "association": {
            "distance_confidence": {"association_error_auprc": auprc_distance},
            "uncalibrated_uncertainty": {"calibration": {"brier": raw_brier}},
            "calibrated_uncertainty": {
                "association_error_auprc": auprc_soft,
                "selective_link_risk": {"risk": selective_risk},
                "calibration": {"brier": calibrated_brier},
            },
            "calibrated_full_coverage_risk": full_risk,
        },
    }


def _evaluation() -> dict:
    dataset = {
        "scenarios": [
            _scenario("clean_0", 0.3, 0.1, 0.9, 0.8, 0.2, 0.05, 0.10, 0.04),
            _scenario("noise_1", 0.4, 0.2, 0.85, 0.75, 0.3, 0.10, 0.12, 0.05),
            _scenario("noise_2", 0.5, 0.4, 0.80, 0.78, 0.4, 0.20, 0.15, 0.08),
        ]
    }
    return {
        "evaluation_count": 1,
        "evaluation_attempted": True,
        "method": "locked-test",
        "decision": "REVISE",
        "results": {"a": dataset, "b": dataset},
    }


class TestStageEStatistics(unittest.TestCase):
    protocol = {"evaluation_panel": {"real_confirmatory_domains": ["a", "b"]}}

    def test_positive_deltas_favor_uncertainty_and_preserve_decision(self):
        result = analyze_stage_e_statistics(
            _evaluation(), self.protocol, seed=7, iterations=500
        )
        self.assertEqual(result["source_decision"], "REVISE")
        self.assertTrue(result["source_decision_unchanged"])
        dataset = result["per_dataset"]["a"]
        self.assertEqual(dataset["registered_clean_motion_wins"], 4)
        for endpoint in ENDPOINTS:
            summary = dataset["paired_motion_error_reduction"][endpoint]
            self.assertGreater(summary["mean_delta"], 0)
            self.assertEqual(summary["win_fraction"], 1.0)
        association = dataset["association_and_calibration_effects"]
        self.assertGreater(
            association["calibrated_error_auprc_minus_distance"]["mean_delta"], 0
        )
        self.assertGreater(
            association["full_coverage_risk_minus_selective_risk"]["mean_delta"], 0
        )
        self.assertGreater(
            association["uncalibrated_brier_minus_calibrated_brier"]["mean_delta"], 0
        )

    def test_is_deterministic(self):
        first = analyze_stage_e_statistics(_evaluation(), self.protocol, seed=11, iterations=300)
        second = analyze_stage_e_statistics(_evaluation(), self.protocol, seed=11, iterations=300)
        self.assertEqual(first, second)

    def test_rejects_missing_registered_domain(self):
        broken = _evaluation()
        del broken["results"]["b"]
        with self.assertRaisesRegex(ValueError, "missing registered real domains"):
            analyze_stage_e_statistics(broken, self.protocol, iterations=100)

    def test_requires_published_one_time_artifact(self):
        broken = _evaluation()
        broken["evaluation_count"] = 0
        with self.assertRaisesRegex(ValueError, "one-time"):
            analyze_stage_e_statistics(broken, self.protocol, iterations=100)


if __name__ == "__main__":
    unittest.main()
