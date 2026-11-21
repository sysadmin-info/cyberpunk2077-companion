"""Curated Iconic weapon registry and conservative save matcher."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any
import json
from urllib.parse import urlparse


def validate_guide(guide: dict) -> None:
    if not isinstance(guide, dict) or guide.get("verification") not in {"source_checked", "needs_verification"}:
        raise IconicWeaponDataError("invalid guide verification")
    if guide.get("method") not in {"loot", "quest", "crafting", "exploration", "account", "purchase", "unknown"}:
        raise IconicWeaponDataError("invalid acquisition method")
    if guide.get("availability") != "not_evaluated":
        raise IconicWeaponDataError("current-save availability is not implemented")
    for field in ("quest", "npc", "conditions"):
        if not isinstance(guide.get(field), str):
            raise IconicWeaponDataError(f"guide {field} must be a string")
    if guide.get("fast_travel") is not None and not isinstance(guide["fast_travel"], str):
        raise IconicWeaponDataError("fast_travel must be a string or null")
    for field in ("sources", "map_links"):
        if not isinstance(guide.get(field), list):
            raise IconicWeaponDataError(f"guide {field} must be an array")
        for link in guide[field]:
            if not isinstance(link, dict) or not isinstance(link.get("label"), str) or not isinstance(link.get("url"), str):
                raise IconicWeaponDataError("invalid guide link")
            url = urlparse(link["url"])
            if url.scheme != "https" or not url.hostname or url.username or url.password or any(c.isspace() for c in link["url"]):
                raise IconicWeaponDataError("guide links must be public HTTPS URLs")
    if guide["verification"] == "source_checked" and (not guide["sources"] or not guide.get("checked_on")):
        raise IconicWeaponDataError("source-checked guide needs sources and review date")

from .binary import tweakdbid_for_name


class IconicWeaponDataError(ValueError):
    pass


REQUIRED_FIELDS = {"id", "name", "game", "weapon_type", "tweakdb_ids", "acquisition", "location"}
STATUS_PRIORITY = {"unknown": -1, "missing": 0, "other": 1, "stash": 2, "inventory": 3, "equipped": 4}


def availability_class(record: dict[str, Any]) -> str:
    """Describe acquisition conditions; never claims save-specific availability."""
    guide = record.get("guide", {})
    tags = set(record.get("collection_tags", []))
    if guide.get("verification") != "source_checked":
        return "unknown"
    if "story_choice" in tags:
        return "decision_dependent"
    if guide.get("method") == "account":
        return "account_or_promo"
    # A checked guide or a historical promotion says nothing about whether
    # this playthrough still permits acquisition.
    return "unknown"


def load_iconic_registry(path: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IconicWeaponDataError(f"cannot read Iconic registry: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("weapons"), list):
        raise IconicWeaponDataError("Iconic registry must contain a weapons array")

    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for index, raw in enumerate(payload["weapons"]):
        if not isinstance(raw, dict):
            raise IconicWeaponDataError(f"weapons[{index}] must be an object")
        missing = REQUIRED_FIELDS - raw.keys()
        if missing:
            raise IconicWeaponDataError(f"weapons[{index}] missing: {', '.join(sorted(missing))}")
        record = dict(raw)
        record["id"] = str(record["id"]).strip()
        if not record["id"] or record["id"] in seen:
            raise IconicWeaponDataError(f"duplicate or empty Iconic id: {record['id']!r}")
        seen.add(record["id"])
        if record["game"] not in {"base", "phantom_liberty"}:
            raise IconicWeaponDataError(f"invalid game for {record['id']}")
        ids = record["tweakdb_ids"]
        if not isinstance(ids, list) or not ids or not all(isinstance(x, str) and x.strip() for x in ids):
            raise IconicWeaponDataError(f"tweakdb_ids must be a non-empty string array for {record['id']}")
        record["tweakdb_ids"] = list(dict.fromkeys(x.strip() for x in ids))
        if "guide" in record:
            validate_guide(record["guide"])
        record["availability_class"] = availability_class(record)
        records.append(record)
    return records


def _row_ids(row: dict[str, Any]) -> set[str]:
    ids = {str(row.get("id") or "").strip()}
    value = str(row.get("tweakdb_value") or "").strip().upper().removeprefix("0X")
    if value:
        ids.add(value.zfill(16))
    return {x for x in ids if x}


def build_iconic_payload(latest: dict[str, Any], registry_path: Path) -> dict[str, Any]:
    registry = load_iconic_registry(registry_path)
    sources = (
        ("equipped", latest.get("equipped_weapons", []) or []),
        ("inventory", [x for x in latest.get("inventory_records", []) or [] if x.get("status") == "player"]),
        ("stash", [x for x in latest.get("inventory_records", []) or [] if x.get("status") == "stash"]),
        ("other", [x for x in latest.get("inventory_records", []) or [] if x.get("status") == "other"]),
    )
    rows: list[dict[str, Any]] = []
    for weapon in registry:
        aliases = set(weapon["tweakdb_ids"])
        hashes = {f"{tweakdbid_for_name(alias):016X}" for alias in aliases}
        matches: list[dict[str, Any]] = []
        complete = (latest.get("binary_parser_status") == "ok"
                    and latest.get("inventory_containers_status") == "ok"
                    and latest.get("equipment_status") == "ok")
        best = "missing" if complete else "unknown"
        for status, candidates in sources:
            for candidate in candidates:
                if _row_ids(candidate) & (aliases | hashes):
                    best = status if STATUS_PRIORITY[status] > STATUS_PRIORITY[best] else best
                    matches.append({"status": status, "id": candidate.get("id"), "tweakdb_value": candidate.get("tweakdb_value"), "storage_ids": candidate.get("storage_ids", []), "node_ids": candidate.get("node_ids", [])})
        rows.append({**weapon, "status": best, "owned": best in {"equipped", "inventory", "stash"}, "matches": matches,
                     "locations": sorted({x['status'] for x in matches}, key=lambda x: -STATUS_PRIORITY[x])})

    counts = Counter(row["status"] for row in rows)
    return {
        "schema": "cp2077-companion/iconic-weapons-v1",
        "registry_scope": "expanded-base-and-phantom-liberty",
        "coverage": {"complete": False, "excludes": ["grenades", "cyberware", "quickhacks", "recipes"],
                     "note": "Expanded reference catalogue; completeness across patches is not guaranteed."},
        "guide_counts": {
            "source_checked": sum(w.get("guide", {}).get("verification") == "source_checked" for w in rows),
            "needs_verification": sum(w.get("guide", {}).get("verification") != "source_checked" for w in rows),
            "with_map": sum(bool(w.get("guide", {}).get("map_links")) for w in rows),
        },
        "records": rows,
        "counts": {
            "total": len(rows),
            "owned": sum(1 for row in rows if row["owned"]),
            "missing": counts["missing"],
            "equipped": counts["equipped"],
            "inventory": counts["inventory"],
            "other": counts["other"],
            "stash": counts["stash"],
            "unknown": counts["unknown"],
            "base": sum(1 for row in rows if row["game"] == "base"),
            "phantom_liberty": sum(1 for row in rows if row["game"] == "phantom_liberty"),
        },
        "notes": [
            "INNY KONTENER nie oznacza automatycznie schowka.",
            "BRAK oznacza tylko brak dopasowania w parsowanych danych, nie ocenę dostępności fabularnej.",
        ],
    }
