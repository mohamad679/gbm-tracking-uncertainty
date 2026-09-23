import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gbm_audit.external_biology import (
    _grid_candidates,
    _link_summary,
    _nearest_neighbor_links,
    _posterior_links,
    _true_links,
    load_trackmate_reference,
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TestExternalBiology(unittest.TestCase):
    def test_parser_reconstructs_source_tracks_and_units(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info = root / "info.json"
            spots = root / "spots.csv"
            tracks = root / "tracks.csv"
            info.write_text(json.dumps({"Frame interval (s)": 600.0}), encoding="utf-8")
            with tracks.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=["TRACK_ID", "NUMBER_SPOTS"])
                writer.writeheader()
                writer.writerow({"TRACK_ID": 1, "NUMBER_SPOTS": 2})
            with spots.open("w", newline="", encoding="utf-8") as handle:
                fields = ["ID", "TRACK_ID", "POSITION_X", "POSITION_Y", "POSITION_T", "FRAME"]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerow({"ID": 10, "TRACK_ID": 1, "POSITION_X": 1, "POSITION_Y": 2, "POSITION_T": 0, "FRAME": 0})
                writer.writerow({"ID": 11, "TRACK_ID": 1, "POSITION_X": 2, "POSITION_Y": 2, "POSITION_T": 600, "FRAME": 1})
                writer.writerow({"ID": 12, "TRACK_ID": -1, "POSITION_X": 5, "POSITION_Y": 5, "POSITION_T": 0, "FRAME": 0})
            with patch("gbm_audit.external_biology.SOURCE_INFO_SHA256", _sha(info)), \
                 patch("gbm_audit.external_biology.SOURCE_SPOTS_SHA256", _sha(spots)), \
                 patch("gbm_audit.external_biology.SOURCE_TRACKS_SHA256", _sha(tracks)):
                result = load_trackmate_reference(info, spots, tracks)
            self.assertEqual(result["track_count"], 1)
            self.assertEqual(result["observation_count"], 2)
            self.assertEqual(result["frame_interval_min"], 10.0)
            self.assertEqual([row["observation_id"] for row in result["observations"]], ["ext_10", "ext_11"])

    def test_parser_rejects_duplicate_track_frame(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            info = root / "info.json"
            spots = root / "spots.csv"
            tracks = root / "tracks.csv"
            info.write_text(json.dumps({"Frame interval (s)": 600.0}), encoding="utf-8")
            tracks.write_text("TRACK_ID,NUMBER_SPOTS\n1,2\n", encoding="utf-8")
            spots.write_text(
                "ID,TRACK_ID,POSITION_X,POSITION_Y,POSITION_T,FRAME\n"
                "10,1,1,2,0,0\n11,1,2,2,0,0\n",
                encoding="utf-8",
            )
            with patch("gbm_audit.external_biology.SOURCE_INFO_SHA256", _sha(info)), \
                 patch("gbm_audit.external_biology.SOURCE_SPOTS_SHA256", _sha(spots)), \
                 patch("gbm_audit.external_biology.SOURCE_TRACKS_SHA256", _sha(tracks)):
                with self.assertRaisesRegex(ValueError, "multiple reference spots"):
                    load_trackmate_reference(info, spots, tracks)

    def test_grid_candidates_and_true_links(self):
        observations = [
            {"observation_id": "a0", "true_track_id": 1, "frame": 0, "x_um": 0.0, "y_um": 0.0},
            {"observation_id": "b0", "true_track_id": 2, "frame": 0, "x_um": 20.0, "y_um": 0.0},
            {"observation_id": "a1", "true_track_id": 1, "frame": 1, "x_um": 1.0, "y_um": 0.0},
            {"observation_id": "b1", "true_track_id": 2, "frame": 1, "x_um": 19.0, "y_um": 0.0},
        ]
        edges = _grid_candidates(observations, 5.0)
        self.assertEqual({(left, right) for left, right, _ in edges}, {("a0", "a1"), ("b0", "b1")})
        self.assertEqual(_true_links(observations), {("a0", "a1"), ("b0", "b1")})

    def test_nearest_neighbor_and_link_summary(self):
        observations = [
            {"observation_id": "a0", "frame": 0, "x_um": 0.0, "y_um": 0.0},
            {"observation_id": "b0", "frame": 0, "x_um": 10.0, "y_um": 0.0},
            {"observation_id": "a1", "frame": 1, "x_um": 1.0, "y_um": 0.0},
            {"observation_id": "b1", "frame": 1, "x_um": 9.0, "y_um": 0.0},
        ]
        edges = _grid_candidates(observations, 5.0)
        predicted = _nearest_neighbor_links(observations, edges)
        truth = {("a0", "a1"), ("b0", "b1")}
        self.assertEqual(predicted, truth)
        self.assertEqual(_link_summary(predicted, truth)["f1"], 1.0)

    def test_posterior_selection_is_one_to_one(self):
        probabilities = {
            ("a0", "x1"): 0.95,
            ("b0", "x1"): 0.90,
            ("b0", "y1"): 0.80,
        }
        selected = _posterior_links(probabilities)
        self.assertIn(("a0", "x1"), selected)
        self.assertIn(("b0", "y1"), selected)
        self.assertNotIn(("b0", "x1"), selected)


if __name__ == "__main__":
    unittest.main()
