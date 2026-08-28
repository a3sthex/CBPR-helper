"""Домен изображений NC//NET: валидация, хранение, выдача, права.

Пилотный домен разделения app/server.py (см. docs/repo-audit-2026-08.md).
Хендлеры — миксин MediaHandlers, наследуемый классом Handler в server.py;
логика перенесена без изменений.
"""
import base64
import os
import re
import secrets
import time

from core import (ApiError, UPLOAD_DIR, can_edit_contract, can_manage_persona,
                  ensure_character_visibility, parse_json_object, user_is_admin,
                  user_is_gm)

MEDIA_LIMIT = 2_500_000
MEDIA_KINDS = {
    'character_portrait', 'account_avatar', 'news_image', 'job_image',
    'persona_avatar', 'persona_cover', 'contract_image', 'feed_image',
}

def image_info(raw):
    """Return (mime, extension, width, height) from trusted file signatures."""
    if raw.startswith(b'\x89PNG\r\n\x1a\n') and len(raw) >= 24:
        return 'image/png', 'png', int.from_bytes(raw[16:20], 'big'), int.from_bytes(raw[20:24], 'big')
    if raw.startswith(b'\xff\xd8'):
        pos = 2
        while pos + 9 < len(raw):
            if raw[pos] != 0xff:
                pos += 1; continue
            marker = raw[pos + 1]; pos += 2
            if marker in (0xd8, 0xd9): continue
            if pos + 2 > len(raw): break
            size = int.from_bytes(raw[pos:pos + 2], 'big')
            if marker in tuple(range(0xc0, 0xc4)) + tuple(range(0xc5, 0xc8)) + tuple(range(0xc9, 0xcc)) + tuple(range(0xcd, 0xd0)):
                return 'image/jpeg', 'jpg', int.from_bytes(raw[pos + 5:pos + 7], 'big'), int.from_bytes(raw[pos + 3:pos + 5], 'big')
            pos += size
    if raw.startswith(b'RIFF') and raw[8:12] == b'WEBP' and len(raw) >= 30:
        chunk = raw[12:16]
        if chunk == b'VP8X':
            return 'image/webp', 'webp', 1 + int.from_bytes(raw[24:27], 'little'), 1 + int.from_bytes(raw[27:30], 'little')
        if chunk == b'VP8 ' and len(raw) >= 30:
            return 'image/webp', 'webp', int.from_bytes(raw[26:28], 'little') & 0x3fff, int.from_bytes(raw[28:30], 'little') & 0x3fff
        if chunk == b'VP8L' and len(raw) >= 25:
            bits = int.from_bytes(raw[21:25], 'little')
            return 'image/webp', 'webp', (bits & 0x3fff) + 1, ((bits >> 14) & 0x3fff) + 1
    return None

def media_payload(row):
    return {'id': row['id'], 'kind': row['kind'], 'mime': row['mime'], 'size': row['size'],
            'width': row['width'], 'height': row['height'], 'url': f'/api/media/{row["id"]}'}

def attach_character_media(conn, user_id, character_id, data):
    media_id = str(data.get('portrait_media_id') or '')
    if not media_id:
        return
    media = conn.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
    if not media or media['owner_id'] != user_id or media['kind'] != 'character_portrait':
        raise ApiError(400, 'Недопустимое изображение персонажа')
    if media['attached_type'] and not (media['attached_type'] == 'character' and media['attached_id'] == character_id):
        raise ApiError(409, 'Изображение уже прикреплено')
    conn.execute("UPDATE media SET attached_type='character', attached_id=? WHERE id=?", (character_id, media_id))


class MediaHandlers:
    """Хендлеры /api/media — миксин для Handler в server.py."""

    def api_media_upload(self, conn, qs, m, body):
        u = self.require_user(conn)
        kind = str((body or {}).get('kind') or '')
        if kind not in MEDIA_KINDS:
            raise ApiError(400, 'Недопустимый тип изображения')
        data_url = str((body or {}).get('data_url') or '')
        match = re.fullmatch(r'data:image/(?:png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)', data_url)
        if not match:
            raise ApiError(400, 'Ожидается JPEG, PNG или WebP')
        try:
            raw = base64.b64decode(match.group(1), validate=True)
        except Exception:
            raise ApiError(400, 'Повреждённые данные изображения')
        if not raw or len(raw) > MEDIA_LIMIT:
            raise ApiError(413, f'Изображение должно быть не больше {MEDIA_LIMIT // 1_000_000} MB')
        info = image_info(raw)
        if not info:
            raise ApiError(400, 'Формат изображения не подтверждён содержимым')
        mime, ext, width, height = info
        if width < 32 or height < 32 or width > 6000 or height > 6000 or width * height > 24_000_000:
            raise ApiError(400, 'Недопустимое разрешение изображения')
        total = conn.execute('SELECT COALESCE(SUM(size),0) n FROM media WHERE owner_id=?', (u['id'],)).fetchone()['n']
        if total + len(raw) > 50_000_000:
            raise ApiError(413, 'Достигнут лимит хранилища изображений')
        media_id = secrets.token_hex(16)
        filename = f'{media_id}.{ext}'
        with open(os.path.join(UPLOAD_DIR, filename), 'wb') as handle:
            handle.write(raw)
        conn.execute('INSERT INTO media(id,owner_id,kind,mime,filename,size,width,height,created) VALUES(?,?,?,?,?,?,?,?,?)',
                     (media_id, u['id'], kind, mime, filename, len(raw), width, height, time.time()))
        conn.commit()
        row = conn.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
        self.send_json(media_payload(row), status=201)

    def api_media_get(self, conn, qs, m, body):
        row = conn.execute('SELECT * FROM media WHERE id=?', (m.group(1),)).fetchone()
        if not row:
            raise ApiError(404, 'Изображение не найдено')
        user = self.current_user(conn)
        allowed = bool(user and user['id'] == row['owner_id']); public_media = False
        if row['attached_type'] == 'character' and row['attached_id']:
            char = conn.execute('SELECT owner_id,public,data FROM characters WHERE id=?',
                                (row['attached_id'],)).fetchone()
            char_data = parse_json_object(char['data']) if char else {}
            portrait_visible = ensure_character_visibility(char_data)['portrait'] if char else False
            authored_public = False
            if char and portrait_visible and not char['public']:
                authored_public = bool(conn.execute(
                    "SELECT 1 FROM feed_posts WHERE author_character_id=? AND status='published' "
                    "UNION SELECT 1 FROM feed_comments fc JOIN feed_posts fp ON fp.id=fc.post_id "
                    "WHERE fc.author_character_id=? AND fc.hidden_at IS NULL AND fp.status='published' LIMIT 1",
                    (char['id'], char['id'])).fetchone())
            public_media = bool(char and portrait_visible and (char['public'] or authored_public))
            allowed = bool(char and (public_media or
                           (user and (user['id'] == char['owner_id'] or user_is_admin(user)))))
        elif row['attached_type'] == 'account' and row['attached_id']:
            account = conn.execute('SELECT id,show_display_name FROM users WHERE id=?',
                                   (row['attached_id'],)).fetchone()
            public_media = bool(account and account['show_display_name'])
            allowed = bool(account and user and
                           (user['id'] == account['id'] or public_media))
        elif row['attached_type'] == 'persona' and row['attached_id']:
            persona = conn.execute('SELECT * FROM personas WHERE id=?', (row['attached_id'],)).fetchone()
            public_media = bool(persona and persona['access'] in ('shared', 'system') and persona['status'] != 'archived')
            allowed = public_media or can_manage_persona(user, persona)
        elif row['attached_type'] == 'contract' and row['attached_id']:
            contract = conn.execute('SELECT * FROM contracts WHERE id=?', (row['attached_id'],)).fetchone()
            public_media = bool(contract and contract['status'] not in ('draft', 'archived'))
            allowed = public_media or can_edit_contract(conn, user, contract)
        elif row['attached_type'] == 'feed_post' and row['attached_id']:
            post = conn.execute('SELECT * FROM feed_posts WHERE id=?', (row['attached_id'],)).fetchone()
            public_media = bool(post and post['status'] == 'published')
            allowed = bool(public_media or (post and user and
                           (post['creator_user_id'] == user['id'] or user_is_gm(user))))
        if not allowed:
            raise ApiError(403, 'Изображение приватное')
        path = os.path.join(UPLOAD_DIR, row['filename'])
        if not os.path.isfile(path):
            raise ApiError(404, 'Файл изображения не найден')
        raw = open(path, 'rb').read()
        self.send_response(200)
        self.send_header('Content-Type', row['mime'])
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Cache-Control', 'public, max-age=86400' if public_media else 'private, no-store')
        self.send_security_headers()
        self.end_headers(); self.wfile.write(raw)

    def api_media_delete(self, conn, qs, m, body):
        u = self.require_user(conn)
        row = conn.execute('SELECT * FROM media WHERE id=?', (m.group(1),)).fetchone()
        if not row or row['owner_id'] != u['id']:
            raise ApiError(404, 'Изображение не найдено')
        if row['attached_type']:
            raise ApiError(409, 'Сначала отсоедините изображение')
        try: os.remove(os.path.join(UPLOAD_DIR, row['filename']))
        except FileNotFoundError: pass
        conn.execute('DELETE FROM media WHERE id=?', (row['id'],)); conn.commit()
        self.send_json({'ok': True})
