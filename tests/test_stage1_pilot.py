import tempfile
import unittest
from pathlib import Path

import numpy as np

from gbm_audit.pilot import prepare_window


class TestStage1PilotPreparation(unittest.TestCase):
    def test_prepares_consecutive_window_and_records_original_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "roi.npz"
            tumor = np.zeros((20, 200, 200), dtype=np.uint8)
            vessel = np.ones_like(tumor)
            tumor[:, 50:55, 70:75] = 255
            np.savez_compressed(source, Tstack=tumor, Vstack=vessel, delta=1.45)
            result = prepare_window(source, root / "out", "Set_67", 333, 84,
                                    "early", 5, 14)
            self.assertEqual(result["first_frame"], 5)
            self.assertEqual(result["last_frame_inclusive"], 14)
            self.assertEqual(result["crop_top_left_bottom_right"], [0, 0, 200, 200])
            self.assertEqual(len(result["frames"]), 10)
            self.assertTrue((root / "out" / "frames" / result["window_id"] / "T_005.png").is_file())

    def test_rejects_nonconsecutive_or_out_of_range_window(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "roi.npz"
            array = np.ones((10, 200, 200), dtype=np.uint8)
            np.savez_compressed(source, Tstack=array, Vstack=array)
            with self.assertRaises(ValueError):
                prepare_window(source, root / "out", "Set_67", 333, 84,
                                "late", 5, 5)
            with self.assertRaises(ValueError):
                prepare_window(source, root / "out", "Set_67", 333, 84,
                                "late", 5, 14)


if __name__ == "__main__":
    unittest.main()
