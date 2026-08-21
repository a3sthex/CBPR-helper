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

DESC_KEYS = ['Description & Data', 'Description & Effect', 'Description', 'Description & Effect.', 'Effect']
NUMERIC_MECHANICS = {
    'rof', 'hands', 'magazine', 'sp', 'sdp', 'seats', 'nomad_access',
    'per', 'spd', 'atk', 'def', 'rez',
}

ACTIVE_GEAR = {
    'Flashlight': {
        'equip_modes': ['held', 'ready'], 'equip_slots': ['hand', 'belt'],
        'hands_required': 1, 'activation_required': True,
        'active_actions': ['Activate light', 'Deactivate light'],
    },
    'Radio Communicator': {
        'equip_modes': ['worn', 'ready'], 'equip_slots': ['ear', 'belt'],
        'hands_required': 0, 'activation_required': True,
        'active_actions': ['Activate radio', 'Deactivate radio', 'Communicate'],
    },
    'Agent (Standard)': {
        'equip_modes': ['held', 'ready'], 'equip_slots': ['hand', 'belt'],
        'hands_required': 1, 'activation_required': True,
        'active_actions': ['Activate Agent', 'Use Agent', 'Deactivate Agent'],
    },
    'Airhypo': {
        'equip_modes': ['held', 'ready'], 'equip_slots': ['hand', 'belt'],
        'hands_required': 1, 'activation_required': False,
        'active_actions': ['Administer dose'],
    },
    'Techtool': {
        'equip_modes': ['held', 'ready', 'workspace'],
        'equip_slots': ['hand', 'belt', 'workspace'], 'hands_required': 1,
        'activation_required': False, 'active_actions': ['Use Techtool'],
    },
    'Medtech Bag': {
        'equip_modes': ['held', 'ready', 'workspace'],
        'equip_slots': ['hand', 'workspace'], 'hands_required': 1,
        'activation_required': False, 'active_actions': ['Use medical toolkit'],
    },
}


def item_interaction_metadata(cat, name, row, desc):
    """Curated declarative Use/Equip metadata; no executable item effects."""
    metadata = {}
    if cat == 'gear' and name in ACTIVE_GEAR:
        metadata.update({'equippable': True, **ACTIVE_GEAR[name]})
    item_type = str(row.get('Type') or '').strip()
    if cat == 'gear' and item_type in ('Pharma', 'Street Drugs'):
        metadata.update({
            'stackable': True,
            'consumable': True,
            'consume_amount': 1,
            'use_context': 'medical' if item_type == 'Pharma' else 'general',
            'use_effect': {
                'kind': 'manual',
                'text': str(desc or '').strip(),
                'manual_resolution_required': True,
            },
        })
    return metadata


def item_modification_metadata(cat, name, row, desc):
    """Normalize host/slot facts while leaving complex compatibility declarative."""
    if cat != 'gun_upgrades':
        return {}
    text = str(desc or '').replace('’', "'")
    low = text.lower()
    slot_match = re.search(r'requires?\s+(\d+)\s+(?:attachment\s+)?slots?', low)
    no_slot = bool(re.search(r"does(?:n't| not) require an attachment slot", low))
    slots_used = 0 if no_slot else (int(slot_match.group(1)) if slot_match else 1)
    compatibility = normalize_display_value(row.get('Available') or '')
    complex_tokens = (
        'individual eligibility', 'capable of firing', 'autofire',
        'choose to replace', 'dv17', 'tech upgraded',
    )
    kind = 'rebuild' if 'rebuild.' in low else 'attachment'
    group = None
    if 'magazine' in name.lower():
        group = 'weapon_magazine'
    elif kind == 'rebuild':
        group = 'weapon_rebuild'
    elif name in ('Smartgun Link',):
        group = 'smart_weapon_link'
    return {
        'host_type': 'weapon',
        'modification_kind': kind,
        'modification_group': group,
        'slots_used': slots_used,
        'compatibility_text': compatibility,
        'permanent_installation': bool(re.search(r'can\s*not be uninstalled|cannot be uninstalled', low)),
        'unique_per_host': bool(re.search(r'only one|cannot be attached.+with', low)),
        'compatibility_manual': any(token in (compatibility + ' ' + low).lower()
                                    for token in complex_tokens),
        'installation_source': (row.get('Source') or '').strip() or None,
    }


def normalize_display_value(value):
    text = str(value).strip()
    if re.fullmatch(r'-?\d+\.0', text):
        return text[:-2]
    return text


def normalize_mechanic_value(key, value):
    text = str(value).strip()
    if key in NUMERIC_MECHANICS and re.fullmatch(r'-?\d+(?:\.\d+)?', text):
        number = float(text)
        return int(number) if number.is_integer() else number
    return normalize_display_value(text)


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


def parse_damage(value):
    """Нормализует бросок урона для карточки и справочного среднего."""
    if not value:
        return None
    match = re.search(r'(?<!\w)(\d+)d(\d+)(?:\s*[/×x]\s*(\d+))?', str(value), re.I)
    if not match:
        return None
    count, sides = int(match.group(1)), int(match.group(2))
    multiplier = int(match.group(3) or 1)
    return {
        'notation': match.group(0).replace('×', 'x').replace(' ', ''),
        'dice': count,
        'sides': sides,
        'multiplier': multiplier,
        'average': round(count * (sides + 1) / 2 * multiplier, 1),
    }


def structured_requirements(cat, row, desc):
    """Извлекает только явные требования; неоднозначные остаются в описании."""
    text = str(desc or '').replace('\n', ' ')
    low = text.lower()
    requirements = []
    known = [
        ('neuroport cyberdeck port', 'Neuroport Cyberdeck Port'),
        ('modular finger cyberhand', 'Modular Finger Cyberhand'),
        ('cyberaudio suite', 'Cyberaudio Suite'),
        ('chipware socket', 'Chipware Socket'),
        ('neural link', 'Neural Link'),
        ('neuroport', 'Neuroport'),
        ('two cybereyes', '2× Cybereye'),
        ('a cybereye', 'Cybereye'),
        ('two cyberlegs', '2× Cyberleg'),
        ('a cyberarm or cyberleg', 'Cyberarm or Cyberleg'),
        ('a cyberarm', 'Cyberarm'),
        ('biomonitor', 'Biomonitor'),
        ('chyron', 'Chyron'),
    ]
    for needle, label in known:
        if ('requires ' + needle) in low or (needle.endswith('suite') and 'cyberaudio option' in low):
            requirements.append({'kind': 'item', 'value': label})
    body = re.search(r'requires body\s+(\d+)', low)
    if body:
        requirements.append({'kind': 'stat', 'stat': 'BODY', 'minimum': int(body.group(1))})
    slots = re.search(r'requires?\s+(\d+)\s+(?:cyberware\s+)?option slots?', low)
    if not slots:
        slots = re.search(r'(?:takes?|uses?)\s+(\d+)\s+(?:cyberware\s+)?option slots?', low)
    slot_count = int(slots.group(1)) if slots else 0
    ctype = str(row.get('Type') or '')
    name = str(row.get('Name') or '').lower()
    foundations = {
        'neuroport', 'neural link', 'cybereye', 'sponsored cybereye',
        'cyberaudio suite', 'discount cyberaudio suite', 'cyberarm',
        'neo-soviet cyberarm', 'cyberleg', 'romanova cyberlegs',
    }
    host = None
    if name not in foundations:
        for token, label in [('cyberarm option', 'Cyberarm'), ('cyberleg option', 'Cyberleg'),
                             ('cybereye option', 'Cybereye'), ('cyberaudio option', 'Cyberaudio Suite'),
                             ('neuralware option', 'Neural Link or Neuroport')]:
            if token in low or token in ctype.lower():
                host = label
                break
    if host and not slot_count:
        slot_count = 1
    total_match = re.search(r'has\s+(\d+)\s+option slots?', low)
    slots_total = int(total_match.group(1)) if total_match else 0
    hosts_required = 2 if ('requires two cybereyes' in low or 'requires two cyberlegs' in low or 'must be paired' in low) else (1 if host else 0)
    unique = bool(re.search(r'only one|cannot be installed more than once|only be installed once|multiple installations.+no additional benefit', low))
    return requirements, {'host': host, 'hosts_required': hosts_required, 'slots_used': slot_count, 'slots_total': slots_total, 'unique': unique}


def item_mechanics(cat, row, desc):
    """Единая структурированная механика для каталога и серверной проверки."""
    mechanics = {}
    damage = parse_damage(row.get('Damage') or (desc if cat in ('grenades', 'gear') else None))
    if damage:
        mechanics['damage'] = damage
    labels = {
        'ROF': 'rof', 'Hands': 'hands', 'Mag': 'magazine', 'Skill': 'skill',
        'Conceal': 'concealable', 'Quality': 'quality', 'SP': 'sp', 'SDP': 'sdp',
        'Seats': 'seats', 'Speed (Combat)': 'combat_speed',
        'Speed (Narrative)': 'narrative_speed', 'Install': 'installation',
        'Nomad Access': 'nomad_access', 'Available': 'compatible_weapons',
        'Availability': 'availability', 'Suitable ammo / weapon': 'compatible_weapons',
        'PER': 'per', 'SPD': 'spd', 'ATK': 'atk', 'DEF': 'def', 'REZ': 'rez',
        'Class': 'program_class', 'Type': 'type',
    }
    for source, target in labels.items():
        value = row.get(source)
        if value is not None and str(value).strip() not in ('', '—', 'N/A'):
            mechanics[target] = normalize_mechanic_value(target, value)
    if cat == 'ammo':
        amount = re.search(r'(\d+)\s*(?:rounds?|arrows?|bolts?|rockets?|grenades?)', str(desc or ''), re.I)
        mechanics['quantity_per_purchase'] = int(amount.group(1)) if amount else 10
    if cat == 'fashion':
        for style in ('Bag Lady Chic', 'Generic Chic', 'Leisurewear', 'Urban Flash',
                      'Businesswear', 'High Fashion', 'Bohemian', 'Asia Pop',
                      'Gang Colors', 'Nomad Leathers'):
            if str(row.get('Name') or '').startswith(style):
                mechanics['fashion_style'] = style
                break
    return mechanics


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
                    it['fields'][key] = normalize_display_value(val)
            it['mechanics'] = item_mechanics(cat, r, desc)
            it.update(item_interaction_metadata(cat, name, r, desc))
            it.update(item_modification_metadata(cat, name, r, desc))
            requirements, capacity = structured_requirements(cat, r, desc)
            it['requirements'] = requirements
            if any(capacity.values()):
                it['capacity'] = capacity
            if cat == 'cyberware':
                it['cyberware_class'] = 'foundation' if capacity.get('slots_total') else ('option' if capacity.get('host') else 'standalone')
                it['hl'] = parse_hl(r.get('HL'))
            if cat == 'armor':
                it['sp'] = parse_sp(r.get('SP'))
                it['penalties'] = parse_armor_penalties(r.get('Penalty'))
                locations, bundled = armor_locations(name, desc, it['sp'])
                it['armor_locations'] = locations
                it['armor_bundled'] = bundled
                it['mechanics']['sp'] = it['sp']
                it['mechanics']['armor_locations'] = locations
                it['mechanics']['armor_bundled'] = bundled
                it['mechanics']['armor_penalties'] = it['penalties']
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

    cats = [{'id': c[1], 'en': c[0], 'ru': c[2], 'emoji': c[3], 'sheet': c[0], 'count': 0} for c in CATS]
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
