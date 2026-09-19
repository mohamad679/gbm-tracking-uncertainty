import unittest

from gbm_audit.candidate_benchmark import build_candidate_benchmark
from gbm_audit.validation import ArtifactValidationError


def _artifacts(radius, recall=(0.96, 0.97), burden=(4.0, 5.0), noise=(0.5, 0.7)):
    sequence_ids = ("01", "02")
    uncertainty_results = {}
    clean_soft_results = {}
    noise_soft_results = {}
    for index, sequence_id in enumerate(sequence_ids):
        uncertainty_results[sequence_id] = {
            "candidate_edges": int(burden[index] * 10),
            "candidate_target_observations": 10,
            "candidate_burden_edges_per_target": burden[index],
            "candidate_true_link_coverage": recall[index],
        }
        clean_soft_results[sequence_id] = {"mean_speed_delta_vs_reference": -0.2}
        noise_soft_results[sequence_id] = {
            "mean_speed_delta_vs_reference": noise[index]
        }
    base = {
        "schema_version": 1,
        "reference_manifest_sha256": "hash",
        "corruption_seed": 1729,
    }
    uncertainty = {
        **base,
        "proposal_model": "distance" if radius is not None else "adaptive_v1",
        "max_distance_px": radius,
        "scenarios": [
            {"scenario_id": "clean_0", "corruption": "clean", "severity": 0,
             "sequence_results": uncertainty_results},
            {"scenario_id": "localization_noise_5p0", "corruption": "localization_noise",
             "severity": 5.0, "sequence_results": uncertainty_results},
        ],
    }
    soft = {
        **base,
        "scenarios": [
            {"scenario_id": "clean_0", "corruption": "clean", "severity": 0,
             "sequence_results": clean_soft_results},
            {"scenario_id": "localization_noise_5p0", "corruption": "localization_noise",
             "severity": 5.0, "sequence_results": noise_soft_results},
        ],
    }
    return uncertainty, soft


class TestCandidateBenchmark(unittest.TestCase):
    def _baselines(self):
        return {
            "fixed_8": _artifacts(8.0, recall=(0.79, 0.89), burden=(2.0, 2.5), noise=(0.2, 1.1)),
            "fixed_12": _artifacts(12.0, recall=(0.92, 0.95), burden=(4.0, 4.5), noise=(2.1, 3.1)),
            "fixed_16": _artifacts(16.0, recall=(0.96, 0.97), burden=(6.0, 7.0), noise=(3.8, 4.4)),
        }

    def test_baseline_contract_is_complete_without_adaptive_run(self):
        result = build_candidate_benchmark(self._baselines())
        self.assertEqual(result["status"], "baseline_contract_complete")
        self.assertIsNone(result["acceptance"])
        self.assertEqual(len(result["runs"]), 3)

    def test_adaptive_run_passes_all_three_pre_registered_gates(self):
        runs = self._baselines()
        runs["adaptive_v1"] = _artifacts(
            None, recall=(0.95, 0.96), burden=(4.0, 5.0), noise=(1.0, 1.8)
        )
        result = build_candidate_benchmark(runs)
        self.assertEqual(result["status"], "stage_a_pass")
        self.assertTrue(result["acceptance"]["stage_a_pass"])

    def test_failure_in_one_locked_sequence_fails_stage(self):
        runs = self._baselines()
        runs["adaptive_v1"] = _artifacts(
            None, recall=(0.95, 0.94), burden=(4.0, 5.0), noise=(1.0, 1.8)
        )
        result = build_candidate_benchmark(runs)
        self.assertEqual(result["status"], "stage_a_revise")
        self.assertFalse(result["acceptance"]["stage_a_pass"])

    def test_wrong_fixed_baseline_radius_is_rejected(self):
        runs = self._baselines()
        runs["fixed_8"] = _artifacts(9.0)
        with self.assertRaises(ArtifactValidationError):
            build_candidate_benchmark(runs)


if __name__ == "__main__":
    unittest.main()
