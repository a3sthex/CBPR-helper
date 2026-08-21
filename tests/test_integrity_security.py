import copy
import importlib.util
import json
import re
import sqlite3
import tempfile
import threading
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
        self.db_path = str(Path(self.tmp.name) / 'integrity.db')
        self.conn = sqlite3.connect(self.db_path)
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
            self.call(server.Handler.api_save_character, self.match(1), {
                'revision': 0, 'data': forged,
            })
        self.assertEqual(denied.exception.status, 400)

        stored = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertEqual(stored['cash'], 100)
        self.assertEqual(stored['ip_available'], 0)
        self.assertEqual(stored['stats']['REF'], 8)
        self.assertEqual(stored['inventory'], [])

        updated = self.call(server.Handler.api_save_character, self.match(1), {
            'revision': 0,
            'patch': {'notes': 'Private campaign note', 'public': False},
        })
        self.assertEqual(updated['data']['notes'], 'Private campaign note')
        self.assertFalse(updated['public'])
        self.assertEqual(updated['revision'], 1)
        with self.assertRaises(server.ApiError) as stale_update:
            self.call(server.Handler.api_save_character, self.match(1), {
                'revision': 0, 'patch': {'notes': 'stale overwrite'},
            })
        self.assertEqual(stale_update.exception.status, 409)
        stored_after_stale = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertEqual(stored_after_stale['notes'], 'Private campaign note')

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

    def test_trust_audit_sheet_edit_records_readable_diff_and_reverts_safely(self):
        edited = copy.deepcopy(self.character_data)
        edited['stats']['REF'] = 9
        edited['cash'] = 777
        edited['ip_available'] = 30
        edited['inventory'] = [{
            'key': 'guns-0', 'catalog_item_id': 'guns-0', 'cat': 'guns',
            'name': 'forged client label', 'qty': 1, 'state': 'carried',
        }]

        with self.assertRaises(server.ApiError) as no_reason:
            self.call(server.Handler.api_character_sheet_update, self.match(1), {
                'revision': 0, 'reason': '', 'data': edited,
            })
        self.assertEqual(no_reason.exception.status, 400)

        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Loot and correction after session', 'data': edited,
        })
        self.assertEqual(updated['revision'], 1)
        self.assertEqual(updated['data']['stats']['REF'], 9)
        self.assertEqual(updated['data']['cash'], 777)
        self.assertEqual(updated['data']['ip_available'], 30)
        self.assertEqual(updated['data']['inventory'][0]['name'],
                         server.item_by_id('guns-0')['name'])
        instance_id = updated['data']['inventory'][0]['instance_id']
        self.assertRegex(instance_id, r'^[a-f0-9]{32}$')
        self.assertTrue(self.conn.execute(
            'SELECT 1 FROM item_instances WHERE character_id=1 AND instance_id=?',
            (instance_id,)).fetchone())

        rows = self.conn.execute(
            'SELECT * FROM character_ledger WHERE character_id=1').fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['category'], 'sheet_update')
        delta = json.loads(rows[0]['delta_json'])
        labels = {change['label'] for change in delta['changes']}
        self.assertTrue({'STAT: REF', 'Cash', 'Available IP'} <= labels)
        self.assertTrue(any(label.startswith('Inventory:') for label in labels))

        history = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertEqual(history['current_revision'], 1)
        self.assertTrue(history['entries'][0]['can_revert'])
        self.assertNotIn('before_json', history['entries'][0])
        reverted = self.call(
            server.Handler.api_character_ledger_revert,
            self.match(1, history['entries'][0]['id']),
            {'revision': 1, 'reason': 'Undo accidental session edit'},
        )
        self.assertEqual(reverted['revision'], 2)
        self.assertEqual(reverted['data']['stats']['REF'], 8)
        self.assertEqual(reverted['data']['cash'], 100)
        self.assertEqual(reverted['data']['ip_available'], 0)
        self.assertEqual(reverted['data']['inventory'], [])
        self.assertFalse(self.conn.execute(
            'SELECT 1 FROM item_instances WHERE character_id=1').fetchone())
        categories = [row['category'] for row in self.conn.execute(
            'SELECT category FROM character_ledger WHERE character_id=1 ORDER BY id')]
        self.assertEqual(categories, ['sheet_update', 'sheet_revert'])

        with self.assertRaises(server.ApiError) as old_revert:
            self.call(server.Handler.api_character_ledger_revert,
                      self.match(1, history['entries'][0]['id']),
                      {'revision': 2})
        self.assertEqual(old_revert.exception.status, 409)

    def test_custom_and_found_items_are_safe_stable_and_audited(self):
        edited = copy.deepcopy(self.character_data)
        edited['inventory'] = [
            {
                'is_custom': True, 'key': 'client-custom', 'cat': 'gear',
                'name': 'Signal Scrambler Prototype', 'custom_name': 'Signal Scrambler Prototype',
                'desc': 'A hand-built story device with unknown internals.',
                'price': 750, 'qty': 4, 'stackable': True, 'state': 'carried',
                'acquisition_source': 'crafted', 'acquisition_note': 'Built during downtime',
                'notes': 'Private calibration phrase',
                # Custom narrative items cannot inject executable/derived mechanics.
                'damage': '99d6', 'sp': 99, 'hl': -100,
                'mechanics': {'attack_bonus': 999}, 'fields': {'evil': True},
                'consumable': True, 'equippable': True, 'active': True,
                'effect_coverage': {'automated': True},
            },
            {
                'is_custom': True, 'key': 'duplicate-prop', 'cat': 'custom',
                'name': 'Unmarked Access Card', 'price': 0, 'qty': 2,
                'stackable': False, 'state': 'carried',
                'acquisition_source': 'loot', 'acquisition_note': 'Warehouse run',
            },
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add crafted and recovered story items', 'data': edited,
        })
        inventory = updated['data']['inventory']
        prototype = next(item for item in inventory if item['name'] == 'Signal Scrambler Prototype')
        cards = [item for item in inventory if item['name'] == 'Unmarked Access Card']
        self.assertEqual(prototype['qty'], 4)
        self.assertEqual(len(cards), 2)
        self.assertTrue(all(item['qty'] == 1 for item in cards))
        self.assertEqual(len({item['instance_id'] for item in inventory}), 3)
        self.assertTrue(all(item['key'] == f"custom-{item['instance_id']}" for item in inventory))
        for forbidden in ('damage', 'sp', 'hl', 'mechanics', 'fields',
                          'consumable', 'equippable', 'active', 'effect_coverage'):
            self.assertNotIn(forbidden, prototype)
        self.assertTrue(prototype['manual_resolution_required'])
        row = self.conn.execute(
            'SELECT * FROM item_instances WHERE instance_id=?',
            (prototype['instance_id'],)).fetchone()
        self.assertIsNone(row['catalog_item_id'])
        self.assertEqual(row['source_type'], 'crafted')
        self.assertEqual(row['source_ref'], 'Built during downtime')

        public_data = copy.deepcopy(updated['data'])
        public_data['visibility'] = {**server.CHARACTER_VISIBILITY_DEFAULTS, 'equipment': True}
        public = server.public_character_data(public_data)
        public_prototype = next(item for item in public['inventory']
                                if item['name'] == 'Signal Scrambler Prototype')
        self.assertNotIn('notes', public_prototype)
        self.assertNotIn('acquisition_note', public_prototype)
        self.assertEqual(public_prototype['desc'], prototype['desc'])

        edited_again = copy.deepcopy(updated['data'])
        target = next(item for item in edited_again['inventory']
                      if item['instance_id'] == prototype['instance_id'])
        target.update({
            'custom_name': 'Scrambler Mk II', 'name': 'Scrambler Mk II',
            'desc': 'Rebuilt after field testing.', 'price': 900,
            'acquisition_source': 'gift', 'acquisition_note': 'Reworked by an allied Tech',
        })
        changed = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 1, 'reason': 'Tech rebuilt the prototype', 'data': edited_again,
        })
        changed_item = next(item for item in changed['data']['inventory']
                            if item['instance_id'] == prototype['instance_id'])
        self.assertEqual(changed_item['name'], 'Scrambler Mk II')
        self.assertEqual(changed_item['price'], 900)
        source_row = self.conn.execute(
            'SELECT source_type,source_ref FROM item_instances WHERE instance_id=?',
            (prototype['instance_id'],)).fetchone()
        self.assertEqual(tuple(source_row), ('gift', 'Reworked by an allied Tech'))
        history = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(any('Scrambler Mk II' in change['label']
                            for change in history['entries'][0]['changes']))

    def test_consumable_and_active_gear_actions_are_authoritative_and_audited(self):
        edited = copy.deepcopy(self.character_data)
        catalog_ids = ('gear-27', 'gear-67', 'gear-91', 'gear-82', 'gear-154')
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'],
                'qty': 2 if item_id == 'gear-154' else 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in catalog_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Prepare field loadout', 'data': edited,
        })
        inventory = updated['data']['inventory']
        by_name = {item['name']: item for item in inventory}
        self.assertTrue(by_name['Flashlight']['equippable'])
        self.assertTrue(by_name['Stim']['consumable'])

        def item_match(instance_id):
            return re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{instance_id}')

        result = self.call(
            server.Handler.api_character_item_action,
            item_match(by_name['Flashlight']['instance_id']),
            {'revision': 1, 'action': 'equip', 'mode': 'held'},
        )
        flashlight = next(item for item in result['character']['data']['inventory']
                          if item['name'] == 'Flashlight')
        self.assertEqual(result['character']['revision'], 2)
        self.assertEqual(flashlight['state'], 'equipped')
        self.assertEqual(flashlight['equipped_mode'], 'held')
        self.assertFalse(flashlight['active'])

        result = self.call(
            server.Handler.api_character_item_action,
            item_match(flashlight['instance_id']),
            {'revision': 2, 'action': 'activate'},
        )
        flashlight = next(item for item in result['character']['data']['inventory']
                          if item['name'] == 'Flashlight')
        self.assertTrue(flashlight['active'])

        radio = next(item for item in result['character']['data']['inventory']
                     if item['name'] == 'Radio Communicator')
        result = self.call(
            server.Handler.api_character_item_action,
            item_match(radio['instance_id']),
            {'revision': 3, 'action': 'equip', 'mode': 'worn'},
        )
        radio = next(item for item in result['character']['data']['inventory']
                     if item['name'] == 'Radio Communicator')
        self.assertEqual(radio['equipped_slot'], 'ear')

        agent = next(item for item in result['character']['data']['inventory']
                     if item['name'] == 'Agent (Standard)')
        result = self.call(
            server.Handler.api_character_item_action,
            item_match(agent['instance_id']),
            {'revision': 4, 'action': 'equip', 'mode': 'held'},
        )
        techtool = next(item for item in result['character']['data']['inventory']
                        if item['name'] == 'Techtool')
        with self.assertRaises(server.ApiError) as no_free_hand:
            self.call(
                server.Handler.api_character_item_action,
                item_match(techtool['instance_id']),
                {'revision': 5, 'action': 'equip', 'mode': 'held'},
            )
        self.assertEqual(no_free_hand.exception.status, 409)

        agent = next(item for item in result['character']['data']['inventory']
                     if item['name'] == 'Agent (Standard)')
        result = self.call(
            server.Handler.api_character_item_action,
            item_match(agent['instance_id']),
            {'revision': 5, 'action': 'activate'},
        )
        self.assertEqual(result['character']['revision'], 6)
        self.assertEqual(
            result['character']['derived']['effects']['skills']['Library Search']['check_modifier'],
            2)
        self.assertTrue(next(source for source in
                             result['character']['derived']['effects']['item_sources']
                             if source['id'] == 'agent-standard-active')['active'])

        stim = next(item for item in result['character']['data']['inventory']
                    if item['name'] == 'Stim')
        used = self.call(
            server.Handler.api_character_item_action,
            item_match(stim['instance_id']),
            {'revision': 6, 'action': 'use', 'amount': 1},
        )
        self.assertEqual(used['character']['revision'], 7)
        self.assertTrue(used['effect']['manual_resolution_required'])
        remaining_stim = next(item for item in used['character']['data']['inventory']
                              if item['name'] == 'Stim')
        self.assertEqual(remaining_stim['qty'], 1)
        used_again = self.call(
            server.Handler.api_character_item_action,
            item_match(remaining_stim['instance_id']),
            {'revision': 7, 'action': 'use', 'amount': 1},
        )
        self.assertEqual(used_again['character']['revision'], 8)
        self.assertFalse(any(item['name'] == 'Stim'
                             for item in used_again['character']['data']['inventory']))
        self.assertFalse(self.conn.execute(
            'SELECT 1 FROM item_instances WHERE instance_id=?',
            (remaining_stim['instance_id'],)).fetchone())

        history = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertEqual(history['entries'][0]['category'], 'item_action')
        self.assertTrue(history['entries'][0]['can_revert'])
        self.assertTrue(any(
            change['path'] == 'effects.item_source.agent-standard-active'
            for entry in history['entries'] for change in entry['changes']))
        reverted = self.call(
            server.Handler.api_character_ledger_revert,
            self.match(1, history['entries'][0]['id']),
            {'revision': 8, 'reason': 'Undo accidental use'},
        )
        restored_stim = next(item for item in reverted['data']['inventory']
                             if item['name'] == 'Stim')
        self.assertEqual(restored_stim['qty'], 1)

    def test_use_preset_creates_replaces_and_reverts_active_effect(self):
        edited = copy.deepcopy(self.character_data)
        edited['inventory'] = [{
            'key': 'gear-161', 'catalog_item_id': 'gear-161', 'cat': 'gear',
            'name': 'Boost', 'qty': 2, 'state': 'carried',
            'acquisition_source': 'loot',
        }]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add recovered Boost doses', 'data': edited,
        })
        boost = updated['data']['inventory'][0]
        item_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{boost["instance_id"]}')
        first = self.call(server.Handler.api_character_item_action, item_match, {
            'revision': 1, 'action': 'use', 'amount': 1,
        })
        self.assertEqual(first['character']['revision'], 2)
        self.assertEqual(len(first['created_effects']), 1)
        self.assertEqual(first['created_effects'][0]['definition']['target'], 'character.stat.INT')
        self.assertEqual(first['created_effects'][0]['preset_id'], 'boost-primary-effect')
        self.assertEqual(first['created_effects'][0]['source_item_instance_id'], boost['instance_id'])
        self.assertTrue(first['created_effects'][0]['context']['manual_rules'])
        self.assertEqual(first['created_effects'][0]['duration_type'], 'campaign_time')
        self.assertEqual(first['created_effects'][0]['context']['campaign_minutes'], 1440)
        self.assertTrue(first['created_effects'][0]['context']['campaign_clock_manual'])
        self.assertIsNone(first['created_effects'][0]['expires_at'])
        self.assertEqual(first['character']['derived']['effects']['stats']['INT']['effective'], 8)
        self.assertTrue(first['manual_rules'])
        first_effect_id = first['created_effects'][0]['effect_id']
        remaining = first['character']['data']['inventory'][0]
        self.assertEqual(remaining['qty'], 1)

        second_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{remaining["instance_id"]}')
        second = self.call(server.Handler.api_character_item_action, second_match, {
            'revision': 2, 'action': 'use', 'amount': 1,
        })
        self.assertEqual(second['character']['revision'], 3)
        self.assertFalse(second['character']['data']['inventory'])
        self.assertEqual(second['character']['derived']['effects']['stats']['INT']['effective'], 8)
        second_effect_id = second['created_effects'][0]['effect_id']
        old_effect = self.conn.execute(
            'SELECT active FROM active_effect_instances WHERE effect_id=?',
            (first_effect_id,)).fetchone()
        self.assertEqual(old_effect['active'], 0)

        history = self.call(server.Handler.api_character_ledger, self.match(1))
        latest = history['entries'][0]
        self.assertTrue(latest['can_revert'])
        delta = self.conn.execute(
            'SELECT delta_json FROM character_ledger WHERE id=?',
            (latest['id'],)).fetchone()['delta_json']
        delta = json.loads(delta)
        self.assertEqual(delta['created_effect_ids'], [second_effect_id])
        self.assertIn(first_effect_id, delta['replaced_effect_ids'])
        reverted = self.call(
            server.Handler.api_character_ledger_revert, self.match(1, latest['id']),
            {'revision': 3, 'reason': 'Undo accidental second dose'},
        )
        self.assertEqual(reverted['revision'], 4)
        self.assertEqual(reverted['data']['inventory'][0]['qty'], 1)
        self.assertEqual(reverted['derived']['effects']['stats']['INT']['effective'], 8)
        restored_old = self.conn.execute(
            'SELECT active FROM active_effect_instances WHERE effect_id=?',
            (first_effect_id,)).fetchone()
        archived_new = self.conn.execute(
            'SELECT active,archived_at FROM active_effect_instances WHERE effect_id=?',
            (second_effect_id,)).fetchone()
        self.assertEqual(restored_old['active'], 1)
        self.assertEqual(archived_new['active'], 0)
        self.assertIsNotNone(archived_new['archived_at'])
        after_revert_ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertFalse(after_revert_ledger['entries'][0]['can_revert'])
        self.assertTrue(after_revert_ledger['entries'][0]['delta']['effect_linked_revert'])

    def test_weapon_modifications_bind_instances_slots_and_revert_atomically(self):
        edited = copy.deepcopy(self.character_data)
        catalog_ids = ('guns-0', 'guns-8', 'gun_upgrades-9', 'gun_upgrades-4',
                       'gun_upgrades-5', 'gun_upgrades-17')
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'],
                'price': server.item_by_id(item_id).get('price') or 0,
                'qty': 1, 'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in catalog_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add weapon workshop inventory', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        pistol, bow = by_name['Medium Pistol'], by_name['Bow']
        smart, drum = by_name['Smartgun Link'], by_name['Drum Magazine']
        extended, string = by_name['Extended Magazine'], by_name['Reinforced String']

        management = self.call(server.Handler.api_character_modifications, self.match(1))
        pistol_summary = next(host for host in management['hosts']
                              if host['instance_id'] == pistol['instance_id'])
        self.assertEqual((pistol_summary['slots_used'], pistol_summary['slots_total']), (0, 3))
        self.assertTrue(next(item for item in management['upgrades']
                             if item['instance_id'] == smart['instance_id'])['compatibility'][pistol['instance_id']]['allowed'])

        installed = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 1, 'host_instance_id': pistol['instance_id'],
            'upgrade_instance_id': smart['instance_id'], 'manual_confirm': False,
            'reason': 'Install Smartgun Link from workshop stock',
        })
        self.assertEqual(installed['character']['revision'], 2)
        smart_after = next(item for item in installed['character']['data']['inventory']
                           if item['instance_id'] == smart['instance_id'])
        self.assertEqual(smart_after['state'], 'installed')
        self.assertEqual(smart_after['host_instance_id'], pistol['instance_id'])
        modification_id = installed['modification_id']
        self.assertEqual(installed['management']['hosts'][0]['slots_used'], 2)

        forged = copy.deepcopy(installed['character']['data'])
        forged['inventory'] = [item for item in forged['inventory']
                               if item['instance_id'] != pistol['instance_id']]
        with self.assertRaises(server.ApiError) as orphan:
            self.call(server.Handler.api_character_sheet_update, self.match(1), {
                'revision': 2, 'reason': 'try deleting modified host', 'data': forged,
            })
        self.assertEqual(orphan.exception.status, 409)

        installed_drum = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 2, 'host_instance_id': pistol['instance_id'],
            'upgrade_instance_id': drum['instance_id'], 'manual_confirm': False,
            'reason': 'Install Drum Magazine',
        })
        self.assertEqual(installed_drum['character']['revision'], 3)
        host_after = next(host for host in installed_drum['management']['hosts']
                          if host['instance_id'] == pistol['instance_id'])
        self.assertEqual(host_after['slots_used'], 3)
        extended_after = next(item for item in installed_drum['management']['upgrades']
                              if item['instance_id'] == extended['instance_id'])
        compatibility = extended_after['compatibility'][pistol['instance_id']]
        self.assertFalse(compatibility['allowed'])
        self.assertTrue(any('slots' in reason.lower() or 'conflicts' in reason.lower()
                            for reason in compatibility['reasons']))

        with self.assertRaises(server.ApiError) as sell_host:
            self.call(server.Handler.api_sell, body={
                'char_id': 1, 'instance_id': pistol['instance_id'], 'qty': 1,
            })
        self.assertEqual(sell_host.exception.status, 409)

        mod_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{modification_id}')
        removed = self.call(server.Handler.api_character_modification_action, mod_match, {
            'revision': 3, 'action': 'remove', 'reason': 'Return link to workshop stock',
        })
        self.assertEqual(removed['character']['revision'], 4)
        removed_smart = next(item for item in removed['character']['data']['inventory']
                             if item['instance_id'] == smart['instance_id'])
        self.assertEqual(removed_smart['state'], 'carried')
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(ledger['entries'][0]['can_revert'])
        reverted = self.call(
            server.Handler.api_character_ledger_revert,
            self.match(1, ledger['entries'][0]['id']),
            {'revision': 4, 'reason': 'Undo accidental removal'},
        )
        self.assertEqual(reverted['revision'], 5)
        restored = self.conn.execute(
            'SELECT active FROM item_modifications WHERE modification_id=?',
            (modification_id,)).fetchone()
        self.assertEqual(restored['active'], 1)
        restored_smart = next(item for item in reverted['data']['inventory']
                              if item['instance_id'] == smart['instance_id'])
        self.assertEqual(restored_smart['state'], 'installed')
        self.assertFalse(self.call(server.Handler.api_character_ledger, self.match(1))['entries'][0]['can_revert'])

        with self.assertRaises(server.ApiError) as needs_manual:
            self.call(server.Handler.api_character_modification_install, self.match(1), {
                'revision': 5, 'host_instance_id': bow['instance_id'],
                'upgrade_instance_id': string['instance_id'], 'manual_confirm': False,
                'reason': 'Install Reinforced String',
            })
        self.assertEqual(needs_manual.exception.status, 409)
        permanent = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 5, 'host_instance_id': bow['instance_id'],
            'upgrade_instance_id': string['instance_id'], 'manual_confirm': True,
            'reason': 'Archery check passed; install permanent string',
        })
        permanent_mod = next(mod for mod in permanent['management']['modifications']
                             if mod['upgrade_instance_id'] == string['instance_id'])
        self.assertTrue(permanent_mod['permanent'])
        permanent_ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertFalse(permanent_ledger['entries'][0]['can_revert'])
        self.assertTrue(permanent_ledger['entries'][0]['delta']['permanent_modification'])
        permanent_match = re.match(r'^(\d+)/([a-f0-9]{32})$',
                                   f'1/{permanent_mod["modification_id"]}')
        with self.assertRaises(server.ApiError) as cannot_remove:
            self.call(server.Handler.api_character_modification_action, permanent_match, {
                'revision': 6, 'action': 'remove', 'reason': 'try removing permanent string',
            })
        self.assertEqual(cannot_remove.exception.status, 409)

    def test_active_effect_instances_apply_expire_tick_and_audit(self):
        character = copy.deepcopy(self.character_data)
        character['skills']['Handgun'] = 3
        self.conn.execute('UPDATE characters SET data=? WHERE id=1', (json.dumps(character),))
        self.conn.commit()

        created = self.call(server.Handler.api_character_effect_create, self.match(1), {
            'revision': 0, 'label': 'Targeting calibration',
            'target': 'skill.Handgun.check', 'operation': 'add', 'value': 2,
            'stack_policy': 'unique', 'stack_group': 'targeting_calibration',
            'duration_type': 'rounds', 'duration_value': 2,
            'reason': 'Temporary Tech calibration for this fight',
        })
        effect = created['effect']
        self.assertRegex(effect['effect_id'], r'^[a-f0-9]{32}$')
        self.assertEqual(effect['status'], 'active')
        self.assertEqual(effect['remaining_rounds'], 2)
        self.assertEqual(created['character']['revision'], 1)
        self.assertEqual(
            created['character']['derived']['effects']['skills']['Handgun']['effective_check_base'],
            13)

        def effect_match(effect_id):
            return re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{effect_id}')

        ticked = self.call(
            server.Handler.api_character_effect_action, effect_match(effect['effect_id']),
            {'revision': 1, 'action': 'tick'})
        self.assertEqual(ticked['effect']['remaining_rounds'], 1)
        self.assertEqual(ticked['character']['revision'], 2)
        self.assertEqual(
            ticked['character']['derived']['effects']['skills']['Handgun']['effective_check_base'],
            13)
        completed = self.call(
            server.Handler.api_character_effect_action, effect_match(effect['effect_id']),
            {'revision': 2, 'action': 'tick'})
        self.assertEqual(completed['effect']['status'], 'completed')
        self.assertEqual(completed['character']['revision'], 3)
        self.assertEqual(
            completed['character']['derived']['effects']['skills']['Handgun']['effective_check_base'],
            11)
        with self.assertRaises(server.ApiError) as cannot_restart:
            self.call(
                server.Handler.api_character_effect_action, effect_match(effect['effect_id']),
                {'revision': 3, 'action': 'enable'})
        self.assertEqual(cannot_restart.exception.status, 409)

        timed = self.call(server.Handler.api_character_effect_create, self.match(1), {
            'revision': 3, 'label': 'REF suppressant',
            'target': 'character.stat.REF', 'operation': 'add', 'value': -1,
            'stack_policy': 'stack', 'duration_type': 'real_time',
            'duration_value': 1, 'reason': 'Short acting narrative penalty',
        })
        timed_id = timed['effect']['effect_id']
        self.assertEqual(timed['character']['derived']['effects']['stats']['REF']['effective'], 7)
        self.conn.execute(
            'UPDATE active_effect_instances SET expires_at=? WHERE effect_id=?',
            (server.time.time() - 1, timed_id))
        self.conn.commit()
        expired_character = self.call(server.Handler.api_get_character, self.match(1))
        expired = next(item for item in expired_character['derived']['effects']['instances']
                       if item['effect_id'] == timed_id)
        self.assertEqual(expired['status'], 'expired')
        self.assertEqual(expired_character['derived']['effects']['stats']['REF']['effective'], 8)

        listed = self.call(server.Handler.api_character_effects, self.match(1))
        self.assertEqual(len(listed['effects']), 2)
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertEqual(ledger['entries'][0]['category'], 'effect')
        self.assertFalse(ledger['entries'][0]['can_revert'])
        self.assertTrue(any(change['path'].startswith('effects.instances.')
                            for entry in ledger['entries'] for change in entry['changes']))

        public_data = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        public_data['visibility'] = {
            **server.CHARACTER_VISIBILITY_DEFAULTS, 'combat': True,
        }
        self.conn.execute('UPDATE characters SET data=? WHERE id=1', (json.dumps(public_data),))
        self.conn.commit()
        self.current = self.user('other')
        public = self.call(server.Handler.api_get_character, self.match(1))
        self.assertTrue(public['derived']['effects']['instances'])
        self.assertTrue(all('reason' not in item and 'actor' not in item
                            for item in public['derived']['effects']['instances']))

    def test_custom_effects_reject_unsafe_payloads_and_foreign_writes(self):
        base = {
            'revision': 0, 'label': 'Unsafe', 'target': 'skill.Handgun.check',
            'operation': 'add', 'value': 1, 'stack_policy': 'stack',
            'duration_type': 'manual', 'reason': 'security test',
        }
        with self.assertRaises(server.ApiError) as script:
            self.call(server.Handler.api_character_effect_create, self.match(1), {
                **base, 'javascript': 'alert(1)',
            })
        self.assertEqual(script.exception.status, 400)
        with self.assertRaises(server.ApiError) as target:
            self.call(server.Handler.api_character_effect_create, self.match(1), {
                **base, 'target': '__proto__.polluted',
            })
        self.assertEqual(target.exception.status, 400)
        self.current = self.user('other')
        with self.assertRaises(server.ApiError) as foreign:
            self.call(server.Handler.api_character_effect_create, self.match(1), base)
        self.assertEqual(foreign.exception.status, 403)
        self.assertFalse(self.conn.execute(
            'SELECT 1 FROM active_effect_instances WHERE character_id=1').fetchone())

    def test_unknown_item_requires_database_or_explicit_custom_marker(self):
        edited = copy.deepcopy(self.character_data)
        edited['inventory'] = [{
            'key': 'made-up-item', 'cat': 'gear', 'name': 'Made Up', 'qty': 1,
            'acquisition_source': 'loot',
        }]
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_character_sheet_update, self.match(1), {
                'revision': 0, 'reason': 'try unknown item', 'data': edited,
            })
        self.assertEqual(denied.exception.status, 400)
        self.assertEqual(json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])['inventory'], [])

    def test_trust_audit_sheet_edit_is_owner_only_and_revision_guarded(self):
        edited = copy.deepcopy(self.character_data)
        edited['cash'] = 200
        self.current = self.user('other')
        with self.assertRaises(server.ApiError) as foreign:
            self.call(server.Handler.api_character_sheet_update, self.match(1), {
                'revision': 0, 'reason': 'not mine', 'data': edited,
            })
        self.assertEqual(foreign.exception.status, 403)
        self.current = self.user('runner')
        self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'cash correction', 'data': edited,
        })
        edited['cash'] = 300
        with self.assertRaises(server.ApiError) as stale:
            self.call(server.Handler.api_character_sheet_update, self.match(1), {
                'revision': 0, 'reason': 'stale tab', 'data': edited,
            })
        self.assertEqual(stale.exception.status, 409)

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
            'revision': 0,
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
            'revision': updated['revision'],
            'patch': {'portrait_media_id': media_id, 'visibility': {'portrait': False}},
        })
        self.current = self.user('other')
        with self.assertRaises(server.ApiError) as private_portrait:
            self.call(server.Handler.api_media_get,
                      re.match(r'^([a-f0-9]{32})$', media_id))
        self.assertEqual(private_portrait.exception.status, 403)

    def test_password_change_and_session_revocation(self):
        password_hash = server.hash_password('oldpassword')
        self.conn.execute('UPDATE users SET pass_hash=? WHERE id=2', (password_hash,))
        self.conn.commit()
        self.current = self.user('runner')
        current_token = server.create_session(self.conn, 2, '192.168.1.10', 'Current Browser')
        other_token = server.create_session(self.conn, 2, '192.168.1.11', 'Other Browser')
        self.handler.cookies = lambda: {'sid': current_token}

        sessions = self.call(server.Handler.api_account_sessions)['sessions']
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sum(1 for item in sessions if item['current']), 1)
        other = next(item for item in sessions if not item['current'])
        self.assertEqual(other['ip_address'], '192.168.1.11')

        with self.assertRaises(server.ApiError) as wrong_password:
            self.call(server.Handler.api_account_password, body={
                'current_password': 'wrong', 'new_password': 'newpassword',
            })
        self.assertEqual(wrong_password.exception.status, 403)
        changed = self.call(server.Handler.api_account_password, body={
            'current_password': 'oldpassword', 'new_password': 'newpassword',
        })
        self.assertTrue(changed['ok'])
        remaining = self.conn.execute('SELECT token FROM sessions WHERE user_id=2').fetchall()
        self.assertEqual([row['token'] for row in remaining], [current_token])
        updated_user = self.user('runner')
        self.assertTrue(server.verify_password('newpassword', updated_user['pass_hash']))
        self.assertFalse(server.verify_password('oldpassword', updated_user['pass_hash']))

        third_token = server.create_session(self.conn, 2, '192.168.1.12', 'Third Browser')
        sessions = self.call(server.Handler.api_account_sessions)['sessions']
        third = next(item for item in sessions if item['ip_address'] == '192.168.1.12')
        self.call(server.Handler.api_account_session_revoke, self.match(third['id']))
        self.assertFalse(self.conn.execute('SELECT 1 FROM sessions WHERE token=?',
                                           (third_token,)).fetchone())
        with self.assertRaises(server.ApiError) as current_revoke:
            current_id = next(item['id'] for item in sessions if item['current'])
            self.call(server.Handler.api_account_session_revoke, self.match(current_id))
        self.assertEqual(current_revoke.exception.status, 409)

        logged_out = self.call(server.Handler.api_account_logout_all)
        self.assertTrue(logged_out['ok'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM sessions WHERE user_id=2').fetchone()['n'], 0)
        audit_types = {row['event_type'] for row in self.conn.execute(
            'SELECT event_type FROM account_security_audit WHERE user_id=2')}
        self.assertTrue({'password_changed', 'session_revoked', 'logout_all'} <= audit_types)

    def test_admin_disables_account_revokes_sessions_and_can_restore(self):
        self.conn.execute("UPDATE users SET account_role='admin',is_gm=1 WHERE username='gm'")
        self.conn.execute('UPDATE users SET pass_hash=? WHERE id=2',
                          (server.hash_password('runnerpass'),))
        self.conn.commit()
        server.create_session(self.conn, 2, '192.168.1.10', 'Runner Browser')
        self.current = self.user('gm')
        disabled = self.call(server.Handler.api_admin_user_status, self.match(2), {
            'disabled': True, 'reason': 'Campaign access suspended',
        })
        self.assertTrue(disabled['disabled'])
        self.assertEqual(self.conn.execute('SELECT COUNT(*) n FROM sessions WHERE user_id=2').fetchone()['n'], 0)
        with self.assertRaises(server.ApiError) as login_denied:
            self.call(server.Handler.api_login, body={
                'username': 'runner', 'password': 'runnerpass',
            })
        self.assertEqual(login_denied.exception.status, 403)
        with self.assertRaises(server.ApiError) as self_disable:
            self.call(server.Handler.api_admin_user_status, self.match(1), {
                'disabled': True, 'reason': 'Mistake',
            })
        self.assertEqual(self_disable.exception.status, 409)
        enabled = self.call(server.Handler.api_admin_user_status, self.match(2), {
            'disabled': False, 'reason': 'Access restored',
        })
        self.assertFalse(enabled['disabled'])
        logged_in = self.call(server.Handler.api_login, body={
            'username': 'runner', 'password': 'runnerpass',
        })
        self.assertEqual(logged_in['username'], 'runner')
        events = [row['event_type'] for row in self.conn.execute(
            'SELECT event_type FROM account_security_audit WHERE user_id=2 ORDER BY id')]
        self.assertEqual(events, ['account_disabled', 'account_enabled'])

    def test_concurrent_contract_join_preserves_capacity_and_waitlist(self):
        other_char = copy.deepcopy(self.character_data)
        other_char['handle'] = 'Other V'
        self.conn.execute(
            'INSERT INTO characters(owner_id,public,data,created,updated) VALUES(3,1,?,1,1)',
            (json.dumps(other_char),))
        self.conn.commit()
        persona, _ = self.create_persona_and_storyline()
        contract = self.create_contract(persona, capacity=1)

        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def join(username, character_id):
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA busy_timeout=10000')
            handler = object.__new__(server.Handler)
            handler.current_user = lambda current: current.execute(
                'SELECT * FROM users WHERE username=?', (username,)).fetchone()
            response = {}
            handler.send_json = lambda payload, status=200, cookies=None: response.update(
                payload=payload, status=status)
            try:
                barrier.wait()
                server.Handler.api_contract_join(
                    handler, conn, {}, self.match(contract['id']),
                    {'character_id': character_id})
                result = response['payload']['my_signups'][0]['status']
            except Exception as error:  # captured for assertion in the main thread
                result = f'error:{error}'
            finally:
                conn.close()
            with lock:
                outcomes.append(result)

        threads = [
            threading.Thread(target=join, args=('runner', 1)),
            threading.Thread(target=join, args=('other', 2)),
        ]
        for thread in threads: thread.start()
        for thread in threads: thread.join(15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ['crew', 'waitlist'])
        rows = self.conn.execute(
            'SELECT status,COUNT(*) n FROM contract_signups WHERE contract_id=? GROUP BY status',
            (contract['id'],)).fetchall()
        self.assertEqual({row['status']: row['n'] for row in rows}, {'crew': 1, 'waitlist': 1})

    def test_concurrent_market_purchase_cannot_spend_same_cash_twice(self):
        market_item = server.night_market()['items'][0]
        character = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=1').fetchone()['data'])
        character['cash'] = market_item['street_price']
        self.conn.execute('UPDATE characters SET data=? WHERE id=1', (json.dumps(character),))
        self.conn.commit()
        barrier = threading.Barrier(2)
        outcomes = []
        lock = threading.Lock()

        def buy():
            conn = sqlite3.connect(self.db_path, timeout=10)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA busy_timeout=10000')
            handler = object.__new__(server.Handler)
            handler.current_user = lambda current: current.execute(
                "SELECT * FROM users WHERE username='runner'").fetchone()
            handler.send_json = lambda payload, status=200, cookies=None: None
            try:
                barrier.wait()
                server.Handler.api_buy(handler, conn, {}, None, {
                    'char_id': 1, 'items': [{'id': market_item['id'], 'qty': 1, 'mode': 'nm'}],
                })
                result = 'bought'
            except server.ApiError as error:
                result = f'denied:{error.status}'
            finally:
                conn.close()
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=buy), threading.Thread(target=buy)]
        for thread in threads: thread.start()
        for thread in threads: thread.join(15)
        self.assertFalse(any(thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ['bought', 'denied:400'])
        data = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertEqual(data['cash'], 0)
        bought = next(item for item in data['inventory'] if item['key'] == market_item['id'])
        self.assertEqual(bought['qty'], 1)
        revision = self.conn.execute('SELECT revision FROM characters WHERE id=1').fetchone()['revision']
        self.assertEqual(revision, 1)

    def test_full_catalog_cannot_bypass_rotating_market_stock(self):
        self.current = self.user('runner')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_buy, body={
                'char_id': 1, 'items': [{'id': 'guns-0', 'qty': 1, 'mode': 'list'}],
            })
        self.assertEqual(denied.exception.status, 400)
        stored = json.loads(self.conn.execute('SELECT data FROM characters WHERE id=1').fetchone()['data'])
        self.assertEqual(stored['cash'], 100)
        self.assertEqual(stored['inventory'], [])

    def test_legacy_stacks_migrate_to_stable_item_instances_idempotently(self):
        legacy = copy.deepcopy(self.character_data)
        legacy['inventory'] = [
            {'key': 'guns-0', 'cat': 'guns', 'name': 'Medium Pistol', 'qty': 2,
             'price': 50, 'mechanics': {'magazine': 12}},
            {'key': 'ammo-0', 'cat': 'ammo', 'name': 'Basic Ammunition', 'qty': 3,
             'price': 10},
        ]
        legacy['cyberware'] = [
            {'key': 'cyberware-0', 'cat': 'cyberware', 'name': 'Cyberaudio Suite',
             'qty': 1, 'price': 500},
        ]
        legacy['weapon_state'] = {
            'guns-0': {'magazine': 7, 'magazine_max': 12, 'reserve': 20},
        }
        self.conn.execute('UPDATE characters SET data=? WHERE id=1', (json.dumps(legacy),))
        self.conn.execute('DELETE FROM schema_migrations WHERE version=?',
                          (server.MIGRATION_ITEM_INSTANCES,))
        self.conn.execute('DROP TABLE item_instances')
        self.conn.commit()

        server.apply_schema_migrations(self.conn, make_backup=False)
        stored = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        pistols = [item for item in stored['inventory'] if item['key'] == 'guns-0']
        ammunition = [item for item in stored['inventory'] if item['key'] == 'ammo-0']
        self.assertEqual(len(pistols), 2)
        self.assertTrue(all(item['qty'] == 1 for item in pistols))
        self.assertEqual(len({item['instance_id'] for item in pistols}), 2)
        self.assertEqual(len(ammunition), 1)
        self.assertEqual(ammunition[0]['qty'], 3)
        self.assertRegex(ammunition[0]['instance_id'], r'^[a-f0-9]{32}$')
        self.assertRegex(stored['cyberware'][0]['instance_id'], r'^[a-f0-9]{32}$')
        self.assertEqual(stored['cyberware'][0]['state'], 'installed')
        self.assertNotIn('guns-0', stored['weapon_state'])
        self.assertTrue(all(stored['weapon_state'][item['instance_id']]['magazine'] == 7
                            for item in pistols))
        rows_before = self.conn.execute(
            'SELECT instance_id,bucket,quantity FROM item_instances WHERE character_id=1 '
            'ORDER BY instance_id').fetchall()
        self.assertEqual(len(rows_before), 4)

        server.apply_schema_migrations(self.conn, make_backup=False)
        rows_after = self.conn.execute(
            'SELECT instance_id,bucket,quantity FROM item_instances WHERE character_id=1 '
            'ORDER BY instance_id').fetchall()
        self.assertEqual([tuple(row) for row in rows_after],
                         [tuple(row) for row in rows_before])

    def test_durable_market_items_are_individual_and_sale_targets_one_instance(self):
        market_item = next(item for item in server.night_market()['items']
                           if item['cat'] == 'guns' and
                           (item.get('mechanics') or {}).get('magazine'))
        character = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        character['cash'] = market_item['street_price'] * 2
        self.conn.execute('UPDATE characters SET data=? WHERE id=1', (json.dumps(character),))
        self.conn.commit()

        self.call(server.Handler.api_buy, body={
            'char_id': 1,
            'items': [{'id': market_item['id'], 'qty': 2, 'mode': 'nm'}],
        })
        purchased = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])['inventory']
        self.assertEqual(len(purchased), 2)
        self.assertEqual({item['qty'] for item in purchased}, {1})
        self.assertEqual(len({item['instance_id'] for item in purchased}), 2)
        self.assertTrue(all(
            purchased_state['magazine'] == 0 and
            purchased_state['magazine_max'] == market_item['mechanics']['magazine']
            for purchased_state in (
                json.loads(self.conn.execute(
                    'SELECT data FROM characters WHERE id=1').fetchone()['data'])['weapon_state'][item['instance_id']]
                for item in purchased)))
        first_id, second_id = (item['instance_id'] for item in purchased)
        db_ids = {row['instance_id'] for row in self.conn.execute(
            'SELECT instance_id FROM item_instances WHERE character_id=1').fetchall()}
        self.assertEqual(db_ids, {first_id, second_id})

        self.call(server.Handler.api_sell, body={
            'char_id': 1, 'instance_id': first_id, 'qty': 1,
        })
        remaining = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])['inventory']
        self.assertEqual([item['instance_id'] for item in remaining], [second_id])
        self.assertEqual({row['instance_id'] for row in self.conn.execute(
            'SELECT instance_id FROM item_instances WHERE character_id=1').fetchall()},
                         {second_id})

        payload = self.call(server.Handler.api_character_items, self.match(1))
        self.assertEqual([item['instance_id'] for item in payload['instances']], [second_id])
        self.current = self.user('other')
        with self.assertRaises(server.ApiError) as denied:
            self.call(server.Handler.api_character_items, self.match(1))
        self.assertEqual(denied.exception.status, 403)

    def test_admin_creates_lists_and_verifies_campaign_backup(self):
        with self.assertRaises(server.ApiError) as player_denied:
            self.call(server.Handler.api_admin_backups)
        self.assertEqual(player_denied.exception.status, 403)

        backup_dir = Path(self.tmp.name) / 'api-backups'
        uploads_dir = Path(self.tmp.name) / 'api-uploads'
        uploads_dir.mkdir()
        (uploads_dir / 'portrait.webp').write_bytes(b'private portrait')
        original = (server.DB_PATH, server.BACKUP_DIR, server.UPLOAD_DIR)
        server.DB_PATH, server.BACKUP_DIR, server.UPLOAD_DIR = (
            self.db_path, str(backup_dir), str(uploads_dir))
        try:
            self.conn.execute("UPDATE users SET account_role='admin',is_gm=1 WHERE username='gm'")
            self.conn.commit()
            self.current = self.user('gm')
            created = self.call(server.Handler.api_admin_backup_create, body={
                'reason': 'API regression',
            })
            self.assertNotIn('path', created)
            self.assertTrue((backup_dir / created['name']).is_file())
            listed = self.call(server.Handler.api_admin_backups)
            self.assertEqual(listed['backups'][0]['name'], created['name'])
            verified = self.call(
                server.Handler.api_admin_backup_verify,
                re.match(r'^([A-Za-z0-9_.-]+)$', created['name']))
            self.assertTrue(verified['valid'])
            audit = self.conn.execute(
                "SELECT * FROM account_security_audit WHERE event_type='backup_created'").fetchone()
            self.assertEqual(audit['detail'], created['name'])
        finally:
            server.DB_PATH, server.BACKUP_DIR, server.UPLOAD_DIR = original

    def test_scoped_session_roles_enforce_capabilities(self):
        self.current = self.user('gm')
        session = self.call(server.Handler.api_session_create, body={'title': 'Scoped Session'})
        self.call(server.Handler.api_session_access_grant, self.match(session['id']), {
            'user_id': 3, 'role': 'assistant',
        })
        self.call(server.Handler.api_session_access_grant, self.match(session['id']), {
            'user_id': 2, 'role': 'rules_helper',
        })

        self.current = self.user('other')
        assistant = self.call(server.Handler.api_session_detail, self.match(session['id']))
        self.assertEqual(assistant['access_role'], 'assistant')
        self.assertTrue(assistant['capabilities']['edit_combatants'])
        self.assertFalse(assistant['capabilities']['edit_session'])
        npc = self.call(server.Handler.api_session_combatant_create, self.match(session['id']), {
            'name': 'Assistant NPC', 'hp_max': 20, 'hp_current': 20,
            'secret': {'plan': 'classified'},
        })
        self.assertTrue(npc['id'])
        advanced = self.call(server.Handler.api_session_update, self.match(session['id']), {
            'round': 1, 'active_turn': 0, 'status': 'active',
        })
        self.assertEqual(advanced['round'], 1)
        with self.assertRaises(server.ApiError) as assistant_notes:
            self.call(server.Handler.api_session_update, self.match(session['id']), {
                'notes': 'Should be forbidden',
            })
        self.assertEqual(assistant_notes.exception.status, 403)

        self.current = self.user('runner')
        helper = self.call(server.Handler.api_session_detail, self.match(session['id']))
        self.assertEqual(helper['access_role'], 'rules_helper')
        self.assertFalse(helper['capabilities']['edit_combatants'])
        self.assertNotIn('secret', helper['combatants'][0])
        with self.assertRaises(server.ApiError) as helper_edit:
            self.call(server.Handler.api_session_combatant_update,
                      self.match(session['id'], npc['id']), {'hp_current': 1})
        self.assertEqual(helper_edit.exception.status, 403)

        self.current = self.user('gm')
        self.call(server.Handler.api_session_access_grant, self.match(session['id']), {
            'user_id': 2, 'role': 'observer',
        })
        self.current = self.user('runner')
        observer = self.call(server.Handler.api_session_player_view, self.match(session['id']))
        self.assertEqual(observer['access_role'], 'observer')
        with self.assertRaises(server.ApiError) as observer_gm_view:
            self.call(server.Handler.api_session_detail, self.match(session['id']))
        self.assertEqual(observer_gm_view.exception.status, 404)

    def test_anonymous_session_safety_signal_and_private_resolution(self):
        self.current = self.user('gm')
        session = self.call(server.Handler.api_session_create, body={'title': 'Safety Session'})
        self.call(server.Handler.api_session_update, self.match(session['id']), {
            'safety_config': {
                'content_notes': 'Body horror', 'lines': ['Harm to children'],
                'veils': ['Torture'], 'pause_enabled': True,
            },
        })
        self.call(server.Handler.api_session_access_grant, self.match(session['id']), {
            'user_id': 2, 'role': 'observer',
        })
        self.call(server.Handler.api_session_access_grant, self.match(session['id']), {
            'user_id': 3, 'role': 'co_gm',
        })

        self.current = self.user('runner')
        signal = self.call(server.Handler.api_session_safety_create, self.match(session['id']), {
            'kind': 'pause', 'message': 'Please fade this scene.',
        })
        self.assertEqual(signal['status'], 'open')
        self.assertNotIn('user_id', signal)
        own = self.call(server.Handler.api_session_safety, self.match(session['id']))
        self.assertFalse(own['can_manage'])
        self.assertEqual(len(own['signals']), 1)
        self.assertNotIn('user_id', own['signals'][0])

        self.current = self.user('other')
        manager = self.call(server.Handler.api_session_safety, self.match(session['id']))
        self.assertTrue(manager['can_manage'])
        self.assertEqual(manager['signals'][0]['message'], 'Please fade this scene.')
        self.assertNotIn('user_id', manager['signals'][0])
        acknowledged = self.call(
            server.Handler.api_session_safety_update,
            self.match(session['id'], signal['id']), {'status': 'acknowledged'})
        self.assertEqual(acknowledged['status'], 'acknowledged')
        resolved = self.call(
            server.Handler.api_session_safety_update,
            self.match(session['id'], signal['id']), {'status': 'resolved'})
        self.assertEqual(resolved['status'], 'resolved')
        stored = self.conn.execute(
            'SELECT user_id,status FROM session_safety_signals WHERE id=?',
            (signal['id'],)).fetchone()
        self.assertEqual(stored['user_id'], 2)
        self.assertEqual(stored['status'], 'resolved')
        activity = self.conn.execute(
            "SELECT COUNT(*) n FROM session_activity WHERE event_type LIKE 'safety%'").fetchone()['n']
        self.assertEqual(activity, 0)

    def test_production_install_is_loopback_https_only_and_login_route_is_unique(self):
        installer = (ROOT / 'deploy/install.sh').read_text(encoding='utf-8')
        nginx = (ROOT / 'deploy/nginx-cbpr.conf').read_text(encoding='utf-8')
        source = (ROOT / 'app/server.py').read_text(encoding='utf-8')
        self.assertIn("ap.add_argument('--host', default='127.0.0.1')", source)
        self.assertIn('--host 127.0.0.1', installer)
        self.assertIn('Environment=CBPR_SECURE_COOKIES=1', installer)
        self.assertIn('Environment=CBPR_REGISTRATION_MODE=invite', installer)
        self.assertIn('cbpr-backup.timer', installer)
        self.assertIn('app/backup.py create --retention 14', installer)
        self.assertIn('return 308 https://$host$request_uri', nginx)
        self.assertIn('listen 443 ssl http2', nginx)
        login_routes = [route for route in server.ROUTES
                        if route[0] == 'POST' and route[1].pattern == '^/api/login$']
        self.assertEqual(len(login_routes), 1)


if __name__ == '__main__':
    unittest.main()
