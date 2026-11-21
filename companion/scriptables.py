"""Minimal read-only decoder for PlayerDevelopmentData in ScriptableSystemsContainer.

The implementation intentionally decodes only the RED package primitives needed by
CP2077 2.x player-development data.  It never writes or reserializes the save.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any


class ScriptableDecodeError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScriptableObject:
    name: str
    data: bytes


@dataclass(frozen=True)
class PlayerDevelopmentSummary:
    status: str
    package_object_count: int
    package_string_count: int
    attributes: dict[str, int]
    development_points: tuple[dict[str, Any], ...]
    available_attribute_points: int
    available_perk_points: int
    available_relic_points: int
    proficiencies: tuple[dict[str, Any], ...]
    skills: tuple[dict[str, Any], ...]
    perk_trees: tuple[dict[str, Any], ...]
    purchased_perk_count: int
    purchased_perk_ranks: int


_FIXED = {
    "Bool": 1,
    "Int32": 4,
    "Uint32": 4,
    "Uint16": 2,
    "Uint8": 1,
    "Float": 4,
    "Uint64": 8,
    "Int64": 8,
    "TweakDBID": 8,
    "CName": 8,
}


def _is_enum(type_name: str) -> bool:
    return type_name.startswith("gamedata") or type_name.startswith("E")


def _primitive(type_name: str, raw: bytes, strings: list[str]) -> Any:
    if type_name == "Bool":
        return bool(raw[0]) if raw else False
    if type_name == "Int32":
        return struct.unpack_from("<i", raw, 0)[0]
    if type_name == "Uint32":
        return struct.unpack_from("<I", raw, 0)[0]
    if type_name == "Uint16":
        return struct.unpack_from("<H", raw, 0)[0]
    if type_name == "Uint8":
        return raw[0]
    if type_name == "Float":
        return struct.unpack_from("<f", raw, 0)[0]
    if type_name == "Uint64":
        return struct.unpack_from("<Q", raw, 0)[0]
    if type_name == "Int64":
        return struct.unpack_from("<q", raw, 0)[0]
    if type_name in ("TweakDBID", "CName"):
        return f"0x{struct.unpack_from('<Q', raw, 0)[0]:016X}"
    if _is_enum(type_name):
        idx = struct.unpack_from("<H", raw, 0)[0]
        return strings[idx] if idx < len(strings) else f"#{idx}"
    return raw


def _value_size(type_name: str, data: bytes, pos: int, strings: list[str]) -> int:
    if type_name in _FIXED:
        return _FIXED[type_name]
    if _is_enum(type_name):
        return 2
    if type_name.startswith("array:"):
        _, consumed = _parse_array(type_name[6:], data, pos, strings)
        return consumed
    if type_name == "entEntityID":
        return 18
    raise ScriptableDecodeError(f"unsupported RED package type {type_name!r}")


def _parse_struct(data: bytes, pos: int, strings: list[str]) -> tuple[dict[str, Any], int]:
    start = pos
    if pos + 2 > len(data):
        raise ScriptableDecodeError("truncated struct")
    field_count = struct.unpack_from("<H", data, pos)[0]
    pos += 2
    if pos + field_count * 8 > len(data):
        raise ScriptableDecodeError("truncated field table")

    desc: list[tuple[str, str, int]] = []
    for _ in range(field_count):
        name_i, type_i, offset = struct.unpack_from("<HHI", data, pos)
        pos += 8
        if name_i >= len(strings) or type_i >= len(strings):
            raise ScriptableDecodeError("field string index outside package string table")
        desc.append((strings[name_i], strings[type_i], offset))

    fields: dict[str, Any] = {}
    max_end = 2 + field_count * 8
    for index, (name, type_name, offset) in enumerate(desc):
        field_pos = start + offset
        if field_pos > len(data):
            raise ScriptableDecodeError("field offset outside struct")

        if index + 1 < len(desc):
            next_pos = start + desc[index + 1][2]
            if next_pos < field_pos or next_pos > len(data):
                raise ScriptableDecodeError("invalid field boundary")
            raw = data[field_pos:next_pos]
            if type_name.startswith("array:"):
                value, consumed = _parse_array(type_name[6:], data, field_pos, strings)
            else:
                value = _primitive(type_name, raw, strings)
                consumed = len(raw)
        else:
            consumed = _value_size(type_name, data, field_pos, strings)
            if type_name.startswith("array:"):
                value, consumed = _parse_array(type_name[6:], data, field_pos, strings)
            else:
                value = _primitive(type_name, data[field_pos:field_pos + consumed], strings)

        fields[name] = value
        max_end = max(max_end, offset + consumed)
    return fields, max_end


def _parse_array(item_type: str, data: bytes, pos: int, strings: list[str]) -> tuple[list[Any], int]:
    start = pos
    if pos + 4 > len(data):
        raise ScriptableDecodeError("truncated array")
    count = struct.unpack_from("<I", data, pos)[0]
    pos += 4
    if count > 100_000:
        raise ScriptableDecodeError(f"unreasonable array count {count}")

    values: list[Any] = []
    if item_type.startswith("handle:"):
        need = count * 4
        if pos + need > len(data):
            raise ScriptableDecodeError("truncated handle array")
        for _ in range(count):
            values.append(struct.unpack_from("<I", data, pos)[0])
            pos += 4
    elif item_type in _FIXED or _is_enum(item_type):
        size = _FIXED.get(item_type, 2)
        if pos + count * size > len(data):
            raise ScriptableDecodeError("truncated primitive array")
        for _ in range(count):
            values.append(_primitive(item_type, data[pos:pos + size], strings))
            pos += size
    else:
        for _ in range(count):
            value, consumed = _parse_struct(data, pos, strings)
            if consumed <= 0:
                raise ScriptableDecodeError("zero-length struct in array")
            values.append(value)
            pos += consumed
    return values, pos - start


def _parse_package(payload: bytes) -> tuple[list[str], list[ScriptableObject]]:
    if len(payload) < 32:
        raise ScriptableDecodeError("ScriptableSystemsContainer package is too short")
    _, total_size = struct.unpack_from("<II", payload, 0)
    if total_size != len(payload) - 8:
        raise ScriptableDecodeError("RED package size mismatch")

    _, package_version = struct.unpack_from("<II", payload, 8)
    string_index_start, string_index_end = struct.unpack_from("<II", payload, 16)
    data_index_start, data_index_end = struct.unpack_from("<II", payload, 24)
    base = 32

    # Newer RED packages can carry an import/ref table before the indexed data.
    if package_version >= 2:
        if base + 4 > len(payload):
            raise ScriptableDecodeError("truncated package ref table")
        ref_count = struct.unpack_from("<I", payload, base)[0]
        base += 4 + ref_count * 8
        if base > len(payload):
            raise ScriptableDecodeError("package ref table outside payload")

    data = payload[base:]
    if string_index_start != 0 or string_index_end < string_index_start or string_index_end % 4:
        raise ScriptableDecodeError("unsupported package string index")

    strings: list[str] = []
    string_pos = string_index_end
    for index_pos in range(string_index_start, string_index_end, 4):
        packed = struct.unpack_from("<I", data, index_pos)[0]
        expected_pos = packed & 0x00FFFFFF
        length = packed >> 24
        if expected_pos != string_pos or not length or string_pos + length > len(data):
            raise ScriptableDecodeError("invalid package string table")
        raw = data[string_pos:string_pos + length - 1]
        strings.append(raw.decode("utf-8", errors="replace"))
        string_pos += length

    if data_index_start != string_pos or data_index_end < data_index_start or (data_index_end - data_index_start) % 8:
        raise ScriptableDecodeError("invalid package object index")

    object_index: list[tuple[int, int]] = []
    for pos in range(data_index_start, data_index_end, 8):
        name_index, offset = struct.unpack_from("<II", data, pos)
        if name_index >= len(strings) or offset > len(data):
            raise ScriptableDecodeError("object index outside package")
        object_index.append((name_index, offset))

    objects: list[ScriptableObject] = []
    for i, (name_index, offset) in enumerate(object_index):
        end = object_index[i + 1][1] if i + 1 < len(object_index) else len(data)
        if end < offset:
            raise ScriptableDecodeError("negative object span")
        objects.append(ScriptableObject(strings[name_index], data[offset:end]))
    return strings, objects


_ATTRIBUTE_NAMES = {
    "Strength": "body",
    "Reflexes": "reflexes",
    "TechnicalAbility": "technical_ability",
    "Intelligence": "intelligence",
    "Cool": "cool",
}

_SKILL_NAMES = {
    "CoolSkill": "Headhunter",
    "IntelligenceSkill": "Netrunner",
    "ReflexesSkill": "Shinobi",
    "StrengthSkill": "Solo",
    "TechnicalAbilitySkill": "Engineer",
}

_TREE_NAMES = {
    "BodyAttributeData": "Body",
    "CoolAttributeData": "Cool",
    "IntelligenceAttributeData": "Intelligence",
    "ReflexesAttributeData": "Reflexes",
    "TechnicalAbilityAttributeData": "Technical Ability",
    "EspionageAttributeData": "Relic",
}


def _dev_point_type(row: dict[str, Any], index: int) -> str:
    # The Attribute entry is serialized with its default enum value omitted.
    if row.get("type"):
        return str(row["type"])
    return "Attribute" if index == 0 else "Unknown"


def _tree_name(row: dict[str, Any]) -> str:
    raw = str(row.get("type") or "")
    if raw:
        return _TREE_NAMES.get(raw, raw)
    # BodyAttributeData often serializes as the default type and therefore has
    # no explicit type field.  Its perk identifiers give an unambiguous hint.
    perks = row.get("unlockedPerks") or []
    if any(str(p.get("type") or "").startswith("Body_") for p in perks):
        return "Body"
    return "Unknown"


def parse_player_development(payload: bytes, perk_names: dict[str, str] | None = None) -> PlayerDevelopmentSummary:
    perk_names = perk_names or {}
    strings, objects = _parse_package(payload)
    pdd = next((obj for obj in objects if obj.name == "PlayerDevelopmentData"), None)
    if pdd is None:
        raise ScriptableDecodeError("PlayerDevelopmentData not found")

    fields, _ = _parse_struct(pdd.data, 0, strings)

    attributes_raw = fields.get("attributes") or []
    attributes: dict[str, int] = {}
    for row in attributes_raw:
        internal = str(row.get("attributeName") or "")
        if internal in _ATTRIBUTE_NAMES and "value" in row:
            attributes[_ATTRIBUTE_NAMES[internal]] = int(row["value"])

    dev_rows: list[dict[str, Any]] = []
    available = {"Attribute": 0, "Primary": 0, "Espionage": 0}
    for index, row in enumerate(fields.get("devPoints") or []):
        point_type = _dev_point_type(row, index)
        normalized = {
            "type": point_type,
            "spent": int(row.get("spent", 0) or 0),
            "unspent": int(row.get("unspent", 0) or 0),
        }
        dev_rows.append(normalized)
        if point_type in available:
            available[point_type] = normalized["unspent"]

    prof_rows: list[dict[str, Any]] = []
    skill_rows: list[dict[str, Any]] = []
    for row in fields.get("proficiencies") or []:
        internal = str(row.get("type") or "")
        normalized = {
            "type": internal or "default",
            "level": int(row.get("currentLevel", 0) or 0),
            "max_level": int(row.get("maxLevel", 0) or 0),
            "exp": int(row.get("currentExp", 0) or 0),
        }
        prof_rows.append(normalized)
        if internal in _SKILL_NAMES:
            skill_rows.append({**normalized, "name": _SKILL_NAMES[internal]})

    tree_rows: list[dict[str, Any]] = []
    purchased_count = 0
    purchased_ranks = 0
    for row in fields.get("attributesData") or []:
        tree_name = _tree_name(row)
        perks: list[dict[str, Any]] = []
        for perk in row.get("unlockedPerks") or []:
            rank = int(perk.get("currLevel", 0) or 0)
            if rank <= 0:
                continue
            internal = str(perk.get("type") or "")
            inferred = False
            # In 2.x Body_Central_Milestone_1 is the default enum value and can
            # be omitted from the serialized struct. The surrounding tree and
            # rank make this particular default deterministic.
            if not internal and tree_name == "Body":
                internal = "Body_Central_Milestone_1"
                inferred = True
            perk_row = {
                "id": internal or "[default/unknown]",
                "name": perk_names.get(internal) if internal else None,
                "rank": rank,
                "inferred_id": inferred,
            }
            perks.append(perk_row)
            purchased_count += 1
            purchased_ranks += rank
        tree_rows.append({
            "name": tree_name,
            "raw_type": str(row.get("type") or "[default]"),
            "perks": perks,
            "purchased_count": len(perks),
            "purchased_ranks": sum(int(x["rank"]) for x in perks),
        })

    return PlayerDevelopmentSummary(
        status="ok",
        package_object_count=len(objects),
        package_string_count=len(strings),
        attributes=attributes,
        development_points=tuple(dev_rows),
        available_attribute_points=available["Attribute"],
        available_perk_points=available["Primary"],
        available_relic_points=available["Espionage"],
        proficiencies=tuple(prof_rows),
        skills=tuple(skill_rows),
        perk_trees=tuple(tree_rows),
        purchased_perk_count=purchased_count,
        purchased_perk_ranks=purchased_ranks,
    )
