import copy
import unittest

from gbm_audit.stage_d_huh7_evaluation import BASELINES
from gbm_audit.stage_d_v3_development import development_gate


def _baseline(rmse, error):
    return {
        "one_step_velocity_rmse_px_per_frame": rmse,
        "mean_next_speed_absolute_error_px_per_frame": error,
    }


def _candidate(rmse=1.0, error=0.15, stable=True):
    return {
        "one_step_velocity_rmse_px_per_frame": rmse,
        "mean_next_speed_absolute_error_px_per_frame": error,
        "stability": {"stability_pass": stable},
    }


class TestStageDV3Development(unittest.TestCase):
    def test_development_gate_requires_improvement_noninferiority_and_stability(self):
        baselines = {
            BASELINES[0]: _baseline(2.0, 0.20),
            BASELINES[1]: _baseline(1.5, 0.10),
        }
        self.assertTrue(development_gate(_candidate(), baselines)["pass"])
        self.assertFalse(development_gate(_candidate(rmse=1.6), baselines)["pass"])
        self.assertFalse(development_gate(_candidate(error=0.201), baselines)["pass"])
        self.assertFalse(development_gate(_candidate(stable=False), baselines)["pass"])


if __name__ == "__main__":
    unittest.main()
