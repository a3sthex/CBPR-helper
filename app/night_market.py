"""Ночной рынок NC//NET: продавцы, детерминированные ротации, резервы (P1-7).

Выделено из app/server.py: дневные ротации ассортимента по сид-функции,
постоянный ассортимент (docs/permanent-assortment.md), стоки, цены с
репутационными/ролевыми модификаторами. Данные PERMANENT_SUPPLY переехали
вместе с доменом. Логика не менялась; crew_reputation_map остаётся в
server.py до выделения домена crew — через bind().
"""
import hashlib
import sqlite3
import time
from datetime import datetime, timedelta

from core import MOSCOW, parse_json_object
from catalog import catalog, item_effect_coverage


_LATE = {}


def bind(**kwargs):
    """Подключить поздние зависимости (см. docstring модуля)."""
    _LATE.update(kwargs)


PERMANENT_SUPPLY = {
    'gunmart-after-dark': [
        'ammo-0', 'ammo-1', 'ammo-4', 'ammo-8',
        'guns-0', 'guns-1', 'guns-2', 'guns-3', 'guns-5', 'guns-6',
        'guns-8', 'guns-9', 'melee-0', 'melee-1', 'melee-2', 'melee-3',
        'grenades-14', 'grenades-7', 'grenades-3'],
    'iron-shell': ['armor-1', 'armor-2', 'armor-3', 'armor-5', 'armor-6', 'armor-0'],
    'chrome-saint': ['cyberware-49', 'cyberware-56', 'cyberware-31', 'cyberware-2',
                     'cyberware-1', 'cyberware-90', 'cyberware-88'],
    'ghost-packet': ['net_stuff-5', 'net_stuff-4', 'net_stuff-19', 'programs-14',
                     'programs-12', 'programs-13', 'programs-6', 'programs-0'],
    'back-alley-general': [
        'gear-22', 'gear-27', 'gear-47', 'gear-60', 'gear-72', 'gear-10', 'gear-1',
        'gear-0', 'gear-6', 'gear-13', 'gear-19', 'gear-31', 'gear-50', 'gear-67',
        'gear-82', 'gear-91'],
    'street-pharmacy': ['gear-150', 'gear-151', 'gear-152', 'gear-153', 'gear-154',
                        'gear-155', 'gear-156', 'gear-157', 'gear-164'],
}



NM_PER_CAT = 6
NM_MULTS = [0.7, 0.8, 0.9, 0.9, 1.0, 1.0, 1.1, 1.2, 1.5]
NIGHT_MARKET_VENDORS = [
    {
        'id': 'gunmart-after-dark', 'handle': 'gunmart-after-dark', 'accent_color': '#ff9d45', 'name_en': 'Gunmart After Dark',
        'name_ru': 'Gunmart After Dark', 'icon': '🔫',
        'tagline_en': 'Weapons, ammunition, explosives, and questionable rebuilds.',
        'tagline_ru': 'Оружие, боеприпасы, взрывчатка и сомнительные переделки.',
        'cats': ['guns', 'melee', 'gun_upgrades', 'ammo', 'grenades'],
        'location': 'Watson',
        'location_id': 'megabuilding-h10',
    },
    {
        'id': 'iron-shell', 'handle': 'iron-shell', 'accent_color': '#8fa0bd', 'name_en': 'Iron Shell', 'name_ru': 'Iron Shell', 'icon': '🛡️',
        'tagline_en': 'Armor, shields, and the confidence to get shot twice.',
        'tagline_ru': 'Броня, щиты и уверенность, что переживёшь второй выстрел.',
        'cats': ['armor'],
        'location': 'Westbrook',
        'location_id': None,
    },
    {
        'id': 'chrome-saint', 'handle': 'chrome-saint', 'accent_color': '#ff2d78', 'name_en': 'Chrome Saint', 'name_ru': 'Chrome Saint', 'icon': '🦾',
        'tagline_en': 'Fashionware, chrome, and discreet installation referrals.',
        'tagline_ru': 'Fashionware, хром и контакты для неброской установки.',
        'cats': ['cyberware'],
        'location': 'City Center',
        'location_id': None,
    },
    {
        'id': 'ghost-packet', 'handle': 'ghost-packet', 'accent_color': '#00e5ff', 'name_en': 'Ghost Packet', 'name_ru': 'Ghost Packet', 'icon': '💾',
        'tagline_en': 'Cyberdecks, Programs, Black ICE, and NET hardware.',
        'tagline_ru': 'Cyberdeck, Programs, Black ICE и NET-железо.',
        'cats': ['net_stuff', 'programs'],
        'location': 'Heywood',
        'location_id': 'afterlife',
    },
    {
        'id': 'nomad-exchange', 'handle': 'nomad-exchange', 'accent_color': '#ffd500', 'name_en': 'Nomad Exchange', 'name_ru': 'Nomad Exchange', 'icon': '🏍️',
        'tagline_en': 'Vehicles, upgrades, cargo solutions, no fixed address.',
        'tagline_ru': 'Транспорт, апгрейды, грузовые решения и никакого адреса.',
        'cats': ['vehicles', 'vehicles_upgrades'],
        'location': 'Badlands',
        'location_id': None,
    },
    {
        'id': 'back-alley-general', 'handle': 'back-alley-general', 'accent_color': '#3cf28a', 'name_en': 'Back-Alley General',
        'name_ru': 'Back-Alley General', 'icon': '🎒',
        'tagline_en': 'Gear, fashion, services, and everything nobody admits buying.',
        'tagline_ru': 'Снаряжение, мода, услуги и всё, в покупке чего не признаются.',
        'cats': ['gear', 'fashion', 'services'],
        'exclude_consumable': True,
        'location': 'Pacifica',
        'location_id': 'grand-imperial-mall',
    },
    {
        'id': 'street-pharmacy', 'handle': 'street-pharmacy', 'accent_color': '#b388ff', 'name_en': 'Street Pharmacy',
        'name_ru': 'Street Pharmacy', 'icon': '💊',
        'tagline_en': 'Pharma and street drugs — no prescription, no questions.',
        'tagline_ru': 'Фарма и уличные наркотики — без рецепта и без вопросов.',
        'cats': ['gear'],
        'consumable_only': True,
        'location': 'Watson',
        'location_id': None,
    },
]


def _h(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16)


def nm_day():
    return datetime.now(MOSCOW).strftime('%Y-%m-%d')


def nm_day_offset(day, delta_days):
    try:
        base = datetime.strptime(str(day or ''), '%Y-%m-%d')
    except ValueError:
        return day
    return (base + timedelta(days=int(delta_days))).strftime('%Y-%m-%d')


def nm_stock_seed(day, vendor_id, item_id):
    """Deterministic 1..5 unit stock seed for a daily vendor+item offer."""
    return 1 + _h(f'stock|{day}|{vendor_id}|{item_id}') % 5


def permanent_offer_payload(item, vendor_id):
    return {
        'id': item['id'], 'cat': item['cat'], 'name': item['name'],
        'price': item['price'], 'street_price': item['price'],
        'permanent': True, 'discount': False, 'multiplier': 1.0,
        'fields': item.get('fields') or {}, 'mechanics': item.get('mechanics') or {},
        'requirements': item.get('requirements') or [], 'capacity': item.get('capacity'),
        'source': item.get('source'), 'desc': item.get('desc'),
        'armor_locations': item.get('armor_locations'), 'armor_bundled': item.get('armor_bundled'),
        'effect_coverage': item_effect_coverage(item.get('id')), 'vendor_id': vendor_id,
    }


def ensure_market_permanent(conn):
    """Idempotently seed the curated always-available base stock."""
    now = time.time()
    by_id = catalog()['_by_id']
    for vendor_id, item_ids in PERMANENT_SUPPLY.items():
        for sort_order, item_id in enumerate(item_ids):
            if item_id in by_id:
                conn.execute(
                    'INSERT OR IGNORE INTO market_permanent(vendor_id,item_id,sort_order,created) '
                    'VALUES(?,?,?,?)', (vendor_id, item_id, sort_order, now))


def market_permanent_rows(conn):
    try:
        rows = conn.execute(
            'SELECT vendor_id,item_id FROM market_permanent ORDER BY vendor_id,sort_order').fetchall()
    except sqlite3.OperationalError:
        return {}
    groups = {}
    for row in rows:
        groups.setdefault(row['vendor_id'], []).append(row['item_id'])
    return groups


def permanent_offers(conn):
    """Permanent offer payloads grouped by vendor_id."""
    groups = market_permanent_rows(conn)
    by_id = catalog()['_by_id']
    return {vendor_id: [permanent_offer_payload(by_id[item_id], vendor_id)
                        for item_id in item_ids if item_id in by_id]
            for vendor_id, item_ids in groups.items()}


def nm_offer_payload(item, day, vendor_id):
    multiplier = NM_MULTS[
        _h(f'price|{day}|{vendor_id}|{item["id"]}') % len(NM_MULTS)]
    street = round(item['price'] * multiplier)
    return {
        'id': item['id'], 'cat': item['cat'], 'name': item['name'],
        'price': item['price'], 'street_price': street,
        'discount': street < item['price'], 'multiplier': multiplier,
        'fields': item.get('fields') or {},
        'mechanics': item.get('mechanics') or {},
        'requirements': item.get('requirements') or [],
        'capacity': item.get('capacity'),
        'source': item.get('source'), 'desc': item.get('desc'),
        'armor_locations': item.get('armor_locations'),
        'armor_bundled': item.get('armor_bundled'),
        'effect_coverage': item_effect_coverage(item.get('id')),
        'vendor_id': vendor_id,
    }


def nm_rotation(day):
    """Deterministic per-day vendor rotation with no persistent state."""
    cat = catalog()
    all_items = []
    vendors = []
    for vendor in NIGHT_MARKET_VENDORS:
        stock = []
        for category_id in vendor['cats']:
            pool = [item for item in cat['items']
                    if item['cat'] == category_id and item.get('price')]
            if vendor.get('consumable_only'):
                pool = [item for item in pool if item.get('consumable')]
            elif vendor.get('exclude_consumable'):
                pool = [item for item in pool if not item.get('consumable')]
            pool.sort(key=lambda item: _h(
                f'{day}|{vendor["id"]}|{category_id}|{item["id"]}'))
            for item in pool[:NM_PER_CAT]:
                payload = nm_offer_payload(item, day, vendor['id'])
                stock.append(payload)
                all_items.append(payload)
        vendor_payload = {key: value for key, value in vendor.items()
                          if key not in ('cats', 'consumable_only', 'exclude_consumable')}
        vendor_payload.update({'categories': list(vendor['cats']), 'items': stock})
        vendors.append(vendor_payload)
    return {'items': all_items, 'vendors': vendors}


def market_stock_rows(conn, day):
    rows = conn.execute(
        'SELECT * FROM market_stock WHERE market_day=?', (day,)).fetchall()
    return {row['item_id']: dict(row) for row in rows}


def ensure_market_stock(conn, day=None):
    """Idempotently seed the persistent finite stock for a market day."""
    day = day or nm_day()
    rotation = nm_rotation(day)
    now = time.time()
    for item in rotation['items']:
        seed = nm_stock_seed(day, item['vendor_id'], item['id'])
        conn.execute(
            'INSERT INTO market_stock(market_day,vendor_id,item_id,stock_initial,'
            'stock_remaining,reserved_character_id,reserved_note,created,updated) '
            'VALUES(?,?,?,?,?,NULL,\'\',?,?) '
            'ON CONFLICT(market_day,vendor_id,item_id) DO NOTHING',
            (day, item['vendor_id'], item['id'], seed, seed, now, now))
    return rotation


def night_market(day=None, conn=None):
    """Assemble the daily market with deterministic rotation and stock state."""
    day = day or nm_day()
    rotation = nm_rotation(day)
    yesterday_keys = {
        (item['vendor_id'], item['id']) for item in nm_rotation(nm_day_offset(day, -1))['items']
    }
    stock_rows = market_stock_rows(conn, day) if conn is not None else {}
    reserved_handles = {}
    if conn is not None:
        reserved_ids = {
            row['reserved_character_id'] for row in stock_rows.values()
            if row.get('reserved_character_id')
        }
        if reserved_ids:
            marks = ','.join('?' for _ in reserved_ids)
            for row in conn.execute(
                    f'SELECT id,data FROM characters WHERE id IN ({marks})',
                    tuple(sorted(reserved_ids))):
                reserved_handles[row['id']] = (
                    parse_json_object(row['data']).get('handle') or 'Unknown Edgerunner')
    for item in rotation['items']:
        seed = nm_stock_seed(day, item['vendor_id'], item['id'])
        item['new_today'] = (item['vendor_id'], item['id']) not in yesterday_keys
        item['stock'] = seed
        state_row = stock_rows.get(item['id'])
        if state_row is not None:
            item['stock'] = state_row['stock_initial']
            item['stock_remaining'] = max(0, state_row['stock_remaining'])
            item['reserved_character_id'] = state_row.get('reserved_character_id')
            item['reserved_note'] = state_row.get('reserved_note') or ''
        else:
            item['stock_remaining'] = seed
            item['reserved_character_id'] = None
            item['reserved_note'] = ''
        item['sold_out'] = item['stock_remaining'] <= 0
        item['reserved'] = bool(item.get('reserved_character_id'))
        item['reserved_handle'] = reserved_handles.get(item['reserved_character_id'])
    perm = permanent_offers(conn) if conn is not None else {}
    crew_rep = _LATE['crew_reputation_map'](conn) if conn is not None else {}
    for vendor in rotation['vendors']:
        vendor['permanent'] = perm.get(vendor['id'], [])
    rotation['crew_reputation'] = crew_rep
    rotation['date'] = day
    return rotation


def nm_price_map():
    return {i['id']: i['street_price'] for i in night_market()['items']}
