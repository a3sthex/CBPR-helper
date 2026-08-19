import importlib.util
import json
import re
import sqlite3
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('ncnet_core_server', ROOT / 'app/server.py')
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


class NCNetCoreFlowTests(unittest.TestCase):
    def test_quick_reference_sources_are_explicit(self):
        self.assertEqual(server.GENERAL_DV, [
            ['Simple', 9], ['Everyday', 13], ['Difficult', 15],
            ['Professional', 17], ['Heroic', 21], ['Incredible', 24], ['Legendary', 29],
        ])
        self.assertIn('p. 129', server.RULE_SOURCES['general_dv'])
        self.assertIn('Corebook', server.RULE_SOURCES['critical_injuries'])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        users = [
            ('admin', 'Admin', 'admin'), ('gm', 'GM', 'gm'),
            ('runner1', 'Runner One', 'player'), ('runner2', 'Runner Two', 'player'),
        ]
        for username, display, role in users:
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,?)',
                (username, display, 'x', 1 if role in ('gm', 'admin') else 0, role, 1))
        for owner, handle in ((3, 'V'), (4, 'K')):
            data = {
                'handle': handle, 'role': 'Solo', 'role_rank': 4,
                'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}],
                'active_role': 'Solo', 'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6},
                'skills': {}, 'inventory': [], 'cyberware': [], 'armor': {},
                'cash': 100, 'ip_available': 0, 'ip_total_earned': 0,
                'ip_total_spent': 0, 'luck_cur': 5, 'reputation': 0,
            }
            self.conn.execute(
                'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(?,1,?,1,1)',
                (owner, json.dumps(data)))
        self.conn.commit()
        self.handler = object.__new__(server.Handler)
        self.response = {}
        self.current = self.user('gm')
        self.handler.current_user = lambda conn: self.current
        self.handler.send_json = lambda payload, status=200, cookies=None: self.response.update(
            payload=payload, status=status, cookies=cookies)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def user(self, username):
        return self.conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()

    def call(self, method, *args):
        self.response = {}
        self.handler.send_json = lambda payload, status=200, cookies=None: self.response.update(
            payload=payload, status=status, cookies=cookies)
        method(self.handler, self.conn, *args)
        return self.response

    @staticmethod
    def match(*values):
        pattern = '^' + '/'.join('(\\d+)' for _ in values) + '$'
        return re.match(pattern, '/'.join(str(value) for value in values))

    def test_legacy_jobs_and_news_migrate_once_without_deletion(self):
        self.conn.execute(
            "INSERT INTO jobs(author_id,title,when_text,system,description,slots,status,created) "
            "VALUES(2,'Legacy Job','Saturday','Cyberpunk RED','Old briefing',1,'open',10)")
        self.conn.execute(
            "INSERT INTO job_signups(job_id,user_id,char_name,note,created) "
            "VALUES(1,3,'V','',11)")
        self.conn.execute(
            "INSERT INTO news(author_id,title,tag,body,created) "
            "VALUES(3,'Legacy Report','Watson','Old city report',12)")
        self.conn.commit()
        server.migrate_legacy_network_content(self.conn)
        server.migrate_legacy_network_content(self.conn)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM jobs').fetchone()['n'], 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM news').fetchone()['n'], 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM contracts WHERE legacy_job_id=1').fetchone()['n'], 1)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM feed_posts WHERE legacy_news_id=1').fetchone()['n'], 1)
        signup = self.conn.execute('SELECT * FROM contract_signups').fetchone()
        self.assertEqual(signup['character_id'], 1)
        self.assertEqual(signup['status'], 'crew')

    def test_persona_contract_feed_session_and_aftermath_flow(self):
        persona = self.call(server.Handler.api_persona_create, {}, None, {
            'handle': 'dex-fixer', 'display_name': 'Dex', 'access': 'shared',
            'kind': 'person', 'public_bio': 'A Night City fixer.',
        })['payload']
        self.assertEqual(persona['handle'], 'dex-fixer')

        storyline = self.call(server.Handler.api_storyline_create, {}, None, {
            'title': 'Watson Blackout', 'code_name': 'BLACKOUT',
            'public_summary': 'Watson goes dark.',
        })['payload']

        contract = self.call(server.Handler.api_contract_create, {}, None, {
            'title': 'Restore the Relay', 'teaser': 'Watson needs a crew.',
            'public_brief': 'Reach the relay and bring it online.',
            'classified_brief': 'The relay contains a trapped AI.',
            'status': 'open', 'district_id': 'watson', 'risk_level': 'high',
            'reward_mode': 'range', 'reward_min': 1000, 'reward_max': 2000,
            'crew_capacity': 1, 'storyline_id': storyline['id'],
            'participants': [{'persona_id': persona['id'], 'role_key': 'poster'}],
        })['payload']
        self.assertEqual(contract['status'], 'open')
        self.assertTrue(contract['has_classified_access'])

        self.current = self.user('runner1')
        joined = self.call(server.Handler.api_contract_join, {}, self.match(contract['id']), {
            'character_id': 1,
        })['payload']
        self.assertEqual(joined['my_signup']['status'], 'crew')
        self.assertEqual(joined['status'], 'crew_full')
        self.assertIn('classified_brief', joined)

        self.current = self.user('runner2')
        waitlisted = self.call(server.Handler.api_contract_join, {}, self.match(contract['id']), {
            'character_id': 2,
        })['payload']
        self.assertEqual(waitlisted['my_signup']['status'], 'waitlist')
        self.assertNotIn('classified_brief', waitlisted)

        self.current = self.user('runner1')
        self.call(server.Handler.api_contract_leave, {}, self.match(contract['id']), {})
        promoted = self.conn.execute(
            "SELECT * FROM contract_signups WHERE contract_id=? AND user_id=4",
            (contract['id'],)).fetchone()
        self.assertEqual(promoted['status'], 'crew')

        self.current = self.user('runner2')
        post = self.call(server.Handler.api_feed_create, {}, None, {
            'author_character_id': 2, 'format': 'short',
            'body': 'The relay is singing again.', 'district_id': 'watson',
            'contract_id': contract['id'], 'storyline_id': storyline['id'],
        })['payload']
        self.assertEqual(post['status'], 'published')
        self.assertEqual(post['author']['display_name'], 'K')

        self.current = self.user('runner1')
        comment = self.call(server.Handler.api_feed_comment_create, {}, self.match(post['id']), {
            'author_character_id': 1, 'body': 'Not for long.',
        })['payload']
        self.assertEqual(comment['body'], 'Not for long.')

        self.current = self.user('gm')
        session = self.call(server.Handler.api_session_create, {}, None, {
            'contract_id': contract['id'], 'title': 'Relay Run',
        })['payload']
        self.assertEqual(len(session['combatants']), 1)
        npc = self.call(server.Handler.api_session_combatant_create, {}, self.match(session['id']), {
            'name': 'Maelstrom Guard', 'hp_max': 30, 'sp_body': 7,
            'initiative': 12, 'visible': True,
        })['payload']
        self.call(server.Handler.api_session_combatant_update, {},
                  self.match(session['id'], npc['id']), {'hp_max': 30, 'hp_current': 20})
        changed = self.conn.execute('SELECT * FROM session_combatants WHERE id=?',
                                    (npc['id'],)).fetchone()
        self.assertEqual(changed['hp_current'], 20)

        aftermath = self.call(server.Handler.api_contract_aftermath, {}, self.match(contract['id']), {
            'result': 'completed', 'author_persona_id': persona['id'],
            'headline': 'Watson Relay Restored',
            'body': 'Local residents report that the grid is stable.',
            'rewards': [{'character_id': 2, 'cash': 500, 'ip': 20}],
        })['payload']
        self.assertEqual(aftermath['result'], 'completed')
        self.assertTrue(self.conn.execute('SELECT 1 FROM feed_posts WHERE id=?',
                                         (aftermath['post_id'],)).fetchone())
        character = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=2').fetchone()['data'])
        self.assertEqual(character['cash'], 600)
        self.assertEqual(character['ip_available'], 20)
        self.assertGreater(self.conn.execute('SELECT COUNT(*) n FROM character_ledger').fetchone()['n'], 0)
        self.assertGreater(self.conn.execute('SELECT COUNT(*) n FROM vk_outbox').fetchone()['n'], 0)


if __name__ == '__main__':
    unittest.main()
