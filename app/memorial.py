"""Memorial / Afterlife: пантеон и фьючерсы простоев (итерация P1-9, выделено из app/server.py, логика не менялась)."""
import sqlite3

from core import ApiError
from rules import _num
from db import optional_timestamp



MEMORIAL_STATUSES = {'deceased', 'retired', 'missing'}
MEMORIAL_VISIBILITIES = {'public', 'private'}
MEMBERSHIP_STATUSES = {'active', 'former', 'secret', 'expelled', 'deceased'}
MEMBERSHIP_VISIBILITIES = {'public', 'gm', 'classified'}
REPUTATION_STANDINGS = {'allied', 'friendly', 'neutral', 'hostile', 'hunted'}

def membership_payload(row):
    return {
        'id': row['id'], 'member_persona_id': row['member_persona_id'],
        'organization_persona_id': row['organization_persona_id'],
        'role_title': row['role_title'], 'status': row['status'],
        'visibility': row['visibility'], 'since_at': row['since_at'],
        'until_at': row['until_at'], 'note': row['note'],
        'sort_order': row['sort_order'],
    }

def crew_reputation_map(conn):
    try:
        rows = conn.execute('SELECT * FROM crew_reputation').fetchall()
        return {row['organization_persona_id']: dict(row) for row in rows}
    except sqlite3.OperationalError:
        return {}

def clean_membership_input(body, existing=None):
    base = dict(existing or {})
    get = lambda key, default='': (body or {}).get(key, base.get(key, default))
    status = str(get('status', 'active')).lower()
    if status not in MEMBERSHIP_STATUSES:
        status = 'active'
    visibility = str(get('visibility', 'public')).lower()
    if visibility not in MEMBERSHIP_VISIBILITIES:
        visibility = 'public'
    member = _num(get('member_persona_id') or base.get('member_persona_id'))
    org = _num(get('organization_persona_id') or base.get('organization_persona_id'))
    if not member or not org:
        raise ApiError(400, 'Membership требует member и organization persona')
    since = get('since_at')
    until = get('until_at')
    return {
        'member_persona_id': member, 'organization_persona_id': org,
        'role_title': str(get('role_title') or '')[:120],
        'status': status, 'visibility': visibility,
        'since_at': optional_timestamp(since) if since not in (None, '') else None,
        'until_at': optional_timestamp(until) if until not in (None, '') else None,
        'note': str(get('note') or '')[:2000],
        'sort_order': max(0, min(999, _num(get('sort_order')) or 0)),
    }

def clean_reputation_input(body, existing=None):
    base = dict(existing or {})
    get = lambda key, default=0: (body or {}).get(key, base.get(key, default))
    standing = str(get('standing', 'neutral')).lower()
    if standing not in REPUTATION_STANDINGS:
        standing = 'neutral'
    return {
        'organization_persona_id': _num(get('organization_persona_id')),
        'reputation': max(-100, min(100, _num(get('reputation')) or 0)),
        'favor': max(-100, min(100, _num(get('favor')) or 0)),
        'heat': max(0, min(100, _num(get('heat')) or 0)),
        'standing': standing,
        'note': str(get('note') or '')[:2000],
    }



def clean_memorial_input(body, existing=None):
    base = dict(existing or {})
    get = lambda key, default='': (body or {}).get(key, base.get(key, default))
    status = str(get('status', 'deceased')).lower()
    if status not in MEMORIAL_STATUSES:
        raise ApiError(400, 'Неизвестный статус memorial')
    handle = str(get('handle') or '').strip()[:60]
    if len(handle) < 1:
        raise ApiError(400, 'Memorial требует handle')
    visibility = str(get('visibility') or 'public').lower()
    if visibility not in MEMORIAL_VISIBILITIES:
        visibility = 'public'
    death_date = None
    if get('death_date') not in (None, ''):
        death_date = optional_timestamp(get('death_date'))
    return {
        'status': status,
        'handle': handle,
        'role': str(get('role') or '').strip()[:80],
        'role_rank': max(0, min(10, _num(get('role_rank')) or 0)),
        'death_date': death_date,
        'location': str(get('location') or '').strip()[:240],
        'cause': str(get('cause') or '').strip()[:2000],
        'epitaph': str(get('epitaph') or '').strip()[:1000],
        'last_words': str(get('last_words') or '').strip()[:2000],
        'obituary': str(get('obituary') or '').strip()[:10000],
        'gm_notes': str(get('gm_notes') or '').strip()[:10000],
        'visibility': visibility,
    }


def clean_legacy_input(body):
    if not isinstance(body, dict):
        raise ApiError(400, 'Afterlife Legacy должен быть объектом')
    drink_name = str(body.get('drink_name') or '').strip()[:120]
    if len(drink_name) < 2:
        raise ApiError(400, 'Напиток требует название')
    return {
        'drink_name': drink_name,
        'ingredients': str(body.get('ingredients') or '').strip()[:2000],
        'preparation': str(body.get('preparation') or '').strip()[:4000],
        'glass': str(body.get('glass') or '').strip()[:200],
        'garnish': str(body.get('garnish') or '').strip()[:500],
        'quote': str(body.get('quote') or '').strip()[:2000],
        'legend': str(body.get('legend') or '').strip()[:6000],
    }


def memorial_payload(row, user=None, full=False):
    payload = {
        'id': row['id'], 'character_id': row['character_id'],
        'handle': row['handle'], 'role': row['role'], 'role_rank': row['role_rank'],
        'portrait_media_id': row['portrait_media_id'],
        'status': row['status'],
        'draft_state': row['draft_state'] if 'draft_state' in row.keys() else 'published',
        'death_date': row['death_date'],
        'location': row['location'], 'cause': row['cause'],
        'epitaph': row['epitaph'], 'last_words': row['last_words'],
        'obituary': row['obituary'],
        'visibility': row['visibility'],
        'feed_post_id': row['feed_post_id'],
        'legacy': {
            'drink_name': row['legacy_drink_name'],
            'ingredients': row['legacy_ingredients'],
            'preparation': row['legacy_preparation'],
            'glass': row['legacy_glass'],
            'garnish': row['legacy_garnish'],
            'quote': row['legacy_quote'],
            'legend': row['legacy_legend'],
            'awarded_at': row['legacy_awarded_at'],
        } if row['legacy_drink_name'] else None,
        'created': row['created'], 'updated': row['updated'],
    }
    if full:
        payload['gm_notes'] = row['gm_notes']
        payload['created_by'] = row['created_by']
    return payload
