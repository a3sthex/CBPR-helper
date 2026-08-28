"""Campaign Clock + Downtime Planner: время кампании и простои (итерация P1-9, выделено из app/server.py, логика не менялась)."""
import json
import os
import time
from datetime import datetime

from core import MOSCOW
from core import ApiError
from catalog import catalog



CAMPAIGN_CLOCK_TZ = 'Europe/Moscow'
# Source-defined campaign-time durations for services that complete on the
# Campaign Clock. Manual times remain unbounded until the table confirms them.
CAMPAIGN_DURATION_SECONDS = {
    '1_hour': 3600,
    '3_hours': 3 * 3600,
    '6_hours': 6 * 3600,
    '1_day': 24 * 3600,
    '1_week': 7 * 24 * 3600,
    '2_weeks': 14 * 24 * 3600,
}
CAMPAIGN_DURATION_LABELS = {
    '1_hour': '1 Hour', '3_hours': '3 Hours', '6_hours': '6 Hours',
    '1_day': '1 Day', '1_week': '1 Week', '2_weeks': '2 Weeks',
}


def campaign_timezone():
    return os.environ.get('CBPR_CAMPAIGN_TZ') or CAMPAIGN_CLOCK_TZ


def ensure_campaign_clock(conn):
    """Seed the single campaign clock row if it does not exist yet."""
    row = conn.execute('SELECT * FROM campaign_state WHERE id=1').fetchone()
    if not row:
        conn.execute(
            'INSERT INTO campaign_state(id,campaign_time,timezone,updated) '
            'VALUES(1,?,?,?)',
            (time.time(), campaign_timezone(), time.time()))
    return row or conn.execute('SELECT * FROM campaign_state WHERE id=1').fetchone()


def campaign_now(conn):
    ensure_campaign_clock(conn)
    return float(conn.execute(
        'SELECT campaign_time FROM campaign_state WHERE id=1').fetchone()['campaign_time'])


def campaign_time_label(ts):
    try:
        return datetime.fromtimestamp(float(ts), MOSCOW).strftime('%Y-%m-%d %H:%M')
    except (TypeError, ValueError, OverflowError, OSError):
        return '—'


def campaign_duration_seconds(key):
    return CAMPAIGN_DURATION_SECONDS.get(str(key or ''))


def campaign_clock_payload(conn):
    state = conn.execute('SELECT * FROM campaign_state WHERE id=1').fetchone()
    if not state:
        state = ensure_campaign_clock(conn)
        state = conn.execute('SELECT * FROM campaign_state WHERE id=1').fetchone()
    changes = conn.execute(
        'SELECT a.*,u.display_name actor FROM campaign_clock_audit a '
        'JOIN users u ON u.id=a.actor_user_id ORDER BY a.id DESC LIMIT 30').fetchall()
    return {
        'campaign_time': float(state['campaign_time']),
        'timezone': state['timezone'],
        'label': campaign_time_label(state['campaign_time']),
        'changes': [{
            'delta_seconds': row['delta_seconds'], 'before_time': row['before_time'],
            'after_time': row['after_time'], 'reason': row['reason'],
            'actor': row['actor'], 'created': row['created'],
        } for row in changes],
    }


def campaign_service_status(now, due_at):
    """Return a campaign-clock readiness label for a started service."""
    if due_at is None:
        return {'ready': None, 'label': 'MANUAL TIME', 'due_label': None}
    remaining = float(due_at) - float(now)
    ready = remaining <= 0
    if ready:
        return {'ready': True, 'label': 'DUE', 'due_label': campaign_time_label(due_at)}
    if remaining < 3600:
        minutes = max(1, int(remaining // 60))
        return {'ready': False, 'label': f'{minutes}m', 'due_label': campaign_time_label(due_at)}
    if remaining < 86400:
        hours = int(remaining // 3600)
        return {'ready': False, 'label': f'{hours}h', 'due_label': campaign_time_label(due_at)}
    days = int(remaining // 86400)
    return {'ready': False, 'label': f'{days}d', 'due_label': campaign_time_label(due_at)}


def character_campaign_services(character, conn):
    """Collect this character's active clock-tracked services."""
    now = campaign_now(conn)
    out = []
    data = character if isinstance(character, dict) else json.loads(character.get('data') or '{}')
    therapy = (data.get('therapy_state') or {}).get('active')
    if isinstance(therapy, dict):
        status = campaign_service_status(now, therapy.get('campaign_due_at'))
        out.append({
            'kind': 'therapy', 'label': therapy.get('label') or 'Therapy',
            'started_at': therapy.get('started_at'),
            'campaign_due_at': therapy.get('campaign_due_at'),
            'status': status['label'], 'ready': status['ready'],
            'due_label': status['due_label'],
            'manual_resolution_required': True,
        })
    repair = data.get('armor_repair_state') if isinstance(data.get('armor_repair_state'), dict) else {}
    for instance_id, workflow in repair.items():
        active = workflow.get('active') if isinstance(workflow, dict) else None
        if not isinstance(active, dict):
            continue
        status = campaign_service_status(now, active.get('campaign_due_at'))
        out.append({
            'kind': 'armor_repair', 'label': f'Armor Repair · {active.get("method")}',
            'started_at': active.get('started_at'),
            'campaign_due_at': active.get('campaign_due_at'),
            'status': status['label'], 'ready': status['ready'],
            'due_label': status['due_label'],
            'manual_resolution_required': True,
        })
    vehicle_state = data.get('vehicle_state') if isinstance(data.get('vehicle_state'), dict) else {}
    for instance_id, state in vehicle_state.items():
        active = state.get('repair') if isinstance(state, dict) else None
        if not isinstance(active, dict):
            continue
        status = campaign_service_status(now, active.get('campaign_due_at'))
        out.append({
            'kind': 'vehicle_repair', 'label': f'Vehicle Repair · {active.get("severity")}',
            'started_at': active.get('started_at'),
            'campaign_due_at': active.get('campaign_due_at'),
            'status': status['label'], 'ready': status['ready'],
            'due_label': status['due_label'],
            'manual_resolution_required': True,
        })
    return out


def campaign_pending_services(conn):
    """GM view: every active clock-tracked service across the campaign."""
    now = campaign_now(conn)
    rows = conn.execute(
        'SELECT c.id character_id,c.owner_id,c.data,u.display_name owner_name '
        'FROM characters c JOIN users u ON u.id=c.owner_id '
        'WHERE c.data NOT LIKE \'%"archived": true%\' OR c.data NOT LIKE \'%"archived":true%\'').fetchall()
    pending = []
    for row in rows:
        try:
            data = json.loads(row['data'])
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        if data.get('archived'):
            continue
        services = character_campaign_services(data, conn)
        for service in services:
            pending.append({
                'character_id': row['character_id'],
                'character_name': data.get('handle') or 'Unknown Edgerunner',
                'owner_name': row['owner_name'],
                **service,
            })
    pending.sort(key=lambda item: (item['campaign_due_at'] is None,
                                    item['campaign_due_at'] or 0))
    return pending





# Declarative downtime activity catalog. ``kind`` drives what a resolution may
# automate; ambiguous activities stay MANUAL (GM resolves the roll at the table
# and records only the outcome).
DOWNTIME_ACTIVITIES = [
    {'id': 'hustle', 'kind': 'hustle', 'label_en': 'Hustle',
     'label_ru': 'Подработка (Hustle)',
     'desc_en': 'Roll the Role Hustle table; record the €$ result.',
     'desc_ru': 'Бросок по таблице Hustle роли; запишите результат в €$.'},
    {'id': 'recover_hp', 'kind': 'recover_hp', 'label_en': 'Recover HP',
     'label_ru': 'Восстановление HP',
     'desc_en': 'Rest and healing; record HP recovered.',
     'desc_ru': 'Отдых и лечение; запишите восстановленные HP.'},
    {'id': 'therapy', 'kind': 'therapy', 'label_en': 'Therapy',
     'label_ru': 'Терапия (Humanity)',
     'desc_en': 'Start a Therapy course (Humanity recovery).',
     'desc_ru': 'Начать курс Therapy (восстановление Humanity).'},
    {'id': 'armor_repair', 'kind': 'armor_repair', 'label_en': 'Armor Repair',
     'label_ru': 'Ремонт брони',
     'desc_en': 'Repair damaged Armor/Shield via the Armor workflow.',
     'desc_ru': 'Ремонт повреждённой брони/щита через Armor workflow.'},
    {'id': 'vehicle_repair', 'kind': 'vehicle_repair', 'label_en': 'Vehicle Repair',
     'label_ru': 'Ремонт транспорта',
     'desc_en': 'Repair vehicle durability via the Garage workflow.',
     'desc_ru': 'Ремонт прочности транспорта через Garage workflow.'},
    {'id': 'fabrication', 'kind': 'fabrication', 'label_en': 'Fabrication / Invention',
     'label_ru': 'Fabrication / Invention',
     'desc_en': 'Tech Maker fabrication or invention during downtime.',
     'desc_ru': 'Fabrication или Invention Tech Maker во время downtime.'},
    {'id': 'fixer_search', 'kind': 'fixer_search', 'label_en': 'Fixer Search',
     'label_ru': 'Поиск через Fixer',
     'desc_en': 'Ask a Fixer to source an item.',
     'desc_ru': 'Попросить Fixer достать предмет.'},
    {'id': 'other', 'kind': 'other', 'label_en': 'Other',
     'label_ru': 'Другое',
     'desc_en': 'Any other downtime activity; record the outcome.',
     'desc_ru': 'Любое другое занятие; запишите результат.'},
]
DOWNTIME_ACTIVITY_BY_ID = {item['id']: item for item in DOWNTIME_ACTIVITIES}
DOWNTIME_ACTIVITY_IDS = set(DOWNTIME_ACTIVITY_BY_ID)
# ``hustle`` and ``recover_hp`` apply a bounded numeric result automatically,
# but the roll itself is always resolved manually at the table.
DOWNTIME_RESOLVE_KINDS = {'hustle', 'recover_hp', 'other'}


def clean_downtime_activity(source):
    if not isinstance(source, dict):
        raise ApiError(400, 'Downtime activity должен быть объектом')
    activity_id = str(source.get('id') or '').strip().lower()
    if activity_id not in DOWNTIME_ACTIVITY_IDS:
        raise ApiError(400, 'Неизвестная Downtime activity')
    return {
        'id': activity_id,
        'note': str(source.get('note') or '').strip()[:500],
        'resolved': bool(source.get('resolved')),
        'resolution_note': str(source.get('resolution_note') or '').strip()[:1000],
    }


def clean_downtime_activities(source):
    if source is None:
        return []
    if not isinstance(source, list) or len(source) > 12:
        raise ApiError(400, 'Downtime activities должен быть списком до 12 записей')
    return [clean_downtime_activity(item) for item in source]


def downtime_state(data):
    state = data.get('downtime_state')
    if not isinstance(state, dict):
        state = {'active': None, 'history': []}
        data['downtime_state'] = state
    if not isinstance(state.get('history'), list):
        state['history'] = []
    active = state.get('active') if isinstance(state.get('active'), dict) else None
    if active is not None and not isinstance(active.get('activities'), list):
        active['activities'] = []
    return state


def downtime_activity_payload(activity):
    catalog = DOWNTIME_ACTIVITY_BY_ID.get(activity.get('id')) or {}
    return {
        'id': activity.get('id'),
        'kind': catalog.get('kind'),
        'label_en': catalog.get('label_en'),
        'label_ru': catalog.get('label_ru'),
        'note': activity.get('note') or '',
        'resolved': bool(activity.get('resolved')),
        'resolution_note': activity.get('resolution_note') or '',
    }


def downtime_payload(data, conn=None):
    state = downtime_state(data)
    active = state.get('active') if isinstance(state.get('active'), dict) else None
    now = campaign_now(conn) if conn is not None else time.time()
    active_payload = None
    if active is not None:
        status = campaign_service_status(now, active.get('campaign_due_at'))
        active_payload = {
            'downtime_id': active.get('downtime_id'),
            'started_at': active.get('started_at'),
            'campaign_started_at': active.get('campaign_started_at'),
            'campaign_due_at': active.get('campaign_due_at'),
            'duration_key': active.get('duration_key'),
            'duration_label': active.get('duration_label'),
            'note': active.get('note') or '',
            'created_by': active.get('created_by'),
            'status': status['label'],
            'ready': status['ready'],
            'due_label': status['due_label'],
            'activities': [downtime_activity_payload(item)
                           for item in active.get('activities') or []],
        }
    history = [{
        'downtime_id': item.get('downtime_id'),
        'started_at': item.get('started_at'),
        'campaign_started_at': item.get('campaign_started_at'),
        'campaign_due_at': item.get('campaign_due_at'),
        'duration_key': item.get('duration_key'),
        'duration_label': item.get('duration_label'),
        'note': item.get('note') or '',
        'completed_at': item.get('completed_at'),
        'summary': item.get('summary') or '',
        'activities': [downtime_activity_payload(activity)
                       for activity in item.get('activities') or []],
    } for item in (state.get('history') or [])[-50:][::-1] if isinstance(item, dict)]
    return {'active': active_payload, 'history': history,
            'activities': DOWNTIME_ACTIVITIES}
