from __future__ import annotations

from typing import Any


CORE_PERKS = {
    "painkiller": "Body_Central_Milestone_1",
    "adrenaline_rush": "Body_Central_Milestone_3",
    "dash": "Reflexes_Central_Milestone_2",
}

SUPPORT_PERKS = {
    "come_back_kid": "Body_Central_Perk_1_2",
    "army_of_one": "Body_Central_Perk_1_3",
    "dorph_head": "Body_Central_Perk_1_4",
    "calm_mind": "Body_Central_Perk_3_1",
    "juggernaut": "Body_Central_Perk_3_2",
    "unstoppable_force": "Body_Central_Perk_3_4",
    "air_dash": "Reflexes_Central_Milestone_3",
    "cant_touch_this": "Reflexes_Central_Perk_2_2",
    "health_freak": "Tech_Left_Milestone_2",
    "field_medic": "Tech_Left_Perk_2_3",
    "borrowed_time": "Tech_Left_Perk_2_2",
    "edgerunner": "Tech_Master_Perk_3",
}

CYBERWARE_MATCHERS = {
    "blood_pump": {"label": "Blood Pump", "names": ("blood pump",), "ids": ("advancedbloodpump", "bloodpump")},
    "biomonitor": {"label": "Biomonitor", "names": ("biomonitor",), "ids": ("advancedbiomonitor", "healthmonitor")},
    "second_heart": {"label": "Second Heart", "names": ("second heart",), "ids": ("advancedsecondheart", "secondheart")},
    "epimorphic_skeleton": {"label": "Epimorphic Skeleton", "names": ("epimorphic skeleton",), "ids": ("advancedendoskeleton", "advancedendoskeleton", "advancedendoskeleton2", "advancedendoskeletonlegendary2", "advancedendoskeleton")},
}

COMBAT_WEAPONS = (
    ("Ba Xing Chong", ("legendary_zhuo_eight_star", "preset_zhuo_eight_star", "ba xing chong")),
    ("Breakthrough", ("nekomata_breakthrough", "breakthrough")),
    ("Pride", ("preset_liberty_rogue", "pride")),
    ("Prejudice", ("preset_masamune_rogue", "prejudice")),
    ("Widow Maker", ("preset_achilles_nash", "widow maker")),
    ("Malorian Arms 3516", ("preset_silverhand_3516", "malorian arms 3516")),
)


def _flatten_perks(save: Any) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for tree in getattr(save, "perk_trees", []) or []:
        for perk in tree.get("perks", []) or []:
            pid = str(perk.get("id") or "")
            if pid:
                out[pid] = perk
    return out


def _item_text(row: dict[str, Any]) -> str:
    return " ".join(str(row.get(k) or "") for k in ("id", "name", "category", "subcategory", "tweakdb_value", "area_type", "slot_label")).casefold()


def _matches(row: dict[str, Any], names: tuple[str, ...], ids: tuple[str, ...]) -> bool:
    text = _item_text(row)
    return any(x.casefold() in text for x in names) or any(x.casefold() in text for x in ids)


def _find_item(save: Any, names: tuple[str, ...] = (), ids: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    return [x for x in (getattr(save, "inventory_records", []) or []) if _matches(x, names, ids)]


def _find_equipped(save: Any, collection: str, names: tuple[str, ...] = (), ids: tuple[str, ...] = ()) -> list[dict[str, Any]]:
    return [x for x in (getattr(save, collection, []) or []) if _matches(x, names, ids)]


def _check(check_id: str, group: str, label: str, status: str, importance: str, value: str, why: str,
           evidence: list[str] | None = None, caveat: str | None = None) -> dict[str, Any]:
    return {
        "id": check_id, "group": group, "label": label, "status": status,
        "importance": importance, "value": value, "why": why,
        "evidence": evidence or [], "caveat": caveat,
    }


def evaluate_reaper_readiness(save: Any) -> dict[str, Any]:
    """Transparent v2 checklist using actual EquipmentSystem + saved stat pools.

    This remains a Companion ruleset, not an in-game hidden score. Route
    eligibility is deliberately separated from combat readiness.
    """
    attrs = getattr(save, "attributes", {}) or {}
    perks = _flatten_perks(save)
    facts = dict(getattr(save, "resolved_binary_facts", {}) or {})
    facts.update(getattr(save, "metadata_facts", {}) or {})
    checks: list[dict[str, Any]] = []

    def attr(name: str) -> int:
        try: return int(attrs.get(name, 0) or 0)
        except (TypeError, ValueError): return 0

    def has_perk(pid: str) -> bool:
        return pid in perks and int(perks[pid].get("rank", 0) or 0) > 0

    body, reflexes, tech, cool = attr("body"), attr("reflexes"), attr("technical_ability"), attr("cool")
    checks += [
        _check("body_15", "Atrybuty", "Body ≥ 15", "ready" if body >= 15 else "missing", "core", f"{body} / 15",
               "Próg dla rdzenia przeżywalności z Adrenaline Rush.", [f"metadata/body={body}"]),
        _check("body_20", "Atrybuty", "Body 20", "ready" if body >= 20 else "partial", "recommended", f"{body} / 20",
               "Dodatkowy zapas pod walkę na wyniszczenie; nie jest wymagany do udanej próby.", [f"metadata/body={body}"]),
        _check("reflexes_15", "Mobilność", "Reflexes ≥ 15", "ready" if reflexes >= 15 else "partial", "recommended", f"{reflexes} / 15",
               "Próg pod Air Dash. Build przeżywalność/control może działać bez niego.", [f"metadata/reflexes={reflexes}"]),
        _check("tech_20", "Atrybuty", "Technical Ability 20", "ready" if tech >= 20 else "partial", "recommended", f"{tech} / 20",
               "Mocny fundament pod ciężki zestaw cyberware.", [f"metadata/technical_ability={tech}"]),
        _check("cool_20", "Styl walki", "Cool 20", "ready" if cool >= 20 else "optional", "optional", str(cool),
               "Pełny dostęp do wysokich perków precyzyjnego strzelania; nie jest warunkiem trasy.", [f"metadata/cool={cool}"]),
    ]

    perk_specs = [
        ("painkiller", "Przeżywalność", "Painkiller", "core", "Stała regeneracja jest podstawą tego wariantu."),
        ("adrenaline_rush", "Przeżywalność", "Adrenaline Rush", "core", "Daje dodatkowy bufor HP podczas leczenia."),
        ("dash", "Mobilność", "Dash", "core", "Zryw daje awaryjną zmianę pozycji nawet w buildzie tank/control."),
        ("air_dash", "Mobilność", "Air Dash", "recommended", "Alternatywna ścieżka mobilności; nie jest wymagany przy mocnej przeżywalności/control."),
        ("come_back_kid", "Przeżywalność", "Comeback Kid", "recommended", "Wzmacnia odzysk zdrowia przy niskim HP."),
        ("army_of_one", "Przeżywalność", "Army of One", "recommended", "Pasuje do samotnej walki przeciw wielu przeciwnikom."),
        ("dorph_head", "Przeżywalność", "Dorph-head", "optional", "Dodatkowe wsparcie po użyciu Health Itemu."),
        ("calm_mind", "Przeżywalność", "Calm Mind", "recommended", "Wspiera utrzymanie Adrenaline."),
        ("juggernaut", "Przeżywalność", "Juggernaut", "recommended", "Wzmacnia wariant oparty na Adrenaline Rush."),
        ("cant_touch_this", "Mobilność", "Can't Touch This", "optional", "Dobrze łączy się z Dashem pod ostrzałem."),
        ("health_freak", "Leczenie", "Health Freak", "recommended", "Większa ekonomia Health Itemów; nie jest konieczny przy mocnym automatycznym leczeniu."),
        ("field_medic", "Leczenie", "Field Medic", "optional", "Wspiera leczenie podczas przemieszczania."),
        ("borrowed_time", "Leczenie", "Borrowed Time", "optional", "Dodatkowe wsparcie przy niskim HP."),
        ("edgerunner", "Cyberware", "Edgerunner", "optional", "Więcej cyberware kosztem maksymalnego HP; przy Relicu nie zawsze opłaca się agresywnie przekraczać limit."),
    ]
    for key, group, label, importance, why in perk_specs:
        pid = CORE_PERKS.get(key) or SUPPORT_PERKS.get(key)
        present = bool(pid and has_perk(pid))
        status = "ready" if present else ("missing" if importance == "core" else "partial" if importance == "recommended" else "optional")
        rank = int(perks.get(pid, {}).get("rank", 0) or 0) if pid else 0
        checks.append(_check(f"perk_{key}", group, label, status, importance, f"rank {rank}" if present else "brak", why,
                             [f"{pid} rank={rank}"] if present else ([pid] if pid else [])))

    detected_cyberware: list[dict[str, Any]] = []
    survival_equipped = 0
    for key, spec in CYBERWARE_MATCHERS.items():
        eq_hits = _find_equipped(save, "equipped_cyberware", tuple(spec["names"]), tuple(spec["ids"]))
        inv_hits = _find_item(save, tuple(spec["names"]), tuple(spec["ids"]))
        if eq_hits:
            survival_equipped += 1
            detected_cyberware.append({"id": key, "label": spec["label"], "equipped": True, "matches": eq_hits[:8]})
        elif inv_hits:
            detected_cyberware.append({"id": key, "label": spec["label"], "equipped": False, "matches": inv_hits[:8]})
        importance = "recommended" if key in {"blood_pump", "biomonitor"} else "optional"
        if eq_hits:
            status, value = "ready", "; ".join(x.get("slot_label") or x.get("area_type") or "slot" for x in eq_hits)
            evidence = [f"{x.get('name') or x.get('id') or x.get('tweakdb_value')} — {x.get('slot_label')}" for x in eq_hits]
            caveat = None
        elif inv_hits:
            status, value = ("partial" if importance == "recommended" else "optional"), "posiadasz, ale NIE jest wyposażone"
            evidence = [f"{x.get('name') or x.get('id')} [inventory]" for x in inv_hits[:4]]
            caveat = "EquipmentSystem został odczytany: to nie jest aktualnie osadzone w slocie."
        else:
            status, value = ("partial" if importance == "recommended" else "unknown"), "nie wykryto"
            evidence, caveat = [], None
        why = {
            "blood_pump": "Aktywne leczenie daje mocny bufor, gdy skryptowo maleje maksymalne HP.",
            "biomonitor": "Automatyczne leczenie zabezpiecza przed nagłym spadkiem HP.",
            "second_heart": "Opcjonalny bezpiecznik na pojedynczy błąd.",
            "epimorphic_skeleton": "Opcjonalne zwiększenie przeżywalności przez większy zapas zdrowia/pancerza.",
        }[key]
        checks.append(_check(f"cyberware_{key}", "Cyberware", spec["label"], status, importance, value, why, evidence, caveat))

    equipped_weapons = list(getattr(save, "equipped_weapons", []) or [])
    strong_equipped: list[dict[str, Any]] = []
    for display, terms in COMBAT_WEAPONS:
        hits = [x for x in equipped_weapons if _matches(x, tuple(terms), tuple(terms))]
        if hits:
            strong_equipped.append({"name": display, "matches": hits})
    if equipped_weapons:
        weapon_value = ", ".join(f"{x.get('slot_label')}: {x.get('name') or x.get('id') or x.get('tweakdb_value')}" for x in equipped_weapons)
        weapon_status = "ready" if strong_equipped else "partial"
        evidence = [f"{x.get('slot_label')} — {x.get('name') or x.get('id') or x.get('tweakdb_value')}" for x in equipped_weapons]
    else:
        weapon_value, weapon_status, evidence = "brak danych z EquipmentSystem", "unknown", []
    checks.append(_check("weapon_package", "Broń", "Aktualnie wyposażony zestaw", weapon_status, "recommended", weapon_value,
                         "v0.5 sprawdza trzy faktyczne sloty Weapon, a nie samą obecność broni w plecaku.", evidence))

    stats = getattr(save, "player_stats", {}) or {}
    health = stats.get("health") or {}
    max_health = health.get("max")
    current_percent = health.get("current_percent")
    health_status = health.get("status")
    health_source = health.get("source")
    if max_health is not None:
        health_value = f"max {max_health}; current {current_percent}%"
        health_why = "StatPoolsSystem daje dokładny zapisany maxValue i currentValue dla tego save'a."
        health_evidence = [f"{health_source or 'StatPoolsSystem'}/Health"]
        check_status = "info"
    else:
        health_value = "nie zapisano dokładnej puli Health w tym save"
        health_why = (
            "StatsSystem przechowuje wejścia/modyfikatory, ale nie materializuje końcowego Max Health. "
            "Companion celowo nie zgaduje HP z atrybutów ani modyfikatorów."
        )
        health_evidence = [f"health-resolution={health_status}"] if health_status else []
        check_status = "unknown"
    checks.append(_check("health_pool", "Przeżywalność", "Health stat pool", check_status, "info",
                         health_value, health_why, health_evidence, health.get("note")))
    humanity = stats.get("saved_humanity_additive")
    checks.append(_check("humanity_saved", "Cyberware", "Saved Humanity modifiers", "info" if humanity is not None else "unknown", "info",
                         str(humanity) if humanity is not None else "nieodczytane",
                         "To suma zapisanych dodatnich modyfikatorów Humanity. Nie nazywamy jej automatycznie końcową Cyberware Capacity.",
                         [f"StatsSystem Humanity additive={humanity}"] if humanity is not None else []))
    checks.append(_check("capacity_effective", "Cyberware", "Effective Cyberware Capacity", "unknown", "info", "not resolved",
                         "Silnik składa capacity z wielu źródeł; v0.5 nie zgaduje wyniku bez potwierdzonego wzoru.", [],
                         "Saved Humanity jest pokazane osobno jako pewny składnik zapisu."))

    johnny_friend = int(facts.get("sq032_johnny_friend", 0) or 0)
    route = {
        "status": "signal" if johnny_friend > 0 else "unknown",
        "label": "Route eligibility",
        "value": f"sq032_johnny_friend={johnny_friend}" if johnny_friend else "brak potwierdzonego sygnału",
        "note": "To sygnał fabularny, nie dowód wyboru konkretnego zestawu dialogów wymaganych do pojawienia się samotnej opcji.",
    }
    checks.append(_check("secret_route_signal", "Ścieżka", "Johnny friend flag", route["status"], "info", route["value"], route["note"],
                         [route["value"]] if johnny_friend else []))
    checks.append(_check("relic_hp_decay", "Relic", "Spadek maksymalnego HP w sekwencji", "info", "info", "nie jest anulowany przez build",
                         "Leczenie i przeżywalność pomagają przetrwać, ale nie cofają skryptowej redukcji maksymalnego HP."))

    core_checks = [x for x in checks if x["importance"] == "core"]
    core_ready = sum(1 for x in core_checks if x["status"] == "ready")
    recommended_checks = [x for x in checks if x["importance"] == "recommended"]
    recommended_ready = sum(1 for x in recommended_checks if x["status"] == "ready")
    recommended_known = sum(1 for x in recommended_checks if x["status"] in {"ready", "partial", "missing"})
    if core_ready == len(core_checks):
        overall, headline = "READY", "Rdzeń buildu jest gotowy do samotnej próby."
    elif core_ready >= max(1, len(core_checks) - 1):
        overall, headline = "PARTIAL", "Brakuje jednego elementu rdzenia buildu."
    else:
        overall, headline = "NOT READY", "Brakuje kilku elementów rdzenia buildu."

    mobility_ready = reflexes >= 15 and has_perk(SUPPORT_PERKS["air_dash"])
    survival_control_ready = has_perk(CORE_PERKS["painkiller"]) and has_perk(CORE_PERKS["adrenaline_rush"]) and survival_equipped >= 2
    profiles = [
        {"id": "survivability-control", "label": "Survivability / control", "status": "ready" if survival_control_ready else "partial",
         "evidence": f"survival implants equipped: {survival_equipped}; Painkiller={has_perk(CORE_PERKS['painkiller'])}; Adrenaline Rush={has_perk(CORE_PERKS['adrenaline_rush'])}"},
        {"id": "mobility", "label": "Mobility / kite", "status": "ready" if mobility_ready else "partial",
         "evidence": f"Reflexes={reflexes}; Air Dash={has_perk(SUPPORT_PERKS['air_dash'])}"},
    ]

    next_actions = [x for x in checks if x["importance"] in {"core", "recommended"} and x["status"] in {"missing", "partial"}][:8]
    return {
        "ruleset": "dont-fear-the-reaper-v2",
        "overall": overall, "headline": headline,
        "core_ready": core_ready, "core_total": len(core_checks),
        "recommended_ready": recommended_ready, "recommended_known": recommended_known,
        "combat_readiness": {"status": overall, "profiles": profiles},
        "route_eligibility": route,
        "checks": checks,
        "next_actions": [{"id": x["id"], "label": x["label"], "group": x["group"], "why": x["why"], "value": x["value"]} for x in next_actions],
        "detected_cyberware": detected_cyberware,
        "detected_weapons": strong_equipped,
        "equipped_weapon_count": len(equipped_weapons),
        "equipped_cyberware_count": len(getattr(save, "equipped_cyberware", []) or []),
        "notes": [
            "READY oznacza gotowość rdzenia buildu według jawnego rulesetu Companiona, nie gwarancję wygranej.",
            "v0.5 odczytuje EquipmentSystem: cyberware i bronie oznaczone EQUIPPED są faktycznie zapisane w aktywnych slotach.",
            "Health pochodzi z StatPoolsSystem; Saved Humanity z StatsSystem. Effective Cyberware Capacity pozostaje nierozwiązane zamiast zgadywane.",
            "Mobilność/Air Dash i survivability/control są traktowane jako alternatywne style, a nie jeden obowiązkowy build.",
            "Route eligibility jest oddzielone od combat readiness; sq032_johnny_friend jest tylko sygnałem.",
            "Skryptowa redukcja maksymalnego HP w Don't Fear the Reaper nie jest traktowana jako coś, co build może wyłączyć.",
        ],
    }
