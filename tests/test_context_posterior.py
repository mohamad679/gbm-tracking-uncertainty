import math
import unittest

from gbm_audit.context_posterior import (
    ExactInferenceResourceError,
    MAX_EXACT_COMPONENT_TARGETS,
    exact_context_marginals,
)


def _observations():
    return [
        {"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0},
        {"observation_id": "b1", "frame": 1, "x_px": 1.0, "y_px": 0.0},
        {"observation_id": "c1", "frame": 1, "x_px": 2.0, "y_px": 0.0},
    ]


class TestContextPosterior(unittest.TestCase):
    def test_competing_links_are_marginalized_over_one_to_one_matchings(self):
        result = exact_context_marginals(
            _observations(),
            [
                {"from_observation_id": "a0", "to_observation_id": "b1", "proposal_score_px": 0.0},
                {"from_observation_id": "a0", "to_observation_id": "c1", "proposal_score_px": 0.0},
            ],
            temperature_px=1.0, new_track_score_px=1.0,
        )
        probabilities = {
            (row["from_observation_id"], row["to_observation_id"]): row["probability"]
            for row in result["link_marginals"]
        }
        births = {row["to_observation_id"]: row["probability"]
                  for row in result["new_track_marginals"]}
        birth_weight = math.exp(-1.0)
        self.assertAlmostEqual(probabilities[("a0", "b1")], 1 / (2 + birth_weight))
        self.assertAlmostEqual(probabilities[("a0", "c1")], 1 / (2 + birth_weight))
        self.assertAlmostEqual(births["b1"], (1 + birth_weight) / (2 + birth_weight))
        self.assertAlmostEqual(births["c1"], (1 + birth_weight) / (2 + birth_weight))
        self.assertTrue(result["invariants"]["target_conservation_pass"])
        self.assertTrue(result["invariants"]["source_capacity_pass"])

    def test_score_changes_context_marginal_without_reading_truth(self):
        observations = [{**row, "true_track_id": 999} for row in _observations()]
        result = exact_context_marginals(
            observations,
            [
                {"from_observation_id": "a0", "to_observation_id": "b1", "proposal_score_px": 0.0},
                {"from_observation_id": "a0", "to_observation_id": "c1", "proposal_score_px": 4.0},
            ],
            temperature_px=1.0, new_track_score_px=1.0,
        )
        probabilities = {row["to_observation_id"]: row["probability"]
                         for row in result["link_marginals"]}
        self.assertGreater(probabilities["b1"], probabilities["c1"])
        self.assertNotIn("true_track_id", str(result))

    def test_isolated_target_has_certain_new_track_mass(self):
        result = exact_context_marginals(_observations(), [])
        births = {row["to_observation_id"]: row["probability"]
                  for row in result["new_track_marginals"]}
        unmatched = {row["from_observation_id"]: row["probability"]
                     for row in result["source_unmatched_marginals"]}
        self.assertEqual(births, {"b1": 1.0, "c1": 1.0})
        self.assertEqual(unmatched, {"a0": 1.0})
        self.assertEqual(result["link_marginals"], [])

    def test_resource_bound_is_explicit(self):
        observations = [{"observation_id": "a0", "frame": 0, "x_px": 0.0, "y_px": 0.0}]
        observations.extend(
            {"observation_id": f"b{index}", "frame": 1, "x_px": float(index), "y_px": 0.0}
            for index in range(MAX_EXACT_COMPONENT_TARGETS + 1)
        )
        edges = [
            {"from_observation_id": "a0", "to_observation_id": f"b{index}", "proposal_score_px": 1.0}
            for index in range(MAX_EXACT_COMPONENT_TARGETS + 1)
        ]
        with self.assertRaises(ExactInferenceResourceError):
            exact_context_marginals(observations, edges)

    def test_invalid_probability_parameters_are_rejected(self):
        with self.assertRaises(ValueError):
            exact_context_marginals(_observations(), [], temperature_px=math.inf)
        with self.assertRaises(ValueError):
            exact_context_marginals(_observations(), [], new_track_score_px=0)


if __name__ == "__main__":
    unittest.main()
