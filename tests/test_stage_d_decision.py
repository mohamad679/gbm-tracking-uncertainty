import copy
import unittest

from gbm_audit.stage_d_decision import (
    DEFAULT_KNOWN_LOCKED_SOURCES,
    FORBIDDEN_OPERATOR_EVALUATION_SOURCES,
    build_step4_decision,
)


def _development_artifact():
    return {
        "status": "DEVELOPMENT_COMPLETE",
        "development_sequence": "01",
        "locked_test_sequence_evaluated": False,
        "invariants": {"selection_performed": False},
    }


class TestStageDDecision(unittest.TestCase):
    def test_no_eligible_source_emits_explicit_hold_without_evaluation(self):
        result = build_step4_decision(_development_artifact(), candidate_sources=[
            {"source_id": "U373_sequence_02_archival_v1_test", "independent": False,
             "data_only_audit_pass": True, "locked": True},
            {"source_id": "T98G_locked_stage_c_v2_test", "independent": True,
             "data_only_audit_pass": True, "locked": True},
        ])
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["status"], "HOLD_NO_INDEPENDENT_EVALUATION_SOURCE")
        self.assertFalse(result["evaluation_attempted"])
        self.assertEqual(result["evaluation_count"], 0)
        self.assertEqual(result["eligible_source_count"], 0)
        self.assertIn("already_consumed_locked_source",
                      result["audited_candidate_sources"][1]["rejection_reasons"])

    def test_eligible_source_is_not_auto_evaluated(self):
        with self.assertRaises(ValueError):
            build_step4_decision(_development_artifact(), candidate_sources=[
                {"source_id": "new_dataset_v1", "independent": True,
                 "data_only_audit_pass": True, "locked": True},
            ])

    def test_selection_or_locked_evaluation_in_step3_is_rejected(self):
        selected = copy.deepcopy(_development_artifact())
        selected["invariants"]["selection_performed"] = True
        with self.assertRaises(ValueError):
            build_step4_decision(selected)
        locked = copy.deepcopy(_development_artifact())
        locked["locked_test_sequence_evaluated"] = True
        with self.assertRaises(ValueError):
            build_step4_decision(locked)

    def test_forbidden_source_registry_is_explicit(self):
        self.assertIn("02", FORBIDDEN_OPERATOR_EVALUATION_SOURCES)
        self.assertIn("T98G_sample", FORBIDDEN_OPERATOR_EVALUATION_SOURCES)
        self.assertEqual(len(DEFAULT_KNOWN_LOCKED_SOURCES), 2)


if __name__ == "__main__":
    unittest.main()
