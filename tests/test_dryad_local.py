import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import zipfile

from gbm_audit.dryad_local import inventory, normalize


def _digest(path: Path, algorithm: str) -> str:
    h = hashlib.new(algorithm)
    h.update(path.read_bytes())
    return h.hexdigest()


class TestDryadLocal(unittest.TestCase):
    def _fixture(self, root: Path):
        source = root / "source"
        source.mkdir()
        bundle = source / "To Generate Figures.zip"
        with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "exp1.csv",
                "cell,track,frame,time,x,y\n"
                "tumour,a,0,0,0,0\n"
                "tumour,a,1,15,1,0\n"
                "microglia,m,0,0,5,5\n",
            )
            archive.writestr(
                "exp2.csv",
                "cell,track,frame,time,x,y\n"
                "tumour,b,0,0,0,0\n"
                "tumour,b,1,15,2,0\n",
            )
            archive.writestr(
                "exp3.csv",
                "cell,track,frame,time,x,y\n"
                "tumour,c,0,0,0,0\n"
                "tumour,c,1,15,3,0\n",
            )
        readme = source / "README_for_To Generate Figures.docx"
        readme.write_bytes(b"test-docx-placeholder")
        bundle_md5 = _digest(bundle, "md5")
        readme_md5 = _digest(readme, "md5")
        manifest = root / "source-manifest.json"
        manifest.write_text(
            json.dumps(
                {
                    "files": [
                        {
                            "path": bundle.name,
                            "size_bytes": bundle.stat().st_size,
                            "digest_type": "md5",
                            "digest": bundle_md5,
                        },
                        {
                            "path": readme.name,
                            "size_bytes": readme.stat().st_size,
                            "digest_type": "md5",
                            "digest": readme_md5,
                        },
                    ]
                }
            ),
            encoding="utf-8",
        )
        return source, manifest, bundle_md5, readme_md5

    def test_inventory_is_schema_only_and_lists_candidate_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, manifest, bundle_md5, readme_md5 = self._fixture(root)
            with patch("gbm_audit.dryad_local.REQUIRED_BUNDLE_MD5", bundle_md5), patch(
                "gbm_audit.dryad_local.REQUIRED_README_MD5", readme_md5
            ):
                result = inventory(source, manifest)
            self.assertEqual(result["status"], "SCHEMA_ONLY_INVENTORY_COMPLETE_NO_METHOD_OUTCOMES")
            self.assertEqual(result["archive"]["member_count"], 3)
            self.assertEqual(len(result["archive"]["candidate_tables"]), 3)
            self.assertIn("No tracking-method performance", result["boundary"])

    def test_normalization_refuses_unlocked_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, manifest, bundle_md5, readme_md5 = self._fixture(root)
            lock = root / "schema-lock.json"
            lock.write_text(
                json.dumps({"status": "PENDING_LOCAL_SCHEMA_INSPECTION", "source_bundle": {"md5": bundle_md5}}),
                encoding="utf-8",
            )
            with patch("gbm_audit.dryad_local.REQUIRED_BUNDLE_MD5", bundle_md5), patch(
                "gbm_audit.dryad_local.REQUIRED_README_MD5", readme_md5
            ):
                with self.assertRaisesRegex(ValueError, "not LOCKED"):
                    normalize(source, manifest, lock, root / "normalized")

    def test_locked_csv_schema_normalizes_three_experiments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, manifest, bundle_md5, readme_md5 = self._fixture(root)
            base_spec = {
                "format": "csv",
                "sheet": None,
                "matlab_variable": None,
                "delimiter": ",",
                "header_row": 1,
                "column_map": {
                    "track_id": "track",
                    "frame": "frame",
                    "time_min": "time",
                    "x_um": "x",
                    "y_um": "y",
                    "cell_type": "cell",
                },
                "cell_type_filter": {"enabled": True, "accepted_values": ["tumour"]},
                "coordinate_scale_to_um": 1.0,
                "time_scale_to_min": 1.0,
                "frame_interval_min_if_time_absent": None,
            }
            lock = root / "schema-lock.json"
            lock.write_text(
                json.dumps(
                    {
                        "status": "LOCKED",
                        "source_bundle": {"md5": bundle_md5},
                        "experiments": {
                            "experiment_1": {**base_spec, "source_members": ["exp1.csv"]},
                            "experiment_2": {**base_spec, "source_members": ["exp2.csv"]},
                            "experiment_3": {**base_spec, "source_members": ["exp3.csv"]},
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch("gbm_audit.dryad_local.REQUIRED_BUNDLE_MD5", bundle_md5), patch(
                "gbm_audit.dryad_local.REQUIRED_README_MD5", readme_md5
            ):
                result = normalize(source, manifest, lock, root / "normalized")
            self.assertEqual(result["status"], "NORMALIZED_THREE_EXPERIMENT_DRYAD_REFERENCE")
            self.assertEqual(result["biological_n"], 3)
            self.assertEqual(result["experiments"]["experiment_1"]["track_count"], 1)
            self.assertEqual(result["experiments"]["experiment_1"]["retained_glioma_observations"], 2)


if __name__ == "__main__":
    unittest.main()
