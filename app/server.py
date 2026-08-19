#!/usr/bin/env python3
"""CBPR Helper — онлайн-помощник для кампаний по Cyberpunk RED.

Только стандартная библиотека Python. Запуск:
    python3 app/server.py [--port 8000]
"""
import argparse
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
DB_PATH = os.path.join(DATA_DIR, 'cbpr.db')
STATIC_DIR = os.path.join(BASE, 'static')
ITEMS_PATH = os.path.join(DATA_DIR, 'items.json')

MOSCOW = timezone(timedelta(hours=3))
SESSION_TTL = 30 * 24 * 3600
PBKDF_ITERS = 120_000

# ---------------------------------------------------------------- каталог

_catalog = None


def load_catalog():
    global _catalog
    if _catalog is not None:
        return _catalog
    if not os.path.exists(ITEMS_PATH):
        sys.path.insert(0, BASE)
        import import_data
        import_data.main()
    with open(ITEMS_PATH, encoding='utf-8') as f:
        _catalog = json.load(f)
    _catalog['_by_id'] = {it['id']: it for it in _catalog['items']}
    return _catalog


def catalog():
    return load_catalog()


def item_by_id(iid):
    return catalog()['_by_id'].get(iid)


# ---------------------------------------------------------------- правила

STATS = ['INT', 'REF', 'DEX', 'TECH', 'COOL', 'WILL', 'LUCK', 'MOVE', 'BODY', 'EMP']

ROLES = {
    'Rockerboy': 'Charismatic Leadership',
    'Solo': 'Combat Awareness',
    'Netrunner': 'Interface',
    'Tech': 'Maker',
    'Medtech': 'Medicine',
    'Media': 'Credibility',
    'Exec': 'Teamwork',
    'Lawman': 'Backup',
    'Fixer': 'Operator',
    'Nomad': 'Moto',
}
ROLE_RU = {
    'Solo': 'Соло', 'Rockerboy': 'Рокербой', 'Netrunner': 'Нетраннер',
    'Tech': 'Техник', 'Medtech': 'Медтех', 'Media': 'Медиа', 'Exec': 'Корпорат',
    'Lawman': 'Законник', 'Fixer': 'Фиксер', 'Nomad': 'Номад',
}
ROLE_DESC = {
    'Rockerboy': 'Рок-н-ролльные бунтари, использующие выступления, искусство и словоблудие для борьбы со властью.',
    'Solo': 'Ассасины, телохранители, убийцы и наёмные солдаты в новом мире беззакония.',
    'Netrunner': 'Кибернетические мастера-хакеры Сетевого мира, выжигающие мозги похитители тайн и секретов.',
    'Tech': 'Механики-ренегаты и изобретатели супертехнологий. Люди, которые заставляют Тёмное Будущее развиваться.',
    'Medtech': 'Нелицензированные уличные доктора и рипперы, одинаково хорошо латающие мясо и хром.',
    'Media': 'Репортёры, медиа-звёзды и инфлюенсеры, рискующие всем ради правды или славы.',
    'Exec': 'Корпоративные воротилы и бизнес-рейдеры на службе у Мегакорпораций.',
    'Lawman': 'Блюстители порядка, патрулирующие неблагодарные улицы и шоссе с варварскими порядками далеко за пределами города.',
    'Fixer': 'Дельцы, организаторы, брокеры информацией на Полуночных Рынках.',
    'Nomad': 'Эксперты по транспорту, ультимативные воины дорог, пираты и контрабандисты, которые держат мир объединённым.',
}

SKILLS = [
    # (категория, имя, стата, x2 стоимость) — 66 навыков, как в гайде по созданию
    ('Осознание', 'Concentration', 'WILL', False),
    ('Осознание', 'Conceal/Reveal Object', 'INT', False),
    ('Осознание', 'Lip Reading', 'INT', False),
    ('Осознание', 'Perception', 'INT', False),
    ('Осознание', 'Tracking', 'INT', False),
    ('Тело', 'Athletics', 'DEX', False),
    ('Тело', 'Contortionist', 'DEX', False),
    ('Тело', 'Dance', 'DEX', False),
    ('Тело', 'Endurance', 'WILL', False),
    ('Тело', 'Resist Torture/Drugs', 'WILL', False),
    ('Тело', 'Stealth', 'DEX', False),
    ('Управление', 'Drive Land Vehicle', 'REF', False),
    ('Управление', 'Pilot Air Vehicle', 'REF', True),
    ('Управление', 'Pilot Sea Vehicle', 'REF', False),
    ('Управление', 'Riding', 'REF', False),
    ('Образование', 'Accounting', 'INT', False),
    ('Образование', 'Animal Handling', 'INT', False),
    ('Образование', 'Bureaucracy', 'INT', False),
    ('Образование', 'Business', 'INT', False),
    ('Образование', 'Composition', 'INT', False),
    ('Образование', 'Criminology', 'INT', False),
    ('Образование', 'Cryptography', 'INT', False),
    ('Образование', 'Deduction', 'INT', False),
    ('Образование', 'Education', 'INT', False),
    ('Образование', 'Gamble', 'INT', False),
    ('Образование', 'Language', 'INT', False),
    ('Образование', 'Library Search', 'INT', False),
    ('Образование', 'Local Expert', 'INT', False),
    ('Образование', 'Science', 'INT', False),
    ('Образование', 'Tactics', 'INT', False),
    ('Образование', 'Wilderness Survival', 'INT', False),
    ('Бой', 'Brawling', 'DEX', False),
    ('Бой', 'Evasion', 'DEX', False),
    ('Бой', 'Martial Arts', 'DEX', True),
    ('Бой', 'Melee Weapon', 'DEX', False),
    ('Выступление', 'Acting', 'COOL', False),
    ('Выступление', 'Play Instrument', 'TECH', False),
    ('Стрелковое', 'Archery', 'REF', False),
    ('Стрелковое', 'Autofire', 'REF', True),
    ('Стрелковое', 'Handgun', 'REF', False),
    ('Стрелковое', 'Heavy Weapons', 'REF', True),
    ('Стрелковое', 'Shoulder Arms', 'REF', False),
    ('Социальные', 'Bribery', 'COOL', False),
    ('Социальные', 'Conversation', 'EMP', False),
    ('Социальные', 'Human Perception', 'EMP', False),
    ('Социальные', 'Interrogation', 'COOL', False),
    ('Социальные', 'Persuasion', 'COOL', False),
    ('Социальные', 'Personal Grooming', 'COOL', False),
    ('Социальные', 'Streetwise', 'COOL', False),
    ('Социальные', 'Trading', 'COOL', False),
    ('Социальные', 'Wardrobe & Style', 'COOL', False),
    ('Технические', 'Air Vehicle Tech', 'TECH', False),
    ('Технические', 'Basic Tech', 'TECH', False),
    ('Технические', 'Cybertech', 'TECH', False),
    ('Технические', 'Demolitions', 'TECH', True),
    ('Технические', 'Electronics/Security Tech', 'TECH', True),
    ('Технические', 'First Aid', 'TECH', False),
    ('Технические', 'Forgery', 'TECH', False),
    ('Технические', 'Land Vehicle Tech', 'TECH', False),
    ('Технические', 'Paint/Draw/Sculpt', 'TECH', False),
    ('Технические', 'Paramedic', 'TECH', True),
    ('Технические', 'Photography/Film', 'TECH', False),
    ('Технические', 'Pick Lock', 'TECH', False),
    ('Технические', 'Pick Pocket', 'TECH', False),
    ('Технические', 'Sea Vehicle Tech', 'TECH', False),
    ('Технические', 'Weaponstech', 'TECH', False),
]
SKILL_BY_NAME = {s[1]: s for s in SKILLS}

# Правила создания из гайда «Создание Киберпанка» (Spes Desperata)
STAT_POINTS = 62          # на 10 характеристик, каждая 2–8
SKILL_POINTS = 86         # на навыки: 26 в обязательные минимумы + 60 свободных
SKILL_MAX_CREATION = 6    # максимум уровня навыка при создании
MUST_SKILLS = [           # минимум 2 очка в каждом (итого 26)
    'Athletics', 'Brawling', 'Concentration', 'Conversation', 'Education',
    'Evasion', 'First Aid', 'Human Perception', 'Language',
    'Local Expert', 'Perception', 'Persuasion', 'Stealth',
]
START_CASH_GEAR = 2550    # стартовые €$ на оружие/броню/снаряжение/хром
START_CASH_FASHION = 800  # отдельный бюджет на Fashion и Fashionware

# Состояния ранений: (название, порог, эффект, DV стабилизации)
WOUND_STATES = [
    ['Смертельное (Mortally Wounded)', 'HP < 1',
     '−4 ко всем действиям, −6 MOVE (мин. 1). В начале хода — спасбросок смерти. Урон атакой: +крит. травма и +1 к штрафу спасброска.', 'DV15 → 1 HP, без сознания (1 минута)'],
    ['Серьёзное (Seriously Wounded)', 'HP ≤ ½ максимума (вверх)',
     '−2 ко всем действиям.', 'DV13'],
    ['Лёгкое (Lightly Wounded)', 'HP < максимума', 'Эффектов нет.', 'DV10'],
    ['Мёртв', 'Проваленный спасбросок смерти', 'Ты мёртв. Соболезнуем.', '—'],
]

# Критические травмы тела: (2d6, травма, эффект, Quick Fix, Treatment)
CRIT_BODY = [
    [2, 'Dismembered Arm (Отрубленная рука)', 'Руки больше нет. Вы роняете все предметы в её кисти. +1 к Base Death Save Penalty.', '—', 'Surgery DV17'],
    [3, 'Dismembered Hand (Отрубленная кисть)', 'Кисти больше нет. Вы роняете все предметы в ней. +1 к Base Death Save Penalty.', '—', 'Surgery DV17'],
    [4, 'Collapsed Lung (Коллапс лёгкого)', '−2 MOVE (мин. 1). +1 к Base Death Save Penalty.', 'Paramedic DV15', 'Surgery DV15'],
    [5, 'Broken Ribs (Перелом рёбер)', 'При перемещении более 4 м на ногах — снова бонусный урон крит. травмы в конце хода.', 'Paramedic DV13', 'Paramedic DV15 или Surgery DV13'],
    [6, 'Broken Arm (Перелом руки)', 'Сломанная рука не используется. Вы роняете всё из её кисти.', 'Paramedic DV13', 'Paramedic DV15 или Surgery DV13'],
    [7, 'Foreign Object (Инородное тело)', 'При перемещении более 4 м на ногах — снова бонусный урон крит. травмы в конце хода.', 'First Aid или Paramedic DV13', 'Quick Fix убирает навсегда'],
    [8, 'Broken Leg (Перелом ноги)', '−4 MOVE (мин. 1).', 'Paramedic DV13', 'Paramedic DV15 или Surgery DV13'],
    [9, 'Torn Muscle (Разрыв мышц)', '−2 к атакам ближнего боя.', 'First Aid или Paramedic DV13', 'Quick Fix убирает навсегда'],
    [10, 'Spinal Injury (Травма позвоночника)', 'В следующем ходу нельзя использовать Действие (можно Перемещаться). +1 к Base Death Save Penalty.', 'Paramedic DV15', 'Surgery DV15'],
    [11, 'Crushed Fingers (Раздавленные пальцы)', '−4 ко всем Действиям этой кистью.', 'Paramedic DV13', 'Surgery DV15'],
    [12, 'Dismembered Leg (Отрубленная нога)', '−6 MOVE (мин. 1). Нельзя уклоняться. +1 к Base Death Save Penalty.', '—', 'Surgery DV17'],
]

# Критические травмы головы
CRIT_HEAD = [
    [2, 'Lost Eye (Потеря глаза)', 'Глаза больше нет. −4 к атакам дальнего боя и зрительным Perception. +1 к Base Death Save Penalty.', '—', 'Surgery DV17'],
    [3, 'Brain Injury (Черепно-мозговая травма)', '−2 ко всем Действиям. +1 к Base Death Save Penalty.', '—', 'Surgery DV17'],
    [4, 'Damaged Eye (Повреждение глаза)', '−2 к атакам дальнего боя и зрительным Perception.', 'Paramedic DV15', 'Surgery DV13'],
    [5, 'Concussion (Сотрясение)', '−2 ко всем Действиям.', 'First Aid или Paramedic DV13', 'Quick Fix убирает навсегда'],
    [6, 'Broken Jaw (Перелом челюсти)', '−4 ко всем Действиям, связанным с речью.', 'Paramedic DV13', 'Paramedic или Surgery DV13'],
    [7, 'Foreign Object (Инородное тело)', 'При перемещении более 4 м на ногах — снова бонусный урон крит. травмы в конце хода.', 'First Aid или Paramedic DV13', 'Quick Fix убирает навсегда'],
    [8, 'Whiplash (Хлыстовая травма)', '+1 к Base Death Save Penalty.', 'Paramedic DV13', 'Paramedic или Surgery DV13'],
    [9, 'Cracked Skull (Треснувший череп)', 'Прицельные атаки в голову дают модификатор ×3, а не ×2. +1 к Base Death Save Penalty.', 'Paramedic DV15', 'Paramedic или Surgery DV15'],
    [10, 'Damaged Ear (Повреждение уха)', 'При перемещении более 4 м — нельзя перемещаться в следующем ходу. −2 к слуховым Perception.', 'Paramedic DV13', 'Surgery DV13'],
    [11, 'Crushed Windpipe (Раздавленная трахея)', 'Нельзя говорить. +1 к Base Death Save Penalty.', '—', 'Surgery DV15'],
    [12, 'Lost Ear (Потеря уха)', 'Уха больше нет. При перемещении более 4 м — нельзя перемещаться в следующем ходу. −4 к слуховым Perception. +1 к Base Death Save Penalty.', '—', 'Surgery DV17'],
]


def derive(char):
    """Производные показатели листа персонажа."""
    st = char.get('stats') or {}
    out = {}
    body = _num(st.get('BODY'))
    will = _num(st.get('WILL'))
    if body is not None and will is not None:
        hp_max = 10 + 5 * ((body + will + 1) // 2)
        out['hp_max'] = hp_max
        out['seriously_wounded'] = (hp_max + 1) // 2
        out['death_save'] = body
    # хром: HL + срез максимума человечности (фэшнвер 0, боргвер 4, прочий хром 2)
    hl_total = sum(_num(c.get('hl')) or 0 for c in char.get('cyberware') or [])
    hum_cut = 0
    for c in char.get('cyberware') or []:
        t = str(c.get('type') or '').lower()
        if 'borgware' in t:
            hum_cut += 4
        elif 'fashionware' not in t:
            hum_cut += 2
    emp_base = _num(st.get('EMP'))
    if emp_base is not None:
        hum_max = emp_base * 10 - hl_total - hum_cut
        out['humanity_max'] = hum_max
        hum_cur = char.get('humanity_cur')
        if hum_cur is None:
            hum_cur = hum_max
        hum_cur = max(0, min(hum_cur, hum_max)) if hum_max >= 0 else 0
        out['humanity_cur'] = hum_cur
        out['emp_cur'] = hum_cur // 10
        out['hl_total'] = hl_total
        out['hum_cut'] = hum_cut
    # броня
    armor = char.get('armor') or {}
    sps = []
    penalty = 0
    for slot in ('body_outer', 'body_inner'):
        a = armor.get(slot)
        if a and _num(a.get('sp')) is not None:
            sps.append(_num(a['sp']))
            penalty += _num(a.get('penalty')) or 0
    if sps:
        sps.sort(reverse=True)
        sp = sps[0] + ((sps[1] + 1) // 2 if len(sps) > 1 else 0)
        out['sp_body'] = sp
        out['armor_penalty'] = penalty
    head = armor.get('head')
    if head and _num(head.get('sp')) is not None:
        out['sp_head'] = _num(head['sp'])
        out['armor_penalty'] = penalty + (_num(head.get('penalty')) or 0)
    return out


def _num(v):
    if v is None or v == '':
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        try:
            return int(float(v))
        except (TypeError, ValueError):
            return None


# ---------------------------------------------------------------- бд

SCHEMA = """
CREATE TABLE IF NOT EXISTS users(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  pass_hash TEXT NOT NULL,
  is_gm INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions(
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  created REAL NOT NULL,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS characters(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_id INTEGER NOT NULL,
  public INTEGER NOT NULL DEFAULT 1,
  data TEXT NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS news(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  tag TEXT,
  body TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  author_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  when_text TEXT,
  system TEXT DEFAULT 'Cyberpunk RED',
  description TEXT NOT NULL,
  slots INTEGER DEFAULT 0,
  status TEXT DEFAULT 'open',
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS job_signups(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  char_name TEXT,
  note TEXT,
  created REAL NOT NULL,
  UNIQUE(job_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_char_owner ON characters(owner_id);
CREATE INDEX IF NOT EXISTS idx_news_created ON news(created);
"""


def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = db()
    conn.executescript(SCHEMA)
    conn.commit()
    # сид: архивный пользователь + ростер из Folio
    has = conn.execute('SELECT COUNT(*) c FROM users WHERE id=1').fetchone()['c']
    if not has:
        folio = catalog().get('folio') or []
        if folio:
            conn.execute(
                'INSERT INTO users(id, username, display_name, pass_hash, is_gm, created) '
                'VALUES(1, ?, ?, ?, 0, ?)',
                ('archive', 'Архив кампании', 'x$seed$disabled', time.time()))
            now = time.time()
            for f in folio:
                data = {
                    'handle': f['handle'],
                    'role': f.get('role'),
                    'role_rank': f.get('role_rank') or 4,
                    'player': f.get('player'),
                    'seed': True,
                    'notes': 'Импортировано из Data Pool.xlsx (лист Folio).',
                    'extra': f.get('extra') or {},
                    'stats': {}, 'skills': {}, 'inventory': [],
                    'cyberware': [], 'armor': {}, 'cash': 0,
                }
                conn.execute(
                    'INSERT INTO characters(owner_id, public, data, created, updated) '
                    'VALUES(1, 1, ?, ?, ?)', (json.dumps(data, ensure_ascii=False), now, now))
            conn.commit()
            print(f'Сид: {len(folio)} персонажей Folio для пользователя «Архив кампании».')
    conn.close()


# ---------------------------------------------------------------- auth

def hash_password(pw):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), PBKDF_ITERS)
    return f'pbkdf2${PBKDF_ITERS}${salt}${dk.hex()}'


def verify_password(pw, stored):
    try:
        _, iters, salt, hexdk = stored.split('$')
        dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), hexdk)
    except Exception:
        return False


def create_session(conn, user_id):
    token = secrets.token_hex(32)
    now = time.time()
    conn.execute('INSERT INTO sessions(token, user_id, created, expires) VALUES(?,?,?,?)',
                 (token, user_id, now, now + SESSION_TTL))
    conn.execute('DELETE FROM sessions WHERE expires < ?', (now,))
    conn.commit()
    return token


# ---------------------------------------------------------------- ночной рынок

NM_PER_CAT = 4
NM_MULTS = [0.7, 0.8, 0.9, 0.9, 1.0, 1.0, 1.1, 1.2, 1.5]


def _h(s):
    return int(hashlib.sha256(s.encode()).hexdigest()[:12], 16)


def nm_day():
    return datetime.now(MOSCOW).strftime('%Y-%m-%d')


def night_market():
    cat = catalog()
    day = nm_day()
    out = []
    for c in cat['cats']:
        pool = [i for i in cat['items'] if i['cat'] == c['id'] and i.get('price')]
        pool.sort(key=lambda i: _h(f'{day}|{c["id"]}|{i["id"]}'))
        for it in pool[:NM_PER_CAT]:
            m = NM_MULTS[_h(f'p|{day}|{it["id"]}') % len(NM_MULTS)]
            street = round(it['price'] * m)
            out.append({
                'id': it['id'], 'cat': it['cat'], 'name': it['name'],
                'price': it['price'], 'street_price': street,
                'discount': street < it['price'],
                'fields': it['fields'], 'source': it['source'], 'desc': it['desc'],
            })
    return {'date': day, 'items': out}


def nm_price_map():
    return {i['id']: i['street_price'] for i in night_market()['items']}


# ---------------------------------------------------------------- валидация персонажа

MAX_CHAR_BYTES = 300_000


def clean_character(data):
    if not isinstance(data, dict):
        raise ApiError(400, 'Лист персонажа должен быть объектом')
    raw = json.dumps(data, ensure_ascii=False)
    if len(raw.encode()) > MAX_CHAR_BYTES:
        raise ApiError(413, 'Лист персонажа слишком большой')
    out = dict(data)
    out['handle'] = str(out.get('handle') or '').strip()[:60]
    if not out['handle']:
        raise ApiError(400, 'Нужен псевдоним (Handle) персонажа')
    for k in ('notes', 'appearance', 'background', 'player'):
        if out.get(k) is not None:
            out[k] = str(out[k])[:4000]
    stats = out.get('stats')
    if stats is not None:
        if not isinstance(stats, dict):
            raise ApiError(400, 'stats должен быть объектом')
        clean = {}
        for k in STATS:
            v = _num(stats.get(k))
            if v is not None:
                clean[k] = max(1, min(13, v))
        out['stats'] = clean
    for k in ('inventory', 'cyberware'):
        v = out.get(k)
        if v is None:
            out[k] = []
        elif not isinstance(v, list) or len(v) > 300:
            raise ApiError(400, f'{k}: ожидается список (до 300 записей)')
    if not isinstance(out.get('skills') or {}, dict):
        out['skills'] = {}
    if not isinstance(out.get('armor') or {}, dict):
        out['armor'] = {}
    out['cash'] = max(0.0, min(9_999_999.0, float(out.get('cash') or 0)))
    return out


# ---------------------------------------------------------------- http

class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


def q1(v, default=None):
    return v[0] if v else default


class Handler(BaseHTTPRequestHandler):
    server_version = 'CBPR/1.0'

    # -- утилиты
    def log_message(self, fmt, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def send_json(self, obj, status=200, cookies=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for c in cookies or []:
            self.send_header('Set-Cookie', c)
        self.end_headers()
        self.wfile.write(body)

    def send_error_json(self, status, message):
        self.send_json({'error': message}, status)

    def read_json(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0:
            raise ApiError(400, 'Пустое тело запроса')
        if n > 1_000_000:
            raise ApiError(413, 'Тело запроса слишком большое')
        try:
            return json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            raise ApiError(400, 'Некорректный JSON')

    def cookies(self):
        out = {}
        raw = self.headers.get('Cookie') or ''
        for part in raw.split(';'):
            if '=' in part:
                k, v = part.strip().split('=', 1)
                out[k] = v
        return out

    def current_user(self, conn):
        tok = self.cookies().get('sid')
        if not tok:
            return None
        row = conn.execute(
            'SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id '
            'WHERE s.token=? AND s.expires > ?', (tok, time.time())).fetchone()
        return dict(row) if row else None

    def require_user(self, conn):
        u = self.current_user(conn)
        if not u:
            raise ApiError(401, 'Требуется вход в систему')
        return u

    def require_gm(self, conn):
        u = self.require_user(conn)
        if not u['is_gm']:
            raise ApiError(403, 'Только для пользователей с ролью ГМ')
        return u

    # -- диспетчеризация
    def do_GET(self):
        self.dispatch('GET')

    def do_POST(self):
        self.dispatch('POST')

    def do_PUT(self):
        self.dispatch('PUT')

    def do_DELETE(self):
        self.dispatch('DELETE')

    def dispatch(self, method):
        parsed = urlparse(self.path)
        path = unquote(parsed.path)
        qs = parse_qs(parsed.query)
        if path.startswith('/api/'):
            conn = db()
            try:
                for m, rx, fn in ROUTES:
                    if m != method:
                        continue
                    match = rx.match(path)
                    if match:
                        fn(self, conn, qs, match, self.read_json() if method in ('POST', 'PUT') else None)
                        return
                raise ApiError(404, 'Не найдено')
            except ApiError as e:
                self.send_error_json(e.status, e.message)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                self.send_error_json(500, 'Внутренняя ошибка сервера')
            finally:
                conn.close()
        elif method == 'GET':
            self.serve_static(path)
        else:
            self.send_error_json(405, 'Метод не поддерживается')

    def serve_static(self, path):
        if path in ('/', '/index.html'):
            fp = os.path.join(STATIC_DIR, 'index.html')
        else:
            rel = os.path.normpath(path.lstrip('/'))
            if rel.startswith('..'):
                self.send_error_json(403, 'Запрещено')
                return
            fp = os.path.join(STATIC_DIR, rel)
        if not os.path.isfile(fp):
            # SPA-фолбэк на корневые не-/api пути
            if not os.path.splitext(path)[1]:
                fp = os.path.join(STATIC_DIR, 'index.html')
            else:
                self.send_error_json(404, 'Не найдено')
                return
        ext = os.path.splitext(fp)[1].lower()
        ctype = {
            '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
            '.css': 'text/css; charset=utf-8', '.json': 'application/json; charset=utf-8',
            '.svg': 'image/svg+xml', '.png': 'image/png', '.ico': 'image/x-icon',
        }.get(ext, 'application/octet-stream')
        with open(fp, 'rb') as f:
            body = f.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ auth api

    def api_register(self, conn, qs, m, body):
        username = str(body.get('username') or '').strip().lower()
        password = str(body.get('password') or '')
        display = str(body.get('display_name') or '').strip()[:60] or username
        is_gm = 1 if body.get('is_gm') else 0
        if not re.fullmatch(r'[a-z0-9_.\-]{3,24}', username):
            raise ApiError(400, 'Логин: 3–24 символа, латиница/цифры/._-')
        if len(password) < 4:
            raise ApiError(400, 'Пароль: минимум 4 символа')
        try:
            cur = conn.execute(
                'INSERT INTO users(username, display_name, pass_hash, is_gm, created) '
                'VALUES(?,?,?,?,?)',
                (username, display, hash_password(password), is_gm, time.time()))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ApiError(409, 'Такой логин уже занят')
        token = create_session(conn, cur.lastrowid)
        u = conn.execute('SELECT * FROM users WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.me_payload(u), cookies=[
            f'sid={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}'])

    def api_login(self, conn, qs, m, body):
        username = str(body.get('username') or '').strip().lower()
        password = str(body.get('password') or '')
        u = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not u or not verify_password(password, u['pass_hash']):
            raise ApiError(401, 'Неверный логин или пароль')
        token = create_session(conn, u['id'])
        self.send_json(self.me_payload(u), cookies=[
            f'sid={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={SESSION_TTL}'])

    def api_logout(self, conn, qs, m, body):
        tok = self.cookies().get('sid')
        if tok:
            conn.execute('DELETE FROM sessions WHERE token=?', (tok,))
            conn.commit()
        self.send_json({'ok': True}, cookies=['sid=; Path=/; HttpOnly; Max-Age=0'])

    def me_payload(self, u):
        return {'id': u['id'], 'username': u['username'], 'display_name': u['display_name'],
                'is_gm': bool(u['is_gm'])}

    def api_me(self, conn, qs, m, body):
        u = self.current_user(conn)
        self.send_json({'user': self.me_payload(u) if u else None})

    def api_profile(self, conn, qs, m, body):
        u = self.require_user(conn)
        if 'display_name' in (body or {}):
            dn = str(body['display_name'] or '').strip()[:60]
            if dn:
                conn.execute('UPDATE users SET display_name=? WHERE id=?', (dn, u['id']))
        if 'is_gm' in (body or {}):
            conn.execute('UPDATE users SET is_gm=? WHERE id=?',
                         (1 if body['is_gm'] else 0, u['id']))
        conn.commit()
        u2 = conn.execute('SELECT * FROM users WHERE id=?', (u['id'],)).fetchone()
        self.send_json(self.me_payload(u2))

    # ------------------------------------------------------------ мета/справочник

    def api_meta(self, conn, qs, m, body):
        cat = catalog()
        self.send_json({
            'stats': STATS, 'roles': ROLES, 'role_ru': ROLE_RU, 'role_desc': ROLE_DESC,
            'skills': SKILLS, 'must_skills': MUST_SKILLS,
            'stat_points': STAT_POINTS, 'skill_points': SKILL_POINTS,
            'skill_max': SKILL_MAX_CREATION,
            'start_cash_gear': START_CASH_GEAR, 'start_cash_fashion': START_CASH_FASHION,
            'wound_states': WOUND_STATES, 'crit_body': CRIT_BODY, 'crit_head': CRIT_HEAD,
            'cats': cat['cats'],
            'range_table': cat['range_table'],
            'autofire_table': cat['autofire_table'],
        })

    def api_stats(self, conn, qs, m, body):
        cat = catalog()
        c = conn.execute('SELECT COUNT(*) n FROM characters').fetchone()['n']
        u = conn.execute('SELECT COUNT(*) n FROM users WHERE id > 1').fetchone()['n']
        nw = conn.execute('SELECT COUNT(*) n FROM news').fetchone()['n']
        jb = conn.execute("SELECT COUNT(*) n FROM jobs WHERE status='open'").fetchone()['n']
        self.send_json({'items': len(cat['items']), 'characters': c, 'users': u,
                        'news': nw, 'open_jobs': jb})

    def api_items(self, conn, qs, m, body):
        cat = catalog()
        q = (q1(qs.get('q')) or '').strip().lower()
        cat_id = q1(qs.get('cat'))
        try:
            limit = min(500, max(1, int(q1(qs.get('limit'), '30'))))
            offset = max(0, int(q1(qs.get('offset'), '0')))
        except ValueError:
            limit, offset = 30, 0
        items = cat['items']
        if cat_id:
            items = [i for i in items if i['cat'] == cat_id]
        if q:
            terms = q.split()
            items = [i for i in items if all(t in i['search'] for t in terms)]
        total = len(items)
        items = items[offset:offset + limit]
        self.send_json({'total': total, 'items': items, 'offset': offset, 'limit': limit})

    def api_item(self, conn, qs, m, body):
        it = item_by_id(m.group(1))
        if not it:
            raise ApiError(404, 'Предмет не найден')
        self.send_json(it)

    def api_nightmarket(self, conn, qs, m, body):
        self.send_json(night_market())

    # ------------------------------------------------------------ персонажи

    CHAR_LIST_FIELDS = ('id', 'owner_id', 'public', 'created', 'updated')

    def char_payload(self, row, owner_name=None):
        data = json.loads(row['data'])
        return {
            'id': row['id'], 'owner_id': row['owner_id'], 'public': bool(row['public']),
            'owner_name': owner_name, 'created': row['created'], 'updated': row['updated'],
            'data': data, 'derived': derive(data),
        }

    def api_my_characters(self, conn, qs, m, body):
        u = self.require_user(conn)
        rows = conn.execute(
            'SELECT * FROM characters WHERE owner_id=? ORDER BY updated DESC',
            (u['id'],)).fetchall()
        self.send_json({'characters': [self.char_payload(r, u['display_name']) for r in rows]})

    def api_create_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        data = clean_character(body.get('data') if isinstance(body, dict) else body)
        count = conn.execute('SELECT COUNT(*) n FROM characters WHERE owner_id=?',
                             (u['id'],)).fetchone()['n']
        if count >= 50:
            raise ApiError(400, 'Слишком много персонажей (максимум 50)')
        now = time.time()
        pub = 1 if data.get('public', True) else 0
        cur = conn.execute(
            'INSERT INTO characters(owner_id, public, data, created, updated) VALUES(?,?,?,?,?)',
            (u['id'], pub, json.dumps(data, ensure_ascii=False), now, now))
        conn.commit()
        row = conn.execute('SELECT * FROM characters WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.char_payload(row, u['display_name']), status=201)

    def get_char(self, conn, cid):
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            raise ApiError(404, 'Персонаж не найден')
        row = conn.execute(
            'SELECT c.*, u.display_name owner FROM characters c '
            'JOIN users u ON u.id=c.owner_id WHERE c.id=?', (cid,)).fetchone()
        if not row:
            raise ApiError(404, 'Персонаж не найден')
        return row

    def api_get_character(self, conn, qs, m, body):
        row = self.get_char(conn, m.group(1))
        u = self.current_user(conn)
        if not row['public'] and (not u or u['id'] != row['owner_id']):
            raise ApiError(403, 'Персонаж приватный')
        self.send_json(self.char_payload(row, row['owner']))

    def api_save_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, m.group(1))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        data = clean_character(body.get('data') if isinstance(body, dict) else body)
        pub = 1 if data.get('public', True) else 0
        conn.execute('UPDATE characters SET data=?, public=?, updated=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), pub, time.time(), row['id']))
        conn.commit()
        row = self.get_char(conn, row['id'])
        self.send_json(self.char_payload(row, row['owner']))

    def api_delete_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, m.group(1))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        conn.execute('DELETE FROM characters WHERE id=?', (row['id'],))
        conn.commit()
        self.send_json({'ok': True})

    def api_roster(self, conn, qs, m, body):
        rows = conn.execute(
            'SELECT c.*, u.display_name owner FROM characters c '
            'JOIN users u ON u.id=c.owner_id WHERE c.public=1 '
            'ORDER BY u.id, c.id').fetchall()
        q = (q1(qs.get('q')) or '').strip().lower()
        out = []
        for r in rows:
            p = self.char_payload(r, r['owner'])
            d = p['data']
            hay = ' '.join(filter(None, [d.get('handle'), d.get('role'),
                                         d.get('player'), r['owner']])).lower()
            if q and q not in hay:
                continue
            out.append(p)
        self.send_json({'characters': out})

    # ------------------------------------------------------------ рынок

    def api_buy(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, body.get('char_id'))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        data = json.loads(row['data'])
        cart = body.get('items') or []
        if not cart or not isinstance(cart, list):
            raise ApiError(400, 'Пустая корзина')
        nm = nm_price_map()
        total = 0.0
        bought = []
        for entry in cart[:50]:
            it = item_by_id(str(entry.get('id') or ''))
            if not it or not it.get('price'):
                continue
            qty = max(1, min(99, int(entry.get('qty') or 1)))
            if entry.get('mode') == 'nm' and it['id'] in nm:
                price = nm[it['id']]
            else:
                price = it['price']
            total += price * qty
            bought.append((it, qty, price))
        if not bought:
            raise ApiError(400, 'В корзине нет известных товаров')
        cash = float(data.get('cash') or 0)
        if total > cash + 1e-9:
            raise ApiError(400, f'Не хватает €$: нужно {total:,.0f}, есть {cash:,.0f}')
        inv = data.setdefault('inventory', [])
        for it, qty, price in bought:
            found = next((x for x in inv if x.get('key') == it['id']), None)
            if found:
                found['qty'] = int(found.get('qty') or 1) + qty
            else:
                inv.append({
                    'key': it['id'], 'cat': it['cat'], 'name': it['name'],
                    'price': price, 'qty': qty,
                    'damage': it.get('damage'), 'sp': it.get('sp'), 'hl': it.get('hl'),
                })
        data['cash'] = round(cash - total, 2)
        conn.execute('UPDATE characters SET data=?, updated=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        receipt = [{'name': it['name'], 'qty': qty, 'price': price}
                   for it, qty, price in bought]
        self.send_json({'ok': True, 'total': round(total, 2), 'cash': data['cash'],
                        'receipt': receipt})

    def api_sell(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, body.get('char_id'))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        data = json.loads(row['data'])
        key = str(body.get('key') or '')
        qty = max(1, int(body.get('qty') or 1))
        inv = data.get('inventory') or []
        ent = next((x for x in inv if x.get('key') == key), None)
        if not ent:
            raise ApiError(404, 'Предмет не найден в инвентаре')
        qty = min(qty, int(ent.get('qty') or 1))
        back = round(float(ent.get('price') or 0) * 0.5 * qty, 2)
        ent['qty'] = int(ent.get('qty') or 1) - qty
        if ent['qty'] <= 0:
            data['inventory'] = [x for x in inv if x.get('key') != key]
        data['cash'] = round(float(data.get('cash') or 0) + back, 2)
        conn.execute('UPDATE characters SET data=?, updated=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'got': back,
                        'name': ent.get('name'), 'qty': qty})

    def api_payroll(self, conn, qs, m, body):
        u = self.require_gm(conn)
        row = self.get_char(conn, body.get('char_id'))
        amount = float(body.get('amount') or 0)
        if abs(amount) > 1e7:
            raise ApiError(400, 'Слишком большая сумма')
        data = json.loads(row['data'])
        data['cash'] = max(0.0, round(float(data.get('cash') or 0) + amount, 2))
        conn.execute('UPDATE characters SET data=?, updated=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'by': u['display_name']})

    # ------------------------------------------------------------ новости

    NEWS_FIELDS = ('id', 'author_id', 'title', 'tag', 'body', 'created')

    def api_news(self, conn, qs, m, body):
        rows = conn.execute(
            'SELECT n.*, u.display_name author FROM news n '
            'JOIN users u ON u.id=n.author_id ORDER BY n.created DESC LIMIT 100').fetchall()
        out = []
        for r in rows:
            o = dict((k, r[k]) for k in self.NEWS_FIELDS)
            o['author'] = r['author']
            o['mine'] = False
            out.append(o)
        u = self.current_user(conn)
        if u:
            for o in out:
                o['mine'] = o['author_id'] == u['id']
        self.send_json({'news': out})

    def api_news_create(self, conn, qs, m, body):
        u = self.require_user(conn)
        title = str(body.get('title') or '').strip()[:140]
        tag = str(body.get('tag') or '').strip()[:40] or None
        text = str(body.get('body') or '').strip()[:20000]
        if not title or not text:
            raise ApiError(400, 'Заголовок и текст обязательны')
        cur = conn.execute(
            'INSERT INTO news(author_id, title, tag, body, created) VALUES(?,?,?,?,?)',
            (u['id'], title, tag, text, time.time()))
        conn.commit()
        r = conn.execute('SELECT * FROM news WHERE id=?', (cur.lastrowid,)).fetchone()
        created = dict((k, r[k]) for k in self.NEWS_FIELDS)
        created['author'] = u['display_name']
        self.send_json(created, status=201)

    def api_news_delete(self, conn, qs, m, body):
        u = self.require_user(conn)
        r = conn.execute('SELECT * FROM news WHERE id=?', (int(m.group(1)),)).fetchone()
        if not r:
            raise ApiError(404, 'Новость не найдена')
        if r['author_id'] != u['id'] and not u['is_gm']:
            raise ApiError(403, 'Можно удалять только свои посты')
        conn.execute('DELETE FROM news WHERE id=?', (r['id'],))
        conn.commit()
        self.send_json({'ok': True})

    # ------------------------------------------------------------ доска заказов

    def job_payload(self, r, conn, user):
        n = conn.execute('SELECT COUNT(*) n FROM job_signups WHERE job_id=?',
                         (r['id'],)).fetchone()['n']
        p = {k: r[k] for k in ('id', 'author_id', 'title', 'when_text', 'system',
                               'description', 'slots', 'status', 'created')}
        p['author'] = r['author']
        p['signups'] = n
        p['mine'] = bool(user and user['id'] == r['author_id'])
        p['joined'] = bool(user and conn.execute(
            'SELECT 1 FROM job_signups WHERE job_id=? AND user_id=?',
            (r['id'], user['id'])).fetchone())
        return p

    def api_jobs(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute(
            'SELECT j.*, u.display_name author FROM jobs j '
            'JOIN users u ON u.id=j.author_id ORDER BY j.created DESC LIMIT 100').fetchall()
        self.send_json({'jobs': [self.job_payload(r, conn, user) for r in rows]})

    def api_jobs_create(self, conn, qs, m, body):
        u = self.require_gm(conn)
        title = str(body.get('title') or '').strip()[:140]
        when_text = str(body.get('when_text') or '').strip()[:80] or None
        system = str(body.get('system') or 'Cyberpunk RED').strip()[:40]
        desc = str(body.get('description') or '').strip()[:8000]
        slots = max(0, min(20, int(body.get('slots') or 0)))
        if not title or not desc:
            raise ApiError(400, 'Название и описание обязательны')
        cur = conn.execute(
            'INSERT INTO jobs(author_id, title, when_text, system, description, slots, '
            'status, created) VALUES(?,?,?,?,?,?,?,?)',
            (u['id'], title, when_text, system, desc, slots, 'open', time.time()))
        conn.commit()
        r = conn.execute(
            'SELECT j.*, u.display_name author FROM jobs j JOIN users u ON u.id=j.author_id '
            'WHERE j.id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.job_payload(r, conn, u), status=201)

    def api_job_detail(self, conn, qs, m, body):
        user = self.current_user(conn)
        r = conn.execute(
            'SELECT j.*, u.display_name author FROM jobs j JOIN users u ON u.id=j.author_id '
            'WHERE j.id=?', (int(m.group(1)),)).fetchone()
        if not r:
            raise ApiError(404, 'Заказ не найден')
        p = self.job_payload(r, conn, user)
        signups = conn.execute(
            'SELECT s.*, u.display_name user FROM job_signups s '
            'JOIN users u ON u.id=s.user_id WHERE s.job_id=? ORDER BY s.created',
            (r['id'],)).fetchall()
        p['signups_list'] = [
            {'id': s['id'], 'user': s['user'], 'user_id': s['user_id'],
             'char_name': s['char_name'], 'note': s['note'], 'created': s['created'],
             'mine': bool(user and user['id'] == s['user_id'])}
            for s in signups]
        self.send_json(p)

    def api_job_join(self, conn, qs, m, body):
        u = self.require_user(conn)
        r = conn.execute('SELECT * FROM jobs WHERE id=?', (int(m.group(1)),)).fetchone()
        if not r:
            raise ApiError(404, 'Заказ не найден')
        if r['status'] != 'open':
            raise ApiError(400, 'Заказ закрыт')
        if r['author_id'] == u['id']:
            raise ApiError(400, 'Нельзя записаться на свой заказ')
        n = conn.execute('SELECT COUNT(*) n FROM job_signups WHERE job_id=?',
                         (r['id'],)).fetchone()['n']
        if r['slots'] and n >= r['slots']:
            raise ApiError(400, 'Все слоты заняты')
        char_name = str(body.get('char_name') or '').strip()[:60] or None
        note = str(body.get('note') or '').strip()[:500] or None
        try:
            conn.execute(
                'INSERT INTO job_signups(job_id, user_id, char_name, note, created) '
                'VALUES(?,?,?,?,?)', (r['id'], u['id'], char_name, note, time.time()))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ApiError(409, 'Вы уже записаны')
        self.send_json({'ok': True})

    def api_job_leave(self, conn, qs, m, body):
        u = self.require_user(conn)
        conn.execute('DELETE FROM job_signups WHERE job_id=? AND user_id=?',
                     (int(m.group(1)), u['id']))
        conn.commit()
        self.send_json({'ok': True})

    def api_job_status(self, conn, qs, m, body):
        u = self.require_user(conn)
        r = conn.execute('SELECT * FROM jobs WHERE id=?', (int(m.group(1)),)).fetchone()
        if not r:
            raise ApiError(404, 'Заказ не найден')
        if r['author_id'] != u['id'] and not u['is_gm']:
            raise ApiError(403, 'Только автор может менять статус')
        status = body.get('status')
        if status not in ('open', 'closed'):
            raise ApiError(400, 'Статус: open/closed')
        conn.execute('UPDATE jobs SET status=? WHERE id=?', (status, r['id']))
        conn.commit()
        self.send_json({'ok': True})

    def api_job_delete(self, conn, qs, m, body):
        u = self.require_user(conn)
        r = conn.execute('SELECT * FROM jobs WHERE id=?', (int(m.group(1)),)).fetchone()
        if not r:
            raise ApiError(404, 'Заказ не найден')
        if r['author_id'] != u['id'] and not u['is_gm']:
            raise ApiError(403, 'Только автор может удалить заказ')
        conn.execute('DELETE FROM job_signups WHERE job_id=?', (r['id'],))
        conn.execute('DELETE FROM jobs WHERE id=?', (r['id'],))
        conn.commit()
        self.send_json({'ok': True})


def rx(p):
    return re.compile('^' + p + '$')


ROUTES = [
    ('POST', rx(r'/api/register'), Handler.api_register),
    ('POST', rx(r'/api/login'), Handler.api_login),
    ('POST', rx(r'/api/logout'), Handler.api_logout),
    ('GET', rx(r'/api/me'), Handler.api_me),
    ('POST', rx(r'/api/profile'), Handler.api_profile),
    ('GET', rx(r'/api/meta'), Handler.api_meta),
    ('GET', rx(r'/api/stats'), Handler.api_stats),
    ('GET', rx(r'/api/items'), Handler.api_items),
    ('GET', rx(r'/api/items/([\w-]+)'), Handler.api_item),
    ('GET', rx(r'/api/nightmarket'), Handler.api_nightmarket),
    ('GET', rx(r'/api/characters'), Handler.api_my_characters),
    ('POST', rx(r'/api/characters'), Handler.api_create_character),
    ('GET', rx(r'/api/characters/(\d+)'), Handler.api_get_character),
    ('PUT', rx(r'/api/characters/(\d+)'), Handler.api_save_character),
    ('DELETE', rx(r'/api/characters/(\d+)'), Handler.api_delete_character),
    ('GET', rx(r'/api/roster'), Handler.api_roster),
    ('POST', rx(r'/api/buy'), Handler.api_buy),
    ('POST', rx(r'/api/sell'), Handler.api_sell),
    ('POST', rx(r'/api/payroll'), Handler.api_payroll),
    ('GET', rx(r'/api/news'), Handler.api_news),
    ('POST', rx(r'/api/news'), Handler.api_news_create),
    ('DELETE', rx(r'/api/news/(\d+)'), Handler.api_news_delete),
    ('GET', rx(r'/api/jobs'), Handler.api_jobs),
    ('POST', rx(r'/api/jobs'), Handler.api_jobs_create),
    ('GET', rx(r'/api/jobs/(\d+)'), Handler.api_job_detail),
    ('POST', rx(r'/api/jobs/(\d+)/join'), Handler.api_job_join),
    ('POST', rx(r'/api/jobs/(\d+)/leave'), Handler.api_job_leave),
    ('POST', rx(r'/api/jobs/(\d+)/status'), Handler.api_job_status),
    ('DELETE', rx(r'/api/jobs/(\d+)'), Handler.api_job_delete),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=8000)
    args = ap.parse_args()
    load_catalog()
    init_db()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'CBPR Helper слушает http://{args.host}:{args.port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
