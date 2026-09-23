import io
import unittest
from unittest.mock import MagicMock, patch
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from gbm_audit.archive import read_member_bytes, validate_zip_archive
from gbm_audit.config import (
    MAX_ZIP_COMPRESSION_RATIO,
    MAX_ZIP_MEMBER_BYTES,
    MAX_ZIP_MEMBERS,
    MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES,
)


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

    def test_member_count_limit_is_enforced(self):
        archive = MagicMock()
        archive.infolist.return_value = [ZipInfo(str(index)) for index in range(MAX_ZIP_MEMBERS + 1)]
        with self.assertRaisesRegex(ValueError, "too many members"):
            validate_zip_archive(archive)

    def test_declared_member_and_total_size_limits_are_enforced(self):
        oversized = ZipInfo("large.bin")
        oversized.file_size = MAX_ZIP_MEMBER_BYTES + 1
        oversized.compress_size = oversized.file_size
        archive = MagicMock()
        archive.infolist.return_value = [oversized]
        with self.assertRaisesRegex(ValueError, "member is too large"):
            validate_zip_archive(archive)
        with self.assertRaisesRegex(ValueError, "member is too large"):
            read_member_bytes(archive, oversized)

        first = ZipInfo("first.bin")
        first.file_size = MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES // 2 + 1
        first.compress_size = first.file_size
        second = ZipInfo("second.bin")
        second.file_size = MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES // 2 + 1
        second.compress_size = second.file_size
        with patch("gbm_audit.archive.MAX_ZIP_MEMBER_BYTES", MAX_ZIP_TOTAL_UNCOMPRESSED_BYTES):
            archive.infolist.return_value = [first, second]
            with self.assertRaisesRegex(ValueError, "total uncompressed size"):
                validate_zip_archive(archive)

    def test_zero_compressed_size_and_read_mismatch_are_rejected(self):
        info = ZipInfo("bad.bin")
        info.file_size = 10
        info.compress_size = 0
        archive = MagicMock()
        archive.infolist.return_value = [info]
        with self.assertRaisesRegex(ValueError, "zero compressed size"):
            validate_zip_archive(archive)

        info.compress_size = 10
        archive.read.return_value = b"short"
        with self.assertRaisesRegex(ValueError, "size mismatch"):
            read_member_bytes(archive, info)


if __name__ == "__main__":
    unittest.main()
