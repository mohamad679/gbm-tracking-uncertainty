import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.stage_d_huh7_audit import audit_huh7_archive


def _tif(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="TIFF")
    return stream.getvalue()


def _archive(path: Path):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for sequence in ("01", "02"):
            root = f"Fluo-C2DL-Huh7/{sequence}"
            for frame in range(4):
                image = np.zeros((8, 9), dtype=np.uint8)
                mask = np.zeros((8, 9), dtype=np.uint16)
                mask[1 + frame, 2] = 1
                mask[5, 5 + (frame % 2)] = 2
                archive.writestr(f"{root}/t{frame:03d}.tif", _tif(image))
                archive.writestr(f"{root}_GT/TRA/man_track{frame:03d}.tif", _tif(mask))
            archive.writestr(f"{root}_GT/TRA/man_track.txt", "1 0 3 0\n2 0 3 0\n")


class TestStageDHuh7Audit(unittest.TestCase):
    def test_data_only_audit_is_deterministic_and_locks_first_eligible_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Fluo-C2DL-Huh7.zip"
            _archive(path)
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            kwargs = {
                "expected_size": path.stat().st_size,
                "expected_sha256": sha256,
                "min_tracks": 2,
                "min_transition_slots": 4,
            }
            first = audit_huh7_archive(path, **kwargs)
            second = audit_huh7_archive(path, **kwargs)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "LOCKED_UNEVALUATED")
            self.assertEqual(first["locked_sequence_id"], "01")
            self.assertFalse(first["data_only_invariants"]["coordinates_extracted"])
            self.assertFalse(first["data_only_invariants"]["outcome_metrics_exposed"])
            self.assertNotIn("x_px", repr(first))
            self.assertNotIn("rmse", repr(first).lower())

    def test_identity_and_structural_thresholds_are_enforced(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "Fluo-C2DL-Huh7.zip"
            _archive(path)
            sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                audit_huh7_archive(
                    path, expected_size=path.stat().st_size,
                    expected_sha256="0" * 64, min_transition_slots=1,
                )
            with self.assertRaisesRegex(ValueError, "no sequence passes"):
                audit_huh7_archive(
                    path, expected_size=path.stat().st_size,
                    expected_sha256=sha256, min_transition_slots=999,
                )


if __name__ == "__main__":
    unittest.main()
