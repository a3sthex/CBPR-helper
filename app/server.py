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
from account_api import AccountMixin                                     # noqa: E402
from feed_api import FeedMixin                                           # noqa: E402
from personas_api import PersonasMixin                                   # noqa: E402
from world_api import WorldMixin                                         # noqa: E402
from sessions_api import SessionsMixin                                   # noqa: E402
from characters_api import CharactersMixin                               # noqa: E402
from admin_api import AdminMixin                                         # noqa: E402
import httpkit as _httpkit_mod                                             # noqa: E402
from httpkit import (                                                     # noqa: E402
    SERVER_ERROR_EN,
    server_error_message,
    theme_contrast,
    validate_theme,
    attach_network_media,
    atomic_endpoint,
    q1,
    rx,
)
import auth as _auth_mod                                                    # noqa: E402
from auth import (                                                           # noqa: E402
    registration_mode,
    invite_code_hash,
    create_invite_code,
    validate_new_password,
    hash_password,
    verify_password,
    session_cookie,
    create_session,
    REGISTRATION_MODES,
)
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
    ensure_progression,
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


class Handler(AdminMixin, CharactersMixin, SessionsMixin, WorldMixin, PersonasMixin, FeedMixin, AccountMixin, MediaHandlers, BaseHTTPRequestHandler):
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

    # ------------------------------------------------------------ NC//NET notifications / VK

    # ------------------------------------------------------------ NC//NET personas

    # ------------------------------------------------------------ NC//NET storylines

    # ------------------------------------------------------------ NC//NET contracts

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

    def require_character_editor(self, conn, cid, allow_gm=False):
        user = self.require_user(conn)
        row = self.get_char(conn, cid)
        if row['owner_id'] != user['id'] and not (allow_gm and user_is_gm(user)):
            raise ApiError(403, 'Нет права изменять этого персонажа')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        return user, row


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

    # ------------------------------------------------------------ Session Recap / Chronicle

    # ------------------------------------------------------------ Map POIs / Key Locations

    # ------------------------------------------------------------ Memorial / Afterlife


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


# позднее связывание каталога (обратные зависимости — do выделения домена rules)
_market_mod.bind(crew_reputation_map=crew_reputation_map)
_charbuild_mod.bind(catalog_item_id_for_entry=catalog_item_id_for_entry,
                   ensure_character_item_instances=ensure_character_item_instances,
)
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
