import copy
import unittest

from gbm_audit.stage_c_v2_development import (
    _canonical_sha256,
    _conformal_interval,
    _development_inputs,
    _fit_family_models,
)


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
            "01": {
                "sequence_id": "01", "split": "development", "frames": 2,
                "frame_indices": [0, 1], "shape_pixels": [10, 10],
                "image_paths": [], "tracking_mask_paths": [], "segmentation_mask_paths": [],
                "lineage_path": "lineage", "lineage_rows": 1, "tracked_ids": 1,
                "consecutive_links": 1,
                "tracks": [{
                    "track_id": 1, "start_frame": 0, "end_frame": 1, "parent_id": 0,
                    "observations": [
                        {"frame": 0, "x_px": 1.0, "y_px": 1.0, "area_px": 1},
                        {"frame": 1, "x_px": 2.0, "y_px": 1.0, "area_px": 1},
                    ],
                }],
                "sequence_root": "test/01",
            },
            "02": {
                "sequence_id": "02", "split": "test", "frames": 2,
                "frame_indices": [0, 1], "shape_pixels": [10, 10],
                "image_paths": [], "tracking_mask_paths": [], "segmentation_mask_paths": [],
                "lineage_path": "lineage", "lineage_rows": 1, "tracked_ids": 1,
                "consecutive_links": 1,
                "tracks": [{
                    "track_id": 1, "start_frame": 0, "end_frame": 1, "parent_id": 0,
                    "observations": [
                        {"frame": 0, "x_px": 1.0, "y_px": 1.0, "area_px": 1},
                        {"frame": 1, "x_px": 2.0, "y_px": 1.0, "area_px": 1},
                    ],
                }],
                "sequence_root": "test/02",
            },
        },
    }


def _corruptions():
    scenarios = []
    for index, family in enumerate((
            "clean", "missed_detection", "localization_noise", "fragmentation",
            "id_switch", "wrong_link", "false_positive")):
        observations = [
            {"observation_id": "ref_0001_0000", "frame": 0, "x_px": 1.0, "y_px": 1.0,
             "observed_track_id": 1, "area_px": 1},
            {"observation_id": "ref_0001_0001", "frame": 1, "x_px": 2.0, "y_px": 1.0,
             "observed_track_id": 1, "area_px": 1},
        ]
        truth = [
            {"observation_id": row["observation_id"], "frame": row["frame"],
             "true_track_id": 1, "observed": True} for row in observations
        ]
        scenario = {
            "scenario_id": f"{family}_0", "corruption": family, "severity": 0,
            "seed": index, "input_kind": "track_table_with_observed_ids",
            "truth_policy": "evaluation_truth is held out from tracker input",
            "sequences": {
                "01": {"sequence_id": "01", "split": "development", "frames": 2,
                        "shape_pixels": [10, 10], "observations": observations,
                        "evaluation_truth": truth},
                "02": {"sequence_id": "02", "split": "test", "frames": 2,
                        "shape_pixels": [10, 10], "observations": observations,
                        "evaluation_truth": truth},
            },
        }
        scenarios.append(scenario)
    result = {
        "schema_version": 1, "dataset": "test", "reference_manifest_sha256": "0" * 64,
        "seed": 20260919, "severity_policy": "test", "scenarios": scenarios,
        "warning": "test",
    }
    result["reference_manifest_sha256"] = _canonical_sha256(_manifest())
    return result


class TestStageCV2Development(unittest.TestCase):
    def test_development_inputs_preserve_sequence_split_and_reject_leakage(self):
        manifest, corruptions = _manifest(), _corruptions()
        sequence, _ = _development_inputs(manifest, corruptions)
        self.assertEqual(sequence["sequence_id"], "01")
        leaked = copy.deepcopy(corruptions)
        leaked["scenarios"][0]["sequences"]["03"] = leaked["scenarios"][0]["sequences"].pop("02")
        with self.assertRaises(Exception):
            _development_inputs(manifest, leaked)

    def test_family_models_are_leave_one_family_out(self):
        sequence, corruptions = _development_inputs(_manifest(), _corruptions())
        models, rows = _fit_family_models(sequence, corruptions)
        self.assertEqual(set(models), {
            "all", "clean", "missed_detection", "localization_noise", "fragmentation",
            "id_switch", "wrong_link", "false_positive",
        })
        self.assertTrue(all(rows[family] for family in rows))
        self.assertEqual(models["clean"]["fit_sequence"], "01")

    def test_conformal_interval_expands_both_sides(self):
        interval = _conformal_interval({"p05": 2.0, "p95": 4.0}, 0.5)
        self.assertEqual(interval["p05"], 1.5)
        self.assertEqual(interval["p95"], 4.5)


if __name__ == "__main__":
    unittest.main()

