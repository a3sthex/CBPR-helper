#!/usr/bin/env python3
"""Classify every page of every extracted book into content categories.

Two-tier approach:
  1. CHAPTER MAP (primary): hand-built per book from its own printed TOC —
     range of pages -> category. High precision for these specific editions.
  2. HEURISTIC FALLBACK: keyword/price scoring for books without a map
     (small CEMK docs, fillable sheet, Night Market Index).

Page-level overrides: price-dense pages -> items_gear (except inside
netrunning chapters), art-only/OCR pages -> art_splash.

Output: extracted/analysis/page_index.csv, categories.json, CATEGORIES.md
"""
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

TEXT_DIR = Path('extracted/text')
OUT_DIR = Path('extracted/analysis')

CAT_NAMES = {
    'rules_core': 'Правила: база (статы, навыки, проверки, экономика, IP)',
    'rules_combat': 'Правила: бой (FNFF, урон, SP, криты, лечение, транспорт)',
    'rules_netrunner': 'Правила: нетраннинг (NET-действия, ICE, программы)',
    'char_creation': 'Создание персонажа (роли, Lifepath, стартовые пакеты)',
    'items_gear': 'Предметы и снаряжение (списки с ценами eb)',
    'lore': 'Лор (история мира, Найт-Сити, повседневность, художка)',
    'gm_advice': 'Мастерская часть (советы ГМ, мобы, сценарии, генераторы)',
    'service': 'Служебное (обложки, оглавления, индексы, кредиты)',
    'art_splash': 'Арт-развороты (нет текстового слоя)',
}
CAT_ORDER = ['rules_core', 'rules_combat', 'rules_netrunner', 'char_creation',
             'items_gear', 'lore', 'gm_advice', 'service', 'art_splash']

# ---------------------------------------------------------------------------
# Chapter maps. Keys: book stem. Value: (offset, [(printed_start, cat, title)]).
# offset: pdf_page = printed_page + offset  (Corebook TOC page is PDF4/printed3 => +1)
# Ranges run up to the next chapter start; last chapter runs to book end.
CHAPTER_MAPS = {
    'CPR Cyberpunk RED Corebook': (1, [
        (1,   'service', 'cover/credits/contents'),
        (5,   'lore', 'Never Fade Away'),
        (17,  'lore', 'View from the Edge'),
        (22,  'rules_core', 'A Tabletop RPG Primer'),
        (24,  'lore', 'Streetslang'),
        (27,  'char_creation', 'Soul and the New Machine — Roles'),
        (40,  'char_creation', 'Three Methods of Making a Character'),
        (43,  'char_creation', 'Tales from The Street (Lifepath)'),
        (71,  'service', 'Fitted for the Future — part cover'),
        (72,  'rules_core', 'What are Statistics?'),
        (81,  'rules_core', 'Skills'),
        (91,  'items_gear', 'Weapons and Armor (lists)'),
        (99,  'items_gear', 'Your Outfit (fashion)'),
        (107, 'rules_core', 'Putting the Cyber into the Punk'),
        (108, 'rules_core', 'Cyberpsychosis'),
        (110, 'items_gear', 'Cyberware (lists)'),
        (121, 'lore', 'The Fall of the Towers — part fiction'),
        (125, 'rules_core', 'Getting it Done / Skill List / Role Abilities'),
        (167, 'rules_combat', 'Friday Night Firefight'),
        (193, 'rules_combat', 'Reputation'),
        (195, 'rules_netrunner', 'Netrunning (NET arch, programs, netrun)'),
        (219, 'rules_combat', 'Trauma Team — Wound States, Crits, Healing'),
        (223, 'items_gear', 'Trauma Team services / Street Drugs (prices)'),
        (229, 'rules_core', 'Therapy and You / Cyberpsychosis rules'),
        (233, 'lore', 'Welcome to the Dark Future'),
        (257, 'lore', 'The Time of the Red'),
        (283, 'lore', 'Welcome to Night City'),
        (300, 'lore', 'Particulars (people, gangs, places)'),
        (315, 'lore', 'Everyday Life'),
        (333, 'rules_core', 'The New Street Economy / Night Markets rules'),
        (340, 'items_gear', 'Night Market Appendix (item pages)'),
        (381, 'gm_advice', 'Making a Living in a Cyberpunk World'),
        (387, 'gm_advice', 'Running Cyberpunk / Beat Charts'),
        (408, 'rules_core', 'Getting Better (IP, improvement)'),
        (412, 'gm_advice', 'Mooks and Grunts'),
        (417, 'gm_advice', 'Encounters in the Red'),
        (425, 'gm_advice', 'Screamsheets'),
        (435, 'gm_advice', 'Black Dog (adventure)'),
    ]),
    'BC Black Chrome': (2, [
        (1,   'service', 'cover/credits/contents'),
        (5,   'rules_core', 'Using Black Chrome (economy/gear rules)'),
        (11,  'items_gear', 'Apps'),
        (15,  'items_gear', 'Cyberware'),
        (27,  'items_gear', 'Fashion and Armor'),
        (39,  'items_gear', 'General Goods and Gear'),
        (51,  'items_gear', 'Linear Frames'),
        (57,  'items_gear', 'Vehicles'),
        (85,  'items_gear', 'Weapons'),
        (125, 'rules_core', 'Economics 101'),
        (131, 'gm_advice', 'Night Markets (vendors, haggling, market gen)'),
        (157, 'items_gear', 'Black Chrome Lists (master index)'),
    ]),
    'IR1 Cyberpunk RED - Interface RED - Volume 1': (1, [
        (1,  'service', 'contents/intro'),
        (2,  'items_gear', 'Old Guns Never Die (2020 guns updated)'),
        (5,  'items_gear', 'Red Chrome Cargo (nomad gear)'),
        (9,  'items_gear', 'The Single Shot Pack (gear)'),
        (37, 'items_gear', 'Cyberchairs'),
        (40, 'lore', 'Elflines Online (in-world MMO)'),
        (46, 'lore', 'Elflines Online Expansion Pass 1'),
        (57, 'items_gear', 'All About Drones'),
    ]),
    'IR2 Cyberpunk RED - Interface RED - Volume 2': (1, [
        (1,  'service', 'contents/intro'),
        (3,  'gm_advice', 'Hardened Mooks'),
        (9,  'gm_advice', 'Hardened Lieutenants'),
        (15, 'gm_advice', 'Night City Weather (tables)'),
        (21, 'gm_advice', 'Jumpstart Kit Conversion Guide'),
        (33, 'items_gear', 'Cargo Containers & Cube Hotels'),
        (39, 'lore', "Daeric Sylar's Guide to ELO"),
        (57, 'items_gear', 'The 12 Days of Gunmas (weapons)'),
        (65, 'items_gear', 'Exotics of 2045 (exotic bodysculpt/cyber)'),
    ]),
    'IR3 Cyberpunk RED - Interface RED - Volume 3': (1, [
        (1,  'service', 'contents/intro'),
        (3,  'gm_advice', 'Hardened Mini Bosses'),
        (9,  'lore', 'Digital Dating in the Dark Future'),
        (25, 'items_gear', "Woodchipper's Garage (nomad vendor)"),
        (31, 'rules_core', 'Salvaging Night City (scavenging rules)'),
        (37, 'lore', 'Midnight With the Upload (fiction)'),
        (45, 'items_gear', 'Must Have Cyberware Deals'),
        (51, 'lore', 'Collecting the Random'),
        (65, 'lore', 'Elflines Online the TCG'),
        (75, 'items_gear', 'Spinning Your Wheels (vehicles)'),
        (83, 'items_gear', 'The 12 Days of Cybermas (cyberware)'),
        (91, 'rules_core', 'Going Metal (full-borg rules)'),
    ]),
    'IR4 Cyberpunk RED - Interface RED - Volume 4': (1, [
        (1,  'service', 'contents/intro'),
        (3,  'items_gear', "Hornet's Pharmacy (drugs)"),
        (9,  'items_gear', 'Black Chrome+ (gear)'),
        (23, 'gm_advice', 'Achievements and Loot Boxes'),
        (31, 'lore', 'Stickball (sport)'),
        (37, 'rules_combat', 'The Dreaded Punknaught (vehicle build/fight)'),
        (55, 'gm_advice', 'Halloween Screamsheets'),
        (65, 'items_gear', '12 Days of Gearmas'),
        (73, 'items_gear', 'Cyberfists of Fury (martial arts gear)'),
    ]),
    'IR5 Cyberpunk RED - Interface RED - Volume 5': (1, [
        (1,  'service', 'contents/intro'),
        (3,  'rules_combat', 'Breaking Your Stuff (gear damage)'),
        (13, 'lore', 'Chasing the Rabbit (fiction)'),
        (23, 'items_gear', 'All About Agents (agents HW/SW)'),
        (35, 'items_gear', "Toggle's Temple (weapon vendor)"),
        (61, 'gm_advice', 'Did Someone Say Murder? (investigation)'),
        (71, 'items_gear', 'Your New Best Friend (pets/robots)'),
        (83, 'gm_advice', 'Screamsheet Generator'),
        (97, 'items_gear', '12 Days of REDmas (gear)'),
        (105, 'items_gear', 'Solo of Fortune 2045 (weapon/armor showcase)'),
    ]),
}

# ---------------------------------------------------------------- fallback
SIGNALS = [
    ('rules_combat', 3, r'\bautofire\b|\bsuppress(?:ive|ion) fire\b|\baimed shot\b|\bdeaths?\s*saves?\b|\bcritical injur'),
    ('rules_combat', 2, r'\bSP\b.{0,40}\b(?:armor|armour|ablat)|\bDV\b\s*\d+|\binitiative\b|\brof\b|\bfumble\b|\bcover\b'),
    ('rules_combat', 1.5, r'\branged?\s+attack|\bmelee\s+attack|\bbrawling|\bmartial arts|\bevasion\b'),
    ('rules_netrunner', 3, r'\bnet actions?\b|\bblack ?ice\b|\bhellbolt\b'),
    ('rules_netrunner', 2, r'\bnet architecture|\bnetrunner|cyberdeck'),
    ('rules_core', 2.5, r'\bskill check|\bability check|\bopposed check|\bcritical success|\bcritical failure\b'),
    ('rules_core', 2, r'\bluck\b.{0,30}\bpoints?|improvement points'),
    ('char_creation', 3, r'\blifepath\b|\bstreet rat\b|\bcomplete package|\bfast and dirty|\bcreation points?'),
    ('items_gear', 3, r'\b(?:cost|price)\b.{0,40}\b(?:eb|€\$|eurodollar)|\b\d+\s*(?:eb|€\$)\b'),
    ('items_gear', 1.5, r'\bgear\b|\bcyberware\b|\bweapon categories'),
    ('lore', 3, r'\bcorporate war|\btime of the red|\bdata krash|\bnever fade away'),
    ('lore', 2, r'\bnight city\b|\bmorado bay|\bhot zone'),
    ('gm_advice', 3, r'\bgamemaster|\brunning the game|\bscreamsheet'),
    ('service', 3, r'\btable of contents|\ball rights reserved|\bisbn\b'),
    ('service', 2, r'\br\.?\s*talsorian|\bcredits\b.{0,50}\b(?:art|writing|layout)'),
]
COMPILED = [(c, w, re.compile(rx, re.I)) for c, w, rx in SIGNALS]
PRICE_RX = re.compile(r'\b\d{1,5}\s*(?:eb|€\$)\b', re.I)

PAGE_RE = re.compile(r'<!-- page (\d+) -->\n\n')


def load_pages(path: Path):
    parts = PAGE_RE.split(path.read_text(encoding='utf-8'))
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts) - 1, 2)]


def heuristic(text: str):
    scores = defaultdict(float)
    for cat, w, rx in COMPILED:
        hits = len(rx.findall(text))
        if hits:
            scores[cat] += w * hits
    ph = len(PRICE_RX.findall(text))
    if ph >= 4:
        scores['items_gear'] += ph / 2
    if len(text.split()) > 350:
        scores['lore'] += 0.5
    if not scores:
        scores['lore'] += 0.5
    return scores


def chapter_category(bookmap, pdf_page: int):
    offset, chapters = bookmap
    cat = chapters[-1][1]
    for i, (start, c, _t) in enumerate(chapters):
        nxt = chapters[i + 1][0] if i + 1 < len(chapters) else 10 ** 9
        if start + offset <= pdf_page < nxt + offset:
            return c
    return chapters[-1][1]


def classify_book(name: str, pages):
    bookmap = CHAPTER_MAPS.get(name)
    labels = []
    for page, text in pages:
        tl = text.strip()
        if tl.startswith('**[OCR]**') or len(re.sub(r'\W+', '', tl)) < 10:
            labels.append((page, 'art_splash'))
            continue
        if page <= 2 or len(tl) < 60 and page < 8:  # covers & thin front matter
            labels.append((page, 'service'))
            continue
        if bookmap:
            cat = chapter_category(bookmap, page)
            if cat not in ('rules_netrunner', 'items_gear', 'art_splash'):
                ph = len(PRICE_RX.findall(text))
                scores = heuristic(text)
                if ph >= 4 and scores.get('items_gear', 0) >= 2 * max(
                        (v for k, v in scores.items() if k != 'items_gear'), default=0):
                    cat = 'items_gear'
            labels.append((page, cat))
        else:
            labels.append((page, max(heuristic(text), key=heuristic(text).get)))
    return labels


def to_ranges(pairs):
    by_cat = defaultdict(list)
    for p, c in pairs:
        by_cat[c].append(p)
    out = {}
    for c, ps in by_cat.items():
        ps.sort()
        rs, start, prev = [], ps[0], ps[0]
        for p in ps[1:]:
            if p == prev + 1:
                prev = p
            else:
                rs.append((start, prev))
                start = prev = p
        rs.append((start, prev))
        out[c] = rs
    return out


def fmt_ranges(rs):
    return ', '.join(str(a) if a == b else f'{a}–{b}' for a, b in rs)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    grand = Counter()
    books_json = {}
    report = ['# Категоризация страниц книг', '',
              'Метод: карта глав из оглавления книги (старт главы → категория),',
              'локальные переопределения: страницы-каталоги с ценами eb → Предметы,',
              'страницы без текстового слоя → Арт. Скрипт: `tools/classify_books.py`.', '']
    with (OUT_DIR / 'page_index.csv').open('w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['book', 'page', 'category'])
        for book_file in sorted(TEXT_DIR.glob('*.md')):
            name = book_file.stem
            pairs = classify_book(name, load_pages(book_file))
            ranges = to_ranges(pairs)
            books_json[name] = {'pages': len(pairs),
                                'method': 'chapter-map' if name in CHAPTER_MAPS else 'heuristic',
                                'categories': ranges,
                                'labels': {p: c for p, c in pairs}}
            for p, c in pairs:
                w.writerow([name, p, c])
                grand[c] += 1
            cnt = Counter(c for _, c in pairs)
            total = len(pairs)
            report += [f'## {name} — {total} стр. '
                       f'({"карта глав" if name in CHAPTER_MAPS else "эвристика"})', '',
                       '| Категория | Страниц | Доля | Диапазоны (страницы PDF) |',
                       '|---|---|---|---|']
            for cat in CAT_ORDER:
                if cnt.get(cat):
                    report.append(f'| {CAT_NAMES[cat]} | {cnt[cat]} | '
                                  f'{cnt[cat] * 100 // total}% | {fmt_ranges(ranges[cat])} |')
            report.append('')

    (OUT_DIR / 'categories.json').write_text(
        json.dumps(books_json, ensure_ascii=False, indent=1), encoding='utf-8')

    total_pages = sum(grand.values())
    report += ['## Сводка по коллекции', '', '| Категория | Страниц | Доля |', '|---|---|---|']
    for cat in CAT_ORDER:
        if grand.get(cat):
            report.append(f'| {CAT_NAMES[cat]} | {grand[cat]} | {grand[cat] * 100 // total_pages}% |')
    report += [f'| **Всего** | **{total_pages}** | 100% |', '']
    (OUT_DIR / 'CATEGORIES.md').write_text('\n'.join(report), encoding='utf-8')

    print(f'classified {total_pages} pages -> extracted/analysis/')
    for cat in CAT_ORDER:
        if grand.get(cat):
            print(f'  {cat:16s} {grand[cat]:5d}')


if __name__ == '__main__':
    main()
