import unittest

from gbm_audit.uncertainty import evaluate_benchmark, sample_link_hypotheses


def _observations():
    rows = []
    for frame in range(5):
        rows.extend([
            {"observation_id": f"a{frame}", "frame": frame, "x_px": float(frame), "y_px": 1.0, "area_px": 1},
            {"observation_id": f"b{frame}", "frame": frame, "x_px": float(frame), "y_px": 10.0, "area_px": 1},
        ])
    return rows


class TestUncertainty(unittest.TestCase):
    def test_hypotheses_are_seeded_and_one_to_one(self):
        first = sample_link_hypotheses(_observations(), count=8, seed=3)
        second = sample_link_hypotheses(_observations(), count=8, seed=3)
        self.assertEqual(first, second)
        for links in first:
            self.assertLessEqual(len(links), 8)

    def test_calibration_output_keeps_truth_out_of_observations(self):
        sequence = {"sequence_id": "01", "split": "development", "frames": 5,
                    "shape_pixels": [20, 20], "tracks": []}
        for track_id, y in ((1, 1.0), (2, 10.0)):
            observations = [{"frame": frame, "x_px": float(frame), "y_px": y, "area_px": 1} for frame in range(5)]
            sequence["tracks"].append({"track_id": track_id, "observations": observations})
        observations = _observations()
        truth = [{"observation_id": f"{prefix}{frame}", "frame": frame,
                  "true_track_id": 1 if prefix == "a" else 2, "observed": True}
                 for frame in range(5) for prefix in ("a", "b")]
        scenario = {"reference_manifest_sha256": "test", "seed": 3, "scenarios": [{
            "scenario_id": "clean_0", "corruption": "clean", "severity": 0,
            "sequences": {"01": {"sequence_id": "01", "observations": observations,
                                   "evaluation_truth": truth}}}]}
        result = evaluate_benchmark({"sequences": {"01": sequence}}, scenario, count=8)
        output = result["scenarios"][0]["sequence_results"]["01"]
        self.assertGreater(output["unique_hypothesis_count"], 0)
        self.assertIn("hypothesis_calibration", output)
        self.assertEqual(output["candidate_true_link_coverage"], 1.0)
        self.assertNotIn("true_track_id", observations[0])


if __name__ == "__main__":
    unittest.main()
