import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.t98g_audit import audit_t98g_archive


def _tif(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="TIFF")
    return stream.getvalue()


def _archive(path: Path, *, missing_label=False, extra_label=False, different_raw=False):
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for variant_index, variant in enumerate(("T98G_human", "T98G_detectron2")):
            root = f"T98G_electrotaxis/{variant}"
            for frame in range(37):
                raw = np.full((5, 6), frame, dtype=np.uint16)
                if different_raw and variant_index and frame == 1:
                    raw[0, 0] = 99
                mask = np.zeros((5, 6), dtype=np.uint16)
                if not (missing_label and frame == 19):
                    mask[1, 1 + frame % 5] = 1
                if frame == 1:
                    mask[3, 3] = 2
                if frame == 2 and extra_label:
                    mask[4, 4] = 99
                archive.writestr(
                    f"{root}/T98G_sample/20180101ef002xy01t{frame + 1:02d}.tif", _tif(raw)
                )
                archive.writestr(f"{root}/T98G_sample_GT/TRA/mask{frame:03d}.tif", _tif(mask))
                archive.writestr(f"{root}/T98G_sample_GT/SEG/man_seg{frame:03d}.tif", _tif(mask))
            archive.writestr(
                f"{root}/T98G_sample_GT/TRA/man_track.txt", "1 0 36 0\n2 1 1 0\n"
            )


def _checksums(path: Path):
    data = path.read_bytes()
    return len(data), hashlib.md5(data, usedforsecurity=False).hexdigest(), hashlib.sha256(data).hexdigest()


class TestT98GAudit(unittest.TestCase):
    def test_structural_audit_is_deterministic_and_exports_no_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "T98G_electrotaxis.zip"
            _archive(path)
            size, md5, sha256 = _checksums(path)
            first = audit_t98g_archive(path, expected_size=size, expected_md5=md5,
                                       expected_sha256=sha256)
            second = audit_t98g_archive(path, expected_size=size, expected_md5=md5,
                                        expected_sha256=sha256)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "PASS")
            self.assertEqual(first["lock_state"], "LOCKED_UNEVALUATED")
            self.assertFalse(first["evaluation_boundary"]["performance_evaluation_run"])
            self.assertNotIn("tracks", first["locked_test"])
            self.assertNotIn("observations", str(first))

    def test_archive_identity_mismatch_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "T98G_electrotaxis.zip"
            _archive(path)
            size, md5, sha256 = _checksums(path)
            with self.assertRaisesRegex(ValueError, "MD5 mismatch"):
                audit_t98g_archive(path, expected_size=size, expected_md5="0" * 32,
                                   expected_sha256=sha256)

    def test_missing_active_track_label_is_recorded_as_a_structural_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "T98G_electrotaxis.zip"
            _archive(path, missing_label=True)
            size, md5, sha256 = _checksums(path)
            result = audit_t98g_archive(path, expected_size=size, expected_md5=md5,
                                        expected_sha256=sha256)
            self.assertEqual(result["locked_test"]["missing_active_label_instances"], 1)

    def test_label_outside_lineage_interval_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "T98G_electrotaxis.zip"
            _archive(path, extra_label=True)
            size, md5, sha256 = _checksums(path)
            with self.assertRaisesRegex(ValueError, "outside lineage intervals"):
                audit_t98g_archive(path, expected_size=size, expected_md5=md5,
                                   expected_sha256=sha256)

    def test_variants_must_share_the_raw_sequence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "T98G_electrotaxis.zip"
            _archive(path, different_raw=True)
            size, md5, sha256 = _checksums(path)
            with self.assertRaisesRegex(ValueError, "identical raw frames"):
                audit_t98g_archive(path, expected_size=size, expected_md5=md5,
                                   expected_sha256=sha256)


if __name__ == "__main__":
    unittest.main()
