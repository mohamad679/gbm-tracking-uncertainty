import copy
import unittest

from gbm_audit.stage_d_huh7_evaluation import BASELINES
from gbm_audit.stage_d_v3_evaluation import evaluation_gates


def _metric(rmse, error, coverage=0.90, stable=True):
    return {
        "one_step_velocity_rmse_px_per_frame": rmse,
        "mean_next_speed_absolute_error_px_per_frame": error,
        "nominal_90_interval_coverage": coverage,
        "stability": {"stability_pass": stable},
    }


class TestStageDV3Evaluation(unittest.TestCase):
    def test_all_frozen_gates_are_required(self):
        baselines = {
            BASELINES[0]: _metric(2.0, 0.20),
            BASELINES[1]: _metric(1.5, 0.10),
        }
        passing = _metric(1.0, 0.20)
        self.assertTrue(all(evaluation_gates(passing, baselines).values()))
        for key, value in (
            ("one_step_velocity_rmse_px_per_frame", 1.6),
            ("mean_next_speed_absolute_error_px_per_frame", 0.201),
            ("nominal_90_interval_coverage", 0.99),
        ):
            failed = copy.deepcopy(passing)
            failed[key] = value
            self.assertFalse(all(evaluation_gates(failed, baselines).values()))
        failed = copy.deepcopy(passing)
        failed["stability"]["stability_pass"] = False
        self.assertFalse(all(evaluation_gates(failed, baselines).values()))


if __name__ == "__main__":
    unittest.main()
