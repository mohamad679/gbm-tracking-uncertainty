import tempfile
import unittest
from pathlib import Path

from gbm_audit.stage_e_evaluation import (
    HYPOTHESIS_COUNT,
    POSTERIOR_TRACK_THRESHOLD,
    _assignment_links,
    _compatible_posterior_links,
    _dataset_seed,
    _decision,
    _frozen_dataset_config,
    _link_tracking_summary,
    _motion_errors,
    _motion_summary,
    _true_links,
)


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

    def test_dataset_seed_is_order_independent(self):
        ids = ["z", "a", "m"]
        self.assertEqual(_dataset_seed("a", ids), 20260922)
        self.assertEqual(_dataset_seed("m", list(reversed(ids))), 20260922 + 100000)

    def test_frozen_config_validates_registered_fields(self):
        development = {"datasets": {"x": {
            "candidate_selection": {"selected": {"max_distance_px": 8, "max_speed_um_per_min": 2}},
            "uncertainty_configuration": {
                "hypothesis_count": HYPOTHESIS_COUNT,
                "temperature_px": 3.5,
                "metric_summary": {"calibration_temperature": 0.75},
            },
        }}}
        config = _frozen_dataset_config(development, "x")
        self.assertEqual(config["max_distance_px"], 8.0)
        self.assertEqual(config["calibration_temperature"], 0.75)
        with self.assertRaisesRegex(ValueError, "missing frozen development"):
            _frozen_dataset_config(development, "missing")
        development["datasets"]["x"]["uncertainty_configuration"]["hypothesis_count"] = 1
        with self.assertRaisesRegex(ValueError, "hypothesis count"):
            _frozen_dataset_config(development, "x")

    def test_true_assignment_and_compatible_links(self):
        sequence = {"tracks": [{"track_id": 1, "observations": [
            {"frame": 0}, {"frame": 1}, {"frame": 3},
        ]}]}
        self.assertEqual(_true_links(sequence), {("ref_0001_0000", "ref_0001_0001")})
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "a1", "frame": 1, "x_px": 1.0, "y_px": 0.0},
            {"observation_id": "b1", "frame": 1, "x_px": 4.0, "y_px": 0.0},
        ]
        assignments = {"a0": 1, "a1": 1, "b1": 2}
        self.assertEqual(_assignment_links(observations, assignments), {("a0", "a1")})
        posterior = [
            {"from_observation_id": "a0", "to_observation_id": "a1", "probability": 0.9},
            {"from_observation_id": "a0", "to_observation_id": "b1", "probability": 0.8},
            {"from_observation_id": "ghost", "to_observation_id": "a1", "probability": 0.99},
        ]
        self.assertEqual(_compatible_posterior_links(observations, posterior, 1.0), {("a0", "a1")})

    def test_motion_and_tracking_summaries_cover_empty_and_nonempty_cases(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "a1", "frame": 1, "x_px": 3.0, "y_px": 4.0},
            {"observation_id": "solo", "frame": 0, "x_px": 10.0, "y_px": 10.0},
        ]
        summary = _motion_summary(observations, {("a0", "a1")})
        self.assertEqual(summary["consecutive_links"], 1)
        self.assertEqual(summary["mean_speed_px_per_frame"], 5.0)
        errors = _motion_errors(summary, summary)
        self.assertTrue(all(value == 0.0 for value in errors.values()))
        empty = _motion_summary(observations, set())
        self.assertEqual(empty["mean_speed_px_per_frame"], 0.0)
        tracking = _link_tracking_summary({("a0", "a1")}, {("a0", "a1"), ("a1", "a2")})
        self.assertEqual(tracking["link_precision"], 1.0)
        self.assertEqual(tracking["link_recall"], 0.5)
        self.assertEqual(tracking["fragmentation_proxy"], 1)

    def test_decision_exercises_risk_calibration_and_motion_failures(self):
        results = {
            "gowt1": _dataset(calibrated_risk=0.2, calibrated_brier=0.2, calibrated_ece=0.2, win=False),
            "hela": _dataset(win=False),
        }
        gates, decision = _decision(results, self.protocol)
        self.assertEqual(decision, "REVISE")
        self.assertFalse(gates["selective_risk_improves_over_full_coverage_on_both_real_tests"])
        self.assertFalse(gates["calibration_improves_under_registered_rule"])
        self.assertFalse(gates["motion_endpoint_wins_at_least_five_of_eight"])


if __name__ == "__main__":
    unittest.main()
