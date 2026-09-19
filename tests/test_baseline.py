import unittest

from gbm_audit.baseline import evaluate_benchmark, nearest_neighbor


class TestBaseline(unittest.TestCase):
    def test_nearest_neighbor_does_not_bridge_a_gap(self):
        observations = [
            {"observation_id": "a", "frame": 0, "x_px": 1.0, "y_px": 1.0, "area_px": 1},
            {"observation_id": "b", "frame": 2, "x_px": 1.0, "y_px": 1.0, "area_px": 1},
        ]
        assignments = nearest_neighbor(observations, max_distance_px=8)
        self.assertNotEqual(assignments["a"], assignments["b"])

    def test_clean_two_track_sequence_has_perfect_links(self):
        sequence = {
            "sequence_id": "01", "split": "development", "frames": 3,
            "shape_pixels": [20, 20],
            "tracks": [
                {"track_id": 1, "observations": [{"frame": i, "x_px": float(i), "y_px": 1.0, "area_px": 1} for i in range(3)]},
                {"track_id": 2, "observations": [{"frame": i, "x_px": float(i), "y_px": 10.0, "area_px": 1} for i in range(3)]},
            ],
        }
        for track in sequence["tracks"]:
            for point in track["observations"]:
                point["observation_id"] = f"ref_{track['track_id']:04d}_{point['frame']:04d}"
        scenario_sequence = {
            "sequence_id": "01", "split": "development", "frames": 3,
            "observations": [
                {"observation_id": point["observation_id"], "frame": point["frame"], "x_px": point["x_px"], "y_px": point["y_px"], "area_px": 1,
                 "observed_track_id": track["track_id"]}
                for track in sequence["tracks"] for point in track["observations"]
            ],
            "evaluation_truth": [
                {"observation_id": point["observation_id"], "frame": point["frame"], "true_track_id": track["track_id"], "observed": True}
                for track in sequence["tracks"] for point in track["observations"]
            ],
        }
        corruption = {"reference_manifest_sha256": "test", "seed": 1, "scenarios": [{
            "scenario_id": "clean_0", "corruption": "clean", "severity": 0,
            "sequences": {"01": scenario_sequence}}]}
        result = evaluate_benchmark({"sequences": {"01": sequence}}, corruption)
        metrics = result["scenarios"][0]["sequence_results"]["01"]
        self.assertEqual(metrics["id_switches"], 0)
        self.assertEqual(metrics["link_precision"], 1.0)
        self.assertEqual(metrics["link_recall"], 1.0)


if __name__ == "__main__":
    unittest.main()
