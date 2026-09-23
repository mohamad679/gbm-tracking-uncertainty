import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gbm_audit.dryad_confirmatory import evaluate_all


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestDryadConfirmatory(unittest.TestCase):
    def test_three_experiment_evaluation_preserves_biological_n_and_no_retuning(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            normalized = root / "normalized"
            normalized.mkdir()
            schema_lock = root / "schema-lock.json"
            schema_lock.write_text(json.dumps({"status": "LOCKED"}), encoding="utf-8")

            experiments = {}
            for experiment_index, experiment_id in enumerate(("experiment_1", "experiment_2", "experiment_3"), 1):
                path = normalized / f"{experiment_id}.csv"
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=["experiment_id", "cell_type", "track_id", "frame", "time_min", "x_um", "y_um"],
                    )
                    writer.writeheader()
                    for frame in range(3):
                        writer.writerow(
                            {
                                "experiment_id": experiment_id,
                                "cell_type": "glioma",
                                "track_id": "a",
                                "frame": frame,
                                "time_min": frame * 15,
                                "x_um": frame * 2.0,
                                "y_um": 0.0,
                            }
                        )
                        writer.writerow(
                            {
                                "experiment_id": experiment_id,
                                "cell_type": "glioma",
                                "track_id": "b",
                                "frame": frame,
                                "time_min": frame * 15,
                                "x_um": 40.0 + frame * (1.0 + experiment_index * 0.1),
                                "y_um": 0.0,
                            }
                        )
                experiments[experiment_id] = {
                    "path": path.name,
                    "sha256": _sha256(path),
                }

            manifest = {
                "status": "NORMALIZED_THREE_EXPERIMENT_DRYAD_REFERENCE",
                "biological_n": 3,
                "schema_lock_sha256": _sha256(schema_lock),
                "experiments": experiments,
            }
            (normalized / "normalized-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            with patch("gbm_audit.dryad_confirmatory.HYPOTHESIS_COUNT", 8), patch(
                "gbm_audit.dryad_confirmatory.TRACK_BOOTSTRAP_REPS", 20
            ), patch("gbm_audit.dryad_confirmatory.EXPERIMENT_BOOTSTRAP_REPS", 100):
                result = evaluate_all(normalized, schema_lock)

            self.assertEqual(result["status"], "COMPLETE_DRYAD_THREE_EXPERIMENT_CONFIRMATORY_EVALUATION")
            self.assertEqual(result["source"]["biological_n"], 3)
            self.assertFalse(result["frozen_configuration"]["dryad_specific_parameter_fitting"])
            self.assertEqual(sorted(result["experiments"]), ["experiment_1", "experiment_2", "experiment_3"])
            self.assertEqual(result["replicate_aware_statistics"]["biological_n"], 3)
            self.assertFalse(result["interpretation_boundary"]["human_gbm_wide_validation"])
            self.assertFalse(result["interpretation_boundary"]["stage_e_decision_changed"])

    def test_evaluation_refuses_unlocked_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            lock = root / "schema-lock.json"
            lock.write_text(json.dumps({"status": "PENDING_LOCAL_SCHEMA_INSPECTION"}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not LOCKED"):
                evaluate_all(root, lock)


if __name__ == "__main__":
    unittest.main()
