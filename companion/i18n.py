"""Localize presentation fields only; never translate save identifiers, URLs, or evidence keys."""

from functools import lru_cache
from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1] / "locales"
FIELDS = frozenset(
    """
    acquisition location conditions fast_travel quest npc title hint decision_point tags label action
    immediate delayed reward condition notes editorial_notes supports note verified_patch name group
    why caveat value headline requirement overall importance evidence source_title type_label description
    message text availability_note ending kind_label weapon_type slot_label area_label
""".split()
)


@lru_cache(maxsize=2)
def catalog(lang):
    if lang not in ("en", "pl"):
        raise ValueError("Unsupported language")
    return json.loads((ROOT / f"content.{lang}.json").read_text(encoding="utf8"))


def localize_state(state, lang):
    words = catalog(lang)

    def translate(s):
        if not isinstance(s, str):
            return s
        if s in words:
            return words[s]
        if s.startswith("Mapa — "):
            return ("Map — " if lang == "en" else "Mapa — ") + s[7:]
        if s.startswith("Poradnik zdobycia — ") and lang == "en":
            return "Acquisition guide — " + s.split(" — ", 1)[1]
        for source, dest in words.get("@patterns", []):
            match = re.fullmatch(source, s)
            if match:
                return dest.format(*match.groups())
        return s

    def walk(el, field=""):
        if isinstance(el, dict):
            return {
                k: walk(v, k if isinstance(v, (dict, list)) or k in FIELDS else "")
                for k, v in el.items()
            }
        if isinstance(el, list):
            return [walk(v, field) for v in el]
        return translate(el) if field in FIELDS else el

    result = dict(state)
    if not state.get("ok"):
        result["error"] = translate(state.get("error", "No data"))
        return result
    for name in (
        "iconic_weapons",
        "quest_choices",
        "hidden_encounters",
        "reaper_readiness",
        "quickhacks",
        "quests",
        "decisions",
        "endings",
    ):
        if name in state:
            result[name] = walk(state[name])
    if "reaper_readiness" in result:
        result["reaper_readiness"]["overall_code"] = state["reaper_readiness"].get(
            "overall", ""
        )
    latest = dict(state["latest"])
    # Raw save values and item/quest IDs keep their original game identities.
    for name in (
        "player_stats",
        "equipped_items",
        "equipped_weapons",
        "equipped_cyberware",
    ):
        if name in latest:
            latest[name] = walk(latest[name])
    result["latest"] = latest
    return result
