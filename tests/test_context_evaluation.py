import copy
import unittest

from gbm_audit.context_evaluation import (
    development_only_artifacts,
    evaluate_development,
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
        "dataset": "synthetic-context-evaluation-test",
        "split_policy": "01 development, 02 test",
        "sequences": {
            "01": sequence("01", "development"),
            "02": sequence("02", "test"),
        },
    }


class TestContextEvaluation(unittest.TestCase):
    def test_development_evaluation_filters_locked_test_and_compares_methods(self):
        manifest = _manifest()
        result = evaluate_development(
            manifest, build_corruption_benchmark(manifest, seed=11)
        )

        self.assertEqual(result["status"], "DEVELOPMENT_COMPLETE")
        self.assertFalse(result["locked_test_sequence_evaluated"])
        self.assertEqual(len(result["scenario_ids"]), 17)
        self.assertTrue(result["exact_context"]["invariants_pass"])
        self.assertLessEqual(
            result["exact_context"]["components"]["maximum_component_targets"], 18
        )
        self.assertEqual(result["sampled_stage_a"]["hypothesis_count"], 64)
        self.assertTrue(all(row["sequence_id"] == "01" for row in result["scenario_results"]))
        for method in ("exact_context", "sampled_stage_a"):
            metrics = result[method]["aggregate_metrics"]
            self.assertIn("negative_log_likelihood", metrics["raw"])
            self.assertIn("brier", metrics["calibrated"])
            self.assertIn("ece", metrics["calibrated"])

    def test_development_filter_rejects_locked_split_drift(self):
        manifest = _manifest()
        broken = copy.deepcopy(manifest)
        broken["sequences"]["02"]["split"] = "development"
        corruptions = build_corruption_benchmark(broken, seed=11)

        with self.assertRaisesRegex(ArtifactValidationError, "requires development sequence"):
            development_only_artifacts(broken, corruptions)


if __name__ == "__main__":
    unittest.main()
