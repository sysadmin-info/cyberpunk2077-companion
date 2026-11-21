from __future__ import annotations

# Catalog is deliberately curated. The engine can grow independently of it.
QUESTS = [
    # Main / endings
    {"id": "q112", "name": "Play It Safe / parade chain", "group": "Main"},
    {"id": "q115", "name": "Nocturne OP55N1 / point of no return", "group": "Main"},
    {"id": "sq031", "name": "Chippin' In — Johnny / Rogue", "group": "Johnny & Rogue"},
    {"id": "sq032", "name": "Blistering Love / Johnny follow-up", "group": "Johnny & Rogue"},
    # Panam
    {"id": "sq004", "name": "Riders on the Storm", "group": "Panam"},
    {"id": "sq027", "name": "Panam / Aldecaldos side chain", "group": "Panam"},
    # Peralez / River
    {"id": "sq012", "name": "I Fought the Law — Peralezowie / River", "group": "Night City mysteries"},
    {"id": "sq006", "name": "Dream On — Peralezowie", "group": "Night City mysteries"},
    {"id": "sq021", "name": "The Hunt — River / Randy", "group": "River"},
    # Night Corp / Blackwall-adjacent / mysteries
    {"id": "mq015", "name": "Spellbound — Nix", "group": "Night City mysteries"},
    {"id": "mq016", "name": "KOLD MIRAGE — Bartmoss / Nix", "group": "Night City mysteries"},
    {"id": "mq024", "name": "Full Disclosure — Sandra Dorsett / Night Corp", "group": "Night City mysteries"},
    {"id": "mq026", "name": "The Prophet's Song — Garry", "group": "Night City mysteries"},
    {"id": "mq030", "name": "Bullets — Jinguji", "group": "Night City mysteries"},
    {"id": "mq033", "name": "Fool on the Hill — tarot", "group": "Night City mysteries"},
    {"id": "mq037", "name": "Coin Operated Boy — Brendan", "group": "Night City mysteries"},
    {"id": "mq007", "name": "Machine Gun — Skippy", "group": "Side jobs"},
    {"id": "mq028", "name": "Every Breath You Take — Blue Moon", "group": "Side jobs"},
    {"id": "mq029", "name": "The Highwayman", "group": "Side jobs"},
    {"id": "sq023", "name": "Sinnerman chain", "group": "Side jobs"},
    # Phantom Liberty
    {"id": "q301", "name": "Dog Eat Dog / Phantom Liberty opening", "group": "Phantom Liberty"},
    {"id": "q304", "name": "Firestarter", "group": "Phantom Liberty"},
    {"id": "q305", "name": "Somewhat Damaged / Reed path chain", "group": "Phantom Liberty"},
    {"id": "q306", "name": "The Killing Moon / Songbird path chain", "group": "Phantom Liberty"},
    {"id": "mq303", "name": "Dazed and Confused", "group": "Phantom Liberty"},
    {"id": "mq304", "name": "Run This Town", "group": "Phantom Liberty"},
    {"id": "mq305", "name": "Shot by Both Sides", "group": "Phantom Liberty"},
    {"id": "mq306", "name": "No Easy Way Out", "group": "Phantom Liberty"},
]

# Fact names whose semantics are either explicit in the internal name or useful as raw evidence.
DECISION_FACTS = [
    ("q000_corpo_background", "Lifepath fact", "Corpo background recorded", "high"),
    ("q103_helped_panam", "Panam", "Helped Panam", "high"),
    ("sq027_panam_lover", "Panam", "Panam romance flag", "high"),
    ("sq032_johnny_friend", "Johnny", "Johnny friend flag", "high"),
    ("sq031_rogue_met_johnny", "Rogue / Johnny", "Johnny met Rogue during the side chain", "high"),
    ("sq031_rogue_lover", "Rogue / Johnny", "Rogue relationship-scene flag", "medium"),
    ("q103_rogue_met", "Rogue", "Rogue met flag", "high"),
    ("q110_08a_netwatch_deal", "Voodoo Boys / NetWatch", "NetWatch deal flag", "raw"),
    ("q110_voodoo_queen_dead", "Voodoo Boys / NetWatch", "Voodoo queen dead flag", "high"),
    ("q112_takemura_dead", "Takemura", "Takemura dead flag", "high"),
    ("q304_kurt_dead", "Phantom Liberty", "Kurt Hansen dead flag", "high"),
    ("q305_fact_songbird_dead", "Phantom Liberty", "Songbird dead flag", "high"),
    ("mq304_bennett_boss", "Dogtown succession", "Bennett boss flag", "high"),
    ("mq304_jago_adjutant", "Dogtown succession", "Jago adjutant flag", "high"),
]

KNOWN_FACT_NAMES = {name for name, *_ in DECISION_FACTS}
KNOWN_FACT_NAMES.update({"q304_songbirds_path", "q304_stadium_escape_active"})
for quest in QUESTS:
    qid = quest["id"]
    for suffix in ("_done", "_finished", "_active", "_started", "_start"):
        KNOWN_FACT_NAMES.add(qid + suffix)

# v0.2: curated TweakDB records used to validate the read-only inventory parser.
# The parser can see unknown hashes too; this catalog only gives human names to
# records whose identifiers we have independently validated.
KNOWN_ITEMS = [
    {"id": "Items.money", "name": "Eurodollars", "category": "currency"},
    {"id": "Items.Preset_Achilles_Nash", "name": "Widow Maker", "category": "iconic weapon"},
    {"id": "Items.Preset_Silverhand_3516", "name": "Malorian Arms 3516", "category": "iconic weapon"},
    {"id": "Items.Preset_Shingen_Prototype", "name": "Prototype: Shingen Mark V", "category": "iconic weapon"},
    {"id": "Items.Preset_Grad_Panam", "name": "Overwatch", "category": "iconic weapon"},
    {"id": "Items.Preset_Nekomata_Breakthrough", "name": "Breakthrough", "category": "iconic weapon"},
    {"id": "Items.Preset_Zhuo_Eight_Star", "name": "Ba Xing Chong", "category": "iconic weapon"},
    {"id": "Items.AdvancedStrongArmsLegendary", "name": "Gorilla Arms", "category": "cyberware"},
    {"id": "Items.AdvancedBerserkC4MK5", "name": "Militech Berserk", "category": "cyberware"},
    {"id": "Items.Preset_Liberty_Rogue", "name": "Pride", "category": "ending reward"},
    {"id": "Items.Preset_Masamune_Rogue", "name": "Prejudice", "category": "ending reward"},
    {"id": "Items.Preset_Liberty_Rogue_Stash", "name": "Pride", "category": "ending reward"},
    {"id": "Items.Preset_Masamune_Rogue_Stash", "name": "Prejudice", "category": "ending reward"},
    {"id": "Items.Legendary_Zhuo_Eight_Star", "name": "Ba Xing Chong", "category": "iconic weapon"},
    {"id": "Items.Epic_Nekomata_Breakthrough", "name": "Breakthrough", "category": "iconic weapon"},
    {"id": "Items.AdvancedEndoSkeletonLegendary2PlusPlus", "name": "Epimorphic Skeleton", "category": "cyberware"},
    {"id": "Items.CasiusTattoo", "name": "Tattoo: Johnny\'s Special", "category": "cyberware"},
    # Exact deck records observed in the supplied 2.31 loadouts. No tier/name
    # guesses for other OS hashes when the optional TSV is unavailable.
    {"id": "Items.AdvancedMilitechParalineMK1Common", "name": "Militech Paraline Mk.1", "category": "cyberware"},
    {"id": "Items.AdvancedMilitechParalineMK1CommonPlus", "name": "Militech Paraline Mk.1", "category": "cyberware"},
    {"id": "Items.AdvancedMilitechParalineMK2Uncommon", "name": "Militech Paraline Mk.2", "category": "cyberware"},
    {"id": "Items.AdvancedMilitechParalineMKIIIRarePlus", "name": "Militech Paraline Mk.3", "category": "cyberware"},
]

# v0.4: CP2077 2.x cyberware BaseID families used by the Reaper readiness
# ruleset.  These aliases let the read-only parser recognize the important
# survival implants even when the optional external item catalog is unavailable.
for _suffix in (
    "Uncommon", "UncommonPlus", "Rare", "RarePlus", "Epic", "EpicPlus",
    "Legendary", "LegendaryPlus", "LegendaryPlusPlus",
):
    KNOWN_ITEMS.append({"id": f"Items.AdvancedBloodPump{_suffix}", "name": "Blood Pump", "category": "cyberware"})
for _suffix in (
    "Common", "CommonPlus", "Uncommon", "UncommonPlus", "Rare", "RarePlus",
    "Epic", "EpicPlus", "Legendary", "LegendaryPlus", "LegendaryPlusPlus",
):
    KNOWN_ITEMS.append({"id": f"Items.AdvancedBiomonitor{_suffix}", "name": "Biomonitor", "category": "cyberware"})
for _suffix in ("Epic", "EpicPlus", "Legendary", "LegendaryPlus", "LegendaryPlusPlus"):
    KNOWN_ITEMS.append({"id": f"Items.AdvancedSecondHeart{_suffix}", "name": "Second Heart", "category": "cyberware"})
    KNOWN_ITEMS.append({"id": f"Items.AdvancedEndoskeleton{_suffix}", "name": "Epimorphic Skeleton", "category": "cyberware"})
# Legacy aliases remain useful for older save branches.
for _id, _name in (
    ("Items.BloodPumpLegendary", "Blood Pump"),
    ("Items.HealthMonitorLegendary", "Biomonitor"),
    ("Items.SecondHeart", "Second Heart"),
):
    KNOWN_ITEMS.append({"id": _id, "name": _name, "category": "cyberware"})


# Internal quest path markers are much better ending evidence than the generic
# EndGameSave flag.  Keep route and epilogue evidence separate.
ENDING_MARKERS = [
    {"marker": "q115_rogues_last_flight", "kind": "route", "name": "Rogue assault on Arasaka", "ending": "Rogue / Johnny route"},
    {"marker": "q203_legend", "kind": "ending", "name": "Path of Glory", "ending": "The Sun"},
    {"marker": "q202_nomads", "kind": "ending", "name": "All Along the Watchtower", "ending": "The Star"},
    {"marker": "q204_reborn", "kind": "ending", "name": "New Dawn Fades", "ending": "Temperance"},
    {"marker": "q201_heir", "kind": "ending", "name": "Where Is My Mind?", "ending": "The Devil"},
]
