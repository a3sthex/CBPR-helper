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
                conn.execute(
                    'INSERT INTO session_combatants(session_id,name,sp_head,sp_body,'
                    'shield_current,ammo_current) VALUES(1,\'Legacy NPC\',7,11,10,20)')
                conn.commit()
                server.apply_schema_migrations(conn, make_backup=True)
            finally:
                server.DB_PATH = original_path
            roles = {row['username']: row['account_role']
                     for row in conn.execute('SELECT * FROM users')}
            self.assertEqual(roles, {'alice': 'gm', 'bob': 'player'})
            self.assertEqual(
                conn.execute('SELECT COUNT(*) n FROM schema_migrations').fetchone()['n'], 6)
            self.assertEqual(len(list(Path(directory).glob('campaign.db.backup-*'))), 1)
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(users)')}
            self.assertTrue({'account_role', 'show_display_name', 'vk_user_id',
                             'notification_prefs', 'theme_json', 'avatar_media_id'} <= columns)
            combatant_columns = {row['name'] for row in conn.execute(
                'PRAGMA table_info(session_combatants)')}
            self.assertTrue({'sp_head_max', 'sp_body_max', 'shield_max', 'ammo_max',
                             'luck_current', 'luck_max'} <= combatant_columns)
            template_columns = {row['name'] for row in conn.execute(
                'PRAGMA table_info(npc_templates)')}
            self.assertIn('archived', template_columns)
            legacy_npc = conn.execute("SELECT * FROM session_combatants WHERE name='Legacy NPC'").fetchone()
            self.assertEqual((legacy_npc['sp_head_max'], legacy_npc['sp_body_max'],
                              legacy_npc['shield_max'], legacy_npc['ammo_max']),
                             (7, 11, 10, 20))
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
            handler = object.__new__(server.Handler)
            handler.require_admin = lambda current: bob
            with self.assertRaises(server.ApiError) as missing_reason:
                server.Handler.api_admin_user_role(
                    handler, conn, {}, mock.Mock(group=lambda index: '1'),
                    {'account_role': 'gm', 'reason': ''})
            self.assertEqual(missing_reason.exception.status, 400)
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
            media_id = 'a' * 32
            conn.execute(
                'INSERT INTO media(id,owner_id,kind,mime,filename,size,width,height,created) '
                "VALUES(?,?,'account_avatar','image/webp','avatar.webp',100,100,100,1)",
                (media_id, row['id']))
            conn.commit()
            server.Handler.api_profile(handler, conn, {}, None, {
                'avatar_media_id': media_id, 'show_display_name': True,
            })
            attached = conn.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
            self.assertEqual((attached['attached_type'], attached['attached_id']),
                             ('account', row['id']))
            self.assertEqual(response['payload']['avatar_media_id'], media_id)
            with self.assertRaises(server.ApiError):
                server.Handler.api_profile(handler, conn, {}, None, {
                    'avatar_media_id': 'f' * 32,
                })
            still_attached = conn.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
            self.assertEqual(still_attached['attached_type'], 'account')
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
        self.assertIn('class="skip-link"', shell)
        self.assertIn('aria-live="polite"', shell)
        self.assertIn('class="nav-rail"', shell)
        self.assertIn('id="workspace-switch"', shell)
        self.assertIn('class="mobile-primary-nav"', shell)
        self.assertIn('id="active-dossier"', shell)
        self.assertIn('role="dialog"', source)
        self.assertIn('MODAL_FOCUSABLE', source)
        self.assertIn("root.insertAdjacentHTML('beforeend'", source)
        self.assertIn('previous.hidden = true', source)
        self.assertIn('closeModal(true)', source)
        self.assertIn("kind === 'feed_image' || kind === 'news_image'", source)
        self.assertIn("'16:9': [1920,1080]", source)
        self.assertIn('crop-output-width', source)
        self.assertIn('12_000_000', source)
        network = (ROOT / 'app/static/ncnet.js').read_text(encoding='utf-8')
        network_css = (ROOT / 'app/static/ncnet.css').read_text(encoding='utf-8')
        self.assertIn('nc-feed-image-frame', network)
        self.assertIn('feed-image-lightbox', network)
        self.assertIn('ncBindMapControls', network)
        self.assertIn('theme-map', network)
        self.assertIn('mix-blend-mode:color', network_css)
        self.assertIn('object-fit:contain', network_css)
        self.assertNotIn('.nc-feed-image{width:100%;max-height:380px;object-fit:cover', network_css)
        self.assertIn('publish immediately', network)
        for district in ('watson', 'westbrook', 'city-center', 'heywood',
                         'santo-domingo', 'pacifica', 'badlands', 'orbital-air-space-center'):
            self.assertIn("id:'" + district + "'", network)
        for location in ('watson-little-china', 'westbrook-japantown',
                         'badlands-near-westbrook', 'badlands-near-santo-domingo',
                         'badlands-near-pacifica'):
            self.assertIn(location, network)
        self.assertIn('NC_AUDIO', network)
        self.assertIn('openSessionDashboard', network)
        self.assertIn('show_injuries', network)
        self.assertIn('/clone', network)
        self.assertIn('account_avatar', source)
        self.assertIn('ncBindActivation', network)
        self.assertIn('role="button" tabindex="0"', network)
        self.assertIn('ss-activity-search', network)
        self.assertIn('ss-export', network)
        self.assertIn('feed-truth-save', network)
        self.assertIn('Revision History', network)
        self.assertIn('data-comment-hide', network)
        self.assertIn('Contract Image (optional)', network)
        self.assertIn('Attach Image (optional)', network)
        self.assertIn('/maps/night-city-v04-nightcityio.jpg', network)
        self.assertIn('gm-ops-search', network)
        self.assertIn('sl-collab-search', network)
        self.assertIn('admin-user-search', source)
        self.assertIn('openCommandPalette', source)
        self.assertIn('city-network-grid', source)
        self.assertIn('refreshShellDossiers', source)
        map_path = ROOT / 'app/static/maps/night-city-v04-nightcityio.jpg'
        self.assertTrue(map_path.is_file())
        self.assertEqual(server.image_info(map_path.read_bytes())[2:], (1920, 1920))


if __name__ == '__main__':
    unittest.main()
