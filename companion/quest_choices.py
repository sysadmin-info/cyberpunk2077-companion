"""Curated consequences plus conservative evidence from one selected save."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any
import json
import re

from .firestarter import classify as firestarter_stage

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "quest_choices.json"


FIRESTARTER_LABELS = {
    "songbird": "Ścieżka Songbird: pomoc w ucieczce.",
    "reed": "Ścieżka Reeda: próba schwytania Songbird.",
    "conflict": "Sprzeczne sygnały w tym zapisie. Nie przypisano ścieżki.",
    "past": "Zadanie ukończone. Zapis nie wskazuje strony wyboru.",
    "candidate": "Zadanie aktywne. Nie ustalono, czy dialog jest jeszcze dostępny.",
    "signal": "Jest sygnał zadania, ale nie wskazuje ścieżki.",
    "unknown": "Brak jednoznacznych danych o tym wyborze.",
}


@lru_cache(maxsize=1)
def load_choices() -> dict[str, Any]:
    return json.loads(DATA_PATH.read_text(encoding="utf-8"))


def choice_evidence(latest: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    """Exact IDs or explicit facts only. Never promote a chain marker to done."""
    quest_ids = spec.get("quest_ids", [])
    chain_ids = spec.get("chain_ids", [])
    finished = set(latest.get("finished_quests", []))
    tracked = set(re.findall(r"[^/\\]+", latest.get("tracked_quest_entry") or ""))
    facts = {
        **latest.get("resolved_binary_facts", {}),
        **latest.get("metadata_facts", {}),
    }
    if spec.get("id") == "firestarter":
        stage, proof = firestarter_stage(
            latest.get("metadata_facts", {}),
            finished,
            latest.get("tracked_quest_entry"),
            latest.get("resolved_binary_facts"),
        )
        done = (
            "q304" in finished
            or facts.get("q304_done") == 1
            or facts.get("q304_finished") == 1
        )
        status = (
            "done"
            if done
            else "active"
            if stage == "candidate"
            else "unknown"
            if stage == "unknown"
            else "signal"
        )
        return {
            "status": status,
            "stage": stage,
            "evidence": proof,
            "outcome": stage
            if stage in ("songbird", "reed", "conflict")
            else "not-resolved",
            "label": FIRESTARTER_LABELS[stage],
        }
    done = [f"finishedQuests:{qid}" for qid in quest_ids if qid in finished]
    if done:
        return {"status": "done", "evidence": done, "outcome": "not-resolved"}
    active = [f"trackedQuest:{qid}" for qid in quest_ids if qid in tracked]
    if active:
        return {"status": "active", "evidence": active, "outcome": "not-resolved"}
    signals = []
    for key, value in sorted(facts.items()):
        if value and any(key == qid or key.startswith(qid + "_") for qid in quest_ids + chain_ids):
            signals.append(f"{key}={value}")
    signals += [f"finishedChain:{qid}" for qid in chain_ids if qid in finished]
    signals += [f"trackedChain:{qid}" for qid in chain_ids if qid in tracked]
    return {"status": "signal" if signals else "unknown", "evidence": signals[:12], "outcome": "not-resolved"}


def quest_choices_payload(latest: dict[str, Any]) -> dict[str, Any]:
    data = load_choices()
    records = [{**row, "save_evidence": choice_evidence(latest, row)} for row in data["records"]]
    return {"schema": "cp2077-companion/quest-choices-v1", "save_name": latest.get("save_name"),
            "lifepath": latest.get("life_path"), "has_phantom_liberty": latest.get("has_phantom_liberty"),
            "checked_on": data["checked_on"], "records": records,
            "counts": {"total": len(records), **{status: sum(r["save_evidence"]["status"] == status for r in records) for status in ("done", "active", "signal", "unknown")}},
            "notes": ["Katalog wybranych rozgałęzień, nie kompletny poradnik wszystkich zadań. Skutki sprawdzono w źródłach; nie testowano każdej gałęzi w grze.",
                      "Status dotyczy wyłącznie wybranego save'a. Sygnał całego łańcucha nie potwierdza rozegrania konkretnego zadania ani wybranego wariantu.",
                      "Nie ustalono nie znaczy dostępne, niedostępne ani jeszcze nieukończone. Moment nieodwracalnego wyboru nie jest automatycznie rozpoznawany.",
                      "Eksport JSON zawiera pełne konsekwencje; Markdown umieszcza je w sekcjach details. Źródła również mogą zawierać spoilery."]}
