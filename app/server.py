#!/usr/bin/env python3
"""CBPR Helper — онлайн-помощник для кампаний по Cyberpunk RED.

Только стандартная библиотека Python. Запуск:
    python3 app/server.py [--port 8000]
"""
import argparse
import base64
import copy
import functools
import hashlib
import hmac
import ipaddress
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

if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (ACCOUNT_ROLES, ACTIVE_EFFECT_DURATIONS, BASE,         # noqa: E402
                  BACKUP_DIR, CHARACTER_VISIBILITY_DEFAULTS, DATA_DIR, DB_PATH,
                  EFFECTS_PATH, INSTANCE_ID_RE, ITEM_INSTANCE_STATES, ITEMS_PATH,
                  SESSION_TTL, STATS, UPLOAD_DIR,
                  ApiError, _row_value,
                  can_edit_contract, can_edit_storyline, can_manage_persona,
                  ensure_character_visibility, parse_json_object,
                  MOSCOW, user_account_role, user_is_admin, user_is_gm)
import db as _db_mod                                                        # noqa: E402
from db import (                                                            # noqa: E402
    enforce_rate_limit,
    _failed_login_bucket,
    account_login_locked,
    record_failed_login,
    clear_failed_logins,
    configured_admin_usernames,
    backup_tools_module,
    backup_retention,
    backup_database,
    ensure_column,
    cyberdeck_profile_for_host,
    cyberdeck_program_category,
    cyberdeck_slot_usage,
    cyberdeck_item_compatibility,
    queue_defense_sequencer_trigger,
    resolve_defense_sequencer_trigger,
    initial_program_runtime_state,
    black_ice_effect_profile,
    instantiate_black_ice_stat_effects,
    roll_dice,
    black_ice_target_type,
    active_black_ice_entity,
    initial_black_ice_entity,
    evaluate_effective_cyberdeck,
    character_effective_cyberdecks,
    vehicle_classification,
    vehicle_repair_severity,
    vehicle_repair_skill,
    character_nomad_rank,
    vehicle_interior_capacity_for_compatibility,
    vehicle_upgrade_compatibility,
    validate_active_modification_references,
    sync_weapon_states_with_modifications,
    sync_vehicle_states_with_modifications,
    backfill_character_item_instances,
    apply_schema_migrations,
    apply_admin_bootstrap,
    parse_json_list,
    clean_location_id,
    optional_timestamp,
    session_view_config,
    session_safety_config,
    session_net_state,
    character_interface_rank,
    net_actions_for_interface,
    session_net_path_between,
    clean_npc_template_input,
    clean_npc_statblock,
    npc_statblock_derived,
    SCHEMA,
    NETWORK_SCHEMA,
    FEED_SCHEMA,
    OPERATIONS_SCHEMA,
    ITEM_INSTANCE_SCHEMA,
    ACTIVE_EFFECT_SCHEMA,
    ITEM_MODIFICATION_SCHEMA,
    CAMPAIGN_CLOCK_SCHEMA,
    CREW_STASH_SCHEMA,
    MARKET_STOCK_SCHEMA,
    MARKET_PERMANENT_SCHEMA,
    ORGANIZATION_SCHEMA,
    SESSION_RECAP_SCHEMA,
    LOCATION_SCHEMA,
    MEMORIAL_SCHEMA,
    NOTIFICATION_SCHEMA,
    MIGRATION_ACCOUNT_ROLES,
    MIGRATION_NETWORK_CORE,
    MIGRATION_CITY_FEED,
    MIGRATION_OPERATIONS,
    MIGRATION_NOTIFICATIONS,
    MIGRATION_TACTICAL_PROFILES,
    MIGRATION_ITEM_INSTANCES,
    MIGRATION_ACTIVE_EFFECTS,
    MIGRATION_EFFECT_PRESETS,
    MIGRATION_ITEM_MODIFICATIONS,
    MIGRATION_SESSION_NET,
    MIGRATION_CAMPAIGN_CLOCK,
    MIGRATION_CREW_STASH,
    MIGRATION_MARKET_STOCK,
    MIGRATION_NPC_STATBLOCKS,
    MIGRATION_SESSION_RECAPS,
    MIGRATION_LOCATIONS,
    MIGRATION_MEMORIAL,
    MIGRATION_MEMORIAL_DRAFT,
    MIGRATION_MARKET_PERMANENT,
    MIGRATION_ORGANIZATIONS,
    DB_BACKUP_LIMIT,
    _RATE_LIMIT_BUCKETS,
    _RATE_LIMIT_LOCK,
    FAILED_LOGIN_LIMIT,
    FAILED_LOGIN_WINDOW,
    PROGRAM_RUNTIME_STATUSES,
    NET_ENTITY_STATUSES,
    BLACK_ICE_ANTI_PROGRAM_DAMAGE,
    ATTACKER_PROGRAM_BLACK_ICE_DAMAGE,
    BLACK_ICE_STAT_EFFECT_TARGETS,
    VEHICLE_REPAIR_RULES,
    PERSONA_ACCESS,
    PERSONA_KINDS,
    PERSONA_STATUSES,
    STORYLINE_STATUSES,
    CONTRACT_STATUSES,
    CONTRACT_REWARD_MODES,
    CONTRACT_RISKS,
    NC_LOCATION_IDS,
    FEED_FORMATS,
    FEED_DEFAULT_FORMAT,
    FEED_TRUTH,
    SESSION_VIEW_DEFAULTS,
    SESSION_ACCESS_ROLES,
    SESSION_ROLE_CAPABILITIES,
    SESSION_SAFETY_DEFAULTS,
    SAFETY_SIGNAL_KINDS,
    SAFETY_SIGNAL_STATUSES,
    SESSION_NET_NODE_TYPES,
    SESSION_NET_PATH_DIRECTIONS,
    NPC_STAT_MAX,
    NPC_SKILL_MAX,
)
import recap as _recap_mod                                                # noqa: E402
from recap import (                                                       # noqa: E402
    _clean_recap_text_list,
    _clean_recap_participants,
    clean_session_recap_input,
    recap_participants,
    recap_public_payload,
    session_recap_payload,
    ensure_system_persona,
    migrate_legacy_network_content,
    assign_account_role,
    persona_payload,
    has_contract_classified_access,
    clean_persona_input,
    record_persona_audit,
    record_feed_revision,
    record_character_changes,
    readable_change_value,
    character_change_summary,
    record_character_change_set,
    record_effect_change,
    record_account_security,
    add_notification,
    queue_vk_event,
    vk_public_contract_message,
    deliver_vk_outbox,
    RECAP_TEXT_LIST_LIMIT,
    CHARACTER_DIFF_SCALARS,
)
import campaign as _camp_mod                                              # noqa: E402
from campaign import (                                                    # noqa: E402
    campaign_timezone,
    ensure_campaign_clock,
    campaign_now,
    campaign_time_label,
    campaign_duration_seconds,
    campaign_clock_payload,
    campaign_service_status,
    character_campaign_services,
    campaign_pending_services,
    clean_downtime_activity,
    clean_downtime_activities,
    downtime_state,
    downtime_activity_payload,
    downtime_payload,
    CAMPAIGN_CLOCK_TZ,
    CAMPAIGN_DURATION_SECONDS,
    CAMPAIGN_DURATION_LABELS,
    DOWNTIME_ACTIVITIES,
    DOWNTIME_ACTIVITY_BY_ID,
    DOWNTIME_ACTIVITY_IDS,
    DOWNTIME_RESOLVE_KINDS,
)
import locations as _loc_mod                                              # noqa: E402
from locations import (                                                   # noqa: E402
    ensure_seed_locations,
    clean_location_input,
    location_payload,
    LOCATION_KINDS,
    NC_SEED_LOCATIONS,
)
import memorial as _memorial_mod                                          # noqa: E402
from memorial import (                                                    # noqa: E402
    membership_payload,
    crew_reputation_map,
    clean_membership_input,
    clean_reputation_input,
    clean_memorial_input,
    clean_legacy_input,
    memorial_payload,
    MEMORIAL_STATUSES,
    MEMORIAL_VISIBILITIES,
    MEMBERSHIP_STATUSES,
    MEMBERSHIP_VISIBILITIES,
    REPUTATION_STANDINGS,
)
import crew as _crew_mod                                                  # noqa: E402
from crew import (                                                        # noqa: E402
    crew_stash_payload,
    item_transfer_history,
    character_open_loans,
    active_loan_for_instance,
    transfer_targets,
    _inventory_entry,
    _character_item_name,
    _transferable_item_error,
    _detach_runtime_state,
    _attach_runtime_state,
    _detach_tech_maker_modifications,
    _attach_tech_maker_modifications,
    _split_stack,
    _prepare_entry_for_holder,
    _record_item_transfer,
    _record_transfer_ledger,
    _persist_transfer_side,
    db,
    init_db,
    TRANSFER_KINDS,
    _RUNTIME_STATE_KEYS,
)
import night_market as _market_mod                                        # noqa: E402
from night_market import (                                                 # noqa: E402
    PERMANENT_SUPPLY,
    NM_PER_CAT,
    NM_MULTS,
    NIGHT_MARKET_VENDORS,
    _h,
    nm_day,
    nm_day_offset,
    nm_stock_seed,
    permanent_offer_payload,
    ensure_market_permanent,
    market_permanent_rows,
    permanent_offers,
    nm_offer_payload,
    nm_rotation,
    market_stock_rows,
    ensure_market_stock,
    night_market,
    nm_price_map,
)
import inventory as _inventory_mod                                        # noqa: E402
from inventory import (                                                    # noqa: E402
    new_item_instance_id,
    catalog_item_id_for_entry,
    item_entry_stackable,
    ensure_character_item_instances,
    persist_character_item_instances,
    item_modification_payload,
    character_modifications,
    weapon_is_exotic,
    weapon_slot_capacity,
    weapon_upgrade_compatibility,
    ITEM_INSTANCE_BUCKETS,
)
import charbuild as _charbuild_mod                                        # noqa: E402
from charbuild import (                                                    # noqa: E402
    public_character_data,
    character_author_payload,
    clean_character_profile_patch,
    clean_character,
    clean_item_acquisition,
    trust_number,
    clean_custom_effect,
    canonical_owned_entry,
    clean_character_trust_update,
    canonical_import_character,
    skill_base,
    creation_skill_cost,
    armor_shield_hp,
    effective_armor_hosts,
    validate_armor_tech_references,
    validate_armor_repair_references,
    tech_maker_fabricable_item,
    tech_maker_host_type,
    character_maker_ranks,
    clean_tech_maker_effect,
    character_tech_maker_modifications,
    validate_tech_maker_references,
    tech_maker_payload,
    cyberware_weapon_profile,
    popup_weapon_binding_kind,
    popup_shield_profile,
    validate_popup_shield_references,
    popup_weapon_binding_compatibility,
    bound_popup_weapon_profile,
    cyberware_curated_payload,
    cyberware_is_installed,
    cyberware_is_paired_leg_foundation,
    cyberware_secondary_host_id,
    cyberware_capacity,
    cyberware_host_assignments,
    cyberware_host_kind,
    cyberware_installation_profile,
    cyberware_side_required,
    validate_cyberware_sides,
    validate_cyberware_payload_conflicts,
    effective_cyberware_loadout,
    cyberware_option_compatibility,
    validate_bound_popup_weapon_references,
    validate_cyberware_trust_lifecycle,
    validate_cyberware_requirements,
    validate_cyberware_slots,
    validate_role_benefits,
    validate_creation_equipment,
    validate_creation_budget,
    validate_role_rank_setup,
    validate_creation,
    MAX_CHAR_BYTES,
    CHARACTER_PROFILE_FIELDS,
    TRUST_EDIT_TEXT_LIMITS,
    ITEM_ACQUISITION_SOURCES,
    IMPORT_STRIP_KEYS,
    TECH_MAKER_SPECIALTIES,
    TECH_MAKER_FABRICATION_SPECIALTIES,
    TECH_MAKER_EFFECT_TARGETS,
    TECH_MAKER_SPECIALTY_LABELS,
    TECH_MAKER_FABRICABLE_CATS,
    CYBERWARE_HOST_ACCEPTED_NAMES,
    CYBERWARE_SIDED_HOST_KINDS,
    CYBERWARE_INSTALLATION_SITES,
    THERAPY_PROFILES,
    CYBERWARE_CURATED_PAYLOADS,
    CYBERWARE_WEAPON_PROFILES,
)
import mod_engine as _engine_mod                                          # noqa: E402
from mod_engine import (                                                   # noqa: E402
    weapon_modification_configuration_schema,
    clean_weapon_modification_choices,
    weapon_profiles_from_rules,
    ammo_kind_for_modification_profile,
    ammo_pack_size,
    ammo_rounds,
    ensure_shared_ammo_state,
    ammo_matches_requirement,
    shared_ammo_available,
    consume_shared_ammo,
    clear_loaded_ammo_if_empty,
    vehicle_action_effects_from_rules,
    vehicle_modification_configuration_schema,
    clean_vehicle_modification_choices,
    initial_vehicle_modification_state,
    normalize_vehicle_modification_state,
    evaluate_effective_weapon,
    character_effective_weapons,
    vehicle_base_interior,
    bound_vehicle_weapon_profile,
    evaluate_effective_vehicle,
    character_effective_vehicles,
    VEHICLE_COMPLEX_PURPOSE_LABELS,
)
import rules as _rules_mod                                                 # noqa: E402
from rules import (                                                        # noqa: E402
    _armor_penalties,
    resolve_modifier_stack,
    apply_modifier_pipeline,
    effect_runtime_status,
    effect_instance_payload,
    character_effect_instances,
    instantiate_consumable_effects,
    evaluate_character_effects,
    derive,
    _num,
    GENERAL_DV,
    RULE_SOURCES,
    ROLES,
    ROLE_RU,
    ROLE_DESC,
    ROLE_DESC_EN,
    SKILLS,
    SKILL_BY_NAME,
    STAT_POINTS,
    SKILL_POINTS,
    SKILL_MAX_CREATION,
    MUST_SKILLS,
    SPECIALIZED_SKILLS,
    START_CASH_GEAR,
    START_CASH_FASHION,
    CULTURAL_LANGUAGES,
    WOUND_STATES,
    CRIT_BODY,
    CRIT_HEAD,
    WOUND_STATES_EN,
    CRIT_BODY_EN,
    CRIT_HEAD_EN,
    CUSTOM_EFFECT_DURATIONS,
    ACTIVE_EFFECT_ACTIONS,
)
import catalog as _catalog_mod                                           # noqa: E402
from catalog import (                                                    # noqa: E402
    cyberdeck_item_metadata,
    load_catalog,
    catalog,
    item_by_id,
    catalog_interaction_data,
    enrich_owned_item_interactions,
    effect_target_allowed,
    validate_effect_definition,
    load_effect_rules,
    item_effect_coverage,
    catalog_item_payload,
    weapon_modification_rules_for_catalog,
    vehicle_modification_rules_for_catalog,
    weapon_range_table_info,
    _catalog,
    ITEM_INTERACTION_FIELDS,
    ITEM_MODIFICATION_FIELDS,
    _effect_rules,
    EFFECT_OPERATIONS,
    EFFECT_STACK_POLICIES,
    CYBERDECK_PROFILES,
    WEAPON_RANGE_FAMILIES,
)
from media import (MEDIA_KINDS, MEDIA_LIMIT, MediaHandlers,                   # noqa: E402
                   attach_character_media, image_info, media_payload)

STATIC_DIR = os.path.join(BASE, 'static')
# ITEMS_PATH / EFFECTS_PATH теперь живут в core.py (итерация P1-2)
PBKDF_ITERS = 120_000


def security_headers():
    """Defense-in-depth response headers.

    CSP is deliberately lenient on script/style ('unsafe-inline') because the
    SPA builds UI with innerHTML + inline event handlers, but still hardens
    object-src/base-uri/connect-src/frame-ancestors. Override the whole policy
    with CBPR_CSP (empty value disables the header).
    """
    csp = os.environ.get('CBPR_CSP')
    if csp is None:
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; base-uri 'self'; "
            "frame-ancestors 'self'; form-action 'self'"
        )
    pairs = [
        ('X-Content-Type-Options', 'nosniff'),
        ('X-Frame-Options', 'SAMEORIGIN'),
        ('Referrer-Policy', 'strict-origin-when-cross-origin'),
    ]
    if csp:
        pairs.append(('Content-Security-Policy', csp))
    return pairs









# ---------------------------------------------------------------- auth

REGISTRATION_MODES = {'open', 'invite', 'closed'}


def registration_mode():
    mode = str(os.environ.get('CBPR_REGISTRATION_MODE', 'invite') or '').strip().lower()
    return mode if mode in REGISTRATION_MODES else 'invite'


def invite_code_hash(code):
    normalized = re.sub(r'[^A-Za-z0-9]', '', str(code or '')).upper()
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else ''


def create_invite_code():
    raw = secrets.token_hex(8).upper()
    return f'NCNET-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}'


def validate_new_password(password):
    if len(password) < 8:
        raise ApiError(400, 'Пароль: минимум 8 символов')
    if len(password) > 256:
        raise ApiError(400, 'Пароль слишком длинный')


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


def create_session(conn, user_id, ip_address='', user_agent=''):
    token = secrets.token_hex(32)
    now = time.time()
    conn.execute(
        'INSERT INTO sessions(token,user_id,created,expires,last_seen,ip_address,user_agent) '
        'VALUES(?,?,?,?,?,?,?)',
        (token, user_id, now, now + SESSION_TTL, now,
         str(ip_address or '')[:64], str(user_agent or '')[:300]))
    conn.execute('DELETE FROM sessions WHERE expires < ?', (now,))
    conn.commit()
    return token



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
        data['primary_role'] = str(primary.get('name') or data.get('primary_role') or '')
        data['role'] = data['primary_role']
        data['role_rank'] = _num(primary.get('rank')) or _num(data.get('role_rank')) or 4
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
    for weapon in [item for item in inventory if item.get('cat') in ('guns','melee')]:
        key = str(weapon.get('instance_id') or weapon.get('key') or
                  weapon.get('source_key') or weapon.get('name'))
        magazine = _num((weapon.get('mechanics') or {}).get('magazine')) or 0
        if key not in states:
            states[key] = {'magazine': magazine, 'magazine_max': magazine, 'reserve': 0}
    ensure_shared_ammo_state(data)
    if not isinstance(data.get('program_state'), dict):
        data['program_state'] = {}
    if not isinstance(data.get('net_entities'), dict):
        data['net_entities'] = {}
    data['schema_version'] = max(8, _num(data.get('schema_version')) or 0)
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
    'Покупка доступна только из текущего Night Market': 'Purchases are only available from the current Night Market stock',
    'Инвентарь не может содержать больше 500 экземпляров': 'Inventory cannot contain more than 500 item instances',
    'Некорректное количество': 'Invalid quantity',
    'Сначала снимите или извлеките предмет': 'Unequip or uninstall the item first',
    'Inventory должен содержать объекты': 'Inventory entries must be objects',
    'Некорректное состояние предмета': 'Invalid item state',
    'У персонажа не может быть двух одинаковых Roles': 'A character cannot have duplicate Roles',
    'Custom items будут добавлены отдельным этапом; выберите предмет из Database': 'Custom items will be added in a later stage; choose an item from the Database',
    'Предмет находится в неправильном разделе Inventory': 'The item is in the wrong Inventory section',
    'skills должен быть объектом до 500 записей': 'skills must be an object with no more than 500 entries',
    'armor должен быть объектом': 'armor must be an object',
    'Укажите причину изменения Character Sheet': 'Provide a reason for the Character Sheet change',
    'В Character Sheet нет изменений': 'There are no Character Sheet changes',
    'Изменение Character Sheet не найдено': 'Character Sheet change not found',
    'Откат доступен только до следующего изменения Dossier': 'Revert is only available before the next Dossier change',
    'Snapshot для отката повреждён': 'The revert snapshot is corrupted',
    'Некорректный источник получения предмета': 'Invalid item acquisition source',
    'Custom Cyberware требует отдельной механики установки': 'Custom Cyberware requires a dedicated installation system',
    'Custom item требует название': 'Custom item name is required',
    'Некорректная категория custom item': 'Invalid custom item category',
    'stackable должен быть логическим значением': 'stackable must be boolean',
    'Неизвестный предмет: выберите Database item или создайте Custom item': 'Unknown item: choose a Database item or create a Custom item',
    'Этот предмет нельзя экипировать': 'This item cannot be equipped',
    'Используйте действие Equip в Character Sheet': 'Use the Equip action in the Character Sheet',
    'Экземпляр предмета не найден': 'Item instance not found',
    'Этот предмет не является расходником': 'This item is not consumable',
    'Расходник должен быть исправен и находиться при персонаже': 'The consumable must be functional and carried by the character',
    'Недостаточно единиц расходника': 'Not enough consumable units',
    'Экипировать можно только carried предмет': 'Only a carried item can be equipped',
    'Недопустимый режим экипировки': 'Invalid equip mode',
    'Недостаточно свободных рук для экипировки': 'Not enough free hands to equip this item',
    'Недопустимый слот экипировки': 'Invalid equipment slot',
    'Достигнут лимит экипированных копий': 'Equipped copy limit reached',
    'Предмет не экипирован': 'The item is not equipped',
    'Неизвестное действие с предметом': 'Unknown item action',
    'Предмет не поддерживает включение и выключение': 'The item cannot be activated or deactivated',
    'Сначала экипируйте предмет': 'Equip the item first',
    'Предмет уже находится в выбранном состоянии': 'The item is already in the requested state',
    'Effect должен быть объектом': 'Effect must be an object',
    'Effect содержит неподдерживаемые поля': 'Effect contains unsupported fields',
    'Укажите название эффекта': 'Effect name is required',
    'Укажите причину эффекта': 'Effect reason is required',
    'Effect value должен быть от -100 до 100': 'Effect value must be between -100 and 100',
    'Multiply effect должен быть от 0 до 10': 'Multiply effect must be between 0 and 10',
    'Некорректная stacking group': 'Invalid stacking group',
    'Некорректный тип длительности эффекта': 'Invalid effect duration type',
    'Effect value должен быть числом': 'Effect value must be numeric',
    'Effect action содержит неподдерживаемые поля': 'Effect action contains unsupported fields',
    'Effect instance не найден': 'Effect instance not found',
    'Effect instance уже архивирован': 'Effect instance is already archived',
    'Неизвестное действие с эффектом': 'Unknown effect action',
    'Эффект уже отключён': 'Effect is already disabled',
    'Истёкший real-time эффект нельзя включить повторно': 'An expired real-time effect cannot be enabled again',
    'Завершённый round effect нельзя включить повторно': 'A completed round effect cannot be enabled again',
    'Эффект уже включён': 'Effect is already enabled',
    'Tick доступен только для round effect': 'Tick is only available for round effects',
    'Round effect сейчас не активен': 'Round effect is not currently active',
    'Сначала снимите установленные модификации': 'Remove installed modifications first',
    'Повреждена связь установленной модификации': 'Installed modification link is corrupted',
    'Modification содержит неподдерживаемые поля': 'Modification contains unsupported fields',
    'Некорректный host или upgrade instance': 'Invalid host or upgrade instance',
    'Укажите причину установки modification': 'Modification installation reason is required',
    'Host или upgrade не найден в Inventory': 'Host or upgrade was not found in Inventory',
    'Host должен быть исправен и находиться при персонаже': 'Host must be functional and carried by the character',
    'Upgrade должен находиться в состоянии carried': 'Upgrade must be in the carried state',
    'Требуется ручное подтверждение сложного правила совместимости': 'Complex compatibility rule requires manual confirmation',
    'Modification action содержит неподдерживаемые поля': 'Modification action contains unsupported fields',
    'weapon_instance_id допустим только для mount_weapon': 'weapon_instance_id is only allowed for mount_weapon',
    'ammo_instance_id допустим только для Reload': 'ammo_instance_id is only allowed for Reload',
    'Выберите конкретный ammo stack': 'Choose a specific ammo stack',
    'Выберите payload для Gas Jet: street_drug / poison / biotoxin': 'Choose a Gas Jet payload: street_drug / poison / biotoxin',
    'Ammo stack недоступен для Reload': 'Ammo stack is unavailable for Reload',
    'Ammo stack несовместим с этим оружием': 'Ammo stack is incompatible with this weapon',
    'Магазин уже заполнен': 'The magazine is already full',
    'Нельзя смешивать разные типы ammo в одном магазине': 'Different ammo types cannot be mixed in one magazine',
    'В выбранном ammo stack нет боеприпасов': 'The selected ammo stack is empty',
    'Частично использованный ammo stack нельзя продать': 'A partially used ammo stack cannot be sold',
    'Vehicle repair содержит неподдерживаемые поля': 'Vehicle repair contains unsupported fields',
    'Укажите причину Vehicle repair': 'Provide a reason for the Vehicle repair',
    'Vehicle repair уже выполняется': 'A Vehicle repair is already in progress',
    'Vehicle не нуждается в ремонте': 'The Vehicle does not need repair',
    'Укажите техника для Vehicle repair': 'Specify the Vehicle repair technician',
    'Нет активного Vehicle repair': 'There is no active Vehicle repair',
    'Укажите итог Repair Check': 'Provide the Repair Check total',
    'Используйте Vehicle Repair Workflow': 'Use the Vehicle Repair Workflow',
    'Vehicle SDP action поддерживает только damage': 'Vehicle SDP actions only support damage',
    'Modification не найдена': 'Modification not found',
    'Modification уже снята': 'Modification is already removed',
    'Эта modification не может быть снята': 'This modification cannot be removed',
    'Неизвестное действие с modification': 'Unknown modification action',
    'Укажите причину снятия modification': 'Modification removal reason is required',
    'Сначала снимите modifications, зависящие от granted slots': 'Remove modifications that depend on granted slots first',
    'Modification не имеет alternate attack profile': 'Modification has no alternate attack profile',
    'Modification не имеет action resource profile': 'Modification has no action resource profile',
    'Alternate weapon разряжен': 'Alternate weapon is unloaded',
    'Нет боеприпасов для перезарядки alternate weapon': 'No ammunition is available to reload the alternate weapon',
    'Modification не является баллоном NOS': 'Modification is not a NOS tank',
    'Баллон NOS уже использован в этот игровой день': 'This NOS tank was already used this campaign day',
    'Укажите причину сброса NOS': 'Provide a reason for resetting NOS',
    'Баллон NOS уже готов к использованию': 'This NOS tank is already ready to use',
    'Баллон NOS не является оружием': 'A NOS tank is not a weapon',
    'Баллон NOS нельзя перезарядить': 'A NOS tank cannot be reloaded',
    'Для атаки требуется X патронов': 'This attack requires X rounds',
    'Vehicle configuration должна быть объектом': 'Vehicle configuration must be an object',
    'Vehicle configuration содержит неизвестные поля': 'Vehicle configuration contains unknown fields',
    'Выберите допустимое направление mounted weapon': 'Choose an allowed mounted weapon orientation',
    'Выберите обязательную конфигурацию транспорта': 'Choose the required vehicle configuration',
    'Некорректная конфигурация транспорта': 'Invalid vehicle configuration',
    'Повреждена связь Vehicle Heavy Weapon Mount': 'Vehicle Heavy Weapon Mount link is corrupted',
    'Modification не является Vehicle Heavy Weapon Mount': 'Modification is not a Vehicle Heavy Weapon Mount',
    'Укажите причину изменения mounted weapon': 'Provide a reason for changing the mounted weapon',
    'Сначала снимите оружие с Vehicle Heavy Weapon Mount': 'Unmount the weapon from the Vehicle Heavy Weapon Mount first',
    'Сначала снимите текущее mounted weapon': 'Unmount the current weapon first',
    'Выберите конкретный экземпляр оружия': 'Choose a specific weapon instance',
    'Крепление принимает только двуручное дальнобойное оружие': 'The mount only accepts a two-handed ranged weapon',
    'Оружие должно быть свободным и находиться в carried': 'The weapon must be free and in the carried state',
    'Mounted weapon instance отсутствует': 'Mounted weapon instance is missing',
    'Сначала снимите upgrades жилых комнат': 'Remove vehicle room upgrades first',
    'Сначала освободите места, занятые Heavy Weapon Mount': 'Free the seats occupied by Heavy Weapon Mounts first',
    'Housing Capacity требуется для нескольких Heavy Weapon Mounts': 'Housing Capacity is required for multiple Heavy Weapon Mounts',
    'Сначала установите оружие в Vehicle Heavy Weapon Mount': 'Mount a weapon in the Vehicle Heavy Weapon Mount first',
    'Оружие не имеет отслеживаемого магазина': 'The weapon has no tracked magazine',
    'Mounted weapon управляется только через Vehicle Garage': 'Mounted weapons are managed only through the Vehicle Garage',
    'Modification configuration должна быть объектом': 'Modification configuration must be an object',
    'Modification configuration содержит неизвестные поля': 'Modification configuration contains unknown fields',
    'Выберите обязательную конфигурацию modification': 'Choose the required modification configuration',
    'Некорректный вариант configuration': 'Invalid configuration choice',
    'Vehicle configuration пока не поддерживается': 'Vehicle configuration is not supported yet',
    'Cyberdeck configuration пока не поддерживается': 'Cyberdeck configuration is not supported yet',
    'Сначала освободите зависимые Cyberdeck slots': 'Free dependent Cyberdeck slots first',
    'Program action содержит неподдерживаемые поля': 'Program action contains unsupported fields',
    'Installed Program instance не найден': 'Installed Program instance not found',
    'Повреждена связь установленной Program': 'Installed Program link is corrupted',
    'Укажите причину Program action': 'Provide a reason for the Program action',
    'Backup restore содержит неподдерживаемые поля': 'Backup restore contains unsupported fields',
    'Installed Backup Drive не найден': 'Installed Backup Drive not found',
    'Backup Drive не содержит Programs': 'Backup Drive contains no Programs',
    'Укажите причину Backup restore': 'Provide a reason for Backup restore',
    'Installed Defense Sequencer не найден': 'Installed Defense Sequencer not found',
    'Defense Sequencer не имеет pending Armor trigger': 'Defense Sequencer has no pending Armor trigger',
    'Выбранная Armor не входит в pending eligibility snapshot': 'The selected Armor is not in the pending eligibility snapshot',
    'Eligible Armor больше не установлена в этом Cyberdeck': 'The eligible Armor is no longer installed in this Cyberdeck',
    'Defense Sequencer может Rez только inactive Armor': 'Defense Sequencer can Rez only inactive Armor',
    'Другая копия Armor уже Rezzed': 'Another Armor copy is already Rezzed',
    'Defense Sequencer resolution содержит неподдерживаемые поля': 'Defense Sequencer resolution contains unsupported fields',
    'Подтвердите, что выбранная Armor не использовалась в этом Netrun': 'Confirm that the selected Armor was not used during this Netrun',
    'Выберите concrete Armor Program instance': 'Choose a concrete Armor Program instance',
    'Укажите причину Defense Sequencer resolution': 'Provide a reason for the Defense Sequencer resolution',
    'Black ICE не имеет curated STAT effect': 'Black ICE has no curated STAT effect',
    'Black ICE STAT penalty roll должен быть от 1 до 6': 'Black ICE STAT penalty roll must be from 1 to 6',
    'Сначала удалите Cyberware через audited Uninstall': 'Remove Cyberware through the audited Uninstall action first',
    'Изменяйте Cyberware installation только через lifecycle action': 'Change Cyberware installation only through a lifecycle action',
    'Изменяйте concrete Cyberware hosts только через lifecycle action': 'Change concrete Cyberware hosts only through a lifecycle action',
    'Cyberware action содержит неподдерживаемые поля': 'Cyberware action contains unsupported fields',
    'Укажите причину Cyberware lifecycle action': 'Provide a reason for the Cyberware lifecycle action',
    'Cyberware instance не найден': 'Cyberware instance not found',
    'Cyberware instance не связан с Data Pool': 'Cyberware instance is not linked to the Data Pool',
    'host_instance_ids должен быть коротким списком': 'host_instance_ids must be a short list',
    'Некорректный concrete Cyberware host': 'Invalid concrete Cyberware host',
    'Cyberware уже установлена': 'Cyberware is already installed',
    'Сломанную Cyberware нельзя установить': 'Broken Cyberware cannot be installed',
    'Эта Cyberware не использует Option host': 'This Cyberware does not use an Option host',
    'Допустима только одна установленная копия Cyberware': 'Only one installed Cyberware copy is allowed',
    'Недостаточно Humanity для установки Cyberware': 'Not enough Humanity to install Cyberware',
    'Rebind требует установленную Cyberware Option': 'Rebind requires an installed Cyberware Option',
    'Cyberware уже не установлена': 'Cyberware is already uninstalled',
    'Стартовый Neuroport нельзя извлечь этим действием': 'The starting Neuroport cannot be removed with this action',
    'Одновременно допустим только один Cyberaudio Suite': 'Only one Cyberaudio Suite may be installed at a time',
    'Paired Cyberlegs требуют обе свободные стороны': 'Paired Cyberlegs require both sides to be free',
    'Изменяйте Cyberware side только через lifecycle action': 'Change Cyberware side only through a lifecycle action',
    'Подтвердите manual surgery/service resolution': 'Confirm manual surgery/service resolution',
    'Укажите clinic, surgeon или technician': 'Specify a clinic, surgeon, or technician',
    'Подтвердите required Biosystem': 'Confirm the required Biosystem',
    'Эта Cyberware не использует left/right side': 'This Cyberware does not use a left/right side',
    'Configure side требует установленный sided foundation': 'Configure side requires an installed sided foundation',
    'Выберите installation side: left/right': 'Choose installation side: left/right',
    'Quick Detach требует установленный Cyberarm': 'Quick Detach requires an installed Cyberarm',
    'Cyberarm не имеет установленный Quick Change Mount': 'Cyberarm has no installed Quick Change Mount',
    'Quick Attach требует detached Quick Change Cyberarm': 'Quick Attach requires a detached Quick Change Cyberarm',
    'Quick Change Cyberarm bundle повреждён': 'Quick Change Cyberarm bundle is corrupted',
    'Therapy action содержит неподдерживаемые поля': 'Therapy action contains unsupported fields',
    'Укажите причину Therapy action': 'Provide a reason for the Therapy action',
    'Therapy course уже активен': 'A Therapy course is already active',
    'Неизвестный Therapy type': 'Unknown Therapy type',
    'Укажите therapist или clinic': 'Specify a therapist or clinic',
    'Недостаточно средств для Therapy': 'Not enough funds for Therapy',
    'Humanity уже достигла Therapy maximum': 'Humanity has already reached the Therapy maximum',
    'Укажите addiction для Therapy': 'Specify the addiction for Therapy',
    'Нет активного Therapy course': 'There is no active Therapy course',
    'Therapy profile повреждён': 'Therapy profile is corrupted',
    'Подтвердите завершение недели Therapy': 'Confirm completion of the Therapy week',
    'Сначала освободите зависимые Cyberware Option Slots': 'Free dependent Cyberware Option Slots first',
    'Cyberweapon action содержит неподдерживаемые поля': 'Cyberweapon action contains unsupported fields',
    'Укажите причину Cyberweapon action': 'Provide a reason for the Cyberweapon action',
    'Installed curated Cyberweapon не найден': 'Installed curated Cyberweapon not found',
    'Cyberweapon не имеет deploy/stow state': 'Cyberweapon has no deploy/stow state',
    'Cyberweapon не имеет rev action': 'Cyberweapon has no rev action',
    'Сначала deploy Cyberweapon': 'Deploy the Cyberweapon first',
    'Fire доступен только ranged Cyberweapon': 'Fire is available only for a ranged Cyberweapon',
    'Cyberweapon magazine пуст': 'Cyberweapon magazine is empty',
    'Cyberweapon не использует tracked ammo': 'Cyberweapon does not use tracked ammunition',
    'Ammo stack несовместим с Cyberweapon': 'Ammo stack is incompatible with the Cyberweapon',
    'Повреждена связь Popup Cyberweapon': 'Popup Cyberweapon binding is corrupted',
    'Permanent Popup Weapon attachments нельзя изменять': 'Permanent Popup Weapon attachments cannot be changed',
    'Popup Weapon binding содержит неподдерживаемые поля': 'Popup Weapon binding contains unsupported fields',
    'Подтвердите permanent Popup Weapon binding': 'Confirm permanent Popup Weapon binding',
    'Укажите причину Popup Weapon binding': 'Provide a reason for Popup Weapon binding',
    'Installed generic Popup Weapon option не найден': 'Installed generic Popup Weapon option not found',
    'Popup Weapon уже имеет permanent bound weapon': 'Popup Weapon already has a permanent bound weapon',
    'Permanent Popup Weapon binding нельзя продать отдельно': 'Permanent Popup Weapon binding cannot be sold separately',
    'Повреждена связь Armor/Shield Tech Upgrade': 'Armor/Shield Tech Upgrade binding is corrupted',
    'Armor Tech Upgrade содержит неподдерживаемые поля': 'Armor Tech Upgrade contains unsupported fields',
    'Подтвердите успешный Tech Upgrade Check': 'Confirm a successful Tech Upgrade Check',
    'Укажите Tech и причину Armor Upgrade': 'Specify the Tech and Armor Upgrade reason',
    'Concrete Armor/Shield instance не найден': 'Concrete Armor/Shield instance not found',
    'Armor/Shield уже имеет Tech Upgrade': 'Armor/Shield already has a Tech Upgrade',
    'Armor instance не имеет upgradeable SP': 'Armor instance has no upgradeable SP',
    'Permanent Armor Tech Upgrade нельзя продать отдельно': 'Permanent Armor Tech Upgrade cannot be sold separately',
    'Повреждена связь Armor Repair Workflow': 'Armor Repair Workflow binding is corrupted',
    'Armor Repair action содержит неподдерживаемые поля': 'Armor Repair action contains unsupported fields',
    'Укажите причину Armor Repair action': 'Provide a reason for the Armor Repair action',
    'Concrete Armor instance не найден': 'Concrete Armor instance not found',
    'Bulletproof Shields не подлежат ремонту': 'Bulletproof Shields cannot be repaired',
    'Эта Armor не может восстанавливать SP': 'This Armor cannot restore SP',
    'Armor Repair уже активен': 'Armor Repair is already active',
    'Armor должна быть экипирована и повреждена': 'Armor must be equipped and damaged',
    'Укажите Armor repair technician': 'Specify the Armor repair technician',
    'Jeeves Executive Garment Bag недоступен': 'Jeeves Executive Garment Bag is unavailable',
    'Jeeves не ремонтирует Luxury/Super Luxury Armor': 'Jeeves cannot repair Luxury or Super Luxury Armor',
    'Нет активного Armor Repair': 'There is no active Armor Repair',
    'Подтвердите завершение Armor Repair': 'Confirm completion of Armor Repair',
    'Armor не имеет daily self-repair': 'Armor has no daily self-repair',
    'Подтвердите день без потери SP': 'Confirm a day without losing SP',
    'Повреждена связь Popup Shield': 'Popup Shield binding is corrupted',
    'Popup Shield action содержит неподдерживаемые поля': 'Popup Shield action contains unsupported fields',
    'Укажите причину Popup Shield action': 'Provide a reason for the Popup Shield action',
    'Installed Popup Shield option не найден': 'Installed Popup Shield option not found',
    'Сначала извлеките concrete Popup Shield': 'Remove the concrete Popup Shield first',
    'Popup Shield уже содержит concrete shield': 'Popup Shield already contains a concrete shield',
    'Popup Shield принимает только free Bulletproof Shield': 'Popup Shield accepts only a free Bulletproof Shield',
    'Popup Shield не содержит concrete shield': 'Popup Shield contains no concrete shield',
    'Destroyed Shield нельзя deploy': 'A destroyed Shield cannot be deployed',
    'Укажите Popup Shield damage 1–100': 'Provide Popup Shield damage from 1 to 100',
    'Укажите bounded Armor Repair service cost': 'Provide a bounded Armor Repair service cost',
    'Подтвердите оплату Armor Repair service': 'Confirm payment for the Armor Repair service',
    'Недостаточно средств для Armor Repair service': 'Not enough funds for the Armor Repair service',
    'Run доступен только Attacker Program': 'Run is available only for an Attacker Program',
    'Saved Program instance недоступен для восстановления': 'Saved Program instance is unavailable for restore',
    'Недостаточно Cyberdeck slots для Backup restore': 'Not enough Cyberdeck slots for Backup restore',
    'Black ICE требует NET entity deployment': 'Black ICE requires NET entity deployment',
    'Activate доступен только Booster или Defender Program': 'Activate is available only for Booster or Defender Programs',
    'Program необходимо сначала Deactivate': 'Deactivate the Program first',
    'REZ damage требует Rezzed Program': 'REZ damage requires a Rezzed Program',
    'Укажите REZ damage от 1 до 100': 'Provide REZ damage from 1 to 100',
    'Только одна копия этой Program может быть Rezzed': 'Only one copy of this Program may be Rezzed',
    'Derez требует Rezzed Program': 'Derez requires a Rezzed Program',
    'Deactivate требует Rezzed или Derezzed Program': 'Deactivate requires a Rezzed or Derezzed Program',
    'Black ICE deployment содержит неподдерживаемые поля': 'Black ICE deployment contains unsupported fields',
    'Installed Black ICE instance не найден': 'Installed Black ICE instance not found',
    'Выбранная Program не является Black ICE': 'The selected Program is not Black ICE',
    'Для этой Black ICE уже существует active NET entity': 'This Black ICE already has an active NET entity',
    'Black ICE необходимо сначала Deactivate': 'Deactivate Black ICE first',
    'Укажите Floor для Black ICE': 'Specify a Floor for Black ICE',
    'Укажите target для deployed Black ICE': 'Specify a target for deployed Black ICE',
    'Укажите причину Black ICE deployment': 'Provide a reason for Black ICE deployment',
    'NET entity action содержит неподдерживаемые поля': 'NET entity action contains unsupported fields',
    'Black ICE NET entity не найдена': 'Black ICE NET entity not found',
    'Black ICE NET entity уже завершена': 'Black ICE NET entity is already completed',
    'Source Black ICE installation отсутствует': 'Source Black ICE installation is missing',
    'Укажите причину NET entity action': 'Provide a reason for the NET entity action',
    'REZ damage требует active Black ICE': 'REZ damage requires active Black ICE',
    'Slide требует hunting Black ICE': 'Slide requires hunting Black ICE',
    'Engage требует lying-in-wait Black ICE': 'Engage requires lying-in-wait Black ICE',
    'Укажите Floor и target для Black ICE': 'Specify a Floor and target for Black ICE',
    'Session NET entity link отсутствует': 'Session NET entity link is missing',
    'Нет права редактировать Session NET Floors': 'No permission to edit Session NET Floors',
    'NET Floor требует label': 'NET Floor requires a label',
    'Укажите причину изменения NET Floors': 'Provide a reason for changing NET Floors',
    'NET Floor уже существует или достигнут лимит': 'NET Floor already exists or the limit was reached',
    'Session NET Floor не найден': 'Session NET Floor not found',
    'NET Floor используется active entity': 'NET Floor is used by an active entity',
    'Нет права управлять Session NET Queue': 'No permission to manage the Session NET Queue',
    'Некорректный Session NET turn state': 'Invalid Session NET turn state',
    'Укажите причину изменения NET Queue': 'Provide a reason for changing the NET Queue',
    'Session NET snapshot для отката повреждён': 'Session NET revert snapshot is corrupted',
    'Session NET context изменён после Character action': 'Session NET context changed after the Character action',
    'Некорректная Live Session': 'Invalid Live Session',
    'Нет доступа к Live NET Session': 'No access to the Live NET Session',
    'Character не участвует в этой Session': 'Character does not participate in this Session',
    'Выберите validated Session NET Floor': 'Choose a validated Session NET Floor',
    'Нет права управлять Black ICE entity': 'No permission to manage the Black ICE entity',
    'Выберите Session target combatant': 'Choose a Session target combatant',
    'Некорректный Session target для Black ICE': 'Invalid Session target for Black ICE',
    'Выберите validated Session Floor и target': 'Choose a validated Session Floor and target',
    'Сначала удалите NET nodes с этого Floor': 'Delete NET nodes from this Floor first',
    'Нет права редактировать NET Architecture': 'No permission to edit NET Architecture',
    'NET node содержит неподдерживаемые поля': 'NET node contains unsupported fields',
    'NET node требует validated Floor': 'NET node requires a validated Floor',
    'Некорректный NET node type или label': 'Invalid NET node type or label',
    'Укажите причину изменения NET Architecture': 'Provide a reason for changing NET Architecture',
    'Достигнут лимит NET nodes': 'NET node limit reached',
    'NET node не найден': 'NET node not found',
    'Сначала удалите NET paths этого node': 'Delete NET paths connected to this node first',
    'NET node используется active entity': 'NET node is used by an active entity',
    'NET path содержит неподдерживаемые поля': 'NET path contains unsupported fields',
    'Некорректные NET path endpoints или direction': 'Invalid NET path endpoints or direction',
    'NET path уже существует': 'NET path already exists',
    'Достигнут лимит NET paths': 'NET path limit reached',
    'NET path не найден': 'NET path not found',
    'Выберите validated Session NET node': 'Choose a validated Session NET node',
    'Выберите validated Session Floor, node и target': 'Choose a validated Session Floor, node, and target',
    'Live NET Session не найдена': 'Live NET Session not found',
    'NET action содержит неподдерживаемые поля': 'NET action contains unsupported fields',
    'NET action требует Character combatant': 'NET action requires a Character combatant',
    'Character для NET action не найден': 'Character for NET action not found',
    'Нет права выполнять NET action этим Character': 'No permission to perform a NET action with this Character',
    'NET action требует Netrunner Role': 'NET action requires the Netrunner Role',
    'Укажите причину NET action': 'Provide a reason for the NET action',
    'Jack In требует Access Point node': 'Jack In requires an Access Point node',
    'Access Point node ещё не revealed': 'Access Point node is not revealed yet',
    'Netrunner не Jacked In': 'Netrunner is not Jacked In',
    'NET action требует Jacked In Netrunner': 'NET action requires a Jacked In Netrunner',
    'Move требует revealed target node': 'Move requires a revealed target node',
    'NET nodes не соединены revealed path': 'NET nodes are not connected by a revealed path',
    'Unresolved Password блокирует движение вперёд': 'Unresolved Password blocks forward movement',
    'Pathfinder target node не найден': 'Pathfinder target node not found',
    'Pathfinder target должен быть adjacent node': 'Pathfinder target must be an adjacent node',
    'Backdoor требует текущий Password node': 'Backdoor requires the current Password node',
    'Eye-Dee доступен только для текущего node': 'Eye-Dee is available only for the current node',
    'Control action требует текущий Control node': 'Control action requires the current Control node',
    'Program Attack требует Black ICE на текущем node': 'Program Attack requires Black ICE on the current node',
    'Program Attack target entity недоступна': 'Program Attack target entity is unavailable',
    'Program Attack требует installed Attacker Program': 'Program Attack requires an installed Attacker Program',
    'NET Action budget исчерпан для текущего NET Round': 'NET Action budget is exhausted for the current NET Round',
    'Target Dossier изменён в другой вкладке': 'Target Dossier changed in another tab',
    'Нет допустимых Programs для curated Black ICE effect': 'No eligible Programs for the curated Black ICE effect',
    'Выбранная target Program недопустима': 'Selected target Program is not eligible',
    'Нет права выполнять Black ICE attack': 'No permission to perform a Black ICE attack',
    'Black ICE attack содержит неподдерживаемые поля': 'Black ICE attack contains unsupported fields',
    'Black ICE attack требует active target link': 'Black ICE attack requires an active target link',
    'Source Black ICE Character отсутствует': 'Source Black ICE Character is missing',
    'Black ICE attack требует hunting entity': 'Black ICE attack requires a hunting entity',
    'Source Black ICE Program отсутствует': 'Source Black ICE Program is missing',
    'Black ICE target требует Netrunner Character': 'Black ICE target requires a Netrunner Character',
    'Black ICE target должен быть Jacked In на том же node': 'Black ICE target must be Jacked In on the same node',
    'Black ICE target не имеет Interface Rank': 'Black ICE target has no Interface Rank',
    'Укажите причину Black ICE attack': 'Provide a reason for the Black ICE attack',
    'Нет Rezzed Programs для Anti-Program Black ICE': 'No Rezzed Programs are available for Anti-Program Black ICE',
    'Anti-Program Black ICE effect требует manual resolution': 'Anti-Program Black ICE effect requires manual resolution',
    'Выбранная target Program не является Rezzed': 'Selected target Program is not Rezzed',
    'Неподдерживаемый тип modification host': 'Unsupported modification host type',
    'Сначала снимите зависимые vehicle upgrades': 'Remove dependent vehicle upgrades first',
    'Vehicle instance не найден': 'Vehicle instance not found',
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
    'Некорректное время события': 'Invalid event time',
    'Некорректная локация Night City': 'Invalid Night City location',
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
    'Укажите причину изменения доступа': 'Provide a reason for the access change',
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
    'Некорректный GM truth status': 'Invalid GM truth status',
    'Укажите причину скрытия': 'Provide a reason for hiding this content',
    'Комментарий не может быть пустым': 'Comment cannot be empty',
    'Комментарий не найден': 'Comment not found',
    'Недоступная персона-автор': 'Unavailable author Persona',
    'Родительский комментарий не найден': 'Parent comment not found',
    'NPC template нужно имя': 'NPC template name is required',
    'Некорректный NPC template': 'Invalid NPC template',
    'Сессия не найдена': 'Session not found',
    'Нет права редактировать сессию': 'You cannot edit this Session',
    'Нет права управлять доступом сессии': 'You cannot manage Session access',
    'Некорректная роль участника сессии': 'Invalid Session member role',
    'Назначение доступа не найдено': 'Session access assignment not found',
    'Assistant может менять только ход и раунд': 'Assistant can only change the turn and round',
    'Safety signal отключён для этой сессии': 'Safety signals are disabled for this Session',
    'Некорректный тип Safety signal': 'Invalid Safety signal type',
    'Нет права управлять Safety signal': 'You cannot manage Safety signals',
    'Safety signal не найден': 'Safety signal not found',
    'Некорректный статус Safety signal': 'Invalid Safety signal status',
    'Resolved Safety signal нельзя открыть повторно': 'A resolved Safety signal cannot be reopened',
    'Некорректный статус сессии': 'Invalid Session status',
    'Участнику сессии нужно имя': 'Session combatant name is required',
    'Нет права редактировать участника': 'You cannot edit this combatant',
    'Нет доступа к экрану сессии': 'You cannot access this Session view',
    'Нет доступа к контракту сессии': 'You cannot access the Session Contract',
    'Нет права завершить контракт': 'You cannot complete this Contract',
    'Результат контракта: completed/failed': 'Contract result must be completed or failed',
    'Выберите доступную персону для Aftermath': 'Choose an available Persona for the Aftermath',
    'Изменение досье должно быть объектом': 'Dossier update must be an object',
    'patch должен быть объектом': 'patch must be an object',
    'Механические поля изменяются только специальными операциями': 'Mechanical fields can only be changed through dedicated operations',
    'public должен быть логическим значением': 'public must be a boolean',
    'Укажите одну конкретную запись: signup_id или character_id': 'Specify exactly one signup: signup_id or character_id',
    'Связать публикацию с контрактом может его GM или участник Crew': 'Only the Contract GM or a Crew member can link a post to it',
    'Сюжетную линию может связать её GM или Crew связанного контракта': 'Only the Storyline GM or Crew of its linked Contract can link a post to it',
    'Награды должны быть списком до 100 записей': 'Rewards must be a list of no more than 100 entries',
    'Некорректная награда': 'Invalid reward',
    'Награду может получить только персонаж из Crew': 'Only a Crew character can receive a reward',
    'Награда персонажа указана дважды': 'A character reward was specified twice',
    'Некорректная сумма награды': 'Invalid reward amount',
    'Награды Cash и IP должны быть неотрицательными числами, IP — целым': 'Cash and IP rewards must be nonnegative numbers, and IP must be an integer',
    'Архивное досье не может получить награду': 'An archived Dossier cannot receive a reward',
    'Деньги изменяются только через Market, Payroll или Aftermath': 'Cash can only be changed through Market, Payroll, or Aftermath',
    'Legacy API доступен только для чтения; используйте NC//NET City Feed': 'Legacy API is read-only; use NC//NET City Feed',
    'Legacy API доступен только для чтения; используйте NC//NET Contracts': 'Legacy API is read-only; use NC//NET Contracts',
    'visibility должен быть объектом': 'visibility must be an object',
    'Некорректные настройки видимости Dossier': 'Invalid Dossier visibility settings',
    'Регистрация новых аккаунтов отключена': 'New account registration is disabled',
    'Пароль: минимум 8 символов': 'Password must contain at least 8 characters',
    'Пароль слишком длинный': 'Password is too long',
    'Приглашение не найдено': 'Invite not found',
    'Приглашение недействительно или уже использовано': 'Invite is invalid or has already been used',
    'Аккаунт отключён администратором': 'Account has been disabled by an administrator',
    'Сессия входа не найдена': 'Login session not found',
    'Текущую сессию завершайте обычным выходом': 'Use regular sign out for the current session',
    'Текущий пароль указан неверно': 'Current password is incorrect',
    'Новый пароль должен отличаться от текущего': 'New password must differ from the current password',
    'Нельзя отключить собственный аккаунт': 'You cannot disable your own account',
    'Нельзя отключить последнего активного администратора': 'The last active administrator cannot be disabled',
    'Укажите revision Dossier': 'Dossier revision is required',
    'Dossier изменён в другой вкладке; обновите страницу': 'Dossier changed in another tab; reload the page',
    'Слишком много запросов; попробуйте позже': 'Too many requests; try again later',
    'Слишком много неудачных входов; попробуйте позже': 'Too many failed sign-in attempts; try again later',
    'Memorial уже опубликован': 'Memorial is already published',
    'Только владелец персонажа заполняет memorial': 'Only the character owner may fill the memorial',
    'Membership требует member и organization persona': 'Membership requires a member and an organization persona',
    'Membership не найден': 'Membership not found',
    'Укажите организацию': 'Specify an organization',
    'Нет доступа к репутации персонажа': 'No access to this character reputation',
    'Действие: store или take': 'Action: store or take',
    'Предмет не найден в личном тайнике': 'Item not found in personal stash',
    'Сначала снимите предмет': 'Unequip the item first',
    'Нет права синхронизировать сессию': 'No permission to sync session',
    'PDF обязателен (base64)': 'PDF is required (base64)',
    'Некорректный base64': 'Invalid base64',
    'Файл не является PDF': 'File is not a PDF',
    'PDF слишком большой (макс 5 МБ)': 'PDF is too large (max 5 MB)',
    'Ошибка парсинга PDF': 'PDF parsing error',
    'Недопустимый источник запроса': 'Invalid request origin',
    'Tech Maker modification содержит неподдерживаемые поля': 'Tech Maker modification contains unsupported fields',
    'Укажите название Tech Maker modification': 'Tech Maker modification name is required',
    'Укажите Tech и причину Tech Maker modification': 'Provide the Tech and a reason for the Tech Maker modification',
    'Выберите конкретный host instance': 'Choose a specific host instance',
    'Host instance не найден': 'Host instance not found',
    'Host не поддерживает Tech Maker modifications': 'The host does not support Tech Maker modifications',
    'Tech Maker effect должен быть объектом': 'Tech Maker effect must be an object',
    'Tech Maker effect содержит неподдерживаемые поля': 'Tech Maker effect contains unsupported fields',
    'Недопустимый Tech Maker effect target': 'Invalid Tech Maker effect target',
    'Tech Maker effect value должен быть целым числом': 'Tech Maker effect value must be an integer',
    'Tech Maker modification требует effect или manual_rule': 'Tech Maker modification requires an effect or a manual rule',
    'Подтвердите успешный Tech Maker Check за столом': 'Confirm the successful Tech Maker Check at the table',
    'Host уже имеет Tech Maker modification этого типа': 'The host already has a Tech Maker modification of this type',
    'Достигнут лимит Tech Maker modifications': 'Tech Maker modification limit reached',
    'Tech Maker action содержит неподдерживаемые поля': 'Tech Maker action contains unsupported fields',
    'Укажите причину Tech Maker action': 'Provide a reason for the Tech Maker action',
    'Tech Maker modification не найдена': 'Tech Maker modification not found',
    'Permanent Tech Maker modification нельзя снять': 'A permanent Tech Maker modification cannot be removed',
    'Tech Maker modification уже снята': 'Tech Maker modification is already removed',
    'Повреждена запись Tech Maker modification': 'Tech Maker modification record is corrupted',
    'Повреждена связь Tech Maker modification': 'Tech Maker modification link is corrupted',
    'Повреждена история Tech Maker modifications': 'Tech Maker modification history is corrupted',
    'Tech Maker fabrication содержит неподдерживаемые поля': 'Tech Maker fabrication contains unsupported fields',
    'Укажите название, Tech и причину Tech Maker fabrication': 'Provide a name, Tech, and reason for the Tech Maker fabrication',
    'Неизвестный blueprint item': 'Unknown blueprint item',
    'Этот предмет нельзя изготовить через Fabrication Expertise': 'This item cannot be fabricated with Fabrication Expertise',
    'Blueprint fabrication требует maker_specialty fabrication': 'Blueprint fabrication requires maker_specialty fabrication',
    'Fabrication Expertise требует blueprint item': 'Fabrication Expertise requires a blueprint item',
    'Некорректная стоимость материалов': 'Invalid material cost',
    'Campaign Clock содержит неподдерживаемые поля': 'Campaign Clock contains unsupported fields',
    'Укажите причину изменения Campaign Clock': 'Provide a reason for changing the Campaign Clock',
    'Укажите либо advance, либо set_to': 'Provide either advance or set_to',
    'Укажите advance или set_to': 'Provide advance or set_to',
    'advance должен быть объектом': 'advance must be an object',
    'advance содержит неподдерживаемые поля': 'advance contains unsupported fields',
    'advance должен быть от 1 минуты до 365 дней': 'advance must be from 1 minute to 365 days',
    'Некорректное set_to время Campaign Clock': 'Invalid set_to Campaign Clock time',
    'Item transfer содержит неподдерживаемые поля': 'Item transfer contains unsupported fields',
    'Неизвестный тип передачи предмета': 'Unknown item transfer type',
    'Некорректный идентификатор предмета': 'Invalid item identifier',
    'Передавать можно только carried предмет (сначала снимите его)': 'Only carried items can be transferred (unequip it first)',
    'Сначала снимите броню из слота': 'Unequip the armor from its slot first',
    'Сначала снимите установленные модификации с предмета': 'Remove installed modifications from the item first',
    'Предмет взят в долг — его можно только вернуть владельцу': 'The item is borrowed — it can only be returned to its owner',
    'Предмет сейчас в долгу у другого персонажа': 'The item is currently loaned out to another character',
    'Некорректное количество для передачи': 'Invalid transfer quantity',
    'Этот предмет передаётся поштучно (не stackable)': 'This item transfers one at a time (not stackable)',
    'Инвентарь получателя переполнен': 'The recipient inventory is full',
    'Делить можно только stackable предметы': 'Only stackable items can be split',
    'Предмет взят в долг — его нельзя делить': 'A borrowed item cannot be split',
    'Для разделения укажите количество меньше размера стека': 'To split, choose an amount smaller than the stack size',
    'Укажите получателя (to_char_id)': 'Provide a recipient (to_char_id)',
    'Нельзя передать предмет самому себе': 'You cannot transfer an item to yourself',
    'Досье получателя заархивировано': 'The recipient Dossier is archived',
    'Досье партнёра заархивировано': 'The trade partner Dossier is archived',
    'Предмет взят в долг — сначала верните владельцу': 'The item is borrowed — return it to its owner first',
    'Предмет не числится за вами как долг': 'The item is not listed as borrowed by you',
    'Досье владельца заархивировано': 'The owner Dossier is archived',
    'Предмет не числится как выданный вами в долг': 'The item is not listed as loaned out by you',
    'Укажите партнёра обмена (to_char_id)': 'Provide a trade partner (to_char_id)',
    'Укажите предмет партнёра (to_instance_id)': 'Provide the partner item (to_instance_id)',
    'Нельзя обменять предмет на самого себя': 'You cannot trade an item with itself',
    'Нельзя обменяться с самим собой': 'You cannot trade with yourself',
    'Dossier партнёра изменён в другой вкладке; обновите страницу': 'The partner Dossier changed in another tab; refresh the page',
    'Crew Stash take содержит неподдерживаемые поля': 'Crew Stash take contains unsupported fields',
    'Предмет не найден в Crew Stash': 'Item not found in the Crew Stash',
    'Недостаточно единиц в Crew Stash': 'Not enough units in the Crew Stash',
    'Этот предмет берётся поштучно (не stackable)': 'This item is taken one at a time (not stackable)',
    'Некорректный JSON импорта': 'Invalid import JSON',
    'Импорт должен быть JSON-объектом': 'Import must be a JSON object',
    'Неизвестный предмет в импорте': 'Unknown item in the import',
    'Market reserve содержит неподдерживаемые поля': 'Market reserve contains unsupported fields',
    'Неизвестный предмет Night Market': 'Unknown Night Market item',
    'Предмет не в текущем Night Market': 'Item is not in the current Night Market',
    'Досье зарезервированного персонажа заархивировано': 'The reserved character Dossier is archived',
    'Fixer request содержит неподдерживаемые поля': 'Fixer request contains unsupported fields',
    'Укажите предмет или название запроса': 'Provide an item or a request name',
    'Неизвестный предмет для запроса': 'Unknown item for the request',
    'Запрос Fixer не найден': 'Fixer request not found',
    'Запрос Fixer уже обработан': 'Fixer request is already resolved',
    'Fixer resolve action: fulfill/decline': 'Fixer resolve action: fulfill/decline',
    'Досье заказчика заархивировано': 'The requester Dossier is archived',
    'Некорректная цена Fixer': 'Invalid Fixer price',
    'Укажите название выдаваемого предмета': 'Provide a name for the granted item',
    'Некорректное количество': 'Invalid quantity',
    'NPC statblock должен быть объектом': 'NPC statblock must be an object',
    'NPC skills должен быть объектом до 200 записей': 'NPC skills must be an object with up to 200 entries',
    'NPC weapons должен быть списком до 30 записей': 'NPC weapons must be a list with up to 30 entries',
    'NPC weapon должен быть объектом': 'NPC weapon must be an object',
    'NPC weapon требует имя': 'NPC weapon requires a name',
    'Recap должен быть объектом': 'Recap must be an object',
    'Recap требует название': 'Recap requires a title',
    'Некорректная дата Recap': 'Invalid Recap date',
    'Recap списки должны быть массивами': 'Recap lists must be arrays',
    'Recap participants должен быть списком': 'Recap participants must be a list',
    'Сессия Recap не найдена': 'Recap session not found',
    'Нет доступа к сессии Recap': 'No access to the Recap session',
    'Нет права связывать Recap с этим контрактом': 'Not allowed to link the Recap to this contract',
    'Нет права связывать Recap с этой сюжетной линией': 'Not allowed to link the Recap to this storyline',
    'Recap не найден': 'Recap not found',
    'Recap не опубликован': 'Recap is not published',
    'Нет права редактировать Recap': 'Not allowed to edit this Recap',
    'Нет права удалять Recap': 'Not allowed to delete this Recap',
    'Downtime activity должен быть объектом': 'Downtime activity must be an object',
    'Неизвестная Downtime activity': 'Unknown Downtime activity',
    'Downtime activities должен быть списком до 12 записей': 'Downtime activities must be a list with up to 12 entries',
    'Downtime start содержит неподдерживаемые поля': 'Downtime start contains unsupported fields',
    'Downtime уже активен': 'Downtime is already active',
    'Неизвестная длительность Downtime': 'Unknown Downtime duration',
    'Downtime action содержит неподдерживаемые поля': 'Downtime action contains unsupported fields',
    'Downtime action: resolve/complete/abandon': 'Downtime action: resolve/complete/abandon',
    'Нет активного Downtime': 'There is no active Downtime',
    'Downtime activity не найдена': 'Downtime activity not found',
    'Downtime activity уже отмечена выполненной': 'Downtime activity is already resolved',
    'Некорректная сумма Hustle': 'Invalid Hustle amount',
    'Некорректное восстановление HP': 'Invalid HP recovery',
    'Локации нужно название': 'Location requires a name',
    'Неизвестный тип локации': 'Unknown location type',
    'Некорректные координаты локации': 'Invalid location coordinates',
    'Локация не найдена': 'Location not found',
    'Некорректный идентификатор локации': 'Invalid location identifier',
    'Локация с таким идентификатором уже существует': 'A location with this identifier already exists',
    'Seed локации можно редактировать только через custom копию': 'Seed locations can only be edited via a custom copy',
    'Seed локации нельзя удалить': 'Seed locations cannot be deleted',
    'Неизвестный статус memorial': 'Unknown memorial status',
    'Memorial требует handle': 'Memorial requires a handle',
    'Персонаж уже помечен memorial': 'The character is already memorialized',
    'Memorial для персонажа уже существует': 'A memorial already exists for this character',
    'Укажите причину memorial': 'Provide a reason for the memorial',
    'Memorial не найден': 'Memorial not found',
    'Укажите причину отмены memorial': 'Provide a reason for restoring the character',
    'Afterlife Legacy должен быть объектом': 'Afterlife Legacy must be an object',
    'Напиток требует название': 'The drink requires a name',
}

def server_error_message(message, language):
    if str(language or '').lower().startswith('ru'):
        return message
    if message in SERVER_ERROR_EN:
        return SERVER_ERROR_EN[message]
    replacements = [
        ('Распродано:', 'Sold out:'),
        ('Зарезервировано для другого персонажа:', 'Reserved for another character:'),
        ('Недостаточно единиц:', 'Not enough units:'),
        ('(доступно ', '(available '),
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
        ('Несовместимая модификация:', 'Incompatible modification:'),
        ('допустимо от', 'allowed range is'),
        (' до ', ' to '),
        ('требуется число', 'must be numeric'),
        ('Неизвестный Skill:', 'Unknown Skill:'),
        ('Неизвестный NPC Skill:', 'Unknown NPC Skill:'),
        ('ожидается список до 500 записей', 'must be a list with no more than 500 entries'),
        ('ожидается объект', 'must be an object'),
        ('Броня', 'Armor'),
        ('отсутствует в Inventory', 'is not present in Inventory'),
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
        ('записей', 'entries'),
        ('некорректный parent-pool', 'invalid parent pool'),
        ('распределено', 'allocated'),
        ('при parent-pool', 'with parent pool'),
        ('требуется совместимых hosts:', 'required compatible hosts:'),
        ('Сначала извлеките зависимые Cyberware Options:', 'Uninstall dependent Cyberware Options first:'),
        (': выберите left/right side', ': choose a left/right side'),
        (': сторона ', ': side '),
        (' уже занята', ' is already occupied'),
        (': требуется installation site ', ': requires installation site '),
        ('заполните', 'complete'),
        ('выберите Team Member', 'choose a Team Member'),
        ('недоступный выбор', 'unavailable choice'),
        ('уже на минимальном Level', 'is already at minimum Level'),
        ('Некорректное число в поле контракта:', 'Invalid number in Contract field:'),
        ('Не удалось прочитать резервные копии:', 'Could not read backups:'),
        ('Не удалось создать резервную копию:', 'Could not create backup:'),
        ('Резервная копия не прошла проверку:', 'Backup verification failed:'),
        ('Резервная копия не найдена:', 'Backup not found:'),
        ('Требуется Maker', 'Requires Maker'),
        ('rank 1+ для Tech Maker modification', 'rank 1+ for the Tech Maker modification'),
        ('недопустим для host', 'is not allowed for host'),
        ('Недопустимая операция', 'Invalid operation'),
        ('Tech Maker effect value вне диапазона', 'Tech Maker effect value is outside the range'),
        ('Недопустимое значение', 'Invalid value'),
        (' для ', ' for '),
    ]
    out = str(message)
    for ru, en in replacements:
        out = out.replace(ru, en)
    return out


def atomic_endpoint(fn):
    """Serialize a state-changing endpoint and always roll back on failure."""
    @functools.wraps(fn)
    def wrapped(self, conn, qs, match, body):
        if conn.in_transaction:
            conn.commit()
        conn.execute('BEGIN IMMEDIATE')
        try:
            result = fn(self, conn, qs, match, body)
            if conn.in_transaction:
                conn.commit()
            return result
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
    return wrapped


def q1(v, default=None):
    return v[0] if v else default


class Handler(MediaHandlers, BaseHTTPRequestHandler):
    server_version = 'CBPR/1.0'

    # -- утилиты
    def log_message(self, fmt, *args):
        sys.stderr.write('%s - %s\n' % (self.address_string(), fmt % args))

    def client_ip(self):
        candidate = getattr(self, 'client_address', ('local',))[0]
        if os.environ.get('CBPR_TRUST_PROXY', '').lower() in ('1', 'true', 'yes'):
            headers = getattr(self, 'headers', {})
            forwarded = [part.strip() for part in
                         str(headers.get('X-Forwarded-For') or '').split(',') if part.strip()]
            candidate = (headers.get('X-NCNET-Client-IP') or
                         headers.get('CF-Connecting-IP') or
                         (forwarded[-1] if forwarded else '') or candidate)
        try:
            return ipaddress.ip_address(str(candidate)).compressed
        except ValueError:
            return 'local'

    def rate_limit(self, scope, limit, window, user_id=None):
        identity = str(user_id) if user_id is not None else self.client_ip()
        enforce_rate_limit(f'{scope}:{identity}', limit, window)

    def send_security_headers(self):
        for name, value in security_headers():
            self.send_header(name, value)

    def send_json(self, obj, status=200, cookies=None):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_security_headers()
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
        now = time.time()
        row = conn.execute(
            'SELECT u.*,s.rowid _session_id,s.last_seen _session_last_seen '
            'FROM sessions s JOIN users u ON u.id=s.user_id '
            'WHERE s.token=? AND s.expires>? AND u.disabled_at IS NULL',
            (tok, now)).fetchone()
        if row and (_row_value(row, '_session_last_seen') is None or
                    _row_value(row, '_session_last_seen', 0) < now - 300):
            was_in_transaction = conn.in_transaction
            conn.execute('UPDATE sessions SET last_seen=? WHERE rowid=?',
                         (now, row['_session_id']))
            if not was_in_transaction:
                conn.commit()
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
                if conn.in_transaction:
                    conn.rollback()
                self.send_error_json(e.status, e.message)
            except Exception as e:  # noqa: BLE001
                if conn.in_transaction:
                    conn.rollback()
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
            fp = os.path.join(STATIC_DIR, rel)
            # Resolve symlinks and '..' so a crafted path cannot escape STATIC_DIR.
            real_fp = os.path.realpath(fp)
            if not (real_fp == STATIC_DIR or real_fp.startswith(STATIC_DIR + os.sep)):
                self.send_error_json(403, 'Запрещено')
                return
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
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body)

    # ------------------------------------------------------------ auth api

    def api_register(self, conn, qs, m, body):
        self.rate_limit('register', 5, 300)
        mode = registration_mode()
        if mode == 'closed':
            raise ApiError(403, 'Регистрация новых аккаунтов отключена')
        username = str(body.get('username') or '').strip().lower()
        password = str(body.get('password') or '')
        display = str(body.get('display_name') or '').strip()[:60] or username
        if not re.fullmatch(r'[a-z0-9_.\-]{3,24}', username):
            raise ApiError(400, 'Логин: 3–24 символа, латиница/цифры/._-')
        validate_new_password(password)
        invite = None
        try:
            conn.execute('BEGIN IMMEDIATE')
            if mode == 'invite':
                code_hash = invite_code_hash((body or {}).get('invite_code'))
                now = time.time()
                invite = conn.execute(
                    'SELECT * FROM registration_invites WHERE code_hash=? AND disabled_at IS NULL '
                    'AND (expires_at IS NULL OR expires_at>?) AND uses<max_uses',
                    (code_hash, now)).fetchone()
                if not invite:
                    raise ApiError(403, 'Приглашение недействительно или уже использовано')
            cur = conn.execute(
                'INSERT INTO users(username, display_name, pass_hash, is_gm, account_role, created) '
                "VALUES(?,?,?,0,'player',?)",
                (username, display, hash_password(password), time.time()))
            if invite:
                conn.execute('UPDATE registration_invites SET uses=uses+1 WHERE id=?',
                             (invite['id'],))
            conn.commit()
        except ApiError:
            conn.rollback()
            raise
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ApiError(409, 'Такой логин уже занят')
        token = create_session(
            conn, cur.lastrowid, self.client_ip(),
            getattr(self, 'headers', {}).get('User-Agent', ''))
        u = conn.execute('SELECT * FROM users WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.me_payload(u), cookies=[session_cookie(token)])

    def api_login(self, conn, qs, m, body):
        self.rate_limit('login', 12, 60)
        username = str(body.get('username') or '').strip().lower()
        if account_login_locked(username):
            raise ApiError(429, 'Слишком много неудачных входов; попробуйте позже')
        password = str(body.get('password') or '')
        u = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not u or not verify_password(password, u['pass_hash']):
            record_failed_login(username)
            raise ApiError(401, 'Неверный логин или пароль')
        if _row_value(u, 'disabled_at'):
            raise ApiError(403, 'Аккаунт отключён администратором')
        clear_failed_logins(username)
        token = create_session(
            conn, u['id'], self.client_ip(),
            getattr(self, 'headers', {}).get('User-Agent', ''))
        self.send_json(self.me_payload(u), cookies=[session_cookie(token)])

    def api_logout(self, conn, qs, m, body):
        tok = self.cookies().get('sid')
        if tok:
            conn.execute('DELETE FROM sessions WHERE token=?', (tok,))
            conn.commit()
        self.send_json({'ok': True}, cookies=[session_cookie('', 0)])

    def api_account_sessions(self, conn, qs, m, body):
        user = self.require_user(conn)
        token = self.cookies().get('sid')
        rows = conn.execute(
            'SELECT rowid session_id,token,created,expires,last_seen,ip_address,user_agent '
            'FROM sessions WHERE user_id=? AND expires>? ORDER BY last_seen DESC,created DESC',
            (user['id'], time.time())).fetchall()
        self.send_json({'sessions': [{
            'id': row['session_id'], 'created': row['created'], 'expires': row['expires'],
            'last_seen': row['last_seen'] or row['created'],
            'ip_address': row['ip_address'] or '',
            'user_agent': row['user_agent'] or '',
            'current': hmac.compare_digest(row['token'], token or ''),
        } for row in rows]})

    def api_account_session_revoke(self, conn, qs, m, body):
        user = self.require_user(conn)
        session_id = int(m.group(1))
        row = conn.execute(
            'SELECT rowid session_id,* FROM sessions WHERE rowid=? AND user_id=?',
            (session_id, user['id'])).fetchone()
        if not row:
            raise ApiError(404, 'Сессия входа не найдена')
        if hmac.compare_digest(row['token'], self.cookies().get('sid') or ''):
            raise ApiError(409, 'Текущую сессию завершайте обычным выходом')
        conn.execute('DELETE FROM sessions WHERE rowid=? AND user_id=?',
                     (session_id, user['id']))
        record_account_security(conn, user['id'], user['id'], 'session_revoked',
                                f'session:{session_id}')
        conn.commit()
        self.send_json({'ok': True})

    def api_account_password(self, conn, qs, m, body):
        user = self.require_user(conn)
        current_password = str((body or {}).get('current_password') or '')
        new_password = str((body or {}).get('new_password') or '')
        if not verify_password(current_password, user['pass_hash']):
            raise ApiError(403, 'Текущий пароль указан неверно')
        validate_new_password(new_password)
        if verify_password(new_password, user['pass_hash']):
            raise ApiError(400, 'Новый пароль должен отличаться от текущего')
        token = self.cookies().get('sid') or ''
        conn.execute('UPDATE users SET pass_hash=? WHERE id=?',
                     (hash_password(new_password), user['id']))
        conn.execute('DELETE FROM sessions WHERE user_id=? AND token!=?',
                     (user['id'], token))
        record_account_security(conn, user['id'], user['id'], 'password_changed',
                                'Other sessions revoked')
        conn.commit()
        self.send_json({'ok': True})

    def api_account_logout_all(self, conn, qs, m, body):
        user = self.require_user(conn)
        record_account_security(conn, user['id'], user['id'], 'logout_all',
                                'All sessions revoked')
        conn.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
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
            'disabled': bool(_row_value(u, 'disabled_at')),
            'disabled_reason': _row_value(u, 'disabled_reason'),
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
        security_rows = conn.execute(
            'SELECT a.*,target.username target_username,actor.username actor_username '
            'FROM account_security_audit a JOIN users target ON target.id=a.user_id '
            'LEFT JOIN users actor ON actor.id=a.actor_user_id '
            'ORDER BY a.created DESC,a.id DESC LIMIT 50'
        ).fetchall()
        self.send_json({
            'users': [{
                'id': row['id'], 'username': row['username'],
                'display_name': row['display_name'],
                'account_role': user_account_role(row),
                'show_display_name': bool(_row_value(row, 'show_display_name', 0)),
                'vk_linked': bool(_row_value(row, 'vk_user_id')),
                'disabled': bool(_row_value(row, 'disabled_at')),
                'disabled_reason': _row_value(row, 'disabled_reason'),
                'disabled_at': _row_value(row, 'disabled_at'),
                'character_count': row['character_count'],
                'created': row['created'],
            } for row in rows],
            'role_audit': [{
                'id': row['id'], 'target_username': row['target_username'],
                'actor_username': row['actor_username'] or 'system',
                'role_before': row['role_before'], 'role_after': row['role_after'],
                'reason': row['reason'], 'created': row['created'],
            } for row in audit_rows],
            'security_audit': [{
                'id': row['id'], 'target_username': row['target_username'],
                'actor_username': row['actor_username'] or 'system',
                'event_type': row['event_type'], 'detail': row['detail'],
                'created': row['created'],
            } for row in security_rows],
        })

    @atomic_endpoint
    def api_admin_user_role(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not reason:
            raise ApiError(400, 'Укажите причину изменения доступа')
        updated = assign_account_role(
            conn, actor, int(m.group(1)), (body or {}).get('account_role'), reason)
        self.send_json(self.me_payload(updated))

    @atomic_endpoint
    def api_admin_user_status(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        target = conn.execute('SELECT * FROM users WHERE id=?',
                              (int(m.group(1)),)).fetchone()
        if not target:
            raise ApiError(404, 'Пользователь не найден')
        disabled = bool((body or {}).get('disabled'))
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not reason:
            raise ApiError(400, 'Укажите причину изменения доступа')
        if disabled and target['id'] == actor['id']:
            raise ApiError(409, 'Нельзя отключить собственный аккаунт')
        if disabled and user_is_admin(target):
            active_admins = conn.execute(
                "SELECT COUNT(*) n FROM users WHERE account_role='admin' AND disabled_at IS NULL"
            ).fetchone()['n']
            if active_admins <= 1:
                raise ApiError(409, 'Нельзя отключить последнего активного администратора')
        currently_disabled = bool(_row_value(target, 'disabled_at'))
        if disabled == currently_disabled:
            self.send_json(self.me_payload(target))
            return
        if disabled:
            conn.execute(
                'UPDATE users SET disabled_at=?,disabled_reason=?,disabled_by=? WHERE id=?',
                (time.time(), reason, actor['id'], target['id']))
            conn.execute('DELETE FROM sessions WHERE user_id=?', (target['id'],))
            event_type = 'account_disabled'
        else:
            conn.execute(
                'UPDATE users SET disabled_at=NULL,disabled_reason=NULL,disabled_by=NULL WHERE id=?',
                (target['id'],))
            event_type = 'account_enabled'
        record_account_security(conn, target['id'], actor['id'], event_type, reason)
        conn.commit()
        updated = conn.execute('SELECT * FROM users WHERE id=?', (target['id'],)).fetchone()
        self.send_json(self.me_payload(updated))

    def invite_payload(self, row):
        now = time.time()
        return {
            'id': row['id'], 'label': row['label'],
            'max_uses': row['max_uses'], 'uses': row['uses'],
            'expires_at': row['expires_at'], 'disabled_at': row['disabled_at'],
            'created_by': row['created_by'], 'created': row['created'],
            'active': (not row['disabled_at'] and row['uses'] < row['max_uses'] and
                       (row['expires_at'] is None or row['expires_at'] > now)),
        }

    def api_admin_invites(self, conn, qs, m, body):
        self.require_admin(conn)
        rows = conn.execute(
            'SELECT * FROM registration_invites ORDER BY created DESC,id DESC LIMIT 200'
        ).fetchall()
        self.send_json({'registration_mode': registration_mode(),
                        'invites': [self.invite_payload(row) for row in rows]})

    def api_admin_invite_create(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        label = str((body or {}).get('label') or '').strip()[:120]
        max_uses = max(1, min(100, _num((body or {}).get('max_uses')) or 1))
        expires_days = _num((body or {}).get('expires_days'))
        expires_at = None if not expires_days else time.time() + max(1, min(365, expires_days)) * 86400
        code = create_invite_code()
        cur = conn.execute(
            'INSERT INTO registration_invites(code_hash,label,created_by,max_uses,uses,'
            'expires_at,created) VALUES(?,?,?,?,0,?,?)',
            (invite_code_hash(code), label, actor['id'], max_uses, expires_at, time.time()))
        conn.commit()
        row = conn.execute('SELECT * FROM registration_invites WHERE id=?',
                           (cur.lastrowid,)).fetchone()
        self.send_json({**self.invite_payload(row), 'code': code}, status=201)

    def api_admin_invite_revoke(self, conn, qs, m, body):
        self.require_admin(conn)
        row = conn.execute('SELECT * FROM registration_invites WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Приглашение не найдено')
        conn.execute('UPDATE registration_invites SET disabled_at=? WHERE id=?',
                     (time.time(), row['id']))
        conn.commit()
        updated = conn.execute('SELECT * FROM registration_invites WHERE id=?',
                               (row['id'],)).fetchone()
        self.send_json(self.invite_payload(updated))

    def api_admin_backups(self, conn, qs, m, body):
        self.require_admin(conn)
        tools = backup_tools_module()
        try:
            backups = tools.list_bundles(BACKUP_DIR)
        except (tools.BackupError, OSError) as error:
            raise ApiError(500, f'Не удалось прочитать резервные копии: {error}')
        self.send_json({'backups': backups, 'retention': backup_retention()})

    def api_admin_backup_create(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        tools = backup_tools_module()
        try:
            retention = backup_retention()
            result = tools.create_bundle(
                DB_PATH, UPLOAD_DIR, BACKUP_DIR, ITEMS_PATH, retention,
                str((body or {}).get('reason') or 'manual')[:120])
        except (tools.BackupError, OSError, sqlite3.DatabaseError) as error:
            raise ApiError(500, f'Не удалось создать резервную копию: {error}')
        record_account_security(conn, actor['id'], actor['id'], 'backup_created', result['name'])
        conn.commit()
        self.send_json({key: value for key, value in result.items() if key != 'path'}, status=201)

    def api_admin_backup_verify(self, conn, qs, m, body):
        self.require_admin(conn)
        tools = backup_tools_module()
        try:
            path = tools.bundle_path(BACKUP_DIR, m.group(1))
            result = tools.verify_bundle(path)
        except (tools.BackupError, OSError, sqlite3.DatabaseError) as error:
            raise ApiError(400, f'Резервная копия не прошла проверку: {error}')
        self.send_json(result)

    def api_admin_backup_download(self, conn, qs, m, body):
        self.require_admin(conn)
        tools = backup_tools_module()
        try:
            path = tools.bundle_path(BACKUP_DIR, m.group(1))
        except (tools.BackupError, OSError) as error:
            raise ApiError(404, f'Резервная копия не найдена: {error}')
        self.send_response(200)
        self.send_header('Content-Type', 'application/gzip')
        self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        self.send_header('Content-Length', str(path.stat().st_size))
        self.send_header('Cache-Control', 'private, no-store')
        self.send_security_headers()
        self.end_headers()
        with open(path, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                self.wfile.write(chunk)

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
        if (body or {}).get('all'):
            conn.execute('UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL',
                         (time.time(), user['id']))
        else:
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
        gm = user_is_gm(user)
        member_rows = conn.execute(
            'SELECT * FROM persona_memberships WHERE member_persona_id=? OR organization_persona_id=? '
            'ORDER BY sort_order,id', (row['id'], row['id'])).fetchall()
        payload['memberships'] = [membership_payload(r) for r in member_rows
                                  if gm or r['visibility'] == 'public']
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

    def api_memberships(self, conn, qs, m, body):
        user = self.current_user(conn)
        gm = user_is_gm(user)
        pid = int(m.group(1))
        rows = conn.execute(
            'SELECT * FROM persona_memberships WHERE member_persona_id=? OR organization_persona_id=? '
            'ORDER BY sort_order,id', (pid, pid)).fetchall()
        visible = [membership_payload(r) for r in rows
                   if gm or r['visibility'] == 'public']
        self.send_json({'memberships': visible})

    @atomic_endpoint
    def api_membership_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cleaned = clean_membership_input(body or {})
        now = time.time()
        cur = conn.execute(
            'INSERT INTO persona_memberships(member_persona_id,organization_persona_id,'
            'role_title,status,visibility,since_at,until_at,note,sort_order,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
            (cleaned['member_persona_id'], cleaned['organization_persona_id'],
             cleaned['role_title'], cleaned['status'], cleaned['visibility'],
             cleaned['since_at'], cleaned['until_at'], cleaned['note'],
             cleaned['sort_order'], now, now))
        conn.commit()
        row = conn.execute('SELECT * FROM persona_memberships WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(membership_payload(row), status=201)

    @atomic_endpoint
    def api_membership_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM persona_memberships WHERE id=?', (int(m.group(2)),)).fetchone()
        if not row:
            raise ApiError(404, 'Membership не найден')
        cleaned = clean_membership_input(body or {}, dict(row))
        conn.execute(
            'UPDATE persona_memberships SET member_persona_id=?,organization_persona_id=?,'
            'role_title=?,status=?,visibility=?,since_at=?,until_at=?,note=?,sort_order=?,updated=? WHERE id=?',
            (cleaned['member_persona_id'], cleaned['organization_persona_id'],
             cleaned['role_title'], cleaned['status'], cleaned['visibility'],
             cleaned['since_at'], cleaned['until_at'], cleaned['note'],
             cleaned['sort_order'], time.time(), row['id']))
        conn.commit()
        fresh = conn.execute('SELECT * FROM persona_memberships WHERE id=?', (row['id'],)).fetchone()
        self.send_json(membership_payload(fresh))

    @atomic_endpoint
    def api_membership_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        conn.execute('DELETE FROM persona_memberships WHERE id=?', (int(m.group(2)),))
        conn.commit()
        self.send_json({'ok': True})

    def api_crew_reputation(self, conn, qs, m, body):
        rows = conn.execute(
            'SELECT cr.*,p.display_name org_name,p.handle org_handle '
            'FROM crew_reputation cr JOIN personas p ON p.id=cr.organization_persona_id '
            'ORDER BY cr.updated DESC').fetchall()
        self.send_json({'reputation': [dict(r) for r in rows]})

    @atomic_endpoint
    def api_crew_reputation_set(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cleaned = clean_reputation_input(body or {})
        if not cleaned['organization_persona_id']:
            raise ApiError(400, 'Укажите организацию')
        now = time.time()
        conn.execute(
            'INSERT INTO crew_reputation(organization_persona_id,reputation,'
            'favor,heat,standing,note,created_by,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(organization_persona_id) DO UPDATE SET '
            'reputation=excluded.reputation,favor=excluded.favor,heat=excluded.heat,'
            'standing=excluded.standing,note=excluded.note,updated=excluded.updated',
            (cleaned['organization_persona_id'], cleaned['reputation'],
             cleaned['favor'], cleaned['heat'], cleaned['standing'],
             cleaned['note'], user['id'], now, now))
        conn.commit()
        row = conn.execute(
            'SELECT * FROM crew_reputation WHERE organization_persona_id=?',
            (cleaned['organization_persona_id'],)).fetchone()
        self.send_json(dict(row))

    @atomic_endpoint
    def api_crew_reputation_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        conn.execute('DELETE FROM crew_reputation WHERE id=?', (int(m.group(1)),))
        conn.commit()
        self.send_json({'ok': True})

    def api_character_reputation(self, conn, qs, m, body):
        user = self.current_user(conn)
        gm = user_is_gm(user)
        cid = int(m.group(1))
        if not gm:
            row = conn.execute('SELECT owner_id FROM characters WHERE id=?', (cid,)).fetchone()
            if not row or row['owner_id'] != (user['id'] if user else -1):
                raise ApiError(403, 'Нет доступа к репутации персонажа')
        rows = conn.execute(
            'SELECT * FROM character_reputation WHERE character_id=? ORDER BY updated DESC', (cid,)).fetchall()
        self.send_json({'reputation': [dict(r) for r in rows]})

    @atomic_endpoint
    def api_character_reputation_set(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cid = int(m.group(1))
        cleaned = clean_reputation_input(body or {})
        if not cleaned['organization_persona_id']:
            raise ApiError(400, 'Укажите организацию')
        now = time.time()
        conn.execute(
            'INSERT INTO character_reputation(character_id,organization_persona_id,reputation,'
            'favor,heat,standing,note,created_by,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?,?) '
            'ON CONFLICT(character_id,organization_persona_id) DO UPDATE SET '
            'reputation=excluded.reputation,favor=excluded.favor,heat=excluded.heat,'
            'standing=excluded.standing,note=excluded.note,updated=excluded.updated',
            (cid, cleaned['organization_persona_id'], cleaned['reputation'],
             cleaned['favor'], cleaned['heat'], cleaned['standing'],
             cleaned['note'], user['id'], now, now))
        conn.commit()
        row = conn.execute(
            'SELECT * FROM character_reputation WHERE character_id=? AND organization_persona_id=?',
            (cid, cleaned['organization_persona_id'])).fetchone()
        self.send_json(dict(row))

    @atomic_endpoint
    def api_character_reputation_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        conn.execute('DELETE FROM character_reputation WHERE id=? AND character_id=?',
                     (int(m.group(2)), int(m.group(1))))
        conn.commit()
        self.send_json({'ok': True})

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
            (row['id'], optional_timestamp((body or {}).get('event_at'), time.time()),
             public_text, private_text,
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
            'my_signups': [item for item in signup_payload
                           if user and item['user_id'] == user['id']],
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
            'district_id': clean_location_id(get('district_id')) or '',
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
            'cover_media_id': str(get('cover_media_id') or '')[:64] or None,
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

    @atomic_endpoint
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

    @atomic_endpoint
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

    def api_contract_preview(self, conn, qs, m, body):
        """Normalise and permission-check a Contract draft without writing anything."""
        user = self.require_gm(conn)
        data = self.clean_contract_input(body or {})
        if data['storyline_id']:
            storyline = conn.execute('SELECT * FROM storylines WHERE id=?', (data['storyline_id'],)).fetchone()
            if not storyline or not can_edit_storyline(conn, user, storyline):
                raise ApiError(400, 'Недоступная сюжетная линия')
        participants = []
        for index, item in enumerate((body or {}).get('participants') or []):
            persona = conn.execute('SELECT * FROM personas WHERE id=?',
                                   (_num(item.get('persona_id')),)).fetchone()
            if not persona or not can_manage_persona(user, persona):
                raise ApiError(400, 'Недоступная персона в контракте')
            participants.append({
                'persona_id': persona['id'],
                'role_key': str(item.get('role_key') or 'custom')[:40],
                'role_label': str(item.get('role_label') or '')[:100],
                'visibility': 'classified' if item.get('visibility') == 'classified' else 'public',
                'note': str(item.get('note') or '')[:1000],
                'sort_order': index,
                'display_name': persona['display_name'], 'handle': persona['handle'],
                'kind': persona['kind'], 'avatar_media_id': persona['avatar_media_id'],
                'accent_color': persona['accent_color'],
            })
        now = time.time()
        payload = {
            'id': None, 'preview': True,
            'storyline_id': data['storyline_id'], 'status': data['status'],
            'title': data['title'], 'teaser': data['teaser'],
            'public_brief': data['public_brief'], 'classified_brief': data['classified_brief'],
            'district_id': data['district_id'] or None, 'risk_level': data['risk_level'],
            'reward_mode': data['reward_mode'],
            'reward_exact': data['reward_exact'], 'reward_min': data['reward_min'],
            'reward_max': data['reward_max'], 'reward_text': data['reward_text'],
            'scheduled_at': data['scheduled_at'], 'crew_capacity': data['crew_capacity'],
            'requirements': data['requirements'], 'content_notes': data['content_notes'],
            'service_format': data['service_format'], 'service_contact': data['service_contact'],
            'service_vtt_url': data['service_vtt_url'], 'service_notes': data['service_notes'],
            'cover_media_id': data['cover_media_id'],
            'participants': participants,
            'crew_count': 0, 'waitlist_count': 0, 'signups': [],
            'has_classified_access': True, 'can_edit': True,
            'gm_display_name': user['display_name'],
            'created': now, 'updated': now,
        }
        self.send_json(payload)

    @atomic_endpoint
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

    @atomic_endpoint
    def api_contract_leave(self, conn, qs, m, body):
        user = self.require_user(conn)
        contract_id = int(m.group(1))
        contract = conn.execute('SELECT * FROM contracts WHERE id=?', (contract_id,)).fetchone()
        signup_id = _num((body or {}).get('signup_id'))
        character_id = _num((body or {}).get('character_id'))
        if bool(signup_id) == bool(character_id):
            raise ApiError(400, 'Укажите одну конкретную запись: signup_id или character_id')
        if signup_id:
            signup = conn.execute(
                "SELECT * FROM contract_signups WHERE id=? AND contract_id=? AND user_id=? "
                "AND status IN ('crew','waitlist')",
                (signup_id, contract_id, user['id'])).fetchone()
        else:
            signup = conn.execute(
                "SELECT * FROM contract_signups WHERE character_id=? AND contract_id=? AND user_id=? "
                "AND status IN ('crew','waitlist')",
                (character_id, contract_id, user['id'])).fetchone()
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

    @atomic_endpoint
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

    def feed_revision_payload(self, row, include_truth=False):
        before = parse_json_object(row['before_json'])
        after = parse_json_object(row['after_json'])
        changes = []
        fields = ('format', 'status', 'headline', 'lead', 'body', 'district_id',
                  'event_at', 'image_media_id', 'truth_status')
        for key in fields:
            if key == 'truth_status' and not include_truth:
                continue
            old_value, new_value = before.get(key), after.get(key)
            if old_value == new_value:
                continue
            if key == 'body':
                old_value = str(old_value or '')[:240]
                new_value = str(new_value or '')[:240]
            changes.append({'field': key, 'before': old_value, 'after': new_value})
        return {
            'id': row['id'], 'action': row['action'], 'actor': row['actor'],
            'reason': row['reason'], 'created': row['created'], 'changes': changes,
        }

    def feed_post_payload(self, conn, row, user, include_comments=False):
        persona = conn.execute('SELECT * FROM personas WHERE id=?',
                               (row['author_persona_id'],)).fetchone() if row['author_persona_id'] else None
        character = conn.execute('SELECT * FROM characters WHERE id=?',
                                 (row['author_character_id'],)).fetchone() if row['author_character_id'] else None
        can_edit = bool(user and (user['id'] == row['creator_user_id'] or user_is_admin(user) or
                        (persona and can_manage_persona(user, persona))))
        payload = {
            'id': row['id'], 'format': row['format'], 'status': row['status'],
            'creator_user_id': row['creator_user_id'],
            'author_persona_id': row['author_persona_id'],
            'author_character_id': row['author_character_id'],
            'author': persona_payload(persona, False) if persona else character_author_payload(character),
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
            if can_edit or user_is_gm(user):
                revisions = conn.execute(
                    'SELECT r.*,u.display_name actor FROM feed_post_revisions r '
                    'JOIN users u ON u.id=r.actor_user_id WHERE r.post_id=? '
                    'ORDER BY r.id DESC LIMIT 100', (row['id'],)).fetchall()
                payload['revisions'] = [
                    self.feed_revision_payload(item, include_truth=user_is_gm(user))
                    for item in revisions
                    if user_is_gm(user) or item['action'] != 'truth'
                ]
        return payload

    def feed_comment_payload(self, conn, row, user):
        persona = conn.execute('SELECT * FROM personas WHERE id=?',
                               (row['author_persona_id'],)).fetchone() if row['author_persona_id'] else None
        character = conn.execute('SELECT * FROM characters WHERE id=?',
                                 (row['author_character_id'],)).fetchone() if row['author_character_id'] else None
        return {
            'id': row['id'], 'post_id': row['post_id'],
            'parent_comment_id': row['parent_comment_id'], 'body': row['body'],
            'created': row['created'], 'updated': row['updated'],
            'hidden': bool(row['hidden_at']),
            'hidden_reason': row['hidden_reason'] if (user_is_gm(user) or
                              (user and row['creator_user_id'] == user['id'])) else None,
            'author': persona_payload(persona, False) if persona else character_author_payload(character),
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
        fmt = str((body or {}).get('format') or FEED_DEFAULT_FORMAT).lower()
        if fmt not in FEED_FORMATS:
            raise ApiError(400, 'Некорректный формат публикации')
        headline = str((body or {}).get('headline') or '').strip()[:240] or None
        text = str((body or {}).get('body') or '').strip()[:30000]
        if not text:
            raise ApiError(400, 'Публикации нужен текст и, для длинного формата, заголовок')
        status = 'draft' if user_is_gm(user) and (body or {}).get('status') == 'draft' else 'published'
        truth = str((body or {}).get('truth_status') or 'unknown') if user_is_gm(user) else 'unknown'
        if truth not in FEED_TRUTH:
            truth = 'unknown'
        contract_id = _num((body or {}).get('contract_id'))
        contract = None
        can_link_contract = False
        if contract_id:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?', (contract_id,)).fetchone()
            if not contract or (contract['status'] in ('draft', 'archived') and
                                not can_edit_contract(conn, user, contract)):
                raise ApiError(400, 'Контракт не найден')
            can_link_contract = can_edit_contract(conn, user, contract)
            if character_id and not can_link_contract:
                can_link_contract = bool(conn.execute(
                    "SELECT 1 FROM contract_signups WHERE contract_id=? AND character_id=? "
                    "AND user_id=? AND status='crew'",
                    (contract_id, character_id, user['id'])).fetchone())
            if not can_link_contract:
                raise ApiError(403, 'Связать публикацию с контрактом может его GM или участник Crew')

        storyline_id = _num((body or {}).get('storyline_id'))
        if storyline_id:
            storyline = conn.execute('SELECT * FROM storylines WHERE id=?', (storyline_id,)).fetchone()
            if not storyline or storyline['status'] == 'archived':
                raise ApiError(400, 'Недоступная сюжетная линия')
            can_link_storyline = can_edit_storyline(conn, user, storyline)
            if (not can_link_storyline and contract and can_link_contract and
                    contract['storyline_id'] == storyline['id']):
                can_link_storyline = True
            if not can_link_storyline:
                raise ApiError(403, 'Сюжетную линию может связать её GM или Crew связанного контракта')
        reply_to_post_id = _num((body or {}).get('reply_to_post_id'))
        if reply_to_post_id and not conn.execute(
                "SELECT 1 FROM feed_posts WHERE id=? AND status='published'",
                (reply_to_post_id,)).fetchone():
            raise ApiError(400, 'Публикация не найдена')
        event_at = optional_timestamp((body or {}).get('event_at'))
        now = time.time(); published = now if status == 'published' else None
        cur = conn.execute(
            'INSERT INTO feed_posts(format,status,creator_user_id,author_persona_id,author_character_id,'
            'storyline_id,contract_id,reply_to_post_id,district_id,headline,lead,body,image_media_id,'
            'truth_status,event_at,published_at,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (fmt, status, user['id'], persona_id, character_id,
             storyline_id, contract_id, reply_to_post_id,
             clean_location_id((body or {}).get('district_id')),
             headline, str((body or {}).get('lead') or '')[:500] or None, text,
             str((body or {}).get('image_media_id') or '')[:64] or None,
             truth, event_at, published, now, now))
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
        requested_status = str((body or {}).get('status', row['status']))
        status = requested_status
        if row['status'] == 'hidden' and not user_is_gm(user) and requested_status != 'archived':
            status = 'hidden'
        if (fmt not in FEED_FORMATS or status not in ('draft', 'published', 'archived', 'hidden') or
                not text):
            raise ApiError(400, 'Некорректная публикация')
        image_media_id = str((body or {}).get('image_media_id', row['image_media_id'] or ''))[:64] or None
        event_at = (optional_timestamp((body or {}).get('event_at'))
                    if 'event_at' in (body or {}) else row['event_at'])
        truth = row['truth_status']
        if user_is_gm(user) and 'truth_status' in (body or {}):
            candidate = str((body or {}).get('truth_status') or 'unknown')
            truth = candidate if candidate in FEED_TRUTH else 'unknown'
        attach_network_media(conn, user['id'], 'feed_post', row['id'],
                             [image_media_id], {'feed_image'})
        published = row['published_at'] or (time.time() if status == 'published' else None)
        conn.execute(
            'UPDATE feed_posts SET format=?,status=?,headline=?,lead=?,body=?,district_id=?,event_at=?,'
            'image_media_id=?,truth_status=?,published_at=?,updated=? WHERE id=?',
            (fmt, status, headline, str((body or {}).get('lead', row['lead'] or ''))[:500] or None,
             text, clean_location_id((body or {}).get('district_id', row['district_id'] or '')),
             event_at, image_media_id, truth, published, time.time(), row['id']))
        updated = conn.execute('SELECT * FROM feed_posts WHERE id=?', (row['id'],)).fetchone()
        after = self.feed_post_payload(conn, updated, user)
        record_feed_revision(conn, row['id'], user['id'], 'update', before, after)
        conn.commit(); self.send_json(after)

    def api_feed_preview(self, conn, qs, m, body):
        """Normalise and permission-check a draft post without writing anything."""
        user = self.require_user(conn)
        persona_id, character_id = self.resolve_feed_author(conn, user, body or {})
        fmt = str((body or {}).get('format') or FEED_DEFAULT_FORMAT).lower()
        if fmt not in FEED_FORMATS:
            raise ApiError(400, 'Некорректный формат публикации')
        headline = str((body or {}).get('headline') or '').strip()[:240] or None
        text = str((body or {}).get('body') or '').strip()[:30000]
        if not text:
            raise ApiError(400, 'Публикации нужен текст и, для длинного формата, заголовок')
        contract_id = _num((body or {}).get('contract_id'))
        if contract_id:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?', (contract_id,)).fetchone()
            if not contract or (contract['status'] in ('draft', 'archived') and
                                not can_edit_contract(conn, user, contract)):
                raise ApiError(400, 'Контракт не найден')
            can_link_contract = can_edit_contract(conn, user, contract)
            if character_id and not can_link_contract:
                can_link_contract = bool(conn.execute(
                    "SELECT 1 FROM contract_signups WHERE contract_id=? AND character_id=? "
                    "AND user_id=? AND status='crew'",
                    (contract_id, character_id, user['id'])).fetchone())
            if not can_link_contract:
                raise ApiError(403, 'Связать публикацию с контрактом может его GM или участник Crew')
        storyline_id = _num((body or {}).get('storyline_id'))
        if storyline_id:
            storyline = conn.execute('SELECT * FROM storylines WHERE id=?', (storyline_id,)).fetchone()
            if not storyline or storyline['status'] == 'archived':
                raise ApiError(400, 'Недоступная сюжетная линия')
            can_link_storyline = can_edit_storyline(conn, user, storyline)
            if (not can_link_storyline and contract_id and can_link_contract and
                    contract['storyline_id'] == storyline['id']):
                can_link_storyline = True
            if not can_link_storyline:
                raise ApiError(403, 'Сюжетную линию может связать её GM или Crew связанного контракта')
        reply_to_post_id = _num((body or {}).get('reply_to_post_id'))
        if reply_to_post_id and not conn.execute(
                "SELECT 1 FROM feed_posts WHERE id=? AND status='published'",
                (reply_to_post_id,)).fetchone():
            raise ApiError(400, 'Публикация не найдена')
        truth = 'unknown'
        if user_is_gm(user):
            candidate = str((body or {}).get('truth_status') or 'unknown')
            truth = candidate if candidate in FEED_TRUTH else 'unknown'
        now = time.time()
        preview_row = {
            'id': None, 'format': fmt, 'status': 'preview',
            'creator_user_id': user['id'],
            'author_persona_id': persona_id, 'author_character_id': character_id,
            'storyline_id': storyline_id, 'contract_id': contract_id,
            'reply_to_post_id': reply_to_post_id,
            'district_id': clean_location_id((body or {}).get('district_id')),
            'headline': headline, 'lead': str((body or {}).get('lead') or '')[:500] or None,
            'body': text,
            'image_media_id': str((body or {}).get('image_media_id') or '')[:64] or None,
            'truth_status': truth, 'hidden_reason': None,
            'event_at': optional_timestamp((body or {}).get('event_at')),
            'published_at': None, 'created': now, 'updated': now,
        }
        persona = conn.execute('SELECT * FROM personas WHERE id=?',
                               (persona_id,)).fetchone() if persona_id else None
        character = conn.execute('SELECT * FROM characters WHERE id=?',
                                 (character_id,)).fetchone() if character_id else None
        payload = {
            'id': None, 'format': fmt, 'status': 'preview',
            'creator_user_id': user['id'],
            'author_persona_id': persona_id, 'author_character_id': character_id,
            'author': persona_payload(persona, False) if persona else character_author_payload(character),
            'storyline_id': storyline_id, 'contract_id': contract_id,
            'reply_to_post_id': reply_to_post_id, 'district_id': preview_row['district_id'],
            'headline': headline, 'lead': preview_row['lead'], 'body': text,
            'image_media_id': preview_row['image_media_id'],
            'event_at': preview_row['event_at'], 'published_at': None,
            'created': now, 'updated': now, 'can_edit': True, 'preview': True,
        }
        if user_is_gm(user):
            payload['truth_status'] = truth
        self.send_json(payload)

    def api_feed_truth_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM feed_posts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Публикация не найдена')
        truth = str((body or {}).get('truth_status') or 'unknown')
        if truth not in FEED_TRUTH:
            raise ApiError(400, 'Некорректный GM truth status')
        before = self.feed_post_payload(conn, row, user)
        conn.execute('UPDATE feed_posts SET truth_status=?,updated=? WHERE id=?',
                     (truth, time.time(), row['id']))
        updated = conn.execute('SELECT * FROM feed_posts WHERE id=?', (row['id'],)).fetchone()
        after = self.feed_post_payload(conn, updated, user)
        record_feed_revision(conn, row['id'], user['id'], 'truth', before, after,
                             str((body or {}).get('reason') or 'GM truth classification')[:500])
        conn.commit(); self.send_json({'ok': True, 'truth_status': truth})

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
            'effects_rules_version': load_effect_rules().get('rules_version'),
            'registration_mode': registration_mode(),
            'character_visibility_defaults': CHARACTER_VISIBILITY_DEFAULTS,
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

    def api_campaign_clock(self, conn, qs, m, body):
        user = self.current_user(conn)
        ensure_campaign_clock(conn)
        payload = campaign_clock_payload(conn)
        if user and user_is_gm(user):
            payload['pending'] = campaign_pending_services(conn)
        self.send_json(payload)

    @atomic_endpoint
    def api_campaign_clock_advance(self, conn, qs, m, body):
        user = self.require_gm(conn)
        allowed = {'advance', 'set_to', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Campaign Clock содержит неподдерживаемые поля')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения Campaign Clock')
        before = campaign_now(conn)
        advance = (body or {}).get('advance')
        set_to = (body or {}).get('set_to')
        if advance is not None and set_to is not None:
            raise ApiError(400, 'Укажите либо advance, либо set_to')
        if advance is not None:
            if not isinstance(advance, dict):
                raise ApiError(400, 'advance должен быть объектом')
            if set(advance) - {'days', 'hours', 'minutes'}:
                raise ApiError(400, 'advance содержит неподдерживаемые поля')
            days = _num(advance.get('days')) or 0
            hours = _num(advance.get('hours')) or 0
            minutes = _num(advance.get('minutes')) or 0
            delta = days * 86400 + hours * 3600 + minutes * 60
            if not 0 < delta <= 365 * 86400:
                raise ApiError(400, 'advance должен быть от 1 минуты до 365 дней')
            after = before + delta
        elif set_to is not None:
            try:
                after = float(set_to)
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректное set_to время Campaign Clock')
            if not math.isfinite(after) or after < 0:
                raise ApiError(400, 'Некорректное set_to время Campaign Clock')
            delta = after - before
        else:
            raise ApiError(400, 'Укажите advance или set_to')
        now = time.time()
        conn.execute('UPDATE campaign_state SET campaign_time=?,updated=? WHERE id=1',
                     (after, now))
        conn.execute(
            'INSERT INTO campaign_clock_audit(actor_user_id,delta_seconds,before_time,'
            'after_time,reason,created) VALUES(?,?,?,?,?,?)',
            (user['id'], delta, before, after, reason, now))
        conn.commit()
        payload = campaign_clock_payload(conn)
        payload['pending'] = campaign_pending_services(conn)
        self.send_json(payload)

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
        items = [catalog_item_payload(item) for item in items[offset:offset + limit]]
        self.send_json({'total': total, 'items': items, 'offset': offset, 'limit': limit})

    def api_item(self, conn, qs, m, body):
        it = item_by_id(m.group(1))
        if not it:
            raise ApiError(404, 'Предмет не найден')
        self.send_json(catalog_item_payload(it))

    def api_nightmarket(self, conn, qs, m, body):
        ensure_market_stock(conn)
        payload = night_market(conn=conn)
        persona_rows = conn.execute(
            "SELECT id,handle FROM personas WHERE handle IN (%s)" %
            ','.join('?' for _ in NIGHT_MARKET_VENDORS),
            tuple(vendor['handle'] for vendor in NIGHT_MARKET_VENDORS)).fetchall()
        persona_ids = {row['handle']: row['id'] for row in persona_rows}
        for vendor in payload['vendors']:
            vendor['persona_id'] = persona_ids.get(vendor.get('handle'))
        self.send_json(payload)

    @atomic_endpoint
    def api_nightmarket_reserve(self, conn, qs, m, body):
        user = self.require_gm(conn)
        allowed = {'item_id', 'character_id', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Market reserve содержит неподдерживаемые поля')
        item_id = str((body or {}).get('item_id') or '').strip()
        character_id = _num((body or {}).get('character_id'))
        note = str((body or {}).get('note') or '').strip()[:200]
        if not item_by_id(item_id):
            raise ApiError(400, 'Неизвестный предмет Night Market')
        ensure_market_stock(conn)
        day = nm_day()
        state_row = conn.execute(
            'SELECT * FROM market_stock WHERE market_day=? AND item_id=?',
            (day, item_id)).fetchone()
        if not state_row:
            raise ApiError(400, 'Предмет не в текущем Night Market')
        if character_id:
            target = self.get_char(conn, character_id)
            if parse_json_object(target['data']).get('archived'):
                raise ApiError(409, 'Досье зарезервированного персонажа заархивировано')
            conn.execute(
                'UPDATE market_stock SET reserved_character_id=?,reserved_note=?,updated=? '
                'WHERE market_day=? AND item_id=?',
                (target['id'], note, time.time(), day, item_id))
        else:
            conn.execute(
                'UPDATE market_stock SET reserved_character_id=NULL,reserved_note=?,updated=? '
                'WHERE market_day=? AND item_id=?',
                (note, time.time(), day, item_id))
        conn.commit()
        self.send_json({'ok': True, 'item_id': item_id,
                        'reserved_character_id': character_id})

    @atomic_endpoint
    def api_fixer_request_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        allowed = {'char_id', 'item_id', 'item_name', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Fixer request содержит неподдерживаемые поля')
        row = self.get_char(conn, (body or {}).get('char_id'))
        if row['owner_id'] != user['id'] and not user_is_gm(user):
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        item_id = str((body or {}).get('item_id') or '').strip()
        item_name = str((body or {}).get('item_name') or '').strip()[:160]
        note = str((body or {}).get('note') or '').strip()[:1000]
        if not item_id and len(item_name) < 2:
            raise ApiError(400, 'Укажите предмет или название запроса')
        if item_id and not item_by_id(item_id):
            raise ApiError(400, 'Неизвестный предмет для запроса')
        if item_id:
            item_name = item_by_id(item_id)['name']
        now = time.time()
        cur = conn.execute(
            'INSERT INTO fixer_requests(character_id,requested_by,item_id,item_name,'
            'note,status,created,updated) VALUES(?,?,?,?,?,?,?,?)',
            (row['id'], user['id'], item_id or None, item_name, note, 'pending', now, now))
        conn.commit()
        self.send_json({'ok': True, 'request_id': cur.lastrowid}, status=201)

    def api_fixer_requests(self, conn, qs, m, body):
        user = self.require_user(conn)
        base = ('SELECT f.*,u.display_name requester,c.data character_data '
                'FROM fixer_requests f JOIN users u ON u.id=f.requested_by '
                'JOIN characters c ON c.id=f.character_id ')
        if user_is_gm(user):
            rows = conn.execute(
                base + "ORDER BY (f.status='pending') DESC,f.created DESC,f.id DESC LIMIT 300").fetchall()
        else:
            rows = conn.execute(
                base + 'WHERE f.requested_by=? '
                'ORDER BY f.created DESC,f.id DESC LIMIT 300', (user['id'],)).fetchall()
        payload = []
        for row in rows:
            item = dict(row)
            character_data = parse_json_object(item.pop('character_data'))
            item['character_name'] = character_data.get('handle') or 'Unknown Edgerunner'
            payload.append(item)
        self.send_json({'requests': payload})

    @atomic_endpoint
    def api_fixer_request_resolve(self, conn, qs, m, body):
        user = self.require_gm(conn)
        request = conn.execute('SELECT * FROM fixer_requests WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not request:
            raise ApiError(404, 'Запрос Fixer не найден')
        if request['status'] != 'pending':
            raise ApiError(409, 'Запрос Fixer уже обработан')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in ('fulfill', 'decline'):
            raise ApiError(400, 'Fixer resolve action: fulfill/decline')
        note = str((body or {}).get('note') or '').strip()[:1000]
        now = time.time()
        if action == 'decline':
            conn.execute('UPDATE fixer_requests SET status=?,resolved_by=?,resolved_at=?,'
                         'resolution_note=?,updated=? WHERE id=?',
                         ('declined', user['id'], now, note, now, request['id']))
            conn.commit()
            self.send_json({'ok': True, 'action': action})
            return
        row = self.get_char(conn, request['character_id'])
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Досье заказчика заархивировано')
        before = json.loads(row['data'])
        data = copy.deepcopy(before)
        ensure_character_item_instances(data)
        ensure_progression(data)
        try:
            qty = max(1, min(99, int((body or {}).get('qty') or 1)))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        raw_price = (body or {}).get('price')
        item_id = str((body or {}).get('grant_item_id') or request['item_id'] or '').strip()
        if item_id and item_by_id(item_id):
            it = item_by_id(item_id)
            if raw_price is None:
                price = it.get('price') or 0
            else:
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректная цена Fixer')
            price = max(0.0, min(9_999_999.0, price))
            if price * qty > float(data.get('cash') or 0) + 1e-9:
                raise ApiError(400, f'Не хватает €$: нужно {price * qty:,.0f}, '
                                    f'есть {float(data.get("cash") or 0):,.0f}')
            owned = {
                'key': it['id'], 'catalog_item_id': it['id'], 'cat': it['cat'],
                'name': it['name'], 'price': price, 'qty': 1, 'state': 'carried',
                'damage': it.get('damage'), 'sp': it.get('sp'), 'hl': it.get('hl'),
                'fields': copy.deepcopy(it.get('fields') or {}),
                'mechanics': copy.deepcopy(it.get('mechanics') or {}),
                'source': it.get('source'), 'acquisition_source': 'fixer',
            }
            owned.update(catalog_interaction_data(it))
            owned.update({key: copy.deepcopy(it[key]) for key in ITEM_MODIFICATION_FIELDS if key in it})
            coverage = item_effect_coverage(it.get('id'))
            if coverage:
                owned['effect_coverage'] = coverage
            inv = data.setdefault('inventory', [])
            if item_entry_stackable(owned):
                owned['instance_id'] = new_item_instance_id()
                owned['qty'] = qty
                if it['cat'] == 'ammo':
                    owned['ammo_rounds'] = qty * ammo_pack_size(owned)
                inv.append(owned)
            else:
                if len(inv) + qty > 500:
                    raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
                for _ in range(qty):
                    instance = copy.deepcopy(owned)
                    instance['instance_id'] = new_item_instance_id()
                    inv.append(instance)
        else:
            name = str(request['item_name'] or (body or {}).get('item_name') or '').strip()[:120]
            if len(name) < 2:
                raise ApiError(400, 'Укажите название выдаваемого предмета')
            if raw_price is None:
                price = 0.0
            else:
                try:
                    price = float(raw_price)
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректная цена Fixer')
            price = max(0.0, min(9_999_999.0, price))
            if price * qty > float(data.get('cash') or 0) + 1e-9:
                raise ApiError(400, f'Не хватает €$: нужно {price * qty:,.0f}, '
                                    f'есть {float(data.get("cash") or 0):,.0f}')
            owned = {
                'is_custom': True, 'key': 'custom', 'cat': 'custom', 'name': name,
                'custom_name': name, 'price': price, 'qty': qty, 'state': 'carried',
                'stackable': False, 'desc': '', 'source': 'Fixer Request',
                'manual_resolution_required': True, 'acquisition_source': 'fixer',
                'acquisition_note': str(note or '')[:160],
            }
            owned['instance_id'] = new_item_instance_id()
            data.setdefault('inventory', []).append(owned)
        data['cash'] = round(float(data.get('cash') or 0) - price * qty, 2)
        persist_character_item_instances(
            conn, row['id'], data, 'fixer_request', source_ref=f'fixer:{request["id"]}')
        record_character_changes(conn, row['id'], user['id'], before, data,
                                 f'Fixer request #{request["id"]}: {request["item_name"]}')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, row['id']))
        conn.execute('UPDATE fixer_requests SET status=?,resolved_by=?,resolved_at=?,'
                     'resolution_note=?,updated=? WHERE id=?',
                     ('fulfilled', user['id'], now, note, now, request['id']))
        conn.commit()
        self.send_json({'ok': True, 'action': action})

    # ------------------------------------------------------------ персонажи

    CHAR_LIST_FIELDS = ('id', 'owner_id', 'public', 'created', 'updated')

    def _reputation_for(self, character_id, conn, public_view):
        if conn is None:
            return []
        try:
            rows = conn.execute(
                'SELECT cr.*,p.display_name org_name,p.handle org_handle '
                'FROM character_reputation cr JOIN personas p ON p.id=cr.organization_persona_id '
                'WHERE cr.character_id=? ORDER BY cr.updated DESC', (int(character_id),)).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []

    def char_payload(self, row, owner_name=None, public_view=False, conn=None):
        full_data = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        visibility = ensure_character_visibility(full_data)
        data = public_character_data(full_data) if public_view else full_data
        active_effects = character_effect_instances(conn, row['id']) if conn is not None else []
        derived = derive(full_data, active_effects)
        if conn is not None:
            modifications = character_modifications(conn, row['id'])
            derived['modifications'] = modifications
            derived['effective_weapons'] = character_effective_weapons(
                full_data, modifications)
            derived['effective_vehicles'] = character_effective_vehicles(
                full_data, modifications)
            derived['effective_cyberdecks'] = character_effective_cyberdecks(
                full_data, modifications)
            derived['tech_maker'] = tech_maker_payload(full_data)
            derived['campaign_services'] = character_campaign_services(full_data, conn)
            derived['campaign_time'] = campaign_now(conn)
            derived['loans'] = character_open_loans(conn, row['id'])
            derived['downtime'] = downtime_payload(full_data, conn=conn)
        if public_view:
            derived.pop('loans', None)
            derived.pop('downtime', None)
        if public_view and not visibility['combat']:
            derived = {}
        elif public_view:
            if not visibility['equipment']:
                for private_key in ('modifications', 'effective_weapons',
                                    'effective_vehicles', 'effective_cyberdecks',
                                    'effective_cyberware', 'effective_armor_hosts',
                                    'tech_maker', 'campaign_services', 'downtime'):
                    derived.pop(private_key, None)
            for effect in (derived.get('effects') or {}).get('instances') or []:
                for private_key in ('reason', 'actor', 'source_item_instance_id'):
                    effect.pop(private_key, None)
            for modification in derived.get('modifications') or []:
                for private_key in ('notes', 'installer', 'configuration'):
                    modification.pop(private_key, None)
            for armor_host in (derived.get('effective_armor_hosts') or {}).get('hosts', []):
                tech_upgrade = armor_host.get('tech_upgrade')
                if isinstance(tech_upgrade, dict):
                    for private_key in ('tech_name', 'installed_by', 'reason'):
                        tech_upgrade.pop(private_key, None)
                tech_maker = armor_host.get('tech_maker_modification')
                if isinstance(tech_maker, dict):
                    for private_key in ('tech_name', 'installed_by', 'reason', 'notes'):
                        tech_maker.pop(private_key, None)
            for vehicle in (derived.get('effective_vehicles') or {}).values():
                repair_state = vehicle.get('state') or {}
                if isinstance(repair_state.get('repair'), dict):
                    repair_state['repair'].pop('technician', None)
                for repair in repair_state.get('repair_history') or []:
                    if isinstance(repair, dict):
                        repair.pop('technician', None)
                tech_maker = vehicle.get('tech_maker_modification')
                if isinstance(tech_maker, dict):
                    for private_key in ('tech_name', 'installed_by', 'reason', 'notes'):
                        tech_maker.pop(private_key, None)
            for mod in (derived.get('tech_maker') or {}).get('modifications') or []:
                for private_key in ('tech_name', 'reason', 'notes'):
                    mod.pop(private_key, None)
            for deck in (derived.get('effective_cyberdecks') or {}).values():
                for program in deck.get('programs') or []:
                    entity = program.get('net_entity')
                    if isinstance(entity, dict):
                        for private_key in ('floor_label', 'target_label',
                                            'owner_character_id', 'initiative_roll',
                                            'session_id', 'session_floor_id',
                                            'session_node_id', 'session_node_label',
                                            'target_combatant_id'):
                            entity.pop(private_key, None)
        return {
            'id': row['id'], 'revision': _row_value(row, 'revision', 0),
            'owner_id': row['owner_id'] if (not public_view or owner_name) else None,
            'public': bool(row['public']),
            'owner_name': owner_name, 'created': row['created'], 'updated': row['updated'],
            'data': data, 'derived': derived,
            'reputation': self._reputation_for(row['id'], conn, public_view),
        }

    def api_my_characters(self, conn, qs, m, body):
        u = self.require_user(conn)
        rows = conn.execute(
            'SELECT * FROM characters WHERE owner_id=? ORDER BY updated DESC',
            (u['id'],)).fetchall()
        self.send_json({'characters': [self.char_payload(r, u['display_name'], conn=conn) for r in rows]})

    @atomic_endpoint
    def api_create_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        data = clean_character(body.get('data') if isinstance(body, dict) else body)
        validate_creation(data)
        # Client-provided IDs are never trusted for a new Dossier. Durable items
        # become separate owned instances; clearly stackable ammunition stays one row.
        ensure_character_item_instances(data, regenerate=True)
        if len(data.get('inventory') or []) + len(data.get('cyberware') or []) > 500:
            raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
        ensure_progression(data)
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
        persist_character_item_instances(
            conn, cur.lastrowid, data, 'character_creation', acquired_at=now, prune=True)
        record_character_changes(conn, cur.lastrowid, u['id'], {}, data, 'Character created')
        conn.commit()
        row = conn.execute('SELECT * FROM characters WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.char_payload(row, u['display_name'], conn=conn), status=201)

    def api_pdf_import(self, conn, qs, m, body):
        """Parse a fillable PDF character sheet and return draft character data."""
        user = self.require_user(conn)
        pdf_b64 = str((body or {}).get('pdf') or '')
        if not pdf_b64:
            raise ApiError(400, 'PDF обязателен (base64)')
        try:
            pdf_bytes = base64.b64decode(pdf_b64)
        except Exception:
            raise ApiError(400, 'Некорректный base64')
        if len(pdf_bytes) < 100 or not pdf_bytes[:5].startswith(b'%PDF'):
            raise ApiError(400, 'Файл не является PDF')
        if len(pdf_bytes) > 5_000_000:
            raise ApiError(413, 'PDF слишком большой (макс 5 МБ)')
        try:
            sys.path.insert(0, BASE)
            import pdf_import
            result = pdf_import.import_pdf(pdf_bytes)
        except ValueError as e:
            raise ApiError(400, str(e))
        except Exception as e:
            raise ApiError(500, 'Ошибка парсинга PDF')
        self.send_json(result)

    @atomic_endpoint
    def api_character_import(self, conn, qs, m, body):
        u = self.require_user(conn)
        raw = (body or {}).get('data')
        if raw is None:
            raw = (body or {})
        data = canonical_import_character(raw)
        owned_rows = conn.execute('SELECT data FROM characters WHERE owner_id=?',
                                  (u['id'],)).fetchall()
        count = sum(1 for item in owned_rows if not parse_json_object(item['data']).get('archived'))
        if count >= 50:
            raise ApiError(400, 'Слишком много персонажей (максимум 50)')
        now = time.time()
        cur = conn.execute(
            'INSERT INTO characters(owner_id, public, data, created, updated) VALUES(?,?,?,?,?)',
            (u['id'], 0, json.dumps(data, ensure_ascii=False), now, now))
        persist_character_item_instances(
            conn, cur.lastrowid, data, 'character_import', acquired_at=now, prune=True)
        record_character_changes(conn, cur.lastrowid, u['id'], {}, data,
                                 'Character imported from JSON')
        conn.commit()
        row = conn.execute('SELECT * FROM characters WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.char_payload(row, u['display_name'], conn=conn), status=201)

    def get_char(self, conn, cid):
        try:
            cid = int(cid)
        except (TypeError, ValueError):
            raise ApiError(404, 'Персонаж не найден')
        row = conn.execute(
            'SELECT c.*,u.display_name owner,u.show_display_name owner_show_name '
            'FROM characters c JOIN users u ON u.id=c.owner_id WHERE c.id=?',
            (cid,)).fetchone()
        if not row:
            raise ApiError(404, 'Персонаж не найден')
        return row

    def api_get_character(self, conn, qs, m, body):
        row = self.get_char(conn, m.group(1))
        user = self.current_user(conn)
        owner_view = bool(user and user['id'] == row['owner_id'])
        admin_view = user_is_admin(user)
        if not row['public'] and not (owner_view or admin_view):
            raise ApiError(403, 'Персонаж приватный')
        privileged_name = bool(owner_view or user_is_gm(user))
        owner_name = row['owner'] if (privileged_name or row['owner_show_name']) else None
        self.send_json(self.char_payload(
            row, owner_name, public_view=not (owner_view or admin_view), conn=conn))

    @atomic_endpoint
    def api_save_character(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, m.group(1))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        old_data = json.loads(row['data'])
        if old_data.get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        expected_revision = _num((body or {}).get('revision'))
        if expected_revision is None:
            raise ApiError(428, 'Укажите revision Dossier')
        if expected_revision != (_row_value(row, 'revision', 0) or 0):
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        patch = clean_character_profile_patch(old_data, body or {})
        data = dict(old_data)
        data.update(patch)
        pub = 1 if patch.get('public', bool(row['public'])) else 0
        data['public'] = bool(pub)
        old_media = str(old_data.get('portrait_media_id') or '')
        new_media = str(data.get('portrait_media_id') or '')
        if old_media and old_media != new_media:
            conn.execute("UPDATE media SET attached_type=NULL, attached_id=NULL WHERE id=? AND owner_id=? AND attached_type='character' AND attached_id=?",
                         (old_media, u['id'], row['id']))
        attach_character_media(conn, u['id'], row['id'], data)
        record_character_changes(conn, row['id'], u['id'], old_data, data,
                                 str((body or {}).get('reason') or 'Dossier profile update'))
        conn.execute('UPDATE characters SET data=?,public=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), pub, time.time(), row['id']))
        conn.commit()
        row = self.get_char(conn, row['id'])
        self.send_json(self.char_payload(row, row['owner'], conn=conn))

    @atomic_endpoint
    def api_character_sheet_update(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        expected_revision = _num((body or {}).get('revision'))
        current_revision = _row_value(row, 'revision', 0) or 0
        if expected_revision is None:
            raise ApiError(428, 'Укажите revision Dossier')
        if expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason = str((body or {}).get('reason') or '').strip()
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения Character Sheet')
        before = json.loads(row['data'])
        after = clean_character_trust_update(before, (body or {}).get('data'))
        if before == after:
            raise ApiError(400, 'В Character Sheet нет изменений')
        validate_cyberware_trust_lifecycle(before, after)
        validate_bound_popup_weapon_references(after)
        validate_popup_shield_references(after)
        validate_armor_tech_references(after)
        validate_armor_repair_references(after)
        validate_tech_maker_references(after)
        validate_active_modification_references(conn, row['id'], after)
        sync_weapon_states_with_modifications(conn, row['id'], after)
        sync_vehicle_states_with_modifications(conn, row['id'], after)
        persist_character_item_instances(
            conn, row['id'], after, 'trust_audit_edit', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        record_character_change_set(
            conn, row['id'], user['id'], before, after, reason,
            current_revision, revision_after)
        conn.execute(
            'UPDATE characters SET data=?,public=?,updated=?,revision=? WHERE id=?',
            (json.dumps(after, ensure_ascii=False), 1 if after.get('public') else 0,
             time.time(), revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json(self.char_payload(fresh, fresh['owner'], conn=conn))

    @atomic_endpoint
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
            conn.execute('UPDATE characters SET public=0,data=?,updated=?,revision=revision+1 WHERE id=?',
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
        conn.execute('DELETE FROM item_modifications WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM item_instances WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM active_effect_instances WHERE character_id=?', (row['id'],))
        conn.execute('DELETE FROM characters WHERE id=?', (row['id'],))
        conn.commit()
        for media in media_rows:
            try: os.remove(os.path.join(UPLOAD_DIR, media['filename']))
            except FileNotFoundError: pass
        self.send_json({'ok': True, 'archived': False})

    def save_character_data(self, conn, row, data, actor_id=None, reason='Character progression'):
        if actor_id is not None:
            record_character_changes(conn, row['id'], actor_id, json.loads(row['data']), data, reason)
        conn.execute('UPDATE characters SET data=?,public=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), 1 if data.get('public') else 0,
                      time.time(), row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        return self.char_payload(fresh, fresh['owner'], conn=conn)

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

    @atomic_endpoint
    def api_character_ip(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = self.get_char(conn, m.group(1))
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
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
        current_revision = _row_value(row, 'revision', 0) or 0
        entries = conn.execute(
            'SELECT l.*,u.display_name actor FROM character_ledger l '
            'JOIN users u ON u.id=l.actor_user_id WHERE character_id=? '
            'ORDER BY l.id DESC LIMIT 500', (row['id'],)).fetchall()
        payload = []
        for raw in entries:
            item = dict(raw)
            delta = parse_json_object(item.get('delta_json'))
            item['delta'] = delta
            item['changes'] = delta.get('changes') if isinstance(delta.get('changes'), list) else []
            item['can_revert'] = bool(
                delta.get('revertible') and
                _num(delta.get('revision_after')) == current_revision and
                item['category'] in (
                    'sheet_update', 'sheet_revert', 'item_action', 'modification', 'vehicle'))
            item['has_snapshot'] = bool(item.get('before_json'))
            item.pop('before_json', None)
            item.pop('after_json', None)
            item.pop('delta_json', None)
            payload.append(item)
        self.send_json({'entries': payload, 'current_revision': current_revision})

    @atomic_endpoint
    def api_character_ledger_revert(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        expected_revision = _num((body or {}).get('revision'))
        current_revision = _row_value(row, 'revision', 0) or 0
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        entry = conn.execute(
            'SELECT * FROM character_ledger WHERE id=? AND character_id=?',
            (int(m.group(2)), row['id'])).fetchone()
        if not entry or entry['category'] not in (
                'sheet_update', 'sheet_revert', 'item_action', 'modification', 'vehicle'):
            raise ApiError(404, 'Изменение Character Sheet не найдено')
        delta = parse_json_object(entry['delta_json'])
        if (not delta.get('revertible') or
                _num(delta.get('revision_after')) != current_revision):
            raise ApiError(409, 'Откат доступен только до следующего изменения Dossier')
        try:
            target = json.loads(entry['before_json'])
        except (TypeError, ValueError, json.JSONDecodeError):
            raise ApiError(409, 'Snapshot для отката повреждён')
        if not isinstance(target, dict):
            raise ApiError(409, 'Snapshot для отката повреждён')
        before = json.loads(row['data'])
        now = time.time()
        session_net_change = delta.get('session_net_change')
        if isinstance(session_net_change, dict):
            session_id = _num(session_net_change.get('session_id'))
            session_before = session_net_change.get('before')
            session_after = session_net_change.get('after')
            session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                   (session_id,)).fetchone() if session_id else None
            if (not session or not isinstance(session_before, dict) or
                    not isinstance(session_after, dict)):
                raise ApiError(409, 'Session NET snapshot для отката повреждён')
            clean_session_before = session_net_state(session_before)
            clean_session_after = session_net_state(session_after)
            current_session_net = session_net_state(
                _row_value(session, 'net_state_json', '{}'))
            if current_session_net != clean_session_after:
                raise ApiError(409, 'Session NET context изменён после Character action')
            conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                         (json.dumps(clean_session_before, ensure_ascii=False), now,
                          session['id']))
            conn.execute(
                'INSERT INTO session_activity(session_id,actor_user_id,event_type,note,created) '
                'VALUES(?,?,?,?,?)',
                (session['id'], user['id'], 'net_entity_revert',
                 f'Revert character ledger #{entry["id"]}', now))
        for effect_id in delta.get('created_effect_ids') or []:
            conn.execute(
                'UPDATE active_effect_instances SET active=0,archived_at=?,updated=? '
                'WHERE effect_id=? AND character_id=?',
                (now, now, str(effect_id), row['id']))
        for effect_id in delta.get('replaced_effect_ids') or []:
            replaced = conn.execute(
                'SELECT * FROM active_effect_instances WHERE effect_id=? AND character_id=?',
                (str(effect_id), row['id'])).fetchone()
            if not replaced or replaced['archived_at']:
                continue
            if replaced['duration_type'] == 'real_time' and replaced['expires_at'] is not None and replaced['expires_at'] <= now:
                continue
            if replaced['duration_type'] == 'rounds' and (_num(replaced['remaining_rounds']) or 0) <= 0:
                continue
            conn.execute('UPDATE active_effect_instances SET active=1,updated=? WHERE effect_id=?',
                         (now, str(effect_id)))
        for modification_id in delta.get('created_modification_ids') or []:
            conn.execute(
                'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                'WHERE modification_id=? AND character_id=?',
                (user['id'], now, now, str(modification_id), row['id']))
        for modification_id in delta.get('removed_modification_ids') or []:
            conn.execute(
                'UPDATE item_modifications SET active=1,removed_by=NULL,removed_at=NULL,updated=? '
                'WHERE modification_id=? AND character_id=?',
                (now, str(modification_id), row['id']))
        ensure_character_item_instances(target)
        ensure_progression(target)
        validate_armor_tech_references(target)
        validate_armor_repair_references(target)
        validate_tech_maker_references(target)
        validate_bound_popup_weapon_references(target)
        validate_popup_shield_references(target)
        validate_active_modification_references(conn, row['id'], target)
        sync_weapon_states_with_modifications(conn, row['id'], target)
        sync_vehicle_states_with_modifications(conn, row['id'], target)
        persist_character_item_instances(
            conn, row['id'], target, 'ledger_revert',
            source_ref=f'ledger:{entry["id"]}', prune=True)
        revision_after = current_revision + 1
        reason = str((body or {}).get('reason') or '').strip()
        reason = reason[:500] or f'Revert ledger entry #{entry["id"]}'
        revert_ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, target, reason,
            current_revision, revision_after, category='sheet_revert',
            reverts_ledger_id=entry['id'])
        if (delta.get('created_effect_ids') or delta.get('replaced_effect_ids') or
                delta.get('created_modification_ids') or delta.get('removed_modification_ids') or
                session_net_change):
            revert_delta_row = conn.execute(
                'SELECT delta_json FROM character_ledger WHERE id=?',
                (revert_ledger_id,)).fetchone()
            revert_delta = parse_json_object(revert_delta_row['delta_json'])
            revert_delta['revertible'] = False
            revert_delta['effect_linked_revert'] = True
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(revert_delta, ensure_ascii=False), revert_ledger_id))
        conn.execute(
            'UPDATE characters SET data=?,public=?,updated=?,revision=? WHERE id=?',
            (json.dumps(target, ensure_ascii=False), 1 if target.get('public') else 0,
             time.time(), revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json(self.char_payload(fresh, fresh['owner'], conn=conn))

    def api_character_items(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        instances = conn.execute(
            'SELECT * FROM item_instances WHERE character_id=? '
            'ORDER BY bucket,acquired_at,instance_id', (row['id'],)).fetchall()
        payload = []
        for instance in instances:
            item = dict(instance)
            item['item'] = parse_json_object(item.pop('data_json'))
            payload.append(item)
        self.send_json({'character_id': row['id'], 'instances': payload})

    def modification_management_payload(self, conn, row):
        data = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        owned = {entry.get('instance_id'): entry for bucket in ('inventory', 'cyberware')
                 for entry in data.get(bucket) or [] if isinstance(entry, dict) and entry.get('instance_id')}
        modifications = character_modifications(conn, row['id'])
        hosts = []
        for host in (entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('cat') == 'guns'):
            active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
            pools = weapon_slot_capacity(host, active, owned)
            host_summary = {
                'instance_id': host.get('instance_id'), 'name': host.get('custom_name') or host.get('name'),
                'catalog_item_id': catalog_item_id_for_entry(host), 'state': host.get('state'),
                'weapon_type': (host.get('mechanics') or {}).get('type'),
                'skill': (host.get('mechanics') or {}).get('skill'),
                'exotic': weapon_is_exotic(host),
                'slots_total': sum(pool['total'] for pool in pools.values()),
                'slots_used': sum(pool['used'] for pool in pools.values()),
                'slot_pools': pools,
                'modification_ids': [mod['modification_id'] for mod in active],
            }
            hosts.append(host_summary)
        upgrades = []
        for upgrade in (entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and entry.get('cat') == 'gun_upgrades'):
            matrix = {}
            configuration_by_host = {}
            for host in (entry for entry in data.get('inventory') or []
                         if isinstance(entry, dict) and entry.get('cat') == 'guns'):
                active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
                matrix[host['instance_id']] = weapon_upgrade_compatibility(
                    host, upgrade, active, owned)
                configuration_by_host[host['instance_id']] = weapon_modification_configuration_schema(
                    catalog_item_id_for_entry(upgrade), host)
            upgrades.append({
                'instance_id': upgrade.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(upgrade),
                'name': upgrade.get('custom_name') or upgrade.get('name'),
                'state': upgrade.get('state'), 'slots_used': upgrade.get('slots_used') or 0,
                'permanent_installation': bool(upgrade.get('permanent_installation')),
                'compatibility_manual': bool(upgrade.get('compatibility_manual')),
                'compatibility_text': upgrade.get('compatibility_text') or '',
                'configuration_schemas': weapon_modification_configuration_schema(
                    catalog_item_id_for_entry(upgrade)),
                'configuration_by_host': configuration_by_host,
                'compatibility': matrix,
            })
        effective_vehicle_map = character_effective_vehicles(data, modifications)
        vehicle_hosts = []
        for host in (entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('cat') == 'vehicles'):
            active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
            mechanics = host.get('mechanics') or {}
            vehicle_effective = effective_vehicle_map.get(host.get('instance_id')) or {}
            vehicle_hosts.append({
                'instance_id': host.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(host),
                'name': host.get('custom_name') or host.get('name'),
                'state': host.get('state'), 'classes': sorted(vehicle_classification(host)),
                'sdp': mechanics.get('sdp'), 'sp': mechanics.get('sp'),
                'seats': mechanics.get('seats'),
                'combat_speed': mechanics.get('combat_speed'),
                'narrative_speed': mechanics.get('narrative_speed'),
                'nomad_access': mechanics.get('nomad_access'),
                'base': vehicle_effective.get('base') or mechanics,
                'effective': vehicle_effective.get('effective') or mechanics,
                'vehicle_state': vehicle_effective.get('state') or {},
                'effect_sources': vehicle_effective.get('sources') or [],
                'nos_tanks': vehicle_effective.get('nos_tanks') or [],
                'mounted_weapons': vehicle_effective.get('mounted_weapons') or [],
                'weapon_mounts': vehicle_effective.get('weapon_mounts') or [],
                'interior': vehicle_effective.get('interior') or {},
                'cargo_modules': vehicle_effective.get('cargo_modules') or [],
                'modification_ids': [mod['modification_id'] for mod in active],
            })
        vehicle_upgrades = []
        for upgrade in (entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and entry.get('cat') == 'vehicles_upgrades'):
            matrix = {}
            for host in (entry for entry in data.get('inventory') or []
                         if isinstance(entry, dict) and entry.get('cat') == 'vehicles'):
                active = [mod for mod in modifications if mod['host_instance_id'] == host.get('instance_id')]
                matrix[host['instance_id']] = vehicle_upgrade_compatibility(
                    host, upgrade, active, owned, data)
            vehicle_upgrades.append({
                'instance_id': upgrade.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(upgrade),
                'name': upgrade.get('custom_name') or upgrade.get('name'),
                'state': upgrade.get('state'),
                'availability_text': upgrade.get('availability_text') or '',
                'nomad_access_required': upgrade.get('nomad_access_required'),
                'repeatable_max': upgrade.get('repeatable_max') or 1,
                'permanent_installation': bool(upgrade.get('permanent_installation')),
                'compatibility_manual': bool(upgrade.get('compatibility_manual')),
                'configuration_schemas': vehicle_modification_configuration_schema(
                    catalog_item_id_for_entry(upgrade)),
                'compatibility': matrix,
            })
        effective_deck_map = character_effective_cyberdecks(data, modifications)
        cyberdeck_hosts = []
        deck_entries = [
            entry for entry in data.get('inventory') or []
            if isinstance(entry, dict) and entry.get('cat') == 'net_stuff' and
            (entry.get('mechanics') or {}).get('type') == 'Cyberdeck']
        for host in deck_entries:
            effective = effective_deck_map.get(host.get('instance_id')) or {}
            cyberdeck_hosts.append({
                'instance_id': host.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(host),
                'name': host.get('custom_name') or host.get('name'),
                'state': host.get('state'),
                'slot_pools': effective.get('pools') or {},
                'slots_total': effective.get('slots_total') or 0,
                'slots_used': effective.get('slots_used') or 0,
                'hardware': effective.get('hardware') or [],
                'programs': effective.get('programs') or [],
                'modification_ids': [
                    mod['modification_id'] for mod in modifications
                    if mod.get('host_instance_id') == host.get('instance_id')],
            })
        cyberdeck_items = []
        for upgrade in (entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and
                        entry.get('host_type') == 'cyberdeck'):
            matrix = {}
            for host in deck_entries:
                active = [mod for mod in modifications
                          if mod.get('host_instance_id') == host.get('instance_id')]
                matrix[host['instance_id']] = cyberdeck_item_compatibility(
                    host, upgrade, active, owned)
            cyberdeck_items.append({
                'instance_id': upgrade.get('instance_id'),
                'catalog_item_id': catalog_item_id_for_entry(upgrade),
                'name': upgrade.get('custom_name') or upgrade.get('name'),
                'state': upgrade.get('state'),
                'item_kind': upgrade.get('modification_kind'),
                'program_class': (upgrade.get('mechanics') or {}).get('program_class'),
                'slots_used': upgrade.get('slots_used') or 1,
                'compatibility': matrix,
            })
        for modification in modifications:
            config = modification.get('configuration') or {}
            modification['host_name'] = (owned.get(modification['host_instance_id']) or {}).get('custom_name') or (owned.get(modification['host_instance_id']) or {}).get('name') or config.get('host_name')
            modification['upgrade_name'] = (owned.get(modification['upgrade_instance_id']) or {}).get('custom_name') or (owned.get(modification['upgrade_instance_id']) or {}).get('name') or config.get('upgrade_name')
        return {
            'character_id': row['id'], 'revision': _row_value(row, 'revision', 0) or 0,
            'hosts': hosts, 'upgrades': upgrades,
            'vehicle_hosts': vehicle_hosts, 'vehicle_upgrades': vehicle_upgrades,
            'cyberdeck_hosts': cyberdeck_hosts, 'cyberdeck_items': cyberdeck_items,
            'modifications': modifications,
        }

    def api_character_modifications(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        self.send_json(self.modification_management_payload(conn, row))

    @atomic_endpoint
    def api_character_modification_install(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {'revision', 'host_instance_id', 'upgrade_instance_id',
                              'manual_confirm', 'configuration', 'reason', 'notes'}:
            raise ApiError(400, 'Modification содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        host_id = str((body or {}).get('host_instance_id') or '').lower()
        upgrade_id = str((body or {}).get('upgrade_instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(host_id) or not INSTANCE_ID_RE.fullmatch(upgrade_id):
            raise ApiError(400, 'Некорректный host или upgrade instance')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину установки modification')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {entry.get('instance_id'): entry for entry in data.get('inventory') or []
                 if isinstance(entry, dict) and entry.get('instance_id')}
        host, upgrade = owned.get(host_id), owned.get(upgrade_id)
        if not host or not upgrade:
            raise ApiError(404, 'Host или upgrade не найден в Inventory')
        if host.get('state') in ('stored', 'broken', 'consumed'):
            raise ApiError(409, 'Host должен быть исправен и находиться при персонаже')
        if host.get('installed_cyberware_instance_id'):
            raise ApiError(409, 'Permanent Popup Weapon attachments нельзя изменять')
        if upgrade.get('state') != 'carried':
            raise ApiError(409, 'Upgrade должен находиться в состоянии carried')
        host_type = str(upgrade.get('host_type') or '')
        active = [mod for mod in character_modifications(conn, row['id'])
                  if mod['host_instance_id'] == host_id]
        if host_type == 'weapon':
            choices = clean_weapon_modification_choices(
                catalog_item_id_for_entry(upgrade), (body or {}).get('configuration'), host)
            compatibility = weapon_upgrade_compatibility(host, upgrade, active, owned)
            effect_rules = weapon_modification_rules_for_catalog(
                catalog_item_id_for_entry(upgrade))
        elif host_type == 'vehicle':
            choices = clean_vehicle_modification_choices(
                catalog_item_id_for_entry(upgrade), (body or {}).get('configuration'))
            compatibility = vehicle_upgrade_compatibility(
                host, upgrade, active, owned, data)
            effect_rules = vehicle_modification_rules_for_catalog(
                catalog_item_id_for_entry(upgrade))
        elif host_type == 'cyberdeck':
            if (body or {}).get('configuration') not in (None, {}):
                raise ApiError(400, 'Cyberdeck configuration пока не поддерживается')
            choices = {}
            compatibility = cyberdeck_item_compatibility(
                host, upgrade, active, owned)
            effect_rules = []
        else:
            raise ApiError(400, 'Неподдерживаемый тип modification host')
        if not compatibility['allowed']:
            raise ApiError(400, 'Несовместимая модификация: ' + '; '.join(compatibility['reasons']))
        if compatibility['manual_resolution_required'] and not bool((body or {}).get('manual_confirm')):
            raise ApiError(409, 'Требуется ручное подтверждение сложного правила совместимости')
        modification_id = secrets.token_hex(16)
        now = time.time()
        configuration = {
            'host_catalog_item_id': catalog_item_id_for_entry(host),
            'upgrade_catalog_item_id': catalog_item_id_for_entry(upgrade),
            'host_name': host.get('custom_name') or host.get('name'),
            'upgrade_name': upgrade.get('custom_name') or upgrade.get('name'),
            'compatibility': compatibility,
            'manual_confirmed': bool((body or {}).get('manual_confirm')),
            'slot_pool': compatibility.get('slot_pool'),
            'grants_slots': copy.deepcopy(upgrade.get('grants_slots') or {}),
            'choices': choices,
            'effect_rules': effect_rules,
            'effects_rules_version': load_effect_rules().get('rules_version'),
        }
        profiles = weapon_profiles_from_rules(configuration['effect_rules'])
        if profiles:
            profile = profiles[0]
            data.setdefault('modification_state', {})[modification_id] = {
                'profile_id': profile['id'],
                'magazine': 0,
                'magazine_max': int(profile['magazine']),
                'reserve': 0,
            }
        elif host_type == 'vehicle':
            initial_state = initial_vehicle_modification_state(
                configuration['effect_rules'], data, choices)
            if initial_state:
                data.setdefault('modification_state', {})[modification_id] = initial_state
        elif host_type == 'cyberdeck':
            if upgrade.get('modification_kind') == 'cyberdeck_program':
                data.setdefault('program_state', {})[upgrade_id] = \
                    initial_program_runtime_state(
                        upgrade, host_id, modification_id)
            elif upgrade.get('name') == 'Backup Drive':
                data.setdefault('modification_state', {})[modification_id] = {
                    'resource_type': 'backup_drive', 'saved_programs': [],
                }
        conn.execute(
            'INSERT INTO item_modifications(modification_id,character_id,host_instance_id,'
            'upgrade_instance_id,host_type,slot_type,slots_used,active,permanent,'
            'configuration_json,notes,source_type,installed_by,installed_at,created,updated) '
            'VALUES(?,?,?,?,?,?,?,1,?,?,?,?,?,?,?,?)',
            (modification_id, row['id'], host_id, upgrade_id, host_type,
             compatibility.get('slot_pool') or upgrade.get('slot_type') or f'{host_type}_upgrade',
             int(upgrade.get('slots_used') or 0), 1 if upgrade.get('permanent_installation') else 0,
             json.dumps(configuration, ensure_ascii=False), str((body or {}).get('notes') or '')[:2000],
             upgrade.get('acquisition_source') or 'inventory', user['id'], now, now, now))
        upgrade['state'] = 'installed'
        upgrade['host_instance_id'] = host_id
        if host_type == 'weapon':
            sync_weapon_states_with_modifications(conn, row['id'], data)
        elif host_type == 'vehicle':
            sync_vehicle_states_with_modifications(conn, row['id'], data)
        revision_after = current_revision + 1
        persist_character_item_instances(conn, row['id'], data, 'modification_install')
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Install {configuration["upgrade_name"]} on {configuration["host_name"]}: {reason}',
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['created_modification_ids'] = [modification_id]
        if upgrade.get('permanent_installation'):
            delta['revertible'] = False
            delta['permanent_modification'] = True
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'modification_id': modification_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
            'management': self.modification_management_payload(conn, fresh),
        }, status=201)

    @atomic_endpoint
    def api_character_modification_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {
                'revision', 'action', 'reason', 'weapon_instance_id', 'ammo_instance_id'}:
            raise ApiError(400, 'Modification action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        modification_id = str(m.group(2)).lower()
        modification_row = conn.execute(
            'SELECT * FROM item_modifications WHERE modification_id=? AND character_id=?',
            (modification_id, row['id'])).fetchone()
        if not modification_row:
            raise ApiError(404, 'Modification не найдена')
        modification = item_modification_payload(modification_row)
        if not modification['active']:
            raise ApiError(409, 'Modification уже снята')
        action = str((body or {}).get('action') or '').lower()
        if 'weapon_instance_id' in (body or {}) and action != 'mount_weapon':
            raise ApiError(400, 'weapon_instance_id допустим только для mount_weapon')
        if 'ammo_instance_id' in (body or {}) and action != 'reload':
            raise ApiError(400, 'ammo_instance_id допустим только для Reload')
        if action in ('fire', 'reload', 'use_nos', 'reset_nos',
                      'mount_weapon', 'unmount_weapon'):
            before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
            data = copy.deepcopy(before)
            state = (data.get('modification_state') or {}).get(modification_id)
            config = modification.get('configuration') or {}
            owned = {entry.get('instance_id'): entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('instance_id')}
            upgrade = owned.get(modification['upgrade_instance_id']) or {}
            resource_rules = config.get('effect_rules')
            if not isinstance(resource_rules, list) or not resource_rules:
                rule_loader = (vehicle_modification_rules_for_catalog
                               if modification.get('host_type') == 'vehicle'
                               else weapon_modification_rules_for_catalog)
                resource_rules = rule_loader(
                    catalog_item_id_for_entry(upgrade) or
                    config.get('upgrade_catalog_item_id'))
            if modification.get('host_type') == 'vehicle':
                authoritative = initial_vehicle_modification_state(
                    resource_rules, data, config.get('choices') or {})
                state = normalize_vehicle_modification_state(state, authoritative)
                if state:
                    data.setdefault('modification_state', {})[modification_id] = state
            if not isinstance(state, dict) or not state.get('profile_id'):
                raise ApiError(400, 'Modification не имеет action resource profile')
            profile_label = config.get('upgrade_name') or state.get('profile_id')
            action_state = state
            reload_weapon = None
            action_reason = str((body or {}).get('reason') or '').strip()[:500]

            if action in ('mount_weapon', 'unmount_weapon'):
                if state.get('resource_type') != 'heavy_weapon_mount':
                    raise ApiError(400, 'Modification не является Vehicle Heavy Weapon Mount')
                if len(action_reason) < 3:
                    raise ApiError(400, 'Укажите причину изменения mounted weapon')
                if action == 'mount_weapon':
                    if state.get('weapon_instance_id'):
                        raise ApiError(409, 'Сначала снимите текущее mounted weapon')
                    weapon_instance_id = str(
                        (body or {}).get('weapon_instance_id') or '').lower()
                    if not INSTANCE_ID_RE.fullmatch(weapon_instance_id):
                        raise ApiError(400, 'Выберите конкретный экземпляр оружия')
                    weapon = owned.get(weapon_instance_id)
                    catalog_weapon = item_by_id(catalog_item_id_for_entry(weapon)) or {}
                    mechanics = catalog_weapon.get('mechanics') or {}
                    if not weapon or weapon.get('cat') != 'guns' or _num(mechanics.get('hands')) != 2:
                        raise ApiError(400, 'Крепление принимает только двуручное дальнобойное оружие')
                    if weapon.get('state') != 'carried' or weapon.get('mounted_modification_id'):
                        raise ApiError(409, 'Оружие должно быть свободным и находиться в carried')
                    state['weapon_instance_id'] = weapon_instance_id
                    weapon.update({
                        'state': 'installed',
                        'mounted_modification_id': modification_id,
                        'mounted_vehicle_id': modification['host_instance_id'],
                    })
                    sync_weapon_states_with_modifications(conn, row['id'], data)
                    profile_label = weapon.get('custom_name') or weapon.get('name') or 'Weapon'
                    reason = f'Mount {profile_label} on Vehicle Heavy Weapon Mount: {action_reason}'
                else:
                    weapon_instance_id = str(state.get('weapon_instance_id') or '')
                    weapon = owned.get(weapon_instance_id)
                    if not weapon:
                        raise ApiError(409, 'Mounted weapon instance отсутствует')
                    profile_label = weapon.get('custom_name') or weapon.get('name') or 'Weapon'
                    state['weapon_instance_id'] = None
                    weapon['state'] = 'carried'
                    weapon.pop('mounted_modification_id', None)
                    weapon.pop('mounted_vehicle_id', None)
                    reason = f'Unmount {profile_label} from Vehicle Heavy Weapon Mount: {action_reason}'
            elif action in ('use_nos', 'reset_nos'):
                if state.get('resource_type') != 'nos_tank':
                    raise ApiError(400, 'Modification не является баллоном NOS')
                current = max(0, int(_num(state.get('uses_remaining')) or 0))
                maximum = max(1, int(_num(state.get('uses_max')) or 1))
                if action == 'use_nos':
                    if current <= 0:
                        raise ApiError(409, 'Баллон NOS уже использован в этот игровой день')
                    state['uses_remaining'] = current - 1
                    reason = f'Use {profile_label}: {current} → {state["uses_remaining"]}'
                else:
                    if len(action_reason) < 3:
                        raise ApiError(400, 'Укажите причину сброса NOS')
                    if current >= maximum:
                        raise ApiError(409, 'Баллон NOS уже готов к использованию')
                    state['uses_remaining'] = maximum
                    reason = f'Reset {profile_label}: {current} → {maximum}; {action_reason}'
            else:
                if state.get('resource_type') == 'nos_tank':
                    raise ApiError(400, 'Баллон NOS не является оружием')
                if state.get('resource_type') == 'heavy_weapon_mount':
                    weapon_instance_id = str(state.get('weapon_instance_id') or '')
                    weapon = owned.get(weapon_instance_id)
                    if not weapon:
                        raise ApiError(409, 'Сначала установите оружие в Vehicle Heavy Weapon Mount')
                    sync_weapon_states_with_modifications(conn, row['id'], data)
                    all_modifications = character_modifications(conn, row['id'])
                    weapon_modifications = [
                        item for item in all_modifications
                        if item.get('host_instance_id') == weapon_instance_id]
                    effective_weapon = evaluate_effective_weapon(
                        weapon, weapon_modifications, owned, data)
                    bound_profile = bound_vehicle_weapon_profile(
                        weapon, effective_weapon, data)
                    action_state = (data.get('weapon_state') or {}).get(weapon_instance_id) or {}
                    profile_label = weapon.get('custom_name') or weapon.get('name') or 'Weapon'
                    reload_weapon = weapon
                    ammo_cost = max(1, int(bound_profile.get('ammo_cost') or 1))
                else:
                    ammo_cost = max(1, int(_num(state.get('ammo_cost')) or 1))
                if action == 'fire':
                    maximum = max(0, int(_num(action_state.get('magazine_max')) or 0))
                    if maximum <= 0:
                        raise ApiError(409, 'Оружие не имеет отслеживаемого магазина')
                    current = max(0, int(_num(action_state.get('magazine')) or 0))
                    if current < ammo_cost:
                        raise ApiError(409, f'Для атаки требуется {ammo_cost} патронов')
                    action_state['magazine'] = current - ammo_cost
                    clear_loaded_ammo_if_empty(action_state)
                    reason = f'Fire {profile_label}: magazine {current} → {action_state["magazine"]}'
                else:
                    reload_ammo_kind = None if reload_weapon else \
                        ammo_kind_for_modification_profile(
                            resource_rules, state.get('profile_id'))
                    transfer = consume_shared_ammo(
                        data, action_state, (body or {}).get('ammo_instance_id'),
                        ammo_kind=reload_ammo_kind, weapon=reload_weapon)
                    reason = (
                        f'Reload {profile_label} with {transfer["ammo_name"]} '
                        f'×{transfer["moved"]}: magazine {action_state["magazine"]}')

            validate_active_modification_references(conn, row['id'], data)
            persist_character_item_instances(
                conn, row['id'], data, 'vehicle_action', source_ref=reason,
                prune=True)
            now = time.time()
            revision_after = current_revision + 1
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after,
                category='vehicle' if modification.get('host_type') == 'vehicle'
                else 'modification')
            conn.execute('UPDATE item_modifications SET updated=? WHERE modification_id=?',
                         (now, modification_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
            conn.commit()
            fresh = self.get_char(conn, row['id'])
            self.send_json({
                'ledger_id': ledger_id,
                'character': self.char_payload(fresh, fresh['owner'], conn=conn),
                'management': self.modification_management_payload(conn, fresh),
            })
            return
        if modification['permanent']:
            raise ApiError(409, 'Эта modification не может быть снята')
        if action != 'remove':
            raise ApiError(400, 'Неизвестное действие с modification')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину снятия modification')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        upgrade = next((entry for entry in data.get('inventory') or []
                        if isinstance(entry, dict) and entry.get('instance_id') == modification['upgrade_instance_id']), None)
        if not upgrade:
            raise ApiError(409, 'Upgrade instance отсутствует в Inventory')
        host = next((entry for entry in data.get('inventory') or []
                     if isinstance(entry, dict) and entry.get('instance_id') == modification['host_instance_id']), None)
        if host and host.get('installed_cyberware_instance_id'):
            raise ApiError(409, 'Permanent Popup Weapon attachments нельзя изменять')
        remaining_modifications = [item for item in character_modifications(conn, row['id'])
                                   if item['modification_id'] != modification_id]
        owned = {entry.get('instance_id'): entry for entry in data.get('inventory') or []
                 if isinstance(entry, dict) and entry.get('instance_id')}
        erased_backup_count = 0
        if host and modification.get('host_type') == 'weapon':
            remaining_pools = weapon_slot_capacity(host, remaining_modifications, owned)
            overloaded = [name for name, pool in remaining_pools.items()
                          if pool['used'] > pool['total']]
            if overloaded:
                raise ApiError(409, 'Сначала снимите modifications, зависящие от granted slots')
        elif host and modification.get('host_type') == 'cyberdeck':
            remaining_deck_modifications = [
                item for item in remaining_modifications
                if item.get('host_instance_id') == host.get('instance_id')]
            remaining_usage = cyberdeck_slot_usage(
                host, remaining_deck_modifications, owned)
            if remaining_usage['overloaded']:
                raise ApiError(409, 'Сначала освободите зависимые Cyberdeck slots')
            if upgrade.get('modification_kind') == 'cyberdeck_program':
                runtime = (data.get('program_state') or {}).get(
                    upgrade.get('instance_id')) or {}
                if runtime.get('status') in ('rezzed', 'derezzed'):
                    raise ApiError(409, 'Deactivate Program before Uninstall')
            if upgrade.get('name') == 'Backup Drive':
                backup_state = (data.get('modification_state') or {}).get(
                    modification_id) or {}
                erased_backup_count = len(backup_state.get('saved_programs') or [])
        elif host and modification.get('host_type') == 'vehicle':
            removed_name = str(upgrade.get('name') or '')
            removed_state = (data.get('modification_state') or {}).get(modification_id) or {}
            if (removed_state.get('resource_type') == 'heavy_weapon_mount' and
                    removed_state.get('weapon_instance_id')):
                raise ApiError(409, 'Сначала снимите оружие с Vehicle Heavy Weapon Mount')
            if removed_name == 'Housing Capacity':
                remaining_upgrades = [owned.get(item.get('upgrade_instance_id')) or {}
                                      for item in remaining_modifications]
                remaining_names = [str(item.get('name') or '')
                                   for item in remaining_upgrades]
                base_room_count = vehicle_base_interior(host)['base_rooms']
                remaining_room_upgrades = sum(
                    name in ('Luxury Vehicle Room', 'Complex Vehicle Room')
                    for name in remaining_names)
                if remaining_room_upgrades > base_room_count:
                    raise ApiError(409, 'Сначала снимите upgrades жилых комнат')
                remaining_mounts = sum(
                    name == 'Vehicle Heavy Weapon Mount' for name in remaining_names)
                if 'groundcar' in vehicle_classification(host) and remaining_mounts > 1:
                    raise ApiError(409, 'Housing Capacity требуется для нескольких Heavy Weapon Mounts')
            for remaining in remaining_modifications:
                dependent = owned.get(remaining.get('upgrade_instance_id')) or {}
                host_names = (dependent.get('prerequisite_host_names') or {}).get(removed_name) or []
                applies = not host_names or str(host.get('name') or '') in host_names
                required_names = dependent.get('prerequisite_upgrades') or []
                removes_prerequisite = any(
                    removed_name == required or removed_name.startswith(required + ' (')
                    for required in required_names)
                if applies and removes_prerequisite:
                    raise ApiError(409, 'Сначала снимите зависимые vehicle upgrades')
            prospective_host_modifications = [
                item for item in remaining_modifications
                if item.get('host_instance_id') == host.get('instance_id')]
            prospective = evaluate_effective_vehicle(
                host, prospective_host_modifications, owned, data,
                remaining_modifications)
            prospective_seats = _num((prospective.get('effective') or {}).get('seats'))
            if prospective_seats is not None and prospective_seats < 0:
                raise ApiError(409, 'Сначала освободите места, занятые Heavy Weapon Mount')
        upgrade['state'] = 'carried'
        upgrade.pop('host_instance_id', None)
        data.setdefault('modification_state', {}).pop(modification_id, None)
        if upgrade.get('modification_kind') == 'cyberdeck_program':
            data.setdefault('program_state', {}).pop(upgrade.get('instance_id'), None)
        now = time.time()
        conn.execute(
            'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
            'WHERE modification_id=?', (user['id'], now, now, modification_id))
        if modification.get('host_type') == 'weapon':
            sync_weapon_states_with_modifications(conn, row['id'], data)
        elif modification.get('host_type') == 'vehicle':
            sync_vehicle_states_with_modifications(conn, row['id'], data)
        revision_after = current_revision + 1
        persist_character_item_instances(conn, row['id'], data, 'modification_remove')
        config = modification.get('configuration') or {}
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Remove {config.get("upgrade_name") or upgrade.get("name")}: {reason}',
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['removed_modification_ids'] = [modification_id]
        if erased_backup_count:
            delta['revertible'] = False
            delta['backup_drive_erased_programs'] = erased_backup_count
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
            'management': self.modification_management_payload(conn, fresh),
        })

    @atomic_endpoint
    def api_character_black_ice_deploy(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'mode', 'floor_label', 'target_label', 'reason',
            'session_id', 'session_floor_id', 'session_node_id',
            'target_combatant_id'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Black ICE deployment содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        deck_id, program_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        modifications = character_modifications(conn, row['id'])
        modification = next((item for item in modifications
                             if item.get('host_instance_id') == deck_id and
                             item.get('upgrade_instance_id') == program_id and
                             item.get('host_type') == 'cyberdeck'), None)
        if not modification:
            raise ApiError(404, 'Installed Black ICE instance не найден')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        program = owned.get(program_id)
        if not program or cyberdeck_program_category(program) != 'black_ice':
            raise ApiError(400, 'Выбранная Program не является Black ICE')
        if active_black_ice_entity(data, program_id):
            raise ApiError(409, 'Для этой Black ICE уже существует active NET entity')
        runtime = initial_program_runtime_state(
            program, deck_id, modification['modification_id'],
            (data.get('program_state') or {}).get(program_id))
        if runtime['status'] != 'inactive':
            raise ApiError(409, 'Black ICE необходимо сначала Deactivate')
        mode = str((body or {}).get('mode') or '')
        if mode not in ('lie_in_wait', 'deploy_combat'):
            raise ApiError(400, 'Black ICE mode: lie_in_wait/deploy_combat')
        session = None
        net_state = None
        net_state_before = None
        session_floor_id = None
        session_node_id = None
        session_node_label = None
        target_combatant_id = None
        session_id = _num((body or {}).get('session_id'))
        floor_label = str((body or {}).get('floor_label') or '').strip()[:120]
        target_label = str((body or {}).get('target_label') or '').strip()[:120]
        if session_id is not None:
            if int(session_id) != session_id:
                raise ApiError(400, 'Некорректная Live Session')
            session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                   (int(session_id),)).fetchone()
            role, capabilities = self.session_capabilities(conn, user, session)
            if (not session or not role or
                    session['status'] not in ('preparing', 'active', 'paused')):
                raise ApiError(403, 'Нет доступа к Live NET Session')
            if ('view_gm' not in capabilities and not conn.execute(
                    'SELECT 1 FROM session_combatants WHERE session_id=? AND character_id=?',
                    (session['id'], row['id'])).fetchone()):
                raise ApiError(403, 'Character не участвует в этой Session')
            net_state = session_net_state(_row_value(session, 'net_state_json', '{}'))
            net_state_before = copy.deepcopy(net_state)
            session_floor_id = str((body or {}).get('session_floor_id') or '').lower()
            floor = next((item for item in net_state['floors']
                          if item['floor_id'] == session_floor_id), None)
            if not floor:
                raise ApiError(400, 'Выберите validated Session NET Floor')
            floor_label = floor['label']
            floor_nodes = [item for item in net_state['nodes']
                           if item['floor_id'] == session_floor_id]
            session_node_id = str((body or {}).get('session_node_id') or '').lower()
            node = None
            if floor_nodes:
                node = next((item for item in floor_nodes
                             if item['node_id'] == session_node_id), None)
                if not node:
                    raise ApiError(400, 'Выберите validated Session NET node')
                session_node_label = node['label']
            else:
                session_node_id = None
            if mode == 'deploy_combat':
                target_combatant_id = _num((body or {}).get('target_combatant_id'))
                if (target_combatant_id is None or int(target_combatant_id) != target_combatant_id):
                    raise ApiError(400, 'Выберите Session target combatant')
                target = conn.execute(
                    'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
                    (session['id'], int(target_combatant_id))).fetchone()
                if not target or target['character_id'] == row['id']:
                    raise ApiError(400, 'Некорректный Session target для Black ICE')
                target_combatant_id = target['id']
                target_label = target['name']
                if node:
                    node['visible'] = True
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(floor_label) < 1:
            raise ApiError(400, 'Укажите Floor для Black ICE')
        if mode == 'deploy_combat' and len(target_label) < 2:
            raise ApiError(400, 'Укажите target для deployed Black ICE')
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Black ICE deployment')
        entity = initial_black_ice_entity(
            program, deck_id, row['id'], mode, floor_label, target_label)
        if session:
            entity.update({
                'session_id': session['id'], 'session_floor_id': session_floor_id,
                'session_node_id': session_node_id,
                'session_node_label': session_node_label,
                'target_combatant_id': target_combatant_id,
            })
        entities = data.setdefault('net_entities', {})
        entities[entity['net_entity_id']] = entity
        if len(entities) > 200:
            archived = sorted(
                (item for item in entities.values()
                 if item.get('status') in ('deactivated', 'destroyed')),
                key=lambda item: item.get('archived_at') or 0)
            for old in archived[:max(0, len(entities) - 200)]:
                entities.pop(old.get('net_entity_id'), None)
        runtime['status'] = 'rezzed'
        runtime['rez_current'] = runtime['rez_max']
        data.setdefault('program_state', {})[program_id] = runtime
        reason = (
            f'Deploy Black ICE {program.get("name")} as {entity["status"]} '
            f'on {floor_label}: {reason_detail}')
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        now = time.time()
        if session:
            net_state['links'].append({
                'net_entity_id': entity['net_entity_id'],
                'character_id': row['id'], 'floor_id': session_floor_id,
                'node_id': session_node_id,
                'target_combatant_id': target_combatant_id,
                'initiative': entity.get('initiative') or 0,
                'active': True, 'visible': mode == 'deploy_combat',
                'linked_at': now,
            })
            conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                         (json.dumps(net_state, ensure_ascii=False), now, session['id']))
            conn.execute(
                'INSERT INTO session_activity(session_id,actor_user_id,event_type,after_json,note,created) '
                'VALUES(?,?,?,?,?,?)',
                (session['id'], user['id'], 'net_entity_deploy',
                 json.dumps(entity, ensure_ascii=False), reason_detail, now))
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['session_net_change'] = {
                'session_id': session['id'], 'before': net_state_before,
                'after': copy.deepcopy(net_state),
            }
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'net_entity': entity,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    @atomic_endpoint
    def api_character_net_entity_action(self, conn, qs, m, body):
        user = self.require_user(conn)
        row = self.get_char(conn, m.group(1))
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        allowed = {'revision', 'action', 'amount', 'floor_label',
                   'target_label', 'reason', 'session_floor_id', 'session_node_id',
                   'target_combatant_id'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET entity action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        entity_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        entity = (data.get('net_entities') or {}).get(entity_id)
        if not isinstance(entity, dict) or entity.get('type') != 'black_ice':
            raise ApiError(404, 'Black ICE NET entity не найдена')
        linked_session = None
        if entity.get('session_id'):
            linked_session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                          (int(entity['session_id']),)).fetchone()
        if row['owner_id'] != user['id']:
            if (not linked_session or
                    'edit_combatants' not in self.session_capabilities(
                        conn, user, linked_session)[1]):
                raise ApiError(403, 'Нет права управлять Black ICE entity')
        if entity.get('status') not in ('lying_in_wait', 'hunting', 'derezzed'):
            raise ApiError(409, 'Black ICE NET entity уже завершена')
        before_entity = copy.deepcopy(entity)
        program_id = str(entity.get('source_program_instance_id') or '')
        deck_id = str(entity.get('deck_instance_id') or '')
        modifications = character_modifications(conn, row['id'])
        modification = next((item for item in modifications
                             if item.get('host_instance_id') == deck_id and
                             item.get('upgrade_instance_id') == program_id), None)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        program = owned.get(program_id)
        if not modification or not program:
            raise ApiError(409, 'Source Black ICE installation отсутствует')
        runtime = initial_program_runtime_state(
            program, deck_id, modification['modification_id'],
            (data.get('program_state') or {}).get(program_id))
        linked_net_state = session_net_state(
            _row_value(linked_session, 'net_state_json', '{}')) if linked_session else None
        linked_net_link = next((item for item in linked_net_state['links']
                                if item['net_entity_id'] == entity_id), None) \
            if linked_net_state else None
        linked_net_state_before = copy.deepcopy(linked_net_state) \
            if linked_net_state else None
        if linked_session and not linked_net_link:
            raise ApiError(409, 'Session NET entity link отсутствует')
        action = str((body or {}).get('action') or '').lower()
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину NET entity action')
        now = time.time()
        removed_modification_ids = []
        if action == 'damage':
            if entity.get('status') not in ('lying_in_wait', 'hunting'):
                raise ApiError(409, 'REZ damage требует active Black ICE')
            amount = _num((body or {}).get('amount'))
            if amount is None or int(amount) != amount or not 1 <= amount <= 100:
                raise ApiError(400, 'Укажите REZ damage от 1 до 100')
            previous = int(entity.get('rez_current') or 0)
            entity['rez_current'] = max(0, previous - int(amount))
            runtime['rez_current'] = entity['rez_current']
            if entity['rez_current'] == 0:
                entity['status'] = 'derezzed'
                runtime['status'] = 'derezzed'
                if linked_net_link:
                    linked_net_link['initiative'] = 0
            reason = (f'Black ICE REZ damage {entity.get("name")}: '
                      f'{previous} → {entity["rez_current"]}; {detail}')
        elif action == 'slide':
            if entity.get('status') != 'hunting':
                raise ApiError(409, 'Slide требует hunting Black ICE')
            entity['status'] = 'lying_in_wait'
            entity['target_label'] = None
            entity['initiative'] = None
            entity['initiative_roll'] = None
            entity['target_combatant_id'] = None
            if linked_net_link:
                linked_net_link['target_combatant_id'] = None
                linked_net_link['initiative'] = 0
            reason = f'Slide from Black ICE {entity.get("name")}: {detail}'
        elif action == 'engage':
            if entity.get('status') != 'lying_in_wait':
                raise ApiError(409, 'Engage требует lying-in-wait Black ICE')
            if linked_session:
                floor_id = str((body or {}).get('session_floor_id') or
                               linked_net_link.get('floor_id') or '').lower()
                floor = next((item for item in linked_net_state['floors']
                              if item['floor_id'] == floor_id), None)
                floor_nodes = [item for item in linked_net_state['nodes']
                               if item['floor_id'] == floor_id]
                node_id = str((body or {}).get('session_node_id') or
                              linked_net_link.get('node_id') or '').lower()
                node = next((item for item in floor_nodes
                             if item['node_id'] == node_id), None) if floor_nodes else None
                target_id = _num((body or {}).get('target_combatant_id'))
                target = conn.execute(
                    'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
                    (linked_session['id'], int(target_id))).fetchone() \
                    if target_id is not None and int(target_id) == target_id else None
                if (not floor or not target or target['character_id'] == row['id'] or
                        (floor_nodes and not node)):
                    raise ApiError(400, 'Выберите validated Session Floor, node и target')
                floor_label, target_label = floor['label'], target['name']
                entity['session_floor_id'] = floor_id
                entity['session_node_id'] = node_id if node else None
                entity['session_node_label'] = node['label'] if node else None
                entity['target_combatant_id'] = target['id']
                linked_net_link['floor_id'] = floor_id
                linked_net_link['node_id'] = node_id if node else None
                linked_net_link['target_combatant_id'] = target['id']
                linked_net_link['visible'] = True
                if node:
                    node['visible'] = True
            else:
                target_label = str((body or {}).get('target_label') or '').strip()[:120]
                floor_label = str((body or {}).get('floor_label') or
                                  entity.get('floor_label') or '').strip()[:120]
                if len(target_label) < 2 or not floor_label:
                    raise ApiError(400, 'Укажите Floor и target для Black ICE')
            roll = secrets.randbelow(10) + 1
            entity.update({
                'status': 'hunting', 'target_label': target_label,
                'floor_label': floor_label, 'initiative_roll': roll,
                'initiative': int(entity.get('spd') or 0) + roll,
            })
            if linked_net_link:
                linked_net_link['initiative'] = entity['initiative']
            reason = f'Engage Black ICE {entity.get("name")} vs {target_label}: {detail}'
        elif action == 'deactivate':
            entity['status'] = 'deactivated'
            entity['archived_at'] = now
            runtime['status'] = 'inactive'
            runtime['rez_current'] = runtime['rez_max']
            if linked_net_link:
                linked_net_link['active'] = False
            reason = f'Deactivate Black ICE {entity.get("name")}: {detail}'
        elif action == 'destroy':
            entity['status'] = 'destroyed'
            entity['rez_current'] = 0
            entity['archived_at'] = now
            runtime['status'] = 'destroyed'
            runtime['rez_current'] = 0
            program['state'] = 'broken'
            program.pop('host_instance_id', None)
            conn.execute(
                'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                'WHERE modification_id=?',
                (user['id'], now, now, modification['modification_id']))
            removed_modification_ids.append(modification['modification_id'])
            if linked_net_link:
                linked_net_link['active'] = False
            reason = f'Destroy Black ICE entity {entity.get("name")}: {detail}'
        else:
            raise ApiError(400, 'NET entity action: damage/slide/engage/deactivate/destroy')
        entity['updated_at'] = now
        data.setdefault('program_state', {})[program_id] = runtime
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'net_entity_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after,
            category='modification' if removed_modification_ids else 'item_action')
        if removed_modification_ids:
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['removed_modification_ids'] = removed_modification_ids
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        if linked_session:
            queue_count = sum(1 for item in linked_net_state['links']
                              if item['active'] and (_num(item.get('initiative')) or 0) > 0)
            linked_net_state['active_turn'] = min(
                linked_net_state['active_turn'], max(0, queue_count - 1))
            conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                         (json.dumps(linked_net_state, ensure_ascii=False), now,
                          linked_session['id']))
            conn.execute(
                'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
                'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
                (linked_session['id'], user['id'], f'net_entity_{action}',
                 json.dumps(before_entity, ensure_ascii=False),
                 json.dumps(entity, ensure_ascii=False), detail, now))
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['session_net_change'] = {
                'session_id': linked_session['id'],
                'before': linked_net_state_before,
                'after': copy.deepcopy(linked_net_state),
            }
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'net_entity': copy.deepcopy(entity),
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_program_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {'revision', 'action', 'amount', 'reason'}:
            raise ApiError(400, 'Program action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        deck_id, program_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        modifications = character_modifications(conn, row['id'])
        modification = next((item for item in modifications
                             if item.get('host_instance_id') == deck_id and
                             item.get('upgrade_instance_id') == program_id and
                             item.get('host_type') == 'cyberdeck'), None)
        if not modification:
            raise ApiError(404, 'Installed Program instance не найден')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        deck, program = owned.get(deck_id), owned.get(program_id)
        if (not deck or not program or
                program.get('modification_kind') != 'cyberdeck_program'):
            raise ApiError(409, 'Повреждена связь установленной Program')
        runtime = initial_program_runtime_state(
            program, deck_id, modification['modification_id'],
            (data.get('program_state') or {}).get(program_id))
        data.setdefault('program_state', {})[program_id] = runtime
        action = str((body or {}).get('action') or '').lower()
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину Program action')
        category = runtime['category']
        status = runtime['status']
        active_entity = active_black_ice_entity(data, program_id) \
            if category == 'black_ice' else None
        if category == 'black_ice' and action != 'destroy':
            raise ApiError(409, 'Black ICE actions require NET entity')
        if category == 'black_ice' and action == 'destroy' and active_entity:
            raise ApiError(409, 'Destroy active Black ICE through its NET entity')
        now = time.time()
        removed_modification_ids = []
        if action == 'run':
            if category != 'attacker':
                raise ApiError(409, 'Run доступен только Attacker Program')
            runtime['run_count'] += 1
            runtime['last_run_at'] = now
            reason = f'Run Attacker Program {program.get("name")}: {detail}'
        elif action == 'rez':
            if category == 'black_ice':
                raise ApiError(409, 'Black ICE требует NET entity deployment')
            if category not in ('booster', 'defender'):
                raise ApiError(409, 'Activate доступен только Booster или Defender Program')
            if status != 'inactive':
                raise ApiError(409, 'Program необходимо сначала Deactivate')
            catalog_program = item_by_id(catalog_item_id_for_entry(program)) or {}
            if re.search(r'Only 1 copy of this Program can be running',
                         str(catalog_program.get('desc') or ''), re.I):
                for other in (data.get('program_state') or {}).values():
                    if (other is not runtime and
                            other.get('catalog_item_id') == runtime['catalog_item_id'] and
                            other.get('status') == 'rezzed'):
                        raise ApiError(409, 'Только одна копия этой Program может быть Rezzed')
            runtime['status'] = 'rezzed'
            runtime['rez_current'] = runtime['rez_max']
            reason = f'Rez {program.get("name")} at REZ {runtime["rez_current"]}: {detail}'
        elif action == 'damage':
            if status != 'rezzed' or runtime['rez_max'] <= 0:
                raise ApiError(409, 'REZ damage требует Rezzed Program')
            amount = _num((body or {}).get('amount'))
            if amount is None or int(amount) != amount or not 1 <= amount <= 100:
                raise ApiError(400, 'Укажите REZ damage от 1 до 100')
            previous = runtime['rez_current']
            runtime['rez_current'] = max(0, previous - int(amount))
            if runtime['rez_current'] == 0:
                runtime['status'] = 'derezzed'
            reason = (f'Program REZ damage {program.get("name")}: '
                      f'{previous} → {runtime["rez_current"]}; {detail}')
        elif action == 'derez':
            if status != 'rezzed':
                raise ApiError(409, 'Derez требует Rezzed Program')
            runtime['status'] = 'derezzed'
            runtime['rez_current'] = 0
            reason = f'Derez Program {program.get("name")}: {detail}'
        elif action == 'deactivate':
            if status not in ('rezzed', 'derezzed'):
                raise ApiError(409, 'Deactivate требует Rezzed или Derezzed Program')
            runtime['status'] = 'inactive'
            runtime['rez_current'] = runtime['rez_max']
            reason = f'Deactivate Program {program.get("name")}: {detail}'
        elif action == 'destroy':
            backup_modification = next((item for item in modifications
                                        if item.get('host_instance_id') == deck_id and
                                        (owned.get(item.get('upgrade_instance_id')) or {}).get('name') == 'Backup Drive'), None)
            if category != 'black_ice' and backup_modification:
                backup_state = data.setdefault('modification_state', {}).setdefault(
                    backup_modification['modification_id'],
                    {'resource_type': 'backup_drive', 'saved_programs': []})
                saved = backup_state.setdefault('saved_programs', [])
                if not any(item.get('program_instance_id') == program_id for item in saved):
                    saved.append({
                        'program_instance_id': program_id,
                        'modification_id': modification['modification_id'],
                        'catalog_item_id': catalog_item_id_for_entry(program),
                        'name': program.get('custom_name') or program.get('name'),
                        'runtime_before': copy.deepcopy(runtime),
                        'saved_at': now,
                    })
            runtime['status'] = 'destroyed'
            runtime['rez_current'] = 0
            program['state'] = 'broken'
            program.pop('host_instance_id', None)
            conn.execute(
                'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                'WHERE modification_id=?',
                (user['id'], now, now, modification['modification_id']))
            removed_modification_ids.append(modification['modification_id'])
            reason = f'Destroy Program {program.get("name")}: {detail}'
        else:
            raise ApiError(400, 'Program action: run/rez/damage/derez/deactivate/destroy')
        if runtime['status'] in ('derezzed', 'destroyed'):
            queue_defense_sequencer_trigger(
                data, modifications, deck_id, program_id)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'program_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after,
            category='modification' if removed_modification_ids else 'item_action')
        if removed_modification_ids:
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['removed_modification_ids'] = removed_modification_ids
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_backup_restore(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        if set(body or {}) - {'revision', 'reason'}:
            raise ApiError(400, 'Backup restore содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        deck_id, hardware_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        modifications = character_modifications(conn, row['id'])
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        backup_modification = next((item for item in modifications
                                    if item.get('host_instance_id') == deck_id and
                                    item.get('upgrade_instance_id') == hardware_id and
                                    (owned.get(hardware_id) or {}).get('name') == 'Backup Drive'), None)
        if not backup_modification:
            raise ApiError(404, 'Installed Backup Drive не найден')
        backup_state = (data.get('modification_state') or {}).get(
            backup_modification['modification_id']) or {}
        saved = backup_state.get('saved_programs') or []
        if not saved:
            raise ApiError(409, 'Backup Drive не содержит Programs')
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину Backup restore')
        active_deck = [item for item in modifications
                       if item.get('host_instance_id') == deck_id]
        restored_rows = []
        for snapshot in saved:
            program_id = str(snapshot.get('program_instance_id') or '')
            program = owned.get(program_id)
            inactive = conn.execute(
                'SELECT * FROM item_modifications WHERE modification_id=? '
                'AND character_id=? AND host_instance_id=? AND upgrade_instance_id=? AND active=0',
                (snapshot.get('modification_id'), row['id'], deck_id, program_id)).fetchone()
            if not program or program.get('state') != 'broken' or not inactive:
                raise ApiError(409, 'Saved Program instance недоступен для восстановления')
            compatibility = cyberdeck_item_compatibility(
                owned.get(deck_id) or {}, program, active_deck, owned)
            if not compatibility['allowed']:
                raise ApiError(409, 'Недостаточно Cyberdeck slots для Backup restore')
            restored_modification = item_modification_payload(inactive)
            restored_modification['active'] = True
            active_deck.append(restored_modification)
            restored_rows.append((snapshot, program, restored_modification))
        now = time.time()
        restored_ids = []
        for snapshot, program, restored_modification in restored_rows:
            modification_id = restored_modification['modification_id']
            conn.execute(
                'UPDATE item_modifications SET active=1,removed_by=NULL,removed_at=NULL,updated=? '
                'WHERE modification_id=?', (now, modification_id))
            program['state'] = 'installed'
            program['host_instance_id'] = deck_id
            data.setdefault('program_state', {})[program['instance_id']] = \
                initial_program_runtime_state(
                    program, deck_id, modification_id,
                    snapshot.get('runtime_before'))
            restored_ids.append(modification_id)
        backup_state['saved_programs'] = []
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'backup_restore', source_ref=detail, prune=True)
        revision_after = current_revision + 1
        reason = f'Restore {len(restored_ids)} Programs from Backup Drive: {detail}'
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['created_modification_ids'] = restored_ids
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id,
            'restored': len(restored_ids),
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_defense_sequencer_resolve(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'armor_instance_id', 'not_used_in_netrun_confirmed',
                   'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Defense Sequencer resolution содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        if (body or {}).get('not_used_in_netrun_confirmed') is not True:
            raise ApiError(
                400, 'Подтвердите, что выбранная Armor не использовалась в этом Netrun')
        deck_id, hardware_id = str(m.group(2)).lower(), str(m.group(3)).lower()
        armor_id = str((body or {}).get('armor_instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(armor_id):
            raise ApiError(400, 'Выберите concrete Armor Program instance')
        detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(detail) < 3:
            raise ApiError(400, 'Укажите причину Defense Sequencer resolution')
        modifications = character_modifications(conn, row['id'])
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        now = time.time()
        resolved = resolve_defense_sequencer_trigger(
            data, modifications, deck_id, hardware_id, armor_id, now=now)
        validate_active_modification_references(conn, row['id'], data)
        reason = (f'Defense Sequencer Rez {resolved["armor_name"]} at REZ '
                  f'{resolved["rez_current"]}: {detail}; '
                  'not-used-in-this-Netrun eligibility confirmed manually')
        persist_character_item_instances(
            conn, row['id'], data, 'defense_sequencer', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta.update({
            'defense_sequencer_resolution': True,
            'manual_eligibility_confirmed': True,
            'resolved_armor_instance_id': armor_id,
        })
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'resolved': resolved,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    def api_character_effects(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        self.send_json({
            'character_id': row['id'], 'revision': _row_value(row, 'revision', 0) or 0,
            'effects': character_effect_instances(conn, row['id']),
        })

    @atomic_endpoint
    def api_character_effect_create(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        current_revision = _row_value(row, 'revision', 0) or 0
        expected_revision = _num((body or {}).get('revision'))
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        effect_id = secrets.token_hex(16)
        clean = clean_custom_effect(body or {}, effect_id)
        now = time.time()
        conn.execute(
            'INSERT INTO active_effect_instances(effect_id,character_id,source_type,label,'
            'definition_json,duration_type,started_at,expires_at,remaining_rounds,active,'
            'created_by,reason,created,updated) VALUES(?,?,?,?,?,?,?,?,?,1,?,?,?,?)',
            (effect_id, row['id'], 'custom', clean['label'],
             json.dumps(clean['definition'], ensure_ascii=False), clean['duration_type'],
             now, clean['expires_at'], clean['remaining_rounds'], user['id'],
             clean['reason'], now, now))
        created_row = conn.execute(
            'SELECT e.*,u.display_name actor FROM active_effect_instances e '
            'JOIN users u ON u.id=e.created_by WHERE e.effect_id=?',
            (effect_id,)).fetchone()
        created = effect_instance_payload(created_row, now)
        revision_after = current_revision + 1
        record_effect_change(
            conn, row['id'], user['id'], effect_id, clean['label'], None, created,
            clean['reason'], current_revision, revision_after)
        conn.execute('UPDATE characters SET updated=?,revision=? WHERE id=?',
                     (now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'effect': created,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    @atomic_endpoint
    def api_character_effect_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        if set(body or {}) - {'revision', 'action'}:
            raise ApiError(400, 'Effect action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        expected_revision = _num((body or {}).get('revision'))
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        effect_id = str(m.group(2)).lower()
        raw = conn.execute(
            'SELECT e.*,u.display_name actor FROM active_effect_instances e '
            'JOIN users u ON u.id=e.created_by WHERE e.effect_id=? AND e.character_id=?',
            (effect_id, row['id'])).fetchone()
        if not raw:
            raise ApiError(404, 'Effect instance не найден')
        before = effect_instance_payload(raw)
        if before.get('archived_at'):
            raise ApiError(409, 'Effect instance уже архивирован')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in ACTIVE_EFFECT_ACTIONS | {'archive'}:
            raise ApiError(400, 'Неизвестное действие с эффектом')
        now = time.time()
        if action == 'disable':
            if not before['active']:
                raise ApiError(409, 'Эффект уже отключён')
            conn.execute('UPDATE active_effect_instances SET active=0,updated=? WHERE effect_id=?',
                         (now, effect_id))
            reason = f'Disable effect {before["label"]}'
        elif action == 'enable':
            if before['duration_type'] == 'real_time' and before.get('expires_at', 0) <= now:
                raise ApiError(409, 'Истёкший real-time эффект нельзя включить повторно')
            if before['duration_type'] == 'rounds' and (_num(before.get('remaining_rounds')) or 0) <= 0:
                raise ApiError(409, 'Завершённый round effect нельзя включить повторно')
            if before['active']:
                raise ApiError(409, 'Эффект уже включён')
            conn.execute('UPDATE active_effect_instances SET active=1,updated=? WHERE effect_id=?',
                         (now, effect_id))
            reason = f'Enable effect {before["label"]}'
        elif action == 'tick':
            if before['duration_type'] != 'rounds':
                raise ApiError(400, 'Tick доступен только для round effect')
            if before['status'] != 'active':
                raise ApiError(409, 'Round effect сейчас не активен')
            remaining = max(0, (_num(before.get('remaining_rounds')) or 0) - 1)
            conn.execute(
                'UPDATE active_effect_instances SET remaining_rounds=?,active=?,updated=? '
                'WHERE effect_id=?', (remaining, 1 if remaining else 0, now, effect_id))
            reason = f'Advance effect round {before["label"]}: {remaining} remaining'
        else:
            conn.execute(
                'UPDATE active_effect_instances SET active=0,archived_at=?,updated=? '
                'WHERE effect_id=?', (now, now, effect_id))
            reason = f'Archive effect {before["label"]}'
        after_row = conn.execute(
            'SELECT e.*,u.display_name actor FROM active_effect_instances e '
            'JOIN users u ON u.id=e.created_by WHERE e.effect_id=?',
            (effect_id,)).fetchone()
        after = effect_instance_payload(after_row, now)
        revision_after = current_revision + 1
        record_effect_change(
            conn, row['id'], user['id'], effect_id, before['label'], before, after,
            reason, current_revision, revision_after)
        conn.execute('UPDATE characters SET updated=?,revision=? WHERE id=?',
                     (now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'effect': after,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_cyberware_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'action', 'host_instance_ids', 'installation_side',
            'installation_site', 'technician', 'manual_resolution_confirmed',
            'biosystem_confirmed', 'reason',
        }
        if set(body or {}) - allowed:
            raise ApiError(400, 'Cyberware action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Cyberware lifecycle action')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        chrome = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and
                       item.get('instance_id') == instance_id), None)
        if not chrome:
            raise ApiError(404, 'Cyberware instance не найден')
        catalog_item = item_by_id(catalog_item_id_for_entry(chrome))
        if not catalog_item or catalog_item.get('cat') != 'cyberware':
            raise ApiError(409, 'Cyberware instance не связан с Data Pool')
        action = str((body or {}).get('action') or '').lower()
        if action not in ('install', 'uninstall', 'rebind', 'configure',
                          'quick_detach', 'quick_attach'):
            raise ApiError(
                400, 'Cyberware action: install/uninstall/rebind/configure/'
                     'quick_detach/quick_attach')
        raw_host_ids = (body or {}).get('host_instance_ids') or []
        if not isinstance(raw_host_ids, list) or len(raw_host_ids) > 4:
            raise ApiError(400, 'host_instance_ids должен быть коротким списком')
        host_ids = []
        for value in raw_host_ids:
            value = str(value or '').lower()
            if not INSTANCE_ID_RE.fullmatch(value):
                raise ApiError(400, 'Некорректный concrete Cyberware host')
            if value not in host_ids:
                host_ids.append(value)
        capacity = cyberware_capacity(chrome)
        expected_host = capacity.get('host')
        installed_before = cyberware_is_installed(chrome)
        humanity_before = derive(data)
        before_current = humanity_before.get('humanity_cur')
        before_maximum = humanity_before.get('humanity_max')
        now = time.time()
        installation_side = str((body or {}).get('installation_side') or '').lower()
        installation_site = str((body or {}).get('installation_site') or '').title() \
            if action in ('install', 'uninstall') else ''
        technician = str((body or {}).get('technician') or '').strip()[:120] \
            if action in ('install', 'uninstall') else ''
        profile = cyberware_installation_profile(chrome)
        runtime_states = data.setdefault('cyberware_state', {})
        if not isinstance(runtime_states, dict):
            runtime_states = {}
            data['cyberware_state'] = runtime_states
        runtime = runtime_states.get(instance_id)
        if not isinstance(runtime, dict):
            runtime = {'installation_count': 0, 'humanity_loss_events': 0,
                       'history': []}
            runtime_states[instance_id] = runtime
        if not isinstance(runtime.get('history'), list):
            runtime['history'] = []

        def append_history(event_action, *, affected_ids=None, humanity_loss=0):
            runtime['history'].append({
                'action': event_action, 'created': now,
                'installation_side': chrome.get('installation_side') or
                    runtime.get('installation_side'),
                'installation_site': installation_site or None,
                'technician': technician or None,
                'affected_instance_ids': affected_ids or [instance_id],
                'humanity_loss': humanity_loss,
                'reason': reason_detail,
                'manual_resolution_confirmed': bool(
                    event_action in ('install', 'uninstall') and
                    (body or {}).get('manual_resolution_confirmed') is True),
            })
            runtime['history'] = runtime['history'][-30:]
            runtime['last_action'] = event_action
            runtime['last_action_at'] = now

        def validate_installation_context():
            if (body or {}).get('manual_resolution_confirmed') is not True:
                raise ApiError(400, 'Подтвердите manual surgery/service resolution')
            if installation_site != profile['required_site']:
                raise ApiError(
                    400, f'{chrome.get("name")}: требуется installation site '
                         f'{profile["required_site"]}')
            if len(technician) < 2:
                raise ApiError(400, 'Укажите clinic, surgeon или technician')
            if profile['biosystem_required'] and \
                    (body or {}).get('biosystem_confirmed') is not True:
                raise ApiError(400, 'Подтвердите required Biosystem')

        def assign_side(required=True):
            if cyberware_is_paired_leg_foundation(chrome):
                chrome['installation_side'] = 'paired'
            elif cyberware_side_required(chrome):
                if installation_side not in ('left', 'right'):
                    if required:
                        raise ApiError(400, 'Выберите installation side: left/right')
                else:
                    chrome['installation_side'] = installation_side
            elif installation_side:
                raise ApiError(400, 'Эта Cyberware не использует left/right side')

        def assign_hosts():
            compatibility = cyberware_option_compatibility(
                data, instance_id, host_ids)
            if not compatibility['allowed']:
                raise ApiError(400, '; '.join(compatibility['reasons']))
            chrome['host_instance'] = host_ids[0]
            chrome['host_instances'] = host_ids
            return compatibility

        compatibility = None
        affected_ids = [instance_id]
        if action == 'install':
            if installed_before:
                raise ApiError(409, 'Cyberware уже установлена')
            if chrome.get('state') == 'broken':
                raise ApiError(409, 'Сломанную Cyberware нельзя установить')
            validate_installation_context()
            assign_side()
            if expected_host:
                compatibility = assign_hosts()
            elif host_ids:
                raise ApiError(400, 'Эта Cyberware не использует Option host')
            catalog_id = catalog_item_id_for_entry(chrome)
            other_installed = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and item.get('instance_id') != instance_id and
                cyberware_is_installed(item)]
            if capacity.get('unique') and any(
                    catalog_item_id_for_entry(item) == catalog_id
                    for item in other_installed):
                raise ApiError(409, 'Допустима только одна установленная копия Cyberware')
            chrome_name = str(chrome.get('name') or '').lower()
            if chrome_name == 'neuroport' and any(
                    str(item.get('name') or '').lower() == 'neuroport'
                    for item in other_installed):
                raise ApiError(409, 'Одновременно допустим только один Neuroport')
            if cyberware_host_kind(chrome) == 'Cyberaudio Suite' and any(
                    cyberware_host_kind(item) == 'Cyberaudio Suite'
                    for item in other_installed):
                raise ApiError(409, 'Одновременно допустим только один Cyberaudio Suite')
            chrome['state'] = 'installed'
            validate_cyberware_requirements(data)
            validate_cyberware_sides(data, allow_unassigned=True)
            validate_cyberware_payload_conflicts(data)
            if expected_host:
                compatibility = cyberware_option_compatibility(data, instance_id, host_ids)
                if not compatibility['allowed']:
                    raise ApiError(400, '; '.join(compatibility['reasons']))
            loss = max(0, int(_num(chrome.get('hl')) or 0))
            if before_current is not None:
                if before_current - loss < 0:
                    raise ApiError(409, 'Недостаточно Humanity для установки Cyberware')
                data['humanity_cur'] = before_current - loss
            runtime['installation_count'] = max(
                0, int(_num(runtime.get('installation_count')) or 0)) + 1
            runtime['humanity_loss_events'] = max(
                0, int(_num(runtime.get('humanity_loss_events')) or 0)) + 1
            runtime['first_installed_at'] = runtime.get('first_installed_at') or now
            runtime['installation_side'] = chrome.get('installation_side')
            runtime['last_installation_site'] = installation_site
            runtime['last_technician'] = technician
            runtime['quick_change_detached'] = False
            append_history('install', humanity_loss=loss)
            reason = f'Install Cyberware {chrome.get("name")}: {reason_detail}'
        elif action == 'rebind':
            if not installed_before or not expected_host:
                raise ApiError(409, 'Rebind требует установленную Cyberware Option')
            compatibility = assign_hosts()
            append_history('rebind')
            reason = f'Rebind Cyberware Option {chrome.get("name")}: {reason_detail}'
        elif action == 'configure':
            if not installed_before or not cyberware_side_required(chrome):
                raise ApiError(409, 'Configure side требует установленный sided foundation')
            assign_side()
            validate_cyberware_sides(data, allow_unassigned=True)
            runtime['installation_side'] = chrome.get('installation_side')
            append_history('configure')
            reason = f'Configure Cyberware side {chrome.get("name")}: {reason_detail}'
        elif action == 'quick_detach':
            if not installed_before or cyberware_host_kind(chrome) != 'Cyberarm':
                raise ApiError(409, 'Quick Detach требует установленный Cyberarm')
            loadout = effective_cyberware_loadout(data)
            foundation_host_ids = {
                host['instance_id'] for host in loadout['hosts']
                if host.get('foundation_instance_id') == instance_id}
            dependents = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and cyberware_is_installed(item) and
                foundation_host_ids.intersection(cyberware_host_assignments(item))]
            if not any(item.get('name') == 'Quick Change Mount' for item in dependents):
                raise ApiError(409, 'Cyberarm не имеет установленный Quick Change Mount')
            affected_ids = [instance_id] + [item['instance_id'] for item in dependents]
            for item in [chrome, *dependents]:
                item['state'] = 'carried'
            runtime['quick_change_detached'] = True
            runtime['quick_change_bundle_instance_ids'] = affected_ids[1:]
            runtime['installation_side'] = chrome.get('installation_side')
            if before_current is not None:
                data['humanity_cur'] = before_current
            append_history('quick_detach', affected_ids=affected_ids)
            reason = f'Quick Detach Cyberarm {chrome.get("name")}: {reason_detail}'
        elif action == 'quick_attach':
            if installed_before or cyberware_host_kind(chrome) != 'Cyberarm' or \
                    not runtime.get('quick_change_detached'):
                raise ApiError(409, 'Quick Attach требует detached Quick Change Cyberarm')
            bundle_ids = [str(value) for value in
                          runtime.get('quick_change_bundle_instance_ids') or []]
            bundle = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and item.get('instance_id') in bundle_ids]
            if len(bundle) != len(set(bundle_ids)) or not any(
                    item.get('name') == 'Quick Change Mount' for item in bundle):
                raise ApiError(409, 'Quick Change Cyberarm bundle повреждён')
            assign_side()
            chrome['state'] = 'installed'
            for item in bundle:
                item['state'] = 'installed'
            validate_cyberware_requirements(data)
            validate_cyberware_sides(data, allow_unassigned=True)
            validate_cyberware_payload_conflicts(data)
            validate_cyberware_slots(data, allow_unbound=True)
            affected_ids = [instance_id, *bundle_ids]
            runtime['quick_change_detached'] = False
            runtime['installation_side'] = chrome.get('installation_side')
            if before_current is not None:
                data['humanity_cur'] = before_current
            append_history('quick_attach', affected_ids=affected_ids, humanity_loss=0)
            reason = f'Quick Attach Cyberarm {chrome.get("name")}: {reason_detail}'
        else:
            if not installed_before:
                raise ApiError(409, 'Cyberware уже не установлена')
            if chrome.get('creation_free') and chrome.get('key') == 'creation-neuroport':
                raise ApiError(409, 'Стартовый Neuroport нельзя извлечь этим действием')
            validate_installation_context()
            foundation_host_ids = {
                host['instance_id'] for host in
                effective_cyberware_loadout(data)['hosts']
                if host.get('foundation_instance_id') == instance_id}
            dependents = [
                item for item in data.get('cyberware') or []
                if isinstance(item, dict) and item.get('instance_id') != instance_id and
                cyberware_is_installed(item) and
                foundation_host_ids.intersection(cyberware_host_assignments(item))]
            if dependents:
                names = ', '.join(str(item.get('name') or 'Option') for item in dependents[:5])
                raise ApiError(409, f'Сначала извлеките зависимые Cyberware Options: {names}')
            runtime['installation_side'] = chrome.get('installation_side')
            chrome['state'] = 'carried'
            chrome.pop('host_instance', None)
            chrome.pop('host_instances', None)
            chrome.pop('installation_side', None)
            validate_cyberware_requirements(data)
            post_remove_loadout = effective_cyberware_loadout(data)
            if any(host['overloaded'] for host in post_remove_loadout['hosts']):
                raise ApiError(409, 'Сначала освободите зависимые Cyberware Option Slots')
            if before_current is not None:
                data['humanity_cur'] = before_current
            append_history('uninstall')
            reason = f'Uninstall Cyberware {chrome.get("name")}: {reason_detail}'

        bound_weapon_id = str(runtime.get('bound_weapon_instance_id') or '')
        if bound_weapon_id:
            bound_weapon = next((item for item in data.get('inventory') or []
                                 if isinstance(item, dict) and
                                 item.get('instance_id') == bound_weapon_id), None)
            if bound_weapon:
                current_hosts = cyberware_host_assignments(chrome)
                bound_weapon['installed_cyberarm_host_id'] = (
                    current_hosts[0] if current_hosts else None)
        humanity_after = derive(data)
        validate_bound_popup_weapon_references(data)
        validate_popup_shield_references(data)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'cyberware_lifecycle', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['cyberware_lifecycle'] = {
            'action': action, 'instance_id': instance_id,
            'affected_instance_ids': affected_ids,
            'host_instance_ids': host_ids,
            'installation_side': chrome.get('installation_side') or
                runtime.get('installation_side'),
            'installation_site': installation_site or None,
            'technician': technician or None,
            'manual_resolution_confirmed': bool(
                action in ('install', 'uninstall') and
                (body or {}).get('manual_resolution_confirmed') is True),
            'humanity_current_before': before_current,
            'humanity_current_after': humanity_after.get('humanity_cur'),
            'humanity_maximum_before': before_maximum,
            'humanity_maximum_after': humanity_after.get('humanity_max'),
            'humanity_restored_on_uninstall': 0,
            'quick_change_no_humanity_loss': action == 'quick_attach',
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'action': action,
            'humanity': delta['cyberware_lifecycle'],
            'compatibility': compatibility,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_therapy_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'action', 'therapy_type', 'therapist',
            'addiction_label', 'manual_time_confirmed', 'reason',
        }
        if set(body or {}) - allowed:
            raise ApiError(400, 'Therapy action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Therapy action')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        therapy_state = data.get('therapy_state')
        if not isinstance(therapy_state, dict):
            therapy_state = {'active': None, 'history': []}
            data['therapy_state'] = therapy_state
        if not isinstance(therapy_state.get('history'), list):
            therapy_state['history'] = []
        active = therapy_state.get('active') \
            if isinstance(therapy_state.get('active'), dict) else None
        action = str((body or {}).get('action') or '').lower()
        now = time.time()
        result = {'action': action}
        if action == 'start':
            if active:
                raise ApiError(409, 'Therapy course уже активен')
            therapy_type = str((body or {}).get('therapy_type') or '').lower()
            profile = THERAPY_PROFILES.get(therapy_type)
            if not profile:
                raise ApiError(400, 'Неизвестный Therapy type')
            therapist = str((body or {}).get('therapist') or '').strip()[:120]
            if len(therapist) < 2:
                raise ApiError(400, 'Укажите therapist или clinic')
            cash = float(data.get('cash') or 0)
            if cash < profile['cost']:
                raise ApiError(409, 'Недостаточно средств для Therapy')
            current_humanity = derive(data).get('humanity_cur')
            maximum_humanity = derive(data).get('humanity_max')
            if (profile['humanity_dice'] and current_humanity is not None and
                    maximum_humanity is not None and
                    current_humanity >= maximum_humanity):
                raise ApiError(409, 'Humanity уже достигла Therapy maximum')
            addiction_label = str((body or {}).get('addiction_label') or '').strip()[:120]
            if therapy_type == 'addiction' and len(addiction_label) < 2:
                raise ApiError(400, 'Укажите addiction для Therapy')
            data['cash'] = round(cash - profile['cost'], 2)
            campaign_started = campaign_now(conn)
            active = {
                'therapy_id': secrets.token_hex(16), 'therapy_type': therapy_type,
                'label': profile['label'], 'catalog_id': profile['catalog_id'],
                'cost': profile['cost'], 'duration_days': profile['duration_days'],
                'humanity_dice': profile['humanity_dice'],
                'therapist': therapist, 'addiction_label': addiction_label or None,
                'started_at': now, 'status': 'active', 'source': profile['source'],
                'manual_time_required': True,
                'campaign_started_at': campaign_started,
                'campaign_due_at': campaign_started + campaign_duration_seconds('1_week'),
            }
            therapy_state['active'] = active
            result['therapy'] = copy.deepcopy(active)
            reason = f'Start {profile["label"]}: {reason_detail}'
        elif action in ('resolve', 'cancel'):
            if not active:
                raise ApiError(409, 'Нет активного Therapy course')
            profile = THERAPY_PROFILES.get(active.get('therapy_type'))
            if not profile:
                raise ApiError(409, 'Therapy profile повреждён')
            completed = action == 'resolve'
            if completed and (body or {}).get('manual_time_confirmed') is not True:
                raise ApiError(400, 'Подтвердите завершение недели Therapy')
            history = copy.deepcopy(active)
            history['resolved_at'] = now
            history['status'] = 'completed' if completed else 'canceled'
            history['reason'] = reason_detail
            if completed and profile['humanity_dice']:
                rolled = roll_dice(profile['humanity_dice'], 6)
                derived_before = derive(data)
                current = int(_num(derived_before.get('humanity_cur')) or 0)
                maximum = int(_num(derived_before.get('humanity_max')) or current)
                after = min(maximum, current + rolled['total'])
                data['humanity_cur'] = after
                history.update({
                    'rolls': rolled['rolls'], 'rolled_humanity': rolled['total'],
                    'humanity_before': current, 'humanity_after': after,
                    'humanity_restored': after - current, 'humanity_maximum': maximum,
                })
                result['humanity'] = {
                    'rolls': rolled['rolls'], 'rolled': rolled['total'],
                    'before': current, 'after': after,
                    'restored': after - current, 'maximum': maximum,
                }
            elif completed:
                history['manual_effect'] = (
                    f'Addiction therapy completed for {active.get("addiction_label")}; '
                    'addiction state remains MANUAL RESOLUTION')
                result['manual_effect'] = history['manual_effect']
            therapy_state['history'].append(history)
            therapy_state['history'] = therapy_state['history'][-50:]
            therapy_state['active'] = None
            result['therapy'] = history
            reason = f'{"Resolve" if completed else "Cancel"} {active.get("label")}: {reason_detail}'
        else:
            raise ApiError(400, 'Therapy action: start/resolve/cancel')
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['therapy_lifecycle'] = copy.deepcopy(result)
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'result': result,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_popup_shield_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'shield_instance_id', 'amount', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Popup Shield action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Popup Shield action')
        option_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        option = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and item.get('instance_id') == option_id), None)
        if not option or not cyberware_is_installed(option) or \
                catalog_item_id_for_entry(option) != 'cyberware-120':
            raise ApiError(404, 'Installed Popup Shield option не найден')
        runtime = data.setdefault('cyberware_state', {}).setdefault(option_id, {})
        popup = runtime.get('popup_shield') if isinstance(runtime.get('popup_shield'), dict) else {}
        action = str((body or {}).get('action') or '').lower()
        shield_id = str(popup.get('shield_instance_id') or '')
        shield = next((item for item in data.get('inventory') or []
                       if isinstance(item, dict) and item.get('instance_id') == shield_id), None)
        result = {'action': action}
        if action == 'install':
            if shield:
                raise ApiError(409, 'Popup Shield уже содержит concrete shield')
            shield_id = str((body or {}).get('shield_instance_id') or '').lower()
            shield = next((item for item in data.get('inventory') or []
                           if isinstance(item, dict) and item.get('instance_id') == shield_id), None)
            if (not shield or catalog_item_id_for_entry(shield) != 'armor-0' or
                    shield.get('state') != 'carried' or
                    shield.get('installed_popup_shield_instance_id')):
                raise ApiError(400, 'Popup Shield принимает только free Bulletproof Shield')
            maximum = armor_shield_hp(shield)
            popup = {'shield_instance_id': shield_id, 'hp_current': maximum,
                     'hp_max': maximum, 'deployed': False, 'installed_at': time.time()}
            runtime['popup_shield'] = popup
            shield['state'] = 'installed'
            shield['installed_popup_shield_instance_id'] = option_id
            reason = f'Install concrete Bulletproof Shield into Popup Shield: {reason_detail}'
        elif action == 'remove':
            if not shield:
                raise ApiError(409, 'Popup Shield не содержит concrete shield')
            current = max(0, int(_num(popup.get('hp_current')) or 0))
            shield['state'] = 'broken' if current <= 0 else 'carried'
            shield.pop('installed_popup_shield_instance_id', None)
            runtime['popup_shield'] = {}
            reason = f'Remove concrete Shield from Popup Shield: {reason_detail}'
        elif action in ('deploy', 'stow'):
            if not shield:
                raise ApiError(409, 'Popup Shield не содержит concrete shield')
            if action == 'deploy' and (_num(popup.get('hp_current')) or 0) <= 0:
                raise ApiError(409, 'Destroyed Shield нельзя deploy')
            popup['deployed'] = action == 'deploy'
            runtime['popup_shield'] = popup
            reason = f'{action.title()} Popup Shield: {reason_detail}'
        elif action == 'damage':
            if not shield:
                raise ApiError(409, 'Popup Shield не содержит concrete shield')
            amount = _num((body or {}).get('amount'))
            if amount is None or not 1 <= amount <= 100:
                raise ApiError(400, 'Укажите Popup Shield damage 1–100')
            previous = max(0, int(_num(popup.get('hp_current')) or 0))
            popup['hp_current'] = max(0, previous - int(amount))
            if popup['hp_current'] == 0:
                popup['deployed'] = False
                shield['state'] = 'broken'
            runtime['popup_shield'] = popup
            result.update({'hp_before': previous, 'hp_after': popup['hp_current']})
            reason = f'Popup Shield damage {previous} → {popup["hp_current"]}: {reason_detail}'
        else:
            raise ApiError(400, 'Popup Shield action: install/remove/deploy/stow/damage')
        validate_popup_shield_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'popup_shield_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ledger_id': ledger_id, 'result': result,
                        'character': self.char_payload(fresh, fresh['owner'], conn=conn)})

    @atomic_endpoint
    def api_character_armor_repair_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {
            'revision', 'action', 'method', 'technician', 'jeeves_instance_id',
            'manual_resolution_confirmed', 'no_sp_loss_confirmed',
            'service_cost', 'payment_confirmed', 'reason',
        }
        if set(body or {}) - allowed:
            raise ApiError(400, 'Armor Repair action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Armor Repair action')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        host = next((item for item in effective_armor_hosts(data)['hosts']
                     if item['instance_id'] == instance_id), None)
        if not host:
            raise ApiError(404, 'Concrete Armor instance не найден')
        if host['host_kind'] == 'shield':
            raise ApiError(409, 'Bulletproof Shields не подлежат ремонту')
        if host['unrepairable']:
            raise ApiError(409, 'Эта Armor не может восстанавливать SP')
        states = data.setdefault('armor_repair_state', {})
        workflow = states.setdefault(instance_id, {'active': None, 'history': []})
        if not isinstance(workflow.get('history'), list):
            workflow['history'] = []
        active = workflow.get('active') if isinstance(workflow.get('active'), dict) else None
        action = str((body or {}).get('action') or '').lower()
        now = time.time()
        result = {'action': action}
        if action == 'start':
            if active:
                raise ApiError(409, 'Armor Repair уже активен')
            if not host['damaged'] or not host['equipped_locations']:
                raise ApiError(409, 'Armor должна быть экипирована и повреждена')
            method = str((body or {}).get('method') or '').lower()
            if method not in ('manual_tech', 'jeeves', 'paid_service'):
                raise ApiError(400, 'Armor Repair method: manual_tech/jeeves/paid_service')
            technician = str((body or {}).get('technician') or '').strip()[:120]
            if len(technician) < 2:
                raise ApiError(400, 'Укажите Armor repair technician')
            duration_label = 'MANUAL TECH TIME'
            duration_key = None
            jeeves_id = None
            if method == 'jeeves':
                jeeves_id = str((body or {}).get('jeeves_instance_id') or '').lower()
                jeeves = next((item for item in data.get('inventory') or []
                               if isinstance(item, dict) and item.get('instance_id') == jeeves_id and
                               catalog_item_id_for_entry(item) == 'gear-39' and
                               item.get('state') in ('carried', 'stored')), None)
                if not jeeves:
                    raise ApiError(409, 'Jeeves Executive Garment Bag недоступен')
                price = float((item_by_id(host['catalog_item_id']) or {}).get('price') or 0)
                if price > 1000:
                    raise ApiError(409, 'Jeeves не ремонтирует Luxury/Super Luxury Armor')
                duration_label = ('1 Hour' if price <= 20 else '6 Hours' if price <= 50 else
                                  '1 Day' if price <= 100 else '1 Week' if price <= 500 else
                                  '2 Weeks')
                duration_key = ('1_hour' if price <= 20 else '6_hours' if price <= 50 else
                                '1_day' if price <= 100 else '1_week' if price <= 500 else
                                '2_weeks')
            service_cost = 0
            if method == 'paid_service':
                service_cost = _num((body or {}).get('service_cost'))
                if service_cost is None or not 0 <= service_cost <= 1_000_000:
                    raise ApiError(400, 'Укажите bounded Armor Repair service cost')
                if (body or {}).get('payment_confirmed') is not True:
                    raise ApiError(400, 'Подтвердите оплату Armor Repair service')
                cash = float(data.get('cash') or 0)
                if cash < service_cost:
                    raise ApiError(409, 'Недостаточно средств для Armor Repair service')
                data['cash'] = round(cash - service_cost, 2)
                duration_label = 'MANUAL PAID SERVICE TIME'
            campaign_started = campaign_now(conn)
            active = {
                'repair_id': secrets.token_hex(16), 'method': method,
                'technician': technician, 'jeeves_instance_id': jeeves_id,
                'service_cost': service_cost,
                'payment_refundable': False if service_cost else None,
                'duration_label': duration_label,
                'target_locations': host['equipped_locations'],
                'before': copy.deepcopy(host['current_by_location']),
                'target_maximum': host['effective_sp'], 'started_at': now,
                'status': 'active', 'source': 'CP:R 140 / BC 43',
                'manual_resolution_required': True,
                'campaign_started_at': campaign_started,
                'campaign_due_at': (
                    campaign_started + campaign_duration_seconds(duration_key)
                    if duration_key else None),
            }
            workflow['active'] = active
            result['repair'] = copy.deepcopy(active)
            reason = f'Start Armor Repair {host["name"]}: {reason_detail}'
        elif action in ('resolve', 'cancel'):
            if not active:
                raise ApiError(409, 'Нет активного Armor Repair')
            completed = action == 'resolve'
            if completed and (body or {}).get('manual_resolution_confirmed') is not True:
                raise ApiError(400, 'Подтвердите завершение Armor Repair')
            history = copy.deepcopy(active)
            history['status'] = 'completed' if completed else 'canceled'
            history['resolved_at'] = now
            history['reason'] = reason_detail
            if completed:
                after_values = {}
                for location in active.get('target_locations') or []:
                    piece = (data.get('armor') or {}).get(location)
                    if isinstance(piece, dict) and piece.get('instance_id') == instance_id:
                        maximum = int(_num(piece.get('maximum')) or
                                      _num(active.get('target_maximum')) or 0)
                        piece['current'] = maximum
                        after_values[location] = maximum
                history['after'] = after_values
                result['restored'] = after_values
            workflow['history'].append(history)
            workflow['history'] = workflow['history'][-30:]
            workflow['active'] = None
            result['repair'] = history
            reason = f'{"Resolve" if completed else "Cancel"} Armor Repair {host["name"]}: {reason_detail}'
        elif action == 'self_repair_tick':
            if host.get('self_repair') != 'executive_armor_daily':
                raise ApiError(409, 'Armor не имеет daily self-repair')
            if (body or {}).get('no_sp_loss_confirmed') is not True:
                raise ApiError(400, 'Подтвердите день без потери SP')
            restored = {}
            for location in host['equipped_locations']:
                piece = (data.get('armor') or {}).get(location)
                if isinstance(piece, dict):
                    maximum = int(_num(piece.get('maximum')) or host['effective_sp'] or 0)
                    current = int(_num(piece.get('current')) or 0)
                    piece['current'] = min(maximum, current + 1)
                    restored[location] = piece['current']
            result['restored'] = restored
            workflow['history'].append({
                'action': action, 'status': 'completed', 'resolved_at': now,
                'after': restored, 'reason': reason_detail, 'source': 'BC 34'})
            workflow['history'] = workflow['history'][-30:]
            reason = f'Executive Armor daily self-repair {host["name"]}: {reason_detail}'
        else:
            raise ApiError(400, 'Armor Repair action: start/resolve/cancel/self_repair_tick')
        validate_armor_repair_references(data)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['armor_repair_lifecycle'] = copy.deepcopy(result)
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'result': result,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_armor_tech_upgrade(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'tech_name', 'manual_confirm', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Armor Tech Upgrade содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        if (body or {}).get('manual_confirm') is not True:
            raise ApiError(400, 'Подтвердите успешный Tech Upgrade Check')
        tech_name = str((body or {}).get('tech_name') or '').strip()[:120]
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(tech_name) < 2 or len(reason_detail) < 3:
            raise ApiError(400, 'Укажите Tech и причину Armor Upgrade')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        armor_item = next((item for item in data.get('inventory') or []
                           if isinstance(item, dict) and item.get('instance_id') == instance_id and
                           item.get('cat') == 'armor'), None)
        if not armor_item:
            raise ApiError(404, 'Concrete Armor/Shield instance не найден')
        states = data.setdefault('armor_tech_state', {})
        if isinstance(states.get(instance_id), dict) and states[instance_id].get('active'):
            raise ApiError(409, 'Armor/Shield уже имеет Tech Upgrade')
        catalog_item = item_by_id(catalog_item_id_for_entry(armor_item)) or armor_item
        locations = catalog_item.get('armor_locations') or []
        shield = 'shield' in locations
        base_sp = _num(catalog_item.get('sp'))
        if not shield and base_sp is None:
            raise ApiError(409, 'Armor instance не имеет upgradeable SP')
        mode = 'manual_shield_upgrade' if shield else 'sp_plus_one'
        now = time.time()
        state = {
            'active': True, 'mode': mode, 'permanent': True,
            'tech_name': tech_name, 'installed_by': user['id'],
            'installed_at': now, 'source': 'CP:R 148 · Upgrade Expertise',
            'manual_resolution_required': shield,
            'reason': reason_detail,
        }
        states[instance_id] = state
        if not shield:
            for location in ('head', 'body'):
                piece = (data.get('armor') or {}).get(location)
                if isinstance(piece, dict) and piece.get('instance_id') == instance_id:
                    previous_max = _num(piece.get('maximum'))
                    previous_max = previous_max if previous_max is not None else base_sp
                    previous_current = _num(piece.get('current'))
                    previous_current = previous_current if previous_current is not None else previous_max
                    piece['sp'] = base_sp + 1
                    piece['maximum'] = base_sp + 1
                    piece['current'] = min(base_sp + 1, previous_current + 1)
        validate_armor_tech_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'armor_tech_upgrade',
            source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        reason = (f'Tech Upgrade {armor_item.get("name")} '
                  f'({"SP +1" if not shield else "MANUAL SHIELD"}): {reason_detail}')
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['armor_tech_upgrade'] = {
            'instance_id': instance_id, 'mode': mode, 'permanent': True,
            'tech_name': tech_name, 'manual_resolution_required': shield,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'upgrade': state,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_tech_maker_create(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'name', 'description', 'host_instance_id',
                   'maker_specialty', 'tech_name', 'effect', 'manual_rule',
                   'manual_confirm', 'reason', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Tech Maker modification содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        name = str((body or {}).get('name') or '').strip()[:120]
        if len(name) < 2:
            raise ApiError(400, 'Укажите название Tech Maker modification')
        tech_name = str((body or {}).get('tech_name') or '').strip()[:120]
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(tech_name) < 2 or len(reason_detail) < 3:
            raise ApiError(400, 'Укажите Tech и причину Tech Maker modification')
        specialty = str((body or {}).get('maker_specialty') or '').strip().lower()
        if specialty not in TECH_MAKER_SPECIALTIES:
            raise ApiError(400, 'maker_specialty: upgrade/invention')
        host_id = str((body or {}).get('host_instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(host_id):
            raise ApiError(400, 'Выберите конкретный host instance')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                 if isinstance(item, dict) and item.get('instance_id')}
        owned.update({item.get('instance_id'): item for item in data.get('cyberware') or []
                      if isinstance(item, dict) and item.get('instance_id')})
        host = owned.get(host_id)
        if not host:
            raise ApiError(404, 'Host instance не найден')
        if host.get('state') in ('stored', 'broken', 'consumed'):
            raise ApiError(409, 'Host должен быть исправен и находиться при персонаже')
        host_type = tech_maker_host_type(host)
        if not host_type:
            raise ApiError(400, 'Host не поддерживает Tech Maker modifications')
        ranks = character_maker_ranks(data)
        rank = ranks.get(specialty, 0)
        if rank < 1:
            raise ApiError(409, f'Требуется Maker {specialty} rank 1+ для Tech Maker modification')
        effect = clean_tech_maker_effect(host_type, (body or {}).get('effect'))
        manual_rule = str((body or {}).get('manual_rule') or '').strip()[:1000]
        if effect is None and not manual_rule:
            raise ApiError(400, 'Tech Maker modification требует effect или manual_rule')
        if effect is not None and not bool((body or {}).get('manual_confirm')):
            raise ApiError(409, 'Подтвердите успешный Tech Maker Check за столом')
        state = data.setdefault('tech_maker_state', {})
        mods = state.setdefault('modifications', {})
        stack_key = (host_id, (effect or {}).get('target') or 'manual')
        for mod in mods.values():
            if (isinstance(mod, dict) and mod.get('active') and
                    (mod.get('host_instance_id'), (mod.get('effect') or {}).get('target') or 'manual') == stack_key):
                raise ApiError(409, 'Host уже имеет Tech Maker modification этого типа')
        if len(mods) >= 100:
            raise ApiError(409, 'Достигнут лимит Tech Maker modifications')
        modification_id = secrets.token_hex(16)
        now = time.time()
        source = f'Maker: {TECH_MAKER_SPECIALTY_LABELS[specialty][0]} · CP:R 148'
        record = {
            'modification_id': modification_id, 'name': name,
            'description': str((body or {}).get('description') or '').strip()[:2000],
            'host_instance_id': host_id, 'host_type': host_type,
            'host_catalog_item_id': catalog_item_id_for_entry(host),
            'maker_specialty': specialty, 'maker_rank': rank,
            'tech_name': tech_name, 'effect': effect,
            'manual_rule': manual_rule,
            'manual_resolution_required': effect is None,
            'source': source, 'active': True, 'permanent': False,
            'installed_by': user['id'], 'installed_at': now,
            'reason': reason_detail,
            'notes': str((body or {}).get('notes') or '')[:2000],
        }
        mods[modification_id] = record
        state.setdefault('history', []).append({
            'action': 'create', 'modification_id': modification_id,
            'name': name, 'host_instance_id': host_id, 'host_type': host_type,
            'maker_specialty': specialty, 'tech_name': tech_name, 'at': now,
        })
        state['history'] = state['history'][-50:]
        validate_tech_maker_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'tech_maker_create', source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Tech Maker {specialty}: {name} on {host.get("name")}: {reason_detail}',
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['tech_maker_modification'] = {
            'modification_id': modification_id, 'name': name,
            'host_instance_id': host_id, 'host_type': host_type,
            'maker_specialty': specialty, 'effect': copy.deepcopy(effect),
            'manual_rule': manual_rule,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'modification_id': modification_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    @atomic_endpoint
    def api_character_tech_maker_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Tech Maker action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Tech Maker action')
        modification_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        state = data.get('tech_maker_state')
        mods = state.get('modifications') if isinstance(state, dict) else {}
        mod = mods.get(modification_id) if isinstance(mods, dict) else None
        if not isinstance(mod, dict):
            raise ApiError(404, 'Tech Maker modification не найдена')
        action = str((body or {}).get('action') or '').lower()
        if action == 'remove':
            if mod.get('permanent'):
                raise ApiError(409, 'Permanent Tech Maker modification нельзя снять')
            if not mod.get('active'):
                raise ApiError(409, 'Tech Maker modification уже снята')
            mod['active'] = False
            mod['removed_by'] = user['id']
            mod['removed_at'] = time.time()
            state.setdefault('history', []).append({
                'action': 'remove', 'modification_id': modification_id,
                'name': mod.get('name'), 'host_instance_id': mod.get('host_instance_id'),
                'host_type': mod.get('host_type'), 'at': time.time(),
            })
            state['history'] = state['history'][-50:]
            reason = f'Remove Tech Maker modification {mod.get("name")}: {reason_detail}'
        else:
            raise ApiError(400, 'Tech Maker action: remove')
        validate_tech_maker_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'tech_maker_action', source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(),
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'modification_id': modification_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_tech_maker_fabricate(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'name', 'description', 'blueprint_catalog_id',
                   'category', 'price', 'qty', 'maker_specialty', 'tech_name',
                   'material_cost', 'manual_confirm', 'reason', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Tech Maker fabrication содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        name = str((body or {}).get('name') or '').strip()[:120]
        tech_name = str((body or {}).get('tech_name') or '').strip()[:120]
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(name) < 2 or len(tech_name) < 2 or len(reason_detail) < 3:
            raise ApiError(400, 'Укажите название, Tech и причину Tech Maker fabrication')
        specialty = str((body or {}).get('maker_specialty') or '').strip().lower()
        if specialty not in TECH_MAKER_FABRICATION_SPECIALTIES:
            raise ApiError(400, 'maker_specialty: fabrication/invention')
        if (body or {}).get('manual_confirm') is not True:
            raise ApiError(400, 'Подтвердите успешный Tech Maker Check за столом')
        try:
            material_cost = max(0, min(9_999_999, int((body or {}).get('material_cost') or 0)))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректная стоимость материалов')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        ranks = character_maker_ranks(data)
        rank = ranks.get(specialty, 0)
        if rank < 1:
            raise ApiError(409, f'Требуется Maker {specialty} rank 1+ для Tech Maker fabrication')
        blueprint_id = str((body or {}).get('blueprint_catalog_id') or '').strip()
        blueprint = item_by_id(blueprint_id) if blueprint_id else None
        if blueprint_id and not blueprint:
            raise ApiError(400, 'Неизвестный blueprint item')
        if blueprint and not tech_maker_fabricable_item(blueprint):
            raise ApiError(400, 'Этот предмет нельзя изготовить через Fabrication Expertise')
        if blueprint and specialty != 'fabrication':
            raise ApiError(400, 'Blueprint fabrication требует maker_specialty fabrication')
        if not blueprint and specialty == 'fabrication':
            raise ApiError(400, 'Fabrication Expertise требует blueprint item')
        try:
            qty = max(1, min(99, int((body or {}).get('qty') or 1)))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        if len(data.get('inventory') or []) + len(data.get('cyberware') or []) + qty > 500:
            raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
        cash = float(data.get('cash') or 0)
        if material_cost > cash + 1e-9:
            raise ApiError(400, f'Не хватает €$: нужно {material_cost:,.0f}, есть {cash:,.0f}')
        inventory = data.setdefault('inventory', [])
        created_instance_ids = []
        if blueprint:
            owned = {
                'key': blueprint['id'], 'catalog_item_id': blueprint['id'],
                'cat': blueprint['cat'], 'name': blueprint['name'],
                'price': blueprint.get('price'), 'qty': 1, 'state': 'carried',
                'damage': blueprint.get('damage'), 'sp': blueprint.get('sp'),
                'hl': blueprint.get('hl'),
                'fields': copy.deepcopy(blueprint.get('fields') or {}),
                'mechanics': copy.deepcopy(blueprint.get('mechanics') or {}),
                'source': blueprint.get('source'),
                'acquisition_source': 'crafted',
                'acquisition_note': f'Fabricated by {tech_name}: {reason_detail}'[:500],
            }
            owned.update(catalog_interaction_data(blueprint))
            owned.update({key: copy.deepcopy(blueprint[key]) for key in ITEM_MODIFICATION_FIELDS if key in blueprint})
            coverage = item_effect_coverage(blueprint.get('id'))
            if coverage:
                owned['effect_coverage'] = coverage
            if item_entry_stackable(owned):
                owned['instance_id'] = new_item_instance_id()
                owned['qty'] = qty
                if blueprint.get('cat') == 'ammo':
                    owned['ammo_rounds'] = qty * ammo_pack_size(owned)
                inventory.append(owned)
                created_instance_ids.append(owned['instance_id'])
            else:
                for _ in range(qty):
                    instance = copy.deepcopy(owned)
                    instance['instance_id'] = new_item_instance_id()
                    inventory.append(instance)
                    created_instance_ids.append(instance['instance_id'])
        else:
            category = str((body or {}).get('category') or 'custom').strip().lower()
            allowed_categories = {row2['id'] for row2 in catalog().get('cats') or []} | {'custom'}
            if category not in allowed_categories:
                raise ApiError(400, 'Некорректная категория custom item')
            price = trust_number((body or {}).get('price', 0),
                                 'Custom item value', 0, 9_999_999)
            stackable = False
            owned = {
                'is_custom': True, 'key': 'custom', 'cat': category,
                'name': name, 'custom_name': name,
                'desc': str((body or {}).get('description') or '')[:4000],
                'price': price, 'stackable': stackable, 'qty': 1,
                'state': 'carried', 'source': 'Tech Maker Invention',
                'manual_resolution_required': True,
                'acquisition_source': 'crafted',
                'acquisition_note': f'Invented by {tech_name}: {reason_detail}'[:500],
            }
            for _ in range(qty):
                instance = copy.deepcopy(owned)
                instance['instance_id'] = new_item_instance_id()
                instance['key'] = f'custom-{instance["instance_id"]}'
                inventory.append(instance)
                created_instance_ids.append(instance['instance_id'])
        data['cash'] = round(cash - material_cost, 2)
        # Fabricated firearms start unloaded, mirroring Night Market purchases.
        for instance_id in created_instance_ids:
            weapon = next((item for item in inventory
                           if isinstance(item, dict) and
                           item.get('instance_id') == instance_id), None)
            if weapon and weapon.get('cat') in ('guns', 'melee'):
                state = (data.get('weapon_state') or {}).get(instance_id)
                if state:
                    state['magazine'] = 0
        state = data.setdefault('tech_maker_state', {})
        fabrication_record = {
            'fabrication_id': secrets.token_hex(16), 'name': name,
            'blueprint_catalog_id': blueprint_id or None,
            'category': blueprint.get('cat') if blueprint else str(
                (body or {}).get('category') or 'custom'),
            'qty': qty, 'maker_specialty': specialty, 'maker_rank': rank,
            'tech_name': tech_name, 'material_cost': material_cost,
            'source': f'Maker: {TECH_MAKER_SPECIALTY_LABELS[specialty][0]} · CP:R 148',
            'at': time.time(), 'reason': reason_detail,
            'instance_ids': created_instance_ids,
        }
        fabrications = state.setdefault('fabrications', [])
        if not isinstance(fabrications, list):
            fabrications = []
            state['fabrications'] = fabrications
        fabrications.append(fabrication_record)
        state['fabrications'] = fabrications[-50:]
        validate_tech_maker_references(data)
        persist_character_item_instances(
            conn, row['id'], data, 'tech_maker_fabricate',
            source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data,
            f'Tech Maker {specialty}: fabricate {name} ×{qty}: {reason_detail}',
            current_revision, revision_after, category='item_action')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['tech_maker_fabrication'] = {
            'fabrication_id': fabrication_record['fabrication_id'],
            'name': name, 'blueprint_catalog_id': blueprint_id or None,
            'qty': qty, 'maker_specialty': specialty, 'material_cost': material_cost,
            'instance_ids': created_instance_ids,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(),
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'fabrication': fabrication_record,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        }, status=201)

    def api_downtime_activities(self, conn, qs, m, body):
        self.require_user(conn)
        self.send_json({'activities': DOWNTIME_ACTIVITIES})

    def api_character_downtime(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        data = ensure_progression(json.loads(row['data']))
        self.send_json(downtime_payload(data, conn=conn))

    @atomic_endpoint
    def api_character_downtime_start(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        allowed = {'revision', 'duration_key', 'activities', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Downtime start содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        state = downtime_state(data)
        if isinstance(state.get('active'), dict):
            raise ApiError(409, 'Downtime уже активен')
        duration_key = str((body or {}).get('duration_key') or '') or None
        duration_label = None
        if duration_key:
            duration = campaign_duration_seconds(duration_key)
            if duration is None:
                raise ApiError(400, 'Неизвестная длительность Downtime')
            duration_label = CAMPAIGN_DURATION_LABELS.get(duration_key)
        activities = clean_downtime_activities((body or {}).get('activities'))
        note = str((body or {}).get('note') or '').strip()[:1000]
        now = time.time()
        campaign_started = campaign_now(conn)
        active = {
            'downtime_id': secrets.token_hex(16),
            'started_at': now,
            'campaign_started_at': campaign_started,
            'campaign_due_at': campaign_started + duration if duration_key else None,
            'duration_key': duration_key,
            'duration_label': duration_label,
            'note': note,
            'created_by': user['id'],
            'activities': activities,
        }
        state['active'] = active
        reason = f'Downtime started: {note or duration_key or "manual"}'
        persist_character_item_instances(conn, row['id'], data, 'downtime_start',
                                         source_ref=reason)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='downtime')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['revertible'] = False
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now, revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ok': True, 'downtime': downtime_payload(
            ensure_progression(json.loads(fresh['data'])), conn=conn)}, status=201)

    @atomic_endpoint
    def api_character_downtime_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        allowed = {'revision', 'action', 'activity_id', 'earned', 'hp', 'note'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Downtime action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in ('resolve', 'complete', 'abandon'):
            raise ApiError(400, 'Downtime action: resolve/complete/abandon')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        state = downtime_state(data)
        active = state.get('active') if isinstance(state.get('active'), dict) else None
        if not active:
            raise ApiError(409, 'Нет активного Downtime')
        note = str((body or {}).get('note') or '').strip()[:1000]
        reason = None
        if action == 'resolve':
            activity_id = str((body or {}).get('activity_id') or '').strip().lower()
            activity = next((item for item in active.get('activities') or []
                             if item.get('id') == activity_id), None)
            if not activity:
                raise ApiError(404, 'Downtime activity не найдена')
            if activity.get('resolved'):
                raise ApiError(409, 'Downtime activity уже отмечена выполненной')
            catalog = DOWNTIME_ACTIVITY_BY_ID[activity_id]
            kind = catalog['kind']
            if kind == 'hustle':
                try:
                    earned = max(0.0, min(9_999_999.0, float((body or {}).get('earned') or 0)))
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректная сумма Hustle')
                cash = float(data.get('cash') or 0)
                if not math.isfinite(cash) or cash + earned > 9_999_999:
                    raise ApiError(400, 'Слишком большая сумма')
                data['cash'] = round(cash + earned, 2)
                resolution_note = note or f'Hustle: +€$ {earned:,.0f} (manual roll)'
                reason = f'Downtime Hustle: +€$ {earned:,.0f}'
            elif kind == 'recover_hp':
                try:
                    hp = max(0, min(1000, int((body or {}).get('hp') or 0)))
                except (TypeError, ValueError):
                    raise ApiError(400, 'Некорректное восстановление HP')
                derived = derive(data)
                hp_max = _num(derived.get('hp_max')) or _num(data.get('hp_cur')) or 0
                hp_cur = _num(data.get('hp_cur'))
                if hp_cur is not None and hp_max:
                    data['hp_cur'] = min(hp_max, hp_cur + hp)
                elif hp_cur is not None:
                    data['hp_cur'] = hp_cur + hp
                else:
                    data['hp_cur'] = hp
                resolution_note = note or f'Recover HP: +{hp}'
                reason = f'Downtime Recover HP: +{hp}'
            else:
                resolution_note = note or 'Resolved at the table'
                reason = f'Downtime activity resolved: {catalog["label_ru"]}'
            activity['resolved'] = True
            activity['resolution_note'] = resolution_note
            revision_after = current_revision + 1
            persist_character_item_instances(conn, row['id'], data, 'downtime_resolve',
                                             source_ref=reason)
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='downtime')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['revertible'] = False
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        elif action == 'complete':
            summary = str(note or 'Downtime completed').strip()[:1000]
            active['completed_at'] = time.time()
            active['summary'] = summary
            state['history'].append(active)
            state['history'] = state['history'][-50:]
            state['active'] = None
            reason = f'Downtime completed: {summary}'
            revision_after = current_revision + 1
            persist_character_item_instances(conn, row['id'], data, 'downtime_complete',
                                             source_ref=reason)
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='downtime')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['revertible'] = False
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        else:  # abandon
            summary = str(note or 'Downtime abandoned').strip()[:1000]
            active['completed_at'] = time.time()
            active['summary'] = summary
            state['history'].append(active)
            state['history'] = state['history'][-50:]
            state['active'] = None
            reason = f'Downtime abandoned: {summary}'
            revision_after = current_revision + 1
            persist_character_item_instances(conn, row['id'], data, 'downtime_abandon',
                                             source_ref=reason)
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='downtime')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['revertible'] = False
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(),
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ok': True, 'action': action,
                        'downtime': downtime_payload(
                            ensure_progression(json.loads(fresh['data'])), conn=conn)})

    @atomic_endpoint
    def api_character_popup_weapon_bind(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'weapon_instance_id', 'permanent_confirmed', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Popup Weapon binding содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        if (body or {}).get('permanent_confirmed') is not True:
            raise ApiError(400, 'Подтвердите permanent Popup Weapon binding')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Popup Weapon binding')
        option_id = str(m.group(2)).lower()
        weapon_id = str((body or {}).get('weapon_instance_id') or '').lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        option = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and item.get('instance_id') == option_id), None)
        if not option or not cyberware_is_installed(option) or not popup_weapon_binding_kind(option):
            raise ApiError(404, 'Installed generic Popup Weapon option не найден')
        runtime_states = data.setdefault('cyberware_state', {})
        runtime = runtime_states.setdefault(option_id, {})
        if runtime.get('bound_weapon_instance_id'):
            raise ApiError(409, 'Popup Weapon уже имеет permanent bound weapon')
        weapon = next((item for item in data.get('inventory') or []
                       if isinstance(item, dict) and item.get('instance_id') == weapon_id), None)
        compatibility = popup_weapon_binding_compatibility(option, weapon)
        if not compatibility['allowed']:
            raise ApiError(400, '; '.join(compatibility['reasons']))
        weapon['state'] = 'installed'
        weapon['installed_cyberware_instance_id'] = option_id
        host_ids = cyberware_host_assignments(option)
        weapon['installed_cyberarm_host_id'] = host_ids[0] if host_ids else None
        runtime['bound_weapon_instance_id'] = weapon_id
        runtime['bound_weapon_permanent'] = True
        runtime['bound_at'] = time.time()
        runtime['binding_reason'] = reason_detail
        validate_bound_popup_weapon_references(data)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'popup_weapon_binding',
            source_ref=reason_detail, prune=True)
        revision_after = current_revision + 1
        reason = (f'Permanently bind {weapon.get("name")} to '
                  f'{option.get("name")}: {reason_detail}')
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='modification')
        ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                  (ledger_id,)).fetchone()
        delta = parse_json_object(ledger_row['delta_json'])
        delta['popup_weapon_binding'] = {
            'option_instance_id': option_id, 'weapon_instance_id': weapon_id,
            'permanent': True, 'attachments_preserved': True,
        }
        conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                     (json.dumps(delta, ensure_ascii=False), ledger_id))
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'compatibility': compatibility,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_cyberware_weapon_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'ammo_instance_id', 'payload_type', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Cyberweapon action содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Cyberweapon action')
        instance_id = str(m.group(2)).lower()
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        chrome = next((item for item in data.get('cyberware') or []
                       if isinstance(item, dict) and item.get('instance_id') == instance_id), None)
        profile = cyberware_weapon_profile(chrome) or bound_popup_weapon_profile(data, chrome)
        if not chrome or not cyberware_is_installed(chrome) or not profile:
            raise ApiError(404, 'Installed curated Cyberweapon не найден')
        runtime_states = data.setdefault('cyberware_state', {})
        runtime = runtime_states.setdefault(instance_id, {})
        bound_weapon = next((item for item in data.get('inventory') or []
                             if isinstance(item, dict) and item.get('instance_id') ==
                             profile.get('bound_weapon_instance_id')), None)
        if bound_weapon:
            weapon_state = data.setdefault('weapon_state', {}).setdefault(
                bound_weapon['instance_id'], {
                    'magazine': int(profile.get('magazine') or 0),
                    'magazine_max': int(profile.get('magazine') or 0), 'reserve': 0,
                })
            weapon_state.setdefault('deployed', False)
            weapon_state.setdefault('revved', False)
        else:
            weapon_state = runtime.setdefault('weapon', {
                'deployed': not profile.get('deployable'), 'revved': False,
                'magazine': 0, 'magazine_max': int(profile.get('magazine') or 0),
            })
        maximum = max(0, int(_num(profile.get('magazine')) or 0))
        weapon_state['magazine_max'] = maximum
        weapon_state['magazine'] = max(
            0, min(maximum, int(_num(weapon_state.get('magazine')) or 0)))
        action = str((body or {}).get('action') or '').lower()
        result = {'action': action, 'profile_id': profile['id']}
        if action in ('deploy', 'stow'):
            if not profile.get('deployable'):
                raise ApiError(409, 'Cyberweapon не имеет deploy/stow state')
            weapon_state['deployed'] = action == 'deploy'
            if action == 'stow':
                weapon_state['revved'] = False
            reason = f'{action.title()} Cyberweapon {chrome.get("name")}: {reason_detail}'
        elif action in ('rev', 'rev_down'):
            if not profile.get('rev_action'):
                raise ApiError(409, 'Cyberweapon не имеет rev action')
            if profile.get('deployable') and not weapon_state.get('deployed'):
                raise ApiError(409, 'Сначала deploy Cyberweapon')
            weapon_state['revved'] = action == 'rev'
            reason = f'{action} Cyberweapon {chrome.get("name")}: {reason_detail}'
        elif action == 'fire':
            if profile.get('kind') not in ('ranged', 'ranged_dual'):
                raise ApiError(409, 'Fire доступен только ranged Cyberweapon')
            if profile.get('deployable') and not weapon_state.get('deployed'):
                raise ApiError(409, 'Сначала deploy Cyberweapon')
            current = weapon_state['magazine']
            if current < 1:
                raise ApiError(409, 'Cyberweapon magazine пуст')
            weapon_state['magazine'] = current - 1
            clear_loaded_ammo_if_empty(weapon_state)
            # Special payload drains entirely on fire (Gas Jet)
            if profile.get('special_ammo') and weapon_state.get('magazine', 0) == 0:
                weapon_state.pop('loaded_payload', None)
                weapon_state.pop('loaded_ammo_kind', None)
            result.update({'magazine_before': current,
                           'magazine_after': weapon_state['magazine']})
            # Manual effect hint for special weapons
            if profile.get('special_ammo') and profile.get('manual_effect'):
                result['manual_effect'] = profile['manual_effect']
                result['manual_resolution_required'] = True
            reason = f'Fire Cyberweapon {chrome.get("name")}: {reason_detail}'
        elif action == 'reload':
            if maximum <= 0:
                raise ApiError(409, 'Cyberweapon не использует tracked ammo')
            if profile.get('special_ammo'):
                if weapon_state.get('magazine', 0) >= maximum:
                    raise ApiError(409, 'Магазин уже заполнен')
                payload = None
                if profile['id'] == 'gas-jet':
                    payload_raw = str((body or {}).get('payload_type') or '').strip().lower()
                    allowed = set(profile.get('payload_options') or ['street_drug', 'poison', 'biotoxin'])
                    if payload_raw not in allowed:
                        raise ApiError(400, 'Выберите payload для Gas Jet: street_drug / poison / biotoxin')
                    payload = payload_raw
                    weapon_state['loaded_payload'] = payload
                elif profile['id'] == 'popup-net-launcher':
                    weapon_state['loaded_payload'] = 'net'
                elif profile['id'] in ('dartgun', 'dartgun-cyberfinger'):
                    weapon_state['loaded_payload'] = 'dart'
                    weapon_state.pop('loaded_ammo_kind', None)
                weapon_state['magazine'] = maximum
                weapon_state.pop('loaded_ammo_catalog_id', None)
                weapon_state.pop('loaded_ammo_name', None)
                if payload != 'street_drug' and payload is not None:
                    weapon_state.pop('loaded_ammo_kind', None)
                result['special_reload'] = True
                result['loaded_payload'] = weapon_state.get('loaded_payload')
                result['magazine_after'] = maximum
                if payload:
                    reason = f'Reload Cyberweapon {chrome.get("name")} [{payload}]: {reason_detail}'
                else:
                    reason = f'Reload Cyberweapon {chrome.get("name")} [special ammo]: {reason_detail}'
            else:
                ammo_id = str((body or {}).get('ammo_instance_id') or '').lower()
                ammo = next((item for item in data.get('inventory') or []
                             if isinstance(item, dict) and item.get('instance_id') == ammo_id), None)
                ammo_kinds = profile.get('ammo_kinds') or ([profile.get('ammo_kind')]
                                                           if profile.get('ammo_kind') else [])
                if bound_weapon:
                    if not ammo_matches_requirement(ammo, weapon=bound_weapon):
                        raise ApiError(400, 'Ammo stack несовместим с Cyberweapon')
                    transfer = consume_shared_ammo(
                        data, weapon_state, ammo_id, weapon=bound_weapon)
                    ammo_kind = None
                else:
                    ammo_kind = next((kind for kind in ammo_kinds
                                      if ammo_matches_requirement(ammo, kind)), None)
                    if not ammo_kind:
                        raise ApiError(400, 'Ammo stack несовместим с Cyberweapon')
                    transfer = consume_shared_ammo(
                        data, weapon_state, ammo_id, ammo_kind=ammo_kind)
                if ammo_kind:
                    weapon_state['loaded_ammo_kind'] = ammo_kind
                result['transfer'] = transfer
                reason = (f'Reload Cyberweapon {chrome.get("name")} with '
                          f'{transfer["ammo_name"]} ×{transfer["moved"]}: {reason_detail}')
        else:
            raise ApiError(400, 'Cyberweapon action: deploy/stow/rev/rev_down/fire/reload')
        if not bound_weapon:
            runtime['weapon'] = weapon_state
        validate_bound_popup_weapon_references(data)
        validate_active_modification_references(conn, row['id'], data)
        persist_character_item_instances(
            conn, row['id'], data, 'cyberweapon_action', source_ref=reason, prune=True)
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        now = time.time()
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id, 'result': result,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_item_action(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        expected_revision = _num((body or {}).get('revision'))
        current_revision = _row_value(row, 'revision', 0) or 0
        if expected_revision is None or expected_revision != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        instance_id = str(m.group(2)).lower()
        index = next((position for position, entry in enumerate(data.get('inventory') or [])
                      if isinstance(entry, dict) and entry.get('instance_id') == instance_id), None)
        if index is None:
            raise ApiError(404, 'Экземпляр предмета не найден')
        entry = data['inventory'][index]
        catalog_item = item_by_id(catalog_item_id_for_entry(entry))
        interaction = catalog_interaction_data(catalog_item)
        action = str((body or {}).get('action') or '').strip().lower()
        display_name = str(entry.get('custom_name') or entry.get('name') or 'Item')
        effect = None
        use_effect_result = {'created': [], 'replaced_effect_ids': [], 'manual_rules': []}

        if action == 'use':
            if not interaction.get('consumable'):
                raise ApiError(400, 'Этот предмет не является расходником')
            if entry.get('state') in ('stored', 'broken', 'consumed'):
                raise ApiError(409, 'Расходник должен быть исправен и находиться при персонаже')
            try:
                uses = max(1, min(99, int((body or {}).get('amount') or 1)))
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректное количество')
            consume_amount = max(1, int(interaction.get('consume_amount') or 1))
            spent = uses * consume_amount
            quantity = max(1, int(entry.get('qty') or 1))
            if spent > quantity:
                raise ApiError(400, 'Недостаточно единиц расходника')
            remaining = quantity - spent
            if remaining:
                entry['qty'] = remaining
            else:
                data['inventory'].pop(index)
            effect = copy.deepcopy(interaction.get('use_effect'))
            reason = f'Use {display_name} ×{spent}'
            use_effect_result = instantiate_consumable_effects(
                conn, row['id'], user['id'], entry)
        elif action == 'equip':
            if not interaction.get('equippable'):
                raise ApiError(400, 'Этот предмет нельзя экипировать')
            if entry.get('state') != 'carried':
                raise ApiError(409, 'Экипировать можно только carried предмет')
            modes = interaction.get('equip_modes') or ['ready']
            mode = str((body or {}).get('mode') or modes[0])
            if mode not in modes:
                raise ApiError(400, 'Недопустимый режим экипировки')
            hands_required = max(0, int(interaction.get('hands_required') or 0)) if mode == 'held' else 0
            occupied_hands = 0
            for equipped in data.get('inventory') or []:
                if (not isinstance(equipped, dict) or equipped.get('state') != 'equipped' or
                        equipped.get('equipped_mode') != 'held'):
                    continue
                equipped_item = item_by_id(catalog_item_id_for_entry(equipped))
                occupied_hands += max(0, int((equipped_item or {}).get('hands_required') or 0))
            shoulder_mounts = sum(
                1 for chrome in data.get('cyberware') or []
                if isinstance(chrome, dict) and chrome.get('state') == 'installed' and
                str(chrome.get('name') or '').lower() == 'artificial shoulder mount')
            available_hands = 2 + shoulder_mounts * 2
            if occupied_hands + hands_required > available_hands:
                raise ApiError(409, 'Недостаточно свободных рук для экипировки')
            limit = _num(interaction.get('equip_limit'))
            if limit is not None:
                equipped_count = sum(
                    1 for owned in data.get('inventory') or []
                    if isinstance(owned, dict) and owned.get('state') == 'equipped' and
                    catalog_item_id_for_entry(owned) == catalog_item_id_for_entry(entry))
                if equipped_count >= limit:
                    raise ApiError(409, 'Достигнут лимит экипированных копий')
            slots = interaction.get('equip_slots') or []
            slot_defaults = {'held': 'hand', 'worn': 'ear', 'ready': 'belt',
                             'workspace': 'workspace', 'mounted': 'weapon'}
            slot = str((body or {}).get('slot') or slot_defaults.get(mode) or (slots[0] if slots else 'other'))
            if slots and slot not in slots:
                raise ApiError(400, 'Недопустимый слот экипировки')
            entry.update({
                'state': 'equipped', 'equipped_mode': mode, 'equipped_slot': slot,
                'active': not bool(interaction.get('activation_required')),
            })
            reason = f'Equip {display_name} ({mode})'
        elif action == 'unequip':
            if entry.get('state') != 'equipped':
                raise ApiError(409, 'Предмет не экипирован')
            entry['state'] = 'carried'
            for key in ('active', 'equipped_mode', 'equipped_slot', 'host_instance_id'):
                entry.pop(key, None)
            reason = f'Unequip {display_name}'
        elif action in ('activate', 'deactivate'):
            if not interaction.get('equippable') or not interaction.get('activation_required'):
                raise ApiError(400, 'Предмет не поддерживает включение и выключение')
            if entry.get('state') != 'equipped':
                raise ApiError(409, 'Сначала экипируйте предмет')
            active = action == 'activate'
            if bool(entry.get('active')) == active:
                raise ApiError(409, 'Предмет уже находится в выбранном состоянии')
            entry['active'] = active
            reason = f'{"Activate" if active else "Deactivate"} {display_name}'
        else:
            raise ApiError(400, 'Неизвестное действие с предметом')

        revision_after = current_revision + 1
        persist_character_item_instances(
            conn, row['id'], data, 'item_action', source_ref=reason, prune=True)
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='item_action')
        if use_effect_result['created']:
            ledger_row = conn.execute(
                'SELECT delta_json FROM character_ledger WHERE id=?', (ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            delta['created_effect_ids'] = [item['effect_id'] for item in use_effect_result['created']]
            delta['replaced_effect_ids'] = use_effect_result['replaced_effect_ids']
            delta['manual_rules'] = use_effect_result['manual_rules']
            for created_effect in use_effect_result['created']:
                definition = created_effect.get('definition') or {}
                delta.setdefault('changes', []).append({
                    'path': f'effects.instances.{created_effect["effect_id"]}',
                    'label': f'Effect: {created_effect["label"]}', 'kind': 'added',
                    'before': '—',
                    'after': readable_change_value({
                        'status': created_effect.get('status'),
                        'target': definition.get('target'),
                        'operation': definition.get('operation'),
                        'value': definition.get('value'),
                        'duration': created_effect.get('duration_type'),
                    }),
                })
            delta['change_count'] = len(delta.get('changes') or [])
            conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                         (json.dumps(delta, ensure_ascii=False), ledger_id))
        conn.execute(
            'UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
            (json.dumps(data, ensure_ascii=False), time.time(), revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ok': True, 'action': action, 'message': reason, 'effect': effect,
            'created_effects': use_effect_result['created'],
            'manual_rules': use_effect_result['manual_rules'],
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
    def api_character_item_transfer(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1), allow_gm=True)
        allowed = {'revision', 'action', 'to_char_id', 'to_instance_id',
                   'to_revision', 'quantity', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Item transfer содержит неподдерживаемые поля')
        action = str((body or {}).get('action') or '').strip().lower()
        if action not in TRANSFER_KINDS:
            raise ApiError(400, 'Неизвестный тип передачи предмета')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        instance_id = str(m.group(2)).lower()
        if not INSTANCE_ID_RE.fullmatch(instance_id):
            raise ApiError(400, 'Некорректный идентификатор предмета')
        notes = str((body or {}).get('notes') or '').strip()[:500]
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        sides = []

        def load_side(target_row):
            target_before = enrich_owned_item_interactions(
                ensure_progression(json.loads(target_row['data'])))
            return target_before, copy.deepcopy(target_before)

        def parse_qty():
            raw = (body or {}).get('quantity')
            if raw is None:
                return None
            try:
                return max(1, int(raw))
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректное количество')

        def move(source_data, source_row_id, target_instance_id, qty, dest,
                 loan_ok=False, force_unequip=False):
            """Move one instance out of ``source_data`` into stash or a character.

            ``dest`` is ``('stash',)`` or ``('char', target_data, target_char_id)``.
            Returns ``(moved_instance_id, moved_qty, name)``.
            """
            index, entry = _inventory_entry(source_data, target_instance_id)
            if index is None:
                raise ApiError(404, 'Экземпляр предмета не найден')
            if force_unequip and entry.get('state') in ('equipped', 'installed'):
                entry['state'] = 'carried'
                for key in ('equipped_mode', 'equipped_slot', 'active',
                            'host_instance_id', 'host_instances'):
                    entry.pop(key, None)
            loan = active_loan_for_instance(conn, target_instance_id)
            _transferable_item_error(conn, source_row_id, entry, source_data,
                                     loan, loan_ok=loan_ok)
            full_qty = max(1, int(entry.get('qty') or 1))
            qty = full_qty if qty is None else int(qty)
            if qty <= 0 or qty > full_qty:
                raise ApiError(400, 'Некорректное количество для передачи')
            if not item_entry_stackable(entry) and qty > 1:
                raise ApiError(400, 'Этот предмет передаётся поштучно (не stackable)')
            name = _character_item_name(entry)
            partial = qty < full_qty
            if partial:
                remaining, taken = _split_stack(entry, qty)
                source_data['inventory'][index] = remaining
                moved_id = new_item_instance_id()
                taken['instance_id'] = moved_id
            else:
                source_data['inventory'].pop(index)
                taken = entry
                moved_id = target_instance_id
                _detach_runtime_state(source_data, taken, target_instance_id)
                _detach_tech_maker_modifications(source_data, taken, target_instance_id)
                # Rehome the relational row now so persist never regenerates the
                # stable instance_id across characters.
                if dest[0] == 'stash':
                    conn.execute('DELETE FROM item_instances WHERE instance_id=?',
                                 (moved_id,))
                else:
                    conn.execute(
                        'UPDATE item_instances SET character_id=? WHERE instance_id=?',
                        (dest[2], moved_id))
            if dest[0] == 'stash':
                cleaned = _prepare_entry_for_holder(taken, 'stash')
                cleaned['instance_id'] = moved_id
                now = time.time()
                conn.execute(
                    'INSERT INTO crew_stash(instance_id,catalog_item_id,custom_name,'
                    'state,quantity,notes,stored_at,data_json,created,updated) '
                    'VALUES(?,?,?,?,?,?,?,?,?,?)',
                    (moved_id, catalog_item_id_for_entry(taken),
                     str(cleaned.get('custom_name') or '')[:120] or None, 'stored',
                     cleaned['qty'], '', now, json.dumps(cleaned, ensure_ascii=False),
                     now, now))
            else:
                target_data = dest[1]
                if len(target_data.get('inventory') or []) + 1 > 500:
                    raise ApiError(400, 'Инвентарь получателя переполнен')
                cleaned = _prepare_entry_for_holder(taken, 'char')
                cleaned['instance_id'] = moved_id
                _attach_runtime_state(target_data, cleaned, moved_id)
                _attach_tech_maker_modifications(target_data, cleaned)
                target_data.setdefault('inventory', []).append(cleaned)
            return moved_id, qty, name

        message = ''
        if action == 'split':
            index, entry = _inventory_entry(data, instance_id)
            if index is None:
                raise ApiError(404, 'Экземпляр предмета не найден')
            if not item_entry_stackable(entry):
                raise ApiError(400, 'Делить можно только stackable предметы')
            loan = active_loan_for_instance(conn, instance_id)
            if loan is not None and loan['borrower_character_id'] == row['id']:
                raise ApiError(409, 'Предмет взят в долг — его нельзя делить')
            full_qty = max(1, int(entry.get('qty') or 1))
            try:
                take_qty = max(1, int((body or {}).get('quantity') or 0))
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректное количество')
            if take_qty >= full_qty:
                raise ApiError(400, 'Для разделения укажите количество меньше размера стека')
            remaining, taken = _split_stack(entry, take_qty)
            data['inventory'][index] = remaining
            new_id = new_item_instance_id()
            taken['instance_id'] = new_id
            data['inventory'].append(taken)
            message = f'Split {_character_item_name(entry)} ×{take_qty}'
            _record_item_transfer(
                conn, new_id, 'split', user['id'], notes,
                from_character_id=row['id'], to_character_id=row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=take_qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
        elif action == 'stash':
            moved_id, qty, name = move(data, row['id'], instance_id, parse_qty(), ('stash',))
            message = f'Move {name} ×{qty} to Crew Stash'
            _record_item_transfer(
                conn, moved_id, 'stash', user['id'], notes,
                from_character_id=row['id'], to_character_id=None,
                from_bucket='inventory', to_bucket='stash', quantity=qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
        elif action in ('give', 'loan'):
            to_char_id = _num((body or {}).get('to_char_id'))
            if not to_char_id:
                raise ApiError(400, 'Укажите получателя (to_char_id)')
            target_row = self.get_char(conn, to_char_id)
            if target_row['id'] == row['id']:
                raise ApiError(400, 'Нельзя передать предмет самому себе')
            if parse_json_object(target_row['data']).get('archived'):
                raise ApiError(409, 'Досье получателя заархивировано')
            target_before, target_data = load_side(target_row)
            moved_id, qty, name = move(data, row['id'], instance_id, parse_qty(),
                                       ('char', target_data, target_row['id']))
            if action == 'loan':
                conn.execute(
                    'INSERT INTO item_loans(loan_id,instance_id,owner_character_id,'
                    'borrower_character_id,quantity,loaned_by,loaned_at,notes) '
                    'VALUES(?,?,?,?,?,?,?,?)',
                    (secrets.token_hex(16), moved_id, row['id'], target_row['id'], qty,
                     user['id'], time.time(), notes))
            message = f'{"Loan" if action == "loan" else "Give"} {name} ×{qty}'
            _record_item_transfer(
                conn, moved_id, action, user['id'], notes,
                from_character_id=row['id'], to_character_id=target_row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
            sides.append({'id': target_row['id'], 'before': target_before,
                          'data': target_data, 'reason': message})
        elif action == 'return':
            loan = active_loan_for_instance(conn, instance_id)
            if not loan or loan['borrower_character_id'] != row['id']:
                raise ApiError(409, 'Предмет не числится за вами как долг')
            owner_row = self.get_char(conn, loan['owner_character_id'])
            if parse_json_object(owner_row['data']).get('archived'):
                raise ApiError(409, 'Досье владельца заархивировано')
            owner_before, owner_data = load_side(owner_row)
            moved_id, qty, name = move(data, row['id'], instance_id, None,
                                       ('char', owner_data, owner_row['id']), loan_ok=True)
            conn.execute('UPDATE item_loans SET returned_at=?,returned_by=? WHERE loan_id=?',
                         (time.time(), user['id'], loan['loan_id']))
            message = f'Return {name} ×{qty} to owner'
            _record_item_transfer(
                conn, moved_id, 'return', user['id'], notes,
                from_character_id=row['id'], to_character_id=owner_row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
            sides.append({'id': owner_row['id'], 'before': owner_before,
                          'data': owner_data, 'reason': message})
        elif action == 'recall':
            loan = active_loan_for_instance(conn, instance_id)
            if not loan or loan['owner_character_id'] != row['id']:
                raise ApiError(409, 'Предмет не числится как выданный вами в долг')
            borrower_row = self.get_char(conn, loan['borrower_character_id'])
            borrower_before, borrower_data = load_side(borrower_row)
            moved_id, qty, name = move(borrower_data, borrower_row['id'], instance_id,
                                       None, ('char', data, row['id']), loan_ok=True,
                                       force_unequip=True)
            conn.execute('UPDATE item_loans SET returned_at=?,returned_by=? WHERE loan_id=?',
                         (time.time(), user['id'], loan['loan_id']))
            message = f'Recall {name} ×{qty} from borrower'
            _record_item_transfer(
                conn, moved_id, 'recall', user['id'], notes,
                from_character_id=borrower_row['id'], to_character_id=row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            # The losing side must persist first so the stable instance_id is freed.
            sides.append({'id': borrower_row['id'], 'before': borrower_before,
                          'data': borrower_data, 'reason': message})
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
        elif action == 'trade':
            to_char_id = _num((body or {}).get('to_char_id'))
            to_instance_id = str((body or {}).get('to_instance_id') or '').lower()
            if not to_char_id:
                raise ApiError(400, 'Укажите партнёра обмена (to_char_id)')
            if not INSTANCE_ID_RE.fullmatch(to_instance_id):
                raise ApiError(400, 'Укажите предмет партнёра (to_instance_id)')
            if to_instance_id == instance_id:
                raise ApiError(400, 'Нельзя обменять предмет на самого себя')
            target_row = self.get_char(conn, to_char_id)
            if target_row['id'] == row['id']:
                raise ApiError(400, 'Нельзя обменяться с самим собой')
            if parse_json_object(target_row['data']).get('archived'):
                raise ApiError(409, 'Досье партнёра заархивировано')
            target_revision = _row_value(target_row, 'revision', 0) or 0
            if _num((body or {}).get('to_revision')) != target_revision:
                raise ApiError(409, 'Dossier партнёра изменён в другой вкладке; обновите страницу')
            target_before, target_data = load_side(target_row)
            moved_id, qty, name = move(data, row['id'], instance_id, None,
                                       ('char', target_data, target_row['id']))
            other_id, other_qty, other_name = move(
                target_data, target_row['id'], to_instance_id, None,
                ('char', data, row['id']))
            message = f'Trade {name} ↔ {other_name}'
            _record_item_transfer(
                conn, moved_id, 'trade', user['id'], notes,
                from_character_id=row['id'], to_character_id=target_row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=qty)
            _record_item_transfer(
                conn, other_id, 'trade', user['id'], notes,
                from_character_id=target_row['id'], to_character_id=row['id'],
                from_bucket='inventory', to_bucket='inventory', quantity=other_qty)
            sides.append({'id': row['id'], 'before': before, 'data': data, 'reason': message})
            sides.append({'id': target_row['id'], 'before': target_before,
                          'data': target_data, 'reason': message})

        if not sides:
            raise ApiError(400, 'Неизвестный тип передачи предмета')
        for side in sides:
            _persist_transfer_side(conn, side['id'], side['data'],
                                   'item_transfer', side['reason'])
            side_row = self.get_char(conn, side['id'])
            revision = _row_value(side_row, 'revision', 0) or 0
            _record_transfer_ledger(conn, side['id'], user['id'], side['before'],
                                    side['data'], side['reason'], revision, revision + 1)
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(side['data'], ensure_ascii=False), time.time(),
                          revision + 1, side['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({'ok': True, 'action': action, 'message': message,
                        'character': self.char_payload(fresh, fresh['owner'], conn=conn)})

    def api_personal_stash(self, conn, qs, m, body):
        user = self.require_user(conn)
        cid = int(m.group(1))
        char = conn.execute('SELECT * FROM characters WHERE id=?', (cid,)).fetchone()
        if not char:
            raise ApiError(404, 'Персонаж не найден')
        if char['owner_id'] != user['id'] and not user_is_gm(user):
            raise ApiError(403, 'Это не ваш персонаж')
        rows = conn.execute(
            'SELECT * FROM personal_stash WHERE character_id=? ORDER BY stored_at', (cid,)).fetchall()
        payload = []
        for row in rows:
            item = dict(row)
            try:
                item.update(json.loads(row['data_json'] or '{}'))
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
            payload.append(item)
        self.send_json({'stash': payload, 'character_id': cid})

    @atomic_endpoint
    def api_personal_stash_action(self, conn, qs, m, body):
        user = self.require_user(conn)
        cid = int(m.group(1))
        char = conn.execute('SELECT * FROM characters WHERE id=?', (cid,)).fetchone()
        if not char:
            raise ApiError(404, 'Персонаж не найден')
        if char['owner_id'] != user['id'] and not user_is_gm(user):
            raise ApiError(403, 'Это не ваш персонаж')
        action = str((body or {}).get('action') or '').lower()
        instance_id = str((body or {}).get('instance_id') or '').lower()
        if action not in ('store', 'take'):
            raise ApiError(400, 'Действие: store или take')
        if action == 'take':
            row = conn.execute(
                'SELECT * FROM personal_stash WHERE instance_id=? AND character_id=?',
                (instance_id, cid)).fetchone()
            if not row:
                raise ApiError(404, 'Предмет не найден в личном тайнике')
            data = json.loads(char['data'])
            data = ensure_progression(data)
            ensure_character_item_instances(data)
            item_data = json.loads(row['data_json'] or '{}')
            item_data['instance_id'] = instance_id
            item_data['state'] = 'carried'
            data.setdefault('inventory', []).append(item_data)
            persist_character_item_instances(conn, cid, data, 'personal_stash_take')
            conn.execute('DELETE FROM personal_stash WHERE instance_id=? AND character_id=?',
                         (instance_id, cid))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), time.time(), cid))
            conn.commit()
            self.send_json({'ok': True, 'action': 'take'})
        else:  # store
            data = json.loads(char['data'])
            data = ensure_progression(data)
            inv = data.get('inventory') or []
            item = next((e for e in inv if isinstance(e, dict) and e.get('instance_id') == instance_id), None)
            if not item:
                raise ApiError(404, 'Предмет не найден в инвентаре')
            if item.get('state') in ('equipped', 'installed'):
                raise ApiError(409, 'Сначала снимите предмет')
            stash_data = copy.deepcopy(item)
            for key in ('active',):
                stash_data.pop(key, None)
            stash_data['state'] = 'stored'
            now = time.time()
            conn.execute(
                'INSERT OR REPLACE INTO personal_stash(instance_id,character_id,catalog_item_id,'
                'custom_name,state,quantity,notes,stored_at,data_json,created,updated) '
                'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
                (instance_id, cid, stash_data.get('catalog_item_id') or stash_data.get('key') or '',
                 str(stash_data.get('custom_name') or stash_data.get('name') or '')[:120],
                 'stored', max(1, int(stash_data.get('qty') or 1)),
                 str(stash_data.get('notes') or '')[:5000], now,
                 json.dumps(stash_data, ensure_ascii=False), now, now))
            inv = [e for e in inv if not (isinstance(e, dict) and e.get('instance_id') == instance_id)]
            data['inventory'] = inv
            persist_character_item_instances(conn, cid, data, 'personal_stash_store')
            conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), time.time(), cid))
            conn.commit()
            self.send_json({'ok': True, 'action': 'store'})

    def api_crew_stash(self, conn, qs, m, body):
        user = self.require_user(conn)
        self.send_json({
            'stash': crew_stash_payload(conn),
            'characters': transfer_targets(conn, user),
        })

    @atomic_endpoint
    def api_crew_stash_take(self, conn, qs, m, body):
        user, target_row = self.require_character_editor(
            conn, _num((body or {}).get('char_id')), allow_gm=True)
        allowed = {'char_id', 'instance_id', 'quantity', 'notes'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Crew Stash take содержит неподдерживаемые поля')
        instance_id = str((body or {}).get('instance_id') or '').lower()
        if not INSTANCE_ID_RE.fullmatch(instance_id):
            raise ApiError(400, 'Некорректный идентификатор предмета')
        stash_row = conn.execute(
            'SELECT * FROM crew_stash WHERE instance_id=?', (instance_id,)).fetchone()
        if not stash_row:
            raise ApiError(404, 'Предмет не найден в Crew Stash')
        notes = str((body or {}).get('notes') or '').strip()[:500]
        target_before = enrich_owned_item_interactions(
            ensure_progression(json.loads(target_row['data'])))
        target_data = copy.deepcopy(target_before)
        entry = parse_json_object(stash_row['data_json'])
        full_qty = max(1, int(entry.get('qty') or 1))
        try:
            qty = max(1, int((body or {}).get('quantity') or 0)) \
                if (body or {}).get('quantity') is not None else full_qty
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        if qty > full_qty:
            raise ApiError(400, 'Недостаточно единиц в Crew Stash')
        if not item_entry_stackable(entry) and qty > 1:
            raise ApiError(400, 'Этот предмет берётся поштучно (не stackable)')
        partial = qty < full_qty
        taken = copy.deepcopy(entry)
        taken['qty'] = qty
        if entry.get('cat') == 'ammo':
            pack = ammo_pack_size(entry)
            rounds = ammo_rounds(entry)
            taken['ammo_rounds'] = qty * pack
            remaining_rounds = max(0, rounds - qty * pack)
        else:
            remaining_rounds = None
        moved_id = instance_id
        if partial:
            remaining = copy.deepcopy(entry)
            remaining['qty'] = full_qty - qty
            if remaining_rounds is not None:
                remaining['ammo_rounds'] = remaining_rounds
            moved_id = new_item_instance_id()
            taken['instance_id'] = moved_id
            conn.execute(
                'UPDATE crew_stash SET quantity=?,data_json=?,updated=? WHERE instance_id=?',
                (remaining['qty'], json.dumps(remaining, ensure_ascii=False),
                 time.time(), instance_id))
        else:
            conn.execute('DELETE FROM crew_stash WHERE instance_id=?', (instance_id,))
        taken['instance_id'] = moved_id
        _attach_runtime_state(target_data, taken, moved_id)
        _attach_tech_maker_modifications(target_data, taken)
        cleaned = _prepare_entry_for_holder(taken, 'char')
        cleaned['instance_id'] = moved_id
        target_data.setdefault('inventory', []).append(cleaned)
        message = f'Take {_character_item_name(taken)} ×{qty} from Crew Stash'
        _record_item_transfer(
            conn, moved_id, 'take', user['id'], notes,
            from_character_id=None, to_character_id=target_row['id'],
            from_bucket='stash', to_bucket='inventory', quantity=qty)
        _persist_transfer_side(conn, target_row['id'], target_data,
                               'crew_stash_take', message)
        revision = _row_value(target_row, 'revision', 0) or 0
        _record_transfer_ledger(conn, target_row['id'], user['id'], target_before,
                                target_data, message, revision, revision + 1)
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(target_data, ensure_ascii=False), time.time(),
                      revision + 1, target_row['id']))
        conn.commit()
        fresh = self.get_char(conn, target_row['id'])
        self.send_json({'ok': True, 'action': 'take', 'message': message,
                        'character': self.char_payload(fresh, fresh['owner'], conn=conn)})

    @atomic_endpoint
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

    @atomic_endpoint
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

    @atomic_endpoint
    def api_character_vehicle_repair(self, conn, qs, m, body):
        user, row = self.require_character_editor(conn, m.group(1))
        allowed = {'revision', 'action', 'technician', 'check_total', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Vehicle repair содержит неподдерживаемые поля')
        current_revision = _row_value(row, 'revision', 0) or 0
        if _num((body or {}).get('revision')) != current_revision:
            raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
        before = enrich_owned_item_interactions(ensure_progression(json.loads(row['data'])))
        data = copy.deepcopy(before)
        instance_id = str(m.group(2)).lower()
        vehicle = next((item for item in data.get('inventory') or []
                        if isinstance(item, dict) and item.get('instance_id') == instance_id and
                        item.get('cat') == 'vehicles'), None)
        if not vehicle:
            raise ApiError(404, 'Vehicle instance не найден')
        sync_vehicle_states_with_modifications(conn, row['id'], data)
        state = (data.get('vehicle_state') or {}).get(instance_id) or {}
        current = max(0, int(_num(state.get('sdp_current')) or 0))
        maximum = max(0, int(_num(state.get('sdp_max')) or 0))
        action = str((body or {}).get('action') or '').lower()
        reason_detail = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason_detail) < 3:
            raise ApiError(400, 'Укажите причину Vehicle repair')
        active = state.get('repair') if isinstance(state.get('repair'), dict) else None
        now = time.time()
        if action == 'start':
            if active:
                raise ApiError(409, 'Vehicle repair уже выполняется')
            if maximum <= 0 or current >= maximum:
                raise ApiError(409, 'Vehicle не нуждается в ремонте')
            technician = str((body or {}).get('technician') or '').strip()[:120]
            if len(technician) < 2:
                raise ApiError(400, 'Укажите техника для Vehicle repair')
            severity = vehicle_repair_severity(current, maximum)
            rule = VEHICLE_REPAIR_RULES[severity]
            campaign_started = campaign_now(conn)
            active = {
                'repair_id': secrets.token_hex(16), 'status': 'in_progress',
                'severity': severity, 'skill': vehicle_repair_skill(vehicle),
                'dv': rule['dv'], 'duration_key': rule['duration_key'],
                'duration_en': rule['duration_en'],
                'duration_ru': rule['duration_ru'],
                'technician': technician, 'sdp_before': current,
                'sdp_target': maximum, 'started_at': now,
                'source': 'CP:R 140', 'manual_resolution_required': True,
                'campaign_started_at': campaign_started,
                'campaign_due_at': campaign_started + campaign_duration_seconds(rule['duration_key']),
            }
            state['repair'] = active
            reason = (
                f'Start Vehicle repair for {vehicle.get("custom_name") or vehicle.get("name")}: '
                f'{severity} DV{rule["dv"]}, {rule["duration_en"]}; {reason_detail}')
        elif action in ('resolve', 'cancel'):
            if not active or active.get('status') != 'in_progress':
                raise ApiError(409, 'Нет активного Vehicle repair')
            history_entry = copy.deepcopy(active)
            history_entry['resolved_at'] = now
            if action == 'resolve':
                total = _num((body or {}).get('check_total'))
                if total is None or int(total) != total or not -50 <= total <= 100:
                    raise ApiError(400, 'Укажите итог Repair Check')
                total = int(total)
                success = total >= int(active.get('dv') or 0)
                history_entry.update({
                    'check_total': total,
                    'status': 'success' if success else 'failed',
                    'sdp_after': maximum if success else current,
                })
                if success:
                    state['sdp_current'] = maximum
                reason = (
                    f'Resolve Vehicle repair {active.get("repair_id")}: '
                    f'{total} vs DV{active.get("dv")} → '
                    f'{"success" if success else "failed"}; {reason_detail}')
            else:
                history_entry.update({'status': 'canceled', 'sdp_after': current})
                reason = f'Cancel Vehicle repair {active.get("repair_id")}: {reason_detail}'
            history = state.setdefault('repair_history', [])
            history.append(history_entry)
            state['repair_history'] = history[-50:]
            state.pop('repair', None)
        else:
            raise ApiError(400, 'Vehicle repair action: start/resolve/cancel')
        revision_after = current_revision + 1
        ledger_id = record_character_change_set(
            conn, row['id'], user['id'], before, data, reason,
            current_revision, revision_after, category='vehicle')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), now,
                      revision_after, row['id']))
        conn.commit()
        fresh = self.get_char(conn, row['id'])
        self.send_json({
            'ledger_id': ledger_id,
            'character': self.char_payload(fresh, fresh['owner'], conn=conn),
        })

    @atomic_endpoint
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
            raise ApiError(403, 'Деньги изменяются только через Market, Payroll или Aftermath')
        elif resource == 'reputation':
            data['reputation'] = max(0, min(10, data['reputation'] + value))
        elif resource == 'armor':
            location = str((body or {}).get('subject') or '')
            piece = (data.get('armor') or {}).get(location)
            if not isinstance(piece, dict): raise ApiError(400, 'Локация брони не экипирована')
            maximum = _num(piece.get('maximum')) or _num(piece.get('sp')) or _num(piece.get('sdp')) or 0
            piece['current'] = maximum if action == 'reset' else max(0, min(maximum, (_num(piece.get('current')) or 0) + value))
        elif resource == 'vehicle_sdp':
            if _num((body or {}).get('revision')) != (_row_value(row, 'revision', 0) or 0):
                raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
            instance_id = str((body or {}).get('subject') or '')
            sync_vehicle_states_with_modifications(conn, row['id'], data)
            state = (data.get('vehicle_state') or {}).get(instance_id)
            if not state:
                raise ApiError(400, 'Vehicle instance не найден')
            maximum = _num(state.get('sdp_max')) or 0
            current = _num(state.get('sdp_current')) or 0
            if action == 'reset' or value > 0:
                raise ApiError(409, 'Используйте Vehicle Repair Workflow')
            if action != 'delta' or value >= 0:
                raise ApiError(400, 'Vehicle SDP action поддерживает только damage')
            state['sdp_current'] = max(0, min(maximum, current + value))
            self.send_json(self.save_character_data(
                conn, row, data, user['id'],
                f'Vehicle SDP {instance_id}: {current} → {state["sdp_current"]}'))
            return
        elif resource == 'weapon':
            current_revision = _row_value(row, 'revision', 0) or 0
            if _num((body or {}).get('revision')) != current_revision:
                raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
            sync_weapon_states_with_modifications(conn, row['id'], data)
            before = copy.deepcopy(data)
            key = str((body or {}).get('subject') or '')
            weapon = next((item for item in data.get('inventory') or []
                           if isinstance(item, dict) and item.get('instance_id') == key), None)
            if weapon and weapon.get('mounted_modification_id'):
                raise ApiError(409, 'Mounted weapon управляется только через Vehicle Garage')
            state = (data.get('weapon_state') or {}).get(key)
            if not weapon or not state:
                raise ApiError(400, 'Оружие не найдено')
            if action == 'fire':
                modifications = character_modifications(conn, row['id'])
                weapon_modifications = [item for item in modifications
                                        if item.get('host_instance_id') == key]
                owned = {item.get('instance_id'): item for item in data.get('inventory') or []
                         if isinstance(item, dict) and item.get('instance_id')}
                effective_weapon = evaluate_effective_weapon(
                    weapon, weapon_modifications, owned, data)
                action_profile = bound_vehicle_weapon_profile(
                    weapon, effective_weapon, data)
                ammo_cost = max(1, int(action_profile.get('ammo_cost') or 1))
                current = max(0, int(_num(state.get('magazine')) or 0))
                if current < ammo_cost:
                    raise ApiError(409, f'Для атаки требуется {ammo_cost} патронов')
                state['magazine'] = current - ammo_cost
                clear_loaded_ammo_if_empty(state)
                reason = (f'Fire {weapon.get("custom_name") or weapon.get("name")}: '
                          f'magazine {current} → {state["magazine"]}')
            elif action == 'reload':
                transfer = consume_shared_ammo(
                    data, state, (body or {}).get('ammo_instance_id'), weapon=weapon)
                reason = (
                    f'Reload {weapon.get("custom_name") or weapon.get("name")} '
                    f'with {transfer["ammo_name"]} ×{transfer["moved"]}')
            else:
                raise ApiError(400, 'Weapon action: fire/reload')
            validate_active_modification_references(conn, row['id'], data)
            persist_character_item_instances(
                conn, row['id'], data, 'weapon_action', source_ref=reason, prune=True)
            now = time.time()
            revision_after = current_revision + 1
            ledger_id = record_character_change_set(
                conn, row['id'], user['id'], before, data, reason,
                current_revision, revision_after, category='item_action')
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now,
                          revision_after, row['id']))
            conn.commit()
            fresh = self.get_char(conn, row['id'])
            self.send_json({
                'ledger_id': ledger_id,
                'character': self.char_payload(fresh, fresh['owner'], conn=conn),
            })
            return
        else:
            raise ApiError(400, 'Неизвестный ресурс')
        self.send_json(self.save_character_data(conn, row, data))


    def api_roster(self, conn, qs, m, body):
        user = self.current_user(conn)
        privileged = user_is_gm(user)
        rows = conn.execute(
            'SELECT c.*,u.display_name owner,u.show_display_name owner_show_name '
            'FROM characters c JOIN users u ON u.id=c.owner_id WHERE c.public=1 '
            'ORDER BY u.id,c.id').fetchall()
        q = (q1(qs.get('q')) or '').strip().lower()
        out = []
        for row in rows:
            owner_name = row['owner'] if (privileged or row['owner_show_name']) else None
            payload = self.char_payload(row, owner_name, public_view=not privileged, conn=conn)
            data = payload['data']
            hay = ' '.join(filter(None, [data.get('handle'), data.get('role'),
                                         data.get('player'), owner_name])).lower()
            if q and q not in hay:
                continue
            out.append(payload)
        self.send_json({'characters': out})

    # ------------------------------------------------------------ рынок

    @atomic_endpoint
    def api_buy(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, body.get('char_id'))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        before_data = json.loads(row['data'])
        data = copy.deepcopy(before_data)
        ensure_character_item_instances(data)
        ensure_progression(data)
        cart = body.get('items') or []
        if not cart or not isinstance(cart, list):
            raise ApiError(400, 'Пустая корзина')
        nm = nm_price_map()
        ensure_market_stock(conn)
        day = nm_day()
        stock_rows = market_stock_rows(conn, day)
        pm = {item_id: item_by_id(item_id)['price']
              for item_ids in market_permanent_rows(conn).values()
              for item_id in item_ids if item_by_id(item_id)}
        total = 0.0
        bought = []
        wanted = {}
        for entry in cart[:50]:
            it = item_by_id(str(entry.get('id') or ''))
            if not it or not it.get('price'):
                continue
            qty = max(1, min(99, int(entry.get('qty') or 1)))
            is_permanent = bool(entry.get('permanent')) and it['id'] in pm
            if entry.get('mode') != 'nm':
                raise ApiError(400, 'Покупка доступна только из текущего Night Market')
            if is_permanent:
                price = pm[it['id']]
            elif it['id'] in nm:
                price = nm[it['id']]
            else:
                raise ApiError(400, 'Покупка доступна только из текущего Night Market')
            if not is_permanent:
                wanted[it['id']] = wanted.get(it['id'], 0) + qty
            total += price * qty
            bought.append((it, qty, price))
        if not bought:
            raise ApiError(400, 'В корзине нет известных товаров')
        # Finite stock and reservations only apply to offers actually seeded today.
        for item_id, qty in wanted.items():
            state_row = stock_rows.get(item_id)
            if state_row is None:
                continue
            name = item_by_id(item_id)['name']
            remaining = max(0, int(state_row['stock_remaining'] or 0))
            if remaining <= 0:
                raise ApiError(400, f'Распродано: {name}')
            if (state_row.get('reserved_character_id') and
                    int(state_row['reserved_character_id']) != int(row['id'])):
                raise ApiError(400, f'Зарезервировано для другого персонажа: {name}')
            if qty > remaining:
                raise ApiError(400, f'Недостаточно единиц: {name} (доступно {remaining})')
        cash = float(data.get('cash') or 0)
        if total > cash + 1e-9:
            raise ApiError(400, f'Не хватает €$: нужно {total:,.0f}, есть {cash:,.0f}')
        inv = data.setdefault('inventory', [])
        chrome = data.setdefault('cyberware', [])
        purchased_weapon_ids = []
        for it, qty, price in bought:
            target_bucket = chrome if it['cat'] == 'cyberware' else inv
            owned = {
                'key': it['id'], 'catalog_item_id': it['id'], 'cat': it['cat'],
                'name': it['name'], 'price': price, 'qty': 1, 'state': 'carried',
                'damage': it.get('damage'), 'sp': it.get('sp'), 'hl': it.get('hl'),
                'fields': copy.deepcopy(it.get('fields') or {}),
                'mechanics': copy.deepcopy(it.get('mechanics') or {}),
                'source': it.get('source'),
            }
            owned.update(catalog_interaction_data(it))
            owned.update({key: copy.deepcopy(it[key]) for key in ITEM_MODIFICATION_FIELDS if key in it})
            coverage = item_effect_coverage(it.get('id'))
            if coverage:
                owned['effect_coverage'] = coverage
            if item_entry_stackable(owned):
                found = next((entry for entry in target_bucket if isinstance(entry, dict) and
                              catalog_item_id_for_entry(entry) == it['id'] and
                              item_entry_stackable(entry) and
                              str(entry.get('state') or 'carried') == 'carried' and
                              not entry.get('custom_name')), None)
                if found:
                    current_rounds = ammo_rounds(found) if it['cat'] == 'ammo' else 0
                    found['qty'] = int(found.get('qty') or 1) + qty
                    if it['cat'] == 'ammo':
                        found['ammo_rounds'] = current_rounds + qty * ammo_pack_size(found)
                else:
                    owned['instance_id'] = new_item_instance_id()
                    owned['qty'] = qty
                    if it['cat'] == 'ammo':
                        owned['ammo_rounds'] = qty * ammo_pack_size(owned)
                    target_bucket.append(owned)
            else:
                if len(inv) + len(chrome) + qty > 500:
                    raise ApiError(400, 'Инвентарь не может содержать больше 500 экземпляров')
                for _ in range(qty):
                    instance = copy.deepcopy(owned)
                    instance['instance_id'] = new_item_instance_id()
                    target_bucket.append(instance)
                    if it['cat'] == 'guns':
                        purchased_weapon_ids.append(instance['instance_id'])
        for item_id, qty in wanted.items():
            state_row = stock_rows.get(item_id)
            if state_row is not None:
                conn.execute(
                    'UPDATE market_stock SET stock_remaining=stock_remaining-?,updated=? '
                    'WHERE market_day=? AND item_id=?',
                    (qty, time.time(), day, item_id))
        data['cash'] = round(cash - total, 2)
        ensure_progression(data)
        for instance_id in purchased_weapon_ids:
            state = (data.get('weapon_state') or {}).get(instance_id)
            if state:
                state['magazine'] = 0
        persist_character_item_instances(
            conn, row['id'], data, 'night_market', source_ref=nm_day())
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 'Night Market purchase')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        receipt = [{'name': it['name'], 'qty': qty, 'price': price}
                   for it, qty, price in bought]
        self.send_json({'ok': True, 'total': round(total, 2), 'cash': data['cash'],
                        'receipt': receipt})

    @atomic_endpoint
    def api_sell(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = self.get_char(conn, body.get('char_id'))
        if row['owner_id'] != u['id']:
            raise ApiError(403, 'Это не ваш персонаж')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        before_data = json.loads(row['data'])
        data = copy.deepcopy(before_data)
        ensure_character_item_instances(data)
        ensure_progression(data)
        key = str(body.get('key') or '')
        instance_id = str(body.get('instance_id') or '').lower()
        try:
            qty = max(1, int(body.get('qty') or 1))
        except (TypeError, ValueError):
            raise ApiError(400, 'Некорректное количество')
        inv = data.get('inventory') or []
        chrome = data.get('cyberware') or []
        bucket = inv
        index = next((position for position, entry in enumerate(bucket)
                      if isinstance(entry, dict) and instance_id and
                      entry.get('instance_id') == instance_id), None)
        if index is None:
            index = next((position for position, entry in enumerate(bucket)
                          if isinstance(entry, dict) and key and entry.get('key') == key), None)
        if index is None:
            bucket = chrome
            index = next((position for position, entry in enumerate(bucket)
                          if isinstance(entry, dict) and instance_id and
                          entry.get('instance_id') == instance_id), None)
        if index is None:
            index = next((position for position, entry in enumerate(bucket)
                          if isinstance(entry, dict) and key and entry.get('key') == key), None)
        if index is None:
            raise ApiError(404, 'Предмет не найден в инвентаре')
        ent = bucket[index]
        if ent.get('instance_id'):
            loan = active_loan_for_instance(conn, ent.get('instance_id'))
            if loan and loan['borrower_character_id'] == row['id']:
                raise ApiError(409, 'Предмет взят в долг — сначала верните владельцу')
        linked = conn.execute(
            'SELECT 1 FROM item_modifications WHERE character_id=? AND active=1 '
            'AND (host_instance_id=? OR upgrade_instance_id=?)',
            (row['id'], ent.get('instance_id'), ent.get('instance_id'))).fetchone()
        if linked:
            raise ApiError(409, 'Сначала снимите установленные модификации')
        cyber_states = data.get('cyberware_state') if isinstance(
            data.get('cyberware_state'), dict) else {}
        ent_cyber_state = cyber_states.get(ent.get('instance_id'))
        if (ent.get('installed_cyberware_instance_id') or
                (isinstance(ent_cyber_state, dict) and
                 ent_cyber_state.get('bound_weapon_instance_id'))):
            raise ApiError(409, 'Permanent Popup Weapon binding нельзя продать отдельно')
        if (ent.get('installed_popup_shield_instance_id') or
                (isinstance(ent_cyber_state, dict) and
                 isinstance(ent_cyber_state.get('popup_shield'), dict) and
                 ent_cyber_state['popup_shield'].get('shield_instance_id'))):
            raise ApiError(409, 'Сначала извлеките concrete Popup Shield')
        armor_tech = data.get('armor_tech_state') if isinstance(
            data.get('armor_tech_state'), dict) else {}
        if isinstance(armor_tech.get(ent.get('instance_id')), dict):
            raise ApiError(409, 'Permanent Armor Tech Upgrade нельзя продать отдельно')
        if str(ent.get('state') or 'carried') in ('equipped', 'installed'):
            raise ApiError(409, 'Сначала снимите или извлеките предмет')
        ammo_units_before = ammo_rounds(ent) if ent.get('cat') == 'ammo' else None
        if ammo_units_before is not None:
            full_packs = ammo_units_before // ammo_pack_size(ent)
            if full_packs <= 0:
                raise ApiError(409, 'Частично использованный ammo stack нельзя продать')
            qty = min(qty, int(ent.get('qty') or 1), full_packs)
        else:
            qty = min(qty, int(ent.get('qty') or 1))
        back = round(float(ent.get('price') or 0) * 0.5 * qty, 2)
        ent['qty'] = int(ent.get('qty') or 1) - qty
        if ammo_units_before is not None:
            ent['ammo_rounds'] = ammo_units_before - qty * ammo_pack_size(ent)
            ent['qty'] = math.ceil(ent['ammo_rounds'] / ammo_pack_size(ent)) \
                if ent['ammo_rounds'] > 0 else 0
        if ent['qty'] <= 0:
            bucket.pop(index)
            (data.get('weapon_state') or {}).pop(str(ent.get('instance_id') or ''), None)
        data['cash'] = round(float(data.get('cash') or 0) + back, 2)
        persist_character_item_instances(
            conn, row['id'], data, 'night_market_resale', prune=True)
        record_character_changes(conn, row['id'], u['id'], before_data, data,
                                 f'Night Market resale: {ent.get("name") or key}')
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'got': back,
                        'name': ent.get('name'), 'qty': qty,
                        'instance_id': ent.get('instance_id')})

    @atomic_endpoint
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
        conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                     (json.dumps(data, ensure_ascii=False), time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'cash': data['cash'], 'by': u['display_name']})

    # ------------------------------------------------------------ NC//NET operations

    def session_access_role(self, conn, user, session):
        if not user or not session:
            return None
        if user_is_admin(user) or session['owner_user_id'] == user['id']:
            return 'owner'
        explicit = conn.execute(
            'SELECT role FROM session_access WHERE session_id=? AND user_id=?',
            (session['id'], user['id'])).fetchone()
        if explicit and explicit['role'] in SESSION_ACCESS_ROLES:
            return explicit['role']
        if conn.execute(
                'SELECT 1 FROM session_combatants sc JOIN characters c '
                'ON c.id=sc.character_id WHERE sc.session_id=? AND c.owner_id=?',
                (session['id'], user['id'])).fetchone():
            return 'crew'
        if session['contract_id']:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?',
                                    (session['contract_id'],)).fetchone()
            if user_is_gm(user) and can_edit_contract(conn, user, contract):
                return 'co_gm'
            if conn.execute(
                    "SELECT 1 FROM contract_signups WHERE contract_id=? AND user_id=? AND status='crew'",
                    (session['contract_id'], user['id'])).fetchone():
                return 'crew'
        return None

    def session_capabilities(self, conn, user, session):
        role = self.session_access_role(conn, user, session)
        return role, set(SESSION_ROLE_CAPABILITIES.get(role, set()))

    def can_edit_nc_session(self, conn, user, session):
        return 'edit_session' in self.session_capabilities(conn, user, session)[1]

    def can_manage_session_access(self, conn, user, session):
        return 'manage_access' in self.session_capabilities(conn, user, session)[1]

    def ordered_session_combatants(self, conn, session_id):
        return conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? '
            'ORDER BY initiative DESC,sort_order,id', (session_id,)).fetchall()

    def session_net_payload(self, conn, row, user=None, player_view=False):
        state = session_net_state(_row_value(row, 'net_state_json', '{}'))
        floor_by_id = {item['floor_id']: item for item in state['floors']}
        node_by_id = {item['node_id']: item for item in state['nodes']}
        combatants = {item['id']: item for item in self.ordered_session_combatants(
            conn, row['id'])}
        entities = []
        skunk_sources_by_target = {}
        for link in state['links']:
            if not link['active'] or (player_view and not link['visible']):
                continue
            character = conn.execute(
                'SELECT id,revision,data FROM characters WHERE id=?',
                (link['character_id'],)).fetchone()
            if not character:
                continue
            character_data = ensure_progression(json.loads(character['data']))
            entity = (character_data.get('net_entities') or {}).get(
                link['net_entity_id'])
            if (not isinstance(entity, dict) or
                    entity.get('status') not in ('lying_in_wait', 'hunting', 'derezzed')):
                continue
            floor = floor_by_id.get(link['floor_id'])
            node = node_by_id.get(link.get('node_id'))
            target = combatants.get(link.get('target_combatant_id'))
            payload = {
                'net_entity_id': link['net_entity_id'],
                'character_id': link['character_id'],
                'name': entity.get('name') or 'Black ICE',
                'status': entity.get('status'),
                'initiative': link['initiative'] if entity.get('status') == 'hunting' else None,
                'in_queue': entity.get('status') == 'hunting',
                'floor_id': link['floor_id'],
                'floor_label': floor['label'] if floor else entity.get('floor_label'),
                'node_id': link.get('node_id'),
                'node_label': node['label'] if node else None,
                'target_combatant_id': link.get('target_combatant_id'),
                'target_label': target['name'] if target and
                    (not player_view or target['visible']) else None,
                'target_type': entity.get('target_type'),
                'per': entity.get('per'), 'spd': entity.get('spd'),
                'atk': entity.get('atk'), 'def': entity.get('def'),
                'rez_current': entity.get('rez_current'),
                'rez_max': entity.get('rez_max'),
                'entity_character_revision': character['revision'],
                'visible': link['visible'],
            }
            source_program = next((item for item in character_data.get('inventory') or []
                                   if isinstance(item, dict) and
                                   item.get('instance_id') == entity.get('source_program_instance_id')), {})
            effect_profile = black_ice_effect_profile(source_program)
            payload['effect_resolution'] = effect_profile['resolution']
            if (payload.get('name') == 'Skunk' and
                    payload.get('status') == 'hunting' and
                    link.get('target_combatant_id')):
                skunk_sources_by_target.setdefault(
                    link['target_combatant_id'], []).append(link['net_entity_id'])
            if not player_view:
                payload['character_revision'] = character['revision']
                payload['initiative_roll'] = entity.get('initiative_roll')
                payload['effect_profile'] = effect_profile
                if target and target['character_id']:
                    target_character = conn.execute(
                        'SELECT id,revision,data FROM characters WHERE id=?',
                        (target['character_id'],)).fetchone()
                    if target_character:
                        target_data = enrich_owned_item_interactions(
                            ensure_progression(json.loads(target_character['data'])))
                        target_modifications = character_modifications(
                            conn, target_character['id'])
                        target_decks = character_effective_cyberdecks(
                            target_data, target_modifications)
                        payload['target_interface_rank'] = character_interface_rank(target_data)
                        payload['target_character_revision'] = target_character['revision']
                        all_target_programs = [
                            {
                                'instance_id': program['instance_id'],
                                'name': program['name'],
                                'def': int(_num((program.get('mechanics') or {}).get('def')) or 0),
                                'rez_current': int(_num((program.get('runtime') or {}).get('rez_current')) or 0),
                                'rez_max': int(_num((program.get('runtime') or {}).get('rez_max')) or 0),
                                'category': (program.get('runtime') or {}).get('category'),
                                'status': (program.get('runtime') or {}).get('status'),
                            }
                            for deck in target_decks.values()
                            for program in deck.get('programs') or []]
                        payload['valid_target_programs'] = [
                            program for program in all_target_programs
                            if program['status'] == 'rezzed']
                        if effect_profile['resolution'] == 'automated_random_destroy':
                            payload['curated_target_programs'] = all_target_programs
                        elif effect_profile['resolution'] == 'automated_random_derez_plus_manual':
                            payload['curated_target_programs'] = [
                                program for program in all_target_programs
                                if program['status'] == 'rezzed' and
                                program['category'] == 'defender']
            else:
                for private_key in ('character_id', 'target_combatant_id', 'visible',
                                    'node_id'):
                    payload.pop(private_key, None)
            entities.append(payload)
        queue = sorted(
            (item for item in entities if item['in_queue']),
            key=lambda item: (-(_num(item.get('initiative')) or 0), item['net_entity_id']))
        active_turn = min(state['active_turn'], max(0, len(queue) - 1))
        active_id = queue[active_turn]['net_entity_id'] if queue else None
        for item in entities:
            item['active'] = item['net_entity_id'] == active_id
        entities.sort(key=lambda item: (
            0 if item['in_queue'] else 1,
            -(_num(item.get('initiative')) or 0), item['net_entity_id']))
        runners = []
        runner_by_combatant = {item['combatant_id']: item
                              for item in state.get('runners') or []}
        for combatant in combatants.values():
            if not combatant['character_id'] or (player_view and not combatant['visible']):
                continue
            character = conn.execute(
                'SELECT id,owner_id,revision,data FROM characters WHERE id=?',
                (combatant['character_id'],)).fetchone()
            if not character:
                continue
            character_data = enrich_owned_item_interactions(
                ensure_progression(json.loads(character['data'])))
            interface_rank = character_interface_rank(character_data)
            if interface_rank <= 0:
                continue
            runner = runner_by_combatant.get(combatant['id']) or {
                'combatant_id': combatant['id'], 'character_id': character['id'],
                'node_id': None, 'jacked_in': False, 'actions_recorded': 0,
                'action_round': state['round'], 'actions_used': 0,
                'action_penalty': 0, 'next_action_penalty': 0,
            }
            node = node_by_id.get(runner.get('node_id'))
            same_action_round = runner.get('action_round') == state['round']
            current_actions_used = runner.get('actions_used', 0) if same_action_round else 0
            action_penalty = (runner.get('action_penalty', 0) if same_action_round else
                              runner.get('next_action_penalty', 0))
            actions_max = max(2, net_actions_for_interface(interface_rank) - action_penalty)
            skunk_sources = skunk_sources_by_target.get(combatant['id'], [])
            runner_payload = {
                'combatant_id': combatant['id'],
                'character_id': character['id'],
                'name': combatant['name'], 'jacked_in': runner.get('jacked_in', False),
                'node_id': runner.get('node_id'),
                'node_label': node['label'] if node else None,
                'interface_rank': interface_rank,
                'actions_recorded': runner.get('actions_recorded', 0),
                'actions_used': current_actions_used,
                'actions_max': actions_max,
                'actions_remaining': max(0, actions_max - current_actions_used),
                'action_penalty': action_penalty,
                'skunk_slide_penalty': -2 * len(skunk_sources),
                'skunk_source_count': len(skunk_sources),
            }
            can_act = bool(user and character['owner_id'] == user['id'])
            if not player_view or can_act:
                modifications = character_modifications(conn, character['id'])
                decks = character_effective_cyberdecks(character_data, modifications)
                runner_payload['character_revision'] = character['revision']
                runner_payload['attacker_programs'] = [
                    {'instance_id': program['instance_id'], 'name': program['name'],
                     'atk': (program.get('mechanics') or {}).get('atk') or 0}
                    for deck in decks.values() for program in deck.get('programs') or []
                    if (program.get('runtime') or {}).get('category') == 'attacker']
            if player_view:
                runner_payload['can_act'] = can_act
                runner_payload.pop('character_id', None)
                runner_payload.pop('node_id', None)
            runners.append(runner_payload)
        if player_view:
            visible_nodes = [item for item in state['nodes'] if item['visible']]
            visible_node_ids = {item['node_id'] for item in visible_nodes}
            nodes = [{
                key: value for key, value in item.items()
                if key not in ('gm_note', 'visible', 'sort_order', 'floor_id',
                               'controlled_by_combatant_id')
            } | {
                'floor_label': (floor_by_id.get(item['floor_id']) or {}).get('label'),
                'controlled': item.get('controlled_by_combatant_id') is not None,
            } for item in visible_nodes]
            paths = [copy.deepcopy(item) for item in state['paths']
                     if item['visible'] and item['from_node_id'] in visible_node_ids and
                     item['to_node_id'] in visible_node_ids]
            visible_floor_ids = {item['floor_id'] for item in visible_nodes} | {
                item['floor_id'] for item in entities}
            floors = [{'label': item['label']} for item in state['floors']
                      if item['floor_id'] in visible_floor_ids]
            for item in entities:
                item.pop('floor_id', None)
        else:
            floors = state['floors']
            nodes = state['nodes']
            paths = state['paths']
        actions = state.get('action_log', [])[-20:]
        if player_view:
            actions = [{key: item.get(key) for key in (
                'action', 'success', 'actor_total', 'defense_total',
                'created', 'summary')} for item in actions]
        return {
            'round': state['round'], 'active_turn': active_turn,
            'floors': floors, 'nodes': nodes, 'paths': paths,
            'entities': entities, 'runners': runners,
            'action_log': actions,
        }

    def session_activity_payload(self, row):
        before = parse_json_object(row['before_json'])
        after = parse_json_object(row['after_json'])
        event_type = row['event_type']
        changes = []

        def display_value(key, value):
            if key in ('conditions_json', 'injuries_json'):
                value = parse_json_list(value)
            if key == 'visible':
                return bool(value)
            if key == 'player_view_config':
                return session_view_config(value)
            if key == 'safety_config':
                return session_safety_config(value)
            if isinstance(value, (dict, list)):
                return value
            return value

        if event_type == 'session_update':
            for key in ('title', 'status', 'round', 'active_turn',
                        'player_view_config', 'safety_config', 'notes'):
                if key not in after:
                    continue
                old_value = before.get(key)
                new_value = after.get(key)
                if key == 'notes':
                    if str(old_value or '') != str(new_value or ''):
                        changes.append({'field': 'notes', 'before': None, 'after': 'updated'})
                    continue
                if key == 'player_view_config':
                    old_config = session_view_config(old_value)
                    new_config = session_view_config(new_value)
                    for setting in SESSION_VIEW_DEFAULTS:
                        if old_config[setting] != new_config[setting]:
                            changes.append({'field': f'player_view.{setting}',
                                            'before': old_config[setting],
                                            'after': new_config[setting]})
                    continue
                old_value = display_value(key, old_value)
                new_value = display_value(key, new_value)
                if old_value != new_value:
                    changes.append({'field': key, 'before': old_value, 'after': new_value})
        elif event_type in ('combatant_create', 'combatant_delete'):
            snapshot = after if event_type == 'combatant_create' else before
            changes.append({
                'field': 'combatant', 'before': None if event_type == 'combatant_create'
                else snapshot.get('name'),
                'after': snapshot.get('name') if event_type == 'combatant_create' else None,
            })
        elif event_type == 'net_action':
            changes.append({
                'field': after.get('action') or 'net_action',
                'before': None,
                'after': after.get('summary') or 'resolved',
            })
        elif event_type.startswith('net_'):
            def net_summary(value):
                if not value:
                    return None
                if value.get('type') == 'black_ice':
                    return {
                        'name': value.get('name'), 'status': value.get('status'),
                        'floor': value.get('floor_label'),
                        'target': value.get('target_label'),
                        'initiative': value.get('initiative'),
                        'rez': f"{value.get('rez_current')}/{value.get('rez_max')}",
                    }
                return {
                    'round': value.get('round'),
                    'active_turn': value.get('active_turn'),
                    'floors': len(value.get('floors') or []),
                    'nodes': len(value.get('nodes') or []),
                    'paths': len(value.get('paths') or []),
                    'links': len(value.get('links') or []),
                }
            changes.append({'field': 'net_context',
                            'before': net_summary(before),
                            'after': net_summary(after)})
        else:
            fields = (
                'name', 'initiative', 'hp_current', 'hp_max',
                'sp_head', 'sp_head_max', 'sp_body', 'sp_body_max',
                'shield_current', 'shield_max', 'ammo_current', 'ammo_max',
                'luck_current', 'luck_max', 'move', 'death_penalty',
                'conditions_json', 'injuries_json', 'visible', 'sort_order',
            )
            for key in fields:
                old_value = display_value(key, before.get(key))
                new_value = display_value(key, after.get(key))
                if old_value != new_value:
                    changes.append({'field': key[:-5] if key.endswith('_json') else key,
                                    'before': old_value, 'after': new_value})
                if len(changes) >= 20:
                    break
        return {
            'id': row['id'], 'combatant_id': row['combatant_id'],
            'event_type': event_type, 'actor': row['actor'],
            'note': row['note'], 'created': row['created'], 'changes': changes,
        }

    def session_payload(self, conn, row, user, player_view=False):
        access_role, capabilities = self.session_capabilities(conn, user, row)
        can_edit = 'edit_session' in capabilities
        config = session_view_config(row['player_view_config'])
        safety = session_safety_config(_row_value(row, 'safety_config', '{}'))
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
                })
                if 'view_secrets' in capabilities:
                    data['secret'] = parse_json_object(item['secret_json'])
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
            if item['kind'] == 'npc':
                statblock = parse_json_object(item['statblock_json'])
                if statblock and (not player_view or config['show_npc_stats']):
                    data['statblock'] = statblock
                    data['derived'] = npc_statblock_derived(statblock)
            out_combatants.append(data)
        visible_active_turn = next(
            (index for index, item in enumerate(out_combatants) if item['active']), None)
        payload = {
            'id': row['id'], 'contract_id': row['contract_id'], 'title': row['title'],
            'status': row['status'], 'round': row['round'],
            'active_turn': visible_active_turn if player_view else active_turn,
            'player_view_config': config, 'safety_config': safety,
            'combatants': out_combatants,
            'net': self.session_net_payload(conn, row, user=user, player_view=player_view),
            'created': row['created'], 'updated': row['updated'], 'can_edit': can_edit,
            'access_role': access_role,
            'capabilities': {key: key in capabilities for key in (
                'view_gm', 'view_secrets', 'edit_session', 'edit_combatants',
                'manage_access', 'manage_safety')},
        }
        if not player_view and 'edit_session' in capabilities:
            payload['notes'] = row['notes']
        if not player_view and capabilities.intersection({'edit_session', 'edit_combatants'}):
            activity = conn.execute(
                'SELECT a.*,u.display_name actor FROM session_activity a '
                'JOIN users u ON u.id=a.actor_user_id WHERE session_id=? '
                'ORDER BY a.id DESC LIMIT 200', (row['id'],)).fetchall()
            payload['activity'] = [self.session_activity_payload(item) for item in activity]
        return payload

    def can_edit_npc_template(self, user, template):
        return bool(user and template and user_is_gm(user) and
                    (user_is_admin(user) or template['owner_user_id'] == user['id']))

    def npc_template_payload(self, row, user):
        data = parse_json_object(row['data_json'])
        return {
            'id': row['id'], 'owner_user_id': row['owner_user_id'],
            'access': row['access'], 'name': row['name'], 'role': row['role'],
            'data': data,
            'derived': npc_statblock_derived(data.get('statblock') or {}),
            'updated': row['updated'],
            'can_edit': self.can_edit_npc_template(user, row),
        }

    def api_npc_templates(self, conn, qs, m, body):
        user = self.require_user(conn)
        if not user_is_gm(user):
            session_id = _num(q1(qs.get('session_id')))
            session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                                   (session_id,)).fetchone() if session_id else None
            if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
                raise ApiError(403, 'Только для пользователей с ролью ГМ')
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

    # ------------------------------------------------------------ Session Recap / Chronicle

    def recap_links(self, conn, cleaned, user):
        """Validate optional session/contract/storyline links for a recap."""
        session_id, contract_id, storyline_id = (
            cleaned['session_id'], cleaned['contract_id'], cleaned['storyline_id'])
        if session_id:
            session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (session_id,)).fetchone()
            if not session:
                raise ApiError(400, 'Сессия Recap не найдена')
            role, capabilities = self.session_capabilities(conn, user, session)
            if 'view_gm' not in capabilities:
                raise ApiError(403, 'Нет доступа к сессии Recap')
            if contract_id is None and session['contract_id']:
                contract_id = session['contract_id']
        if contract_id:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?', (contract_id,)).fetchone()
            if not contract or not can_edit_contract(conn, user, contract):
                raise ApiError(403, 'Нет права связывать Recap с этим контрактом')
            if storyline_id is None:
                storyline_id = contract['storyline_id']
        if storyline_id:
            storyline = conn.execute('SELECT * FROM storylines WHERE id=?', (storyline_id,)).fetchone()
            if not storyline or not can_edit_storyline(conn, user, storyline):
                raise ApiError(403, 'Нет права связывать Recap с этой сюжетной линией')
        return session_id, contract_id, storyline_id

    def recap_apply_feed(self, conn, user, recap_id, cleaned, existing_feed_id=None):
        """Create or refresh the City Feed draft linked to a recap."""
        if not cleaned['publish_feed']:
            return existing_feed_id
        summary = cleaned['public_summary']
        if not summary:
            return existing_feed_id
        now = time.time()
        if existing_feed_id:
            conn.execute(
                "UPDATE feed_posts SET headline=?,body=?,event_at=?,storyline_id=?,contract_id=?,updated=? "
                'WHERE id=? AND creator_user_id=?',
                (cleaned['title'], summary, cleaned['session_date'],
                 cleaned['storyline_id'], cleaned['contract_id'], now,
                 existing_feed_id, user['id']))
            return existing_feed_id
        cur = conn.execute(
            'INSERT INTO feed_posts(format,status,creator_user_id,storyline_id,contract_id,'
            'headline,body,truth_status,event_at,created,updated) '
            "VALUES('article','draft',?,?,?,?,?,'unknown',?,?,?)",
            (user['id'], cleaned['storyline_id'], cleaned['contract_id'],
             cleaned['title'], summary, cleaned['session_date'], now, now))
        return cur.lastrowid

    def recap_apply_timeline(self, conn, user, recap_id, cleaned, existing_timeline_id=None):
        """Create or refresh the Storyline timeline entry linked to a recap."""
        storyline_id = cleaned['storyline_id']
        if not storyline_id:
            return existing_timeline_id
        now = time.time()
        if existing_timeline_id:
            conn.execute(
                'UPDATE storyline_timeline SET event_at=?,public_text=?,private_text=? WHERE id=?',
                (cleaned['session_date'], cleaned['public_summary'] or cleaned['title'],
                 cleaned['gm_notes'], existing_timeline_id))
            return existing_timeline_id
        if not cleaned['public_summary'] and not cleaned['gm_notes']:
            return None
        cur = conn.execute(
            'INSERT INTO storyline_timeline(storyline_id,event_at,public_text,private_text,'
            'contract_id,created_by,created) VALUES(?,?,?,?,?,?,?)',
            (storyline_id, cleaned['session_date'],
             cleaned['public_summary'] or cleaned['title'], cleaned['gm_notes'],
             cleaned['contract_id'], user['id'], now))
        conn.execute('UPDATE storylines SET updated=? WHERE id=?', (now, storyline_id))
        return cur.lastrowid

    def api_recaps(self, conn, qs, m, body):
        user = self.require_user(conn)
        full = user_is_gm(user)
        if full:
            rows = conn.execute(
                'SELECT * FROM session_recaps ORDER BY session_date DESC,id DESC LIMIT 500').fetchall()
            payload = [session_recap_payload(row, full=True) for row in rows]
        else:
            rows = conn.execute(
                'SELECT * FROM session_recaps WHERE published=1 '
                'ORDER BY session_date DESC,id DESC LIMIT 500').fetchall()
            payload = [session_recap_payload(row) for row in rows]
        self.send_json({'recaps': payload, 'full': full})

    def api_recap_detail(self, conn, qs, m, body):
        user = self.require_user(conn)
        row = conn.execute('SELECT * FROM session_recaps WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Recap не найден')
        full = user_is_gm(user) or row['owner_user_id'] == user['id']
        if not full and not row['published']:
            raise ApiError(403, 'Recap не опубликован')
        self.send_json(session_recap_payload(row, full=full))

    @atomic_endpoint
    def api_recap_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cleaned = clean_session_recap_input(body or {})
        session_id, contract_id, storyline_id = self.recap_links(conn, cleaned, user)
        cleaned.update({'session_id': session_id, 'contract_id': contract_id,
                        'storyline_id': storyline_id})
        participants = cleaned['participants'] or \
            recap_participants(conn, session_id=session_id, contract_id=contract_id)
        now = time.time()
        cur = conn.execute(
            'INSERT INTO session_recaps(owner_user_id,session_id,contract_id,storyline_id,'
            'session_date,title,public_summary,gm_notes,participants_json,choices_json,'
            'npc_changes_json,locations_json,loot_json,injuries_json,quotes_json,published,'
            'created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (user['id'], session_id, contract_id, storyline_id,
             cleaned['session_date'], cleaned['title'], cleaned['public_summary'],
             cleaned['gm_notes'], json.dumps(participants, ensure_ascii=False),
             json.dumps(cleaned['choices'], ensure_ascii=False),
             json.dumps(cleaned['npc_changes'], ensure_ascii=False),
             json.dumps(cleaned['locations'], ensure_ascii=False),
             json.dumps(cleaned['loot'], ensure_ascii=False),
             json.dumps(cleaned['injuries'], ensure_ascii=False),
             json.dumps(cleaned['quotes'], ensure_ascii=False),
             1 if cleaned['published'] else 0, now, now))
        recap_id = cur.lastrowid
        feed_id = self.recap_apply_feed(conn, user, recap_id, cleaned)
        timeline_id = self.recap_apply_timeline(conn, user, recap_id, cleaned)
        conn.execute('UPDATE session_recaps SET feed_post_id=?,timeline_id=? WHERE id=?',
                     (feed_id, timeline_id, recap_id))
        conn.commit()
        row = conn.execute('SELECT * FROM session_recaps WHERE id=?', (recap_id,)).fetchone()
        self.send_json(session_recap_payload(row, full=True), status=201)

    @atomic_endpoint
    def api_recap_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM session_recaps WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Recap не найден')
        if row['owner_user_id'] != user['id'] and not user_is_admin(user):
            raise ApiError(403, 'Нет права редактировать Recap')
        cleaned = clean_session_recap_input(body or {})
        session_id, contract_id, storyline_id = self.recap_links(conn, cleaned, user)
        cleaned.update({'session_id': session_id, 'contract_id': contract_id,
                        'storyline_id': storyline_id})
        participants = cleaned['participants'] or \
            recap_participants(conn, session_id=session_id, contract_id=contract_id)
        feed_id = self.recap_apply_feed(conn, user, row['id'], cleaned, row['feed_post_id'])
        timeline_id = self.recap_apply_timeline(
            conn, user, row['id'], cleaned, row['timeline_id'])
        conn.execute(
            'UPDATE session_recaps SET session_id=?,contract_id=?,storyline_id=?,session_date=?,'
            'title=?,public_summary=?,gm_notes=?,participants_json=?,choices_json=?,'
            'npc_changes_json=?,locations_json=?,loot_json=?,injuries_json=?,quotes_json=?,'
            'feed_post_id=?,timeline_id=?,published=?,updated=? WHERE id=?',
            (session_id, contract_id, storyline_id, cleaned['session_date'],
             cleaned['title'], cleaned['public_summary'], cleaned['gm_notes'],
             json.dumps(participants, ensure_ascii=False),
             json.dumps(cleaned['choices'], ensure_ascii=False),
             json.dumps(cleaned['npc_changes'], ensure_ascii=False),
             json.dumps(cleaned['locations'], ensure_ascii=False),
             json.dumps(cleaned['loot'], ensure_ascii=False),
             json.dumps(cleaned['injuries'], ensure_ascii=False),
             json.dumps(cleaned['quotes'], ensure_ascii=False),
             feed_id, timeline_id, 1 if cleaned['published'] else 0,
             time.time(), row['id']))
        conn.commit()
        fresh = conn.execute('SELECT * FROM session_recaps WHERE id=?', (row['id'],)).fetchone()
        self.send_json(session_recap_payload(fresh, full=True))

    @atomic_endpoint
    def api_recap_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM session_recaps WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Recap не найден')
        if row['owner_user_id'] != user['id'] and not user_is_admin(user):
            raise ApiError(403, 'Нет права удалять Recap')
        if row['feed_post_id']:
            conn.execute("DELETE FROM feed_posts WHERE id=? AND status='draft' AND creator_user_id=?",
                         (row['feed_post_id'], user['id']))
        if row['timeline_id']:
            conn.execute('DELETE FROM storyline_timeline WHERE id=?', (row['timeline_id'],))
        conn.execute('DELETE FROM session_recaps WHERE id=?', (row['id'],))
        conn.commit()
        self.send_json({'ok': True, 'deleted': True})

    # ------------------------------------------------------------ Map POIs / Key Locations

    def api_locations(self, conn, qs, m, body):
        user = self.current_user(conn)
        gm = user_is_gm(user)
        query = ('SELECT * FROM locations WHERE (? OR archived=0) '
                 'ORDER BY custom,name_en')
        rows = conn.execute(query, (1 if gm else 0,)).fetchall()
        q = (q1(qs.get('q')) or '').strip().lower()
        district = q1(qs.get('district')) or ''
        kind = q1(qs.get('kind')) or ''
        out = []
        for row in rows:
            if district and row['district_id'] != district:
                continue
            if kind and row['kind'] != kind:
                continue
            if q:
                hay = ' '.join(filter(None, [row['name_en'], row['name_ru'],
                                             row['description_en'], row['description_ru']])).lower()
                if q not in hay:
                    continue
            out.append(location_payload(row, user))
        self.send_json({'locations': out, 'kinds': sorted(LOCATION_KINDS)})

    def api_location_detail(self, conn, qs, m, body):
        user = self.current_user(conn)
        row = conn.execute('SELECT * FROM locations WHERE id=?', (m.group(1),)).fetchone()
        if not row:
            raise ApiError(404, 'Локация не найдена')
        if row['archived'] and not user_is_gm(user):
            raise ApiError(404, 'Локация не найдена')
        self.send_json(location_payload(row, user))

    @atomic_endpoint
    def api_location_create(self, conn, qs, m, body):
        user = self.require_gm(conn)
        cleaned = clean_location_input(body or {})
        location_id = str((body or {}).get('id') or '').strip().lower() or None
        if location_id:
            if not re.fullmatch(r'[a-z0-9-]{2,80}', location_id):
                raise ApiError(400, 'Некорректный идентификатор локации')
            if conn.execute('SELECT 1 FROM locations WHERE id=?', (location_id,)).fetchone():
                raise ApiError(409, 'Локация с таким идентификатором уже существует')
        else:
            location_id = f'custom-{secrets.token_hex(8)}'
        now = time.time()
        conn.execute(
            'INSERT INTO locations(id,name_en,name_ru,kind,district_id,x,y,'
            'description_en,description_ru,source,custom,owner_user_id,archived,created,updated) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,1,?,0,?,?)',
            (location_id, cleaned['name_en'], cleaned['name_ru'], cleaned['kind'],
             cleaned['district_id'], cleaned['x'], cleaned['y'],
             cleaned['description_en'], cleaned['description_ru'], cleaned['source'] or 'Custom',
             user['id'], now, now))
        conn.commit()
        row = conn.execute('SELECT * FROM locations WHERE id=?', (location_id,)).fetchone()
        self.send_json(location_payload(row, user), status=201)

    @atomic_endpoint
    def api_location_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM locations WHERE id=?', (m.group(1),)).fetchone()
        if not row or row['archived']:
            raise ApiError(404, 'Локация не найдена')
        if not row['custom']:
            raise ApiError(403, 'Seed локации можно редактировать только через custom копию')
        cleaned = clean_location_input(body or {}, row)
        conn.execute(
            'UPDATE locations SET name_en=?,name_ru=?,kind=?,district_id=?,x=?,y=?,'
            'description_en=?,description_ru=?,source=?,updated=? WHERE id=?',
            (cleaned['name_en'], cleaned['name_ru'], cleaned['kind'], cleaned['district_id'],
             cleaned['x'], cleaned['y'], cleaned['description_en'], cleaned['description_ru'],
             cleaned['source'] or row['source'], time.time(), row['id']))
        conn.commit()
        fresh = conn.execute('SELECT * FROM locations WHERE id=?', (row['id'],)).fetchone()
        self.send_json(location_payload(fresh, user))

    @atomic_endpoint
    def api_location_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM locations WHERE id=?', (m.group(1),)).fetchone()
        if not row:
            raise ApiError(404, 'Локация не найдена')
        conn.execute('UPDATE locations SET archived=1,updated=? WHERE id=?',
                     (time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'archived': True})

    # ------------------------------------------------------------ Memorial / Afterlife

    @atomic_endpoint
    def api_character_memorialize(self, conn, qs, m, body):
        """Mark a Character as fallen (deceased/retired/missing)."""
        user = self.require_gm(conn)
        row = self.get_char(conn, m.group(1))
        data = ensure_progression(json.loads(row['data']))
        status = str((body or {}).get('status') or 'deceased').lower()
        if status not in MEMORIAL_STATUSES:
            raise ApiError(400, 'Неизвестный статус memorial')
        if data.get('status') in MEMORIAL_STATUSES:
            raise ApiError(409, 'Персонаж уже помечен memorial')
        existing = conn.execute('SELECT * FROM memorials WHERE character_id=?',
                                (row['id'],)).fetchone()
        if existing:
            raise ApiError(409, 'Memorial для персонажа уже существует')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину memorial')
        collaborative = bool((body or {}).get('collaborative'))
        # Identity fields are always taken from the Dossier for a memorial.
        source = dict(body or {})
        source.setdefault('handle', data.get('handle'))
        source.setdefault('role', data.get('role'))
        source.setdefault('role_rank', _num(data.get('role_rank')) or 0)
        cleaned = clean_memorial_input(source)
        now = time.time()
        draft_state = 'pending_owner' if collaborative else 'published'
        cur = conn.execute(
            'INSERT INTO memorials(character_id,handle,role,role_rank,portrait_media_id,status,'
            'death_date,location,cause,epitaph,last_words,obituary,gm_notes,visibility,'
            'created_by,created,updated,draft_state) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (row['id'], cleaned['handle'], cleaned['role'], cleaned['role_rank'],
             str(data.get('portrait_media_id') or '')[:64] or None, cleaned['status'],
             cleaned['death_date'], cleaned['location'], cleaned['cause'],
             cleaned['epitaph'], cleaned['last_words'], cleaned['obituary'],
             cleaned['gm_notes'], cleaned['visibility'], user['id'], now, now, draft_state))
        memorial_id = cur.lastrowid
        if collaborative:
            # Owner fills the narrative; the Dossier is frozen only at publish.
            if row['owner_id']:
                add_notification(conn, row['owner_id'], 'memorial_draft',
                                 'Memorial draft awaiting your input',
                                 data.get('handle') or 'Edgerunner',
                                 f'#/memorial/{memorial_id}')
        else:
            feed_post_id = None
            if (body or {}).get('publish_obituary') and cleaned['obituary']:
                cur_feed = conn.execute(
                    'INSERT INTO feed_posts(format,status,creator_user_id,headline,body,'
                    'truth_status,event_at,created,updated) '
                    "VALUES('article','draft',?,?,?,'unknown',?,?,?)",
                    (user['id'], f'In Memoriam: {cleaned["handle"]}', cleaned['obituary'],
                     cleaned['death_date'] or now, now, now))
                feed_post_id = cur_feed.lastrowid
            conn.execute('UPDATE memorials SET feed_post_id=? WHERE id=?',
                         (feed_post_id, memorial_id))
            before = json.loads(row['data'])
            after = copy.deepcopy(before)
            after['status'] = status
            after['archived'] = True
            after['public'] = False
            after['archive_reason'] = reason
            conn.execute('UPDATE characters SET data=?,public=0,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(after, ensure_ascii=False), now, row['id']))
            record_character_changes(conn, row['id'], user['id'], before, after,
                                     f'Memorialized as {status}: {reason}')
        conn.commit()
        fresh = conn.execute('SELECT * FROM memorials WHERE id=?', (memorial_id,)).fetchone()
        self.send_json(memorial_payload(fresh, user, full=True), status=201)

    def api_memorial_list(self, conn, qs, m, body):
        user = self.current_user(conn)
        gm = user_is_gm(user)
        user_id = user['id'] if user else None
        rows = conn.execute(
            'SELECT * FROM memorials WHERE '
            '(? OR visibility=\'public\' OR '
            '(draft_state=\'pending_owner\' AND character_id IN '
            '(SELECT id FROM characters WHERE owner_id=?))) '
            'ORDER BY (status=\'deceased\') DESC,death_date DESC,id DESC',
            (1 if gm else 0, user_id)).fetchall()
        owner_ids = {}
        char_ids = [row['character_id'] for row in rows if row['character_id']]
        if char_ids:
            marks = ','.join('?' for _ in char_ids)
            for r in conn.execute(
                    f'SELECT id,owner_id FROM characters WHERE id IN ({marks})', char_ids):
                owner_ids[r['id']] = r['owner_id']
        memorials = []
        for row in rows:
            payload = memorial_payload(row, user, full=gm)
            draft = row['draft_state'] if 'draft_state' in row.keys() else 'published'
            payload['can_publish'] = bool(gm and draft != 'published')
            owns = bool(row['character_id'] and owner_ids.get(row['character_id']) == user_id)
            payload['can_owner_draft'] = bool(owns and draft == 'pending_owner')
            memorials.append(payload)
        self.send_json({'memorials': memorials})

    def api_memorial_detail(self, conn, qs, m, body):
        user = self.current_user(conn)
        gm = user_is_gm(user)
        user_id = user['id'] if user else None
        row = conn.execute('SELECT * FROM memorials WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Memorial не найден')
        draft = row['draft_state'] if 'draft_state' in row.keys() else 'published'
        owner_match = False
        if row['character_id']:
            owner_match = conn.execute(
                'SELECT owner_id FROM characters WHERE id=?',
                (row['character_id'],)).fetchone()
            owner_match = bool(owner_match and owner_match['owner_id'] == user_id)
        if row['visibility'] != 'public' and not gm and not (
                draft == 'pending_owner' and owner_match):
            raise ApiError(404, 'Memorial не найден')
        payload = memorial_payload(row, user, full=gm)
        payload['can_publish'] = bool(gm and draft != 'published')
        payload['can_owner_draft'] = bool(owner_match and draft == 'pending_owner')
        self.send_json(payload)

    @atomic_endpoint
    def api_memorial_update(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM memorials WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Memorial не найден')
        cleaned = clean_memorial_input(body or {}, row)
        conn.execute(
            'UPDATE memorials SET status=?,handle=?,role=?,role_rank=?,death_date=?,location=?,'
            'cause=?,epitaph=?,last_words=?,obituary=?,gm_notes=?,visibility=?,updated=? WHERE id=?',
            (cleaned['status'], cleaned['handle'], cleaned['role'], cleaned['role_rank'],
             cleaned['death_date'], cleaned['location'], cleaned['cause'],
             cleaned['epitaph'], cleaned['last_words'], cleaned['obituary'],
             cleaned['gm_notes'], cleaned['visibility'], time.time(), row['id']))
        if row['feed_post_id'] and cleaned['obituary']:
            conn.execute(
                "UPDATE feed_posts SET headline=?,body=?,event_at=?,updated=? "
                "WHERE id=? AND status='draft'",
                (f'In Memoriam: {cleaned["handle"]}', cleaned['obituary'],
                 cleaned['death_date'] or row['death_date'] or time.time(),
                 time.time(), row['feed_post_id']))
        conn.commit()
        fresh = conn.execute('SELECT * FROM memorials WHERE id=?', (row['id'],)).fetchone()
        self.send_json(memorial_payload(fresh, user, full=True))

    @atomic_endpoint
    def api_memorial_legacy(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM memorials WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Memorial не найден')
        cleaned = clean_legacy_input(body or {})
        conn.execute(
            'UPDATE memorials SET legacy_drink_name=?,legacy_ingredients=?,legacy_preparation=?,'
            'legacy_glass=?,legacy_garnish=?,legacy_quote=?,legacy_legend=?,'
            'legacy_awarded_by=?,legacy_awarded_at=?,updated=? WHERE id=?',
            (cleaned['drink_name'], cleaned['ingredients'], cleaned['preparation'],
             cleaned['glass'], cleaned['garnish'], cleaned['quote'], cleaned['legend'],
             user['id'], time.time(), time.time(), row['id']))
        conn.commit()
        fresh = conn.execute('SELECT * FROM memorials WHERE id=?', (row['id'],)).fetchone()
        self.send_json(memorial_payload(fresh, user, full=True))

    @atomic_endpoint
    def api_memorial_owner_draft(self, conn, qs, m, body):
        """Owner fills the narrative fields of a pending collaborative memorial."""
        user = self.require_user(conn)
        row = conn.execute('SELECT * FROM memorials WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Memorial не найден')
        if row['draft_state'] == 'published':
            raise ApiError(409, 'Memorial уже опубликован')
        owner_id = None
        if row['character_id']:
            character = conn.execute('SELECT owner_id FROM characters WHERE id=?',
                                     (row['character_id'],)).fetchone()
            owner_id = character['owner_id'] if character else None
        if owner_id is None or owner_id != user['id']:
            raise ApiError(403, 'Только владелец персонажа заполняет memorial')
        payload = body or {}
        visibility = str(payload.get('visibility') or row['visibility']).lower()
        if visibility not in MEMORIAL_VISIBILITIES:
            visibility = row['visibility']
        death_date = row['death_date']
        if payload.get('death_date') not in (None, ''):
            death_date = optional_timestamp(payload.get('death_date'))
        values = [
            death_date,
            str(payload.get('location') or '')[:240],
            str(payload.get('cause') or '')[:2000],
            str(payload.get('epitaph') or '')[:1000],
            str(payload.get('last_words') or '')[:2000],
            str(payload.get('obituary') or '')[:10000],
            visibility,
        ]
        columns = ('death_date=?,location=?,cause=?,epitaph=?,last_words=?,'
                   'obituary=?,visibility=?')
        if len(str(payload.get('drink_name') or '').strip()) >= 2:
            legacy = clean_legacy_input(payload)
            columns = (columns + ',legacy_drink_name=?,legacy_ingredients=?,'
                       'legacy_preparation=?,legacy_glass=?,legacy_garnish=?,'
                       'legacy_quote=?,legacy_legend=?,legacy_awarded_by=?,'
                       'legacy_awarded_at=?')
            values.extend([legacy['drink_name'], legacy['ingredients'],
                           legacy['preparation'], legacy['glass'], legacy['garnish'],
                           legacy['quote'], legacy['legend'], user['id'], time.time()])
        values.extend([time.time(), row['id']])
        conn.execute(f'UPDATE memorials SET {columns},updated=? WHERE id=?', values)
        conn.commit()
        fresh = conn.execute('SELECT * FROM memorials WHERE id=?', (row['id'],)).fetchone()
        self.send_json(memorial_payload(fresh, user, full=True))

    @atomic_endpoint
    def api_memorial_publish(self, conn, qs, m, body):
        """GM finalizes a collaborative memorial: freeze Dossier + obituary draft."""
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM memorials WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Memorial не найден')
        if row['draft_state'] == 'published':
            raise ApiError(409, 'Memorial уже опубликован')
        now = time.time()
        feed_post_id = row['feed_post_id']
        if not feed_post_id and row['obituary']:
            cur_feed = conn.execute(
                'INSERT INTO feed_posts(format,status,creator_user_id,headline,body,'
                'truth_status,event_at,created,updated) '
                "VALUES('article','draft',?,?,?,'unknown',?,?,?)",
                (user['id'], f'In Memoriam: {row["handle"]}', row['obituary'],
                 row['death_date'] or now, now, now))
            feed_post_id = cur_feed.lastrowid
        if row['character_id']:
            character = conn.execute('SELECT * FROM characters WHERE id=?',
                                     (row['character_id'],)).fetchone()
            if character:
                before = json.loads(character['data'])
                after = copy.deepcopy(before)
                after['status'] = row['status']
                after['archived'] = True
                after['public'] = False
                after['archive_reason'] = 'Memorial published'
                conn.execute(
                    'UPDATE characters SET data=?,public=0,updated=?,revision=revision+1 WHERE id=?',
                    (json.dumps(after, ensure_ascii=False), now, row['character_id']))
                record_character_changes(conn, row['character_id'], user['id'],
                                         before, after, 'Memorial published')
        conn.execute(
            'UPDATE memorials SET draft_state=?,feed_post_id=?,updated=? WHERE id=?',
            ('published', feed_post_id, now, row['id']))
        conn.commit()
        fresh = conn.execute('SELECT * FROM memorials WHERE id=?', (row['id'],)).fetchone()
        self.send_json(memorial_payload(fresh, user, full=True))

    @atomic_endpoint
    def api_memorial_restore(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM memorials WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Memorial не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if row['character_id']:
            character = conn.execute('SELECT * FROM characters WHERE id=?',
                                     (row['character_id'],)).fetchone()
            if character:
                before = json.loads(character['data'])
                after = copy.deepcopy(before)
                after.pop('status', None)
                after.pop('archive_reason', None)
                after['archived'] = False
                conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                             (json.dumps(after, ensure_ascii=False), time.time(),
                              row['character_id']))
                restore_note = f'Memorial restored: {reason}' if reason else 'Memorial restored'
                record_character_changes(conn, row['character_id'], user['id'],
                                         before, after, restore_note)
        if row['feed_post_id']:
            conn.execute("DELETE FROM feed_posts WHERE id=? AND status='draft'",
                         (row['feed_post_id'],))
        conn.execute('DELETE FROM memorials WHERE id=?', (row['id'],))
        conn.commit()
        self.send_json({'ok': True, 'restored': True})

    def api_session_access(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or not self.can_manage_session_access(conn, user, session):
            raise ApiError(403, 'Нет права управлять доступом сессии')
        assignments = conn.execute(
            'SELECT a.*,u.username,u.display_name,u.account_role FROM session_access a '
            'JOIN users u ON u.id=a.user_id WHERE a.session_id=? ORDER BY a.role,u.display_name',
            (session['id'],)).fetchall()
        candidates = conn.execute(
            "SELECT id,username,display_name,account_role FROM users "
            "WHERE id>1 AND disabled_at IS NULL AND account_role!='admin' "
            'ORDER BY display_name,username').fetchall()
        self.send_json({
            'owner_user_id': session['owner_user_id'],
            'roles': sorted(SESSION_ACCESS_ROLES),
            'assignments': [dict(row) for row in assignments],
            'candidates': [dict(row) for row in candidates],
        })

    @atomic_endpoint
    def api_session_access_grant(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or not self.can_manage_session_access(conn, user, session):
            raise ApiError(403, 'Нет права управлять доступом сессии')
        target_id = _num((body or {}).get('user_id'))
        role = str((body or {}).get('role') or '').lower()
        target = conn.execute('SELECT * FROM users WHERE id=? AND disabled_at IS NULL',
                              (target_id,)).fetchone()
        if not target or target['id'] == session['owner_user_id'] or role not in SESSION_ACCESS_ROLES:
            raise ApiError(400, 'Некорректная роль участника сессии')
        before = conn.execute('SELECT role FROM session_access WHERE session_id=? AND user_id=?',
                              (session['id'], target['id'])).fetchone()
        now = time.time()
        conn.execute(
            'INSERT INTO session_access(session_id,user_id,role,created_by,created,updated) '
            'VALUES(?,?,?,?,?,?) ON CONFLICT(session_id,user_id) DO UPDATE SET '
            'role=excluded.role,created_by=excluded.created_by,updated=excluded.updated',
            (session['id'], target['id'], role, user['id'], now, now))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'access_grant',
             json.dumps({'user_id': target['id'], 'role': before['role'] if before else None}),
             json.dumps({'user_id': target['id'], 'role': role}), '', now))
        add_notification(conn, target['id'], 'session_access', 'NC//NET Session access',
                         f'{session["title"]}: {role}', f'#/session/{session["id"]}')
        conn.commit()
        self.send_json({'ok': True, 'user_id': target['id'], 'role': role})

    @atomic_endpoint
    def api_session_access_revoke(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or not self.can_manage_session_access(conn, user, session):
            raise ApiError(403, 'Нет права управлять доступом сессии')
        target_id = int(m.group(2))
        before = conn.execute('SELECT * FROM session_access WHERE session_id=? AND user_id=?',
                              (session['id'], target_id)).fetchone()
        if not before:
            raise ApiError(404, 'Назначение доступа не найдено')
        conn.execute('DELETE FROM session_access WHERE session_id=? AND user_id=?',
                     (session['id'], target_id))
        now = time.time()
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'access_revoke', json.dumps(dict(before)),
             json.dumps({'user_id': target_id, 'role': None}), '', now))
        add_notification(conn, target_id, 'session_access_revoked', 'NC//NET Session access revoked',
                         session['title'], None)
        conn.commit()
        self.send_json({'ok': True})

    def safety_signal_payload(self, row):
        return {
            'id': row['id'], 'kind': row['kind'], 'message': row['message'],
            'status': row['status'], 'created': row['created'],
            'acknowledged_at': row['acknowledged_at'], 'resolved_at': row['resolved_at'],
        }

    def api_session_safety(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, session)
        if not session or not role:
            raise ApiError(403, 'Нет доступа к экрану сессии')
        if 'manage_safety' in capabilities:
            rows = conn.execute(
                'SELECT * FROM session_safety_signals WHERE session_id=? '
                'ORDER BY CASE status WHEN \'open\' THEN 0 WHEN \'acknowledged\' THEN 1 ELSE 2 END,created DESC',
                (session['id'],)).fetchall()
        else:
            rows = conn.execute(
                'SELECT * FROM session_safety_signals WHERE session_id=? AND user_id=? ORDER BY created DESC',
                (session['id'], user['id'])).fetchall()
        self.send_json({'safety_config': session_safety_config(session['safety_config']),
                        'can_manage': 'manage_safety' in capabilities,
                        'signals': [self.safety_signal_payload(row) for row in rows]})

    @atomic_endpoint
    def api_session_safety_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, session)
        if not session or not role:
            raise ApiError(403, 'Нет доступа к экрану сессии')
        config = session_safety_config(session['safety_config'])
        if not config['pause_enabled']:
            raise ApiError(409, 'Safety signal отключён для этой сессии')
        self.rate_limit('session-safety', 10, 3600, user['id'])
        kind = str((body or {}).get('kind') or 'pause').lower()
        if kind not in SAFETY_SIGNAL_KINDS:
            raise ApiError(400, 'Некорректный тип Safety signal')
        message = str((body or {}).get('message') or '').strip()[:500]
        now = time.time()
        cur = conn.execute(
            'INSERT INTO session_safety_signals(session_id,user_id,kind,message,status,created) '
            "VALUES(?,?,?,?,'open',?)", (session['id'], user['id'], kind, message, now))
        recipients = {session['owner_user_id']}
        recipients.update(row['user_id'] for row in conn.execute(
            "SELECT user_id FROM session_access WHERE session_id=? AND role='co_gm'",
            (session['id'],)).fetchall())
        for recipient in recipients:
            if recipient != user['id']:
                add_notification(conn, recipient, 'session_safety', 'Anonymous Session safety signal',
                                 session['title'], f'#/session/{session["id"]}')
        conn.commit()
        row = conn.execute('SELECT * FROM session_safety_signals WHERE id=?',
                           (cur.lastrowid,)).fetchone()
        self.send_json(self.safety_signal_payload(row), status=201)

    @atomic_endpoint
    def api_session_safety_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, session)
        if not session or 'manage_safety' not in capabilities:
            raise ApiError(403, 'Нет права управлять Safety signal')
        signal = conn.execute(
            'SELECT * FROM session_safety_signals WHERE id=? AND session_id=?',
            (int(m.group(2)), session['id'])).fetchone()
        if not signal:
            raise ApiError(404, 'Safety signal не найден')
        status = str((body or {}).get('status') or '').lower()
        if status not in ('acknowledged', 'resolved'):
            raise ApiError(400, 'Некорректный статус Safety signal')
        if signal['status'] == 'resolved' and status != 'resolved':
            raise ApiError(409, 'Resolved Safety signal нельзя открыть повторно')
        now = time.time()
        if status == 'acknowledged':
            conn.execute(
                "UPDATE session_safety_signals SET status='acknowledged',acknowledged_by=?,"
                'acknowledged_at=? WHERE id=?', (user['id'], now, signal['id']))
        else:
            conn.execute(
                "UPDATE session_safety_signals SET status='resolved',resolved_by=?,resolved_at=?,"
                'acknowledged_by=COALESCE(acknowledged_by,?),'
                'acknowledged_at=COALESCE(acknowledged_at,?) WHERE id=?',
                (user['id'], now, user['id'], now, signal['id']))
        conn.commit()
        updated = conn.execute('SELECT * FROM session_safety_signals WHERE id=?',
                               (signal['id'],)).fetchone()
        self.send_json(self.safety_signal_payload(updated))

    def api_character_net_contexts(self, conn, qs, m, body):
        user, character = self.require_character_editor(conn, m.group(1))
        rows = conn.execute(
            'SELECT DISTINCT s.* FROM nc_sessions s JOIN session_combatants c '
            'ON c.session_id=s.id WHERE c.character_id=? '
            "AND s.status IN ('preparing','active','paused') ORDER BY s.updated DESC",
            (character['id'],)).fetchall()
        contexts = []
        for session in rows:
            role, capabilities = self.session_capabilities(conn, user, session)
            if not role:
                continue
            state = session_net_state(_row_value(session, 'net_state_json', '{}'))
            targets = conn.execute(
                'SELECT id,kind,character_id,name FROM session_combatants '
                'WHERE session_id=? AND (character_id IS NULL OR character_id!=?) '
                'ORDER BY initiative DESC,sort_order,id',
                (session['id'], character['id'])).fetchall()
            contexts.append({
                'session_id': session['id'], 'title': session['title'],
                'status': session['status'], 'access_role': role,
                'floors': state['floors'], 'nodes': state['nodes'],
                'paths': state['paths'],
                'targets': [dict(target) for target in targets],
                'can_manage_net': 'edit_combatants' in capabilities,
            })
        self.send_json({'character_id': character['id'], 'sessions': contexts})

    @atomic_endpoint
    def api_session_net_floor_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать Session NET Floors')
        label = str((body or {}).get('label') or '').strip()[:120]
        note = str((body or {}).get('reason') or '').strip()[:500]
        if not label:
            raise ApiError(400, 'NET Floor требует label')
        if len(note) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Floors')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        if len(state['floors']) >= 100 or any(
                item['label'].lower() == label.lower() for item in state['floors']):
            raise ApiError(409, 'NET Floor уже существует или достигнут лимит')
        before = copy.deepcopy(state)
        floor = {'floor_id': secrets.token_hex(16), 'label': label,
                 'sort_order': len(state['floors'])}
        state['floors'].append(floor)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_floor_create',
             json.dumps(before, ensure_ascii=False),
             json.dumps(state, ensure_ascii=False), note, now))
        conn.commit()
        self.send_json(floor, status=201)

    @atomic_endpoint
    def api_session_net_floor_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать Session NET Floors')
        floor_id = str(m.group(2)).lower()
        note = str((body or {}).get('reason') or '').strip()[:500]
        if len(note) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Floors')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        floor = next((item for item in state['floors']
                      if item['floor_id'] == floor_id), None)
        if not floor:
            raise ApiError(404, 'Session NET Floor не найден')
        if any(item['floor_id'] == floor_id for item in state['nodes']):
            raise ApiError(409, 'Сначала удалите NET nodes с этого Floor')
        if any(item['active'] and item['floor_id'] == floor_id
               for item in state['links']):
            raise ApiError(409, 'NET Floor используется active entity')
        before = copy.deepcopy(state)
        state['floors'] = [item for item in state['floors']
                           if item['floor_id'] != floor_id]
        for index, item in enumerate(state['floors']):
            item['sort_order'] = index
        state['links'] = [item for item in state['links']
                          if item['floor_id'] != floor_id]
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_floor_delete',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             note, now))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_net_node_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        allowed = {'floor_id', 'type', 'label', 'dv', 'defense',
                   'visible', 'resolved', 'gm_note', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET node содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        floor_id = str((body or {}).get('floor_id') or '').lower()
        node_type = str((body or {}).get('type') or '').lower()
        label = str((body or {}).get('label') or '').strip()[:120]
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not any(item['floor_id'] == floor_id for item in state['floors']):
            raise ApiError(400, 'NET node требует validated Floor')
        if node_type not in SESSION_NET_NODE_TYPES or not label:
            raise ApiError(400, 'Некорректный NET node type или label')
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        if len(state['nodes']) >= 500:
            raise ApiError(409, 'Достигнут лимит NET nodes')
        before = copy.deepcopy(state)
        node = {
            'node_id': secrets.token_hex(16), 'floor_id': floor_id,
            'type': node_type, 'label': label,
            'dv': max(0, min(29, int(_num((body or {}).get('dv')) or 0))),
            'defense': max(0, min(29, int(_num((body or {}).get('defense')) or 0))),
            'visible': (body or {}).get('visible') is True,
            'resolved': (body or {}).get('resolved') is True,
            'gm_note': str((body or {}).get('gm_note') or '')[:2000],
            'sort_order': len(state['nodes']),
        }
        state['nodes'].append(node)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_node_create',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(node, status=201)

    @atomic_endpoint
    def api_session_net_node_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        allowed = {'type', 'label', 'dv', 'defense', 'visible',
                   'resolved', 'gm_note', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET node содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        node_id = str(m.group(2)).lower()
        node = next((item for item in state['nodes']
                     if item['node_id'] == node_id), None)
        if not node:
            raise ApiError(404, 'NET node не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        node_type = str((body or {}).get('type', node['type'])).lower()
        label = str((body or {}).get('label', node['label'])).strip()[:120]
        if node_type not in SESSION_NET_NODE_TYPES or not label:
            raise ApiError(400, 'Некорректный NET node type или label')
        node.update({
            'type': node_type, 'label': label,
            'dv': max(0, min(29, int(_num((body or {}).get('dv', node['dv'])) or 0))),
            'defense': max(0, min(29, int(_num(
                (body or {}).get('defense', node['defense'])) or 0))),
            'visible': (body or {}).get('visible', node['visible']) is True,
            'resolved': (body or {}).get('resolved', node['resolved']) is True,
            'gm_note': str((body or {}).get('gm_note', node['gm_note']) or '')[:2000],
        })
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_node_update',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(node)

    @atomic_endpoint
    def api_session_net_node_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        node_id = str(m.group(2)).lower()
        node = next((item for item in state['nodes']
                     if item['node_id'] == node_id), None)
        if not node:
            raise ApiError(404, 'NET node не найден')
        if any(item['from_node_id'] == node_id or item['to_node_id'] == node_id
               for item in state['paths']):
            raise ApiError(409, 'Сначала удалите NET paths этого node')
        if any(item['active'] and item.get('node_id') == node_id
               for item in state['links']):
            raise ApiError(409, 'NET node используется active entity')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        state['nodes'] = [item for item in state['nodes'] if item['node_id'] != node_id]
        for index, item in enumerate(state['nodes']):
            item['sort_order'] = index
        for link in state['links']:
            if link.get('node_id') == node_id:
                link['node_id'] = None
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_node_delete',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_net_path_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        allowed = {'from_node_id', 'to_node_id', 'direction',
                   'label', 'visible', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET path содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        from_id = str((body or {}).get('from_node_id') or '').lower()
        to_id = str((body or {}).get('to_node_id') or '').lower()
        direction = str((body or {}).get('direction') or 'bidirectional').lower()
        node_ids = {item['node_id'] for item in state['nodes']}
        if (from_id not in node_ids or to_id not in node_ids or from_id == to_id or
                direction not in SESSION_NET_PATH_DIRECTIONS):
            raise ApiError(400, 'Некорректные NET path endpoints или direction')
        if any(item['from_node_id'] == from_id and item['to_node_id'] == to_id and
               item['direction'] == direction for item in state['paths']):
            raise ApiError(409, 'NET path уже существует')
        if direction == 'bidirectional' and any(
                item['from_node_id'] == to_id and item['to_node_id'] == from_id and
                item['direction'] == direction for item in state['paths']):
            raise ApiError(409, 'NET path уже существует')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        if len(state['paths']) >= 1000:
            raise ApiError(409, 'Достигнут лимит NET paths')
        before = copy.deepcopy(state)
        path = {
            'path_id': secrets.token_hex(16), 'from_node_id': from_id,
            'to_node_id': to_id, 'direction': direction,
            'label': str((body or {}).get('label') or '')[:120],
            'visible': (body or {}).get('visible') is True,
        }
        state['paths'].append(path)
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_path_create',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(path, status=201)

    @atomic_endpoint
    def api_session_net_path_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        if set(body or {}) - {'label', 'visible', 'reason'}:
            raise ApiError(400, 'NET path содержит неподдерживаемые поля')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        path_id = str(m.group(2)).lower()
        path = next((item for item in state['paths']
                     if item['path_id'] == path_id), None)
        if not path:
            raise ApiError(404, 'NET path не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        path['label'] = str((body or {}).get('label', path['label']) or '')[:120]
        path['visible'] = (body or {}).get('visible', path['visible']) is True
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_path_update',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json(path)

    @atomic_endpoint
    def api_session_net_path_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_session' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права редактировать NET Architecture')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        path_id = str(m.group(2)).lower()
        if not any(item['path_id'] == path_id for item in state['paths']):
            raise ApiError(404, 'NET path не найден')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Architecture')
        before = copy.deepcopy(state)
        state['paths'] = [item for item in state['paths'] if item['path_id'] != path_id]
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_path_delete',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             reason, now))
        conn.commit()
        self.send_json({'ok': True})

    @atomic_endpoint
    def api_session_net_action(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or session['status'] not in ('preparing', 'active', 'paused'):
            raise ApiError(404, 'Live NET Session не найдена')
        allowed = {'action', 'actor_combatant_id', 'target_node_id',
                   'program_instance_id', 'target_entity_id',
                   'character_revision', 'target_character_revision', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'NET action содержит неподдерживаемые поля')
        actor_id = _num((body or {}).get('actor_combatant_id'))
        actor = conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
            (session['id'], int(actor_id))).fetchone() \
            if actor_id is not None and int(actor_id) == actor_id else None
        if not actor or not actor['character_id']:
            raise ApiError(400, 'NET action требует Character combatant')
        character = conn.execute('SELECT * FROM characters WHERE id=?',
                                 (actor['character_id'],)).fetchone()
        if not character:
            raise ApiError(404, 'Character для NET action не найден')
        capabilities = self.session_capabilities(conn, user, session)[1]
        if character['owner_id'] != user['id'] and 'edit_combatants' not in capabilities:
            raise ApiError(403, 'Нет права выполнять NET action этим Character')
        character_data = enrich_owned_item_interactions(
            ensure_progression(json.loads(character['data'])))
        interface_rank = character_interface_rank(character_data)
        if interface_rank <= 0:
            raise ApiError(409, 'NET action требует Netrunner Role')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину NET action')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        before_state = copy.deepcopy(state)
        node_by_id = {item['node_id']: item for item in state['nodes']}
        runner = next((item for item in state['runners']
                       if item['combatant_id'] == actor['id']), None)
        if not runner:
            runner = {
                'combatant_id': actor['id'], 'character_id': character['id'],
                'node_id': None, 'previous_node_id': None, 'jacked_in': False,
                'interface_rank': interface_rank, 'actions_recorded': 0,
                'action_round': state['round'], 'actions_used': 0,
                'action_penalty': 0, 'next_action_penalty': 0,
                'last_action_at': None,
            }
            state['runners'].append(runner)
        runner['interface_rank'] = interface_rank
        action = str((body or {}).get('action') or '').lower()
        if runner.get('action_round') != state['round']:
            runner['action_round'] = state['round']
            runner['actions_used'] = 0
            runner['action_penalty'] = runner.get('next_action_penalty', 0)
            runner['next_action_penalty'] = 0
        consumes_net_action = action not in ('jack_in', 'jack_out')
        actions_max = max(
            2, net_actions_for_interface(interface_rank) - runner.get('action_penalty', 0))
        if consumes_net_action and runner.get('actions_used', 0) >= actions_max:
            raise ApiError(409, 'NET Action budget исчерпан для текущего NET Round')
        target_node_id = str((body or {}).get('target_node_id') or '').lower()
        target_node = node_by_id.get(target_node_id)
        now = time.time()
        result = {'action': action, 'actor_combatant_id': actor['id'],
                  'interface_rank': interface_rank}
        character_before = None
        character_ledger_id = None
        target_character = None
        target_character_data = None
        target_character_before = None
        target_character_ledger_id = None
        if action == 'jack_in':
            if not target_node or target_node['type'] != 'access_point':
                raise ApiError(400, 'Jack In требует Access Point node')
            if not target_node['visible'] and 'edit_combatants' not in capabilities:
                raise ApiError(403, 'Access Point node ещё не revealed')
            runner.update({'jacked_in': True, 'node_id': target_node_id,
                           'previous_node_id': None})
            target_node['visible'] = True
            result.update({'success': True, 'summary': f'Jack In at {target_node["label"]}'})
        elif action == 'jack_out':
            if not runner['jacked_in']:
                raise ApiError(409, 'Netrunner не Jacked In')
            runner.update({'jacked_in': False, 'node_id': None,
                           'previous_node_id': None})
            result.update({'success': True, 'summary': 'Safe Jack Out recorded'})
        else:
            if not runner['jacked_in'] or runner.get('node_id') not in node_by_id:
                raise ApiError(409, 'NET action требует Jacked In Netrunner')
            current_node = node_by_id[runner['node_id']]
            if action == 'move':
                if not target_node or not target_node['visible']:
                    raise ApiError(409, 'Move требует revealed target node')
                path = session_net_path_between(
                    state, current_node['node_id'], target_node_id,
                    require_visible=True)
                if not path:
                    raise ApiError(409, 'NET nodes не соединены revealed path')
                if (current_node['type'] == 'password' and
                        not current_node['resolved'] and
                        target_node_id != runner.get('previous_node_id')):
                    raise ApiError(409, 'Unresolved Password блокирует движение вперёд')
                runner['previous_node_id'] = current_node['node_id']
                runner['node_id'] = target_node_id
                result.update({'success': True,
                               'summary': f'Move to {target_node["label"]}'})
            elif action == 'pathfinder':
                if not target_node:
                    target_node = next((node for node in state['nodes']
                                        if not node['visible'] and
                                        session_net_path_between(
                                            state, current_node['node_id'],
                                            node['node_id'], require_visible=False)), None)
                    target_node_id = target_node['node_id'] if target_node else ''
                if not target_node:
                    raise ApiError(404, 'Pathfinder target node не найден')
                path = session_net_path_between(
                    state, current_node['node_id'], target_node_id,
                    require_visible=False)
                if not path:
                    raise ApiError(409, 'Pathfinder target должен быть adjacent node')
                dv = max(1, target_node['dv'] or 9)
                die = secrets.randbelow(10) + 1
                total = interface_rank + die
                success = total >= dv
                if success:
                    target_node['visible'] = True
                    path['visible'] = True
                result.update({'success': success, 'actor_roll': die,
                               'actor_total': total, 'defense_total': dv,
                               'summary': f'Pathfinder {total} vs DV{dv}'})
            elif action == 'backdoor':
                node = target_node or current_node
                if node['node_id'] != current_node['node_id'] or node['type'] != 'password':
                    raise ApiError(409, 'Backdoor требует текущий Password node')
                dv = max(1, node['dv'] or 9)
                die = secrets.randbelow(10) + 1
                total = interface_rank + die
                success = total >= dv
                if success:
                    node['resolved'] = True
                    node['visible'] = True
                result.update({'success': success, 'actor_roll': die,
                               'actor_total': total, 'defense_total': dv,
                               'summary': f'Backdoor {total} vs DV{dv}'})
            elif action == 'eye_dee':
                node = target_node or current_node
                if node['node_id'] != current_node['node_id']:
                    raise ApiError(409, 'Eye-Dee доступен только для текущего node')
                node['visible'] = True
                result.update({'success': True,
                               'summary': f'Eye-Dee identifies {node["label"]}'})
            elif action == 'control':
                node = target_node or current_node
                if node['node_id'] != current_node['node_id'] or node['type'] != 'control':
                    raise ApiError(409, 'Control action требует текущий Control node')
                dv = max(1, node['dv'] or node['defense'] or 9)
                die = secrets.randbelow(10) + 1
                total = interface_rank + die
                success = total >= dv
                if success:
                    node['resolved'] = True
                    node['visible'] = True
                    node['controlled_by_combatant_id'] = actor['id']
                result.update({'success': success, 'actor_roll': die,
                               'actor_total': total, 'defense_total': dv,
                               'summary': f'Control {total} vs DV{dv}'})
            elif action == 'program_attack':
                program_id = str((body or {}).get('program_instance_id') or '').lower()
                entity_id = str((body or {}).get('target_entity_id') or '').lower()
                link = next((item for item in state['links']
                             if item['net_entity_id'] == entity_id and item['active']), None)
                if not link or link.get('node_id') != current_node['node_id']:
                    raise ApiError(409, 'Program Attack требует Black ICE на текущем node')
                target_character = conn.execute('SELECT * FROM characters WHERE id=?',
                                                (link['character_id'],)).fetchone()
                target_character_data = enrich_owned_item_interactions(
                    ensure_progression(json.loads(target_character['data']))) \
                    if target_character else None
                if target_character and target_character['id'] == character['id']:
                    target_character_data = character_data
                target_entity = (target_character_data.get('net_entities') or {}).get(
                    entity_id) if target_character_data else None
                if not isinstance(target_entity, dict) or target_entity.get('status') not in (
                        'lying_in_wait', 'hunting'):
                    raise ApiError(409, 'Program Attack target entity недоступна')
                owned = {item.get('instance_id'): item for item in character_data.get('inventory') or []
                         if isinstance(item, dict) and item.get('instance_id')}
                program = owned.get(program_id)
                modifications = character_modifications(conn, character['id'])
                program_modification = next((item for item in modifications
                                             if item.get('upgrade_instance_id') == program_id and
                                             item.get('host_type') == 'cyberdeck'), None)
                if (not program or not program_modification or
                        cyberdeck_program_category(program) != 'attacker'):
                    raise ApiError(409, 'Program Attack требует installed Attacker Program')
                expected_revision = _num((body or {}).get('character_revision'))
                if expected_revision != (_row_value(character, 'revision', 0) or 0):
                    raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
                attack_die = secrets.randbelow(10) + 1
                defense_die = secrets.randbelow(10) + 1
                attack = interface_rank + int(_num((program.get('mechanics') or {}).get('atk')) or 0) + attack_die
                defense = int(_num(target_entity.get('def')) or 0) + defense_die
                success = attack > defense
                character_before = copy.deepcopy(character_data)
                runtime = initial_program_runtime_state(
                    program, program_modification['host_instance_id'],
                    program_modification['modification_id'],
                    (character_data.get('program_state') or {}).get(program_id))
                runtime['run_count'] += 1
                runtime['last_run_at'] = now
                character_data.setdefault('program_state', {})[program_id] = runtime
                catalog_program = item_by_id(catalog_item_id_for_entry(program)) or {}
                result.update({
                    'success': success, 'actor_roll': attack_die,
                    'defense_roll': defense_die, 'actor_total': attack,
                    'defense_total': defense,
                    'manual_effect': str(catalog_program.get('desc') or '')[:2000],
                    'summary': f'{program.get("name")} attack {attack} vs DEF {defense}',
                })
                damage_dice = ATTACKER_PROGRAM_BLACK_ICE_DAMAGE.get(
                    str(program.get('name') or ''))
                if success and damage_dice:
                    expected_target_revision = _num(
                        (body or {}).get('target_character_revision'))
                    if expected_target_revision != (
                            _row_value(target_character, 'revision', 0) or 0):
                        raise ApiError(409, 'Target Dossier изменён в другой вкладке')
                    damage = roll_dice(damage_dice, 6)
                    if target_character['id'] != character['id']:
                        target_character_before = copy.deepcopy(target_character_data)
                    previous_target_rez = int(target_entity.get('rez_current') or 0)
                    target_entity['rez_current'] = max(
                        0, previous_target_rez - damage['total'])
                    target_entity['updated_at'] = now
                    source_program_id = str(
                        target_entity.get('source_program_instance_id') or '')
                    target_program_item = next(
                        (item for item in target_character_data.get('inventory') or []
                         if isinstance(item, dict) and
                         item.get('instance_id') == source_program_id), None)
                    target_modifications = character_modifications(
                        conn, target_character['id'])
                    target_program_modification = next(
                        (item for item in target_modifications
                         if item.get('upgrade_instance_id') == source_program_id), None)
                    if target_program_item and target_program_modification:
                        target_runtime = initial_program_runtime_state(
                            target_program_item,
                            target_program_modification['host_instance_id'],
                            target_program_modification['modification_id'],
                            (target_character_data.get('program_state') or {}).get(
                                source_program_id))
                        target_runtime['rez_current'] = target_entity['rez_current']
                        if target_entity['rez_current'] == 0:
                            target_entity['status'] = 'derezzed'
                            target_runtime['status'] = 'derezzed'
                            link['initiative'] = 0
                        target_character_data.setdefault('program_state', {})[
                            source_program_id] = target_runtime
                    result.update({
                        'damage_rolls': damage['rolls'],
                        'damage_total': damage['total'],
                        'damage_target': 'black_ice_rez',
                        'damage_application': 'automated',
                        'rez_before': previous_target_rez,
                        'rez_after': target_entity['rez_current'],
                        'target_derezzed': target_entity['rez_current'] == 0,
                    })
            else:
                raise ApiError(400, 'NET action: jack_in/jack_out/move/pathfinder/backdoor/eye_dee/control/program_attack')
            runner['actions_recorded'] += 1
            runner['actions_used'] = runner.get('actions_used', 0) + 1
        runner['last_action_at'] = now
        action_entry = {
            'action_id': secrets.token_hex(16), 'combatant_id': actor['id'],
            'action': action, 'target_node_id': target_node_id or None,
            'target_entity_id': str((body or {}).get('target_entity_id') or '') or None,
            'success': result.get('success'),
            'actor_total': result.get('actor_total'),
            'defense_total': result.get('defense_total'),
            'created': now, 'summary': result.get('summary') or action,
        }
        state.setdefault('action_log', []).append(action_entry)
        state['action_log'] = state['action_log'][-100:]
        if target_character_before is not None:
            target_revision_before = _row_value(target_character, 'revision', 0) or 0
            target_character_ledger_id = record_character_change_set(
                conn, target_character['id'], user['id'],
                target_character_before, target_character_data,
                f'Live NET target damage from {result["summary"]}: {reason}',
                target_revision_before, target_revision_before + 1,
                category='item_action')
            target_ledger_row = conn.execute(
                'SELECT delta_json FROM character_ledger WHERE id=?',
                (target_character_ledger_id,)).fetchone()
            target_delta = parse_json_object(target_ledger_row['delta_json'])
            target_delta.update({
                'revertible': False, 'multi_character_operation': True,
                'session_id': session['id'],
            })
            conn.execute('UPDATE character_ledger SET session_id=?,delta_json=? WHERE id=?',
                         (session['id'], json.dumps(target_delta, ensure_ascii=False),
                          target_character_ledger_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(target_character_data, ensure_ascii=False), now,
                          target_revision_before + 1, target_character['id']))
            result['target_character_revision'] = target_revision_before + 1
        if character_before is not None:
            revision_before = _row_value(character, 'revision', 0) or 0
            character_ledger_id = record_character_change_set(
                conn, character['id'], user['id'], character_before, character_data,
                f'Live NET {result["summary"]}: {reason}',
                revision_before, revision_before + 1, category='item_action')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (character_ledger_id,)).fetchone()
            ledger_delta = parse_json_object(ledger_row['delta_json'])
            ledger_delta['session_net_change'] = {
                'session_id': session['id'], 'before': before_state,
                'after': copy.deepcopy(state),
            }
            if target_character_ledger_id is not None:
                ledger_delta.update({
                    'revertible': False, 'multi_character_operation': True,
                    'linked_target_ledger_id': target_character_ledger_id,
                    'linked_target_character_id': target_character['id'],
                })
            conn.execute('UPDATE character_ledger SET session_id=?,delta_json=? WHERE id=?',
                         (session['id'], json.dumps(ledger_delta, ensure_ascii=False),
                          character_ledger_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(character_data, ensure_ascii=False), now,
                          revision_before + 1, character['id']))
            result['character_revision'] = revision_before + 1
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_action',
             json.dumps(before_state, ensure_ascii=False),
             json.dumps(action_entry, ensure_ascii=False), reason, now))
        conn.commit()
        updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (session['id'],)).fetchone()
        self.send_json({
            'result': result,
            'session': self.session_payload(
                conn, updated, user,
                player_view='view_gm' not in capabilities),
        })

    @atomic_endpoint
    def api_session_black_ice_attack(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права выполнять Black ICE attack')
        allowed = {'selection_mode', 'target_program_instance_id',
                   'target_character_revision', 'reason'}
        if set(body or {}) - allowed:
            raise ApiError(400, 'Black ICE attack содержит неподдерживаемые поля')
        entity_id = str(m.group(2)).lower()
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        state_before = copy.deepcopy(state)
        link = next((item for item in state['links']
                     if item['net_entity_id'] == entity_id and item['active']), None)
        if not link or not link.get('target_combatant_id'):
            raise ApiError(409, 'Black ICE attack требует active target link')
        source_character = conn.execute('SELECT * FROM characters WHERE id=?',
                                        (link['character_id'],)).fetchone()
        if not source_character:
            raise ApiError(409, 'Source Black ICE Character отсутствует')
        source_data = enrich_owned_item_interactions(
            ensure_progression(json.loads(source_character['data'])))
        entity = (source_data.get('net_entities') or {}).get(entity_id)
        if not isinstance(entity, dict) or entity.get('status') != 'hunting':
            raise ApiError(409, 'Black ICE attack требует hunting entity')
        source_program = next((item for item in source_data.get('inventory') or []
                               if isinstance(item, dict) and
                               item.get('instance_id') == entity.get('source_program_instance_id')), None)
        if not source_program:
            raise ApiError(409, 'Source Black ICE Program отсутствует')
        target_combatant = conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? AND id=?',
            (session['id'], link['target_combatant_id'])).fetchone()
        if not target_combatant or not target_combatant['character_id']:
            raise ApiError(409, 'Black ICE target требует Netrunner Character')
        target_runner = next((item for item in state['runners']
                              if item['combatant_id'] == target_combatant['id']), None)
        if (not target_runner or not target_runner['jacked_in'] or
                target_runner.get('node_id') != link.get('node_id')):
            raise ApiError(409, 'Black ICE target должен быть Jacked In на том же node')
        target_character = conn.execute('SELECT * FROM characters WHERE id=?',
                                        (target_combatant['character_id'],)).fetchone()
        target_data = enrich_owned_item_interactions(
            ensure_progression(json.loads(target_character['data'])))
        target_interface = character_interface_rank(target_data)
        if target_interface <= 0:
            raise ApiError(409, 'Black ICE target не имеет Interface Rank')
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if len(reason) < 3:
            raise ApiError(400, 'Укажите причину Black ICE attack')
        effect = black_ice_effect_profile(source_program)
        attack_die = secrets.randbelow(10) + 1
        attack_total = int(entity.get('atk') or 0) + attack_die
        target_before = None
        target_ledger_id = None
        removed_modification_ids = []
        created_effects = []
        now = time.time()
        result = {
            'action': 'black_ice_attack', 'actor_entity_id': entity_id,
            'name': entity.get('name'), 'attack_roll': attack_die,
            'attack_total': attack_total, 'effect_profile': effect,
        }
        target_program_id = None
        if entity.get('target_type') == 'enemy_program_source':
            target_modifications = character_modifications(conn, target_character['id'])
            target_decks = character_effective_cyberdecks(target_data, target_modifications)
            valid_programs = [
                program for deck in target_decks.values()
                for program in deck.get('programs') or []
                if (program.get('runtime') or {}).get('status') == 'rezzed']
            if not valid_programs:
                raise ApiError(409, 'Нет Rezzed Programs для Anti-Program Black ICE')
            selection_mode = str((body or {}).get('selection_mode') or 'random').lower()
            if selection_mode == 'random':
                target_program = valid_programs[secrets.randbelow(len(valid_programs))]
            elif selection_mode == 'override':
                requested_id = str((body or {}).get('target_program_instance_id') or '').lower()
                target_program = next((program for program in valid_programs
                                       if program['instance_id'] == requested_id), None)
                if not target_program:
                    raise ApiError(400, 'Выбранная target Program не является Rezzed')
            else:
                raise ApiError(400, 'selection_mode: random/override')
            expected_revision = _num((body or {}).get('target_character_revision'))
            if expected_revision != (_row_value(target_character, 'revision', 0) or 0):
                raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
            target_program_id = target_program['instance_id']
            defense_die = secrets.randbelow(10) + 1
            defense_total = int(_num((target_program.get('mechanics') or {}).get('def')) or 0) + defense_die
            success = attack_total > defense_total
            result.update({
                'selection_mode': selection_mode,
                'target_program_instance_id': target_program_id,
                'target_program_name': target_program['name'],
                'defense_roll': defense_die, 'defense_total': defense_total,
                'success': success,
            })
            if success:
                damage = roll_dice(effect.get('damage_dice') or 0, 6)
                if not damage['rolls']:
                    raise ApiError(409, 'Anti-Program Black ICE effect требует manual resolution')
                target_before = copy.deepcopy(target_data)
                program_item = next(item for item in target_data.get('inventory') or []
                                    if isinstance(item, dict) and
                                    item.get('instance_id') == target_program_id)
                runtime = initial_program_runtime_state(
                    program_item, (target_program.get('runtime') or {}).get('deck_instance_id'),
                    (target_program.get('runtime') or {}).get('modification_id'),
                    (target_data.get('program_state') or {}).get(target_program_id))
                previous_rez = runtime['rez_current']
                destroyed = damage['total'] >= previous_rez and effect['destroy_on_derez']
                if destroyed:
                    program_modification = next(
                        item for item in target_modifications
                        if item.get('upgrade_instance_id') == target_program_id)
                    backup_modification = next((
                        item for item in target_modifications
                        if item.get('host_instance_id') == program_modification.get('host_instance_id') and
                        (next((owned for owned in target_data.get('inventory') or []
                               if isinstance(owned, dict) and
                               owned.get('instance_id') == item.get('upgrade_instance_id')), {}) or {}).get('name') == 'Backup Drive'), None)
                    if runtime['category'] != 'black_ice' and backup_modification:
                        backup_state = target_data.setdefault('modification_state', {}).setdefault(
                            backup_modification['modification_id'],
                            {'resource_type': 'backup_drive', 'saved_programs': []})
                        backup_state.setdefault('saved_programs', []).append({
                            'program_instance_id': target_program_id,
                            'modification_id': program_modification['modification_id'],
                            'catalog_item_id': catalog_item_id_for_entry(program_item),
                            'name': program_item.get('name'),
                            'runtime_before': copy.deepcopy(runtime), 'saved_at': now,
                        })
                    runtime['status'] = 'destroyed'
                    runtime['rez_current'] = 0
                    if runtime['category'] == 'black_ice':
                        target_ice = next((ice for ice in
                                           (target_data.get('net_entities') or {}).values()
                                           if isinstance(ice, dict) and
                                           ice.get('source_program_instance_id') == target_program_id and
                                           ice.get('status') in ('lying_in_wait', 'hunting', 'derezzed')), None)
                        if target_ice:
                            target_ice['status'] = 'destroyed'
                            target_ice['rez_current'] = 0
                            target_ice['archived_at'] = now
                            target_ice['updated_at'] = now
                            linked_target_ice = next((item for item in state['links']
                                                      if item['net_entity_id'] ==
                                                      target_ice.get('net_entity_id')), None)
                            if linked_target_ice:
                                linked_target_ice['active'] = False
                    program_item['state'] = 'broken'
                    program_item.pop('host_instance_id', None)
                    conn.execute(
                        'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                        'WHERE modification_id=?',
                        (user['id'], now, now, program_modification['modification_id']))
                    removed_modification_ids.append(program_modification['modification_id'])
                else:
                    runtime['rez_current'] = max(0, previous_rez - damage['total'])
                    if runtime['rez_current'] == 0:
                        runtime['status'] = 'derezzed'
                target_data.setdefault('program_state', {})[target_program_id] = runtime
                if runtime['status'] in ('derezzed', 'destroyed'):
                    pending = queue_defense_sequencer_trigger(
                        target_data, target_modifications,
                        runtime.get('deck_instance_id'), target_program_id)
                    if pending:
                        result['defense_sequencer_pending'] = pending
                result.update({
                    'damage_rolls': damage['rolls'], 'damage_total': damage['total'],
                    'rez_before': previous_rez, 'rez_after': runtime['rez_current'],
                    'destroyed': destroyed,
                })
        else:
            defense_die = secrets.randbelow(10) + 1
            defense_total = target_interface + defense_die
            result.update({
                'target_combatant_id': target_combatant['id'],
                'target_interface_rank': target_interface,
                'defense_roll': defense_die, 'defense_total': defense_total,
                'success': attack_total > defense_total,
                'manual_effect': effect['manual_effect'],
            })
            if result['success'] and source_program.get('name') == 'Wisp':
                target_runner['next_action_penalty'] = max(
                    1, target_runner.get('next_action_penalty', 0))
                result['next_action_penalty'] = 1
                result['action_penalty_minimum'] = 2
            if result['success'] and effect['resolution'] == 'automated_stat_penalty':
                expected_revision = _num((body or {}).get('target_character_revision'))
                if expected_revision != (_row_value(target_character, 'revision', 0) or 0):
                    raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
                target_before = copy.deepcopy(target_data)
                stat_effect = instantiate_black_ice_stat_effects(
                    conn, target_character['id'], user['id'], source_program,
                    session['id'], now=now)
                created_effects = stat_effect['created']
                result.update({
                    'effect_application': 'automated',
                    'stat_penalty_roll': stat_effect['penalty_roll'],
                    'stat_penalty_targets': stat_effect['targets'],
                    'created_effects': [{
                        'effect_id': item['effect_id'], 'label': item['label'],
                        'target': (item.get('definition') or {}).get('target'),
                        'value': (item.get('definition') or {}).get('value'),
                        'minimum_value': (item.get('definition') or {}).get(
                            'minimum_value'),
                        'duration_type': item.get('duration_type'),
                    } for item in created_effects],
                    'manual_expiry': True, 'campaign_minutes': 60,
                })
            if result['success'] and effect['resolution'] in (
                    'automated_random_destroy', 'automated_random_derez_plus_manual'):
                target_modifications = character_modifications(conn, target_character['id'])
                target_decks = character_effective_cyberdecks(target_data, target_modifications)
                eligible = [
                    program for deck in target_decks.values()
                    for program in deck.get('programs') or []
                    if (effect['resolution'] == 'automated_random_destroy' or
                        ((program.get('runtime') or {}).get('status') == 'rezzed' and
                         (program.get('runtime') or {}).get('category') == 'defender'))]
                if not eligible:
                    raise ApiError(409, 'Нет допустимых Programs для curated Black ICE effect')
                selection_mode = str((body or {}).get('selection_mode') or 'random').lower()
                if selection_mode == 'random':
                    target_program = eligible[secrets.randbelow(len(eligible))]
                elif selection_mode == 'override':
                    requested_id = str((body or {}).get('target_program_instance_id') or '').lower()
                    target_program = next((program for program in eligible
                                           if program['instance_id'] == requested_id), None)
                    if not target_program:
                        raise ApiError(400, 'Выбранная target Program недопустима')
                else:
                    raise ApiError(400, 'selection_mode: random/override')
                expected_revision = _num((body or {}).get('target_character_revision'))
                if expected_revision != (_row_value(target_character, 'revision', 0) or 0):
                    raise ApiError(409, 'Dossier изменён в другой вкладке; обновите страницу')
                target_program_id = target_program['instance_id']
                target_before = copy.deepcopy(target_data)
                program_item = next(item for item in target_data.get('inventory') or []
                                    if isinstance(item, dict) and
                                    item.get('instance_id') == target_program_id)
                runtime = initial_program_runtime_state(
                    program_item, (target_program.get('runtime') or {}).get('deck_instance_id'),
                    (target_program.get('runtime') or {}).get('modification_id'),
                    (target_data.get('program_state') or {}).get(target_program_id))
                if effect['resolution'] == 'automated_random_destroy':
                    program_modification = next(
                        item for item in target_modifications
                        if item.get('upgrade_instance_id') == target_program_id)
                    backup_modification = next((
                        item for item in target_modifications
                        if item.get('host_instance_id') == program_modification.get('host_instance_id') and
                        (next((owned for owned in target_data.get('inventory') or []
                               if isinstance(owned, dict) and
                               owned.get('instance_id') == item.get('upgrade_instance_id')), {}) or {}).get('name') == 'Backup Drive'), None)
                    if runtime['category'] != 'black_ice' and backup_modification:
                        backup_state = target_data.setdefault('modification_state', {}).setdefault(
                            backup_modification['modification_id'],
                            {'resource_type': 'backup_drive', 'saved_programs': []})
                        backup_state.setdefault('saved_programs', []).append({
                            'program_instance_id': target_program_id,
                            'modification_id': program_modification['modification_id'],
                            'catalog_item_id': catalog_item_id_for_entry(program_item),
                            'name': program_item.get('name'),
                            'runtime_before': copy.deepcopy(runtime), 'saved_at': now,
                        })
                    runtime['status'] = 'destroyed'
                    runtime['rez_current'] = 0
                    if runtime['category'] == 'black_ice':
                        target_ice = next((ice for ice in
                                           (target_data.get('net_entities') or {}).values()
                                           if isinstance(ice, dict) and
                                           ice.get('source_program_instance_id') == target_program_id and
                                           ice.get('status') in ('lying_in_wait', 'hunting', 'derezzed')), None)
                        if target_ice:
                            target_ice['status'] = 'destroyed'
                            target_ice['rez_current'] = 0
                            target_ice['archived_at'] = now
                            target_ice['updated_at'] = now
                            linked_target_ice = next((item for item in state['links']
                                                      if item['net_entity_id'] ==
                                                      target_ice.get('net_entity_id')), None)
                            if linked_target_ice:
                                linked_target_ice['active'] = False
                    program_item['state'] = 'broken'
                    program_item.pop('host_instance_id', None)
                    conn.execute(
                        'UPDATE item_modifications SET active=0,removed_by=?,removed_at=?,updated=? '
                        'WHERE modification_id=?',
                        (user['id'], now, now, program_modification['modification_id']))
                    removed_modification_ids.append(program_modification['modification_id'])
                    result['destroyed'] = True
                else:
                    runtime['status'] = 'derezzed'
                    runtime['rez_current'] = 0
                    result['derezzed'] = True
                target_data.setdefault('program_state', {})[target_program_id] = runtime
                if runtime['status'] in ('derezzed', 'destroyed'):
                    pending = queue_defense_sequencer_trigger(
                        target_data, target_modifications,
                        runtime.get('deck_instance_id'), target_program_id)
                    if pending:
                        result['defense_sequencer_pending'] = pending
                result.update({
                    'selection_mode': selection_mode,
                    'target_program_instance_id': target_program_id,
                    'target_program_name': target_program['name'],
                    'rez_after': runtime['rez_current'],
                })
        summary = (f'{entity.get("name")} attack {attack_total} vs '
                   f'{result.get("defense_total")} → '
                   f'{"hit" if result.get("success") else "miss"}')
        action_entry = {
            'action_id': secrets.token_hex(16), 'combatant_id': target_combatant['id'],
            'actor_entity_id': entity_id, 'action': 'black_ice_attack',
            'target_node_id': link.get('node_id'),
            'target_program_instance_id': target_program_id,
            'success': result.get('success'), 'actor_total': attack_total,
            'defense_total': result.get('defense_total'), 'created': now,
            'summary': summary,
        }
        state.setdefault('action_log', []).append(action_entry)
        state['action_log'] = state['action_log'][-100:]
        queue_count = sum(1 for item in state['links']
                          if item['active'] and (_num(item.get('initiative')) or 0) > 0)
        state['active_turn'] = min(state['active_turn'], max(0, queue_count - 1))
        if target_before is not None:
            validate_active_modification_references(
                conn, target_character['id'], target_data)
            persist_character_item_instances(
                conn, target_character['id'], target_data,
                'black_ice_attack', source_ref=summary, prune=True)
            revision_before = _row_value(target_character, 'revision', 0) or 0
            target_ledger_id = record_character_change_set(
                conn, target_character['id'], user['id'], target_before, target_data,
                f'Live NET {summary}: {reason}', revision_before,
                revision_before + 1,
                category='modification' if removed_modification_ids else 'item_action')
            ledger_row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                                      (target_ledger_id,)).fetchone()
            delta = parse_json_object(ledger_row['delta_json'])
            if removed_modification_ids:
                delta['removed_modification_ids'] = removed_modification_ids
            if created_effects:
                delta['created_effect_ids'] = [
                    item['effect_id'] for item in created_effects]
                delta['automated_black_ice_effect'] = entity.get('name')
                delta['manual_campaign_expiry'] = True
                for created_effect in created_effects:
                    definition = created_effect.get('definition') or {}
                    delta.setdefault('changes', []).append({
                        'path': f'effects.instances.{created_effect["effect_id"]}',
                        'label': f'Effect: {created_effect["label"]}',
                        'kind': 'added', 'before': '—',
                        'after': readable_change_value({
                            'status': created_effect.get('status'),
                            'target': definition.get('target'),
                            'operation': definition.get('operation'),
                            'value': definition.get('value'),
                            'minimum_value': definition.get('minimum_value'),
                            'duration': created_effect.get('duration_type'),
                        }),
                    })
                delta['change_count'] = len(delta.get('changes') or [])
            delta['session_net_change'] = {
                'session_id': session['id'], 'before': state_before,
                'after': copy.deepcopy(state),
            }
            conn.execute('UPDATE character_ledger SET session_id=?,delta_json=? WHERE id=?',
                         (session['id'], json.dumps(delta, ensure_ascii=False),
                          target_ledger_id))
            conn.execute('UPDATE characters SET data=?,updated=?,revision=? WHERE id=?',
                         (json.dumps(target_data, ensure_ascii=False), now,
                          revision_before + 1, target_character['id']))
            result['target_character_revision'] = revision_before + 1
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_action',
             json.dumps(state_before, ensure_ascii=False),
             json.dumps(action_entry, ensure_ascii=False), reason, now))
        conn.commit()
        updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (session['id'],)).fetchone()
        self.send_json({'result': result,
                        'session': self.session_payload(conn, updated, user)})

    @atomic_endpoint
    def api_session_net_state_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права управлять Session NET Queue')
        state = session_net_state(_row_value(session, 'net_state_json', '{}'))
        before = copy.deepcopy(state)
        net_payload = self.session_net_payload(conn, session, player_view=False)
        queue_count = sum(1 for item in net_payload['entities'] if item['in_queue'])
        round_number = _num((body or {}).get('round', state['round']))
        active_turn = _num((body or {}).get('active_turn', state['active_turn']))
        if (round_number is None or int(round_number) != round_number or round_number < 0 or
                active_turn is None or int(active_turn) != active_turn or active_turn < 0):
            raise ApiError(400, 'Некорректный Session NET turn state')
        state['round'] = int(round_number)
        state['active_turn'] = min(int(active_turn), max(0, queue_count - 1))
        note = str((body or {}).get('reason') or '').strip()[:500]
        if len(note) < 3:
            raise ApiError(400, 'Укажите причину изменения NET Queue')
        now = time.time()
        conn.execute('UPDATE nc_sessions SET net_state_json=?,updated=? WHERE id=?',
                     (json.dumps(state, ensure_ascii=False), now, session['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,'
            'after_json,note,created) VALUES(?,?,?,?,?,?,?)',
            (session['id'], user['id'], 'net_turn_update',
             json.dumps(before, ensure_ascii=False), json.dumps(state, ensure_ascii=False),
             note, now))
        conn.commit()
        updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (session['id'],)).fetchone()
        self.send_json(self.session_payload(conn, updated, user))

    def api_sessions(self, conn, qs, m, body):
        user = self.require_user(conn)
        rows = conn.execute('SELECT * FROM nc_sessions ORDER BY updated DESC').fetchall()
        visible = []
        for row in rows:
            role, capabilities = self.session_capabilities(conn, user, row)
            if not role:
                continue
            visible.append(self.session_payload(
                conn, row, user, player_view='view_gm' not in capabilities))
        self.send_json({'sessions': visible})

    @atomic_endpoint
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
        safety = session_safety_config((body or {}).get('safety_config'))
        now = time.time()
        cur = conn.execute(
            'INSERT INTO nc_sessions(contract_id,owner_user_id,title,status,player_view_config,'
            'safety_config,notes,created,updated) VALUES(?,?,?,\'preparing\',?,?,?,?,?)',
            (contract_id, user['id'], title, json.dumps(config), json.dumps(safety),
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
        user = self.require_user(conn)
        row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, row)
        if not row or 'view_gm' not in capabilities:
            raise ApiError(404, 'Сессия не найдена')
        self.send_json(self.session_payload(conn, row, user))

    @atomic_endpoint
    def api_session_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        row = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        role, capabilities = self.session_capabilities(conn, user, row)
        if not row or not capabilities.intersection({'edit_session', 'edit_combatants'}):
            raise ApiError(403, 'Нет права редактировать сессию')
        if 'edit_session' not in capabilities:
            forbidden = set(body or {}) - {'round', 'active_turn', 'status', 'activity_note'}
            if forbidden:
                raise ApiError(403, 'Assistant может менять только ход и раунд')
        status = str((body or {}).get('status', row['status']))
        if status not in ('preparing', 'active', 'paused', 'completed', 'archived'):
            raise ApiError(400, 'Некорректный статус сессии')
        before = {
            'title': row['title'], 'status': row['status'], 'round': row['round'],
            'active_turn': row['active_turn'],
            'player_view_config': session_view_config(row['player_view_config']),
            'safety_config': session_safety_config(row['safety_config']),
            'notes': row['notes'],
        }
        title = str((body or {}).get('title', row['title'])).strip()[:180] or row['title']
        round_number = max(0, _num((body or {}).get('round', row['round'])) or 0)
        combatant_count = conn.execute(
            'SELECT COUNT(*) n FROM session_combatants WHERE session_id=?',
            (row['id'],)).fetchone()['n']
        active_turn = max(0, _num((body or {}).get('active_turn', row['active_turn'])) or 0)
        active_turn = min(active_turn, max(0, combatant_count - 1))
        config = session_view_config(
            (body or {}).get('player_view_config', row['player_view_config']))
        safety = session_safety_config(
            (body or {}).get('safety_config', row['safety_config']))
        notes = str((body or {}).get('notes', row['notes']))[:20000]
        now = time.time()
        after = {
            'title': title, 'status': status, 'round': round_number,
            'active_turn': active_turn, 'player_view_config': config,
            'safety_config': safety, 'notes': notes,
        }
        conn.execute(
            'UPDATE nc_sessions SET title=?,status=?,round=?,active_turn=?,player_view_config=?,'
            'safety_config=?,notes=?,updated=? WHERE id=?',
            (title, status, round_number, active_turn, json.dumps(config), json.dumps(safety),
             notes, now, row['id']))
        conn.execute(
            'INSERT INTO session_activity(session_id,actor_user_id,event_type,before_json,after_json,note,created) '
            'VALUES(?,?,?,?,?,?,?)',
            (row['id'], user['id'], 'session_update', json.dumps(before, ensure_ascii=False),
             json.dumps(after, ensure_ascii=False),
             str((body or {}).get('activity_note') or '')[:500], now))
        conn.commit(); updated = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (row['id'],)).fetchone()
        self.send_json(self.session_payload(conn, updated, user))

    @atomic_endpoint
    def api_session_combatant_create(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
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
        # Snapshot the full statblock (STATs/Skills/Weapons) when adding from a
        # template, or accept an explicit statblock for a custom NPC.
        statblock_source = (body or {}).get('statblock') if not template else source.get('statblock')
        statblock = clean_npc_statblock(statblock_source)
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
            'luck_current,luck_max,move,conditions_json,injuries_json,death_penalty,visible,secret_json,'
            'statblock_json,sort_order) '
            'VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (session['id'], 'npc', template['id'] if template else None, name,
             max(-1000, min(1000, _num(source.get('initiative')) or 0)), current, maximum,
             sp_head, sp_head_max, sp_body, sp_body_max, shield_current, shield_max,
             ammo_current, ammo_max, luck_current, luck_max,
             max(0, _num(source.get('move')) or 0), json.dumps(conditions), json.dumps(injuries),
             max(0, _num(source.get('death_penalty')) or 0),
             0 if source.get('visible') is False else 1,
             json.dumps(secret, ensure_ascii=False),
             json.dumps(statblock, ensure_ascii=False), order))
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

    @atomic_endpoint
    def api_session_combatant_update(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        combatant = conn.execute('SELECT * FROM session_combatants WHERE id=? AND session_id=?',
                                 (int(m.group(2)), int(m.group(1)))).fetchone()
        if (not session or not combatant or
                'edit_combatants' not in self.session_capabilities(conn, user, session)[1]):
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
        if 'statblock' in (body or {}):
            statblock = clean_npc_statblock((body or {}).get('statblock'))
        else:
            statblock = parse_json_object(combatant['statblock_json'])
        conn.execute(
            'UPDATE session_combatants SET name=?,initiative=?,hp_current=?,hp_max=?,sp_head=?,sp_head_max=?,'
            'sp_body=?,sp_body_max=?,shield_current=?,shield_max=?,ammo_current=?,ammo_max=?,luck_current=?,'
            'luck_max=?,move=?,conditions_json=?,injuries_json=?,death_penalty=?,visible=?,secret_json=?,'
            'statblock_json=?,sort_order=? WHERE id=?',
            (name, values['initiative'], values['hp_current'], values['hp_max'],
             values['sp_head'], values['sp_head_max'], values['sp_body'], values['sp_body_max'],
             values['shield_current'], values['shield_max'],
             values['ammo_current'], values['ammo_max'], values['luck_current'], values['luck_max'],
             values['move'], json.dumps(conditions), json.dumps(injuries), values['death_penalty'],
             1 if visible else 0, json.dumps(secret, ensure_ascii=False),
             json.dumps(statblock, ensure_ascii=False),
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

    @atomic_endpoint
    def api_session_combatant_delete(self, conn, qs, m, body):
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?', (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
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
        role, capabilities = self.session_capabilities(conn, user, session)
        if 'view_player' not in capabilities and 'view_gm' not in capabilities:
            raise ApiError(403, 'Нет доступа к экрану сессии')
        self.send_json(self.session_payload(conn, session, user, player_view=True))


    @atomic_endpoint
    def api_session_sync(self, conn, qs, m, body):
        """Write Session combatant resources back to their Dossiers (P-Sync)."""
        user = self.require_user(conn)
        session = conn.execute('SELECT * FROM nc_sessions WHERE id=?',
                               (int(m.group(1)),)).fetchone()
        if not session or 'edit_combatants' not in self.session_capabilities(conn, user, session)[1]:
            raise ApiError(403, 'Нет права синхронизировать сессию')
        combatants = conn.execute(
            'SELECT * FROM session_combatants WHERE session_id=? AND character_id IS NOT NULL',
            (session['id'],)).fetchall()
        synced = []
        for combatant in combatants:
            char = conn.execute('SELECT * FROM characters WHERE id=?',
                                (combatant['character_id'],)).fetchone()
            if not char:
                continue
            before = json.loads(char['data'])
            after = copy.deepcopy(before)
            changed = False
            if combatant['hp_current'] is not None:
                after['hp_cur'] = max(0, combatant['hp_current'])
                changed = True
            if combatant['luck_current'] is not None:
                after['luck_cur'] = max(0, combatant['luck_current'])
                changed = True
            if changed:
                record_character_changes(conn, char['id'], user['id'], before, after,
                                         f'Session sync: {session["title"]}',
                                         session_id=session['id'])
                conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                             (json.dumps(after, ensure_ascii=False), time.time(), char['id']))
                synced.append(char['id'])
        conn.commit()
        self.send_json({'ok': True, 'synced': synced, 'count': len(synced)})

    @atomic_endpoint
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

        crew_ids = {row['character_id'] for row in conn.execute(
            "SELECT character_id FROM contract_signups WHERE contract_id=? AND status='crew'",
            (contract['id'],)).fetchall() if row['character_id']}
        rewards = (body or {}).get('rewards') or []
        if not isinstance(rewards, list) or len(rewards) > 100:
            raise ApiError(400, 'Награды должны быть списком до 100 записей')
        validated_rewards = []
        rewarded_characters = set()
        for reward in rewards:
            if not isinstance(reward, dict):
                raise ApiError(400, 'Некорректная награда')
            character_id = _num(reward.get('character_id'))
            if character_id not in crew_ids:
                raise ApiError(400, 'Награду может получить только персонаж из Crew')
            if character_id in rewarded_characters:
                raise ApiError(400, 'Награда персонажа указана дважды')
            rewarded_characters.add(character_id)
            try:
                cash = float(reward.get('cash') or 0)
                raw_ip = float(reward.get('ip') or 0)
            except (TypeError, ValueError):
                raise ApiError(400, 'Некорректная сумма награды')
            if (not math.isfinite(cash) or not math.isfinite(raw_ip) or
                    cash < 0 or raw_ip < 0 or not raw_ip.is_integer()):
                raise ApiError(400, 'Награды Cash и IP должны быть неотрицательными числами, IP — целым')
            ip = int(raw_ip)
            if cash > 10_000_000 or ip > 1_000_000:
                raise ApiError(400, 'Слишком большая сумма')
            char_row = self.get_char(conn, character_id)
            before = json.loads(char_row['data'])
            data = ensure_progression(copy.deepcopy(before))
            if data.get('archived'):
                raise ApiError(409, 'Архивное досье не может получить награду')
            current_cash = float(data.get('cash') or 0)
            if not math.isfinite(current_cash) or current_cash + cash > 9_999_999:
                raise ApiError(400, 'Слишком большая сумма')
            validated_rewards.append((character_id, cash, ip, before, data))

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
        for character_id, cash, ip, before, data in validated_rewards:
            data['cash'] = float(data.get('cash') or 0) + cash
            if ip:
                ip_before = data['ip_available']; data['ip_available'] += ip
                if ip > 0: data['ip_total_earned'] += ip
                self.add_ip_ledger(conn, character_id, user['id'], ip, ip_before,
                                   data['ip_available'], 'contract', contract['title'], 'Contract Aftermath')
            record_character_changes(conn, character_id, user['id'], before, data,
                                     'Contract Aftermath', contract_id=contract['id'])
            conn.execute('UPDATE characters SET data=?,updated=?,revision=revision+1 WHERE id=?',
                         (json.dumps(data, ensure_ascii=False), now, character_id))
        queue_vk_event(conn, f'contract:{contract["id"]}:{result}', f'contract_{result}',
                       contract['id'], {'contract_id': contract['id'], 'title': contract['title'], 'result': result})
        conn.commit(); self.send_json({'contract_id': contract['id'], 'post_id': post_id, 'result': result})

    # ------------------------------------------------------------ новости

    NEWS_FIELDS = ('id', 'author_id', 'title', 'tag', 'body', 'created')

    def api_calendar_ics(self, conn, qs, m, body):
        user = self.current_user(conn)
        contracts = conn.execute(
            'SELECT id,title,district_id,scheduled_at,crew_capacity FROM contracts '
            "WHERE status IN ('open','crew_full','in_progress') AND scheduled_at IS NOT NULL "
            'ORDER BY scheduled_at').fetchall()
        lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//NC//NET//Cyberpunk RED//EN',
                 'CALSCALE:GREGORIAN', 'X-WR-CALNAME:NC//NET Contracts']
        for c in contracts:
            if not c['scheduled_at']:
                continue
            dt = datetime.fromtimestamp(c['scheduled_at'], tz=MOSCOW)
            dt_end = dt + timedelta(hours=3)
            lines.extend([
                'BEGIN:VEVENT',
                f'UID:contract-{c["id"]}@ncnet',
                f'DTSTAMP:{dt.strftime("%Y%m%dT%H%M%S")}',
                f'DTSTART:{dt.strftime("%Y%m%dT%H%M%S")}',
                f'DTEND:{dt_end.strftime("%Y%m%dT%H%M%S")}',
                f'SUMMARY:{str(c["title"] or "Contract")[:100]}',
                f'DESCRIPTION:NC//NET Contract #{c["id"]}',
                'END:VEVENT',
            ])
        lines.append('END:VCALENDAR')
        ics = '\r\n'.join(lines)
        body_bytes = ics.encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'text/calendar; charset=utf-8')
        self.send_header('Content-Disposition', 'attachment; filename="ncnet-contracts.ics"')
        self.send_header('Content-Length', str(len(body_bytes)))
        self.send_security_headers()
        self.end_headers()
        self.wfile.write(body_bytes)

    def api_news(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute(
            'SELECT n.*,u.display_name author,u.show_display_name author_public FROM news n '
            'JOIN users u ON u.id=n.author_id ORDER BY n.created DESC LIMIT 100').fetchall()
        out = []
        for row in rows:
            item = dict((key, row[key]) for key in self.NEWS_FIELDS)
            item['mine'] = bool(user and row['author_id'] == user['id'])
            item['author'] = row['author'] if (row['author_public'] or item['mine']) else None
            out.append(item)
        self.send_json({'news': out})

    def api_news_create(self, conn, qs, m, body):
        raise ApiError(410, 'Legacy API доступен только для чтения; используйте NC//NET City Feed')

    def api_news_delete(self, conn, qs, m, body):
        raise ApiError(410, 'Legacy API доступен только для чтения; используйте NC//NET City Feed')

    def job_payload(self, r, conn, user):
        n = conn.execute('SELECT COUNT(*) n FROM job_signups WHERE job_id=?',
                         (r['id'],)).fetchone()['n']
        p = {k: r[k] for k in ('id', 'author_id', 'title', 'when_text', 'system',
                               'description', 'slots', 'status', 'created')}
        p['author'] = r['author'] if (r['author_public'] or
                      (user and user['id'] == r['author_id'])) else None
        p['signups'] = n
        p['mine'] = bool(user and user['id'] == r['author_id'])
        p['joined'] = bool(user and conn.execute(
            'SELECT 1 FROM job_signups WHERE job_id=? AND user_id=?',
            (r['id'], user['id'])).fetchone())
        return p

    def api_jobs(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute(
            'SELECT j.*,u.display_name author,u.show_display_name author_public FROM jobs j '
            'JOIN users u ON u.id=j.author_id ORDER BY j.created DESC LIMIT 100').fetchall()
        self.send_json({'jobs': [self.job_payload(r, conn, user) for r in rows]})

    def api_jobs_create(self, conn, qs, m, body):
        raise ApiError(410, 'Legacy API доступен только для чтения; используйте NC//NET Contracts')

    def api_job_detail(self, conn, qs, m, body):
        user = self.current_user(conn)
        r = conn.execute(
            'SELECT j.*,u.display_name author,u.show_display_name author_public FROM jobs j '
            'JOIN users u ON u.id=j.author_id WHERE j.id=?', (int(m.group(1)),)).fetchone()
        if not r:
            raise ApiError(404, 'Заказ не найден')
        p = self.job_payload(r, conn, user)
        signups = conn.execute(
            'SELECT s.*,u.display_name user,u.show_display_name user_public FROM job_signups s '
            'JOIN users u ON u.id=s.user_id WHERE s.job_id=? ORDER BY s.created',
            (r['id'],)).fetchall()
        p['signups_list'] = []
        for signup in signups:
            mine = bool(user and user['id'] == signup['user_id'])
            owner_view = bool(user and user['id'] == r['author_id'])
            p['signups_list'].append({
                'id': signup['id'],
                'user': signup['user'] if (signup['user_public'] or mine or owner_view) else None,
                'user_id': signup['user_id'] if (mine or owner_view) else None,
                'char_name': signup['char_name'], 'note': signup['note'],
                'created': signup['created'], 'mine': mine,
            })
        self.send_json(p)

    def api_job_join(self, conn, qs, m, body):
        raise ApiError(410, 'Legacy API доступен только для чтения; используйте NC//NET Contracts')

    def api_job_leave(self, conn, qs, m, body):
        raise ApiError(410, 'Legacy API доступен только для чтения; используйте NC//NET Contracts')

    def api_job_status(self, conn, qs, m, body):
        raise ApiError(410, 'Legacy API доступен только для чтения; используйте NC//NET Contracts')

    def api_job_delete(self, conn, qs, m, body):
        raise ApiError(410, 'Legacy API доступен только для чтения; используйте NC//NET Contracts')


def rx(p):
    return re.compile('^' + p + '$')


# позднее связывание каталога (обратные зависимости — do выделения домена rules)
_crew_mod.bind(ensure_progression=ensure_progression)
_market_mod.bind(crew_reputation_map=crew_reputation_map)
_db_mod.bind(ensure_progression=ensure_progression)
_charbuild_mod.bind(catalog_item_id_for_entry=catalog_item_id_for_entry,
                   ensure_character_item_instances=ensure_character_item_instances,
                   ensure_progression=ensure_progression)
_engine_mod.bind(catalog_item_id_for_entry=catalog_item_id_for_entry,
                character_tech_maker_modifications=character_tech_maker_modifications,
                weapon_slot_capacity=weapon_slot_capacity)
_rules_mod.bind(catalog_item_id_for_entry=catalog_item_id_for_entry,
              effective_armor_hosts=effective_armor_hosts,
              effective_cyberware_loadout=effective_cyberware_loadout)
_catalog_mod.bind(SKILL_BY_NAME=SKILL_BY_NAME,
                  catalog_item_id_for_entry=catalog_item_id_for_entry)


ROUTES = [
    ('POST', rx(r'/api/register'), Handler.api_register),
    ('POST', rx(r'/api/login'), Handler.api_login),
    ('POST', rx(r'/api/logout'), Handler.api_logout),
    ('GET', rx(r'/api/me'), Handler.api_me),
    ('POST', rx(r'/api/profile'), Handler.api_profile),
    ('GET', rx(r'/api/account/sessions'), Handler.api_account_sessions),
    ('DELETE', rx(r'/api/account/sessions/(\d+)'), Handler.api_account_session_revoke),
    ('POST', rx(r'/api/account/password'), Handler.api_account_password),
    ('POST', rx(r'/api/account/logout-all'), Handler.api_account_logout_all),
    ('GET', rx(r'/api/gm/users'), Handler.api_gm_users),
    ('GET', rx(r'/api/admin/users'), Handler.api_admin_users),
    ('POST', rx(r'/api/admin/users/(\d+)/role'), Handler.api_admin_user_role),
    ('POST', rx(r'/api/admin/users/(\d+)/status'), Handler.api_admin_user_status),
    ('GET', rx(r'/api/admin/invites'), Handler.api_admin_invites),
    ('POST', rx(r'/api/admin/invites'), Handler.api_admin_invite_create),
    ('DELETE', rx(r'/api/admin/invites/(\d+)'), Handler.api_admin_invite_revoke),
    ('GET', rx(r'/api/admin/backups'), Handler.api_admin_backups),
    ('POST', rx(r'/api/admin/backups'), Handler.api_admin_backup_create),
    ('POST', rx(r'/api/admin/backups/([A-Za-z0-9_.-]+)/verify'), Handler.api_admin_backup_verify),
    ('GET', rx(r'/api/admin/backups/([A-Za-z0-9_.-]+)/download'), Handler.api_admin_backup_download),
    ('GET', rx(r'/api/notifications'), Handler.api_notifications),
    ('GET', rx(r'/api/calendar.ics'), Handler.api_calendar_ics),
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
    ('GET', rx(r'/api/personas/(\d+)/memberships'), Handler.api_memberships),
    ('POST', rx(r'/api/personas/(\d+)/memberships'), Handler.api_membership_create),
    ('PUT', rx(r'/api/personas/(\d+)/memberships/(\d+)'), Handler.api_membership_update),
    ('DELETE', rx(r'/api/personas/(\d+)/memberships/(\d+)'), Handler.api_membership_delete),
    ('GET', rx(r'/api/crew-reputation'), Handler.api_crew_reputation),
    ('POST', rx(r'/api/crew-reputation'), Handler.api_crew_reputation_set),
    ('DELETE', rx(r'/api/crew-reputation/(\d+)'), Handler.api_crew_reputation_delete),
    ('GET', rx(r'/api/characters/(\d+)/reputation'), Handler.api_character_reputation),
    ('POST', rx(r'/api/characters/(\d+)/reputation'), Handler.api_character_reputation_set),
    ('DELETE', rx(r'/api/characters/(\d+)/reputation/(\d+)'), Handler.api_character_reputation_delete),
    ('GET', rx(r'/api/storylines'), Handler.api_storylines),
    ('POST', rx(r'/api/storylines'), Handler.api_storyline_create),
    ('GET', rx(r'/api/storylines/(\d+)'), Handler.api_storyline_detail),
    ('PUT', rx(r'/api/storylines/(\d+)'), Handler.api_storyline_update),
    ('POST', rx(r'/api/storylines/(\d+)/timeline'), Handler.api_storyline_timeline_create),
    ('GET', rx(r'/api/contracts'), Handler.api_contracts),
    ('POST', rx(r'/api/contracts'), Handler.api_contract_create),
    ('POST', rx(r'/api/contracts/preview'), Handler.api_contract_preview),
    ('GET', rx(r'/api/contracts/(\d+)'), Handler.api_contract_detail),
    ('PUT', rx(r'/api/contracts/(\d+)'), Handler.api_contract_update),
    ('DELETE', rx(r'/api/contracts/(\d+)'), Handler.api_contract_delete),
    ('POST', rx(r'/api/contracts/(\d+)/join'), Handler.api_contract_join),
    ('POST', rx(r'/api/contracts/(\d+)/leave'), Handler.api_contract_leave),
    ('POST', rx(r'/api/contracts/(\d+)/aftermath'), Handler.api_contract_aftermath),
    ('GET', rx(r'/api/feed'), Handler.api_feed),
    ('POST', rx(r'/api/feed'), Handler.api_feed_create),
    ('POST', rx(r'/api/feed/preview'), Handler.api_feed_preview),
    ('GET', rx(r'/api/feed/(\d+)'), Handler.api_feed_detail),
    ('PUT', rx(r'/api/feed/(\d+)'), Handler.api_feed_update),
    ('POST', rx(r'/api/feed/(\d+)/truth'), Handler.api_feed_truth_update),
    ('POST', rx(r'/api/feed/(\d+)/hide'), Handler.api_feed_hide),
    ('POST', rx(r'/api/feed/(\d+)/comments'), Handler.api_feed_comment_create),
    ('POST', rx(r'/api/feed/(\d+)/comments/(\d+)/hide'), Handler.api_feed_comment_hide),
    ('GET', rx(r'/api/npc-templates'), Handler.api_npc_templates),
    ('POST', rx(r'/api/npc-templates'), Handler.api_npc_template_create),
    ('PUT', rx(r'/api/npc-templates/(\d+)'), Handler.api_npc_template_update),
    ('POST', rx(r'/api/npc-templates/(\d+)/clone'), Handler.api_npc_template_clone),
    ('DELETE', rx(r'/api/npc-templates/(\d+)'), Handler.api_npc_template_delete),
    ('GET', rx(r'/api/recaps'), Handler.api_recaps),
    ('GET', rx(r'/api/locations'), Handler.api_locations),
    ('GET', rx(r'/api/memorial'), Handler.api_memorial_list),
    ('GET', rx(r'/api/memorial/(\d+)'), Handler.api_memorial_detail),
    ('PUT', rx(r'/api/memorial/(\d+)'), Handler.api_memorial_update),
    ('POST', rx(r'/api/memorial/(\d+)/legacy'), Handler.api_memorial_legacy),
    ('PUT', rx(r'/api/memorial/(\d+)/owner-draft'), Handler.api_memorial_owner_draft),
    ('POST', rx(r'/api/memorial/(\d+)/publish'), Handler.api_memorial_publish),
    ('DELETE', rx(r'/api/memorial/(\d+)'), Handler.api_memorial_restore),
    ('POST', rx(r'/api/locations'), Handler.api_location_create),
    ('GET', rx(r'/api/locations/([a-z0-9-]+)'), Handler.api_location_detail),
    ('PUT', rx(r'/api/locations/([a-z0-9-]+)'), Handler.api_location_update),
    ('DELETE', rx(r'/api/locations/([a-z0-9-]+)'), Handler.api_location_delete),
    ('POST', rx(r'/api/recaps'), Handler.api_recap_create),
    ('GET', rx(r'/api/recaps/(\d+)'), Handler.api_recap_detail),
    ('PUT', rx(r'/api/recaps/(\d+)'), Handler.api_recap_update),
    ('DELETE', rx(r'/api/recaps/(\d+)'), Handler.api_recap_delete),
    ('GET', rx(r'/api/sessions'), Handler.api_sessions),
    ('POST', rx(r'/api/sessions'), Handler.api_session_create),
    ('GET', rx(r'/api/sessions/(\d+)'), Handler.api_session_detail),
    ('PUT', rx(r'/api/sessions/(\d+)'), Handler.api_session_update),
    ('GET', rx(r'/api/sessions/(\d+)/player-view'), Handler.api_session_player_view),
    ('POST', rx(r'/api/sessions/(\d+)/net/floors'), Handler.api_session_net_floor_create),
    ('DELETE', rx(r'/api/sessions/(\d+)/net/floors/([a-f0-9]{32})'), Handler.api_session_net_floor_delete),
    ('POST', rx(r'/api/sessions/(\d+)/net/nodes'), Handler.api_session_net_node_create),
    ('PUT', rx(r'/api/sessions/(\d+)/net/nodes/([a-f0-9]{32})'), Handler.api_session_net_node_update),
    ('DELETE', rx(r'/api/sessions/(\d+)/net/nodes/([a-f0-9]{32})'), Handler.api_session_net_node_delete),
    ('POST', rx(r'/api/sessions/(\d+)/net/paths'), Handler.api_session_net_path_create),
    ('PUT', rx(r'/api/sessions/(\d+)/net/paths/([a-f0-9]{32})'), Handler.api_session_net_path_update),
    ('DELETE', rx(r'/api/sessions/(\d+)/net/paths/([a-f0-9]{32})'), Handler.api_session_net_path_delete),
    ('POST', rx(r'/api/sessions/(\d+)/net/actions'), Handler.api_session_net_action),
    ('POST', rx(r'/api/sessions/(\d+)/net/entities/([a-f0-9]{32})/attack'), Handler.api_session_black_ice_attack),
    ('PUT', rx(r'/api/sessions/(\d+)/net/state'), Handler.api_session_net_state_update),
    ('GET', rx(r'/api/sessions/(\d+)/access'), Handler.api_session_access),
    ('POST', rx(r'/api/sessions/(\d+)/access'), Handler.api_session_access_grant),
    ('DELETE', rx(r'/api/sessions/(\d+)/access/(\d+)'), Handler.api_session_access_revoke),
    ('GET', rx(r'/api/sessions/(\d+)/safety'), Handler.api_session_safety),
    ('POST', rx(r'/api/sessions/(\d+)/safety'), Handler.api_session_safety_create),
    ('POST', rx(r'/api/sessions/(\d+)/safety/(\d+)'), Handler.api_session_safety_update),
    ('POST', rx(r'/api/sessions/(\d+)/combatants'), Handler.api_session_combatant_create),
    ('PUT', rx(r'/api/sessions/(\d+)/combatants/(\d+)'), Handler.api_session_combatant_update),
    ('DELETE', rx(r'/api/sessions/(\d+)/combatants/(\d+)'), Handler.api_session_combatant_delete),
    ('POST', rx(r'/api/media'), Handler.api_media_upload),
    ('GET', rx(r'/api/media/([a-f0-9]{32})'), Handler.api_media_get),
    ('DELETE', rx(r'/api/media/([a-f0-9]{32})'), Handler.api_media_delete),
    ('GET', rx(r'/api/meta'), Handler.api_meta),
    ('GET', rx(r'/api/stats'), Handler.api_stats),
    ('GET', rx(r'/api/campaign-clock'), Handler.api_campaign_clock),
    ('POST', rx(r'/api/campaign-clock'), Handler.api_campaign_clock_advance),
    ('GET', rx(r'/api/items'), Handler.api_items),
    ('GET', rx(r'/api/items/([\w-]+)'), Handler.api_item),
    ('GET', rx(r'/api/nightmarket'), Handler.api_nightmarket),
    ('POST', rx(r'/api/nightmarket/reserve'), Handler.api_nightmarket_reserve),
    ('GET', rx(r'/api/fixer-requests'), Handler.api_fixer_requests),
    ('POST', rx(r'/api/fixer-requests'), Handler.api_fixer_request_create),
    ('POST', rx(r'/api/fixer-requests/(\d+)/resolve'), Handler.api_fixer_request_resolve),
    ('GET', rx(r'/api/characters'), Handler.api_my_characters),
    ('POST', rx(r'/api/characters'), Handler.api_create_character),
    ('POST', rx(r'/api/characters/pdf-import'), Handler.api_pdf_import),
    ('POST', rx(r'/api/characters/import'), Handler.api_character_import),
    ('GET', rx(r'/api/characters/(\d+)'), Handler.api_get_character),
    ('PUT', rx(r'/api/characters/(\d+)'), Handler.api_save_character),
    ('PUT', rx(r'/api/characters/(\d+)/sheet'), Handler.api_character_sheet_update),
    ('DELETE', rx(r'/api/characters/(\d+)'), Handler.api_delete_character),
    ('POST', rx(r'/api/characters/(\d+)/memorial'), Handler.api_character_memorialize),
    ('POST', rx(r'/api/characters/(\d+)/ip'), Handler.api_character_ip),
    ('GET', rx(r'/api/characters/(\d+)/ip'), Handler.api_character_ip_history),
    ('GET', rx(r'/api/characters/(\d+)/ledger'), Handler.api_character_ledger),
    ('POST', rx(r'/api/characters/(\d+)/ledger/(\d+)/revert'), Handler.api_character_ledger_revert),
    ('GET', rx(r'/api/characters/(\d+)/items'), Handler.api_character_items),
    ('POST', rx(r'/api/characters/(\d+)/items/([a-f0-9]{32})/action'), Handler.api_character_item_action),
    ('POST', rx(r'/api/characters/(\d+)/items/([a-f0-9]{32})/transfer'), Handler.api_character_item_transfer),
    ('GET', rx(r'/api/characters/(\d+)/personal-stash'), Handler.api_personal_stash),
    ('POST', rx(r'/api/characters/(\d+)/personal-stash'), Handler.api_personal_stash_action),
    ('GET', rx(r'/api/crew-stash'), Handler.api_crew_stash),
    ('POST', rx(r'/api/crew-stash/take'), Handler.api_crew_stash_take),
    ('POST', rx(r'/api/characters/(\d+)/cyberware/([a-f0-9]{32})/action'), Handler.api_character_cyberware_action),
    ('POST', rx(r'/api/characters/(\d+)/therapy/action'), Handler.api_character_therapy_action),
    ('POST', rx(r'/api/characters/(\d+)/cyberware/([a-f0-9]{32})/popup-shield/action'), Handler.api_character_popup_shield_action),
    ('POST', rx(r'/api/characters/(\d+)/armor/([a-f0-9]{32})/repair'), Handler.api_character_armor_repair_action),
    ('POST', rx(r'/api/characters/(\d+)/armor/([a-f0-9]{32})/tech-upgrade'), Handler.api_character_armor_tech_upgrade),
    ('POST', rx(r'/api/characters/(\d+)/tech-maker/modifications'), Handler.api_character_tech_maker_create),
    ('POST', rx(r'/api/characters/(\d+)/tech-maker/modifications/([a-f0-9]{32})/action'), Handler.api_character_tech_maker_action),
    ('POST', rx(r'/api/characters/(\d+)/tech-maker/fabricate'), Handler.api_character_tech_maker_fabricate),
    ('GET', rx(r'/api/downtime/activities'), Handler.api_downtime_activities),
    ('GET', rx(r'/api/characters/(\d+)/downtime'), Handler.api_character_downtime),
    ('POST', rx(r'/api/characters/(\d+)/downtime/start'), Handler.api_character_downtime_start),
    ('POST', rx(r'/api/characters/(\d+)/downtime/action'), Handler.api_character_downtime_action),
    ('POST', rx(r'/api/characters/(\d+)/cyberware/([a-f0-9]{32})/popup-weapon/bind'), Handler.api_character_popup_weapon_bind),
    ('POST', rx(r'/api/characters/(\d+)/cyberware/([a-f0-9]{32})/weapon/action'), Handler.api_character_cyberware_weapon_action),
    ('GET', rx(r'/api/characters/(\d+)/modifications'), Handler.api_character_modifications),
    ('POST', rx(r'/api/characters/(\d+)/modifications'), Handler.api_character_modification_install),
    ('POST', rx(r'/api/characters/(\d+)/modifications/([a-f0-9]{32})/action'), Handler.api_character_modification_action),
    ('POST', rx(r'/api/characters/(\d+)/cyberdecks/([a-f0-9]{32})/black-ice/([a-f0-9]{32})/deploy'), Handler.api_character_black_ice_deploy),
    ('POST', rx(r'/api/characters/(\d+)/net-entities/([a-f0-9]{32})/action'), Handler.api_character_net_entity_action),
    ('POST', rx(r'/api/characters/(\d+)/cyberdecks/([a-f0-9]{32})/programs/([a-f0-9]{32})/action'), Handler.api_character_program_action),
    ('POST', rx(r'/api/characters/(\d+)/cyberdecks/([a-f0-9]{32})/hardware/([a-f0-9]{32})/restore'), Handler.api_character_backup_restore),
    ('POST', rx(r'/api/characters/(\d+)/cyberdecks/([a-f0-9]{32})/hardware/([a-f0-9]{32})/defense-sequencer/resolve'), Handler.api_character_defense_sequencer_resolve),
    ('GET', rx(r'/api/characters/(\d+)/net-contexts'), Handler.api_character_net_contexts),
    ('GET', rx(r'/api/characters/(\d+)/effects'), Handler.api_character_effects),
    ('POST', rx(r'/api/characters/(\d+)/effects'), Handler.api_character_effect_create),
    ('POST', rx(r'/api/characters/(\d+)/effects/([a-f0-9]{32})/action'), Handler.api_character_effect_action),
    ('GET', rx(r'/api/characters/(\d+)/network'), Handler.api_character_network),
    ('POST', rx(r'/api/characters/(\d+)/improve'), Handler.api_character_improve),
    ('POST', rx(r'/api/characters/(\d+)/specialization'), Handler.api_character_specialization),
    ('POST', rx(r'/api/characters/(\d+)/vehicles/([a-f0-9]{32})/repair'), Handler.api_character_vehicle_repair),
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
    ap.add_argument('--host', default='127.0.0.1')
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
