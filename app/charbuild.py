"""Сборка и валидация персонажа + Tech Maker NC//NET (итерация P1-5).

Выделено из app/server.py: валидация создания (очки 62/86, роли,
lifepath-ограничения), нормализация clean_character, правила
изготовления/улучшения Tech Maker и эффективная нагрузка брони/
кибердеки. Логика не менялась; обратные зависимости на
inventory/progression — через bind() (docs/repo-audit-2026-08.md).
"""
import copy, json, math, re, time

from core import (ApiError, CHARACTER_VISIBILITY_DEFAULTS, INSTANCE_ID_RE,
                  ITEM_INSTANCE_STATES, STATS, ensure_character_visibility,
                  parse_json_object)
from rules import (CULTURAL_LANGUAGES, CUSTOM_EFFECT_DURATIONS, MUST_SKILLS,
                   ROLES, SKILL_BY_NAME, SKILL_MAX_CREATION, SKILL_POINTS,
                   SPECIALIZED_SKILLS, START_CASH_FASHION, START_CASH_GEAR,
                   STAT_POINTS, _armor_penalties, _num, derive)
from catalog import (ITEM_INTERACTION_FIELDS, ITEM_MODIFICATION_FIELDS, catalog,
                     item_by_id, item_effect_coverage, validate_effect_definition,
                     weapon_range_table_info)
from mod_engine import ammo_pack_size, ammo_rounds, shared_ammo_available


_LATE = {}


def bind(**kwargs):
    """Подключить поздние зависимости (см. docstring модуля)."""
    _LATE.update(kwargs)



MAX_CHAR_BYTES = 300_000
CHARACTER_PROFILE_FIELDS = {'notes', 'portrait_media_id', 'public', 'visibility'}


def public_character_data(data):
    """Return an allowlisted Dossier view; private sheet fields never cross the API."""
    source = copy.deepcopy(data if isinstance(data, dict) else {})
    visibility = ensure_character_visibility(source)
    allowed = {
        'handle', 'role', 'role_rank', 'primary_role', 'active_role', 'roles',
        'public', 'archived', 'archive_reason', 'schema_version', 'seed', 'visibility',
    }
    if visibility['portrait']:
        allowed.add('portrait_media_id')
    if visibility['identity']:
        allowed.update({'first_name', 'last_name'})
    if visibility['biography']:
        allowed.update({'appearance', 'background', 'languages', 'native_language',
                        'lifestyle', 'housing'})
    if visibility['stats']:
        allowed.add('stats')
    if visibility['skills']:
        allowed.update({'skills', 'skill_pools', 'skill_specializations'})
    if visibility['lifepath']:
        allowed.update({'lifepath', 'role_lifepath', 'lifepath_mode'})
    if visibility['equipment']:
        allowed.update({'inventory', 'cyberware', 'armor', 'weapon_state'})
    if visibility['combat']:
        allowed.update({'hp_cur', 'humanity_cur', 'luck_cur', 'reputation'})
    if visibility['player_name']:
        allowed.add('player')
    public = {key: source[key] for key in allowed if key in source}
    # Mini-dossier highlight: top-5 skills (excluding Language) so a public
    # profile reads like a hireable operator card without exposing every skill.
    skills_source = source.get('skills') if isinstance(source.get('skills'), dict) else {}
    top_pairs = []
    for name, level in skills_source.items():
        if name == 'Language':
            continue
        try:
            value = int(level)
        except (TypeError, ValueError):
            try:
                value = int(float(level))
            except (TypeError, ValueError):
                continue
        top_pairs.append((str(name), value))
    top_pairs.sort(key=lambda item: item[1], reverse=True)
    public['top_skills'] = [{'name': name, 'level': level}
                            for name, level in top_pairs[:5]]
    for bucket in ('inventory', 'cyberware'):
        if isinstance(public.get(bucket), list):
            for entry in public[bucket]:
                if isinstance(entry, dict):
                    entry.pop('notes', None)
                    entry.pop('acquisition_note', None)
    if isinstance(public.get('roles'), list):
        public['roles'] = [{
            key: role[key] for key in ('name', 'rank', 'primary') if key in role
        } for role in public['roles'] if isinstance(role, dict)]
    return public


def character_author_payload(character):
    if not character:
        return None
    data = parse_json_object(character['data'])
    visibility = ensure_character_visibility(data)
    return {
        'id': character['id'], 'kind': 'character',
        'display_name': data.get('handle') or 'Unknown Edgerunner',
        'handle': data.get('handle') or 'unknown',
        'avatar_media_id': data.get('portrait_media_id') if visibility['portrait'] else None,
        'accent_color': '#ff2d78',
    }


def clean_character_profile_patch(old_data, body):
    """Return the small owner-editable Dossier patch.

    Character mechanics are deliberately immutable through the generic PUT endpoint.
    Progression, resources, inventory and rewards have dedicated server-side commands.
    A legacy full ``data`` payload is accepted only when every non-profile field is
    byte-for-byte equivalent to the stored sheet, so old clients cannot overwrite it.
    """
    if not isinstance(body, dict):
        raise ApiError(400, 'Изменение досье должно быть объектом')
    raw_size = len(json.dumps(body, ensure_ascii=False).encode())
    if raw_size > MAX_CHAR_BYTES:
        raise ApiError(413, 'Лист персонажа слишком большой')

    if 'patch' in body:
        patch = body.get('patch')
        if not isinstance(patch, dict):
            raise ApiError(400, 'patch должен быть объектом')
        unknown = set(patch) - CHARACTER_PROFILE_FIELDS
        if unknown:
            raise ApiError(400, 'Механические поля изменяются только специальными операциями')
    elif 'data' in body:
        incoming = body.get('data')
        if not isinstance(incoming, dict):
            raise ApiError(400, 'Лист персонажа должен быть объектом')
        changed = {key for key in set(old_data) | set(incoming)
                   if old_data.get(key) != incoming.get(key)}
        protected = changed - CHARACTER_PROFILE_FIELDS
        if protected:
            raise ApiError(400, 'Механические поля изменяются только специальными операциями')
        patch = {key: incoming.get(key) for key in changed}
    else:
        patch = {key: value for key, value in body.items() if key != 'reason'}
        unknown = set(patch) - CHARACTER_PROFILE_FIELDS
        if unknown:
            raise ApiError(400, 'Механические поля изменяются только специальными операциями')

    clean = {}
    if 'notes' in patch:
        clean['notes'] = str(patch.get('notes') or '')[:20_000]
    if 'portrait_media_id' in patch:
        media_id = str(patch.get('portrait_media_id') or '')
        if media_id and not re.fullmatch(r'[a-f0-9]{32}', media_id):
            raise ApiError(400, 'Недопустимое изображение персонажа')
        clean['portrait_media_id'] = media_id
    if 'public' in patch:
        if not isinstance(patch['public'], bool):
            raise ApiError(400, 'public должен быть логическим значением')
        clean['public'] = patch['public']
    if 'visibility' in patch:
        visibility = patch.get('visibility')
        if not isinstance(visibility, dict):
            raise ApiError(400, 'visibility должен быть объектом')
        unknown = set(visibility) - set(CHARACTER_VISIBILITY_DEFAULTS)
        if unknown or any(not isinstance(value, bool) for value in visibility.values()):
            raise ApiError(400, 'Некорректные настройки видимости Dossier')
        clean['visibility'] = {
            key: visibility.get(key, old_data.get('visibility', {}).get(key, default))
            for key, default in CHARACTER_VISIBILITY_DEFAULTS.items()
        }
    return clean


def clean_character(data):
    if not isinstance(data, dict):
        raise ApiError(400, 'Лист персонажа должен быть объектом')
    raw = json.dumps(data, ensure_ascii=False)
    if len(raw.encode()) > MAX_CHAR_BYTES:
        raise ApiError(413, 'Лист персонажа слишком большой')
    out = dict(data)
    # Runtime/audit containers are server-owned and never accepted on creation.
    out.pop('cyberware_state', None)
    out.pop('therapy_state', None)
    out.pop('armor_tech_state', None)
    out.pop('armor_repair_state', None)
    out.pop('tech_maker_state', None)
    out.pop('downtime_state', None)
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
    progressed = _LATE['ensure_progression'](out)
    ensure_character_visibility(progressed)
    if any(role.get('role_lifepath') for role in progressed.get('roles', []) if not role.get('primary')):
        raise ApiError(400, 'Role-Based Lifepath разрешён только primary Role')
    return progressed


TRUST_EDIT_TEXT_LIMITS = {
    'handle': 60, 'first_name': 60, 'last_name': 60, 'player': 120,
    'appearance': 4000, 'background': 4000, 'languages': 500,
    'lifestyle': 200, 'housing': 200, 'notes': 20000,
}
ITEM_ACQUISITION_SOURCES = {
    'loot', 'gift', 'crafted', 'role_access', 'gm_award', 'custom', 'other',
    'fixer',
}


def clean_item_acquisition(entry, owned, require_source=False):
    source = str(entry.get('acquisition_source') or owned.get('acquisition_source') or '').strip().lower()
    if require_source and not source:
        source = 'loot'
    if source and source not in ITEM_ACQUISITION_SOURCES:
        raise ApiError(400, 'Некорректный источник получения предмета')
    if source:
        owned['acquisition_source'] = source
    note_value = entry.get('acquisition_note') if 'acquisition_note' in entry else owned.get('acquisition_note')
    note = str(note_value or '').strip()[:500]
    if note:
        owned['acquisition_note'] = note
    else:
        owned.pop('acquisition_note', None)


def trust_number(value, label, minimum, maximum, integer=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ApiError(400, f'{label}: требуется число')
    if not math.isfinite(number) or number < minimum or number > maximum:
        raise ApiError(400, f'{label}: допустимо от {minimum} до {maximum}')
    return int(number) if integer else round(number, 2)


def clean_custom_effect(body, effect_id):
    if not isinstance(body, dict):
        raise ApiError(400, 'Effect должен быть объектом')
    allowed = {
        'revision', 'label', 'target', 'operation', 'value', 'stack_policy',
        'stack_group', 'duration_type', 'duration_value', 'reason',
    }
    if set(body) - allowed:
        raise ApiError(400, 'Effect содержит неподдерживаемые поля')
    label = str(body.get('label') or '').strip()[:120]
    reason = str(body.get('reason') or '').strip()[:500]
    if not label:
        raise ApiError(400, 'Укажите название эффекта')
    if len(reason) < 3:
        raise ApiError(400, 'Укажите причину эффекта')
    target = str(body.get('target') or '').strip()
    operation = str(body.get('operation') or 'add').strip().lower()
    try:
        value = float(body.get('value'))
    except (TypeError, ValueError):
        raise ApiError(400, 'Effect value должен быть числом')
    if not math.isfinite(value) or abs(value) > 100:
        raise ApiError(400, 'Effect value должен быть от -100 до 100')
    if operation == 'multiply' and not (0 <= value <= 10):
        raise ApiError(400, 'Multiply effect должен быть от 0 до 10')
    if value.is_integer():
        value = int(value)
    stack_policy = str(body.get('stack_policy') or 'stack').strip().lower()
    stack_group = str(body.get('stack_group') or f'custom_{effect_id}').strip().lower()
    if not re.fullmatch(r'[a-z0-9_.-]{1,80}', stack_group):
        raise ApiError(400, 'Некорректная stacking group')
    definition = {
        'id': f'custom-{effect_id}', 'target': target,
        'operation': operation, 'value': value,
        'stack_group': stack_group, 'stack_policy': stack_policy,
        'priority': 500, 'source': 'Custom Effect',
    }
    try:
        validate_effect_definition(definition)
    except RuntimeError as error:
        raise ApiError(400, str(error))
    duration_type = str(body.get('duration_type') or 'manual').strip().lower()
    if duration_type not in CUSTOM_EFFECT_DURATIONS:
        raise ApiError(400, 'Некорректный тип длительности эффекта')
    expires_at = None
    remaining_rounds = None
    duration_value = None
    if duration_type == 'real_time':
        duration_value = trust_number(body.get('duration_value'), 'Duration minutes', 1, 10080, integer=True)
        expires_at = time.time() + duration_value * 60
    elif duration_type == 'rounds':
        duration_value = trust_number(body.get('duration_value'), 'Duration rounds', 1, 100, integer=True)
        remaining_rounds = duration_value
    return {
        'label': label, 'reason': reason, 'definition': definition,
        'duration_type': duration_type, 'duration_value': duration_value,
        'expires_at': expires_at, 'remaining_rounds': remaining_rounds,
    }


def canonical_owned_entry(entry, bucket, old_entries):
    if not isinstance(entry, dict):
        raise ApiError(400, 'Inventory должен содержать объекты')
    instance_id = str(entry.get('instance_id') or '').lower()
    existing = old_entries.get(instance_id) if INSTANCE_ID_RE.fullmatch(instance_id) else None
    catalog_id = _LATE['catalog_item_id_for_entry'](entry) or _LATE['catalog_item_id_for_entry'](existing)
    custom = not catalog_id and bool(entry.get('is_custom') or (existing or {}).get('is_custom'))
    if not catalog_id and custom:
        if bucket != 'inventory':
            raise ApiError(400, 'Custom Cyberware требует отдельной механики установки')
        name = str(entry.get('custom_name') or entry.get('name') or
                   (existing or {}).get('custom_name') or (existing or {}).get('name') or '').strip()[:120]
        if not name:
            raise ApiError(400, 'Custom item требует название')
        category = str(entry.get('cat') or (existing or {}).get('cat') or 'custom').strip().lower()
        allowed_categories = {row['id'] for row in catalog().get('cats') or []} | {'custom'}
        if category not in allowed_categories:
            raise ApiError(400, 'Некорректная категория custom item')
        price = trust_number(entry.get('price', (existing or {}).get('price') or 0),
                             'Custom item value', 0, 9_999_999)
        stackable = entry.get('stackable', (existing or {}).get('stackable', False))
        if not isinstance(stackable, bool):
            raise ApiError(400, 'stackable должен быть логическим значением')
        owned = copy.deepcopy(existing or {})
        owned.update({
            'is_custom': True, 'key': str(owned.get('key') or 'custom'),
            'cat': category, 'name': name, 'custom_name': name,
            'desc': str(entry.get('desc') if 'desc' in entry else owned.get('desc') or '')[:4000],
            'price': price, 'stackable': stackable, 'state': str(entry.get('state') or owned.get('state') or 'carried'),
            'source': 'Custom / Trust + Audit', 'manual_resolution_required': True,
        })
        for unsafe in ('catalog_item_id', 'source_key', 'damage', 'sp', 'hl', 'fields',
                       'mechanics', 'requirements', 'capacity', 'type',
                       *ITEM_INTERACTION_FIELDS, *ITEM_MODIFICATION_FIELDS,
                       'effect_coverage', 'active', 'equipped_mode',
                       'equipped_slot', 'host_instance_id'):
            owned.pop(unsafe, None)
        # Custom items may control storage shape, but never Use/Equip mechanics.
        owned['stackable'] = stackable
    elif not catalog_id:
        if not existing:
            raise ApiError(400, 'Неизвестный предмет: выберите Database item или создайте Custom item')
        owned = copy.deepcopy(existing)
        for key in ('custom_name', 'notes', 'state', 'qty',
                    'acquisition_source', 'acquisition_note'):
            if key in entry:
                owned[key] = entry[key]
    else:
        item = item_by_id(catalog_id)
        if not item or (bucket == 'cyberware') != (item.get('cat') == 'cyberware'):
            raise ApiError(400, 'Предмет находится в неправильном разделе Inventory')
        owned = copy.deepcopy(entry)
        raw_key = str(entry.get('key') or catalog_id)
        if raw_key.split('@', 1)[0] != catalog_id:
            raw_key = catalog_id
        owned.update({
            'key': raw_key, 'catalog_item_id': catalog_id, 'cat': item['cat'],
            'name': item['name'], 'damage': item.get('damage'),
            'sp': item.get('sp'), 'hl': item.get('hl'),
            'fields': copy.deepcopy(item.get('fields') or {}),
            'mechanics': copy.deepcopy(item.get('mechanics') or {}),
            'requirements': copy.deepcopy(item.get('requirements') or []),
            'capacity': copy.deepcopy(item.get('capacity')),
            'source': item.get('source'),
            'price': (existing or {}).get('price', item.get('price') or 0),
        })
        for key in ITEM_INTERACTION_FIELDS + ITEM_MODIFICATION_FIELDS:
            if key in item:
                owned[key] = copy.deepcopy(item[key])
            else:
                owned.pop(key, None)
        coverage = item_effect_coverage(catalog_id)
        if coverage:
            owned['effect_coverage'] = coverage
        else:
            owned.pop('effect_coverage', None)
        owned.pop('is_custom', None)
    try:
        owned['qty'] = max(1, min(999, int(entry.get('qty') or owned.get('qty') or 1)))
    except (TypeError, ValueError):
        raise ApiError(400, 'Некорректное количество')
    if owned.get('cat') == 'ammo':
        pack_size = ammo_pack_size(owned)
        if existing:
            old_qty = max(1, int(_num(existing.get('qty')) or 1))
            old_rounds = ammo_rounds(existing)
            quantity_delta = owned['qty'] - old_qty
            owned['ammo_rounds'] = max(
                0, min(owned['qty'] * pack_size,
                       old_rounds + max(0, quantity_delta) * pack_size))
        else:
            owned['ammo_rounds'] = owned['qty'] * pack_size
    if INSTANCE_ID_RE.fullmatch(instance_id):
        owned['instance_id'] = instance_id
    else:
        owned.pop('instance_id', None)
    if not custom:
        custom_name_value = entry.get('custom_name') if 'custom_name' in entry else owned.get('custom_name')
        owned['custom_name'] = str(custom_name_value or '')[:120]
    notes_value = entry.get('notes') if 'notes' in entry else owned.get('notes')
    owned['notes'] = str(notes_value or '')[:2000]
    if bucket == 'cyberware':
        # Concrete host links and installation state are changed only through the
        # audited Cyberware lifecycle endpoint, never through a generic sheet PUT.
        for key in ('host_instance', 'host_instances', 'installation_side'):
            if existing and key in existing:
                owned[key] = copy.deepcopy(existing[key])
            else:
                owned.pop(key, None)
        state = str((existing or {}).get('state') or
                    ('installed' if existing else 'carried'))
    else:
        state = str(entry.get('state') or owned.get('state') or 'carried')
    if state not in ITEM_INSTANCE_STATES:
        raise ApiError(400, 'Некорректное состояние предмета')
    if bucket == 'inventory' and state == 'equipped' and owned.get('cat') != 'armor':
        if custom or not owned.get('equippable'):
            raise ApiError(400, 'Этот предмет нельзя экипировать')
        if not existing or existing.get('state') != 'equipped':
            raise ApiError(400, 'Используйте действие Equip в Character Sheet')
        for key in ('active', 'equipped_mode', 'equipped_slot', 'host_instance_id'):
            if key in existing:
                owned[key] = copy.deepcopy(existing[key])
            else:
                owned.pop(key, None)
    elif state != 'equipped':
        for key in ('active', 'equipped_mode', 'equipped_slot', 'host_instance_id'):
            owned.pop(key, None)
    owned['state'] = state
    clean_item_acquisition(entry, owned, require_source=existing is None)
    return owned


def clean_character_trust_update(old_data, incoming):
    """Validate an owner-authored Trust + Audit sheet without creation-budget rules."""
    if not isinstance(incoming, dict):
        raise ApiError(400, 'Лист персонажа должен быть объектом')
    if len(json.dumps(incoming, ensure_ascii=False).encode()) > MAX_CHAR_BYTES:
        raise ApiError(413, 'Лист персонажа слишком большой')
    data = copy.deepcopy(old_data)
    for key, maximum in TRUST_EDIT_TEXT_LIMITS.items():
        if key in incoming:
            value = str(incoming.get(key) or '')[:maximum]
            data[key] = value.strip() if key in ('handle', 'first_name', 'last_name') else value
    if not data.get('handle'):
        raise ApiError(400, 'Нужен псевдоним (Handle) персонажа')

    role = str(incoming.get('role', data.get('role') or '')).strip()
    if role not in ROLES:
        raise ApiError(400, 'Неизвестная Role')
    rank = trust_number(incoming.get('role_rank', data.get('role_rank') or 4),
                        'Role Rank', 1, 10, integer=True)
    previous_role = str(data.get('role') or '')
    data['role'], data['role_rank'] = role, rank
    roles = copy.deepcopy(data.get('roles') or [])
    primary = next((item for item in roles if isinstance(item, dict) and item.get('primary')), None)
    if primary:
        old_primary_name = str(primary.get('name') or previous_role)
        primary['name'], primary['rank'], primary['primary'] = role, rank, True
        if data.get('active_role') == old_primary_name:
            data['active_role'] = role
    else:
        roles.insert(0, {'name': role, 'rank': rank, 'primary': True,
                         'setup': copy.deepcopy(data.get('role_setup') or {})})
    if len({item.get('name') for item in roles if isinstance(item, dict)}) != len(roles):
        raise ApiError(400, 'У персонажа не может быть двух одинаковых Roles')
    data['roles'], data['primary_role'] = roles, role

    if 'stats' in incoming:
        raw_stats = incoming.get('stats')
        if not isinstance(raw_stats, dict):
            raise ApiError(400, 'stats должен быть объектом')
        stats = {}
        for stat in STATS:
            if stat in raw_stats:
                stats[stat] = trust_number(raw_stats[stat], stat, 1, 13, integer=True)
            elif stat in (data.get('stats') or {}):
                stats[stat] = data['stats'][stat]
        data['stats'] = stats

    if 'skills' in incoming:
        raw_skills = incoming.get('skills')
        if not isinstance(raw_skills, dict) or len(raw_skills) > 500:
            raise ApiError(400, 'skills должен быть объектом до 500 записей')
        skills = {}
        old_skills = data.get('skills') or {}
        for name, value in raw_skills.items():
            name = str(name).strip()[:120]
            if not skill_base(name) and name not in old_skills:
                raise ApiError(400, f'Неизвестный Skill: {name}')
            skills[name] = trust_number(value, f'Skill {name}', 0, 10, integer=True)
        data['skills'] = skills
    if 'skill_pools' in incoming:
        pools = incoming.get('skill_pools')
        if not isinstance(pools, dict) or set(pools) - SPECIALIZED_SKILLS:
            raise ApiError(400, 'skill_pools содержит неизвестный специализированный навык')
        data['skill_pools'] = {
            key: trust_number(value, f'{key} Pool', 0, 10, integer=True)
            for key, value in pools.items()
        }
    if 'native_language' in incoming:
        data['native_language'] = str(incoming.get('native_language') or '')[:120]

    for key, label, minimum, maximum, integer in (
            ('cash', 'Cash', 0, 9_999_999, False),
            ('reputation', 'Reputation', 0, 10, True),
            ('hp_cur', 'Current HP', -1000, 1000, True),
            ('humanity_cur', 'Current Humanity', 0, 100, True),
            ('luck_cur', 'Current LUCK', 0, 20, True)):
        if key in incoming and incoming[key] is not None:
            data[key] = trust_number(incoming[key], label, minimum, maximum, integer)
        elif key in incoming:
            data[key] = None
    if 'ip_available' in incoming:
        old_ip = _num(data.get('ip_available')) or 0
        new_ip = trust_number(incoming['ip_available'], 'Available IP', 0, 1_000_000, integer=True)
        delta = new_ip - old_ip
        data['ip_available'] = new_ip
        if delta > 0:
            data['ip_total_earned'] = (_num(data.get('ip_total_earned')) or old_ip) + delta
        elif delta < 0:
            data['ip_total_spent'] = (_num(data.get('ip_total_spent')) or 0) - delta
    if 'public' in incoming:
        if not isinstance(incoming['public'], bool):
            raise ApiError(400, 'public должен быть логическим значением')
        data['public'] = incoming['public']

    old_entries = {}
    for bucket in ('inventory', 'cyberware'):
        for entry in old_data.get(bucket) or []:
            if isinstance(entry, dict) and INSTANCE_ID_RE.fullmatch(str(entry.get('instance_id') or '')):
                old_entries[entry['instance_id']] = entry
        if bucket in incoming:
            entries = incoming.get(bucket)
            if not isinstance(entries, list) or len(entries) > 500:
                raise ApiError(400, f'{bucket}: ожидается список до 500 записей')
            data[bucket] = [canonical_owned_entry(entry, bucket, old_entries) for entry in entries]
    _LATE['ensure_character_item_instances'](data)
    valid_cyberware_ids = {item.get('instance_id') for item in data.get('cyberware') or []
                           if isinstance(item, dict) and item.get('instance_id')}
    if isinstance(data.get('cyberware_state'), dict):
        data['cyberware_state'] = {
            key: value for key, value in data['cyberware_state'].items()
            if key in valid_cyberware_ids and isinstance(value, dict)}
    if len(data.get('inventory') or []) + len(data.get('cyberware') or []) > 500:
        raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')

    raw_armor = incoming.get('armor', data.get('armor') or {})
    if not isinstance(raw_armor, dict):
        raise ApiError(400, 'armor должен быть объектом')
    armor = {}
    inventory = [entry for entry in data.get('inventory') or []
                 if isinstance(entry, dict) and entry.get('cat') == 'armor']
    for entry in inventory:
        if entry.get('state') == 'equipped':
            entry['state'] = 'carried'
    used = set()
    for location in ('head', 'body', 'shield'):
        piece = raw_armor.get(location)
        if not piece:
            continue
        if not isinstance(piece, dict):
            raise ApiError(400, f'Armor {location}: ожидается объект')
        catalog_id = _LATE['catalog_item_id_for_entry'](piece)
        item = item_by_id(catalog_id)
        if not item or item.get('cat') != 'armor' or location not in (item.get('armor_locations') or []):
            raise ApiError(400, f'Недопустимая броня для локации {location}')
        instance_id = str(piece.get('instance_id') or '')
        bundled = bool(piece.get('bundled') or item.get('armor_bundled'))
        owned = next((entry for entry in inventory
                      if entry.get('instance_id') == instance_id), None)
        if not owned:
            owned = next((entry for entry in inventory
                          if _LATE['catalog_item_id_for_entry'](entry) == catalog_id and
                          (entry.get('instance_id') not in used or bundled)), None)
        if not owned:
            raise ApiError(400, f'Броня {item["name"]} отсутствует в Inventory')
        used.add(owned['instance_id'])
        owned['state'] = 'equipped'
        tech_state = (data.get('armor_tech_state') or {}).get(owned['instance_id']) or {}
        base_maximum = (armor_shield_hp(item) if location == 'shield' else
                        (_num(item.get('sp')) or _num(item.get('sdp')) or 0))
        automated_sp_upgrade = (
            location != 'shield' and tech_state.get('active') is True and
            tech_state.get('mode') == 'sp_plus_one')
        maximum = base_maximum + (1 if automated_sp_upgrade else 0)
        current = _num(piece.get('current'))
        armor[location] = {
            'key': str(piece.get('key') or owned.get('key') or catalog_id),
            'source_key': catalog_id, 'catalog_item_id': catalog_id,
            'instance_id': owned['instance_id'], 'name': item['name'],
            'sp': maximum if location != 'shield' else item.get('sp'),
            'sdp': maximum if location == 'shield' else item.get('sdp'),
            'penalties': copy.deepcopy(item.get('penalties') or {}),
            'bundled': bundled, 'maximum': maximum,
            'current': max(0, min(maximum, current if current is not None else maximum)),
        }
    data['armor'] = armor

    valid_weapon_ids = {
        entry.get('instance_id') for entry in data.get('inventory') or []
        if isinstance(entry, dict) and entry.get('cat') in ('guns', 'melee')
    }
    data['weapon_state'] = {
        key: value for key, value in (old_data.get('weapon_state') or {}).items()
        if key in valid_weapon_ids
    }
    _LATE['ensure_progression'](data)
    ensure_character_visibility(data)
    return data


# Server-owned runtime/audit containers are never portable between deployments.
# A JSON import carries the Dossier (identity, stats, skills, loadout, resources)
# but resets transient runtime state to fresh defaults.
IMPORT_STRIP_KEYS = (
    'cyberware_state', 'therapy_state', 'armor_tech_state', 'armor_repair_state',
    'tech_maker_state', 'modification_state', 'weapon_state', 'program_state',
    'net_entities', 'vehicle_state', 'downtime_state',
    'portrait_media_id', 'archived', 'archive_reason', 'public',
)


def canonical_import_character(raw):
    """Validate a portable Dossier export without creation-budget rules."""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ApiError(400, 'Некорректный JSON импорта')
    if not isinstance(raw, dict):
        raise ApiError(400, 'Импорт должен быть JSON-объектом')
    # Accept the plain data object or common envelopes (full char_payload, sheet).
    for key in ('data', 'character', 'sheet'):
        if isinstance(raw.get(key), dict):
            raw = raw[key]
            break
    base = clean_character(raw)
    for key in IMPORT_STRIP_KEYS:
        base.pop(key, None)
    # Unknown non-custom items are rejected instead of passed through silently.
    for bucket in ('inventory', 'cyberware'):
        for entry in base.get(bucket) or []:
            if not isinstance(entry, dict):
                raise ApiError(400, 'Inventory должен содержать объекты')
            if not _LATE['catalog_item_id_for_entry'](entry) and not entry.get('is_custom'):
                raise ApiError(400, 'Неизвестный предмет в импорте')
    data = clean_character_trust_update(base, base)
    data['public'] = False
    data.pop('portrait_media_id', None)
    _LATE['ensure_character_item_instances'](data, regenerate=True)
    if len(data.get('inventory') or []) + len(data.get('cyberware') or []) > 500:
        raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
    # Re-default runtime containers against the regenerated instance ids so no
    # stale per-instance state from the source sheet survives the import.
    for key in ('weapon_state', 'program_state', 'net_entities'):
        data.pop(key, None)
    _LATE['ensure_progression'](data)
    ensure_character_visibility(data)
    return data


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


def armor_shield_hp(item):
    catalog_item = item_by_id(_LATE['catalog_item_id_for_entry'](item)) or item or {}
    text = ' '.join([str(catalog_item.get('desc') or ''),
                     *[str(value) for value in (catalog_item.get('fields') or {}).values()]])
    match = re.search(r'(\d+)\s*HP', text, re.I)
    return int(match.group(1)) if match else 0


def effective_armor_hosts(data):
    """Project concrete Armor/Shield instances and permanent Tech upgrades."""
    inventory = [item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('cat') == 'armor' and
                 item.get('instance_id')]
    equipped = data.get('armor') if isinstance(data.get('armor'), dict) else {}
    tech_states = data.get('armor_tech_state') \
        if isinstance(data.get('armor_tech_state'), dict) else {}
    repair_states = data.get('armor_repair_state') \
        if isinstance(data.get('armor_repair_state'), dict) else {}
    hosts = []
    for item in inventory:
        catalog_item = item_by_id(_LATE['catalog_item_id_for_entry'](item)) or item
        locations = list(catalog_item.get('armor_locations') or item.get('armor_locations') or [])
        shield = 'shield' in locations
        base_sp = _num(catalog_item.get('sp') if not shield else None)
        base_sdp = armor_shield_hp(item) if shield else None
        state = tech_states.get(item['instance_id'])
        state = state if isinstance(state, dict) else {}
        upgraded = state.get('active') is True
        mode = state.get('mode')
        effective_sp = (base_sp + 1) if upgraded and mode == 'sp_plus_one' and \
            base_sp is not None else base_sp
        effective_sdp = base_sdp
        tech_maker = None
        for mod in character_tech_maker_modifications(data).values():
            if mod.get('host_instance_id') != item['instance_id']:
                continue
            effect = mod.get('effect')
            if not isinstance(effect, dict):
                continue
            if effect.get('target') == 'armor.sp' and not shield and effective_sp is not None:
                effective_sp += int(effect.get('value') or 0)
                tech_maker = copy.deepcopy(mod)
        if tech_maker:
            tech_maker['effective'] = effective_sp
        equipped_locations = [
            location for location in ('head', 'body', 'shield')
            if isinstance(equipped.get(location), dict) and
            equipped[location].get('instance_id') == item['instance_id']]
        current_by_location = {
            location: _num(equipped[location].get('current'))
            for location in equipped_locations}
        maximum = effective_sdp if shield else effective_sp
        damaged = any(current is not None and maximum is not None and current < maximum
                      for current in current_by_location.values())
        description = str(catalog_item.get('desc') or '')
        unrepairable = _LATE['catalog_item_id_for_entry'](item) == 'armor-26' or \
            'cannot be restored' in description.lower()
        repair_state = repair_states.get(item['instance_id'])
        repair_state = copy.deepcopy(repair_state) if isinstance(repair_state, dict) else None
        hosts.append({
            'instance_id': item['instance_id'],
            'catalog_item_id': _LATE['catalog_item_id_for_entry'](item),
            'name': item.get('custom_name') or item.get('name') or 'Armor',
            'host_kind': 'shield' if shield else 'armor',
            'locations': locations, 'equipped_locations': equipped_locations,
            'state': item.get('state') or 'carried',
            'base_sp': base_sp, 'effective_sp': effective_sp,
            'base_sdp': base_sdp, 'effective_sdp': effective_sdp,
            'current_by_location': current_by_location,
            'bundled': bool(catalog_item.get('armor_bundled')),
            'damaged': damaged, 'repairable': not shield and not unrepairable,
            'unrepairable': unrepairable, 'repair_state': repair_state,
            'self_repair': ('executive_armor_daily' if _LATE['catalog_item_id_for_entry'](item) ==
                            'armor-19' else None),
            'tech_upgrade': copy.deepcopy(state) if upgraded else None,
            'tech_upgrade_available': not upgraded and
                (base_sp is not None or shield),
            'automated_upgrade_available': not upgraded and base_sp is not None and not shield,
            'manual_resolution_required': shield,
            'tech_maker_modification': tech_maker,
        })
    return {'hosts': hosts, 'upgraded_count': sum(bool(item['tech_upgrade']) for item in hosts)}


def validate_armor_tech_references(data):
    states = data.get('armor_tech_state') if isinstance(data.get('armor_tech_state'), dict) else {}
    armor_ids = {item.get('instance_id') for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('cat') == 'armor'}
    if any(instance_id not in armor_ids or not isinstance(state, dict)
           for instance_id, state in states.items()):
        raise ApiError(409, 'Повреждена связь Armor/Shield Tech Upgrade')


def validate_armor_repair_references(data):
    states = data.get('armor_repair_state') if isinstance(data.get('armor_repair_state'), dict) else {}
    armor_ids = {item.get('instance_id') for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('cat') == 'armor'}
    if any(instance_id not in armor_ids or not isinstance(state, dict)
           for instance_id, state in states.items()):
        raise ApiError(409, 'Повреждена связь Armor Repair Workflow')


TECH_MAKER_SPECIALTIES = ('upgrade', 'invention')
TECH_MAKER_FABRICATION_SPECIALTIES = ('fabrication', 'invention')
# Declarative allowlist of what a Tech Maker custom modification may do.
# Values are bounded; no executable data is accepted.
TECH_MAKER_EFFECT_TARGETS = {
    'weapon.attack_check': {
        'host_types': {'weapon'}, 'operations': ('add',),
        'value_kind': 'number', 'value_min': -3, 'value_max': 3,
        'label_en': 'Attack Check', 'label_ru': 'Бросок атаки',
    },
    'weapon.magazine': {
        'host_types': {'weapon'}, 'operations': ('add',),
        'value_kind': 'number', 'value_min': 1, 'value_max': 20,
        'label_en': 'Magazine capacity', 'label_ru': 'Ёмкость магазина',
    },
    'weapon.concealable': {
        'host_types': {'weapon'}, 'operations': ('set',),
        'value_kind': 'choice', 'choices': ('YES', 'NO'),
        'label_en': 'Concealability', 'label_ru': 'Скрываемость',
    },
    'armor.sp': {
        'host_types': {'armor'}, 'operations': ('add',),
        'value_kind': 'number', 'value_min': 1, 'value_max': 1,
        'label_en': 'Stopping Power', 'label_ru': 'Stopping Power',
    },
    'vehicle.sdp_max': {
        'host_types': {'vehicle'}, 'operations': ('add',),
        'value_kind': 'number', 'value_min': 1, 'value_max': 50,
        'label_en': 'Maximum SDP', 'label_ru': 'Максимальный SDP',
    },
}
TECH_MAKER_SPECIALTY_LABELS = {
    'upgrade': ('Upgrade Expertise', 'Upgrade Expertise'),
    'invention': ('Invention Expertise', 'Invention Expertise'),
    'fabrication': ('Fabrication Expertise', 'Fabrication Expertise'),
}
# Physical item categories a Tech can reproduce from a blueprint via
# Fabrication Expertise. Cyberware and Services are excluded on purpose:
# Cyberware requires a clinic install, Services are not physical goods.
TECH_MAKER_FABRICABLE_CATS = {
    'guns', 'melee', 'gun_upgrades', 'ammo', 'grenades', 'armor',
    'gear', 'fashion', 'vehicles', 'vehicles_upgrades', 'net_stuff', 'programs',
}


def tech_maker_fabricable_item(item):
    if not isinstance(item, dict):
        return False
    if not item_by_id(item.get('id')):
        return False
    return item.get('cat') in TECH_MAKER_FABRICABLE_CATS


def tech_maker_host_type(entry):
    """Map a concrete owned instance to a Tech Maker host type."""
    if not isinstance(entry, dict):
        return None
    cat = str(entry.get('cat') or '')
    if cat == 'guns':
        return 'weapon'
    if cat == 'armor':
        return 'armor'
    if cat == 'vehicles':
        return 'vehicle'
    if cat == 'cyberware':
        return 'cyberware'
    return None


def character_maker_ranks(data):
    """Return Maker specialty ranks for the character's active Tech Role."""
    roles = data.get('roles') or []
    active_name = str(data.get('active_role') or data.get('role') or '')
    role = next((row for row in roles if isinstance(row, dict) and
                 str(row.get('name') or '') == active_name), None)
    if not role or role.get('name') != 'Tech':
        role = next((row for row in roles if isinstance(row, dict) and
                     row.get('name') == 'Tech'), None)
    if not role:
        return {}
    setup = role.get('setup') if isinstance(role.get('setup'), dict) else {}
    return {key: max(0, _num(setup.get(key)) or 0)
            for key in ('field', 'upgrade', 'fabrication', 'invention')}


def clean_tech_maker_effect(host_type, raw):
    """Validate and normalize a declarative Tech Maker effect payload."""
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ApiError(400, 'Tech Maker effect должен быть объектом')
    if set(raw) - {'target', 'operation', 'value'}:
        raise ApiError(400, 'Tech Maker effect содержит неподдерживаемые поля')
    target = str(raw.get('target') or '')
    definition = TECH_MAKER_EFFECT_TARGETS.get(target)
    if not definition:
        raise ApiError(400, 'Недопустимый Tech Maker effect target')
    if host_type not in definition['host_types']:
        raise ApiError(400, f'Effect target {target} недопустим для host {host_type}')
    operation = str(raw.get('operation') or '')
    if operation not in definition['operations']:
        raise ApiError(400, f'Недопустимая операция {operation} для {target}')
    value = raw.get('value')
    if definition['value_kind'] == 'number':
        if not isinstance(value, int) or isinstance(value, bool):
            raise ApiError(400, 'Tech Maker effect value должен быть целым числом')
        if not definition['value_min'] <= value <= definition['value_max']:
            raise ApiError(400, f'Tech Maker effect value вне диапазона '
                                f'{definition["value_min"]}–{definition["value_max"]}')
    else:
        if value not in definition['choices']:
            raise ApiError(400, f'Недопустимое значение {value} для {target}')
    return {'target': target, 'operation': operation, 'value': value}


def character_tech_maker_modifications(data):
    """Return active Tech Maker custom modifications keyed by modification_id."""
    state = data.get('tech_maker_state')
    if not isinstance(state, dict):
        return {}
    mods = state.get('modifications')
    if not isinstance(mods, dict):
        return {}
    return {key: value for key, value in mods.items()
            if isinstance(value, dict) and value.get('active')}


def validate_tech_maker_references(data):
    state = data.get('tech_maker_state')
    if not isinstance(state, dict):
        return
    mods = state.get('modifications')
    if not isinstance(mods, dict):
        return
    owned_ids = {item.get('instance_id') for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
    owned_ids |= {item.get('instance_id') for item in data.get('cyberware') or []
                  if isinstance(item, dict) and item.get('instance_id')}
    for mod_id, mod in mods.items():
        if not isinstance(mod, dict):
            raise ApiError(409, 'Повреждена запись Tech Maker modification')
        if mod.get('active') and mod.get('host_instance_id') not in owned_ids:
            raise ApiError(409, 'Повреждена связь Tech Maker modification')
    history = state.get('history')
    if history is not None and not isinstance(history, list):
        raise ApiError(409, 'Повреждена история Tech Maker modifications')


def tech_maker_payload(data):
    state = data.get('tech_maker_state')
    state = state if isinstance(state, dict) else {}
    mods = state.get('modifications')
    mods = mods if isinstance(mods, dict) else {}
    owned = {item.get('instance_id'): item for item in data.get('inventory') or []
             if isinstance(item, dict) and item.get('instance_id')}
    owned.update({item.get('instance_id'): item for item in data.get('cyberware') or []
                  if isinstance(item, dict) and item.get('instance_id')})
    out = []
    for mod_id, mod in sorted(mods.items()):
        if not isinstance(mod, dict):
            continue
        host = owned.get(mod.get('host_instance_id')) or {}
        out.append({
            'modification_id': mod_id,
            'name': mod.get('name') or 'Tech Maker Modification',
            'description': mod.get('description') or '',
            'host_instance_id': mod.get('host_instance_id'),
            'host_name': host.get('custom_name') or host.get('name'),
            'host_type': mod.get('host_type'),
            'maker_specialty': mod.get('maker_specialty'),
            'maker_rank': mod.get('maker_rank'),
            'tech_name': mod.get('tech_name'),
            'effect': copy.deepcopy(mod.get('effect')) if isinstance(mod.get('effect'), dict) else None,
            'manual_rule': mod.get('manual_rule') or '',
            'manual_resolution_required': bool(mod.get('manual_resolution_required')),
            'source': mod.get('source'),
            'active': bool(mod.get('active')),
            'permanent': bool(mod.get('permanent')),
            'installed_at': mod.get('installed_at'),
            'reason': mod.get('reason') or '',
            'notes': mod.get('notes') or '',
        })
    fabrications = [
        copy.deepcopy(item) for item in state.get('fabrications') or []
        if isinstance(item, dict)
    ][-50:][::-1]
    return {'modifications': out, 'fabrications': fabrications,
            'history': [copy.deepcopy(item) for item in state.get('history') or []
                        if isinstance(item, dict)][-50:][::-1]}


CYBERWARE_HOST_ACCEPTED_NAMES = {
    'Cyberarm': {'cyberarm', 'neo-soviet cyberarm'},
    'Cyberleg': {'cyberleg', 'romanova cyberlegs'},
    'Cybereye': {'cybereye', 'sponsored cybereye'},
    'Cyberaudio Suite': {'cyberaudio suite', 'discount cyberaudio suite'},
    'Neural Link or Neuroport': {'neural link', 'neuroport'},
}
CYBERWARE_SIDED_HOST_KINDS = {'Cyberarm', 'Cyberleg', 'Cybereye'}
CYBERWARE_INSTALLATION_SITES = {'Mall', 'Clinic', 'Hospital', 'Zoo', 'Tech', 'Manual'}
THERAPY_PROFILES = {
    'standard_hl': {
        'label': 'Therapy (Standard HL)', 'catalog_id': 'services-31',
        'cost': 500, 'duration_days': 7, 'humanity_dice': 2,
        'source': 'CP:R 230',
    },
    'extreme_hl': {
        'label': 'Therapy (Extreme HL)', 'catalog_id': 'services-32',
        'cost': 1000, 'duration_days': 7, 'humanity_dice': 4,
        'source': 'CP:R 230',
    },
    'addiction': {
        'label': 'Therapy (Addiction)', 'catalog_id': 'services-30',
        'cost': 1000, 'duration_days': 7, 'humanity_dice': 0,
        'source': 'CP:R 230', 'manual_effect': True,
    },
}
CYBERWARE_CURATED_PAYLOADS = {
    'cyberware-16': {
        'id': 'reflex-co-processor-dodge', 'kind': 'capability',
        'capability': 'dodge_ranged_attacks_below_ref_8',
        'label': 'Dodge ranged attacks regardless of REF', 'source': 'BC 21',
    },
    'cyberware-62': {
        'id': 'kerenzikov-initiative', 'kind': 'numeric_modifier',
        'target': 'initiative.check', 'operation': 'add', 'value': 2,
        'conflict_group': 'speedware', 'label': 'Initiative +2', 'source': 'CP:R 359',
    },
    'cyberware-63': {
        'id': 'sandevistan-activation', 'kind': 'activation',
        'target': 'initiative.check', 'operation': 'add', 'value': 3,
        'duration_seconds': 60, 'cooldown_seconds': 3600,
        'action_required': True, 'conflict_group': 'speedware',
        'label': 'Activate: Initiative +3 for 1 minute', 'source': 'CP:R 359',
    },
    'cyberware-71': {
        'id': 'image-enhance-sight', 'kind': 'contextual_skill_modifier',
        'skills': ['Perception', 'Lip Reading', 'Conceal/Reveal Object'],
        'operation': 'add', 'value': 2, 'condition': 'sight-based Check',
        'label': 'Sight-based Checks +2', 'source': 'CP:R 360',
    },
    'cyberware-75': {
        'id': 'amplified-hearing', 'kind': 'contextual_skill_modifier',
        'skills': ['Perception'], 'operation': 'add', 'value': 2,
        'condition': 'hearing-based Check', 'label': 'Hearing-based Perception +2',
        'source': 'CP:R 361',
    },
    'cyberware-83': {
        'id': 'targeting-scope-aimed-shot', 'kind': 'contextual_modifier',
        'target': 'aimed_shot.check', 'operation': 'add', 'value': 1,
        'condition': 'Aimed Shot', 'label': 'Aimed Shot Check +1', 'source': 'CP:R 361',
    },
    'cyberware-141': {
        'id': 'sensor-array-slots', 'kind': 'host_slot_grant',
        'target': 'Cyberaudio Suite', 'slots_granted': 5, 'slots_used_override': 0,
        'label': 'Cyberaudio Option Slots +5', 'source': 'CP:R 367',
    },
    'cyberware-156': {
        'id': 'micro-waldo-surgery', 'kind': 'contextual_skill_modifier',
        'skills': ['Surgery'], 'operation': 'add', 'value': 1,
        'condition': 'Medtech using MicroWaldo', 'label': 'Surgery +1',
        'source': 'DL:12Cy 5 / DGD 146 / IR3 87',
    },
}
CYBERWARE_WEAPON_PROFILES = {
    'cyberware-13': {'id': 'popup-net-launcher', 'kind': 'ranged', 'weapon_type': 'Exotic Weapon', 'skill': 'Shoulder Arms', 'damage': '—', 'rof': 1, 'magazine': 1, 'ammo_kind': 'net', 'range_table': 'Shotgun', 'deployable': True, 'concealable': True, 'manual_effect': 'On hit the target is grappled: cannot use Move Action, cannot use two-handed weapons, -2 to physical Actions. Net HP 15, destroyed beyond repair at 0 HP. Escape DV13 Contortionist (target inside only) or DV13 Brawling (anyone); success destroys net. Firing into net damages both net and target equally. Range max 25m. Replacement net 50eb.', 'source': 'BC 20', 'special_ammo': True},
    'cyberware-15': {'id': 'popup-shotgun', 'kind': 'ranged', 'weapon_type': 'Shotgun', 'skill': 'Shoulder Arms', 'damage': '5d6', 'rof': 1, 'magazine': 2, 'ammo_kind': 'shotgun', 'range_table': 'Shotgun', 'deployable': True, 'concealable': True, 'source': 'BC 21'},
    'cyberware-25': {'id': 'dartgun-cyberfinger', 'kind': 'ranged', 'weapon_type': 'Exotic Weapon', 'skill': 'Handgun', 'damage': '—', 'rof': 1, 'magazine': 1, 'deployable': False, 'concealable': True, 'manual_effect': 'Single concealed dart; toxin/drug payload is manual. No conceal check if glove worn. Requires Modular Finger Cyberhand. Single shot clip.', 'source': 'BC 24', 'special_ammo': True},
    'cyberware-42': {'id': 'mantis-blade', 'kind': 'melee', 'weapon_type': 'Heavy Melee Weapon', 'skill': 'Melee Weapon', 'damage': '3d6', 'rof': 2, 'quality': 'Excellent', 'hands_required': 1, 'deployable': True, 'concealable': True, 'source': 'CEMK 35'},
    'cyberware-43': {'id': 'gorilla-arm', 'kind': 'melee', 'weapon_type': 'Heavy Melee Weapon', 'skill': 'Melee Weapon', 'damage': '3d6', 'rof': 2, 'quality': 'Excellent', 'hands_required': 1, 'deployable': False, 'concealable': True, 'manual_effect': 'BODY 11 weapon handling; paired BODY 11 feats are contextual.', 'source': 'CEMK 35'},
    'cyberware-44': {'id': 'monowire', 'kind': 'melee', 'weapon_type': 'Exotic Heavy Melee Weapon', 'skill': 'Melee Weapon', 'damage': '3d6', 'rof': 2, 'hands_required': 1, 'deployable': True, 'concealable': True, 'reach_m': 6, 'manual_effect': 'On Critical Injury roll twice and choose one result.', 'source': 'CEMK 35'},
    'cyberware-48': {'id': 'projectile-launch-system', 'kind': 'ranged_dual', 'weapon_type': 'Rocket/Grenade Launcher', 'skill': 'Heavy Weapons', 'damage': '6d6 / 8d6', 'damage_by_ammo': {'grenade': '6d6', 'rocket': '8d6'}, 'rof': 1, 'magazine': 1, 'ammo_kinds': ['grenade', 'rocket'], 'deployable': True, 'concealable': True, 'source': 'CEMK 36'},
    'cyberware-107': {'id': 'big-knucks', 'kind': 'melee', 'weapon_type': 'Medium Melee Weapon', 'skill': 'Melee Weapon', 'damage': '2d6', 'rof': 2, 'hands_required': 1, 'deployable': False, 'concealable': True, 'source': 'CP:R 364'},
    'cyberware-117': {'id': 'popup-grenade-launcher', 'kind': 'ranged', 'weapon_type': 'Grenade Launcher', 'skill': 'Heavy Weapons', 'damage': '6d6', 'rof': 1, 'magazine': 1, 'ammo_kind': 'grenade', 'range_table': 'Grenade Launcher', 'deployable': True, 'concealable': True, 'source': 'CP:R 365'},
    'cyberware-121': {'id': 'rippers', 'kind': 'melee', 'weapon_type': 'Medium Melee Weapon', 'skill': 'Melee Weapon', 'damage': '2d6', 'rof': 2, 'hands_required': 1, 'deployable': True, 'concealable': True, 'source': 'CP:R 365'},
    'cyberware-124': {'id': 'scratchers', 'kind': 'melee', 'weapon_type': 'Light Melee Weapon', 'skill': 'Melee Weapon', 'damage': '1d6', 'rof': 2, 'hands_required': 1, 'deployable': False, 'concealable': True, 'source': 'CP:R 366'},
    'cyberware-131': {'id': 'slice-n-dice', 'kind': 'melee', 'weapon_type': 'Medium Melee Weapon', 'skill': 'Melee Weapon', 'damage': '2d6', 'rof': 2, 'hands_required': 1, 'deployable': True, 'concealable': True, 'source': 'CP:R 366'},
    'cyberware-133': {'id': 'wolvers', 'kind': 'melee', 'weapon_type': 'Heavy Melee Weapon', 'skill': 'Melee Weapon', 'damage': '3d6', 'rof': 2, 'hands_required': 1, 'deployable': True, 'concealable': True, 'source': 'CP:R 366'},
    'cyberware-70': {'id': 'dartgun', 'kind': 'ranged', 'weapon_type': 'Exotic Weapon', 'skill': 'Handgun', 'damage': '—', 'rof': 1, 'magazine': 1, 'deployable': False, 'concealable': True, 'manual_effect': 'Cybereye Dartgun Exotic Weapon, single shot clip concealed in Cybereye. Payload effects manual (toxin/drug).', 'source': 'CP:R 360', 'special_ammo': True},
    'cyberware-146': {'id': 'mono-paw', 'kind': 'melee', 'weapon_type': 'Medium Melee Weapon', 'skill': 'Melee Weapon', 'damage': '1d6', 'rof': 2, 'quality': 'Excellent', 'hands_required': 1, 'deployable': True, 'concealable': True, 'manual_effect': 'Ignores armor below SP11; higher SP applies normally.', 'source': 'DL:12Cute 6'},
    'cyberware-148': {'id': 'chainripp', 'kind': 'melee', 'weapon_type': 'Very Heavy Melee Weapon', 'skill': 'Melee Weapon', 'damage': '4d6', 'rof': 1, 'hands_required': 1, 'deployable': True, 'rev_action': True, 'concealable': False, 'manual_effect': 'Excellent Exotic quality only while revved.', 'source': 'DL:12Cy 3 / IR3 85'},
    'cyberware-171': {'id': 'gas-jet', 'kind': 'ranged', 'weapon_type': 'Exotic Weapon', 'skill': 'Shoulder Arms', 'damage': '—', 'rof': 1, 'magazine': 1, 'ammo_kinds': ['street_drug', 'poison', 'biotoxin'], 'range_table': 'Shotgun', 'deployable': False, 'concealable': True, 'manual_effect': 'Acts as One-Handed Exotic Shotgun in Shotgun Shell mode only; instead of damage applies loaded Street Drug / Poison / Biotoxin to all vulnerable targets in spread. Nasal Filters negate. Requires fully loaded (3 doses) and drains entirely each shot.', 'source': 'DL:HP 5 / IR4 7', 'special_ammo': True, 'payload_options': ['street_drug', 'poison', 'biotoxin']},
}


def cyberware_weapon_profile(entry):
    return copy.deepcopy(CYBERWARE_WEAPON_PROFILES.get(_LATE['catalog_item_id_for_entry'](entry)))


def popup_weapon_binding_kind(entry):
    catalog_id = _LATE['catalog_item_id_for_entry'](entry)
    if catalog_id == 'cyberware-118':
        return 'melee'
    if catalog_id == 'cyberware-119':
        return 'ranged'
    return None


def popup_shield_profile(data, option):
    if _LATE['catalog_item_id_for_entry'](option) != 'cyberware-120':
        return None
    state = (data.get('cyberware_state') or {}).get(option.get('instance_id')) or {}
    popup = state.get('popup_shield') if isinstance(state.get('popup_shield'), dict) else {}
    shield_id = str(popup.get('shield_instance_id') or '')
    shield = next((item for item in data.get('inventory') or []
                   if isinstance(item, dict) and item.get('instance_id') == shield_id), None)
    if not shield:
        return {'option_instance_id': option.get('instance_id'), 'installed': False}
    maximum = armor_shield_hp(shield)
    current = max(0, min(maximum, int(_num(popup.get('hp_current'))
                                      if _num(popup.get('hp_current')) is not None else maximum)))
    return {
        'option_instance_id': option.get('instance_id'), 'installed': True,
        'shield_instance_id': shield_id,
        'shield_name': shield.get('custom_name') or shield.get('name'),
        'hp_current': current, 'hp_max': maximum,
        'deployed': popup.get('deployed') is True and current > 0,
        'destroyed': current <= 0, 'source': 'CP:R 365',
        'manual_resolution_required': False,
    }


def validate_popup_shield_references(data):
    chrome = {item.get('instance_id'): item for item in data.get('cyberware') or []
              if isinstance(item, dict) and item.get('instance_id')}
    inventory = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
    states = data.get('cyberware_state') if isinstance(data.get('cyberware_state'), dict) else {}
    claimed = set()
    for option_id, runtime in states.items():
        popup = runtime.get('popup_shield') if isinstance(runtime, dict) else None
        if not isinstance(popup, dict) or not popup.get('shield_instance_id'):
            continue
        option = chrome.get(option_id)
        shield_id = str(popup['shield_instance_id'])
        shield = inventory.get(shield_id)
        if (not option or _LATE['catalog_item_id_for_entry'](option) != 'cyberware-120' or
                not shield or shield_id in claimed or
                shield.get('installed_popup_shield_instance_id') != option_id):
            raise ApiError(409, 'Повреждена связь Popup Shield')
        claimed.add(shield_id)


def popup_weapon_binding_compatibility(option, weapon):
    kind = popup_weapon_binding_kind(option)
    reasons = []
    catalog_weapon = item_by_id(_LATE['catalog_item_id_for_entry'](weapon)) or {}
    mechanics = (weapon or {}).get('mechanics') or catalog_weapon.get('mechanics') or {}
    weapon_type = str(mechanics.get('type') or '')
    if not kind:
        reasons.append('Cyberware is not a generic Popup Weapon option')
    if not weapon or weapon.get('state') != 'carried':
        reasons.append('Weapon must be a free carried instance')
    if (weapon or {}).get('mounted_modification_id') or \
            (weapon or {}).get('installed_cyberware_instance_id'):
        reasons.append('Weapon is already bound to another host')
    if kind == 'ranged' and _num(mechanics.get('hands')) != 1:
        reasons.append('Popup Ranged Weapon requires a one-handed weapon')
    if kind == 'ranged' and (weapon or {}).get('cat') != 'guns':
        reasons.append('Popup Ranged Weapon requires a ranged weapon')
    if kind == 'melee':
        if (weapon or {}).get('cat') != 'melee':
            reasons.append('Popup Melee Weapon requires a melee weapon')
        if not any(label in weapon_type for label in
                   ('Light Melee Weapon', 'Medium Melee Weapon', 'Heavy Melee Weapon')) or \
                'Very Heavy' in weapon_type:
            reasons.append('Popup Melee Weapon accepts Light, Medium, or Heavy Melee Weapon')
    return {'allowed': not reasons, 'reasons': reasons, 'kind': kind}


def bound_popup_weapon_profile(data, option):
    kind = popup_weapon_binding_kind(option)
    if not kind:
        return None
    state = (data.get('cyberware_state') or {}).get(option.get('instance_id')) or {}
    weapon_id = str(state.get('bound_weapon_instance_id') or '')
    weapon = next((item for item in data.get('inventory') or []
                   if isinstance(item, dict) and item.get('instance_id') == weapon_id), None)
    if not weapon:
        return None
    catalog_weapon = item_by_id(_LATE['catalog_item_id_for_entry'](weapon)) or {}
    mechanics = weapon.get('mechanics') or catalog_weapon.get('mechanics') or {}
    damage = mechanics.get('damage')
    if isinstance(damage, dict):
        damage = damage.get('notation')
    profile = {
        'id': f'bound-popup-{kind}:{weapon_id}',
        'kind': kind, 'weapon_type': mechanics.get('type'),
        'skill': mechanics.get('skill') or ('Melee Weapon' if kind == 'melee' else None),
        'damage': damage, 'rof': mechanics.get('rof'),
        'quality': mechanics.get('quality'),
        'hands_required': 1, 'deployable': True, 'concealable': True,
        'bound_weapon_instance_id': weapon_id,
        'bound_weapon_name': weapon.get('custom_name') or weapon.get('name'),
        'attachments_preserved': True,
        'source': (item_by_id(_LATE['catalog_item_id_for_entry'](option)) or option).get('source'),
        'manual_effect': 'Bound weapon attachments remain installed; contextual attachment effects use the weapon Dossier.',
    }
    if kind == 'ranged':
        profile.update({
            'magazine': int(_num(mechanics.get('magazine')) or 0),
            'range_table': weapon_range_table_info(weapon).get('base'),
        })
    return profile


def cyberware_curated_payload(entry):
    return copy.deepcopy(CYBERWARE_CURATED_PAYLOADS.get(
        _LATE['catalog_item_id_for_entry'](entry)))


def cyberware_is_installed(entry):
    return str((entry or {}).get('state') or 'installed') == 'installed'


def cyberware_is_paired_leg_foundation(entry):
    catalog_item = item_by_id(_LATE['catalog_item_id_for_entry'](entry)) or entry or {}
    return 'paired cyberlegs' in str(catalog_item.get('desc') or '').lower()


def cyberware_secondary_host_id(instance_id):
    """Derive a stable second physical host ID for one paired foundation item."""
    value = str(instance_id or '').lower()
    if INSTANCE_ID_RE.fullmatch(value):
        return value[:-1] + format((int(value[-1], 16) + 1) % 16, 'x')
    return f'{value}:paired-2'


def cyberware_capacity(entry):
    catalog_item = item_by_id(_LATE['catalog_item_id_for_entry'](entry)) or {}
    capacity = copy.deepcopy(
        catalog_item.get('capacity') or (entry or {}).get('capacity') or {})
    description = str(catalog_item.get('desc') or (entry or {}).get('desc') or '')
    if capacity.get('host'):
        slot_match = re.search(
            r'(?:takes?|uses?|requires?)\s+(?:up\s+)?(\d+)\s+(?:(?:cyberware|cyberarm|cybereye|cyberleg|cyberaudio)\s+)?option slots?',
            description, re.I)
        if slot_match:
            capacity['slots_used'] = int(slot_match.group(1))
    if cyberware_is_paired_leg_foundation(entry):
        match = re.search(r'each cyberleg has\s+(\d+)\s+option slots?',
                          description, re.I)
        capacity.update({
            'host': None, 'hosts_required': 0, 'slots_used': 0,
            'slots_total': int(match.group(1)) if match else
                max(1, int(_num(capacity.get('slots_total')) or 1)),
        })
    return capacity


def cyberware_host_assignments(entry):
    raw = entry.get('host_instances') if isinstance(entry, dict) else None
    if not isinstance(raw, list) or not raw:
        raw = [entry.get('host_instance')] if isinstance(entry, dict) and entry.get(
            'host_instance') else []
    result = []
    for value in raw:
        value = str(value or '')
        if value and value not in result:
            result.append(value)
    return result


def cyberware_host_kind(entry):
    if cyberware_is_paired_leg_foundation(entry):
        return 'Cyberleg'
    name = str((entry or {}).get('name') or '').lower()
    for kind, accepted in CYBERWARE_HOST_ACCEPTED_NAMES.items():
        if name in accepted:
            return kind
    return None


def cyberware_installation_profile(entry):
    catalog_item = item_by_id(_LATE['catalog_item_id_for_entry'](entry)) or entry or {}
    raw = str((catalog_item.get('mechanics') or {}).get('installation') or
              ((catalog_item.get('fields') or {}).get('Install')) or '').strip()
    biosystem_required = 'requires biosystem' in raw.lower()
    site = raw.split('(', 1)[0].strip().title() if raw else 'Manual'
    if site not in CYBERWARE_INSTALLATION_SITES:
        site = 'Manual'
    return {
        'required_site': site, 'source_installation': raw or 'Manual',
        'biosystem_required': biosystem_required,
        'manual_resolution_required': True,
        'source': catalog_item.get('source'),
    }


def cyberware_side_required(entry):
    return bool(cyberware_host_kind(entry) in CYBERWARE_SIDED_HOST_KINDS and
                not cyberware_is_paired_leg_foundation(entry))


def validate_cyberware_sides(data, allow_unassigned=False):
    occupied = set()
    for entry in data.get('cyberware') or []:
        if not isinstance(entry, dict) or not cyberware_is_installed(entry) or \
                not cyberware_side_required(entry):
            continue
        side = str(entry.get('installation_side') or '').lower()
        if side not in ('left', 'right'):
            if allow_unassigned:
                continue
            raise ApiError(400, f'{entry.get("name") or "Cyberware"}: выберите left/right side')
        key = (cyberware_host_kind(entry), side)
        if key in occupied:
            raise ApiError(409, f'{cyberware_host_kind(entry)}: сторона {side} уже занята')
        occupied.add(key)
    # A paired Cyberleg foundation occupies both physical leg sides.
    paired_count = sum(
        1 for entry in data.get('cyberware') or []
        if isinstance(entry, dict) and cyberware_is_installed(entry) and
        cyberware_is_paired_leg_foundation(entry))
    regular_legs = sum(
        1 for kind, _side in occupied if kind == 'Cyberleg')
    if paired_count > 1 or (paired_count and regular_legs):
        raise ApiError(409, 'Paired Cyberlegs требуют обе свободные стороны')


def validate_cyberware_payload_conflicts(data):
    groups = {}
    for entry in data.get('cyberware') or []:
        if not isinstance(entry, dict) or not cyberware_is_installed(entry):
            continue
        payload = cyberware_curated_payload(entry) or {}
        group = payload.get('conflict_group')
        if not group:
            continue
        groups.setdefault(group, []).append(entry.get('name') or 'Cyberware')
    for group, names in groups.items():
        if len(names) > 1:
            raise ApiError(
                409, f'Cyberware conflict {group}: {", ".join(names[:5])}')


def effective_cyberware_loadout(data):
    """Return concrete Cyberware foundations, options, slots, and staged items."""
    chrome = [item for item in data.get('cyberware') or []
              if isinstance(item, dict) and item.get('instance_id')]
    raw_runtime_states = data.get('cyberware_state') \
        if isinstance(data.get('cyberware_state'), dict) else {}
    runtime_states = {key: value for key, value in raw_runtime_states.items()
                      if isinstance(value, dict)}
    hosts = {}
    for entry in chrome:
        capacity = cyberware_capacity(entry)
        kind = cyberware_host_kind(entry)
        total = max(0, int(_num(capacity.get('slots_total')) or 0))
        if kind and total and cyberware_is_installed(entry):
            parent_id = entry['instance_id']
            physical_ids = [parent_id]
            if cyberware_is_paired_leg_foundation(entry):
                physical_ids.append(cyberware_secondary_host_id(parent_id))
            base_name = entry.get('custom_name') or entry.get('name') or kind
            for side_index, physical_id in enumerate(physical_ids):
                side = ('left' if side_index == 0 else 'right') \
                    if len(physical_ids) > 1 else None
                installation_side = side or str(entry.get('installation_side') or '').lower() or None
                hosts[physical_id] = {
                    'instance_id': physical_id,
                    'foundation_instance_id': parent_id,
                    'catalog_item_id': _LATE['catalog_item_id_for_entry'](entry),
                    'name': f'{base_name} · {side.title()}' if side else base_name,
                    'foundation_name': base_name,
                    'host_kind': kind, 'physical_side': installation_side,
                    'side_required': cyberware_side_required(entry),
                    'side_status': 'assigned' if installation_side else
                        ('required' if cyberware_side_required(entry) else 'not_applicable'),
                    'paired_foundation': len(physical_ids) > 1,
                    'installation_profile': cyberware_installation_profile(entry),
                    'state': 'installed', 'slots_total': total,
                    'slots_used': 0, 'slots_free': total,
                    'overloaded': False, 'quick_change_mount': False,
                    'options': [],
                }

    side_counts = {}
    for host in hosts.values():
        if host['side_required'] and host.get('physical_side'):
            key = (host['host_kind'], host['physical_side'])
            side_counts[key] = side_counts.get(key, 0) + 1
    paired_legs = {host['foundation_instance_id'] for host in hosts.values()
                   if host['host_kind'] == 'Cyberleg' and host['paired_foundation']}
    regular_leg_hosts = [host for host in hosts.values()
                         if host['host_kind'] == 'Cyberleg' and
                         not host['paired_foundation']]
    for host in hosts.values():
        key = (host['host_kind'], host.get('physical_side'))
        conflict = bool(
            (host['side_required'] and host.get('physical_side') and
             side_counts.get(key, 0) > 1) or
            (host['host_kind'] == 'Cyberleg' and
             ((len(paired_legs) > 1) or (paired_legs and regular_leg_hosts))))
        if conflict:
            host['side_status'] = 'conflict'
    used = {host_id: 0 for host_id in hosts}
    option_rows = []
    unique_counts = {}
    for entry in chrome:
        capacity = cyberware_capacity(entry)
        expected = capacity.get('host')
        if not expected:
            continue
        installed = cyberware_is_installed(entry)
        host_ids = cyberware_host_assignments(entry)
        required = max(1, int(_num(capacity.get('hosts_required')) or 1))
        payload = cyberware_curated_payload(entry)
        slots_override = _num((payload or {}).get('slots_used_override'))
        slots = max(0, int(slots_override if slots_override is not None else
                           (_num(capacity.get('slots_used')) or 1)))
        reasons = []
        if installed:
            unique_counts[_LATE['catalog_item_id_for_entry'](entry)] = \
                unique_counts.get(_LATE['catalog_item_id_for_entry'](entry), 0) + 1
            if len(host_ids) != required:
                reasons.append(f'Requires {required} concrete hosts')
            for host_id in host_ids:
                host = hosts.get(host_id)
                if not host:
                    reasons.append('Assigned host is missing or not installed')
                elif host['host_kind'] != expected:
                    reasons.append(f'Host must be {expected}')
                else:
                    used[host_id] += slots
        option_rows.append({
            'instance_id': entry['instance_id'],
            'catalog_item_id': _LATE['catalog_item_id_for_entry'](entry),
            'name': entry.get('custom_name') or entry.get('name') or 'Cyberware Option',
            'state': str(entry.get('state') or 'installed'),
            'expected_host': expected, 'hosts_required': required,
            'slots_used_per_host': slots, 'host_instance_ids': host_ids,
            'compatible_host_ids': [],
            'installation_profile': cyberware_installation_profile(entry),
            'curated_payload': payload,
            'weapon_profile': cyberware_weapon_profile(entry) or
                bound_popup_weapon_profile(data, entry),
            'popup_binding_kind': popup_weapon_binding_kind(entry),
            'bound_weapon_instance_id': str(
                ((data.get('cyberware_state') or {}).get(entry['instance_id']) or {}).get(
                    'bound_weapon_instance_id') or '') or None,
            'status': 'staged' if not installed else ('installed' if not reasons else 'unbound'),
            'reasons': reasons,
            'unique': bool(capacity.get('unique')),
        })

    for option in option_rows:
        payload = option.get('curated_payload') or {}
        if (option['state'] == 'installed' and not option['reasons'] and
                payload.get('kind') == 'host_slot_grant'):
            for host_id in option['host_instance_ids']:
                host = hosts.get(host_id)
                if host and host['host_kind'] == payload.get('target'):
                    granted = max(0, int(_num(payload.get('slots_granted')) or 0))
                    host['slots_base'] = host.get('slots_base', host['slots_total'])
                    host['slots_granted'] = host.get('slots_granted', 0) + granted
                    host['slots_total'] += granted
    option_by_id = {item['instance_id']: item for item in option_rows}
    for host_id, amount in used.items():
        host = hosts[host_id]
        host.setdefault('slots_base', host['slots_total'])
        host.setdefault('slots_granted', 0)
        host['slots_used'] = amount
        host['slots_free'] = max(0, host['slots_total'] - amount)
        host['overloaded'] = amount > host['slots_total']
    for option in option_rows:
        option['compatible_host_ids'] = [
            host_id for host_id, host in hosts.items()
            if host['host_kind'] == option['expected_host'] and
            host['slots_used'] - (
                option['slots_used_per_host']
                if host_id in option['host_instance_ids'] and
                option['state'] == 'installed' else 0) +
            option['slots_used_per_host'] <= host['slots_total']]
        if option['state'] != 'installed':
            continue
        for host_id in option['host_instance_ids']:
            host = hosts.get(host_id)
            if not host or host['host_kind'] != option['expected_host']:
                continue
            host['options'].append({
                'instance_id': option['instance_id'], 'name': option['name'],
                'slots_used': option['slots_used_per_host'],
                'paired': option['hosts_required'] > 1,
                'curated_payload': copy.deepcopy(option.get('curated_payload')),
                'weapon_profile': copy.deepcopy(option.get('weapon_profile')),
                'popup_binding_kind': option.get('popup_binding_kind'),
                'bound_weapon_instance_id': option.get('bound_weapon_instance_id'),
            })
            if option['name'] == 'Quick Change Mount':
                host['quick_change_mount'] = True
            if host['overloaded']:
                option['status'] = 'invalid'
                if 'Host Option Slots exceeded' not in option['reasons']:
                    option['reasons'].append('Host Option Slots exceeded')
    for catalog_id, count in unique_counts.items():
        if not catalog_id or count <= 1:
            continue
        for option in option_rows:
            if option['catalog_item_id'] == catalog_id and option['unique']:
                option['status'] = 'invalid'
                option['reasons'].append('Only one installed copy is allowed')

    hosted_ids = set(option_by_id)
    host_ids = set(hosts)
    staged = [{
        'instance_id': item['instance_id'],
        'catalog_item_id': _LATE['catalog_item_id_for_entry'](item),
        'name': item.get('custom_name') or item.get('name') or 'Cyberware',
        'state': str(item.get('state') or 'installed'),
        'host_kind': cyberware_host_kind(item),
        'expected_host': cyberware_capacity(item).get('host'),
        'side_required': cyberware_side_required(item),
        'installation_side': item.get('installation_side') or
            (runtime_states.get(item['instance_id']) or {}).get('installation_side'),
        'installation_profile': cyberware_installation_profile(item),
        'quick_change_detached': bool(
            (runtime_states.get(item['instance_id']) or {}).get('quick_change_detached')),
        'hl': _num(item.get('hl')) or 0,
    } for item in chrome if not cyberware_is_installed(item)]
    standalone = [{
        'instance_id': item['instance_id'],
        'catalog_item_id': _LATE['catalog_item_id_for_entry'](item),
        'name': item.get('custom_name') or item.get('name') or 'Cyberware',
        'state': 'installed',
        'installation_profile': cyberware_installation_profile(item),
        'hl': _num(item.get('hl')) or 0,
    } for item in chrome
        if cyberware_is_installed(item) and item['instance_id'] not in hosted_ids and
        item['instance_id'] not in host_ids]
    active_payloads = [
        copy.deepcopy(option['curated_payload']) | {
            'instance_id': option['instance_id'], 'name': option['name']}
        for option in option_rows
        if option['state'] == 'installed' and option['status'] == 'installed' and
        isinstance(option.get('curated_payload'), dict)]
    initiative_modifier = sum(
        int(_num(payload.get('value')) or 0) for payload in active_payloads
        if payload.get('kind') == 'numeric_modifier' and
        payload.get('target') == 'initiative.check')
    weapon_profiles = []
    for option in option_rows:
        profile = copy.deepcopy(option.get('weapon_profile'))
        if option['state'] != 'installed' or option['status'] != 'installed' or not profile:
            continue
        stored = runtime_states.get(option['instance_id']) or {}
        if profile.get('bound_weapon_instance_id'):
            weapon_state = (data.get('weapon_state') or {}).get(
                profile['bound_weapon_instance_id']) or {}
        else:
            weapon_state = stored.get('weapon') if isinstance(stored.get('weapon'), dict) else {}
        maximum = max(0, int(_num(profile.get('magazine')) or 0))
        profile['instance_id'] = option['instance_id']
        profile['name'] = option['name']
        profile['state'] = {
            'deployed': weapon_state.get('deployed') is True or
                not profile.get('deployable'),
            'revved': weapon_state.get('revved') is True,
            'magazine': max(0, min(maximum, int(_num(weapon_state.get('magazine')) or 0))),
            'magazine_max': maximum,
            'loaded_ammo_catalog_id': weapon_state.get('loaded_ammo_catalog_id'),
            'loaded_ammo_name': weapon_state.get('loaded_ammo_name'),
            'loaded_ammo_kind': weapon_state.get('loaded_ammo_kind'),
            'loaded_payload': weapon_state.get('loaded_payload'),
        }
        if profile.get('damage_by_ammo') and profile['state']['loaded_ammo_kind']:
            profile['effective_damage'] = profile['damage_by_ammo'].get(
                profile['state']['loaded_ammo_kind'], profile.get('damage'))
        ammo_kinds = profile.get('ammo_kinds') or ([profile.get('ammo_kind')]
                                                   if profile.get('ammo_kind') else [])
        if profile.get('special_ammo'):
            profile['shared_ammo_available'] = 0
            # Track special payload availability manually
            if profile.get('payload_options'):
                profile['payload_options'] = list(profile['payload_options'])
        elif profile.get('bound_weapon_instance_id'):
            bound_weapon = next((item for item in data.get('inventory') or []
                                 if isinstance(item, dict) and item.get('instance_id') ==
                                 profile['bound_weapon_instance_id']), None)
            profile['shared_ammo_available'] = shared_ammo_available(
                data, weapon=bound_weapon)
        else:
            profile['shared_ammo_available'] = sum(
                shared_ammo_available(data, ammo_kind=kind) for kind in ammo_kinds
                if kind not in ('net', 'street_drug', 'poison', 'biotoxin'))
        weapon_profiles.append(profile)
    # Standalone cyberweapons (e.g. Dartgun Cyberfinger) also produce tracked profiles
    for entry in chrome:
        if entry.get('instance_id') in {opt['instance_id'] for opt in option_rows}:
            continue
        if entry['instance_id'] not in {item['instance_id'] for item in standalone}:
            continue
        profile = cyberware_weapon_profile(entry)
        if not profile:
            continue
        stored = runtime_states.get(entry['instance_id']) or {}
        weapon_state = stored.get('weapon') if isinstance(stored.get('weapon'), dict) else {}
        maximum = max(0, int(_num(profile.get('magazine')) or 0))
        profile = copy.deepcopy(profile)
        profile['instance_id'] = entry['instance_id']
        profile['name'] = entry.get('custom_name') or entry.get('name') or profile['id']
        profile['state'] = {
            'deployed': weapon_state.get('deployed') is True or not profile.get('deployable'),
            'revved': weapon_state.get('revved') is True,
            'magazine': max(0, min(maximum, int(_num(weapon_state.get('magazine')) or 0))),
            'magazine_max': maximum,
            'loaded_payload': weapon_state.get('loaded_payload'),
        }
        if profile.get('special_ammo'):
            profile['shared_ammo_available'] = 0
        else:
            ammo_kinds = profile.get('ammo_kinds') or ([profile.get('ammo_kind')] if profile.get('ammo_kind') else [])
            profile['shared_ammo_available'] = sum(shared_ammo_available(data, ammo_kind=kind) for kind in ammo_kinds)
        weapon_profiles.append(profile)
    popup_shields = [
        popup_shield_profile(data, next(entry for entry in chrome
                                        if entry.get('instance_id') == option['instance_id']))
        for option in option_rows
        if option['state'] == 'installed' and option['status'] == 'installed' and
        option['catalog_item_id'] == 'cyberware-120']
    popup_shields = [item for item in popup_shields if item]
    return {
        'hosts': sorted(hosts.values(), key=lambda item: (item['host_kind'], item['name'],
                                                          item['instance_id'])),
        'options': option_rows, 'standalone': standalone, 'staged': staged,
        'active_payloads': active_payloads,
        'initiative_modifier': initiative_modifier,
        'capabilities': [payload['capability'] for payload in active_payloads
                         if payload.get('kind') == 'capability'],
        'contextual_modifiers': [payload for payload in active_payloads
                                 if payload.get('kind') in (
                                     'contextual_modifier', 'contextual_skill_modifier')],
        'weapon_profiles': weapon_profiles,
        'popup_shields': popup_shields,
        'unbound_count': sum(item['status'] in ('unbound', 'invalid')
                             for item in option_rows),
    }


def cyberware_option_compatibility(data, option_instance_id, requested_host_ids):
    loadout = effective_cyberware_loadout(data)
    option = next((item for item in loadout['options']
                   if item['instance_id'] == option_instance_id), None)
    if not option:
        return {'allowed': False, 'reasons': ['Item is not a Cyberware Option']}
    host_by_id = {item['instance_id']: item for item in loadout['hosts']}
    host_ids = []
    for value in requested_host_ids or []:
        value = str(value or '').lower()
        if value and value not in host_ids:
            host_ids.append(value)
    reasons = []
    if len(host_ids) != option['hosts_required']:
        reasons.append(f'Requires {option["hosts_required"]} different concrete hosts')
    for host_id in host_ids:
        host = host_by_id.get(host_id)
        if not host:
            reasons.append('Selected host is missing or not installed')
            continue
        if host['host_kind'] != option['expected_host']:
            reasons.append(f'Selected host must be {option["expected_host"]}')
        current_uses = option['slots_used_per_host'] \
            if host_id in option['host_instance_ids'] and option['state'] == 'installed' else 0
        if (host['slots_used'] - current_uses + option['slots_used_per_host'] >
                host['slots_total']):
            reasons.append(f'{host["name"]}: not enough Option Slots')
    entry = next((item for item in data.get('cyberware') or []
                  if isinstance(item, dict) and
                  item.get('instance_id') == option_instance_id), {})
    if cyberware_capacity(entry).get('unique'):
        catalog_id = _LATE['catalog_item_id_for_entry'](entry)
        if any(isinstance(item, dict) and item.get('instance_id') != option_instance_id and
               cyberware_is_installed(item) and
               _LATE['catalog_item_id_for_entry'](item) == catalog_id
               for item in data.get('cyberware') or []):
            reasons.append('Only one installed copy is allowed')
    return {
        'allowed': not reasons, 'reasons': reasons,
        'option': option, 'host_instance_ids': host_ids,
    }


def validate_bound_popup_weapon_references(data):
    chrome_by_id = {item.get('instance_id'): item for item in data.get('cyberware') or []
                    if isinstance(item, dict) and item.get('instance_id')}
    weapon_by_id = {item.get('instance_id'): item for item in data.get('inventory') or []
                    if isinstance(item, dict) and item.get('instance_id')}
    claimed = set()
    states = data.get('cyberware_state') if isinstance(data.get('cyberware_state'), dict) else {}
    for option_id, state in states.items():
        if not isinstance(state, dict) or not state.get('bound_weapon_instance_id'):
            continue
        option = chrome_by_id.get(option_id)
        weapon_id = str(state.get('bound_weapon_instance_id') or '')
        weapon = weapon_by_id.get(weapon_id)
        if (not option or not popup_weapon_binding_kind(option) or not weapon or
                weapon_id in claimed or weapon.get('state') != 'installed' or
                weapon.get('installed_cyberware_instance_id') != option_id):
            raise ApiError(409, 'Повреждена связь Popup Cyberweapon')
        claimed.add(weapon_id)
    for weapon in weapon_by_id.values():
        option_id = str(weapon.get('installed_cyberware_instance_id') or '')
        if option_id and weapon.get('instance_id') not in claimed:
            raise ApiError(409, 'Повреждена связь Popup Cyberweapon')


def validate_cyberware_trust_lifecycle(before, after):
    """Prevent generic sheet edits from bypassing surgical install/uninstall audit."""
    old = {item.get('instance_id'): item for item in before.get('cyberware') or []
           if isinstance(item, dict) and item.get('instance_id')}
    new = {item.get('instance_id'): item for item in after.get('cyberware') or []
           if isinstance(item, dict) and item.get('instance_id')}
    for instance_id, previous in old.items():
        if not cyberware_is_installed(previous):
            continue
        current = new.get(instance_id)
        if not current:
            raise ApiError(409, 'Сначала удалите Cyberware через audited Uninstall')
        if not cyberware_is_installed(current):
            raise ApiError(409, 'Изменяйте Cyberware installation только через lifecycle action')
        if cyberware_host_assignments(previous) != cyberware_host_assignments(current):
            raise ApiError(409, 'Изменяйте concrete Cyberware hosts только через lifecycle action')
        if previous.get('installation_side') != current.get('installation_side'):
            raise ApiError(409, 'Изменяйте Cyberware side только через lifecycle action')


def validate_cyberware_requirements(data):
    """Проверяет явные фундаментальные требования из описаний Data Pool."""
    installed = [c for c in data.get('cyberware') or []
                 if isinstance(c, dict) and cyberware_is_installed(c)]
    chrome = [c for c in installed
              if not (c.get('creation_free') and c.get('key') == 'creation-neuroport')]
    items = [item_by_id(str(c.get('key') or '')) for c in chrome]
    items = [item for item in items if item]
    names = [item['name'].lower() for item in items]
    inventory_names = [str(entry.get('name') or '').lower() for entry in data.get('inventory') or []]
    has_port = any(c.get('key') == 'creation-neuroport' for c in installed) or \
        'neuroport' in names
    foundations = {
        'cybereye': {'cybereye', 'sponsored cybereye'},
        'cyberarm': {'cyberarm', 'neo-soviet cyberarm'},
        'cyberleg': {'cyberleg', 'romanova cyberlegs',
                     'rocklin augmentics skydrivers'},
        'cyberaudio suite': {'cyberaudio suite', 'discount cyberaudio suite'},
        'chipware socket': {'chipware socket', 'budget chipware socket'},
    }
    def count_foundation(kind):
        return sum(
            (2 if kind == 'cyberleg' and name in {
                'romanova cyberlegs', 'rocklin augmentics skydrivers'} else 1)
            for name in names if name in foundations[kind])
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


def validate_cyberware_slots(data, allow_unbound=False):
    """Validate concrete host assignment, paired options, slots, and uniqueness."""
    unique_counts = {}
    for entry in data.get('cyberware') or []:
        if not isinstance(entry, dict) or not cyberware_is_installed(entry) or \
                not cyberware_capacity(entry).get('unique'):
            continue
        catalog_id = _LATE['catalog_item_id_for_entry'](entry)
        unique_counts[catalog_id] = unique_counts.get(catalog_id, 0) + 1
        if unique_counts[catalog_id] > 1:
            name = (item_by_id(catalog_id) or entry).get('name') or 'Cyberware'
            raise ApiError(400, f'{name}: допустима только одна установка')
    loadout = effective_cyberware_loadout(data)
    for option in loadout['options']:
        if option['state'] != 'installed':
            continue
        if option['status'] in ('unbound', 'invalid'):
            if allow_unbound and not option['host_instance_ids']:
                continue
            if len(option['host_instance_ids']) != option['hosts_required']:
                raise ApiError(
                    400, f'{option["name"]}: требуется совместимых hosts: '
                         f'{option["hosts_required"]}')
            reason = '; '.join(option['reasons']) or 'invalid host assignment'
            raise ApiError(400, f'{option["name"]}: {reason}')
    for host in loadout['hosts']:
        if host['overloaded']:
            raise ApiError(
                400, f'{host["name"]}: Option Slots '
                     f'{host["slots_used"]}/{host["slots_total"]}')


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
    validate_cyberware_sides(data, allow_unassigned=True)
    validate_cyberware_payload_conflicts(data)
    if (derive(data).get('humanity_cur') or 0) < 0:
        raise ApiError(400, 'Нельзя завершить создание с Humanity ниже 0')
    validate_creation_budget(data)
