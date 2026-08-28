"""Админ-панель NC//NET: пользователи, роли, инвайты, бэкапы, VK outbox (миксин Handler; P1, логика не менялась)."""


import os
import sqlite3
import time

from auth import create_invite_code, invite_code_hash, registration_mode
from core import (BACKUP_DIR, DB_PATH, ITEMS_PATH, UPLOAD_DIR, ApiError,
                  _row_value, user_account_role, user_is_admin)
from db import backup_retention, backup_tools_module
from httpkit import atomic_endpoint
from recap import assign_account_role, deliver_vk_outbox, record_account_security
from rules import _num


class AdminMixin:

    def api_admin_backup_create(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        tools = backup_tools_module()
        try:
            retention = backup_retention()
            result = tools.create_bundle(
                DB_PATH, UPLOAD_DIR, BACKUP_DIR, ITEMS_PATH, retention,
                str((body or {}).get('reason') or 'manual')[:120])
        except (tools.BackupError, OSError, sqlite3.DatabaseError) as error:
            raise ApiError(500, f'Не удалось создать резервную копию: {error}')
        record_account_security(conn, actor['id'], actor['id'], 'backup_created', result['name'])
        conn.commit()
        self.send_json({key: value for key, value in result.items() if key != 'path'}, status=201)

    def api_admin_backup_download(self, conn, qs, m, body):
        self.require_admin(conn)
        tools = backup_tools_module()
        try:
            path = tools.bundle_path(BACKUP_DIR, m.group(1))
        except (tools.BackupError, OSError) as error:
            raise ApiError(404, f'Резервная копия не найдена: {error}')
        self.send_response(200)
        self.send_header('Content-Type', 'application/gzip')
        self.send_header('Content-Disposition', f'attachment; filename="{path.name}"')
        self.send_header('Content-Length', str(path.stat().st_size))
        self.send_header('Cache-Control', 'private, no-store')
        self.send_security_headers()
        self.end_headers()
        with open(path, 'rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                self.wfile.write(chunk)

    def api_admin_backup_verify(self, conn, qs, m, body):
        self.require_admin(conn)
        tools = backup_tools_module()
        try:
            path = tools.bundle_path(BACKUP_DIR, m.group(1))
            result = tools.verify_bundle(path)
        except (tools.BackupError, OSError, sqlite3.DatabaseError) as error:
            raise ApiError(400, f'Резервная копия не прошла проверку: {error}')
        self.send_json(result)

    def api_admin_backups(self, conn, qs, m, body):
        self.require_admin(conn)
        tools = backup_tools_module()
        try:
            backups = tools.list_bundles(BACKUP_DIR)
        except (tools.BackupError, OSError) as error:
            raise ApiError(500, f'Не удалось прочитать резервные копии: {error}')
        self.send_json({'backups': backups, 'retention': backup_retention()})

    def api_admin_invite_create(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        label = str((body or {}).get('label') or '').strip()[:120]
        max_uses = max(1, min(100, _num((body or {}).get('max_uses')) or 1))
        expires_days = _num((body or {}).get('expires_days'))
        expires_at = None if not expires_days else time.time() + max(1, min(365, expires_days)) * 86400
        code = create_invite_code()
        cur = conn.execute(
            'INSERT INTO registration_invites(code_hash,label,created_by,max_uses,uses,'
            'expires_at,created) VALUES(?,?,?,?,0,?,?)',
            (invite_code_hash(code), label, actor['id'], max_uses, expires_at, time.time()))
        conn.commit()
        row = conn.execute('SELECT * FROM registration_invites WHERE id=?',
                           (cur.lastrowid,)).fetchone()
        self.send_json({**self.invite_payload(row), 'code': code}, status=201)

    def api_admin_invite_revoke(self, conn, qs, m, body):
        self.require_admin(conn)
        row = conn.execute('SELECT * FROM registration_invites WHERE id=?',
                           (int(m.group(1)),)).fetchone()
        if not row:
            raise ApiError(404, 'Приглашение не найдено')
        conn.execute('UPDATE registration_invites SET disabled_at=? WHERE id=?',
                     (time.time(), row['id']))
        conn.commit()
        updated = conn.execute('SELECT * FROM registration_invites WHERE id=?',
                               (row['id'],)).fetchone()
        self.send_json(self.invite_payload(updated))

    def api_admin_invites(self, conn, qs, m, body):
        self.require_admin(conn)
        rows = conn.execute(
            'SELECT * FROM registration_invites ORDER BY created DESC,id DESC LIMIT 200'
        ).fetchall()
        self.send_json({'registration_mode': registration_mode(),
                        'invites': [self.invite_payload(row) for row in rows]})

    @atomic_endpoint
    def api_admin_user_role(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not reason:
            raise ApiError(400, 'Укажите причину изменения доступа')
        updated = assign_account_role(
            conn, actor, int(m.group(1)), (body or {}).get('account_role'), reason)
        self.send_json(self.me_payload(updated))

    @atomic_endpoint
    def api_admin_user_status(self, conn, qs, m, body):
        actor = self.require_admin(conn)
        target = conn.execute('SELECT * FROM users WHERE id=?',
                              (int(m.group(1)),)).fetchone()
        if not target:
            raise ApiError(404, 'Пользователь не найден')
        disabled = bool((body or {}).get('disabled'))
        reason = str((body or {}).get('reason') or '').strip()[:500]
        if not reason:
            raise ApiError(400, 'Укажите причину изменения доступа')
        if disabled and target['id'] == actor['id']:
            raise ApiError(409, 'Нельзя отключить собственный аккаунт')
        if disabled and user_is_admin(target):
            active_admins = conn.execute(
                "SELECT COUNT(*) n FROM users WHERE account_role='admin' AND disabled_at IS NULL"
            ).fetchone()['n']
            if active_admins <= 1:
                raise ApiError(409, 'Нельзя отключить последнего активного администратора')
        currently_disabled = bool(_row_value(target, 'disabled_at'))
        if disabled == currently_disabled:
            self.send_json(self.me_payload(target))
            return
        if disabled:
            conn.execute(
                'UPDATE users SET disabled_at=?,disabled_reason=?,disabled_by=? WHERE id=?',
                (time.time(), reason, actor['id'], target['id']))
            conn.execute('DELETE FROM sessions WHERE user_id=?', (target['id'],))
            event_type = 'account_disabled'
        else:
            conn.execute(
                'UPDATE users SET disabled_at=NULL,disabled_reason=NULL,disabled_by=NULL WHERE id=?',
                (target['id'],))
            event_type = 'account_enabled'
        record_account_security(conn, target['id'], actor['id'], event_type, reason)
        conn.commit()
        updated = conn.execute('SELECT * FROM users WHERE id=?', (target['id'],)).fetchone()
        self.send_json(self.me_payload(updated))

    def api_admin_users(self, conn, qs, m, body):
        self.require_admin(conn)
        rows = conn.execute(
            'SELECT u.*, COUNT(c.id) character_count FROM users u '
            'LEFT JOIN characters c ON c.owner_id=u.id GROUP BY u.id ORDER BY u.created, u.id'
        ).fetchall()
        audit_rows = conn.execute(
            'SELECT a.*, target.username target_username, actor.username actor_username '
            'FROM account_role_audit a JOIN users target ON target.id=a.target_user_id '
            'LEFT JOIN users actor ON actor.id=a.actor_user_id '
            'ORDER BY a.created DESC, a.id DESC LIMIT 50'
        ).fetchall()
        security_rows = conn.execute(
            'SELECT a.*,target.username target_username,actor.username actor_username '
            'FROM account_security_audit a JOIN users target ON target.id=a.user_id '
            'LEFT JOIN users actor ON actor.id=a.actor_user_id '
            'ORDER BY a.created DESC,a.id DESC LIMIT 50'
        ).fetchall()
        self.send_json({
            'users': [{
                'id': row['id'], 'username': row['username'],
                'display_name': row['display_name'],
                'account_role': user_account_role(row),
                'show_display_name': bool(_row_value(row, 'show_display_name', 0)),
                'vk_linked': bool(_row_value(row, 'vk_user_id')),
                'disabled': bool(_row_value(row, 'disabled_at')),
                'disabled_reason': _row_value(row, 'disabled_reason'),
                'disabled_at': _row_value(row, 'disabled_at'),
                'character_count': row['character_count'],
                'created': row['created'],
            } for row in rows],
            'role_audit': [{
                'id': row['id'], 'target_username': row['target_username'],
                'actor_username': row['actor_username'] or 'system',
                'role_before': row['role_before'], 'role_after': row['role_after'],
                'reason': row['reason'], 'created': row['created'],
            } for row in audit_rows],
            'security_audit': [{
                'id': row['id'], 'target_username': row['target_username'],
                'actor_username': row['actor_username'] or 'system',
                'event_type': row['event_type'], 'detail': row['detail'],
                'created': row['created'],
            } for row in security_rows],
        })

    def api_admin_vk_flush(self, conn, qs, m, body):
        self.require_admin(conn)
        self.send_json(deliver_vk_outbox(conn, _num((body or {}).get('limit')) or 20))

    def api_admin_vk_status(self, conn, qs, m, body):
        self.require_admin(conn)
        counts = {row['status']: row['n'] for row in conn.execute(
            'SELECT status,COUNT(*) n FROM vk_outbox GROUP BY status').fetchall()}
        self.send_json({'configured': bool(os.environ.get('VK_COMMUNITY_TOKEN') and os.environ.get('VK_PEER_ID')),
                        'counts': counts, 'peer_id': bool(os.environ.get('VK_PEER_ID'))})

    def api_gm_users(self, conn, qs, m, body):
        self.require_gm(conn)
        rows = conn.execute(
            "SELECT id,username,display_name,account_role FROM users "
            "WHERE account_role IN ('gm','admin') ORDER BY display_name").fetchall()
        self.send_json({'users': [dict(row) for row in rows]})
