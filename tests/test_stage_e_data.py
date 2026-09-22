import hashlib
import io
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.stage_e_data import audit_ctc_archive, build_development_manifest


def _tif(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="TIFF")
    return stream.getvalue()


def _entry(path: Path) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "dataset_id": "test_ctc",
        "archive_file": path.name,
        "archive_size_bytes": path.stat().st_size,
        "archive_sha256": digest,
        "annotation_type": "test reference",
        "archive_url": "https://example.invalid/test.zip",
        "pixel_size_um": [0.5, 0.5],
        "time_step_min": 5,
        "sequences": [
            {"sequence_id": "01", "raw_frame_count": 2, "tracking_mask_count": 2,
             "gold_segmentation_mask_count": 0, "lineage_row_count": 1},
            {"sequence_id": "02", "raw_frame_count": 2, "tracking_mask_count": 2,
             "gold_segmentation_mask_count": 0, "lineage_row_count": 1},
        ],
    }


class TestStageEDataBoundary(unittest.TestCase):
    def test_structural_audit_and_development_parser_do_not_decode_sequence_02(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.zip"
            root = "Test-CTC"
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                for sequence in ("01", "02"):
                    for frame in range(2):
                        image_path = f"{root}/{sequence}/t{frame:03d}.tif"
                        track_path = f"{root}/{sequence}_GT/TRA/man_track{frame:03d}.tif"
                        if sequence == "01":
                            image = np.zeros((6, 7), dtype=np.uint8)
                            mask = np.zeros((6, 7), dtype=np.uint16)
                            mask[2, 2 + frame] = 1
                            archive.writestr(image_path, _tif(image))
                            archive.writestr(track_path, _tif(mask))
                        else:
                            archive.writestr(image_path, b"not-a-tiff")
                            archive.writestr(track_path, b"not-a-tiff")
                    archive.writestr(f"{root}/{sequence}_GT/TRA/man_track.txt", "1 0 1 0\n")
            entry = _entry(path)
            audit = audit_ctc_archive(path, entry)
            self.assertFalse(audit["sequences"]["02"]["tiff_pixels_decoded"])
            manifest = build_development_manifest(path, entry)
            self.assertEqual(set(manifest["sequences"]), {"01"})
            self.assertEqual(manifest["stage_e_access_boundary"]["locked_sequences"], ["02"])
            self.assertEqual(manifest["sequences"]["01"]["tracks"][0]["observations"][1]["x_px"], 3.0)

    def test_identity_mismatch_is_rejected_before_decoding(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.zip"
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                archive.writestr("placeholder.txt", "x")
            entry = _entry(path)
            entry["archive_sha256"] = "0" * 64
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                audit_ctc_archive(path, entry)


if __name__ == "__main__":
    unittest.main()
