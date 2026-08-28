"""Персоны NC//NET: контракты, джобы фиксера, публичные личности (миксин Handler; P1, логика не менялась)."""


import copy
import json
import math
import sqlite3
import time

from charbuild import ensure_progression
from core import (ApiError, can_edit_contract, can_edit_storyline, can_manage_persona,
                  parse_json_object, user_is_admin, user_is_gm)
from db import (CONTRACT_REWARD_MODES, CONTRACT_RISKS, CONTRACT_STATUSES,
                clean_location_id)
from httpkit import atomic_endpoint, attach_network_media, q1
from memorial import membership_payload
from recap import (add_notification, clean_persona_input,
                   has_contract_classified_access, persona_payload, queue_vk_event,
                   record_character_changes, record_persona_audit)
from rules import _num


class PersonasMixin:

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

    @atomic_endpoint
    def api_contract_delete(self, conn, qs, m, body):
        user = self.require_gm(conn)
        contract = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not contract or not can_edit_contract(conn, user, contract):
            raise ApiError(403, 'Нет права редактировать этот контракт')
        conn.execute("UPDATE contracts SET status='archived',updated=? WHERE id=?",
                     (time.time(), contract['id']))
        conn.commit(); self.send_json({'ok': True})

    def api_contract_detail(self, conn, qs, m, body):
        row = conn.execute('SELECT * FROM contracts WHERE id=?', (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Контракт не найден')
        user = self.current_user(conn)
        if row['status'] in ('draft', 'archived') and not can_edit_contract(conn, user, row):
            raise ApiError(404, 'Контракт не найден')
        self.send_json(self.contract_payload(conn, row, user))

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

    def api_contracts(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute('SELECT * FROM contracts ORDER BY scheduled_at IS NULL,scheduled_at,created DESC').fetchall()
        visible = []
        for row in rows:
            if row['status'] in ('draft', 'archived') and not can_edit_contract(conn, user, row):
                continue
            visible.append(self.contract_payload(conn, row, user))
        self.send_json({'contracts': visible})

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

    def api_job_delete(self, conn, qs, m, body):
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
