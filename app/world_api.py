"""Мир NC//NET: Memorial/Afterlife, точки карты, часы кампании, рекапы сессий, даунтайм, составы экипажей (миксин Handler; P1, логика не менялась)."""


import copy
import json
import math
import re
import secrets
import time

from campaign import (DOWNTIME_ACTIVITIES, campaign_clock_payload, campaign_now,
                      campaign_pending_services, ensure_campaign_clock)
from core import (ApiError, can_edit_contract, can_edit_storyline, user_is_admin,
                  user_is_gm)
from db import optional_timestamp
from httpkit import atomic_endpoint, q1
from locations import LOCATION_KINDS, clean_location_input, location_payload
from memorial import (MEMORIAL_VISIBILITIES, clean_legacy_input,
                      clean_membership_input, clean_memorial_input,
                      membership_payload, memorial_payload)
from recap import (clean_session_recap_input, recap_participants,
                   record_character_changes, session_recap_payload)
from rules import _num


class WorldMixin:

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
    def api_location_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        row = conn.execute('SELECT * FROM locations WHERE id=?', (m.group(1),)).fetchone()
        if not row:
            raise ApiError(404, 'Локация не найдена')
        conn.execute('UPDATE locations SET archived=1,updated=? WHERE id=?',
                     (time.time(), row['id']))
        conn.commit()
        self.send_json({'ok': True, 'archived': True})

    def api_location_detail(self, conn, qs, m, body):
        user = self.current_user(conn)
        row = conn.execute('SELECT * FROM locations WHERE id=?', (m.group(1),)).fetchone()
        if not row:
            raise ApiError(404, 'Локация не найдена')
        if row['archived'] and not user_is_gm(user):
            raise ApiError(404, 'Локация не найдена')
        self.send_json(location_payload(row, user))

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

    def api_downtime_activities(self, conn, qs, m, body):
        self.require_user(conn)
        self.send_json({'activities': DOWNTIME_ACTIVITIES})

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
    def api_membership_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        conn.execute('DELETE FROM persona_memberships WHERE id=?', (int(m.group(2)),))
        conn.commit()
        self.send_json({'ok': True})

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
