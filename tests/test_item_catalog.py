import unittest

from companion.binary import tweakdbid_for_name
from companion.item_catalog import CatalogItem, _apply_display_name_overrides, load_catalog


class ItemAliasTests(unittest.TestCase):
    def test_sulimov_alias_is_available_without_external_catalog(self):
        by_tweakdb, by_id, info = load_catalog()
        item = by_id["Items.Preset_Warden_Boris"]
        self.assertEqual(item.name, "SULIMOV")
        self.assertEqual(item.catalog_name, "PIZDETS")
        self.assertEqual(item.name_source, "observed-game-ui-2.31-pl")
        self.assertIs(by_tweakdb[tweakdbid_for_name(item.id)], item)
        self.assertGreaterEqual(info["alias_overrides"], 3)

    def test_malorian_and_widow_maker_display_corrections(self):
        _, by_id, _ = load_catalog()
        self.assertEqual(by_id["Items.Preset_Silverhand_3516"].name, "MALORIAN ARMS 3516")
        self.assertEqual(by_id["Items.Preset_Achilles_Nash"].name, "WIDOW MAKER")

    def test_external_catalog_label_is_preserved_as_diagnostic_name(self):
        item_id = "Items.Preset_Warden_Boris"
        key = tweakdbid_for_name(item_id)
        original = CatalogItem(
            id=item_id, name="PIZDETS", subcategory="SMART SMG",
            category="WEAPONS", source="nightcity-console",
        )
        by_tweakdb = {key: original}
        by_id = {item_id: original}
        _apply_display_name_overrides(by_tweakdb, by_id)
        corrected = by_id[item_id]
        self.assertEqual(corrected.name, "SULIMOV")
        self.assertEqual(corrected.catalog_name, "PIZDETS")
        self.assertEqual(corrected.source, "nightcity-console")
        self.assertEqual(corrected.category, "WEAPONS")


if __name__ == "__main__":
    unittest.main()
