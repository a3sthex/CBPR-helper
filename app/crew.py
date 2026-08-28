"""Crew Stash & transfers: общий схрон, займы, репутация экипажа (итерация P1-9, выделено из app/server.py, логика не менялась)."""
import copy
import json
import os
import secrets
import sqlite3
import time

from core import (BACKUP_DIR, DATA_DIR, DB_PATH, UPLOAD_DIR, ApiError,
                  parse_json_object, user_is_gm)
from catalog import catalog, load_effect_rules
from db import SCHEMA, apply_admin_bootstrap, apply_schema_migrations
from inventory import character_modifications, persist_character_item_instances
from mod_engine import ammo_pack_size, ammo_rounds
from night_market import NIGHT_MARKET_VENDORS, ensure_market_permanent
from campaign import ensure_campaign_clock
from locations import ensure_seed_locations
from recap import (ensure_system_persona, migrate_legacy_network_content,
                   record_character_change_set)


_LATE = {}


def bind(**kwargs):
    """Подключить ensure_progression (живёт в server.py до домена progression)."""
    _LATE.update(kwargs)



TRANSFER_KINDS = {'give', 'stash', 'take', 'loan', 'return', 'recall', 'trade', 'split'}


def crew_stash_payload(conn):
    rows = conn.execute(
        'SELECT * FROM crew_stash ORDER BY stored_at,instance_id').fetchall()
    payload = []
    for row in rows:
        item = dict(row)
        item['item'] = parse_json_object(item.pop('data_json'))
        item['item'].pop('_runtime', None)
        item['item'].pop('_tech_maker', None)
        item['transfers'] = item_transfer_history(conn, item['instance_id'])
        payload.append(item)
    return payload


def item_transfer_history(conn, instance_id, limit=50):
    rows = conn.execute(
        'SELECT t.*,u.display_name actor FROM item_transfers t '
        'JOIN users u ON u.id=t.actor_user_id WHERE t.instance_id=? '
        'ORDER BY t.created DESC,t.transfer_id LIMIT ?',
        (str(instance_id), max(1, min(500, int(limit))))).fetchall()
    return [dict(row) for row in rows]


def character_open_loans(conn, character_id):
    rows = conn.execute(
        'SELECT * FROM item_loans WHERE (owner_character_id=? OR borrower_character_id=?) '
        'AND returned_at IS NULL ORDER BY loaned_at,loan_id',
        (int(character_id), int(character_id))).fetchall()
    out = []
    for row in rows:
        item = dict(row)
        instance = conn.execute(
            'SELECT * FROM item_instances WHERE instance_id=?',
            (row['instance_id'],)).fetchone()
        entry = parse_json_object(instance['data_json']) if instance else {}
        item['item_name'] = entry.get('custom_name') or entry.get('name') or 'Item'
        owner = conn.execute(
            'SELECT data FROM characters WHERE id=?',
            (row['owner_character_id'],)).fetchone()
        borrower = conn.execute(
            'SELECT data FROM characters WHERE id=?',
            (row['borrower_character_id'],)).fetchone()
        item['owner_handle'] = (parse_json_object(owner['data']) if owner else {}).get('handle') or '?'
        item['borrower_handle'] = (parse_json_object(borrower['data']) if borrower else {}).get('handle') or '?'
        out.append(item)
    return out


def active_loan_for_instance(conn, instance_id):
    return conn.execute(
        'SELECT * FROM item_loans WHERE instance_id=? AND returned_at IS NULL',
        (str(instance_id),)).fetchone()


def transfer_targets(conn, user):
    """Characters an actor may hand items to: own + public for players, all for GM."""
    if user_is_gm(user):
        rows = conn.execute(
            'SELECT c.id,c.owner_id,c.data,u.display_name owner_name '
            'FROM characters c JOIN users u ON u.id=c.owner_id '
            'ORDER BY u.id,c.id').fetchall()
    else:
        rows = conn.execute(
            'SELECT c.id,c.owner_id,c.data,u.display_name owner_name '
            'FROM characters c JOIN users u ON u.id=c.owner_id '
            'WHERE c.public=1 OR c.owner_id=? ORDER BY u.id,c.id',
            (user['id'],)).fetchall()
    out = []
    for row in rows:
        data = parse_json_object(row['data'])
        out.append({
            'id': row['id'], 'handle': data.get('handle') or 'Unknown Edgerunner',
            'owner_id': row['owner_id'], 'owner_name': row['owner_name'],
            'archived': bool(data.get('archived')), 'role': data.get('role') or '',
        })
    return out


def _inventory_entry(data, instance_id):
    for index, entry in enumerate(data.get('inventory') or []):
        if isinstance(entry, dict) and entry.get('instance_id') == instance_id:
            return index, entry
    return None, None


def _character_item_name(entry):
    return str(entry.get('custom_name') or entry.get('name') or 'Item')


def _transferable_item_error(conn, character_id, entry, data, loan=None, loan_ok=False):
    """Return a translated ApiError when the instance cannot leave the character."""
    if entry.get('state') in ('equipped', 'installed', 'consumed', 'broken'):
        raise ApiError(409, 'Передавать можно только carried предмет (сначала снимите его)')
    armor = data.get('armor') if isinstance(data.get('armor'), dict) else {}
    for location in ('head', 'body', 'shield'):
        piece = armor.get(location)
        if isinstance(piece, dict) and piece.get('instance_id') == entry.get('instance_id'):
            raise ApiError(409, 'Сначала снимите броню из слота')
    modifications = character_modifications(conn, character_id)
    if any(mod.get('host_instance_id') == entry.get('instance_id') for mod in modifications):
        raise ApiError(409, 'Сначала снимите установленные модификации с предмета')
    if not loan_ok and loan is not None and loan['borrower_character_id'] == int(character_id):
        raise ApiError(409, 'Предмет взят в долг — его можно только вернуть владельцу')
    if not loan_ok and loan is not None and loan['owner_character_id'] == int(character_id):
        raise ApiError(409, 'Предмет сейчас в долгу у другого персонажа')


_RUNTIME_STATE_KEYS = ('weapon_state', 'vehicle_state', 'armor_repair_state', 'armor_tech_state')


def _detach_runtime_state(source_data, entry, instance_id):
    """Pull per-instance server-owned runtime containers into the moving entry."""
    packed = {}
    for key in _RUNTIME_STATE_KEYS:
        source_map = source_data.get(key) if isinstance(source_data.get(key), dict) else {}
        if instance_id in source_map:
            packed[key] = source_map.pop(instance_id)
    if packed:
        entry['_runtime'] = packed


def _attach_runtime_state(target_data, entry, instance_id):
    packed = entry.pop('_runtime', None)
    if isinstance(packed, dict):
        for key, value in packed.items():
            if key in _RUNTIME_STATE_KEYS and isinstance(value, dict):
                target_data.setdefault(key, {})[instance_id] = value


def _detach_tech_maker_modifications(source_data, entry, instance_id):
    """Tech Maker work stays on the item; detach its records with the host."""
    source_state = source_data.get('tech_maker_state')
    if not isinstance(source_state, dict):
        return
    mods = source_state.get('modifications') if isinstance(source_state.get('modifications'), dict) else {}
    moved = {mod_id: mod for mod_id, mod in mods.items()
             if isinstance(mod, dict) and mod.get('host_instance_id') == instance_id}
    if not moved:
        return
    for mod_id in moved:
        mods.pop(mod_id)
    source_history = source_state.get('history') if isinstance(source_state.get('history'), list) else []
    keep, history = [], []
    for record in source_history:
        if isinstance(record, dict) and record.get('modification_id') in moved:
            history.append(record)
        else:
            keep.append(record)
    source_state['history'] = keep
    entry['_tech_maker'] = {'modifications': moved, 'history': history}


def _attach_tech_maker_modifications(target_data, entry):
    packed = entry.pop('_tech_maker', None)
    if not isinstance(packed, dict):
        return
    mods = packed.get('modifications') if isinstance(packed.get('modifications'), dict) else {}
    history = packed.get('history') if isinstance(packed.get('history'), list) else []
    if not mods:
        return
    target_state = target_data.setdefault('tech_maker_state', {})
    target_mods = target_state.setdefault('modifications', {})
    target_mods.update(mods)
    target_history = target_state.setdefault('history', [])
    target_history.extend(history)
    target_state['history'] = target_history[-50:]


def _split_stack(entry, take_qty):
    """Return (remaining_entry_or_None, taken_entry) where taken is a fresh copy."""
    full_qty = max(1, int(entry.get('qty') or 1))
    take_qty = max(1, min(full_qty, int(take_qty or 0) or full_qty))
    if take_qty >= full_qty:
        return None, copy.deepcopy(entry)
    remaining = copy.deepcopy(entry)
    taken = copy.deepcopy(entry)
    remaining['qty'] = full_qty - take_qty
    taken['qty'] = take_qty
    if entry.get('cat') == 'ammo':
        pack = ammo_pack_size(entry)
        rounds = ammo_rounds(entry)
        taken['ammo_rounds'] = take_qty * pack
        remaining['ammo_rounds'] = max(0, rounds - take_qty * pack)
    return remaining, taken


def _prepare_entry_for_holder(entry, holder_kind):
    """Normalise an entry before it lands in a stash or another character."""
    cleaned = copy.deepcopy(entry)
    cleaned['qty'] = max(1, int(cleaned.get('qty') or 1))
    cleaned['state'] = 'stored' if holder_kind == 'stash' else 'carried'
    for key in ('equipped_mode', 'equipped_slot', 'active', 'host_instance_id',
                'host_instances', 'mounted_modification_id', 'mounted_vehicle_id'):
        cleaned.pop(key, None)
    return cleaned


def _record_item_transfer(conn, instance_id, kind, actor_user_id, notes,
                          from_character_id=None, to_character_id=None,
                          from_bucket=None, to_bucket=None, quantity=1):
    conn.execute(
        'INSERT INTO item_transfers(transfer_id,instance_id,from_character_id,'
        'to_character_id,from_bucket,to_bucket,quantity,kind,actor_user_id,notes,created) '
        'VALUES(?,?,?,?,?,?,?,?,?,?,?)',
        (secrets.token_hex(16), str(instance_id), from_character_id, to_character_id,
         from_bucket, to_bucket, max(1, int(quantity or 1)), kind,
         int(actor_user_id), str(notes or '')[:500], time.time()))


def _record_transfer_ledger(conn, character_id, actor_user_id, before, after,
                            reason, revision_before, revision_after):
    ledger_id = record_character_change_set(
        conn, character_id, actor_user_id, before, after, reason,
        revision_before, revision_after, category='transfer')
    row = conn.execute('SELECT delta_json FROM character_ledger WHERE id=?',
                       (ledger_id,)).fetchone()
    delta = parse_json_object(row['delta_json'])
    delta['revertible'] = False
    conn.execute('UPDATE character_ledger SET delta_json=? WHERE id=?',
                 (json.dumps(delta, ensure_ascii=False), ledger_id))
    return ledger_id


def _persist_transfer_side(conn, character_id, data, source_type, source_ref):
    _LATE['ensure_progression'](data)
    persist_character_item_instances(
        conn, character_id, data, source_type, source_ref=source_ref, prune=True)


def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA busy_timeout=15000')
    conn.execute('PRAGMA foreign_keys=ON')
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    os.makedirs(BACKUP_DIR, exist_ok=True)
    load_effect_rules()  # fail closed on invalid or non-allowlisted declarative effects
    conn = db()
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA synchronous=NORMAL')
    had_users_table = bool(conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone())
    conn.executescript(SCHEMA)
    apply_schema_migrations(conn, make_backup=had_users_table)
    ensure_campaign_clock(conn)
    ensure_seed_locations(conn)
    ensure_market_permanent(conn)
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
    for vendor in NIGHT_MARKET_VENDORS:
        persona_id = ensure_system_persona(conn, vendor['handle'], vendor['name_en'], 'outlet')
        if persona_id:
            conn.execute(
                'UPDATE personas SET display_name=?,short_bio=?,public_bio=?,accent_color=?,updated=? '
                'WHERE id=?',
                (vendor['name_en'], vendor['tagline_en'],
                 vendor['tagline_en'] + ' Daily stock rotates at 00:00 Europe/Moscow.',
                 vendor['accent_color'], time.time(), persona_id))
    migrate_legacy_network_content(conn)
    conn.close()
