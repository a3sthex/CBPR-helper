import importlib.util
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ncnet_access_server', ROOT / 'app/server.py')
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class AccessRoleMigrationTests(unittest.TestCase):
    def legacy_connection(self, path):
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        conn.executescript('''
            CREATE TABLE users(
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              username TEXT UNIQUE NOT NULL,
              display_name TEXT NOT NULL,
              pass_hash TEXT NOT NULL,
              is_gm INTEGER NOT NULL DEFAULT 0,
              created REAL NOT NULL
            );
            INSERT INTO users(username,display_name,pass_hash,is_gm,created)
              VALUES('alice','Alice','x',1,1),('bob','Bob','x',0,2);
        ''')
        conn.commit()
        return conn

    def test_legacy_roles_migrate_idempotently_with_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / 'campaign.db')
            conn = self.legacy_connection(path)
            original_path = server.DB_PATH
            server.DB_PATH = path
            try:
                server.apply_schema_migrations(conn, make_backup=True)
                server.apply_schema_migrations(conn, make_backup=True)
            finally:
                server.DB_PATH = original_path
            roles = {row['username']: row['account_role']
                     for row in conn.execute('SELECT * FROM users')}
            self.assertEqual(roles, {'alice': 'gm', 'bob': 'player'})
            self.assertEqual(
                conn.execute('SELECT COUNT(*) n FROM schema_migrations').fetchone()['n'], 5)
            self.assertEqual(len(list(Path(directory).glob('campaign.db.backup-*'))), 1)
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(users)')}
            self.assertTrue({'account_role', 'show_display_name', 'vk_user_id',
                             'notification_prefs', 'theme_json'} <= columns)
            conn.close()

    def test_admin_bootstrap_is_explicit_and_audited(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = self.legacy_connection(str(Path(directory) / 'campaign.db'))
            server.apply_schema_migrations(conn, make_backup=False)
            with mock.patch.dict(os.environ, {'CBPR_ADMIN_USERS': 'alice, missing'}, clear=False):
                promoted = server.apply_admin_bootstrap(conn)
            self.assertEqual(promoted, ['alice'])
            alice = conn.execute("SELECT * FROM users WHERE username='alice'").fetchone()
            self.assertEqual(server.user_account_role(alice), 'admin')
            self.assertTrue(alice['is_gm'])
            audit = conn.execute('SELECT * FROM account_role_audit').fetchall()
            self.assertEqual(len(audit), 1)
            self.assertEqual(audit[0]['role_before'], 'gm')
            self.assertEqual(audit[0]['role_after'], 'admin')
            conn.close()

    def test_admin_assigns_roles_and_last_admin_is_protected(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = self.legacy_connection(str(Path(directory) / 'campaign.db'))
            server.apply_schema_migrations(conn, make_backup=False)
            with mock.patch.dict(os.environ, {'CBPR_ADMIN_USERS': 'alice'}, clear=False):
                server.apply_admin_bootstrap(conn)
            alice = conn.execute("SELECT * FROM users WHERE username='alice'").fetchone()
            bob = server.assign_account_role(conn, alice, 2, 'gm', 'Campaign GM')
            self.assertEqual(server.user_account_role(bob), 'gm')
            bob = server.assign_account_role(conn, alice, 2, 'admin', 'Second administrator')
            alice = server.assign_account_role(conn, bob, 1, 'player', 'Transfer ownership')
            self.assertEqual(server.user_account_role(alice), 'player')
            with self.assertRaises(server.ApiError) as raised:
                server.assign_account_role(conn, bob, 2, 'gm', 'Would remove last Admin')
            self.assertEqual(raised.exception.status, 409)
            self.assertEqual(conn.execute('SELECT COUNT(*) n FROM account_role_audit').fetchone()['n'], 4)
            conn.close()

    def test_registration_cannot_self_assign_gm(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = sqlite3.connect(str(Path(directory) / 'fresh.db'))
            conn.row_factory = sqlite3.Row
            conn.executescript(server.SCHEMA)
            server.apply_schema_migrations(conn, make_backup=False)
            response = {}
            handler = object.__new__(server.Handler)
            handler.send_json = lambda payload, status=200, cookies=None: response.update(
                payload=payload, status=status, cookies=cookies)
            server.Handler.api_register(handler, conn, {}, None, {
                'username': 'newplayer', 'display_name': 'New Player',
                'password': 'password', 'is_gm': True, 'account_role': 'admin',
            })
            row = conn.execute("SELECT * FROM users WHERE username='newplayer'").fetchone()
            self.assertEqual(row['account_role'], 'player')
            self.assertFalse(row['is_gm'])
            self.assertEqual(response['payload']['account_role'], 'player')
            self.assertFalse(response['payload']['is_gm'])
            handler.require_user = lambda current: row
            with self.assertRaises(server.ApiError) as raised:
                server.Handler.api_profile(handler, conn, {}, None, {'is_gm': True})
            self.assertEqual(raised.exception.status, 403)
            conn.close()

    def test_player_post_is_published_without_gm_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            conn = sqlite3.connect(str(Path(directory) / 'feed.db'))
            conn.row_factory = sqlite3.Row
            conn.executescript(server.SCHEMA)
            server.apply_schema_migrations(conn, make_backup=False)
            conn.execute(
                "INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) "
                "VALUES('reporter','Reporter','x',0,'player',1)")
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE username='reporter'").fetchone()
            response = {}
            handler = object.__new__(server.Handler)
            handler.require_user = lambda current: user
            handler.send_json = lambda payload, status=200, cookies=None: response.update(
                payload=payload, status=status)
            server.Handler.api_news_create(handler, conn, {}, None, {
                'title': 'Street transmission', 'tag': 'Watson',
                'body': 'Published directly from the city feed.',
            })
            self.assertEqual(response['status'], 201)
            self.assertEqual(conn.execute('SELECT COUNT(*) n FROM news').fetchone()['n'], 1)
            self.assertEqual(response['payload']['author_id'], user['id'])
            conn.close()

    def test_secure_cookie_rate_limit_and_origin_guard(self):
        with mock.patch.dict(os.environ, {'NCNET_PUBLIC_URL': 'https://ncnet.example'}, clear=False):
            self.assertIn('Secure', server.session_cookie('token'))
        key = 'unit-rate-limit-unique'
        server.enforce_rate_limit(key, 1, 60)
        with self.assertRaises(server.ApiError) as limited:
            server.enforce_rate_limit(key, 1, 60)
        self.assertEqual(limited.exception.status, 429)
        handler = object.__new__(server.Handler)
        handler.headers = {'Origin': 'https://evil.example', 'Host': 'ncnet.example'}
        with self.assertRaises(server.ApiError) as denied:
            server.Handler.verify_request_origin(handler)
        self.assertEqual(denied.exception.status, 403)

    def test_frontend_has_no_self_assign_gm_controls(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertNotIn('id="rg-gm"', source)
        self.assertNotIn('id="pf-gm"', source)
        self.assertIn("admin: viewAdmin", source)
        shell = (ROOT / 'app/static/index.html').read_text(encoding='utf-8')
        self.assertIn('NC<b>//NET</b>', shell)
        self.assertIn('#/contracts', shell)
        self.assertIn('#/feed', shell)
        self.assertIn('/ncnet.js', shell)
        network = (ROOT / 'app/static/ncnet.js').read_text(encoding='utf-8')
        self.assertIn('publish immediately', network)
        for district in ('watson', 'westbrook', 'city-center', 'heywood',
                         'santo-domingo', 'pacifica', 'badlands'):
            self.assertIn("id:'" + district + "'", network)
        self.assertIn('NC_AUDIO', network)
        self.assertIn('openSessionDashboard', network)


if __name__ == '__main__':
    unittest.main()
