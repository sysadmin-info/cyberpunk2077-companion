import unittest
from types import SimpleNamespace

from companion.readiness import evaluate_reaper_readiness


def fake_save(**overrides):
    base = dict(
        attributes={"body": 18, "reflexes": 12, "technical_ability": 20, "cool": 20, "intelligence": 5},
        perk_trees=[
            {"name": "Body", "perks": [
                {"id": "Body_Central_Milestone_1", "name": "Painkiller", "rank": 1},
                {"id": "Body_Central_Milestone_3", "name": "Adrenaline Rush", "rank": 3},
            ]},
            {"name": "Reflexes", "perks": [
                {"id": "Reflexes_Central_Milestone_2", "name": "Dash", "rank": 2},
            ]},
            {"name": "Technical Ability", "perks": []},
        ],
        inventory_records=[
            {"id": "Items.AdvancedBloodPumpLegendary", "name": "Blood Pump", "status": "player", "quantity": 1},
            {"id": "Items.Preset_Zhuo_Eight_Star", "name": "Ba Xing Chong", "status": "player", "quantity": 1},
        ],
        resolved_binary_facts={"sq032_johnny_friend": 1},
        metadata_facts={},
    )
    base.update(overrides)
    return SimpleNamespace(**base)


class ReadinessTests(unittest.TestCase):
    def test_core_ready_with_dash_body_and_survival_perks(self):
        result = evaluate_reaper_readiness(fake_save())
        self.assertEqual(result["overall"], "READY")
        self.assertEqual(result["core_ready"], result["core_total"])

    def test_air_dash_is_recommended_not_core(self):
        result = evaluate_reaper_readiness(fake_save())
        air = next(x for x in result["checks"] if x["id"] == "perk_air_dash")
        self.assertEqual(air["importance"], "recommended")
        self.assertEqual(air["status"], "partial")
        self.assertEqual(result["overall"], "READY")

    def test_missing_adrenaline_breaks_core(self):
        save = fake_save(perk_trees=[
            {"name": "Body", "perks": [{"id": "Body_Central_Milestone_1", "name": "Painkiller", "rank": 1}]},
            {"name": "Reflexes", "perks": [{"id": "Reflexes_Central_Milestone_2", "name": "Dash", "rank": 2}]},
        ])
        result = evaluate_reaper_readiness(save)
        self.assertNotEqual(result["overall"], "READY")
        adrenaline = next(x for x in result["checks"] if x["id"] == "perk_adrenaline_rush")
        self.assertEqual(adrenaline["status"], "missing")

    def test_survivability_control_profile_uses_actual_equipped_cyberware(self):
        save = fake_save(
            equipped_cyberware=[
                {"id": "Items.AdvancedBloodPumpLegendaryPlusPlus", "name": "Blood Pump", "slot_label": "Circulatory System / slot 1"},
                {"id": "Items.AdvancedBiomonitorLegendaryPlusPlus", "name": "Biomonitor", "slot_label": "Circulatory System / slot 2"},
            ],
            equipped_weapons=[
                {"id": "Items.Legendary_Zhuo_Eight_Star", "name": "Ba Xing Chong", "slot_label": "Weapon 1"},
            ],
            player_stats={"health": {"max": 544.364, "current_percent": 100.0}, "saved_humanity_additive": 90.0},
        )
        result = evaluate_reaper_readiness(save)
        profile = next(x for x in result["combat_readiness"]["profiles"] if x["id"] == "survivability-control")
        self.assertEqual(profile["status"], "ready")
        weapon = next(x for x in result["checks"] if x["id"] == "weapon_package")
        self.assertEqual(weapon["status"], "ready")
        pump = next(x for x in result["checks"] if x["id"] == "cyberware_blood_pump")
        self.assertEqual(pump["status"], "ready")
        self.assertIn("Circulatory System", pump["value"])


if __name__ == "__main__":
    unittest.main()
