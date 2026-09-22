# NC//NET Street File

Unofficial, offline Cyberpunk RED packet. Not affiliated with R. Talsorian Games or CD PROJEKT.

| File | What |
|---|---|
| `Street-File.pdf` | 4-page **A4 landscape** fillable dossier (AcroForm) |
| `Street-File.xlsx` | Ledger, contacts, role tabs, play-screen tables (all sheets landscape) |

English labels. Rebuild:

```
sheets/.venv/bin/python sheets/build_street_file.py
```

## PDF pages

0. Hybrid NCPD / Operator dossier (two photos, rephrased lifepath)
1. Edgerunner — stats (LUCK/EMP as cur/max), skills, weapons, Combat Awareness, backup
2. Street kit — cash, IP, gear, fashion inventory, **IN CASE OF FLATLINE**
3. Chrome — Neuroport suite + slots (NET programs are in the xlsx)

**Source of truth:** PDF = who you are (stats, skills, chrome, dossier). xlsx META/LEDGER = €$, IP, heat, people, jobs. After a session, copy Cash / IP / Heat from META onto PDF page 2.

**Photos:** In Adobe Acrobat, click BOOKING PHOTO / KNOWN PHOTOGRAPH and import. In a browser viewer the frames stay empty — print and paste.

**Calc:** fill LVL yourself; STAT is printed; BASE = LVL + STAT (write it, or let Acrobat if you add a script). HP = `10 + 5×⌈(BODY+WILL)/2⌉`. Death Save = BODY. Humanity max = EMP max × 10.

## xlsx tabs

META · LEDGER · CONTACTS · NET · GARAGE · WORKSHOP · CLINIC · TEAM · WISHLIST · REF_COMBAT · REF_RANGE · REF_DV
