"""Firestarter is a route decision, not a generic quest-complete flag."""

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from companion.core import find_firestarter_saves
from companion.firestarter import classify
from companion.i18n import localize_state
from companion.localio import local_read_scope
from companion.quest_choices import quest_choices_payload
from companion.server import CompanionApp


def write_slot(root, slot, stamp, facts=(), finished="", profile="example-A", dat=True):
    folder = root / slot
    folder.mkdir()
    meta = {
        "playthroughID": profile,
        "timestampString": stamp,
        "name": "Repeated game label",
        "facts": list(facts),
        "finishedQuests": finished,
    }
    (folder / "metadata.9.json").write_text(
        json.dumps({"Data": {"metadata": meta}}), encoding="utf8"
    )
    if dat:
        (folder / "sav.dat").write_bytes(b"metadata-only test fixture")
    return folder


def search(root, profile="example-A"):
    with local_read_scope():
        return find_firestarter_saves(root, profile)


class RouteDecisionTests(unittest.TestCase):
    def test_routes_require_positive_exact_markers(self):
        cases = [
            ({"q304_songbirds_path": 1}, [], "", "songbird"),
            ({"q304_songbirds_path": 0}, [], "", "unknown"),
            ({"q304_done": 1, "q304_kurt_dead": 1}, [], "", "past"),
            ({"q304_kurt_dead": 1, "q304_active": 1}, [], "", "signal"),
            ({"q304_stadium_escape_active": 1, "q304_active": 1}, [], "", "signal"),
            ({"q304_started": 1, "q304_active": 1}, [], "", "candidate"),
            ({"q304_started": 1}, [], "", "signal"),
            ({"q304_active": 0}, [], "journal/q304/objective", "unknown"),
            (
                {"mq305_active": 1},
                ["mq306", "q306_extra"],
                "journal/mq305/objective",
                "unknown",
            ),
            ({}, ["q304"], "", "past"),
            ({}, ["q305"], "", "reed"),
            ({}, ["q306"], "", "songbird"),
            ({"q305_started": 1}, [], "", "reed"),
            ({}, [], "journal/q306/objective", "songbird"),
            ({"q304_songbirds_path": 1}, ["q305"], "", "conflict"),
        ]
        for facts, finished, tracked, want in cases:
            with self.subTest(facts=facts, finished=finished, tracked=tracked):
                self.assertEqual(classify(facts, finished, tracked)[0], want)
        self.assertEqual(
            classify({"q304_songbirds_path": 0}, [], binary={"q304_songbirds_path": 1})[
                0
            ],
            "conflict",
        )

    def test_card_localization_and_raw_proof_are_separate(self):
        state = {
            "ok": True,
            "latest": {},
            "quest_choices": quest_choices_payload(
                {
                    "metadata_facts": {"q304_songbirds_path": 1},
                    "finished_quests": ["q304"],
                }
            ),
        }
        for lang, branch, consequence in (
            ("pl", "Ścieżka Songbird", "Cierniach i gwiazdach"),
            ("en", "Songbird route", "The Killing Moon"),
        ):
            row = next(
                x
                for x in localize_state(state, lang)["quest_choices"]["records"]
                if x["id"] == "firestarter"
            )
            self.assertEqual(row["save_evidence"]["outcome"], "songbird")
            self.assertIn(branch, row["save_evidence"]["label"])
            self.assertEqual(
                row["save_evidence"]["evidence"], ["q304_songbirds_path=1"]
            )
            self.assertIn(consequence, row["branches"][0]["delayed"])
            self.assertIn("Cerber", row["branches"][1]["delayed"])

    def test_windows_types_order_duplicate_names_and_own_profile(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            write_slot(p, "ManualSave-90", "10:00:00, 10.01.2026", ["q304_active=1"])
            write_slot(p, "AutoSave-2", "10:01:00, 10.01.2026", ["q304_active=1"])
            write_slot(
                p, "AutoSave-1", "10:02:00, 10.01.2026", ["q304_songbirds_path=1"]
            )
            write_slot(p, "ManualSave-1", "10:04:00, 10.01.2026", finished="q304 q306")
            write_slot(
                p,
                "Unrelated",
                "10:05:00, 10.01.2026",
                ["q304_active=1"],
                profile="example-B",
            )
            write_slot(
                p, "NoData", "10:06:00, 10.01.2026", ["q304_active=1"], dat=False
            )
            write_slot(p, "WrongQuest", "10:07:00, 10.01.2026", ["mq304_active=1"])
            with patch(
                "companion.core.parse_sav_dat",
                side_effect=AssertionError("finder read a binary"),
            ):
                data = search(p)
            self.assertEqual(data["windows"]["all"]["candidates"], ["AutoSave-2"])
            self.assertEqual(data["windows"]["all"]["first_confirmed"], ["AutoSave-1"])
            self.assertEqual(data["windows"]["manual"]["candidates"], ["ManualSave-90"])
            self.assertEqual(
                data["windows"]["manual"]["first_confirmed"], ["ManualSave-1"]
            )
            self.assertEqual(
                {x["slot"] for x in data["rows"]},
                {"ManualSave-90", "AutoSave-2", "AutoSave-1", "ManualSave-1"},
            )
            self.assertEqual(data["incomplete"], 1)
            self.assertEqual(data["profile_slots"], 6)

    def test_finder_includes_slots_beyond_main_window(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            write_slot(p, "Earlier", "10:00:00, 10.01.2026", ["q304_active=1"])
            write_slot(p, "Later", "10:02:00, 10.01.2026", finished="q304 q305")
            app = CompanionApp(p, max_saves=1)
            state = app.state()
            self.assertEqual(
                [x["save_id"] for x in state["save_selection"]["saves"]], ["Later"]
            )
            self.assertEqual(
                search(p, state["latest"]["playthrough_id"])["windows"]["all"][
                    "candidates"
                ],
                ["Earlier"],
            )

    def test_bad_optional_time_does_not_hide_other_slots(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            slot = write_slot(
                p, "Copied slot", "10:00:00, 10.01.2026", ["q304_active=1"]
            )
            meta = slot / "metadata.9.json"
            data = json.loads(meta.read_text())
            data["Data"]["metadata"]["playthroughTime"] = "unavailable"
            meta.write_text(json.dumps(data), encoding="utf8")
            write_slot(p, "After", "10:01:00, 10.01.2026", finished="q306")
            result = search(p)
            self.assertEqual(result["windows"]["all"]["candidates"], ["Copied slot"])
            self.assertEqual(result["windows"]["all"]["first_confirmed"], ["After"])
            self.assertIsNone(
                next(r["hours"] for r in result["rows"] if r["slot"] == "Copied slot")
            )

    def test_missing_profile_bad_clock_ties_and_parallel_routes(self):
        with TemporaryDirectory() as tmp:
            p = Path(tmp)
            for name in ("BackupA", "BackupB"):
                write_slot(p, name, "10:01:00, 10.01.2026", ["q304_active=1"])
            write_slot(p, "BrokenClock", "?", ["q304_active=1"])
            write_slot(p, "TiedLater", "10:01:00, 10.01.2026", finished="q305")
            write_slot(p, "OtherEnding", "10:04:00, 10.01.2026", finished="q306")
            w = search(p)["windows"]["all"]
            self.assertEqual(set(w["candidates"]), {"BackupA", "BackupB"})
            self.assertEqual(w["first_confirmed"], ["OtherEnding"])
            self.assertTrue(w["same_time"] and w["both_routes"])
            with patch(
                "companion.core._slot_metadata",
                side_effect=AssertionError("no cross-profile fallback"),
            ):
                none = search(p, "")
            self.assertEqual((none["reason"], none["rows"]), ("no-profile", []))
