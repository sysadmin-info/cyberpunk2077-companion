"""Selection and HTTP regression using optional private saves."""
import json
import os
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from companion.server import CompanionApp, Handler


@unittest.skipUnless(os.environ.get('CP2077_TEST_SAVE_ROOT'), 'Requires private save fixtures')
class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.app = CompanionApp(Path(os.environ['CP2077_TEST_SAVE_ROOT']))

    def test_selection_refresh_exports_and_return_to_auto(self):
        server = ThreadingHTTPServer(('127.0.0.1', 0), type('TestHandler', (Handler,), {'app': self.app}))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(path, payload=None):
            req = Request(f'http://127.0.0.1:{server.server_port}{path}',
                          data=json.dumps(payload).encode() if payload is not None else None,
                          headers={'Content-Type':'application/json', 'Origin':f'http://127.0.0.1:{server.server_port}', 'X-Companion-Token':self.app.session_token})
            with urlopen(req) as r:
                return r.read()
        try:
            initial = json.loads(request('/api/state'))
            self.assertEqual(initial['latest']['save_name'], 'ManualSave-661')
            request('/api/save-selection', {'save_name': 'ManualSave-660'})
            state = json.loads(request('/api/state'))
            self.assertEqual(state['latest']['save_name'], 'ManualSave-660')
            self.assertEqual(state['save_selection']['mode'], 'manual')
            self.assertEqual(state['history'][0]['save_name'], 'ManualSave-661')
            self.assertEqual(next(x['status'] for x in state['iconic_weapons']['records'] if x['id']=='byakko'), 'equipped')
            self.assertEqual(json.loads(request('/api/assistant-context.json'))['generated_from'], 'ManualSave-660')
            self.assertIn(b'ManualSave-660', request('/api/assistant-context.md'))
            self.assertEqual(request('/api/screenshot'), (self.app.save_root/state['latest']['save_id']/'screenshot.png').read_bytes())
            # Simulate new filesystem changes while the user has pinned a save.
            with patch.object(self.app, '_save_signature', return_value=('changed',)):
                self.assertEqual(self.app.state()['latest']['save_name'], 'ManualSave-660')
            with self.assertRaises(HTTPError) as exc:
                request('/api/save-selection', {'save_name': '../outside'})
            self.assertEqual(exc.exception.code, 400)
            self.assertEqual(self.app.selected_save, 'ManualSave-660')
            request('/api/save-selection', {'save_name': None})
            self.assertEqual(json.loads(request('/api/state'))['latest']['save_name'], 'ManualSave-661')
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_missing_selection_keeps_previous_and_deleted_save_does_not_fallback(self):
        self.app.select_save('ManualSave-660')
        with self.assertRaises(ValueError):
            self.app.select_save('does-not-exist')
        self.assertEqual(self.app.selected_save, 'ManualSave-660')
        with patch('companion.server.scan_saves', return_value=[]), patch.object(self.app, '_save_signature', return_value=('deleted',)):
            state = self.app.state()
            self.assertFalse(state['ok'])
            self.assertEqual(state['save_selection']['selected_save'], 'ManualSave-660')
            self.assertIsNone(state['save_selection']['active_save'])
        self.app.select_save(None)
        self.assertEqual(self.app.state()['latest']['save_name'], 'ManualSave-661')

    def test_invalid_input(self):
        for name in ('', '..', '../foo', 'a/b', 'a\\b', 123, {}, []):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.app.select_save(name)
