import copy
import unittest

from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.stage_c_locked_evaluation import evaluate_locked, locked_test_artifacts
from gbm_audit.validation import ArtifactValidationError


def _manifest():
    def sequence(sequence_id, split, speed):
        return {
            "sequence_id": sequence_id,
            "split": split,
            "frames": 6,
            "shape_pixels": [64, 64],
            "tracks": [{
                "track_id": 1,
                "start_frame": 0,
                "end_frame": 5,
                "parent_id": 0,
                "observations": [
                    {"frame": frame, "x_px": speed * frame, "y_px": 1.0, "area_px": 4}
                    for frame in range(6)
                ],
            }, {
                "track_id": 2,
                "start_frame": 0,
                "end_frame": 5,
                "parent_id": 0,
                "observations": [
                    {"frame": frame, "x_px": 2.0 * frame, "y_px": 12.0, "area_px": 4}
                    for frame in range(6)
                ],
            }],
        }
    return {
        "schema_version": 1,
        "dataset": "synthetic-stage-c-locked-test",
        "split_policy": "01 development, 02 test",
        "sequences": {
            "01": sequence("01", "development", 1.0),
            "02": sequence("02", "test", 4.0),
        },
    }


class TestStageCLockedEvaluation(unittest.TestCase):
    def test_locked_evaluation_uses_registered_hmm_and_test_split(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        corruptions["scenarios"] = corruptions["scenarios"][:1]
        result = evaluate_locked(manifest, corruptions)

        self.assertTrue(result["one_time_locked_test_evaluation"])
        self.assertEqual(result["locked_test_sequence"], "02")
        self.assertEqual(result["frozen_hmm"]["fit_sequence"], "01")
        self.assertEqual(result["ensemble"]["count"], 256)
        self.assertEqual([row["sequence_id"] for row in result["scenarios"]], ["02"])
        self.assertEqual(set(result["gates"]), {
            "ensemble_and_component_invariants",
            "mean_speed_interval_coverage",
            "mean_speed_error_noninferiority",
            "required_summary_completeness",
        })
        self.assertEqual(result["coverage"]["eligible"], 1)

    def test_locked_filter_rejects_split_drift(self):
        manifest = _manifest()
        broken = copy.deepcopy(manifest)
        broken["sequences"]["02"]["split"] = "development"
        with self.assertRaisesRegex(ArtifactValidationError, "sequence 02 must"):
            locked_test_artifacts(broken, build_corruption_benchmark(broken, seed=11))


if __name__ == "__main__":
    unittest.main()
