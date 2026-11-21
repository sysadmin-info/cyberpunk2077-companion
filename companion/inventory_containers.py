"""Read inventory headers, validating every boundary against the node table."""
import struct


def decode_containers(payload, inventory_index, nodes, inventory_offset):
    if len(payload) < 8 or struct.unpack_from('<I', payload)[0] != inventory_index:
        raise ValueError('Invalid inventory header')
    count = struct.unpack_from('<I', payload, 4)[0]
    if count > (len(payload) - 8) // 12:
        raise ValueError('Invalid subinventory count')
    pos = 8
    containers = {}
    for _ in range(count):
        if pos + 12 > len(payload):
            raise ValueError('Truncated container header')
        storage_id, item_count = struct.unpack_from('<QI', payload, pos)
        pos += 12
        if storage_id in containers or item_count > (len(payload) - pos) // 28:
            raise ValueError('Invalid container or item count')
        items = []
        for _ in range(item_count):
            if pos + 20 > len(payload):
                raise ValueError('Truncated item header')
            item_id = payload[pos:pos + 16]
            pos += 16
            node_index = struct.unpack_from('<I', payload, pos)[0]
            if node_index >= len(nodes):
                raise ValueError('Item node outside table')
            node = nodes[node_index]
            if node.name != 'itemData' or node.offset != inventory_offset + pos or node.size < 20:
                raise ValueError('Item node boundary mismatch')
            end = pos + node.size
            if end > len(payload) or payload[pos + 4:pos + 20] != item_id:
                raise ValueError('Item identity or size mismatch')
            items.append((node_index, payload[pos:end]))
            pos = end
        containers[storage_id] = items
    if pos != len(payload):
        raise ValueError('Unexpected trailing inventory bytes')
    return containers
