import unittest

import numpy as np

from gbm_audit.appearance import add_descriptors, patch_descriptor


class TestAppearance(unittest.TestCase):
    def test_patch_descriptor_is_deterministic_and_finite(self):
        image = np.zeros((21, 21), dtype=np.float32)
        image[8:13, 8:13] = 1.0
        first = patch_descriptor(image, 10, 10)
        second = patch_descriptor(image, 10, 10)
        self.assertEqual(first, second)
        self.assertTrue(all(np.isfinite(value) for value in first))
        self.assertEqual(len(first), 28)

    def test_add_descriptors_does_not_mutate_observations(self):
        rows = [{"observation_id": "a", "frame": 0, "x_px": 3.0, "y_px": 3.0, "area_px": 4}]
        enriched = add_descriptors(rows, {0: np.ones((8, 8), dtype=np.float32)})
        self.assertNotIn("appearance_descriptor", rows[0])
        self.assertEqual(len(enriched[0]["appearance_descriptor"]), 28)


if __name__ == "__main__":
    unittest.main()
