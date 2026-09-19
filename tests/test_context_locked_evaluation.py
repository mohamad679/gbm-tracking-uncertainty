import copy
import unittest

from gbm_audit.context_locked_evaluation import (
    evaluate_locked,
    locked_test_artifacts,
)
from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.validation import ArtifactValidationError


def _manifest():
    def sequence(sequence_id, split):
        return {
            "sequence_id": sequence_id,
            "split": split,
            "frames": 4,
            "shape_pixels": [32, 32],
            "tracks": [{
                "track_id": 1,
                "start_frame": 0,
                "end_frame": 3,
                "parent_id": 0,
                "observations": [
                    {"frame": frame, "x_px": float(frame), "y_px": 1.0, "area_px": 4}
                    for frame in range(4)
                ],
            }],
        }
    return {
        "schema_version": 1,
        "dataset": "synthetic-context-locked-test",
        "split_policy": "01 development, 02 test",
        "sequences": {
            "01": sequence("01", "development"),
            "02": sequence("02", "test"),
        },
    }


class TestContextLockedEvaluation(unittest.TestCase):
    def test_locked_evaluation_uses_frozen_calibration_and_reports_both_splits(self):
        manifest = _manifest()
        result = evaluate_locked(manifest, build_corruption_benchmark(manifest, seed=11))

        self.assertTrue(result["one_time_locked_test_evaluation"])
        self.assertEqual(result["sequence_ids"], ["01", "02"])
        self.assertEqual(result["calibration"]["fit_sequence"], "01")
        self.assertEqual(result["calibration"]["exact_context_temperature"], 0.55)
        self.assertEqual(result["calibration"]["sampled_stage_a_temperature"], 0.55)
        self.assertEqual(
            result["sequence_results"]["02"]["evaluation_role"], "one_time_locked_test"
        )
        self.assertEqual(len(result["sequence_results"]["02"]["scenario_results"]), 17)
        self.assertTrue(all(
            row["sequence_id"] == "02"
            for row in result["sequence_results"]["02"]["scenario_results"]
        ))
        for gates in result["gates_by_sequence"].values():
            self.assertEqual(set(gates), {
                "exact_invariants",
                "resource_bound",
                "calibrated_brier_noninferior",
                "calibrated_ece_noninferior",
            })

    def test_locked_filter_rejects_wrong_test_split(self):
        manifest = _manifest()
        broken = copy.deepcopy(manifest)
        broken["sequences"]["02"]["split"] = "development"
        corruptions = build_corruption_benchmark(broken, seed=11)

        with self.assertRaisesRegex(ArtifactValidationError, "sequence 02 must"):
            locked_test_artifacts(broken, corruptions)


if __name__ == "__main__":
    unittest.main()
