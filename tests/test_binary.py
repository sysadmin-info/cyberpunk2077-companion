import unittest

from companion.binary import fnv1a32, tweakdbid_for_name


class HashTests(unittest.TestCase):
    def test_fnv1a32_known_vector(self):
        self.assertEqual(fnv1a32("hello"), 0x4F9F2CAB)

    def test_fact_hash_is_stable(self):
        self.assertEqual(fnv1a32("q305_fact_songbird_dead"), fnv1a32("q305_fact_songbird_dead"))

    def test_tweakdbid_items_money(self):
        # CRC32("Items.money") == F5E188EC, textual byte length == 11.
        self.assertEqual(tweakdbid_for_name("Items.money"), 0x0000000BF5E188EC)

    def test_tweakdbid_casius_tattoo(self):
        # ManualSave-352 Hands / slot 1 serializes this legacy/base record.
        self.assertEqual(tweakdbid_for_name("Items.CasiusTattoo"), 0x00000012A93E60FD)


if __name__ == "__main__":
    unittest.main()
