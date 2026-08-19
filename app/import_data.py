#!/usr/bin/env python3
"""Импорт Data Pool.xlsx -> app/data/items.json (каталог + таблицы + сид-ростер Folio).

Только стандартная библиотека — xlsx читается напрямую как zip+xml.
"""
import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

BASE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.path.join(BASE, os.pardir, 'Data Pool.xlsx')
OUT = os.path.join(BASE, 'data', 'items.json')

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

# (sheet, cat_id, ru name, emoji, поля для карточки: (ключ, подпись))
CATS = [
    ('Guns', 'guns', 'Огнестрельное оружие', '🔫', [
        ('Type', 'Класс'), ('Skill', 'Навык'), ('Damage', 'Урон'), ('Mag', 'Магазин'),
        ('ROF', 'СКО'), ('Hands', 'Руки'), ('Conceal', 'Скрытность'), ('Quality', 'Качество'),
        ('Alt. Fire Modes & Spec. Feat.', 'Режимы / особенности')]),
    ('Melee', 'melee', 'Ближний бой', '🗡️', [
        ('Type', 'Класс'), ('Damage', 'Урон'), ('ROF', 'СКО'), ('Conceal', 'Скрытность'),
        ('Spec. Feat', 'Особенности')]),
    ('Gun Upgrades', 'gun_upgrades', 'Апгрейды оружия', '🔧', [('Available', 'Совместимость')]),
    ('Ammo', 'ammo', 'Патроны', '📦', [('Suitable ammo / weapon', 'Для чего')]),
    ('Grenades & Explosives', 'grenades', 'Гранаты и взрывчатка', '💥', []),
    ('Armor', 'armor', 'Броня', '🛡️', [('SP', 'SP'), ('Penalty', 'Штраф')]),
    ('Cyberware', 'cyberware', 'Кибернетика', '🦾', [
        ('Type', 'Тип'), ('Install', 'Установка'), ('HL', 'Потеря человечности')]),
    ('Gear', 'gear', 'Снаряжение', '🎒', [('Type', 'Тип')]),
    ('Fashion', 'fashion', 'Мода', '🧥', []),
    ('Services & Housing', 'services', 'Услуги и жильё', '🏢', [('Type', 'Тип')]),
    ('Vehicles', 'vehicles', 'Транспорт', '🏍️', [
        ('SP', 'SP'), ('SDP', 'SDP'), ('Seats', 'Мест'), ('Speed (Combat)', 'Скорость (бой)'),
        ('Speed (Narrative)', 'Скорость (в мире)'), ('Nomad Access', 'Nomad')]),
    ('Vehicles Upgrades', 'vehicles_upgrades', 'Апгрейды транспорта', '⚙️', [
        ('Availability', 'Доступность'), ('Nomad Access', 'Nomad')]),
    ('Net Stuff', 'net_stuff', 'Нэтраннинг: железо', '🔌', [('Type', 'Тип')]),
    ('Programs', 'programs', 'Программы', '💾', [
        ('PER', 'PER'), ('SPD', 'SPD'), ('ATK', 'ATK'), ('DEF', 'DEF'), ('REZ', 'REZ'),
        ('Class', 'Класс'), ('Icon', 'Иконка')]),
]

DESC_KEYS = ['Description & Data', 'Description & Effect', 'Description', 'Description & Effect.']


def load_workbook(path):
    z = zipfile.ZipFile(path)
    sst = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall(M + 'si'):
            sst.append(''.join(t.text or '' for t in si.iter(M + 't')))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    relmap = {r.get('Id'): r.get('Target') for r in rels}
    sheets = {}
    for sh in wb.find(M + 'sheets'):
        rid = sh.get(RNS + 'id')
        target = relmap[rid]
        if target.startswith('/'):
            target = target.lstrip('/')
        elif not target.startswith('xl/'):
            target = 'xl/' + target
        sheets[sh.get('name')] = target
    return z, sst, sheets


def sheet_rows(z, sst, target):
    """Список строк, каждая — dict {буква_колонки: значение}."""
    root = ET.fromstring(z.read(target))
    rows = []
    for row in root.iter(M + 'row'):
        cells = {}
        for c in row:
            v = c.find(M + 'v')
            if v is None:
                t = c.find(M + 'is')
                if t is not None:
                    cells[c.get('r')] = ''.join(x.text or '' for x in t.iter(M + 't'))
                continue
            cells[c.get('r')] = sst[int(v.text)] if c.get('t') == 's' else v.text
        rows.append(cells)
    return rows


def col_of(ref):
    return ''.join(ch for ch in ref if ch.isalpha())


def col_idx(col):
    n = 0
    for ch in col:
        n = n * 26 + ord(ch) - 64
    return n


def parse_rows(rows):
    """Первая строка — заголовки. Возвращает list[dict]."""
    if not rows:
        return []
    headers = {}
    for ref, name in rows[0].items():
        col = col_of(ref)
        if name and name.strip():
            headers[col] = name.strip()
    out = []
    for r in rows[1:]:
        cells = {col_of(ref): v for ref, v in r.items()}
        d = {h: cells.get(c) for c, h in headers.items()}
        out.append(d)
    return out


def parse_price(v):
    if v is None:
        return None
    s = str(v).strip().replace(',', ' ')
    m = re.search(r'\d+', s)
    if not m:
        return None
    try:
        return float(m.group())
    except ValueError:
        return None


def parse_hl(v):
    if v is None:
        return 0
    s = str(v).strip()
    m = re.match(r'^(\d+)', s)
    if m:
        return int(m.group(1))
    m = re.match(r'^(\d*)d(\d+)', s, re.I)
    if m:
        n = int(m.group(1) or 1)
        die = int(m.group(2))
        return round(n * (die + 1) / 2)
    return 0


def parse_sp(v):
    if v is None:
        return None
    m = re.search(r'(\d+)', str(v))
    return int(m.group(1)) if m else None


def parse_armor_penalties(v):
    """Нормализует раздельные штрафы брони к REF/DEX/MOVE.

    В Data Pool встречаются как одинаковые штрафы (−2 ко всем трём STAT),
    так и разные, например Hybrid Metalgear: −3 REF, −4 DEX, −4 MOVE.
    """
    if not v:
        return {}
    text = str(v).upper().replace('−', '-')
    found = {stat: int(value) for value, stat in
             re.findall(r'(-?\d+)\s*(REF|DEX|MOVE)', text)}
    return found


def armor_locations(name, desc, sp):
    """Допустимые варианты покупки брони согласно описанию источника.

    Обычная броня покупается отдельно для головы и тела. Описание предмета
    может сузить локацию или объявить единый комплект на обе локации.
    Щиты не являются носимой бронёй.
    """
    name_l = (name or '').lower()
    desc_l = (desc or '').lower().replace('’', "'")
    if 'shield' in name_l or sp == 0:
        return ['shield'], False
    bundled = ("isn't bought in two pieces" in desc_l or
               'is not bought in two pieces' in desc_l or
               'must always be worn on both' in desc_l)
    if bundled:
        return ['body', 'head'], True
    if ('head and body are purchased separately' in desc_l or
            'head or body armor' in desc_l):
        return ['body', 'head'], False
    if 'head armor' in desc_l or 'helmet' in name_l:
        return ['head'], False
    if 'body armor' in desc_l:
        return ['body'], False
    return ['body', 'head'], False


def main():
    xlsx = os.path.abspath(XLSX)
    if not os.path.exists(xlsx):
        print('Data Pool.xlsx не найден, пропускаю импорт.', file=sys.stderr)
        return 1
    z, sst, sheets = load_workbook(xlsx)

    items = []
    for sheet, cat, ru, emoji, fields in CATS:
        rows = parse_rows(sheet_rows(z, sst, sheets[sheet]))
        n = 0
        for r in rows:
            name = (r.get('Name') or '').strip()
            if not name or name.startswith('#'):
                continue
            desc = ''
            for k in DESC_KEYS:
                if r.get(k):
                    desc = str(r[k]).strip()
                    break
            price = parse_price(r.get('€$'))
            it = {
                'id': f'{cat}-{n}',
                'cat': cat,
                'name': name,
                'price': price,
                'price_raw': str(r.get('€$') or '') or None,
                'source': (r.get('Source') or '').strip() or None,
                'desc': desc or None,
                'fields': {},
            }
            for key, label in fields:
                val = r.get(key)
                if val is not None and str(val).strip() not in ('', '—', 'N/A'):
                    it['fields'][key] = str(val).strip()
            if cat == 'cyberware':
                it['hl'] = parse_hl(r.get('HL'))
            if cat == 'armor':
                it['sp'] = parse_sp(r.get('SP'))
                it['penalties'] = parse_armor_penalties(r.get('Penalty'))
                locations, bundled = armor_locations(name, desc, it['sp'])
                it['armor_locations'] = locations
                it['armor_bundled'] = bundled
            if cat in ('guns', 'melee', 'grenades') and r.get('Damage'):
                dm = re.search(r'(\d+d\d+(?:\s*[/×x]\s*\d+)?)', str(r['Damage']))
                it['damage'] = dm.group(1) if dm else str(r['Damage']).strip()
            it['search'] = (name + ' ' + ' '.join(str(v) for v in it['fields'].values()) +
                            ' ' + (desc or '')).lower()[:2000]
            items.append(it)
            n += 1

    # Таблицы
    range_rows = [[c for c in r.values()] for r in sheet_rows(z, sst, sheets['Range Table'])]
    range_table = [[('' if v is None else str(v).replace('.0', '')) for v in r] for r in range_rows]
    autofire_rows = [[c for c in r.values()] for r in sheet_rows(z, sst, sheets['Autofire Table'])]
    autofire_table = [[('' if v is None else str(v).replace('.0', '')) for v in r] for r in autofire_rows]

    # Сид-ростер из Folio
    folio = []
    for r in parse_rows(sheet_rows(z, sst, sheets['Folio'])):
        handle = (r.get('Handle') or '').strip()
        if not handle:
            continue
        role_raw = (r.get('Роль') or '').strip()
        role, rank = role_raw, 4
        m = re.match(r'^(.*?)\s*(\d+)?$', role_raw)
        if m:
            role = m.group(1).strip() or None
            if m.group(2):
                rank = int(m.group(2))
        extra = {}
        for k in ('Sync', 'DT', '€$', 'Monthly', 'IP', 'Lifestyle', 'Жилье', 'Кому продался'):
            v = (r.get(k) or '')
            v = str(v).strip()
            if v and v not in ('0', '0.0'):
                extra[k] = v
        folio.append({
            'handle': handle,
            'role': role,
            'role_rank': rank,
            'player': (r.get('Игрок') or '').strip() or None,
            'extra': extra,
        })

    cats = [{'id': c[1], 'ru': c[2], 'emoji': c[3], 'sheet': c[0], 'count': 0} for c in CATS]
    for it in items:
        for c in cats:
            if c['id'] == it['cat']:
                c['count'] += 1

    data = {
        'version': 1,
        'generated': __import__('datetime').datetime.now().isoformat(timespec='seconds'),
        'cats': cats,
        'items': items,
        'range_table': range_table,
        'autofire_table': autofire_table,
        'folio': folio,
    }
    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    print(f'OK: {len(items)} items, {len(folio)} folio chars -> {os.path.abspath(OUT)}')
    for c in cats:
        print(f"  {c['emoji']} {c['ru']}: {c['count']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
