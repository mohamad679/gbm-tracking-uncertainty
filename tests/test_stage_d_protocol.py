import json
from pathlib import Path
import unittest


class TestStageDProtocol(unittest.TestCase):
    def setUp(self):
        self.protocol = json.loads(
            Path("docs/archive/stage-d/stage-d-protocol.json").read_text()
        )

    def test_protocol_has_four_ordered_steps_and_stage_d_complete_with_hold(self):
        self.assertEqual(self.protocol["step_count"], 4)
        steps = self.protocol["steps"]
        self.assertEqual([step["step"] for step in steps], [1, 2, 3, 4])
        self.assertEqual([step["status"] for step in steps], ["complete", "complete", "complete", "complete"])
        self.assertEqual(self.protocol["status"], "STEP_4_COMPLETE_HOLD_NO_INDEPENDENT_SOURCE")

    def test_forbidden_evaluation_sources_are_not_development_sources(self):
        boundary = self.protocol["data_boundary"]
        self.assertNotIn("U373_sequence_02_archival_v1_test", boundary["development_sources"])
        self.assertNotIn("T98G_locked_stage_c_v2_test", boundary["development_sources"])
        self.assertIn("T98G_locked_stage_c_v2_test", boundary["forbidden_for_fit_or_selection"])

    def test_go_requires_all_declared_gates(self):
        gates = self.protocol["acceptance_gates"]
        policy = self.protocol["decision_policy"]
        self.assertGreaterEqual(len(gates), 7)
        self.assertIn("all gates pass", policy["GO"])
        self.assertIn("biological_claim", policy)


if __name__ == "__main__":
    unittest.main()
