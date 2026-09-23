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
    "FA_1": "Skinwatch (fashionware, 0 HL)",
    "FA_2": "EMP Threading (fashionware, 0 HL)",
    "ChromeNotes": "No Neuroport. NCPD chip never sat. Do not install. Quickhack: not a valid jack target.",
}

# LVL, BASE
SKILLS = {
    "Athletics": (4, 12),
    "Brawling": (6, 14),
    "Bureaucracy": (2, 7),
    "Concentration": (2, 9),
    "Conversation": (4, 9),
    "Criminology": (2, 7),
    "Education": (2, 7),
    "Evasion": (6, 14),
    "First Aid": (2, 6),
    "Handgun": (6, 14),
    "Human Perception": (4, 9),
    "Interrogation": (6, 14),
    "Language (Streetslang)": (4, 9),
    "Local Expert": (6, 11),
    "Melee Weapon": (4, 12),
    "Perception": (6, 11),
    "Persuasion": (2, 10),
    "Resist Torture/Drugs": (2, 9),
    "Shoulder Arms": (6, 14),
    "Stealth": (2, 10),
    "Streetwise": (6, 14),
}

CHECKS_ON = {"DoNotBurn", "Class_POI"}


def main():
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
