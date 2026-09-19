import copy
import unittest

from gbm_audit.adaptive_tuning import (
    development_only_artifacts,
    feasibility_bound,
    predefined_grid,
    select_configuration,
)
from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.uncertainty import evaluate_benchmark
from gbm_audit.validation import ArtifactValidationError


def _manifest():
    def sequence(sequence_id, split):
        return {
            "sequence_id": sequence_id,
            "split": split,
            "frames": 3,
            "shape_pixels": [32, 32],
            "tracks": [{
                "track_id": 1,
                "start_frame": 0,
                "end_frame": 2,
                "parent_id": 0,
                "observations": [
                    {"frame": frame, "x_px": frame, "y_px": 1.0, "area_px": 4}
                    for frame in range(3)
                ],
            }],
        }
    return {
        "schema_version": 1,
        "dataset": "synthetic-tuning-test",
        "split_policy": "01 development, 02 test",
        "sequences": {
            "01": sequence("01", "development"),
            "02": sequence("02", "test"),
        },
    }


def _evaluated(config_id, passes=True, noise=1.0, clean=1.0, burden=1.0):
    return {
        "config_id": config_id,
        "config": {},
        "metrics": {
            "development_pass": passes,
            "noise_sigma_5_soft_speed_error_px_per_frame": noise,
            "clean_soft_speed_error_px_per_frame": clean,
            "clean_candidate_burden_edges_per_target": burden,
        },
    }


class TestAdaptiveTuning(unittest.TestCase):
    def test_grid_is_predeclared_and_deterministic(self):
        first = predefined_grid()
        second = predefined_grid()
        self.assertEqual(first, second)
        self.assertEqual(len(first), 27)
        self.assertEqual(first[0].motion_uncertainty_weight, 0.0)
        self.assertEqual(first[-1].cold_start_uncertainty_px, 4.0)

    def test_development_subset_excludes_locked_sequence_and_extra_scenarios(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        dev_manifest, dev_corruptions = development_only_artifacts(manifest, corruptions)

        self.assertEqual(set(dev_manifest["sequences"]), {"01"})
        self.assertEqual(
            [row["scenario_id"] for row in dev_corruptions["scenarios"]],
            ["clean_0", "localization_noise_5p0"],
        )
        self.assertTrue(all(
            set(row["sequences"]) == {"01"}
            for row in dev_corruptions["scenarios"]
        ))

    def test_split_drift_fails_closed(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        broken = copy.deepcopy(manifest)
        broken["sequences"]["02"]["split"] = "development"
        broken_corruptions = build_corruption_benchmark(broken, seed=11)

        with self.assertRaisesRegex(ArtifactValidationError, "requires development sequence"):
            development_only_artifacts(broken, broken_corruptions)

    def test_scenario_sampling_seed_is_stable_after_development_filtering(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        full = evaluate_benchmark(manifest, corruptions, count=2)
        dev_manifest, dev_corruptions = development_only_artifacts(manifest, corruptions)
        filtered = evaluate_benchmark(dev_manifest, dev_corruptions, count=2)
        full_by_id = {row["scenario_id"]: row for row in full["scenarios"]}

        for row in filtered["scenarios"]:
            self.assertEqual(
                row["sequence_results"]["01"]["posterior_links"],
                full_by_id[row["scenario_id"]]["sequence_results"]["01"]["posterior_links"],
            )

    def test_selection_uses_frozen_robustness_first_order(self):
        selected = select_configuration([
            _evaluated("b", noise=0.8, clean=0.1, burden=0.1),
            _evaluated("a", noise=0.5, clean=0.9, burden=0.9),
            _evaluated("failed", passes=False, noise=0.0, clean=0.0, burden=0.0),
        ])
        self.assertEqual(selected["config_id"], "a")

    def test_selection_returns_none_when_no_configuration_passes(self):
        self.assertIsNone(select_configuration([
            _evaluated("a", passes=False),
            _evaluated("b", passes=False),
        ]))

    def test_feasibility_bound_detects_incompatible_frozen_gates(self):
        result = feasibility_bound(
            reference_links=757,
            fixed_16_candidate_edges=726,
            target_observations=759,
        )
        self.assertEqual(result["minimum_candidate_edges_for_recall_gate"], 720)
        self.assertAlmostEqual(
            result["maximum_possible_burden_reduction_vs_fixed_16_fraction"],
            1 - 720 / 726,
        )
        self.assertFalse(result["recall_and_burden_gates_jointly_feasible"])


if __name__ == "__main__":
    unittest.main()
