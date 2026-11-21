import unittest
from types import SimpleNamespace

from companion.core import _player_stats_summary


class StatPoolsPublicSummaryTests(unittest.TestCase):
    def test_exports_all_persisted_player_pools_and_health_first(self):
        health = {
            "type": "Health",
            "stat": "Health",
            "max_value": 553.5638427734375,
            "current_value": 100.0,
            "custom_limit_value": None,
            "modification_delay": 1.0,
            "change_mode": "NonZero",
            "record_id": "0x00000020F319225A",
        }
        stale = {
            "type": "SandevistanCharge",
            "stat": "TimeDilationSandevistanDuration",
            "max_value": None,
            "current_value": None,
            "custom_limit_value": None,
            "modification_delay": None,
            "change_mode": None,
            "record_id": "0x0000002C5331BDFC",
        }
        binary = SimpleNamespace(
            stat_pools=SimpleNamespace(health=health, pools=(stale, health)),
            player_stats=None,
        )
        result = _player_stats_summary(binary)
        self.assertEqual(result["saved_stat_pool_count"], 2)
        self.assertEqual(result["saved_stat_pools"][0]["type"], "Health")
        self.assertTrue(result["saved_stat_pools"][0]["is_health"])
        self.assertEqual(result["saved_stat_pools"][1]["type"], "SandevistanCharge")
        self.assertAlmostEqual(result["health"]["max"], 553.564)
        self.assertEqual(result["health"]["status"], "exact")
        self.assertEqual(result["health"]["source"], "StatPoolsSystem")

    def test_missing_health_does_not_hide_other_pools(self):
        other = {
            "type": "SandevistanCharge",
            "stat": "TimeDilationSandevistanDuration",
            "max_value": None,
            "current_value": None,
            "custom_limit_value": None,
            "modification_delay": None,
            "change_mode": None,
            "record_id": "0x1",
        }
        binary = SimpleNamespace(
            stat_pools=SimpleNamespace(health=None, pools=(other,)),
            player_stats=None,
        )
        result = _player_stats_summary(binary)
        self.assertIsNone(result["health"]["max"])
        self.assertEqual(result["health"]["status"], "not-persisted")
        self.assertIsNone(result["health"]["source"])
        self.assertIn("does not persist", result["health"]["note"])
        self.assertEqual(result["saved_stat_pool_count"], 1)
        self.assertEqual(result["saved_stat_pools"][0]["type"], "SandevistanCharge")


if __name__ == "__main__":
    unittest.main()
