import copy
import importlib.util
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('integrity_server', ROOT / 'app/server.py')
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class IntegritySecurityRegressionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'integrity.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        for username, display, role in (
            ('gm', 'Game Master', 'gm'),
            ('runner', 'Runner', 'player'),
            ('other', 'Other Player', 'player'),
        ):
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,1)',
                (username, display, 'x', 1 if role == 'gm' else 0, role))
        self.character_data = {
            'handle': 'V', 'role': 'Solo', 'role_rank': 4,
            'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}],
            'active_role': 'Solo',
            'stats': {
                'INT': 6, 'REF': 8, 'DEX': 8, 'TECH': 6, 'COOL': 6,
                'WILL': 6, 'LUCK': 5, 'MOVE': 6, 'BODY': 6, 'EMP': 5,
            },
            'skills': {}, 'inventory': [], 'cyberware': [], 'armor': {},
            'cash': 100, 'ip_available': 0, 'ip_total_earned': 0,
            'ip_total_spent': 0, 'luck_cur': 5, 'reputation': 0,
            'notes': '', 'public': True,
        }
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(2,1,?,1,1)',
            (json.dumps(self.character_data),))
        self.conn.commit()

        self.handler = object.__new__(server.Handler)
        self.current = self.user('runner')
        self.response = {}
        self.handler.current_user = lambda conn: self.current
        self.handler.send_json = lambda payload, status=200, cookies=None: self.response.update(
            payload=payload, status=status, cookies=cookies)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def user(self, username):
        return self.conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()

    @staticmethod
    def match(*values):
        pattern = '^' + '/'.join('(\\d+)' for _ in values) + '$'
        return re.match(pattern, '/'.join(str(value) for value in values))

    def call(self, method, match=None, body=None, query=None):
        self.response = {}
        method(self.handler, self.conn, query or {}, match, body or {})
        return self.response.get('payload')

    def create_persona_and_storyline(self):
        self.current = self.user('gm')
        persona = self.call(server.Handler.api_persona_create, body={
            'handle': 'secure-fixer', 'display_name': 'Secure Fixer',
            'access': 'shared', 'kind': 'person',
        })
        storyline = self.call(server.Handler.api_storyline_create, body={
            'title': 'Integrity Run', 'code_name': 'INTEGRITY',
        })
        return persona, storyline

    def create_contract(self, persona, storyline=None, capacity=0):
        self.current = self.user('gm')
        return self.call(server.Handler.api_contract_create, body={
            'title': 'Integrity Contract', 'status': 'open',
            'public_brief': 'Test the relay.', 'crew_capacity': capacity,
            'storyline_id': storyline['id'] if storyline else None,
            'participants': [{'persona_id': persona['id'], 'role_key': 'poster'}],
        })

    def test_full_character_put_cannot_replace_mechanics(self):
        forged = copy.deepcopy(self.character_data)
        forged['cash'] = 9_999_999
        forged['ip_available'] = 1_000_000
        forged['stats']['REF'] = 13
        forged['inventory'] = [{'key': 'forged', 'name': 'Forged item', 'qty': 99}]
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_save_character, self.match(1), {'data': forged})
        self.assertEqual(denied.exception.status, 400)

        stored = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertEqual(stored['cash'], 100)
        self.assertEqual(stored['ip_available'], 0)
        self.assertEqual(stored['stats']['REF'], 8)
        self.assertEqual(stored['inventory'], [])

        updated = self.call(server.Handler.api_save_character, self.match(1), {
            'patch': {'notes': 'Private campaign note', 'public': False},
        })
        self.assertEqual(updated['data']['notes'], 'Private campaign note')
        self.assertFalse(updated['public'])

        with self.assertRaises(server.ApiError) as cash_denied:
            self.call(server.Handler.api_character_resource, self.match(1), {
                'resource': 'cash', 'action': 'delta', 'value': 9_999_999,
            })
        self.assertEqual(cash_denied.exception.status, 403)
        with self.assertRaises(server.ApiError) as ip_denied:
            self.call(server.Handler.api_character_ip, self.match(1), {
                'amount': 1000, 'reason': 'self award',
            })
        self.assertEqual(ip_denied.exception.status, 403)

    def test_aftermath_rejects_negative_ip_before_writing(self):
        persona, storyline = self.create_persona_and_storyline()
        contract = self.create_contract(persona, storyline)
        self.current = self.user('runner')
        self.call(server.Handler.api_contract_join, self.match(contract['id']), {
            'character_id': 1,
        })
        self.current = self.user('gm')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_contract_aftermath, self.match(contract['id']), {
                'result': 'completed', 'author_persona_id': persona['id'],
                'headline': 'Invalid payout', 'body': 'Must roll back.',
                'rewards': [{'character_id': 1, 'cash': 0, 'ip': -1}],
            })
        self.assertEqual(denied.exception.status, 400)
        stored = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertEqual(stored['ip_available'], 0)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM feed_posts').fetchone()['n'], 0)
        self.assertEqual(
            self.conn.execute('SELECT status FROM contracts WHERE id=?', (contract['id'],)).fetchone()['status'],
            'open')

    def test_leave_targets_an_explicit_signup_when_user_has_two_characters(self):
        second = copy.deepcopy(self.character_data)
        second['handle'] = 'Second V'
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(2,1,?,1,1)',
            (json.dumps(second),))
        self.conn.commit()
        persona, _ = self.create_persona_and_storyline()
        contract = self.create_contract(persona)
        self.current = self.user('runner')
        first_join = self.call(server.Handler.api_contract_join, self.match(contract['id']), {
            'character_id': 1,
        })
        both = self.call(server.Handler.api_contract_join, self.match(contract['id']), {
            'character_id': 2,
        })
        self.assertEqual(len(both['my_signups']), 2)
        first_signup = next(item for item in first_join['my_signups'] if item['character_id'] == 1)

        left = self.call(server.Handler.api_contract_leave, self.match(contract['id']), {
            'signup_id': first_signup['id'],
        })
        self.assertEqual([item['character_id'] for item in left['my_signups']], [2])
        statuses = dict(self.conn.execute(
            'SELECT character_id,status FROM contract_signups WHERE contract_id=?',
            (contract['id'],)).fetchall())
        self.assertEqual(statuses, {1: 'withdrawn', 2: 'crew'})
        with self.assertRaises(server.ApiError) as ambiguous:
            self.call(server.Handler.api_contract_leave, self.match(contract['id']), {})
        self.assertEqual(ambiguous.exception.status, 400)

    def test_feed_links_require_editor_or_exact_crew_character(self):
        persona, storyline = self.create_persona_and_storyline()
        unrelated = self.call(server.Handler.api_storyline_create, body={
            'title': 'Unrelated Storyline', 'code_name': 'OTHER',
        })
        contract = self.create_contract(persona, storyline)
        self.current = self.user('runner')
        post_body = {
            'author_character_id': 1, 'format': 'short', 'body': 'False linkage.',
            'contract_id': contract['id'], 'storyline_id': storyline['id'],
        }
        with self.assertRaises(server.ApiError) as not_crew:
            self.call(server.Handler.api_feed_create, body=post_body)
        self.assertEqual(not_crew.exception.status, 403)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM feed_posts').fetchone()['n'], 0)

        self.call(server.Handler.api_contract_join, self.match(contract['id']), {'character_id': 1})
        linked = self.call(server.Handler.api_feed_create, body={
            **post_body, 'body': 'Crew report.',
        })
        self.assertEqual(linked['contract_id'], contract['id'])
        self.assertEqual(linked['storyline_id'], storyline['id'])

        with self.assertRaises(server.ApiError) as unrelated_story:
            self.call(server.Handler.api_feed_create, body={
                **post_body, 'body': 'Wrong storyline.',
                'storyline_id': unrelated['id'],
            })
        self.assertEqual(unrelated_story.exception.status, 403)

    def test_legacy_gets_obey_privacy_and_writes_are_disabled(self):
        self.conn.execute(
            "INSERT INTO news(author_id,title,body,created) VALUES(2,'Archived','Old post',1)")
        self.conn.execute(
            "INSERT INTO jobs(author_id,title,description,slots,status,created) "
            "VALUES(1,'Archived Job','Old contract',1,'open',1)")
        self.conn.execute(
            "INSERT INTO job_signups(job_id,user_id,char_name,note,created) "
            "VALUES(1,2,'V','Private note',1)")
        self.conn.commit()

        self.current = self.user('other')
        news = self.call(server.Handler.api_news)['news'][0]
        job = self.call(server.Handler.api_jobs)['jobs'][0]
        detail = self.call(server.Handler.api_job_detail, self.match(1))
        self.assertIsNone(news['author'])
        self.assertIsNone(job['author'])
        self.assertIsNone(detail['signups_list'][0]['user'])
        self.assertIsNone(detail['signups_list'][0]['user_id'])

        self.current = self.user('gm')
        owner_detail = self.call(server.Handler.api_job_detail, self.match(1))
        self.assertEqual(owner_detail['signups_list'][0]['user'], 'Runner')
        with self.assertRaises(server.ApiError) as legacy_write:
            self.call(server.Handler.api_jobs_create, body={'title': 'Bypass'})
        self.assertEqual(legacy_write.exception.status, 410)

    def test_invite_registration_is_hashed_limited_and_player_only(self):
        self.conn.execute("UPDATE users SET account_role='admin',is_gm=1 WHERE username='gm'")
        self.conn.commit()
        self.current = self.user('gm')
        created = self.call(server.Handler.api_admin_invite_create, body={
            'label': 'New player', 'max_uses': 1, 'expires_days': 7,
        })
        self.assertRegex(created['code'], r'^NCNET-[A-F0-9]{4}(?:-[A-F0-9]{4}){3}$')
        stored = self.conn.execute('SELECT * FROM registration_invites WHERE id=?',
                                   (created['id'],)).fetchone()
        self.assertNotEqual(stored['code_hash'], created['code'])
        self.assertNotIn(created['code'], stored['code_hash'])

        with mock.patch.dict(server.os.environ, {'CBPR_REGISTRATION_MODE': 'invite'}, clear=False):
            registered = self.call(server.Handler.api_register, body={
                'username': 'invited', 'display_name': 'Invited Runner',
                'password': 'longpass', 'invite_code': created['code'],
                'is_gm': True, 'account_role': 'admin',
            })
            self.assertEqual(registered['account_role'], 'player')
            self.assertFalse(registered['is_gm'])
            with self.assertRaises(server.ApiError) as reused:
                self.call(server.Handler.api_register, body={
                    'username': 'secondinvite', 'password': 'longpass',
                    'invite_code': created['code'],
                })
            self.assertEqual(reused.exception.status, 403)
            with self.assertRaises(server.ApiError) as short_password:
                self.call(server.Handler.api_register, body={
                    'username': 'shortpass', 'password': '1234567',
                    'invite_code': 'invalid',
                })
            self.assertEqual(short_password.exception.status, 400)

        invite_row = self.conn.execute('SELECT * FROM registration_invites WHERE id=?',
                                       (created['id'],)).fetchone()
        self.assertEqual(invite_row['uses'], 1)
        listed = self.call(server.Handler.api_admin_invites)['invites']
        self.assertFalse(next(item for item in listed if item['id'] == created['id'])['active'])

    def test_public_dossier_uses_configurable_allowlist_and_account_privacy(self):
        self.current = self.user('other')
        public = self.call(server.Handler.api_roster)['characters'][0]
        self.assertIsNone(public['owner_name'])
        self.assertIsNone(public['owner_id'])
        self.assertNotIn('cash', public['data'])
        self.assertNotIn('notes', public['data'])
        self.assertNotIn('player', public['data'])
        self.assertNotIn('stats', public['data'])
        self.assertNotIn('inventory', public['data'])
        self.assertEqual(public['derived'], {})

        self.current = self.user('runner')
        updated = self.call(server.Handler.api_save_character, self.match(1), {
            'patch': {'visibility': {'stats': True, 'equipment': True, 'combat': True}},
        })
        self.assertTrue(updated['data']['visibility']['stats'])
        self.assertTrue(updated['data']['visibility']['equipment'])

        self.current = self.user('other')
        visible = self.call(server.Handler.api_get_character, self.match(1))
        self.assertIn('stats', visible['data'])
        self.assertIn('inventory', visible['data'])
        self.assertTrue(visible['derived'])
        self.assertNotIn('cash', visible['data'])
        self.assertNotIn('notes', visible['data'])

        self.conn.execute('UPDATE users SET show_display_name=1 WHERE id=2')
        self.conn.commit()
        named = self.call(server.Handler.api_roster)['characters'][0]
        self.assertEqual(named['owner_name'], 'Runner')
        self.assertEqual(named['owner_id'], 2)

        media_id = 'c' * 32
        self.conn.execute(
            'INSERT INTO media(id,owner_id,kind,mime,filename,size,width,height,created) '
            "VALUES(?,2,'character_portrait','image/webp','missing.webp',100,100,100,1)",
            (media_id,))
        self.conn.commit()
        self.current = self.user('runner')
        self.call(server.Handler.api_save_character, self.match(1), {
            'patch': {'portrait_media_id': media_id, 'visibility': {'portrait': False}},
        })
        self.current = self.user('other')
        with self.assertRaises(server.ApiError) as private_portrait:
            self.call(server.Handler.api_media_get,
                      re.match(r'^([a-f0-9]{32})$', media_id))
        self.assertEqual(private_portrait.exception.status, 403)

    def test_production_install_is_loopback_https_only_and_login_route_is_unique(self):
        installer = (ROOT / 'deploy/install.sh').read_text(encoding='utf-8')
        nginx = (ROOT / 'deploy/nginx-cbpr.conf').read_text(encoding='utf-8')
        source = (ROOT / 'app/server.py').read_text(encoding='utf-8')
        self.assertIn("ap.add_argument('--host', default='127.0.0.1')", source)
        self.assertIn('--host 127.0.0.1', installer)
        self.assertIn('Environment=CBPR_SECURE_COOKIES=1', installer)
        self.assertIn('Environment=CBPR_REGISTRATION_MODE=invite', installer)
        self.assertIn('return 308 https://$host$request_uri', nginx)
        self.assertIn('listen 443 ssl http2', nginx)
        login_routes = [route for route in server.ROUTES
                        if route[0] == 'POST' and route[1].pattern == '^/api/login$']
        self.assertEqual(len(login_routes), 1)


if __name__ == '__main__':
    unittest.main()
