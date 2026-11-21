import struct
import unittest
from companion.binary import NodeInfo
from companion.inventory_containers import decode_containers


class ContainerTests(unittest.TestCase):
    def fixture(self):
        identity = struct.pack('<QII', 0x1A97612D07, 1812748997, 0)
        item = struct.pack('<I', 1) + identity
        payload = struct.pack('<IIQI', 0, 2, 1, 0)
        payload += struct.pack('<QI', 1000000, 1) + identity + item
        nodes = [NodeInfo('inventory', None, 1, 100, len(payload)),
                 NodeInfo('itemData', None, None, 148, len(item))]
        return payload, nodes

    def test_empty_player_followed_by_stash(self):
        data, nodes = self.fixture()
        out = decode_containers(data, 0, nodes, 100)
        self.assertEqual(out[1], [])
        self.assertEqual(out[1000000][0][0], 1)

    def test_truncation_and_extra_bytes_are_rejected(self):
        data, nodes = self.fixture()
        for corrupted in (data[:-1], data + b'X', data[:10]):
            with self.assertRaises(ValueError):
                decode_containers(corrupted, 0, nodes, 100)

    def test_wrong_identity_and_boundary_are_rejected(self):
        data, nodes = self.fixture()
        bad = bytearray(data)
        bad[32] ^= 1
        with self.assertRaises(ValueError):
            decode_containers(bad, 0, nodes, 100)
        with self.assertRaises(ValueError):
            decode_containers(data, 0, nodes, 101)
