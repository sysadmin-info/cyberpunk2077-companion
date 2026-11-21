from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
import math
import heapq
import json
import re
import struct
from typing import Any

from .binary import (
    BinarySaveData,
    SaveFormatError,
    fnv1a32,
    parse_sav_dat,
    tweakdbid_for_name,
)
from .localio import META_LIMIT, regular_local, read_limited
from .catalog import DECISION_FACTS, ENDING_MARKERS, KNOWN_FACT_NAMES, KNOWN_ITEMS, QUESTS
from .item_catalog import load_catalog
from .readiness import evaluate_reaper_readiness
from .quickhacks import quickhacks_payload
from .quest_choices import quest_choices_payload
from . import firestarter


SAVE_TS_FORMAT = "%H:%M:%S, %d.%m.%Y"


@dataclass
class SaveSnapshot:
    save_name: str
    save_path: str
    timestamp_string: str
    timestamp_iso: str
    play_time_hours: float
    playthrough_hours: float
    level: int
    street_cred: int
    life_path: str
    difficulty: str
    body_gender: str
    brain_gender: str
    attributes: dict[str, int]
    patch: str
    game_version: int
    save_version: int
    playthrough_id: str
    point_of_no_return_id: str
    location_name: str
    position: dict[str, float]
    tracked_quest: str
    tracked_quest_entry: str
    active_quests: list[str]
    finished_quests: list[str]
    metadata_facts: dict[str, int]
    resolved_binary_facts: dict[str, int]
    binary_fact_entries: int
    binary_node_count: int
    binary_parser_status: str
    reward_strings: list[str]
    inventory_subinventory_count: int
    inventory_containers_status: str
    player_inventory_storage_id: int | None
    player_inventory_declared_count: int
    player_inventory_parsed_count: int
    all_item_record_count: int
    wallet_eurodollars: int | None
    inventory_items: list[dict[str, Any]]
    inventory_records: list[dict[str, Any]]
    item_catalog: dict[str, Any]
    equipment_status: str
    equipped_items: list[dict[str, Any]]
    equipped_weapons: list[dict[str, Any]]
    equipped_cyberware: list[dict[str, Any]]
    stat_pools_status: str
    player_stats_status: str
    player_stats: dict[str, Any]
    player_development_status: str
    development_points: list[dict[str, Any]]
    available_attribute_points: int | None
    available_perk_points: int | None
    available_relic_points: int | None
    skills: list[dict[str, Any]]
    perk_trees: list[dict[str, Any]]
    purchased_perk_count: int
    purchased_perk_ranks: int
    is_point_of_no_return: bool
    is_end_game_save: bool
    is_checkpoint: bool
    is_modded: bool
    has_phantom_liberty: bool
    screenshot_path: str | None


def _metadata_file(save_dir: Path) -> Path | None:
    files = [p for p in save_dir.glob("metadata.*.json") if regular_local(p)]
    if not files:
        return None

    def key(path: Path) -> tuple[int, float]:
        match = re.search(r"metadata\.(\d+)\.json$", path.name)
        generation = int(match.group(1)) if match else -1
        return generation, path.stat().st_mtime

    return max(files, key=key)


def _parse_timestamp(value: str) -> datetime:
    try:
        return datetime.strptime(value, SAVE_TS_FORMAT)
    except ValueError:
        return datetime.min


def _fact_map(raw_facts: list[Any]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in raw_facts or []:
        text = str(item)
        name, sep, value = text.partition("=")
        if not sep:
            continue
        try:
            result[name] = int(value)
        except ValueError:
            continue
    return result


def _inventory_summary(binary: BinarySaveData | None) -> tuple[int | None, list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    catalog_by_tweakdb, _, catalog_info = load_catalog()
    if binary is None:
        return None, [], [], catalog_info

    player_items = list(binary.player_inventory_items)
    all_items = list(binary.all_item_records)
    player_ids = {item.node_index for item in player_items}
    known_rows: list[dict[str, Any]] = []
    wallet: int | None = None

    # Compatibility/diagnostic probes used by the existing v0.2 cards.
    for known in KNOWN_ITEMS:
        expected = tweakdbid_for_name(known["id"])
        in_player = [item for item in player_items if item.tweakdb_value == expected]
        elsewhere = [
            item for item in all_items
            if item.node_index not in player_ids and item.tweakdb_value == expected
        ]

        if in_player:
            status = "player"
            matches = in_player
        elif elsewhere:
            status = "stash" if any(x.storage_id == 1000000 for x in elsewhere) else "other"
            matches = [x for x in elsewhere if x.storage_id == 1000000] if status == "stash" else elsewhere
        else:
            status = "absent"
            matches = []

        quantity = sum(item.quantity for item in matches) if matches else 0
        row = {
            **known,
            "status": status,
            "quantity": quantity,
            "node_ids": [item.node_index for item in matches],
            "raw_sizes": sorted({item.raw_size for item in matches}),
            "tweakdb_hash": f"{expected & 0xFFFFFFFF:08X}",
            "tweakdb_length": (expected >> 32) & 0xFF,
        }
        known_rows.append(row)
        if known["id"] == "Items.money" and in_player:
            wallet = sum(item.quantity for item in in_player)

    # Resolve every itemData record we can, and keep unknown TweakDB values
    # visible. Aggregate identical item types inside the same coarse container.
    grouped: dict[tuple[str, int], list[Any]] = {}
    for item in all_items:
        status = "player" if item.node_index in player_ids else "stash" if item.storage_id == 1000000 else "other"
        grouped.setdefault((status, item.tweakdb_value), []).append(item)

    records: list[dict[str, Any]] = []
    for (status, tweakdb_value), matches in grouped.items():
        cat = catalog_by_tweakdb.get(tweakdb_value)
        records.append({
            "status": status,
            "id": cat.id if cat else None,
            "storage_ids": sorted({x.storage_id for x in matches if x.storage_id is not None}),
            "name": cat.name if cat else None,
            "subcategory": cat.subcategory if cat else "",
            "category": cat.category if cat else "",
            "catalog_source": cat.source if cat else None,
            "catalog_name": cat.catalog_name if cat else None,
            "name_source": cat.name_source if cat else None,
            "quantity": sum(int(x.quantity) for x in matches),
            "node_ids": [int(x.node_index) for x in matches],
            "raw_sizes": sorted({int(x.raw_size) for x in matches}),
            "quantity_sources": sorted({x.quantity_source for x in matches}),
            "tweakdb_value": f"{tweakdb_value:016X}",
            "tweakdb_hash": f"{tweakdb_value & 0xFFFFFFFF:08X}",
            "tweakdb_length": (tweakdb_value >> 32) & 0xFF,
            "resolved": cat is not None,
        })

    records.sort(key=lambda x: (0 if x["status"] == "player" else 1, 0 if x["resolved"] else 1, (x["name"] or x["id"] or x["tweakdb_value"]).lower()))

    # Some reward IDs changed/alias across game revisions. If the exact v0.2
    # probe misses but the external catalog resolves a player item to the same
    # display name, surface that evidence instead of a misleading red card.
    for probe in known_rows:
        if probe["status"] != "absent" or probe.get("category") != "ending reward":
            continue
        aliases = [r for r in records if r["status"] == "player" and r.get("name") and r["name"].casefold() == probe["name"].casefold()]
        if aliases:
            probe["status"] = "player"
            probe["quantity"] = sum(int(r["quantity"]) for r in aliases)
            probe["node_ids"] = [node for r in aliases for node in r["node_ids"]]
            probe["resolved_via_catalog_alias"] = True
            probe["actual_ids"] = [r["id"] for r in aliases if r.get("id")]

    catalog_info = dict(catalog_info)
    catalog_info.update({
        "resolved_item_groups": sum(1 for x in records if x["resolved"]),
        "unknown_item_groups": sum(1 for x in records if not x["resolved"]),
        "item_groups": len(records),
    })
    return wallet, known_rows, records, catalog_info



_EQUIP_AREA_LABELS = {
    "EyesCW": "Face / Eyes",
    "FrontalCortexCW": "Frontal Cortex",
    "MusculoskeletalSystemCW": "Skeleton",
    "NervousSystemCW": "Nervous System",
    "CardiovascularSystemCW": "Circulatory System",
    "ImmuneSystemCW": "Immune System",
    "IntegumentarySystemCW": "Integumentary System",
    "HandsCW": "Hands",
    "ArmsCW": "Arms",
    "LegsCW": "Legs",
    "AbilityCW": "Cyberware ability",
    "SystemReplacementCW": "Operating System",
}


def _equipment_summary(binary: BinarySaveData | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    if binary is None or binary.equipment is None:
        return [], [], []
    catalog_by_tweakdb, _, _ = load_catalog()
    rows: list[dict[str, Any]] = []
    for item in binary.equipment.items:
        cat = catalog_by_tweakdb.get(item.tweakdb_value)
        area_label = _EQUIP_AREA_LABELS.get(item.area_type, item.area_type)
        slot_label = f"Weapon {item.slot_index + 1}" if item.area_type == "Weapon" else f"{area_label} / slot {item.slot_index + 1}"
        rows.append({
            "area_type": item.area_type,
            "area_label": area_label,
            "slot_index": item.slot_index,
            "slot_label": slot_label,
            "id": cat.id if cat else None,
            "name": cat.name if cat else None,
            "category": cat.category if cat else "",
            "subcategory": cat.subcategory if cat else "",
            "catalog_source": cat.source if cat else None,
            "catalog_name": cat.catalog_name if cat else None,
            "name_source": cat.name_source if cat else None,
            "resolved": cat is not None,
            "tweakdb_value": f"{item.tweakdb_value:016X}",
            "tweakdb_hash": f"{item.tweakdb_hash:08X}",
            "tweakdb_length": item.tweakdb_length,
            "rng_seed": item.rng_seed,
            "active_index": item.active_index,
            "equipped": True,
        })
    weapons = [x for x in rows if x["area_type"] == "Weapon"]
    cyberware = [x for x in rows if x["area_type"] in _EQUIP_AREA_LABELS]
    weapons.sort(key=lambda x: x["slot_index"])
    cyberware.sort(key=lambda x: (x["area_label"], x["slot_index"]))
    return rows, weapons, cyberware


def _round_saved_float(value: Any) -> float | None:
    if value is None:
        return None
    number = float(value)
    return round(number, 3) if math.isfinite(number) else None


def _public_stat_pool(pool: dict[str, Any]) -> dict[str, Any]:
    """Normalize one persisted player StatPoolsSystem row for UI/export.

    These are saved pools, not a declaration that a related OS/cyberware is
    currently active. CP2077 can retain scripted or stale pools in the save.
    """
    return {
        "type": pool.get("type"),
        "stat": pool.get("stat"),
        "max_value": _round_saved_float(pool.get("max_value")),
        "current_value": _round_saved_float(pool.get("current_value")),
        "custom_limit_value": _round_saved_float(pool.get("custom_limit_value")),
        "modification_delay": _round_saved_float(pool.get("modification_delay")),
        "change_mode": pool.get("change_mode"),
        "record_id": pool.get("record_id"),
        "is_health": pool.get("type") == "Health" or pool.get("stat") == "Health",
    }


def _player_stats_summary(binary: BinarySaveData | None) -> dict[str, Any]:
    if binary is None:
        return {}
    health = binary.stat_pools.health if binary.stat_pools else None
    saved_pools = [_public_stat_pool(pool) for pool in (binary.stat_pools.pools if binary.stat_pools else ())]
    saved_pools.sort(key=lambda row: (0 if row.get("is_health") else 1, str(row.get("type") or ""), str(row.get("stat") or "")))
    stats = binary.player_stats

    health_modifiers = [dict(x) for x in (stats.health_modifier_evidence if stats else ())]
    if health:
        health_status = "exact"
        health_source = "StatPoolsSystem"
        health_note = "Dokładna pula Health została utrwalona w tym save."
    elif health_modifiers:
        health_status = "modifier-evidence-only"
        health_source = "StatsSystem"
        health_note = (
            "StatsSystem contains Health/MaxHealth modifier evidence, but not the engine-derived final Health value; "
            "Companion does not convert a modifier into fake max HP."
        )
    else:
        health_status = "not-persisted"
        health_source = None
        health_note = (
            "This save does not persist a player Health StatPool. StatsSystem stores saved stat inputs/modifiers, "
            "not the engine-derived current/max Health value, so there is no exact read-only fallback in sav.dat."
        )

    known_saved_stats = [dict(x) for x in (stats.known_saved_stats if stats else ())]
    return {
        "health": {
            "max": _round_saved_float(health.get("max_value")) if health else None,
            "current_percent": _round_saved_float(health.get("current_value")) if health else None,
            "custom_limit": _round_saved_float(health.get("custom_limit_value")) if health else None,
            "change_mode": health.get("change_mode") if health else None,
            "status": health_status,
            "source": health_source,
            "note": health_note,
            "stats_system_modifier_evidence": health_modifiers,
        },
        "saved_stat_pool_count": len(saved_pools),
        "saved_stat_pools": saved_pools,
        "stats_system_record_id": f"0x{stats.record_id:016X}" if stats and stats.record_id is not None else None,
        "stats_system_record_name": stats.record_name if stats else None,
        "stats_system_seed": stats.seed if stats else None,
        "known_saved_stats": known_saved_stats,
        "saved_humanity_additive": _round_saved_float(stats.humanity_additive) if stats else None,
        "constant_modifier_count": len(stats.modifiers) if stats else 0,
        "forced_modifier_count": len(stats.forced_modifiers) if stats else 0,
        "inactive_stats": list(stats.inactive_stats) if stats else [],
        "cyberware_capacity": {
            "installed_cost": None,
            "effective_capacity": None,
            "status": "not resolved",
            "note": "v0.5 exposes saved Humanity modifiers but does not reconstruct the engine's full derived Cyberware Capacity formula.",
        },
    }

def _finite(value):
    n = float(value)
    if not math.isfinite(n):
        raise ValueError("Non-finite number in save metadata")
    return n


def _read_metadata(save_dir: Path) -> dict:
    metadata_path = _metadata_file(save_dir)
    if metadata_path is None:
        raise FileNotFoundError("no save metadata")
    m = json.loads(read_limited(metadata_path, META_LIMIT).decode("utf-8-sig"))["Data"]["metadata"]
    if not isinstance(m, dict):
        raise ValueError("invalid save metadata")
    return m


def load_save(save_dir: Path, parse_binary: bool = True, metadata: dict | None = None) -> SaveSnapshot:
    m = _read_metadata(save_dir) if metadata is None else metadata
    ts = _parse_timestamp(str(m.get("timestampString", "")))
    finished = [x for x in str(m.get("finishedQuests", "")).split() if x]
    metadata_facts = _fact_map(m.get("facts", []))

    binary: BinarySaveData | None = None
    binary_status = "missing sav.dat" if parse_binary else "not requested"
    if parse_binary and regular_local(save_dir / "sav.dat"):
        try:
            binary = parse_sav_dat(save_dir / "sav.dat")
            binary_status = "ok"
        except OSError as exc:
            binary_status = f"error: could not read sav.dat ({type(exc).__name__})"
        except (SaveFormatError, ValueError, IndexError, OverflowError, RecursionError, struct.error) as exc:
            binary_status = f"error: {exc}"

    resolved_binary: dict[str, int] = {}
    reward_strings: list[str] = []
    if binary:
        names = set(KNOWN_FACT_NAMES) | set(metadata_facts)
        for name in names:
            value = binary.facts_by_hash.get(fnv1a32(name))
            if value is not None:
                resolved_binary[name] = value
        reward_strings = list(binary.reward_strings)

    wallet, inventory_items, inventory_records, item_catalog = _inventory_summary(binary)
    equipped_items, equipped_weapons, equipped_cyberware = _equipment_summary(binary)
    player_stats = _player_stats_summary(binary)

    development = binary.player_development if binary else None
    screenshot = save_dir / "screenshot.png"
    return SaveSnapshot(
        save_name=str(m.get("name") or save_dir.name),
        save_path=str(save_dir),
        timestamp_string=str(m.get("timestampString", "")),
        timestamp_iso=ts.isoformat() if ts != datetime.min else "",
        play_time_hours=round(_finite(m.get("playTime", 0)) / 3600, 2),
        playthrough_hours=round(_finite(m.get("playthroughTime", 0)) / 3600, 2),
        level=int(_finite(m.get("level", 0))),
        street_cred=int(_finite(m.get("streetCred", 0))),
        life_path=str(m.get("lifePath", "")),
        difficulty=str(m.get("difficulty", "")),
        body_gender=str(m.get("bodyGender", "")),
        brain_gender=str(m.get("brainGender", "")),
        attributes={
            "body": int(_finite(m.get("strength", 0))),
            "intelligence": int(_finite(m.get("intelligence", 0))),
            "reflexes": int(_finite(m.get("reflexes", 0))),
            "technical_ability": int(_finite(m.get("technicalAbility", 0))),
            "cool": int(_finite(m.get("cool", 0))),
        },
        patch=str(m.get("buildPatch", "")),
        game_version=int(m.get("gameVersion", 0) or 0),
        save_version=int(m.get("saveVersion", 0) or 0),
        playthrough_id=str(m.get("playthroughID") or ""),
        point_of_no_return_id=str(m.get("pointOfNoReturnId", "")),
        location_name=str(m.get("locationName", "")),
        position={
            "x": _finite((m.get("playerPosition") or {}).get("X", 0)),
            "y": _finite((m.get("playerPosition") or {}).get("Y", 0)),
            "z": _finite((m.get("playerPosition") or {}).get("Z", 0)),
        },
        tracked_quest=str(m.get("trackedQuest", "")),
        tracked_quest_entry=str(m.get("trackedQuestEntry", "")),
        active_quests=[x for x in str(m.get("activeQuests", "")).split(";") if x],
        finished_quests=finished,
        metadata_facts=metadata_facts,
        resolved_binary_facts=resolved_binary,
        binary_fact_entries=binary.fact_entry_count if binary else 0,
        binary_node_count=binary.node_count if binary else 0,
        binary_parser_status=binary_status,
        reward_strings=reward_strings,
        inventory_subinventory_count=binary.inventory_subinventory_count if binary else 0,
        player_inventory_storage_id=binary.player_inventory_storage_id if binary else None,
        player_inventory_declared_count=binary.player_inventory_declared_count if binary else 0,
        player_inventory_parsed_count=len(binary.player_inventory_items) if binary else 0,
        all_item_record_count=len(binary.all_item_records) if binary else 0,
        wallet_eurodollars=wallet,
        inventory_items=inventory_items,
        inventory_records=inventory_records,
        inventory_containers_status=binary.inventory_containers_status if binary else 'not parsed',
        item_catalog=item_catalog,
        equipment_status=binary.equipment_status if binary else "not requested",
        equipped_items=equipped_items,
        equipped_weapons=equipped_weapons,
        equipped_cyberware=equipped_cyberware,
        stat_pools_status=binary.stat_pools_status if binary else "not requested",
        player_stats_status=binary.player_stats_status if binary else "not requested",
        player_stats=player_stats,
        player_development_status=binary.player_development_status if binary else "not requested",
        development_points=list(development.development_points) if development else [],
        available_attribute_points=development.available_attribute_points if development else None,
        available_perk_points=development.available_perk_points if development else None,
        available_relic_points=development.available_relic_points if development else None,
        skills=list(development.skills) if development else [],
        perk_trees=list(development.perk_trees) if development else [],
        purchased_perk_count=development.purchased_perk_count if development else 0,
        purchased_perk_ranks=development.purchased_perk_ranks if development else 0,
        is_point_of_no_return=bool(m.get("isPointOfNoReturn")),
        is_end_game_save=bool(m.get("isEndGameSave")),
        is_checkpoint=bool(m.get("isCheckpoint")),
        is_modded=bool(m.get("isModded")),
        has_phantom_liberty="EP1" in (m.get("additionalContentIds") or []),
        screenshot_path=str(screenshot) if regular_local(screenshot) else None,
    )


def _slot_metadata(save_root, on_error):
    for path in save_root.iterdir():
        if not regular_local(path, directory=True):
            continue
        try:
            meta = _read_metadata(path)
        except FileNotFoundError:
            continue
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            RecursionError,
        ):
            on_error(path.name)
            continue
        yield path, meta


def find_firestarter_saves(save_root: Path, playthrough: str) -> dict:
    result = {"reason": "ok", "profile_slots": 0, "unreadable": 0, "incomplete": 0}
    if not playthrough or not playthrough.strip():
        return {**result, "reason": "no-profile", **firestarter.summarize([])}

    def unreadable(_name):
        result["unreadable"] += 1

    rows = []
    for path, m in _slot_metadata(save_root, unreadable):
        if m.get("playthroughID") != playthrough:
            continue
        result["profile_slots"] += 1
        raw_facts = m.get("facts") or []
        if not isinstance(raw_facts, list):
            unreadable(path.name)
            continue
        stage, evidence = firestarter.classify(
            _fact_map(raw_facts),
            str(m.get("finishedQuests") or "").split(),
            str(m.get("trackedQuestEntry") or ""),
        )
        if stage == "unknown":
            continue
        try:
            dat = path / "sav.dat"
            if not regular_local(dat) or dat.stat().st_size == 0:
                result["incomplete"] += 1
                continue
        except OSError:
            result["incomplete"] += 1
            continue
        stamp = str(m.get("timestampString") or "")
        dt = _parse_timestamp(stamp)
        try:
            hours = round(_finite(m["playthroughTime"]) / 3600, 2)
        except (KeyError, ValueError, TypeError, OverflowError):
            hours = None  # Missing optional display data does not invalidate choice evidence.
        rows.append(
            {
                "slot": path.name,
                "kind": firestarter.slot_kind(path.name),
                "time": stamp if dt != datetime.min else "",
                "time_iso": dt.isoformat() if dt != datetime.min else "",
                "hours": hours,
                "stage": stage,
                "evidence": evidence,
            }
        )
    return {**result, **firestarter.summarize(rows)}


def scan_saves(save_root: Path, max_saves: int = 500, binary_latest_only: bool = True, selected_save: str | None = None, warnings: list[str] | None = None) -> list[SaveSnapshot]:
    if not 1 <= max_saves <= 1000:
        raise ValueError("max-saves must be between 1 and 1000")
    def note(name: str):
        if warnings is not None and len(warnings) < 100:
            warnings.append(name)
    def candidates():
        for path, m in _slot_metadata(save_root, note):
            yield _parse_timestamp(str(m.get("timestampString", ""))), path.name, path, m
    snapshots = []
    for _, name, path, metadata in heapq.nlargest(max_saves, candidates(), key=lambda row: row[:2]):
        try:
            parse = not binary_latest_only or (name == selected_save if selected_save is not None else not snapshots)
            snapshots.append(load_save(path, parse_binary=parse, metadata=metadata))
        except (OSError, ValueError, TypeError, KeyError, AttributeError, OverflowError, RecursionError):
            note(name)
    return snapshots


def _merged_facts(save: SaveSnapshot) -> dict[str, int]:
    merged = dict(save.resolved_binary_facts)
    merged.update(save.metadata_facts)
    return merged


def quest_status(save: SaveSnapshot, quest: dict[str, str]) -> dict[str, Any]:
    qid = quest["id"]
    facts = _merged_facts(save)
    evidence: list[str] = []

    if qid in save.finished_quests:
        evidence.append(f"finishedQuests:{qid}")
        return {**quest, "status": "done", "evidence": evidence}

    if qid and qid in save.tracked_quest_entry:
        evidence.append("trackedQuestEntry")
        return {**quest, "status": "active", "evidence": evidence}

    for name in (qid + "_done", qid + "_finished"):
        if facts.get(name, 0) > 0:
            evidence.append(f"{name}={facts[name]}")
            return {**quest, "status": "done", "evidence": evidence}

    for name in (qid + "_active", qid + "_started", qid + "_start"):
        if facts.get(name, 0) > 0:
            evidence.append(f"{name}={facts[name]}")
            return {**quest, "status": "started", "evidence": evidence}

    prefix_hits = [f"{name}={value}" for name, value in facts.items() if name.startswith(qid + "_") and value]
    if prefix_hits:
        return {**quest, "status": "signal", "evidence": prefix_hits[:6]}

    return {**quest, "status": "unknown", "evidence": []}


def decisions(save: SaveSnapshot) -> list[dict[str, Any]]:
    facts = _merged_facts(save)
    out = []
    for fact_name, group, label, confidence in DECISION_FACTS:
        if fact_name not in facts:
            continue
        value = facts[fact_name]
        out.append(
            {
                "group": group,
                "label": label,
                "fact": fact_name,
                "value": value,
                "confidence": confidence,
                "active": value != 0,
            }
        )
    return out


def branch_markers(saves: list[SaveSnapshot]) -> list[dict[str, Any]]:
    ordered = sorted(saves, key=lambda s: s.timestamp_iso or "")
    previous_by_playthrough: dict[str, SaveSnapshot] = {}
    markers: dict[str, dict[str, Any]] = {}

    for save in ordered:
        previous = previous_by_playthrough.get(save.playthrough_id)
        marker = {"save_name": save.save_name, "kind": "normal", "delta_hours": 0.0}
        if previous:
            delta = save.playthrough_hours - previous.playthrough_hours
            marker["delta_hours"] = round(delta, 2)
            if delta < -0.17:
                marker["kind"] = "rewind"
            elif save.is_end_game_save and not previous.is_end_game_save:
                marker["kind"] = "ending"
            elif save.is_point_of_no_return and not previous.is_point_of_no_return:
                marker["kind"] = "point-of-no-return"
        elif save.is_point_of_no_return:
            marker["kind"] = "point-of-no-return"
        elif save.is_end_game_save:
            marker["kind"] = "ending"

        markers[save.save_path] = marker
        previous_by_playthrough[save.playthrough_id] = save

    return [markers[s.save_path] for s in saves]


def ending_evidence(saves: list[SaveSnapshot]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for spec in ENDING_MARKERS:
        hits = [s for s in saves if spec["marker"] in (s.tracked_quest_entry or "")]
        if not hits:
            continue
        chronological = sorted(hits, key=lambda s: s.timestamp_iso or "")
        out.append(
            {
                **spec,
                "save_count": len(hits),
                "first_seen": chronological[0].timestamp_string,
                "last_seen": chronological[-1].timestamp_string,
                "sample_saves": [
                    {"save": s.save_name, "tracked": s.tracked_quest_entry, "timestamp": s.timestamp_string}
                    for s in chronological[-3:]
                ],
            }
        )
    return out


def build_state(saves: list[SaveSnapshot], selected_save: str | None = None) -> dict[str, Any]:
    if not saves:
        return {"ok": False, "error": "no saves found"}
    latest = next((s for s in saves if Path(s.save_path).name == selected_save), None) if selected_save is not None else saves[0]
    if latest is None:
        return {"ok": False, "error": "Wybrany zapis nie jest dostępny. Wybierz inny zapis lub tryb automatyczny."}
    quest_rows = [quest_status(latest, q) for q in QUESTS]
    marker_rows = branch_markers(saves)
    history = []
    for save, marker in zip(saves, marker_rows):
        history.append(
            {
                "save_name": save.save_name,
                "timestamp": save.timestamp_string,
                "timestamp_iso": save.timestamp_iso,
                "playthrough_hours": save.playthrough_hours,
                "level": save.level,
                "street_cred": save.street_cred,
                "finished_count": len(save.finished_quests),
                "tracked": save.tracked_quest_entry,
                "end_game": save.is_end_game_save,
                "point_of_no_return": save.is_point_of_no_return,
                "branch": marker,
            }
        )

    public = asdict(latest)
    public["save_id"] = Path(public.pop("save_path")).name
    public["has_screenshot"] = bool(public.pop("screenshot_path"))
    public["item_catalog"] = {k: v for k, v in public.get("item_catalog", {}).items() if k != "path"}
    return {
        "ok": True,
        "latest": public,
        "decisions": decisions(latest),
        "quests": quest_rows,
        "endings": ending_evidence(saves),
        "reaper_readiness": evaluate_reaper_readiness(latest),
        "quickhacks": quickhacks_payload(asdict(latest)),
        "quest_choices": quest_choices_payload(asdict(latest)),
        "history": history,
        "stats": {
            "save_count": len(saves),
            "rewinds_detected": sum(1 for x in marker_rows if x["kind"] == "rewind"),
            "endgame_saves": sum(1 for x in saves if x.is_end_game_save),
            "point_of_no_return_saves": sum(1 for x in saves if x.is_point_of_no_return),
        },
    }


def assistant_context(state: dict[str, Any]) -> dict[str, Any]:
    if not state.get("ok"):
        return state
    latest = state["latest"]
    found_items = [x for x in latest["inventory_items"] if x["status"] != "absent" and x["category"] != "currency"]
    reward_probes = [x for x in latest["inventory_items"] if x["category"] == "ending reward"]
    resolved_player = [
        x for x in latest.get("inventory_records", [])
        if x.get("status") == "player" and x.get("resolved") and x.get("id") != "Items.money"
    ]
    player_stats = latest.get("player_stats", {}) or {}
    return {
        "schema": "cp2077-companion/assistant-context-v9",
        "generated_from": latest["save_name"],
        "save_timestamp": latest["timestamp_string"],
        "character": {
            "level": latest["level"],
            "street_cred": latest["street_cred"],
            "lifepath": latest["life_path"],
            "difficulty": latest["difficulty"],
            "attributes": latest["attributes"],
            "playthrough_hours": latest["playthrough_hours"],
            "patch": latest["patch"],
            "wallet_eurodollars": latest["wallet_eurodollars"],
            "development": {
                "parser_status": latest.get("player_development_status"),
                "available_attribute_points": latest.get("available_attribute_points"),
                "available_perk_points": latest.get("available_perk_points"),
                "available_relic_points": latest.get("available_relic_points"),
                "development_points_raw": latest.get("development_points", []),
                "skills": latest.get("skills", []),
                "purchased_perk_count": latest.get("purchased_perk_count", 0),
                "purchased_perk_ranks": latest.get("purchased_perk_ranks", 0),
                "perk_trees": latest.get("perk_trees", []),
            },
        },
        "current": {
            "tracked_quest": latest["tracked_quest"],
            "tracked_quest_entry": latest["tracked_quest_entry"],
            "active_quests": latest["active_quests"],
            "point_of_no_return": latest["is_point_of_no_return"],
            "end_game_save": latest["is_end_game_save"],
        },
        "equipment": {
            "parser_status": latest.get("equipment_status"),
            "all_equipped_count": len(latest.get("equipped_items", [])),
            "weapon_count": len(latest.get("equipped_weapons", [])),
            "cyberware_count": len(latest.get("equipped_cyberware", [])),
            "weapons": latest.get("equipped_weapons", []),
            "cyberware": latest.get("equipped_cyberware", []),
        },
        "stats": {
            "stat_pools_parser_status": latest.get("stat_pools_status"),
            "stats_system_parser_status": latest.get("player_stats_status"),
            "health": player_stats.get("health", {}),
            "saved_stat_pool_count": player_stats.get("saved_stat_pool_count", 0),
            "saved_stat_pools": player_stats.get("saved_stat_pools", []),
            "stats_system_record_id": player_stats.get("stats_system_record_id"),
            "stats_system_record_name": player_stats.get("stats_system_record_name"),
            "stats_system_seed": player_stats.get("stats_system_seed"),
            "known_saved_stats": player_stats.get("known_saved_stats", []),
            "saved_humanity_additive": player_stats.get("saved_humanity_additive"),
            "constant_modifier_count": player_stats.get("constant_modifier_count", 0),
            "forced_modifier_count": player_stats.get("forced_modifier_count", 0),
            "inactive_stats": player_stats.get("inactive_stats", []),
            "cyberware_capacity": player_stats.get("cyberware_capacity", {}),
        },
        "inventory": {
            "subinventory_count": latest["inventory_subinventory_count"],
            "containers_status": latest.get("inventory_containers_status", "not parsed"),
            "stash_items": [x for x in latest.get("inventory_records", []) if x["status"] == "stash"],
            "player_storage_id": latest["player_inventory_storage_id"],
            "player_declared_records": latest["player_inventory_declared_count"],
            "player_parsed_records": latest["player_inventory_parsed_count"],
            "all_item_records": latest["all_item_record_count"],
            "catalog": latest.get("item_catalog", {}),
            "known_items_found": found_items,
            "ending_reward_probes": reward_probes,
            "resolved_player_item_type_count": len(resolved_player),
            "resolved_player_items": resolved_player[:250],
        },
        "endings": state["endings"],
        "dont_fear_the_reaper_readiness": state.get("reaper_readiness", {}),
        "world_state": state["decisions"],
        "quest_tracker": state["quests"],
        "hidden_encounters": state.get("hidden_encounters", {}),
        "iconic_weapons": state.get("iconic_weapons", {}),
        "quickhacks": state.get("quickhacks", {}),
        "quest_choices": state.get("quest_choices", {}),
        "finished_quest_ids": latest["finished_quests"],
        "save_history_summary": state["stats"],
        "binary_parser": {
            "status": latest["binary_parser_status"],
            "node_count": latest["binary_node_count"],
            "fact_entries": latest["binary_fact_entries"],
            "player_development_status": latest.get("player_development_status"),
            "equipment_status": latest.get("equipment_status"),
            "stat_pools_status": latest.get("stat_pools_status"),
            "stats_system_status": latest.get("player_stats_status"),
        },
        "notes": [
            "The application is read-only and does not modify Cyberpunk 2077 saves.",
            "Hidden Encounters is a curated spoiler-light dataset. User discovered/completed progress is stored only in data/hidden_encounters.sqlite3 per playthrough inside the Companion folder, never in sav.dat.",
            "The expanded Iconic registry includes base-game, Phantom Liberty and special-reward weapons; completeness across patches is not guaranteed. Guide verification is separate from ownership. Missing means no parsed match, not permanently unavailable. Map links were read from a guide; destination map views were not all independently checked.",
            "EquipmentSystem is the source used for equipped weapon and cyberware slots; inventory presence is kept separate.",
            "Exact Health max/current values are read only when the player's StatPoolsSystem Health pool is persisted in that save.",
            "v0.5.4 exposes named StatsSystem inputs/modifiers and explicitly reports when Health is not persisted; StatsSystem modifiers are not mislabeled as an engine-derived Max Health fallback.",
            "All StatPoolsSystem rows persisted for EntityID=1 are exported; a saved pool does not by itself prove that matching cyberware or an operating system is currently active.",
            "Saved Humanity additive modifiers are read from StatsSystem. Effective Cyberware Capacity is deliberately left unresolved until the complete derived formula is validated.",
            "Development point type Primary is the game's perk-point pool; Espionage is the Relic-point pool in CP2077 2.x.",
            "Skill mappings use the CP2077 2.x internal proficiency names: CoolSkill=Headhunter, IntelligenceSkill=Netrunner, ReflexesSkill=Shinobi, StrengthSkill=Solo, TechnicalAbilitySkill=Engineer.",
            "Inventory status 'player' means the item was found in storage id 1; 'stash' means validated storage 1000000; 'other' is not ownership evidence.",
            "The optional NightCity Console TSV catalog resolves TweakDB item IDs to community item names; unknown hashes remain visible.",
            "Don't Fear the Reaper readiness v2 separates combat readiness from route eligibility and recognizes survivability/control and mobility as different viable profiles.",
            "Quest status 'unknown' means no supported signal was found; it does not prove the quest is unavailable or unfinished.",
        ],
    }


def assistant_context_markdown(ctx: dict[str, Any]) -> str:
    if not ctx.get("schema"):
        return "# CP2077 Companion\n\nNo save data available.\n"
    c = ctx["character"]
    dev = c.get("development", {})
    lines = [
        "# Cyberpunk 2077 — assistant context",
        "",
        f"- Save: **{ctx['generated_from']}** ({ctx['save_timestamp']})",
        f"- Level / Street Cred: **{c['level']} / {c['street_cred']}**",
        f"- Lifepath: **{c['lifepath']}**",
        f"- Difficulty: **{c['difficulty']}**",
        f"- Playthrough: **{c['playthrough_hours']} h**",
        f"- Patch: **{c['patch']}**",
        f"- Wallet: **€${c['wallet_eurodollars']}**" if c.get("wallet_eurodollars") is not None else "- Wallet: **not parsed**",
        "",
        "## Attributes / development",
    ]
    for name, value in c["attributes"].items():
        lines.append(f"- {name}: {value}")
    lines += [
        f"- free attribute points: {dev.get('available_attribute_points')}",
        f"- free perk points: {dev.get('available_perk_points')}",
        f"- free Relic points: {dev.get('available_relic_points')}",
        f"- purchased perk nodes/ranks: {dev.get('purchased_perk_count', 0)} / {dev.get('purchased_perk_ranks', 0)}",
        "",
        "## Skills",
    ]
    for skill in dev.get("skills", []):
        lines.append(f"- {skill['name']}: level {skill['level']}, currentExp {skill['exp']} (`{skill['type']}`)")

    lines += ["", "## Purchased perks"]
    for tree in dev.get("perk_trees", []):
        if not tree.get("perks"):
            continue
        lines.append(f"### {tree['name']}")
        for perk in tree["perks"]:
            display = perk.get("name") or perk["id"]
            inferred = " (ID inferred from default enum)" if perk.get("inferred_id") else ""
            lines.append(f"- {display} — rank {perk['rank']}; `{perk['id']}`{inferred}")

    equipment = ctx.get("equipment", {})
    lines += [
        "",
        "## Equipped weapons",
        f"- EquipmentSystem parser: **{equipment.get('parser_status', 'unknown')}**",
    ]
    for item in equipment.get("weapons", []):
        lines.append(f"- {item.get('slot_label')}: **{item.get('name') or item.get('id') or 'unresolved'}** — `{item.get('id') or item.get('tweakdb_value')}`")
    if not equipment.get("weapons"):
        lines.append("- no equipped weapon slots decoded")

    lines += ["", "## Equipped cyberware"]
    for item in equipment.get("cyberware", []):
        lines.append(f"- {item.get('slot_label')}: **{item.get('name') or item.get('id') or 'unresolved'}** — `{item.get('id') or item.get('tweakdb_value')}`")
    if not equipment.get("cyberware"):
        lines.append("- no equipped cyberware slots decoded")

    saved_stats = ctx.get("stats", {})
    health = saved_stats.get("health", {}) or {}
    capacity = saved_stats.get("cyberware_capacity", {}) or {}
    lines += [
        "",
        "## Saved stats",
        f"- StatPoolsSystem parser: **{saved_stats.get('stat_pools_parser_status', 'unknown')}**",
        f"- StatsSystem parser: **{saved_stats.get('stats_system_parser_status', 'unknown')}**",
        f"- Health max: **{health.get('max')}**",
        f"- Health current: **{health.get('current_percent')}%**" if health.get("current_percent") is not None else "- Health current: **not parsed**",
        f"- Health status/source: **{health.get('status', 'unknown')} / {health.get('source') or 'none'}**",
        f"- Health note: {health.get('note') or '—'}",
        f"- StatsSystem record: **{saved_stats.get('stats_system_record_name') or saved_stats.get('stats_system_record_id') or 'unknown'}**",
        f"- Saved Humanity additive: **{saved_stats.get('saved_humanity_additive')}**",
        f"- Effective Cyberware Capacity: **{capacity.get('status', 'not resolved')}**",
        f"- Persisted player stat pools: **{saved_stats.get('saved_stat_pool_count', 0)}**",
    ]
    for pool in saved_stats.get("saved_stat_pools", []):
        lines.append(
            f"- StatPool `{pool.get('type') or '—'}` / `{pool.get('stat') or '—'}` — "
            f"max={pool.get('max_value')}, current={pool.get('current_value')}, "
            f"limit={pool.get('custom_limit_value')}, mode={pool.get('change_mode') or '—'}, "
            f"record={pool.get('record_id') or '—'}"
        )
    known_stats = saved_stats.get("known_saved_stats", [])
    if known_stats:
        lines.append("- Named StatsSystem inputs/modifiers:")
        for row in known_stats:
            lines.append(
                f"  - `{row.get('stat')}` = {row.get('value')} "
                f"({row.get('modifier_type_name') or row.get('modifier_type')}; {row.get('source')})"
            )

    readiness = ctx.get("dont_fear_the_reaper_readiness", {})
    lines += [
        "",
        "## Don't Fear the Reaper readiness",
        f"- overall: **{readiness.get('overall', 'unknown')}**",
        f"- core: **{readiness.get('core_ready', 0)} / {readiness.get('core_total', 0)}**",
        f"- headline: {readiness.get('headline', '')}",
    ]
    for profile in (readiness.get("combat_readiness", {}) or {}).get("profiles", []):
        lines.append(f"- combat profile [{profile.get('status')}]: {profile.get('label')} — {profile.get('evidence')}")
    route = readiness.get("route_eligibility", {}) or {}
    if route:
        lines.append(f"- route eligibility [{route.get('status')}]: {route.get('value')} — {route.get('note')}")
    for row in readiness.get("checks", []):
        lines.append(f"- [{row.get('status')}] {row.get('group')}: {row.get('label')} — {row.get('value')} ({row.get('importance')})")

    inv = ctx["inventory"]
    cat = inv.get("catalog", {})
    lines += [
        "",
        "## Inventory",
        f"- Player inventory records: **{inv['player_parsed_records']} / {inv['player_declared_records']}**",
        f"- All itemData records indexed: **{inv['all_item_records']}**",
        f"- Item catalog: external={cat.get('external_records', 0)}, resolved groups={cat.get('resolved_item_groups', 0)}, unknown groups={cat.get('unknown_item_groups', 0)}",
    ]
    for item in inv["known_items_found"]:
        location = "player inventory" if item["status"] == "player" else "stash" if item["status"] == "stash" else "other inventory container"
        lines.append(f"- {item['name']} — {location}; `{item['id']}`; node(s) {item['node_ids']}")
    if inv.get("resolved_player_items"):
        lines += ["", "### Resolved player item types (up to 250)"]
        for item in inv["resolved_player_items"]:
            lines.append(f"- {item.get('name') or item.get('id')} x{item.get('quantity')} — `{item.get('id')}`")

    lines += ["", "## Ending / route evidence"]
    if ctx["endings"]:
        for ending in ctx["endings"]:
            lines.append(f"- {ending['kind']}: **{ending['ending']} — {ending['name']}**; marker `{ending['marker']}`; saves: {ending['save_count']}")
    else:
        lines.append("- no supported ending marker found in scanned history")

    lines += ["", "## World state / decisions"]
    for item in ctx["world_state"]:
        lines.append(f"- {item['group']}: {item['label']} — `{item['fact']}={item['value']}` (confidence: {item['confidence']})")
    lines += ["", "## Quest tracker"]
    for q in ctx["quest_tracker"]:
        evidence = ", ".join(q["evidence"]) if q["evidence"] else "no supported signal"
        lines.append(f"- [{q['status']}] {q['name']} (`{q['id']}`) — {evidence}")

    quick = ctx.get("quickhacks", {}) or {}
    lines += ["", "## Quickhacks / Cyberdeck", f"- Save: {quick.get('save_name', ctx.get('generated_from'))}"]
    for deck in quick.get("operating_systems", []):
        lines.append(f"- System operacyjny: {deck.get('name') or deck.get('id')}; `{deck.get('id') or deck.get('tweakdb_value')}`")
    lines.append(f"- Osadzone sloty: {quick.get('installed_quickhacks', {}).get('status', 'not-resolved')} — posiadanie nie potwierdza osadzenia.")
    for hack in quick.get("records", []):
        tier = hack.get("tier") if hack.get("tier") is not None else "nieustalona"
        lines.append(f"- [{hack.get('location')}; {hack.get('kind')}] {hack.get('name_pl') or hack.get('name')} — generacja {tier}{' iconic' if hack.get('iconic') else ''}; szt. {hack.get('quantity')}; `{hack.get('id') or hack.get('tweakdb_value')}`; owned={hack.get('owned')}")
    for note in quick.get("notes", []):
        lines.append(f"- {note}")

    choices = ctx.get("quest_choices", {}) or {}
    lines += ["", "## Decyzje i konsekwencje", "", "Konsekwencje poniżej zawierają spoilery. Stan zadania i rozpoznanie ścieżki to osobne informacje."]
    for choice in choices.get("records", []):
        evidence = choice.get("save_evidence", {})
        lines += ["", f"### {choice['title']}", f"- Sygnał: {evidence.get('status', 'unknown')}; dowód: {', '.join(evidence.get('evidence', [])) or 'nie ustalono'}",
                  f"- Trop: {choice['hint']}", "", "<details><summary>Pokaż konsekwencje — spoilery</summary>", "", f"Moment decyzji: {choice['decision_point']}", ""]
        if evidence.get("label"):
            lines.append(f"Ścieżka w tym zapisie: {evidence['label']}")
        for branch in choice.get("branches", []):
            lines += [f"**{branch['label']}**", ""]
            for field, label in (("condition", "Warunek"), ("action", "Co zrobić"), ("immediate", "Od razu"), ("delayed", "Później"), ("reward", "Nagroda")):
                if branch.get(field):
                    lines.append(f"- {label}: {branch[field]}")
            lines.append("")
        for note in choice.get("notes", []):
            lines.append(f"- Uwaga: {note}")
        for source in choice.get("sources", []):
            lines.append(f"- [{source['label']}]({source['url']})")
        lines += ["", "</details>"]
    for note in choices.get("notes", []):
        lines.append(f"- {note}")

    hidden = ctx.get("hidden_encounters", {}) or {}
    lines += ["", "## Hidden Encounters / Ukryte interakcje"]
    counts = hidden.get("counts", {}) or {}
    lines.append(
        f"- dataset: {counts.get('total', len(hidden.get('records', [])))} entries; "
        f"unknown={counts.get('unknown', 0)}, discovered={counts.get('discovered', 0)}, completed={counts.get('completed', 0)}"
    )
    for encounter in hidden.get("records", []):
        rel = encounter.get("related_activity", {}) or {}
        verification = encounter.get("verification", {}) or {}
        lines.append(
            f"- [{encounter.get('user_status', 'unknown')}] {encounter.get('subdistrict') or encounter.get('district')} — "
            f"{encounter.get('title')}: {encounter.get('hint')} "
            f"(type={encounter.get('interaction_type')}, related={rel.get('name') or 'none'}, verification={verification.get('status', 'unverified')})"
        )

    lines += ["", "## Iconic Weapons"]
    for weapon in ctx.get("iconic_weapons", {}).get("records", []):
        lines.append(f"- [{weapon['status']}] {weapon['name']} — {weapon['location']}")
        guide = weapon.get("guide", {})
        lines.append(f"  - Jak zdobyć: {weapon.get('acquisition', '')}")
        lines.append(f"  - Weryfikacja opisu: {guide.get('verification', 'needs_verification')}; dostępność w zapisie: nie oceniono.")
        for field, label in (("quest", "Zadanie"), ("npc", "NPC"), ("fast_travel", "Szybka podróż"), ("conditions", "Warunki")):
            if guide.get(field):
                lines.append(f"  - {label}: {guide[field]}")
        for link in guide.get("sources", []) + guide.get("map_links", []):
            lines.append(f"  - [{link['label']}]({link['url']})")

    lines += ["", "## Parser", f"- {ctx['binary_parser']}", ""]
    return "\n".join(lines)
