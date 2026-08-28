"""Движок модификаций оружия/транспорта и боеприпасов NC//NET (P1-4).

Выделено из app/server.py: схемы конфигурации модификаций, состояние
обойм/общего боезапаса, вычисление эффективных характеристик оружия и
транспорта с учётом установленных модификаций и навыков персонажа.
Логика не менялась. Поздние зависимости на inventory/tech-maker — через
bind() (см. docs/repo-audit-2026-08.md).
"""
import copy
import math
import re

from core import INSTANCE_ID_RE, ApiError
from rules import _num
from catalog import (item_by_id, vehicle_modification_rules_for_catalog,
                     weapon_modification_rules_for_catalog, weapon_range_table_info)


_LATE = {}


def bind(**kwargs):
    """Подключить поздние зависимости (см. docstring модуля)."""
    _LATE.update(kwargs)



def weapon_modification_configuration_schema(catalog_id, host=None):
    schemas = [copy.deepcopy(rule['configuration'])
               for rule in weapon_modification_rules_for_catalog(catalog_id)
               if isinstance(rule.get('configuration'), dict)]
    for schema in schemas:
        if schema.get('choice_source') == 'compatible_range_tables':
            info = weapon_range_table_info(host or {})
            schema['choices'] = [
                {'value': name, 'label_en': name, 'label_ru': name}
                for name in info['choices']]
            schema['base_value'] = info['base']
            schema['weapon_family'] = info['family']
    return schemas


def clean_weapon_modification_choices(catalog_id, raw, host=None):
    schemas = weapon_modification_configuration_schema(catalog_id, host)
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ApiError(400, 'Modification configuration должна быть объектом')
    allowed_keys = {schema['key'] for schema in schemas}
    if set(raw) - allowed_keys:
        raise ApiError(400, 'Modification configuration содержит неизвестные поля')
    clean = {}
    for schema in schemas:
        value = str(raw.get(schema['key']) or '')
        choices = {choice['value'] for choice in schema.get('choices') or []}
        if schema.get('required') and not value:
            raise ApiError(400, 'Выберите обязательную конфигурацию modification')
        if value and value not in choices:
            raise ApiError(400, 'Некорректный вариант configuration')
        if value:
            clean[schema['key']] = value
    return clean


def weapon_profiles_from_rules(rules):
    return [copy.deepcopy(effect['profile']) for rule in rules or []
            for effect in rule.get('effects') or []
            if effect.get('target') == 'weapon.alternate_profile' and
            isinstance(effect.get('profile'), dict)]


def ammo_kind_for_modification_profile(rules, profile_id):
    for rule in rules or []:
        for effect in rule.get('effects') or []:
            profile = effect.get('profile') or {}
            if profile.get('id') == profile_id:
                return profile.get('ammo_kind')
    return None


def ammo_pack_size(entry):
    mechanics = (entry or {}).get('mechanics') or {}
    return max(1, int(_num(mechanics.get('quantity_per_purchase')) or 1))


def ammo_rounds(entry):
    if not isinstance(entry, dict) or entry.get('cat') != 'ammo':
        return 0
    maximum = max(1, int(_num(entry.get('qty')) or 1)) * ammo_pack_size(entry)
    current = _num(entry.get('ammo_rounds'))
    return max(0, min(maximum, int(current if current is not None else maximum)))


def ensure_shared_ammo_state(data):
    for item in data.get('inventory') or []:
        if not isinstance(item, dict) or item.get('cat') != 'ammo':
            continue
        item['ammo_rounds'] = ammo_rounds(item)
    for state in (data.get('weapon_state') or {}).values():
        if isinstance(state, dict):
            state['reserve'] = 0
            if (_num(state.get('magazine')) or 0) <= 0:
                state.pop('loaded_ammo_catalog_id', None)
                state.pop('loaded_ammo_name', None)
    for state in (data.get('modification_state') or {}).values():
        if isinstance(state, dict) and state.get('resource_type') == 'mounted_weapon':
            state['reserve'] = 0
            if (_num(state.get('magazine')) or 0) <= 0:
                state.pop('loaded_ammo_catalog_id', None)
                state.pop('loaded_ammo_name', None)
    return data


def ammo_matches_requirement(entry, ammo_kind=None, weapon=None):
    if not isinstance(entry, dict) or entry.get('cat') != 'ammo' or ammo_rounds(entry) <= 0:
        return False
    mechanics = entry.get('mechanics') or {}
    compatible = str(mechanics.get('compatible_weapons') or '').lower()
    ammo_name = str(entry.get('name') or '').lower()
    if ammo_kind == 'grenade':
        return 'grenade' in compatible and 'except grenades' not in compatible
    if ammo_kind == 'shotgun':
        return ('shotgun' in compatible or 'slug' in compatible or
                'shell' in compatible or 'all except grenades & rockets' in compatible)
    if ammo_kind == 'incendiary_shotgun':
        return ('incendiary' in ammo_name and
                ('shotgun' in compatible or 'slug' in compatible or
                 'shell' in compatible))
    if ammo_kind == 'rifle':
        return ('bullet' in compatible or
                'all except grenades & rockets' in compatible or
                'all except shotgun shells' in compatible)
    if ammo_kind == 'rocket':
        return 'rocket' in compatible and 'except grenades & rockets' not in compatible
    catalog_weapon = item_by_id(_LATE['catalog_item_id_for_entry'](weapon)) or {}
    weapon_name = str((weapon or {}).get('name') or catalog_weapon.get('name') or '').lower()
    weapon_type = str(((weapon or {}).get('mechanics') or
                       catalog_weapon.get('mechanics') or {}).get('type') or '').lower()
    if weapon_name and weapon_name in compatible:
        return True
    if 'grenade launcher' in weapon_type:
        return 'grenade' in compatible and 'except grenades' not in compatible
    if 'rocket launcher' in weapon_type or 'missile launcher' in weapon_type:
        return 'rocket' in compatible and 'except grenades & rockets' not in compatible
    if 'shotgun' in weapon_type:
        return ('shotgun' in compatible or 'slug' in compatible or
                'shell' in compatible or 'all except grenades & rockets' in compatible)
    if 'bow' in weapon_type or 'crossbow' in weapon_type:
        return ('arrow' in compatible or 'bolt' in compatible or
                'all except grenades & rockets' in compatible)
    return ('bullet' in compatible or
            'all except grenades & rockets' in compatible or
            'all except shotgun shells' in compatible)


def shared_ammo_available(character, ammo_kind=None, weapon=None):
    return sum(ammo_rounds(item) for item in character.get('inventory') or []
               if ammo_matches_requirement(item, ammo_kind, weapon))


def consume_shared_ammo(data, state, ammo_instance_id, *, ammo_kind=None, weapon=None):
    ammo_instance_id = str(ammo_instance_id or '').lower()
    if not INSTANCE_ID_RE.fullmatch(ammo_instance_id):
        raise ApiError(400, 'Выберите конкретный ammo stack')
    inventory = data.get('inventory') or []
    ammo = next((item for item in inventory if isinstance(item, dict) and
                 item.get('instance_id') == ammo_instance_id), None)
    if not ammo or ammo.get('state') not in ('carried', 'stored'):
        raise ApiError(409, 'Ammo stack недоступен для Reload')
    if not ammo_matches_requirement(ammo, ammo_kind, weapon):
        raise ApiError(400, 'Ammo stack несовместим с этим оружием')
    current = max(0, int(_num(state.get('magazine')) or 0))
    maximum = max(0, int(_num(state.get('magazine_max')) or 0))
    if maximum <= current:
        raise ApiError(409, 'Магазин уже заполнен')
    catalog_id = _LATE['catalog_item_id_for_entry'](ammo)
    loaded_catalog_id = str(state.get('loaded_ammo_catalog_id') or '')
    if current > 0 and loaded_catalog_id and loaded_catalog_id != catalog_id:
        raise ApiError(409, 'Нельзя смешивать разные типы ammo в одном магазине')
    available = ammo_rounds(ammo)
    moved = min(maximum - current, available)
    if moved <= 0:
        raise ApiError(409, 'В выбранном ammo stack нет боеприпасов')
    state['magazine'] = current + moved
    state['loaded_ammo_catalog_id'] = catalog_id
    state['loaded_ammo_name'] = ammo.get('name') or 'Ammo'
    remaining = available - moved
    if remaining <= 0:
        inventory.remove(ammo)
    else:
        ammo['ammo_rounds'] = remaining
        ammo['qty'] = max(1, math.ceil(remaining / ammo_pack_size(ammo)))
    return {
        'moved': moved, 'ammo_name': state['loaded_ammo_name'],
        'ammo_catalog_id': catalog_id, 'remaining': remaining,
    }


def clear_loaded_ammo_if_empty(state):
    if (_num((state or {}).get('magazine')) or 0) <= 0:
        state.pop('loaded_ammo_catalog_id', None)
        state.pop('loaded_ammo_name', None)


VEHICLE_COMPLEX_PURPOSE_LABELS = {
    'cargo_bay': ('Cargo Bay', 'Грузовой отсек'),
    'bunkhouse': ('Bunkhouse', 'Казарма'),
    'cafeteria': ('Cafeteria', 'Кафетерий'),
    'restaurant': ('Restaurant', 'Ресторан'),
    'recreation_deck': ('Recreation Deck', 'Зона отдыха'),
    'prison': ('Prison', 'Тюремный блок'),
    'bowling_alley': ('Bowling Alley', 'Боулинг'),
    'laser_tag_arena': ('Laser Tag Arena', 'Арена лазертага'),
    'other_complex': ('Other Complex Room', 'Другая комплексная комната'),
}


def vehicle_action_effects_from_rules(rules):
    return [copy.deepcopy(effect) for rule in rules or []
            for effect in rule.get('effects') or []
            if effect.get('target') in {
                'vehicle.nos_tank', 'vehicle.mounted_weapon', 'vehicle.weapon_mount',
                'vehicle.interior', 'vehicle.room_upgrade', 'vehicle.cargo'}]


def vehicle_modification_configuration_schema(catalog_id):
    schemas = []
    for effect in vehicle_action_effects_from_rules(
            vehicle_modification_rules_for_catalog(catalog_id)):
        profile = effect.get('profile') or {}
        if effect.get('target') == 'vehicle.mounted_weapon':
            orientations = profile.get('orientations') or []
            if len(orientations) > 1:
                schemas.append({
                    'key': 'orientation',
                    'label_en': 'Mount orientation',
                    'label_ru': 'Направление установки',
                    'required': True,
                    'choices': [
                        {'value': value, 'label_en': value.title(),
                         'label_ru': {'front': 'Спереди', 'side': 'Сбоку',
                                      'rear': 'Сзади'}[value]}
                        for value in orientations],
                })
        elif (effect.get('target') == 'vehicle.room_upgrade' and
              profile.get('kind') == 'complex'):
            schemas.append({
                'key': 'purpose', 'label_en': 'Complex Room purpose',
                'label_ru': 'Назначение комплексной комнаты', 'required': True,
                'choices': [
                    {'value': value,
                     'label_en': VEHICLE_COMPLEX_PURPOSE_LABELS[value][0],
                     'label_ru': VEHICLE_COMPLEX_PURPOSE_LABELS[value][1]}
                    for value in profile.get('purposes') or []],
            })
    return schemas


def clean_vehicle_modification_choices(catalog_id, raw):
    schemas = vehicle_modification_configuration_schema(catalog_id)
    raw = raw or {}
    if not isinstance(raw, dict):
        raise ApiError(400, 'Vehicle configuration должна быть объектом')
    allowed_keys = {schema['key'] for schema in schemas}
    if set(raw) - allowed_keys:
        raise ApiError(400, 'Vehicle configuration содержит неизвестные поля')
    clean = {}
    for schema in schemas:
        value = str(raw.get(schema['key']) or '')
        choices = {choice['value'] for choice in schema.get('choices') or []}
        if len(choices) == 1 and not value:
            value = next(iter(choices))
        if schema.get('required') and not value:
            raise ApiError(400, 'Выберите обязательную конфигурацию транспорта')
        if value and value not in choices:
            raise ApiError(400, 'Некорректная конфигурация транспорта')
        if value:
            clean[schema['key']] = value
    return clean


def initial_vehicle_modification_state(rules, character, choices=None):
    choices = choices or {}
    effects = vehicle_action_effects_from_rules(rules)
    for effect in effects:
        if effect.get('target') == 'vehicle.nos_tank':
            maximum = int((effect.get('resource') or {}).get('uses') or 1)
            return {
                'resource_type': 'nos_tank', 'profile_id': 'nos_tank',
                'uses_remaining': maximum, 'uses_max': maximum,
            }
        if effect.get('target') == 'vehicle.weapon_mount':
            resource = effect.get('resource') or {}
            return {
                'resource_type': 'heavy_weapon_mount',
                'profile_id': resource.get('id') or 'heavy_weapon_mount',
                'weapon_instance_id': None,
            }
        if effect.get('target') == 'vehicle.mounted_weapon':
            profile = effect.get('profile') or {}
            return {
                'resource_type': 'mounted_weapon',
                'profile_id': profile.get('id'),
                'magazine': 0,
                'magazine_max': int(profile.get('magazine') or 0),
                'reserve': 0,
                'ammo_cost': int(profile.get('ammo_cost') or 1),
                'orientation': choices.get('orientation') or
                    ((profile.get('orientations') or [None])[0]),
            }
    return None


def normalize_vehicle_modification_state(existing, authoritative):
    if not authoritative:
        return existing
    existing = existing if isinstance(existing, dict) else {}
    normalized = copy.deepcopy(authoritative)
    if authoritative['resource_type'] == 'nos_tank':
        maximum = authoritative['uses_max']
        current = _num(existing.get('uses_remaining'))
        normalized['uses_remaining'] = max(
            0, min(maximum, int(current if current is not None else maximum)))
    elif authoritative['resource_type'] == 'heavy_weapon_mount':
        weapon_instance_id = str(existing.get('weapon_instance_id') or '').lower()
        normalized['weapon_instance_id'] = (
            weapon_instance_id if INSTANCE_ID_RE.fullmatch(weapon_instance_id) else None)
    else:
        maximum = authoritative['magazine_max']
        magazine = _num(existing.get('magazine'))
        normalized['magazine'] = max(
            0, min(maximum, int(magazine if magazine is not None else 0)))
        normalized['reserve'] = 0
        if normalized['magazine'] > 0:
            loaded_catalog_id = str(existing.get('loaded_ammo_catalog_id') or '')
            if item_by_id(loaded_catalog_id):
                normalized['loaded_ammo_catalog_id'] = loaded_catalog_id
                normalized['loaded_ammo_name'] = str(
                    existing.get('loaded_ammo_name') or
                    item_by_id(loaded_catalog_id).get('name') or 'Ammo')[:120]
    return normalized


def evaluate_effective_weapon(host, modifications, owned_by_id, character):
    base = copy.deepcopy(host.get('mechanics') or {})
    effective = copy.deepcopy(base)
    host_catalog = item_by_id(_LATE['catalog_item_id_for_entry'](host)) or {}
    base_feature_text = ' '.join(str(value) for value in (host_catalog.get('fields') or {}).values()).lower()
    base_has_autofire = 'autofire' in base_feature_text
    excellent_quality = 'excellent' in str(base.get('quality') or '').lower()
    range_info = weapon_range_table_info(host)
    base_range_table = range_info.get('base')
    effective_range_table = base_range_table
    base_magazine = _num(base.get('magazine')) or 0
    effective_magazine = base_magazine
    base_concealable = base.get('concealable')
    effective_concealable = base_concealable
    attack_modifier = 0
    alternate_attacks = []
    autofire_profiles = []
    weapon_tags = []
    applied = []
    sources = []
    installed_cyberware = {
        _LATE['catalog_item_id_for_entry'](item) for item in character.get('cyberware') or []
        if isinstance(item, dict) and str(item.get('state') or 'installed') == 'installed'
    }
    weapon_type = str(base.get('type') or '')
    for modification in modifications:
        upgrade = owned_by_id.get(modification.get('upgrade_instance_id')) or {}
        config = modification.get('configuration') or {}
        rules = config.get('effect_rules')
        if not isinstance(rules, list):
            rules = weapon_modification_rules_for_catalog(_LATE['catalog_item_id_for_entry'](upgrade))
        if not rules:
            grants = copy.deepcopy(upgrade.get('grants_slots') or {})
            sources.append({
                'id': f'{"slot-grant" if grants else "manual"}:{modification.get("modification_id")}',
                'label_en': upgrade.get('name') or config.get('upgrade_name') or 'Upgrade',
                'label_ru': upgrade.get('name') or config.get('upgrade_name') or 'Upgrade',
                'active': True, 'automated': bool(grants),
                'manual_resolution_required': not bool(grants),
                'source': upgrade.get('installation_source') or upgrade.get('source'),
                'effects': [
                    {'target': f'weapon.{pool}_slots', 'operation': 'add',
                     'value': amount, 'active': True}
                    for pool, amount in grants.items()],
                'manual_rules': [],
            })
            continue
        for rule in rules:
            requirements = rule.get('requirements') or {}
            required_any = requirements.get('installed_any') or []
            requirements_met = not required_any or bool(installed_cyberware & set(required_any))
            rule_effects = []
            for definition in rule.get('effects') or []:
                effect = copy.deepcopy(definition)
                effect['active'] = requirements_met
                effect['modification_id'] = modification.get('modification_id')
                if effect['target'] == 'weapon.magazine':
                    value = (effect.get('values') or {}).get(weapon_type)
                    if value is None:
                        effect['active'] = False
                        effect['suppressed_reason'] = f'No magazine value for {weapon_type}'
                    elif requirements_met:
                        effect['before'] = effective_magazine
                        effective_magazine = int(value)
                        effect['after'] = effective_magazine
                elif effect['target'] == 'weapon.concealable' and requirements_met:
                    effect['before'] = effective_concealable
                    effective_concealable = effect['value']
                    effect['after'] = effective_concealable
                elif effect['target'] == 'weapon.alternate_profile' and requirements_met:
                    profile = copy.deepcopy(effect['profile'])
                    profile.update({
                        'modification_id': modification.get('modification_id'),
                        'upgrade_instance_id': modification.get('upgrade_instance_id'),
                        'source': effect.get('source'),
                        'shared_ammo_available': shared_ammo_available(
                            character, profile.get('ammo_kind')),
                        'state': copy.deepcopy(
                            (character.get('modification_state') or {}).get(
                                modification.get('modification_id'), {})),
                    })
                    alternate_attacks.append(profile)
                elif effect['target'] == 'weapon.autofire_profile' and requirements_met:
                    if effect.get('operation') == 'grant':
                        profile = copy.deepcopy(effect.get('profile') or {})
                        enhanced_when = set(effect.get('enhanced_when') or [])
                        if (('excellent_quality' in enhanced_when and excellent_quality) or
                                ('base_autofire' in enhanced_when and base_has_autofire)):
                            profile['multiplier'] = effect.get('enhanced_multiplier', profile.get('multiplier'))
                    else:
                        choice = (config.get('choices') or {}).get(effect.get('configuration_key'))
                        profile = copy.deepcopy((effect.get('profiles') or {}).get(choice) or {})
                        if not profile:
                            effect['active'] = False
                            effect['suppressed_reason'] = 'Required installation configuration is missing'
                    if profile:
                        profile.update({
                            'modification_id': modification.get('modification_id'),
                            'upgrade_instance_id': modification.get('upgrade_instance_id'),
                            'source': effect.get('source'),
                        })
                        autofire_profiles.append(profile)
                elif effect['target'] == 'weapon.range_table' and requirements_met:
                    choice = (config.get('choices') or {}).get(effect.get('configuration_key'))
                    if choice in range_info.get('choices', []):
                        effect['before'] = effective_range_table
                        effective_range_table = choice
                        effect['after'] = effective_range_table
                    else:
                        effect['active'] = False
                        effect['suppressed_reason'] = 'Required compatible Range Table choice is missing'
                elif effect['target'] == 'weapon.tag' and requirements_met:
                    if effect.get('value') not in weapon_tags:
                        weapon_tags.append(effect.get('value'))
                elif effect['target'] == 'weapon.attack_check' and requirements_met:
                    effect['before'] = attack_modifier
                    attack_modifier += effect['value']
                    effect['after'] = attack_modifier
                if effect.get('active'):
                    applied.append(effect)
                rule_effects.append(effect)
            sources.append({
                'id': rule['id'], 'label_en': rule.get('label_en') or rule['id'],
                'label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
                'active': requirements_met,
                'automated': True,
                'requirements_met': requirements_met,
                'requirement_label_en': requirements.get('label_en'),
                'requirement_label_ru': requirements.get('label_ru'),
                'source': next((effect.get('source') for effect in rule_effects
                                if effect.get('source')), None),
                'effects': rule_effects,
                'manual_rules': [
                    {**copy.deepcopy(manual), 'manual_resolution_required': True}
                    for manual in rule.get('manual_rules') or []],
                'modification_id': modification.get('modification_id'),
                'upgrade_instance_id': modification.get('upgrade_instance_id'),
            })
    # Tech Maker custom modifications: declarative, allowlisted, non-stacking.
    for mod in _LATE['character_tech_maker_modifications'](character).values():
        if mod.get('host_instance_id') != host.get('instance_id'):
            continue
        effect = mod.get('effect')
        if not isinstance(effect, dict):
            continue
        target = effect.get('target')
        maker = {
            'id': f'tech-maker:{target}',
            'label_en': mod.get('name') or 'Tech Maker Modification',
            'label_ru': mod.get('name') or 'Tech Maker Modification',
            'active': True, 'automated': True, 'source_type': 'tech_maker',
            'source': mod.get('source'),
            'modification_id': mod.get('modification_id'),
            'manual_resolution_required': False,
            'effects': [copy.deepcopy(effect)],
        }
        if target == 'weapon.attack_check':
            effect['before'] = attack_modifier
            attack_modifier += int(effect.get('value') or 0)
            effect['after'] = attack_modifier
        elif target == 'weapon.magazine':
            effect['before'] = effective_magazine
            effective_magazine = max(0, effective_magazine + int(effect.get('value') or 0))
            effect['after'] = effective_magazine
        elif target == 'weapon.concealable':
            effect['before'] = effective_concealable
            effective_concealable = effect.get('value')
            effect['after'] = effective_concealable
        maker['effects'] = [copy.deepcopy(effect)]
        applied.append(effect)
        sources.append(maker)
    if base_magazine or effective_magazine:
        effective['magazine'] = effective_magazine
    if effective_concealable is not None:
        effective['concealable'] = effective_concealable
    if effective_range_table is not None:
        effective['range_table'] = effective_range_table
    slot_pools = _LATE['weapon_slot_capacity'](host, modifications, owned_by_id)
    return {
        'instance_id': host.get('instance_id'),
        'base': {**base, 'range_table': base_range_table}, 'effective': effective,
        'attack_modifier': attack_modifier,
        'shared_ammo_available': shared_ammo_available(character, weapon=host),
        'alternate_attacks': alternate_attacks,
        'autofire_profiles': autofire_profiles,
        'tags': weapon_tags,
        'slot_pools': slot_pools,
        'slots_total': sum(pool['total'] for pool in slot_pools.values()),
        'slots_used': sum(pool['used'] for pool in slot_pools.values()),
        'modifiers': applied, 'sources': sources,
    }


def character_effective_weapons(character, modifications):
    owned = {item.get('instance_id'): item for item in character.get('inventory') or []
             if isinstance(item, dict) and item.get('instance_id')}
    result = {}
    for host in (item for item in character.get('inventory') or []
                 if isinstance(item, dict) and item.get('cat') == 'guns'):
        host_modifications = [modification for modification in modifications
                              if modification.get('host_instance_id') == host.get('instance_id')]
        result[host['instance_id']] = evaluate_effective_weapon(
            host, host_modifications, owned, character)
    return result


def vehicle_base_interior(host):
    catalog_item = item_by_id(_LATE['catalog_item_id_for_entry'](host)) or {}
    mechanics = host.get('mechanics') or catalog_item.get('mechanics') or {}
    name = str(host.get('name') or catalog_item.get('name') or '')
    description = str(catalog_item.get('desc') or '')
    room_count = 0
    total_match = re.search(r'total of\s+(\d+)\s+rooms?', description, re.I)
    minimum_match = re.search(r'minimum\s+(\w+)\s+rooms?', description, re.I)
    word_numbers = {'one': 1, 'two': 2, 'three': 3, 'four': 4}
    if total_match:
        room_count = int(total_match.group(1))
    elif re.search(r'only one room', description, re.I):
        room_count = 1
    elif minimum_match:
        token = minimum_match.group(1).lower()
        room_count = int(token) if token.isdigit() else word_numbers.get(token, 0)
    elif name == 'Cabin Cruiser':
        room_count = 2
    elif name == 'Yacht':
        room_count = 4
    elif name == 'Aerozep':
        room_count = 2
    seats_value = str(mechanics.get('seats') or '')
    seats_match = re.search(r'(\d+)\s+per\s+room', seats_value, re.I)
    seats_per_room = int(seats_match.group(1)) if seats_match else (
        4 if 'yacht' in f'{name} {description}'.lower() else
        (2 if room_count else 0))
    return {
        'base_rooms': room_count, 'rooms_total': room_count,
        'normal_rooms': room_count, 'luxury_rooms': 0, 'complex_rooms': 0,
        'seats_per_room': seats_per_room,
        'kombi': False, 'beds': 0, 'amenities': [],
        'complex_purposes': [],
    }


def bound_vehicle_weapon_profile(weapon, effective_weapon, character):
    mechanics = effective_weapon.get('effective') or weapon.get('mechanics') or {}
    catalog_item = item_by_id(_LATE['catalog_item_id_for_entry'](weapon)) or {}
    description = str(catalog_item.get('desc') or '')
    rule_text = ' '.join([
        description,
        *[str(value) for value in (catalog_item.get('fields') or {}).values()],
    ])
    skill = str(mechanics.get('skill') or '')
    autofire_only = skill == 'Autofire' or 'can only autofire' in rule_text.lower()
    ammo_cost_match = re.search(r'uses\s+(\d+)\s+rounds whenever it fires',
                                rule_text, re.I)
    multiplier_match = re.search(r'max autofire multiplier of\s+(\d+)',
                                  rule_text, re.I)
    weapon_state = copy.deepcopy((character.get('weapon_state') or {}).get(
        weapon.get('instance_id')) or {})
    profile = {
        'id': f'bound:{weapon.get("instance_id")}',
        'weapon_instance_id': weapon.get('instance_id'),
        'label_en': weapon.get('custom_name') or weapon.get('name') or 'Mounted Weapon',
        'label_ru': weapon.get('custom_name') or weapon.get('name') or 'Закреплённое оружие',
        'kind': 'autofire' if autofire_only else 'standard',
        'skill': skill, 'weapon_type': mechanics.get('type'),
        'range_table': mechanics.get('range_table'),
        'damage': (mechanics.get('damage') or {}).get('notation')
            if isinstance(mechanics.get('damage'), dict) else mechanics.get('damage'),
        'rof': mechanics.get('rof'), 'hands_required': mechanics.get('hands'),
        'magazine': mechanics.get('magazine'),
        'ammo_cost': int(ammo_cost_match.group(1)) if ammo_cost_match else
            (10 if autofire_only else 1),
        'autofire_multiplier': int(multiplier_match.group(1))
            if multiplier_match else (4 if autofire_only else None),
        'reload_actions': 2 if re.search(
            r'(?:requires?|takes?)\s+2\s+(?:rounds|actions?)\s+to reload|'
            r'2\s+actions?\s+to reload', rule_text, re.I) else 1,
        'attack_modifier': effective_weapon.get('attack_modifier') or 0,
        'shared_ammo_available': shared_ammo_available(character, weapon=weapon),
        'state': weapon_state, 'operator': 'passenger',
        'source': catalog_item.get('source') or weapon.get('source'),
        'manual_resolution_required': True,
    }
    return profile


def evaluate_effective_vehicle(host, modifications, owned_by_id,
                               character=None, all_modifications=None):
    character = character or {}
    all_modifications = all_modifications or modifications
    base = copy.deepcopy(host.get('mechanics') or {})
    base_sdp = max(0, _num(base.get('sdp')) or 0)
    base_body_sp = max(0, _num(base.get('body_sp')) or 0)
    base_glass_hp = max(0, _num(base.get('glass_hp')) or 0)
    base_seats = _num(base.get('seats'))
    effective_sdp = base_sdp
    effective_body_sp = base_body_sp
    effective_glass_hp = base_glass_hp
    interior = vehicle_base_interior(host)
    effective_seats = base_seats if base_seats is not None else base.get('seats')
    if (base_seats is None and interior['rooms_total'] and
            interior['seats_per_room']):
        effective_seats = interior['rooms_total'] * interior['seats_per_room']
    sources = []
    nos_tanks = []
    mounted_weapons = []
    weapon_mounts = []
    cargo_modules = []
    modification_states = host.get('_modification_state') or {}
    active_catalog_counts = {}
    for modification in modifications:
        upgrade = owned_by_id.get(modification.get('upgrade_instance_id')) or {}
        catalog_id = _LATE['catalog_item_id_for_entry'](upgrade)
        active_catalog_counts[catalog_id] = active_catalog_counts.get(catalog_id, 0) + 1
    for modification in modifications:
        upgrade = owned_by_id.get(modification.get('upgrade_instance_id')) or {}
        config = modification.get('configuration') or {}
        catalog_id = _LATE['catalog_item_id_for_entry'](upgrade)
        rules = config.get('effect_rules')
        if not isinstance(rules, list) or not rules:
            rules = vehicle_modification_rules_for_catalog(catalog_id)
        if not rules:
            sources.append({
                'id': f'manual:{modification.get("modification_id")}',
                'label_en': upgrade.get('name') or config.get('upgrade_name') or 'Upgrade',
                'label_ru': upgrade.get('name') or config.get('upgrade_name') or 'Upgrade',
                'active': True, 'automated': False, 'effects': [],
                'manual_rules': [], 'source': upgrade.get('installation_source') or upgrade.get('source'),
            })
            continue
        for rule in rules:
            rule_effects = []
            for definition in rule.get('effects') or []:
                effect = copy.deepcopy(definition)
                effect['active'] = True
                effect['modification_id'] = modification.get('modification_id')
                effect['before'] = None
                if effect['target'] == 'vehicle.sdp_max':
                    effect['before'] = effective_sdp
                    effective_sdp += int(effect['value'])
                    effect['after'] = effective_sdp
                elif effect['target'] == 'vehicle.body_sp':
                    effect['before'] = effective_body_sp
                    effective_body_sp = max(effective_body_sp, int(effect['value']))
                    effect['after'] = effective_body_sp
                elif effect['target'] == 'vehicle.glass_hp':
                    effect['before'] = effective_glass_hp
                    count = min(2, active_catalog_counts.get(catalog_id, 1))
                    effective_glass_hp = max(
                        effective_glass_hp, int((effect.get('values') or {}).get(str(count), 0)))
                    effect['after'] = effective_glass_hp
                elif effect['target'] == 'vehicle.seats':
                    if isinstance(effective_seats, int):
                        effect['before'] = effective_seats
                        effective_seats += int(effect['value'])
                        effect['after'] = effective_seats
                    else:
                        effect['active'] = False
                        effect['suppressed_reason'] = 'Base seats are not a fixed numeric value'
                elif effect['target'] == 'vehicle.nos_tank':
                    resource = copy.deepcopy(effect.get('resource') or {})
                    maximum = int(resource.get('uses') or 1)
                    resource.update({
                        'modification_id': modification.get('modification_id'),
                        'upgrade_instance_id': modification.get('upgrade_instance_id'),
                        'state': copy.deepcopy(modification_states.get(
                            modification.get('modification_id')) or {
                                'resource_type': 'nos_tank',
                                'uses_remaining': maximum, 'uses_max': maximum,
                            }),
                        'source': effect.get('source'),
                    })
                    nos_tanks.append(resource)
                elif effect['target'] == 'vehicle.weapon_mount':
                    resource = copy.deepcopy(effect.get('resource') or {})
                    state = copy.deepcopy(modification_states.get(
                        modification.get('modification_id')) or {
                            'resource_type': 'heavy_weapon_mount',
                            'profile_id': 'heavy_weapon_mount',
                            'weapon_instance_id': None,
                        })
                    weapon_instance_id = state.get('weapon_instance_id')
                    weapon = owned_by_id.get(weapon_instance_id) if weapon_instance_id else None
                    bound_profile = None
                    if weapon and weapon.get('cat') == 'guns':
                        weapon_modifications = [
                            item for item in all_modifications
                            if item.get('host_instance_id') == weapon_instance_id]
                        effective_weapon = evaluate_effective_weapon(
                            weapon, weapon_modifications, owned_by_id, character)
                        bound_profile = bound_vehicle_weapon_profile(
                            weapon, effective_weapon, character)
                    resource.update({
                        'modification_id': modification.get('modification_id'),
                        'upgrade_instance_id': modification.get('upgrade_instance_id'),
                        'state': state, 'bound_weapon': bound_profile,
                        'source': effect.get('source'),
                    })
                    weapon_mounts.append(resource)
                elif effect['target'] == 'vehicle.interior':
                    profile = copy.deepcopy(effect.get('profile') or {})
                    if interior['base_rooms']:
                        interior['rooms_total'] += int(profile.get('rooms') or 0)
                        if isinstance(effective_seats, int) and interior['seats_per_room']:
                            effective_seats += interior['seats_per_room']
                    else:
                        interior['rooms_total'] = max(
                            interior['rooms_total'], int(profile.get('rooms') or 1))
                        interior['kombi'] = True
                        interior['beds'] += int(profile.get('beds') or 0)
                        for amenity in profile.get('amenities') or []:
                            if amenity not in interior['amenities']:
                                interior['amenities'].append(amenity)
                elif effect['target'] == 'vehicle.room_upgrade':
                    profile = copy.deepcopy(effect.get('profile') or {})
                    if profile.get('kind') == 'luxury':
                        interior['luxury_rooms'] += 1
                    elif profile.get('kind') == 'complex':
                        interior['complex_rooms'] += 1
                        purpose = (config.get('choices') or {}).get('purpose')
                        if purpose:
                            interior['complex_purposes'].append(purpose)
                            if purpose == 'cargo_bay':
                                cargo_modules.append({
                                    'id': f'complex-cargo:{modification.get("modification_id")}',
                                    'kind': 'cargo_bay', 'cargo_spaces': None,
                                    'modification_id': modification.get('modification_id'),
                                    'source': effect.get('source'),
                                    'manual_resolution_required': True,
                                })
                        if isinstance(effective_seats, int) and interior['seats_per_room']:
                            effective_seats += interior['seats_per_room'] * 2
                elif effect['target'] == 'vehicle.cargo':
                    profile = copy.deepcopy(effect.get('profile') or {})
                    profile.update({
                        'modification_id': modification.get('modification_id'),
                        'upgrade_instance_id': modification.get('upgrade_instance_id'),
                        'source': effect.get('source'),
                        'manual_resolution_required': True,
                    })
                    cargo_modules.append(profile)
                elif effect['target'] == 'vehicle.mounted_weapon':
                    profile = copy.deepcopy(effect.get('profile') or {})
                    orientations = profile.get('orientations') or []
                    choices = config.get('choices') or {}
                    profile.update({
                        'modification_id': modification.get('modification_id'),
                        'upgrade_instance_id': modification.get('upgrade_instance_id'),
                        'orientation': choices.get('orientation') or
                            (orientations[0] if orientations else None),
                        'shared_ammo_available': shared_ammo_available(
                            character, profile.get('ammo_kind')),
                        'state': copy.deepcopy(modification_states.get(
                            modification.get('modification_id')) or {
                                'resource_type': 'mounted_weapon',
                                'magazine': 0,
                                'magazine_max': int(profile.get('magazine') or 0),
                                'reserve': 0,
                                'ammo_cost': int(profile.get('ammo_cost') or 1),
                            }),
                        'source': effect.get('source'),
                    })
                    mounted_weapons.append(profile)
                rule_effects.append(effect)
            sources.append({
                'id': rule['id'], 'label_en': rule.get('label_en') or rule['id'],
                'label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
                'active': any(effect.get('active') for effect in rule_effects),
                'automated': True, 'effects': rule_effects,
                'manual_rules': [
                    {**copy.deepcopy(manual), 'manual_resolution_required': True}
                    for manual in rule.get('manual_rules') or []],
                'source': next((effect.get('source') for effect in rule_effects
                                if effect.get('source')), None),
                'modification_id': modification.get('modification_id'),
            })
    interior['normal_rooms'] = max(
        0, interior['rooms_total'] - interior['luxury_rooms'] - interior['complex_rooms'])
    interior['cargo_bays'] = sum(
        1 for module in cargo_modules if module.get('kind') == 'cargo_bay')
    interior['hidden_cargo_spaces'] = sum(
        int(module.get('cargo_spaces') or 0) for module in cargo_modules
        if str(module.get('kind') or '').startswith('hidden'))
    tech_maker = None
    for mod in _LATE['character_tech_maker_modifications'](character).values():
        if mod.get('host_instance_id') != host.get('instance_id'):
            continue
        effect = mod.get('effect')
        if not isinstance(effect, dict):
            continue
        if effect.get('target') == 'vehicle.sdp_max':
            effect['before'] = effective_sdp
            effective_sdp += int(effect.get('value') or 0)
            effect['after'] = effective_sdp
            tech_maker = copy.deepcopy(mod)
            sources.append({
                'id': f'tech-maker:{mod.get("modification_id")}',
                'label_en': mod.get('name') or 'Tech Maker Modification',
                'label_ru': mod.get('name') or 'Tech Maker Modification',
                'active': True, 'automated': True, 'effects': [copy.deepcopy(effect)],
                'manual_rules': [], 'source': mod.get('source'),
                'modification_id': mod.get('modification_id'),
            })
    effective = copy.deepcopy(base)
    effective.update({'sdp': effective_sdp, 'body_sp': effective_body_sp,
                      'glass_hp': effective_glass_hp, 'seats': effective_seats})
    state = copy.deepcopy((host.get('_vehicle_state') or {}))
    if not state:
        state = {'sdp_current': effective_sdp, 'sdp_max': effective_sdp}
    return {
        'instance_id': host.get('instance_id'),
        'base': {**base, 'sdp': base_sdp, 'body_sp': base_body_sp,
                 'glass_hp': base_glass_hp, 'seats': base_seats if base_seats is not None else base.get('seats')},
        'effective': effective, 'state': state, 'sources': sources,
        'nos_tanks': nos_tanks, 'mounted_weapons': mounted_weapons,
        'weapon_mounts': weapon_mounts, 'interior': interior,
        'cargo_modules': cargo_modules, 'tech_maker_modification': tech_maker,
    }


def character_effective_vehicles(character, modifications):
    owned = {item.get('instance_id'): item for item in character.get('inventory') or []
             if isinstance(item, dict) and item.get('instance_id')}
    states = character.get('vehicle_state') or {}
    modification_states = character.get('modification_state') or {}
    result = {}
    for host in (item for item in character.get('inventory') or []
                 if isinstance(item, dict) and item.get('cat') == 'vehicles'):
        copy_host = copy.deepcopy(host)
        copy_host['_vehicle_state'] = copy.deepcopy(states.get(host.get('instance_id')) or {})
        copy_host['_modification_state'] = copy.deepcopy(modification_states)
        host_modifications = [modification for modification in modifications
                              if modification.get('host_instance_id') == host.get('instance_id')]
        result[host['instance_id']] = evaluate_effective_vehicle(
            copy_host, host_modifications, owned, character, modifications)
    return result
