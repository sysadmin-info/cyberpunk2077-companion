"""Read-only decoder for player StatPoolsSystem values (CP2077 2.x)."""
from __future__ import annotations

from dataclasses import dataclass
import re
import struct
from typing import Any

from .scriptables import ScriptableDecodeError, _parse_package


class StatPoolsDecodeError(ScriptableDecodeError):
    pass


@dataclass(frozen=True)
class StatPoolSummary:
    status: str
    player_owner_hash: int
    pools: tuple[dict[str, Any], ...]
    health: dict[str, Any] | None


_FIXED = {
    "Bool": 1, "Int32": 4, "Uint32": 4, "Uint16": 2, "Uint8": 1,
    "Float": 4, "Uint64": 8, "Int64": 8, "TweakDBID": 8, "CName": 8,
}


def _is_enum(type_name: str) -> bool:
    return type_name.startswith("gamedata") or type_name.startswith("gameStatIDType") or type_name.startswith("gameStatPoolDataValueChangeMode") or type_name.startswith("E")


def _descriptors(data: bytes, pos: int, strings: list[str]) -> list[tuple[str, str, int]]:
    if pos + 2 > len(data):
        raise StatPoolsDecodeError("truncated struct")
    count = struct.unpack_from("<H", data, pos)[0]
    if count > 512 or pos + 2 + count * 8 > len(data):
        raise StatPoolsDecodeError("invalid struct descriptor table")
    out = []
    for i in range(count):
        ni, ti, off = struct.unpack_from("<HHI", data, pos + 2 + i * 8)
        if ni >= len(strings) or ti >= len(strings):
            raise StatPoolsDecodeError("descriptor string index outside package")
        out.append((strings[ni], strings[ti], off))
    return out


def _type_size(type_name: str, data: bytes, pos: int, strings: list[str], depth: int = 0) -> int:
    if depth > 20:
        raise StatPoolsDecodeError("nested stat-pool structure too deep")
    if type_name in _FIXED:
        return _FIXED[type_name]
    if _is_enum(type_name):
        return 2
    fixed_array = re.match(r"^\[(\d+)\](.+)$", type_name)
    if fixed_array:
        count = int(fixed_array.group(1))
        if count > 100_000 or count > len(data) - pos:
            raise StatPoolsDecodeError("fixed array exceeds budget")
        item_type = fixed_array.group(2)
        q = pos
        for _ in range(count):
            q += _type_size(item_type, data, q, strings, depth + 1)
        return q - pos
    if type_name.startswith("array:"):
        item_type = type_name[6:]
        if pos + 4 > len(data):
            raise StatPoolsDecodeError("truncated array")
        count = struct.unpack_from("<I", data, pos)[0]
        if count > 100_000:
            raise StatPoolsDecodeError(f"unreasonable array count {count}")
        q = pos + 4
        for _ in range(count):
            q += _type_size(item_type, data, q, strings, depth + 1)
        return q - pos
    if type_name == "DataBuffer":
        if pos + 4 > len(data):
            raise StatPoolsDecodeError("truncated DataBuffer")
        return 4 + struct.unpack_from("<I", data, pos)[0]
    return _struct_size(data, pos, strings, depth + 1)


def _struct_size(data: bytes, pos: int, strings: list[str], depth: int = 0) -> int:
    desc = _descriptors(data, pos, strings)
    max_end = 2 + len(desc) * 8
    for i, (_, type_name, offset) in enumerate(desc):
        if i + 1 < len(desc):
            consumed = desc[i + 1][2] - offset
            if consumed < 0:
                raise StatPoolsDecodeError("invalid field boundary")
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


def _parse_pool(data: bytes, pos: int, strings: list[str]) -> tuple[dict[str, Any], int]:
    desc = _descriptors(data, pos, strings)
    size = _struct_size(data, pos, strings)
    out: dict[str, Any] = {}
    for name, type_name, offset in desc:
        p = pos + offset
        if name == "ownerID" and type_name == "gameStatsObjectID":
            out[name], _ = _stats_object_id(data, p, strings)
        elif type_name == "Float":
            out[name] = float(struct.unpack_from("<f", data, p)[0])
        elif type_name == "TweakDBID":
            out[name] = f"0x{struct.unpack_from('<Q', data, p)[0]:016X}"
        elif _is_enum(type_name):
            out[name] = _enum(data, p, strings)
    return out, size


def parse_stat_pools(payload: bytes, player_owner_hash: int = 1) -> StatPoolSummary:
    strings, objects = _parse_package(payload)
    if not objects or objects[0].name != "gameStatPoolsSystemSave":
        raise StatPoolsDecodeError("gameStatPoolsSystemSave root not found")
    root = objects[0].data
    desc = _descriptors(root, 0, strings)
    fields = {name: (type_name, offset) for name, type_name, offset in desc}
    if "mapping" not in fields or "statPools" not in fields:
        raise StatPoolsDecodeError("StatPoolsSystem mapping/statPools fields missing")

    mapping_type, mapping_offset = fields["mapping"]
    pools_type, pools_offset = fields["statPools"]
    if mapping_type != "array:gameStatsObjectID" or pools_type != "array:gameStatPoolData":
        raise StatPoolsDecodeError("unexpected StatPoolsSystem field types")

    mapping_pos = mapping_offset
    mapping_count = struct.unpack_from("<I", root, mapping_pos)[0]
    q = mapping_pos + 4
    mapping: list[dict[str, Any]] = []
    for _ in range(mapping_count):
        row, consumed = _stats_object_id(root, q, strings)
        mapping.append(row)
        q += consumed

    pools_pos = pools_offset
    pool_count = struct.unpack_from("<I", root, pools_pos)[0]
    if pool_count != mapping_count:
        raise StatPoolsDecodeError(f"mapping/statPools count mismatch: {mapping_count}/{pool_count}")
    q = pools_pos + 4
    player_pools: list[dict[str, Any]] = []
    for index in range(pool_count):
        pool, consumed = _parse_pool(root, q, strings)
        key = mapping[index]
        if key.get("idType") == "EntityID" and int(key.get("entityHash", -1)) == player_owner_hash:
            normalized = {
                "type": pool.get("type"),
                "stat": pool.get("stat"),
                "max_value": pool.get("maxValue"),
                "current_value": pool.get("currentValue"),
                "custom_limit_value": pool.get("customLimitValue"),
                "modification_delay": pool.get("modificationDelay"),
                "change_mode": pool.get("changeMode"),
                "record_id": pool.get("recordID"),
            }
            player_pools.append(normalized)
        q += consumed

    health = next((x for x in player_pools if x.get("type") == "Health" or x.get("stat") == "Health"), None)
    return StatPoolSummary(
        status="ok",
        player_owner_hash=player_owner_hash,
        pools=tuple(player_pools),
        health=health,
    )
