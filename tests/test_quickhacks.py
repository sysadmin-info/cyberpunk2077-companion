import unittest
from companion.binary import tweakdbid_for_name
from companion.item_catalog import load_catalog
from companion.quickhacks import identify, quickhacks_payload


def item(item_id, status='player', **extra):
    return dict(id=item_id, status=status, quantity=1, resolved=True, **extra)


class QuickhackEvidenceTests(unittest.TestCase):
    def test_program_and_recipe_are_distinct_and_other_is_not_owned(self):
        payload = quickhacks_payload({'inventory_containers_status': 'ok', 'inventory_records': [
            item('Items.ContagionLvl3Program', 'other'),
            item('Items.Recipe_ContagionLvl3Program'),
            item('Items.ContagionProgram', 'stash')]})
        self.assertEqual(payload['counts']['owned_program_variants'], 1)
        self.assertEqual(payload['counts']['owned_recipe_variants'], 1)
        group = payload['groups'][0]
        self.assertEqual(group['program_tiers'], [2])
        self.assertEqual(group['recipe_without_program_tiers'], [4])
        self.assertFalse(next(r for r in payload['records'] if r['location'] == 'other')['owned'])

    def test_tier_exceptions_and_iconic(self):
        for item_id, tier, iconic in [('Items.ContagionProgram',2,False),
                                    ('Items.EMPOverloadProgram',1,False),
                                    ('Items.MemoryWipeLvl3Program',4,False),
                                    ('Items.PingLvl2Program',3,False),
                                    ('Items.BlindLvl4PlusPlusProgram',5,True)]:
            with self.subTest(item_id=item_id):
                found = identify(item(item_id))
                self.assertEqual((found['tier'], found['iconic']), (tier, iconic))

    def test_unsupported_and_unknown_do_not_gain_a_tier(self):
        for row in [item('Items.MemoryWipeLvl1Program'), item('Items.NewHackLvl3Program'),
                    {'id': None, 'subcategory':'QUICKHACK', 'category':'CYBERWARE', 'tweakdb_value':123}]:
            with self.subTest(row=row):
                self.assertIsNone(identify(row)['tier'])
        self.assertIsNone(identify(item('Items.SuicideMaterial')))
        self.assertIsNone(identify({'resolved':False,'tweakdb_value':123}))

    def test_inventory_and_equipped_deck_never_imply_installed_programs(self):
        deck = {'area_type':'SystemReplacementCW','id':'Items.AdvancedMilitechParalineMKIIIRarePlus','name':'MILITECH PARALINE MK.3'}
        payload = quickhacks_payload({'equipped_cyberware':[deck], 'inventory_records':[
            item('Items.BlindLvl3Program')], 'inventory_containers_status':'partial'})
        self.assertEqual(payload['cyberdecks'], [deck])
        self.assertFalse(payload['ownership_scan_complete'])
        self.assertEqual(payload['installed_quickhacks']['slots'], [])
        self.assertEqual(payload['installed_quickhacks']['status'], 'not-resolved')

    def test_builtin_resolves_core_hashes_without_tsv(self):
        by_hash, _, _ = load_catalog()
        for item_id in ['Items.MemoryWipeLvl3Program','Items.Recipe_ContagionLvl3Program',
                        'Items.AdvancedMilitechParalineMK1CommonPlus',
                        'Items.AdvancedMilitechParalineMKIIIRarePlus']:
            self.assertEqual(by_hash[tweakdbid_for_name(item_id)].id, item_id)

    def test_empty_failed_parse_is_explicitly_partial(self):
        payload = quickhacks_payload({})
        self.assertFalse(payload['ownership_scan_complete'])
        self.assertEqual(payload['counts']['owned_program_variants'], 0)
