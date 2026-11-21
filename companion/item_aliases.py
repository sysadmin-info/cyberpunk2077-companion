"""Curated display-name overrides for records whose public catalog labels lag the game.

The optional NightCity Console TSV is intentionally kept as the broad item-name
source.  This module is a tiny correction layer on top of that catalog.  Each
entry is backed by direct game/UI evidence or another independently validated
source, and keeps the previous/catalog label for diagnostics.

CP2077 Companion currently targets the user's patch 2.31 setup.  Do not add
localised translations here merely because they look nicer: this table is for
identity/name corrections where the underlying TweakDB record is unchanged.
"""
from __future__ import annotations

# keyed by TweakDB record ID
DISPLAY_NAME_OVERRIDES: dict[str, dict[str, str]] = {
    # The supplied 2.31 Polish-game screenshot shows this record as SULIMOV.
    # Public/community catalogs still commonly label the same record PIZDETS.
    "Items.Preset_Warden_Boris": {
        "name": "SULIMOV",
        "previous_name": "PIZDETS",
        "evidence": "observed-game-ui-2.31-pl",
    },
    # NightCity Console currently contains the long-standing 3156 typo, while
    # the game UI and the record itself are Malorian Arms 3516.
    "Items.Preset_Silverhand_3516": {
        "name": "MALORIAN ARMS 3516",
        "previous_name": "MALORIAN ARMS 3156",
        "evidence": "observed-game-ui-2.31-pl",
    },
    # The external catalog collapses the space, but the supplied game UI shows
    # the canonical two-word weapon name.
    "Items.Preset_Achilles_Nash": {
        "name": "WIDOW MAKER",
        "previous_name": "WIDOWMAKER",
        "evidence": "observed-game-ui-2.31-pl",
    },
}
