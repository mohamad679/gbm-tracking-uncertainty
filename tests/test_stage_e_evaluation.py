import unittest

from gbm_audit.stage_e_evaluation import POSTERIOR_TRACK_THRESHOLD, _decision


def _dataset(*, auprc=0.9, distance=0.7, calibrated_risk=0.01, full_risk=0.05,
             calibrated_brier=0.02, raw_brier=0.04, calibrated_ece=0.01,
             raw_ece=0.08, win=True):
    errors = {
        "mean_speed_absolute_error": 0.1 if win else 0.3,
        "total_path_length_relative_absolute_error": 0.1 if win else 0.3,
        "net_displacement_relative_absolute_error": 0.1 if win else 0.3,
        "directionality_absolute_error": 0.1 if win else 0.3,
    }
    hard = {key: 0.2 for key in errors}
    return {
        "clean_primary_endpoints": {
            "distance_confidence": {"association_error_auprc": distance},
            "uncalibrated_uncertainty": {"calibration": {"brier": raw_brier, "ece": raw_ece}},
            "calibrated_uncertainty": {
                "association_error_auprc": auprc,
                "selective_link_risk": {"risk": calibrated_risk},
                "calibration": {"brier": calibrated_brier, "ece": calibrated_ece},
            },
            "calibrated_full_coverage_risk": full_risk,
        },
        "scenarios": [{"motion": {
            "hard_nearest_neighbor": {"errors": hard},
            "uncertainty_compatible_p50": {"errors": errors},
        }}],
    }


class TestStageELockedDecision(unittest.TestCase):
    protocol = {"evaluation_panel": {"real_confirmatory_domains": ["gowt1", "hela"]}}

    def test_registered_threshold_is_fixed(self):
        self.assertEqual(POSTERIOR_TRACK_THRESHOLD, 0.5)

    def test_all_registered_gates_pass_to_go(self):
        gates, decision = _decision({"gowt1": _dataset(), "hela": _dataset()}, self.protocol)
        self.assertEqual(decision, "GO")
        self.assertEqual(gates["motion_endpoint_wins"], 8)

    def test_any_real_domain_failure_is_revise(self):
        gates, decision = _decision({"gowt1": _dataset(), "hela": _dataset(auprc=0.6)}, self.protocol)
        self.assertEqual(decision, "REVISE")
        self.assertFalse(gates["calibrated_error_auprc_beats_distance_on_both_real_tests"])


if __name__ == "__main__":
    unittest.main()
