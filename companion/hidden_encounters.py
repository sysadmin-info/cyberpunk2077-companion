from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import sqlite3
from contextlib import closing
from typing import Any


ALLOWED_USER_STATUSES = {"unknown", "discovered", "completed"}
ALLOWED_VERIFICATION_STATUSES = {
    "game_data",
    "multi_source",
    "community",
    "user_observation",
    "needs_verification",
    "unverified",
}


class HiddenEncounterDataError(ValueError):
    """Raised when the hidden encounter dataset has an invalid shape."""


def _default_data_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "hidden_encounters.json"


def _default_status_path() -> Path:
    return Path(__file__).resolve().parent.parent / "data" / "hidden_encounters.sqlite3"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_source(source: dict[str, Any], encounter_id: str) -> None:
    kind = str(source.get("kind", "")).strip()
    title = str(source.get("title", "")).strip()
    if not kind or not title:
        raise HiddenEncounterDataError(f"{encounter_id}: every source requires kind and title")
    url = source.get("url")
    if url is not None and not str(url).startswith(("https://", "http://")):
        raise HiddenEncounterDataError(f"{encounter_id}: source URL must be http(s) or null")


def _validate_record(record: dict[str, Any], seen: set[str]) -> None:
    encounter_id = str(record.get("id", "")).strip()
    if not encounter_id:
        raise HiddenEncounterDataError("hidden encounter record is missing id")
    if encounter_id in seen:
        raise HiddenEncounterDataError(f"duplicate hidden encounter id: {encounter_id}")
    seen.add(encounter_id)

    required_text = ("title", "district", "location", "interaction_type", "hint", "miss_risk")
    for field in required_text:
        if not str(record.get(field, "")).strip():
            raise HiddenEncounterDataError(f"{encounter_id}: missing {field}")

    default_status = str(record.get("user_status", "unknown"))
    if default_status not in ALLOWED_USER_STATUSES:
        raise HiddenEncounterDataError(f"{encounter_id}: invalid user_status {default_status}")

    conditions = record.get("conditions", {})
    if not isinstance(conditions, dict):
        raise HiddenEncounterDataError(f"{encounter_id}: conditions must be an object")

    sources = record.get("sources", [])
    if not isinstance(sources, list) or not sources:
        raise HiddenEncounterDataError(f"{encounter_id}: at least one source is required")
    for source in sources:
        if not isinstance(source, dict):
            raise HiddenEncounterDataError(f"{encounter_id}: source must be an object")
        _validate_source(source, encounter_id)

    verification = record.get("verification", {})
    if not isinstance(verification, dict):
        raise HiddenEncounterDataError(f"{encounter_id}: verification must be an object")
    verification_status = str(verification.get("status", "unverified"))
    if verification_status not in ALLOWED_VERIFICATION_STATUSES:
        raise HiddenEncounterDataError(
            f"{encounter_id}: invalid verification status {verification_status}"
        )

    coordinates = record.get("coordinates")
    if coordinates is not None:
        if not isinstance(coordinates, dict) or "lat" not in coordinates or "lng" not in coordinates:
            raise HiddenEncounterDataError(f"{encounter_id}: coordinates require lat/lng or null")


def load_hidden_encounter_dataset(data_path: Path | None = None) -> dict[str, Any]:
    path = data_path or _default_data_path()
    payload = _read_json(path)
    if not isinstance(payload, dict):
        raise HiddenEncounterDataError("hidden encounter dataset must be an object")
    records = payload.get("records")
    if not isinstance(records, list):
        raise HiddenEncounterDataError("hidden encounter dataset requires records[]")

    seen: set[str] = set()
    for record in records:
        if not isinstance(record, dict):
            raise HiddenEncounterDataError("hidden encounter record must be an object")
        _validate_record(record, seen)
    return payload


def profile_scope(latest: dict) -> str:
    return ("play:" + str(latest["playthrough_id"]) if latest.get("playthrough_id")
            else "slot:" + str(latest.get("save_id", "")))

def load_user_statuses(status_path: Path | None = None, scope: str = "legacy") -> dict[str, str]:
    path = status_path or _default_status_path()
    if not path.exists():
        return {}
    with closing(sqlite3.connect(path, timeout=5)) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='checks'").fetchone():
            return {}
        return dict(db.execute("SELECT encounter, status FROM checks WHERE scope=?", (scope,)))

def _ensure(db):
    db.execute("CREATE TABLE IF NOT EXISTS checks (scope TEXT NOT NULL, encounter TEXT NOT NULL, status TEXT NOT NULL, PRIMARY KEY(scope, encounter))")

def import_legacy(path: Path, scope: str, valid_ids: set[str]) -> int:
    from .localio import read_limited, META_LIMIT
    old = path.with_name("hidden_encounters_status.json")
    obj = json.loads(read_limited(old, META_LIMIT).decode("utf-8-sig"))
    if not isinstance(obj, dict):
        raise HiddenEncounterDataError("Invalid legacy checklist")
    entries = obj.get("statuses", obj)
    if not isinstance(entries, dict):
        raise HiddenEncounterDataError("Invalid legacy checklist")
    rows = [(scope,k,v) for k,v in entries.items() if k in valid_ids and isinstance(v,str) and v in ALLOWED_USER_STATUSES]
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        _ensure(db)
        db.executemany("INSERT OR IGNORE INTO checks VALUES (?,?,?)", rows)
        return db.total_changes


def build_hidden_encounters_payload(
    data_path: Path | None = None,
    status_path: Path | None = None,
    scope: str = "legacy",
) -> dict[str, Any]:
    dataset = load_hidden_encounter_dataset(data_path)
    statuses = load_user_statuses(status_path, scope)
    records: list[dict[str, Any]] = []

    for raw in dataset.get("records", []):
        record = deepcopy(raw)
        record["user_status"] = statuses.get(record["id"], record.get("user_status", "unknown"))
        records.append(record)

    filters = {
        "districts": sorted({str(x.get("district")) for x in records if x.get("district")}),
        "interaction_types": sorted({str(x.get("interaction_type")) for x in records if x.get("interaction_type")}),
        "related_activities": sorted(
            {
                str((x.get("related_activity") or {}).get("name"))
                for x in records
                if (x.get("related_activity") or {}).get("name")
            }
        ),
        "statuses": sorted(ALLOWED_USER_STATUSES),
        "miss_risks": sorted({str(x.get("miss_risk")) for x in records if x.get("miss_risk")}),
    }
    return {
        "schema": dataset.get("schema", "cp2077-companion/hidden-encounters-v1"),
        "scope": scope,
        "legacy_available": (status_path or _default_status_path()).with_name("hidden_encounters_status.json").is_file(),
        "dataset_version": dataset.get("dataset_version", 1),
        "records": records,
        "filters": filters,
        "counts": {
            "total": len(records),
            "unknown": sum(1 for x in records if x.get("user_status") == "unknown"),
            "discovered": sum(1 for x in records if x.get("user_status") == "discovered"),
            "completed": sum(1 for x in records if x.get("user_status") == "completed"),
            "do_not_attack_first": sum(
                1 for x in records if bool((x.get("conditions") or {}).get("do_not_attack_first"))
            ),
            "needs_verification": sum(
                1
                for x in records
                if str((x.get("verification") or {}).get("status"))
                in {"needs_verification", "unverified", "community", "user_observation"}
            ),
        },
    }


def set_user_status(
    encounter_id: str,
    status: str,
    data_path: Path | None = None,
    status_path: Path | None = None,
    scope: str = "legacy",
) -> dict[str, Any]:
    encounter_id = str(encounter_id).strip()
    status = str(status).strip()
    if status not in ALLOWED_USER_STATUSES:
        raise HiddenEncounterDataError(f"invalid hidden encounter status: {status}")

    dataset = load_hidden_encounter_dataset(data_path)
    ids = {str(x.get("id")) for x in dataset.get("records", [])}
    if encounter_id not in ids:
        raise HiddenEncounterDataError(f"unknown hidden encounter id: {encounter_id}")

    path = status_path or _default_status_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=5)) as db, db:
        _ensure(db)
        db.execute("INSERT INTO checks VALUES (?,?,?) ON CONFLICT(scope,encounter) DO UPDATE SET status=excluded.status",
                   (scope, encounter_id, status))
    return {"id": encounter_id, "status": status}
