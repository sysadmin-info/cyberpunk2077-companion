"""Firestarter evidence. Quest progress, route and save chronology are separate."""

from __future__ import annotations

import re


def classify(facts, finished, tracked="", binary=None):
    """Only affirmative, exact markers identify the initial route, never a later ending."""
    binary = binary or {}
    merged = {**binary, **facts}
    finished = set(finished)
    segments = set(re.split(r"[/\\]", tracked or ""))

    def flags(*names):
        return [f"{key}=1" for key in names if merged.get(key) == 1]

    def journal(q):
        return ([f"finishedQuests:{q}"] if q in finished else []) + (
            [f"trackedQuest:{q}"] if q in segments else []
        )

    def route(q):
        return journal(q) + flags(
            *(q + s for s in ("_started", "_active", "_done", "_finished"))
        )

    direct = "q304_songbirds_path"
    song = flags(direct) + route("q306")
    reed = route("q305")
    if direct in binary and direct in facts and binary[direct] != facts[direct]:
        return "conflict", [
            f"metadata:{direct}={facts[direct]}",
            f"binary:{direct}={binary[direct]}",
            *reed,
            *song,
        ]
    if song and reed:
        return "conflict", song + reed
    if song:
        return "songbird", song
    if reed:
        return "reed", reed
    done = (["finishedQuests:q304"] if "q304" in finished else []) + flags(
        "q304_done", "q304_finished"
    )
    if done:
        return "past", done
    # Both routes can have a dead Hansen. Never offer such a slot as a pre-choice candidate.
    later = flags("q304_kurt_dead", "q304_stadium_escape_active")
    if later:
        return "signal", later
    active = flags("q304_active")
    if "q304" in segments and merged.get("q304_active") != 0:
        active.append("trackedQuest:q304")
    if active:
        return "candidate", active
    started = flags("q304_started")
    return ("signal", started) if started else ("unknown", [])


def slot_kind(slot):
    name = slot.casefold()
    for prefix, kind in (
        ("manualsave-", "manual"),
        ("autosave-", "auto"),
        ("quicksave-", "quick"),
    ):
        if name.startswith(prefix):
            return kind
    return "other"


def _window(ordered):
    """Return all ties. Never infer a sequence from a slot's name or from an invalid clock."""
    dated = [r for r in ordered if r["time_iso"]]
    candidates = [r for r in dated if r["stage"] == "candidate"]
    candidate_time = candidates[0]["time_iso"] if candidates else ""
    confirmed = [r for r in dated if r["stage"] in ("songbird", "reed")]
    later = [r for r in confirmed if r["time_iso"] > candidate_time]
    after_time = later[-1]["time_iso"] if later else ""
    return {
        "candidates": [
            r["slot"] for r in candidates if r["time_iso"] == candidate_time
        ],
        "first_confirmed": [r["slot"] for r in later if r["time_iso"] == after_time],
        "same_time": bool(
            candidate_time and any(r["time_iso"] == candidate_time for r in confirmed)
        ),
        "both_routes": {r["stage"] for r in ordered} >= {"reed", "songbird"},
    }


def summarize(rows):
    ordered = sorted(rows, key=lambda r: (r["time_iso"], r["slot"]), reverse=True)
    windows = {"all": _window(ordered)}
    for kind in ("manual", "auto", "quick", "other"):
        windows[kind] = _window([r for r in ordered if r["kind"] == kind])
    return {"rows": ordered, "windows": windows}
