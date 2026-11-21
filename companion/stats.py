"""Read-only player StatsSystem parser for CP2077 2.x.

The save stores a ``gameStatsStateMapStructure`` keyed by ``gameStatsObjectID``.
This module locates the player's EntityID=1 record and exposes conservative
saved-stat evidence.  It intentionally does *not* pretend to reproduce the
engine's full derived-stat calculation.

Important for v0.5.4: the player's *current/max Health* is a StatPool value.
``StatsSystem`` stores inputs/modifiers (attributes, progression, Humanity,
etc.), not a materialized derived Max Health number.  We therefore expose
Health/MaxHealth modifier evidence if present, but never label a modifier as
an exact current/max Health fallback.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from typing import Any

from .scriptables import ScriptableDecodeError, _parse_package


class StatsDecodeError(ScriptableDecodeError):
    pass


@dataclass(frozen=True)
class StatsSummary:
    status: str
    player_owner_hash: int
    player_index: int
    record_id: int | None
    record_name: str | None
    seed: int | None
    inactive_stats: tuple[str, ...]
    modifiers: tuple[dict[str, Any], ...]
    forced_modifiers: tuple[dict[str, Any], ...]
    humanity_additive: float | None
    known_saved_stats: tuple[dict[str, Any], ...]
    health_modifier_evidence: tuple[dict[str, Any], ...]


_FIXED = {
    "Bool": 1, "Int32": 4, "Uint32": 4, "Uint16": 2, "Uint8": 1,
    "Float": 4, "Uint64": 8, "Int64": 8, "TweakDBID": 8, "CName": 8,
}


def fnv1a64(value: str) -> int:
    h = 0xCBF29CE484222325
    for byte in value.encode("utf-8"):
        h ^= byte
        h = (h * 0x100000001B3) & 0xFFFFFFFFFFFFFFFF
    return h


# Names confirmed against 2.x player StatsSystem samples.  REDengine serializes
# gamedataStatType here as the 64-bit FNV-1a of the enum name.
_KNOWN_STATS = (
    "Humanity",
    "Health",
    "MaxHealth",
    "Level",
    "StreetCred",
    "Strength",              # UI label: Body
    "Reflexes",
    "TechnicalAbility",
    "Cool",
    "Intelligence",
    "StrengthSkill",         # UI label: Solo
    "ReflexesSkill",         # UI label: Shinobi
    "TechnicalAbilitySkill", # UI label: Engineer
    "CoolSkill",             # UI label: Headhunter
    "IntelligenceSkill",     # UI label: Netrunner
    "Memory",
    "Armor",
)
_STAT_NAMES_BY_HASH = {fnv1a64(name): name for name in _KNOWN_STATS}

# Player StatsSystem record in the supplied unmodded 2.31 saves.
_PLAYER_PUPPET_BASE_ID = 0x0000001C15982ADF  # TDBID("Character.Player_Puppet_Base")
_RECORD_NAMES = {
    _PLAYER_PUPPET_BASE_ID: "Character.Player_Puppet_Base",
}

_MODIFIER_TYPE_NAMES = {
    0: "Additive",
    1: "Multiplier",
    2: "AdditiveMultiplier",
}


def _is_enum(type_name: str) -> bool:
    return type_name.startswith("gamedata") or type_name.startswith("gameStatIDType") or type_name.startswith("E")


def _descriptors(data: bytes, pos: int, strings: list[str]) -> list[tuple[str, str, int]]:
    if pos + 2 > len(data):
        raise StatsDecodeError("truncated struct")
    count = struct.unpack_from("<H", data, pos)[0]
    if count > 512 or pos + 2 + count * 8 > len(data):
        raise StatsDecodeError("invalid struct descriptor table")
    out = []
    for i in range(count):
        ni, ti, off = struct.unpack_from("<HHI", data, pos + 2 + i * 8)
        if ni >= len(strings) or ti >= len(strings):
            raise StatsDecodeError("descriptor string index outside package")
        out.append((strings[ni], strings[ti], off))
    return out


def _type_size(type_name: str, data: bytes, pos: int, strings: list[str], depth: int = 0) -> int:
    if depth > 20:
        raise StatsDecodeError("nested StatsSystem structure too deep")
    if type_name in _FIXED:
        return _FIXED[type_name]
    if _is_enum(type_name):
        return 2
    if type_name == "DataBuffer":
        if pos + 4 > len(data):
            raise StatsDecodeError("truncated DataBuffer")
        length = struct.unpack_from("<I", data, pos)[0]
        if pos + 4 + length > len(data):
            raise StatsDecodeError("DataBuffer outside StatsSystem")
        return 4 + length
    if type_name.startswith("array:"):
        item_type = type_name[6:]
        count = struct.unpack_from("<I", data, pos)[0]
        if count > 100_000:
            raise StatsDecodeError(f"unreasonable array count {count}")
        q = pos + 4
        if item_type in _FIXED or _is_enum(item_type):
            return 4 + count * _FIXED.get(item_type, 2)
        for _ in range(count):
            q += _struct_size(data, q, strings, depth + 1)
        return q - pos
    return _struct_size(data, pos, strings, depth + 1)


def _struct_size(data: bytes, pos: int, strings: list[str], depth: int = 0) -> int:
    desc = _descriptors(data, pos, strings)
    max_end = 2 + len(desc) * 8
    for i, (_, type_name, offset) in enumerate(desc):
        if i + 1 < len(desc):
            consumed = desc[i + 1][2] - offset
            if consumed < 0:
                raise StatsDecodeError("invalid StatsSystem field boundary")
        else:
            consumed = _type_size(type_name, data, pos + offset, strings, depth + 1)
        max_end = max(max_end, offset + consumed)
    return max_end


def _enum(data: bytes, pos: int, strings: list[str]) -> str:
    idx = struct.unpack_from("<H", data, pos)[0]
    return strings[idx] if idx < len(strings) else f"#{idx}"


def _stats_object_id(data: bytes, pos: int, strings: list[str]) -> tuple[dict[str, Any], int]:
    desc = _descriptors(data, pos, strings)
    size = _struct_size(data, pos, strings)
    out: dict[str, Any] = {}
    for name, type_name, offset in desc:
        p = pos + offset
        if type_name == "Uint64":
            out[name] = struct.unpack_from("<Q", data, p)[0]
        elif _is_enum(type_name):
            out[name] = _enum(data, p, strings)
    return out, size


def _decode_modifier_buffer(raw: bytes) -> tuple[dict[str, Any], ...]:
    """Decode validated constant-stat entries; preserve only synchronized rows.

    CP2077 2.31 serializes ``gameConstantStatModifier`` entries as 41-byte
    records: class marker + 64-bit FNV stat name + modifier kind + float.
    Other modifier classes are deliberately not guessed.
    """
    if len(raw) < 4:
        return ()
    length = struct.unpack_from("<I", raw, 0)[0]
    payload = raw[4:4 + length]
    if len(payload) != length:
        return ()
    marker = b"\x98gameConstantStatModifier"
    entry_size = 41
    if len(payload) // entry_size > 100_000:
        raise StatsDecodeError("Saved stat modifier list exceeds the supported limit")
    out: list[dict[str, Any]] = []
    pos = 0
    while pos + entry_size <= len(payload):
        entry = payload[pos:pos + entry_size]
        if not entry.startswith(marker):
            # Unknown modifier class/encoding: stop rather than desynchronize.
            break
        stat_hash = struct.unpack_from("<Q", entry, 25)[0]
        modifier_type = struct.unpack_from("<I", entry, 33)[0]
        value = float(struct.unpack_from("<f", entry, 37)[0])
        if not math.isfinite(value):
            raise StatsDecodeError("Non-finite saved stat modifier")
        out.append({
            "class": "gameConstantStatModifier",
            "stat_hash": f"{stat_hash:016X}",
            "stat": _STAT_NAMES_BY_HASH.get(stat_hash),
            "modifier_type": modifier_type,
            "modifier_type_name": _MODIFIER_TYPE_NAMES.get(modifier_type),
            "value": value,
        })
        pos += entry_size
    return tuple(out)


def _known_saved_stats(modifiers: tuple[dict[str, Any], ...], forced: tuple[dict[str, Any], ...]) -> tuple[dict[str, Any], ...]:
    """Return named, directly persisted stat modifiers as transparent evidence.

    These are *inputs/modifiers*, not engine-derived final values.  Forced
    modifiers are especially useful because player level/attributes/skills are
    persisted there in supplied 2.31 saves.
    """
    out: list[dict[str, Any]] = []
    for source, rows in (("modifiers", modifiers), ("forcedModifiers", forced)):
        for row in rows:
            if not row.get("stat"):
                continue
            out.append({
                "source": source,
                "stat": row.get("stat"),
                "stat_hash": row.get("stat_hash"),
                "modifier_type": row.get("modifier_type"),
                "modifier_type_name": row.get("modifier_type_name"),
                "value": row.get("value"),
            })
    return tuple(out)


def parse_stats(payload: bytes, player_owner_hash: int = 1) -> StatsSummary:
    strings, objects = _parse_package(payload)
    if not objects or objects[0].name != "gameStatsStateMapStructure":
        raise StatsDecodeError("gameStatsStateMapStructure root not found")
    root = objects[0].data
    desc = _descriptors(root, 0, strings)
    fields = {name: (type_name, offset) for name, type_name, offset in desc}
    if fields.get("keys", (None,))[0] != "array:gameStatsObjectID" or fields.get("values", (None,))[0] != "array:gameSavedStatsData":
        raise StatsDecodeError("StatsSystem keys/values fields missing or unexpected")

    keys_pos = fields["keys"][1]
    key_count = struct.unpack_from("<I", root, keys_pos)[0]
    q = keys_pos + 4
    player_index: int | None = None
    for index in range(key_count):
        key, consumed = _stats_object_id(root, q, strings)
        if key.get("idType") == "EntityID" and int(key.get("entityHash", -1)) == player_owner_hash:
            player_index = index
        q += consumed
    if player_index is None:
        raise StatsDecodeError(f"player StatsSystem EntityID={player_owner_hash} not found")

    values_pos = fields["values"][1]
    value_count = struct.unpack_from("<I", root, values_pos)[0]
    if value_count != key_count:
        raise StatsDecodeError(f"StatsSystem keys/values count mismatch: {key_count}/{value_count}")
    q = values_pos + 4
    for _ in range(player_index):
        q += _struct_size(root, q, strings)

    value_pos = q
    value_desc = _descriptors(root, value_pos, strings)
    value_fields = {name: (type_name, offset) for name, type_name, offset in value_desc}

    modifiers: tuple[dict[str, Any], ...] = ()
    forced: tuple[dict[str, Any], ...] = ()
    inactive: list[str] = []
    record_id: int | None = None
    seed: int | None = None

    for name, (type_name, offset) in value_fields.items():
        p = value_pos + offset
        if type_name == "DataBuffer":
            size = _type_size(type_name, root, p, strings)
            decoded = _decode_modifier_buffer(root[p:p + size])
            if name == "modifiersBuffer":
                modifiers = decoded
            elif name == "forcedModifiersBuffer":
                forced = decoded
        elif name == "inactiveStats" and type_name == "array:gamedataStatType":
            count = struct.unpack_from("<I", root, p)[0]
            p += 4
            if count > 100_000 or count > (len(root) - p) // 2:
                raise StatsDecodeError("Invalid inactive stat list")
            for _ in range(count):
                inactive.append(_enum(root, p, strings))
                p += 2
        elif name == "recordID" and type_name == "TweakDBID":
            record_id = struct.unpack_from("<Q", root, p)[0]
        elif name == "seed" and type_name == "Uint32":
            seed = struct.unpack_from("<I", root, p)[0]

    humanity_values = [
        float(x["value"])
        for x in modifiers
        if x.get("stat") == "Humanity" and int(x.get("modifier_type", -1)) == 0
    ]
    humanity_additive = sum(humanity_values) if humanity_values else None
    known = _known_saved_stats(modifiers, forced)
    health_evidence = tuple(x for x in known if x.get("stat") in {"Health", "MaxHealth"})

    return StatsSummary(
        status="ok",
        player_owner_hash=player_owner_hash,
        player_index=player_index,
        record_id=record_id,
        record_name=_RECORD_NAMES.get(record_id) if record_id is not None else None,
        seed=seed,
        inactive_stats=tuple(inactive),
        modifiers=modifiers,
        forced_modifiers=forced,
        humanity_additive=humanity_additive,
        known_saved_stats=known,
        health_modifier_evidence=health_evidence,
    )
