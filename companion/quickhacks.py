"""Inventory evidence for quickhacks. Never infer the deck's installed slots."""
from __future__ import annotations

from typing import Any, Iterator
import re


# Lvl3 means generation IV, not III. Base variants differ between families.
# Source links and limits are shipped with the payload, independent of saves.
FAMILIES = (
    ("Contagion", "Contagion", "Atak wirusowy", "combat", 2, (2, 3, 4)),
    ("EMPOverload", "Short Circuit", "Zwarcie", "combat", 1, (1, 2, 3, 4)),
    ("Overheat", "Overheat", "Przegrzanie", "combat", 1, (1, 2, 3, 4)),
    ("Blind", "Reboot Optics", "", "control", 1, (1, 2, 3, 4)),
    ("MemoryWipe", "Memory Wipe", "", "covert", None, (2, 3, 4)),
    ("Ping", "Ping", "", "covert", 1, (2, 4)),
    ("Whistle", "Bait", "", "covert", None, (0, 1, 2, 3, 4)),
    ("CommsNoise", "Sonic Shock", "", "covert", 2, (2, 3, 4)),
    ("CommsCallIn", "Request Backup", "", "covert", None, (1, 2, 3, 4)),
    ("LocomotionMalfunction", "Cripple Movement", "", "control", 2, (2, 3, 4)),
    ("DisableCyberware", "Cyberware Malfunction", "", "control", 2, (2, 3, 4)),
    ("WeaponMalfunction", "Weapon Glitch", "", "control", 2, (2, 3, 4)),
    ("BrainMelt", "Synapse Burnout", "", "combat", None, (2, 3, 4)),
    ("Madness", "Cyberpsychosis", "", "ultimate", None, (3, 4)),
    ("GrenadeExplode", "Detonate Grenade", "", "ultimate", None, (3, 4)),
    ("Suicide", "Suicide", "", "ultimate", None, (3, 4)),
    ("SystemCollapse", "System Collapse", "", "ultimate", None, (3, 4)),
)
SOURCES = [{"label": "Cyberpunk Wiki — quickhacks 2.x", "url": "https://cyberpunk.fandom.com/wiki/Cyberpunk_2077_Quickhacks"}]


def registry_rows() -> Iterator[dict[str, Any]]:
    """Explicit supported IDs, also usable without the optional TSV catalog."""
    for prefix, name, name_pl, kind, base, levels in FAMILIES:
        variants = [(f"{prefix}Lvl{level}Program", level + 1, False) for level in levels]
        if base is not None:
            variants.append((f"{prefix}Program", base, False))
        variants.append((f"{prefix}Lvl4PlusPlusProgram", 5, True))
        for suffix, tier, iconic in variants:
            for recipe in (False, True):
                yield {"id": "Items." + ("Recipe_" if recipe else "") + suffix,
                       "family": prefix, "name": name, "name_pl": name_pl,
                       "hack_type": kind, "tier": tier, "iconic": iconic,
                       "kind": "recipe" if recipe else "program"}


REGISTRY = {row["id"]: row for row in registry_rows()}


def identify(record: dict[str, Any]) -> dict[str, Any] | None:
    item_id = record.get("id") or ""
    if item_id in REGISTRY:
        return {**REGISTRY[item_id], "identification": "supported-id"}
    # Unsupported/legacy program variants remain visible with unresolved tier.
    match = re.fullmatch(r"Items\.(Recipe_)?(.+?)Program", item_id)
    subcategory = str(record.get("subcategory") or "").casefold()
    if not match and "quickhack" not in subcategory:
        return None
    category = str(record.get("category") or "").casefold()
    recipe = bool(match and match[1]) or category == "crafting"
    family = match[2] if match else item_id or str(record.get("tweakdb_value") or "unresolved")
    known = next((f for f in FAMILIES if re.fullmatch(re.escape(f[0]) + r"(?:Lvl\d+(?:PlusPlus)?)?", family)), None)
    return {"id": item_id or None, "family": known[0] if known else family,
            "name": known[1] if known else record.get("name") or item_id or "Nierozpoznany quickhack",
            "name_pl": known[2] if known else "", "hack_type": known[3] if known else "unknown",
            "tier": None, "iconic": None, "kind": "recipe" if recipe else "program",
            "identification": "unresolved-variant"}


def quickhacks_payload(latest: dict[str, Any]) -> dict[str, Any]:
    records = []
    for item in latest.get("inventory_records", []):
        spec = identify(item)
        if spec is None:
            continue
        location = item.get("status") or "unknown"
        records.append({**spec, "location": location, "owned": location in {"player", "stash"},
                        "quantity": item.get("quantity", 1), "node_ids": item.get("node_ids", []),
                        "storage_ids": item.get("storage_ids", []), "tweakdb_value": item.get("tweakdb_value")})
    records.sort(key=lambda r: (r["name"].casefold(), r["kind"], r["tier"] or 0, bool(r["iconic"]), r["location"]))
    owned = [r for r in records if r["owned"]]
    groups = []
    for family in sorted({r["family"] for r in records}):
        rows = [r for r in records if r["family"] == family]
        programs = [r for r in rows if r["owned"] and r["kind"] == "program"]
        recipes = [r for r in rows if r["owned"] and r["kind"] == "recipe"]
        groups.append({"family": family, "name": rows[0]["name"], "name_pl": rows[0]["name_pl"],
                       "program_tiers": sorted({r["tier"] for r in programs if r["tier"] is not None}),
                       "recipe_tiers": sorted({r["tier"] for r in recipes if r["tier"] is not None}),
                       "recipe_without_program_tiers": sorted({r["tier"] for r in recipes if r["tier"] is not None} - {r["tier"] for r in programs if r["tier"] is not None}),
                       "records": rows})
    os_items = [r for r in latest.get("equipped_cyberware", []) if r.get("area_type") == "SystemReplacementCW"]
    deck_pattern = re.compile(r"Paraline|Rippler|Netdriver|Raven|Stephenson|Arasaka|Canto", re.I)
    decks = [r for r in os_items if deck_pattern.search(str(r.get("id") or "") + " " + str(r.get("name") or ""))]
    inventory_ok = latest.get("inventory_containers_status") == "ok"
    return {"schema": "cp2077-companion/quickhacks-v1", "save_name": latest.get("save_name"),
            "inventory_status": latest.get("inventory_containers_status", "not parsed"),
            "ownership_scan_complete": inventory_ok, "operating_systems": os_items, "cyberdecks": decks,
            "installed_quickhacks": {"status": "not-resolved", "slots": [],
                                    "note": "Lista i kolejność hacków osadzonych w cyberdecku nie zostały odczytane. Posiadanie programu nie potwierdza jego osadzenia."},
            "counts": {"owned_program_variants": len({r["id"] or r["tweakdb_value"] for r in owned if r["kind"] == "program"}),
                       "owned_recipe_variants": len({r["id"] or r["tweakdb_value"] for r in owned if r["kind"] == "recipe"}),
                       "families": len(groups), "other_container_records": sum(not r["owned"] for r in records),
                       "unresolved_quickhack_records": sum(r["identification"] != "supported-id" for r in records),
                       "unclassified_inventory_records": sum(not r.get("resolved") and identify(r) is None for r in latest.get("inventory_records", []))},
            "groups": groups, "records": records, "sources": SOURCES,
            "notes": ["Generacja jest mapowana z obsługiwanych identyfikatorów 2.x, nie z koloru ani nazwy w katalogu. Nieznany wariant nie dostaje zgadywanej generacji.",
                      "Schemat oznacza odczytany rekord receptury. Nie potwierdza dostępności wszystkich składników ani gotowego programu.",
                      "Quickhack wyższej generacji wytwarza się jako nowy program ze schematu lub zdobywa gotowy. Cyberdeck ulepsza się osobno u ripperdoca.",
                      "Brak programu w odczytanym ekwipunku nie rozstrzyga zawartości nierozpoznanych slotów cyberdecku."]}
