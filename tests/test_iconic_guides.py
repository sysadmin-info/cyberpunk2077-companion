import copy
import unittest
from pathlib import Path
from companion.iconic_weapons import load_iconic_registry, validate_guide, IconicWeaponDataError, build_iconic_payload


class GuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = Path(__file__).parents[1] / 'data/iconic_weapons.json'
        cls.rows = load_iconic_registry(cls.path)
        cls.by_id = {w['id']: w for w in cls.rows}

    def test_coverage_is_explicit(self):
        payload = build_iconic_payload({}, self.path)
        self.assertEqual(payload['guide_counts'], {'source_checked':112, 'needs_verification':0, 'with_map':46})
        self.assertEqual(len(self.rows), 112)

    def test_each_guide_is_valid_and_availability_not_assumed(self):
        for w in self.rows:
            with self.subTest(weapon=w['id']):
                validate_guide(w['guide'])
                self.assertEqual(w['guide']['availability'], 'not_evaluated')
                if w['guide']['verification'] == 'needs_verification':
                    self.assertFalse(w['guide']['sources'])
                    self.assertFalse(w['guide']['map_links'])
                    self.assertIn('weryfikację', w['acquisition'])

    def test_multiple_locations_and_account_reward(self):
        self.assertEqual(len(self.by_id['genjiroh']['guide']['map_links']), 2)
        self.assertEqual(self.by_id['black-unicorn']['guide']['map_links'], [])
        self.assertEqual(self.by_id['guts-carnage']['guide']['fast_travel'], 'Arasaka Tower')
        self.assertEqual(self.by_id['breakthrough']['guide']['method'], 'crafting')

    def test_unsafe_links_rejected(self):
        for url in ('javascript:alert(1)', 'http://example.com/', '//example.com/', 'https://a:b@example.com/', 'https://example.com/a b'):
            g = copy.deepcopy(self.rows[0]['guide'])
            g['sources'][0]['url'] = url
            with self.subTest(url=url), self.assertRaises(IconicWeaponDataError):
                validate_guide(g)

    def test_new_guides_keep_quest_conditions_and_markers(self):
        self.assertEqual(self.by_id['hawk']['guide']['quest'], 'Lucretia My Reflection')
        self.assertIn('Reeda', self.by_id['fang']['guide']['conditions'])
        self.assertEqual(self.by_id['comrades-hammer']['guide']['method'], 'crafting')
        self.assertTrue(self.by_id['errata']['guide']['map_links'][0]['url'].endswith('marker-id=4902'))
        self.assertEqual(self.by_id['erebus']['guide']['verification'], 'source_checked')
        self.assertEqual(self.by_id['erebus']['guide']['method'], 'crafting')
        self.assertIn('941229', self.by_id['rook']['acquisition'] + self.by_id['rook']['guide']['conditions'])
        self.assertIn('Relacja użytkownika', self.by_id['ndi-osprey']['guide']['conditions'])

    def test_checked_status_requires_source(self):
        g = copy.deepcopy(self.rows[0]['guide'])
        g['sources'] = []
        with self.assertRaises(IconicWeaponDataError):
            validate_guide(g)
