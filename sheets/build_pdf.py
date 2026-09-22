#!/usr/bin/env python3
"""Build Street-File.pdf — 4-page A4 fillable AcroForm dossier."""
from pathlib import Path

from reportlab.lib.colors import Color, HexColor, white, black
from reportlab.lib.pagesizes import A4, landscape
from reportlab.pdfbase import pdfform  # noqa: F401
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent
PRINT = ROOT / "assets" / "print"

PAGE = landscape(A4)
W, H = PAGE  # 841.89 x 595.27
M = 14

INK = HexColor("#111111")
CRIMSON = HexColor("#C41E3A")
AMBER = HexColor("#FF9F1C")
GOLD = AMBER  # alias used throughout
PAPER = white
FIELD = HexColor("#FFF7EC")
RULE = HexColor("#1A1A1A")
MUTED = HexColor("#5C5C5C")
NCPD_BG = HexColor("#111111")
FIXER_BG = HexColor("#111111")

SKILL_GROUPS = [
    ("AWARENESS", [
        ("Concentration", "WILL", "Concentration", ""),
        ("Conceal/Reveal Object", "INT", "Conceal/Reveal Object", ""),
        ("Lip Reading", "INT", "Lip Reading", ""),
        ("Perception", "INT", "Perception", ""),
        ("Tracking", "INT", "Tracking", ""),
    ]),
    ("BODY", [
        ("Athletics", "DEX", "Athletics", ""),
        ("Contortionist", "DEX", "Contortionist", ""),
        ("Dance", "DEX", "Dance", ""),
        ("Endurance", "WILL", "Endurance", ""),
        ("Resist Torture/Drugs", "WILL", "Resist Torture/Drugs", ""),
        ("Stealth", "DEX", "Stealth", ""),
    ]),
    ("CONTROL", [
        ("Drive Land Vehicle", "REF", "Drive Land Vehicle", ""),
        ("Pilot Air Vehicle (x2)", "REF", "Pilot Air Vehicle", ""),
        ("Pilot Sea Vehicle", "REF", "Pilot Sea Vehicle", ""),
        ("Riding", "REF", "Riding", ""),
    ]),
    ("EDUCATION", [
        ("Accounting", "INT", "Accounting", ""),
        ("Animal Handling", "INT", "Animal Handling", ""),
        ("Bureaucracy", "INT", "Bureaucracy", ""),
        ("Business", "INT", "Business", ""),
        ("Composition", "INT", "Composition", ""),
        ("Criminology", "INT", "Criminology", ""),
        ("Cryptography", "INT", "Cryptography", ""),
        ("Deduction", "INT", "Deduction", ""),
        ("Education", "INT", "Education", ""),
        ("Gamble", "INT", "Gamble", ""),
        ("Language (Streetslang)", "INT", "Language (Streetslang)", ""),
        ("Language", "INT", "Language 2", "spec"),
        ("Language", "INT", "Language 3", "spec"),
        ("Library Search", "INT", "Library Search", ""),
        ("Local Expert (Your Home)", "INT", "Local Expert", ""),
        ("Local Expert", "INT", "Local Expert 2", "spec"),
        ("Science", "INT", "Science", "spec"),
        ("Tactics", "INT", "Tactics", ""),
        ("Wilderness Survival", "INT", "Wilderness Survival", ""),
    ]),
    ("FIGHTING", [
        ("Brawling", "DEX", "Brawling", ""),
        ("Evasion", "DEX", "Evasion", ""),
        ("Martial Arts (x2)", "DEX", "Martial Arts", "spec"),
        ("Martial Arts (x2)", "DEX", "Martial Arts 2", "spec"),
        ("Melee Weapon", "DEX", "Melee Weapon", ""),
    ]),
    ("PERFORMANCE", [
        ("Acting", "COOL", "Acting", ""),
        ("Play Instrument", "TECH", "Play Instrument", "spec"),
        ("Play Instrument", "TECH", "Play Instrument 2", "spec"),
    ]),
    ("RANGED", [
        ("Archery", "REF", "Archery", ""),
        ("Autofire (x2)", "REF", "Autofire", ""),
        ("Handgun", "REF", "Handgun", ""),
        ("Heavy Weapons (x2)", "REF", "Heavy Weapons", ""),
        ("Shoulder Arms", "REF", "Shoulder Arms", ""),
    ]),
    ("SOCIAL", [
        ("Bribery", "COOL", "Bribery", ""),
        ("Conversation", "EMP", "Conversation", ""),
        ("Human Perception", "EMP", "Human Perception", ""),
        ("Interrogation", "COOL", "Interrogation", ""),
        ("Persuasion", "COOL", "Persuasion", ""),
        ("Personal Grooming", "COOL", "Personal Grooming", ""),
        ("Streetwise", "COOL", "Streetwise", ""),
        ("Trading", "COOL", "Trading", ""),
        ("Wardrobe & Style", "COOL", "Wardrobe & Style", ""),
    ]),
    ("TECHNIQUE", [
        ("Air Vehicle Tech", "TECH", "Air Vehicle Tech", ""),
        ("Basic Tech", "TECH", "Basic Tech", ""),
        ("Cybertech", "TECH", "Cybertech", ""),
        ("Demolitions (x2)", "TECH", "Demolitions", ""),
        ("Electronics/Security Tech (x2)", "TECH", "Electronics/Security Tech", ""),
        ("First Aid", "TECH", "First Aid", ""),
        ("Forgery", "TECH", "Forgery", ""),
        ("Land Vehicle Tech", "TECH", "Land Vehicle Tech", ""),
        ("Paint/Draw/Sculpt", "TECH", "Paint/Draw/Sculpt", ""),
        ("Paramedic (x2)", "TECH", "Paramedic", ""),
        ("Photography/Film", "TECH", "Photography/Film", ""),
        ("Pick Lock", "TECH", "Pick Lock", ""),
        ("Pick Pocket", "TECH", "Pick Pocket", ""),
        ("Sea Vehicle Tech", "TECH", "Sea Vehicle Tech", ""),
        ("Weaponstech", "TECH", "Weaponstech", ""),
    ]),
]


class Form:
    def __init__(self, c: canvas.Canvas):
        self.c = c
        self.f = c.acroForm

    def tf(self, name, x, y, w, h, multiline=False, size=7.5, tooltip=""):
        flags = "multiline" if multiline else ""
        self.f.textfield(
            name=name,
            tooltip=tooltip or name,
            x=x, y=y, width=w, height=h,
            fontName="Courier",
            fontSize=size,
            fillColor=FIELD,
            textColor=INK,
            borderColor=RULE,
            borderWidth=0.45,
            forceBorder=True,
            fieldFlags=flags,
            borderStyle="underlined",
        )

    def cb(self, name, x, y, size=8, tooltip=""):
        self.f.checkbox(
            name=name,
            tooltip=tooltip or name,
            x=x, y=y, size=size,
            buttonStyle="check",
            borderColor=RULE,
            fillColor=white,
            textColor=CRIMSON,
            checked=False,
        )

    def btn(self, name, x, y, w, h, tooltip=""):
        # reportlab 5 AcroForm has no push-button widget. Photo frames are print/paste.
        return


def _font(c, name, size, color=INK):
    c.setFillColor(color)
    c.setFont(name, size)


def _string(c, text, x, y, font="Helvetica", size=7, color=INK):
    _font(c, font, size, color)
    c.drawString(x, y, text)


def _right(c, text, x, y, font="Helvetica", size=7, color=INK):
    _font(c, font, size, color)
    c.drawRightString(x, y, text)


def _center(c, text, x, y, font="Helvetica", size=7, color=INK):
    _font(c, font, size, color)
    c.drawCentredString(x, y, text)


def _rect(c, x, y, w, h, fill=None, stroke=INK, lw=0.6):
    c.setStrokeColor(stroke)
    c.setLineWidth(lw)
    if fill is not None:
        c.setFillColor(fill)
        c.rect(x, y, w, h, stroke=1, fill=1)
    else:
        c.rect(x, y, w, h, stroke=1, fill=0)


def _hline(c, x, y, w, color=INK, lw=0.5):
    c.setStrokeColor(color)
    c.setLineWidth(lw)
    c.line(x, y, x + w, y)


def _footer(c, page, total=4):
    _string(c, "NC//NET STREET FILE  ·  unofficial table aid  ·  not affiliated with R. Talsorian Games or CD PROJEKT",
            M, 8, "Helvetica", 5.5, MUTED)
    _right(c, f"{page} / {total}", W - M, 8, "Helvetica", 6, MUTED)


def _draw_image(c, path, x, y, w, h):
    p = Path(path)
    if p.exists():
        c.drawImage(str(p), x, y, width=w, height=h, mask="auto",
                    preserveAspectRatio=True, anchor="c")


def _labeled_field(form, c, label, name, x, y, w, h=11, lab_w=None, size=7):
    if lab_w is None:
        lab_w = min(70, w * 0.38)
    _string(c, label.upper(), x, y + h + 1.5, "Helvetica", 5.2, MUTED)
    form.tf(name, x, y, w, h, size=size)
    return y


def _pair(form, c, label, name, x, y, w, h=11):
    _string(c, label.upper(), x, y + h + 1.2, "Helvetica", 5.2, MUTED)
    form.tf(name, x, y, w, h)
    return y


# ---------------------------------------------------------------------------
# PAGE 0 — dossier
# ---------------------------------------------------------------------------

def _header_bar(c, title, right=""):
    c.setFillColor(NCPD_BG)
    c.rect(0, H - 30, W, 30, stroke=0, fill=1)
    c.setFillColor(CRIMSON)
    c.rect(0, H - 33, W, 3, stroke=0, fill=1)
    _string(c, title, M, H - 19, "Helvetica-Bold", 11, white)
    if right:
        _right(c, right, W - M, H - 19, "Helvetica-Bold", 8, AMBER)


def page_dossier(c, form: Form):
    c.setFillColor(PAPER)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(NCPD_BG)
    c.rect(0, H - 36, W, 36, stroke=0, fill=1)
    c.setFillColor(CRIMSON)
    c.rect(0, H - 39, W, 3, stroke=0, fill=1)
    c.setFillColor(white)
    c.circle(26, H - 18, 15, fill=1, stroke=0)
    _draw_image(c, PRINT / "ncpd-seal.png", 10, H - 34, 32, 32)
    _string(c, "NIGHT CITY POLICE DEPARTMENT", 48, H - 16, "Helvetica-Bold", 12, white)
    _string(c, "RECORDS DIVISION  ·  STREET FILE", 48, H - 28, "Helvetica", 7, AMBER)
    c.setFillColor(white)
    c.circle(W - 26, H - 18, 15, fill=1, stroke=0)
    _draw_image(c, PRINT / "operator-mark.png", W - 42, H - 34, 32, 32)
    _right(c, "OPERATOR FILE", W - 48, H - 16, "Helvetica-Bold", 10, AMBER)
    _right(c, "NIGHT MARKET COPY", W - 48, H - 28, "Helvetica", 6.5, white)

    y = H - 54
    _string(c, "CASE", M, y + 3, "Helvetica-Bold", 6, CRIMSON)
    form.tf("CaseNo", M + 28, y - 2, 100, 12, size=8)
    _string(c, "PRECINCT", M + 136, y + 3, "Helvetica-Bold", 6, MUTED)
    form.tf("Precinct", M + 180, y - 2, 54, 12)
    _string(c, "OPENED", M + 242, y + 3, "Helvetica-Bold", 6, MUTED)
    form.tf("FileDate", M + 280, y - 2, 64, 12)
    _string(c, "UPDATED", M + 352, y + 3, "Helvetica-Bold", 6, MUTED)
    form.tf("FileUpdated", M + 396, y - 2, 64, 12)
    _string(c, "PLAYER", M + 468, y + 3, "Helvetica-Bold", 6, MUTED)
    form.tf("Player", M + 508, y - 2, 90, 12)
    _string(c, "FILE PRICE", M + 606, y + 3, "Helvetica-Bold", 6, AMBER)
    form.tf("FilePrice", M + 658, y - 2, 44, 12)
    _string(c, "eb", M + 704, y + 1, "Helvetica", 6, MUTED)
    form.cb("DoNotBurn", M + 722, y - 1, 8)
    _string(c, "DO NOT BURN", M + 734, y + 1, "Helvetica-Bold", 6, CRIMSON)

    y = H - 72
    _string(c, "CLASSIFICATION", M, y + 2, "Helvetica-Bold", 6, CRIMSON)
    tags = [
        ("Class_POI", "POI"),
        ("Class_WANT", "WANT"),
        ("Class_CI", "CI"),
        ("Class_PSYCHO", "CYBERPSYCHO WATCH"),
        ("Class_DEAD", "DECEASED"),
    ]
    x = M + 82
    for name, lab in tags:
        form.cb(name, x, y - 1, 8)
        _string(c, lab, x + 11, y + 1, "Helvetica", 6.5)
        x += 12 + c.stringWidth(lab, "Helvetica", 6.5) + 14
    _string(c, "RELIABILITY 1–5", x + 8, y + 2, "Helvetica-Bold", 6, AMBER)
    form.tf("SourceReliability", x + 90, y - 2, 28, 12)

    photo_h, photo_w = 126, 82
    y_photo = H - 208
    # booking
    _string(c, "BOOKING PHOTO", M, y_photo + photo_h + 3, "Helvetica-Bold", 6, CRIMSON)
    _rect(c, M, y_photo, photo_w, photo_h, fill=HexColor("#F4F4F4"), stroke=INK, lw=1.2)
    _draw_mugshot_ticks(c, M, y_photo, photo_w, photo_h)
    form.btn("Mugshot", M + 14, y_photo + 4, photo_w - 18, photo_h - 8,
             "Acrobat: click to import booking photo")
    _center(c, "CLICK / PASTE", M + photo_w / 2, y_photo + 8, "Helvetica", 5, MUTED)

    # known photo
    kx = 430
    _string(c, "KNOWN PHOTOGRAPH", kx, y_photo + photo_h + 3, "Helvetica-Bold", 6, GOLD)
    _rect(c, kx, y_photo, photo_w, photo_h, fill=HexColor("#FFF4E0"), stroke=AMBER, lw=1.2)
    form.btn("KnownPhoto", kx + 4, y_photo + 4, photo_w - 8, photo_h - 8,
             "Acrobat: click to import street / known photograph")
    _center(c, "CLICK / PASTE", kx + photo_w / 2, y_photo + 8, "Helvetica", 5, MUTED)

    # ID block between photos? No - to the right of booking, left of known? 
    # Layout: booking | ID | known | fixer meta
    id_x = M + photo_w + 8
    id_w = kx - id_x - 8
    yy = y_photo + photo_h - 10
    _string(c, "HANDLE", id_x, yy, "Helvetica", 5.2, MUTED)
    form.tf("Handle", id_x, yy - 11, id_w, 11, size=9)
    yy -= 21
    _string(c, "LEGAL NAME", id_x, yy, "Helvetica", 5.2, MUTED)
    form.tf("Real Name", id_x, yy - 11, id_w, 11)
    yy -= 21
    _string(c, "AKA / ALIASES", id_x, yy, "Helvetica", 5.2, MUTED)
    form.tf("Aliases", id_x, yy - 11, id_w, 11)
    yy -= 21
    hw = (id_w - 6) / 2
    _string(c, "ROLE", id_x, yy, "Helvetica", 5.2, MUTED)
    form.tf("Role", id_x, yy - 11, hw, 11)
    _string(c, "RANK", id_x + hw + 6, yy, "Helvetica", 5.2, MUTED)
    form.tf("Rank", id_x + hw + 6, yy - 11, hw, 11)
    yy -= 21
    _string(c, "COVER OCCUPATION", id_x, yy, "Helvetica", 5.2, MUTED)
    form.tf("CoverOccupation", id_x, yy - 11, id_w, 11)

    # fixer meta to the right of known photo
    fx = kx + photo_w + 8
    fw = W - M - fx
    fy = y_photo + photo_h - 14
    for lab, name, h in [
        ("HEAT (NCPD / CORP / GANG)", "Heat", 12),
        ("DEAD DROP", "DeadDrop", 12),
        ("BACKER", "Backer", 12),
        ("OWED (YOU OWE THEM)", "Owed", 20),
        ("OWING (THEY OWE YOU)", "Owing", 20),
    ]:
        _string(c, lab, fx, fy, "Helvetica", 5.2, GOLD)
        form.tf(name, fx, fy - h, fw, h, multiline=(h > 14), size=7)
        fy -= h + 10

    # physical ID row under photos
    y = y_photo - 44
    _string(c, "PHYSICAL / ID", M, y + 26, "Helvetica-Bold", 6, CRIMSON)
    cols = [
        ("Age", "AGE", 36),
        ("Sex", "SEX / PRONOUNS", 70),
        ("Height", "HEIGHT", 44),
        ("Weight", "WEIGHT", 44),
        ("Eyes", "EYES", 44),
        ("Hair", "HAIR", 50),
        ("Agent", "AGENT #", 78),
        ("SIN", "ID / SIN", 86),
        ("Badge", "BADGE / LICENSE", 80),
    ]
    x = M
    for name, lab, w in cols:
        _string(c, lab, x, y + 13, "Helvetica", 4.8, MUTED)
        form.tf(name, x, y, w, 11)
        x += w + 4
    _string(c, "LANGUAGES", M, y - 14, "Helvetica", 4.8, MUTED)
    form.tf("Languages", M + 52, y - 26, W - M - M - 52, 11)

    # BOLO
    y = y - 48
    _string(c, "BOLO  /  DISTINGUISHING MARKS", M, y + 12, "Helvetica-Bold", 6.5, CRIMSON)
    _string(c, "NCPD: visible chrome, scars  ·  Operator: how they show up to a meet", M + 178, y + 12, "Helvetica-Oblique", 5.5, MUTED)
    form.tf("BOLO", M, y - 24, W - 2 * M, 34, multiline=True, size=8)

    y = y - 42
    # two voice columns
    col_w = (W - 2 * M - 8) / 2
    left_x = M
    right_x = M + col_w + 8
    # headers
    c.setFillColor(NCPD_BG)
    c.rect(left_x, y - 2, col_w, 14, stroke=0, fill=1)
    _string(c, "NCPD  ·  PSYCH / RAP / ORIGIN", left_x + 6, y + 2, "Helvetica-Bold", 7, white)
    c.setFillColor(FIXER_BG)
    c.rect(right_x, y - 2, col_w, 14, stroke=0, fill=1)
    _string(c, "OPERATOR  ·  HOW TO WORK THEM / STREET TALK", right_x + 6, y + 2, "Helvetica-Bold", 7, GOLD)

    y -= 16
    h = 24
    _string(c, "PSYCHOLOGICAL PROFILE", left_x, y, "Helvetica", 5, MUTED)
    form.tf("PsychProfile", left_x, y - h, col_w, h, multiline=True)
    _string(c, "HOW TO WORK THEM  (what to say / not say)", right_x, y, "Helvetica", 5, GOLD)
    form.tf("HowToWorkThem", right_x, y - h, col_w, h, multiline=True)

    y -= h + 12
    h = 36
    _string(c, "RAP  ·  WHO / WHAT / WHAT THEY CAN THROW / WHAT’S GONNA HAPPEN", left_x, y, "Helvetica", 5, MUTED)
    form.tf("RAP", left_x, y - h, col_w, h, multiline=True)
    _string(c, "STREET TALK  ·  WHAT THE STREET SAYS", right_x, y, "Helvetica", 5, GOLD)
    form.tf("StreetTalk", right_x, y - h, col_w, h, multiline=True)

    y -= h + 12
    h = 24
    _string(c, "OCCUPATIONAL HISTORY  /  M.O.  (role-specific lifepath, prose)", left_x, y, "Helvetica", 5, MUTED)
    form.tf("OccupationHistory", left_x, y - h, col_w, h, multiline=True)
    _string(c, "GOALS  ·  PREDICTED ACTIVITY / WHAT GIG THEY BITE ON", right_x, y, "Helvetica", 5, GOLD)
    form.tf("Goals", right_x, y - h, col_w, h, multiline=True)

    y -= h + 12
    # leverage row — dual labels, one box each, full width grid 3x2
    boxes = [
        ("Leverage", "LEVERAGE  ·  what they value / what they’ll take a job for"),
        ("Approach", "APPROACH  ·  feelings about people / will they burn a choom"),
        ("ValuedPerson", "VALUED PERSON  ·  hostage risk / DO NOT TOUCH"),
        ("ValuedPossession", "VALUED POSSESSION  ·  seizure target / what they’d die for"),
        ("Associates", "ASSOCIATES  ·  names only  (full cards → xlsx CONTACTS)"),
        ("Enemies", "ENEMIES  ·  rivalries / don’t sit them together"),
        ("Affairs", "AFFAIRS  ·  where it hurts"),
        ("Origin", "ORIGIN  ·  culture / family background"),
        ("Childhood", "CHILDHOOD ENVIRONMENT"),
        ("FamilyCrisis", "FAMILY CRISIS"),
    ]
    bw = (W - 2 * M - 24) / 5
    bh = 22
    for i, (name, lab) in enumerate(boxes):
        col = i % 5
        row = i // 5
        bx = M + col * (bw + 6)
        by = y - row * (bh + 14) - bh
        _string(c, lab, bx, by + bh + 1, "Helvetica", 4.8, MUTED if col == 0 else GOLD)
        form.tf(name, bx, by, bw, bh, multiline=True, size=7)

    # stamps sit in the bottom margin, not over fields
    c.saveState()
    try:
        c.setFillAlpha(0.7)
        c.setStrokeAlpha(0.7)
    except Exception:
        pass
    _draw_image(c, PRINT / "stamp-felony.png", M + 6, y_photo + 6, 72, 28)
    _draw_image(c, PRINT / "stamp-confidential.png", kx + 6, y_photo + 6, 74, 28)
    c.restoreState()
    _draw_image(c, PRINT / "stamp-burn.png", kx + 8, y_photo + photo_h - 38, 70, 28)

    _footer(c, 1)
    c.showPage()


def _draw_mugshot_ticks(c, x, y, w, h):
    c.setStrokeColor(INK)
    c.setFillColor(INK)
    c.setLineWidth(0.5)
    n = 8
    for i in range(n + 1):
        yy = y + 8 + i * ((h - 16) / n)
        ln = 10 if i % 2 == 0 else 6
        c.line(x, yy, x + ln, yy)
        if i % 2 == 0:
            cm = 150 + (i // 2) * 10
            _string(c, str(cm), x + 2, yy + 1, "Helvetica", 4, INK)


# ---------------------------------------------------------------------------
# PAGE 1 — edgerunner
# ---------------------------------------------------------------------------

def page_edgerunner(c, form: Form):
    c.setFillColor(white)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    _header_bar(c, "EDGERUNNER  ·  PAGE 1", "STATS + SKILLS + COMBAT")

    y = H - 42
    _string(c, "HANDLE", M, y, "Helvetica", 5.2, MUTED)
    form.tf("Handle", M, y - 12, 110, 12, size=9)
    _string(c, "ROLE", M + 116, y, "Helvetica", 5.2, MUTED)
    form.tf("Role", M + 116, y - 12, 80, 12)
    _string(c, "RANK", M + 202, y, "Helvetica", 5.2, MUTED)
    form.tf("Rank", M + 202, y - 12, 28, 12)
    _string(c, "ROLE 2", M + 236, y, "Helvetica", 5.2, MUTED)
    form.tf("Role2", M + 236, y - 12, 80, 12)
    _string(c, "RANK 2", M + 322, y, "Helvetica", 5.2, MUTED)
    form.tf("Rank2", M + 322, y - 12, 28, 12)
    _string(c, "PLAYER", M + 356, y, "Helvetica", 5.2, MUTED)
    form.tf("Player", M + 356, y - 12, W - M - 356, 12)

    # STATS strip
    y = H - 78
    _string(c, "STATISTICS   ·   LUCK and EMP are current / max — do not repeat below",
            M, y + 16, "Helvetica-Bold", 7, CRIMSON)
    stats = ["INT", "REF", "DEX", "TECH", "COOL", "WILL", "MOVE", "BODY"]
    box_w = 42
    x = M
    for st in stats:
        _rect(c, x, y - 18, box_w, 30, fill=NCPD_BG, stroke=NCPD_BG, lw=0)
        _center(c, st, x + box_w / 2, y + 4, "Helvetica-Bold", 6, GOLD)
        form.tf(st, x + 4, y - 14, box_w - 8, 16, size=11)
        x += box_w + 4

    # LUCK cur/max
    lw = 70
    _rect(c, x, y - 18, lw, 30, fill=CRIMSON, stroke=CRIMSON, lw=0)
    _center(c, "LUCK  cur / max", x + lw / 2, y + 4, "Helvetica-Bold", 5.5, white)
    form.tf("Luck Current", x + 4, y - 14, 28, 16, size=10)
    _string(c, "/", x + 33, y - 8, "Helvetica-Bold", 10, white)
    form.tf("LUCK", x + 38, y - 14, 28, 16, size=10)
    x += lw + 4
    ew = 70
    _rect(c, x, y - 18, ew, 30, fill=CRIMSON, stroke=CRIMSON, lw=0)
    _center(c, "EMP  cur / max", x + ew / 2, y + 4, "Helvetica-Bold", 5.5, white)
    form.tf("EMP Current", x + 4, y - 14, 28, 16, size=10)
    _string(c, "/", x + 33, y - 8, "Helvetica-Bold", 10, white)
    form.tf("EMP", x + 38, y - 14, 28, 16, size=10)

    y_luck = H - 108
    _string(c, "LUCK SPENT", M, y_luck + 2, "Helvetica", 5.5, MUTED)
    for i in range(10):
        form.cb(f"LuckTick{i+1}", M + 58 + i * 13, y_luck - 6, 9)
    _string(c, "SKILLS: LVL + STAT = BASE   ·   (x2) double IP",
            M + 200, y_luck + 2, "Helvetica", 5.5, MUTED)

    y_top = H - 126
    weapons_top = 128
    left_w = 548
    _draw_skills(c, form, M, y_top, left_w, y_top - weapons_top - 8, cols=3)

    rx = M + left_w + 10
    rw = W - M - rx
    dy = y_top
    c.setFillColor(NCPD_BG)
    c.rect(rx, dy - 2, rw, 14, stroke=0, fill=1)
    _string(c, "DERIVED", rx + 4, dy + 2, "Helvetica-Bold", 7, GOLD)
    dy -= 16
    _string(c, "HP  cur / max", rx, dy, "Helvetica", 5.5, MUTED)
    _string(c, "10+5×ceil((BODY+WILL)/2)", rx + 70, dy, "Helvetica", 5, MUTED)
    dy -= 16
    form.tf("HP", rx, dy, 40, 14, size=10)
    _string(c, "/", rx + 42, dy + 3, "Helvetica-Bold", 10)
    form.tf("HP Max", rx + 50, dy, 40, 14, size=10)
    dy -= 18
    _string(c, "SERIOUSLY WOUNDED  = ceil(HPmax/2)", rx, dy, "Helvetica", 5.2, MUTED)
    dy -= 15
    form.tf("SeriouslyWounded", rx, dy, 36, 13)
    _string(c, "DEATH SAVE = BODY", rx + 44, dy + 3, "Helvetica", 5.2, MUTED)
    form.tf("DeathSave", rx + 140, dy, 28, 13)
    dy -= 18
    _string(c, "DS PENALTY (when Mortally Wounded)", rx, dy, "Helvetica", 5.2, MUTED)
    dy -= 15
    form.tf("DeathSavePenalty", rx, dy, 32, 13)
    dy -= 18
    _string(c, "HUMANITY  cur / max    (EMP max × 10)", rx, dy, "Helvetica", 5.2, MUTED)
    dy -= 16
    form.tf("Humanity", rx, dy, 40, 14, size=10)
    _string(c, "/", rx + 42, dy + 3, "Helvetica-Bold", 10)
    form.tf("Humanity Max", rx + 50, dy, 40, 14, size=10)
    dy -= 18
    _string(c, "MED ALERT", rx, dy + 6, "Helvetica-Bold", 6.5, CRIMSON)
    form.tf("MedAlert", rx, dy - 22, rw, 26, multiline=True, size=7)
    dy -= 40
    _string(c, "ROLE ABILITY", rx, dy + 6, "Helvetica-Bold", 7, CRIMSON)
    form.tf("RoleAbility", rx, dy - 22, rw, 26, multiline=True, size=7)
    dy -= 40
    _string(c, "COMBAT AWARENESS  (Solo: split Rank before Initiative)", rx, dy + 6, "Helvetica-Bold", 5.5, CRIMSON)
    ca = [
        ("CA_Deflect", "DEFLECT"),
        ("CA_Fumble", "FUMBLE"),
        ("CA_Init", "INIT"),
        ("CA_Prec", "PRECISE"),
        ("CA_Weak", "WEAK"),
        ("CA_Threat", "THREAT"),
    ]
    cw = (rw - 10) / 3
    for i, (name, lab) in enumerate(ca):
        xx = rx + (i % 3) * cw
        yy = dy - (0 if i < 3 else 28)
        _string(c, lab, xx, yy - 6, "Helvetica", 5, MUTED)
        form.tf(name, xx, yy - 20, cw - 6, 12, size=8)
    dy -= 64
    _string(c, "BACKUP  (Lawman: ≤Rank on d10, then 1d6 rd)", rx, dy + 6, "Helvetica", 5.2, MUTED)
    form.tf("BackupCall", rx, dy - 12, 70, 12)
    _string(c, "ARRIVES", rx + 74, dy - 9, "Helvetica", 5, MUTED)
    form.tf("BackupETA", rx + 114, dy - 12, 32, 12)
    _string(c, "rd", rx + 148, dy - 9, "Helvetica", 6, MUTED)
    dy -= 28
    _string(c, "CRITICAL INJURIES", rx, dy + 6, "Helvetica-Bold", 6.5, CRIMSON)
    form.tf("CritInjuries", rx, dy - 28, rw, 32, multiline=True, size=7)
    dy -= 44
    _string(c, "ADDICTIONS", rx, dy + 6, "Helvetica-Bold", 6.5, CRIMSON)
    add_h = max(28, dy - (weapons_top + 10))
    form.tf("Addictions", rx, dy - add_h, rw, add_h, multiline=True, size=7)

    y = weapons_top
    _hline(c, M, y + 8, left_w, CRIMSON, 1.2)
    _string(c, "WEAPONS", M, y - 2, "Helvetica-Bold", 8, CRIMSON)
    notes_w = left_w - 150 - 44 - 48 - 32 - 16
    headers = [("NAME", 150), ("DMG", 44), ("AMMO", 48), ("ROF", 32), ("NOTES", notes_w)]
    x = M
    hy = y - 14
    for lab, w in headers:
        _string(c, lab, x, hy, "Helvetica", 5, MUTED)
        x += w + 4
    for i in range(4):
        yy = hy - 14 - i * 16
        x = M
        names = [f"W{i+1}_Name", f"W{i+1}_DMG", f"W{i+1}_Ammo", f"W{i+1}_ROF", f"W{i+1}_Notes"]
        widths = [150, 44, 48, 32, headers[-1][1]]
        for n, w in zip(names, widths):
            form.tf(n, x, yy, w, 14, size=7)
            x += w + 4

    ay = hy - 14 - 4 * 16 - 6
    _string(c, "ARMOR  ·  penalty to REF, DEX & MOVE   ·   SP cur / max", M, ay + 12, "Helvetica-Bold", 7, CRIMSON)
    rows = [("HEAD", "Head"), ("BODY", "Body"), ("SHIELD", "Shield")]
    for i, (lab, key) in enumerate(rows):
        xx = M + i * 185
        _string(c, lab, xx, ay - 2, "Helvetica-Bold", 7, INK)
        form.tf(f"{key}SP", xx + 48, ay - 6, 28, 13)
        _string(c, "/", xx + 78, ay - 3, "Helvetica-Bold", 9, MUTED)
        form.tf(f"{key}SPmax", xx + 88, ay - 6, 28, 13)
        _string(c, "PEN", xx + 122, ay - 2, "Helvetica", 6, MUTED)
        form.tf(f"{key}Penalty", xx + 142, ay - 6, 24, 13)

    _footer(c, 2)
    c.showPage()


def _draw_skills(c, form: Form, x, y_top, width, height, cols=2):
    gap = 8
    col_w = (width - gap * (cols - 1)) / cols
    row_h = 9.45
    # flatten with headers
    items = []
    for title, skills in SKILL_GROUPS:
        items.append(("hdr", title, None, None, None))
        for label, stat, fname, spec in skills:
            items.append(("sk", label, stat, fname, spec))

    col_h = height
    col_i = 0
    yy = y_top
    cx = x
    # mini header per column
    def col_caps(cx, yy):
        _string(c, "SKILL", cx, yy, "Helvetica", 4.5, MUTED)
        _right(c, "LVL", cx + col_w - 44, yy, "Helvetica", 4.5, MUTED)
        _right(c, "ST", cx + col_w - 26, yy, "Helvetica", 4.5, MUTED)
        _right(c, "BASE", cx + col_w - 2, yy, "Helvetica", 4.5, MUTED)
        return yy - 8

    yy = col_caps(cx, yy)

    for kind, *rest in items:
        need = row_h + (2 if kind == "hdr" else 0)
        if yy - need < y_top - col_h:
            col_i += 1
            if col_i >= cols:
                break
            cx = x + col_i * (col_w + gap)
            yy = col_caps(cx, y_top)
        if kind == "hdr":
            title = rest[0]
            c.setFillColor(NCPD_BG)
            c.rect(cx, yy - 8, col_w, 10, stroke=0, fill=1)
            _string(c, title, cx + 3, yy - 5.5, "Helvetica-Bold", 6, GOLD)
            yy -= 12
            continue
        label, stat, fname, spec = rest
        if spec:
            # name + tiny spec field
            form.tf(fname + " Spec", cx, yy - 8, 52, 9, size=5.5, tooltip=label)
            _string(c, label[:16], cx + 54, yy - 6, "Helvetica", 5.2, INK)
        else:
            _string(c, label, cx, yy - 6, "Helvetica", 5.5, INK)
        form.tf(fname, cx + col_w - 62, yy - 8.5, 18, 9.2, size=7, tooltip=f"{label} LVL")
        _center(c, stat[:4], cx + col_w - 35, yy - 6, "Helvetica", 5, MUTED)
        form.tf(fname + " BASE", cx + col_w - 22, yy - 8.5, 22, 9.2, size=7)
        yy -= row_h


# ---------------------------------------------------------------------------
# PAGE 2 — street kit
# ---------------------------------------------------------------------------

def page_street(c, form: Form):
    c.setFillColor(white)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    _header_bar(c, "STREET KIT  ·  PAGE 2", "POCKET  ·  copy Cash / IP / Heat from xlsx META")

    y = H - 44
    _string(c, "HANDLE", M, y, "Helvetica", 5.2, MUTED)
    form.tf("Handle", M, y - 16, 120, 12, size=9)
    _string(c, "CASH eb", M + 128, y, "Helvetica-Bold", 6, CRIMSON)
    form.tf("Cash", M + 128, y - 16, 70, 12, size=10)
    _string(c, "IP NOW", M + 206, y, "Helvetica-Bold", 6, CRIMSON)
    form.tf("IP_Current", M + 206, y - 16, 48, 12, size=10)
    _string(c, "IP EARNED", M + 262, y, "Helvetica", 5.2, MUTED)
    form.tf("IP_TotalEarned", M + 262, y - 16, 48, 12)
    _string(c, "IP SPENT", M + 318, y, "Helvetica", 5.2, MUTED)
    form.tf("IP_Spent", M + 318, y - 16, 48, 12)
    _string(c, "REP #", M + 374, y, "Helvetica", 5.2, MUTED)
    form.tf("Reputation", M + 374, y - 16, 40, 12)
    _string(c, "HEAT", M + 422, y, "Helvetica", 5.2, MUTED)
    form.tf("Heat", M + 422, y - 16, 120, 12)
    _string(c, "LIFESTYLE", M + 550, y, "Helvetica", 5.2, MUTED)
    form.tf("Lifestyle", M + 550, y - 16, 90, 12)
    _string(c, "HOUSING", M + 648, y, "Helvetica", 5.2, MUTED)
    form.tf("Housing", M + 648, y - 16, W - M - 648, 12)

    y = H - 76
    _string(c, "RENT / mo", M, y, "Helvetica", 5.2, MUTED)
    form.tf("Rent", M, y - 16, 70, 12)
    _string(c, "TRAUMA TEAM / SUBS", M + 80, y, "Helvetica", 5.2, MUTED)
    form.tf("TraumaTeam", M + 80, y - 16, 160, 12)
    _string(c, "REP EVENTS", M + 250, y, "Helvetica-Bold", 6, CRIMSON)
    form.tf("RepEvent1", M + 310, y - 16, 160, 12)
    form.tf("RepEvent2", M + 476, y - 16, 160, 12)
    form.tf("RepEvent3", M + 642, y - 16, W - M - 642, 12)

    y = H - 108
    c.setFillColor(CRIMSON)
    c.rect(M, y - 2, W - 2 * M, 14, stroke=0, fill=1)
    _string(c, "IN CASE OF FLATLINE", M + 6, y + 2, "Helvetica-Bold", 8, white)
    y -= 22
    _string(c, "TRAUMA TEAM # / TIER", M, y + 4, "Helvetica", 5, MUTED)
    form.tf("FlatlineTT", M, y - 10, 170, 12)
    _string(c, "RIPPERDOC", M + 180, y + 4, "Helvetica", 5, MUTED)
    form.tf("FlatlineRipper", M + 180, y - 10, 160, 12)
    _string(c, "WHO TO CALL", M + 350, y + 4, "Helvetica", 5, MUTED)
    form.tf("FlatlineCall", M + 350, y - 10, 200, 12)
    _string(c, "AGENT", M + 560, y + 4, "Helvetica", 5, MUTED)
    form.tf("Agent", M + 560, y - 10, W - M - 560, 12)

    y = H - 160
    third = (W - 2 * M - 16) / 3
    box_h = 355
    _string(c, "GEAR", M, y + 6, "Helvetica-Bold", 8, CRIMSON)
    form.tf("Gear", M, y - box_h, third, box_h, multiline=True, size=8)
    _string(c, "FASHION INVENTORY  (look is BOLO on p.0)", M + third + 8, y + 6, "Helvetica-Bold", 7, AMBER)
    form.tf("FashionInventory", M + third + 8, y - box_h, third, box_h, multiline=True, size=8)
    _string(c, "NOTES  /  DOWNTIME  /  THERAPY", M + 2 * (third + 8), y + 6, "Helvetica-Bold", 7, CRIMSON)
    form.tf("Notes", M + 2 * (third + 8), y - box_h, third, box_h, multiline=True, size=8)

    y = y - box_h - 18
    _string(c, "AMMUNITION", M, y + 6, "Helvetica-Bold", 8, CRIMSON)
    for i in range(6):
        xx = M + (i % 6) * 135
        yy = y - 16
        form.tf(f"Ammo{i+1}_Type", xx, yy, 90, 13)
        form.tf(f"Ammo{i+1}_Qty", xx + 92, yy, 36, 13)

    _footer(c, 3)
    c.showPage()


# ---------------------------------------------------------------------------
# PAGE 3 — chrome
# ---------------------------------------------------------------------------

CYBER_BLOCKS = [
    ("Neural Link", "NL", True, 3),
    ("Neuroport (CEMK)", "NP", True, 4),
    ("Right Cybereye", "RE", True, 3),
    ("Left Cybereye", "LE", True, 3),
    ("Cyberaudio Suite", "CA", True, 3),
    ("Right Cyberarm", "RA", True, 3),
    ("Left Cyberarm", "LA", True, 3),
    ("Right Cyberleg", "RL", True, 3),
    ("Left Cyberleg", "LL", True, 3),
    ("Internal Cyberware", "IN", False, 5),
    ("External Cyberware", "EX", False, 4),
    ("Fashionware", "FA", False, 4),
    ("Borgware", "BO", False, 3),
]


def page_chrome(c, form: Form):
    c.setFillColor(white)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    _header_bar(c, "CHROME  ·  PAGE 3", "NEURAL LINK / NEUROPORT / SLOTS  ·  NET in the xlsx")

    y = H - 46
    _string(c, "HANDLE", M, y, "Helvetica", 5.2, MUTED)
    form.tf("Handle", M, y - 12, 120, 12, size=9)
    _string(c, "HL TOTAL", M + 130, y, "Helvetica-Bold", 6, CRIMSON)
    form.tf("HumanityLossTotal", M + 130, y - 12, 40, 12)
    _string(c, "HUMANITY cur / max", M + 180, y, "Helvetica", 5.2, MUTED)
    form.tf("Humanity", M + 180, y - 12, 36, 12)
    _string(c, "/", M + 218, y - 9, "Helvetica-Bold", 9)
    form.tf("Humanity Max", M + 226, y - 12, 36, 12)
    form.cb("HouseHUM", M + 280, y - 10, 9)
    _string(c, "CAMPAIGN: −2 HUM max per non-fashion chrome, −4 Borgware", M + 292, y - 8, "Helvetica", 6, MUTED)

    y = H - 78
    _string(c, "Check the box if you have the foundation. Options go in the slots. Internal / Fashionware / Borgware: list pieces.",
            M, y + 6, "Helvetica-Oblique", 6, MUTED)

    # neuroport built-ins row
    y = H - 96
    c.setFillColor(NCPD_BG)
    c.rect(M, y - 4, W - 2 * M, 14, stroke=0, fill=1)
    _string(c, "NEUROPORT SUITE  (Holophone, Biomonitor, Virtu, HUD, 2 shard slots, Personal Link)", M + 4, y, "Helvetica-Bold", 7, GOLD)
    y -= 18
    np_bits = [
        ("NP_Holophone", "Holophone"),
        ("NP_Biomonitor", "Biomonitor"),
        ("NP_Virtu", "Virtu"),
        ("NP_HUD", "HUD / Chyron"),
        ("NP_Shard1", "Shard 1"),
        ("NP_Shard2", "Shard 2"),
        ("NP_Link", "Personal Link"),
        ("NP_Deck", "Cyberdeck Port"),
        ("NP_ICE", "Self-ICE"),
        ("NP_Speed", "Speedware"),
    ]
    x = M
    for name, lab in np_bits:
        form.cb(name, x, y - 2, 8)
        _string(c, lab, x + 11, y, "Helvetica", 6)
        x += 11 + c.stringWidth(lab, "Helvetica", 6) + 12
        if x > W - 80:
            x = M
            y -= 14

    y -= 22
    col_w = (W - 2 * M - 24) / 4
    chunks = [CYBER_BLOCKS[0:4], CYBER_BLOCKS[4:8], CYBER_BLOCKS[8:11], CYBER_BLOCKS[11:]]
    y0 = y

    def draw_blocks(blocks, x, y):
        for title, key, founded, slots in blocks:
            _string(c, title.upper(), x + (14 if founded else 0), y, "Helvetica-Bold", 7, CRIMSON)
            if founded:
                form.cb(f"{key}_Has", x, y - 2, 9)
            _string(c, "HL", x + col_w - 40, y, "Helvetica", 5, MUTED)
            form.tf(f"{key}_HL", x + col_w - 26, y - 4, 24, 11, size=7)
            y -= 14
            for i in range(slots):
                form.tf(f"{key}_{i+1}", x, y - 2, col_w, 12, size=7)
                y -= 14
            y -= 6
        return y

    for i, chunk in enumerate(chunks):
        draw_blocks(chunk, M + i * (col_w + 8), y0)

    _string(c, "Install notes / therapy / humanity recovery — also track on xlsx CLINIC",
            M, 56, "Helvetica", 6, MUTED)
    form.tf("ChromeNotes", M, 18, W - 2 * M, 34, multiline=True, size=8)

    _footer(c, 4)
    c.showPage()


def _wire_image_js(path: Path):
    """Add Acrobat buttonImportIcon actions to Mugshot / KnownPhoto."""
    try:
        from pypdf import PdfReader, PdfWriter
        from pypdf.generic import (
            ArrayObject, DecodedStreamObject, DictionaryObject,
            NameObject, NumberObject, TextStringObject,
        )
    except ImportError:
        return
    reader = PdfReader(str(path))
    # document-level JS
    js = (
        "var _importPic = app.trustedFunction(function(f){"
        "app.beginPriv(); try { this.getField(f).buttonImportIcon(); } catch(e) {} app.endPriv();});"
    )
    # Attach JS action on widget annotations named Mugshot / KnownPhoto
    writer = PdfWriter()
    writer.append(reader)
    # Open action hint
    try:
        writer.add_js(
            "// NC//NET Street File\n"
            "// In Adobe Acrobat, click BOOKING PHOTO or KNOWN PHOTOGRAPH to import an image.\n"
        )
    except Exception:
        pass
    tmp = path.with_suffix(".tmp.pdf")
    with open(tmp, "wb") as fh:
        writer.write(fh)
    tmp.replace(path)


def build_pdf(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(path), pagesize=PAGE)
    c.setTitle("NC//NET Street File")
    c.setAuthor("NC//NET")
    c.setSubject("Unofficial Cyberpunk RED fillable character dossier + street kit")
    c.setCreator("NC//NET Street File builder")
    form = Form(c)
    page_dossier(c, form)
    page_edgerunner(c, form)
    page_street(c, form)
    page_chrome(c, form)
    c.save()
    _wire_image_js(path)
    print("wrote", path, "size", path.stat().st_size)
    return path

    return path
