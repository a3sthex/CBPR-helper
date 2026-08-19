#!/usr/bin/env python3
"""CBPR Helper — онлайн-помощник для кампаний по Cyberpunk RED.

Только стандартная библиотека Python. Запуск:
    python3 app/server.py [--port 8000]
"""
import argparse
import base64
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
DB_PATH = os.path.abspath(os.path.expanduser(
    os.environ.get('CBPR_DB_PATH') or os.path.join(DATA_DIR, 'cbpr.db')))
STATIC_DIR = os.path.join(BASE, 'static')
ITEMS_PATH = os.path.join(DATA_DIR, 'items.json')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')

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
    'Rockerboy': 'Charismatic Impact',
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
ROLE_DESC_EN = {
    'Rockerboy': 'Rock-and-roll rebels who use performance, art, and rhetoric to fight authority.',
    'Solo': 'Assassins, bodyguards, killers, and mercenaries in a lawless new world.',
    'Netrunner': 'Cybernetic master hackers who steal secrets and burn minds in the NET.',
    'Tech': 'Renegade mechanics and inventors of advanced technology who keep the Dark Future moving.',
    'Medtech': 'Unlicensed street doctors and ripperdocs equally skilled at repairing flesh and chrome.',
    'Media': 'Reporters, media stars, and influencers who risk everything for truth or fame.',
    'Exec': 'Corporate power players and business raiders serving the Megacorporations.',
    'Lawman': 'Officers who patrol hostile streets and highways where order is often brutal.',
    'Fixer': 'Dealmakers, organizers, and information brokers of the Night Markets.',
    'Nomad': 'Transport experts, road warriors, pirates, and smugglers who keep the world connected.',
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
SPECIALIZED_SKILLS = {'Language', 'Local Expert', 'Martial Arts', 'Science', 'Play Instrument'}
START_CASH_GEAR = 2550    # стартовые €$ на оружие/броню/снаряжение/хром
START_CASH_FASHION = 800  # отдельный бюджет на Fashion и Fashionware
CULTURAL_LANGUAGES = {
    'Северная Америка': {'Английский', 'Испанский', 'Навахо', 'Кри', 'Креольский', 'Французский'},
    'Латинская Америка': {'Испанский', 'Португальский', 'Гуарани', 'Кечуа', 'Майя', 'Науатль', 'Английский', 'Креольский'},
    'Южная / Центральная Америка': {'Испанский', 'Португальский', 'Гуарани', 'Кечуа', 'Майя', 'Науатль'},
    'Центральная Америка': {'Испанский', 'Английский', 'Креольский', 'Майя', 'Науатль'},
    'Южная Америка': {'Испанский', 'Португальский', 'Гуарани', 'Кечуа'},
    'Западная Европа': {'Английский', 'Французский', 'Немецкий', 'Итальянский', 'Испанский', 'Норвежский'},
    'Восточная Европа': {'Русский', 'Украинский', 'Польский', 'Финский', 'Румынский'},
    'Ближний Восток / Северная Африка': {'Арабский', 'Иврит', 'Персидский', 'Турецкий', 'Берберский'},
    'Африка южнее Сахары': {'Суахили', 'Хауса', 'Лингала', 'Зулу', 'Эве', 'Амхарский'},
    'Южная Азия': {'Хинди', 'Бенгальский', 'Урду', 'Тамильский', 'Непальский'},
    'Юго-Восточная Азия': {'Вьетнамский', 'Тайский', 'Индонезийский', 'Тагальский', 'Кхмерский'},
    'Восточная Азия': {'Китайский', 'Японский', 'Корейский', 'Монгольский'},
    'Океания / Тихоокеанские острова': {'Английский', 'Маори', 'Гавайский', 'Самоанский', 'Таитянский'},
}

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

WOUND_STATES_EN = [
    ['Mortally Wounded', 'HP < 1', '−4 to all Actions and −6 MOVE (minimum 1). Make a Death Save at the start of every Turn. Taking damage causes another Critical Injury and adds 1 to the Death Save Penalty.', 'DV15 → 1 HP and unconscious for 1 minute'],
    ['Seriously Wounded', 'HP ≤ half maximum, rounded up', '−2 to all Actions.', 'DV13'],
    ['Lightly Wounded', 'HP below maximum', 'No effect.', 'DV10'],
    ['Dead', 'Failed Death Save', 'You are dead.', '—'],
]
CRIT_BODY_EN = [
    [2, 'Dismembered Arm', 'The arm is gone. Drop everything held in that hand. +1 Base Death Save Penalty.', '—', 'Surgery DV17'],
    [3, 'Dismembered Hand', 'The hand is gone. Drop everything held in it. +1 Base Death Save Penalty.', '—', 'Surgery DV17'],
    [4, 'Collapsed Lung', '−2 MOVE (minimum 1). +1 Base Death Save Penalty.', 'Paramedic DV15', 'Surgery DV15'],
    [5, 'Broken Ribs', 'Moving more than 4 m on foot causes the Critical Injury bonus damage again at the end of the Turn.', 'Paramedic DV13', 'Paramedic DV15 or Surgery DV13'],
    [6, 'Broken Arm', 'The broken arm cannot be used. Drop everything held in that hand.', 'Paramedic DV13', 'Paramedic DV15 or Surgery DV13'],
    [7, 'Foreign Object', 'Moving more than 4 m on foot causes the Critical Injury bonus damage again at the end of the Turn.', 'First Aid or Paramedic DV13', 'Quick Fix is permanent'],
    [8, 'Broken Leg', '−4 MOVE (minimum 1).', 'Paramedic DV13', 'Paramedic DV15 or Surgery DV13'],
    [9, 'Torn Muscle', '−2 to melee attacks.', 'First Aid or Paramedic DV13', 'Quick Fix is permanent'],
    [10, 'Spinal Injury', 'You cannot take an Action on your next Turn, but can still Move. +1 Base Death Save Penalty.', 'Paramedic DV15', 'Surgery DV15'],
    [11, 'Crushed Fingers', '−4 to all Actions made with that hand.', 'Paramedic DV13', 'Surgery DV15'],
    [12, 'Dismembered Leg', '−6 MOVE (minimum 1). You cannot dodge. +1 Base Death Save Penalty.', '—', 'Surgery DV17'],
]
CRIT_HEAD_EN = [
    [2, 'Lost Eye', 'The eye is gone. −4 to ranged attacks and sight-based Perception. +1 Base Death Save Penalty.', '—', 'Surgery DV17'],
    [3, 'Brain Injury', '−2 to all Actions. +1 Base Death Save Penalty.', '—', 'Surgery DV17'],
    [4, 'Damaged Eye', '−2 to ranged attacks and sight-based Perception.', 'Paramedic DV15', 'Surgery DV13'],
    [5, 'Concussion', '−2 to all Actions.', 'First Aid or Paramedic DV13', 'Quick Fix is permanent'],
    [6, 'Broken Jaw', '−4 to all speech-related Actions.', 'Paramedic DV13', 'Paramedic or Surgery DV13'],
    [7, 'Foreign Object', 'Moving more than 4 m on foot causes the Critical Injury bonus damage again at the end of the Turn.', 'First Aid or Paramedic DV13', 'Quick Fix is permanent'],
    [8, 'Whiplash', '+1 Base Death Save Penalty.', 'Paramedic DV13', 'Paramedic or Surgery DV13'],
    [9, 'Cracked Skull', 'Aimed Shots to the head use a ×3 modifier instead of ×2. +1 Base Death Save Penalty.', 'Paramedic DV15', 'Paramedic or Surgery DV15'],
    [10, 'Damaged Ear', 'After moving more than 4 m, you cannot Move on your next Turn. −2 to hearing-based Perception.', 'Paramedic DV13', 'Surgery DV13'],
    [11, 'Crushed Windpipe', 'You cannot speak. +1 Base Death Save Penalty.', '—', 'Surgery DV15'],
    [12, 'Lost Ear', 'The ear is gone. After moving more than 4 m, you cannot Move on your next Turn. −4 to hearing-based Perception. +1 Base Death Save Penalty.', '—', 'Surgery DV17'],
]


def _armor_penalties(piece):
    """Возвращает раздельные штрафы брони, включая старый формат данных."""
    if not isinstance(piece, dict):
        return {}
    penalties = piece.get('penalties')
    if isinstance(penalties, dict):
        return {stat: _num(penalties.get(stat)) or 0 for stat in ('REF', 'DEX', 'MOVE')}
    legacy = _num(piece.get('penalty')) or 0
    return {stat: legacy for stat in ('REF', 'DEX', 'MOVE')} if legacy else {}


def derive(char):
    """Производные показатели листа персонажа по правилам CP:R/CEMK."""
    st = char.get('stats') or {}
    out = {}
    body = _num(st.get('BODY'))
    will = _num(st.get('WILL'))
    if body is not None and will is not None:
        hp_max = 10 + 5 * ((body + will + 1) // 2)
        out['hp_max'] = hp_max
        out['seriously_wounded'] = (hp_max + 1) // 2
        out['death_save'] = body

    # HL уменьшает текущую Humanity. Максимум отдельно режется на 2 за
    # обычный хром и на 4 за Borgware. Стартовый Neuroport из CEMK не
    # вызывает ни одного из эффектов.
    hl_total = 0
    hum_cut = 0
    for chrome in char.get('cyberware') or []:
        if chrome.get('humanity_exempt') and chrome.get('key') == 'creation-neuroport':
            continue
        hl_total += _num(chrome.get('hl')) or 0
        ctype = str(chrome.get('type') or '').lower()
        if 'borgware' in ctype:
            hum_cut += 4
        elif 'fashionware' not in ctype:
            hum_cut += 2
    emp_base = _num(st.get('EMP'))
    if emp_base is not None:
        humanity_start = emp_base * 10
        hum_max = humanity_start - hum_cut
        hum_cur = _num(char.get('humanity_cur'))
        if hum_cur is None:
            hum_cur = humanity_start - hl_total
        hum_cur = min(hum_cur, hum_max)
        out['humanity_max'] = hum_max
        out['humanity_cur'] = hum_cur
        out['emp_cur'] = max(0, hum_cur // 10)
        out['hl_total'] = hl_total
        out['hum_cut'] = hum_cut

    # На каждой локации работает только наибольший SP. Штраф применяется
    # один раз — самый строгий отдельно для REF, DEX и MOVE.
    armor = char.get('armor') or {}
    body_pieces = [armor.get('body'), armor.get('body_outer'), armor.get('body_inner')]
    head_pieces = [armor.get('head')]
    body_pieces = [a for a in body_pieces if isinstance(a, dict)]
    head_pieces = [a for a in head_pieces if isinstance(a, dict)]
    body_sps = [_num(a.get('sp')) for a in body_pieces]
    head_sps = [_num(a.get('sp')) for a in head_pieces]
    body_sps = [sp for sp in body_sps if sp is not None]
    head_sps = [sp for sp in head_sps if sp is not None]
    if body_sps:
        out['sp_body'] = max(body_sps)
    if head_sps:
        out['sp_head'] = max(head_sps)
    penalties = {'REF': 0, 'DEX': 0, 'MOVE': 0}
    for piece in body_pieces + head_pieces:
        for stat, value in _armor_penalties(piece).items():
            penalties[stat] = min(penalties[stat], value)
    out['armor_penalties'] = penalties
    out['armor_penalty'] = min(penalties.values())
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
  account_role TEXT NOT NULL DEFAULT 'player',
  show_display_name INTEGER NOT NULL DEFAULT 0,
  vk_user_id TEXT,
  vk_linked_at REAL,
  notification_prefs TEXT NOT NULL DEFAULT '{}',
  theme_json TEXT NOT NULL DEFAULT '{}',
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
CREATE TABLE IF NOT EXISTS media(
  id TEXT PRIMARY KEY,
  owner_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  mime TEXT NOT NULL,
  filename TEXT NOT NULL,
  size INTEGER NOT NULL,
  width INTEGER NOT NULL,
  height INTEGER NOT NULL,
  attached_type TEXT,
  attached_id INTEGER,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS ip_ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  actor_id INTEGER NOT NULL,
  amount INTEGER NOT NULL,
  balance_before INTEGER NOT NULL,
  balance_after INTEGER NOT NULL,
  kind TEXT NOT NULL,
  subject TEXT,
  reason TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS schema_migrations(
  version INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  applied REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS account_role_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_user_id INTEGER NOT NULL,
  actor_user_id INTEGER,
  role_before TEXT NOT NULL,
  role_after TEXT NOT NULL,
  reason TEXT NOT NULL,
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_char_owner ON characters(owner_id);
CREATE INDEX IF NOT EXISTS idx_news_created ON news(created);
CREATE INDEX IF NOT EXISTS idx_media_owner ON media(owner_id);
CREATE INDEX IF NOT EXISTS idx_media_attached ON media(attached_type, attached_id);
CREATE INDEX IF NOT EXISTS idx_ip_character ON ip_ledger(character_id, created);
CREATE INDEX IF NOT EXISTS idx_role_audit_target ON account_role_audit(target_user_id, created);
"""

ACCOUNT_ROLES = {'player', 'gm', 'admin'}
MIGRATION_ACCOUNT_ROLES = 1
DB_BACKUP_LIMIT = 5


def _row_value(row, key, default=None):
    if row is None:
        return default
    try:
        return row[key] if key in row.keys() else default
    except (AttributeError, KeyError, TypeError):
        return row.get(key, default) if isinstance(row, dict) else default


def user_account_role(user):
    role = str(_row_value(user, 'account_role', '') or '').lower()
    if role in ACCOUNT_ROLES:
        return role
    return 'gm' if bool(_row_value(user, 'is_gm', 0)) else 'player'


def user_is_gm(user):
    return user_account_role(user) in ('gm', 'admin')


def user_is_admin(user):
    return user_account_role(user) == 'admin'


def configured_admin_usernames():
    raw = os.environ.get('CBPR_ADMIN_USERS', '')
    return {part.strip().lower() for part in raw.split(',') if part.strip()}


def backup_database(conn, label):
    """Create a bounded SQLite backup before a destructive-capable schema migration."""
    if not os.path.isfile(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        return None
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    path = f'{DB_PATH}.backup-{label}-{stamp}'
    target = sqlite3.connect(path)
    try:
        conn.backup(target)
    finally:
        target.close()
    prefix = os.path.basename(DB_PATH) + '.backup-'
    backups = sorted(
        (os.path.join(os.path.dirname(DB_PATH), name)
         for name in os.listdir(os.path.dirname(DB_PATH) or '.')
         if name.startswith(prefix)),
        key=os.path.getmtime,
        reverse=True,
    )
    for stale in backups[DB_BACKUP_LIMIT:]:
        try:
            os.remove(stale)
        except FileNotFoundError:
            pass
    return path


def apply_schema_migrations(conn, make_backup=True):
    """Idempotently upgrade legacy databases without resetting campaign data."""
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations('
                 'version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied REAL NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS account_role_audit('
                 'id INTEGER PRIMARY KEY AUTOINCREMENT, target_user_id INTEGER NOT NULL, '
                 'actor_user_id INTEGER, role_before TEXT NOT NULL, role_after TEXT NOT NULL, '
                 'reason TEXT NOT NULL, created REAL NOT NULL)')
    applied = {row['version'] for row in conn.execute('SELECT version FROM schema_migrations')}
    if MIGRATION_ACCOUNT_ROLES not in applied:
        if make_backup:
            backup_database(conn, 'roles-v1')
        columns = {row['name'] for row in conn.execute('PRAGMA table_info(users)')}
        additions = {
            'account_role': "TEXT NOT NULL DEFAULT 'player'",
            'show_display_name': 'INTEGER NOT NULL DEFAULT 0',
            'vk_user_id': 'TEXT',
            'vk_linked_at': 'REAL',
            'notification_prefs': "TEXT NOT NULL DEFAULT '{}'",
            'theme_json': "TEXT NOT NULL DEFAULT '{}'",
        }
        for name, definition in additions.items():
            if name not in columns:
                conn.execute(f'ALTER TABLE users ADD COLUMN {name} {definition}')
        conn.execute("UPDATE users SET account_role='gm' WHERE is_gm=1 "
                     "AND account_role!='admin'")
        conn.execute("UPDATE users SET account_role='player' "
                     "WHERE account_role IS NULL OR account_role NOT IN ('player','gm','admin')")
        conn.execute(
            'INSERT INTO schema_migrations(version,name,applied) VALUES(?,?,?)',
            (MIGRATION_ACCOUNT_ROLES, 'account roles and privacy foundation', time.time()))
    conn.execute("UPDATE users SET is_gm=CASE WHEN account_role IN ('gm','admin') "
                 "THEN 1 ELSE 0 END")
    conn.execute('CREATE INDEX IF NOT EXISTS idx_role_audit_target '
                 'ON account_role_audit(target_user_id, created)')
    conn.commit()


def apply_admin_bootstrap(conn):
    """Promote only explicitly configured existing users; never auto-promote registration."""
    usernames = configured_admin_usernames()
    if not usernames:
        return []
    promoted = []
    for username in sorted(usernames):
        row = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not row:
            continue
        before = user_account_role(row)
        if before == 'admin':
            continue
        conn.execute("UPDATE users SET account_role='admin', is_gm=1 WHERE id=?", (row['id'],))
        conn.execute(
            'INSERT INTO account_role_audit(target_user_id,actor_user_id,role_before,'
            'role_after,reason,created) VALUES(?,NULL,?,?,?,?)',
            (row['id'], before, 'admin', 'CBPR_ADMIN_USERS bootstrap', time.time()))
        promoted.append(username)
    conn.commit()
    return promoted


def assign_account_role(conn, actor, target_user_id, role, reason='Admin role assignment'):
    """Change access with last-Admin protection and an append-only audit record."""
    if not user_is_admin(actor):
        raise ApiError(403, 'Только для администраторов NC//NET')
    target = conn.execute('SELECT * FROM users WHERE id=?', (int(target_user_id),)).fetchone()
    if not target:
        raise ApiError(404, 'Пользователь не найден')
    role = str(role or '').lower()
    if role not in ACCOUNT_ROLES:
        raise ApiError(400, 'Недопустимая роль аккаунта')
    before = user_account_role(target)
    if before == role:
        return target
    if before == 'admin' and role != 'admin':
        admins = conn.execute("SELECT COUNT(*) n FROM users WHERE account_role='admin'").fetchone()['n']
        if admins <= 1:
            raise ApiError(409, 'Нельзя снять роль с последнего администратора')
    reason = str(reason or 'Admin role assignment').strip()[:500]
    conn.execute('UPDATE users SET account_role=?, is_gm=? WHERE id=?',
                 (role, 1 if role in ('gm', 'admin') else 0, target['id']))
    conn.execute(
        'INSERT INTO account_role_audit(target_user_id,actor_user_id,role_before,'
        'role_after,reason,created) VALUES(?,?,?,?,?,?)',
        (target['id'], actor['id'], before, role, reason, time.time()))
    conn.commit()
    return conn.execute('SELECT * FROM users WHERE id=?', (target['id'],)).fetchone()


def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    conn = db()
    had_users_table = bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone())
    conn.executescript(SCHEMA)
    apply_schema_migrations(conn, make_backup=had_users_table)
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    stale = conn.execute('SELECT * FROM media WHERE attached_type IS NULL AND created < ?', (time.time() - 7 * 86400,)).fetchall()
    for media in stale:
        try: os.remove(os.path.join(UPLOAD_DIR, media['filename']))
        except FileNotFoundError: pass
    conn.execute('DELETE FROM media WHERE attached_type IS NULL AND created < ?', (time.time() - 7 * 86400,))
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
    promoted = apply_admin_bootstrap(conn)
    if promoted:
        print('NC//NET Admin bootstrap: ' + ', '.join(promoted))
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
    out['first_name'] = str(out.get('first_name') or '').strip()[:60]
    out['last_name'] = str(out.get('last_name') or '').strip()[:60]
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
    if out.get('skill_pools') is not None and not isinstance(out.get('skill_pools'), dict):
        raise ApiError(400, 'skill_pools должен быть объектом')
    specializations = out.get('skill_specializations')
    if specializations is not None and (not isinstance(specializations, list) or len(specializations) > 100):
        raise ApiError(400, 'skill_specializations должен быть списком до 100 записей')
    if not isinstance(out.get('armor') or {}, dict):
        out['armor'] = {}
    try:
        out['cash'] = max(0.0, min(9_999_999.0, float(out.get('cash') or 0)))
    except (TypeError, ValueError):
        raise ApiError(400, 'cash должен быть числом')
    out['portrait_media_id'] = str(out.get('portrait_media_id') or '')[:64]
    progressed = ensure_progression(out)
    if any(role.get('role_lifepath') for role in progressed.get('roles', []) if not role.get('primary')):
        raise ApiError(400, 'Role-Based Lifepath разрешён только primary Role')
    return progressed


def skill_base(name):
    name = str(name or '')
    for known in SKILL_BY_NAME:
        if name == known or name.startswith(known + ' ('):
            return known
    return None


def creation_skill_cost(data):
    """Стоимость навыков; в новой схеме специализации оплачиваются parent-pool."""
    skills = data.get('skills') or {}
    pools = data.get('skill_pools')
    native = str(data.get('native_language') or '').strip()
    native_key = f'Language ({native})' if native else None
    total = 0

    if pools is not None:
        if set(pools) - SPECIALIZED_SKILLS:
            raise ApiError(400, 'skill_pools содержит неизвестный специализированный навык')
        for base in SPECIALIZED_SKILLS:
            level = _num(pools.get(base)) or 0
            if level < 0 or level > SKILL_POINTS:
                raise ApiError(400, f'{base}: некорректный parent-pool')
            total += level * (2 if SKILL_BY_NAME[base][3] else 1)

    allocated = {base: 0 for base in SPECIALIZED_SKILLS}
    for name, raw_level in skills.items():
        base = skill_base(name)
        if not base:
            raise ApiError(400, f'Неизвестный навык: {name}')
        if base in SPECIALIZED_SKILLS and name == base:
            raise ApiError(400, f'{base}: укажите конкретную специализацию в скобках')
        level = _num(raw_level)
        if level is None or level < 0 or level > SKILL_MAX_CREATION:
            raise ApiError(400, f'{name}: при создании допустим уровень 0–{SKILL_MAX_CREATION}')
        if base in SPECIALIZED_SKILLS:
            free_native = name == native_key and base == 'Language'
            allocated[base] += max(0, level - 4) if free_native else level
            if pools is None:
                total += level * (2 if SKILL_BY_NAME[base][3] else 1)
                if free_native:
                    total -= min(4, level)
        else:
            total += level * (2 if SKILL_BY_NAME[base][3] else 1)

    if pools is not None:
        for base in SPECIALIZED_SKILLS:
            pool = _num(pools.get(base)) or 0
            if allocated[base] > pool:
                raise ApiError(400, f'{base}: распределено {allocated[base]} при parent-pool {pool}')
    return total


def validate_cyberware_requirements(data):
    """Проверяет явные фундаментальные требования из описаний Data Pool."""
    chrome = [c for c in data.get('cyberware') or []
              if not (c.get('creation_free') and c.get('key') == 'creation-neuroport')]
    items = [item_by_id(str(c.get('key') or '')) for c in chrome]
    items = [item for item in items if item]
    names = [item['name'].lower() for item in items]
    inventory_names = [str(entry.get('name') or '').lower() for entry in data.get('inventory') or []]
    has_port = any(c.get('key') == 'creation-neuroport' for c in data.get('cyberware') or []) or 'neuroport' in names
    foundations = {
        'cybereye': {'cybereye', 'sponsored cybereye'},
        'cyberarm': {'cyberarm', 'neo-soviet cyberarm'},
        'cyberleg': {'cyberleg', 'romanova cyberlegs'},
        'cyberaudio suite': {'cyberaudio suite', 'discount cyberaudio suite'},
        'chipware socket': {'chipware socket', 'budget chipware socket'},
    }
    count_foundation = lambda kind: sum(name in foundations[kind] for name in names)
    body = _num((data.get('stats') or {}).get('BODY')) or 0

    for item in items:
        desc = str(item.get('desc') or '').lower().replace('\n', ' ')
        missing = None
        if 'requires a modular finger cyberhand' in desc and 'modular finger cyberhand' not in names:
            missing = 'Modular Finger Cyberhand'
        elif ('requires a cyberaudio suite' in desc or 'cyberaudio option' in desc) and not count_foundation('cyberaudio suite'):
            missing = 'Cyberaudio Suite'
        elif 'cybereye option' in desc and not count_foundation('cybereye'):
            missing = 'Cybereye'
        elif ('cyberarm option' in desc and 'can be installed as the only piece of cyberware in a meat arm' not in desc
              and not count_foundation('cyberarm')):
            missing = 'Cyberarm'
        elif 'cyberleg option' in desc and not count_foundation('cyberleg'):
            missing = 'Cyberleg'
        elif ('cyberlimb option' in desc and not (count_foundation('cyberarm') or count_foundation('cyberleg'))):
            missing = 'Cyberarm или Cyberleg'
        elif ('neuralware option' in desc and not (has_port or 'neural link' in names)):
            missing = 'Neural Link или Neuroport'
        elif ('requires chipware socket' in desc or 'requires a chipware socket' in desc) and not count_foundation('chipware socket'):
            missing = 'Chipware Socket'
        elif ('requires neural link' in desc or 'requires interface plugs and neural link' in desc) and not (
                has_port or 'neural link' in names):
            missing = 'Neural Link или Neuroport'
        elif 'requires neuroport cyberdeck port' in desc and 'neuroport cyberdeck port' not in names:
            missing = 'Neuroport Cyberdeck Port'
        elif 'requires neuroport' in desc and not has_port:
            missing = 'Neuroport'
        elif 'requires two cybereyes' in desc and count_foundation('cybereye') < 2:
            missing = 'две Cybereye'
        elif 'requires a cybereye' in desc and not count_foundation('cybereye'):
            missing = 'Cybereye'
        elif 'requires two cyberlegs' in desc and count_foundation('cyberleg') < 2:
            missing = 'две Cyberleg'
        elif 'requires a cyberarm or cyberleg' in desc and not (
                count_foundation('cyberarm') or count_foundation('cyberleg')):
            missing = 'Cyberarm или Cyberleg'
        elif 'requires a cyberarm' in desc and not count_foundation('cyberarm'):
            missing = 'Cyberarm'
        elif 'requires biomonitor' in desc and not (has_port or 'biomonitor' in names):
            missing = 'Biomonitor или Neuroport'
        elif 'requires skinweave or subdermal armor' in desc and not any(
                name in names for name in ('skinweave', 'subdermal armor')):
            missing = 'Skinweave или Subdermal Armor'
        elif 'requires a scrambler/descrambler' in desc and not any(
                'scrambler/descrambler' in name for name in inventory_names):
            missing = 'Scrambler/Descrambler'
        elif 'requires chyron' in desc and not (has_port or 'chyron' in names):
            missing = 'Chyron или Neuroport'
        body_match = re.search(r'requires body\s+(\d+)', desc)
        if body_match and body < int(body_match.group(1)):
            missing = f'BODY {body_match.group(1)}'
        lace_match = re.search(r'requires body\s+\d+\s+and\s+(?:two|2|3)\s+(?:installations of )?grafted muscle', desc)
        if lace_match:
            needed = 3 if ' and 3 ' in lace_match.group(0) else 2
            if names.count('grafted muscle & bone lace') < needed:
                missing = f'{needed} установки Grafted Muscle & Bone Lace'
        if missing:
            raise ApiError(400, f'{item["name"]} требует: {missing}')


def validate_cyberware_slots(data):
    """Проверяет host assignment, Option Slots и явные запреты дубликатов."""
    raw = data.get('cyberware') or []
    hosts = {}
    catalog_items = []
    for index, entry in enumerate(raw):
        if entry.get('creation_free') and entry.get('key') == 'creation-neuroport':
            iid = str(entry.get('instance_id') or 'creation-neuroport')
            hosts[iid] = {'name': 'Neuroport', 'total': 5}
            catalog_items.append((entry, None))
            continue
        item = item_by_id(str(entry.get('key') or ''))
        catalog_items.append((entry, item))
        if not item:
            continue
        capacity = item.get('capacity') or {}
        total = _num(capacity.get('slots_total')) or 0
        iid = str(entry.get('instance_id') or f'{entry.get("key")}:{index}')
        if total:
            hosts[iid] = {'name': item['name'], 'total': total}

    accepted = {
        'Cyberarm': {'cyberarm', 'neo-soviet cyberarm'},
        'Cyberleg': {'cyberleg', 'romanova cyberlegs'},
        'Cybereye': {'cybereye', 'sponsored cybereye'},
        'Cyberaudio Suite': {'cyberaudio suite', 'discount cyberaudio suite'},
        'Neural Link or Neuroport': {'neural link', 'neuroport'},
    }
    used = {iid: 0 for iid in hosts}
    unique_counts = {}
    for entry, item in catalog_items:
        if not item:
            continue
        capacity = item.get('capacity') or {}
        if capacity.get('unique'):
            unique_counts[item['id']] = unique_counts.get(item['id'], 0) + 1
            if unique_counts[item['id']] > 1:
                raise ApiError(400, f'{item["name"]}: допустима только одна установка')
        expected = capacity.get('host')
        slots = _num(capacity.get('slots_used')) or 0
        if not expected:
            continue
        host_ids = entry.get('host_instances') or ([entry.get('host_instance')] if entry.get('host_instance') else [])
        host_ids = [str(value) for value in host_ids if value]
        required = _num(capacity.get('hosts_required')) or 1
        if len(set(host_ids)) != required or any(host_id not in hosts for host_id in host_ids):
            raise ApiError(400, f'{item["name"]}: требуется совместимых hosts: {required}')
        for host_id in host_ids:
            if hosts[host_id]['name'].lower() not in accepted.get(expected, set()):
                raise ApiError(400, f'{item["name"]}: несовместимый host {hosts[host_id]["name"]}')
            used[host_id] += slots
    for iid, amount in used.items():
        if amount > hosts[iid]['total']:
            raise ApiError(400, f'{hosts[iid]["name"]}: Option Slots {amount}/{hosts[iid]["total"]}')


def validate_role_benefits(data):
    role = data.get('role')
    setup = data.get('role_setup') or {}
    for entry in data.get('inventory') or []:
        if not entry.get('role_benefit'):
            continue
        key = str(entry.get('key') or '')
        name = str(entry.get('name') or '')
        if key == 'role-exec-businesswear' and role == 'Exec':
            continue
        if key.startswith('role-nomad-') and role == 'Nomad' and name in (setup.get('moto_choices') or []):
            continue
        raise ApiError(400, f'Недопустимое стартовое преимущество роли: {name or key}')


def validate_creation_equipment(data):
    """Не позволяет подменить HL, тип, SP или локацию купленного предмета."""
    inventory_keys = {str(entry.get('key') or '') for entry in data.get('inventory') or []}
    for chrome in data.get('cyberware') or []:
        if chrome.get('creation_free') and chrome.get('key') == 'creation-neuroport':
            continue
        item = item_by_id(str(chrome.get('key') or ''))
        if not item or item.get('cat') != 'cyberware':
            raise ApiError(400, f'Неизвестный имплант: {chrome.get("key")}')
        expected_type = str((item.get('fields') or {}).get('Type') or '')
        if (_num(chrome.get('hl')) or 0) != (_num(item.get('hl')) or 0) or str(chrome.get('type') or '') != expected_type:
            raise ApiError(400, f'Характеристики импланта {item["name"]} не совпадают с Data Pool')

    armor = data.get('armor') or {}
    for location in ('body', 'head'):
        piece = armor.get(location)
        if not piece:
            continue
        raw_key = str(piece.get('source_key') or piece.get('key') or '')
        item = item_by_id(raw_key.split('@', 1)[0])
        locations = item.get('armor_locations') if item else []
        if not item or item.get('cat') != 'armor' or location not in locations or 'shield' in locations:
            raise ApiError(400, f'Недопустимая броня для локации {location}')
        if (_num(piece.get('sp')) or 0) != (_num(item.get('sp')) or 0):
            raise ApiError(400, f'SP брони {item["name"]} не совпадает с Data Pool')
        if _armor_penalties(piece) != _armor_penalties(item):
            raise ApiError(400, f'Штрафы брони {item["name"]} не совпадают с Data Pool')
        if str(piece.get('key') or '') not in inventory_keys:
            raise ApiError(400, f'Надетая броня {item["name"]} отсутствует в стартовой закупке')
    shield = armor.get('shield')
    if shield:
        raw_key = str(shield.get('source_key') or shield.get('key') or '')
        item = item_by_id(raw_key.split('@', 1)[0])
        if not item or item.get('cat') != 'armor' or 'shield' not in (item.get('armor_locations') or []):
            raise ApiError(400, 'Недопустимый щит')
        if str(shield.get('key') or '') not in inventory_keys:
            raise ApiError(400, 'Экипированный щит отсутствует в стартовой закупке')


def validate_creation_budget(data):
    """Пересчитывает стартовые фонды по ценам каталога, не доверяя клиенту."""
    gear_total = 0.0
    fashion_total = 0.0
    for entry in data.get('inventory') or []:
        if entry.get('role_benefit'):
            continue
        raw_key = str(entry.get('source_key') or entry.get('key') or '')
        item = item_by_id(raw_key.split('@', 1)[0])
        if not item or item.get('price') is None:
            raise ApiError(400, f'Неизвестный предмет стартовой закупки: {raw_key}')
        qty = max(1, min(99, _num(entry.get('qty')) or 1))
        amount = float(item['price']) * qty
        if item['cat'] == 'fashion':
            fashion_total += amount
        else:
            gear_total += amount

    chrome_total = 0.0
    has_neuroport = False
    neuroport_count = 0
    for entry in data.get('cyberware') or []:
        if entry.get('creation_free') and entry.get('key') == 'creation-neuroport':
            has_neuroport = True
            neuroport_count += 1
            continue
        item = item_by_id(str(entry.get('key') or ''))
        if not item or item.get('cat') != 'cyberware' or item.get('price') is None:
            raise ApiError(400, f'Неизвестный имплант стартовой закупки: {entry.get("key")}')
        if item['name'].lower() == 'neuroport':
            has_neuroport = True
            neuroport_count += 1
        ctype = str((item.get('fields') or {}).get('Type') or '').lower()
        if 'fashionware' in ctype:
            fashion_total += float(item['price'])
        else:
            chrome_total += float(item['price'])

    if neuroport_count > 1:
        raise ApiError(400, 'Одновременно допустим только один Neuroport')
    if fashion_total > START_CASH_FASHION + 1e-9:
        raise ApiError(400, f'Fashion/Fashionware превышает бюджет {START_CASH_FASHION}€$')
    creation = data.get('creation') or {}
    sold_soul = bool(creation.get('sold_soul'))
    if sold_soul and (not str(creation.get('patron') or '').strip() or
                      not str(creation.get('obligation') or '').strip()):
        raise ApiError(400, 'Sell Your Soul требует покровителя и обязательство')
    if (chrome_total > 0 or fashion_total > 0 or sold_soul) and not has_neuroport:
        raise ApiError(400, 'В 2070-х хром при создании требует Neuroport')
    chrome_bonus = 1500 if sold_soul else 0
    main_spent = gear_total + max(0.0, chrome_total - chrome_bonus)
    if main_spent > START_CASH_GEAR + 1e-9:
        raise ApiError(400, f'Закупка превышает основной бюджет {START_CASH_GEAR}€$')
    expected_cash = round(START_CASH_GEAR - main_spent, 2)
    if abs(float(data.get('cash') or 0) - expected_cash) > 0.01:
        raise ApiError(400, 'Остаток стартового бюджета рассчитан неверно')


def validate_role_rank_setup(role, rank, setup):
    setup = setup or {}
    if role == 'Tech':
        values = [_num(setup.get(key)) or 0 for key in ('field','upgrade','fabrication','invention')]
        if sum(values) != rank * 2 or any(value < 0 or value > rank for value in values):
            raise ApiError(400, f'Tech Rank {rank}: распределите {rank * 2} Maker Points, максимум {rank} в specialty')
    elif role == 'Medtech':
        values = [_num(setup.get(key)) or 0 for key in ('surgery','pharma','cryo')]
        if sum(values) != rank or any(value < 0 or value > rank for value in values):
            raise ApiError(400, f'Medtech Rank {rank}: распределите {rank} Medicine Points')
    elif role == 'Nomad':
        choices = setup.get('moto_choices')
        if not isinstance(choices, list) or len(choices) != rank or any(not str(value or '').strip() for value in choices):
            raise ApiError(400, f'Nomad Rank {rank}: заполните {rank} Moto choices')
    elif role == 'Exec' and rank >= 3:
        members = setup.get('team_members') or ([setup.get('team_member')] if setup.get('team_member') else [])
        if not members:
            raise ApiError(400, f'Exec Rank {rank}: выберите Team Member')


def validate_creation(data):
    """Серверная проверка Complete Package, не применяемая к последующему росту."""
    role = data.get('role')
    if role not in ROLES or _num(data.get('role_rank')) != 4:
        raise ApiError(400, 'Новый персонаж должен иметь одну роль с рангом 4')

    stats = data.get('stats') or {}
    if set(stats) != set(STATS):
        raise ApiError(400, 'Нужно заполнить все 10 характеристик')
    values = [_num(stats.get(stat)) for stat in STATS]
    if any(value is None or value < 2 or value > 8 for value in values):
        raise ApiError(400, 'При создании каждая характеристика должна быть от 2 до 8')
    if sum(values) != STAT_POINTS:
        raise ApiError(400, f'Нужно распределить ровно {STAT_POINTS} очка характеристик')

    skills = data.get('skills') or {}
    if creation_skill_cost(data) != SKILL_POINTS:
        raise ApiError(400, f'Нужно распределить ровно {SKILL_POINTS} очков навыков')
    for required in MUST_SKILLS:
        if required == 'Language':
            level = _num(skills.get('Language (Streetslang)')) or 0
        elif required == 'Local Expert':
            level = max([_num(v) or 0 for k, v in skills.items()
                         if skill_base(k) == 'Local Expert'] or [0])
        else:
            level = _num(skills.get(required)) or 0
        if level < 2:
            label = 'Language (Streetslang)' if required == 'Language' else required
            raise ApiError(400, f'Обязательный навык {label} должен быть минимум 2')
    native = str(data.get('native_language') or '').strip()
    if not native or (_num(skills.get(f'Language ({native})')) or 0) < 4:
        raise ApiError(400, 'Выберите культурный язык с бесплатным уровнем 4')

    mode = data.get('lifepath_mode')
    lifepath = data.get('lifepath') or {}
    # friends/enemies/tragic love остаются читаемыми у старых листов, но больше
    # не являются обязательной частью создания. Новый мастер объединяет источники.
    common = {
        'merged': ('region', 'personality', 'clothing', 'hair', 'hair_color',
                   'affectation', 'value', 'people', 'person', 'possession',
                   'family', 'environment', 'crisis', 'goal'),
        'core': ('region', 'personality', 'clothing', 'hair', 'affectation',
                 'value', 'people', 'person', 'possession', 'family',
                 'environment', 'crisis', 'goal'),
        'cemk': ('region', 'personality', 'wardrobe', 'hair_style', 'hair_color',
                 'value', 'people', 'family', 'environment', 'crisis', 'goal'),
    }
    if mode not in common or any(not str(lifepath.get(key) or '').strip()
                                 for key in common[mode]):
        raise ApiError(400, 'Заполните общий Lifepath')
    region = str(lifepath.get('region') or '')
    region_key = next((key for key in CULTURAL_LANGUAGES if region.startswith(key)), None)
    if not region_key or native not in CULTURAL_LANGUAGES[region_key]:
        raise ApiError(400, 'Культурный язык должен соответствовать происхождению Lifepath')
    role_lifepath = data.get('role_lifepath') or {}
    role_required = {
        'Rockerboy': ('kind', 'act', 'venue', 'enemy'),
        'Solo': ('kind', 'moral', 'enemy', 'territory'),
        'Netrunner': ('kind', 'partner', 'workspace', 'clients', 'supplies', 'enemy'),
        'Tech': ('kind', 'partner', 'workspace', 'clients', 'supplies', 'enemy'),
        'Medtech': ('kind', 'partner', 'workspace', 'clients', 'supplies'),
        'Media': ('kind', 'channel', 'ethics', 'stories'),
        'Exec': ('kind', 'division', 'ethics', 'base', 'enemy', 'boss'),
        'Lawman': ('position', 'jurisdiction', 'corruption', 'enemy', 'target'),
        'Fixer': ('kind', 'partner', 'office', 'clients', 'enemy'),
        'Nomad': ('size', 'domain', 'activity', 'duty', 'philosophy', 'enemy'),
    }[role]
    if not isinstance(role_lifepath, dict) or any(
            not str(role_lifepath.get(key) or '').strip() for key in role_required):
        raise ApiError(400, 'Заполните все поля Lifepath выбранной роли')

    setup = data.get('role_setup') or {}
    if role == 'Tech':
        ranks = [_num(setup.get(k)) or 0 for k in
                 ('field', 'upgrade', 'fabrication', 'invention')]
        if sum(ranks) != 8 or any(rank < 0 or rank > 4 for rank in ranks):
            raise ApiError(400, 'Tech распределяет 8 рангов Maker: по 2 за каждый ранг роли')
    elif role == 'Medtech':
        ranks = [_num(setup.get(k)) or 0 for k in ('surgery', 'pharma', 'cryo')]
        if sum(ranks) != 4 or any(rank < 0 or rank > 4 for rank in ranks):
            raise ApiError(400, 'Medtech распределяет 4 ранга Medicine')
    elif role == 'Exec' and not str(setup.get('team_member') or '').strip():
        raise ApiError(400, 'Exec должен выбрать стартового сотрудника Teamwork')
    elif role == 'Nomad':
        choices = setup.get('moto_choices')
        if (not isinstance(choices, list) or len(choices) != 4 or
                any(not str(choice or '').strip() for choice in choices)):
            raise ApiError(400, 'Nomad должен заполнить 4 стартовых выбора Moto')
        vehicle_items = {item['name']: item for item in catalog()['items']
                         if item.get('cat') in ('vehicles', 'vehicles_upgrades')}
        for rank, choice in enumerate(choices, start=1):
            item = vehicle_items.get(str(choice))
            access = _num((item.get('mechanics') or {}).get('nomad_access')) if item else None
            if not item or access is None or access > rank:
                raise ApiError(400, f'Nomad Moto Rank {rank}: недоступный выбор {choice}')

    validate_role_benefits(data)
    validate_creation_equipment(data)
    validate_cyberware_requirements(data)
    validate_cyberware_slots(data)
    if (derive(data).get('humanity_cur') or 0) < 0:
        raise ApiError(400, 'Нельзя завершить создание с Humanity ниже 0')
    validate_creation_budget(data)


# ---------------------------------------------------------------- http

def theme_contrast(a, b):
    def lum(color):
        values=[int(color[index:index+2],16)/255 for index in (1,3,5)]
        values=[value/12.92 if value<=.03928 else ((value+.055)/1.055)**2.4 for value in values]
        return .2126*values[0]+.7152*values[1]+.0722*values[2]
    x,y=lum(a),lum(b);return (max(x,y)+.05)/(min(x,y)+.05)

def validate_theme(theme):
    color_keys={'bg','bg2','panel','panel2','line','text','muted','primary','secondary','accent','success','danger','warning'}
    for key in color_keys:
        if key in theme and not re.fullmatch(r'#[0-9a-fA-F]{6}', str(theme[key])):
            raise ApiError(400, f'Некорректный цвет темы: {key}')
    bg=str(theme.get('bg') or '#0b0e14');panel=str(theme.get('panel') or '#141a2a');text=str(theme.get('text') or '#d7e3f4')
    if theme_contrast(bg,text)<4.5 or theme_contrast(panel,text)<4.5:
        raise ApiError(400, 'Контраст текста темы должен быть не ниже 4.5:1')


MEDIA_LIMIT = 2_500_000
MEDIA_KINDS = {'character_portrait', 'account_avatar', 'news_image', 'job_image'}

def image_info(raw):
    """Return (mime, extension, width, height) from trusted file signatures."""
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24:
        return 'image/png', 'png', int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
    if raw.startswith(b'\xff\xd8'):
        pos = 2
        while pos + 9 < len(raw):
            if raw[pos] != 0xff:
                pos += 1; continue
            marker = raw[pos + 1]; pos += 2
            if marker in (0xd8, 0xd9): continue
            if pos + 2 > len(raw): break
            size = int.from_bytes(raw[pos:pos + 2], 'big')
            if marker in tuple(range(0xc0, 0xc4)) + tuple(range(0xc5, 0xc8)) + tuple(range(0xc9, 0xcc)) + tuple(range(0xcd, 0xd0)):
                return 'image/jpeg', 'jpg', int.from_bytes(raw[pos + 5:pos + 7], 'big'), int.from_bytes(raw[pos + 3:pos + 5], 'big')
            pos += size
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP' and len(raw) >= 30:
        chunk = raw[12:16]
        if chunk == b'VP8X':
            return 'image/webp', 'webp', 1 + int.from_bytes(raw[24:27], 'little'), 1 + int.from_bytes(raw[27:30], 'little')
        if chunk == b'VP8 ' and len(raw) >= 30:
            return 'image/webp', 'webp', int.from_bytes(raw[26:28], 'little') & 0x3fff, int.from_bytes(raw[28:30], 'little') & 0x3fff
        if chunk == b'VP8L' and len(raw) >= 25:
            bits = int.from_bytes(raw[21:25], 'little')
            return 'image/webp', 'webp', (bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1
    return None

def media_payload(row):
    return {'id': row['id'], 'kind': row['kind'], 'mime': row['mime'], 'size': row['size'],
            'width': row['width'], 'height': row['height'], 'url': f'/api/media/{row["id"]}'}

def attach_character_media(conn, user_id, character_id, data):
    media_id = str(data.get('portrait_media_id') or '')
    if not media_id:
        return
    media = conn.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
    if not media or media['owner_id'] != user_id or media['kind'] != 'character_portrait':
        raise ApiError(400, 'Недопустимое изображение персонажа')
    if media['attached_type'] and not (media['attached_type'] == 'character' and media['attached_id'] == character_id):
        raise ApiError(409, 'Изображение уже прикреплено')
    conn.execute("UPDATE media SET attached_type='character', attached_id=? WHERE id=?", (character_id, media_id))


def ensure_progression(data):
    """Lazy backward-compatible progression schema."""
    if not isinstance(data.get('roles'), list) or not data['roles']:
        role = str(data.get('role') or '')
        data['roles'] = [{'name': role, 'rank': _num(data.get('role_rank')) or 4,
                          'setup': dict(data.get('role_setup') or {}), 'primary': True}] if role else []
    if data['roles']:
        primary = next((row for row in data['roles'] if row.get('primary')), data['roles'][0])
        primary['primary'] = True
        data['primary_role'] = str(data.get('primary_role') or primary.get('name') or '')
        data['active_role'] = str(data.get('active_role') or data['roles'][-1].get('name') or data['primary_role'])
    data['luck_cur'] = max(0, min(_num((data.get('stats') or {}).get('LUCK')) or 0,
                                  _num(data.get('luck_cur')) if _num(data.get('luck_cur')) is not None else (_num((data.get('stats') or {}).get('LUCK')) or 0)))
    data['ip_available'] = max(0, _num(data.get('ip_available')) or 0)
    data['ip_total_earned'] = max(data['ip_available'], _num(data.get('ip_total_earned')) or data['ip_available'])
    data['ip_total_spent'] = max(0, _num(data.get('ip_total_spent')) or 0)
    data['reputation'] = max(0, min(10, _num(data.get('reputation')) or 0))
    armor = data.get('armor') or {}
    for location in ('head','body','shield'):
        piece = armor.get(location)
        if isinstance(piece, dict):
            maximum = _num(piece.get('sp')) or _num(piece.get('sdp')) or 0
            piece['current'] = max(0, min(maximum, _num(piece.get('current')) if _num(piece.get('current')) is not None else maximum))
            piece['maximum'] = maximum
    states = data.setdefault('weapon_state', {})
    inventory = data.get('inventory') or []
    ammo = [item for item in inventory if item.get('cat') in ('ammo','grenades')]
    for weapon in [item for item in inventory if item.get('cat') in ('guns','melee')]:
        key = str(weapon.get('key') or weapon.get('source_key') or weapon.get('name'))
        magazine = _num((weapon.get('mechanics') or {}).get('magazine')) or 0
        if key not in states:
            weapon_type = str((weapon.get('mechanics') or {}).get('type') or '').lower()
            reserve = 0
            for pack in ammo:
                suitable = str((pack.get('mechanics') or {}).get('compatible_weapons') or '').lower()
                compatible = weapon_type and (weapon_type in suitable or ('all except' in suitable and not any(token in weapon_type for token in ('grenade','rocket'))))
                if compatible:
                    reserve += (_num(pack.get('qty')) or 1) * (_num((pack.get('mechanics') or {}).get('quantity_per_purchase')) or 1)
            states[key] = {'magazine': magazine, 'magazine_max': magazine, 'reserve': reserve}
    data['schema_version'] = max(4, _num(data.get('schema_version')) or 0)
    return data


SERVER_ERROR_EN = {
    'Требуется вход в систему': 'Authentication required',
    'Нужен псевдоним (Handle) персонажа': 'Character Handle is required',
    'Новый персонаж должен иметь одну роль с рангом 4': 'A new character must have one Role at Rank 4',
    'Нужно заполнить все 10 характеристик': 'All 10 Characteristics are required',
    'При создании каждая характеристика должна быть от 2 до 8': 'Each Characteristic must be between 2 and 8 at creation',
    'Нужно распределить ровно 62 очка характеристик': 'Allocate exactly 62 Characteristic Points',
    'Нужно распределить ровно 86 очков навыков': 'Allocate exactly 86 Skill Points',
    'Выберите культурный язык с бесплатным уровнем 4': 'Choose a Cultural Language at free Level 4',
    'Культурный язык должен соответствовать происхождению Lifepath': 'Cultural Language must match Lifepath origin',
    'Заполните общий Lifepath': 'Complete the Common Lifepath',
    'Заполните все поля Lifepath выбранной роли': 'Complete every Role-Based Lifepath field',
    'Одновременно допустим только один Neuroport': 'Only one Neuroport is allowed',
    'В 2070-х хром при создании требует Neuroport': 'Cyberware at creation requires a Neuroport',
    'Sell Your Soul требует покровителя и обязательство': 'Sell Your Soul requires a Patron and an Obligation',
    'Нельзя завершить создание с Humanity ниже 0': 'Creation cannot finish below 0 Humanity',
    'Лист персонажа должен быть объектом': 'Character data must be an object',
    'Лист персонажа слишком большой': 'Character data is too large',
    'Некорректный JSON': 'Invalid JSON',
    'Пустое тело запроса': 'Empty request body',
    'Active Role должна достичь Rank 4 перед multiclass': 'Active Role must reach Rank 4 before multiclassing',
    'Active Role должна достичь Rank 4 перед переключением': 'Active Role must reach Rank 4 before switching',
    'Exec должен выбрать стартового сотрудника Teamwork': 'Exec must choose a starting Teamwork Team Member',
    'Medtech распределяет 4 ранга Medicine': 'Medtech must allocate 4 Medicine ranks',
    'Nomad должен заполнить 4 стартовых выбора Moto': 'Nomad must complete 4 starting Moto choices',
    'Role Ability уже достигла Rank 10': 'Role Ability has already reached Rank 10',
    'Role не принадлежит персонажу': 'The character does not have this Role',
    'Role-Based Lifepath разрешён только primary Role': 'Role-Based Lifepath is only allowed for the primary Role',
    'Skill уже достиг Level 10': 'Skill has already reached Level 10',
    'Specialization уже достигла Level 10': 'Specialization has already reached Level 10',
    'Tech распределяет 8 рангов Maker: по 2 за каждый ранг роли': 'Tech must allocate 8 Maker ranks: 2 for each Role rank',
    'cash должен быть числом': 'cash must be numeric',
    'skill_pools должен быть объектом': 'skill_pools must be an object',
    'skill_pools содержит неизвестный специализированный навык': 'skill_pools contains an unknown specialized Skill',
    'skill_specializations должен быть списком до 100 записей': 'skill_specializations must be a list of no more than 100 entries',
    'stats должен быть объектом': 'stats must be an object',
    'Баланс IP не может быть отрицательным': 'IP balance cannot be negative',
    'В корзине нет известных товаров': 'The Cart contains no recognized items',
    'Все слоты заняты': 'All slots are filled',
    'Вы уже записаны': 'You are already signed up',
    'Для специализированного навыка повышайте parent-pool': 'Increase the parent pool for a specialized Skill',
    'Достигнут лимит хранилища изображений': 'Image storage limit reached',
    'Заголовок и текст обязательны': 'Title and body are required',
    'Заказ закрыт': 'This Job is closed',
    'Заказ не найден': 'Job not found',
    'Изображение не найдено': 'Image not found',
    'Изображение приватное': 'This image is private',
    'Изображение уже прикреплено': 'Image is already attached',
    'Контраст текста темы должен быть не ниже 4.5:1': 'Theme text contrast must be at least 4.5:1',
    'Логин: 3–24 символа, латиница/цифры/._-': 'Username: 3–24 Latin letters, digits, or ._-',
    'Локация брони не экипирована': 'No Armor is equipped at this location',
    'Можно удалять только свои посты': 'You can only delete your own posts',
    'Название и описание обязательны': 'Title and description are required',
    'Не найдено': 'Not found',
    'Неверный логин или пароль': 'Invalid username or password',
    'Недопустимое изображение персонажа': 'Invalid character image',
    'Недопустимое разрешение изображения': 'Invalid image dimensions',
    'Недопустимый тип изображения': 'Invalid image type',
    'Недопустимый щит': 'Invalid shield',
    'Неизвестная Role': 'Unknown Role',
    'Неизвестный parent Skill': 'Unknown parent Skill',
    'Неизвестный ресурс': 'Unknown resource',
    'Неизвестный тип улучшения': 'Unknown advancement type',
    'Некорректная тема': 'Invalid theme',
    'Нельзя записаться на свой заказ': 'You cannot sign up for your own Job',
    'Нет права изменять этого персонажа': 'You do not have permission to modify this character',
    'Нет свободных parent points': 'No free parent points',
    'Новость не найдена': 'Report not found',
    'Ожидается JPEG, PNG или WebP': 'Expected a JPEG, PNG, or WebP image',
    'Оружие не найдено': 'Weapon not found',
    'Пароль: минимум 4 символа': 'Password must contain at least 4 characters',
    'Персонаж не найден': 'Character not found',
    'Персонаж приватный': 'This character is private',
    'Повреждённые данные изображения': 'Corrupted image data',
    'Повышать можно только active Role': 'Only the active Role can be advanced',
    'Предмет не найден': 'Item not found',
    'Предмет не найден в инвентаре': 'Item not found in Inventory',
    'Пустая корзина': 'The Cart is empty',
    'Слишком большая сумма': 'Amount is too large',
    'Слишком много персонажей (максимум 50)': 'Too many characters (maximum 50)',
    'Сначала отсоедините изображение': 'Detach the image first',
    'Статус: open/closed': 'Status must be open or closed',
    'Такой логин уже занят': 'That username is already taken',
    'Тело запроса слишком большое': 'Request body is too large',
    'Только автор может менять статус': 'Only the author can change the status',
    'Только автор может удалить заказ': 'Only the author can delete this Job',
    'Только для пользователей с ролью ГМ': 'GM role required',
    'Укажите parent и specialization': 'Specify parent and specialization',
    'Укажите ненулевое изменение IP и причину': 'Specify a nonzero IP change and a reason',
    'Файл изображения не найден': 'Image file not found',
    'Формат изображения не подтверждён содержимым': 'The image content does not match a supported format',
    'Экипированный щит отсутствует в стартовой закупке': 'The equipped shield is missing from starting purchases',
    'Это не ваш персонаж': 'This is not your character',
    'Только для администраторов NC//NET': 'NC//NET Admin role required',
    'Роли аккаунтов назначает только администратор NC//NET': 'Only an NC//NET Admin can assign account roles',
    'Некорректные настройки уведомлений': 'Invalid notification settings',
    'Пользователь не найден': 'User not found',
    'Недопустимая роль аккаунта': 'Invalid account role',
    'Нельзя снять роль с последнего администратора': 'The last Admin cannot be demoted',
}

def server_error_message(message, language):
    if str(language or '').lower().startswith('ru'):
        return message
    if message in SERVER_ERROR_EN:
        return SERVER_ERROR_EN[message]
    replacements = [
        ('Неизвестный навык:', 'Unknown Skill:'),
        ('Обязательный навык', 'Required Skill'),
        ('должен быть минимум', 'must be at least'),
        ('при создании допустим уровень', 'allowed Level at creation is'),
        ('укажите конкретную специализацию в скобках', 'provide a specialization in parentheses'),
        ('Неизвестный имплант:', 'Unknown Cyberware:'),
        ('Неизвестный предмет стартовой закупки:', 'Unknown starting item:'),
        ('Неизвестный имплант стартовой закупки:', 'Unknown starting Cyberware:'),
        ('требует:', 'requires:'),
        ('не выбран совместимый host', 'no compatible host selected'),
        ('несовместимый host', 'incompatible host'),
        ('допустима только одна установка', 'only one installation is allowed'),
        ('Закупка превышает основной бюджет', 'Shopping exceeds Main Budget'),
        ('Fashion/Fashionware превышает бюджет', 'Fashion/Fashionware exceeds Style Budget'),
        ('Остаток стартового бюджета рассчитан неверно', 'Starting cash was calculated incorrectly'),
        ('Недопустимое стартовое преимущество роли:', 'Invalid starting Role benefit:'),
        ('Нужно распределить ровно', 'Allocate exactly'),
        ('очка характеристик', 'Characteristic Points'),
        ('очков навыков', 'Skill Points'),
        ('Характеристики импланта', 'Cyberware mechanics for'),
        ('не совпадают с Data Pool', 'do not match the Data Pool'),
        ('не совпадает с Data Pool', 'does not match the Data Pool'),
        ('Недопустимая броня для локации', 'Invalid Armor for location'),
        ('SP брони', 'Armor SP for'),
        ('Штрафы брони', 'Armor penalties for'),
        ('Надетая броня', 'Equipped Armor'),
        ('отсутствует в стартовой закупке', 'is missing from starting purchases'),
        ('распределите', 'allocate'),
        ('максимум', 'maximum'),
        ('в specialty', 'in one specialty'),
        ('Некорректный цвет темы:', 'Invalid theme color:'),
        ('Изображение должно быть не больше', 'Image must be no larger than'),
        ('Недостаточно IP: требуется', 'Not enough IP; required:'),
        ('Не хватает €$: нужно', 'Not enough eb; required:'),
        ('есть', 'available'),
        ('ожидается список', 'expected a list'),
        ('до 300 записей', 'up to 300 entries'),
        ('некорректный parent-pool', 'invalid parent pool'),
        ('распределено', 'allocated'),
        ('при parent-pool', 'with parent pool'),
        ('требуется совместимых hosts:', 'required compatible hosts:'),
        ('заполните', 'complete'),
        ('выберите Team Member', 'choose a Team Member'),
        ('недоступный выбор', 'unavailable choice'),
        ('уже на минимальном Level', 'is already at minimum Level'),
    ]
    out = str(message)
    for ru, en in replacements:
        out = out.replace(ru, en)
    return out


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
        language = self.headers.get('Accept-Language') or 'en'
        self.send_json({'error': server_error_message(message, language)}, status)

    def read_json(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n <= 0:
            raise ApiError(400, 'Пустое тело запроса')
        if n > 4_000_000:
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
        if not user_is_gm(u):
            raise ApiError(403, 'Только для пользователей с ролью ГМ')
        return u

    def require_admin(self, conn):
        u = self.require_user(conn)
        if not user_is_admin(u):
            raise ApiError(403, 'Только для администраторов NC//NET')
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
                        if method in ('POST', 'PUT'):
                            body = self.read_json() if int(self.headers.get('Content-Length') or 0) else {}
                        else:
                            body = None
                        fn(self, conn, qs, match, body)
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
            '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.ico': 'image/x-icon',
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
        if not re.fullmatch(r'[a-z0-9_.\-]{3,24}', username):
            raise ApiError(400, 'Логин: 3–24 символа, латиница/цифры/._-')
        if len(password) < 4:
            raise ApiError(400, 'Пароль: минимум 4 символа')
        try:
            cur = conn.execute(
                'INSERT INTO users(username, display_name, pass_hash, is_gm, account_role, created) '
                "VALUES(?,?,?,0,'player',?)",
                (username, display, hash_password(password), time.time()))
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
        try:
            theme = json.loads(_row_value(u, 'theme_json', '{}') or '{}')
        except (TypeError, ValueError):
            theme = {}
        try:
            notification_prefs = json.loads(_row_value(u, 'notification_prefs', '{}') or '{}')
        except (TypeError, ValueError):
            notification_prefs = {}
        role = user_account_role(u)
        return {
            'id': u['id'], 'username': u['username'], 'display_name': u['display_name'],
            'account_role': role, 'is_gm': role in ('gm', 'admin'),
            'is_admin': role == 'admin',
            'show_display_name': bool(_row_value(u, 'show_display_name', 0)),
            'vk_linked': bool(_row_value(u, 'vk_user_id')),
            'notification_prefs': notification_prefs,
            'theme': theme,
        }

    def api_me(self, conn, qs, m, body):
        u = self.current_user(conn)
        self.send_json({'user': self.me_payload(u) if u else None})

    def api_profile(self, conn, qs, m, body):
        u = self.require_user(conn)
        if 'display_name' in (body or {}):
            dn = str(body['display_name'] or '').strip()[:60]
            if dn:
                conn.execute('UPDATE users SET display_name=? WHERE id=?', (dn, u['id']))
        if 'is_gm' in (body or {}) or 'account_role' in (body or {}):
            raise ApiError(403, 'Роли аккаунтов назначает только администратор NC//NET')
        if 'show_display_name' in (body or {}):
            conn.execute('UPDATE users SET show_display_name=? WHERE id=?',
                         (1 if body['show_display_name'] else 0, u['id']))
        if 'notification_prefs' in (body or {}):
            prefs = body.get('notification_prefs') or {}
            if not isinstance(prefs, dict) or len(json.dumps(prefs)) > 5000:
                raise ApiError(400, 'Некорректные настройки уведомлений')
            conn.execute('UPDATE users SET notification_prefs=? WHERE id=?',
                         (json.dumps(prefs, separators=(',', ':')), u['id']))
        if 'theme' in (body or {}):
            theme = body.get('theme') or {}
            if not isinstance(theme, dict) or len(json.dumps(theme)) > 5000:
                raise ApiError(400, 'Некорректная тема')
            validate_theme(theme)
            conn.execute('UPDATE users SET theme_json=? WHERE id=?',
                         (json.dumps(theme, separators=(',', ':')), u['id']))
        conn.commit()
        u2 = conn.execute('SELECT * FROM users WHERE id=?', (u['id'],)).fetchone()
        self.send_json(self.me_payload(u2))

    def api_admin_users(self, conn, qs, m, body):
        self.require_admin(conn)
        rows = conn.execute(
            'SELECT u.*, COUNT(c.id) character_count FROM users u '
            'LEFT JOIN characters c ON c.owner_id=u.id GROUP BY u.id ORDER BY u.created, u.id'
        ).fetchall()
        audit_rows = conn.execute(
            'SELECT a.*, target.username target_username, actor.username actor_username '
            'FROM account_role_audit a JOIN users target ON target.id=a.target_user_id '
            'LEFT JOIN users actor ON actor.id=a.actor_user_id '
            'ORDER BY a.created DESC, a.id DESC LIMIT 50'
        ).fetchall()
        self.send_json({
            'users': [{
                'id': row['id'], 'username': row['username'],
                'display_name': row['display_name'],
                'account_role': user_account_role(row),
                'show_display_name': bool(_row_value(row, 'show_display_name', 0)),
                'vk_linked': bool(_row_value(row, 'vk_user_id')),
                'character_count': row['character_count'],
                'created': row['created'],
            } for row in rows],
            'role_audit': [{
                'id': row['id'], 'target_username': row['target_username'],
                'actor_username': row['actor_username'] or 'system',
                'role_before': row['role_before'], 'role_after': row['role_after'],
                'reason': row['reason'], 'created': row['created'],
            } for row in audit_rows],
        })

    def api_admin_user_role(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        updated = assign_account_role(
            conn, actor, int(m.group(1)), (body or {}).get('account_role'),
            (body or {}).get('reason') or 'Admin role assignment')
        self.send_json(self.me_payload(updated))

    # ------------------------------------------------------------ media

    def api_media_upload(self, conn, qs, m, body):
        u = self.require_user(conn)
        kind = str((body or {}).get('kind') or '')
        if kind not in MEDIA_KINDS:
            raise ApiError(400, 'Недопустимый тип изображения')
        data_url = str((body or {}).get('data_url') or '')
        match = re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)', data_url)
        if not match:
            raise ApiError(400, 'Ожидается JPEG, PNG или WebP')
        try:
            raw = base64.b64decode(match.group(1), validate=True)
        except Exception:
            raise ApiError(400, 'Повреждённые данные изображения')
        if not raw or len(raw) > MEDIA_LIMIT:
            raise ApiError(413, f'Изображение должно быть не больше {MEDIA_LIMIT // 1_000_000} MB')
        info = image_info(raw)
        if not info:
            raise ApiError(400, 'Формат изображения не подтверждён содержимым')
        mime, ext, width, height = info
        if width < 32 or height < 32 or width > 6000 or height > 6000 or width * height > 24_000_000:
            raise ApiError(400, 'Недопустимое разрешение изображения')
        total = conn.execute('SELECT COALESCE(SUM(size),0) n FROM media WHERE owner_id=?', (u['id'],)).fetchone()['n']
        if total + len(raw) > 50_000_000:
            raise ApiError(413, 'Достигнут лимит хранилища изображений')
        media_id = secrets.token_hex(16)
        filename = f'{media_id}.{ext}'
        with open(os.path.join(UPLOAD_DIR, filename), 'wb') as handle:
            handle.write(raw)
        conn.execute('INSERT INTO media(id,owner_id,kind,mime,filename,size,width,height,created) VALUES(?,?,?,?,?,?,?,?,?)',
                     (media_id, u['id'], kind, mime, filename, len(raw), width, height, time.time()))
        conn.commit()
        row = conn.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
        self.send_json(media_payload(row), status=201)

    def api_media_get(self, conn, qs, m, body):
        row = conn.execute('SELECT * FROM media WHERE id=?', (m.group(1),)).fetchone()
        if not row:
            raise ApiError(404, 'Изображение не найдено')
        user = self.current_user(conn)
        allowed = bool(user and user['id'] == row['owner_id']); public_media = False
        if row['attached_type'] == 'character' and row['attached_id']:
            char = conn.execute('SELECT owner_id,public FROM characters WHERE id=?', (row['attached_id'],)).fetchone()
            public_media = bool(char and char['public'])
            allowed = bool(char and (public_media or (user and user['id'] == char['owner_id'])))
        if not allowed:
            raise ApiError(403, 'Изображение приватное')
        path = os.path.join(UPLOAD_DIR, row['filename'])
        if not os.path.isfile(path):
            raise ApiError(404, 'Файл изображения не найден')
        raw = open(path, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', row['mime'])
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'public, max-age=86400' if public_media else 'private, no-store')
        self.end_headers(); self.wfile.write(raw)

    def api_media_delete(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = conn.execute('SELECT * FROM media WHERE id=?', (m.group(1),)).fetchone()
        if not row or row['owner_id'] != u['id']:
            raise ApiError(404, 'Изображение не найдено')
        if row['attached_type']:
            raise ApiError(409, 'Сначала отсоедините изображение')
        try: os.remove(os.path.join(UPLOAD_DIR, row['filename']))
        except FileNotFoundError: pass
        conn.execute('DELETE FROM media WHERE id=?', (row['id'],)); conn.commit()
        self.send_json({'ok': True})


    # ------------------------------------------------------------ мета/справочник

    def api_meta(self, conn, qs, m, body):
        cat = catalog()
        is_ru = (self.headers.get('Accept-Language') or 'en').lower().startswith('ru')
        self.send_json({
            'stats': STATS, 'roles': ROLES, 'role_ru': ROLE_RU, 'role_desc': ROLE_DESC, 'role_desc_en': ROLE_DESC_EN,
            'skills': SKILLS, 'must_skills': MUST_SKILLS,
            'stat_points': STAT_POINTS, 'skill_points': SKILL_POINTS,
            'skill_max': SKILL_MAX_CREATION,
            'start_cash_gear': START_CASH_GEAR, 'start_cash_fashion': START_CASH_FASHION,
            'wound_states': WOUND_STATES if is_ru else WOUND_STATES_EN,
            'crit_body': CRIT_BODY if is_ru else CRIT_BODY_EN,
            'crit_head': CRIT_HEAD if is_ru else CRIT_HEAD_EN,
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
        data = ensure_progression(json.loads(row['data']))
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
        validate_creation(data)
        count = conn.execute('SELECT COUNT(*) n FROM characters WHERE owner_id=?',
                             (u['id'],)).fetchone()['n']
        if count >= 50:
            raise ApiError(400, 'Слишком много персонажей (максимум 50)')
        now = time.time()
        pub = 1 if data.get('public', False) else 0
        cur = conn.execute(
            'INSERT INTO characters(owner_id, public, data, created, updated) VALUES(?,?,?,?,?)',
            (u['id'], pub, json.dumps(data, ensure_ascii=False), now, now))
        attach_character_media(conn, u['id'], cur.lastrowid, data)
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
        old_data = json.loads(row['data'])
        data = clean_character(body.get('data') if isinstance(body, dict) else body)
        pub = 1 if data.get('public', False) else 0
        old_media = str(old_data.get('portrait_media_id') or '')
        new_media = str(data.get('portrait_media_id') or '')
        if old_media and old_media != new_media:
            conn.execute("UPDATE media SET attached_type=NULL, attached_id=NULL WHERE id=? AND owner_id=? AND attached_type='character' AND attached_id=?",
                         (old_media, u['id'], row['id']))
        attach_character_media(conn, u['id'], row['id'], data)
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
        media_rows = conn.execute("SELECT * FROM media WHERE attached_type='character' AND attached_id=?", (row['id'],)).fetchall()
        conn.execute("DELETE FROM media WHERE attached_type='character' AND attached_id=?", (row['id'],))
        conn.execute('DELETE FROM ip_ledger WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM characters WHERE id=?', (row['id'],))
        conn.commit()
        for media in media_rows:
            try: os.remove(os.path.join(UPLOAD_DIR, media['filename']))
            except FileNotFoundError: pass
        self.send_json({'ok': True})

    def save_character_data(self, conn, row, data):
        conn.execute('UPDATE characters SET data=?, public=?, updated=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), 1 if data.get('public') else 0,
                      time.time(), row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        return self.char_payload(fresh, fresh['owner'])

    def require_character_editor(self, conn, cid, allow_gm=False):
        user = self.require_user(conn)
        row = self.get_char(conn, cid)
        if row['owner_id'] != user['id'] and not (allow_gm and user_is_gm(user)):
            raise ApiError(403, 'Нет права изменять этого персонажа')
        return user, row

    def add_ip_ledger(self, conn, character_id, actor_id, amount, before, after,
                      kind, subject, reason):
        conn.execute('INSERT INTO ip_ledger(character_id,actor_id,amount,balance_before,balance_after,kind,subject,reason,created) VALUES(?,?,?,?,?,?,?,?,?)',
                     (character_id, actor_id, amount, before, after, kind,
                      str(subject or '')[:120] or None, str(reason or '')[:500], time.time()))

    def api_character_ip(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        data = ensure_progression(json.loads(row['data']))
        amount = _num((body or {}).get('amount')) or 0
        reason = str((body or {}).get('reason') or '').strip()
        if not amount or abs(amount) > 10_000 or not reason:
            raise ApiError(400, 'Укажите ненулевое изменение IP и причину')
        before = data['ip_available']; after = before + amount
        if after < 0:
            raise ApiError(400, 'Баланс IP не может быть отрицательным')
        data['ip_available'] = after
        if amount > 0: data['ip_total_earned'] += amount
        self.add_ip_ledger(conn, row['id'], user['id'], amount, before, after,
                           'adjustment', None, reason)
        self.send_json(self.save_character_data(conn, row, data))

    def api_character_ip_history(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        rows = conn.execute('SELECT l.*,u.display_name actor FROM ip_ledger l JOIN users u ON u.id=l.actor_id WHERE character_id=? ORDER BY id DESC LIMIT 500',
                            (row['id'],)).fetchall()
        self.send_json({'entries': [dict(item) for item in rows]})

    def api_character_improve(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        kind = str((body or {}).get('kind') or '')
        subject = str((body or {}).get('subject') or '').strip()
        before = data['ip_available']; cost = 0; reason = ''
        if kind == 'skill':
            base = skill_base(subject)
            if not base or base in SPECIALIZED_SKILLS or subject != base:
                raise ApiError(400, 'Для специализированного навыка повышайте parent-pool')
            current = _num((data.get('skills') or {}).get(subject)) or 0
            if current >= 10: raise ApiError(400, 'Skill уже достиг Level 10')
            target = current + 1; cost = target * (40 if SKILL_BY_NAME[base][3] else 20)
            data.setdefault('skills', {})[subject] = target
            reason = f'{subject} {current} → {target}'
        elif kind == 'parent':
            if subject not in SPECIALIZED_SKILLS:
                raise ApiError(400, 'Неизвестный parent Skill')
            pools = data.setdefault('skill_pools', {})
            current = _num(pools.get(subject)) or 0; target = current + 1
            cost = target * (40 if SKILL_BY_NAME[subject][3] else 20)
            pools[subject] = target; reason = f'{subject} Pool {current} → {target}'
        elif kind == 'activate_role':
            if subject not in ROLES or not any(item.get('name') == subject for item in data['roles']):
                raise ApiError(400, 'Role не принадлежит персонажу')
            active = next((item for item in data['roles'] if item.get('name') == data.get('active_role')), None)
            if active and (_num(active.get('rank')) or 0) < 4:
                raise ApiError(400, 'Active Role должна достичь Rank 4 перед переключением')
            previous = data.get('active_role'); data['active_role'] = subject
            reason = f'Active Role: {previous} → {subject}'
        elif kind == 'role':
            if subject not in ROLES: raise ApiError(400, 'Неизвестная Role')
            roles = data['roles']; existing = next((item for item in roles if item.get('name') == subject), None)
            active = next((item for item in roles if item.get('name') == data.get('active_role')), None)
            if existing:
                if subject != data.get('active_role'): raise ApiError(400, 'Повышать можно только active Role')
                current = _num(existing.get('rank')) or 0
                if current >= 10: raise ApiError(400, 'Role Ability уже достигла Rank 10')
                target = current + 1; cost = target * 60; existing['rank'] = target
                if isinstance((body or {}).get('setup'), dict): existing['setup'] = body['setup']
                validate_role_rank_setup(subject, target, existing.get('setup') or {})
                reason = f'{subject} {current} → {target}'
            else:
                if active and (_num(active.get('rank')) or 0) < 4:
                    raise ApiError(400, 'Active Role должна достичь Rank 4 перед multiclass')
                cost = 60
                setup = dict((body or {}).get('setup') or {})
                validate_role_rank_setup(subject, 1, setup)
                roles.append({'name': subject, 'rank': 1, 'setup': setup, 'primary': False})
                data['active_role'] = subject; reason = f'New Role: {subject} 1'
        else:
            raise ApiError(400, 'Неизвестный тип улучшения')
        if before < cost: raise ApiError(400, f'Недостаточно IP: требуется {cost}')
        data['ip_available'] = before - cost; data['ip_total_spent'] += cost
        self.add_ip_ledger(conn, row['id'], user['id'], -cost, before,
                           data['ip_available'], 'improvement', subject, reason)
        self.send_json(self.save_character_data(conn, row, data))

    def api_character_specialization(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        parent = str((body or {}).get('parent') or '')
        name = str((body or {}).get('name') or '').strip()[:80]
        delta = 1 if (_num((body or {}).get('delta')) or 0) > 0 else -1
        if parent not in SPECIALIZED_SKILLS or not name:
            raise ApiError(400, 'Укажите parent и specialization')
        key = f'{parent} ({name})'; skills = data.setdefault('skills', {})
        current = _num(skills.get(key)) or 0
        native_key = f'Language ({data.get("native_language")})' if data.get('native_language') else None
        children = 0
        for skill, raw in skills.items():
            if skill_base(skill) != parent or skill == parent: continue
            level = _num(raw) or 0
            children += max(0, level - 4) if skill == native_key else level
        pool = _num((data.get('skill_pools') or {}).get(parent)) or 0
        if delta > 0:
            if current >= 10: raise ApiError(400, 'Specialization уже достигла Level 10')
            if children >= pool: raise ApiError(400, 'Нет свободных parent points')
            skills[key] = current + 1
        else:
            minimum = 4 if key == native_key else 0
            if current <= minimum: raise ApiError(400, f'Specialization уже на минимальном Level {minimum}')
            skills[key] = current - 1
        reason = f'{key} {current} → {skills[key]}'
        self.add_ip_ledger(conn, row['id'], user['id'], 0, data['ip_available'],
                           data['ip_available'], 'allocation', key, reason)
        self.send_json(self.save_character_data(conn, row, data))

    def api_character_resource(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        resource = str((body or {}).get('resource') or '')
        action = str((body or {}).get('action') or 'delta')
        value = _num((body or {}).get('value')) or 0
        derived = derive(data)
        if resource == 'luck':
            maximum = _num((data.get('stats') or {}).get('LUCK')) or 0
            data['luck_cur'] = maximum if action == 'reset' else max(0, min(maximum, data['luck_cur'] + value))
        elif resource == 'hp':
            maximum = derived.get('hp_max') or 0
            current = _num(data.get('hp_cur')) if _num(data.get('hp_cur')) is not None else maximum
            data['hp_cur'] = max(-maximum, min(maximum, current + value))
        elif resource == 'cash':
            data['cash'] = max(0, min(9_999_999, (float(data.get('cash') or 0) + value) if action == 'delta' else value))
        elif resource == 'reputation':
            data['reputation'] = max(0, min(10, data['reputation'] + value))
        elif resource == 'armor':
            location = str((body or {}).get('subject') or '')
            piece = (data.get('armor') or {}).get(location)
            if not isinstance(piece, dict): raise ApiError(400, 'Локация брони не экипирована')
            maximum = _num(piece.get('maximum')) or _num(piece.get('sp')) or _num(piece.get('sdp')) or 0
            piece['current'] = maximum if action == 'reset' else max(0, min(maximum, (_num(piece.get('current')) or 0) + value))
        elif resource == 'weapon':
            key = str((body or {}).get('subject') or '')
            state = (data.get('weapon_state') or {}).get(key)
            if not state: raise ApiError(400, 'Оружие не найдено')
            if action == 'fire': state['magazine'] = max(0, (_num(state.get('magazine')) or 0) - max(1, abs(value) or 1))
            elif action == 'reload':
                need = max(0, (_num(state.get('magazine_max')) or 0) - (_num(state.get('magazine')) or 0)); moved = min(need, _num(state.get('reserve')) or 0)
                state['magazine'] = (_num(state.get('magazine')) or 0) + moved; state['reserve'] = (_num(state.get('reserve')) or 0) - moved
            else: raise ApiError(400, 'Weapon action: fire/reload')
        else:
            raise ApiError(400, 'Неизвестный ресурс')
        self.send_json(self.save_character_data(conn, row, data))


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
        if r['author_id'] != u['id'] and not user_is_gm(u):
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
        if r['author_id'] != u['id'] and not user_is_gm(u):
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
        if r['author_id'] != u['id'] and not user_is_gm(u):
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
    ('GET', rx(r'/api/admin/users'), Handler.api_admin_users),
    ('POST', rx(r'/api/admin/users/(\d+)/role'), Handler.api_admin_user_role),
    ('POST', rx(r'/api/media'), Handler.api_media_upload),
    ('GET', rx(r'/api/media/([a-f0-9]{32})'), Handler.api_media_get),
    ('DELETE', rx(r'/api/media/([a-f0-9]{32})'), Handler.api_media_delete),
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
    ('POST', rx(r'/api/characters/(\d+)/ip'), Handler.api_character_ip),
    ('GET', rx(r'/api/characters/(\d+)/ip'), Handler.api_character_ip_history),
    ('POST', rx(r'/api/characters/(\d+)/improve'), Handler.api_character_improve),
    ('POST', rx(r'/api/characters/(\d+)/specialization'), Handler.api_character_specialization),
    ('POST', rx(r'/api/characters/(\d+)/resource'), Handler.api_character_resource),
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
    print(f'NC//NET listening on http://{args.host}:{args.port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
