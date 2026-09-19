import copy
import unittest

from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.dynamics import evaluate_dynamics
from gbm_audit.uncertainty import evaluate_benchmark
from gbm_audit.validation import (
    ArtifactValidationError,
    scenario_map,
    validate_manifest,
)


def _manifest():
    def sequence(sequence_id, split):
        tracks = []
        for track_id, offset in ((1, 2.0), (2, 10.0)):
            tracks.append({
                "track_id": track_id,
                "start_frame": 0,
                "end_frame": 5,
                "parent_id": 0,
                "observations": [
                    {"frame": frame, "x_px": offset + frame, "y_px": offset,
                     "area_px": 4}
                    for frame in range(6)
                ],
            })
        return {"sequence_id": sequence_id, "split": split, "frames": 6,
                "shape_pixels": [32, 32], "tracks": tracks}
    return {
        "schema_version": 1,
        "dataset": "synthetic-contract-test",
        "split_policy": "01 development, 02 test",
        "sequences": {"01": sequence("01", "development"),
                      "02": sequence("02", "test")},
    }


class TestPipelineContracts(unittest.TestCase):
    def test_reordered_uncertainty_scenarios_are_aligned_by_id(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        uncertainty = evaluate_benchmark(manifest, corruptions, count=4, max_distance_px=8.0)
        uncertainty["scenarios"] = list(reversed(uncertainty["scenarios"]))

        dynamics = evaluate_dynamics(manifest, corruptions, uncertainty)

        self.assertEqual(
            [scenario["scenario_id"] for scenario in dynamics["scenarios"]],
            [scenario["scenario_id"] for scenario in corruptions["scenarios"]],
        )

    def test_mismatched_reference_hash_is_rejected(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        uncertainty = evaluate_benchmark(manifest, corruptions, count=2)
        uncertainty["reference_manifest_sha256"] = "stale-artifact"

        with self.assertRaisesRegex(ArtifactValidationError, "reference manifest hash"):
            evaluate_dynamics(manifest, corruptions, uncertainty)

    def test_invalid_schema_version_is_rejected(self):
        manifest = _manifest()
        manifest["schema_version"] = 999
        with self.assertRaisesRegex(ArtifactValidationError, "schema_version"):
            validate_manifest(manifest)

    def test_duplicate_scenario_ids_are_rejected(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        broken = copy.deepcopy(corruptions)
        broken["scenarios"].append(copy.deepcopy(broken["scenarios"][0]))
        with self.assertRaisesRegex(ArtifactValidationError, "duplicate scenario_id"):
            scenario_map(broken, "broken artifact")


if __name__ == "__main__":
    unittest.main()
