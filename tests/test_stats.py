import struct
import unittest

from companion.stats import _decode_modifier_buffer, fnv1a64


class StatsTests(unittest.TestCase):
    def _one(self, stat: str, value: float, mod_type: int = 0):
        marker = b"\x98gameConstantStatModifier"
        entry = marker + struct.pack("<QIf", fnv1a64(stat), mod_type, value)
        self.assertEqual(len(entry), 41)
        return _decode_modifier_buffer(struct.pack("<I", len(entry)) + entry)[0]

    def test_humanity_hash(self):
        self.assertEqual(fnv1a64("Humanity"), 0x86758571A1F9AC7A)

    def test_constant_humanity_modifier(self):
        row = self._one("Humanity", 12.5)
        self.assertEqual(row["stat"], "Humanity")
        self.assertEqual(row["modifier_type"], 0)
        self.assertEqual(row["modifier_type_name"], "Additive")
        self.assertAlmostEqual(row["value"], 12.5)

    def test_known_player_stat_hashes(self):
        self.assertEqual(self._one("Level", 57)["stat"], "Level")
        self.assertEqual(self._one("Strength", 20)["stat"], "Strength")
        self.assertEqual(self._one("Reflexes", 13)["stat"], "Reflexes")
        self.assertEqual(self._one("Health", 100)["stat"], "Health")
        self.assertEqual(self._one("MaxHealth", 100)["stat"], "MaxHealth")


if __name__ == "__main__":
    unittest.main()
