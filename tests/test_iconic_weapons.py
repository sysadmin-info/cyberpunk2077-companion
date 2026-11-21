from pathlib import Path
import json
import tempfile
import unittest

from companion.binary import tweakdbid_for_name
from companion.iconic_weapons import IconicWeaponDataError, build_iconic_payload, load_iconic_registry


class IconicWeaponsTests(unittest.TestCase):
    def setUp(self):
        self.registry = Path(__file__).parents[1] / "data" / "iconic_weapons.json"

    def test_registry_is_valid_and_has_aliases(self):
        rows = load_iconic_registry(self.registry)
        self.assertGreaterEqual(len(rows), 13)
        breakthrough = next(x for x in rows if x["id"] == "breakthrough")
        self.assertIn("Items.Epic_Nekomata_Breakthrough", breakthrough["tweakdb_ids"])

    def test_matcher_prefers_equipped_over_inventory_and_other(self):
        state = {
            "binary_parser_status": "ok",
            "inventory_containers_status": "ok",
            "equipment_status": "ok",
            "equipped_weapons": [{"id": "Items.Preset_Silverhand_3516"}],
            "inventory_records": [
                {"id": "Items.Preset_Silverhand_3516", "status": "other"},
                {"id": "Items.Preset_Achilles_Nash", "status": "player"},
                {"id": "Items.Preset_Grad_Panam", "status": "other"},
            ],
        }
        payload = build_iconic_payload(state, self.registry)
        by_id = {x["id"]: x for x in payload["records"]}
        self.assertEqual(by_id["malorian-arms-3516"]["status"], "equipped")
        self.assertEqual(by_id["widow-maker"]["status"], "inventory")
        self.assertEqual(by_id["overwatch"]["status"], "other")
        self.assertFalse(by_id["overwatch"]["owned"])
        self.assertEqual(by_id["pride"]["status"], "missing")

    def test_matcher_uses_raw_tweakdb_value_without_catalog_name(self):
        value = f"{tweakdbid_for_name('Items.Preset_Zhuo_Eight_Star'):016X}"
        payload = build_iconic_payload({"equipped_weapons": [], "inventory_records": [{"id": None, "tweakdb_value": value, "status": "player"}]}, self.registry)
        row = next(x for x in payload["records"] if x["id"] == "ba-xing-chong")
        self.assertEqual(row["status"], "inventory")

    def test_invalid_registry_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.json"
            path.write_text(json.dumps({"weapons": [{"id": "broken"}]}), encoding="utf-8")
            with self.assertRaises(IconicWeaponDataError):
                load_iconic_registry(path)

    def test_stash_duplicates_count_one_model_and_keep_locations(self):
        payload = build_iconic_payload({"inventory_records": [
            {"id": "Items.Preset_Liberty_Rogue", "status": "stash"},
            {"id": "Items.Preset_Liberty_Rogue_Stash", "status": "stash"},
            {"id": "Items.Preset_Liberty_Rogue", "status": "player"},
        ]}, self.registry)
        row = next(x for x in payload['records'] if x['id'] == 'pride')
        self.assertTrue(row['owned'])
        self.assertEqual(row['status'], 'inventory')
        self.assertEqual(row['locations'], ['inventory', 'stash'])
        self.assertEqual(payload['counts']['owned'], 1)

    def test_parser_failure_is_not_absence(self):
        payload = build_iconic_payload({}, self.registry)
        self.assertEqual(payload['counts']['missing'], 0)
        self.assertEqual(payload['counts']['unknown'], payload['counts']['total'])

    def test_recipe_and_display_name_do_not_match_weapon(self):
        payload = build_iconic_payload({'inventory_records': [
            {'id': 'Items.Recipe_Preset_Borg4a_HauntedGun', 'name': 'EREBUS', 'status': 'stash'},
        ]}, self.registry)
        self.assertEqual(payload['counts']['owned'], 0)

    def test_actual_crafted_and_boss_weapon_ids_are_recognized(self):
        payload = build_iconic_payload({
            'binary_parser_status': 'ok', 'inventory_containers_status': 'ok',
            'equipment_status': 'ok', 'inventory_records': [
                {'id': 'Items.Legendary_Copperhead_Genesis', 'status': 'stash'},
                {'id': 'Items.Legendary_Burya_Comrade', 'status': 'stash'},
                {'id': 'Items.w_melee_boss_hammer', 'status': 'stash'},
                {'id': 'Items.Preset_Hammer_Default', 'status': 'stash'},
            ],
        }, self.registry)
        rows = {row['id']: row for row in payload['records']}
        for key in ('psalm-116', 'comrades-hammer', 'sasquatchs-hammer'):
            self.assertEqual(rows[key]['status'], 'stash', key)
        self.assertEqual(payload['counts']['owned'], 3)
        self.assertEqual(payload['counts']['total'], 112)
        self.assertFalse(any('Items.Preset_Hammer_Default' in row['tweakdb_ids'] for row in rows.values()))

    def test_registry_has_no_alias_shared_by_two_models(self):
        seen = set()
        for row in load_iconic_registry(self.registry):
            self.assertFalse(seen.intersection(row['tweakdb_ids']), row['id'])
            seen.update(row['tweakdb_ids'])

    def test_expanded_models_are_matched_not_hardcoded_missing(self):
        state = {'binary_parser_status': 'ok', 'inventory_containers_status': 'ok',
                 'equipment_status': 'ok', 'inventory_records': [
            {'tweakdb_value': f"{tweakdbid_for_name('Items.Preset_Ticon_Reed'):016X}", 'status': 'stash'},
            {'id': 'Items.Preset_Kenshin_Royce', 'status': 'player'},
            {'id': 'Items.Recipe_Preset_Pulsar_Buzzsaw', 'status': 'player'},
            {'id': 'Items.Preset_Warden_Boris_Hologram', 'status': 'player'},
            {'id': 'Items.Preset_RocketLauncher_Test', 'status': 'player'},
        ]}
        payload = build_iconic_payload(state, self.registry)
        rows = {r['id']: r for r in payload['records']}
        self.assertEqual(payload['counts']['total'], 112)
        self.assertEqual(payload['counts']['owned'], 2)
        self.assertEqual(rows['pariah']['status'], 'stash')
        self.assertEqual(rows['chaos']['status'], 'inventory')
        for key in ('buzzsaw', 'sulimov', 'ofive'):
            self.assertEqual(rows[key]['status'], 'missing')
        self.assertIn('special_reward', rows['yasha']['collection_tags'])
        self.assertIn('story_choice', rows['pariah']['collection_tags'])

    def test_availability_class_is_separate_from_save_status(self):
        payload = build_iconic_payload({'binary_parser_status': 'ok',
            'inventory_containers_status': 'ok', 'equipment_status': 'ok',
            'inventory_records': []}, self.registry)
        rows = {r['id']: r for r in payload['records']}
        self.assertEqual(rows['pariah']['status'], 'missing')
        self.assertEqual(rows['pariah']['availability_class'], 'decision_dependent')
        self.assertEqual(rows['yasha']['availability_class'], 'unknown')
        self.assertEqual(rows['volkodav']['availability_class'], 'unknown')
        for weapon in ('satori', 'nehan', 'kongou', 'errata', 'hawk'):
            self.assertEqual(rows[weapon]['availability_class'], 'unknown', weapon)
        self.assertEqual(rows['gwynbleidd']['availability_class'], 'account_or_promo')
        self.assertNotIn('generally_available', {r['availability_class'] for r in rows.values()})


if __name__ == "__main__":
    unittest.main()
