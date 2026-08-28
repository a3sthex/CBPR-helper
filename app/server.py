#!/usr/bin/env python3
"""CBPR Helper — онлайн-помощник для кампаний по Cyberpunk RED.

Только стандартная библиотека Python. Запуск:
    python3 app/server.py [--port 8000]

Этот модуль — тонкая точка входа (HTTP-диспетчер, ROUTES, main). Домены
вынесены в модули (декомпозиция P1-2026-08, docs/repo-audit-2026-08.md):

    core.py          конфиг, константы, ApiError, роли/права
    auth.py          сессии, PBKDF-хеши, инвайты, регистрация
    db.py            SQLite-схема, миграции, bootstrap, бэкап-глей
    httpkit.py       локализация ошибок, atomic_endpoint, темы, rx
    rules.py         справочники правил RED (роли, навыки, раны…)
    catalog.py       каталог снаряжения + эффекты/взаимодействия
    mod_engine.py    модификации оружия/брони/техники, боеприпасы
    charbuild.py     создание/валидация персонажа, Tech Maker, ensure_progression
    inventory.py     экземпляры предметов, состояния, стеки
    night_market.py  ночной рынок: ротации, постоянный ассортимент, стоки
    recap.py         рекапы, хроника, персоны, уведомления, VK-outbox helpers
    campaign.py      часы кампании + даунтайм-планировщик
    locations.py     точки карты Найт-Сити (POI)
    memorial.py      Memorial / Afterlife
    crew.py          схрон экипажа, займы, репутация
    media.py         загрузка/проверка изображений (MediaHandlers миксин)
    account_api.py   AccountMixin  — аккаунт, вход, профиль, VK OAuth
    feed_api.py      FeedMixin     — NC//NET лента, новости, сюжетки
    personas_api.py  PersonasMixin — персоны, контракты, джобы фиксера
    world_api.py     WorldMixin    — memorial/POI/часы/рекапы/даунтайм/memberships
    sessions_api.py  SessionsMixin — сессии, NET-действия, бой, NPC-шаблоны
    characters_api.py CharactersMixin — листы, инвентарь, Tech Maker, IP
    admin_api.py     AdminMixin    — админ-панель, бэкапы, инвайты
    misc_api.py      MiscMixin     — рынок, роспись, календарь, meta/stats

Handler = ядро Dispatch'а + миксины из *_api модулей.
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
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs, unquote

if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core import (
    BASE,
    CHARACTER_VISIBILITY_DEFAULTS,
    STATS,
    ApiError,
    _row_value,
    can_manage_persona,
    ensure_character_visibility,
    parse_json_object,
    user_account_role,
    user_is_admin,
    user_is_gm,
)
from account_api import AccountMixin                                     # noqa: E402
from feed_api import FeedMixin                                           # noqa: E402
from personas_api import PersonasMixin                                   # noqa: E402
from world_api import WorldMixin                                         # noqa: E402
from sessions_api import SessionsMixin                                   # noqa: E402
from characters_api import CharactersMixin                               # noqa: E402
from admin_api import AdminMixin                                         # noqa: E402
from misc_api import MiscMixin                                           # noqa: E402
import httpkit as _httpkit_mod                                             # noqa: E402
from httpkit import server_error_message, validate_theme, rx
import auth as _auth_mod                                                    # noqa: E402
from auth import hash_password, verify_password, session_cookie, create_session
import db as _db_mod                                                        # noqa: E402
from db import (
    enforce_rate_limit,
    account_login_locked,
    record_failed_login,
    clear_failed_logins,
    cyberdeck_slot_usage,
    cyberdeck_item_compatibility,
    queue_defense_sequencer_trigger,
    resolve_defense_sequencer_trigger,
    initial_program_runtime_state,
    black_ice_effect_profile,
    instantiate_black_ice_stat_effects,
    roll_dice,
    initial_black_ice_entity,
    vehicle_repair_severity,
    vehicle_repair_skill,
    vehicle_upgrade_compatibility,
    apply_schema_migrations,
    apply_admin_bootstrap,
    clean_location_id,
    session_net_state,
    character_interface_rank,
    net_actions_for_interface,
    session_net_path_between,
    clean_npc_statblock,
    npc_statblock_derived,
    SCHEMA,
    CAMPAIGN_CLOCK_SCHEMA,
    MARKET_STOCK_SCHEMA,
    MIGRATION_ITEM_INSTANCES,
    MIGRATION_FEED_SINGLE_FORMAT,
    MIGRATION_ORGANIZATIONS,
    FAILED_LOGIN_LIMIT,
    VEHICLE_REPAIR_RULES,
    NC_LOCATION_IDS,
)
import recap as _recap_mod                                                # noqa: E402
from recap import (
    _clean_recap_text_list,
    clean_session_recap_input,
    recap_public_payload,
    session_recap_payload,
    migrate_legacy_network_content,
    assign_account_role,
    character_change_summary,
    deliver_vk_outbox,
    RECAP_TEXT_LIST_LIMIT,
)
import campaign as _camp_mod                                              # noqa: E402
from campaign import (
    ensure_campaign_clock,
    campaign_now,
    campaign_duration_seconds,
    campaign_service_status,
    character_campaign_services,
    clean_downtime_activity,
    clean_downtime_activities,
    downtime_payload,
    DOWNTIME_ACTIVITIES,
)
import locations as _loc_mod                                              # noqa: E402
from locations import (
    ensure_seed_locations,
    clean_location_input,
    LOCATION_KINDS,
    NC_SEED_LOCATIONS,
)
import memorial as _memorial_mod                                          # noqa: E402
from memorial import (
    crew_reputation_map,
    clean_memorial_input,
    clean_legacy_input,
    memorial_payload,
)
import crew as _crew_mod                                                  # noqa: E402
from crew import (
    crew_stash_payload,
    item_transfer_history,
    character_open_loans,
    _detach_runtime_state,
    _attach_runtime_state,
    _split_stack,
    _prepare_entry_for_holder,
    db,
    init_db,
)
import night_market as _market_mod                                        # noqa: E402
from night_market import (
    NIGHT_MARKET_VENDORS,
    nm_day,
    nm_day_offset,
    nm_stock_seed,
    ensure_market_permanent,
    nm_rotation,
    ensure_market_stock,
    night_market,
)
import inventory as _inventory_mod                                        # noqa: E402
from inventory import (
    catalog_item_id_for_entry,
    ensure_character_item_instances,
    persist_character_item_instances,
    weapon_is_exotic,
    weapon_slot_capacity,
    weapon_upgrade_compatibility,
)
import charbuild as _charbuild_mod                                        # noqa: E402
from charbuild import (
    ensure_progression,
    public_character_data,
    clean_character,
    canonical_import_character,
    skill_base,
    creation_skill_cost,
    effective_armor_hosts,
    tech_maker_fabricable_item,
    tech_maker_host_type,
    character_maker_ranks,
    clean_tech_maker_effect,
    character_tech_maker_modifications,
    validate_tech_maker_references,
    cyberware_weapon_profile,
    popup_weapon_binding_compatibility,
    cyberware_secondary_host_id,
    cyberware_capacity,
    cyberware_installation_profile,
    validate_cyberware_sides,
    validate_cyberware_payload_conflicts,
    effective_cyberware_loadout,
    cyberware_option_compatibility,
    validate_cyberware_requirements,
    validate_cyberware_slots,
    validate_creation,
)
import mod_engine as _engine_mod                                          # noqa: E402
from mod_engine import (
    weapon_modification_configuration_schema,
    clean_weapon_modification_choices,
    weapon_profiles_from_rules,
    ammo_matches_requirement,
    vehicle_modification_configuration_schema,
    clean_vehicle_modification_choices,
    initial_vehicle_modification_state,
    normalize_vehicle_modification_state,
    evaluate_effective_weapon,
    bound_vehicle_weapon_profile,
    evaluate_effective_vehicle,
)
import rules as _rules_mod                                                 # noqa: E402
from rules import (
    apply_modifier_pipeline,
    character_effect_instances,
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
    WOUND_STATES_EN,
    CRIT_BODY_EN,
    CRIT_HEAD_EN,
)
import catalog as _catalog_mod                                           # noqa: E402
from catalog import (
    load_catalog,
    catalog,
    item_by_id,
    validate_effect_definition,
    load_effect_rules,
    item_effect_coverage,
    weapon_modification_rules_for_catalog,
    vehicle_modification_rules_for_catalog,
    weapon_range_table_info,
)
from media import MediaHandlers, image_info

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


class Handler(MiscMixin, AdminMixin, CharactersMixin, SessionsMixin, WorldMixin, PersonasMixin, FeedMixin, AccountMixin, MediaHandlers, BaseHTTPRequestHandler):
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

    # ------------------------------------------------------------ персонажи

    CHAR_LIST_FIELDS = ('id', 'owner_id', 'public', 'created', 'updated')

    def require_character_editor(self, conn, cid, allow_gm=False):
        user = self.require_user(conn)
        row = self.get_char(conn, cid)
        if row['owner_id'] != user['id'] and not (allow_gm and user_is_gm(user)):
            raise ApiError(403, 'Нет права изменять этого персонажа')
        if parse_json_object(row['data']).get('archived'):
            raise ApiError(409, 'Архивное досье доступно только для чтения')
        return user, row


    # ------------------------------------------------------------ рынок

    # ------------------------------------------------------------ NC//NET operations

    # ------------------------------------------------------------ Session Recap / Chronicle

    # ------------------------------------------------------------ Map POIs / Key Locations

    # ------------------------------------------------------------ Memorial / Afterlife


    # ------------------------------------------------------------ новости

    NEWS_FIELDS = ('id', 'author_id', 'title', 'tag', 'body', 'created')


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
    ('POST', rx(r'/api/sessions/(\d+)/sync'), Handler.api_session_sync),
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
