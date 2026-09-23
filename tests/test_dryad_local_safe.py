import tempfile
import unittest
from pathlib import Path
import zipfile

from gbm_audit.dryad_local_safe import inspect_bundle, _normalize_records_with_frame_strategy


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

    def test_global_time_rank_preserves_irregular_time_and_builds_frames(self):
        # Mirrors the deposited MAT schema: [time_hr, track_id, x_um, y_um].
        # Irregular acquisition intervals are deliberate; frame identity comes
        # from global time order, not from imposing a fixed interval.
        records = [
            [0.00, 1, 10.0, 20.0],
            [0.25, 1, 11.0, 20.0],
            [0.70, 1, 12.0, 20.0],
            [0.00, 2, 30.0, 40.0],
            [0.25, 2, 31.0, 40.0],
            [0.70, 2, 32.0, 40.0],
        ]
        spec = {
            "column_map": {
                "track_id": 1,
                "frame": None,
                "time_min": 0,
                "x_um": 2,
                "y_um": 3,
                "cell_type": None,
            },
            "cell_type_filter": {"enabled": False, "accepted_values": []},
            "coordinate_scale_to_um": 1.0,
            "time_scale_to_min": 60.0,
            "frame_interval_min_if_time_absent": None,
            "frame_derivation": "global_time_rank",
        }

        rows, summary = _normalize_records_with_frame_strategy(records, "experiment_1", spec)

        self.assertEqual(summary["frame_derivation"], "global_time_rank")
        self.assertEqual(summary["global_frame_count"], 3)
        self.assertEqual(summary["frame_min"], 0)
        self.assertEqual(summary["frame_max"], 2)
        by_track = {}
        for row in rows:
            by_track.setdefault(row["track_id"], []).append(row)
        self.assertEqual([row["frame"] for row in by_track["1"]], [0, 1, 2])
        self.assertEqual([row["time_min"] for row in by_track["1"]], [0.0, 15.0, 42.0])
        self.assertEqual([row["x_um"] for row in by_track["2"]], [30.0, 31.0, 32.0])


if __name__ == "__main__":
    unittest.main()
