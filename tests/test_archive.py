import io
import unittest
from zipfile import ZIP_DEFLATED, ZipFile

from gbm_audit.archive import read_member_bytes, validate_zip_archive


class TestArchiveSafety(unittest.TestCase):
    def test_small_archive_is_accepted_and_read_exactly(self):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("small.txt", b"hello")
        buffer.seek(0)
        with ZipFile(buffer) as archive:
            validate_zip_archive(archive)
            self.assertEqual(read_member_bytes(archive, "small.txt"), b"hello")

    def test_high_compression_ratio_is_rejected(self):
        buffer = io.BytesIO()
        with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
            archive.writestr("bomb.txt", b"0" * 1_000_000)
        buffer.seek(0)
        with ZipFile(buffer) as archive:
            with self.assertRaisesRegex(ValueError, "compression ratio"):
                validate_zip_archive(archive)


if __name__ == "__main__":
    unittest.main()
