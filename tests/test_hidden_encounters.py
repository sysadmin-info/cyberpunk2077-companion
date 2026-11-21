from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from companion.hidden_encounters import (
    HiddenEncounterDataError,
    build_hidden_encounters_payload,
    load_hidden_encounter_dataset,
    set_user_status,
)


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "hidden_encounters.json"


class HiddenEncountersTests(unittest.TestCase):
    def test_release_dataset_is_valid_and_small(self):
        dataset = load_hidden_encounter_dataset(DATA)
        records = dataset["records"]
        self.assertEqual(4, len(records))
        self.assertEqual(4, len({row["id"] for row in records}))
        self.assertTrue(all(row.get("sources") for row in records))
        self.assertTrue(all(row.get("hint") for row in records))

    def test_quick_filter_flags_expected_records(self):
        payload = build_hidden_encounters_payload(DATA, Path("/definitely/not/present/status.sqlite3"))
        flagged = [
            row["id"]
            for row in payload["records"]
            if row.get("conditions", {}).get("do_not_attack_first")
        ]
        self.assertEqual(
            {"stadium-love-holster-first", "only-pain-talk-before-fight"},
            set(flagged),
        )
        self.assertEqual(2, payload["counts"]["do_not_attack_first"])

    def test_padre_is_not_presented_as_fully_verified(self):
        dataset = load_hidden_encounter_dataset(DATA)
        padre = next(x for x in dataset["records"] if x["id"] == "padre-the-glen-bleachers-dialogue")
        self.assertEqual("needs_verification", padre["verification"]["status"])

    def test_user_status_roundtrip_is_app_local(self):
        with TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "hidden_encounters_status.sqlite3"
            set_user_status(
                "stadium-love-holster-first",
                "discovered",
                DATA,
                status_path,
            )
            payload = build_hidden_encounters_payload(DATA, status_path)
            row = next(x for x in payload["records"] if x["id"] == "stadium-love-holster-first")
            self.assertEqual("discovered", row["user_status"])
            self.assertTrue(status_path.exists())

    def test_invalid_status_and_id_are_rejected(self):
        with TemporaryDirectory() as tmp:
            status_path = Path(tmp) / "status.sqlite3"
            with self.assertRaises(HiddenEncounterDataError):
                set_user_status("stadium-love-holster-first", "seen-ish", DATA, status_path)
            with self.assertRaises(HiddenEncounterDataError):
                set_user_status("made-up-encounter", "completed", DATA, status_path)


if __name__ == "__main__":
    unittest.main()
