import unittest

import numpy as np

from gbm_audit.numerics import gaussian_emission, normalize_transition_rows, stationary_distribution


class TestNumerics(unittest.TestCase):
    def test_gaussian_emission_is_finite_and_positive(self):
        values = np.asarray([0.0, 1.0, 2.0])
        result = gaussian_emission(values, np.asarray([0.5, 1.5]), np.asarray([0.2, 0.3]))
        self.assertEqual(result.shape, (3, 2))
        self.assertTrue(np.all(np.isfinite(result)))
        self.assertTrue(np.all(result > 0))

    def test_transition_normalization_uses_fallback_for_empty_row(self):
        candidate = np.asarray([[2.0, 2.0], [0.0, 0.0]])
        fallback = np.asarray([[0.8, 0.2], [0.3, 0.7]])
        result = normalize_transition_rows(candidate, fallback)
        np.testing.assert_allclose(result, [[0.5, 0.5], [0.3, 0.7]])

    def test_transition_normalization_validates_shapes_and_uniform_fallback(self):
        with self.assertRaisesRegex(ValueError, "matching 2D"):
            normalize_transition_rows(np.asarray([1.0, 2.0]), np.asarray([1.0, 2.0]))
        candidate = np.asarray([[0.0, 0.0], [float("nan"), 0.0]])
        fallback = np.asarray([[0.0, 0.0], [0.0, 0.0]])
        np.testing.assert_allclose(normalize_transition_rows(candidate, fallback), [[0.5, 0.5], [0.5, 0.5]])

    def test_stationary_distribution(self):
        transition = np.asarray([[0.9, 0.1], [0.2, 0.8]])
        stationary = stationary_distribution(transition)
        np.testing.assert_allclose(stationary @ transition, stationary, atol=1e-10)
        self.assertAlmostEqual(float(stationary.sum()), 1.0)

    def test_stationary_distribution_rejects_invalid_matrices(self):
        for transition in (
            np.asarray([]),
            np.asarray([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]]),
            np.asarray([[1.0, float("nan")], [0.0, 1.0]]),
            np.asarray([[0.2, 0.2], [0.2, 0.2]]),
        ):
            with self.assertRaises(ValueError):
                stationary_distribution(transition)


if __name__ == "__main__":
    unittest.main()
