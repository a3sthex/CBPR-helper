"""Лента NC//NET: посты, комментарии, модерация; новости; сюжетные линии (миксин Handler; P1, логика не менялась)."""


import time

from charbuild import character_author_payload
from core import (ApiError, can_edit_contract, can_edit_storyline, can_manage_persona,
                  parse_json_object, user_is_admin, user_is_gm)
from db import (FEED_DEFAULT_FORMAT, FEED_FORMATS, FEED_TRUTH, STORYLINE_STATUSES,
                clean_location_id, optional_timestamp)
from httpkit import attach_network_media
from recap import add_notification, persona_payload, record_feed_revision
from rules import _num


class FeedMixin:

    def api_feed(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute('SELECT * FROM feed_posts ORDER BY published_at DESC,created DESC LIMIT 200').fetchall()
        posts = [self.feed_post_payload(conn, row, user) for row in rows
                 if row['status'] == 'published' or
                 (user and (row['creator_user_id'] == user['id'] or user_is_gm(user)))]
        self.send_json({'posts': posts})

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

    def api_storylines(self, conn, qs, m, body):
        user = self.current_user(conn)
        rows = conn.execute('SELECT * FROM storylines ORDER BY updated DESC').fetchall()
        self.send_json({'storylines': [self.storyline_payload(conn, row, user) for row in rows
                                       if row['status'] != 'archived' or can_edit_storyline(conn, user, row)]})
