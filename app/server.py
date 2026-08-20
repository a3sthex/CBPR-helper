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
import math
import os
import re
import secrets
import sqlite3
import sys
import time
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote, urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

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
GENERAL_DV = [
    ['Simple', 9], ['Everyday', 13], ['Difficult', 15],
    ['Professional', 17], ['Heroic', 21], ['Incredible', 24], ['Legendary', 29],
]
RULE_SOURCES = {
    'general_dv': 'Cyberpunk RED Corebook p. 129',
    'range_dv': 'Cyberpunk RED Corebook pp. 172–173; Data Pool source tables',
    'autofire_dv': 'Cyberpunk RED Corebook pp. 173–174; Data Pool source tables',
    'critical_injuries': 'Cyberpunk RED Corebook pp. 187–190',
    'wound_states': 'Cyberpunk RED Corebook pp. 186–187',
}

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
  avatar_media_id TEXT,
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

NETWORK_SCHEMA = """
CREATE TABLE IF NOT EXISTS personas(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  access TEXT NOT NULL DEFAULT 'private',
  kind TEXT NOT NULL DEFAULT 'person',
  handle TEXT UNIQUE COLLATE NOCASE NOT NULL,
  display_name TEXT NOT NULL,
  avatar_media_id TEXT,
  cover_media_id TEXT,
  accent_color TEXT NOT NULL DEFAULT '#00e5ff',
  short_bio TEXT NOT NULL DEFAULT '',
  public_bio TEXT NOT NULL DEFAULT '',
  affiliation TEXT NOT NULL DEFAULT '',
  public_connections TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'active',
  secret_bio TEXT NOT NULL DEFAULT '',
  goals TEXT NOT NULL DEFAULT '',
  voice_notes TEXT NOT NULL DEFAULT '',
  secret_connections TEXT NOT NULL DEFAULT '{}',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS persona_audit(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  persona_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS storylines(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  code_name TEXT NOT NULL DEFAULT '',
  public_summary TEXT NOT NULL DEFAULT '',
  private_summary TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'active',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS storyline_collaborators(
  storyline_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  can_edit INTEGER NOT NULL DEFAULT 1,
  PRIMARY KEY(storyline_id,user_id)
);
CREATE TABLE IF NOT EXISTS storyline_timeline(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  storyline_id INTEGER NOT NULL,
  event_at REAL,
  public_text TEXT,
  private_text TEXT NOT NULL DEFAULT '',
  contract_id INTEGER,
  feed_post_id INTEGER,
  created_by INTEGER NOT NULL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS contracts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  legacy_job_id INTEGER UNIQUE,
  owner_user_id INTEGER NOT NULL,
  storyline_id INTEGER,
  status TEXT NOT NULL DEFAULT 'draft',
  title TEXT NOT NULL,
  teaser TEXT NOT NULL DEFAULT '',
  public_brief TEXT NOT NULL DEFAULT '',
  classified_brief TEXT NOT NULL DEFAULT '',
  district_id TEXT NOT NULL DEFAULT '',
  risk_level TEXT NOT NULL DEFAULT 'moderate',
  reward_mode TEXT NOT NULL DEFAULT 'hidden',
  reward_exact REAL,
  reward_min REAL,
  reward_max REAL,
  reward_text TEXT,
  scheduled_at REAL,
  timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
  duration_text TEXT,
  crew_capacity INTEGER NOT NULL DEFAULT 0,
  requirements TEXT NOT NULL DEFAULT '',
  content_notes TEXT NOT NULL DEFAULT '',
  service_format TEXT NOT NULL DEFAULT '',
  service_contact TEXT NOT NULL DEFAULT '',
  service_vtt_url TEXT NOT NULL DEFAULT '',
  service_notes TEXT NOT NULL DEFAULT '',
  cover_media_id TEXT,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS contract_participants(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id INTEGER NOT NULL,
  persona_id INTEGER NOT NULL,
  role_key TEXT NOT NULL DEFAULT 'custom',
  role_label TEXT NOT NULL DEFAULT '',
  visibility TEXT NOT NULL DEFAULT 'public',
  note TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS contract_signups(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id INTEGER NOT NULL,
  user_id INTEGER NOT NULL,
  character_id INTEGER,
  legacy_char_name TEXT,
  status TEXT NOT NULL DEFAULT 'crew',
  queue_position INTEGER NOT NULL DEFAULT 0,
  joined_at REAL NOT NULL,
  updated REAL NOT NULL,
  UNIQUE(contract_id,character_id)
);
CREATE INDEX IF NOT EXISTS idx_personas_access ON personas(access,status);
CREATE INDEX IF NOT EXISTS idx_persona_audit ON persona_audit(persona_id,created);
CREATE INDEX IF NOT EXISTS idx_storylines_status ON storylines(status,updated);
CREATE INDEX IF NOT EXISTS idx_contracts_status ON contracts(status,scheduled_at);
CREATE INDEX IF NOT EXISTS idx_contract_signups ON contract_signups(contract_id,status,queue_position);
"""

FEED_SCHEMA = """
CREATE TABLE IF NOT EXISTS feed_posts(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  legacy_news_id INTEGER UNIQUE,
  format TEXT NOT NULL DEFAULT 'short',
  status TEXT NOT NULL DEFAULT 'published',
  creator_user_id INTEGER NOT NULL,
  hidden_by_user_id INTEGER,
  hidden_reason TEXT,
  author_persona_id INTEGER,
  author_character_id INTEGER,
  storyline_id INTEGER,
  contract_id INTEGER,
  reply_to_post_id INTEGER,
  district_id TEXT,
  headline TEXT,
  lead TEXT,
  body TEXT NOT NULL,
  image_media_id TEXT,
  truth_status TEXT NOT NULL DEFAULT 'unknown',
  event_at REAL,
  published_at REAL,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feed_post_revisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  action TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  reason TEXT,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS feed_post_links(
  post_id INTEGER NOT NULL,
  linked_post_id INTEGER NOT NULL,
  relation TEXT NOT NULL DEFAULT 'related',
  PRIMARY KEY(post_id,linked_post_id,relation)
);
CREATE TABLE IF NOT EXISTS feed_comments(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  post_id INTEGER NOT NULL,
  parent_comment_id INTEGER,
  creator_user_id INTEGER NOT NULL,
  author_persona_id INTEGER,
  author_character_id INTEGER,
  body TEXT NOT NULL,
  created REAL NOT NULL,
  updated REAL NOT NULL,
  hidden_at REAL,
  hidden_by INTEGER,
  hidden_reason TEXT
);
CREATE INDEX IF NOT EXISTS idx_feed_posts_public ON feed_posts(status,published_at);
CREATE INDEX IF NOT EXISTS idx_feed_comments_post ON feed_comments(post_id,created);
CREATE INDEX IF NOT EXISTS idx_feed_revisions ON feed_post_revisions(post_id,created);
"""

OPERATIONS_SCHEMA = """
CREATE TABLE IF NOT EXISTS character_ledger(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  character_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  session_id INTEGER,
  contract_id INTEGER,
  category TEXT NOT NULL,
  delta_json TEXT NOT NULL DEFAULT '{}',
  before_json TEXT,
  after_json TEXT,
  reason TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS npc_templates(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  owner_user_id INTEGER NOT NULL,
  access TEXT NOT NULL DEFAULT 'private',
  name TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT '',
  data_json TEXT NOT NULL DEFAULT '{}',
  archived INTEGER NOT NULL DEFAULT 0,
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS nc_sessions(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  contract_id INTEGER,
  owner_user_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'preparing',
  round INTEGER NOT NULL DEFAULT 0,
  active_turn INTEGER NOT NULL DEFAULT 0,
  player_view_config TEXT NOT NULL DEFAULT '{}',
  notes TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL,
  updated REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS session_combatants(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  kind TEXT NOT NULL DEFAULT 'npc',
  character_id INTEGER,
  template_id INTEGER,
  name TEXT NOT NULL,
  initiative INTEGER NOT NULL DEFAULT 0,
  hp_current INTEGER NOT NULL DEFAULT 0,
  hp_max INTEGER NOT NULL DEFAULT 0,
  sp_head INTEGER NOT NULL DEFAULT 0,
  sp_head_max INTEGER NOT NULL DEFAULT 0,
  sp_body INTEGER NOT NULL DEFAULT 0,
  sp_body_max INTEGER NOT NULL DEFAULT 0,
  shield_current INTEGER NOT NULL DEFAULT 0,
  shield_max INTEGER NOT NULL DEFAULT 0,
  ammo_current INTEGER NOT NULL DEFAULT 0,
  ammo_max INTEGER NOT NULL DEFAULT 0,
  luck_current INTEGER NOT NULL DEFAULT 0,
  luck_max INTEGER NOT NULL DEFAULT 0,
  move INTEGER NOT NULL DEFAULT 0,
  conditions_json TEXT NOT NULL DEFAULT '[]',
  injuries_json TEXT NOT NULL DEFAULT '[]',
  death_penalty INTEGER NOT NULL DEFAULT 0,
  visible INTEGER NOT NULL DEFAULT 1,
  secret_json TEXT NOT NULL DEFAULT '{}',
  sort_order INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS session_activity(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  actor_user_id INTEGER NOT NULL,
  combatant_id INTEGER,
  event_type TEXT NOT NULL,
  before_json TEXT,
  after_json TEXT,
  note TEXT NOT NULL DEFAULT '',
  created REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_character_ledger ON character_ledger(character_id,created);
CREATE INDEX IF NOT EXISTS idx_sessions_owner ON nc_sessions(owner_user_id,status,updated);
CREATE INDEX IF NOT EXISTS idx_session_combatants ON session_combatants(session_id,sort_order);
CREATE INDEX IF NOT EXISTS idx_session_activity ON session_activity(session_id,created);
"""

NOTIFICATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS notifications(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL,
  event_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '',
  link TEXT,
  read_at REAL,
  created REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vk_oauth_states(
  state TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL,
  expires REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS vk_outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_key TEXT UNIQUE NOT NULL,
  event_type TEXT NOT NULL,
  contract_id INTEGER,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',
  attempts INTEGER NOT NULL DEFAULT 0,
  next_attempt_at REAL,
  last_error TEXT,
  created REAL NOT NULL,
  sent_at REAL
);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id,read_at,created);
CREATE INDEX IF NOT EXISTS idx_vk_outbox_pending ON vk_outbox(status,next_attempt_at);
"""

ACCOUNT_ROLES = {'player', 'gm', 'admin'}
MIGRATION_ACCOUNT_ROLES = 1
MIGRATION_NETWORK_CORE = 2
MIGRATION_CITY_FEED = 3
MIGRATION_OPERATIONS = 4
MIGRATION_NOTIFICATIONS = 5
MIGRATION_TACTICAL_PROFILES = 6
DB_BACKUP_LIMIT = 5
_RATE_LIMIT_BUCKETS = {}
_RATE_LIMIT_LOCK = threading.Lock()


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


def enforce_rate_limit(identifier, limit, window):
    now = time.time()
    with _RATE_LIMIT_LOCK:
        bucket = [stamp for stamp in _RATE_LIMIT_BUCKETS.get(identifier, []) if stamp > now - window]
        if len(bucket) >= limit:
            raise ApiError(429, 'Слишком много запросов; попробуйте позже')
        bucket.append(now)
        _RATE_LIMIT_BUCKETS[identifier] = bucket
        if len(_RATE_LIMIT_BUCKETS) > 5000:
            for key in list(_RATE_LIMIT_BUCKETS)[:1000]:
                if not _RATE_LIMIT_BUCKETS[key] or _RATE_LIMIT_BUCKETS[key][-1] <= now - 3600:
                    _RATE_LIMIT_BUCKETS.pop(key, None)


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


def ensure_column(conn, table, name, definition):
    columns = {row['name'] for row in conn.execute(f'PRAGMA table_info({table})')}
    if name not in columns:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')


def apply_schema_migrations(conn, make_backup=True):
    """Idempotently upgrade legacy databases without resetting campaign data."""
    conn.execute('CREATE TABLE IF NOT EXISTS schema_migrations('
                 'version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied REAL NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS account_role_audit('
                 'id INTEGER PRIMARY KEY AUTOINCREMENT, target_user_id INTEGER NOT NULL, '
                 'actor_user_id INTEGER, role_before TEXT NOT NULL, role_after TEXT NOT NULL, '
                 'reason TEXT NOT NULL, created REAL NOT NULL)')
    applied = {row['version'] for row in conn.execute('SELECT version FROM schema_migrations')}
    migrations = [
        (MIGRATION_ACCOUNT_ROLES, 'account roles and privacy foundation'),
        (MIGRATION_NETWORK_CORE, 'personas storylines and contracts'),
        (MIGRATION_CITY_FEED, 'city feed posts comments and revisions'),
        (MIGRATION_OPERATIONS, 'character ledger and session operations'),
        (MIGRATION_NOTIFICATIONS, 'site notifications and VK outbox'),
        (MIGRATION_TACTICAL_PROFILES, 'profile media and tactical session resources'),
    ]
    pending = [version for version, _ in migrations if version not in applied]
    if make_backup and pending:
        backup_database(conn, f'v{min(pending)}-v{max(pending)}')
    if MIGRATION_ACCOUNT_ROLES not in applied:
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
    if MIGRATION_NETWORK_CORE not in applied:
        conn.executescript(NETWORK_SCHEMA)
    if MIGRATION_CITY_FEED not in applied:
        conn.executescript(FEED_SCHEMA)
    if MIGRATION_OPERATIONS not in applied:
        conn.executescript(OPERATIONS_SCHEMA)
    if MIGRATION_NOTIFICATIONS not in applied:
        conn.executescript(NOTIFICATION_SCHEMA)
    if MIGRATION_TACTICAL_PROFILES not in applied:
        ensure_column(conn, 'users', 'avatar_media_id', 'TEXT')
        ensure_column(conn, 'npc_templates', 'archived', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'sp_head_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'sp_body_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'shield_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'ammo_max', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'luck_current', 'INTEGER NOT NULL DEFAULT 0')
        ensure_column(conn, 'session_combatants', 'luck_max', 'INTEGER NOT NULL DEFAULT 0')
    # Re-run additive CREATE IF NOT EXISTS blocks so patch-level tables added to an
    # already-applied migration remain safe during development and rolling deploys.
    conn.executescript(NETWORK_SCHEMA)
    conn.executescript(FEED_SCHEMA)
    conn.executescript(OPERATIONS_SCHEMA)
    conn.executescript(NOTIFICATION_SCHEMA)
    # Recover safely if a rolling/patch deployment recorded the migration before
    # every additive column reached a particular database.
    ensure_column(conn, 'users', 'avatar_media_id', 'TEXT')
    ensure_column(conn, 'npc_templates', 'archived', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'sp_head_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'sp_body_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'shield_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'ammo_max', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'luck_current', 'INTEGER NOT NULL DEFAULT 0')
    ensure_column(conn, 'session_combatants', 'luck_max', 'INTEGER NOT NULL DEFAULT 0')
    conn.execute('UPDATE session_combatants SET sp_head_max=sp_head '
                 'WHERE sp_head_max=0 AND sp_head>0')
    conn.execute('UPDATE session_combatants SET sp_body_max=sp_body '
                 'WHERE sp_body_max=0 AND sp_body>0')
    conn.execute('UPDATE session_combatants SET shield_max=shield_current '
                 'WHERE shield_max=0 AND shield_current>0')
    conn.execute('UPDATE session_combatants SET ammo_max=ammo_current '
                 'WHERE ammo_max=0 AND ammo_current>0')
    for version, name in migrations:
        if version not in applied:
            conn.execute(
                'INSERT INTO schema_migrations(version,name,applied) VALUES(?,?,?)',
                (version, name, time.time()))
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


PERSONA_ACCESS = {'private', 'shared', 'system'}
PERSONA_KINDS = {'person', 'organization', 'outlet', 'gang', 'corporation', 'government', 'anonymous'}
PERSONA_STATUSES = {'active', 'missing', 'dead', 'dissolved', 'destroyed', 'archived'}
STORYLINE_STATUSES = {'active', 'paused', 'completed', 'archived'}
CONTRACT_STATUSES = {'draft', 'open', 'crew_full', 'in_progress', 'completed', 'failed', 'cancelled', 'archived'}
CONTRACT_REWARD_MODES = {'exact', 'range', 'negotiable', 'hidden'}
CONTRACT_RISKS = {'low', 'moderate', 'high', 'extreme', 'classified'}
FEED_FORMATS = {'short', 'article', 'blog', 'bulletin', 'statement', 'rumor'}
FEED_TRUTH = {'true', 'partially_true', 'false', 'propaganda', 'unknown'}
SESSION_VIEW_DEFAULTS = {
    'show_initiative': True,
    'show_ally_hp': True,
    'show_armor': True,
    'show_shield': True,
    'show_ammo': False,
    'show_move': True,
    'show_luck': True,
    'show_conditions': True,
    'show_injuries': True,
}


def parse_json_object(value, default=None):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or '{}')
        return parsed if isinstance(parsed, dict) else (default or {})
    except (TypeError, ValueError):
        return default or {}


def parse_json_list(value):
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value or '[]')
        return parsed if isinstance(parsed, list) else []
    except (TypeError, ValueError):
        return []


def session_view_config(value):
    raw = parse_json_object(value)
    return {
        key: raw[key] if isinstance(raw.get(key), bool) else default
        for key, default in SESSION_VIEW_DEFAULTS.items()
    }


def clean_npc_template_input(body, existing=None):
    base = dict(existing or {})
    name = str((body or {}).get('name', base.get('name', '')) or '').strip()[:120]
    if not name:
        raise ApiError(400, 'NPC template нужно имя')
    access = str((body or {}).get('access', base.get('access', 'private'))).lower()
    if access not in ('private', 'shared'):
        raise ApiError(400, 'Некорректный NPC template')
    existing_data = parse_json_object(base.get('data_json'))
    source = (body or {}).get('data')
    if source is None:
        source = existing_data
    if not isinstance(source, dict):
        raise ApiError(400, 'Некорректный NPC template')
    data = {**existing_data, **source}
    provided_keys = set(data)
    numeric = ('initiative', 'hp_current', 'hp_max', 'sp_head', 'sp_head_max',
               'sp_body', 'sp_body_max', 'shield_current', 'shield_max', 'ammo_current', 'ammo_max',
               'luck_current', 'luck_max', 'move', 'death_penalty')
    for key in numeric:
        value = _num(data.get(key)) or 0
        data[key] = max(-1000, min(1000, value)) if key == 'initiative' else max(0, value)
    for current_key, maximum_key in (('hp_current', 'hp_max'),
                                     ('sp_head', 'sp_head_max'),
                                     ('sp_body', 'sp_body_max'),
                                     ('shield_current', 'shield_max'),
                                     ('ammo_current', 'ammo_max'),
                                     ('luck_current', 'luck_max')):
        maximum = data[maximum_key]
        if current_key not in provided_keys and maximum:
            data[current_key] = maximum
        if not maximum and data[current_key]:
            maximum = data[current_key]
            data[maximum_key] = maximum
        if maximum:
            data[current_key] = min(maximum, data[current_key])
    for key in ('conditions', 'injuries'):
        values = data.get(key) or []
        if not isinstance(values, list):
            raise ApiError(400, 'Некорректный NPC template')
        data[key] = [str(value)[:120] for value in values[:20]]
    secret = data.get('secret') or {}
    if not isinstance(secret, dict):
        raise ApiError(400, 'Некорректный NPC template')
    data['secret'] = secret
    data['visible'] = data.get('visible') is not False
    if len(json.dumps(data, ensure_ascii=False)) > 20000:
        raise ApiError(400, 'Некорректный NPC template')
    return {
        'name': name,
        'access': access,
        'role': str((body or {}).get('role', base.get('role', '')) or '')[:80],
        'data': data,
    }


def ensure_system_persona(conn, handle, display_name, kind):
    row = conn.execute('SELECT * FROM personas WHERE handle=? COLLATE NOCASE', (handle,)).fetchone()
    if row:
        return row['id']
    owner = conn.execute('SELECT id FROM users WHERE id=1').fetchone()
    if not owner:
        owner = conn.execute('SELECT id FROM users ORDER BY id LIMIT 1').fetchone()
    if not owner:
        return None
    now = time.time()
    cur = conn.execute(
        "INSERT INTO personas(owner_user_id,access,kind,handle,display_name,short_bio,"
        "public_bio,status,created,updated) VALUES(?,'system',?,?,?,?,?,'active',?,?)",
        (owner['id'], kind, handle, display_name,
         'Imported NC//NET archive relay.',
         'System relay preserving transmissions from the legacy network.', now, now))
    return cur.lastrowid


def migrate_legacy_network_content(conn):
    """Copy legacy Jobs/News once; old tables remain available as compatibility APIs."""
    contract_persona = ensure_system_persona(
        conn, 'ncnet-contract-archive', 'NC//NET Contract Archive', 'anonymous')
    feed_persona = ensure_system_persona(
        conn, 'ncnet-city-archive', 'NC//NET City Archive', 'outlet')
    if contract_persona:
        jobs = conn.execute('SELECT * FROM jobs ORDER BY id').fetchall()
        for job in jobs:
            exists = conn.execute('SELECT id FROM contracts WHERE legacy_job_id=?', (job['id'],)).fetchone()
            if exists:
                continue
            now = time.time()
            status = 'open' if job['status'] == 'open' else 'archived'
            cur = conn.execute(
                'INSERT INTO contracts(legacy_job_id,owner_user_id,status,title,teaser,'
                'public_brief,scheduled_at,crew_capacity,service_format,created,updated) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (job['id'], job['author_id'], status, job['title'],
                 str(job['description'] or '')[:280], job['description'], None,
                 max(0, int(job['slots'] or 0)), job['system'] or 'Cyberpunk RED',
                 job['created'], now))
            contract_id = cur.lastrowid
            conn.execute(
                "INSERT INTO contract_participants(contract_id,persona_id,role_key,role_label,"
                "visibility,note,sort_order) VALUES(?,?,'poster','Archive Relay','public','',0)",
                (contract_id, contract_persona))
            signups = conn.execute(
                'SELECT * FROM job_signups WHERE job_id=? ORDER BY created,id', (job['id'],)).fetchall()
            capacity = max(0, int(job['slots'] or 0))
            for index, signup in enumerate(signups):
                character_id = None
                if signup['char_name']:
                    chars = conn.execute('SELECT * FROM characters WHERE owner_id=?',
                                         (signup['user_id'],)).fetchall()
                    for char in chars:
                        if str(json.loads(char['data']).get('handle') or '') == signup['char_name']:
                            character_id = char['id']; break
                signup_status = 'crew' if capacity == 0 or index < capacity else 'waitlist'
                conn.execute(
                    'INSERT INTO contract_signups(contract_id,user_id,character_id,legacy_char_name,'
                    'status,queue_position,joined_at,updated) VALUES(?,?,?,?,?,?,?,?)',
                    (contract_id, signup['user_id'], character_id, signup['char_name'],
                     signup_status, index + 1, signup['created'], now))
    if feed_persona:
        news_rows = conn.execute('SELECT * FROM news ORDER BY id').fetchall()
        for news in news_rows:
            if conn.execute('SELECT id FROM feed_posts WHERE legacy_news_id=?',
                            (news['id'],)).fetchone():
                continue
            conn.execute(
                "INSERT INTO feed_posts(legacy_news_id,format,status,creator_user_id,"
                "author_persona_id,headline,lead,body,truth_status,event_at,published_at,created,updated) "
                "VALUES(?,'article','published',?,?,?,?,?,'unknown',?,?,?,?)",
                (news['id'], news['author_id'], feed_persona, news['title'], news['tag'],
                 news['body'], news['created'], news['created'], news['created'], news['created']))
    conn.commit()


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


def can_manage_persona(user, persona):
    if not user or not persona or not user_is_gm(user):
        return False
    if user_is_admin(user):
        return True
    access = persona['access']
    return access == 'shared' or (access == 'private' and persona['owner_user_id'] == user['id'])


def persona_payload(row, include_secret=False):
    payload = {
        'id': row['id'], 'owner_user_id': row['owner_user_id'],
        'access': row['access'], 'kind': row['kind'], 'handle': row['handle'],
        'display_name': row['display_name'], 'avatar_media_id': row['avatar_media_id'],
        'cover_media_id': row['cover_media_id'], 'accent_color': row['accent_color'],
        'short_bio': row['short_bio'], 'public_bio': row['public_bio'],
        'affiliation': row['affiliation'],
        'public_connections': parse_json_object(row['public_connections']),
        'status': row['status'], 'created': row['created'], 'updated': row['updated'],
    }
    if include_secret:
        payload.update({
            'secret_bio': row['secret_bio'], 'goals': row['goals'],
            'voice_notes': row['voice_notes'],
            'secret_connections': parse_json_object(row['secret_connections']),
        })
    return payload


def can_edit_storyline(conn, user, storyline):
    if not user or not storyline or not user_is_gm(user):
        return False
    if user_is_admin(user) or storyline['owner_user_id'] == user['id']:
        return True
    return bool(conn.execute(
        'SELECT 1 FROM storyline_collaborators WHERE storyline_id=? AND user_id=? AND can_edit=1',
        (storyline['id'], user['id'])).fetchone())


def can_edit_contract(conn, user, contract):
    if not user or not contract or not user_is_gm(user):
        return False
    if user_is_admin(user) or contract['owner_user_id'] == user['id']:
        return True
    if contract['storyline_id']:
        storyline = conn.execute('SELECT * FROM storylines WHERE id=?',
                                 (contract['storyline_id'],)).fetchone()
        return can_edit_storyline(conn, user, storyline)
    return False


def has_contract_classified_access(conn, user, contract):
    if can_edit_contract(conn, user, contract):
        return True
    if not user:
        return False
    return bool(conn.execute(
        "SELECT 1 FROM contract_signups WHERE contract_id=? AND user_id=? AND status='crew'",
        (contract['id'], user['id'])).fetchone())


def clean_persona_input(body, existing=None):
    base = dict(existing or {})
    get = lambda key, default='': body.get(key, base.get(key, default))
    handle = str(get('handle')).strip().lower()
    if not re.fullmatch(r'[a-z0-9_.\-]{3,40}', handle):
        raise ApiError(400, 'Handle персоны: 3–40 латинских символов, цифр или ._-')
    display_name = str(get('display_name')).strip()[:100]
    if not display_name:
        raise ApiError(400, 'Персоне нужно отображаемое имя')
    access = str(get('access', 'private')).lower()
    kind = str(get('kind', 'person')).lower()
    status = str(get('status', 'active')).lower()
    if access not in PERSONA_ACCESS or kind not in PERSONA_KINDS or status not in PERSONA_STATUSES:
        raise ApiError(400, 'Некорректный тип, доступ или статус персоны')
    accent = str(get('accent_color', '#00e5ff'))
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', accent):
        raise ApiError(400, 'Некорректный цвет персоны')
    return {
        'access': access, 'kind': kind, 'handle': handle,
        'display_name': display_name,
        'avatar_media_id': str(get('avatar_media_id'))[:64] or None,
        'cover_media_id': str(get('cover_media_id'))[:64] or None,
        'accent_color': accent.lower(),
        'short_bio': str(get('short_bio'))[:500],
        'public_bio': str(get('public_bio'))[:10000],
        'affiliation': str(get('affiliation'))[:200],
        'public_connections': json.dumps(parse_json_object(get('public_connections', {})), ensure_ascii=False),
        'status': status,
        'secret_bio': str(get('secret_bio'))[:10000],
        'goals': str(get('goals'))[:5000],
        'voice_notes': str(get('voice_notes'))[:5000],
        'secret_connections': json.dumps(parse_json_object(get('secret_connections', {})), ensure_ascii=False),
    }


def record_persona_audit(conn, persona_id, actor_id, action, before, after):
    conn.execute(
        'INSERT INTO persona_audit(persona_id,actor_user_id,action,before_json,after_json,created) '
        'VALUES(?,?,?,?,?,?)',
        (persona_id, actor_id, action,
         json.dumps(before, ensure_ascii=False) if before is not None else None,
         json.dumps(after, ensure_ascii=False) if after is not None else None,
         time.time()))


def record_feed_revision(conn, post_id, actor_id, action, before=None, after=None, reason=''):
    conn.execute(
        'INSERT INTO feed_post_revisions(post_id,actor_user_id,action,before_json,after_json,reason,created) '
        'VALUES(?,?,?,?,?,?,?)',
        (post_id, actor_id, action,
         json.dumps(before, ensure_ascii=False) if before is not None else None,
         json.dumps(after, ensure_ascii=False) if after is not None else None,
         str(reason or '')[:500] or None, time.time()))


def record_character_changes(conn, character_id, actor_user_id, before, after,
                             reason='Character sheet update', contract_id=None, session_id=None):
    tracked = {
        'cash': 'cash', 'roles': 'role', 'role': 'role', 'role_rank': 'role',
        'skills': 'skill', 'skill_pools': 'skill', 'stats': 'stat',
        'reputation': 'reputation', 'inventory': 'inventory',
        'cyberware': 'cyberware', 'armor': 'armor',
        'archived': 'status', 'public': 'status',
    }
    recorded = set()
    for key, category in tracked.items():
        if before.get(key) == after.get(key) or category in recorded:
            continue
        related = [name for name, value in tracked.items() if value == category]
        old_value = {name: before.get(name) for name in related}
        new_value = {name: after.get(name) for name in related}
        conn.execute(
            'INSERT INTO character_ledger(character_id,actor_user_id,session_id,contract_id,'
            'category,delta_json,before_json,after_json,reason,created) VALUES(?,?,?,?,?,?,?,?,?,?)',
            (character_id, actor_user_id, session_id, contract_id, category, '{}',
             json.dumps(old_value, ensure_ascii=False), json.dumps(new_value, ensure_ascii=False),
             str(reason or '')[:500], time.time()))
        recorded.add(category)


def add_notification(conn, user_id, event_type, title, body='', link=None):
    conn.execute(
        'INSERT INTO notifications(user_id,event_type,title,body,link,created) VALUES(?,?,?,?,?,?)',
        (user_id, str(event_type)[:60], str(title)[:180], str(body)[:1000],
         str(link)[:300] if link else None, time.time()))


def queue_vk_event(conn, event_key, event_type, contract_id, payload):
    conn.execute(
        "INSERT OR IGNORE INTO vk_outbox(event_key,event_type,contract_id,payload_json,status,created) "
        "VALUES(?,?,?,?, 'pending', ?)",
        (str(event_key)[:180], str(event_type)[:60], contract_id,
         json.dumps(payload, ensure_ascii=False), time.time()))


def vk_public_contract_message(conn, event):
    payload = parse_json_object(event['payload_json'])
    contract = conn.execute('SELECT * FROM contracts WHERE id=?',
                            (event['contract_id'],)).fetchone() if event['contract_id'] else None
    if not contract:
        return payload.get('title') or 'NC//NET update'
    poster = conn.execute(
        "SELECT p.display_name FROM contract_participants cp JOIN personas p ON p.id=cp.persona_id "
        "WHERE cp.contract_id=? AND cp.visibility='public' ORDER BY cp.sort_order LIMIT 1",
        (contract['id'],)).fetchone()
    reward = 'CLASSIFIED'
    if contract['reward_mode'] == 'exact' and contract['reward_exact'] is not None:
        reward = f"€$ {contract['reward_exact']:,.0f}"
    elif contract['reward_mode'] == 'range':
        reward = f"€$ {contract['reward_min'] or 0:,.0f}–{contract['reward_max'] or 0:,.0f}"
    elif contract['reward_mode'] == 'negotiable':
        reward = contract['reward_text'] or 'NEGOTIABLE'
    event_label = event['event_type'].replace('contract_', '').replace('_', ' ').upper()
    url = (os.environ.get('NCNET_PUBLIC_URL') or '').rstrip('/')
    link = f'{url}/#/contracts/{contract["id"]}' if url else f'#/contracts/{contract["id"]}'
    lines = [
        f'NC//NET // {event_label}', '', contract['title'],
        f'RELAY: {poster["display_name"] if poster else "NC//NET"}',
        f'DISTRICT: {contract["district_id"] or "CLASSIFIED"}',
        f'RISK: {contract["risk_level"].upper()}',
        f'REWARD: {reward}',
        f'CREW: {contract["crew_capacity"] or "UNLIMITED"}',
        f'CONNECTION WINDOW: {datetime.fromtimestamp(contract["scheduled_at"], MOSCOW).strftime("%Y-%m-%d %H:%M MSK") if contract["scheduled_at"] else "UNSCHEDULED"}',
    ]
    if contract['teaser']:
        lines.extend(['', contract['teaser']])
    if contract['cover_media_id'] and url:
        lines.extend(['', f'IMAGE: {url}/api/media/{contract["cover_media_id"]}'])
    lines.extend(['', link])
    return '\n'.join(lines)


def deliver_vk_outbox(conn, limit=20):
    token = os.environ.get('VK_COMMUNITY_TOKEN')
    peer_id = os.environ.get('VK_PEER_ID')
    if not token or not peer_id:
        return {'configured': False, 'sent': 0, 'failed': 0}
    version = os.environ.get('VK_API_VERSION', '5.199')
    rows = conn.execute(
        "SELECT * FROM vk_outbox WHERE status IN ('pending','failed') "
        'AND (next_attempt_at IS NULL OR next_attempt_at<=?) ORDER BY id LIMIT ?',
        (time.time(), max(1, min(100, int(limit))))).fetchall()
    sent = failed = 0
    for row in rows:
        params = {
            'access_token': token, 'v': version, 'peer_id': peer_id,
            'random_id': row['id'], 'message': vk_public_contract_message(conn, row),
        }
        try:
            request = Request('https://api.vk.com/method/messages.send',
                              data=urlencode(params).encode(), method='POST')
            response = json.loads(urlopen(request, timeout=15).read().decode())
            if response.get('error'):
                raise RuntimeError(response['error'].get('error_msg') or 'VK API error')
            conn.execute("UPDATE vk_outbox SET status='sent',attempts=attempts+1,sent_at=?,last_error=NULL WHERE id=?",
                         (time.time(), row['id']))
            sent += 1
        except (URLError, HTTPError, RuntimeError, ValueError) as error:
            attempts = row['attempts'] + 1
            delay = min(3600, 30 * (2 ** min(attempts, 6)))
            conn.execute("UPDATE vk_outbox SET status='failed',attempts=?,next_attempt_at=?,last_error=? WHERE id=?",
                         (attempts, time.time() + delay, str(error)[:500], row['id']))
            failed += 1
        conn.commit()
    return {'configured': True, 'sent': sent, 'failed': failed}


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
    migrate_legacy_network_content(conn)
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


def session_cookie(token, max_age=SESSION_TTL):
    secure = (os.environ.get('CBPR_SECURE_COOKIES', '').lower() in ('1','true','yes') or
              (os.environ.get('NCNET_PUBLIC_URL') or '').lower().startswith('https://'))
    parts = [f'sid={token}', 'Path=/', 'HttpOnly', 'SameSite=Lax', f'Max-Age={max_age}']
    if secure:
        parts.append('Secure')
    return '; '.join(parts)


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
MEDIA_KINDS = {
    'character_portrait', 'account_avatar', 'news_image', 'job_image',
    'persona_avatar', 'persona_cover', 'contract_image', 'feed_image',
}

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


def attach_network_media(conn, user_id, entity_type, entity_id, media_ids, allowed_kinds):
    desired = {str(value or '') for value in media_ids if value}
    validated = []
    for media_id in desired:
        media = conn.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
        if not media or media['kind'] not in allowed_kinds:
            raise ApiError(400, 'Недопустимое изображение NC//NET')
        already = media['attached_type'] == entity_type and media['attached_id'] == entity_id
        if not already and media['owner_id'] != user_id:
            raise ApiError(403, 'Изображение принадлежит другому аккаунту')
        if media['attached_type'] and not already:
            raise ApiError(409, 'Изображение уже прикреплено')
        validated.append(media_id)
    attached = conn.execute('SELECT * FROM media WHERE attached_type=? AND attached_id=?',
                            (entity_type, entity_id)).fetchall()
    for media in attached:
        if media['id'] not in desired:
            conn.execute('UPDATE media SET attached_type=NULL,attached_id=NULL WHERE id=?',
                         (media['id'],))
    for media_id in validated:
        conn.execute('UPDATE media SET attached_type=?,attached_id=? WHERE id=?',
                     (entity_type, entity_id, media_id))


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
    'Некорректная сумма': 'Invalid amount',
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
    'Handle персоны: 3–40 латинских символов, цифр или ._-': 'Persona Handle: 3–40 Latin letters, digits, or ._-',
    'Персоне нужно отображаемое имя': 'Persona display name is required',
    'Некорректный тип, доступ или статус персоны': 'Invalid Persona kind, access, or status',
    'Некорректный цвет персоны': 'Invalid Persona color',
    'Недопустимое изображение NC//NET': 'Invalid NC//NET image',
    'Изображение принадлежит другому аккаунту': 'Image belongs to another account',
    'VK OAuth не настроен': 'VK OAuth is not configured',
    'Некорректный или истёкший VK OAuth state': 'Invalid or expired VK OAuth state',
    'VK OAuth не вернул пользователя': 'VK OAuth did not return a user',
    'VK OAuth временно недоступен': 'VK OAuth is temporarily unavailable',
    'Только Admin создаёт системные персоны': 'Only an Admin can create System Personas',
    'Только Admin редактирует системные персоны': 'Only an Admin can edit System Personas',
    'Персона не найдена': 'Persona not found',
    'Нет права редактировать эту персону': 'You cannot edit this Persona',
    'Такой Handle персоны уже занят': 'That Persona Handle is already taken',
    'Нужно название сюжетной линии': 'Storyline title is required',
    'Некорректный статус сюжетной линии': 'Invalid Storyline status',
    'Сюжетная линия не найдена': 'Storyline not found',
    'Нет права редактировать эту сюжетную линию': 'You cannot edit this Storyline',
    'Некорректная сюжетная линия': 'Invalid Storyline',
    'Событие хронологии не может быть пустым': 'Timeline event cannot be empty',
    'Контракту нужно название': 'Contract title is required',
    'Некорректный статус, риск или награда контракта': 'Invalid Contract status, risk, or reward',
    'Контракт не найден': 'Contract not found',
    'Нет права редактировать этот контракт': 'You cannot edit this Contract',
    'Контракт недоступен для записи': 'Contract is not open for signup',
    'Завершённый контракт хранит неизменяемый состав': 'A finished Contract preserves its historical Crew',
    'Этот персонаж уже записан': 'This Character is already signed up',
    'Запись на контракт не найдена': 'Contract signup not found',
    'Размер команды меньше уже записанного Crew': 'Crew Capacity is below the current Crew size',
    'Архивное досье доступно только для чтения': 'Archived Dossier is read-only',
    'Архивное досье нельзя записать на контракт': 'Archived Dossier cannot join a Contract',
    'Архивное досье нельзя использовать как автора': 'Archived Dossier cannot publish content',
    'Aftermath уже опубликован или контракт не активен': 'Aftermath is already published or the Contract is not active',
    'Недоступный NPC template': 'Unavailable NPC template',
    'NPC template не найден': 'NPC template not found',
    'Нет права редактировать NPC template': 'You cannot edit this NPC template',
    'Некорректный NPC template': 'Invalid NPC template',
    'NPC template нужно имя': 'NPC template requires a name',
    'Некорректные данные участника сессии': 'Invalid session combatant data',
    'Участник сессии не найден': 'Session combatant not found',
    'Недоступная персона в контракте': 'Unavailable Persona in Contract',
    'Недоступная сюжетная линия': 'Unavailable Storyline',
    'Выберите одного автора публикации': 'Choose exactly one post author',
    'Некорректный формат публикации': 'Invalid post format',
    'Публикации нужен текст и, для длинного формата, заголовок': 'Post body and, for long formats, headline are required',
    'Публикация не найдена': 'Post not found',
    'Нет права редактировать эту публикацию': 'You cannot edit this post',
    'Некорректная публикация': 'Invalid post',
    'Укажите причину скрытия': 'Provide a reason for hiding this content',
    'Комментарий не может быть пустым': 'Comment cannot be empty',
    'Комментарий не найден': 'Comment not found',
    'Недоступная персона-автор': 'Unavailable author Persona',
    'Родительский комментарий не найден': 'Parent comment not found',
    'NPC template нужно имя': 'NPC template name is required',
    'Некорректный NPC template': 'Invalid NPC template',
    'Сессия не найдена': 'Session not found',
    'Нет права редактировать сессию': 'You cannot edit this Session',
    'Некорректный статус сессии': 'Invalid Session status',
    'Участнику сессии нужно имя': 'Session combatant name is required',
    'Нет права редактировать участника': 'You cannot edit this combatant',
    'Нет доступа к экрану сессии': 'You cannot access this Session view',
    'Нет доступа к контракту сессии': 'You cannot access the Session Contract',
    'Нет права завершить контракт': 'You cannot complete this Contract',
    'Результат контракта: completed/failed': 'Contract result must be completed or failed',
    'Выберите доступную персону для Aftermath': 'Choose an available Persona for the Aftermath',
    'Слишком много запросов; попробуйте позже': 'Too many requests; try again later',
    'Недопустимый источник запроса': 'Invalid request origin',
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
        ('Некорректное число в поле контракта:', 'Invalid number in Contract field:'),
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

    def rate_limit(self, scope, limit, window, user_id=None):
        identity = str(user_id) if user_id is not None else getattr(self, 'client_address', ('local',))[0]
        enforce_rate_limit(f'{scope}:{identity}', limit, window)

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

    def verify_request_origin(self):
        origin = self.headers.get('Origin')
        if not origin:
            return
        expected = self.headers.get('X-Forwarded-Host') or self.headers.get('Host') or ''
        if urlparse(origin).netloc.lower() != expected.lower():
            raise ApiError(403, 'Недопустимый источник запроса')

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
                if method in ('POST', 'PUT', 'DELETE'):
                    self.verify_request_origin()
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
        self.rate_limit('register', 5, 300)
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
            session_cookie(token)])

    def api_login(self, conn, qs, m, body):
        self.rate_limit('login', 12, 60)
        username = str(body.get('username') or '').strip().lower()
        password = str(body.get('password') or '')
        u = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not u or not verify_password(password, u['pass_hash']):
            raise ApiError(401, 'Неверный логин или пароль')
        token = create_session(conn, u['id'])
        self.send_json(self.me_payload(u), cookies=[
            session_cookie(token)])

    def api_logout(self, conn, qs, m, body):
        tok = self.cookies().get('sid')
        if tok:
            conn.execute('DELETE FROM sessions WHERE token=?', (tok,))
            conn.commit()
        self.send_json({'ok': True}, cookies=[session_cookie('', 0)])

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
            'avatar_media_id': _row_value(u, 'avatar_media_id'),
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
        if 'avatar_media_id' in (body or {}):
            avatar_media_id = str(body.get('avatar_media_id') or '')[:64] or None
            attach_network_media(conn, u['id'], 'account', u['id'],
                                 [avatar_media_id], {'account_avatar'})
            conn.execute('UPDATE users SET avatar_media_id=? WHERE id=?',
                         (avatar_media_id, u['id']))
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

    def api_gm_users(self, conn, qs, m, body):
        self.require_gm(conn)
        rows = conn.execute(
            "SELECT id,username,display_name,account_role FROM users "
            "WHERE account_role IN ('gm','admin') ORDER BY display_name").fetchall()
        self.send_json({'users': [dict(row) for row in rows]})

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

    # ------------------------------------------------------------ NC//NET notifications / VK

    def api_notifications(self, conn, qs, m, body):
        user = self.require_user(conn)
        rows = conn.execute(
            'SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 100',
            (user['id'],)).fetchall()
        self.send_json({'notifications': [dict(row) for row in rows],
                        'unread': sum(1 for row in rows if not row['read_at'])})

    def api_notification_read(self, conn, qs, m, body):
        user = self.require_user(conn)
        conn.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?',
                     (time.time(), int(m.group(1)), user['id']))
        conn.commit(); self.send_json({'ok': True})

    def api_admin_vk_status(self, conn, qs, m, body):
        self.require_admin(conn)
        counts = {row['status']: row['n'] for row in conn.execute(
            'SELECT status,COUNT(*) n FROM vk_outbox GROUP BY status').fetchall()}
        self.send_json({'configured': bool(os.environ.get('VK_COMMUNITY_TOKEN') and os.environ.get('VK_PEER_ID')),
                        'counts': counts, 'peer_id': bool(os.environ.get('VK_PEER_ID'))})

    def api_admin_vk_flush(self, conn, qs, m, body):
        self.require_admin(conn)
        self.send_json(deliver_vk_outbox(conn, _num((body or {}).get('limit')) or 20))

    def api_vk_oauth_start(self, conn, qs, m, body):
        user = self.require_user(conn)
        client_id = os.environ.get('VK_CLIENT_ID')
        redirect_uri = os.environ.get('VK_REDIRECT_URI')
        if not client_id or not redirect_uri:
            raise ApiError(503, 'VK OAuth не настроен')
        state = secrets.token_urlsafe(32)
        conn.execute('INSERT INTO vk_oauth_states(state,user_id,expires) VALUES(?,?,?)',
                     (state, user['id'], time.time() + 900))
        conn.execute('DELETE FROM vk_oauth_states WHERE expires<?', (time.time(),))
        conn.commit()
        query = urlencode({'client_id': client_id, 'redirect_uri': redirect_uri,
                           'display': 'page', 'scope': 0, 'response_type': 'code',
                           'v': os.environ.get('VK_API_VERSION', '5.199'), 'state': state})
        self.send_json({'url': 'https://oauth.vk.com/authorize?' + query})

    def api_vk_oauth_callback(self, conn, qs, m, body):
        state = q1(qs.get('state')); code = q1(qs.get('code'))
        record = conn.execute('SELECT * FROM vk_oauth_states WHERE state=? AND expires>?',
                              (state, time.time())).fetchone()
        if not record or not code:
            raise ApiError(400, 'Некорректный или истёкший VK OAuth state')
        client_id = os.environ.get('VK_CLIENT_ID'); secret = os.environ.get('VK_CLIENT_SECRET')
        redirect_uri = os.environ.get('VK_REDIRECT_URI')
        if not client_id or not secret or not redirect_uri:
            raise ApiError(503, 'VK OAuth не настроен')
        query = urlencode({'client_id': client_id, 'client_secret': secret,
                           'redirect_uri': redirect_uri, 'code': code})
        try:
            response = json.loads(urlopen('https://oauth.vk.com/access_token?' + query, timeout=15).read().decode())
        except (URLError, HTTPError, ValueError) as error:
            raise ApiError(502, 'VK OAuth временно недоступен')
        vk_user_id = response.get('user_id')
        if not vk_user_id:
            raise ApiError(400, 'VK OAuth не вернул пользователя')
        conn.execute('UPDATE users SET vk_user_id=?,vk_linked_at=? WHERE id=?',
                     (str(vk_user_id), time.time(), record['user_id']))
        conn.execute('DELETE FROM vk_oauth_states WHERE state=?', (state,))
        conn.commit(); self.send_json({'ok': True, 'vk_user_id': str(vk_user_id)})

    # ------------------------------------------------------------ NC//NET personas

    def api_personas(self, conn, qs, m, body):
        user = self.current_user(conn)
        manage = q1(qs.get('manage')) == '1' and user_is_gm(user)
        if manage and user_is_admin(user):
            rows = conn.execute('SELECT * FROM personas ORDER BY updated DESC').fetchall()
        elif manage:
            rows = conn.execute(
                "SELECT * FROM personas WHERE access IN ('shared','system') OR owner_user_id=? "
                'ORDER BY updated DESC', (user['id'],)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM personas WHERE access IN ('shared','system') AND status!='archived' "
                'ORDER BY updated DESC').fetchall()
        self.send_json({'personas': [
            {**persona_payload(row, manage and can_manage_persona(user, row)),
             'can_edit': can_manage_persona(user, row)} for row in rows
        ]})

    def api_persona_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        data = clean_persona_input(body or {})
        if data['access'] == 'system' and not user_is_admin(user):
            raise ApiError(403, 'Только Admin создаёт системные персоны')
        now = time.time()
        columns = list(data)
        try:
            cur = conn.execute(
                f"INSERT INTO personas(owner_user_id,{','.join(columns)},created,updated) "
                f"VALUES(? ,{','.join('?' for _ in columns)},?,?)",
                (user['id'], *(data[key] for key in columns), now, now))
        except sqlite3.IntegrityError:
            raise ApiError(409, 'Такой Handle персоны уже занят')
        row = conn.execute('SELECT * FROM personas WHERE id=?', (cur.lastrowid,)).fetchone()
        attach_network_media(conn, user['id'], 'persona', row['id'],
                             [row['avatar_media_id'], row['cover_media_id']],
                             {'persona_avatar', 'persona_cover'})
        record_persona_audit(conn, row['id'], user['id'], 'create', None,
                             persona_payload(row, True))
        conn.commit()
        self.send_json(persona_payload(row, True), status=201)

    def api_persona_detail(self, conn, qs, m, body):
        row = conn.execute('SELECT * FROM personas WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Персона не найдена')
        user = self.current_user(conn)
        can_edit = can_manage_persona(user, row)
        if row['access'] == 'private' and not can_edit:
            raise ApiError(404, 'Персона не найдена')
        payload = persona_payload(row, can_edit)
        payload['can_edit'] = can_edit
        contract_rows = conn.execute(
            'SELECT DISTINCT c.id,c.title,c.status,c.district_id FROM contracts c '
            'JOIN contract_participants cp ON cp.contract_id=c.id WHERE cp.persona_id=? '
            "AND (cp.visibility='public' OR ?) AND c.status!='draft' ORDER BY c.updated DESC LIMIT 50",
            (row['id'], 1 if can_edit else 0)).fetchall()
        post_rows = conn.execute(
            "SELECT id,headline,body,format,published_at FROM feed_posts "
            "WHERE author_persona_id=? AND (status='published' OR ?) ORDER BY created DESC LIMIT 50",
            (row['id'], 1 if can_edit else 0)).fetchall()
        payload['contracts'] = [dict(item) for item in contract_rows]
        payload['posts'] = [dict(item) for item in post_rows]
        if can_edit:
            audit = conn.execute(
                'SELECT a.*,u.display_name actor FROM persona_audit a '
                'JOIN users u ON u.id=a.actor_user_id WHERE persona_id=? '
                'ORDER BY a.id DESC LIMIT 100', (row['id'],)).fetchall()
            payload['audit'] = [dict(item) for item in audit]
        self.send_json(payload)

    def api_persona_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM personas WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Персона не найдена')
        if not can_manage_persona(user, row):
            raise ApiError(403, 'Нет права редактировать эту персону')
        data = clean_persona_input(body or {}, dict(row))
        if data['access'] == 'system' and not user_is_admin(user):
            raise ApiError(403, 'Только Admin редактирует системные персоны')
        before = persona_payload(row, True)
        assignments = ','.join(f'{key}=?' for key in data)
        try:
            conn.execute(f'UPDATE personas SET {assignments},updated=? WHERE id=?',
                         (*(data[key] for key in data), time.time(), row['id']))
        except sqlite3.IntegrityError:
            raise ApiError(409, 'Такой Handle персоны уже занят')
        updated = conn.execute('SELECT * FROM personas WHERE id=?', (row['id'],)).fetchone()
        attach_network_media(conn, user['id'], 'persona', row['id'],
                             [updated['avatar_media_id'], updated['cover_media_id']],
                             {'persona_avatar', 'persona_cover'})
        record_persona_audit(conn, row['id'], user['id'], 'update', before,
                             persona_payload(updated, True))
        conn.commit()
        self.send_json(persona_payload(updated, True))

    def api_persona_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM personas WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Персона не найдена')
        if not can_manage_persona(user, row):
            raise ApiError(403, 'Нет права редактировать эту персону')
        before = persona_payload(row, True)
        conn.execute("UPDATE personas SET status='archived',updated=? WHERE id=?",
                     (time.time(), row['id']))
        updated = conn.execute('SELECT * FROM personas WHERE id=?', (row['id'],)).fetchone()
        record_persona_audit(conn, row['id'], user['id'], 'archive', before,
                             persona_payload(updated, True))
        conn.commit()
        self.send_json({'ok': True})

    # ------------------------------------------------------------ NC//NET storylines

    def storyline_payload(self, conn, row, user):
        editable = can_edit_storyline(conn, user, row)
        collaborators = conn.execute(
            'SELECT u.id,u.username,u.display_name,c.can_edit FROM storyline_collaborators c '
            'JOIN users u ON u.id=c.user_id WHERE c.storyline_id=? ORDER BY u.display_name',
            (row['id'],)).fetchall()
        payload = {
            'id': row['id'], 'owner_user_id': row['owner_user_id'],
            'title': row['title'], 'code_name': row['code_name'],
            'public_summary': row['public_summary'], 'status': row['status'],
            'created': row['created'], 'updated': row['updated'],
            'can_edit': editable,
        }
        if editable:
            payload['private_summary'] = row['private_summary']
            payload['collaborators'] = [dict(item) for item in collaborators]
        return payload

    def api_storylines(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute('SELECT * FROM storylines ORDER BY updated DESC').fetchall()
        self.send_json({'storylines': [self.storyline_payload(conn, row, user) for row in rows
                                       if row['status'] != 'archived' or can_edit_storyline(conn, user, row)]})

    def api_storyline_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        title = str((body or {}).get('title') or '').strip()[:160]
        if not title:
            raise ApiError(400, 'Нужно название сюжетной линии')
        status = str((body or {}).get('status') or 'active')
        if status not in STORYLINE_STATUSES:
            raise ApiError(400, 'Некорректный статус сюжетной линии')
        now = time.time()
        cur = conn.execute(
            'INSERT INTO storylines(owner_user_id,title,code_name,public_summary,private_summary,'
            'status,created,updated) VALUES(?,?,?,?,?,?,?,?)',
            (user['id'], title, str((body or {}).get('code_name') or '')[:100],
             str((body or {}).get('public_summary') or '')[:5000],
             str((body or {}).get('private_summary') or '')[:10000], status, now, now))
        for uid in {int(value) for value in ((body or {}).get('collaborator_ids') or []) if str(value).isdigit()}:
            candidate = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
            if candidate and user_is_gm(candidate) and uid != user['id']:
                conn.execute('INSERT OR IGNORE INTO storyline_collaborators(storyline_id,user_id,can_edit) VALUES(?,?,1)',
                             (cur.lastrowid, uid))
        conn.commit()
        row = conn.execute('SELECT * FROM storylines WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.storyline_payload(conn, row, user), status=201)

    def api_storyline_detail(self, conn, qs, m, body):
        row = conn.execute('SELECT * FROM storylines WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Сюжетная линия не найдена')
        user = self.current_user(conn)
        payload = self.storyline_payload(conn, row, user)
        timeline = conn.execute(
            'SELECT * FROM storyline_timeline WHERE storyline_id=? ORDER BY event_at,created',
            (row['id'],)).fetchall()
        payload['timeline'] = [{
            'id': item['id'], 'event_at': item['event_at'],
            'public_text': item['public_text'],
            'private_text': item['private_text'] if payload['can_edit'] else None,
            'contract_id': item['contract_id'], 'feed_post_id': item['feed_post_id'],
        } for item in timeline]
        self.send_json(payload)

    def api_storyline_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM storylines WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Сюжетная линия не найдена')
        if not can_edit_storyline(conn, user, row):
            raise ApiError(403, 'Нет права редактировать эту сюжетную линию')
        title = str((body or {}).get('title', row['title']) or '').strip()[:160]
        status = str((body or {}).get('status', row['status']))
        if not title or status not in STORYLINE_STATUSES:
            raise ApiError(400, 'Некорректная сюжетная линия')
        conn.execute(
            'UPDATE storylines SET title=?,code_name=?,public_summary=?,private_summary=?,status=?,updated=? WHERE id=?',
            (title, str((body or {}).get('code_name', row['code_name']))[:100],
             str((body or {}).get('public_summary', row['public_summary']))[:5000],
             str((body or {}).get('private_summary', row['private_summary']))[:10000],
             status, time.time(), row['id']))
        if 'collaborator_ids' in (body or {}) and (row['owner_user_id'] == user['id'] or user_is_admin(user)):
            ids = {int(value) for value in ((body or {}).get('collaborator_ids') or [])
                   if str(value).isdigit() and int(value) != row['owner_user_id']}
            conn.execute('DELETE FROM storyline_collaborators WHERE storyline_id=?', (row['id'],))
            for uid in ids:
                candidate = conn.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
                if candidate and user_is_gm(candidate):
                    conn.execute('INSERT INTO storyline_collaborators(storyline_id,user_id,can_edit) VALUES(?,?,1)',
                                 (row['id'], uid))
        conn.commit()
        updated = conn.execute('SELECT * FROM storylines WHERE id=?', (row['id'],)).fetchone()
        self.send_json(self.storyline_payload(conn, updated, user))

    def api_storyline_timeline_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM storylines WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row or not can_edit_storyline(conn, user, row):
            raise ApiError(403, 'Нет права редактировать эту сюжетную линию')
        public_text = str((body or {}).get('public_text') or '')[:5000] or None
        private_text = str((body or {}).get('private_text') or '')[:10000]
        if not public_text and not private_text:
            raise ApiError(400, 'Событие хронологии не может быть пустым')
        cur = conn.execute(
            'INSERT INTO storyline_timeline(storyline_id,event_at,public_text,private_text,contract_id,'
            'feed_post_id,created_by,created) VALUES(?,?,?,?,?,?,?,?)',
            (row['id'], (body or {}).get('event_at'), public_text, private_text,
             _num((body or {}).get('contract_id')), _num((body or {}).get('feed_post_id')),
             user['id'], time.time()))
        conn.execute('UPDATE storylines SET updated=? WHERE id=?', (time.time(), row['id']))
        conn.commit()
        self.send_json({'id': cur.lastrowid}, status=201)

    # ------------------------------------------------------------ NC//NET contracts

    def contract_payload(self, conn, row, user):
        can_edit = can_edit_contract(conn, user, row)
        classified = has_contract_classified_access(conn, user, row)
        participant_rows = conn.execute(
            'SELECT cp.*,p.handle,p.display_name,p.kind,p.avatar_media_id,p.accent_color '
            'FROM contract_participants cp JOIN personas p ON p.id=cp.persona_id '
            'WHERE cp.contract_id=? ORDER BY cp.sort_order,cp.id', (row['id'],)).fetchall()
        signups = conn.execute(
            'SELECT s.*,u.display_name user_name,u.show_display_name signup_show_name,c.data character_data FROM contract_signups s '
            'JOIN users u ON u.id=s.user_id LEFT JOIN characters c ON c.id=s.character_id '
            "WHERE s.contract_id=? AND s.status IN ('crew','waitlist') "
            'ORDER BY CASE s.status WHEN \'crew\' THEN 0 ELSE 1 END,s.queue_position,s.joined_at',
            (row['id'],)).fetchall()
        signup_payload = []
        for signup in signups:
            character = parse_json_object(signup['character_data']) if signup['character_data'] else {}
            signup_payload.append({
                'id': signup['id'], 'user_id': signup['user_id'],
                'character_id': signup['character_id'],
                'character_name': character.get('handle') or signup['legacy_char_name'] or 'Unknown',
                'status': signup['status'], 'queue_position': signup['queue_position'],
                'joined_at': signup['joined_at'],
                'account_name': signup['user_name'] if (can_edit or bool(signup['signup_show_name'])) else None,
            })
        owner = conn.execute('SELECT * FROM users WHERE id=?', (row['owner_user_id'],)).fetchone()
        active_session = conn.execute(
            "SELECT id,status FROM nc_sessions WHERE contract_id=? AND status IN ('preparing','active','paused') "
            'ORDER BY id DESC LIMIT 1', (row['id'],)).fetchone()
        aftermath_published = bool(conn.execute(
            "SELECT 1 FROM vk_outbox WHERE event_key IN (?,?) LIMIT 1",
            (f'contract:{row["id"]}:completed', f'contract:{row["id"]}:failed')).fetchone())
        payload = {
            'id': row['id'], 'owner_user_id': row['owner_user_id'],
            'storyline_id': row['storyline_id'], 'status': row['status'],
            'title': row['title'], 'teaser': row['teaser'],
            'public_brief': row['public_brief'], 'district_id': row['district_id'],
            'risk_level': row['risk_level'], 'reward_mode': row['reward_mode'],
            'reward_exact': row['reward_exact'], 'reward_min': row['reward_min'],
            'reward_max': row['reward_max'], 'reward_text': row['reward_text'],
            'scheduled_at': row['scheduled_at'], 'timezone': row['timezone'],
            'duration_text': row['duration_text'], 'crew_capacity': row['crew_capacity'],
            'requirements': row['requirements'], 'content_notes': row['content_notes'],
            'service_format': row['service_format'], 'cover_media_id': row['cover_media_id'],
            'created': row['created'], 'updated': row['updated'],
            'active_session_id': active_session['id'] if active_session else None,
            'active_session_status': active_session['status'] if active_session else None,
            'aftermath_published': aftermath_published,
            'participants': [{
                'id': item['id'], 'persona_id': item['persona_id'],
                'role_key': item['role_key'], 'role_label': item['role_label'],
                'visibility': item['visibility'], 'note': item['note'],
                'handle': item['handle'], 'display_name': item['display_name'],
                'kind': item['kind'], 'avatar_media_id': item['avatar_media_id'],
                'accent_color': item['accent_color'],
            } for item in participant_rows if item['visibility'] == 'public' or classified],
            'signups': signup_payload,
            'crew_count': sum(1 for item in signup_payload if item['status'] == 'crew'),
            'waitlist_count': sum(1 for item in signup_payload if item['status'] == 'waitlist'),
            'my_signup': next((item for item in signup_payload if user and item['user_id'] == user['id']), None),
            'can_edit': can_edit, 'has_classified_access': classified,
            'gm_display_name': owner['display_name'] if owner and owner['show_display_name'] else None,
        }
        if classified:
            payload.update({
                'classified_brief': row['classified_brief'],
                'service_contact': row['service_contact'],
                'service_vtt_url': row['service_vtt_url'],
                'service_notes': row['service_notes'],
            })
        return payload

    def clean_contract_input(self, body, existing=None):
        base = dict(existing or {})
        get = lambda key, default='': (body or {}).get(key, base.get(key, default))
        title = str(get('title')).strip()[:180]
        if not title:
            raise ApiError(400, 'Контракту нужно название')
        status = str(get('status', 'draft')).lower()
        reward_mode = str(get('reward_mode', 'hidden')).lower()
        risk = str(get('risk_level', 'moderate')).lower()
        if status not in CONTRACT_STATUSES or reward_mode not in CONTRACT_REWARD_MODES or risk not in CONTRACT_RISKS:
            raise ApiError(400, 'Некорректный статус, риск или награда контракта')
        capacity = max(0, min(100, _num(get('crew_capacity', 0)) or 0))
        def optional_number(key):
            raw = get(key)
            if raw is None or str(raw).strip() == '':
                return None
            try:
                return float(raw)
            except (TypeError, ValueError):
                raise ApiError(400, f'Некорректное число в поле контракта: {key}')
        return {
            'storyline_id': _num(get('storyline_id')),
            'status': status, 'title': title,
            'teaser': str(get('teaser'))[:500],
            'public_brief': str(get('public_brief'))[:30000],
            'classified_brief': str(get('classified_brief'))[:30000],
            'district_id': str(get('district_id'))[:80],
            'risk_level': risk, 'reward_mode': reward_mode,
            'reward_exact': optional_number('reward_exact'),
            'reward_min': optional_number('reward_min'),
            'reward_max': optional_number('reward_max'),
            'reward_text': str(get('reward_text'))[:200] or None,
            'scheduled_at': optional_number('scheduled_at'),
            'timezone': str(get('timezone', 'Europe/Moscow'))[:80] or 'Europe/Moscow',
            'duration_text': str(get('duration_text'))[:100] or None,
            'crew_capacity': capacity,
            'requirements': str(get('requirements'))[:5000],
            'content_notes': str(get('content_notes'))[:5000],
            'service_format': str(get('service_format'))[:200],
            'service_contact': str(get('service_contact'))[:500],
            'service_vtt_url': str(get('service_vtt_url'))[:1000],
            'service_notes': str(get('service_notes'))[:5000],
            'cover_media_id': str(get('cover_media_id'))[:64] or None,
        }

    def replace_contract_participants(self, conn, contract_id, user, participants):
        existing_ids = {row['persona_id'] for row in conn.execute(
            'SELECT persona_id FROM contract_participants WHERE contract_id=?',
            (contract_id,)).fetchall()}
        conn.execute('DELETE FROM contract_participants WHERE contract_id=?', (contract_id,))
        for index, item in enumerate(participants or []):
            persona = conn.execute('SELECT * FROM personas WHERE id=?',
                                   (_num(item.get('persona_id')),)).fetchone()
            if not persona or (not can_manage_persona(user, persona) and persona['id'] not in existing_ids):
                raise ApiError(400, 'Недоступная персона в контракте')
            visibility = 'classified' if item.get('visibility') == 'classified' else 'public'
            role_key = str(item.get('role_key') or 'custom')[:40]
            conn.execute(
                'INSERT INTO contract_participants(contract_id,persona_id,role_key,role_label,'
                'visibility,note,sort_order) VALUES(?,?,?,?,?,?,?)',
                (contract_id, persona['id'], role_key, str(item.get('role_label') or '')[:100],
                 visibility, str(item.get('note') or '')[:1000], index))

    def api_contracts(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute('SELECT * FROM contracts ORDER BY scheduled_at IS NULL,scheduled_at,created DESC').fetchall()
        visible = []
        for row in rows:
            if row['status'] in ('draft', 'archived') and not can_edit_contract(conn, user, row):
                continue
            visible.append(self.contract_payload(conn, row, user))
        self.send_json({'contracts': visible})

    def api_contract_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        data = self.clean_contract_input(body or {})
        if data['storyline_id']:
            storyline = conn.execute('SELECT * FROM storylines WHERE id=?', (data['storyline_id'],)).fetchone()
            if not storyline or not can_edit_storyline(conn, user, storyline):
                raise ApiError(400, 'Недоступная сюжетная линия')
        now = time.time(); columns = list(data)
        cur = conn.execute(
            f"INSERT INTO contracts(owner_user_id,{','.join(columns)},created,updated) "
            f"VALUES(? ,{','.join('?' for _ in columns)},?,?)",
            (user['id'], *(data[key] for key in columns), now, now))
        attach_network_media(conn, user['id'], 'contract', cur.lastrowid,
                             [data['cover_media_id']], {'contract_image'})
        self.replace_contract_participants(conn, cur.lastrowid, user, (body or {}).get('participants') or [])
        if data['status'] == 'open':
            queue_vk_event(conn, f'contract:{cur.lastrowid}:published', 'contract_published',
                           cur.lastrowid, {'contract_id': cur.lastrowid, 'title': data['title']})
            for recipient in conn.execute('SELECT id FROM users WHERE id>1').fetchall():
                add_notification(conn, recipient['id'], 'contract_published',
                                 'New NC//NET Contract', data['title'],
                                 f'#/contracts/{cur.lastrowid}')
        conn.commit()
        row = conn.execute('SELECT * FROM contracts WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.contract_payload(conn, row, user), status=201)

    def api_contract_detail(self, conn, qs, m, body):
        row = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Контракт не найден')
        user = self.current_user(conn)
        if row['status'] in ('draft', 'archived') and not can_edit_contract(conn, user, row):
            raise ApiError(404, 'Контракт не найден')
        self.send_json(self.contract_payload(conn, row, user))

    def api_contract_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row or not can_edit_contract(conn, user, row):
            raise ApiError(403, 'Нет права редактировать этот контракт')
        data = self.clean_contract_input(body or {}, row)
        crew_count = conn.execute(
            "SELECT COUNT(*) n FROM contract_signups WHERE contract_id=? AND status='crew'",
            (row['id'],)).fetchone()['n']
        if data['crew_capacity'] and data['crew_capacity'] < crew_count:
            raise ApiError(409, 'Размер команды меньше уже записанного Crew')
        if data['status'] == 'crew_full' and (data['crew_capacity'] == 0 or crew_count < data['crew_capacity']):
            data['status'] = 'open'
        if data['storyline_id']:
            storyline = conn.execute('SELECT * FROM storylines WHERE id=?', (data['storyline_id'],)).fetchone()
            if not storyline or not can_edit_storyline(conn, user, storyline):
                raise ApiError(400, 'Недоступная сюжетная линия')
        assignments = ','.join(f'{key}=?' for key in data)
        conn.execute(f'UPDATE contracts SET {assignments},updated=? WHERE id=?',
                     (*(data[key] for key in data), time.time(), row['id']))
        attach_network_media(conn, user['id'], 'contract', row['id'],
                             [data['cover_media_id']], {'contract_image'})
        if 'participants' in (body or {}):
            self.replace_contract_participants(conn, row['id'], user, (body or {}).get('participants'))
        if row['status'] != data['status'] or row['scheduled_at'] != data['scheduled_at']:
            queue_vk_event(conn, f'contract:{row["id"]}:update:{int(time.time())}',
                           f'contract_{data["status"]}', row['id'],
                           {'contract_id': row['id'], 'title': data['title'],
                            'status': data['status'], 'scheduled_at': data['scheduled_at']})
            for recipient in conn.execute(
                    "SELECT DISTINCT user_id FROM contract_signups WHERE contract_id=? "
                    "AND status IN ('crew','waitlist')", (row['id'],)).fetchall():
                add_notification(conn, recipient['user_id'], 'contract_updated',
                                 'Contract updated', data['title'], f'#/contracts/{row["id"]}')
        conn.commit()
        updated = conn.execute('SELECT * FROM contracts WHERE id=?', (row['id'],)).fetchone()
        self.send_json(self.contract_payload(conn, updated, user))

    def api_contract_join(self, conn, qs, m, body):
        user = self.require_user(conn)
        contract = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not contract or contract['status'] not in ('open', 'crew_full'):
            raise ApiError(409, 'Контракт недоступен для записи')
        character = self.get_char(conn, (body or {}).get('character_id'))
        if character['owner_id'] != user['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(character['data']).get('archived'):
            raise ApiError(409, 'Архивное досье нельзя записать на контракт')
        existing = conn.execute(
            "SELECT * FROM contract_signups WHERE contract_id=? AND character_id=? AND status IN ('crew','waitlist')",
            (contract['id'], character['id'])).fetchone()
        if existing:
            raise ApiError(409, 'Этот персонаж уже записан')
        previous = conn.execute(
            'SELECT * FROM contract_signups WHERE contract_id=? AND character_id=? ORDER BY id DESC LIMIT 1',
            (contract['id'], character['id'])).fetchone()
        crew_count = conn.execute(
            "SELECT COUNT(*) n FROM contract_signups WHERE contract_id=? AND status='crew'",
            (contract['id'],)).fetchone()['n']
        capacity = contract['crew_capacity']
        status = 'crew' if capacity == 0 or crew_count < capacity else 'waitlist'
        position = conn.execute(
            'SELECT COALESCE(MAX(queue_position),0)+1 n FROM contract_signups WHERE contract_id=?',
            (contract['id'],)).fetchone()['n']
        now = time.time()
        if previous:
            conn.execute(
                'UPDATE contract_signups SET user_id=?,status=?,queue_position=?,joined_at=?,updated=? WHERE id=?',
                (user['id'], status, position, now, now, previous['id']))
        else:
            conn.execute(
                'INSERT INTO contract_signups(contract_id,user_id,character_id,status,queue_position,'
                'joined_at,updated) VALUES(?,?,?,?,?,?,?)',
                (contract['id'], user['id'], character['id'], status, position, now, now))
        if status == 'crew' and capacity and crew_count + 1 >= capacity:
            conn.execute("UPDATE contracts SET status='crew_full',updated=? WHERE id=?",
                         (now, contract['id']))
            queue_vk_event(conn, f'contract:{contract["id"]}:crew-full:{position}',
                           'contract_crew_full', contract['id'],
                           {'contract_id': contract['id'], 'title': contract['title']})
        add_notification(conn, user['id'], 'contract_joined',
                         'Contract access confirmed' if status == 'crew' else 'Added to Contract waitlist',
                         contract['title'], f'#/contracts/{contract["id"]}')
        conn.commit()
        updated = conn.execute('SELECT * FROM contracts WHERE id=?', (contract['id'],)).fetchone()
        self.send_json(self.contract_payload(conn, updated, user))

    def api_contract_leave(self, conn, qs, m, body):
        user = self.require_user(conn)
        contract = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        signup = conn.execute(
            "SELECT * FROM contract_signups WHERE contract_id=? AND user_id=? AND status IN ('crew','waitlist') "
            'ORDER BY id DESC LIMIT 1', (int(m.group(1)), user['id'])).fetchone()
        if not contract or not signup:
            raise ApiError(404, 'Запись на контракт не найдена')
        if contract['status'] not in ('open', 'crew_full', 'in_progress'):
            raise ApiError(409, 'Завершённый контракт хранит неизменяемый состав')
        was_crew = signup['status'] == 'crew'; now = time.time()
        conn.execute("UPDATE contract_signups SET status='withdrawn',updated=? WHERE id=?",
                     (now, signup['id']))
        promoted = None
        if was_crew:
            promoted = conn.execute(
                "SELECT * FROM contract_signups WHERE contract_id=? AND status='waitlist' "
                'ORDER BY queue_position,joined_at LIMIT 1', (contract['id'],)).fetchone()
            if promoted:
                conn.execute("UPDATE contract_signups SET status='crew',updated=? WHERE id=?",
                             (now, promoted['id']))
                add_notification(conn, promoted['user_id'], 'contract_promoted',
                                 'Promoted from waitlist', contract['title'],
                                 f'#/contracts/{contract["id"]}')
            else:
                conn.execute("UPDATE contracts SET status='open',updated=? WHERE id=?",
                             (now, contract['id']))
                queue_vk_event(conn, f'contract:{contract["id"]}:vacancy:{signup["id"]}',
                               'contract_vacancy', contract['id'],
                               {'contract_id': contract['id'], 'title': contract['title']})
        conn.commit()
        updated = conn.execute('SELECT * FROM contracts WHERE id=?', (contract['id'],)).fetchone()
        self.send_json(self.contract_payload(conn, updated, user))

    def api_contract_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        contract = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not contract or not can_edit_contract(conn, user, contract):
            raise ApiError(403, 'Нет права редактировать этот контракт')
        conn.execute("UPDATE contracts SET status='archived',updated=? WHERE id=?",
                     (time.time(), contract['id']))
        conn.commit(); self.send_json({'ok': True})

    # ------------------------------------------------------------ NC//NET City Feed

    def resolve_feed_author(self, conn, user, body):
        persona_id = _num((body or {}).get('author_persona_id'))
        character_id = _num((body or {}).get('author_character_id'))
        if bool(persona_id) == bool(character_id):
            raise ApiError(400, 'Выберите одного автора публикации')
        if persona_id:
            persona = conn.execute('SELECT * FROM personas WHERE id=?', (persona_id,)).fetchone()
            if not persona or not can_manage_persona(user, persona):
                raise ApiError(403, 'Недоступная персона-автор')
            return persona_id, None
        character = self.get_char(conn, character_id)
        if character['owner_id'] != user['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(character['data']).get('archived'):
            raise ApiError(409, 'Архивное досье нельзя использовать как автора')
        return None, character['id']

    def feed_post_payload(self, conn, row, user, include_comments=False):
        persona = conn.execute('SELECT * FROM personas WHERE id=?',
                               (row['author_persona_id'],)).fetchone() if row['author_persona_id'] else None
        character = conn.execute('SELECT * FROM characters WHERE id=?',
                                 (row['author_character_id'],)).fetchone() if row['author_character_id'] else None
        char_data = parse_json_object(character['data']) if character else {}
        can_edit = bool(user and (user['id'] == row['creator_user_id'] or user_is_admin(user) or
                        (persona and can_manage_persona(user, persona))))
        payload = {
            'id': row['id'], 'format': row['format'], 'status': row['status'],
            'creator_user_id': row['creator_user_id'],
            'author_persona_id': row['author_persona_id'],
            'author_character_id': row['author_character_id'],
            'author': persona_payload(persona, False) if persona else ({
                'id': character['id'], 'kind': 'character',
                'display_name': char_data.get('handle') or 'Unknown Edgerunner',
                'handle': char_data.get('handle') or 'unknown',
                'avatar_media_id': char_data.get('portrait_media_id'),
                'accent_color': '#ff2d78',
            } if character else None),
            'storyline_id': row['storyline_id'], 'contract_id': row['contract_id'],
            'reply_to_post_id': row['reply_to_post_id'], 'district_id': row['district_id'],
            'headline': row['headline'], 'lead': row['lead'], 'body': row['body'],
            'image_media_id': row['image_media_id'], 'event_at': row['event_at'],
            'published_at': row['published_at'], 'created': row['created'],
            'updated': row['updated'], 'can_edit': can_edit,
        }
        if user_is_gm(user):
            payload['truth_status'] = row['truth_status']
            payload['hidden_reason'] = row['hidden_reason']
        if include_comments:
            comments = conn.execute(
                'SELECT * FROM feed_comments WHERE post_id=? ORDER BY created,id',
                (row['id'],)).fetchall()
            payload['comments'] = [self.feed_comment_payload(conn, item, user) for item in comments
                                   if not item['hidden_at'] or user_is_gm(user) or
                                   (user and item['creator_user_id'] == user['id'])]
        return payload

    def feed_comment_payload(self, conn, row, user):
        persona = conn.execute('SELECT * FROM personas WHERE id=?',
                               (row['author_persona_id'],)).fetchone() if row['author_persona_id'] else None
        character = conn.execute('SELECT * FROM characters WHERE id=?',
                                 (row['author_character_id'],)).fetchone() if row['author_character_id'] else None
        char_data = parse_json_object(character['data']) if character else {}
        return {
            'id': row['id'], 'post_id': row['post_id'],
            'parent_comment_id': row['parent_comment_id'], 'body': row['body'],
            'created': row['created'], 'updated': row['updated'],
            'hidden': bool(row['hidden_at']),
            'hidden_reason': row['hidden_reason'] if user_is_gm(user) else None,
            'author': persona_payload(persona, False) if persona else ({
                'id': character['id'], 'kind': 'character',
                'display_name': char_data.get('handle') or 'Unknown Edgerunner',
                'handle': char_data.get('handle') or 'unknown',
                'avatar_media_id': char_data.get('portrait_media_id'),
                'accent_color': '#ff2d78',
            } if character else None),
            'mine': bool(user and row['creator_user_id'] == user['id']),
        }

    def api_feed(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute('SELECT * FROM feed_posts ORDER BY published_at DESC,created DESC LIMIT 200').fetchall()
        posts = [self.feed_post_payload(conn, row, user) for row in rows
                 if row['status'] == 'published' or
                 (user and (row['creator_user_id'] == user['id'] or user_is_gm(user)))]
        self.send_json({'posts': posts})

    def api_feed_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        self.rate_limit('feed-post', 20, 3600, user['id'])
        persona_id, character_id = self.resolve_feed_author(conn, user, body or {})
        fmt = str((body or {}).get('format') or 'short').lower()
        if fmt not in FEED_FORMATS:
            raise ApiError(400, 'Некорректный формат публикации')
        headline = str((body or {}).get('headline') or '').strip()[:240] or None
        text = str((body or {}).get('body') or '').strip()[:30000]
        if not text or (fmt in ('article', 'blog', 'bulletin') and not headline):
            raise ApiError(400, 'Публикации нужен текст и, для длинного формата, заголовок')
        status = 'draft' if user_is_gm(user) and (body or {}).get('status') == 'draft' else 'published'
        truth = str((body or {}).get('truth_status') or 'unknown') if user_is_gm(user) else 'unknown'
        if truth not in FEED_TRUTH:
            truth = 'unknown'
        now = time.time(); published = now if status == 'published' else None
        cur = conn.execute(
            'INSERT INTO feed_posts(format,status,creator_user_id,author_persona_id,author_character_id,'
            'storyline_id,contract_id,reply_to_post_id,district_id,headline,lead,body,image_media_id,'
            'truth_status,event_at,published_at,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (fmt, status, user['id'], persona_id, character_id,
             _num((body or {}).get('storyline_id')), _num((body or {}).get('contract_id')),
             _num((body or {}).get('reply_to_post_id')),
             str((body or {}).get('district_id') or '')[:80] or None,
             headline, str((body or {}).get('lead') or '')[:500] or None, text,
             str((body or {}).get('image_media_id') or '')[:64] or None,
             truth, (body or {}).get('event_at'), published, now, now))
        attach_network_media(conn, user['id'], 'feed_post', cur.lastrowid,
                             [str((body or {}).get('image_media_id') or '')], {'feed_image'})
        row = conn.execute('SELECT * FROM feed_posts WHERE id=?', (cur.lastrowid,)).fetchone()
        record_feed_revision(conn, row['id'], user['id'], 'publish' if status == 'published' else 'draft',
                             None, self.feed_post_payload(conn, row, user))
        conn.commit()
        self.send_json(self.feed_post_payload(conn, row, user), status=201)

    def api_feed_detail(self, conn, qs, m, body):
        row = conn.execute('SELECT * FROM feed_posts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Публикация не найдена')
        user = self.current_user(conn)
        if row['status'] != 'published' and not (user and (user_is_gm(user) or row['creator_user_id'] == user['id'])):
            raise ApiError(404, 'Публикация не найдена')
        self.send_json(self.feed_post_payload(conn, row, user, include_comments=True))

    def api_feed_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        row = conn.execute('SELECT * FROM feed_posts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Публикация не найдена')
        persona = conn.execute('SELECT * FROM personas WHERE id=?',
                               (row['author_persona_id'],)).fetchone() if row['author_persona_id'] else None
        allowed = row['creator_user_id'] == user['id'] or user_is_admin(user) or (persona and can_manage_persona(user, persona))
        if not allowed:
            raise ApiError(403, 'Нет права редактировать эту публикацию')
        before = self.feed_post_payload(conn, row, user)
        fmt = str((body or {}).get('format', row['format']))
        headline = str((body or {}).get('headline', row['headline'] or '')).strip()[:240] or None
        text = str((body or {}).get('body', row['body'])).strip()[:30000]
        status = str((body or {}).get('status', row['status']))
        if fmt not in FEED_FORMATS or status not in ('draft', 'published', 'archived') or not text:
            raise ApiError(400, 'Некорректная публикация')
        published = row['published_at'] or (time.time() if status == 'published' else None)
        conn.execute(
            'UPDATE feed_posts SET format=?,status=?,headline=?,lead=?,body=?,district_id=?,event_at=?,published_at=?,updated=? WHERE id=?',
            (fmt, status, headline, str((body or {}).get('lead', row['lead'] or ''))[:500] or None,
             text, str((body or {}).get('district_id', row['district_id'] or ''))[:80] or None,
             (body or {}).get('event_at', row['event_at']), published, time.time(), row['id']))
        updated = conn.execute('SELECT * FROM feed_posts WHERE id=?', (row['id'],)).fetchone()
        after = self.feed_post_payload(conn, updated, user)
        record_feed_revision(conn, row['id'], user['id'], 'update', before, after)
        conn.commit(); self.send_json(after)

    def api_feed_hide(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM feed_posts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Публикация не найдена')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not reason:
            raise ApiError(400, 'Укажите причину скрытия')
        before = self.feed_post_payload(conn, row, user)
        conn.execute("UPDATE feed_posts SET status='hidden',hidden_by_user_id=?,hidden_reason=?,updated=? WHERE id=?",
                     (user['id'], reason, time.time(), row['id']))
        updated = conn.execute('SELECT * FROM feed_posts WHERE id=?', (row['id'],)).fetchone()
        record_feed_revision(conn, row['id'], user['id'], 'hide', before,
                             self.feed_post_payload(conn, updated, user), reason)
        conn.commit(); self.send_json({'ok': True})

    def api_feed_comment_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        self.rate_limit('feed-comment', 60, 3600, user['id'])
        post = conn.execute("SELECT * FROM feed_posts WHERE id=? AND status='published'",
                            (int(m.group(1)),)).fetchone()
        if not post:
            raise ApiError(404, 'Публикация не найдена')
        persona_id, character_id = self.resolve_feed_author(conn, user, body or {})
        text = str((body or {}).get('body') or '').strip()[:5000]
        if not text:
            raise ApiError(400, 'Комментарий не может быть пустым')
        parent_id = _num((body or {}).get('parent_comment_id'))
        if parent_id:
            parent = conn.execute('SELECT * FROM feed_comments WHERE id=? AND post_id=?',
                                  (parent_id, post['id'])).fetchone()
            if not parent:
                raise ApiError(400, 'Родительский комментарий не найден')
            if parent['parent_comment_id']:
                parent_id = parent['parent_comment_id']
        now = time.time()
        cur = conn.execute(
            'INSERT INTO feed_comments(post_id,parent_comment_id,creator_user_id,author_persona_id,'
            'author_character_id,body,created,updated) VALUES(?,?,?,?,?,?,?,?)',
            (post['id'], parent_id, user['id'], persona_id, character_id, text, now, now))
        if post['creator_user_id'] != user['id']:
            add_notification(conn, post['creator_user_id'], 'feed_comment',
                             'New reply to your transmission', text[:180], f'#/feed/{post["id"]}')
        conn.commit(); row = conn.execute('SELECT * FROM feed_comments WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.feed_comment_payload(conn, row, user), status=201)

    def api_feed_comment_hide(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM feed_comments WHERE id=?', (int(m.group(2)),)).fetchone()
        if not row or row['post_id'] != int(m.group(1)):
            raise ApiError(404, 'Комментарий не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not reason:
            raise ApiError(400, 'Укажите причину скрытия')
        conn.execute('UPDATE feed_comments SET hidden_at=?,hidden_by=?,hidden_reason=?,updated=? WHERE id=?',
                     (time.time(), user['id'], reason, time.time(), row['id']))
        conn.commit(); self.send_json({'ok': True})

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
        elif row['attached_type'] == 'account' and row['attached_id']:
            account = conn.execute('SELECT id,show_display_name FROM users WHERE id=?',
                                   (row['attached_id'],)).fetchone()
            public_media = bool(account and account['show_display_name'])
            allowed = bool(account and user and
                           (user['id'] == account['id'] or public_media))
        elif row['attached_type'] == 'persona' and row['attached_id']:
            persona = conn.execute('SELECT * FROM personas WHERE id=?', (row['attached_id'],)).fetchone()
            public_media = bool(persona and persona['access'] in ('shared', 'system') and persona['status'] != 'archived')
            allowed = public_media or can_manage_persona(user, persona)
        elif row['attached_type'] == 'contract' and row['attached_id']:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?', (row['attached_id'],)).fetchone()
            public_media = bool(contract and contract['status'] not in ('draft', 'archived'))
            allowed = public_media or can_edit_contract(conn, user, contract)
        elif row['attached_type'] == 'feed_post' and row['attached_id']:
            post = conn.execute('SELECT * FROM feed_posts WHERE id=?', (row['attached_id'],)).fetchone()
            public_media = bool(post and post['status'] == 'published')
            allowed = bool(public_media or (post and user and
                           (post['creator_user_id'] == user['id'] or user_is_gm(user))))
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
            'general_dv': GENERAL_DV,
            'rule_sources': RULE_SOURCES,
        })

    def api_stats(self, conn, qs, m, body):
        cat = catalog()
        c = conn.execute('SELECT COUNT(*) n FROM characters').fetchone()['n']
        u = conn.execute('SELECT COUNT(*) n FROM users WHERE id > 1').fetchone()['n']
        nw = conn.execute('SELECT COUNT(*) n FROM news').fetchone()['n']
        jb = conn.execute("SELECT COUNT(*) n FROM jobs WHERE status='open'").fetchone()['n']
        feed = conn.execute("SELECT COUNT(*) n FROM feed_posts WHERE status='published'").fetchone()['n']
        contracts = conn.execute("SELECT COUNT(*) n FROM contracts WHERE status IN ('open','crew_full')").fetchone()['n']
        self.send_json({'items': len(cat['items']), 'characters': c, 'users': u,
                        'news': nw, 'open_jobs': jb,
                        'feed_posts': feed, 'open_contracts': contracts})

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
        owned_rows = conn.execute('SELECT data FROM characters WHERE owner_id=?',
                                  (u['id'],)).fetchall()
        count = sum(1 for item in owned_rows if not parse_json_object(item['data']).get('archived'))
        if count >= 50:
            raise ApiError(400, 'Слишком много персонажей (максимум 50)')
        now = time.time()
        pub = 1 if data.get('public', False) else 0
        cur = conn.execute(
            'INSERT INTO characters(owner_id, public, data, created, updated) VALUES(?,?,?,?,?)',
            (u['id'], pub, json.dumps(data, ensure_ascii=False), now, now))
        attach_character_media(conn, u['id'], cur.lastrowid, data)
        record_character_changes(conn, cur.lastrowid, u['id'], {}, data, 'Character created')
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
        if old_data.get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        data = clean_character(body.get('data') if isinstance(body, dict) else body)
        pub = 1 if data.get('public', False) else 0
        old_media = str(old_data.get('portrait_media_id') or '')
        new_media = str(data.get('portrait_media_id') or '')
        if old_media and old_media != new_media:
            conn.execute("UPDATE media SET attached_type=NULL, attached_id=NULL WHERE id=? AND owner_id=? AND attached_type='character' AND attached_id=?",
                         (old_media, u['id'], row['id']))
        attach_character_media(conn, u['id'], row['id'], data)
        record_character_changes(conn, row['id'], u['id'], old_data, data,
                                 str((body or {}).get('reason') or 'Character sheet update'))
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
        network_refs = sum(conn.execute(query, (row['id'],)).fetchone()['n'] for query in (
            'SELECT COUNT(*) n FROM contract_signups WHERE character_id=?',
            'SELECT COUNT(*) n FROM feed_posts WHERE author_character_id=?',
            'SELECT COUNT(*) n FROM feed_comments WHERE author_character_id=?',
            'SELECT COUNT(*) n FROM session_combatants WHERE character_id=?',
        ))
        if network_refs:
            data = json.loads(row['data'])
            data['archived'] = True
            data['public'] = False
            data['archive_reason'] = 'Preserved because this Dossier has NC//NET history.'
            now = time.time()
            active = conn.execute(
                "SELECT s.* FROM contract_signups s JOIN contracts c ON c.id=s.contract_id "
                "WHERE s.character_id=? AND s.status IN ('crew','waitlist') "
                "AND c.status IN ('open','crew_full','in_progress')",
                (row['id'],)).fetchall()
            for signup in active:
                conn.execute("UPDATE contract_signups SET status='withdrawn',updated=? WHERE id=?",
                             (now, signup['id']))
                if signup['status'] == 'crew':
                    promoted = conn.execute(
                        "SELECT * FROM contract_signups WHERE contract_id=? AND status='waitlist' "
                        'ORDER BY queue_position,joined_at LIMIT 1', (signup['contract_id'],)).fetchone()
                    if promoted:
                        conn.execute("UPDATE contract_signups SET status='crew',updated=? WHERE id=?",
                                     (now, promoted['id']))
                        add_notification(conn, promoted['user_id'], 'contract_promoted',
                                         'Promoted from waitlist', 'A Crew place became available.',
                                         f'#/contracts/{signup["contract_id"]}')
                    else:
                        conn.execute("UPDATE contracts SET status='open',updated=? WHERE id=? AND status='crew_full'",
                                     (now, signup['contract_id']))
            conn.execute('UPDATE characters SET public=0,data=?,updated=? WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now, row['id']))
            record_character_changes(conn, row['id'], u['id'], json.loads(row['data']), data,
                                     'Dossier archived with NC//NET history')
            conn.commit()
            self.send_json({'ok': True, 'archived': True})
            return
        media_rows = conn.execute("SELECT * FROM media WHERE attached_type='character' AND attached_id=?", (row['id'],)).fetchall()
        conn.execute("DELETE FROM media WHERE attached_type='character' AND attached_id=?", (row['id'],))
        conn.execute('DELETE FROM ip_ledger WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM character_ledger WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM characters WHERE id=?', (row['id'],))
        conn.commit()
        for media in media_rows:
            try: os.remove(os.path.join(UPLOAD_DIR, media['filename']))
            except FileNotFoundError: pass
        self.send_json({'ok': True, 'archived': False})

    def save_character_data(self, conn, row, data, actor_id=None, reason='Character progression'):
        if actor_id is not None:
            record_character_changes(conn, row['id'], actor_id, json.loads(row['data']), data, reason)
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
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
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
        self.send_json(self.save_character_data(conn, row, data, user['id'], reason))

    def api_character_ip_history(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        rows = conn.execute('SELECT l.*,u.display_name actor FROM ip_ledger l JOIN users u ON u.id=l.actor_id WHERE character_id=? ORDER BY id DESC LIMIT 500',
                            (row['id'],)).fetchall()
        self.send_json({'entries': [dict(item) for item in rows]})

    def api_character_network(self, conn, qs, m, body):
        row = self.get_char(conn, m.group(1))
        user = self.current_user(conn)
        if not row['public'] and (not user or (user['id'] != row['owner_id'] and not user_is_gm(user))):
            raise ApiError(403, 'Персонаж приватный')
        contracts = conn.execute(
            'SELECT c.id,c.title,c.status,c.district_id,s.status signup_status,s.joined_at '
            'FROM contract_signups s JOIN contracts c ON c.id=s.contract_id '
            'WHERE s.character_id=? ORDER BY s.joined_at DESC', (row['id'],)).fetchall()
        posts = conn.execute(
            "SELECT id,headline,body,format,published_at FROM feed_posts "
            "WHERE author_character_id=? AND status='published' ORDER BY published_at DESC",
            (row['id'],)).fetchall()
        comments = conn.execute(
            'SELECT fc.id,fc.post_id,fc.body,fc.created FROM feed_comments fc '
            'WHERE fc.author_character_id=? AND fc.hidden_at IS NULL ORDER BY fc.created DESC LIMIT 100',
            (row['id'],)).fetchall()
        self.send_json({'contracts': [dict(item) for item in contracts],
                        'posts': [dict(item) for item in posts],
                        'comments': [dict(item) for item in comments]})

    def api_character_ledger(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        entries = conn.execute(
            'SELECT l.*,u.display_name actor FROM character_ledger l '
            'JOIN users u ON u.id=l.actor_user_id WHERE character_id=? '
            'ORDER BY l.id DESC LIMIT 500', (row['id'],)).fetchall()
        self.send_json({'entries': [dict(item) for item in entries]})

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
        self.send_json(self.save_character_data(conn, row, data, user['id'], reason))

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
        self.send_json(self.save_character_data(conn, row, data, user['id'], reason))

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
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        before_data = json.loads(row['data'])
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
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 'Night Market purchase')
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
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        before_data = json.loads(row['data'])
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
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 'Night Market resale')
        conn.execute('UPDATE characters SET data=?, updated=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'got': back,
                        'name': ent.get('name'), 'qty': qty})

    def api_payroll(self, conn, qs, m, body):
        u = self.require_gm(conn)
        row = self.get_char(conn, body.get('char_id'))
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        try:
            amount = float(body.get('amount') or 0)
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректная сумма')
        if not math.isfinite(amount) or abs(amount) > 1e7:
            raise ApiError(400, 'Слишком большая сумма')
        before_data = json.loads(row['data'])
        data = json.loads(row['data'])
        data['cash'] = max(0.0, round(float(data.get('cash') or 0) + amount, 2))
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 str((body or {}).get('reason') or 'GM payout'))
        conn.execute('UPDATE characters SET data=?, updated=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'by': u['display_name']})

    # ------------------------------------------------------------ NC//NET operations

    def can_edit_nc_session(self, conn, user, session):
        if not user or not user_is_gm(user):
            return False
        if user_is_admin(user) or session['owner_user_id'] == user['id']:
            return True
        if session['contract_id']:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?',
                                    (session['contract_id'],)).fetchone()
            return can_edit_contract(conn, user, contract)
        return False

    def ordered_session_combatants(self, conn, session_id):
        return conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? '
            'ORDER BY initiative DESC,sort_order,id', (session_id,)).fetchall()

    def session_payload(self, conn, row, user, player_view=False):
        can_edit = self.can_edit_nc_session(conn, user, row)
        config = session_view_config(row['player_view_config'])
        combatants = self.ordered_session_combatants(conn, row['id'])
        active_turn = min(max(0, _num(row['active_turn']) or 0), max(0, len(combatants) - 1))
        out_combatants = []
        for index, item in enumerate(combatants):
            if player_view and not item['visible']:
                continue
            data = {
                'id': item['id'], 'kind': item['kind'], 'character_id': item['character_id'],
                'name': item['name'], 'visible': bool(item['visible']),
                'sort_order': item['sort_order'],
                'active': bool(combatants) and index == active_turn,
            }
            if not player_view or config['show_initiative']:
                data['initiative'] = item['initiative']
            if not player_view:
                data.update({
                    'hp_current': item['hp_current'], 'hp_max': item['hp_max'],
                    'sp_head': item['sp_head'], 'sp_head_max': item['sp_head_max'],
                    'sp_body': item['sp_body'], 'sp_body_max': item['sp_body_max'],
                    'shield_current': item['shield_current'], 'shield_max': item['shield_max'],
                    'ammo_current': item['ammo_current'], 'ammo_max': item['ammo_max'],
                    'luck_current': item['luck_current'], 'luck_max': item['luck_max'],
                    'move': item['move'], 'conditions': parse_json_list(item['conditions_json']),
                    'injuries': parse_json_list(item['injuries_json']),
                    'death_penalty': item['death_penalty'],
                    'secret': parse_json_object(item['secret_json']),
                })
            else:
                if item['kind'] == 'character' and config['show_ally_hp']:
                    data.update({'hp_current': item['hp_current'], 'hp_max': item['hp_max']})
                if config['show_armor']:
                    data.update({'sp_head': item['sp_head'], 'sp_head_max': item['sp_head_max'],
                                 'sp_body': item['sp_body'], 'sp_body_max': item['sp_body_max']})
                if config['show_shield']:
                    data.update({'shield_current': item['shield_current'],
                                 'shield_max': item['shield_max']})
                if config['show_ammo']:
                    data.update({'ammo_current': item['ammo_current'], 'ammo_max': item['ammo_max']})
                if config['show_move']:
                    data['move'] = item['move']
                if config['show_luck'] and item['luck_max']:
                    data.update({'luck_current': item['luck_current'], 'luck_max': item['luck_max']})
                if config['show_conditions']:
                    data['conditions'] = parse_json_list(item['conditions_json'])
                if config['show_injuries']:
                    data['injuries'] = parse_json_list(item['injuries_json'])
                    data['death_penalty'] = item['death_penalty']
            out_combatants.append(data)
        visible_active_turn = next(
            (index for index, item in enumerate(out_combatants) if item['active']), None)
        payload = {
            'id': row['id'], 'contract_id': row['contract_id'], 'title': row['title'],
            'status': row['status'], 'round': row['round'],
            'active_turn': visible_active_turn if player_view else active_turn,
            'player_view_config': config, 'combatants': out_combatants,
            'created': row['created'], 'updated': row['updated'], 'can_edit': can_edit,
        }
        if can_edit and not player_view:
            payload['notes'] = row['notes']
            activity = conn.execute(
                'SELECT a.*,u.display_name actor FROM session_activity a '
                'JOIN users u ON u.id=a.actor_user_id WHERE session_id=? '
                'ORDER BY a.id DESC LIMIT 200', (row['id'],)).fetchall()
            payload['activity'] = [dict(item) for item in activity]
        return payload

    def can_edit_npc_template(self, user, template):
        return bool(user and template and user_is_gm(user) and
                    (user_is_admin(user) or template['owner_user_id'] == user['id']))

    def npc_template_payload(self, row, user):
        return {
            'id': row['id'], 'owner_user_id': row['owner_user_id'],
            'access': row['access'], 'name': row['name'], 'role': row['role'],
            'data': parse_json_object(row['data_json']), 'updated': row['updated'],
            'can_edit': self.can_edit_npc_template(user, row),
        }

    def api_npc_templates(self, conn, qs, m, body):
        user = self.require_gm(conn)
        rows = conn.execute(
            "SELECT * FROM npc_templates WHERE archived=0 AND "
            "(? OR access='shared' OR owner_user_id=?) ORDER BY updated DESC",
            (1 if user_is_admin(user) else 0, user['id'])).fetchall()
        self.send_json({'templates': [self.npc_template_payload(row, user) for row in rows]})

    def api_npc_template_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cleaned = clean_npc_template_input(body or {})
        now = time.time()
        cur = conn.execute(
            'INSERT INTO npc_templates(owner_user_id,access,name,role,data_json,created,updated) '
            'VALUES(?,?,?,?,?,?,?)',
            (user['id'], cleaned['access'], cleaned['name'], cleaned['role'],
             json.dumps(cleaned['data'], ensure_ascii=False), now, now))
        conn.commit()
        row = conn.execute('SELECT * FROM npc_templates WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.npc_template_payload(row, user), status=201)

    def api_npc_template_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM npc_templates WHERE id=? AND archived=0',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'NPC template не найден')
        if not self.can_edit_npc_template(user, row):
            raise ApiError(403, 'Нет права редактировать NPC template')
        cleaned = clean_npc_template_input(body or {}, row)
        conn.execute(
            'UPDATE npc_templates SET access=?,name=?,role=?,data_json=?,updated=? WHERE id=?',
            (cleaned['access'], cleaned['name'], cleaned['role'],
             json.dumps(cleaned['data'], ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        updated = conn.execute('SELECT * FROM npc_templates WHERE id=?', (row['id'],)).fetchone()
        self.send_json(self.npc_template_payload(updated, user))

    def api_npc_template_clone(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute(
            "SELECT * FROM npc_templates WHERE id=? AND archived=0 AND "
            "(? OR access='shared' OR owner_user_id=?)",
            (int(m.group(1)), 1 if user_is_admin(user) else 0, user['id'])).fetchone()
        if not row:
            raise ApiError(404, 'NPC template не найден')
        cleaned = clean_npc_template_input({
            'name': str((body or {}).get('name') or f'{row["name"]} Copy'),
            'role': row['role'],
            'access': (body or {}).get('access') or 'private',
            'data': parse_json_object(row['data_json']),
        })
        now = time.time()
        cur = conn.execute(
            'INSERT INTO npc_templates(owner_user_id,access,name,role,data_json,created,updated) '
            'VALUES(?,?,?,?,?,?,?)',
            (user['id'], cleaned['access'], cleaned['name'], cleaned['role'],
             json.dumps(cleaned['data'], ensure_ascii=False), now, now))
        conn.commit()
        cloned = conn.execute('SELECT * FROM npc_templates WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.npc_template_payload(cloned, user), status=201)

    def api_npc_template_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM npc_templates WHERE id=? AND archived=0',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'NPC template не найден')
        if not self.can_edit_npc_template(user, row):
            raise ApiError(403, 'Нет права редактировать NPC template')
        conn.execute('UPDATE npc_templates SET archived=1,updated=? WHERE id=?',
                     (time.time(), row['id']))
        conn.commit(); self.send_json({'ok': True, 'archived': True})

    def api_sessions(self, conn, qs, m, body):
        user = self.require_gm(conn)
        rows = conn.execute('SELECT * FROM nc_sessions ORDER BY updated DESC').fetchall()
        self.send_json({'sessions': [self.session_payload(conn, row, user) for row in rows
                                     if self.can_edit_nc_session(conn, user, row)]})

    def api_session_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        contract_id = _num((body or {}).get('contract_id'))
        contract = None
        if contract_id:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?', (contract_id,)).fetchone()
            if not contract or not can_edit_contract(conn, user, contract):
                raise ApiError(403, 'Нет доступа к контракту сессии')
        title = str((body or {}).get('title') or (contract['title'] if contract else 'NC//NET Session')).strip()[:180]
        if not title:
            title = contract['title'] if contract else 'NC//NET Session'
        config = session_view_config((body or {}).get('player_view_config'))
        now = time.time()
        cur = conn.execute(
            'INSERT INTO nc_sessions(contract_id,owner_user_id,title,status,player_view_config,notes,created,updated) '
            "VALUES(?,?,?,'preparing',?,?,?,?)",
            (contract_id, user['id'], title, json.dumps(config),
             str((body or {}).get('notes') or '')[:20000], now, now))
        session_id = cur.lastrowid
        if contract:
            signups = conn.execute(
                "SELECT s.*,c.data FROM contract_signups s JOIN characters c ON c.id=s.character_id "
                "WHERE s.contract_id=? AND s.status='crew' ORDER BY s.queue_position",
                (contract_id,)).fetchall()
            for index, signup in enumerate(signups):
                char = ensure_progression(json.loads(signup['data'])); derived = derive(char)
                shield = (char.get('armor') or {}).get('shield') or {}
                shield_max = (_num(shield.get('maximum')) or _num(shield.get('sdp')) or
                              _num(shield.get('sp')) or 0) if isinstance(shield, dict) else 0
                shield_current = (_num(shield.get('current')) if isinstance(shield, dict) else None)
                shield_current = shield_max if shield_current is None else max(0, min(shield_max, shield_current))
                weapon_states = [value for value in (char.get('weapon_state') or {}).values()
                                 if isinstance(value, dict)]
                ammo_current = sum(max(0, _num(value.get('magazine')) or 0) for value in weapon_states)
                ammo_max = sum(max(0, _num(value.get('magazine_max')) or 0) for value in weapon_states)
                luck_max = max(0, _num((char.get('stats') or {}).get('LUCK')) or 0)
                injuries = char.get('critical_injuries') or []
                injuries = injuries if isinstance(injuries, list) else []
                conn.execute(
                    "INSERT INTO session_combatants(session_id,kind,character_id,name,initiative,hp_current,"
                    "hp_max,sp_head,sp_head_max,sp_body,sp_body_max,shield_current,shield_max,ammo_current,"
                    "ammo_max,luck_current,luck_max,move,injuries_json,death_penalty,visible,sort_order) "
                    "VALUES(?,'character',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?)",
                    (session_id, signup['character_id'], char.get('handle') or 'Edgerunner', 0,
                     char.get('hp_cur') if char.get('hp_cur') is not None else (derived.get('hp_max') or 0),
                     derived.get('hp_max') or 0, derived.get('sp_head') or 0,
                     derived.get('sp_head') or 0, derived.get('sp_body') or 0,
                     derived.get('sp_body') or 0, shield_current, shield_max,
                     ammo_current, ammo_max, max(0, min(luck_max, _num(char.get('luck_cur')) or 0)),
                     luck_max, _num((char.get('stats') or {}).get('MOVE')) or 0,
                     json.dumps([str(value)[:120] for value in injuries[:20]], ensure_ascii=False),
                     max(0, _num(char.get('death_penalty')) or 0), index))
        conn.commit(); row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (session_id,)).fetchone()
        self.send_json(self.session_payload(conn, row, user), status=201)

    def api_session_detail(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row or not self.can_edit_nc_session(conn, user, row):
            raise ApiError(404, 'Сессия не найдена')
        self.send_json(self.session_payload(conn, row, user))

    def api_session_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row or not self.can_edit_nc_session(conn, user, row):
            raise ApiError(403, 'Нет права редактировать сессию')
        status = str((body or {}).get('status', row['status']))
        if status not in ('preparing', 'active', 'paused', 'completed', 'archived'):
            raise ApiError(400, 'Некорректный статус сессии')
        before = self.session_payload(conn, row, user)
        title = str((body or {}).get('title', row['title'])).strip()[:180] or row['title']
        round_number = max(0, _num((body or {}).get('round', row['round'])) or 0)
        combatant_count = conn.execute(
            'SELECT COUNT(*) n FROM session_combatants WHERE session_id=?',
            (row['id'],)).fetchone()['n']
        active_turn = max(0, _num((body or {}).get('active_turn', row['active_turn'])) or 0)
        active_turn = min(active_turn, max(0, combatant_count - 1))
        config = session_view_config(
            (body or {}).get('player_view_config', row['player_view_config']))
        conn.execute(
            'UPDATE nc_sessions SET title=?,status=?,round=?,active_turn=?,player_view_config=?,notes=?,updated=? WHERE id=?',
            (title, status, round_number, active_turn, json.dumps(config),
             str((body or {}).get('notes', row['notes']))[:20000], time.time(), row['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (row['id'], user['id'], 'session_update', json.dumps(before, ensure_ascii=False),
             json.dumps(body or {}, ensure_ascii=False), str((body or {}).get('activity_note') or '')[:500], time.time()))
        conn.commit(); updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (row['id'],)).fetchone()
        self.send_json(self.session_payload(conn, updated, user))

    def api_session_combatant_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session or not self.can_edit_nc_session(conn, user, session):
            raise ApiError(403, 'Нет права редактировать сессию')
        before_rows = self.ordered_session_combatants(conn, session['id'])
        old_index = min(max(0, session['active_turn']), max(0, len(before_rows) - 1))
        active_id = before_rows[old_index]['id'] if before_rows else None
        template = None
        template_id = _num((body or {}).get('template_id'))
        if template_id:
            template = conn.execute(
                "SELECT * FROM npc_templates WHERE id=? AND archived=0 "
                "AND (? OR access='shared' OR owner_user_id=?)",
                (template_id, 1 if user_is_admin(user) else 0, user['id'])).fetchone()
            if not template:
                raise ApiError(403, 'Недоступный NPC template')
        source = parse_json_object(template['data_json']) if template else (body or {})
        name = str((body or {}).get('name') or (template['name'] if template else '')).strip()[:120]
        if not name:
            raise ApiError(400, 'Участнику сессии нужно имя')
        conditions = source.get('conditions') or []
        injuries = source.get('injuries') or []
        secret = source.get('secret') or {}
        if not isinstance(conditions, list) or not isinstance(injuries, list) or not isinstance(secret, dict):
            raise ApiError(400, 'Некорректные данные участника сессии')
        conditions = [str(value)[:120] for value in conditions[:20]]
        injuries = [str(value)[:120] for value in injuries[:20]]
        if len(json.dumps(secret, ensure_ascii=False)) > 20000:
            raise ApiError(400, 'Некорректные данные участника сессии')
        maximum = max(0, _num(source.get('hp_max')) or 0)
        current = _num(source.get('hp_current'))
        current = maximum if current is None else max(0, min(maximum or current, current))
        sp_head = max(0, _num(source.get('sp_head')) or 0)
        sp_head_max = max(sp_head, _num(source.get('sp_head_max')) or 0)
        sp_body = max(0, _num(source.get('sp_body')) or 0)
        sp_body_max = max(sp_body, _num(source.get('sp_body_max')) or 0)
        shield_current = max(0, _num(source.get('shield_current')) or 0)
        shield_max = max(shield_current, _num(source.get('shield_max')) or 0)
        ammo_current = max(0, _num(source.get('ammo_current')) or 0)
        ammo_max = max(ammo_current, _num(source.get('ammo_max')) or 0)
        luck_current = max(0, _num(source.get('luck_current')) or 0)
        luck_max = max(luck_current, _num(source.get('luck_max')) or 0)
        order = conn.execute('SELECT COALESCE(MAX(sort_order),-1)+1 n FROM session_combatants WHERE session_id=?',
                             (session['id'],)).fetchone()['n']
        cur = conn.execute(
            'INSERT INTO session_combatants(session_id,kind,template_id,name,initiative,hp_current,hp_max,'
            'sp_head,sp_head_max,sp_body,sp_body_max,shield_current,shield_max,ammo_current,ammo_max,'
            'luck_current,luck_max,move,conditions_json,injuries_json,death_penalty,visible,secret_json,sort_order) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (session['id'], 'npc', template['id'] if template else None, name,
             max(-1000, min(1000, _num(source.get('initiative')) or 0)), current, maximum,
             sp_head, sp_head_max, sp_body, sp_body_max, shield_current, shield_max,
             ammo_current, ammo_max, luck_current, luck_max,
             max(0, _num(source.get('move')) or 0), json.dumps(conditions), json.dumps(injuries),
             max(0, _num(source.get('death_penalty')) or 0),
             0 if source.get('visible') is False else 1,
             json.dumps(secret, ensure_ascii=False), order))
        after_rows = self.ordered_session_combatants(conn, session['id'])
        active_turn = next((index for index, item in enumerate(after_rows) if item['id'] == active_id), 0)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET active_turn=?,updated=? WHERE id=?',
                     (active_turn, now, session['id']))
        created = dict(conn.execute('SELECT * FROM session_combatants WHERE id=?', (cur.lastrowid,)).fetchone())
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,combatant_id,event_type,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], cur.lastrowid, 'combatant_create',
             json.dumps(created, ensure_ascii=False), '', now))
        conn.commit(); self.send_json({'id': cur.lastrowid}, status=201)

    def api_session_combatant_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        combatant = conn.execute('SELECT * FROM session_combatants WHERE id=? AND session_id=?',
                                 (int(m.group(2)), int(m.group(1)))).fetchone()
        if not session or not combatant or not self.can_edit_nc_session(conn, user, session):
            raise ApiError(403, 'Нет права редактировать участника')
        ordered_before = self.ordered_session_combatants(conn, session['id'])
        old_index = min(max(0, session['active_turn']), max(0, len(ordered_before) - 1))
        active_id = ordered_before[old_index]['id'] if ordered_before else None
        before = dict(combatant)
        numeric = ['initiative', 'hp_current', 'hp_max', 'sp_head', 'sp_head_max',
                   'sp_body', 'sp_body_max', 'shield_current', 'shield_max', 'ammo_current', 'ammo_max',
                   'luck_current', 'luck_max', 'move', 'death_penalty', 'sort_order']
        values = {key: _num((body or {}).get(key, combatant[key])) or 0 for key in numeric}
        values['initiative'] = max(-1000, min(1000, values['initiative']))
        for key in numeric:
            if key != 'initiative':
                values[key] = max(0, values[key])
        hp_limit = values['hp_max'] if values['hp_max'] > 0 else values['hp_current']
        values['hp_current'] = min(hp_limit, values['hp_current'])
        for current_key, maximum_key in (('sp_head', 'sp_head_max'),
                                         ('sp_body', 'sp_body_max'),
                                         ('shield_current', 'shield_max'),
                                         ('ammo_current', 'ammo_max'),
                                         ('luck_current', 'luck_max')):
            if values[maximum_key] > 0:
                values[current_key] = min(values[maximum_key], values[current_key])
        conditions = (body or {}).get('conditions', parse_json_list(combatant['conditions_json']))
        injuries = (body or {}).get('injuries', parse_json_list(combatant['injuries_json']))
        secret = (body or {}).get('secret', parse_json_object(combatant['secret_json']))
        if not isinstance(conditions, list) or not isinstance(injuries, list) or not isinstance(secret, dict):
            raise ApiError(400, 'Некорректные данные участника сессии')
        conditions = [str(value)[:120] for value in conditions[:20]]
        injuries = [str(value)[:120] for value in injuries[:20]]
        if len(json.dumps(secret, ensure_ascii=False)) > 20000:
            raise ApiError(400, 'Некорректные данные участника сессии')
        visible = (body or {}).get('visible', bool(combatant['visible']))
        visible = visible if isinstance(visible, bool) else bool(combatant['visible'])
        name = str((body or {}).get('name', combatant['name'])).strip()[:120] or combatant['name']
        conn.execute(
            'UPDATE session_combatants SET name=?,initiative=?,hp_current=?,hp_max=?,sp_head=?,sp_head_max=?,'
            'sp_body=?,sp_body_max=?,shield_current=?,shield_max=?,ammo_current=?,ammo_max=?,luck_current=?,'
            'luck_max=?,move=?,conditions_json=?,injuries_json=?,death_penalty=?,visible=?,secret_json=?,'
            'sort_order=? WHERE id=?',
            (name, values['initiative'], values['hp_current'], values['hp_max'],
             values['sp_head'], values['sp_head_max'], values['sp_body'], values['sp_body_max'],
             values['shield_current'], values['shield_max'],
             values['ammo_current'], values['ammo_max'], values['luck_current'], values['luck_max'],
             values['move'], json.dumps(conditions), json.dumps(injuries), values['death_penalty'],
             1 if visible else 0, json.dumps(secret, ensure_ascii=False),
             values['sort_order'], combatant['id']))
        ordered_after = self.ordered_session_combatants(conn, session['id'])
        active_turn = next((index for index, item in enumerate(ordered_after) if item['id'] == active_id), 0)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET active_turn=?,updated=? WHERE id=?',
                     (active_turn, now, session['id']))
        after = dict(conn.execute('SELECT * FROM session_combatants WHERE id=?', (combatant['id'],)).fetchone())
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,combatant_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?,?)',
            (session['id'], user['id'], combatant['id'], 'combatant_update',
             json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
             str((body or {}).get('note') or '')[:500], now))
        conn.commit(); self.send_json({'ok': True})

    def api_session_combatant_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session or not self.can_edit_nc_session(conn, user, session):
            raise ApiError(403, 'Нет права редактировать сессию')
        ordered_before = self.ordered_session_combatants(conn, session['id'])
        combatant_id = int(m.group(2))
        combatant = next((item for item in ordered_before if item['id'] == combatant_id), None)
        if not combatant:
            raise ApiError(404, 'Участник сессии не найден')
        old_index = min(max(0, session['active_turn']), max(0, len(ordered_before) - 1))
        active_id = ordered_before[old_index]['id'] if ordered_before else None
        conn.execute('DELETE FROM session_combatants WHERE id=? AND session_id=?',
                     (combatant_id, session['id']))
        ordered_after = self.ordered_session_combatants(conn, session['id'])
        if active_id != combatant_id:
            active_turn = next((index for index, item in enumerate(ordered_after)
                                if item['id'] == active_id), 0)
        else:
            active_turn = old_index % len(ordered_after) if ordered_after else 0
        now = time.time()
        conn.execute('UPDATE nc_sessions SET active_turn=?,updated=? WHERE id=?',
                     (active_turn, now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,combatant_id,event_type,before_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], combatant_id, 'combatant_delete',
             json.dumps(dict(combatant), ensure_ascii=False),
             str((body or {}).get('note') or '')[:500], now))
        conn.commit(); self.send_json({'ok': True})

    def api_session_player_view(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session:
            raise ApiError(404, 'Сессия не найдена')
        allowed = self.can_edit_nc_session(conn, user, session)
        if not allowed and session['contract_id']:
            allowed = bool(conn.execute(
                "SELECT 1 FROM contract_signups WHERE contract_id=? AND user_id=? AND status='crew'",
                (session['contract_id'], user['id'])).fetchone())
        if not allowed:
            raise ApiError(403, 'Нет доступа к экрану сессии')
        self.send_json(self.session_payload(conn, session, user, player_view=True))

    def api_contract_aftermath(self, conn, qs, m, body):
        user = self.require_gm(conn)
        contract = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not contract or not can_edit_contract(conn, user, contract):
            raise ApiError(403, 'Нет права завершить контракт')
        aftermath_exists = conn.execute(
            "SELECT 1 FROM vk_outbox WHERE event_key IN (?,?) LIMIT 1",
            (f'contract:{contract["id"]}:completed', f'contract:{contract["id"]}:failed')).fetchone()
        if aftermath_exists or contract['status'] not in (
                'open', 'crew_full', 'in_progress', 'completed', 'failed'):
            raise ApiError(409, 'Aftermath уже опубликован или контракт не активен')
        result = str((body or {}).get('result') or 'completed').lower()
        if result not in ('completed', 'failed'):
            raise ApiError(400, 'Результат контракта: completed/failed')
        persona_id = _num((body or {}).get('author_persona_id'))
        persona = conn.execute('SELECT * FROM personas WHERE id=?', (persona_id,)).fetchone()
        if not persona or not can_manage_persona(user, persona):
            raise ApiError(400, 'Выберите доступную персону для Aftermath')
        headline = str((body or {}).get('headline') or f'Aftermath: {contract["title"]}')[:240]
        text = str((body or {}).get('body') or contract['public_brief'] or contract['teaser']).strip()[:30000]
        now = time.time()
        try:
            event_at = float((body or {}).get('event_at') or now)
        except (TypeError, ValueError):
            event_at = now
        if not math.isfinite(event_at):
            event_at = now
        cur = conn.execute(
            "INSERT INTO feed_posts(format,status,creator_user_id,author_persona_id,storyline_id,contract_id,"
            "headline,body,truth_status,event_at,published_at,created,updated) "
            "VALUES('article','published',?,?,?,?,?,?,'unknown',?,?,?,?)",
            (user['id'], persona_id, contract['storyline_id'], contract['id'], headline, text,
             event_at, now, now, now))
        post_id = cur.lastrowid
        conn.execute('UPDATE contracts SET status=?,updated=? WHERE id=?', (result, now, contract['id']))
        if contract['storyline_id']:
            conn.execute(
                'INSERT INTO storyline_timeline(storyline_id,event_at,public_text,private_text,contract_id,'
                'feed_post_id,created_by,created) VALUES(?,?,?,?,?,?,?,?)',
                (contract['storyline_id'], event_at,
                 headline, str((body or {}).get('private_note') or '')[:10000],
                 contract['id'], post_id, user['id'], now))
        crew_ids = {row['character_id'] for row in conn.execute(
            "SELECT character_id FROM contract_signups WHERE contract_id=? AND status='crew'",
            (contract['id'],)).fetchall() if row['character_id']}
        for reward in (body or {}).get('rewards') or []:
            character_id = _num(reward.get('character_id'))
            if character_id not in crew_ids:
                continue
            char_row = self.get_char(conn, character_id)
            before = json.loads(char_row['data'])
            data = ensure_progression(json.loads(char_row['data']))
            if data.get('archived'):
                continue
            try:
                cash = float(reward.get('cash') or 0)
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректная сумма')
            ip = _num(reward.get('ip')) or 0
            if not math.isfinite(cash) or abs(cash) > 10_000_000 or abs(ip) > 1_000_000:
                raise ApiError(400, 'Слишком большая сумма')
            data['cash'] = max(0, min(9_999_999, float(data.get('cash') or 0) + cash))
            if ip:
                ip_before = data['ip_available']; data['ip_available'] += ip
                if ip > 0: data['ip_total_earned'] += ip
                self.add_ip_ledger(conn, character_id, user['id'], ip, ip_before,
                                   data['ip_available'], 'contract', contract['title'], 'Contract Aftermath')
            record_character_changes(conn, character_id, user['id'], before, data,
                                     'Contract Aftermath', contract_id=contract['id'])
            conn.execute('UPDATE characters SET data=?,updated=? WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now, character_id))
        queue_vk_event(conn, f'contract:{contract["id"]}:{result}', f'contract_{result}',
                       contract['id'], {'contract_id': contract['id'], 'title': contract['title'], 'result': result})
        conn.commit(); self.send_json({'contract_id': contract['id'], 'post_id': post_id, 'result': result})

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
    ('GET', rx(r'/api/gm/users'), Handler.api_gm_users),
    ('GET', rx(r'/api/admin/users'), Handler.api_admin_users),
    ('POST', rx(r'/api/admin/users/(\d+)/role'), Handler.api_admin_user_role),
    ('GET', rx(r'/api/notifications'), Handler.api_notifications),
    ('POST', rx(r'/api/notifications/(\d+)/read'), Handler.api_notification_read),
    ('GET', rx(r'/api/admin/vk'), Handler.api_admin_vk_status),
    ('POST', rx(r'/api/admin/vk/flush'), Handler.api_admin_vk_flush),
    ('POST', rx(r'/api/vk/oauth/start'), Handler.api_vk_oauth_start),
    ('GET', rx(r'/api/vk/oauth/callback'), Handler.api_vk_oauth_callback),
    ('GET', rx(r'/api/personas'), Handler.api_personas),
    ('POST', rx(r'/api/personas'), Handler.api_persona_create),
    ('GET', rx(r'/api/personas/(\d+)'), Handler.api_persona_detail),
    ('PUT', rx(r'/api/personas/(\d+)'), Handler.api_persona_update),
    ('DELETE', rx(r'/api/personas/(\d+)'), Handler.api_persona_delete),
    ('GET', rx(r'/api/storylines'), Handler.api_storylines),
    ('POST', rx(r'/api/storylines'), Handler.api_storyline_create),
    ('GET', rx(r'/api/storylines/(\d+)'), Handler.api_storyline_detail),
    ('PUT', rx(r'/api/storylines/(\d+)'), Handler.api_storyline_update),
    ('POST', rx(r'/api/storylines/(\d+)/timeline'), Handler.api_storyline_timeline_create),
    ('GET', rx(r'/api/contracts'), Handler.api_contracts),
    ('POST', rx(r'/api/contracts'), Handler.api_contract_create),
    ('GET', rx(r'/api/contracts/(\d+)'), Handler.api_contract_detail),
    ('PUT', rx(r'/api/contracts/(\d+)'), Handler.api_contract_update),
    ('DELETE', rx(r'/api/contracts/(\d+)'), Handler.api_contract_delete),
    ('POST', rx(r'/api/contracts/(\d+)/join'), Handler.api_contract_join),
    ('POST', rx(r'/api/contracts/(\d+)/leave'), Handler.api_contract_leave),
    ('POST', rx(r'/api/contracts/(\d+)/aftermath'), Handler.api_contract_aftermath),
    ('GET', rx(r'/api/feed'), Handler.api_feed),
    ('POST', rx(r'/api/feed'), Handler.api_feed_create),
    ('GET', rx(r'/api/feed/(\d+)'), Handler.api_feed_detail),
    ('PUT', rx(r'/api/feed/(\d+)'), Handler.api_feed_update),
    ('POST', rx(r'/api/feed/(\d+)/hide'), Handler.api_feed_hide),
    ('POST', rx(r'/api/feed/(\d+)/comments'), Handler.api_feed_comment_create),
    ('POST', rx(r'/api/feed/(\d+)/comments/(\d+)/hide'), Handler.api_feed_comment_hide),
    ('GET', rx(r'/api/npc-templates'), Handler.api_npc_templates),
    ('POST', rx(r'/api/npc-templates'), Handler.api_npc_template_create),
    ('PUT', rx(r'/api/npc-templates/(\d+)'), Handler.api_npc_template_update),
    ('POST', rx(r'/api/npc-templates/(\d+)/clone'), Handler.api_npc_template_clone),
    ('DELETE', rx(r'/api/npc-templates/(\d+)'), Handler.api_npc_template_delete),
    ('GET', rx(r'/api/sessions'), Handler.api_sessions),
    ('POST', rx(r'/api/sessions'), Handler.api_session_create),
    ('GET', rx(r'/api/sessions/(\d+)'), Handler.api_session_detail),
    ('PUT', rx(r'/api/sessions/(\d+)'), Handler.api_session_update),
    ('GET', rx(r'/api/sessions/(\d+)/player-view'), Handler.api_session_player_view),
    ('POST', rx(r'/api/sessions/(\d+)/combatants'), Handler.api_session_combatant_create),
    ('PUT', rx(r'/api/sessions/(\d+)/combatants/(\d+)'), Handler.api_session_combatant_update),
    ('DELETE', rx(r'/api/sessions/(\d+)/combatants/(\d+)'), Handler.api_session_combatant_delete),
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
    ('GET', rx(r'/api/characters/(\d+)/ledger'), Handler.api_character_ledger),
    ('GET', rx(r'/api/characters/(\d+)/network'), Handler.api_character_network),
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


def vk_outbox_worker(stop_event):
    while not stop_event.is_set():
        try:
            conn = db()
            deliver_vk_outbox(conn, 20)
            conn.close()
        except Exception as error:  # background integration must not stop the web server
            sys.stderr.write(f'NC//NET VK worker: {error}\n')
        stop_event.wait(15)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--host', default='0.0.0.0')
    ap.add_argument('--port', type=int, default=8000)
    args = ap.parse_args()
    load_catalog()
    init_db()
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    vk_stop = threading.Event()
    vk_thread = None
    if os.environ.get('VK_COMMUNITY_TOKEN') and os.environ.get('VK_PEER_ID'):
        vk_thread = threading.Thread(target=vk_outbox_worker, args=(vk_stop,), daemon=True)
        vk_thread.start()
    print(f'NC//NET listening on http://{args.host}:{args.port}')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        vk_stop.set()
        if vk_thread:
            vk_thread.join(timeout=2)


if __name__ == '__main__':
    main()
