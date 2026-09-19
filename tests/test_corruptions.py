import unittest

from gbm_audit.corruptions import build_corruption_benchmark


def _manifest():
    def sequence(sequence_id, split):
        tracks = []
        for track_id, offset in ((1, 2), (2, 8)):
            tracks.append({
                "track_id": track_id,
                "start_frame": 0,
                "end_frame": 5,
                "parent_id": 0,
                "observations": [
                    {"frame": frame, "x_px": offset + frame, "y_px": 4.0, "area_px": 4}
                    for frame in range(6)
                ],
            })
        return {"sequence_id": sequence_id, "split": split, "frames": 6,
                "shape_pixels": [20, 20], "tracks": tracks}
    return {"schema_version": 1, "dataset": "synthetic", "split_policy": "01 development, 02 test",
            "sequences": {"01": sequence("01", "development"),
                          "02": sequence("02", "test")}}


class TestControlledCorruptions(unittest.TestCase):
    def test_seeded_generation_is_deterministic_and_truth_is_separate(self):
        first = build_corruption_benchmark(_manifest(), seed=7)
        second = build_corruption_benchmark(_manifest(), seed=7)
        self.assertEqual(first, second)
        for scenario in first["scenarios"]:
            for sequence in scenario["sequences"].values():
                for row in sequence["observations"]:
                    self.assertNotIn("true_track_id", row)

    def test_misses_and_false_positives_have_known_effects(self):
        result = build_corruption_benchmark(_manifest(), seed=7)
        clean = next(s for s in result["scenarios"] if s["scenario_id"] == "clean_0")
        missed = next(s for s in result["scenarios"] if s["scenario_id"] == "missed_detection_0p5")
        false = next(s for s in result["scenarios"] if s["scenario_id"] == "false_positive_20")
        self.assertLess(len(missed["sequences"]["01"]["observations"]), len(clean["sequences"]["01"]["observations"]))
        false_truth = false["sequences"]["01"]["evaluation_truth"]
        self.assertEqual(sum(row["true_track_id"] == 0 for row in false_truth), 20)

    def test_association_corruption_changes_observed_ids_but_not_truth(self):
        result = build_corruption_benchmark(_manifest(), seed=7)
        clean = next(s for s in result["scenarios"] if s["scenario_id"] == "clean_0")
        switched = next(s for s in result["scenarios"] if s["scenario_id"] == "id_switch_1")
        clean_ids = {row["observation_id"]: row["observed_track_id"] for row in clean["sequences"]["01"]["observations"]}
        switched_ids = {row["observation_id"]: row["observed_track_id"] for row in switched["sequences"]["01"]["observations"]}
        self.assertNotEqual(clean_ids, switched_ids)
        self.assertEqual(sum(row["true_track_id"] > 0 for row in switched["sequences"]["01"]["evaluation_truth"]), 12)

    def test_wrong_link_is_local_while_id_switch_is_persistent(self):
        result = build_corruption_benchmark(_manifest(), seed=7)
        clean = next(s for s in result["scenarios"] if s["scenario_id"] == "clean_0")["sequences"]["01"]
        wrong = next(s for s in result["scenarios"] if s["scenario_id"] == "wrong_link_1")["sequences"]["01"]
        switched = next(s for s in result["scenarios"] if s["scenario_id"] == "id_switch_1")["sequences"]["01"]

        clean_ids = {row["observation_id"]: row["observed_track_id"] for row in clean["observations"]}
        wrong_ids = {row["observation_id"]: row["observed_track_id"] for row in wrong["observations"]}
        switched_ids = {row["observation_id"]: row["observed_track_id"] for row in switched["observations"]}

        wrong_changes = [observation_id for observation_id in clean_ids if clean_ids[observation_id] != wrong_ids[observation_id]]
        switched_changes = [observation_id for observation_id in clean_ids if clean_ids[observation_id] != switched_ids[observation_id]]

        self.assertEqual(set(wrong_changes), {"ref_0001_0003", "ref_0002_0003"})
        self.assertEqual(set(switched_changes), {
            "ref_0001_0004", "ref_0001_0005", "ref_0002_0004", "ref_0002_0005"
        })
        self.assertEqual(wrong_ids["ref_0001_0004"], clean_ids["ref_0001_0004"])
        self.assertEqual(wrong_ids["ref_0002_0004"], clean_ids["ref_0002_0004"])


if __name__ == "__main__":
    unittest.main()
