"""Общие низкоуровневые хелперы и конфиг путей NC//NET.

Выделены из app/server.py при пилотном разделении монолита (см.
docs/repo-audit-2026-08.md, P1). Импортируется и server.py, и доменными
модулями (media.py). Никакой логики не менялось — только перенос.
"""
import json
import os
import re
from datetime import timedelta, timezone

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, 'data')
UPLOAD_DIR = os.path.join(DATA_DIR, 'uploads')
DB_PATH = os.path.abspath(os.path.expanduser(
    os.environ.get('CBPR_DB_PATH') or os.path.join(DATA_DIR, 'cbpr.db')))
BACKUP_DIR = os.path.abspath(os.path.expanduser(
    os.environ.get('CBPR_BACKUP_DIR') or os.path.join(DATA_DIR, 'backups')))

SESSION_TTL = 30 * 24 * 3600
ITEMS_PATH = os.path.join(DATA_DIR, 'items.json')
EFFECTS_PATH = os.path.join(DATA_DIR, 'effects.json')

STATS = ['INT', 'REF', 'DEX', 'TECH', 'COOL', 'WILL', 'LUCK', 'MOVE', 'BODY', 'EMP']
ACTIVE_EFFECT_DURATIONS = {'manual', 'real_time', 'rounds', 'campaign_time'}
ITEM_INSTANCE_STATES = {
    'carried', 'stored', 'equipped', 'installed', 'consumed', 'broken',
}
INSTANCE_ID_RE = re.compile(r'^[a-f0-9]{32}$')
MOSCOW = timezone(timedelta(hours=3))

ACCOUNT_ROLES = {'player', 'gm', 'admin'}


class ApiError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


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


def parse_json_object(value, default=None):
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or '{}')
        return parsed if isinstance(parsed, dict) else (default or {})
    except (TypeError, ValueError):
        return default or {}


def can_manage_persona(user, persona):
    if not user or not persona or not user_is_gm(user):
        return False
    if user_is_admin(user):
        return True
    access = persona['access']
    return access == 'shared' or (access == 'private' and persona['owner_user_id'] == user['id'])


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


CHARACTER_VISIBILITY_DEFAULTS = {
    'portrait': True,
    'identity': True,
    'biography': True,
    'stats': True,
    'skills': False,
    'lifepath': False,
    'equipment': False,
    'combat': False,
    'player_name': False,
}


def ensure_character_visibility(data):
    raw = data.get('visibility') if isinstance(data, dict) else None
    raw = raw if isinstance(raw, dict) else {}
    visibility = {
        key: raw[key] if isinstance(raw.get(key), bool) else default
        for key, default in CHARACTER_VISIBILITY_DEFAULTS.items()
    }
    data['visibility'] = visibility
    return visibility
