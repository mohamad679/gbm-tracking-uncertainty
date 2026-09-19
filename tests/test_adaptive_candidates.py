import random
import unittest

from gbm_audit.adaptive_candidates import (
    AdaptiveCandidateConfig,
    generate_adaptive_candidate_graph,
)


def _row(observation_id, frame, x, y=0.0, **extra):
    return {
        "observation_id": observation_id,
        "frame": frame,
        "x_px": float(x),
        "y_px": float(y),
        **extra,
    }


class TestAdaptiveCandidates(unittest.TestCase):
    def test_output_is_deterministic_and_input_order_independent(self):
        rows = [
            _row("a0", 0, 0), _row("b0", 0, 0, 20),
            _row("a1", 1, 4), _row("b1", 1, 4, 20),
            _row("a2", 2, 10), _row("b2", 2, 10, 20),
        ]
        shuffled = list(rows)
        random.Random(17).shuffle(shuffled)
        self.assertEqual(
            generate_adaptive_candidate_graph(rows),
            generate_adaptive_candidate_graph(shuffled),
        )

    def test_truth_fields_cannot_change_candidate_graph(self):
        rows = [_row("a0", 0, 0), _row("a1", 1, 10), _row("a2", 2, 20)]
        with_truth = [{**row, "true_track_id": 99, "true_link": True} for row in rows]
        self.assertEqual(
            generate_adaptive_candidate_graph(rows),
            generate_adaptive_candidate_graph(with_truth),
        )

    def test_adaptive_prediction_recovers_link_outside_fixed_eight_pixel_gate(self):
        rows = [_row("a0", 0, 0), _row("a1", 1, 4), _row("a2", 2, 14)]
        graph = generate_adaptive_candidate_graph(rows)
        edge = next(
            row for row in graph["candidate_edges"]
            if row["from_observation_id"] == "a1" and row["to_observation_id"] == "a2"
        )
        self.assertEqual(edge["distance_px"], 10.0)
        self.assertEqual(edge["proposal_score_px"], 6.0)
        self.assertEqual(edge["inclusion"], "adaptive")

    def test_base_gate_is_retained_during_abrupt_turn(self):
        rows = [_row("a0", 0, 0), _row("a1", 1, 8), _row("a2", 2, 1)]
        graph = generate_adaptive_candidate_graph(rows)
        edge = next(
            row for row in graph["candidate_edges"]
            if row["from_observation_id"] == "a1" and row["to_observation_id"] == "a2"
        )
        self.assertEqual(edge["distance_px"], 7.0)
        self.assertEqual(edge["inclusion"], "base")

    def test_density_increases_radius_but_clips_at_maximum(self):
        rows = [_row(f"s{i}", 0, i) for i in range(8)]
        rows.extend(_row(f"t{i}", 1, i) for i in range(8))
        graph = generate_adaptive_candidate_graph(rows)
        self.assertTrue(graph["source_gates"])
        self.assertTrue(all(gate["adaptive_radius_px"] <= 16.0 for gate in graph["source_gates"]))
        self.assertTrue(any(gate["adaptive_radius_px"] == 16.0 for gate in graph["source_gates"]))

    def test_invalid_configuration_and_duplicate_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            generate_adaptive_candidate_graph([], AdaptiveCandidateConfig(max_radius_px=7.0))
        with self.assertRaises(ValueError):
            generate_adaptive_candidate_graph(
                [], AdaptiveCandidateConfig(density_saturation_count=1.5)
            )
        with self.assertRaises(ValueError):
            generate_adaptive_candidate_graph([
                _row("duplicate", 0, 0), _row("duplicate", 1, 1)
            ])

    def test_optional_new_track_score_is_validated_without_changing_graph(self):
        rows = [_row("a0", 0, 0), _row("a1", 1, 1)]
        base = generate_adaptive_candidate_graph(rows)
        tuned = generate_adaptive_candidate_graph(
            rows, AdaptiveCandidateConfig(new_track_score_px=9.0)
        )
        self.assertEqual(base["candidate_edges"], tuned["candidate_edges"])
        with self.assertRaises(ValueError):
            AdaptiveCandidateConfig(new_track_score_px=0).validate()
        with self.assertRaises(ValueError):
            AdaptiveCandidateConfig(posterior_probability_floor=1.1).validate()


if __name__ == "__main__":
    unittest.main()
