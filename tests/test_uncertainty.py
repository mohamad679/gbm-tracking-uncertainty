import unittest

from gbm_audit.uncertainty import evaluate_benchmark, sample_link_hypotheses, sample_motion_link_hypotheses


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

    def test_candidate_coverage_counts_true_links_outside_gate(self):
        sequence = {"sequence_id": "01", "split": "development", "frames": 2,
                    "shape_pixels": [100, 100], "tracks": []}
        scenario = {"reference_manifest_sha256": "test", "seed": 3, "scenarios": [{
            "scenario_id": "clean_0", "corruption": "clean", "severity": 0,
            "sequences": {"01": {"sequence_id": "01", "observations": [
                {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
                {"observation_id": "a1", "frame": 1, "x_px": 20.0, "y_px": 0.0}],
                "evaluation_truth": [
                    {"observation_id": "a0", "frame": 0, "true_track_id": 1, "observed": True},
                    {"observation_id": "a1", "frame": 1, "true_track_id": 1, "observed": True}]}}}]}
        result = evaluate_benchmark({"sequences": {"01": sequence}}, scenario, count=4, max_distance_px=8)
        output = result["scenarios"][0]["sequence_results"]["01"]
        self.assertEqual(output["reference_links_present"], 1)
        self.assertEqual(output["candidate_true_link_coverage"], 0.0)

    def test_motion_hypotheses_are_seeded_and_use_constant_velocity(self):
        rows = []
        for frame, x in enumerate((0.0, 2.0, 4.0, 6.0)):
            rows.append({"observation_id": f"track{frame}", "frame": frame,
                         "x_px": x, "y_px": 0.0, "area_px": 1})
            rows.append({"observation_id": f"decoy{frame}", "frame": frame,
                         "x_px": x + 5.0, "y_px": 0.0, "area_px": 1})
        first = sample_motion_link_hypotheses(rows, count=8, seed=3)
        second = sample_motion_link_hypotheses(rows, count=8, seed=3)
        self.assertEqual(first, second)
        self.assertTrue(any(("track1", "track2") in links and ("track2", "track3") in links
                            for links in first))


if __name__ == "__main__":
    unittest.main()
