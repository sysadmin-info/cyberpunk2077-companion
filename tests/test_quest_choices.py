import unittest
from companion.quest_choices import choice_evidence, load_choices, quest_choices_payload


class DecisionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.spec = {'quest_ids':['sq026_04_hiromi'], 'chain_ids':['sq026']}

    def test_completed_chain_does_not_mean_completed_pisces(self):
        result = choice_evidence({'finished_quests':['sq026']},self.spec)
        self.assertEqual(result['status'], 'signal')
        self.assertEqual(result['outcome'], 'not-resolved')

    def test_exact_quest_and_path_boundary(self):
        self.assertEqual(choice_evidence({'finished_quests':['sq026_04_hiromi']},self.spec)['status'],'done')
        self.assertEqual(choice_evidence({'tracked_quest_entry':'quests/sq026_04_hiromi/meeting'},self.spec)['status'],'active')
        self.assertEqual(choice_evidence({'tracked_quest_entry':'quests/sq026_04_hiromi_other/meeting'},self.spec)['status'],'unknown')

    def test_absence_and_zero_facts_never_imply_availability(self):
        result = choice_evidence({'metadata_facts':{'sq026_active':0}},self.spec)
        self.assertEqual(result['status'],'unknown')
        self.assertNotIn('available',result)

    def test_fact_signal_keeps_name_and_value(self):
        result = choice_evidence({'resolved_binary_facts':{'sq026_maiko':2}},self.spec)
        self.assertEqual(result['status'],'signal')
        self.assertEqual(result['evidence'],['sq026_maiko=2'])
        self.assertEqual(result['outcome'],'not-resolved')

    def test_catalog_integrity_and_requested_cases(self):
        rows = load_choices()['records']
        self.assertEqual(len({r['id'] for r in rows}),len(rows))
        self.assertGreaterEqual(len(rows),20)
        for row in rows:
            with self.subTest(id=row['id']):
                self.assertTrue(row['hint'])
                self.assertGreaterEqual(len(row['branches']),2)
                self.assertTrue(row['sources'])
                self.assertTrue(all(s['url'].startswith('https://') for s in row['sources']))
                self.assertEqual(row['verification'],'source_checked')
        cases = {r['id']:r for r in rows}
        self.assertIn('nie opisuje odmiennych',cases['blue-moon']['notes'][0])
        self.assertIn('zablokowane',cases['joshua']['branches'][1]['delayed'])
        self.assertIn('Nomad',cases['anna-hamill']['branches'][0]['condition'])

    def test_payload_uses_only_selected_save_evidence(self):
        a = quest_choices_payload({'save_name':'a','finished_quests':['sq023_hit_order']})
        b = quest_choices_payload({'save_name':'b','finished_quests':[]})
        self.assertEqual(next(r for r in a['records'] if r['id']=='joshua')['save_evidence']['status'],'done')
        self.assertEqual(next(r for r in b['records'] if r['id']=='joshua')['save_evidence']['status'],'unknown')
