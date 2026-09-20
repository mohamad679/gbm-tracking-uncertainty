import copy
import unittest

from gbm_audit.context_posterior import trajectories_from_links
from gbm_audit.corruptions import build_corruption_benchmark
from gbm_audit.stage_c_dynamics import (
    evaluate_development,
    fit_development_speed_hmm,
    summarize_trajectories,
)


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
        "dataset": "synthetic-stage-c-test",
        "split_policy": "01 development, 02 test",
        "sequences": {
            "01": sequence("01", "development", 1.0),
            "02": sequence("02", "test", 7.0),
        },
    }


class TestStageCDynamics(unittest.TestCase):
    def test_summary_reports_migration_msd_persistence_and_states(self):
        observations = {
            f"a{frame}": {"observation_id": f"a{frame}", "frame": frame,
                           "x_px": float(frame), "y_px": 0.0}
            for frame in range(5)
        }
        trajectories, invariants = trajectories_from_links(
            sorted(observations), [(f"a{frame}", f"a{frame + 1}") for frame in range(4)]
        )
        hmm = {
            "status": "ok",
            "state_means_px_per_frame": [1.0, 3.0],
            "state_stds_px_per_frame": [0.2, 0.2],
            "transition_matrix": [[0.9, 0.1], [0.1, 0.9]],
            "initial_state_probability": [0.5, 0.5],
        }
        summary = summarize_trajectories(trajectories, observations, hmm)
        self.assertTrue(invariants["one_to_one_pass"])
        self.assertEqual(summary["consecutive_steps"], 4)
        self.assertAlmostEqual(summary["mean_speed_px_per_frame"], 1.0)
        self.assertAlmostEqual(summary["directional_persistence"], 1.0)
        self.assertEqual(summary["mean_squared_displacement_px2"]["1"], 1.0)
        self.assertEqual(summary["hmm_2state"]["status"], "ok")

    def test_hmm_fit_is_development_only_and_evaluator_excludes_locked_test(self):
        manifest = _manifest()
        changed_test = copy.deepcopy(manifest)
        changed_test["sequences"]["02"]["tracks"][0]["observations"][1]["x_px"] = 999.0
        self.assertEqual(
            fit_development_speed_hmm(manifest), fit_development_speed_hmm(changed_test)
        )
        corruptions = build_corruption_benchmark(manifest, seed=11)
        corruptions["scenarios"] = corruptions["scenarios"][:1]
        result = evaluate_development(manifest, corruptions, ensemble_count=4)
        self.assertFalse(result["locked_test_sequence_evaluated"])
        self.assertEqual(result["development_sequence"], "01")
        self.assertEqual(result["frozen_hmm"]["fit_sequence"], "01")
        self.assertEqual([row["sequence_id"] for row in result["scenarios"]], ["01"])
        self.assertEqual(result["ensemble"]["count"], 4)
        self.assertTrue(result["scenarios"][0]["exact_context"]["invariants_pass"])
        self.assertIsNotNone(
            result["scenarios"][0]["exact_context"]["posterior_summary"]
            ["hmm_2state"]["state_occupancy"][0]["mean"]
        )

    def test_development_evaluator_rejects_invalid_ensemble_size(self):
        manifest = _manifest()
        corruptions = build_corruption_benchmark(manifest, seed=11)
        with self.assertRaisesRegex(ValueError, "ensemble_count"):
            evaluate_development(manifest, corruptions, ensemble_count=0)


if __name__ == "__main__":
    unittest.main()
