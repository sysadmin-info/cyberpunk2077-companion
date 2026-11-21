"""Read-only decoder for the player's EquipmentSystem loadout.

CP2077 stores equipped weapons/cyberware in ``EquipmentSystem`` inside the
``ScriptableSystemsContainer`` RED package.  This module deliberately reads only
that structure; it never mutates or reserializes save data.
"""
from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Any

from .scriptables import ScriptableDecodeError, _parse_package, _parse_struct


class EquipmentDecodeError(ScriptableDecodeError):
    pass


@dataclass(frozen=True)
class EquippedItem:
    area_type: str
    slot_index: int
    tweakdb_value: int
    tweakdb_hash: int
    tweakdb_length: int
    rng_seed: int | None
    active_index: int | None = None


@dataclass(frozen=True)
class EquipmentSummary:
    status: str
    player_owner_hash: int
    area_count: int
    items: tuple[EquippedItem, ...]
    weapons: tuple[EquippedItem, ...]
    cyberware: tuple[EquippedItem, ...]


_CYBERWARE_AREAS = {
    "EyesCW",
    "FrontalCortexCW",
    "MusculoskeletalSystemCW",
    "NervousSystemCW",
    "CardiovascularSystemCW",
    "ImmuneSystemCW",
    "IntegumentarySystemCW",
    "HandsCW",
    "ArmsCW",
    "LegsCW",
    "AbilityCW",
    "SystemReplacementCW",
}


def _descriptors(data: bytes, pos: int, strings: list[str]) -> list[tuple[str, str, int]]:
    if pos + 2 > len(data):
        raise EquipmentDecodeError("truncated struct")
    field_count = struct.unpack_from("<H", data, pos)[0]
    if field_count > 512 or pos + 2 + field_count * 8 > len(data):
        raise EquipmentDecodeError("invalid struct field table")
    out: list[tuple[str, str, int]] = []
    for index in range(field_count):
        name_i, type_i, offset = struct.unpack_from("<HHI", data, pos + 2 + index * 8)
        if name_i >= len(strings) or type_i >= len(strings):
            raise EquipmentDecodeError("field string index outside package")
        out.append((strings[name_i], strings[type_i], offset))
    return out


def _field_span(data: bytes, pos: int, desc: list[tuple[str, str, int]], index: int) -> tuple[int, int | None]:
    start = pos + desc[index][2]
    end = pos + desc[index + 1][2] if index + 1 < len(desc) else None
    if start > len(data) or (end is not None and (end < start or end > len(data))):
        raise EquipmentDecodeError("invalid field boundary")
    return start, end


def _entity_hash(raw: bytes, strings: list[str]) -> int | None:
    try:
        fields, _ = _parse_struct(raw, 0, strings)
    except ScriptableDecodeError:
        return None
    value = fields.get("hash")
    return int(value) if isinstance(value, int) else None


def _parse_game_item_id(data: bytes, pos: int, strings: list[str]) -> tuple[dict[str, int], int]:
    desc = _descriptors(data, pos, strings)
    max_end = 2 + len(desc) * 8
    values: dict[str, int] = {}
    for index, (name, type_name, offset) in enumerate(desc):
        field_pos, next_pos = _field_span(data, pos, desc, index)
        if type_name == "TweakDBID":
            if field_pos + 8 > len(data):
                raise EquipmentDecodeError("truncated gameItemID TweakDBID")
            values[name] = struct.unpack_from("<Q", data, field_pos)[0]
            consumed = 8
        elif type_name == "Uint32":
            if field_pos + 4 > len(data):
                raise EquipmentDecodeError("truncated gameItemID Uint32")
            values[name] = struct.unpack_from("<I", data, field_pos)[0]
            consumed = 4
        elif type_name == "Uint16":
            if field_pos + 2 > len(data):
                raise EquipmentDecodeError("truncated gameItemID Uint16")
            values[name] = struct.unpack_from("<H", data, field_pos)[0]
            consumed = 2
        elif next_pos is not None:
            consumed = next_pos - field_pos
        else:
            raise EquipmentDecodeError(f"unsupported gameItemID field {name}:{type_name}")
        max_end = max(max_end, offset + consumed)
    return values, max_end


def _parse_slot(data: bytes, pos: int, strings: list[str]) -> tuple[dict[str, Any], int]:
    desc = _descriptors(data, pos, strings)
    max_end = 2 + len(desc) * 8
    values: dict[str, Any] = {}
    for index, (name, type_name, offset) in enumerate(desc):
        field_pos, next_pos = _field_span(data, pos, desc, index)
        if name == "itemID" and type_name == "gameItemID":
            item, consumed = _parse_game_item_id(data, field_pos, strings)
            values[name] = item
        elif next_pos is not None:
            consumed = next_pos - field_pos
        else:
            # Empty/default slots commonly serialize as a zero-field gameItemID;
            # anything else at the tail would be a format change we should not guess.
            raise EquipmentDecodeError(f"unsupported gameSEquipSlot field {name}:{type_name}")
        max_end = max(max_end, offset + consumed)
    return values, max_end


def _parse_area(data: bytes, pos: int, strings: list[str]) -> tuple[dict[str, Any], int]:
    desc = _descriptors(data, pos, strings)
    max_end = 2 + len(desc) * 8
    values: dict[str, Any] = {"equipSlots": []}

    for index, (name, type_name, offset) in enumerate(desc):
        field_pos, next_pos = _field_span(data, pos, desc, index)
        if name == "areaType" and type_name == "gamedataEquipmentArea":
            if field_pos + 2 > len(data):
                raise EquipmentDecodeError("truncated equipment area enum")
            enum_index = struct.unpack_from("<H", data, field_pos)[0]
            values[name] = strings[enum_index] if enum_index < len(strings) else f"#{enum_index}"
            consumed = 2
        elif name == "equipSlots" and type_name == "array:gameSEquipSlot":
            if field_pos + 4 > len(data):
                raise EquipmentDecodeError("truncated equipSlots array")
            count = struct.unpack_from("<I", data, field_pos)[0]
            if count > 128:
                raise EquipmentDecodeError(f"unreasonable equip slot count {count}")
            q = field_pos + 4
            slots: list[dict[str, Any]] = []
            for _ in range(count):
                slot, slot_size = _parse_slot(data, q, strings)
                if slot_size <= 0:
                    raise EquipmentDecodeError("zero-length equip slot")
                slots.append(slot)
                q += slot_size
            values[name] = slots
            consumed = q - field_pos
        elif type_name == "Int32":
            if field_pos + 4 > len(data):
                raise EquipmentDecodeError("truncated Int32 in equip area")
            values[name] = struct.unpack_from("<i", data, field_pos)[0]
            consumed = 4
        elif type_name == "Uint32":
            if field_pos + 4 > len(data):
                raise EquipmentDecodeError("truncated Uint32 in equip area")
            values[name] = struct.unpack_from("<I", data, field_pos)[0]
            consumed = 4
        elif type_name == "Bool":
            if field_pos >= len(data):
                raise EquipmentDecodeError("truncated Bool in equip area")
            values[name] = bool(data[field_pos])
            consumed = 1
        elif next_pos is not None:
            consumed = next_pos - field_pos
        else:
            raise EquipmentDecodeError(f"unsupported gameSEquipArea field {name}:{type_name}")
        max_end = max(max_end, offset + consumed)
    return values, max_end


def _parse_loadout(raw: bytes, strings: list[str]) -> list[dict[str, Any]]:
    desc = _descriptors(raw, 0, strings)
    equip = next(((i, row) for i, row in enumerate(desc) if row[0] == "equipAreas"), None)
    if equip is None:
        raise EquipmentDecodeError("gameSLoadout.equipAreas not found")
    index, (_, type_name, _) = equip
    if type_name != "array:gameSEquipArea":
        raise EquipmentDecodeError(f"unexpected equipAreas type {type_name}")
    field_pos, _ = _field_span(raw, 0, desc, index)
    if field_pos + 4 > len(raw):
        raise EquipmentDecodeError("truncated equipAreas")
    count = struct.unpack_from("<I", raw, field_pos)[0]
    if count > 128:
        raise EquipmentDecodeError(f"unreasonable equipment area count {count}")
    q = field_pos + 4
    areas: list[dict[str, Any]] = []
    for _ in range(count):
        area, consumed = _parse_area(raw, q, strings)
        if consumed <= 0:
            raise EquipmentDecodeError("zero-length equipment area")
        areas.append(area)
        q += consumed
    return areas


def parse_equipment(payload: bytes, player_owner_hash: int = 1) -> EquipmentSummary:
    strings, objects = _parse_package(payload)
    system = next((obj for obj in objects if obj.name == "EquipmentSystem"), None)
    if system is None:
        raise EquipmentDecodeError("EquipmentSystem not found")

    fields, _ = _parse_struct(system.data, 0, strings)
    handles = fields.get("ownerData") or []
    player_obj = None
    player_hash = None

    for handle in handles:
        if not isinstance(handle, int) or handle < 0 or handle >= len(objects):
            continue
        obj = objects[handle]
        if obj.name != "EquipmentSystemPlayerData":
            continue
        desc = _descriptors(obj.data, 0, strings)
        owner_row = next(((i, row) for i, row in enumerate(desc) if row[0] == "ownerID"), None)
        if owner_row is None:
            continue
        owner_index, _ = owner_row
        owner_pos, owner_end = _field_span(obj.data, 0, desc, owner_index)
        if owner_end is None:
            continue
        owner_hash = _entity_hash(obj.data[owner_pos:owner_end], strings)
        if owner_hash == player_owner_hash:
            player_obj = obj
            player_hash = owner_hash
            break

    if player_obj is None:
        raise EquipmentDecodeError(f"EquipmentSystemPlayerData owner hash {player_owner_hash} not found")

    desc = _descriptors(player_obj.data, 0, strings)
    equipment_row = next(((i, row) for i, row in enumerate(desc) if row[0] == "equipment"), None)
    if equipment_row is None:
        raise EquipmentDecodeError("EquipmentSystemPlayerData.equipment not found")
    equipment_index, (_, equipment_type, _) = equipment_row
    if equipment_type != "gameSLoadout":
        raise EquipmentDecodeError(f"unexpected equipment field type {equipment_type}")
    equipment_pos, equipment_end = _field_span(player_obj.data, 0, desc, equipment_index)
    if equipment_end is None:
        raise EquipmentDecodeError("cannot determine gameSLoadout boundary")

    areas = _parse_loadout(player_obj.data[equipment_pos:equipment_end], strings)
    items: list[EquippedItem] = []
    for area in areas:
        area_type = str(area.get("areaType") or "Unknown")
        active_index = area.get("activeIndex")
        for slot_index, slot in enumerate(area.get("equipSlots") or []):
            item_id = slot.get("itemID") or {}
            tweakdb_value = int(item_id.get("id", 0) or 0)
            if tweakdb_value == 0:
                continue
            items.append(EquippedItem(
                area_type=area_type,
                slot_index=slot_index,
                tweakdb_value=tweakdb_value,
                tweakdb_hash=tweakdb_value & 0xFFFFFFFF,
                tweakdb_length=(tweakdb_value >> 32) & 0xFF,
                rng_seed=int(item_id["rngSeed"]) if "rngSeed" in item_id else None,
                active_index=int(active_index) if isinstance(active_index, int) else None,
            ))

    weapons = tuple(x for x in items if x.area_type == "Weapon")
    cyberware = tuple(x for x in items if x.area_type in _CYBERWARE_AREAS)
    return EquipmentSummary(
        status="ok",
        player_owner_hash=int(player_hash or player_owner_hash),
        area_count=len(areas),
        items=tuple(items),
        weapons=weapons,
        cyberware=cyberware,
    )
