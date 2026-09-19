import unittest

from gbm_audit.uncertainty import (
    evaluate_benchmark,
    sample_candidate_graph_hypotheses,
    sample_link_hypotheses,
    sample_motion_link_hypotheses,
)
from gbm_audit.adaptive_candidates import AdaptiveCandidateConfig
from gbm_audit.soft_dynamics import soft_summary


def _observations():
    rows = []
    for frame in range(5):
        rows.extend([
            {"observation_id": f"a{frame}", "frame": frame, "x_px": float(frame), "y_px": 1.0, "area_px": 1},
            {"observation_id": f"b{frame}", "frame": frame, "x_px": float(frame), "y_px": 10.0, "area_px": 1},
        ])
    return rows


def _assert_one_to_one(testcase: unittest.TestCase, links: set[tuple[str, str]]) -> None:
    left = [edge[0] for edge in links]
    right = [edge[1] for edge in links]
    testcase.assertEqual(len(left), len(set(left)))
    testcase.assertEqual(len(right), len(set(right)))


class TestUncertainty(unittest.TestCase):
    def test_explicit_candidate_sampler_never_emits_an_edge_outside_graph(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "b0", "frame": 0, "x_px": 0.0, "y_px": 10.0},
            {"observation_id": "a1", "frame": 1, "x_px": 1.0, "y_px": 0.0},
            {"observation_id": "b1", "frame": 1, "x_px": 1.0, "y_px": 10.0},
        ]
        candidate_edges = [{
            "from_observation_id": "a0", "to_observation_id": "a1",
            "proposal_score_px": 1.0,
        }]
        hypotheses = sample_candidate_graph_hypotheses(
            observations, candidate_edges, count=16, seed=5
        )
        allowed = {("a0", "a1")}
        self.assertTrue(any(hypothesis for hypothesis in hypotheses))
        self.assertTrue(all(hypothesis <= allowed for hypothesis in hypotheses))

    def test_hypotheses_are_seeded_and_one_to_one(self):
        first = sample_link_hypotheses(_observations(), count=8, seed=3)
        second = sample_link_hypotheses(_observations(), count=8, seed=3)
        self.assertEqual(first, second)
        for links in first:
            _assert_one_to_one(self, links)
            self.assertLessEqual(len(links), 8)

    def test_sampling_parameters_reject_invalid_values(self):
        rows = _observations()
        invalid = [
            {"count": 0},
            {"count": -1},
            {"max_distance_px": 0.0},
            {"max_distance_px": -1.0},
            {"temperature_px": 0.0},
            {"temperature_px": -1.0},
            {"temperature_px": float("nan")},
        ]
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    sample_link_hypotheses(rows, **kwargs)

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
        self.assertEqual(output["candidate_target_observations"], 8)
        self.assertAlmostEqual(
            output["candidate_burden_edges_per_target"], output["candidate_edges"] / 8
        )
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

    def test_motion_hypotheses_are_seeded_and_one_to_one(self):
        rows = []
        for frame, x in enumerate((0.0, 2.0, 4.0, 6.0)):
            rows.append({"observation_id": f"track{frame}", "frame": frame,
                         "x_px": x, "y_px": 0.0, "area_px": 1})
            rows.append({"observation_id": f"decoy{frame}", "frame": frame,
                         "x_px": x + 5.0, "y_px": 0.0, "area_px": 1})
        first = sample_motion_link_hypotheses(rows, count=8, seed=3)
        second = sample_motion_link_hypotheses(rows, count=8, seed=3)
        self.assertEqual(first, second)
        for links in first:
            _assert_one_to_one(self, links)
        self.assertTrue(any(("track1", "track2") in links and ("track2", "track3") in links
                            for links in first))

    def test_motion_scoring_cannot_escape_fixed_candidate_graph(self):
        rows = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
            {"observation_id": "a1", "frame": 1, "x_px": 4.0, "y_px": 0.0},
            {"observation_id": "a2", "frame": 2, "x_px": 14.0, "y_px": 0.0},
        ]
        hypotheses = sample_motion_link_hypotheses(
            rows, count=32, max_distance_px=8.0, seed=9
        )
        self.assertTrue(all(("a1", "a2") not in hypothesis for hypothesis in hypotheses))

    def test_adaptive_graph_drives_posterior_and_soft_dynamics(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0, "area_px": 1},
            {"observation_id": "a1", "frame": 1, "x_px": 4.0, "y_px": 0.0, "area_px": 1},
            {"observation_id": "a2", "frame": 2, "x_px": 14.0, "y_px": 0.0, "area_px": 1},
        ]
        truth = [
            {"observation_id": row["observation_id"], "frame": row["frame"],
             "true_track_id": 1, "observed": True}
            for row in observations
        ]
        sequence = {
            "sequence_id": "01", "split": "development", "frames": 3,
            "frame_indices": [0, 1, 2], "shape_pixels": [20, 20],
            "tracks": [{"track_id": 1, "observations": [
                {"frame": row["frame"], "x_px": row["x_px"], "y_px": row["y_px"]}
                for row in observations
            ]}],
        }
        corruptions = {
            "reference_manifest_sha256": "test", "seed": 3,
            "scenarios": [{
                "scenario_id": "clean_0", "corruption": "clean", "severity": 0,
                "sequences": {"01": {
                    "sequence_id": "01", "observations": observations,
                    "evaluation_truth": truth,
                }},
            }],
        }
        result = evaluate_benchmark(
            {"sequences": {"01": sequence}}, corruptions, count=16,
            proposal_model="adaptive_v1", adaptive_config=AdaptiveCandidateConfig(),
        )
        output = result["scenarios"][0]["sequence_results"]["01"]
        pairs = {
            (row["from_observation_id"], row["to_observation_id"])
            for row in output["posterior_links"]
        }
        self.assertIn(("a1", "a2"), pairs)
        self.assertEqual(output["candidate_true_link_coverage"], 1.0)
        self.assertEqual(output["sampled_links_outside_candidate_graph"], 0)
        self.assertEqual(output["candidate_graph_method"], "adaptive_motion_uncertainty_density_v1")
        self.assertTrue(all("proposal_score_px" in row for row in output["posterior_links"]))
        downstream = soft_summary(
            observations, output["posterior_links"], result["calibration"]["temperature"]
        )
        self.assertGreater(downstream["expected_link_mass"], 0)


if __name__ == "__main__":
    unittest.main()
