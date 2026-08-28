"""Аккаунты и вход NC//NET: регистрация, сессии, пароли, профиль, VK OAuth, уведомления (миксин Handler; P1, логика не менялась)."""


import hmac
import json
import os
import re
import secrets
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from auth import (create_session, hash_password, invite_code_hash, registration_mode,
                  session_cookie, validate_new_password, verify_password)
from core import ApiError, _row_value, user_account_role
from db import account_login_locked, clear_failed_logins, record_failed_login
from httpkit import attach_network_media, q1, validate_theme
from recap import record_account_security


class AccountMixin:

    def api_register(self, conn, qs, m, body):
        self.rate_limit('register', 5, 300)
        mode = registration_mode()
        if mode == 'closed':
            raise ApiError(403, 'Регистрация новых аккаунтов отключена')
        username = str(body.get('username') or '').strip().lower()
        password = str(body.get('password') or '')
        display = str(body.get('display_name') or '').strip()[:60] or username
        if not re.fullmatch(r'[a-z0-9_.\-]{3,24}', username):
            raise ApiError(400, 'Логин: 3–24 символа, латиница/цифры/._-')
        validate_new_password(password)
        invite = None
        try:
            conn.execute('BEGIN IMMEDIATE')
            if mode == 'invite':
                code_hash = invite_code_hash((body or {}).get('invite_code'))
                now = time.time()
                invite = conn.execute(
                    'SELECT * FROM registration_invites WHERE code_hash=? AND disabled_at IS NULL '
                    'AND (expires_at IS NULL OR expires_at>?) AND uses<max_uses',
                    (code_hash, now)).fetchone()
                if not invite:
                    raise ApiError(403, 'Приглашение недействительно или уже использовано')
            cur = conn.execute(
                'INSERT INTO users(username, display_name, pass_hash, is_gm, account_role, created) '
                "VALUES(?,?,?,0,'player',?)",
                (username, display, hash_password(password), time.time()))
            if invite:
                conn.execute('UPDATE registration_invites SET uses=uses+1 WHERE id=?',
                             (invite['id'],))
            conn.commit()
        except ApiError:
            conn.rollback()
            raise
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ApiError(409, 'Такой логин уже занят')
        token = create_session(
            conn, cur.lastrowid, self.client_ip(),
            getattr(self, 'headers', {}).get('User-Agent', ''))
        u = conn.execute('SELECT * FROM users WHERE id=?', (cur.lastrowid,)).fetchone()
        self.send_json(self.me_payload(u), cookies=[session_cookie(token)])

    def api_login(self, conn, qs, m, body):
        self.rate_limit('login', 12, 60)
        username = str(body.get('username') or '').strip().lower()
        if account_login_locked(username):
            raise ApiError(429, 'Слишком много неудачных входов; попробуйте позже')
        password = str(body.get('password') or '')
        u = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        if not u or not verify_password(password, u['pass_hash']):
            record_failed_login(username)
            raise ApiError(401, 'Неверный логин или пароль')
        if _row_value(u, 'disabled_at'):
            raise ApiError(403, 'Аккаунт отключён администратором')
        clear_failed_logins(username)
        token = create_session(
            conn, u['id'], self.client_ip(),
            getattr(self, 'headers', {}).get('User-Agent', ''))
        self.send_json(self.me_payload(u), cookies=[session_cookie(token)])

    def api_logout(self, conn, qs, m, body):
        tok = self.cookies().get('sid')
        if tok:
            conn.execute('DELETE FROM sessions WHERE token=?', (tok,))
            conn.commit()
        self.send_json({'ok': True}, cookies=[session_cookie('', 0)])

    def api_account_logout_all(self, conn, qs, m, body):
        user = self.require_user(conn)
        record_account_security(conn, user['id'], user['id'], 'logout_all',
                                'All sessions revoked')
        conn.execute('DELETE FROM sessions WHERE user_id=?', (user['id'],))
        conn.commit()
        self.send_json({'ok': True}, cookies=[session_cookie('', 0)])

    def api_account_password(self, conn, qs, m, body):
        user = self.require_user(conn)
        current_password = str((body or {}).get('current_password') or '')
        new_password = str((body or {}).get('new_password') or '')
        if not verify_password(current_password, user['pass_hash']):
            raise ApiError(403, 'Текущий пароль указан неверно')
        validate_new_password(new_password)
        if verify_password(new_password, user['pass_hash']):
            raise ApiError(400, 'Новый пароль должен отличаться от текущего')
        token = self.cookies().get('sid') or ''
        conn.execute('UPDATE users SET pass_hash=? WHERE id=?',
                     (hash_password(new_password), user['id']))
        conn.execute('DELETE FROM sessions WHERE user_id=? AND token!=?',
                     (user['id'], token))
        record_account_security(conn, user['id'], user['id'], 'password_changed',
                                'Other sessions revoked')
        conn.commit()
        self.send_json({'ok': True})

    def api_account_session_revoke(self, conn, qs, m, body):
        user = self.require_user(conn)
        session_id = int(m.group(1))
        row = conn.execute(
            'SELECT rowid session_id,* FROM sessions WHERE rowid=? AND user_id=?',
            (session_id, user['id'])).fetchone()
        if not row:
            raise ApiError(404, 'Сессия входа не найдена')
        if hmac.compare_digest(row['token'], self.cookies().get('sid') or ''):
            raise ApiError(409, 'Текущую сессию завершайте обычным выходом')
        conn.execute('DELETE FROM sessions WHERE rowid=? AND user_id=?',
                     (session_id, user['id']))
        record_account_security(conn, user['id'], user['id'], 'session_revoked',
                                f'session:{session_id}')
        conn.commit()
        self.send_json({'ok': True})

    def api_account_sessions(self, conn, qs, m, body):
        user = self.require_user(conn)
        token = self.cookies().get('sid')
        rows = conn.execute(
            'SELECT rowid session_id,token,created,expires,last_seen,ip_address,user_agent '
            'FROM sessions WHERE user_id=? AND expires>? ORDER BY last_seen DESC,created DESC',
            (user['id'], time.time())).fetchall()
        self.send_json({'sessions': [{
            'id': row['session_id'], 'created': row['created'], 'expires': row['expires'],
            'last_seen': row['last_seen'] or row['created'],
            'ip_address': row['ip_address'] or '',
            'user_agent': row['user_agent'] or '',
            'current': hmac.compare_digest(row['token'], token or ''),
        } for row in rows]})

    def api_me(self, conn, qs, m, body):
        u = self.current_user(conn)
        self.send_json({'user': self.me_payload(u) if u else None})

    def me_payload(self, u):
        try:
            theme = json.loads(_row_value(u, 'theme_json', '{}') or '{}')
        except (TypeError, ValueError):
            theme = {}
        try:
            notification_prefs = json.loads(_row_value(u, 'notification_prefs', '{}') or '{}')
        except (TypeError, ValueError):
            notification_prefs = {}
        role = user_account_role(u)
        return {
            'id': u['id'], 'username': u['username'], 'display_name': u['display_name'],
            'account_role': role, 'is_gm': role in ('gm', 'admin'),
            'is_admin': role == 'admin',
            'show_display_name': bool(_row_value(u, 'show_display_name', 0)),
            'avatar_media_id': _row_value(u, 'avatar_media_id'),
            'vk_linked': bool(_row_value(u, 'vk_user_id')),
            'disabled': bool(_row_value(u, 'disabled_at')),
            'disabled_reason': _row_value(u, 'disabled_reason'),
            'notification_prefs': notification_prefs,
            'theme': theme,
        }

    def api_profile(self, conn, qs, m, body):
        u = self.require_user(conn)
        if 'display_name' in (body or {}):
            dn = str(body['display_name'] or '').strip()[:60]
            if dn:
                conn.execute('UPDATE users SET display_name=? WHERE id=?', (dn, u['id']))
        if 'is_gm' in (body or {}) or 'account_role' in (body or {}):
            raise ApiError(403, 'Роли аккаунтов назначает только администратор NC//NET')
        if 'show_display_name' in (body or {}):
            conn.execute('UPDATE users SET show_display_name=? WHERE id=?',
                         (1 if body['show_display_name'] else 0, u['id']))
        if 'avatar_media_id' in (body or {}):
            avatar_media_id = str(body.get('avatar_media_id') or '')[:64] or None
            attach_network_media(conn, u['id'], 'account', u['id'],
                                 [avatar_media_id], {'account_avatar'})
            conn.execute('UPDATE users SET avatar_media_id=? WHERE id=?',
                         (avatar_media_id, u['id']))
        if 'notification_prefs' in (body or {}):
            prefs = body.get('notification_prefs') or {}
            if not isinstance(prefs, dict) or len(json.dumps(prefs)) > 5000:
                raise ApiError(400, 'Некорректные настройки уведомлений')
            conn.execute('UPDATE users SET notification_prefs=? WHERE id=?',
                         (json.dumps(prefs, separators=(',', ':')), u['id']))
        if 'theme' in (body or {}):
            theme = body.get('theme') or {}
            if not isinstance(theme, dict) or len(json.dumps(theme)) > 5000:
                raise ApiError(400, 'Некорректная тема')
            validate_theme(theme)
            conn.execute('UPDATE users SET theme_json=? WHERE id=?',
                         (json.dumps(theme, separators=(',', ':')), u['id']))
        conn.commit()
        u2 = conn.execute('SELECT * FROM users WHERE id=?', (u['id'],)).fetchone()
        self.send_json(self.me_payload(u2))

    def invite_payload(self, row):
        now = time.time()
        return {
            'id': row['id'], 'label': row['label'],
            'max_uses': row['max_uses'], 'uses': row['uses'],
            'expires_at': row['expires_at'], 'disabled_at': row['disabled_at'],
            'created_by': row['created_by'], 'created': row['created'],
            'active': (not row['disabled_at'] and row['uses'] < row['max_uses'] and
                       (row['expires_at'] is None or row['expires_at'] > now)),
        }

    def api_vk_oauth_start(self, conn, qs, m, body):
        user = self.require_user(conn)
        client_id = os.environ.get('VK_CLIENT_ID')
        redirect_uri = os.environ.get('VK_REDIRECT_URI')
        if not client_id or not redirect_uri:
            raise ApiError(503, 'VK OAuth не настроен')
        state = secrets.token_urlsafe(32)
        conn.execute('INSERT INTO vk_oauth_states(state,user_id,expires) VALUES(?,?,?)',
                     (state, user['id'], time.time() + 900))
        conn.execute('DELETE FROM vk_oauth_states WHERE expires<?', (time.time(),))
        conn.commit()
        query = urlencode({'client_id': client_id, 'redirect_uri': redirect_uri,
                           'display': 'page', 'scope': 0, 'response_type': 'code',
                           'v': os.environ.get('VK_API_VERSION', '5.199'), 'state': state})
        self.send_json({'url': 'https://oauth.vk.com/authorize?' + query})

    def api_vk_oauth_callback(self, conn, qs, m, body):
        state = q1(qs.get('state')); code = q1(qs.get('code'))
        record = conn.execute('SELECT * FROM vk_oauth_states WHERE state=? AND expires>?',
                              (state, time.time())).fetchone()
        if not record or not code:
            raise ApiError(400, 'Некорректный или истёкший VK OAuth state')
        client_id = os.environ.get('VK_CLIENT_ID'); secret = os.environ.get('VK_CLIENT_SECRET')
        redirect_uri = os.environ.get('VK_REDIRECT_URI')
        if not client_id or not secret or not redirect_uri:
            raise ApiError(503, 'VK OAuth не настроен')
        query = urlencode({'client_id': client_id, 'client_secret': secret,
                           'redirect_uri': redirect_uri, 'code': code})
        try:
            response = json.loads(urlopen('https://oauth.vk.com/access_token?' + query, timeout=15).read().decode())
        except (URLError, HTTPError, ValueError) as error:
            raise ApiError(502, 'VK OAuth временно недоступен')
        vk_user_id = response.get('user_id')
        if not vk_user_id:
            raise ApiError(400, 'VK OAuth не вернул пользователя')
        conn.execute('UPDATE users SET vk_user_id=?,vk_linked_at=? WHERE id=?',
                     (str(vk_user_id), time.time(), record['user_id']))
        conn.execute('DELETE FROM vk_oauth_states WHERE state=?', (state,))
        conn.commit(); self.send_json({'ok': True, 'vk_user_id': str(vk_user_id)})

    def api_notifications(self, conn, qs, m, body):
        user = self.require_user(conn)
        rows = conn.execute(
            'SELECT * FROM notifications WHERE user_id=? ORDER BY created DESC LIMIT 100',
            (user['id'],)).fetchall()
        self.send_json({'notifications': [dict(row) for row in rows],
                        'unread': sum(1 for row in rows if not row['read_at'])})

    def api_notification_read(self, conn, qs, m, body):
        user = self.require_user(conn)
        if (body or {}).get('all'):
            conn.execute('UPDATE notifications SET read_at=? WHERE user_id=? AND read_at IS NULL',
                         (time.time(), user['id']))
        else:
            conn.execute('UPDATE notifications SET read_at=? WHERE id=? AND user_id=?',
                         (time.time(), int(m.group(1)), user['id']))
        conn.commit(); self.send_json({'ok': True})
