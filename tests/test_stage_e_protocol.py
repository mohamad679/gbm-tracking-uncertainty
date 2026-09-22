import hashlib
import json
from pathlib import Path
import unittest


DOCS = Path("docs")


def load_json(name: str) -> dict:
    return json.loads((DOCS / name).read_text())


def sha256(name: str) -> str:
    return hashlib.sha256((DOCS / name).read_bytes()).hexdigest()


class TestStageEProtocol(unittest.TestCase):
    def setUp(self):
        self.manifest = load_json("stage-e-dataset-manifest.json")
        self.split = load_json("stage-e-split-lock.json")
        self.protocol = load_json("stage-e-protocol.json")

    def test_registered_artifact_hashes_match(self):
        self.assertEqual(
            self.split["dataset_manifest_sha256"],
            sha256("stage-e-dataset-manifest.json"),
        )
        inputs = self.protocol["registered_inputs"]
        self.assertEqual(inputs["dataset_manifest_sha256"], sha256("stage-e-dataset-manifest.json"))
        self.assertEqual(inputs["split_lock_sha256"], sha256("stage-e-split-lock.json"))

    def test_manifest_contains_only_registered_new_domains(self):
        dataset_ids = {dataset["dataset_id"] for dataset in self.manifest["datasets"]}
        self.assertEqual(
            dataset_ids,
            {
                "CTC_Fluo-N2DH-GOWT1_training",
                "CTC_DIC-C2DH-HeLa_training",
                "CTC_Fluo-N2DH-SIM+_training",
            },
        )
        consumed = {item["source"] for item in self.manifest["previously_consumed_sources"]}
        self.assertEqual(
            consumed,
            {"CTC_PhC-C2DH-U373", "T98G_sample", "CTC_Fluo-C2DL-Huh7"},
        )

    def test_every_dataset_has_one_development_and_one_locked_sequence(self):
        assignments = self.split["assignments"]
        by_dataset = {}
        for assignment in assignments:
            by_dataset.setdefault(assignment["dataset_id"], []).append(assignment)
        self.assertEqual(len(by_dataset), 3)
        for dataset_assignments in by_dataset.values():
            self.assertEqual({item["sequence_id"] for item in dataset_assignments}, {"01", "02"})
            sequence_02 = next(item for item in dataset_assignments if item["sequence_id"] == "02")
            self.assertIn("locked", sequence_02["role"])

    def test_locked_test_starts_without_outcome_access(self):
        self.assertEqual(
            self.split["status"],
            "LOCKED_BEFORE_IMPLEMENTATION_OR_OUTCOME_EVALUATION",
        )
        self.assertTrue(all(value is False for value in self.split["test_access_state"].values()))
        real_tests = self.split["decision_population"]["real_locked_tests"]
        self.assertEqual(
            real_tests,
            [
                "CTC_Fluo-N2DH-GOWT1_training/02",
                "CTC_DIC-C2DH-HeLa_training/02",
            ],
        )

    def test_protocol_has_fixed_scope_and_decision_policy(self):
        self.assertEqual(
            self.protocol["status"],
            "STEPS_1_TO_3_LOCKED_NO_OUTCOMES_EVALUATED",
        )
        self.assertEqual(len(self.protocol["primary_endpoints"]), 2)
        policy = self.protocol["decision_policy"]
        self.assertEqual(len(policy["GO"]), 4)
        self.assertEqual(policy["biological_claim"], "not supported under every decision")
        self.assertIn("STOP", policy)
        self.assertIn("REVISE", policy)


if __name__ == "__main__":
    unittest.main()
