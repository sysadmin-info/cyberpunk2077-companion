"""Offline release boundaries, normal backup workflows and local user data."""

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
import json
import struct
import threading
import os
import shutil

from cp2077_companion import write_exports
from companion import catalog_fetch, item_catalog, binary
from companion.core import scan_saves, build_state
from companion.hidden_encounters import (
    import_legacy,
    set_user_status,
    load_user_statuses,
)
from companion.i18n import localize_state
from companion.server import CompanionApp, Handler, normalize_host
from companion.localio import read_limited, require_local_root

DATA = Path(__file__).resolve().parents[1] / "data" / "hidden_encounters.json"


class ReleaseTests(TestCase):
    def test_parser_budget_for_an_ordinary_literal(self):
        plain = b"item"
        block = (
            b"4ZLX" + struct.pack("<I", len(plain)) + bytes([len(plain) << 4]) + plain
        )
        self.assertEqual(plain, binary._decompress_lz4_chunk(block, len(plain)))
        with (
            patch.object(binary, "BLOCK_LIMIT", 3),
            self.assertRaises(binary.SaveFormatError),
        ):
            binary._decompress_lz4_chunk(block, len(plain))
        with TemporaryDirectory() as tmp:
            f = Path(tmp) / "example.txt"
            f.write_bytes(plain)
            with self.assertRaises(ValueError):
                read_limited(f, 3)

    def test_catalog_is_installed_only_after_full_verification(self):
        with TemporaryDirectory() as tmp:
            dest = Path(tmp) / "items.tsv"
            expected = b"Items.money\tEurodollars\tMONEY\tMISC\n"
            with (
                patch.object(catalog_fetch, "SIZE", len(expected)),
                patch.object(catalog_fetch, "SHA256", sha256(expected).hexdigest()),
            ):
                catalog_fetch.install_stream(BytesIO(expected), dest)
                for other in (b"", expected.replace(b"MISC", b"ITEM"), expected + b" "):
                    with self.subTest(size=len(other)), self.assertRaises(ValueError):
                        catalog_fetch.install_stream(BytesIO(other), dest)
                    self.assertEqual(dest.read_bytes(), expected)
                self.assertEqual([dest], list(dest.parent.iterdir()))

    def test_existing_unverified_tsv_is_ignored(self):
        with (
            TemporaryDirectory() as tmp,
            patch.object(item_catalog, "CATALOG_PATH", Path(tmp) / "items.tsv"),
        ):
            item_catalog.CATALOG_PATH.write_text(
                "Items.Example\tExample", encoding="utf8"
            )
            item_catalog._load_catalog_cached.cache_clear()
            try:
                _, ids, info = item_catalog.load_catalog()
                self.assertNotIn("Items.Example", ids)
                self.assertEqual(info["verification"], "unverified")
                self.assertNotIn("path", info)
            finally:
                item_catalog._load_catalog_cached.cache_clear()

    def test_saves_with_repeated_labels_select_by_directory(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i, label in enumerate(("A", "B"), 1):
                d = root / label
                d.mkdir()
                (d / "metadata.9.json").write_text(
                    json.dumps(
                        {
                            "Data": {
                                "metadata": {
                                    "name": "My backup",
                                    "level": i,
                                    "timestampString": f"11:00:00, 0{i}.11.2026",
                                }
                            }
                        }
                    )
                )
            bad = root / "Incomplete"
            bad.mkdir()
            (bad / "metadata.9.json").write_text(
                json.dumps({"Data": {"metadata": {"level": "not ready"}}})
            )
            warnings = []
            s = scan_saves(root, selected_save="A", warnings=warnings)
            self.assertEqual(["Incomplete"], warnings)
            state = build_state(s, selected_save="A")
            self.assertEqual(
                (
                    state["latest"]["save_name"],
                    state["latest"]["save_id"],
                    state["latest"]["level"],
                ),
                ("My backup", "A", 1),
            )
            self.assertEqual(build_state(s, selected_save="B")["latest"]["level"], 2)
            self.assertFalse(build_state(s, selected_save="My backup")["ok"])

    def test_per_playthrough_transactions_and_explicit_legacy_import(self):
        ids = ["stadium-love-holster-first", "only-pain-talk-before-fight"]
        with TemporaryDirectory() as tmp:
            db = Path(tmp) / "encounters.sqlite3"
            old = db.with_name("hidden_encounters_status.json")
            old.write_text(
                json.dumps({"statuses": {ids[0]: "discovered", ids[1]: "discovered"}})
            )
            self.assertEqual(load_user_statuses(db, "nomad"), {})
            with ThreadPoolExecutor(2) as pool:
                list(
                    pool.map(
                        lambda i: set_user_status(i, "completed", DATA, db, "corpo"),
                        ids,
                    )
                )
            self.assertEqual(
                load_user_statuses(db, "corpo"), dict.fromkeys(ids, "completed")
            )
            self.assertEqual(import_legacy(db, "corpo", set(ids)), 0)
            self.assertEqual(import_legacy(db, "nomad", set(ids)), 2)
            self.assertEqual(import_legacy(db, "nomad", set(ids)), 0)
            self.assertEqual(
                load_user_statuses(db, "nomad"), dict.fromkeys(ids, "discovered")
            )
            self.assertTrue(old.is_file())

    def test_local_binding_and_session_contract(self):
        self.assertEqual(normalize_host("localhost"), "127.0.0.1")
        self.assertEqual(normalize_host("::1"), "::1")
        for name in ("0.0.0.0", "192.0.2.1", "::"):
            with self.subTest(host=name), self.assertRaises(ValueError):
                normalize_host(name)
        with self.assertRaises(ValueError):
            require_local_root(Path("//example.invalid/shared"))
        with TemporaryDirectory() as tmp:
            app = CompanionApp(Path(tmp))
            server = ThreadingHTTPServer(
                ("127.0.0.1", 0),
                type(
                    "TestHandler",
                    (Handler,),
                    {"app": app, "log_message": lambda *_: None},
                ),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                with urlopen(base + "/api/health") as r:
                    self.assertEqual(json.load(r), {"ok": True})
                with urlopen(base + "/api/session") as r:
                    self.assertEqual(json.load(r)["token"], app.session_token)
                with self.assertRaises(HTTPError) as exc:
                    urlopen(
                        Request(
                            base + "/api/save-selection",
                            data=b"{}",
                            headers={
                                "Origin": base,
                                "Content-Type": "application/json",
                            },
                        )
                    )
                self.assertEqual(exc.exception.code, 403)
                with self.assertRaises(HTTPError) as exc:
                    urlopen(
                        Request(
                            base + "/api/save-selection",
                            data=b"{}",
                            headers={
                                "Origin": base,
                                "X-Companion-Token": app.session_token,
                                "Content-Type": "text/plain",
                            },
                        )
                    )
                self.assertEqual(exc.exception.code, 415)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_missing_data_keeps_last_export_and_does_not_write_to_saves(self):
        with TemporaryDirectory() as tmp:
            saves = Path(tmp) / "saves"
            saves.mkdir()
            dest = Path(tmp) / "exports"
            dest.mkdir()
            previous = dest / "state.json"
            previous.write_text("previous")
            with self.assertRaises(ValueError):
                write_exports(CompanionApp(saves), dest)
            self.assertEqual(previous.read_text(), "previous")
            self.assertEqual(list(saves.iterdir()), [])

    def test_release_language_catalogs_and_guide_coverage(self):
        root = DATA.parents[1]
        ui = [
            json.loads((root / f"locales/ui.{lang}.json").read_text("utf8"))
            for lang in ("pl", "en")
        ]
        self.assertEqual(ui[0].keys(), ui[1].keys())
        raw = json.loads((root / "data/iconic_weapons.json").read_text("utf8"))[
            "weapons"
        ]
        state = {"ok": True, "latest": {}, "iconic_weapons": {"records": raw}}
        english = localize_state(state, "en")["iconic_weapons"]["records"]
        self.assertTrue(
            all(
                a["id"] == b["id"]
                and a["acquisition"] != b["acquisition"]
                and a["tweakdb_ids"] == b["tweakdb_ids"]
                for a, b in zip(raw, english)
            )
        )
        self.assertEqual(
            raw[0]["guide"]["sources"][0]["url"],
            english[0]["guide"]["sources"][0]["url"],
        )
        choices = json.loads((root / "data/quest_choices.json").read_text("utf8"))[
            "records"
        ]
        translated = localize_state(
            {"ok": True, "latest": {}, "quest_choices": {"records": choices}}, "en"
        )["quest_choices"]["records"]
        for a, b in zip(choices, translated):
            self.assertNotEqual(a["hint"], b["hint"])
            for x, y in zip(a["branches"], b["branches"]):
                self.assertNotEqual(x["action"], y["action"])

    def test_real_backup_cli_without_network(self):
        root = os.environ.get("CP2077_TEST_SAVE_ROOT")
        if not root:
            self.skipTest("requires the two real fixtures")
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "saves"
            copy = src / "Restored-661"
            shutil.copytree(Path(root) / "ManualSave-661", copy)
            before = {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in copy.iterdir()
                if p.is_file()
            }
            with patch(
                "socket.socket.connect",
                side_effect=AssertionError("unexpected network access"),
            ):
                app = CompanionApp(src)
                app.select_save(copy.name)
                self.assertEqual(app.state()["latest"]["binary_parser_status"], "ok")
                with self.assertRaises(ValueError):
                    write_exports(app, src / "exports")
                snap = write_exports(app, Path(tmp) / "exports")
                self.assertEqual(
                    {p.name for p in snap.iterdir()},
                    {"state.json", "assistant-context.json", "assistant-context.md"},
                )
                for f in snap.iterdir():
                    self.assertNotIn(str(Path(tmp)), f.read_text("utf8"))
            after = {
                p.name: sha256(p.read_bytes()).hexdigest()
                for p in copy.iterdir()
                if p.is_file()
            }
            self.assertEqual(before, after)

    def test_in_progress_save_preserves_only_same_slot_and_refuses_export(self):
        root = os.environ.get("CP2077_TEST_SAVE_ROOT")
        if not root:
            self.skipTest("requires a real save fixture")
        with TemporaryDirectory() as tmp:
            src = Path(tmp) / "saves"
            slot = src / "Restored"
            shutil.copytree(Path(root) / "ManualSave-661", slot)
            app = CompanionApp(src)
            app.select_save(slot.name)
            initial = app.state()
            self.assertEqual(initial["latest"]["binary_parser_status"], "ok")
            saved = slot / "sav.dat"
            staging = slot / "sav.pending"
            saved.rename(staging)
            old = app.state()
            self.assertTrue(old["scan_stale"])
            self.assertEqual(old["latest"]["save_id"], slot.name)
            self.assertEqual(
                old["latest"]["inventory_records"],
                initial["latest"]["inventory_records"],
            )
            with self.assertRaises(ValueError):
                write_exports(app, Path(tmp) / "exports")
            self.assertFalse((Path(tmp) / "exports").exists())
            with self.assertRaises(ValueError):
                app.mark("/api/hidden-encounters/status", {})
            staging.rename(saved)
            self.assertFalse(app.state().get("scan_stale"))
            self.assertEqual(app.state()["latest"]["binary_parser_status"], "ok")
            shutil.rmtree(slot)
            self.assertFalse(app.state()["ok"])

    def test_nested_network_mount_skipped_in_local_tree(self):
        from companion import localio

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            remote = base / "shared"
            remote.mkdir()
            sample = remote / "note.txt"
            sample.write_text("example")
            with (
                patch.object(localio, "_remote_mounts", return_value=(remote,)),
                localio.local_read_scope(),
            ):
                self.assertEqual(localio.require_local_root(base), base)
                self.assertFalse(localio.regular_local(remote, directory=True))
                with self.assertRaises(ValueError):
                    localio.read_limited(sample, 100)
                with self.assertRaises(ValueError):
                    localio.require_local_root(base / "other" / ".." / "shared")
