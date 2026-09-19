import math
import unittest

from gbm_audit.adaptive_candidates import AdaptiveCandidateConfig
from gbm_audit.adaptive_tuning_v2 import (
    MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16,
    _circle_union_area,
    config_id_v2,
    predefined_grid_v2,
    select_configuration_v2,
)


def _evaluated(config_id, passes=True, noise=1.0, clean=1.0, area=1.0):
    return {
        "config_id": config_id,
        "config": {},
        "metrics": {
            "development_pass": passes,
            "noise_sigma_5_soft_speed_error_px_per_frame": noise,
            "clean_soft_speed_error_px_per_frame": clean,
            "search_area_burden_px2_per_source": area,
        },
    }


class TestAdaptiveTuningV2(unittest.TestCase):
    def test_spatial_area_proxy_has_exact_circle_limits(self):
        self.assertAlmostEqual(_circle_union_area(8, 8, 0), math.pi * 64)
        self.assertAlmostEqual(_circle_union_area(8, 8, 20), math.pi * 128)
        self.assertGreater(_circle_union_area(8, 16, 10), math.pi * 16 ** 2)

    def test_grid_and_config_ids_are_deterministic(self):
        first = predefined_grid_v2()
        self.assertEqual(first, predefined_grid_v2())
        self.assertEqual(len(first), 75)
        self.assertEqual(config_id_v2(first[0]), "m2-d0-c4-n8")
        self.assertEqual(config_id_v2(first[-1]), "m3-d4-c4-n12")

    def test_spatial_gate_threshold_is_explicit(self):
        self.assertEqual(MIN_SPATIAL_AREA_REDUCTION_VS_FIXED_16, 0.15)
        self.assertTrue(AdaptiveCandidateConfig(new_track_score_px=9).validate() is None)

    def test_selection_requires_all_v2_gates(self):
        selected = select_configuration_v2([
            _evaluated("b", noise=0.8, clean=0.1, area=0.1),
            _evaluated("a", noise=0.5, clean=0.9, area=0.9),
            _evaluated("failed", passes=False, noise=0.0, clean=0.0, area=0.0),
        ])
        self.assertEqual(selected["config_id"], "a")
        self.assertIsNone(select_configuration_v2([_evaluated("x", passes=False)]))


if __name__ == "__main__":
    unittest.main()
