import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.stage_e_ctc_metrics import (
    _track_assignments,
    _validate_frozen_development_identity,
    export_fixed_detection_ctc_result,
)


def _tif(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="TIFF")
    return stream.getvalue()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestStageECTCMetrics(unittest.TestCase):
    def test_track_assignments_include_linked_paths_and_singletons(self):
        observations = [
            {"observation_id": "a0", "frame": 0},
            {"observation_id": "a1", "frame": 1},
            {"observation_id": "solo", "frame": 0},
        ]
        assignments, tracks = _track_assignments(observations, {("a0", "a1")})
        self.assertEqual(assignments["a0"], assignments["a1"])
        self.assertNotEqual(assignments["a0"], assignments["solo"])
        self.assertEqual(len(tracks), 2)

    def test_invalid_non_forward_or_many_to_one_links_are_rejected(self):
        observations = [
            {"observation_id": "a0", "frame": 0},
            {"observation_id": "b0", "frame": 0},
            {"observation_id": "a1", "frame": 1},
        ]
        with self.assertRaisesRegex(ValueError, "forward-in-time"):
            _track_assignments(observations, {("a1", "a0")})
        with self.assertRaisesRegex(ValueError, "one-to-one"):
            _track_assignments(observations, {("a0", "a1"), ("b0", "a1")})

    def test_frozen_identity_binds_development_to_published_evaluation(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            manifest_path = directory / "manifest.json"
            split_path = directory / "split.json"
            development_path = directory / "development.json"
            evaluation_path = directory / "evaluation.json"
            evaluation_lock_path = directory / "evaluation-lock.json"

            manifest_path.write_text("manifest\n", encoding="utf-8")
            split_path.write_text("split\n", encoding="utf-8")
            development_path.write_text("development\n", encoding="utf-8")
            evaluation_path.write_text("evaluation\n", encoding="utf-8")
            evaluation_lock_path.write_text("lock\n", encoding="utf-8")

            development = {
                "dataset_manifest_sha256": _sha256(manifest_path),
                "split_lock_sha256": _sha256(split_path),
            }
            evaluation = {
                "dataset_manifest_sha256": _sha256(manifest_path),
                "split_lock_sha256": _sha256(split_path),
                "development_artifact_sha256": _sha256(development_path),
                "evaluation_count": 1,
                "evaluation_attempted": True,
            }
            evaluation_lock = {
                "status": "EVALUATED_ONCE",
                "evaluation_count": 1,
                "development_artifact_sha256": _sha256(development_path),
                "evaluation_artifact_sha256": _sha256(evaluation_path),
                "posterior_track_threshold": 0.5,
            }

            verified = _validate_frozen_development_identity(
                manifest_path,
                split_path,
                development_path,
                evaluation_lock_path,
                evaluation_path,
                development,
                evaluation_lock,
                evaluation,
            )
            self.assertTrue(verified["verified"])

            development_path.write_text("modified development\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "development artifact hash mismatch"):
                _validate_frozen_development_identity(
                    manifest_path,
                    split_path,
                    development_path,
                    evaluation_lock_path,
                    evaluation_path,
                    development,
                    evaluation_lock,
                    evaluation,
                )

    def test_export_relabels_gold_masks_without_changing_shapes(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            archive_path = directory / "sample.zip"
            root = "Sample"
            with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
                archive.writestr(f"{root}/02_GT/TRA/man_track.txt", "1 0 1 0\n")
                for frame in (0, 1):
                    mask = np.zeros((5, 6), dtype=np.uint16)
                    mask[2, 2 + frame] = 1
                    archive.writestr(
                        f"{root}/02_GT/TRA/man_track{frame:03d}.tif",
                        _tif(mask),
                    )
            observations = [
                {"observation_id": "ref_0001_0000", "frame": 0},
                {"observation_id": "ref_0001_0001", "frame": 1},
            ]
            gt_dir, res_dir, metadata = export_fixed_detection_ctc_result(
                archive_path,
                "02",
                observations,
                {("ref_0001_0000", "ref_0001_0001")},
                directory / "export",
                "test",
            )
            self.assertTrue((gt_dir / "TRA" / "man_track.txt").is_file())
            self.assertEqual(metadata["predicted_track_count"], 1)
            self.assertEqual((res_dir / "res_track.txt").read_text().strip(), "1 0 1 0")
            for frame in (0, 1):
                with Image.open(res_dir / f"mask{frame:03d}.tif") as image:
                    mask = np.asarray(image)
                self.assertEqual(mask.shape, (5, 6))
                self.assertEqual(int(mask.max()), 1)


if __name__ == "__main__":
    unittest.main()
