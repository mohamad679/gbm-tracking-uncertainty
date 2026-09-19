import unittest

from gbm_audit.adaptive_tuning_v3 import (
    LOCKED_ADAPTIVE_V3_CONFIG,
    POSTERIOR_PROBABILITY_FLOORS,
    config_id_v3,
    predefined_grid_v3,
)


class TestAdaptiveTuningV3(unittest.TestCase):
    def test_grid_is_deterministic_and_locked_config_is_in_grid(self):
        grid = predefined_grid_v3()
        self.assertEqual(len(grid), 375)
        self.assertEqual(grid, predefined_grid_v3())
        self.assertIn(LOCKED_ADAPTIVE_V3_CONFIG, grid)
        self.assertEqual(config_id_v3(LOCKED_ADAPTIVE_V3_CONFIG), "m2.75-d0-c4-n10-p0.7")

    def test_probability_floor_grid_is_predeclared(self):
        self.assertEqual(POSTERIOR_PROBABILITY_FLOORS, (0.3, 0.4, 0.5, 0.6, 0.7))


if __name__ == "__main__":
    unittest.main()
