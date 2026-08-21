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
        effective_pistol = installed_drum['character']['derived']['effective_weapons'][pistol['instance_id']]
        self.assertEqual(effective_pistol['base']['magazine'], 12)
        self.assertEqual(effective_pistol['effective']['magazine'], 36)
        self.assertEqual(effective_pistol['attack_modifier'], 0)
        smart_source = next(source for source in effective_pistol['sources']
                            if source['id'] == 'smartgun-link-effective')
        self.assertFalse(smart_source['requirements_met'])
        pistol_state = installed_drum['character']['data']['weapon_state'][pistol['instance_id']]
        self.assertEqual(pistol_state['magazine_max'], 36)
        self.assertEqual(pistol_state['magazine'], 12)
        installed_config = self.conn.execute(
            'SELECT configuration_json FROM item_modifications WHERE modification_id=?',
            (modification_id,)).fetchone()['configuration_json']
        self.assertTrue(json.loads(installed_config)['effect_rules'])
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

    def test_range_table_modification_rejects_cross_family_choice(self):
        edited = copy.deepcopy(self.character_data)
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in ('guns-0', 'gun_upgrades-19')
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add pistol and range modification', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        host, upgrade = by_name['Medium Pistol'], by_name['Range Table Modification']
        management = self.call(server.Handler.api_character_modifications, self.match(1))
        upgrade_payload = next(item for item in management['upgrades']
                               if item['instance_id'] == upgrade['instance_id'])
        schema = upgrade_payload['configuration_by_host'][host['instance_id']][0]
        self.assertEqual(schema['base_value'], 'Pistol')
        self.assertEqual([choice['value'] for choice in schema['choices']],
                         ['Snubnose Pistol', 'Long Barrel Pistol'])
        with self.assertRaises(server.ApiError) as cross_family:
            self.call(server.Handler.api_character_modification_install, self.match(1), {
                'revision': 1, 'host_instance_id': host['instance_id'],
                'upgrade_instance_id': upgrade['instance_id'], 'manual_confirm': True,
                'configuration': {'range_table': 'Sniper Rifle'},
                'reason': 'try invalid cross-family range table',
            })
        self.assertEqual(cross_family.exception.status, 400)
        installed = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 1, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': upgrade['instance_id'], 'manual_confirm': True,
            'configuration': {'range_table': 'Long Barrel Pistol'},
            'reason': 'Install long-barrel range profile',
        })
        effective = installed['character']['derived']['effective_weapons'][host['instance_id']]
        self.assertEqual(effective['base']['range_table'], 'Pistol')
        self.assertEqual(effective['effective']['range_table'], 'Long Barrel Pistol')
        self.assertEqual(effective['base']['damage'], effective['effective']['damage'])
        self.assertEqual(installed['management']['modifications'][0]['configuration']['choices'],
                         {'range_table': 'Long Barrel Pistol'})

    def test_configurable_smg_upgrade_requires_valid_autofire_choice(self):
        edited = copy.deepcopy(self.character_data)
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in ('guns-3', 'gun_upgrades-22')
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add SMG and cyclic internals', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        host, upgrade = by_name['SMG'], by_name['SMG Cyclic Internals']
        management = self.call(server.Handler.api_character_modifications, self.match(1))
        upgrade_payload = next(item for item in management['upgrades']
                               if item['instance_id'] == upgrade['instance_id'])
        self.assertEqual(upgrade_payload['configuration_schemas'][0]['key'], 'autofire_mode')
        with self.assertRaises(server.ApiError) as missing:
            self.call(server.Handler.api_character_modification_install, self.match(1), {
                'revision': 1, 'host_instance_id': host['instance_id'],
                'upgrade_instance_id': upgrade['instance_id'], 'manual_confirm': True,
                'reason': 'Install without required choice',
            })
        self.assertEqual(missing.exception.status, 400)
        with self.assertRaises(server.ApiError) as invalid:
            self.call(server.Handler.api_character_modification_install, self.match(1), {
                'revision': 1, 'host_instance_id': host['instance_id'],
                'upgrade_instance_id': upgrade['instance_id'], 'manual_confirm': True,
                'configuration': {'autofire_mode': 'railgun99'},
                'reason': 'Install invalid choice',
            })
        self.assertEqual(invalid.exception.status, 400)
        installed = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 1, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': upgrade['instance_id'], 'manual_confirm': True,
            'configuration': {'autofire_mode': 'smg4'},
            'reason': 'Weaponstech DV17 passed; choose SMG 4',
        })
        profile = installed['character']['derived']['effective_weapons'][host['instance_id']]['autofire_profiles'][0]
        self.assertEqual((profile['table'], profile['multiplier']), ('SMG', 4))
        modification = installed['management']['modifications'][0]
        self.assertEqual(modification['configuration']['choices']['autofire_mode'], 'smg4')

    def test_smart_rebuild_applies_connected_attack_bonus_and_removes_cleanly(self):
        edited = copy.deepcopy(self.character_data)
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in ('guns-6', 'gun_upgrades-1')
        ]
        edited['cyberware'] = [{
            'key': 'cyberware-61', 'catalog_item_id': 'cyberware-61',
            'cat': 'cyberware', 'name': 'Interface Plugs', 'qty': 1,
            'state': 'installed', 'acquisition_source': 'loot',
        }]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Prepare Smart Rebuild test loadout', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        host, rebuild = by_name['Assault Rifle'], by_name['Smart Rebuild']
        installed = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 1, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': rebuild['instance_id'], 'manual_confirm': False,
            'reason': 'Install Smart Rebuild',
        })
        modification_id = installed['modification_id']
        effective = installed['character']['derived']['effective_weapons'][host['instance_id']]
        self.assertIn('Smart Weapon', effective['tags'])
        self.assertEqual(effective['attack_modifier'], 1)
        self.assertTrue(any(source['manual_rules'] for source in effective['sources']
                            if source['id'] == 'smart-rebuild-tag'))
        mod_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{modification_id}')
        removed = self.call(server.Handler.api_character_modification_action, mod_match, {
            'revision': 2, 'action': 'remove', 'reason': 'Return weapon to base rebuild',
        })
        effective_after = removed['character']['derived']['effective_weapons'][host['instance_id']]
        self.assertNotIn('Smart Weapon', effective_after['tags'])
        self.assertEqual(effective_after['attack_modifier'], 0)

    def test_underbarrel_profile_has_independent_unloaded_magazine_and_revert(self):
        edited = copy.deepcopy(self.character_data)
        catalog_ids = ('guns-6', 'gun_upgrades-6', 'ammo-3')
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in catalog_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add rifle, underbarrel and grenade ammo', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        host = by_name['Assault Rifle']
        upgrade = by_name['Grenade Launcher Underbarrel']
        grenade_ammo = by_name['EMP']
        installed = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 1, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': upgrade['instance_id'], 'manual_confirm': False,
            'reason': 'Install underbarrel launcher',
        })
        modification_id = installed['modification_id']
        profile = installed['character']['derived']['effective_weapons'][host['instance_id']]['alternate_attacks'][0]
        self.assertEqual(profile['skill'], 'Heavy Weapons')
        self.assertEqual(profile['damage'], '6d6')
        self.assertEqual(profile['state']['magazine'], 0)
        self.assertEqual(profile['state']['magazine_max'], 1)
        self.assertEqual(profile['state']['reserve'], 0)
        self.assertEqual(profile['shared_ammo_available'], 10)
        self.assertEqual(
            installed['character']['derived']['effective_weapons'][host['instance_id']]['effective']['concealable'],
            'NO')
        source = next(item for item in
                      installed['character']['derived']['effective_weapons'][host['instance_id']]['sources']
                      if item['id'] == 'grenade-underbarrel-profile')
        self.assertTrue(source['manual_rules'][0]['manual_resolution_required'])

        mod_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{modification_id}')
        with self.assertRaises(server.ApiError) as empty:
            self.call(server.Handler.api_character_modification_action, mod_match, {
                'revision': 2, 'action': 'fire',
            })
        self.assertEqual(empty.exception.status, 409)
        reloaded = self.call(server.Handler.api_character_modification_action, mod_match, {
            'revision': 2, 'action': 'reload',
            'ammo_instance_id': grenade_ammo['instance_id'],
        })
        profile = reloaded['character']['derived']['effective_weapons'][host['instance_id']]['alternate_attacks'][0]
        self.assertEqual((profile['state']['magazine'], profile['state']['reserve']), (1, 0))
        self.assertEqual(profile['state']['loaded_ammo_name'], 'EMP')
        self.assertEqual(profile['shared_ammo_available'], 9)
        ammo_after = next(item for item in reloaded['character']['data']['inventory']
                          if item['instance_id'] == grenade_ammo['instance_id'])
        self.assertEqual(ammo_after['ammo_rounds'], 9)
        fired = self.call(server.Handler.api_character_modification_action, mod_match, {
            'revision': 3, 'action': 'fire',
        })
        profile = fired['character']['derived']['effective_weapons'][host['instance_id']]['alternate_attacks'][0]
        self.assertEqual(profile['state']['magazine'], 0)
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(ledger['entries'][0]['can_revert'])
        reverted = self.call(server.Handler.api_character_ledger_revert,
                             self.match(1, ledger['entries'][0]['id']),
                             {'revision': 4, 'reason': 'Undo accidental underbarrel shot'})
        profile = reverted['derived']['effective_weapons'][host['instance_id']]['alternate_attacks'][0]
        self.assertEqual(profile['state']['magazine'], 1)

        removed = self.call(server.Handler.api_character_modification_action, mod_match, {
            'revision': 5, 'action': 'remove', 'reason': 'Detach underbarrel launcher',
        })
        self.assertFalse(removed['character']['derived']['effective_weapons'][host['instance_id']]['alternate_attacks'])
        self.assertNotIn(modification_id, removed['character']['data'].get('modification_state', {}))

    def test_shared_ammo_reload_consumes_real_stack_and_reverts_atomically(self):
        edited = copy.deepcopy(self.character_data)
        item_ids = ('guns-1', 'ammo-0', 'ammo-1')
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'],
                'qty': 2 if item_id == 'ammo-0' else 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in item_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add shared ammo test loadout', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        weapon, basic, armor_piercing = (
            by_name['Heavy Pistol'], by_name['Basic'], by_name['Armor-Piercing'])
        self.assertEqual(basic['ammo_rounds'], 20)
        fired = self.call(server.Handler.api_character_resource, self.match(1), {
            'revision': 1, 'resource': 'weapon', 'subject': weapon['instance_id'],
            'action': 'fire', 'value': 1,
        })
        self.assertEqual(fired['character']['data']['weapon_state'][
            weapon['instance_id']]['magazine'], 7)
        reloaded = self.call(server.Handler.api_character_resource, self.match(1), {
            'revision': 2, 'resource': 'weapon', 'subject': weapon['instance_id'],
            'action': 'reload', 'ammo_instance_id': basic['instance_id'],
        })
        weapon_state = reloaded['character']['data']['weapon_state'][weapon['instance_id']]
        self.assertEqual(weapon_state['magazine'], 8)
        self.assertEqual(weapon_state['reserve'], 0)
        self.assertEqual(weapon_state['loaded_ammo_name'], 'Basic')
        basic_after = next(item for item in reloaded['character']['data']['inventory']
                           if item['instance_id'] == basic['instance_id'])
        self.assertEqual((basic_after['ammo_rounds'], basic_after['qty']), (19, 2))
        reload_history = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(reload_history['entries'][0]['can_revert'])
        reverted_reload = self.call(
            server.Handler.api_character_ledger_revert,
            self.match(1, reload_history['entries'][0]['id']), {
                'revision': 3, 'reason': 'Undo reload from the wrong ammo stack',
            })
        self.assertEqual(reverted_reload['data']['weapon_state'][
            weapon['instance_id']]['magazine'], 7)
        self.assertEqual(next(item for item in reverted_reload['data']['inventory']
                              if item['instance_id'] == basic['instance_id'])['ammo_rounds'], 20)

        reloaded_again = self.call(server.Handler.api_character_resource, self.match(1), {
            'revision': 4, 'resource': 'weapon', 'subject': weapon['instance_id'],
            'action': 'reload', 'ammo_instance_id': basic['instance_id'],
        })
        self.assertEqual(reloaded_again['character']['data']['weapon_state'][
            weapon['instance_id']]['magazine'], 8)
        fired_again = self.call(server.Handler.api_character_resource, self.match(1), {
            'revision': 5, 'resource': 'weapon', 'subject': weapon['instance_id'],
            'action': 'fire', 'value': 1,
        })
        self.assertEqual(fired_again['character']['data']['weapon_state'][
            weapon['instance_id']]['magazine'], 7)
        with self.assertRaises(server.ApiError) as mixed_ammo:
            self.call(server.Handler.api_character_resource, self.match(1), {
                'revision': 6, 'resource': 'weapon', 'subject': weapon['instance_id'],
                'action': 'reload', 'ammo_instance_id': armor_piercing['instance_id'],
            })
        self.assertEqual(mixed_ammo.exception.status, 409)
        sold_pack = self.call(server.Handler.api_sell, body={
            'char_id': 1, 'instance_id': basic['instance_id'], 'qty': 1,
        })
        self.assertEqual(sold_pack['qty'], 1)
        stored = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        partial_stack = next(item for item in stored['inventory']
                             if item['instance_id'] == basic['instance_id'])
        self.assertEqual((partial_stack['qty'], partial_stack['ammo_rounds']), (1, 9))
        with self.assertRaises(server.ApiError) as partial_sale:
            self.call(server.Handler.api_sell, body={
                'char_id': 1, 'instance_id': basic['instance_id'], 'qty': 1,
            })
        self.assertEqual(partial_sale.exception.status, 409)

    def test_exotic_scope_requires_rail_and_blocks_dependency_removal(self):
        edited = copy.deepcopy(self.character_data)
        catalog_ids = ('guns-30', 'gun_upgrades-16', 'gun_upgrades-7')
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in catalog_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add exotic weapon workshop parts', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        host = by_name['Militech Fox Dual Ammo']
        rail, scope = by_name['Compatibility Rail'], by_name['Infrared Nightvision Scope']
        installed_rail = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 1, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': rail['instance_id'], 'manual_confirm': True,
            'reason': 'Weaponstech check passed for Compatibility Rail',
        })
        rail_mod_id = installed_rail['modification_id']
        host_summary = next(item for item in installed_rail['management']['hosts']
                            if item['instance_id'] == host['instance_id'])
        self.assertEqual(host_summary['slot_pools']['scope'], {'total': 1, 'used': 0})
        installed_scope = self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 2, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': scope['instance_id'], 'manual_confirm': False,
            'reason': 'Install infrared scope on dedicated rail',
        })
        scope_mod_id = installed_scope['modification_id']
        host_summary = next(item for item in installed_scope['management']['hosts']
                            if item['instance_id'] == host['instance_id'])
        self.assertEqual(host_summary['slot_pools']['scope'], {'total': 1, 'used': 1})

        rail_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{rail_mod_id}')
        with self.assertRaises(server.ApiError) as dependency:
            self.call(server.Handler.api_character_modification_action, rail_match, {
                'revision': 3, 'action': 'remove', 'reason': 'try removing occupied rail',
            })
        self.assertEqual(dependency.exception.status, 409)
        scope_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{scope_mod_id}')
        removed_scope = self.call(server.Handler.api_character_modification_action, scope_match, {
            'revision': 3, 'action': 'remove', 'reason': 'Remove scope before rail',
        })
        self.assertEqual(removed_scope['character']['revision'], 4)
        removed_rail = self.call(server.Handler.api_character_modification_action, rail_match, {
            'revision': 4, 'action': 'remove', 'reason': 'Rail no longer has dependents',
        })
        self.assertEqual(removed_rail['character']['revision'], 5)

    def test_cyberdeck_loadout_binds_hardware_programs_and_enforces_slots(self):
        edited = copy.deepcopy(self.character_data)
        item_ids = (
            'net_stuff-1', 'net_stuff-19', 'net_stuff-20',
            'programs-12', 'programs-25',
        )
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in item_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add Cyberdeck loadout test items', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        deck = by_name['Cyberdeck (Standard Quality)']
        backup = by_name['Backup Drive']
        bushido = by_name['Bushido Accelerator']
        armor = by_name['Armor']
        killer = by_name['Killer']
        management = self.call(server.Handler.api_character_modifications, self.match(1))
        deck_payload = next(item for item in management['cyberdeck_hosts']
                            if item['instance_id'] == deck['instance_id'])
        self.assertEqual(deck_payload['slot_pools']['mixed'], {'total': 7, 'used': 0})
        backup_payload = next(item for item in management['cyberdeck_items']
                              if item['instance_id'] == backup['instance_id'])
        self.assertTrue(backup_payload['compatibility'][deck['instance_id']]['allowed'])

        installed_backup = self.call(
            server.Handler.api_character_modification_install, self.match(1), {
                'revision': 1, 'host_instance_id': deck['instance_id'],
                'upgrade_instance_id': backup['instance_id'],
                'manual_confirm': False, 'reason': 'Install Backup Drive in selected deck',
            })
        backup_mod_id = installed_backup['modification_id']
        installed_killer = self.call(
            server.Handler.api_character_modification_install, self.match(1), {
                'revision': 2, 'host_instance_id': deck['instance_id'],
                'upgrade_instance_id': killer['instance_id'],
                'manual_confirm': False, 'reason': 'Install Killer Black ICE',
            })
        self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 3, 'host_instance_id': deck['instance_id'],
            'upgrade_instance_id': armor['instance_id'],
            'manual_confirm': False, 'reason': 'Install Armor Defender Program',
        })
        effective = installed_killer['character']['derived']['effective_cyberdecks'][
            deck['instance_id']]
        self.assertEqual(effective['slots_used'], 4)
        final_management = self.call(server.Handler.api_character_modifications, self.match(1))
        deck_payload = next(item for item in final_management['cyberdeck_hosts']
                            if item['instance_id'] == deck['instance_id'])
        self.assertEqual(deck_payload['slot_pools']['mixed'], {'total': 7, 'used': 5})
        with self.assertRaises(server.ApiError) as overflow:
            self.call(server.Handler.api_character_modification_install, self.match(1), {
                'revision': 4, 'host_instance_id': deck['instance_id'],
                'upgrade_instance_id': bushido['instance_id'],
                'manual_confirm': False, 'reason': 'Try overflowing Cyberdeck slots',
            })
        self.assertEqual(overflow.exception.status, 400)
        backup_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$', f'1/{backup_mod_id}')
        removed = self.call(server.Handler.api_character_modification_action,
                            backup_match, {
            'revision': 4, 'action': 'remove',
            'reason': 'Uninstall Backup Drive from Cyberdeck',
        })
        backup_after = next(item for item in removed['character']['data']['inventory']
                            if item['instance_id'] == backup['instance_id'])
        self.assertEqual(backup_after['state'], 'carried')
        self.assertEqual(removed['character']['derived']['effective_cyberdecks'][
            deck['instance_id']]['slots_used'], 3)
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(any('Backup Drive' in entry['reason']
                            for entry in ledger['entries']))

    def test_program_runtime_rez_damage_destroy_and_backup_restore(self):
        edited = copy.deepcopy(self.character_data)
        item_ids = (
            'net_stuff-1', 'net_stuff-19', 'programs-12',
            'programs-0', 'programs-25',
        )
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in item_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add Program runtime test loadout', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        deck, backup, armor, banhammer, killer = (
            by_name['Cyberdeck (Standard Quality)'], by_name['Backup Drive'],
            by_name['Armor'], by_name['Banhammer'], by_name['Killer'])
        revision = 1
        installed = {}
        for item, reason in (
                (backup, 'Install Backup Drive for Program recovery'),
                (armor, 'Install Armor Defender Program'),
                (banhammer, 'Install Banhammer Attacker Program'),
                (killer, 'Install Killer Black ICE copy')):
            result = self.call(
                server.Handler.api_character_modification_install, self.match(1), {
                    'revision': revision, 'host_instance_id': deck['instance_id'],
                    'upgrade_instance_id': item['instance_id'],
                    'manual_confirm': False, 'reason': reason,
                })
            installed[item['name']] = result['modification_id']
            revision += 1
        self.assertEqual(revision, 5)

        def program_match(program):
            return re.match(
                r'^(\d+)/([a-f0-9]{32})/([a-f0-9]{32})$',
                f'1/{deck["instance_id"]}/{program["instance_id"]}')

        rezzed = self.call(server.Handler.api_character_program_action,
                           program_match(armor), {
            'revision': 5, 'action': 'rez', 'reason': 'Activate Armor in Netrun',
        })
        armor_state = rezzed['character']['data']['program_state'][armor['instance_id']]
        self.assertEqual((armor_state['status'], armor_state['rez_current']), ('rezzed', 7))
        damaged = self.call(server.Handler.api_character_program_action,
                            program_match(armor), {
            'revision': 6, 'action': 'damage', 'amount': 3,
            'reason': 'Armor takes Program REZ damage',
        })
        self.assertEqual(damaged['character']['data']['program_state'][
            armor['instance_id']]['rez_current'], 4)
        derezzed = self.call(server.Handler.api_character_program_action,
                             program_match(armor), {
            'revision': 7, 'action': 'damage', 'amount': 4,
            'reason': 'Armor reaches zero REZ',
        })
        self.assertEqual(derezzed['character']['data']['program_state'][
            armor['instance_id']]['status'], 'derezzed')
        armor_mod_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$', f'1/{installed["Armor"]}')
        with self.assertRaises(server.ApiError) as active_uninstall:
            self.call(server.Handler.api_character_modification_action,
                      armor_mod_match, {
                'revision': 8, 'action': 'remove',
                'reason': 'Try uninstalling Derezzed Program',
            })
        self.assertEqual(active_uninstall.exception.status, 409)
        deactivated = self.call(server.Handler.api_character_program_action,
                                program_match(armor), {
            'revision': 8, 'action': 'deactivate',
            'reason': 'Deactivate Armor before future activation',
        })
        self.assertEqual(deactivated['character']['data']['program_state'][
            armor['instance_id']]['rez_current'], 7)
        ran = self.call(server.Handler.api_character_program_action,
                        program_match(banhammer), {
            'revision': 9, 'action': 'run',
            'reason': 'Resolve Banhammer attack manually',
        })
        self.assertEqual(ran['character']['data']['program_state'][
            banhammer['instance_id']]['run_count'], 1)
        with self.assertRaises(server.ApiError) as black_ice_entity:
            self.call(server.Handler.api_character_program_action,
                      program_match(killer), {
                'revision': 10, 'action': 'rez',
                'reason': 'Try deploying Killer without NET entity',
            })
        self.assertEqual(black_ice_entity.exception.status, 409)

        destroyed = self.call(server.Handler.api_character_program_action,
                              program_match(banhammer), {
            'revision': 10, 'action': 'destroy',
            'reason': 'Enemy effect destroys Banhammer copy',
        })
        destroyed_item = next(item for item in destroyed['character']['data']['inventory']
                              if item['instance_id'] == banhammer['instance_id'])
        self.assertEqual(destroyed_item['state'], 'broken')
        deck_effective = destroyed['character']['derived']['effective_cyberdecks'][
            deck['instance_id']]
        backup_payload = next(item for item in deck_effective['hardware']
                              if item['name'] == 'Backup Drive')
        self.assertEqual(len(backup_payload['backup_state']['saved_programs']), 1)
        destroy_ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(destroy_ledger['entries'][0]['can_revert'])
        reverted_destroy = self.call(
            server.Handler.api_character_ledger_revert,
            self.match(1, destroy_ledger['entries'][0]['id']), {
                'revision': 11, 'reason': 'Undo incorrectly targeted Program destruction',
            })
        reverted_program = next(item for item in reverted_destroy['data']['inventory']
                                if item['instance_id'] == banhammer['instance_id'])
        self.assertEqual(reverted_program['state'], 'installed')
        reverted_deck = reverted_destroy['derived']['effective_cyberdecks'][deck['instance_id']]
        reverted_backup = next(item for item in reverted_deck['hardware']
                               if item['name'] == 'Backup Drive')
        self.assertFalse(reverted_backup['backup_state']['saved_programs'])

        self.call(server.Handler.api_character_program_action,
                  program_match(banhammer), {
            'revision': 12, 'action': 'destroy',
            'reason': 'Confirm enemy effect destroys Banhammer copy',
        })
        backup_match = re.match(
            r'^(\d+)/([a-f0-9]{32})/([a-f0-9]{32})$',
            f'1/{deck["instance_id"]}/{backup["instance_id"]}')
        restored = self.call(server.Handler.api_character_backup_restore,
                             backup_match, {
            'revision': 13, 'reason': 'Use Meat Action to restore saved Program',
        })
        self.assertEqual(restored['restored'], 1)
        restored_item = next(item for item in restored['character']['data']['inventory']
                             if item['instance_id'] == banhammer['instance_id'])
        self.assertEqual(restored_item['state'], 'installed')
        restored_state = restored['character']['data']['program_state'][banhammer['instance_id']]
        self.assertEqual((restored_state['status'], restored_state['run_count']),
                         ('inactive', 1))

        self.call(server.Handler.api_character_program_action,
                  program_match(banhammer), {
            'revision': 14, 'action': 'destroy',
            'reason': 'Destroy Banhammer again before removing Backup Drive',
        })
        backup_mod_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$', f'1/{installed["Backup Drive"]}')
        removed_backup = self.call(
            server.Handler.api_character_modification_action, backup_mod_match, {
                'revision': 15, 'action': 'remove',
                'reason': 'Remove Backup Drive and erase saved contents',
            })
        self.assertEqual(removed_backup['character']['revision'], 16)
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertFalse(ledger['entries'][0]['can_revert'])
        self.assertEqual(ledger['entries'][0]['delta']['backup_drive_erased_programs'], 1)

    def test_black_ice_net_entity_deploys_tracks_rez_and_reverts_destroy(self):
        edited = copy.deepcopy(self.character_data)
        item_ids = ('net_stuff-1', 'programs-25')
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in item_ids
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add Black ICE entity test loadout', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        deck, killer = by_name['Cyberdeck (Standard Quality)'], by_name['Killer']
        installed = self.call(
            server.Handler.api_character_modification_install, self.match(1), {
                'revision': 1, 'host_instance_id': deck['instance_id'],
                'upgrade_instance_id': killer['instance_id'],
                'manual_confirm': False, 'reason': 'Install Killer Black ICE',
            })
        killer_mod_id = installed['modification_id']
        deploy_match = re.match(
            r'^(\d+)/([a-f0-9]{32})/([a-f0-9]{32})$',
            f'1/{deck["instance_id"]}/{killer["instance_id"]}')
        deployed = self.call(server.Handler.api_character_black_ice_deploy,
                             deploy_match, {
            'revision': 2, 'mode': 'deploy_combat', 'floor_label': 'Floor 3',
            'target_label': 'Enemy Netrunner',
            'reason': 'Deploy Killer into active NET combat',
        })
        entity = deployed['net_entity']
        entity_id = entity['net_entity_id']
        self.assertRegex(entity_id, r'^[a-f0-9]{32}$')
        self.assertEqual(entity['status'], 'hunting')
        self.assertEqual(entity['target_type'], 'enemy_program_source')
        self.assertEqual(entity['rez_current'], 20)
        self.assertGreaterEqual(entity['initiative'], 9)
        self.assertLessEqual(entity['initiative'], 18)
        runtime = deployed['character']['data']['program_state'][killer['instance_id']]
        self.assertEqual(runtime['status'], 'rezzed')

        public_data = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        public_data['visibility'] = {
            **server.ensure_character_visibility(public_data),
            'equipment': True, 'combat': True,
        }
        self.conn.execute('UPDATE characters SET data=? WHERE id=1',
                          (json.dumps(public_data),))
        self.conn.commit()
        self.current = self.user('other')
        public = self.call(server.Handler.api_get_character, self.match(1))
        public_entity = public['derived']['effective_cyberdecks'][
            deck['instance_id']]['programs'][0]['net_entity']
        self.assertNotIn('floor_label', public_entity)
        self.assertNotIn('target_label', public_entity)
        self.assertNotIn('initiative_roll', public_entity)
        self.current = self.user('runner')

        with self.assertRaises(server.ApiError) as duplicate:
            self.call(server.Handler.api_character_black_ice_deploy,
                      deploy_match, {
                'revision': 3, 'mode': 'lie_in_wait', 'floor_label': 'Floor 3',
                'reason': 'Try duplicate deployment from one Program copy',
            })
        self.assertEqual(duplicate.exception.status, 409)
        entity_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$', f'1/{entity_id}')
        damaged = self.call(server.Handler.api_character_net_entity_action,
                            entity_match, {
            'revision': 3, 'action': 'damage', 'amount': 5,
            'reason': 'Killer takes Zap damage',
        })
        self.assertEqual(damaged['net_entity']['rez_current'], 15)
        slid = self.call(server.Handler.api_character_net_entity_action,
                         entity_match, {
            'revision': 4, 'action': 'slide',
            'reason': 'Enemy Netrunner succeeds on Slide',
        })
        self.assertEqual(slid['net_entity']['status'], 'lying_in_wait')
        self.assertIsNone(slid['net_entity']['target_label'])
        engaged = self.call(server.Handler.api_character_net_entity_action,
                            entity_match, {
            'revision': 5, 'action': 'engage', 'floor_label': 'Floor 3',
            'target_label': 'Second Enemy Netrunner',
            'reason': 'Killer acquires a new valid Program source',
        })
        self.assertEqual(engaged['net_entity']['status'], 'hunting')
        derezzed = self.call(server.Handler.api_character_net_entity_action,
                             entity_match, {
            'revision': 6, 'action': 'damage', 'amount': 20,
            'reason': 'Killer is reduced to zero REZ',
        })
        self.assertEqual(derezzed['net_entity']['status'], 'derezzed')
        killer_mod_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$', f'1/{killer_mod_id}')
        with self.assertRaises(server.ApiError) as active_uninstall:
            self.call(server.Handler.api_character_modification_action,
                      killer_mod_match, {
                'revision': 7, 'action': 'remove',
                'reason': 'Try uninstalling active Black ICE entity',
            })
        self.assertEqual(active_uninstall.exception.status, 409)
        deactivated = self.call(server.Handler.api_character_net_entity_action,
                                entity_match, {
            'revision': 7, 'action': 'deactivate',
            'reason': 'Spend NET Action to deactivate Killer',
        })
        self.assertEqual(deactivated['net_entity']['status'], 'deactivated')
        self.assertEqual(deactivated['character']['data']['program_state'][
            killer['instance_id']]['rez_current'], 20)

        waiting = self.call(server.Handler.api_character_black_ice_deploy,
                            deploy_match, {
            'revision': 8, 'mode': 'lie_in_wait', 'floor_label': 'Floor 5',
            'reason': 'Place Killer on Floor 5 to lie in wait',
        })
        waiting_entity = waiting['net_entity']
        self.assertEqual(waiting_entity['status'], 'lying_in_wait')
        waiting_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$',
            f'1/{waiting_entity["net_entity_id"]}')
        destroyed = self.call(server.Handler.api_character_net_entity_action,
                              waiting_match, {
            'revision': 9, 'action': 'destroy',
            'reason': 'Destroy Killer entity and Program copy',
        })
        killer_after = next(item for item in destroyed['character']['data']['inventory']
                            if item['instance_id'] == killer['instance_id'])
        self.assertEqual(killer_after['state'], 'broken')
        self.assertFalse(destroyed['character']['derived']['effective_cyberdecks'][
            deck['instance_id']]['programs'])
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(ledger['entries'][0]['can_revert'])
        reverted = self.call(server.Handler.api_character_ledger_revert,
                             self.match(1, ledger['entries'][0]['id']), {
            'revision': 10, 'reason': 'Undo incorrect Black ICE destruction',
        })
        restored_killer = next(item for item in reverted['data']['inventory']
                               if item['instance_id'] == killer['instance_id'])
        self.assertEqual(restored_killer['state'], 'installed')
        restored_program = reverted['derived']['effective_cyberdecks'][
            deck['instance_id']]['programs'][0]
        self.assertEqual(restored_program['net_entity']['status'], 'lying_in_wait')
        self.assertEqual(restored_program['runtime']['status'], 'rezzed')

    def test_vehicle_garage_installs_prerequisites_and_preserves_nomad_access_semantics(self):
        edited = copy.deepcopy(self.character_data)
        edited['inventory'] = [
            {
                'key': item_id, 'catalog_item_id': item_id,
                'cat': server.item_by_id(item_id)['cat'],
                'name': server.item_by_id(item_id)['name'], 'qty': 1,
                'state': 'carried', 'acquisition_source': 'loot',
            }
            for item_id in ('vehicles-2', 'vehicles_upgrades-9', 'vehicles_upgrades-18')
        ]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add Compact Groundcar and garage upgrades', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        vehicle = by_name['Compact Groundcar']
        heavy, housing = by_name['Heavy Chassis'], by_name['Housing Capacity']
        management = self.call(server.Handler.api_character_modifications, self.match(1))
        vehicle_payload = next(item for item in management['vehicle_hosts']
                               if item['instance_id'] == vehicle['instance_id'])
        self.assertEqual(vehicle_payload['sdp'], 50)
        heavy_payload = next(item for item in management['vehicle_upgrades']
                             if item['instance_id'] == heavy['instance_id'])
        heavy_compatibility = heavy_payload['compatibility'][vehicle['instance_id']]
        self.assertTrue(heavy_compatibility['allowed'])
        self.assertFalse(heavy_compatibility['role_access_item'])
        self.assertEqual(heavy_compatibility['nomad_access_required'], 1)
        housing_payload = next(item for item in management['vehicle_upgrades']
                               if item['instance_id'] == housing['instance_id'])
        self.assertFalse(housing_payload['compatibility'][vehicle['instance_id']]['allowed'])

        installed_heavy = self.call(server.Handler.api_character_modification_install,
                                    self.match(1), {
            'revision': 1, 'host_instance_id': vehicle['instance_id'],
            'upgrade_instance_id': heavy['instance_id'], 'manual_confirm': False,
            'reason': 'Install purchased Heavy Chassis',
        })
        heavy_mod_id = installed_heavy['modification_id']
        self.assertEqual(installed_heavy['character']['revision'], 2)
        heavy_after = next(item for item in installed_heavy['character']['data']['inventory']
                           if item['instance_id'] == heavy['instance_id'])
        self.assertEqual(heavy_after['state'], 'installed')
        management = installed_heavy['management']
        housing_payload = next(item for item in management['vehicle_upgrades']
                               if item['instance_id'] == housing['instance_id'])
        self.assertTrue(housing_payload['compatibility'][vehicle['instance_id']]['allowed'])
        installed_housing = self.call(server.Handler.api_character_modification_install,
                                      self.match(1), {
            'revision': 2, 'host_instance_id': vehicle['instance_id'],
            'upgrade_instance_id': housing['instance_id'], 'manual_confirm': False,
            'reason': 'Install Housing Capacity after Heavy Chassis',
        })
        housing_mod_id = installed_housing['modification_id']
        self.assertEqual(installed_housing['character']['revision'], 3)
        effective_vehicle = installed_housing['character']['derived']['effective_vehicles'][vehicle['instance_id']]
        self.assertEqual(effective_vehicle['base']['sdp'], 50)
        self.assertEqual(effective_vehicle['effective']['sdp'], 70)
        self.assertEqual(effective_vehicle['state'], {'sdp_current': 70, 'sdp_max': 70})
        damaged = self.call(server.Handler.api_character_resource, self.match(1), {
            'revision': 3, 'resource': 'vehicle_sdp', 'subject': vehicle['instance_id'],
            'action': 'delta', 'value': -10,
        })
        self.assertEqual(damaged['revision'], 4)
        self.assertEqual(damaged['data']['vehicle_state'][vehicle['instance_id']],
                         {'sdp_current': 60, 'sdp_max': 70})
        damage_ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertEqual(damage_ledger['entries'][0]['category'], 'vehicle')
        self.assertIn('Vehicle SDP', damage_ledger['entries'][0]['reason'])
        heavy_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{heavy_mod_id}')
        with self.assertRaises(server.ApiError) as dependency:
            self.call(server.Handler.api_character_modification_action, heavy_match, {
                'revision': 4, 'action': 'remove', 'reason': 'try removing prerequisite',
            })
        self.assertEqual(dependency.exception.status, 409)
        housing_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{housing_mod_id}')
        removed_housing = self.call(server.Handler.api_character_modification_action,
                                    housing_match, {
            'revision': 4, 'action': 'remove', 'reason': 'Remove dependent housing first',
        })
        self.assertEqual(removed_housing['character']['revision'], 5)
        removed_heavy = self.call(server.Handler.api_character_modification_action,
                                  heavy_match, {
            'revision': 5, 'action': 'remove', 'reason': 'Remove Heavy Chassis after housing',
        })
        self.assertEqual(removed_heavy['character']['revision'], 6)
        self.assertFalse(removed_heavy['management']['modifications'])
        final_state = removed_heavy['character']['data']['vehicle_state'][vehicle['instance_id']]
        self.assertEqual(final_state, {'sdp_current': 40, 'sdp_max': 50})

    def test_vehicle_nos_and_mounted_weapons_are_authoritative_and_audited(self):
        edited = copy.deepcopy(self.character_data)
        item_ids = (
            'vehicles-2', 'vehicles_upgrades-3', 'vehicles_upgrades-4',
            'vehicles_upgrades-5', 'ammo-0',
        )
        edited['inventory'] = []
        for item_id in item_ids:
            item = server.item_by_id(item_id)
            edited['inventory'].append({
                'key': item_id, 'catalog_item_id': item_id,
                'cat': item['cat'], 'name': item['name'],
                'qty': 3 if item_id == 'ammo-0' else 1,
                'state': 'carried', 'acquisition_source': 'loot',
            })
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add vehicle action test loadout', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        vehicle = by_name['Compact Groundcar']
        nos = by_name['NOS']
        machinegun = by_name['Onboard Machinegun']
        flamethrower = by_name['Onboard Flamethrower']
        rifle_ammo = by_name['Basic']

        installed_nos = self.call(server.Handler.api_character_modification_install,
                                  self.match(1), {
            'revision': 1, 'host_instance_id': vehicle['instance_id'],
            'upgrade_instance_id': nos['instance_id'], 'manual_confirm': False,
            'reason': 'Install NOS tank for field test',
        })
        nos_mod_id = installed_nos['modification_id']
        nos_state = installed_nos['character']['data']['modification_state'][nos_mod_id]
        self.assertEqual(nos_state['resource_type'], 'nos_tank')
        self.assertEqual(nos_state['uses_remaining'], 1)
        nos_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{nos_mod_id}')
        used = self.call(server.Handler.api_character_modification_action, nos_match, {
            'revision': 2, 'action': 'use_nos',
        })
        self.assertEqual(
            used['character']['data']['modification_state'][nos_mod_id]['uses_remaining'], 0)
        self.assertEqual(used['character']['revision'], 3)
        with self.assertRaises(server.ApiError) as duplicate_use:
            self.call(server.Handler.api_character_modification_action, nos_match, {
                'revision': 3, 'action': 'use_nos',
            })
        self.assertEqual(duplicate_use.exception.status, 409)
        with self.assertRaises(server.ApiError):
            self.call(server.Handler.api_character_modification_action, nos_match, {
                'revision': 3, 'action': 'reset_nos',
            })
        reset = self.call(server.Handler.api_character_modification_action, nos_match, {
            'revision': 3, 'action': 'reset_nos',
            'reason': 'Campaign clock advanced to the next day',
        })
        self.assertEqual(
            reset['character']['data']['modification_state'][nos_mod_id]['uses_remaining'], 1)

        installed_machinegun = self.call(
            server.Handler.api_character_modification_install, self.match(1), {
                'revision': 4, 'host_instance_id': vehicle['instance_id'],
                'upgrade_instance_id': machinegun['instance_id'],
                'manual_confirm': False, 'configuration': {},
                'reason': 'Install front-facing onboard machinegun',
            })
        machinegun_mod_id = installed_machinegun['modification_id']
        machinegun_state = installed_machinegun['character']['data'][
            'modification_state'][machinegun_mod_id]
        self.assertEqual(machinegun_state['orientation'], 'front')
        self.assertEqual(machinegun_state['magazine'], 0)
        self.assertEqual(machinegun_state['magazine_max'], 30)
        self.assertEqual(machinegun_state['reserve'], 0)
        self.assertEqual(machinegun_state['ammo_cost'], 10)
        self.assertEqual(installed_machinegun['character']['derived']['effective_vehicles'][
            vehicle['instance_id']]['mounted_weapons'][0]['shared_ammo_available'], 30)
        machinegun_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$', f'1/{machinegun_mod_id}')
        reloaded = self.call(server.Handler.api_character_modification_action,
                             machinegun_match, {
            'revision': 5, 'action': 'reload',
            'ammo_instance_id': rifle_ammo['instance_id'],
        })
        reloaded_state = reloaded['character']['data'][
            'modification_state'][machinegun_mod_id]
        self.assertEqual((reloaded_state['magazine'], reloaded_state['reserve']), (30, 0))
        self.assertFalse(any(item.get('instance_id') == rifle_ammo['instance_id']
                             for item in reloaded['character']['data']['inventory']))
        self.assertEqual(reloaded['character']['derived']['effective_vehicles'][
            vehicle['instance_id']]['mounted_weapons'][0]['shared_ammo_available'], 0)
        fired = self.call(server.Handler.api_character_modification_action,
                          machinegun_match, {
            'revision': 6, 'action': 'fire',
        })
        self.assertEqual(fired['character']['data'][
            'modification_state'][machinegun_mod_id]['magazine'], 20)
        self.assertEqual(fired['character']['derived']['effective_vehicles'][
            vehicle['instance_id']]['mounted_weapons'][0]['kind'], 'autofire')
        action_ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(action_ledger['entries'][0]['can_revert'])
        reverted_fire = self.call(
            server.Handler.api_character_ledger_revert,
            self.match(1, action_ledger['entries'][0]['id']), {
                'revision': 7, 'reason': 'Undo accidental mounted weapon fire',
            })
        self.assertEqual(reverted_fire['data']['modification_state'][
            machinegun_mod_id]['magazine'], 30)
        with self.assertRaises(server.ApiError) as permanent:
            self.call(server.Handler.api_character_modification_action,
                      machinegun_match, {
                'revision': 8, 'action': 'remove',
                'reason': 'Try removing permanent onboard weapon',
            })
        self.assertEqual(permanent.exception.status, 409)

        with self.assertRaises(server.ApiError) as missing_orientation:
            self.call(server.Handler.api_character_modification_install,
                      self.match(1), {
                'revision': 8, 'host_instance_id': vehicle['instance_id'],
                'upgrade_instance_id': flamethrower['instance_id'],
                'manual_confirm': False,
                'reason': 'Try installation without choosing orientation',
            })
        self.assertEqual(missing_orientation.exception.status, 400)
        installed_flamethrower = self.call(
            server.Handler.api_character_modification_install, self.match(1), {
                'revision': 8, 'host_instance_id': vehicle['instance_id'],
                'upgrade_instance_id': flamethrower['instance_id'],
                'manual_confirm': False, 'configuration': {'orientation': 'side'},
                'reason': 'Install side-facing onboard flamethrower',
            })
        flame_mod_id = installed_flamethrower['modification_id']
        self.assertEqual(installed_flamethrower['character']['data'][
            'modification_state'][flame_mod_id]['orientation'], 'side')
        profiles = installed_flamethrower['character']['derived']['effective_vehicles'][
            vehicle['instance_id']]['mounted_weapons']
        self.assertEqual({profile['id'] for profile in profiles},
                         {'onboard_machinegun', 'onboard_flamethrower'})
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        action_entries = [entry for entry in ledger['entries']
                          if entry['category'] == 'vehicle']
        self.assertGreaterEqual(len(action_entries), 4)
        self.assertTrue(any('Use NOS' in entry['reason'] for entry in action_entries))
        self.assertTrue(any('Fire Onboard Machinegun' in entry['reason']
                            for entry in action_entries))

    def test_vehicle_repair_workflow_uses_damage_severity_check_and_history(self):
        edited = copy.deepcopy(self.character_data)
        vehicle_item = server.item_by_id('vehicles-2')
        edited['inventory'] = [{
            'key': vehicle_item['id'], 'catalog_item_id': vehicle_item['id'],
            'cat': vehicle_item['cat'], 'name': vehicle_item['name'], 'qty': 1,
            'state': 'carried', 'acquisition_source': 'loot',
        }]
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add repair workflow test vehicle', 'data': edited,
        })
        vehicle = updated['data']['inventory'][0]
        damaged = self.call(server.Handler.api_character_resource, self.match(1), {
            'revision': 1, 'resource': 'vehicle_sdp',
            'subject': vehicle['instance_id'], 'action': 'delta', 'value': -10,
        })
        self.assertEqual(damaged['data']['vehicle_state'][
            vehicle['instance_id']]['sdp_current'], 40)
        repair_match = re.match(
            r'^(\d+)/([a-f0-9]{32})$', f'1/{vehicle["instance_id"]}')
        started = self.call(server.Handler.api_character_vehicle_repair,
                            repair_match, {
            'revision': 2, 'action': 'start', 'technician': 'Yokai',
            'reason': 'Repair collision damage in the garage',
        })
        repair = started['character']['data']['vehicle_state'][
            vehicle['instance_id']]['repair']
        self.assertEqual(repair['severity'], 'minor')
        self.assertEqual((repair['dv'], repair['duration_key']), (9, '3_hours'))
        self.assertEqual(repair['skill'], 'Land Vehicle Tech')
        public_data = json.loads(self.conn.execute(
            'SELECT data FROM characters WHERE id=1').fetchone()['data'])
        public_data['visibility'] = {
            **server.ensure_character_visibility(public_data),
            'equipment': True, 'combat': True,
        }
        self.conn.execute('UPDATE characters SET data=? WHERE id=1',
                          (json.dumps(public_data),))
        self.conn.commit()
        self.current = self.user('other')
        public_repair = self.call(server.Handler.api_get_character, self.match(1))[
            'derived']['effective_vehicles'][vehicle['instance_id']]['state']['repair']
        self.assertNotIn('technician', public_repair)
        self.current = self.user('runner')
        with self.assertRaises(server.ApiError) as instant_repair:
            self.call(server.Handler.api_character_resource, self.match(1), {
                'revision': 3, 'resource': 'vehicle_sdp',
                'subject': vehicle['instance_id'], 'action': 'reset', 'value': 0,
            })
        self.assertEqual(instant_repair.exception.status, 409)

        failed = self.call(server.Handler.api_character_vehicle_repair,
                           repair_match, {
            'revision': 3, 'action': 'resolve', 'check_total': 8,
            'reason': 'Repair Check failed halfway through the work',
        })
        failed_state = failed['character']['data']['vehicle_state'][vehicle['instance_id']]
        self.assertEqual(failed_state['sdp_current'], 40)
        self.assertNotIn('repair', failed_state)
        self.assertEqual(failed_state['repair_history'][-1]['status'], 'failed')

        restarted = self.call(server.Handler.api_character_vehicle_repair,
                              repair_match, {
            'revision': 4, 'action': 'start', 'technician': 'Yokai',
            'reason': 'Restart repair from scratch after failed check',
        })
        self.assertEqual(restarted['character']['revision'], 5)
        repaired = self.call(server.Handler.api_character_vehicle_repair,
                             repair_match, {
            'revision': 5, 'action': 'resolve', 'check_total': 9,
            'reason': 'Repair Check succeeded after required work time',
        })
        repaired_state = repaired['character']['data']['vehicle_state'][vehicle['instance_id']]
        self.assertEqual(repaired_state['sdp_current'], 50)
        self.assertEqual(repaired_state['repair_history'][-1]['status'], 'success')
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(ledger['entries'][0]['can_revert'])
        reverted = self.call(server.Handler.api_character_ledger_revert,
                             self.match(1, ledger['entries'][0]['id']), {
            'revision': 6, 'reason': 'Undo incorrectly resolved Repair Check',
        })
        reverted_state = reverted['data']['vehicle_state'][vehicle['instance_id']]
        self.assertEqual(reverted_state['sdp_current'], 40)
        self.assertEqual(reverted_state['repair']['status'], 'in_progress')

    def test_vehicle_heavy_weapon_mount_binds_a_concrete_two_handed_weapon(self):
        edited = copy.deepcopy(self.character_data)
        item_ids = (
            'vehicles-2', 'vehicles_upgrades-9', 'vehicles_upgrades-18',
            'vehicles_upgrades-11', 'guns-6', 'guns-1', 'ammo-0',
        )
        edited['inventory'] = []
        for item_id in item_ids:
            item = server.item_by_id(item_id)
            edited['inventory'].append({
                'key': item_id, 'catalog_item_id': item_id,
                'cat': item['cat'], 'name': item['name'],
                'qty': 3 if item_id == 'ammo-0' else 1,
                'state': 'carried', 'acquisition_source': 'loot',
            })
        updated = self.call(server.Handler.api_character_sheet_update, self.match(1), {
            'revision': 0, 'reason': 'Add heavy mount test loadout', 'data': edited,
        })
        by_name = {item['name']: item for item in updated['data']['inventory']}
        vehicle = by_name['Compact Groundcar']
        heavy = by_name['Heavy Chassis']
        housing = by_name['Housing Capacity']
        mount = by_name['Vehicle Heavy Weapon Mount']
        rifle = by_name['Assault Rifle']
        pistol = by_name['Heavy Pistol']

        self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 1, 'host_instance_id': vehicle['instance_id'],
            'upgrade_instance_id': heavy['instance_id'], 'manual_confirm': False,
            'reason': 'Install required Heavy Chassis',
        })
        self.call(server.Handler.api_character_modification_install, self.match(1), {
            'revision': 2, 'host_instance_id': vehicle['instance_id'],
            'upgrade_instance_id': housing['instance_id'], 'manual_confirm': False,
            'reason': 'Install Housing Capacity for future expansion',
        })
        installed_mount = self.call(
            server.Handler.api_character_modification_install, self.match(1), {
                'revision': 3, 'host_instance_id': vehicle['instance_id'],
                'upgrade_instance_id': mount['instance_id'], 'manual_confirm': True,
                'reason': 'Install passenger heavy weapon mount',
            })
        mount_id = installed_mount['modification_id']
        mount_state = installed_mount['character']['data']['modification_state'][mount_id]
        self.assertEqual(mount_state['resource_type'], 'heavy_weapon_mount')
        self.assertIsNone(mount_state['weapon_instance_id'])
        effective = installed_mount['character']['derived']['effective_vehicles'][
            vehicle['instance_id']]
        self.assertEqual(effective['effective']['seats'], 3)
        self.assertIsNone(effective['weapon_mounts'][0]['bound_weapon'])
        mount_match = re.match(r'^(\d+)/([a-f0-9]{32})$', f'1/{mount_id}')

        with self.assertRaises(server.ApiError) as one_handed:
            self.call(server.Handler.api_character_modification_action, mount_match, {
                'revision': 4, 'action': 'mount_weapon',
                'weapon_instance_id': pistol['instance_id'],
                'reason': 'Try mounting a one-handed pistol',
            })
        self.assertEqual(one_handed.exception.status, 400)
        mounted = self.call(server.Handler.api_character_modification_action,
                            mount_match, {
            'revision': 4, 'action': 'mount_weapon',
            'weapon_instance_id': rifle['instance_id'],
            'reason': 'Passenger secures the rifle to the swivel mount',
        })
        mounted_rifle = next(item for item in mounted['character']['data']['inventory']
                             if item['instance_id'] == rifle['instance_id'])
        self.assertEqual(mounted_rifle['state'], 'installed')
        self.assertEqual(mounted_rifle['mounted_modification_id'], mount_id)
        bound = mounted['character']['derived']['effective_vehicles'][
            vehicle['instance_id']]['weapon_mounts'][0]['bound_weapon']
        self.assertEqual(bound['weapon_instance_id'], rifle['instance_id'])
        self.assertEqual(bound['skill'], 'Shoulder Arms')
        self.assertEqual(bound['state']['magazine'], 25)
        mount_ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(mount_ledger['entries'][0]['can_revert'])
        reverted_mount = self.call(
            server.Handler.api_character_ledger_revert,
            self.match(1, mount_ledger['entries'][0]['id']), {
                'revision': 5, 'reason': 'Undo accidental weapon binding',
            })
        reverted_rifle = next(item for item in reverted_mount['data']['inventory']
                              if item['instance_id'] == rifle['instance_id'])
        self.assertEqual(reverted_rifle['state'], 'carried')
        self.assertIsNone(reverted_mount['data']['modification_state'][
            mount_id]['weapon_instance_id'])
        remounted = self.call(server.Handler.api_character_modification_action,
                              mount_match, {
            'revision': 6, 'action': 'mount_weapon',
            'weapon_instance_id': rifle['instance_id'],
            'reason': 'Passenger confirms the intended rifle binding',
        })
        remounted_rifle = next(
            item for item in remounted['character']['data']['inventory']
            if item['instance_id'] == rifle['instance_id'])
        self.assertEqual(remounted_rifle['state'], 'installed')

        with self.assertRaises(server.ApiError) as sell_mounted:
            self.call(server.Handler.api_sell, body={
                'char_id': 1, 'instance_id': rifle['instance_id'], 'qty': 1,
            })
        self.assertEqual(sell_mounted.exception.status, 409)
        with self.assertRaises(server.ApiError) as bypass:
            self.call(server.Handler.api_character_resource, self.match(1), {
                'revision': 7, 'resource': 'weapon', 'subject': rifle['instance_id'],
                'action': 'fire', 'value': 1,
            })
        self.assertEqual(bypass.exception.status, 409)
        fired = self.call(server.Handler.api_character_modification_action,
                          mount_match, {
            'revision': 7, 'action': 'fire',
        })
        self.assertEqual(fired['character']['data']['weapon_state'][
            rifle['instance_id']]['magazine'], 24)
        with self.assertRaises(server.ApiError) as occupied_mount:
            self.call(server.Handler.api_character_modification_action,
                      mount_match, {
                'revision': 8, 'action': 'remove',
                'reason': 'Try removing an occupied mount',
            })
        self.assertEqual(occupied_mount.exception.status, 409)

        unmounted = self.call(server.Handler.api_character_modification_action,
                              mount_match, {
            'revision': 8, 'action': 'unmount_weapon',
            'reason': 'Passenger removes the rifle using an Action',
        })
        unmounted_rifle = next(item for item in unmounted['character']['data']['inventory']
                               if item['instance_id'] == rifle['instance_id'])
        self.assertEqual(unmounted_rifle['state'], 'carried')
        self.assertNotIn('mounted_modification_id', unmounted_rifle)
        self.assertEqual(unmounted['character']['data']['weapon_state'][
            rifle['instance_id']]['magazine'], 24)
        removed = self.call(server.Handler.api_character_modification_action,
                            mount_match, {
            'revision': 9, 'action': 'remove',
            'reason': 'Remove the now-empty heavy weapon mount',
        })
        self.assertNotIn(mount_id, removed['character']['data']['modification_state'])
        ledger = self.call(server.Handler.api_character_ledger, self.match(1))
        self.assertTrue(any('Mount Assault Rifle' in entry['reason']
                            for entry in ledger['entries']))
        self.assertTrue(any('Unmount Assault Rifle' in entry['reason']
                            for entry in ledger['entries']))

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
        combat_only = self.call(server.Handler.api_save_character, self.match(1), {
            'revision': 0, 'patch': {'visibility': {'combat': True}},
        })
        self.current = self.user('other')
        combat_visible = self.call(server.Handler.api_get_character, self.match(1))
        self.assertTrue(combat_visible['derived'])
        self.assertNotIn('inventory', combat_visible['data'])
        self.assertNotIn('effective_weapons', combat_visible['derived'])
        self.assertNotIn('effective_vehicles', combat_visible['derived'])
        self.assertNotIn('effective_cyberdecks', combat_visible['derived'])
        self.assertNotIn('modifications', combat_visible['derived'])

        self.current = self.user('runner')
        updated = self.call(server.Handler.api_save_character, self.match(1), {
            'revision': combat_only['revision'],
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
