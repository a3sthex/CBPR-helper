"""Правила Cyberpunk RED/CEMK как данные и чистые функции (итерация P1-3).

Выделено из app/server.py: статы/навыки/роли, таблицы DV, критические
травмы и состояния ран (RU/EN), пайплайн модификаторов и рантайм
эффектов, derive() характеристик персонажа. Логика не менялась.

Обратные зависимости на mod-engine/inventory живут в _LATE и
подключаются через bind() из server.py до выделения их доменов.
"""
import copy
import json
import secrets
import time

from core import ACTIVE_EFFECT_DURATIONS, STATS
from catalog import item_by_id, load_effect_rules, validate_effect_definition


_LATE = {}


def bind(**kwargs):
    """Подключить поздние зависимости (см. docstring модуля)."""
    _LATE.update(kwargs)



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


def resolve_modifier_stack(modifiers):
    """Apply explicit stacking groups and return applied/suppressed modifiers."""
    groups = {}
    for modifier in modifiers:
        group = (modifier.get('target'), modifier.get('stack_group') or modifier.get('id'))
        groups.setdefault(group, []).append(copy.deepcopy(modifier))
    resolved = []
    for rows in groups.values():
        rows.sort(key=lambda item: (-int(item.get('priority', 100)), str(item.get('id') or '')))
        policy = rows[0].get('stack_policy', 'stack')
        selected = rows
        if policy == 'unique':
            selected = rows[:1]
        elif policy == 'highest':
            selected = [max(rows, key=lambda item: item.get('value', 0))]
        elif policy == 'lowest':
            selected = [min(rows, key=lambda item: item.get('value', 0))]
        elif policy == 'replace':
            selected = rows[:1]
        selected_ids = {id(item) for item in selected}
        for item in rows:
            item['applied'] = id(item) in selected_ids
            if not item['applied']:
                item['suppressed_reason'] = f'not stacked ({policy})'
            resolved.append(item)
    return sorted(resolved, key=lambda item: (
        str(item.get('target') or ''), int(item.get('priority', 100)), str(item.get('id') or '')))


def apply_modifier_pipeline(base_value, modifiers):
    applied = [item for item in resolve_modifier_stack(modifiers) if item.get('applied')]
    order = {'set': 0, 'minimum': 1, 'maximum': 1, 'add': 2, 'multiply': 3}
    applied.sort(key=lambda item: (
        order.get(item.get('operation'), 99), int(item.get('priority', 100)),
        str(item.get('id') or '')))
    value = base_value
    for item in applied:
        operation, amount = item['operation'], item['value']
        if operation == 'set':
            value = amount
        elif operation == 'minimum':
            value = max(value, amount)
        elif operation == 'maximum':
            value = min(value, amount)
        elif operation == 'add':
            value += amount
        elif operation == 'multiply':
            value *= amount
    # Some source effects define a floor for their complete modifier rather than
    # a separate operation. Apply the strictest declared floor after the whole
    # numeric pipeline so stacked penalties cannot push a protected STAT below it.
    floors = [item.get('minimum_value') for item in applied
              if item.get('minimum_value') is not None]
    if floors:
        value = max(value, max(floors))
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return value, resolve_modifier_stack(modifiers)




# ACTIVE_EFFECT_DURATIONS переехала в core.py; эти две остаются здесь
CUSTOM_EFFECT_DURATIONS = {'manual', 'real_time', 'rounds'}
ACTIVE_EFFECT_ACTIONS = {'enable', 'disable', 'tick'}


def effect_runtime_status(effect, now=None):
    now = time.time() if now is None else now
    if effect.get('archived_at'):
        return 'archived'
    duration = effect.get('duration_type') or 'manual'
    if duration == 'real_time' and effect.get('expires_at') is not None and effect['expires_at'] <= now:
        return 'expired'
    if duration == 'rounds' and (_num(effect.get('remaining_rounds')) or 0) <= 0:
        return 'completed'
    if not effect.get('active'):
        return 'disabled'
    return 'active'


def effect_instance_payload(row, now=None):
    item = dict(row)
    try:
        definition = json.loads(item.pop('definition_json'))
        validate_effect_definition(definition)
        valid = True
    except (TypeError, ValueError, json.JSONDecodeError, RuntimeError):
        definition, valid = {}, False
    try:
        context = json.loads(item.pop('context_json', '{}') or '{}')
        if not isinstance(context, dict):
            context = {}
    except (TypeError, ValueError, json.JSONDecodeError):
        context = {}
    item['definition'] = definition
    item['context'] = context
    item['active'] = bool(item.get('active'))
    item['valid'] = valid
    item['status'] = effect_runtime_status(item, now) if valid else 'invalid'
    item['effective_active'] = valid and item['status'] == 'active'
    if item.get('duration_type') == 'real_time' and item.get('expires_at') is not None:
        item['remaining_seconds'] = max(0, int(item['expires_at'] - (time.time() if now is None else now)))
    return item


def character_effect_instances(conn, character_id, include_archived=False):
    where = '' if include_archived else 'AND e.archived_at IS NULL'
    rows = conn.execute(
        'SELECT e.*,u.display_name actor FROM active_effect_instances e '
        'JOIN users u ON u.id=e.created_by WHERE e.character_id=? ' + where +
        ' ORDER BY e.created DESC,e.effect_id', (int(character_id),)).fetchall()
    now = time.time()
    return [effect_instance_payload(row, now) for row in rows]


def instantiate_consumable_effects(conn, character_id, actor_user_id, item_entry, now=None):
    """Create allowlisted effect snapshots for one consumed catalog item."""
    now = time.time() if now is None else now
    catalog_id = _LATE['catalog_item_id_for_entry'](item_entry)
    rules = [rule for rule in load_effect_rules().get('use_effect_rules') or []
             if rule.get('catalog_id') == catalog_id]
    created = []
    replaced = []
    for rule in rules:
        duration_type = rule['duration_type']
        duration_value = int(rule['duration_value'])
        expires_at = now + duration_value * 60 if duration_type == 'real_time' else None
        remaining_rounds = duration_value if duration_type == 'rounds' else None
        for definition in rule.get('effects') or []:
            stack_group = definition.get('stack_group') or definition['id']
            if definition.get('stack_policy') in ('replace', 'unique'):
                old_rows = conn.execute(
                    "SELECT * FROM active_effect_instances WHERE character_id=? "
                    "AND source_type='consumable' AND active=1 AND archived_at IS NULL",
                    (int(character_id),)).fetchall()
                for old_row in old_rows:
                    try:
                        old_definition = json.loads(old_row['definition_json'])
                    except (TypeError, ValueError, json.JSONDecodeError):
                        continue
                    if (old_definition.get('stack_group') or old_definition.get('id')) == stack_group:
                        conn.execute(
                            'UPDATE active_effect_instances SET active=0,updated=? WHERE effect_id=?',
                            (now, old_row['effect_id']))
                        replaced.append(old_row['effect_id'])
            effect_id = secrets.token_hex(16)
            label = str(rule.get('label_en') or rule['id'])[:120]
            if len(rule.get('effects') or []) > 1:
                label = f'{label}: {definition["target"]}'[:120]
            reason = f'Use {item_entry.get("custom_name") or item_entry.get("name") or catalog_id}'
            context = {
                'rules_version': load_effect_rules().get('rules_version'),
                'label_en': rule.get('label_en') or rule['id'],
                'label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
                'manual_rules': copy.deepcopy(rule.get('manual_rules') or []),
                'campaign_minutes': duration_value if duration_type == 'campaign_time' else None,
                'campaign_clock_manual': duration_type == 'campaign_time',
            }
            conn.execute(
                'INSERT INTO active_effect_instances(effect_id,character_id,source_type,'
                'source_item_instance_id,preset_id,label,definition_json,context_json,'
                'duration_type,started_at,expires_at,remaining_rounds,active,created_by,'
                'reason,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,1,?,?,?,?)',
                (effect_id, int(character_id), 'consumable', item_entry.get('instance_id'),
                 rule['id'], label, json.dumps(definition, ensure_ascii=False),
                 json.dumps(context, ensure_ascii=False), duration_type, now,
                 expires_at, remaining_rounds, int(actor_user_id), reason, now, now))
            row = conn.execute(
                'SELECT e.*,u.display_name actor FROM active_effect_instances e '
                'JOIN users u ON u.id=e.created_by WHERE e.effect_id=?',
                (effect_id,)).fetchone()
            created.append(effect_instance_payload(row, now))
    manual_rules = [
        copy.deepcopy(manual)
        for rule in rules for manual in rule.get('manual_rules') or []]
    return {'created': created, 'replaced_effect_ids': sorted(set(replaced)),
            'manual_rules': manual_rules}


def evaluate_character_effects(char, derived, active_effects=None):
    """Evaluate allowlisted declarative effects without mutating base Character data."""
    payload = load_effect_rules()
    inventory = [item for item in char.get('inventory') or [] if isinstance(item, dict)]
    cyberware = [item for item in char.get('cyberware') or [] if isinstance(item, dict)]
    owned_items = inventory + cyberware

    def installed_count(catalog_id, state='installed'):
        return sum(1 for item in cyberware
                   if _LATE['catalog_item_id_for_entry'](item) == catalog_id and
                   str(item.get('state') or 'installed') == state)

    modifiers = []
    synergies = []
    for rule in payload.get('synergy_rules') or []:
        requirements = []
        active = True
        for catalog_id, requirement in (rule.get('required_counts') or {}).items():
            minimum = max(1, int(requirement.get('minimum') or 1))
            current = installed_count(catalog_id, requirement.get('state') or 'installed')
            met = current >= minimum
            active = active and met
            requirements.append({
                'catalog_id': catalog_id,
                'label': requirement.get('label') or item_by_id(catalog_id)['name'],
                'current': current, 'required': minimum, 'met': met,
            })
        for requirement in rule.get('required_all') or []:
            catalog_id = requirement['catalog_id']
            current = installed_count(catalog_id, requirement.get('state') or 'installed')
            met = current >= 1
            active = active and met
            requirements.append({
                'catalog_id': catalog_id,
                'label': requirement.get('label') or item_by_id(catalog_id)['name'],
                'current': min(current, 1), 'required': 1, 'met': met,
            })
        effects = []
        for definition in rule.get('effects') or []:
            effect = copy.deepcopy(definition)
            effect.update({
                'rule_id': rule['id'], 'rule_label_en': rule.get('label_en') or rule['id'],
                'rule_label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
                'active': active,
            })
            effects.append(effect)
            if active:
                modifiers.append(effect)
        synergies.append({
            'id': rule['id'], 'label_en': rule.get('label_en') or rule['id'],
            'label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
            'active': active, 'requirements': requirements, 'effects': effects,
        })

    item_sources = []
    for rule in payload.get('item_effect_rules') or []:
        matching = [item for item in owned_items
                    if _LATE['catalog_item_id_for_entry'](item) == rule['catalog_id']]
        if not matching:
            continue
        condition = rule.get('active_when') or {}
        active_instances = []
        for item in matching:
            state_ok = str(item.get('state') or 'carried') == condition.get('state')
            active_ok = ('active' not in condition or
                         bool(item.get('active')) == condition.get('active'))
            if state_ok and active_ok:
                active_instances.append(item)
        active = bool(active_instances)
        effects = []
        for definition in rule.get('effects') or []:
            effect = copy.deepcopy(definition)
            effect.update({
                'rule_id': rule['id'], 'rule_label_en': rule.get('label_en') or rule['id'],
                'rule_label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
                'active': active, 'source_type': 'catalog_item',
            })
            effects.append(effect)
            if active:
                modifiers.append(effect)
        item_sources.append({
            'id': rule['id'], 'catalog_id': rule['catalog_id'],
            'label_en': rule.get('label_en') or rule['id'],
            'label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
            'active': active,
            'matching_instance_ids': [item.get('instance_id') for item in matching],
            'active_instance_ids': [item.get('instance_id') for item in active_instances],
            'active_when': copy.deepcopy(condition), 'effects': effects,
            'manual_rules': [
                {**copy.deepcopy(manual), 'manual_resolution_required': True}
                for manual in rule.get('manual_rules') or []],
        })

    instances = []
    for raw_instance in active_effects or []:
        instance = copy.deepcopy(raw_instance)
        definition = instance.get('definition')
        valid = bool(instance.get('valid', True))
        if valid:
            try:
                validate_effect_definition(definition)
            except RuntimeError:
                valid = False
        runtime_active = valid and effect_runtime_status(instance) == 'active'
        public_instance = {
            key: copy.deepcopy(instance.get(key)) for key in (
                'effect_id', 'label', 'source_type', 'source_item_instance_id',
                'preset_id', 'context', 'duration_type', 'started_at', 'expires_at', 'remaining_rounds',
                'session_id', 'active', 'archived_at', 'actor', 'reason')
        }
        public_instance.update({
            'definition': copy.deepcopy(definition) if valid else {},
            'valid': valid, 'status': effect_runtime_status(instance) if valid else 'invalid',
            'effective_active': runtime_active,
        })
        if instance.get('remaining_seconds') is not None:
            public_instance['remaining_seconds'] = instance['remaining_seconds']
        instances.append(public_instance)
        if runtime_active:
            modifier = copy.deepcopy(definition)
            modifier.update({
                'effect_instance_id': instance.get('effect_id'),
                'rule_id': f'instance:{instance.get("effect_id")}',
                'rule_label_en': instance.get('label') or definition['id'],
                'rule_label_ru': instance.get('label') or definition['id'],
                'source': instance.get('label') or definition.get('source') or 'Active Effect',
                'active': True,
            })
            modifiers.append(modifier)

    by_target = {}
    for modifier in modifiers:
        by_target.setdefault(modifier['target'], []).append(modifier)

    stats = {}
    for stat in STATS:
        base = _num((char.get('stats') or {}).get(stat)) or 0
        stat_modifiers = list(by_target.get(f'character.stat.{stat}', []))
        armor_penalty = _num((derived.get('armor_penalties') or {}).get(stat)) or 0
        if armor_penalty:
            stat_modifiers.append({
                'id': f'armor-penalty-{stat.lower()}', 'target': f'character.stat.{stat}',
                'operation': 'add', 'value': armor_penalty,
                'stack_group': f'armor_penalty_{stat.lower()}', 'stack_policy': 'lowest',
                'priority': 100, 'source': 'Equipped Armor', 'active': True,
            })
        if stat == 'EMP' and derived.get('emp_cur') is not None:
            stat_modifiers.append({
                'id': 'humanity-current-emp', 'target': 'character.stat.EMP',
                'operation': 'set', 'value': derived['emp_cur'],
                'stack_group': 'humanity_current_emp', 'stack_policy': 'replace',
                'priority': 50, 'source': 'Current Humanity', 'active': True,
            })
        effective, breakdown = apply_modifier_pipeline(base, stat_modifiers)
        stats[stat] = {'base': base, 'effective': effective, 'modifiers': breakdown}

    skills = {}
    for name, metadata in SKILL_BY_NAME.items():
        stat = metadata[2]
        level = _num((char.get('skills') or {}).get(name)) or 0
        check_modifiers = list(by_target.get(f'skill.{name}.check', []))
        check_modifier, breakdown = apply_modifier_pipeline(0, check_modifiers)
        stat_effective = stats.get(stat, {'effective': 0})['effective']
        skills[name] = {
            'stat': stat, 'stat_effective': stat_effective,
            'level_base': level, 'check_modifier': check_modifier,
            'effective_check_base': stat_effective + level + check_modifier,
            'modifiers': breakdown,
        }
    return {
        'rules_version': payload.get('rules_version'),
        'stats': stats, 'skills': skills,
        'synergies': synergies, 'item_sources': item_sources, 'instances': instances,
        'modifiers': resolve_modifier_stack(modifiers),
    }


def derive(char, active_effects=None):
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
        if str(chrome.get('state') or 'installed') != 'installed':
            continue
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
    armor_hosts = _LATE['effective_armor_hosts'](char)
    armor_host_by_id = {item['instance_id']: item for item in armor_hosts['hosts']}
    body_pieces = [armor.get('body'), armor.get('body_outer'), armor.get('body_inner')]
    head_pieces = [armor.get('head')]
    body_pieces = [copy.deepcopy(a) for a in body_pieces if isinstance(a, dict)]
    head_pieces = [copy.deepcopy(a) for a in head_pieces if isinstance(a, dict)]
    for piece in body_pieces + head_pieces:
        host = armor_host_by_id.get(piece.get('instance_id'))
        if host and host.get('effective_sp') is not None:
            piece['sp'] = host['effective_sp']
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
    out['effects'] = evaluate_character_effects(char, out, active_effects)
    out['effective_stats'] = {
        stat: values['effective'] for stat, values in out['effects']['stats'].items()
    }
    out['effective_cyberware'] = _LATE['effective_cyberware_loadout'](char)
    out['effective_armor_hosts'] = armor_hosts
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
