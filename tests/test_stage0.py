"""Protect against the axis mix-up observed between source prose and raw NPY headers."""

import tempfile
import unittest
from pathlib import Path
import hashlib
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np

from gbm_audit.cli import inspect_npz
from gbm_audit.roi import describe_roi
from scripts.fetch_pilot_rois import unpack_member


class TestImageAxisDetection(unittest.TestCase):
    def test_uses_independent_frame_count_to_identify_first_axis_as_time(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roi.npz"
            a = np.zeros((68, 5, 5), dtype=np.uint8)
            np.savez_compressed(path, Tstack=a, Vstack=a)
            result = inspect_npz(path, expected_frames=68)
            self.assertEqual(result["axis_interpretation"], "time,height,width")
            self.assertTrue(result["two_or_more_3d_channels_same_shape"])
            self.assertFalse(result["loaded_pixels"])

    def test_refuses_to_infer_axis_when_frame_count_matches_none(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roi.npz"
            np.savez_compressed(path, Tstack=np.zeros((5, 5, 68), dtype=np.uint8))
            result = inspect_npz(path, expected_frames=67)
            self.assertEqual(result["axis_interpretation"], "unverified")

    def test_flags_metadata_frame_count_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "roi.npz"
            np.savez_compressed(path, Tstack=np.zeros((3, 4, 4), dtype=np.uint8),
                                Vstack=np.ones((3, 4, 4), dtype=np.uint8), delta=1.45)
            with self.assertRaisesRegex(ValueError, "differs from metadata frame count"):
                describe_roi(path, expected_frames=2)

    def test_byte_range_extraction_checks_outer_crc_and_roi_hash(self):
        nested = BytesIO()
        np.savez_compressed(nested, Tstack=np.ones((3, 4, 4), dtype=np.uint8))
        contents = nested.getvalue()
        outer = BytesIO()
        with ZipFile(outer, "w", ZIP_DEFLATED) as archive:
            archive.writestr("Set_68/roi.npz", contents)
            item = archive.getinfo("Set_68/roi.npz")
        member = outer.getvalue()[item.header_offset:]
        sha = hashlib.sha256(contents).hexdigest()
        self.assertEqual(unpack_member(member, item.CRC, sha), contents)
        with self.assertRaisesRegex(ValueError, "CRC mismatch"):
            unpack_member(member, item.CRC ^ 1, sha)


if __name__ == "__main__":
    unittest.main()
