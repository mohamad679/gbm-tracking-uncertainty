import unittest
from unittest.mock import patch

from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.locked_evaluation import evaluate_locked
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
        "dataset": "synthetic-locked-test",
        "split_policy": "01 development, 02 test",
        "sequences": {
            "01": sequence("01", "development"),
            "02": sequence("02", "test"),
        },
    }


class TestLockedEvaluation(unittest.TestCase):
    def test_locked_evaluation_includes_both_sequences_once(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=7)
        row = {
            "clean_true_link_recall": 0.96,
            "clean_candidate_edges": 12,
            "clean_candidate_burden_edges_per_target": 1.5,
            "clean_soft_speed_error_px_per_frame": 0.2,
            "noise_sigma_5_soft_speed_error_px_per_frame": 0.5,
        }
        summaries = {
            "fixed_8": {"sequence_results": {"01": row, "02": row}},
            "fixed_16": {"sequence_results": {"01": row, "02": row}},
            "adaptive_v3": {"sequence_results": {"01": row, "02": row}},
        }
        area = {
            "fixed_16_mean_search_area_px2": 804.0,
            "adaptive_mean_search_area_px2": 680.0,
            "search_area_reduction_vs_fixed_16_fraction": 0.154,
        }
        with patch("gbm_audit.locked_evaluation._fixed_baseline_run", side_effect=[({}, {}, {}), ({}, {}, {})]), \
                patch("gbm_audit.locked_evaluation.evaluate_benchmark", return_value={}), \
                patch("gbm_audit.dynamics.evaluate_dynamics", return_value={}), \
                patch("gbm_audit.soft_dynamics.evaluate_soft_dynamics", return_value={}), \
                patch("gbm_audit.locked_evaluation.summarize_run", side_effect=lambda name, *_: summaries[name]), \
                patch("gbm_audit.locked_evaluation.generate_adaptive_candidate_graph", return_value={}), \
                patch("gbm_audit.locked_evaluation._spatial_metrics", return_value=area):
            result = evaluate_locked(manifest, corruptions)
        self.assertTrue(result["one_time_locked_test_evaluation"])
        self.assertEqual(result["sequence_ids"], ["01", "02"])
        self.assertEqual(set(result["sequence_results"]), {"01", "02"})
        self.assertEqual(result["locked_config_id"], "m2.75-d0-c4-n10-p0.7")

    def test_locked_evaluation_rejects_missing_test_sequence(self):
        manifest = _manifest()
        del manifest["sequences"]["02"]
        with self.assertRaisesRegex(ArtifactValidationError, "exactly sequences"):
            evaluate_locked(manifest, build_corruption_benchmark(manifest, seed=7))


if __name__ == "__main__":
    unittest.main()
