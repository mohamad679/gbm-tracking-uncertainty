import copy
import unittest

from gbm_audit.stage_d_development import (
    _track_transition_groups,
    fit_development_and_check_stability,
)
from gbm_audit.validation import canonical_sha256


def _sequence(sequence_id="01", split="development"):
    tracks = []
    for track_id, offset in enumerate((0.0, 3.0), start=1):
        observations = [
            {"frame": frame, "x_px": offset + frame * 1.0, "y_px": offset + frame * 0.5,
             "area_px": 1}
            for frame in range(5)
        ]
        tracks.append({
            "track_id": track_id,
            "start_frame": 0,
            "end_frame": 4,
            "parent_id": 0,
            "observations": observations,
        })
    return {
        "sequence_id": sequence_id,
        "split": split,
        "frames": 5,
        "frame_indices": list(range(5)),
        "shape_pixels": [20, 20],
        "image_paths": [],
        "tracking_mask_paths": [],
        "segmentation_mask_paths": [],
        "lineage_path": "lineage",
        "lineage_rows": 2,
        "tracked_ids": 2,
        "consecutive_links": 8,
        "tracks": tracks,
        "sequence_root": f"test/{sequence_id}",
    }


def _manifest():
    return {
        "schema_version": 1,
        "dataset": "test",
        "reference_kind": "expert_tracking_masks_and_lineage",
        "source": "test",
        "archive": {"file_name": "test.zip", "size_bytes": 1, "sha256": "0" * 64},
        "split_policy": "sequence-level: 01 development, 02 test",
        "warning": "test",
        "sequences": {
            "01": _sequence("01", "development"),
            "02": _sequence("02", "test"),
        },
    }


def _stage_c_development():
    return {
        "reference_manifest_sha256": canonical_sha256(_manifest()),
        "development_sequence": "01",
        "locked_test_sequence_evaluated": False,
        "frozen_hmm": {
            "model": {
                "status": "ok",
                "state_means_px_per_frame": [0.2, 2.0],
                "state_stds_px_per_frame": [0.4, 1.0],
                "transition_matrix": [[0.8, 0.2], [0.1, 0.9]],
                "initial_state_probability": [1.0, 0.0],
            },
        },
    }


class TestStageDDevelopment(unittest.TestCase):
    def test_transition_rows_are_truth_blind_and_grouped_by_development_track(self):
        groups = _track_transition_groups(_manifest())
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups[0]), 3)
        self.assertNotIn("track_id", groups[0][0])
        self.assertNotIn("true_track_id", groups[0][0])
        self.assertEqual(groups[0][0]["sequence_id"], "01")

    def test_fit_is_development_only_stable_and_does_not_select(self):
        result = fit_development_and_check_stability(_manifest(), _stage_c_development())
        self.assertEqual(result["status"], "DEVELOPMENT_COMPLETE")
        self.assertEqual(result["decision"], "HOLD_PENDING_STEP_4_HELD_OUT_EVALUATION")
        self.assertTrue(result["invariants"]["development_only_pass"])
        self.assertFalse(result["invariants"]["selection_performed"])
        self.assertTrue(result["stability"]["all_candidates_and_folds_pass"])
        self.assertEqual(set(result["full_development_fit"]), {
            "frozen_hmm_speed_baseline_v1",
            "weighted_empirical_transition_baseline_v1",
            "stable_linear_koopman_operator_v1",
        })
        self.assertEqual(len(result["cross_validation"]["folds"]), 2)

    def test_rejects_development_split_drift_and_locked_stage_c_input(self):
        manifest = _manifest()
        broken = copy.deepcopy(manifest)
        broken["sequences"]["02"]["split"] = "development"
        with self.assertRaises(ValueError):
            fit_development_and_check_stability(broken, _stage_c_development())
        locked = _stage_c_development()
        locked["locked_test_sequence_evaluated"] = True
        with self.assertRaises(ValueError):
            fit_development_and_check_stability(manifest, locked)
        mismatched = _stage_c_development()
        mismatched["reference_manifest_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            fit_development_and_check_stability(manifest, mismatched)


if __name__ == "__main__":
    unittest.main()
