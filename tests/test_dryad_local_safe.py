import tempfile
import unittest
from pathlib import Path
import zipfile

from gbm_audit.dryad_local_safe import inspect_bundle


class TestDryadLocalSafe(unittest.TestCase):
    def test_inventory_ignores_macos_appledouble_table_members(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle.zip"
            with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "To Generate Figures/Data/real.csv",
                    "track,frame,x,y\na,0,0,0\n",
                )
                archive.writestr(
                    "__MACOSX/To Generate Figures/Data/._fake.xlsx",
                    b"not-an-xlsx-workbook",
                )
                archive.writestr(
                    "To Generate Figures/Data/.DS_Store",
                    b"metadata",
                )

            result = inspect_bundle(bundle)

            self.assertEqual(result["member_count"], 3)
            self.assertEqual(result["ignored_macos_metadata_members"], 2)
            self.assertEqual(len(result["candidate_tables"]), 1)
            self.assertEqual(
                result["candidate_tables"][0]["path"],
                "To Generate Figures/Data/real.csv",
            )

    def test_inventory_allows_high_compression_non_table_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bundle.zip"
            with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(
                    "To Generate Figures/Data/real.csv",
                    "track,frame,x,y\na,0,0,0\n",
                )
                # Highly-compressible binary image surrogate: its compression ratio
                # exceeds the generic guard, but it is not parsed as a tracking table.
                archive.writestr(
                    "To Generate Figures/Data/PIV/deformation.tif",
                    b"\x00" * 2_000_000,
                )

            result = inspect_bundle(bundle)

            self.assertEqual(result["member_count"], 2)
            self.assertGreaterEqual(result["high_ratio_non_table_members"], 1)
            self.assertEqual(len(result["candidate_tables"]), 1)
            self.assertEqual(
                result["candidate_tables"][0]["path"],
                "To Generate Figures/Data/real.csv",
            )


if __name__ == "__main__":
    unittest.main()
