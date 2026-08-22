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
        self.assertIn('orbital-air-space-center', server.NC_LOCATION_IDS)
        self.assertIn('badlands-near-pacifica', server.NC_LOCATION_IDS)
        self.assertEqual(server.clean_location_id('Westbrook-Japantown'), 'westbrook-japantown')
        with self.assertRaises(server.ApiError):
            server.clean_location_id('unknown-sector')

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
            'avatar_media_id': None, 'cover_media_id': None,
        })['payload']
        self.assertEqual(persona['handle'], 'dex-fixer')

        storyline = self.call(server.Handler.api_storyline_create, {}, None, {
            'title': 'Watson Blackout', 'code_name': 'BLACKOUT',
            'public_summary': 'Watson goes dark.',
        })['payload']
        timeline_event = self.call(server.Handler.api_storyline_timeline_create, {},
                                   self.match(storyline['id']), {
            'public_text': 'Grid instability reported.', 'event_at': 1000,
        })['payload']
        self.assertTrue(timeline_event['id'])
        with self.assertRaises(server.ApiError) as invalid_timeline_time:
            self.call(server.Handler.api_storyline_timeline_create, {},
                      self.match(storyline['id']), {
                          'public_text': 'Impossible timestamp', 'event_at': 'nan',
                      })
        self.assertEqual(invalid_timeline_time.exception.status, 400)

        self.current = self.user('admin')
        private_template = self.call(server.Handler.api_npc_template_create, {}, None, {
            'name': 'Admin Secret', 'access': 'private', 'data': {'hp_max': 10},
        })['payload']
        self.assertEqual(private_template['data']['hp_current'], 10)
        self.current = self.user('gm')
        with self.assertRaises(server.ApiError) as private_template_denied:
            self.call(server.Handler.api_npc_template_update, {},
                      self.match(private_template['id']), {'name': 'Stolen'})
        self.assertEqual(private_template_denied.exception.status, 403)
        self.assertNotIn(private_template['id'], [item['id'] for item in self.call(
            server.Handler.api_npc_templates, {}, None, {})['payload']['templates']])

        template = self.call(server.Handler.api_npc_template_create, {}, None, {
            'name': 'Maelstrom Guard', 'role': 'Boosterganger', 'access': 'shared',
            'data': {
                'hp_max': 30, 'hp_current': 30, 'sp_body': 7, 'sp_head': 7,
                'shield_max': 10, 'shield_current': 10,
                'ammo_max': 20, 'ammo_current': 20,
                'luck_max': 3, 'luck_current': 3, 'move': 5, 'initiative': 12,
                'conditions': ['Alert'], 'injuries': ['Damaged Ear'],
                'death_penalty': 1,
            },
        })['payload']
        updated_template = self.call(server.Handler.api_npc_template_update, {},
                                     self.match(template['id']), {
            'name': 'Maelstrom Guard', 'data': {'hp_max': 32, 'hp_current': 32},
        })['payload']
        self.assertEqual(updated_template['data']['hp_max'], 32)
        self.assertEqual(updated_template['data']['shield_max'], 10)
        cloned_template = self.call(server.Handler.api_npc_template_clone, {},
                                    self.match(template['id']), {})['payload']
        self.assertTrue(cloned_template['can_edit'])
        self.call(server.Handler.api_npc_template_delete, {}, self.match(template['id']), {})
        listed_templates = self.call(server.Handler.api_npc_templates, {}, None, {})['payload']['templates']
        self.assertEqual([item['id'] for item in listed_templates], [cloned_template['id']])

        contract = self.call(server.Handler.api_contract_create, {}, None, {
            'title': 'Restore the Relay', 'teaser': 'Watson needs a crew.',
            'public_brief': 'Reach the relay and bring it online.',
            'classified_brief': 'The relay contains a trapped AI.',
            'status': 'open', 'district_id': 'watson-little-china', 'risk_level': 'high',
            'reward_mode': 'range', 'reward_min': 1000, 'reward_max': 2000,
            'crew_capacity': 1, 'storyline_id': storyline['id'],
            'cover_media_id': None,
            'participants': [{'persona_id': persona['id'], 'role_key': 'poster'}],
        })['payload']
        self.assertEqual(contract['status'], 'open')
        self.assertEqual(contract['district_id'], 'watson-little-china')
        self.assertIsNone(contract['cover_media_id'])
        self.assertTrue(contract['has_classified_access'])

        self.current = self.user('runner1')
        joined = self.call(server.Handler.api_contract_join, {}, self.match(contract['id']), {
            'character_id': 1,
        })['payload']
        self.assertEqual(joined['my_signups'][0]['status'], 'crew')
        self.assertEqual(joined['status'], 'crew_full')
        self.assertIn('classified_brief', joined)

        self.current = self.user('runner2')
        char2 = 2
        waitlisted = self.call(server.Handler.api_contract_join, {}, self.match(contract['id']), {
            'character_id': char2,
        })['payload']
        self.assertEqual(waitlisted['my_signups'][0]['status'], 'waitlist')
        self.assertNotIn('classified_brief', waitlisted)

        self.current = self.user('runner1')
        self.call(server.Handler.api_contract_leave, {}, self.match(contract['id']), {
            'signup_id': joined['my_signups'][0]['id'],
        })
        promoted = self.conn.execute(
            "SELECT * FROM contract_signups WHERE contract_id=? AND user_id=4",
            (contract['id'],)).fetchone()
        self.assertEqual(promoted['status'], 'crew')

        self.current = self.user('runner2')
        post = self.call(server.Handler.api_feed_create, {}, None, {
            'author_character_id': 2, 'format': 'short',
            'body': 'The relay is singing again.', 'district_id': 'watson-kabuki',
            'contract_id': contract['id'], 'storyline_id': storyline['id'],
        })['payload']
        self.assertEqual(post['status'], 'published')
        self.assertEqual(post['district_id'], 'watson-kabuki')
        self.assertIsNone(post['image_media_id'])
        self.assertEqual(post['author']['display_name'], 'K')

        self.current = self.user('runner1')
        comment = self.call(server.Handler.api_feed_comment_create, {}, self.match(post['id']), {
            'author_character_id': 1, 'body': 'Not for long.',
        })['payload']
        self.assertEqual(comment['body'], 'Not for long.')

        self.current = self.user('runner2')
        feed_media_id = 'b' * 32
        self.conn.execute(
            'INSERT INTO media(id,owner_id,kind,mime,filename,size,width,height,created) '
            "VALUES(?,4,'feed_image','image/webp','feed.webp',100,100,100,1)",
            (feed_media_id,))
        self.conn.commit()
        edited_post = self.call(server.Handler.api_feed_update, {}, self.match(post['id']), {
            'format': 'short', 'body': 'The relay is singing clearly again.',
            'lead': 'Signal restored', 'event_at': 12345,
            'image_media_id': feed_media_id, 'status': 'published',
        })['payload']
        self.assertEqual(edited_post['event_at'], 12345)
        attached_feed_media = self.conn.execute('SELECT * FROM media WHERE id=?',
                                                (feed_media_id,)).fetchone()
        self.assertEqual((attached_feed_media['attached_type'], attached_feed_media['attached_id']),
                         ('feed_post', post['id']))

        self.current = self.user('gm')
        truth = self.call(server.Handler.api_feed_truth_update, {}, self.match(post['id']), {
            'truth_status': 'partially_true', 'reason': 'Known omissions',
        })['payload']
        self.assertEqual(truth['truth_status'], 'partially_true')
        self.call(server.Handler.api_feed_comment_hide, {},
                  self.match(post['id'], comment['id']), {'reason': 'Operational security'})
        gm_post = self.call(server.Handler.api_feed_detail, {}, self.match(post['id']), {})['payload']
        self.assertEqual(gm_post['truth_status'], 'partially_true')
        self.assertTrue(any(revision['action'] == 'truth' for revision in gm_post['revisions']))

        self.current = self.user('runner2')
        owner_post = self.call(server.Handler.api_feed_detail, {}, self.match(post['id']), {})['payload']
        self.assertNotIn('truth_status', owner_post)
        self.assertTrue(any(revision['action'] == 'update' for revision in owner_post['revisions']))
        self.assertFalse(any(revision['action'] == 'truth' for revision in owner_post['revisions']))

        self.current = self.user('runner1')
        player_post = self.call(server.Handler.api_feed_detail, {}, self.match(post['id']), {})['payload']
        hidden_comment = next(item for item in player_post['comments'] if item['id'] == comment['id'])
        self.assertTrue(hidden_comment['hidden'])
        self.assertEqual(hidden_comment['hidden_reason'], 'Operational security')

        self.current = self.user('gm')
        self.call(server.Handler.api_feed_hide, {}, self.match(post['id']), {
            'reason': 'Temporary operational blackout',
        })
        self.current = self.user('runner2')
        moderation_locked = self.call(server.Handler.api_feed_update, {}, self.match(post['id']), {
            'format': 'short', 'body': 'Attempted republication', 'status': 'published',
        })['payload']
        self.assertEqual(moderation_locked['status'], 'hidden')

        self.current = self.user('gm')
        session = self.call(server.Handler.api_session_create, {}, None, {
            'contract_id': contract['id'], 'title': 'Relay Run',
        })['payload']
        self.assertEqual(len(session['combatants']), 1)
        npc = self.call(server.Handler.api_session_combatant_create, {}, self.match(session['id']), {
            'template_id': cloned_template['id'], 'name': 'Maelstrom Guard',
        })['payload']
        self.call(server.Handler.api_session_combatant_update, {},
                  self.match(session['id'], npc['id']), {
                      'hp_max': 32, 'hp_current': 20,
                      'shield_max': 10, 'shield_current': 8,
                      'ammo_max': 20, 'ammo_current': 17,
                      'luck_max': 3, 'luck_current': 2,
                  })
        changed = self.conn.execute('SELECT * FROM session_combatants WHERE id=?',
                                    (npc['id'],)).fetchone()
        self.assertEqual(changed['hp_current'], 20)
        session_detail = self.call(server.Handler.api_session_detail, {},
                                   self.match(session['id']), {})['payload']
        self.assertEqual([item['id'] for item in session_detail['combatants']], [npc['id'], 1])
        self.assertFalse(session_detail['combatants'][0]['active'])
        self.assertTrue(session_detail['combatants'][1]['active'])
        self.assertEqual(session_detail['combatants'][0]['shield_current'], 8)
        self.assertEqual(session_detail['combatants'][0]['ammo_current'], 17)
        self.assertEqual(session_detail['combatants'][0]['luck_current'], 2)
        self.assertEqual(session_detail['combatants'][0]['injuries'], ['Damaged Ear'])
        self.call(server.Handler.api_session_update, {}, self.match(session['id']), {
            'round': 1, 'active_turn': 0,
            'player_view_config': {
                'show_initiative': False, 'show_ally_hp': True,
                'show_armor': False, 'show_shield': False, 'show_ammo': False,
                'show_move': True, 'show_luck': True,
                'show_conditions': True, 'show_injuries': True,
            },
        })
        self.current = self.user('runner2')
        player_view = self.call(server.Handler.api_session_player_view, {},
                                self.match(session['id']), {})['payload']
        self.assertTrue(player_view['combatants'][0]['active'])
        self.assertNotIn('initiative', player_view['combatants'][0])
        self.assertNotIn('sp_body', player_view['combatants'][0])
        self.assertNotIn('shield_current', player_view['combatants'][0])
        self.assertNotIn('ammo_current', player_view['combatants'][0])
        self.assertEqual(player_view['combatants'][0]['move'], 5)
        self.assertEqual(player_view['combatants'][0]['luck_current'], 2)
        self.assertEqual(player_view['combatants'][0]['injuries'], ['Damaged Ear'])
        self.assertNotIn('secret', player_view['combatants'][0])
        self.assertNotIn('notes', player_view)

        self.current = self.user('gm')
        activity_detail = self.call(server.Handler.api_session_detail, {},
                                    self.match(session['id']), {})['payload']
        self.assertGreaterEqual(len(activity_detail['activity']), 3)
        self.assertNotIn('before_json', activity_detail['activity'][0])
        session_event = next(item for item in activity_detail['activity']
                             if item['event_type'] == 'session_update')
        self.assertTrue(any(change['field'] == 'round' for change in session_event['changes']))
        combatant_event = next(item for item in activity_detail['activity']
                               if item['event_type'] == 'combatant_update')
        self.assertTrue(any(change['field'] == 'hp_current'
                            for change in combatant_event['changes']))
        stored_session_event = self.conn.execute(
            "SELECT before_json FROM session_activity WHERE event_type='session_update' "
            'ORDER BY id DESC LIMIT 1').fetchone()
        self.assertNotIn('activity', json.loads(stored_session_event['before_json']))

        aftermath_body = {
            'result': 'completed', 'author_persona_id': persona['id'],
            'headline': 'Watson Relay Restored',
            'body': 'Local residents report that the grid is stable.',
            'rewards': [{'character_id': 2, 'cash': 500, 'ip': 20}],
        }
        aftermath = self.call(server.Handler.api_contract_aftermath, {},
                              self.match(contract['id']), aftermath_body)['payload']
        self.assertEqual(aftermath['result'], 'completed')
        with self.assertRaises(server.ApiError) as duplicate_aftermath:
            self.call(server.Handler.api_contract_aftermath, {},
                      self.match(contract['id']), aftermath_body)
        self.assertEqual(duplicate_aftermath.exception.status, 409)
        self.assertTrue(self.conn.execute('SELECT 1 FROM feed_posts WHERE id=?',
                                         (aftermath['post_id'],)).fetchone())
        character = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=2').fetchone()['data'])
        self.assertEqual(character['cash'], 600)
        self.assertEqual(character['ip_available'], 20)
        self.assertGreater(self.conn.execute('SELECT COUNT(*) n FROM character_ledger').fetchone()['n'], 0)
        self.assertGreater(self.conn.execute('SELECT COUNT(*) n FROM vk_outbox').fetchone()['n'], 0)

        self.current = self.user('runner2')
        with self.assertRaises(server.ApiError) as terminal_leave:
            self.call(server.Handler.api_contract_leave, {}, self.match(contract['id']), {
                'character_id': char2,
            })
        self.assertEqual(terminal_leave.exception.status, 409)
        archived = self.call(server.Handler.api_delete_character, {}, self.match(char2), {})['payload']
        self.assertTrue(archived['archived'])
        kept = self.conn.execute('SELECT * FROM characters WHERE id=?', (char2,)).fetchone()
        self.assertTrue(json.loads(kept['data'])['archived'])
        self.assertFalse(kept['public'])
        historical_signup = self.conn.execute(
            'SELECT status FROM contract_signups WHERE contract_id=? AND character_id=?',
            (contract['id'], char2)).fetchone()
        self.assertEqual(historical_signup['status'], 'crew')
        with self.assertRaises(server.ApiError) as readonly:
            self.call(server.Handler.api_character_resource, {}, self.match(char2), {
                'resource': 'hp', 'value': -1,
            })
        self.assertEqual(readonly.exception.status, 409)
        self.current = self.user('gm')
        with self.assertRaises(server.ApiError) as payroll_readonly:
            self.call(server.Handler.api_payroll, {}, None, {
                'char_id': char2, 'amount': 100,
            })
        self.assertEqual(payroll_readonly.exception.status, 409)
        self.current = self.user('runner2')
        post_after_archive = self.call(server.Handler.api_feed_detail, {}, self.match(post['id']), {})['payload']
        self.assertEqual(post_after_archive['author']['display_name'], 'K')

    def test_campaign_clock_gm_advance_and_player_denied(self):
        server.ensure_campaign_clock(self.conn)
        self.current = self.user('gm')
        before = server.campaign_now(self.conn)
        payload = self.call(server.Handler.api_campaign_clock_advance, {}, None, {
            'advance': {'days': 2}, 'reason': 'Downtime passed'})
        self.assertEqual(payload['status'], 200)
        after = server.campaign_now(self.conn)
        self.assertAlmostEqual(after - before, 2 * 86400, delta=5)
        audit = self.conn.execute('SELECT COUNT(*) n FROM campaign_clock_audit').fetchone()['n']
        self.assertEqual(audit, 1)
        self.current = self.user('runner1')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_campaign_clock_advance, {}, None, {
                'advance': {'days': 1}, 'reason': 'Cheat'})
        self.assertEqual(denied.exception.status, 403)

    def test_campaign_clock_get_exposes_pending_for_gm(self):
        server.ensure_campaign_clock(self.conn)
        self.current = self.user('gm')
        payload = self.call(server.Handler.api_campaign_clock, {}, None, {})['payload']
        self.assertIn('pending', payload)
        self.assertIn('campaign_time', payload)
        self.current = self.user('runner1')
        player_payload = self.call(server.Handler.api_campaign_clock, {}, None, {})['payload']
        self.assertNotIn('pending', player_payload)



class TechMakerFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        self.conn.execute(
            'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
            "VALUES('runner1','Runner One','x',0,'player',1)")
        self.conn.commit()
        self.weapon_id = '1' * 32
        data = {
            'handle': 'V', 'role': 'Tech', 'role_rank': 4,
            'roles': [{'name': 'Tech', 'rank': 4, 'primary': True,
                       'setup': {'field': 2, 'upgrade': 2, 'fabrication': 2, 'invention': 2}}],
            'active_role': 'Tech',
            'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6},
            'skills': {}, 'cyberware': [], 'armor': {},
            'cash': 100, 'ip_available': 0, 'ip_total_earned': 0,
            'ip_total_spent': 0, 'luck_cur': 5, 'reputation': 0,
            'inventory': [{
                'key': 'guns-0', 'catalog_item_id': 'guns-0',
                'instance_id': self.weapon_id, 'cat': 'guns',
                'name': 'Medium Pistol', 'qty': 1, 'state': 'carried',
                'mechanics': {'type': 'Medium Pistol', 'skill': 'Handgun',
                              'damage': {'notation': '2d6'}, 'magazine': 12,
                              'concealable': 'YES'},
            }],
        }
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(1,1,?,1,1)',
            (json.dumps(data),))
        self.conn.commit()
        self.handler = object.__new__(server.Handler)
        self.response = {}
        self.current = self.user('runner1')
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
        return re.match('^' + '/'.join('(\\d+)' for _ in values) + '$',
                        '/'.join(str(value) for value in values))

    def test_create_applies_effect_and_remove_clears_it(self):
        self.call(server.Handler.api_character_tech_maker_create, {}, self.match(1), {
            'revision': 0, 'name': 'Calibrated', 'tech_name': 'Vee',
            'host_instance_id': self.weapon_id, 'maker_specialty': 'upgrade',
            'effect': {'target': 'weapon.attack_check', 'operation': 'add', 'value': 1},
            'manual_confirm': True, 'reason': 'Upgrade Expertise at the table',
        })
        payload = self.response['payload']
        mod_id = payload['modification_id']
        character = payload['character']
        self.assertIn(mod_id, character['data']['tech_maker_state']['modifications'])
        weapon = character['derived']['effective_weapons'][self.weapon_id]
        self.assertEqual(weapon['attack_modifier'], 1)
        self.assertEqual(weapon['effective']['magazine'], 12)

        # Duplicate effect on the same host/target is blocked.
        with self.assertRaises(server.ApiError) as duplicate:
            self.call(server.Handler.api_character_tech_maker_create, {}, self.match(1), {
                'revision': character['revision'], 'name': 'Second', 'tech_name': 'Vee',
                'host_instance_id': self.weapon_id, 'maker_specialty': 'upgrade',
                'effect': {'target': 'weapon.attack_check', 'operation': 'add', 'value': 1},
                'manual_confirm': True, 'reason': 'Upgrade Expertise at the table',
            })
        self.assertEqual(duplicate.exception.status, 409)

        action_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{mod_id}')
        self.call(server.Handler.api_character_tech_maker_action, {}, action_match, {
            'revision': character['revision'], 'action': 'remove',
            'reason': 'Removed during downtime',
        })
        removed = self.response['payload']['character']
        self.assertFalse(
            removed['data']['tech_maker_state']['modifications'][mod_id]['active'])
        weapon_after = removed['derived']['effective_weapons'][self.weapon_id]
        self.assertEqual(weapon_after['attack_modifier'], 0)

    def test_requires_tech_role_and_allowlisted_effect(self):
        with self.assertRaises(server.ApiError) as bad_effect:
            self.call(server.Handler.api_character_tech_maker_create, {}, self.match(1), {
                'revision': 0, 'name': 'Bad', 'tech_name': 'Vee',
                'host_instance_id': self.weapon_id, 'maker_specialty': 'upgrade',
                'effect': {'target': 'weapon.damage', 'operation': 'set', 'value': '10d6'},
                'manual_confirm': True, 'reason': 'Upgrade Expertise at the table',
            })
        self.assertEqual(bad_effect.exception.status, 400)

        with self.assertRaises(server.ApiError) as missing_confirm:
            self.call(server.Handler.api_character_tech_maker_create, {}, self.match(1), {
                'revision': 0, 'name': 'NoConfirm', 'tech_name': 'Vee',
                'host_instance_id': self.weapon_id, 'maker_specialty': 'upgrade',
                'effect': {'target': 'weapon.attack_check', 'operation': 'add', 'value': 1},
                'reason': 'Upgrade Expertise at the table',
            })
        self.assertEqual(missing_confirm.exception.status, 409)

    def test_fabricate_blueprint_and_invention(self):
        # Blueprint fabrication deducts material cost and creates a carried item.
        self.call(server.Handler.api_character_tech_maker_fabricate, {}, self.match(1), {
            'revision': 0, 'name': 'Custom Pistol', 'tech_name': 'Vee',
            'blueprint_catalog_id': 'guns-0', 'maker_specialty': 'fabrication',
            'qty': 2, 'material_cost': 100, 'manual_confirm': True,
            'reason': 'Fabrication Expertise at the table',
        })
        payload = self.response['payload']
        character = payload['character']
        inv = character['data']['inventory']
        crafted = [item for item in inv if item.get('acquisition_source') == 'crafted']
        self.assertEqual(len(crafted), 2)
        self.assertEqual(character['data']['cash'], 0)
        fabrications = character['derived']['tech_maker']['fabrications']
        self.assertEqual(fabrications[0]['blueprint_catalog_id'], 'guns-0')
        self.assertEqual(fabrications[0]['qty'], 2)

        # Invention without a blueprint creates a custom item.
        self.call(server.Handler.api_character_tech_maker_fabricate, {}, self.match(1), {
            'revision': character['revision'], 'name': 'Boom Gadget', 'tech_name': 'Vee',
            'maker_specialty': 'invention', 'category': 'custom',
            'description': 'A one-off prototype.', 'qty': 1, 'material_cost': 0,
            'manual_confirm': True, 'reason': 'Invention Expertise at the table',
        })
        invented = self.response['payload']['character']['data']['inventory']
        custom = [item for item in invented if item.get('is_custom')]
        self.assertEqual(len(custom), 1)
        self.assertEqual(custom[0]['custom_name'], 'Boom Gadget')

    def test_fabricate_gates_on_specialty_and_blueprint(self):
        # Fabrication requires a blueprint.
        with self.assertRaises(server.ApiError) as no_blueprint:
            self.call(server.Handler.api_character_tech_maker_fabricate, {}, self.match(1), {
                'revision': 0, 'name': 'Ghost', 'tech_name': 'Vee',
                'maker_specialty': 'fabrication', 'manual_confirm': True,
                'reason': 'Fabrication Expertise at the table',
            })
        self.assertEqual(no_blueprint.exception.status, 400)
        # A blueprint cannot be run under invention.
        with self.assertRaises(server.ApiError) as wrong_specialty:
            self.call(server.Handler.api_character_tech_maker_fabricate, {}, self.match(1), {
                'revision': 0, 'name': 'Ghost', 'tech_name': 'Vee',
                'blueprint_catalog_id': 'guns-0', 'maker_specialty': 'invention',
                'manual_confirm': True, 'reason': 'Invention Expertise at the table',
            })
        self.assertEqual(wrong_specialty.exception.status, 400)


class CrewStashFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        for username, display, role in (('gm', 'GM', 'gm'),
                                        ('runner1', 'Runner One', 'player'),
                                        ('runner2', 'Runner Two', 'player')):
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,?)',
                (username, display, 'x', 1 if role in ('gm', 'admin') else 0, role, 1))
        self.weapon_id = 'a' * 32
        self.ammo_id = 'b' * 32
        self.grenade_id = 'c' * 32
        weapon = {
            'key': 'guns-0', 'catalog_item_id': 'guns-0', 'instance_id': self.weapon_id,
            'cat': 'guns', 'name': 'Medium Pistol', 'qty': 1, 'state': 'carried',
            'mechanics': {'type': 'Medium Pistol', 'skill': 'Handgun',
                          'damage': {'notation': '2d6'}, 'magazine': 12,
                          'concealable': 'YES'},
        }
        ammo = {
            'key': 'ammo-0', 'catalog_item_id': 'ammo-0', 'instance_id': self.ammo_id,
            'cat': 'ammo', 'name': 'Basic Handgun Ammo', 'qty': 3, 'state': 'carried',
            'mechanics': {'quantity_per_purchase': 10}, 'ammo_rounds': 30,
        }
        base = {
            'handle': 'V', 'role': 'Solo', 'role_rank': 4,
            'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}], 'active_role': 'Solo',
            'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6}, 'skills': {},
            'inventory': [weapon, ammo], 'cyberware': [], 'armor': {},
            'cash': 100, 'ip_available': 0, 'ip_total_earned': 0,
            'ip_total_spent': 0, 'luck_cur': 5, 'reputation': 0,
        }
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(2,1,?,1,1)',
            (json.dumps(base),))
        k = dict(base)
        k['handle'] = 'K'
        k['inventory'] = [{
            'key': 'grenade-0', 'catalog_item_id': 'grenade-0', 'instance_id': self.grenade_id,
            'cat': 'grenades', 'name': 'Frag Grenade', 'qty': 1, 'state': 'carried',
        }]
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(3,1,?,1,1)',
            (json.dumps(k),))
        self.conn.commit()
        server.persist_character_item_instances(
            self.conn, 1, base, 'test_seed', prune=True)
        server.persist_character_item_instances(
            self.conn, 2, k, 'test_seed', prune=True)
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

    def char_data(self, char_id):
        return json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=?', (char_id,)).fetchone()['data'])

    def revision(self, char_id):
        return self.conn.execute(
            'SELECT revision FROM characters WHERE id=?', (char_id,)).fetchone()['revision']

    def transfer(self, char_id, instance_id, body):
        self.current = self.user(body.pop('_as', 'gm'))
        return self.call(server.Handler.api_character_item_transfer, {},
                         self.transfer_match(char_id, instance_id), body)

    @staticmethod
    def transfer_match(char_id, instance_id):
        return re.match(r'^(\d+)/([a-f0-9]{32})$', f'{char_id}/{instance_id}')

    def test_give_stash_take_roundtrip(self):
        self.current = self.user('gm')
        self.transfer(1, self.weapon_id, {
            'revision': self.revision(1), 'action': 'give', 'to_char_id': 2,
            'notes': 'hand it over', '_as': 'gm',
        })
        self.assertEqual(self.response['status'], 200)
        self.assertFalse(any(i['instance_id'] == self.weapon_id
                             for i in self.char_data(1)['inventory']))
        self.assertTrue(any(i['instance_id'] == self.weapon_id
                            for i in self.char_data(2)['inventory']))
        # K stashes the weapon.
        self.transfer(2, self.weapon_id, {
            'revision': self.revision(2), 'action': 'stash', 'notes': 'pool it', '_as': 'gm',
        })
        stash = server.crew_stash_payload(self.conn)
        self.assertEqual(len(stash), 1)
        self.assertEqual(stash[0]['instance_id'], self.weapon_id)
        # V takes it back from the stash.
        self.call(server.Handler.api_crew_stash_take, {}, None, {
            'char_id': 1, 'instance_id': self.weapon_id, 'notes': 'mine again',
        })
        self.assertEqual(self.response['status'], 200)
        self.assertTrue(any(i['instance_id'] == self.weapon_id
                            for i in self.char_data(1)['inventory']))
        self.assertEqual(len(server.crew_stash_payload(self.conn)), 0)
        history = server.item_transfer_history(self.conn, self.weapon_id)
        kinds = [entry['kind'] for entry in history]
        self.assertEqual(kinds, ['take', 'stash', 'give'])

    def test_split_stack_and_partial_stash(self):
        self.current = self.user('gm')
        self.transfer(1, self.ammo_id, {
            'revision': self.revision(1), 'action': 'stash', 'quantity': 1,
            'notes': 'pool one pack', '_as': 'gm',
        })
        self.assertEqual(self.response['status'], 200)
        stash = server.crew_stash_payload(self.conn)
        self.assertEqual(stash[0]['item']['qty'], 1)
        remaining = next(i for i in self.char_data(1)['inventory']
                         if i['cat'] == 'ammo')
        self.assertEqual(remaining['qty'], 2)
        self.assertNotEqual(stash[0]['instance_id'], self.ammo_id)

    def test_loan_return_and_recall(self):
        self.current = self.user('gm')
        self.transfer(1, self.weapon_id, {
            'revision': self.revision(1), 'action': 'loan', 'to_char_id': 2,
            'notes': 'borrow for the run', '_as': 'gm',
        })
        self.assertEqual(self.response['status'], 200)
        loans = server.character_open_loans(self.conn, 1)
        self.assertEqual(len(loans), 1)
        self.assertEqual(loans[0]['borrower_character_id'], 2)
        # Borrower returns it.
        self.transfer(2, self.weapon_id, {
            'revision': self.revision(2), 'action': 'return', 'notes': 'thanks', '_as': 'gm',
        })
        self.assertEqual(self.response['status'], 200)
        self.assertEqual(len(server.character_open_loans(self.conn, 1)), 0)
        self.assertTrue(any(i['instance_id'] == self.weapon_id
                            for i in self.char_data(1)['inventory']))
        # Loan again, then the owner recalls from the borrower.
        self.transfer(1, self.weapon_id, {
            'revision': self.revision(1), 'action': 'loan', 'to_char_id': 2,
            'notes': 'once more', '_as': 'gm',
        })
        self.transfer(1, self.weapon_id, {
            'revision': self.revision(1), 'action': 'recall', 'notes': 'need it back',
            '_as': 'gm',
        })
        self.assertEqual(self.response['status'], 200)
        self.assertFalse(any(i['instance_id'] == self.weapon_id
                             for i in self.char_data(2)['inventory']))
        self.assertTrue(any(i['instance_id'] == self.weapon_id
                            for i in self.char_data(1)['inventory']))

    def test_trade_two_items(self):
        self.current = self.user('gm')
        self.transfer(1, self.weapon_id, {
            'revision': self.revision(1), 'action': 'trade', 'to_char_id': 2,
            'to_instance_id': self.grenade_id, 'to_revision': self.revision(2),
            'notes': 'pistol for a grenade', '_as': 'gm',
        })
        self.assertEqual(self.response['status'], 200)
        self.assertTrue(any(i['instance_id'] == self.grenade_id
                            for i in self.char_data(1)['inventory']))
        self.assertTrue(any(i['instance_id'] == self.weapon_id
                            for i in self.char_data(2)['inventory']))

    def test_player_cannot_transfer_other_character_item(self):
        self.current = self.user('runner2')
        with self.assertRaises(server.ApiError) as denied:
            self.transfer(1, self.weapon_id, {
                'revision': self.revision(1), 'action': 'give', 'to_char_id': 2,
                'notes': 'sneaky', '_as': 'runner2',
            })
        self.assertEqual(denied.exception.status, 403)

    def test_equipped_item_cannot_be_transferred(self):
        self.current = self.user('gm')
        data = self.char_data(1)
        for item in data['inventory']:
            if item['instance_id'] == self.weapon_id:
                item['state'] = 'equipped'
        self.conn.execute('UPDATE characters SET data=? WHERE id=?',
                          (json.dumps(data), 1))
        self.conn.commit()
        with self.assertRaises(server.ApiError) as blocked:
            self.transfer(1, self.weapon_id, {
                'revision': self.revision(1), 'action': 'give', 'to_char_id': 2,
                'notes': 'nope', '_as': 'gm',
            })
        self.assertEqual(blocked.exception.status, 409)


class CharacterImportFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        self.conn.execute(
            'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
            "VALUES('runner1','Runner One','x',0,'player',1)")
        self.conn.commit()
        self.handler = object.__new__(server.Handler)
        self.response = {}
        self.current = self.user('runner1')
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

    def portable(self):
        return {
            'handle': 'Imported V', 'role': 'Solo', 'role_rank': 4,
            'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}],
            'active_role': 'Solo',
            'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6,
                      'DEX': 7, 'REF': 7, 'TECH': 4, 'INT': 4, 'COOL': 4, 'EMP': 5},
            'skills': {'Handgun': 6, 'Evasion': 4, 'Language (Streetslang)': 2,
                       'Local Expert (Watson)': 2},
            'native_language': 'Streetslang',
            'inventory': [{
                'key': 'guns-0', 'catalog_item_id': 'guns-0', 'instance_id': 'a' * 32,
                'cat': 'guns', 'name': 'Medium Pistol', 'qty': 1, 'state': 'carried',
                'price': 50,
            }],
            'cyberware': [], 'armor': {},
            'weapon_state': {'a' * 32: {'magazine': 2, 'magazine_max': 12}},
            'cash': 200, 'ip_available': 5, 'ip_total_earned': 5,
            'ip_total_spent': 0, 'reputation': 1, 'luck_cur': 5,
        }

    def test_import_creates_owned_private_character(self):
        self.current = self.user('runner1')
        payload = self.call(server.Handler.api_character_import, {}, None, {
            'data': self.portable(),
        })
        self.assertEqual(payload['status'], 201)
        character = payload['payload']
        self.assertEqual(character['owner_id'], 1)
        self.assertEqual(character['data']['handle'], 'Imported V')
        self.assertFalse(character['data'].get('public'))
        self.assertNotIn('armor_tech_state', character['data'])
        instances = self.conn.execute(
            'SELECT * FROM item_instances WHERE character_id=?', (character['id'],)).fetchall()
        self.assertEqual(len(instances), 1)
        ledger = self.conn.execute(
            'SELECT COUNT(*) n FROM character_ledger WHERE character_id=? '
            "AND reason='Character imported from JSON'",
            (character['id'],)).fetchone()['n']
        self.assertGreaterEqual(ledger, 1)
        # Runtime state resets: the imported weapon starts with a fresh magazine.
        weapon = next(i for i in character['data']['inventory'] if i['cat'] == 'guns')
        state = character['data']['weapon_state'][weapon['instance_id']]
        self.assertEqual(state['magazine'], state['magazine_max'])

    def test_import_requires_login(self):
        self.current = None
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_character_import, {}, None, {'data': self.portable()})
        self.assertEqual(denied.exception.status, 401)

    def test_import_rejects_malformed_payload(self):
        self.current = self.user('runner1')
        with self.assertRaises(server.ApiError) as bad:
            self.call(server.Handler.api_character_import, {}, None, {'data': {'handle': ''}})
        self.assertEqual(bad.exception.status, 400)


if __name__ == '__main__':
    unittest.main()


class MarketStockFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        for username, display, role in (('gm', 'GM', 'gm'),
                                        ('runner1', 'Runner One', 'player'),
                                        ('runner2', 'Runner Two', 'player')):
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,?)',
                (username, display, 'x', 1 if role in ('gm', 'admin') else 0, role, 1))
        base = {
            'handle': 'V', 'role': 'Solo', 'role_rank': 4,
            'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}], 'active_role': 'Solo',
            'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6}, 'skills': {},
            'inventory': [], 'cyberware': [], 'armor': {},
            'cash': 100000, 'ip_available': 0, 'ip_total_earned': 0,
            'ip_total_spent': 0, 'luck_cur': 5, 'reputation': 0,
        }
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(2,1,?,1,1)',
            (json.dumps(dict(base)),))
        k = dict(base)
        k['handle'] = 'K'
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(3,1,?,1,1)',
            (json.dumps(k),))
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

    def market_item(self):
        return server.night_market()['items'][0]

    def seed_stock(self, item, remaining):
        now = server.time.time()
        self.conn.execute(
            'INSERT OR REPLACE INTO market_stock(market_day,vendor_id,item_id,'
            'stock_initial,stock_remaining,reserved_character_id,reserved_note,'
            'created,updated) VALUES(?,?,?,?,?,NULL,\'\',?,?)',
            (server.nm_day(), item['vendor_id'], item['id'],
             remaining, remaining, now, now))
        self.conn.commit()

    def char_cash(self, char_id):
        return json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=?', (char_id,)).fetchone()['data'])['cash']

    def test_buy_decrements_stock_then_sells_out(self):
        item = self.market_item()
        self.seed_stock(item, 2)
        self.current = self.user('runner1')
        body = {'char_id': 1, 'items': [{'id': item['id'], 'qty': 1, 'mode': 'nm'}]}
        self.call(server.Handler.api_buy, {}, None, body)
        self.assertEqual(self.response['status'], 200)
        self.call(server.Handler.api_buy, {}, None, body)
        self.assertEqual(self.response['status'], 200)
        with self.assertRaises(server.ApiError) as sold_out:
            self.call(server.Handler.api_buy, {}, None, body)
        self.assertEqual(sold_out.exception.status, 400)
        remaining = self.conn.execute(
            'SELECT stock_remaining FROM market_stock WHERE item_id=?',
            (item['id'],)).fetchone()['stock_remaining']
        self.assertEqual(remaining, 0)

    def test_reserve_blocks_others_and_allows_reserved_character(self):
        item = self.market_item()
        self.seed_stock(item, 3)
        self.current = self.user('gm')
        self.call(server.Handler.api_nightmarket_reserve, {}, None, {
            'item_id': item['id'], 'character_id': 2, 'note': 'held for K'})
        self.assertEqual(self.response['status'], 200)
        # Player V (character 1) is blocked.
        self.current = self.user('runner1')
        with self.assertRaises(server.ApiError) as blocked:
            self.call(server.Handler.api_buy, {}, None, {
                'char_id': 1, 'items': [{'id': item['id'], 'qty': 1, 'mode': 'nm'}]})
        self.assertEqual(blocked.exception.status, 400)
        # Reserved character can buy.
        self.current = self.user('runner2')
        self.call(server.Handler.api_buy, {}, None, {
            'char_id': 2, 'items': [{'id': item['id'], 'qty': 1, 'mode': 'nm'}]})
        self.assertEqual(self.response['status'], 200)

    def test_reserve_is_gm_only(self):
        item = self.market_item()
        self.seed_stock(item, 2)
        self.current = self.user('runner1')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_nightmarket_reserve, {}, None, {
                'item_id': item['id'], 'character_id': 1})
        self.assertEqual(denied.exception.status, 403)

    def test_fixer_request_fulfill_grants_catalog_item(self):
        self.current = self.user('runner1')
        self.call(server.Handler.api_fixer_request_create, {}, None, {
            'char_id': 1, 'item_id': 'gear-0', 'note': 'Need a flashlight'})
        self.assertEqual(self.response['status'], 201)
        request_id = self.response['payload']['request_id']
        self.current = self.user('gm')
        listing = self.call(server.Handler.api_fixer_requests, {}, None, {})['payload']
        self.assertEqual(len(listing['requests']), 1)
        self.assertEqual(listing['requests'][0]['status'], 'pending')
        self.call(server.Handler.api_fixer_request_resolve, {}, self.match(request_id), {
            'action': 'fulfill', 'price': 0})
        self.assertEqual(self.response['status'], 200)
        data = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertTrue(any(i.get('catalog_item_id') == 'gear-0' for i in data['inventory']))
        status = self.conn.execute(
            'SELECT status FROM fixer_requests WHERE id=?', (request_id,)).fetchone()['status']
        self.assertEqual(status, 'fulfilled')

    def test_fixer_request_free_text_creates_custom_item(self):
        self.current = self.user('runner1')
        self.call(server.Handler.api_fixer_request_create, {}, None, {
            'char_id': 1, 'item_name': 'Prototype Scanner', 'note': 'Something off the books'})
        request_id = self.response['payload']['request_id']
        self.current = self.user('gm')
        self.call(server.Handler.api_fixer_request_resolve, {}, self.match(request_id), {
            'action': 'fulfill', 'price': 0})
        data = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertTrue(any(i.get('is_custom') and i.get('custom_name') == 'Prototype Scanner'
                            for i in data['inventory']))

    def test_fixer_request_decline(self):
        self.current = self.user('runner1')
        self.call(server.Handler.api_fixer_request_create, {}, None, {
            'char_id': 1, 'item_id': 'gear-0'})
        request_id = self.response['payload']['request_id']
        self.current = self.user('gm')
        self.call(server.Handler.api_fixer_request_resolve, {}, self.match(request_id), {
            'action': 'decline', 'note': 'No stock'})
        status = self.conn.execute(
            'SELECT status FROM fixer_requests WHERE id=?', (request_id,)).fetchone()['status']
        self.assertEqual(status, 'declined')

    @staticmethod
    def match(*values):
        pattern = '^' + '/'.join('(\\d+)' for _ in values) + '$'
        return re.match(pattern, '/'.join(str(value) for value in values))


if __name__ == '__main__':
    unittest.main()


class NPCStatblockFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        for username, display, role in (('gm', 'GM', 'gm'), ('runner1', 'Runner One', 'player')):
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,?)',
                (username, display, 'x', 1 if role in ('gm', 'admin') else 0, role, 1))
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

    def statblock(self):
        return {
            'stats': {'REF': 8, 'DEX': 7, 'BODY': 6, 'INT': 4},
            'skills': {'Handgun': 6, 'Evasion': 6, 'Brawling': 4},
            'weapons': [{'name': 'Medium Pistol', 'skill': 'Handgun', 'damage': '2d6', 'rof': '1'}],
            'notes': 'Maelstrom guard',
        }

    def create_template(self):
        self.current = self.user('gm')
        payload = self.call(server.Handler.api_npc_template_create, {}, None, {
            'name': 'Maelstrom Guard', 'role': 'Ganger', 'access': 'shared',
            'data': {'hp_max': 30, 'sp_body': 7, 'initiative': 10, 'statblock': self.statblock()},
        })
        self.assertEqual(payload['status'], 201)
        return payload['payload']

    def create_session(self, view_config=None):
        self.current = self.user('gm')
        body = {'title': 'Test Session'}
        if view_config is not None:
            body['player_view_config'] = view_config
        payload = self.call(server.Handler.api_session_create, {}, None, body)
        self.assertEqual(payload['status'], 201)
        return payload['payload']

    def add_combatant(self, session_id, template_id=None):
        self.current = self.user('gm')
        body = {'name': 'Maelstrom Guard', 'initiative': 10, 'hp_max': 30, 'hp_current': 30,
                'sp_body': 7, 'sp_body_max': 7, 'sp_head': 7, 'sp_head_max': 7}
        if template_id:
            body['template_id'] = template_id
        payload = self.call(server.Handler.api_session_combatant_create, {}, self.match(session_id), body)
        self.assertEqual(payload['status'], 201)
        return payload['payload']['id']

    def test_template_exposes_derived_attacks(self):
        template = self.create_template()
        self.assertIn('derived', template)
        attacks = template['derived']['attacks']
        self.assertEqual(len(attacks), 1)
        self.assertEqual(attacks[0]['base'], 14)  # REF 8 + Handgun 6
        self.assertEqual(template['derived']['death_save'], 6)
        self.assertEqual(template['derived']['evasion_base'], 13)

    def test_combatant_snapshots_statblock_for_gm(self):
        template = self.create_template()
        session = self.create_session()
        self.add_combatant(session['id'], template_id=template['id'])
        self.current = self.user('gm')
        payload = self.call(server.Handler.api_session_detail, {}, self.match(session['id']), {})['payload']
        combatant = payload['combatants'][0]
        self.assertIn('statblock', combatant)
        self.assertEqual(combatant['statblock']['skills']['Handgun'], 6)
        self.assertEqual(combatant['derived']['attacks'][0]['base'], 14)

    def test_player_view_hides_statblock_unless_enabled(self):
        template = self.create_template()
        session = self.create_session(view_config={'show_npc_stats': False})
        self.add_combatant(session['id'], template_id=template['id'])
        row = self.conn.execute('SELECT * FROM nc_sessions WHERE id=?', (session['id'],)).fetchone()
        runner = self.user('runner1')
        player_payload = self.handler.session_payload(self.conn, row, runner, player_view=True)
        combatant = player_payload['combatants'][0]
        self.assertNotIn('statblock', combatant)
        self.assertNotIn('derived', combatant)
        # Enable the flag; the statblock becomes visible to players.
        self.current = self.user('gm')
        self.call(server.Handler.api_session_update, {}, self.match(session['id']), {
            'player_view_config': {'show_npc_stats': True}, 'activity_note': 'reveal'})
        row = self.conn.execute('SELECT * FROM nc_sessions WHERE id=?', (session['id'],)).fetchone()
        revealed = self.handler.session_payload(self.conn, row, runner, player_view=True)
        revealed_combatant = revealed['combatants'][0]
        self.assertIn('derived', revealed_combatant)
        self.assertEqual(revealed_combatant['derived']['attacks'][0]['base'], 14)

    def test_custom_combatant_accepts_inline_statblock(self):
        session = self.create_session()
        self.current = self.user('gm')
        payload = self.call(server.Handler.api_session_combatant_create, {}, self.match(session['id']), {
            'name': 'Custom Heavy', 'initiative': 8, 'hp_max': 40, 'hp_current': 40,
            'sp_body': 11, 'sp_body_max': 11, 'sp_head': 11, 'sp_head_max': 11,
            'statblock': self.statblock(),
        })
        self.assertEqual(payload['status'], 201)
        self.current = self.user('gm')
        detail = self.call(server.Handler.api_session_detail, {}, self.match(session['id']), {})['payload']
        combatant = detail['combatants'][0]
        self.assertEqual(combatant['derived']['attacks'][0]['name'], 'Medium Pistol')


if __name__ == '__main__':
    unittest.main()


class SessionRecapFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        for username, display, role in (('gm', 'GM', 'gm'), ('runner1', 'Runner One', 'player')):
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,?)',
                (username, display, 'x', 1 if role in ('gm', 'admin') else 0, role, 1))
        self.conn.execute(
            "INSERT INTO storylines(owner_user_id,title,code_name,public_summary,private_summary,status,created,updated) "
            "VALUES(1,'The Arc','ARC','','','active',1,1)")
        self.conn.execute(
            "INSERT INTO contracts(owner_user_id,status,title,storyline_id,created,updated) "
            "VALUES(1,'in_progress','The Heist',1,1,1)")
        self.conn.execute(
            "INSERT INTO nc_sessions(contract_id,owner_user_id,title,status,created,updated) "
            "VALUES(1,1,'Heist Session','active',1,1)")
        self.conn.execute(
            "INSERT INTO session_combatants(session_id,kind,name,initiative,visible,sort_order) "
            "VALUES(1,'npc','Maelstrom Guard',10,1,0)")
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

    def test_create_recap_autocollects_participants_and_links(self):
        self.current = self.user('gm')
        payload = self.call(server.Handler.api_recap_create, {}, None, {
            'title': 'The Watson Heist', 'session_id': 1, 'storyline_id': 1,
            'public_summary': 'The crew cracked the vault.', 'gm_notes': 'NPC escaped.',
            'choices': ['Betrayed the fixer'], 'loot': ['2000 eb'],
            'published': True, 'publish_feed': True, 'session_date': 1700000000,
        })
        self.assertEqual(payload['status'], 201)
        recap = payload['payload']
        self.assertEqual([p['name'] for p in recap['participants']], ['Maelstrom Guard'])
        self.assertTrue(recap['published'])
        self.assertEqual(recap['choices'], ['Betrayed the fixer'])
        self.assertTrue(recap['feed_post_id'])
        self.assertTrue(recap['timeline_id'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM session_recaps').fetchone()['n'], 1)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) n FROM feed_posts WHERE status='draft'").fetchone()['n'], 1)
        self.assertEqual(self.conn.execute(
            'SELECT COUNT(*) n FROM storyline_timeline').fetchone()['n'], 1)

    def test_recap_visibility_gates_private_fields_for_players(self):
        self.current = self.user('gm')
        self.call(server.Handler.api_recap_create, {}, None, {
            'title': 'Secret Op', 'public_summary': 'Public summary',
            'gm_notes': 'GM only', 'loot': ['100 eb'], 'published': True,
            'session_date': 1700000000,
        })
        self.current = self.user('runner1')
        listing = self.call(server.Handler.api_recaps, {}, None, {})['payload']
        self.assertFalse(listing['full'])
        self.assertEqual(len(listing['recaps']), 1)
        public = listing['recaps'][0]
        self.assertEqual(public['public_summary'], 'Public summary')
        self.assertNotIn('gm_notes', public)
        self.assertNotIn('loot', public)

    def test_player_cannot_create_recap(self):
        self.current = self.user('runner1')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_recap_create, {}, None, {'title': 'Cheat Recap'})
        self.assertEqual(denied.exception.status, 403)

    def test_unpublished_recap_hidden_from_players(self):
        self.current = self.user('gm')
        self.call(server.Handler.api_recap_create, {}, None, {
            'title': 'Draft Recap', 'public_summary': 'Not yet public',
            'published': False, 'session_date': 1700000000,
        })
        self.current = self.user('runner1')
        listing = self.call(server.Handler.api_recaps, {}, None, {})['payload']
        self.assertEqual(listing['recaps'], [])
        self.current = self.user('gm')
        gm_listing = self.call(server.Handler.api_recaps, {}, None, {})['payload']
        self.assertEqual(len(gm_listing['recaps']), 1)

    def test_update_and_delete_recap(self):
        self.current = self.user('gm')
        recap = self.call(server.Handler.api_recap_create, {}, None, {
            'title': 'Old Title', 'public_summary': 'Summary', 'publish_feed': True,
            'storyline_id': 1, 'session_date': 1700000000,
        })['payload']
        updated = self.call(server.Handler.api_recap_update, {}, self.match(recap['id']), {
            'title': 'New Title', 'public_summary': 'Updated summary',
            'gm_notes': 'Extra notes', 'published': True, 'publish_feed': True,
            'session_date': 1700000100,
        })['payload']
        self.assertEqual(updated['title'], 'New Title')
        self.assertEqual(updated['gm_notes'], 'Extra notes')
        self.assertEqual(updated['feed_post_id'], recap['feed_post_id'])
        self.assertEqual(updated['timeline_id'], recap['timeline_id'])
        # Delete removes the recap, its draft feed post and timeline entry.
        self.call(server.Handler.api_recap_delete, {}, self.match(recap['id']), {})
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM session_recaps').fetchone()['n'], 0)
        self.assertEqual(self.conn.execute(
            "SELECT COUNT(*) n FROM feed_posts WHERE status='draft'").fetchone()['n'], 0)
        self.assertEqual(self.conn.execute(
            'SELECT COUNT(*) n FROM storyline_timeline').fetchone()['n'], 0)


if __name__ == '__main__':
    unittest.main()


class DowntimeFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        for username, display, role in (('gm', 'GM', 'gm'),
                                        ('runner1', 'Runner One', 'player'),
                                        ('runner2', 'Runner Two', 'player')):
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,?)',
                (username, display, 'x', 1 if role in ('gm', 'admin') else 0, role, 1))
        base = {
            'handle': 'V', 'role': 'Solo', 'role_rank': 4,
            'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}], 'active_role': 'Solo',
            'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6, 'DEX': 7, 'REF': 7,
                      'TECH': 4, 'INT': 4, 'COOL': 4, 'EMP': 5},
            'skills': {}, 'inventory': [], 'cyberware': [], 'armor': {},
            'cash': 100, 'hp_cur': 20, 'ip_available': 0, 'ip_total_earned': 0,
            'ip_total_spent': 0, 'luck_cur': 5, 'reputation': 0,
        }
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(2,1,?,1,1)',
            (json.dumps(base),))
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(3,1,?,1,1)',
            (json.dumps(dict(base, handle='K')),))
        self.conn.commit()
        self.handler = object.__new__(server.Handler)
        self.response = {}
        self.current = self.user('runner1')
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

    def char_data(self, char_id):
        return json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=?', (char_id,)).fetchone()['data'])

    def revision(self, char_id):
        return self.conn.execute(
            'SELECT revision FROM characters WHERE id=?', (char_id,)).fetchone()['revision']

    def start(self, char_id, body, as_user='runner1'):
        self.current = self.user(as_user)
        body = dict(body)
        body.setdefault('revision', self.revision(char_id))
        return self.call(server.Handler.api_character_downtime_start, {},
                          self.match(char_id), body)

    def action(self, char_id, body, as_user='runner1'):
        self.current = self.user(as_user)
        body = dict(body)
        body.setdefault('revision', self.revision(char_id))
        return self.call(server.Handler.api_character_downtime_action, {},
                          self.match(char_id), body)

    def test_start_hustle_and_complete(self):
        self.start(1, {'duration_key': '1_week',
                       'activities': [{'id': 'hustle'}], 'note': 'Week off'})
        self.assertEqual(self.response['status'], 201)
        active = self.response['payload']['downtime']['active']
        self.assertEqual(active['duration_key'], '1_week')
        self.assertEqual([a['id'] for a in active['activities']], ['hustle'])
        # Resolve hustle: cash applied and ledger recorded.
        self.action(1, {'action': 'resolve', 'activity_id': 'hustle', 'earned': 500,
                        'note': 'Rolled a 5'})
        self.assertEqual(self.response['status'], 200)
        self.assertEqual(self.char_data(1)['cash'], 600)
        self.assertTrue(self.conn.execute(
            "SELECT 1 FROM character_ledger WHERE character_id=1 AND category='downtime' "
            'LIMIT 1').fetchone())
        # Complete the period.
        self.action(1, {'action': 'complete', 'note': 'Back on the street'})
        self.assertEqual(self.response['status'], 200)
        payload = self.response['payload']['downtime']
        self.assertIsNone(payload['active'])
        self.assertEqual(len(payload['history']), 1)

    def test_recover_hp_is_bounded_by_max(self):
        self.start(1, {'activities': [{'id': 'recover_hp'}]})
        hp_max = server.derive(self.char_data(1)).get('hp_max')
        self.action(1, {'action': 'resolve', 'activity_id': 'recover_hp', 'hp': 999})
        self.assertEqual(self.char_data(1)['hp_cur'], hp_max)

    def test_activity_resolve_requires_known_activity(self):
        self.start(1, {'activities': [{'id': 'hustle'}]})
        with self.assertRaises(server.ApiError) as err:
            self.action(1, {'action': 'resolve', 'activity_id': 'therapy'})
        self.assertEqual(err.exception.status, 404)

    def test_double_start_blocked(self):
        self.start(1, {'activities': [{'id': 'other'}]})
        self.assertEqual(self.response['status'], 201)
        with self.assertRaises(server.ApiError) as err:
            self.start(1, {'activities': [{'id': 'other'}]})
        self.assertEqual(err.exception.status, 409)

    def test_gm_can_manage_others_player_cannot(self):
        self.current = self.user('gm')
        self.start(1, {'activities': [{'id': 'other'}]}, as_user='gm')
        self.assertEqual(self.response['status'], 201)
        self.current = self.user('runner2')
        with self.assertRaises(server.ApiError) as denied:
            self.start(1, {'activities': [{'id': 'other'}]}, as_user='runner2')
        self.assertEqual(denied.exception.status, 403)


if __name__ == '__main__':
    unittest.main()


class PublishingPreviewFlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(str(Path(self.tmp.name) / 'ncnet.db'))
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(server.SCHEMA)
        server.apply_schema_migrations(self.conn, make_backup=False)
        for username, display, role in (('gm', 'GM', 'gm'), ('runner1', 'Runner One', 'player')):
            self.conn.execute(
                'INSERT INTO users(username,display_name,pass_hash,is_gm,account_role,created) '
                'VALUES(?,?,?,?,?,?)',
                (username, display, 'x', 1 if role in ('gm', 'admin') else 0, role, 1))
        self.conn.execute(
            "INSERT INTO personas(owner_user_id,access,kind,handle,display_name,short_bio,"
            "public_bio,status,created,updated) VALUES(1,'shared','person','fixer','Dex','','','active',1,1)")
        self.conn.execute(
            "INSERT INTO storylines(owner_user_id,title,code_name,public_summary,private_summary,"
            "status,created,updated) VALUES(1,'Arc','ARC','','','active',1,1)")
        base = {'handle': 'V', 'role': 'Solo', 'role_rank': 4,
                'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}], 'active_role': 'Solo',
                'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6}, 'skills': {},
                'inventory': [], 'cyberware': [], 'armor': {}, 'cash': 100,
                'ip_available': 0, 'ip_total_earned': 0, 'ip_total_spent': 0,
                'luck_cur': 5, 'reputation': 0}
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(2,1,?,1,1)',
            (json.dumps(base),))
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

    def test_feed_preview_normalizes_without_writing(self):
        self.current = self.user('gm')
        payload = self.call(server.Handler.api_feed_preview, {}, None, {
            'author_persona_id': 1, 'format': 'article', 'headline': 'Big News',
            'body': 'Body text', 'district_id': 'watson', 'storyline_id': 1,
            'truth_status': 'true',
        })
        self.assertEqual(payload['status'], 200)
        preview = payload['payload']
        self.assertTrue(preview['preview'])
        self.assertEqual(preview['author']['display_name'], 'Dex')
        self.assertEqual(preview['district_id'], 'watson')
        self.assertEqual(preview['truth_status'], 'true')
        # Nothing written to the database.
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM feed_posts').fetchone()['n'], 0)

    def test_feed_preview_validates_author_and_body(self):
        self.current = self.user('runner1')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_feed_preview, {}, None, {
                'author_persona_id': 1, 'format': 'short', 'body': 'x'})
        self.assertEqual(denied.exception.status, 403)
        self.current = self.user('gm')
        with self.assertRaises(server.ApiError) as bad_body:
            self.call(server.Handler.api_feed_preview, {}, None, {
                'author_persona_id': 1, 'format': 'article', 'headline': 'H', 'body': ''})
        self.assertEqual(bad_body.exception.status, 400)

    def test_contract_preview_normalizes_without_writing(self):
        self.current = self.user('gm')
        payload = self.call(server.Handler.api_contract_preview, {}, None, {
            'title': 'Heist', 'status': 'open', 'risk_level': 'moderate',
            'reward_mode': 'range', 'reward_min': 1000, 'reward_max': 2000,
            'district_id': 'watson', 'storyline_id': 1, 'teaser': 'Teaser',
            'public_brief': 'Public brief', 'classified_brief': 'Classified',
            'crew_capacity': 4,
            'participants': [{'persona_id': 1, 'role_key': 'poster',
                              'role_label': 'Fixer', 'visibility': 'public'}],
        })
        self.assertEqual(payload['status'], 200)
        preview = payload['payload']
        self.assertTrue(preview['preview'])
        self.assertEqual(preview['title'], 'Heist')
        self.assertEqual(preview['participants'][0]['display_name'], 'Dex')
        self.assertEqual(preview['participants'][0]['visibility'], 'public')
        self.assertEqual(preview['has_classified_access'], True)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM contracts').fetchone()['n'], 0)
        self.assertEqual(self.conn.execute(
            'SELECT COUNT(*) n FROM contract_participants').fetchone()['n'], 0)

    def test_contract_preview_requires_gm_and_valid_persona(self):
        self.current = self.user('runner1')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_contract_preview, {}, None, {'title': 'X'})
        self.assertEqual(denied.exception.status, 403)
        self.current = self.user('gm')
        with self.assertRaises(server.ApiError) as bad_persona:
            self.call(server.Handler.api_contract_preview, {}, None, {
                'title': 'X', 'participants': [{'persona_id': 9999}]})
        self.assertEqual(bad_persona.exception.status, 400)


if __name__ == '__main__':
    unittest.main()
