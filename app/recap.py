"""Session Recap / Chronicle: рекапы, хроника, лента событий (итерация P1-9, выделено из app/server.py, логика не менялась)."""
import json
import math
import os
import re
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError


from core import (ACCOUNT_ROLES, MOSCOW, ApiError, _row_value, can_edit_contract,
                  parse_json_object, user_account_role, user_is_admin)
from rules import _num, derive
from db import PERSONA_ACCESS, PERSONA_KINDS, PERSONA_STATUSES, parse_json_list
from charbuild import cyberware_host_assignments



RECAP_TEXT_LIST_LIMIT = 50


def _clean_recap_text_list(source):
    if source is None:
        return []
    if not isinstance(source, list):
        raise ApiError(400, 'Recap списки должны быть массивами')
    return [str(value).strip()[:300] for value in source[:RECAP_TEXT_LIST_LIMIT]
            if str(value).strip()]


def _clean_recap_participants(source):
    if source is None:
        return []
    if not isinstance(source, list):
        raise ApiError(400, 'Recap participants должен быть списком')
    out = []
    for value in source[:RECAP_TEXT_LIST_LIMIT]:
        if isinstance(value, dict):
            kind = str(value.get('kind') or 'character')[:40]
            name = str(value.get('name') or '').strip()[:120]
            if name:
                out.append({'kind': kind, 'name': name})
        elif str(value).strip():
            out.append({'kind': 'character', 'name': str(value).strip()[:120]})
    return out


def clean_session_recap_input(body):
    if not isinstance(body, dict):
        raise ApiError(400, 'Recap должен быть объектом')
    title = str(body.get('title') or '').strip()[:240]
    if len(title) < 2:
        raise ApiError(400, 'Recap требует название')
    try:
        session_date = float(body.get('session_date') or time.time())
    except (TypeError, ValueError):
        raise ApiError(400, 'Некорректная дата Recap')
    if not math.isfinite(session_date):
        session_date = time.time()
    return {
        'title': title,
        'session_date': session_date,
        'session_id': _num(body.get('session_id')),
        'contract_id': _num(body.get('contract_id')),
        'storyline_id': _num(body.get('storyline_id')),
        'public_summary': str(body.get('public_summary') or '')[:10000],
        'gm_notes': str(body.get('gm_notes') or '')[:20000],
        'participants': _clean_recap_participants(body.get('participants')),
        'choices': _clean_recap_text_list(body.get('choices')),
        'npc_changes': _clean_recap_text_list(body.get('npc_changes')),
        'locations': _clean_recap_text_list(body.get('locations')),
        'loot': _clean_recap_text_list(body.get('loot')),
        'injuries': _clean_recap_text_list(body.get('injuries')),
        'quotes': _clean_recap_text_list(body.get('quotes')),
        'published': bool(body.get('published')),
        'publish_feed': bool(body.get('publish_feed')),
    }


def recap_participants(conn, session_id=None, contract_id=None):
    """Auto-collect participant names from a session or contract."""
    participants = []
    seen = set()
    if session_id:
        rows = conn.execute(
            'SELECT sc.*,c.data character_data FROM session_combatants sc '
            'LEFT JOIN characters c ON c.id=sc.character_id '
            'WHERE sc.session_id=? ORDER BY sc.sort_order,sc.id', (session_id,)).fetchall()
        for row in rows:
            if row['character_id']:
                character = parse_json_object(row['character_data']) if row['character_data'] else {}
                name = character.get('handle') or row['name']
                kind = 'character'
            else:
                name = row['name']
                kind = 'npc'
            key = (kind, name)
            if key not in seen:
                seen.add(key)
                participants.append({'kind': kind, 'name': name})
    if not participants and contract_id:
        rows = conn.execute(
            "SELECT c.data character_data FROM contract_signups s "
            "JOIN characters c ON c.id=s.character_id WHERE s.contract_id=? AND s.status='crew' "
            'ORDER BY s.queue_position,s.joined_at', (contract_id,)).fetchall()
        for row in rows:
            character = parse_json_object(row['character_data']) if row['character_data'] else {}
            name = character.get('handle')
            if name and ('character', name) not in seen:
                seen.add(('character', name))
                participants.append({'kind': 'character', 'name': name})
    return participants


def recap_public_payload(row):
    """Public chronicle view: only shareable fields."""
    return {
        'id': row['id'], 'session_date': row['session_date'], 'title': row['title'],
        'public_summary': row['public_summary'],
        'participants': parse_json_list(row['participants_json']),
        'locations': parse_json_list(row['locations_json']),
        'session_id': row['session_id'], 'contract_id': row['contract_id'],
        'storyline_id': row['storyline_id'], 'published': bool(row['published']),
        'created': row['created'], 'updated': row['updated'],
    }


def session_recap_payload(row, full=False):
    payload = recap_public_payload(row)
    if full:
        payload.update({
            'owner_user_id': row['owner_user_id'],
            'gm_notes': row['gm_notes'],
            'choices': parse_json_list(row['choices_json']),
            'npc_changes': parse_json_list(row['npc_changes_json']),
            'loot': parse_json_list(row['loot_json']),
            'injuries': parse_json_list(row['injuries_json']),
            'quotes': parse_json_list(row['quotes_json']),
            'feed_post_id': row['feed_post_id'],
            'timeline_id': row['timeline_id'],
        })
    return payload


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
    if before == 'admin' and role != 'admin' and not _row_value(target, 'disabled_at'):
        admins = conn.execute(
            "SELECT COUNT(*) n FROM users WHERE account_role='admin' AND disabled_at IS NULL"
        ).fetchone()['n']
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
        'avatar_media_id': str(get('avatar_media_id') or '')[:64] or None,
        'cover_media_id': str(get('cover_media_id') or '')[:64] or None,
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
        'vehicle_state': 'vehicle',
        'archived': 'status', 'public': 'status', 'visibility': 'status',
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


CHARACTER_DIFF_SCALARS = (
    ('handle', 'Handle'), ('first_name', 'First name'), ('last_name', 'Last name'),
    ('player', 'Player'), ('role', 'Primary Role'), ('role_rank', 'Role Rank'),
    ('cash', 'Cash'), ('ip_available', 'Available IP'), ('reputation', 'Reputation'),
    ('hp_cur', 'Current HP'), ('humanity_cur', 'Current Humanity'),
    ('luck_cur', 'Current LUCK'), ('lifestyle', 'Lifestyle'), ('housing', 'Housing'),
    ('appearance', 'Appearance'), ('background', 'Background'),
    ('languages', 'Languages'), ('notes', 'Notes'), ('public', 'Public Dossier'),
)


def readable_change_value(value):
    if value is None or value == '':
        return '—'
    if isinstance(value, bool):
        return 'Yes' if value else 'No'
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 160 else value[:157] + '…'
    return json.dumps(value, ensure_ascii=False)[:240]


def character_change_summary(before, after, limit=250):
    """Build compact, human-readable changes while full snapshots stay server-side."""
    changes = []

    def add(path, label, old, new, kind='changed'):
        if old == new or len(changes) >= limit:
            return
        changes.append({
            'path': path, 'label': label, 'kind': kind,
            'before': readable_change_value(old), 'after': readable_change_value(new),
        })

    for key, label in CHARACTER_DIFF_SCALARS:
        add(key, label, before.get(key), after.get(key))
    for group, label in (('stats', 'STAT'), ('skills', 'Skill'),
                         ('skill_pools', 'Skill Pool')):
        old_values = before.get(group) if isinstance(before.get(group), dict) else {}
        new_values = after.get(group) if isinstance(after.get(group), dict) else {}
        for key in sorted(set(old_values) | set(new_values)):
            add(f'{group}.{key}', f'{label}: {key}', old_values.get(key), new_values.get(key))

    def item_map(data, bucket):
        result = {}
        for index, item in enumerate(data.get(bucket) or []):
            if not isinstance(item, dict):
                continue
            identity = str(item.get('instance_id') or f'{item.get("key") or item.get("name")}:{index}')
            result[identity] = item
        return result

    for bucket, label in (('inventory', 'Inventory'), ('cyberware', 'Cyberware')):
        old_items, new_items = item_map(before, bucket), item_map(after, bucket)
        for identity in sorted(set(old_items) | set(new_items)):
            old, new = old_items.get(identity), new_items.get(identity)
            if old is None:
                name = new.get('custom_name') or new.get('name') or 'Item'
                add(f'{bucket}.{identity}', f'{label}: {name}', '—',
                    f'added ×{new.get("qty") or 1}', 'added')
            elif new is None:
                name = old.get('custom_name') or old.get('name') or 'Item'
                add(f'{bucket}.{identity}', f'{label}: {name}',
                    f'owned ×{old.get("qty") or 1}', 'removed', 'removed')
            else:
                old_view = {
                    'name': old.get('custom_name') or old.get('name'),
                    'qty': old.get('qty') or 1, 'state': old.get('state') or 'carried',
                    'mode': old.get('equipped_mode'), 'active': old.get('active'),
                    'category': old.get('cat'), 'value': old.get('price'),
                    'source': old.get('acquisition_source'),
                    'hosts': cyberware_host_assignments(old)
                        if bucket == 'cyberware' else None,
                    'side': old.get('installation_side') if bucket == 'cyberware' else None,
                    'description': old.get('desc') if old.get('is_custom') else None,
                }
                new_view = {
                    'name': new.get('custom_name') or new.get('name'),
                    'qty': new.get('qty') or 1, 'state': new.get('state') or 'carried',
                    'mode': new.get('equipped_mode'), 'active': new.get('active'),
                    'category': new.get('cat'), 'value': new.get('price'),
                    'source': new.get('acquisition_source'),
                    'hosts': cyberware_host_assignments(new)
                        if bucket == 'cyberware' else None,
                    'side': new.get('installation_side') if bucket == 'cyberware' else None,
                    'description': new.get('desc') if new.get('is_custom') else None,
                }
                add(f'{bucket}.{identity}', f'{label}: {new_view["name"]}',
                    old_view, new_view)

    old_armor = before.get('armor') if isinstance(before.get('armor'), dict) else {}
    new_armor = after.get('armor') if isinstance(after.get('armor'), dict) else {}
    for location in ('head', 'body', 'shield'):
        old_piece, new_piece = old_armor.get(location), new_armor.get(location)
        old_view = (old_piece or {}).get('name') if isinstance(old_piece, dict) else None
        new_view = (new_piece or {}).get('name') if isinstance(new_piece, dict) else None
        add(f'armor.{location}', f'Armor: {location}', old_view, new_view)
    old_mod_state = before.get('modification_state') if isinstance(before.get('modification_state'), dict) else {}
    new_mod_state = after.get('modification_state') if isinstance(after.get('modification_state'), dict) else {}
    for modification_id in sorted(set(old_mod_state) | set(new_mod_state)):
        add(f'modification_state.{modification_id}', 'Modification resource state',
            old_mod_state.get(modification_id), new_mod_state.get(modification_id))
    old_program_state = before.get('program_state') if isinstance(before.get('program_state'), dict) else {}
    new_program_state = after.get('program_state') if isinstance(after.get('program_state'), dict) else {}
    for program_id in sorted(set(old_program_state) | set(new_program_state)):
        add(f'program_state.{program_id}', 'Program runtime state',
            old_program_state.get(program_id), new_program_state.get(program_id))
    old_net_entities = before.get('net_entities') if isinstance(before.get('net_entities'), dict) else {}
    new_net_entities = after.get('net_entities') if isinstance(after.get('net_entities'), dict) else {}
    for entity_id in sorted(set(old_net_entities) | set(new_net_entities)):
        add(f'net_entities.{entity_id}', 'Black ICE NET entity',
            old_net_entities.get(entity_id), new_net_entities.get(entity_id))
    old_vehicle_state = before.get('vehicle_state') if isinstance(before.get('vehicle_state'), dict) else {}
    new_vehicle_state = after.get('vehicle_state') if isinstance(after.get('vehicle_state'), dict) else {}
    for vehicle_id in sorted(set(old_vehicle_state) | set(new_vehicle_state)):
        add(f'vehicle_state.{vehicle_id}', 'Vehicle SDP',
            old_vehicle_state.get(vehicle_id), new_vehicle_state.get(vehicle_id))

    def synergy_views(data):
        result = {}
        for rule in derive(data).get('effects', {}).get('synergies', []):
            progress = ', '.join(
                f"{item['label']} {item['current']}/{item['required']}"
                for item in rule.get('requirements') or [])
            result[rule['id']] = {
                'label': rule.get('label_en') or rule['id'],
                'status': 'ACTIVE' if rule.get('active') else 'INACTIVE',
                'progress': progress,
            }
        return result

    old_synergies, new_synergies = synergy_views(before), synergy_views(after)
    for rule_id in sorted(set(old_synergies) | set(new_synergies)):
        old_view, new_view = old_synergies.get(rule_id), new_synergies.get(rule_id)
        add(f'effects.synergy.{rule_id}',
            f'Effect: {(new_view or old_view or {}).get("label", rule_id)}',
            old_view, new_view)

    def item_effect_views(data):
        result = {}
        for source in derive(data).get('effects', {}).get('item_sources', []):
            result[source['id']] = {
                'label': source.get('label_en') or source['id'],
                'status': 'ACTIVE' if source.get('active') else 'INACTIVE',
                'matching_instances': len(source.get('matching_instance_ids') or []),
                'active_instances': len(source.get('active_instance_ids') or []),
            }
        return result

    old_sources, new_sources = item_effect_views(before), item_effect_views(after)
    for rule_id in sorted(set(old_sources) | set(new_sources)):
        old_view, new_view = old_sources.get(rule_id), new_sources.get(rule_id)
        add(f'effects.item_source.{rule_id}',
            f'Effect: {(new_view or old_view or {}).get("label", rule_id)}',
            old_view, new_view)
    return changes


def record_character_change_set(conn, character_id, actor_user_id, before, after,
                                reason, revision_before, revision_after,
                                category='sheet_update', reverts_ledger_id=None):
    changes = character_change_summary(before, after)
    delta = {
        'changes': changes,
        'change_count': len(changes),
        'revision_before': int(revision_before),
        'revision_after': int(revision_after),
        'revertible': True,
    }
    if reverts_ledger_id is not None:
        delta['reverts_ledger_id'] = int(reverts_ledger_id)
    cursor = conn.execute(
        'INSERT INTO character_ledger(character_id,actor_user_id,category,delta_json,'
        'before_json,after_json,reason,created) VALUES(?,?,?,?,?,?,?,?)',
        (character_id, actor_user_id, category, json.dumps(delta, ensure_ascii=False),
         json.dumps(before, ensure_ascii=False), json.dumps(after, ensure_ascii=False),
         str(reason or '')[:500], time.time()))
    return cursor.lastrowid


def record_effect_change(conn, character_id, actor_user_id, effect_id, label,
                         before, after, reason, revision_before, revision_after):
    def summary(value):
        if not value:
            return '—'
        definition = value.get('definition') or {}
        return {
            'status': value.get('status') or ('active' if value.get('active') else 'disabled'),
            'target': definition.get('target'),
            'operation': definition.get('operation'),
            'value': definition.get('value'),
            'duration': value.get('duration_type'),
            'remaining_rounds': value.get('remaining_rounds'),
        }

    delta = {
        'changes': [{
            'path': f'effects.instances.{effect_id}', 'label': f'Effect: {label}',
            'kind': 'changed', 'before': readable_change_value(summary(before)),
            'after': readable_change_value(summary(after)),
        }],
        'change_count': 1,
        'revision_before': int(revision_before),
        'revision_after': int(revision_after),
        'revertible': False,
    }
    conn.execute(
        'INSERT INTO character_ledger(character_id,actor_user_id,category,delta_json,'
        'before_json,after_json,reason,created) VALUES(?,?,?,?,?,?,?,?)',
        (character_id, actor_user_id, 'effect', json.dumps(delta, ensure_ascii=False),
         json.dumps(before, ensure_ascii=False) if before else None,
         json.dumps(after, ensure_ascii=False) if after else None,
         str(reason or '')[:500], time.time()))


def record_account_security(conn, user_id, actor_user_id, event_type, detail=''):
    conn.execute(
        'INSERT INTO account_security_audit(user_id,actor_user_id,event_type,detail,created) '
        'VALUES(?,?,?,?,?)',
        (user_id, actor_user_id, str(event_type)[:80], str(detail or '')[:500], time.time()))


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
