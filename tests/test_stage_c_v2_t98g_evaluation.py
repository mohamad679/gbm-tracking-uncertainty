import json
from pathlib import Path
import unittest

from gbm_audit.adaptive_tuning_v3 import LOCKED_ADAPTIVE_V3_CONFIG
from gbm_audit.stage_c_v2_sampler import StageCV2SamplerConfig
from gbm_audit.stage_c_v2_t98g_evaluation import (
    _all_invariants,
    _assert_frozen_development,
    _predictive_summary_parallel,
)


class TestStageCV2T98GEvaluation(unittest.TestCase):
    def test_frozen_development_artifact_is_accepted_without_t98g(self):
        artifact = json.loads(Path("docs/stage-c-v2-development-fit.json").read_text())
        _assert_frozen_development(artifact, ensemble_count=256)
        self.assertEqual(artifact["locked_adaptive_config"], {
            key: value for key, value in artifact["locked_adaptive_config"].items()
        })

    def test_frozen_configuration_drift_is_rejected(self):
        artifact = json.loads(Path("docs/stage-c-v2-development-fit.json").read_text())
        artifact["sampler_config"]["temperature_px"] = 99.0
        with self.assertRaises(ValueError):
            _assert_frozen_development(artifact, ensemble_count=256)

    def test_parallel_batch_matches_serial_member_stream(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 1.0, "y_px": 1.0},
            {"observation_id": "b0", "frame": 0, "x_px": 50.0, "y_px": 50.0},
            {"observation_id": "a1", "frame": 1, "x_px": 2.0, "y_px": 1.0},
            {"observation_id": "b1", "frame": 1, "x_px": 51.0, "y_px": 50.0},
        ]
        model = {
            "schema_version": 1,
            "method": "development_nonnegative_affine_rayleigh_localization_v1",
            "coefficients": {
                "intercept_px": 0.0,
                "median_proposal_distance_weight": 0.0,
                "candidate_degree_weight": 0.0,
            },
        }
        hmm = {
            "status": "ok", "transition_matrix": [[0.8, 0.2], [0.2, 0.8]],
            "state_means_px_per_frame": [0.2, 2.0],
            "state_stds_px_per_frame": [0.4, 1.0],
            "initial_state_probability": [0.5, 0.5],
        }
        config = StageCV2SamplerConfig(ensemble_count=4)
        result = _predictive_summary_parallel(
            observations, model, hmm, count=4, seed=123,
            sampler_config=config, workers=2,
        )
        self.assertTrue(result["invariants"]["sample_count_pass"])
        self.assertTrue(result["invariants"]["truth_blind_pass"])
        self.assertTrue(_all_invariants(
            {"invariants": {"one_to_one_pass": True, "trajectory_partition_pass": True,
                            "candidate_graph_pass": True}}, result
        ))


if __name__ == "__main__":
    unittest.main()
