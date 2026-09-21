import copy
import unittest

from gbm_audit.stage_d_huh7_evaluation import (
    BASELINES,
    CANDIDATE,
    _decision,
)


def _metric(rmse, summary_error, coverage=0.90, stable=True):
    return {
        "one_step_velocity_rmse_px_per_frame": rmse,
        "mean_next_speed_absolute_error_px_per_frame": summary_error,
        "nominal_90_interval_coverage": coverage,
        "stability": {"stability_pass": stable},
    }


class TestStageDHuh7Evaluation(unittest.TestCase):
    def test_go_requires_every_pre_registered_gate(self):
        metrics = {
            BASELINES[0]: _metric(2.0, 0.20),
            BASELINES[1]: _metric(1.5, 0.10),
            CANDIDATE: _metric(1.0, 0.15),
        }
        gates, decision = _decision(metrics)
        self.assertEqual(decision, "GO")
        self.assertTrue(all(gates.values()))

        failure_fields = {
            "primary": ("one_step_velocity_rmse_px_per_frame", 2.5),
            "noninferiority": ("mean_next_speed_absolute_error_px_per_frame", 0.21),
            "coverage": ("nominal_90_interval_coverage", 0.79),
        }
        for field, (key, value) in failure_fields.items():
            with self.subTest(field=field):
                failed = copy.deepcopy(metrics)
                failed[CANDIDATE][key] = value
                _, failed_decision = _decision(failed)
                self.assertEqual(failed_decision, "HOLD")

        failed = copy.deepcopy(metrics)
        failed[CANDIDATE]["stability"]["stability_pass"] = False
        _, failed_decision = _decision(failed)
        self.assertEqual(failed_decision, "HOLD")

    def test_noninferiority_margin_is_inclusive_and_fixed_at_point_one(self):
        metrics = {
            BASELINES[0]: _metric(2.0, 0.20),
            BASELINES[1]: _metric(1.5, 0.10),
            CANDIDATE: _metric(1.0, 0.20),
        }
        gates, decision = _decision(metrics)
        self.assertTrue(gates["state_summary_noninferiority"])
        self.assertEqual(decision, "GO")


if __name__ == "__main__":
    unittest.main()
