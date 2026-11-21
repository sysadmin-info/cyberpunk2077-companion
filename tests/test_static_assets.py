"""Regression for an installation that reads saves but lacks app.js."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import contextlib
import io
import shutil
import tempfile
import threading
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

import cp2077_companion
from companion import __version__
from companion.server import Handler, validate_static_assets


STATIC = Path(__file__).resolve().parent.parent / "companion" / "static"


class StaticAssetTests(unittest.TestCase):
    def test_release_has_required_ui_files(self):
        validate_static_assets(STATIC)

    def test_missing_and_empty_script_report_exact_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "static"
            shutil.copytree(STATIC, root)
            script = root / "app.js"
            script.unlink()
            for state in ("missing", "empty"):
                with self.subTest(state=state), self.assertRaises(FileNotFoundError) as error:
                    validate_static_assets(root)
                self.assertIn(str(script.resolve()), str(error.exception))
                self.assertIn("Extract the complete ZIP", str(error.exception))
                script.write_bytes(b"")

    def test_startup_stops_before_save_scan_if_ui_is_missing(self):
        with patch.object(cp2077_companion, "validate_static_assets", side_effect=FileNotFoundError("missing app.js")), \
                patch.object(cp2077_companion, "write_exports") as exports, \
                patch("sys.argv", ["cp2077_companion.py", "--no-open"]), \
                contextlib.redirect_stderr(io.StringIO()) as errors:
            self.assertEqual(cp2077_companion.main(), 2)
        exports.assert_not_called()
        self.assertIn("missing app.js", errors.getvalue())

    def test_http_serves_script_and_reproduces_404_after_removal(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "static"
            shutil.copytree(STATIC, root)
            app = SimpleNamespace(static_dir=root)
            handler = type("AssetHandler", (Handler,), {"app": app, "log_message": lambda *_: None})
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            script_path = f"/app.js?v={__version__}"
            try:
                with urlopen(base + "/") as response:
                    self.assertIn(script_path.encode(), response.read())
                with urlopen(base + script_path) as response:
                    self.assertEqual(response.read(), (root / "app.js").read_bytes())
                    self.assertIn("javascript", response.headers["Content-Type"])
                (root / "app.js").unlink()
                with self.assertRaises(HTTPError) as error:
                    urlopen(base + script_path)
                self.assertEqual(error.exception.code, 404)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
