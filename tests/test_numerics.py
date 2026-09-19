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

    def test_stationary_distribution(self):
        transition = np.asarray([[0.9, 0.1], [0.2, 0.8]])
        stationary = stationary_distribution(transition)
        np.testing.assert_allclose(stationary @ transition, stationary, atol=1e-10)
        self.assertAlmostEqual(float(stationary.sum()), 1.0)


if __name__ == "__main__":
    unittest.main()
