import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import zipfile

from gbm_audit.dryad_schema_probe import _context_matches, _docx_text, _xls_preview


class _FakeSheet:
    name = "Tracking"
    nrows = 2
    ncols = 4

    def cell_value(self, row, col):
        rows = [["track", "frame", "x", "y"], [1.0, 0.0, 10.0, 20.0]]
        return rows[row][col]


class _FakeBook:
    def sheet_names(self):
        return ["Tracking"]

    def sheet_by_name(self, name):
        self.last_name = name
        return _FakeSheet()

    def release_resources(self):
        pass


class TestDryadSchemaProbe(unittest.TestCase):
    def test_context_matches_returns_local_source_context(self):
        text = "alpha\nbeta\nStoreData = data;\ngamma\ndelta\n"
        matches = _context_matches(text, context=1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["line_number"], 3)
        self.assertEqual(matches[0]["lines"], ["beta", "StoreData = data;", "gamma"])

    def test_docx_text_extracts_paragraphs(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "README.docx"
            xml = (
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                '<w:body><w:p><w:r><w:t>Tracking schema note</w:t></w:r></w:p>'
                '<w:p><w:r><w:t>Second paragraph</w:t></w:r></w:p></w:body></w:document>'
            )
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("word/document.xml", xml)
            self.assertEqual(_docx_text(path), "Tracking schema note\nSecond paragraph")

    def test_xls_preview_records_sheet_shape_and_sample_rows(self):
        fake_xlrd = SimpleNamespace(open_workbook=lambda **kwargs: _FakeBook())
        with patch.dict("sys.modules", {"xlrd": fake_xlrd}):
            result = _xls_preview(b"fake-xls-bytes")
        self.assertEqual(result["kind"], "xls")
        self.assertEqual(result["sheets"][0]["name"], "Tracking")
        self.assertEqual(result["sheets"][0]["nrows"], 2)
        self.assertEqual(result["sheets"][0]["sample_rows"][0], ["track", "frame", "x", "y"])


if __name__ == "__main__":
    unittest.main()
