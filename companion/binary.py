"""Read-only Cyberpunk 2077 ``sav.dat`` parser used by CP2077 Companion.

Implemented pieces:
- VASC/FZLC container parsing,
- CP2077 LZ4 block decompression,
- EDON node table parsing,
- FactsTable extraction,
- QuestProgressedAggregator_v3 printable identifiers,
- inventory/itemData inspection for the player's inventory.

There is deliberately no save-writing code in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import io
import re
import struct
from typing import Iterable
import zlib

from .equipment import EquipmentDecodeError, EquipmentSummary, parse_equipment
from .perk_names import PERK_NAMES
from .scriptables import PlayerDevelopmentSummary, ScriptableDecodeError, parse_player_development
from .statpools import StatPoolSummary, StatPoolsDecodeError, parse_stat_pools
from .stats import StatsDecodeError, StatsSummary, parse_stats


from .localio import BLOCK_LIMIT, OUTPUT_LIMIT, SAVE_LIMIT, read_limited


class SaveFormatError(RuntimeError):
    pass


@dataclass(frozen=True)
class NodeInfo:
    name: str
    next_id: int | None
    child_id: int | None
    offset: int
    size: int


@dataclass(frozen=True)
class InventoryItem:
    node_index: int
    storage_id: int | None
    tweakdb_hash: int
    tweakdb_length: int
    tweakdb_value: int
    quantity: int
    quantity_source: str
    raw_size: int


@dataclass(frozen=True)
class BinarySaveData:
    facts_by_hash: dict[int, int]
    reward_strings: tuple[str, ...]
    node_count: int
    fact_entry_count: int
    inventory_subinventory_count: int
    player_inventory_storage_id: int | None
    player_inventory_declared_count: int
    player_inventory_items: tuple[InventoryItem, ...]
    all_item_records: tuple[InventoryItem, ...]
    player_development: PlayerDevelopmentSummary | None
    player_development_status: str
    equipment: EquipmentSummary | None
    equipment_status: str
    stat_pools: StatPoolSummary | None
    stat_pools_status: str
    player_stats: StatsSummary | None
    player_stats_status: str
    inventory_containers_status: str = 'not parsed'


def fnv1a32(value: str) -> int:
    h = 0x811C9DC5
    for byte in value.encode("utf-8"):
        h ^= byte
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def tweakdbid_for_name(value: str) -> int:
    """Return the 64-bit serialized TweakDBID used by itemData.

    For normal textual TweakDB records in current CP2077 saves the low 32 bits
    are CRC32(name), while bits 32..39 carry the UTF-8 byte length.
    """
    encoded = value.encode("utf-8")
    if len(encoded) > 0xFF:
        raise ValueError("TweakDBID textual name is too long")
    return (len(encoded) << 32) | (zlib.crc32(encoded) & 0xFFFFFFFF)


def tweakdb_hash_for_name(value: str) -> int:
    return tweakdbid_for_name(value) & 0xFFFFFFFF


def _unpack_packed_int(raw: bytes) -> int:
    if not raw:
        raise SaveFormatError("empty packed integer")
    first = raw[0]
    value = first & 0x3F
    shift = 6
    negative = bool(first & 0x80)
    for byte in raw[1:]:
        value |= (byte & 0x7F) << shift
        shift += 7
    return -value if negative else value


def _read_packed_bytes(stream: io.BytesIO) -> bytes:
    first = stream.read(1)
    if not first:
        raise SaveFormatError("unexpected EOF while reading packed integer")
    out = bytearray(first)
    if not (first[0] & 0x40):
        return bytes(out)
    nxt = stream.read(1)
    if not nxt:
        raise SaveFormatError("unexpected EOF while reading packed integer")
    out.extend(nxt)
    while out[-1] & 0x80:
        nxt = stream.read(1)
        if not nxt:
            raise SaveFormatError("unexpected EOF while reading packed integer")
        out.extend(nxt)
    return bytes(out)


def _read_packed_int(stream: io.BytesIO) -> int:
    return _unpack_packed_int(_read_packed_bytes(stream))


def _read_packed_from_bytes(data: bytes, pos: int) -> tuple[int, int]:
    if pos >= len(data):
        raise SaveFormatError("packed integer outside node")
    start = pos
    first = data[pos]
    pos += 1
    if first & 0x40:
        while True:
            if pos >= len(data):
                raise SaveFormatError("truncated packed integer")
            current = data[pos]
            pos += 1
            if not (current & 0x80):
                break
    return _unpack_packed_int(data[start:pos]), pos


def _decompress_lz4_chunk(blob: bytes, table_size: int | None = None) -> bytes:
    if len(blob) < 8 or blob[:4] != b"4ZLX":
        raise SaveFormatError("unsupported CP2077 data chunk")
    expected = struct.unpack_from("<I", blob, 4)[0]
    if expected > BLOCK_LIMIT or (table_size is not None and expected != table_size):
        raise SaveFormatError("unsupported LZ4 output length")
    pos = 8
    out = bytearray()

    while pos < len(blob):
        token = blob[pos]
        pos += 1

        literal_len = token >> 4
        if literal_len == 15:
            while True:
                if pos >= len(blob):
                    raise SaveFormatError("truncated LZ4 literal length")
                extra = blob[pos]
                pos += 1
                literal_len += extra
                if extra != 255:
                    break

        end = pos + literal_len
        if end > len(blob):
            raise SaveFormatError("LZ4 literal exceeds chunk")
        if literal_len > expected - len(out):
            raise SaveFormatError("literal exceeds output budget")
        out.extend(blob[pos:end])
        pos = end

        if pos >= len(blob):
            break
        if pos + 2 > len(blob):
            raise SaveFormatError("truncated LZ4 match offset")

        back = blob[pos] | (blob[pos + 1] << 8)
        pos += 2
        if back <= 0 or back > len(out):
            raise SaveFormatError("invalid LZ4 match offset")

        match_len = (token & 0x0F) + 4
        if (token & 0x0F) == 15:
            while True:
                if pos >= len(blob):
                    raise SaveFormatError("truncated LZ4 match length")
                extra = blob[pos]
                pos += 1
                match_len += extra
                if extra != 255:
                    break

        if match_len > expected - len(out):
            raise SaveFormatError("match exceeds output budget")
        source = len(out) - back
        for _ in range(match_len):
            out.append(out[source])
            source += 1

    if len(out) != expected:
        raise SaveFormatError(
            f"LZ4 length mismatch: expected {expected}, got {len(out)}"
        )
    return bytes(out)


def _parse_node_table(raw: bytes, offset: int) -> tuple[list[NodeInfo], int]:
    stream = io.BytesIO(raw[offset:])
    if stream.read(4) != b"EDON":
        raise SaveFormatError("EDON node table not found")

    count = _read_packed_int(stream)
    if count < 0 or count > min(100_000, (len(raw) - offset) // 17):
        raise SaveFormatError("unsupported node count")
    nodes: list[NodeInfo] = []
    none = 0xFFFFFFFF

    for _ in range(count):
        name_len = -_read_packed_int(stream)
        if name_len < 0 or name_len > 4096:
            raise SaveFormatError(f"invalid node name length: {name_len}")
        payload = stream.read(name_len + 16)
        if len(payload) != name_len + 16:
            raise SaveFormatError("truncated node table")
        name = payload[:name_len].decode("utf-8", errors="replace")
        next_id, child_id, node_offset, size = struct.unpack_from(
            "<IIII", payload, name_len
        )
        nodes.append(
            NodeInfo(
                name=name,
                next_id=None if next_id == none else next_id,
                child_id=None if child_id == none else child_id,
                offset=node_offset,
                size=size,
            )
        )

    table_offset_raw = stream.read(4)
    if len(table_offset_raw) != 4:
        raise SaveFormatError("missing node table offset")
    recorded_offset = struct.unpack("<I", table_offset_raw)[0]
    if recorded_offset != offset:
        raise SaveFormatError(
            f"node table offset mismatch: expected {offset}, got {recorded_offset}"
        )
    return nodes, count


def _extract_ascii_strings(data: bytes, min_len: int = 5) -> Iterable[str]:
    pattern = rb"[\x20-\x7e]{" + str(min_len).encode() + rb",}"
    for match in re.finditer(pattern, data):
        text = match.group(0).decode("ascii", errors="ignore").strip()
        if text:
            yield text


def _parse_item_data(payload: bytes, node_index: int, storage_id: int | None) -> InventoryItem | None:
    # Current 2.31 itemData nodes begin with the node index followed by a
    # serialized 64-bit TweakDBID.  Do not pretend to understand the remaining
    # weapon/cyberware payload yet; only simple 29-byte stack nodes have a
    # validated quantity field at offset 25.
    if len(payload) < 12:
        return None
    stored_node_index = struct.unpack_from("<I", payload, 0)[0]
    if stored_node_index != node_index:
        return None
    tweakdb_value = struct.unpack_from("<Q", payload, 4)[0]
    tweakdb_hash = tweakdb_value & 0xFFFFFFFF
    tweakdb_length = (tweakdb_value >> 32) & 0xFF
    if not tweakdb_hash:
        return None

    if len(payload) == 29:
        quantity = struct.unpack_from("<I", payload, 25)[0]
        quantity_source = "stack-field"
    else:
        quantity = 1
        quantity_source = "unique-assumed"

    return InventoryItem(
        node_index=node_index,
        storage_id=storage_id,
        tweakdb_hash=tweakdb_hash,
        tweakdb_length=tweakdb_length,
        tweakdb_value=tweakdb_value,
        quantity=quantity,
        quantity_source=quantity_source,
        raw_size=len(payload),
    )


def parse_sav_dat(path: str | Path) -> BinarySaveData:
    raw = read_limited(Path(path), SAVE_LIMIT)
    if len(raw) < 64 or raw[:4] != b"VASC":
        raise SaveFormatError("not a Cyberpunk 2077 VASC save")

    header_size = 25
    if raw[header_size : header_size + 4] != b"FZLC":
        raise SaveFormatError("FZLC chunk table not found")

    count = struct.unpack_from("<I", raw, header_size + 4)[0]
    entries_start = header_size + 8
    first_chunk_offset = struct.unpack_from("<I", raw, entries_start)[0]
    table_payload = first_chunk_offset - entries_start
    if table_payload <= 0 or table_payload % 12:
        raise SaveFormatError("invalid FZLC table size")

    capacity = table_payload // 12
    if capacity not in (0x100, 0x200, 0x400):
        raise SaveFormatError(f"unsupported FZLC capacity: {capacity:#x}")
    if not 0 < count <= capacity or first_chunk_offset > len(raw):
        raise SaveFormatError("FZLC chunk count exceeds capacity")

    chunks: list[tuple[int, int, int]] = []
    for index in range(count):
        pos = entries_start + index * 12
        chunks.append(struct.unpack_from("<III", raw, pos))

    if any(n > BLOCK_LIMIT for _, _, n in chunks) or sum(n for _, _, n in chunks) > OUTPUT_LIMIT:
        raise SaveFormatError("save exceeds decompression budget")
    uncompressed = bytearray()
    previous_end = first_chunk_offset
    for chunk_offset, compressed_len, expected_len in chunks:
        end = chunk_offset + compressed_len
        if chunk_offset < previous_end or end > len(raw):
            raise SaveFormatError("compressed chunk outside sav.dat")
        previous_end = end
        block = _decompress_lz4_chunk(raw[chunk_offset:end], expected_len)
        if len(block) != expected_len:
            raise SaveFormatError("chunk decompressed length mismatch")
        uncompressed.extend(block)

    node_table_offset = chunks[-1][0] + chunks[-1][1]
    nodes, node_count = _parse_node_table(raw, node_table_offset)
    virtual_base = first_chunk_offset


    def node_data(node: NodeInfo) -> bytes:
        start = node.offset - virtual_base
        end = start + node.size
        if start < 0 or end > len(uncompressed):
            raise SaveFormatError(f"node {node.name!r} points outside data")
        return bytes(memoryview(uncompressed)[start:end])

    facts: dict[int, int] = {}
    total_fact_entries = 0
    rewards: list[str] = []

    player_development: PlayerDevelopmentSummary | None = None
    player_development_status = "not found"
    equipment: EquipmentSummary | None = None
    equipment_status = "not found"
    stat_pools: StatPoolSummary | None = None
    stat_pools_status = "not found"
    player_stats: StatsSummary | None = None
    player_stats_status = "not found"

    for node in nodes:
        if node.name == "FactsTable":
            payload = node_data(node)
            if len(payload) < 5:
                continue
            fact_count, pos = _read_packed_from_bytes(payload, 4)
            if fact_count < 0:
                raise SaveFormatError("negative FactsTable count")
            need = pos + fact_count * 8
            if need > len(payload):
                raise SaveFormatError("truncated FactsTable")
            hashes = struct.unpack_from(f"<{fact_count}I", payload, pos) if fact_count else ()
            values = (
                struct.unpack_from(f"<{fact_count}I", payload, pos + 4 * fact_count)
                if fact_count
                else ()
            )
            total_fact_entries += fact_count
            for fact_hash, fact_value in zip(hashes, values):
                facts[fact_hash] = fact_value

        elif node.name == "QuestProgressedAggregator_v3":
            for text in _extract_ascii_strings(node_data(node)):
                cleaned = text.strip("@^`~|\\")
                if re.search(r"(?:^|_)(?:q\d|sq|mq|sts|ma|sa|wst|cbj|reward)", cleaned, re.I):
                    rewards.append(cleaned)

        elif node.name == "ScriptableSystemsContainer":
            payload = node_data(node)
            if player_development is None:
                try:
                    player_development = parse_player_development(payload, PERK_NAMES)
                    player_development_status = "ok"
                except (ScriptableDecodeError, ValueError, struct.error, IndexError) as exc:
                    # Additive feature: future patches must not break base parsing.
                    player_development_status = f"error: {exc}"
            if equipment is None:
                try:
                    equipment = parse_equipment(payload)
                    equipment_status = "ok"
                except (EquipmentDecodeError, ValueError, struct.error, IndexError) as exc:
                    equipment_status = f"error: {exc}"

        elif node.name == "StatPoolsSystem" and stat_pools is None:
            try:
                stat_pools = parse_stat_pools(node_data(node))
                stat_pools_status = "ok"
            except (StatPoolsDecodeError, ValueError, struct.error, IndexError) as exc:
                stat_pools_status = f"error: {exc}"

        elif node.name == "StatsSystem" and player_stats is None:
            try:
                player_stats = parse_stats(node_data(node))
                player_stats_status = "ok"
            except (StatsDecodeError, ValueError, struct.error, IndexError) as exc:
                player_stats_status = f"error: {exc}"

    # Inventory v2.31: the inventory parent starts with its node id, then the
    # number of subinventories, then the first storage id + declared item count.
    # Storage id 1 is the player inventory in the supplied unmodded 2.31 saves.
    inventory_subinventory_count = 0
    player_storage_id: int | None = None
    player_declared_count = 0
    player_items: list[InventoryItem] = []
    all_items: list[InventoryItem] = []

    inventory_index = next((i for i, n in enumerate(nodes) if n.name == "inventory"), None)
    if inventory_index is not None:
        inv_node = nodes[inventory_index]
        inv_payload = node_data(inv_node)
        if len(inv_payload) >= 20:
            stored_id = struct.unpack_from("<I", inv_payload, 0)[0]
            if stored_id == inventory_index:
                inventory_subinventory_count = struct.unpack_from("<I", inv_payload, 4)[0]
                player_storage_id = struct.unpack_from("<Q", inv_payload, 8)[0]
                player_declared_count = struct.unpack_from("<I", inv_payload, 16)[0]

                child = inv_node.child_id
                seen: set[int] = set()
                for _ in range(player_declared_count):
                    if child is None or child in seen or child >= len(nodes):
                        break
                    seen.add(child)
                    child_node = nodes[child]
                    if child_node.name != "itemData":
                        break
                    item = _parse_item_data(node_data(child_node), child, player_storage_id)
                    if item is not None:
                        player_items.append(item)
                    child = child_node.next_id

    # Validate every subinventory before assigning any additional owner.
    # storage 1000000 is confirmed as stash by the 660/661 Byakko transfer.
    from .inventory_containers import decode_containers
    mapped_by_node = {}
    inventory_containers_status = 'not found'
    if inventory_index is not None:
        try:
            containers = decode_containers(inv_payload, inventory_index, nodes, inv_node.offset)
            inventory_containers_status = 'ok'
        except (ValueError, struct.error) as exc:
            inventory_containers_status = f'error: {exc}'
            containers = {}  # Preserve the old player-only fallback on unknown formats.
        for storage_id, entries in containers.items():
            for node_index, payload in entries:
                item = _parse_item_data(payload, node_index, storage_id)
                if item is not None:
                    mapped_by_node[node_index] = item
        if containers:
            player_items = [x for x in mapped_by_node.values() if x.storage_id == 1]
            player_storage_id = 1 if 1 in containers else None
            player_declared_count = len(containers.get(1, []))

    # Scan all itemData nodes as a diagnostic index. Records outside the first
    # player inventory are intentionally labelled with storage_id=None until
    # the remaining container headers are fully mapped.
    player_by_node = {x.node_index: x for x in player_items}
    player_by_node.update(mapped_by_node)
    for index, node in enumerate(nodes):
        if node.name != "itemData":
            continue
        if index in player_by_node:
            item = player_by_node[index]
        else:
            item = _parse_item_data(node_data(node), index, None)
        if item is not None:
            all_items.append(item)

    return BinarySaveData(
        facts_by_hash=facts,
        reward_strings=tuple(dict.fromkeys(rewards)),
        node_count=node_count,
        fact_entry_count=total_fact_entries,
        inventory_subinventory_count=inventory_subinventory_count,
        inventory_containers_status=inventory_containers_status,
        player_inventory_storage_id=player_storage_id,
        player_inventory_declared_count=player_declared_count,
        player_inventory_items=tuple(player_items),
        all_item_records=tuple(all_items),
        player_development=player_development,
        player_development_status=player_development_status,
        equipment=equipment,
        equipment_status=equipment_status,
        stat_pools=stat_pools,
        stat_pools_status=stat_pools_status,
        player_stats=player_stats,
        player_stats_status=player_stats_status,
    )
