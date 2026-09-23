import hashlib
import json
from pathlib import Path
import unittest


DOCS = Path("docs/evidence/stage-e")


def load_json(name: str) -> dict:
    return json.loads((DOCS / name).read_text())


def sha256(name: str) -> str:
    return hashlib.sha256((DOCS / name).read_bytes()).hexdigest()


class TestStageEFinalEvaluation(unittest.TestCase):
    def setUp(self):
        self.result = load_json("stage-e-sequence02-evaluation.json")
        self.lock = load_json("stage-e-sequence02-evaluation-lock.json")

    def test_published_artifact_identity_is_locked(self):
        self.assertEqual(
            sha256("stage-e-sequence02-evaluation.json"),
            "514fae28860f51d57cdda3453ffe6639687f753a7e2ac0ed48d9a1f9d0faa545",
        )
        self.assertEqual(
            self.result["evaluation_lock_sha256"],
            self.lock["pre_evaluation_lock_sha256"],
        )
        self.assertEqual(
            self.lock["evaluation_artifact_sha256"],
            sha256("stage-e-sequence02-evaluation.json"),
        )

    def test_one_time_result_is_valid_revise(self):
        self.assertEqual(self.result["status"], "COMPLETE_REVISE")
        self.assertEqual(self.result["decision"], "REVISE")
        self.assertEqual(self.result["evaluation_count"], 1)
        self.assertTrue(self.result["evaluation_attempted"])
        self.assertFalse(self.result["selection_performed_after_heldout_inspection"])
        self.assertEqual(
            self.result["decision_reason"],
            "The valid one-time locked evaluation failed one or more pre-registered GO gates; no test retuning is permitted.",
        )

    def test_registered_gate_outcomes_are_preserved(self):
        gates = self.result["gates"]
        self.assertTrue(gates["provenance_and_split_integrity"])
        self.assertTrue(gates["leakage_boundary"])
        self.assertFalse(gates["calibrated_error_auprc_beats_distance_on_both_real_tests"])
        self.assertTrue(gates["selective_risk_improves_over_full_coverage_on_both_real_tests"])
        self.assertTrue(gates["calibration_improves_under_registered_rule"])
        self.assertFalse(gates["motion_endpoint_wins_at_least_five_of_eight"])
        self.assertEqual(gates["motion_endpoint_wins"], 4)
        self.assertTrue(gates["reproducibility"])

    def test_clean_real_domain_endpoints_explain_the_decision(self):
        gowt1 = self.result["results"]["CTC_Fluo-N2DH-GOWT1_training"]["clean_primary_endpoints"]
        hela = self.result["results"]["CTC_DIC-C2DH-HeLa_training"]["clean_primary_endpoints"]
        self.assertLess(
            gowt1["calibrated_uncertainty"]["association_error_auprc"],
            gowt1["distance_confidence"]["association_error_auprc"],
        )
        self.assertGreater(
            hela["calibrated_uncertainty"]["association_error_auprc"],
            hela["distance_confidence"]["association_error_auprc"],
        )
        for endpoints in (gowt1, hela):
            self.assertLess(
                endpoints["calibrated_uncertainty"]["selective_link_risk"]["risk"],
                endpoints["calibrated_full_coverage_risk"],
            )
            self.assertLessEqual(
                endpoints["calibrated_uncertainty"]["calibration"]["brier"],
                endpoints["uncalibrated_uncertainty"]["calibration"]["brier"],
            )


if __name__ == "__main__":
    unittest.main()
