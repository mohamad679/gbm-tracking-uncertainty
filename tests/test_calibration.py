import unittest

from gbm_audit.calibration import temperature_transform


class TestCalibration(unittest.TestCase):
    def test_identity_temperature(self):
        self.assertAlmostEqual(temperature_transform(0.2, 1.0), 0.2, places=6)
        self.assertAlmostEqual(temperature_transform(0.8, 1.0), 0.8, places=6)

    def test_invalid_inputs_are_rejected(self):
        for probability in (-0.1, 1.1, float("nan")):
            with self.assertRaises(ValueError):
                temperature_transform(probability, 1.0)
        for temperature in (0.0, -1.0, float("inf")):
            with self.assertRaises(ValueError):
                temperature_transform(0.5, temperature)


if __name__ == "__main__":
    unittest.main()
