"""Каталог предметов и правила эффектов NC//NET (итерация P1-2).

Выделено из app/server.py: загрузка items.json/effects.json, валидация
эффектов, метаданные/пэйлоады предметов, профили кибердеков, дальности
оружия. Движок модификаций остаётся в server.py (следующая итерация —
после выноса inventory/tech-maker хелперов).

Обратные зависимости (SKILL_BY_NAME, catalog_item_id_for_entry) приходят
через bind() после загрузки server.py — до выделения домена rules.
"""
import copy
import json
import math
import os
import re
import sys

from core import (ACTIVE_EFFECT_DURATIONS, BASE, EFFECTS_PATH,
                  ITEM_INSTANCE_STATES, ITEMS_PATH, STATS)


_LATE = {}


def bind(**kwargs):
    """Подключить поздние зависимости (см. docstring модуля)."""
    _LATE.update(kwargs)


_catalog = None


def cyberdeck_item_metadata(item):
    """Return declarative host metadata for Cyberdecks, Hardware, and Programs."""
    if not isinstance(item, dict):
        return {}
    item_type = str((item.get('mechanics') or {}).get('type') or '')
    description = str(item.get('desc') or '')
    if item.get('cat') == 'net_stuff' and item_type == 'Cyberdeck Hardware':
        slots = re.search(r'Takes?\s+(\d+)\s+Hardware Option Slots?',
                          description, re.I)
        return {
            'host_type': 'cyberdeck', 'modification_kind': 'cyberdeck_hardware',
            'modification_group': None, 'slot_type': 'hardware',
            'grants_slots': {}, 'slots_used': int(slots.group(1)) if slots else 1,
            'compatibility_text': 'Cyberdeck Hardware',
            'permanent_installation': False,
            'unique_per_host': bool(re.search(
                r'Multiple installations do nothing', description, re.I)),
            'compatibility_manual': False,
            'installation_source': item.get('source'),
        }
    if item.get('cat') == 'programs':
        program_class = str((item.get('mechanics') or {}).get('program_class') or '')
        return {
            'host_type': 'cyberdeck', 'modification_kind': 'cyberdeck_program',
            'modification_group': None, 'slot_type': 'program',
            'grants_slots': {},
            'slots_used': 2 if 'Black ICE' in program_class else 1,
            'compatibility_text': program_class,
            'permanent_installation': False, 'unique_per_host': False,
            'compatibility_manual': False,
            'installation_source': item.get('source'),
        }
    return {}


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
    for item in _catalog.get('items') or []:
        item.update(cyberdeck_item_metadata(item))
        # Normalize exotic/multi-ammo magazine notation ("20 / 2",
        # "6 (Rubber Arrows)", "-") to the first integer so weapon_state
        # magazine_max does not collapse to 0. Raw text stays in `fields`.
        mechanics = item.get('mechanics')
        if isinstance(mechanics, dict) and 'magazine' in mechanics:
            mag = mechanics['magazine']
            if not isinstance(mag, int):
                match = re.search(r'\d+', str(mag))
                mechanics['magazine'] = int(match.group(0)) if match else 0
    _catalog['_by_id'] = {it['id']: it for it in _catalog['items']}
    return _catalog


def catalog():
    return load_catalog()


def item_by_id(iid):
    return catalog()['_by_id'].get(iid)


ITEM_INTERACTION_FIELDS = (
    'stackable', 'consumable', 'consume_amount', 'use_context', 'use_effect',
    'equippable', 'equip_modes', 'equip_slots', 'hands_required',
    'activation_required', 'active_actions', 'equip_limit', 'exclusive_group',
    'requires_host_type',
)
ITEM_MODIFICATION_FIELDS = (
    'host_type', 'modification_kind', 'modification_group', 'slot_type',
    'grants_slots', 'slots_used', 'compatibility_text',
    'permanent_installation', 'unique_per_host', 'compatibility_manual',
    'installation_source', 'availability_text', 'nomad_access_required',
    'repeatable_max', 'prerequisite_upgrades', 'prerequisite_host_names',
    'conflicting_upgrades',
)


def catalog_interaction_data(item):
    if not isinstance(item, dict):
        return {}
    return {key: copy.deepcopy(item[key]) for key in ITEM_INTERACTION_FIELDS if key in item}


def enrich_owned_item_interactions(data):
    """Refresh safe declarative interaction flags for legacy owned catalog items."""
    for bucket in ('inventory', 'cyberware'):
        for entry in data.get(bucket) or []:
            if not isinstance(entry, dict) or entry.get('is_custom'):
                continue
            item = item_by_id(_LATE['catalog_item_id_for_entry'](entry))
            if not item:
                continue
            for key in ITEM_INTERACTION_FIELDS + ITEM_MODIFICATION_FIELDS:
                if key in item:
                    entry[key] = copy.deepcopy(item[key])
                else:
                    entry.pop(key, None)
            coverage = item_effect_coverage(item.get('id'))
            if coverage:
                entry['effect_coverage'] = coverage
            else:
                entry.pop('effect_coverage', None)
    return data


_effect_rules = None
EFFECT_OPERATIONS = {'add', 'set', 'minimum', 'maximum', 'multiply'}
EFFECT_STACK_POLICIES = {'stack', 'highest', 'lowest', 'unique', 'replace'}


def effect_target_allowed(target):
    target = str(target or '')
    if target.startswith('character.stat.'):
        return target.removeprefix('character.stat.') in STATS
    if target.startswith('skill.') and target.endswith('.check'):
        return target[6:-6] in _LATE['SKILL_BY_NAME']
    return False


def validate_effect_definition(effect):
    allowed_keys = {
        'id', 'target', 'operation', 'value', 'stack_group', 'stack_policy',
        'priority', 'source', 'minimum_value',
    }
    if not isinstance(effect, dict) or set(effect) - allowed_keys:
        raise RuntimeError('Effect contains non-allowlisted fields')
    if not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(effect.get('id') or '')):
        raise RuntimeError('Invalid declarative effect id')
    if not effect_target_allowed(effect.get('target')):
        raise RuntimeError(f'Effect target is not allowlisted: {effect.get("target")}')
    if effect.get('operation') not in EFFECT_OPERATIONS:
        raise RuntimeError(f'Effect operation is not allowlisted: {effect.get("operation")}')
    value = effect.get('value')
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value) or abs(value) > 1000:
        raise RuntimeError('Effect value must be a finite bounded number')
    minimum_value = effect.get('minimum_value')
    if (minimum_value is not None and
            (not isinstance(minimum_value, (int, float)) or
             isinstance(minimum_value, bool) or not math.isfinite(minimum_value) or
             abs(minimum_value) > 1000)):
        raise RuntimeError('Effect minimum_value must be a finite bounded number')
    if effect.get('stack_policy', 'stack') not in EFFECT_STACK_POLICIES:
        raise RuntimeError('Invalid effect stack policy')
    if not isinstance(effect.get('priority', 100), int):
        raise RuntimeError('Effect priority must be an integer')


def load_effect_rules():
    global _effect_rules
    if _effect_rules is not None:
        return _effect_rules
    with open(EFFECTS_PATH, encoding='utf-8') as handle:
        payload = json.load(handle)
    rules = payload.get('synergy_rules')
    item_rules = payload.get('item_effect_rules') or []
    use_rules = payload.get('use_effect_rules') or []
    weapon_rules = payload.get('weapon_modification_rules') or []
    vehicle_rules = payload.get('vehicle_modification_rules') or []
    if (payload.get('version') != 1 or
            set(payload) - {'version', 'rules_version', 'synergy_rules',
                            'item_effect_rules', 'use_effect_rules',
                            'weapon_modification_rules', 'vehicle_modification_rules'} or
            not isinstance(rules, list) or len(rules) > 500 or
            not isinstance(item_rules, list) or len(item_rules) > 500 or
            not isinstance(use_rules, list) or len(use_rules) > 500 or
            not isinstance(weapon_rules, list) or len(weapon_rules) > 500 or
            not isinstance(vehicle_rules, list) or len(vehicle_rules) > 500):
        raise RuntimeError('Unsupported effects data format')
    seen = set()
    for rule in rules:
        if not isinstance(rule, dict) or set(rule) - {
                'id', 'label_en', 'label_ru', 'required_counts', 'required_all', 'effects'}:
            raise RuntimeError('Synergy rule contains non-allowlisted fields')
        rule_id = str(rule.get('id') or '')
        if not re.fullmatch(r'[a-z0-9_.-]{3,100}', rule_id) or rule_id in seen:
            raise RuntimeError('Invalid or duplicate synergy rule id')
        seen.add(rule_id)
        required_counts = rule.get('required_counts') or {}
        required_all = rule.get('required_all') or []
        if not isinstance(required_counts, dict) or not isinstance(required_all, list):
            raise RuntimeError(f'Invalid requirements in synergy {rule_id}')
        for requirement in required_counts.values():
            if (not isinstance(requirement, dict) or
                    set(requirement) - {'minimum', 'state', 'label'} or
                    requirement.get('state', 'installed') != 'installed' or
                    not isinstance(requirement.get('minimum', 1), int)):
                raise RuntimeError(f'Invalid count requirement in synergy {rule_id}')
        for requirement in required_all:
            if (not isinstance(requirement, dict) or
                    set(requirement) - {'catalog_id', 'state', 'label'} or
                    requirement.get('state', 'installed') != 'installed'):
                raise RuntimeError(f'Invalid all requirement in synergy {rule_id}')
        requirements = list(required_counts.keys()) + [
            item.get('catalog_id') for item in required_all]
        if not requirements or any(not item_by_id(item_id) for item_id in requirements):
            raise RuntimeError(f'Unknown catalog requirement in synergy {rule_id}')
        effects = rule.get('effects')
        if not isinstance(effects, list) or not effects:
            raise RuntimeError(f'Synergy {rule_id} has no effects')
        for effect in effects:
            validate_effect_definition(effect)
    for rule in item_rules:
        if not isinstance(rule, dict) or set(rule) - {
                'id', 'catalog_id', 'label_en', 'label_ru', 'active_when',
                'effects', 'manual_rules'}:
            raise RuntimeError('Item effect rule contains non-allowlisted fields')
        rule_id = str(rule.get('id') or '')
        if not re.fullmatch(r'[a-z0-9_.-]{3,100}', rule_id) or rule_id in seen:
            raise RuntimeError('Invalid or duplicate item effect rule id')
        seen.add(rule_id)
        if not item_by_id(rule.get('catalog_id')):
            raise RuntimeError(f'Unknown catalog item in effect rule {rule_id}')
        active_when = rule.get('active_when') or {}
        if (not isinstance(active_when, dict) or
                set(active_when) - {'state', 'active'} or
                active_when.get('state') not in ITEM_INSTANCE_STATES or
                ('active' in active_when and not isinstance(active_when['active'], bool))):
            raise RuntimeError(f'Invalid activation condition in item effect rule {rule_id}')
        effects = rule.get('effects') or []
        manual_rules = rule.get('manual_rules') or []
        if not isinstance(effects, list) or not isinstance(manual_rules, list) or not (effects or manual_rules):
            raise RuntimeError(f'Item effect rule {rule_id} has no effect or manual rule')
        for effect in effects:
            validate_effect_definition(effect)
        for manual in manual_rules:
            if (not isinstance(manual, dict) or
                    set(manual) - {'id', 'text_en', 'text_ru', 'condition', 'source'} or
                    not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(manual.get('id') or '')) or
                    not str(manual.get('text_en') or '').strip() or
                    not str(manual.get('text_ru') or '').strip()):
                raise RuntimeError(f'Invalid manual rule in item effect rule {rule_id}')
    for rule in use_rules:
        if not isinstance(rule, dict) or set(rule) - {
                'id', 'catalog_id', 'label_en', 'label_ru', 'duration_type',
                'duration_value', 'effects', 'manual_rules'}:
            raise RuntimeError('Use effect rule contains non-allowlisted fields')
        rule_id = str(rule.get('id') or '')
        if not re.fullmatch(r'[a-z0-9_.-]{3,100}', rule_id) or rule_id in seen:
            raise RuntimeError('Invalid or duplicate use effect rule id')
        seen.add(rule_id)
        item = item_by_id(rule.get('catalog_id'))
        if not item or not item.get('consumable'):
            raise RuntimeError(f'Unknown or non-consumable item in use effect rule {rule_id}')
        duration_type = rule.get('duration_type')
        duration_value = rule.get('duration_value')
        if (duration_type not in ACTIVE_EFFECT_DURATIONS or duration_type == 'manual' or
                not isinstance(duration_value, int) or duration_value < 1 or
                (duration_type == 'real_time' and duration_value > 10080) or
                (duration_type == 'rounds' and duration_value > 100) or
                (duration_type == 'campaign_time' and duration_value > 525600)):
            raise RuntimeError(f'Invalid duration in use effect rule {rule_id}')
        effects = rule.get('effects') or []
        manual_rules = rule.get('manual_rules') or []
        if not isinstance(effects, list) or not effects or not isinstance(manual_rules, list):
            raise RuntimeError(f'Use effect rule {rule_id} has no automated effect')
        for effect in effects:
            validate_effect_definition(effect)
        for manual in manual_rules:
            if (not isinstance(manual, dict) or
                    set(manual) - {'id', 'text_en', 'text_ru', 'condition', 'source'} or
                    not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(manual.get('id') or '')) or
                    not str(manual.get('text_en') or '').strip() or
                    not str(manual.get('text_ru') or '').strip()):
                raise RuntimeError(f'Invalid manual rule in use effect rule {rule_id}')
    for rule in weapon_rules:
        if not isinstance(rule, dict) or set(rule) - {
                'id', 'catalog_id', 'label_en', 'label_ru', 'requirements',
                'configuration', 'effects', 'manual_rules'}:
            raise RuntimeError('Weapon modification rule contains non-allowlisted fields')
        rule_id = str(rule.get('id') or '')
        if not re.fullmatch(r'[a-z0-9_.-]{3,100}', rule_id) or rule_id in seen:
            raise RuntimeError('Invalid or duplicate weapon modification rule id')
        seen.add(rule_id)
        item = item_by_id(rule.get('catalog_id'))
        if not item or item.get('cat') != 'gun_upgrades':
            raise RuntimeError(f'Unknown weapon upgrade in rule {rule_id}')
        requirements = rule.get('requirements') or {}
        if (not isinstance(requirements, dict) or
                set(requirements) - {'installed_any', 'label_en', 'label_ru'}):
            raise RuntimeError(f'Invalid requirements in weapon rule {rule_id}')
        installed_any = requirements.get('installed_any') or []
        if (not isinstance(installed_any, list) or
                any(not item_by_id(item_id) or item_by_id(item_id).get('cat') != 'cyberware'
                    for item_id in installed_any)):
            raise RuntimeError(f'Invalid installed requirement in weapon rule {rule_id}')
        configuration = rule.get('configuration')
        if configuration is not None:
            if (not isinstance(configuration, dict) or
                    set(configuration) - {'key', 'label_en', 'label_ru', 'required',
                                          'choices', 'choice_source'} or
                    not re.fullmatch(r'[a-z0-9_.-]{2,80}', str(configuration.get('key') or '')) or
                    not isinstance(configuration.get('required', False), bool) or
                    configuration.get('choice_source') not in (None, 'compatible_range_tables') or
                    (configuration.get('choice_source') is None and
                     (not isinstance(configuration.get('choices'), list) or
                      not configuration['choices']))):
                raise RuntimeError(f'Invalid configuration in weapon rule {rule_id}')
            choice_values = set()
            for choice in configuration.get('choices') or []:
                if (not isinstance(choice, dict) or
                        set(choice) - {'value', 'label_en', 'label_ru'} or
                        not re.fullmatch(r'[a-z0-9_.-]{1,80}', str(choice.get('value') or '')) or
                        not str(choice.get('label_en') or '').strip() or
                        not str(choice.get('label_ru') or '').strip() or
                        choice['value'] in choice_values):
                    raise RuntimeError(f'Invalid configuration choice in weapon rule {rule_id}')
                choice_values.add(choice['value'])
        effects = rule.get('effects') or []
        manual_rules = rule.get('manual_rules') or []
        if (not isinstance(effects, list) or not isinstance(manual_rules, list) or
                not (effects or manual_rules)):
            raise RuntimeError(f'Weapon modification rule {rule_id} has no effects or manual rule')
        for effect in effects:
            if (not isinstance(effect, dict) or
                    set(effect) - {'id', 'target', 'operation', 'value', 'values',
                                   'profile', 'profiles', 'configuration_key',
                                   'enhanced_when', 'enhanced_multiplier', 'source'} or
                    not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(effect.get('id') or '')) or
                    effect.get('target') not in {'weapon.magazine', 'weapon.concealable',
                                                 'weapon.attack_check',
                                                 'weapon.alternate_profile',
                                                 'weapon.autofire_profile',
                                                 'weapon.range_table',
                                                 'weapon.tag'}):
                raise RuntimeError(f'Invalid weapon effect in rule {rule_id}')
            if effect['target'] == 'weapon.magazine':
                values = effect.get('values')
                if (effect.get('operation') != 'set_by_weapon_type' or
                        not isinstance(values, dict) or not values or
                        any(not isinstance(key, str) or not isinstance(value, int) or
                            value < 1 or value > 999 for key, value in values.items())):
                    raise RuntimeError(f'Invalid magazine effect in rule {rule_id}')
            elif effect['target'] == 'weapon.concealable':
                if effect.get('operation') != 'set' or effect.get('value') not in ('YES', 'NO'):
                    raise RuntimeError(f'Invalid concealability effect in rule {rule_id}')
            elif effect['target'] == 'weapon.alternate_profile':
                profile = effect.get('profile')
                if (effect.get('operation') != 'grant' or not isinstance(profile, dict) or
                        set(profile) - {'id', 'label_en', 'label_ru', 'skill', 'damage',
                                        'rof', 'magazine', 'ammo_kind', 'hands_required'} or
                        not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(profile.get('id') or '')) or
                        profile.get('skill') not in _LATE['SKILL_BY_NAME'] or
                        not re.fullmatch(r'\d+d\d+', str(profile.get('damage') or '')) or
                        not isinstance(profile.get('rof'), int) or profile['rof'] < 1 or
                        not isinstance(profile.get('magazine'), int) or profile['magazine'] < 1 or
                        profile.get('ammo_kind') not in ('grenade', 'shotgun') or
                        profile.get('hands_required') != 2):
                    raise RuntimeError(f'Invalid alternate profile in rule {rule_id}')
            elif effect['target'] == 'weapon.autofire_profile':
                operation = effect.get('operation')
                profiles = ([effect.get('profile')] if operation == 'grant' else
                            list((effect.get('profiles') or {}).values()))
                if operation not in ('grant', 'configure') or not profiles:
                    raise RuntimeError(f'Invalid Autofire operation in rule {rule_id}')
                for profile in profiles:
                    if (not isinstance(profile, dict) or
                            set(profile) - {'id', 'label_en', 'label_ru', 'skill', 'table',
                                            'multiplier', 'ammo_cost', 'suppressive_fire'} or
                            not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(profile.get('id') or '')) or
                            profile.get('skill') != 'Autofire' or
                            profile.get('table') not in ('SMG', 'Machine Pistol') or
                            not isinstance(profile.get('multiplier'), int) or
                            not 1 <= profile['multiplier'] <= 4 or
                            profile.get('ammo_cost') != 10 or
                            not isinstance(profile.get('suppressive_fire'), bool)):
                        raise RuntimeError(f'Invalid Autofire profile in rule {rule_id}')
                if operation == 'configure':
                    configured = effect.get('profiles') or {}
                    config_key = effect.get('configuration_key')
                    choices = {choice['value'] for choice in (configuration or {}).get('choices', [])}
                    if (not configuration or config_key != configuration.get('key') or
                            set(configured) != choices):
                        raise RuntimeError(f'Invalid Autofire configuration in rule {rule_id}')
                enhanced_when = effect.get('enhanced_when') or []
                if (not isinstance(enhanced_when, list) or
                        set(enhanced_when) - {'excellent_quality', 'base_autofire'} or
                        ('enhanced_multiplier' in effect and
                         effect.get('enhanced_multiplier') not in (1, 2, 3, 4))):
                    raise RuntimeError(f'Invalid Autofire enhancement in rule {rule_id}')
            elif effect['target'] == 'weapon.range_table':
                if (effect.get('operation') != 'configure' or not configuration or
                        effect.get('configuration_key') != configuration.get('key') or
                        configuration.get('choice_source') != 'compatible_range_tables'):
                    raise RuntimeError(f'Invalid Range Table configuration in rule {rule_id}')
            elif effect['target'] == 'weapon.tag':
                if (effect.get('operation') != 'grant' or
                        effect.get('value') not in ('Power Weapon', 'Smart Weapon', 'Tech Weapon')):
                    raise RuntimeError(f'Invalid weapon tag in rule {rule_id}')
            elif (effect.get('operation') != 'add' or
                  not isinstance(effect.get('value'), (int, float)) or
                  abs(effect['value']) > 10):
                raise RuntimeError(f'Invalid attack effect in rule {rule_id}')
        for manual in manual_rules:
            if (not isinstance(manual, dict) or
                    set(manual) - {'id', 'text_en', 'text_ru', 'condition', 'source'} or
                    not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(manual.get('id') or '')) or
                    not str(manual.get('text_en') or '').strip() or
                    not str(manual.get('text_ru') or '').strip()):
                raise RuntimeError(f'Invalid manual rule in weapon rule {rule_id}')
    for rule in vehicle_rules:
        if not isinstance(rule, dict) or set(rule) - {
                'id', 'catalog_id', 'label_en', 'label_ru', 'effects', 'manual_rules'}:
            raise RuntimeError('Vehicle modification rule contains non-allowlisted fields')
        rule_id = str(rule.get('id') or '')
        if not re.fullmatch(r'[a-z0-9_.-]{3,100}', rule_id) or rule_id in seen:
            raise RuntimeError('Invalid or duplicate vehicle modification rule id')
        seen.add(rule_id)
        item = item_by_id(rule.get('catalog_id'))
        if not item or item.get('cat') != 'vehicles_upgrades':
            raise RuntimeError(f'Unknown vehicle upgrade in rule {rule_id}')
        effects = rule.get('effects') or []
        manual_rules = rule.get('manual_rules') or []
        if not isinstance(effects, list) or not effects or not isinstance(manual_rules, list):
            raise RuntimeError(f'Vehicle modification rule {rule_id} has no effects')
        for effect in effects:
            if (not isinstance(effect, dict) or
                    set(effect) - {'id', 'target', 'operation', 'value', 'values',
                                   'resource', 'profile', 'source'} or
                    not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(effect.get('id') or '')) or
                    effect.get('target') not in {'vehicle.sdp_max', 'vehicle.body_sp',
                                                 'vehicle.glass_hp', 'vehicle.seats',
                                                 'vehicle.nos_tank', 'vehicle.weapon_mount',
                                                 'vehicle.mounted_weapon', 'vehicle.interior',
                                                 'vehicle.room_upgrade', 'vehicle.cargo'}):
                raise RuntimeError(f'Invalid vehicle effect in rule {rule_id}')
            target, operation = effect['target'], effect.get('operation')
            if target == 'vehicle.glass_hp':
                values = effect.get('values')
                if (operation != 'set_by_count' or not isinstance(values, dict) or
                        set(values) != {'1', '2'} or
                        any(not isinstance(value, int) or value < 0 for value in values.values())):
                    raise RuntimeError(f'Invalid glass effect in rule {rule_id}')
            elif target in ('vehicle.body_sp',):
                if operation != 'set' or not isinstance(effect.get('value'), int):
                    raise RuntimeError(f'Invalid vehicle SP effect in rule {rule_id}')
            elif target == 'vehicle.nos_tank':
                resource = effect.get('resource')
                if (operation != 'grant' or not isinstance(resource, dict) or
                        set(resource) != {'id', 'label_en', 'label_ru', 'uses'} or
                        resource.get('id') != 'nos_tank' or
                        not str(resource.get('label_en') or '').strip() or
                        not str(resource.get('label_ru') or '').strip() or
                        resource.get('uses') != 1):
                    raise RuntimeError(f'Invalid NOS resource in rule {rule_id}')
            elif target == 'vehicle.weapon_mount':
                resource = effect.get('resource')
                if (operation != 'grant' or not isinstance(resource, dict) or
                        set(resource) != {'id', 'label_en', 'label_ru'} or
                        resource.get('id') != 'heavy_weapon_mount' or
                        not str(resource.get('label_en') or '').strip() or
                        not str(resource.get('label_ru') or '').strip()):
                    raise RuntimeError(f'Invalid heavy weapon mount resource in rule {rule_id}')
            elif target == 'vehicle.interior':
                profile = effect.get('profile')
                if (operation != 'grant' or not isinstance(profile, dict) or
                        set(profile) != {'id', 'kind', 'rooms', 'beds', 'amenities'} or
                        profile.get('id') != 'housing_capacity' or
                        profile.get('kind') != 'housing' or profile.get('rooms') != 1 or
                        profile.get('beds') != 1 or
                        profile.get('amenities') != ['toilet', 'shower', 'small_kitchen']):
                    raise RuntimeError(f'Invalid vehicle interior profile in rule {rule_id}')
            elif target == 'vehicle.room_upgrade':
                profile = effect.get('profile')
                if (operation != 'grant' or not isinstance(profile, dict) or
                        set(profile) - {'id', 'kind', 'purposes'} or
                        profile.get('kind') not in ('luxury', 'complex') or
                        profile.get('id') not in
                            ('luxury_vehicle_room', 'complex_vehicle_room')):
                    raise RuntimeError(f'Invalid vehicle room profile in rule {rule_id}')
                if (profile['kind'] == 'luxury' and
                        (profile['id'] != 'luxury_vehicle_room' or
                         set(profile) != {'id', 'kind'})):
                    raise RuntimeError(f'Invalid Luxury Room profile in rule {rule_id}')
                if (profile['kind'] == 'complex' and
                        profile['id'] != 'complex_vehicle_room'):
                    raise RuntimeError(f'Invalid Complex Room profile in rule {rule_id}')
                purposes = profile.get('purposes')
                allowed_purposes = {
                    'cargo_bay', 'bunkhouse', 'cafeteria', 'restaurant',
                    'recreation_deck', 'prison', 'bowling_alley',
                    'laser_tag_arena', 'other_complex',
                }
                if (profile['kind'] == 'complex' and
                        (not isinstance(purposes, list) or not purposes or
                         len(set(purposes)) != len(purposes) or
                         set(purposes) - allowed_purposes)):
                    raise RuntimeError(f'Invalid Complex Room purposes in rule {rule_id}')
            elif target == 'vehicle.cargo':
                profile = effect.get('profile')
                if (operation != 'grant' or not isinstance(profile, dict) or
                        set(profile) != {'id', 'kind', 'cargo_spaces',
                                        'hidden_holsters', 'discovery_dv'} or
                        (profile.get('id'), profile.get('kind'),
                         profile.get('hidden_holsters')) not in {
                            ('smuggling_upgrade', 'hidden', 2),
                            ('bicycle_smuggling_compartment', 'hidden_small', 0)} or
                        profile.get('cargo_spaces') != 1 or
                        profile.get('discovery_dv') != 17):
                    raise RuntimeError(f'Invalid vehicle cargo profile in rule {rule_id}')
            elif target == 'vehicle.mounted_weapon':
                profile = effect.get('profile')
                profile_keys = {
                    'id', 'label_en', 'label_ru', 'kind', 'skill', 'weapon_type',
                    'range_table', 'damage', 'rof', 'magazine', 'ammo_kind',
                    'ammo_cost', 'orientations', 'operator', 'autofire_multiplier',
                    'suppressive_fire',
                }
                if (operation != 'grant' or not isinstance(profile, dict) or
                        set(profile) - profile_keys or
                        not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(profile.get('id') or '')) or
                        not str(profile.get('label_en') or '').strip() or
                        not str(profile.get('label_ru') or '').strip() or
                        profile.get('kind') not in ('standard', 'autofire') or
                        profile.get('skill') not in _LATE['SKILL_BY_NAME'] or
                        profile.get('range_table') not in
                            ('Shotgun', 'Assault Rifle', 'Rocket Launcher') or
                        not isinstance(profile.get('rof'), int) or profile['rof'] != 1 or
                        not isinstance(profile.get('magazine'), int) or
                            not 1 <= profile['magazine'] <= 100 or
                        profile.get('ammo_kind') not in
                            ('incendiary_shotgun', 'rifle', 'rocket') or
                        not isinstance(profile.get('ammo_cost'), int) or
                            not 1 <= profile['ammo_cost'] <= profile['magazine'] or
                        not isinstance(profile.get('orientations'), list) or
                        not profile['orientations'] or
                        len(set(profile['orientations'])) != len(profile['orientations']) or
                        set(profile['orientations']) - {'front', 'side', 'rear'} or
                        profile.get('operator') != 'driver' or
                        not isinstance(profile.get('suppressive_fire'), bool)):
                    raise RuntimeError(f'Invalid mounted weapon profile in rule {rule_id}')
                if profile['kind'] == 'standard':
                    if (not re.fullmatch(r'\d+d\d+', str(profile.get('damage') or '')) or
                            'autofire_multiplier' in profile or profile['ammo_cost'] != 1):
                        raise RuntimeError(f'Invalid standard mounted weapon in rule {rule_id}')
                elif (profile.get('skill') != 'Autofire' or 'damage' in profile or
                      profile.get('autofire_multiplier') != 4 or
                      profile['ammo_cost'] != 10 or not profile['suppressive_fire']):
                    raise RuntimeError(f'Invalid Autofire mounted weapon in rule {rule_id}')
            elif operation != 'add' or not isinstance(effect.get('value'), int):
                raise RuntimeError(f'Invalid additive vehicle effect in rule {rule_id}')
        for manual in manual_rules:
            if (not isinstance(manual, dict) or
                    set(manual) - {'id', 'text_en', 'text_ru', 'condition', 'source'} or
                    not re.fullmatch(r'[a-z0-9_.-]{3,100}', str(manual.get('id') or '')) or
                    not str(manual.get('text_en') or '').strip() or
                    not str(manual.get('text_ru') or '').strip()):
                raise RuntimeError(f'Invalid manual rule in vehicle rule {rule_id}')
    _effect_rules = payload
    return payload


def item_effect_coverage(catalog_id):
    payload = load_effect_rules()
    rules = [
        ('state', rule) for rule in payload.get('item_effect_rules') or []
        if rule.get('catalog_id') == catalog_id]
    rules += [
        ('use', rule) for rule in payload.get('use_effect_rules') or []
        if rule.get('catalog_id') == catalog_id]
    rules += [
        ('modification', rule) for rule in payload.get('weapon_modification_rules') or []
        if rule.get('catalog_id') == catalog_id]
    rules += [
        ('modification', rule) for rule in payload.get('vehicle_modification_rules') or []
        if rule.get('catalog_id') == catalog_id]
    catalog_item = item_by_id(catalog_id) or {}
    if catalog_item.get('grants_slots'):
        rules.append(('modification', {
            'id': f'{catalog_id}-slot-grant', 'label_en': catalog_item.get('name'),
            'label_ru': catalog_item.get('name'),
            'effects': [{'source': catalog_item.get('installation_source')}],
            'manual_rules': [],
        }))
    if not rules:
        return None
    return {
        'automated': any(rule.get('effects') for _, rule in rules),
        'manual': any(rule.get('manual_rules') for _, rule in rules),
        'rules': [{
            'id': rule['id'], 'kind': kind,
            'label_en': rule.get('label_en') or rule['id'],
            'label_ru': rule.get('label_ru') or rule.get('label_en') or rule['id'],
            'source': next((effect.get('source') for effect in rule.get('effects') or []
                            if effect.get('source')), None) or
                      next((manual.get('source') for manual in rule.get('manual_rules') or []
                            if manual.get('source')), None),
        } for kind, rule in rules],
    }


def catalog_item_payload(item):
    payload = copy.deepcopy(item)
    coverage = item_effect_coverage(item.get('id'))
    if coverage:
        payload['effect_coverage'] = coverage
    return payload


def weapon_modification_rules_for_catalog(catalog_id):
    return [copy.deepcopy(rule) for rule in
            load_effect_rules().get('weapon_modification_rules') or []
            if rule.get('catalog_id') == catalog_id]


def vehicle_modification_rules_for_catalog(catalog_id):
    return [copy.deepcopy(rule) for rule in
            load_effect_rules().get('vehicle_modification_rules') or []
            if rule.get('catalog_id') == catalog_id]


CYBERDECK_PROFILES = {
    'net_stuff-0': {'mixed': 5},
    'net_stuff-1': {'mixed': 7},
    'net_stuff-2': {'mixed': 9},
    'net_stuff-3': {'mixed': 5},
    'net_stuff-4': {'program': 5},
    'net_stuff-5': {'program': 5},
    'net_stuff-6': {'program': 4, 'hardware': 5},
    'net_stuff-7': {'mixed': 5},
    'net_stuff-8': {'program': 7},
    'net_stuff-9': {'hardware': 2},
    'net_stuff-10': {'program': 7},
    'net_stuff-11': {'mixed': 6},
    'net_stuff-12': {'program': 6, 'hardware': 5},
    'net_stuff-13': {'program': 9},
    'net_stuff-14': {'mixed': 9},
    'net_stuff-15': {'flak': 3, 'mixed': 6},
    'net_stuff-16': {'mixed': 9},
    'net_stuff-17': {'program': 3, 'hardware': 6},
}


WEAPON_RANGE_FAMILIES = {
    'pistol': ['Snubnose Pistol', 'Pistol', 'Long Barrel Pistol'],
    'smg': ['Subcompact SMG', 'SMG'],
    'shotgun': ['Short Barrel Shotgun', 'Shotgun', 'Long Barrel Shotgun'],
    'rifle': ['Carbine', 'Assault Rifle', 'Battle Rifle', 'Marksman Rifle',
              'Scout Rifle', 'Sniper Rifle', 'Anti-materiel Rifle'],
    'bow': ['Shortbow', 'Bow', 'Longbow'],
    'grenade_launcher': ['Grenade Launcher'],
    'rocket_launcher': ['Rocket Launcher', 'Missile Launcher'],
}


def weapon_range_table_info(host):
    weapon_type = str((host.get('mechanics') or {}).get('type') or '')
    low = weapon_type.lower()
    if 'pistol' in low:
        family, base = 'pistol', 'Pistol'
    elif 'smg' in low:
        family, base = 'smg', 'SMG'
    elif 'shotgun' in low:
        family, base = 'shotgun', 'Shotgun'
    elif any(token in low for token in ('rifle', 'carbine')):
        family = 'rifle'
        base = weapon_type if weapon_type in WEAPON_RANGE_FAMILIES[family] else 'Assault Rifle'
    elif 'bow' in low:
        family, base = 'bow', 'Bow'
    elif 'grenade launcher' in low:
        family, base = 'grenade_launcher', 'Grenade Launcher'
    elif 'rocket launcher' in low or 'missile launcher' in low:
        family = 'rocket_launcher'
        base = 'Missile Launcher' if 'missile' in low else 'Rocket Launcher'
    else:
        return {'family': None, 'base': None, 'choices': []}
    available_rows = {str(row[0]) for row in (catalog().get('range_table') or [])[1:] if row}
    choices = [name for name in WEAPON_RANGE_FAMILIES[family]
               if name in available_rows and name != base]
    return {'family': family, 'base': base, 'choices': choices}
