import io
import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import numpy as np
from PIL import Image

from gbm_audit.benchmark import build_manifest


def _tif(array):
    stream = io.BytesIO()
    Image.fromarray(array).save(stream, format="TIFF")
    return stream.getvalue()


class TestReferenceBenchmark(unittest.TestCase):
    def test_manifest_is_deterministic_and_contains_centroids(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "u373.zip"
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                for sequence in ("01", "02"):
                    root = f"PhC-C2DH-U373/{sequence}"
                    for frame in range(2):
                        mask = np.zeros((8, 9), dtype=np.uint16)
                        mask[2 + frame, 3:5] = 1
                        archive.writestr(f"{root}/t{frame:03d}.tif", _tif(np.zeros_like(mask, dtype=np.uint8)))
                        archive.writestr(f"{root}_GT/TRA/man_track{frame:03d}.tif", _tif(mask))
                    archive.writestr(f"{root}_GT/TRA/man_track.txt", "1 0 1 0\n")
            first = build_manifest(path)
            second = build_manifest(path)
            self.assertEqual(first, second)
            self.assertEqual(first["sequences"]["01"]["tracks"][0]["observations"][0]["x_px"], 3.5)
            self.assertEqual(first["sequences"]["01"]["consecutive_links"], 1)

    def test_unknown_lineage_parent_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "u373.zip"
            with ZipFile(path, "w", ZIP_DEFLATED) as archive:
                for sequence in ("01", "02"):
                    root = f"PhC-C2DH-U373/{sequence}"
                    mask = np.ones((3, 3), dtype=np.uint16)
                    archive.writestr(f"{root}/t000.tif", _tif(mask.astype(np.uint8)))
                    archive.writestr(f"{root}_GT/TRA/man_track000.tif", _tif(mask))
                    archive.writestr(f"{root}_GT/TRA/man_track.txt", "1 0 0 99\n")
            with self.assertRaisesRegex(ValueError, "unknown parent"):
                build_manifest(path)


if __name__ == "__main__":
    unittest.main()
