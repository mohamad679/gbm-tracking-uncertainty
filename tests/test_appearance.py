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

    def test_empty_out_of_bounds_patch_keeps_fixed_descriptor_length(self):
        image = np.zeros((8, 8), dtype=np.float32)
        descriptor = patch_descriptor(image, 1000.0, 1000.0)
        self.assertEqual(descriptor, [0.0] * 28)

    def test_invalid_descriptor_inputs_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "2D grayscale"):
            patch_descriptor(np.zeros((2, 2, 3), dtype=np.float32), 0, 0)
        with self.assertRaisesRegex(ValueError, "non-negative"):
            patch_descriptor(np.zeros((2, 2), dtype=np.float32), 0, 0, radius=-1)
        with self.assertRaisesRegex(ValueError, "finite"):
            patch_descriptor(np.zeros((2, 2), dtype=np.float32), float("nan"), 0)

    def test_add_descriptors_does_not_mutate_observations(self):
        rows = [{"observation_id": "a", "frame": 0, "x_px": 3.0, "y_px": 3.0, "area_px": 4}]
        enriched = add_descriptors(rows, {0: np.ones((8, 8), dtype=np.float32)})
        self.assertNotIn("appearance_descriptor", rows[0])
        self.assertEqual(len(enriched[0]["appearance_descriptor"]), 28)


if __name__ == "__main__":
    unittest.main()
