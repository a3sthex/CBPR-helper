"""Аутентификация NC//NET: раунды PBKDF, сессии, инвайты (итерация P1-11,
выделено из app/server.py; логика не менялась)."""
import hashlib
import hmac
import os
import re
import secrets
import time

from core import PBKDF_ITERS, SESSION_TTL, ApiError



REGISTRATION_MODES = {'open', 'invite', 'closed'}


def registration_mode():
    mode = str(os.environ.get('CBPR_REGISTRATION_MODE', 'invite') or '').strip().lower()
    return mode if mode in REGISTRATION_MODES else 'invite'


def invite_code_hash(code):
    normalized = re.sub(r'[^A-Za-z0-9]', '', str(code or '')).upper()
    return hashlib.sha256(normalized.encode()).hexdigest() if normalized else ''


def create_invite_code():
    raw = secrets.token_hex(8).upper()
    return f'NCNET-{raw[:4]}-{raw[4:8]}-{raw[8:12]}-{raw[12:16]}'


def validate_new_password(password):
    if len(password) < 8:
        raise ApiError(400, 'Пароль: минимум 8 символов')
    if len(password) > 256:
        raise ApiError(400, 'Пароль слишком длинный')


def hash_password(pw):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), PBKDF_ITERS)
    return f'pbkdf2${PBKDF_ITERS}${salt}${dk.hex()}'


def verify_password(pw, stored):
    try:
        _, iters, salt, hexdk = stored.split('$')
        dk = hashlib.pbkdf2_hmac('sha256', pw.encode(), salt.encode(), int(iters))
        return hmac.compare_digest(dk.hex(), hexdk)
    except Exception:
        return False


def session_cookie(token, max_age=SESSION_TTL):
    secure = (os.environ.get('CBPR_SECURE_COOKIES', '').lower() in ('1','true','yes') or
              (os.environ.get('NCNET_PUBLIC_URL') or '').lower().startswith('https://'))
    parts = [f'sid={token}', 'Path=/', 'HttpOnly', 'SameSite=Lax', f'Max-Age={max_age}']
    if secure:
        parts.append('Secure')
    return '; '.join(parts)


def create_session(conn, user_id, ip_address='', user_agent=''):
    token = secrets.token_hex(32)
    now = time.time()
    conn.execute(
        'INSERT INTO sessions(token,user_id,created,expires,last_seen,ip_address,user_agent) '
        'VALUES(?,?,?,?,?,?,?)',
        (token, user_id, now, now + SESSION_TTL, now,
         str(ip_address or '')[:64], str(user_agent or '')[:300]))
    conn.execute('DELETE FROM sessions WHERE expires < ?', (now,))
    conn.commit()
    return token
