"""Optional real-save checks; private saves are never distributed."""
import os
from collections import Counter
from dataclasses import asdict
from pathlib import Path
import unittest

from companion.binary import parse_sav_dat, tweakdbid_for_name
from companion.core import load_save, assistant_context, assistant_context_markdown, build_state
from companion.iconic_weapons import build_iconic_payload


@unittest.skipUnless(os.environ.get('CP2077_TEST_SAVE_ROOT'), 'Set CP2077_TEST_SAVE_ROOT for real-save regression')
class SaveRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(os.environ['CP2077_TEST_SAVE_ROOT'])
        cls.registry = Path(__file__).parents[1] / 'data' / 'iconic_weapons.json'
        cls.saves = {n: load_save(cls.root / f'ManualSave-{n}') for n in (660, 661)}

    def test_byakko_moves_and_sixty_unique_models_remain_owned(self):
        for n, expected in ((660, 'equipped'), (661, 'stash')):
            s = self.saves[n]
            self.assertEqual(s.inventory_containers_status, 'ok')
            payload = build_iconic_payload(asdict(s), self.registry)
            self.assertEqual(payload['counts']['owned'], 60)
            self.assertEqual(payload['counts']['stash'], 57 if n == 660 else 58)
            self.assertEqual(next(x for x in payload['records'] if x['id']=='byakko')['status'], expected)
            self.assertEqual(next(x for x in payload['records'] if x['id']=='skippy')['status'], 'equipped')

    def test_container_record_counts(self):
        for n, player, stash in ((660, 736, 3042), (661, 735, 3043)):
            b = parse_sav_dat(self.root / f'ManualSave-{n}' / 'sav.dat')
            counts = Counter(x.storage_id for x in b.all_item_records)
            self.assertEqual(counts[1], player)
            self.assertEqual(counts[1000000], stash)
            target = tweakdbid_for_name('Items.Preset_Katana_Wakako')
            self.assertEqual([x.storage_id for x in b.all_item_records if x.tweakdb_value==target], [1 if n==660 else 1000000])

    def test_exports_include_stash_and_iconic(self):
        state = build_state([self.saves[661]])
        state['iconic_weapons'] = build_iconic_payload(state['latest'], self.registry)
        ctx = assistant_context(state)
        self.assertTrue(ctx['inventory']['stash_items'])
        md = assistant_context_markdown(ctx)
        self.assertIn('[stash] Byakko', md)
        self.assertIn('[equipped] SKIPPY', md)
        self.assertIn('Professional Widow', md)
        self.assertIn('mapgenie.io/cyberpunk-2077/maps/night-city?locationIds=', md)
        self.assertIn('source_checked', md)
        self.assertIn('source_checked', md)
        self.assertNotIn('Weryfikacja opisu: needs_verification', md)
        self.assertEqual(ctx['iconic_weapons']['guide_counts']['source_checked'], 112)
