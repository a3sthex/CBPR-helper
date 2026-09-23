#!/usr/bin/env python3
"""Fill Street-File.pdf with DODGE (Rafael Mora). No portraits."""
from pathlib import Path
import fitz

PDF = Path(__file__).resolve().parent / "Street-File.pdf"

TEXT = {
    "CaseNo": "SF-76-VDR-MORA",
    "Precinct": "HYW / Vista · H5",
    "FileDate": "2076",
    "FileUpdated": "",
    "Player": "",
    "FilePrice": "300",
    "SourceReliability": "3",
    "Handle": "DODGE",
    "Real Name": "Rafael Mora",
    "Aliases": "el verdugo del Rey · Mora",
    "Role": "Lawman",
    "Rank": "4",
    "Role2": "",
    "Rank2": "",
    "CoverOccupation": "skiptrace / off-books enforcement",
    "Heat": "NCPD personal · Glen aide · H5 Valentinos",
    "DeadDrop": "Mercado Sonora — stall, not the chapel",
    "Backer": "none (Dwyer unofficial)",
    "Owed": "Dwyer — blood if heavies drop",
    "Owing": "Ruiz — the report · Tran — one call",
    "Age": "24",
    "Sex": "he/him",
    "Height": "183 cm",
    "Weight": "85 kg",
    "Eyes": "brown",
    "Hair": "black, cropped",
    "Agent": "",
    "SIN": "Academy SIN — FLAGGED",
    "Badge": "NCPD Heywood — PULLED",
    "Languages": "Streetslang · Spanish · English",
    "BOLO": (
        "Powder-burn scar, left jaw (Floor 22). Short regulation cut gone slightly long. "
        "On the street: slim tactical visor mask, hood up, open overcoat, plate carrier. "
        "Pulled badge in the jacket, never on the chest. Heavy pistol worn like policy never ended. "
        "Walks the hallway like it belongs to him."
    ),
    "PsychProfile": (
        "Treats Vista as a courtroom. Few words. If the name is in the book, the sentence is already done. "
        "Not cyberpsycho — a cop who stopped waiting for a judge."
    ),
    "HowToWorkThem": (
        "Don't say “let the law handle it.” Don't touch Casa / H5 civilians as leverage. "
        "Offer a name already in the book. Pay in ammo or a location, not speeches."
    ),
    "RAP": (
        "Ex-NCPD beat, Megabuilding H5. Floor 22: three down, “resisted,” badge pulled. Still armed. "
        "Can throw: four phones on the force, the stack's map, Unity + Satara. "
        "What's gonna happen: he finishes the list."
    ),
    "StreetTalk": (
        "“That cop from H5 they fired.” Some say verdugo, some say rat. "
        "Valentinos don't toast him. Glen doesn't either."
    ),
    "OccupationHistory": (
        "Beat / patrol, Vista · H5. Moonlight gigs as hallway muscle and skiptrace. "
        "M.O.: one floor, one pistol, report reads “resisted arrest.” "
        "Lifepath: Beat · Heywood patrol · Corruption 5 · hunted by H5 Valentinos + Glen · target: street crime on his stack."
    ),
    "Goals": (
        "Finish H5 / La Catrina names. Stay useful enough that Ruiz still picks up. "
        "Don't die as an eight-second BD."
    ),
    "Leverage": "A name in the book. A clean shot at the Glen fixer. The stack.",
    "Approach": "Burns a choom if they're in the book. Won't burn Ruiz for free.",
    "ValuedPerson": "El Sereno — childhood rumor, H5 stairs after midnight. DO NOT TOUCH",
    "ValuedPossession": "The notebook. The pulled badge.",
    "Associates": "Elena Ruiz · Sgt. Frank Dwyer · Marcus “Oz” Osorio · Kim Tran",
    "Enemies": "H5 Valentinos · La Catrina crew · Glen aide · BD seller",
    "Affairs": "Floor 22 · scav BD · IA file",
    "Origin": "Hispanic Heywood · Vista del Rey · street-Catholic varnish",
    "Childhood": "Megabuilding H5, Vista del Rey",
    "FamilyCrisis": "Older brother ran with the H5 Valentinos. Died before Dodge put on a badge. That's the book.",
    # stats
    "INT": "5",
    "REF": "8",
    "DEX": "8",
    "TECH": "4",
    "COOL": "8",
    "WILL": "7",
    "MOVE": "6",
    "BODY": "7",
    "Luck Current": "4",
    "LUCK": "4",
    "EMP Current": "5",
    "EMP": "5",
    "HP": "45",
    "HP Max": "45",
    "SeriouslyWounded": "23",
    "DeathSave": "7",
    "DeathSavePenalty": "",
    "Humanity": "50",
    "Humanity Max": "50",
    "HumanityLossTotal": "0",
    "MedAlert": "powder burn, left jaw — Floor 22",
    "RoleAbility": (
        "Backup 4. Action: d10≤4, then 1d6 rd. Not dispatch — Ruiz, Dwyer, Oz, Tran. "
        "Beat-cop numbers (Combat 10, SP 7, HP 25, Heavy Pistol). "
        "6 on ETA = next tier; you owe Dwyer blood."
    ),
    "BackupCall": "",
    "BackupETA": "",
    "CritInjuries": "",
    "Addictions": "",
    "W1_Name": "Con Arms Unity",
    "W1_DMG": "3d6/4d6",
    "W1_Ammo": "12",
    "W1_ROF": "2",
    "W1_Notes": "Exotic HP · Power Rebuild · aimed = 4d6",
    "W2_Name": "Rostović DB-2 Satara",
    "W2_DMG": "5d6",
    "W2_Ammo": "2",
    "W2_ROF": "1",
    "W2_Notes": "Exotic SG · Tech Rebuild · 2 barrels · through walls",
    "W3_Name": "Stun Baton",
    "W3_DMG": "2d6",
    "W3_Ammo": "—",
    "W3_ROF": "2",
    "W3_Notes": "non-lethal",
    "HeadSP": "7",
    "HeadSPmax": "7",
    "HeadPenalty": "0",
    "BodySP": "11",
    "BodySPmax": "11",
    "BodyPenalty": "0",
    "Cash": "30",
    "IP_Current": "0",
    "IP_TotalEarned": "0",
    "IP_Spent": "0",
    "Reputation": "0",
    "Lifestyle": "Kibble",
    "Housing": "company (free)",
    "Rent": "0",
    "TraumaTeam": "none",
    "RepEvent1": "Floor 22, H5",
    "FlatlineTT": "none",
    "FlatlineRipper": "",
    "FlatlineCall": "Elena Ruiz",
    "Gear": (
        "Agent\n"
        "Grapple Gun\n"
        "Handcuffs\n"
        "Radio Scanner / Music Player\n"
        "Binoculars\n"
        "Airhypo (empty)\n"
        "Flashlight\n"
        "Anti-Smog Breathing Mask\n"
        "Carryall\n"
        "Duct Tape\n"
        "Rope 60m\n"
        "Lock Picking Set\n"
        "Medtech Bag\n"
        "Speedheal x1\n"
        "Glow Paint\n"
        "Memory Chips"
    ),
    "FashionInventory": (
        "Urban Flash: jacket, bottoms, top, footwear\n"
        "Urban Flash Mirrorshades\n"
        "Leisurewear: jacket, bottoms, top, footwear\n"
        "Jewelry (badge chain)\n"
        "Generic Chic hat"
    ),
    "Notes": (
        "Notebook lives in the jacket. Badge pulled, still in the pocket.\n"
        "Backup is named — not dispatch. See xlsx CONTACTS.\n"
        "El Sereno is a rumor. Do not hunt it.\n"
        "No Neuroport. Do not offer chrome.\n"
        "Satara: barrel A Basic Shell / barrel B Explosive Slug."
    ),
    "Ammo1_Type": "Basic Heavy Pistol",
    "Ammo1_Qty": "50",
    "Ammo2_Type": "Basic Shotgun Shell",
    "Ammo2_Qty": "20",
    "Ammo3_Type": "Explosive Slug",
    "Ammo3_Qty": "20",
    "Ammo4_Type": "Flashbang",
    "Ammo4_Qty": "1",
    "Ammo5_Type": "Smoke Grenade",
    "Ammo5_Qty": "1",
    "Language 2 Spec": "Spanish",
    "Language 2": "4",
    "Language 2 BASE": "9",
    "Language 3 Spec": "",
    "Language 3": "0",
    "Language 3 BASE": "5",
    "Local Expert 2 Spec": "",
    "Local Expert 2": "0",
    "Local Expert 2 BASE": "5",
    "Science Spec": "",
    "Martial Arts Spec": "",
    "Martial Arts 2 Spec": "",
    "Play Instrument Spec": "",
    "Play Instrument 2 Spec": "",
    "FA_1": "Skinwatch (fashionware, 0 HL)",
    "FA_2": "EMP Threading (fashionware, 0 HL)",
    "ChromeNotes": "No Neuroport. NCPD chip never sat. Do not install. Quickhack: not a valid jack target.",
}

# Complete Package: 86 pts, max 6, x2 skills cost 2/level.
# Mandatory ≥2: Athletics, Brawling, Concentration, Conversation, Education,
# Evasion, First Aid, Human Perception, Streetslang, Local Expert (home),
# Perception, Persuasion, Stealth. Cultural origin Language 4 is free (Spanish).
# SA 6 (x2=12) made the old list 90. Cut Conversation 4→2 and Criminology 2→0.
STAT = {
    "INT": 5, "REF": 8, "DEX": 8, "TECH": 4, "COOL": 8, "WILL": 7, "EMP": 5,
}

# name -> (stat, lvl, x2)
SKILL_DEF = {
    "Concentration": ("WILL", 2, False),
    "Conceal/Reveal Object": ("INT", 0, False),
    "Lip Reading": ("INT", 0, False),
    "Perception": ("INT", 6, False),
    "Tracking": ("INT", 0, False),
    "Athletics": ("DEX", 4, False),
    "Contortionist": ("DEX", 0, False),
    "Dance": ("DEX", 0, False),
    "Endurance": ("WILL", 0, False),
    "Resist Torture/Drugs": ("WILL", 2, False),
    "Stealth": ("DEX", 2, False),
    "Drive Land Vehicle": ("REF", 0, False),
    "Pilot Air Vehicle": ("REF", 0, True),
    "Pilot Sea Vehicle": ("REF", 0, False),
    "Riding": ("REF", 0, False),
    "Accounting": ("INT", 0, False),
    "Animal Handling": ("INT", 0, False),
    "Bureaucracy": ("INT", 2, False),
    "Business": ("INT", 0, False),
    "Composition": ("INT", 0, False),
    "Criminology": ("INT", 0, False),
    "Cryptography": ("INT", 0, False),
    "Deduction": ("INT", 0, False),
    "Education": ("INT", 2, False),
    "Gamble": ("INT", 0, False),
    "Language (Streetslang)": ("INT", 4, False),
    "Library Search": ("INT", 0, False),
    "Local Expert": ("INT", 6, False),
    "Science": ("INT", 0, False),
    "Tactics": ("INT", 0, False),
    "Wilderness Survival": ("INT", 0, False),
    "Brawling": ("DEX", 6, False),
    "Evasion": ("DEX", 6, False),
    "Martial Arts": ("DEX", 0, True),
    "Martial Arts 2": ("DEX", 0, True),
    "Melee Weapon": ("DEX", 4, False),
    "Acting": ("COOL", 0, False),
    "Play Instrument": ("TECH", 0, False),
    "Play Instrument 2": ("TECH", 0, False),
    "Archery": ("REF", 0, False),
    "Autofire": ("REF", 0, True),
    "Handgun": ("REF", 6, False),
    "Heavy Weapons": ("REF", 0, True),
    "Shoulder Arms": ("REF", 6, True),
    "Bribery": ("COOL", 0, False),
    "Conversation": ("EMP", 2, False),
    "Human Perception": ("EMP", 4, False),
    "Interrogation": ("COOL", 6, False),
    "Persuasion": ("COOL", 2, False),
    "Personal Grooming": ("COOL", 0, False),
    "Streetwise": ("COOL", 6, False),
    "Trading": ("COOL", 0, False),
    "Wardrobe & Style": ("COOL", 0, False),
    "Air Vehicle Tech": ("TECH", 0, False),
    "Basic Tech": ("TECH", 0, False),
    "Cybertech": ("TECH", 0, False),
    "Demolitions": ("TECH", 0, True),
    "Electronics/Security Tech": ("TECH", 0, True),
    "First Aid": ("TECH", 2, False),
    "Forgery": ("TECH", 0, False),
    "Land Vehicle Tech": ("TECH", 0, False),
    "Paint/Draw/Sculpt": ("TECH", 0, False),
    "Paramedic": ("TECH", 0, True),
    "Photography/Film": ("TECH", 0, False),
    "Pick Lock": ("TECH", 0, False),
    "Pick Pocket": ("TECH", 0, False),
    "Sea Vehicle Tech": ("TECH", 0, False),
    "Weaponstech": ("TECH", 0, False),
}

MUST_MIN2 = {
    "Athletics", "Brawling", "Concentration", "Conversation", "Education",
    "Evasion", "First Aid", "Human Perception", "Language (Streetslang)",
    "Local Expert", "Perception", "Persuasion", "Stealth",
}

SKILLS = {}  # name -> (lvl, base)
for _n, (_st, _lvl, _x2) in SKILL_DEF.items():
    SKILLS[_n] = (_lvl, STAT[_st] + _lvl)


def _assert_creation_legal():
    cost = 0
    for n, (st, lvl, x2) in SKILL_DEF.items():
        if not (0 <= lvl <= 6):
            raise SystemExit(f"{n} lvl {lvl} not in 0–6")
        if n in MUST_MIN2 and lvl < 2:
            raise SystemExit(f"{n} mandatory min 2, got {lvl}")
        cost += lvl * (2 if x2 else 1)
    # Spanish 4 free — not in SKILL_DEF cost
    if cost != 86:
        raise SystemExit(f"skill cost {cost} != 86")
    print("Complete Package skills OK: 86 pts, max 6, mandatory ≥2, Spanish 4 free")

CHECKS_ON = {"DoNotBurn", "Class_POI"}


def main():
    _assert_creation_legal()
    doc = fitz.open(PDF)
    filled, missing = 0, []
    seen = set()
    for page in doc:
        for w in page.widgets() or []:
            name = w.field_name
            seen.add(name)
            if name in CHECKS_ON:
                w.field_value = True
                w.update()
                filled += 1
                continue
            if name in TEXT:
                w.field_value = TEXT[name]
                w.update()
                filled += 1
                continue
            if name in SKILLS:
                w.field_value = str(SKILLS[name][0])
                w.update()
                filled += 1
                continue
            if name.endswith(" BASE"):
                base = name[: -len(" BASE")]
                if base in SKILLS:
                    w.field_value = str(SKILLS[base][1])
                    w.update()
                    filled += 1
    tmp = PDF.with_suffix(".filled.pdf")
    doc.save(tmp, deflate=True)
    doc.close()
    tmp.replace(PDF)
    print("filled widgets", filled)
    print("wrote", PDF, "size", PDF.stat().st_size)


if __name__ == "__main__":
    main()
