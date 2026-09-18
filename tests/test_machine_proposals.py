"""Check mechanics on synthetic images; these are not biological validations."""

import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from gbm_audit.proposals import link_frames, peaks


class TestMachineProposals(unittest.TestCase):
    def test_one_bright_spot_can_be_followed_for_ten_frames(self):
        with tempfile.TemporaryDirectory() as directory:
            detections = []
            for frame in range(10):
                image = np.zeros((170, 170), dtype=np.uint8)
                image[80:87, 65 + frame:72 + frame] = 240
                path = Path(directory) / f"T_{frame:03d}.png"
                Image.fromarray(image).save(path)
                found = peaks(path)
                self.assertEqual(len(found), 1)
                detections.append((frame, found))
            tracks = link_frames(detections)
            self.assertEqual(len(tracks), 1)
            self.assertEqual(len(tracks[0]), 10)

    def test_missing_frame_is_not_automatically_bridged(self):
        first = (70, 70, 180)
        tracks = link_frames([(0, [first]), (1, []), (2, [first])])
        self.assertEqual(sorted(len(track) for track in tracks), [1, 1])


if __name__ == "__main__":
    unittest.main()
