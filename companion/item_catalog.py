"""TweakDB item-name resolver.

A small built-in catalog is always available.  If ``data/cet_catalog.tsv`` is
present, CP2077 Companion also indexes the public NightCity Console catalog.
The catalog is data-only; the companion remains fully read-only with respect to
Cyberpunk saves and the game installation.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from functools import lru_cache
import json
import hashlib

from .binary import tweakdbid_for_name
from .catalog import KNOWN_ITEMS
from .item_aliases import DISPLAY_NAME_OVERRIDES
from .quickhacks import registry_rows


CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "cet_catalog.tsv"
from .catalog_fetch import URL as CATALOG_SOURCE, SHA256, SIZE
from .localio import read_limited, regular_local


@dataclass(frozen=True)
class CatalogItem:
    id: str
    name: str
    subcategory: str = ""
    category: str = ""
    source: str = "builtin"
    catalog_name: str | None = None
    name_source: str | None = None


def _builtin() -> Iterable[CatalogItem]:
    for row in registry_rows():
        yield CatalogItem(id=row['id'], name=row['name'], subcategory='QUICKHACK',
                          category='CRAFTING' if row['kind'] == 'recipe' else 'CYBERWARE',
                          source='quickhack-registry')
    registry_path = Path(__file__).resolve().parent.parent / 'data' / 'iconic_weapons.json'
    if registry_path.is_file():
        for weapon in json.loads(registry_path.read_text(encoding='utf-8'))['weapons']:
            for item_id in weapon['tweakdb_ids']:
                yield CatalogItem(id=item_id, name=weapon['name'], category='WEAPONS',
                                  subcategory=weapon['weapon_type'], source='iconic-registry')
    for row in KNOWN_ITEMS:
        yield CatalogItem(
            id=row["id"],
            name=row["name"],
            category=row.get("category", ""),
            source="builtin",
        )


def _read_tsv(data: bytes) -> Iterable[CatalogItem]:
    for raw_line in data.decode("utf-8-sig").splitlines():
        line = raw_line.strip("\r\n")
        if not line or line.lstrip().startswith("#"):
            continue
        parts = [x.strip() for x in line.split("\t")]
        if len(parts) < 2:
            # Deliberately do not guess a whitespace schema. The upstream file
            # is TSV; a mangled HTML/text copy should simply be ignored.
            continue
        item_id, display_name = parts[0], parts[1]
        if not item_id or not (item_id.startswith("Items.") or item_id.startswith("Ammo.") or item_id.startswith("TEST.")):
            continue
        yield CatalogItem(
            id=item_id,
            name=display_name or item_id,
            subcategory=parts[2] if len(parts) > 2 else "",
            category=parts[3] if len(parts) > 3 else "",
            source="nightcity-console",
        )


def _apply_display_name_overrides(
    by_tweakdb: dict[int, CatalogItem],
    by_id: dict[str, CatalogItem],
) -> int:
    """Apply the small curated correction layer after broad catalog loading.

    The original catalog label is retained in ``catalog_name`` whenever the
    override changes it.  This makes the UI/export transparent instead of
    silently rewriting community data.
    """
    applied = 0
    for item_id, override in DISPLAY_NAME_OVERRIDES.items():
        try:
            key = tweakdbid_for_name(item_id)
        except ValueError:
            continue

        existing = by_id.get(item_id)
        previous = override.get("previous_name") or (existing.name if existing else None)
        if existing is not None:
            if existing.name and existing.name.casefold() != override["name"].casefold():
                previous = existing.name
            corrected = CatalogItem(
                id=existing.id,
                name=override["name"],
                subcategory=existing.subcategory,
                category=existing.category,
                source=existing.source,
                catalog_name=previous,
                name_source=override.get("evidence") or "curated-alias",
            )
        else:
            corrected = CatalogItem(
                id=item_id,
                name=override["name"],
                source="curated-alias",
                catalog_name=previous,
                name_source=override.get("evidence") or "curated-alias",
            )

        by_tweakdb[key] = corrected
        by_id[item_id] = corrected
        applied += 1
    return applied


@lru_cache(maxsize=4)
def _load_catalog_cached(signature: tuple[bool, int, int]) -> tuple[dict[int, CatalogItem], dict[str, CatalogItem], dict[str, object]]:
    by_tweakdb: dict[int, CatalogItem] = {}
    by_id: dict[str, CatalogItem] = {}

    for item in _builtin():
        try:
            key = tweakdbid_for_name(item.id)
        except ValueError:
            continue
        by_tweakdb[key] = item
        by_id[item.id] = item

    external = 0
    verification = "absent"
    data = b""
    if regular_local(CATALOG_PATH):
        try:
            raw = read_limited(CATALOG_PATH, SIZE)
        except (ValueError, OSError):
            raw = b""
        if len(raw) == SIZE and hashlib.sha256(raw).hexdigest() == SHA256:
            data = raw
            verification = "verified"
        else:
            verification = "unverified"
    if data:
        for item in _read_tsv(data):
            try:
                key = tweakdbid_for_name(item.id)
            except ValueError:
                continue
            # External catalog wins for its richer human/category labels, but
            # curated built-ins still cover probes if the TSV lacks a row.
            by_tweakdb[key] = item
            by_id[item.id] = item
            external += 1

    alias_overrides = _apply_display_name_overrides(by_tweakdb, by_id)

    return by_tweakdb, by_id, {
        "present": verification == "verified",
        "verification": verification,
        "external_records": external,
        "resolved_records": len(by_tweakdb),
        "alias_overrides": alias_overrides,
        "source_url": CATALOG_SOURCE,
    }


def load_catalog() -> tuple[dict[int, CatalogItem], dict[str, CatalogItem], dict[str, object]]:
    signature = (False, 0, 0)
    try:
        if regular_local(CATALOG_PATH):
            st = CATALOG_PATH.lstat()
            signature = (True, int(st.st_mtime_ns), int(st.st_size))
    except OSError:
        pass
    return _load_catalog_cached(signature)
