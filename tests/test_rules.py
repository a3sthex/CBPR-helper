import ast
import copy
import importlib.util
import json
import re
import sqlite3
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cbpr_server', ROOT / 'app/server.py')
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)
server.load_catalog()


def valid_character(role='Solo'):
    stats = {name: 6 for name in server.STATS}
    stats['WILL'] = 7
    stats['BODY'] = 7
    skills = {name: 2 for name in server.MUST_SKILLS
              if name not in ('Language', 'Local Expert')}
    skills['Language (Streetslang)'] = 2
    skills['Local Expert (Свой район)'] = 2
    skills['Language (Русский)'] = 4
    extras = [name for _, name, _, is_x2 in server.SKILLS
              if name not in server.MUST_SKILLS and not is_x2 and
              name not in ('Language', 'Local Expert', 'Science', 'Play Instrument')]
    for name in extras[:10]:
        skills[name] = 6
    setup = {}
    if role == 'Tech':
        setup = {'field': 2, 'upgrade': 2, 'fabrication': 2, 'invention': 2}
    elif role == 'Medtech':
        setup = {'surgery': 2, 'pharma': 1, 'cryo': 1}
    elif role == 'Exec':
        setup = {'team_member': 'Телохранитель'}
    elif role == 'Nomad':
        setup = {'moto_choices': ['Roadbike', 'Bulletproof Glass', 'Heavy Chassis', 'Housing Capacity']}
    role_fields = {
        'Rockerboy': ('kind', 'act', 'venue', 'enemy'),
        'Solo': ('kind', 'moral', 'enemy', 'territory'),
        'Netrunner': ('kind', 'partner', 'workspace', 'clients', 'supplies', 'enemy'),
        'Tech': ('kind', 'partner', 'workspace', 'clients', 'supplies', 'enemy'),
        'Medtech': ('kind', 'partner', 'workspace', 'clients', 'supplies'),
        'Media': ('kind', 'channel', 'ethics', 'stories'),
        'Exec': ('kind', 'division', 'ethics', 'base', 'enemy', 'boss'),
        'Lawman': ('position', 'jurisdiction', 'corruption', 'enemy', 'target'),
        'Fixer': ('kind', 'partner', 'office', 'clients', 'enemy'),
        'Nomad': ('size', 'domain', 'activity', 'duty', 'philosophy', 'enemy'),
    }[role]
    return {
        'handle': 'Test Runner', 'role': role, 'role_rank': 4,
        'role_setup': setup, 'stats': stats, 'skills': skills,
        'native_language': 'Русский', 'lifepath_mode': 'cemk',
        'lifepath': {key: ('Восточная Европа' if key == 'region' else 'тест') for key in (
            'region', 'personality', 'wardrobe', 'hair_style', 'hair_color',
            'value', 'people', 'family', 'environment', 'crisis', 'friends',
            'friend_role', 'friend_circle', 'enemies', 'enemy_role', 'enemy_circle',
            'love', 'goal')},
        'role_lifepath': {key: 'тест' for key in role_fields},
        'inventory': [],
        'cyberware': [{
            'key': 'creation-neuroport', 'name': 'Neuroport', 'hl': 0,
            'price': 0, 'type': 'Neuralware', 'creation_free': True,
            'humanity_exempt': True,
        }],
        'armor': {}, 'cash': 2550,
        'creation': {'sold_soul': False, 'free_neuroport': True},
        'public': True,
    }


def valid_merged_character(role='Solo'):
    char = valid_character(role)
    char['first_name'] = 'Ирина'
    char['last_name'] = 'Волкова'
    char['lifepath_mode'] = 'merged'
    char['lifepath'] = {key: ('Восточная Европа' if key == 'region' else 'тест') for key in (
        'region', 'personality', 'clothing', 'hair', 'hair_color', 'affectation',
        'value', 'people', 'person', 'possession', 'family', 'environment', 'crisis', 'goal')}
    char['skill_pools'] = {
        'Language': 2, 'Local Expert': 2, 'Martial Arts': 0,
        'Science': 0, 'Play Instrument': 0,
    }
    return char


class MediaAndProgressionTests(unittest.TestCase):
    def test_png_signature_and_dimensions(self):
        raw = b'\x89PNG\r\n\x1a\n' + b'\x00' * 8 + (1000).to_bytes(4, 'big') + (1250).to_bytes(4, 'big')
        self.assertEqual(server.image_info(raw), ('image/png', 'png', 1000, 1250))

    def test_role_art_is_valid_webp(self):
        raw = (ROOT / 'app/static/role-art/nomad.webp').read_bytes()
        info = server.image_info(raw)
        self.assertIsNotNone(info)
        self.assertEqual(info[0], 'image/webp')
        self.assertGreater(info[2], 100)
        self.assertGreater(info[3], 300)

    def test_theme_contrast_is_server_validated(self):
        server.validate_theme({'bg': '#000000', 'panel': '#111111', 'text': '#ffffff'})
        with self.assertRaisesRegex(server.ApiError, '4.5:1'):
            server.validate_theme({'bg': '#111111', 'panel': '#111111', 'text': '#222222'})

    def test_legacy_character_gets_progression_schema(self):
        data = server.ensure_progression({'role': 'Solo', 'role_rank': 4,
                                          'role_setup': {}, 'stats': {'LUCK': 6}})
        self.assertEqual(data['luck_cur'], 6)
        self.assertEqual(data['active_role'], 'Solo')
        self.assertEqual(data['roles'][0]['rank'], 4)
        self.assertEqual(data['schema_version'], 8)


class LocalizationTests(unittest.TestCase):
    def test_server_errors_follow_requested_language(self):
        message = 'Требуется вход в систему'
        self.assertEqual(server.server_error_message(message, 'en'), 'Authentication required')
        self.assertEqual(server.server_error_message(message, 'ru'), message)


class DerivedRulesTests(unittest.TestCase):
    def test_humanity_current_and_maximum_are_separate(self):
        result = server.derive({
            'stats': {'EMP': 8},
            'cyberware': [{'name': 'Neuroport', 'hl': 7, 'type': 'Neuralware'}],
        })
        self.assertEqual(result['humanity_cur'], 73)
        self.assertEqual(result['humanity_max'], 78)
        self.assertEqual(result['emp_cur'], 7)

    def test_free_cemk_neuroport_is_exempt(self):
        result = server.derive({
            'stats': {'EMP': 6},
            'cyberware': [{'key': 'creation-neuroport', 'name': 'Neuroport', 'hl': 0,
                           'type': 'Neuralware', 'humanity_exempt': True}],
        })
        self.assertEqual(result['humanity_cur'], 60)
        self.assertEqual(result['humanity_max'], 60)

    def test_armor_uses_highest_sp_and_strictest_penalty_once(self):
        result = server.derive({'stats': {'REF': 8, 'DEX': 7, 'MOVE': 6}, 'armor': {
            'body_outer': {'sp': 11, 'penalties': {'REF': 0, 'DEX': 0, 'MOVE': 0}},
            'body_inner': {'sp': 7, 'penalties': {'REF': -2, 'DEX': -3, 'MOVE': -4}},
            'head': {'sp': 13, 'penalties': {'REF': -3, 'DEX': -2, 'MOVE': -2}},
        }})
        self.assertEqual(result['sp_body'], 11)
        self.assertEqual(result['sp_head'], 13)
        self.assertEqual(result['armor_penalties'], {'REF': -3, 'DEX': -3, 'MOVE': -4})
        self.assertEqual(result['effects']['stats']['REF']['base'], 8)
        self.assertEqual(result['effects']['stats']['REF']['effective'], 5)


class StructuredEffectsTests(unittest.TestCase):
    def fashion_character(self, light_tattoos=0, chemskin=False, techhair=False):
        chrome = []
        for index in range(light_tattoos):
            chrome.append({
                'instance_id': f'{index + 1:032x}', 'key': 'cyberware-52',
                'catalog_item_id': 'cyberware-52', 'name': 'Light Tattoo',
                'state': 'installed', 'hl': 0, 'type': 'Fashionware',
            })
        for catalog_id, name, enabled in (
                ('cyberware-51', 'Chemskin', chemskin),
                ('cyberware-55', 'TechHair', techhair)):
            if enabled:
                chrome.append({
                    'instance_id': f'{len(chrome) + 10:032x}', 'key': catalog_id,
                    'catalog_item_id': catalog_id, 'name': name,
                    'state': 'installed', 'hl': 0, 'type': 'Fashionware',
                })
        return {
            'stats': {'COOL': 6, 'EMP': 6},
            'skills': {'Wardrobe & Style': 4, 'Personal Grooming': 3},
            'cyberware': chrome, 'armor': {},
        }

    def test_confirmed_fashionware_synergies_apply_once_and_independently(self):
        partial = server.derive(self.fashion_character(
            light_tattoos=2, chemskin=True, techhair=True))
        by_id = {rule['id']: rule for rule in partial['effects']['synergies']}
        self.assertFalse(by_id['light-tattoo-trio']['active'])
        self.assertEqual(by_id['light-tattoo-trio']['requirements'][0]['current'], 2)
        self.assertTrue(by_id['chemskin-techhair-combo']['active'])
        self.assertEqual(
            partial['effects']['skills']['Personal Grooming']['effective_check_base'], 11)
        self.assertEqual(
            partial['effects']['skills']['Wardrobe & Style']['effective_check_base'], 10)

        complete_character = self.fashion_character(
            light_tattoos=5, chemskin=True, techhair=True)
        complete = server.derive(complete_character)
        self.assertEqual(
            complete['effects']['skills']['Wardrobe & Style']['effective_check_base'], 12)
        self.assertEqual(
            complete['effects']['skills']['Personal Grooming']['effective_check_base'], 11)
        self.assertEqual(
            complete['effects']['skills']['Wardrobe & Style']['check_modifier'], 2)
        self.assertEqual(
            complete['effects']['skills']['Personal Grooming']['check_modifier'], 2)
        self.assertEqual(complete_character['skills']['Wardrobe & Style'], 4)
        self.assertEqual(complete_character['skills']['Personal Grooming'], 3)

    def test_synergy_activation_is_visible_in_readable_change_summary(self):
        before = self.fashion_character(light_tattoos=2)
        after = self.fashion_character(light_tattoos=3)
        changes = server.character_change_summary(before, after)
        effect = next(change for change in changes
                      if change['path'] == 'effects.synergy.light-tattoo-trio')
        self.assertIn('INACTIVE', effect['before'])
        self.assertIn('ACTIVE', effect['after'])
        self.assertIn('Light Tattoo Ensemble', effect['label'])

    def test_agent_automated_bonus_requires_active_gear_and_manual_rule_stays_manual(self):
        base = {
            'stats': {'INT': 6, 'COOL': 6, 'EMP': 6},
            'skills': {'Library Search': 4, 'Wardrobe & Style': 4},
            'inventory': [{
                'instance_id': 'a' * 32, 'key': 'gear-91',
                'catalog_item_id': 'gear-91', 'name': 'Agent (Standard)',
                'state': 'carried', 'active': False,
            }],
            'cyberware': [], 'armor': {},
        }
        inactive = server.derive(base)
        source = next(item for item in inactive['effects']['item_sources']
                      if item['id'] == 'agent-standard-active')
        self.assertFalse(source['active'])
        self.assertEqual(inactive['effects']['skills']['Library Search']['effective_check_base'], 10)

        active = copy.deepcopy(base)
        active['inventory'][0].update({
            'state': 'equipped', 'active': True,
            'equipped_mode': 'ready', 'equipped_slot': 'belt',
        })
        result = server.derive(active)
        source = next(item for item in result['effects']['item_sources']
                      if item['id'] == 'agent-standard-active')
        self.assertTrue(source['active'])
        self.assertEqual(result['effects']['skills']['Library Search']['effective_check_base'], 12)
        self.assertEqual(result['effects']['skills']['Library Search']['check_modifier'], 2)
        # Seasonal wardrobe advice remains explicit manual resolution.
        self.assertEqual(result['effects']['skills']['Wardrobe & Style']['effective_check_base'], 10)
        self.assertTrue(source['manual_rules'][0]['manual_resolution_required'])
        self.assertEqual(source['manual_rules'][0]['source'], 'CP:R 352')
        changes = server.character_change_summary(base, active)
        activation = next(change for change in changes
                          if change['path'] == 'effects.item_source.agent-standard-active')
        self.assertIn('INACTIVE', activation['before'])
        self.assertIn('ACTIVE', activation['after'])

        active['inventory'].append({**active['inventory'][0], 'instance_id': 'b' * 32})
        duplicated = server.derive(active)
        self.assertEqual(duplicated['effects']['skills']['Library Search']['check_modifier'], 2)

    def test_catalog_effect_coverage_distinguishes_automated_and_manual_rules(self):
        coverage = server.item_effect_coverage('gear-91')
        self.assertTrue(coverage['automated'])
        self.assertTrue(coverage['manual'])
        self.assertEqual(coverage['rules'][0]['source'], 'CP:R 352')
        self.assertIsNone(server.item_effect_coverage('gear-10'))

    def test_curated_use_presets_have_safe_duration_source_and_coverage(self):
        payload = server.load_effect_rules()
        by_id = {rule['id']: rule for rule in payload['use_effect_rules']}
        boost = by_id['boost-primary-effect']
        synthcoke = by_id['synthcoke-primary-effect']
        self.assertEqual((boost['duration_type'], boost['duration_value']), ('campaign_time', 1440))
        self.assertEqual(boost['effects'][0]['target'], 'character.stat.INT')
        self.assertEqual(boost['effects'][0]['source'], 'CP:R 357')
        self.assertEqual(synthcoke['effects'][0]['target'], 'character.stat.REF')
        self.assertEqual(synthcoke['effects'][0]['value'], 1)
        coverage = server.item_effect_coverage('gear-161')
        self.assertTrue(coverage['automated'])
        self.assertTrue(coverage['manual'])
        self.assertEqual(coverage['rules'][0]['kind'], 'use')

    def test_modifier_pipeline_is_deterministic_and_respects_stacking(self):
        modifiers = [
            {'id': 'unique-a', 'target': 'skill.Handgun.check', 'operation': 'add',
             'value': 2, 'stack_group': 'same', 'stack_policy': 'unique', 'priority': 100},
            {'id': 'unique-b', 'target': 'skill.Handgun.check', 'operation': 'add',
             'value': 2, 'stack_group': 'same', 'stack_policy': 'unique', 'priority': 200},
            {'id': 'stacked', 'target': 'skill.Handgun.check', 'operation': 'add',
             'value': 1, 'stack_group': 'other', 'stack_policy': 'stack', 'priority': 100},
            {'id': 'multiplier', 'target': 'skill.Handgun.check', 'operation': 'multiply',
             'value': 2, 'stack_group': 'multiply', 'stack_policy': 'unique', 'priority': 300},
        ]
        value, breakdown = server.apply_modifier_pipeline(5, modifiers)
        self.assertEqual(value, 16)  # (5 + 2 + 1) × 2
        self.assertEqual(sum(1 for item in breakdown if item['applied']), 3)
        self.assertEqual(sum(1 for item in breakdown if not item['applied']), 1)

    def test_effect_schema_rejects_non_allowlisted_or_executable_fields(self):
        server.validate_effect_definition({
            'id': 'safe-effect', 'target': 'skill.Handgun.check',
            'operation': 'add', 'value': 1,
        })
        with self.assertRaises(RuntimeError):
            server.validate_effect_definition({
                'id': 'unsafe-effect', 'target': 'skill.Handgun.check',
                'operation': 'add', 'value': 1, 'javascript': 'alert(1)',
            })
        with self.assertRaises(RuntimeError):
            server.validate_effect_definition({
                'id': 'unsafe-target', 'target': '__proto__.polluted',
                'operation': 'add', 'value': 1,
            })


class WeaponModificationEffectTests(unittest.TestCase):
    def owned(self, catalog_id, instance_id):
        item = copy.deepcopy(server.item_by_id(catalog_id))
        item.update({'key': catalog_id, 'catalog_item_id': catalog_id,
                     'instance_id': instance_id, 'qty': 1, 'state': 'carried'})
        return item

    def test_magazine_concealability_and_smartgun_requirements_are_effective_only(self):
        host = self.owned('guns-0', '1' * 32)
        drum = self.owned('gun_upgrades-4', '2' * 32)
        smart = self.owned('gun_upgrades-9', '3' * 32)
        drum['state'] = smart['state'] = 'installed'
        drum['host_instance_id'] = smart['host_instance_id'] = host['instance_id']
        owned = {item['instance_id']: item for item in (host, drum, smart)}
        modifications = [
            {
                'modification_id': 'a' * 32, 'host_instance_id': host['instance_id'],
                'upgrade_instance_id': drum['instance_id'], 'slots_used': 1, 'active': True,
                'configuration': {'effect_rules': server.weapon_modification_rules_for_catalog('gun_upgrades-4')},
            },
            {
                'modification_id': 'b' * 32, 'host_instance_id': host['instance_id'],
                'upgrade_instance_id': smart['instance_id'], 'slots_used': 2, 'active': True,
                'configuration': {'effect_rules': server.weapon_modification_rules_for_catalog('gun_upgrades-9')},
            },
        ]
        character = {'inventory': [host, drum, smart], 'cyberware': []}
        missing = server.evaluate_effective_weapon(host, modifications, owned, character)
        self.assertEqual(missing['base']['magazine'], 12)
        self.assertEqual(missing['effective']['magazine'], 36)
        self.assertEqual(missing['effective']['concealable'], 'NO')
        self.assertEqual(missing['attack_modifier'], 0)
        smart_source = next(source for source in missing['sources']
                            if source['id'] == 'smartgun-link-effective')
        self.assertFalse(smart_source['requirements_met'])

        character['cyberware'] = [{
            'key': 'cyberware-61', 'catalog_item_id': 'cyberware-61',
            'instance_id': '4' * 32, 'name': 'Interface Plugs', 'state': 'installed',
        }]
        connected = server.evaluate_effective_weapon(host, modifications, owned, character)
        self.assertEqual(connected['attack_modifier'], 1)
        self.assertEqual(host['mechanics']['magazine'], 12)
        self.assertEqual(host['mechanics']['concealable'], 'YES')

    def test_compatibility_rail_grants_exotic_scope_only_capacity(self):
        host = self.owned('guns-30', '7' * 32)
        rail = self.owned('gun_upgrades-16', '8' * 32)
        infrared = self.owned('gun_upgrades-7', '9' * 32)
        sniping = self.owned('gun_upgrades-10', 'a' * 32)
        owned = {item['instance_id']: item for item in (host, rail, infrared, sniping)}
        self.assertTrue(server.weapon_is_exotic(host))
        before = server.weapon_upgrade_compatibility(host, infrared, [], owned)
        self.assertFalse(before['allowed'])
        rail_check = server.weapon_upgrade_compatibility(host, rail, [], owned)
        self.assertTrue(rail_check['allowed'])
        self.assertTrue(rail_check['manual_resolution_required'])

        rail['state'] = 'installed'
        rail_mod = {
            'modification_id': 'd' * 32, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': rail['instance_id'], 'slots_used': 0, 'active': True,
            'configuration': {'slot_pool': None},
        }
        with_rail = server.weapon_upgrade_compatibility(host, infrared, [rail_mod], owned)
        self.assertTrue(with_rail['allowed'])
        self.assertEqual(with_rail['slot_pool'], 'scope')
        self.assertEqual(with_rail['slot_pool_total'], 1)
        infrared['state'] = 'installed'
        scope_mod = {
            'modification_id': 'e' * 32, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': infrared['instance_id'], 'slots_used': 1, 'active': True,
            'configuration': {'slot_pool': 'scope'},
        }
        pools = server.weapon_slot_capacity(host, [rail_mod, scope_mod], owned)
        self.assertEqual(pools['scope'], {'total': 1, 'used': 1})
        evaluated = server.evaluate_effective_weapon(
            host, [rail_mod, scope_mod], owned,
            {'inventory': [host, rail, infrared], 'cyberware': []})
        rail_source = next(source for source in evaluated['sources']
                           if source['id'].startswith('slot-grant:'))
        scope_source = next(source for source in evaluated['sources']
                            if source['id'] == 'infrared-nightvision-scope-rule')
        self.assertTrue(rail_source['automated'])
        self.assertEqual(rail_source['effects'][0]['target'], 'weapon.scope_slots')
        self.assertTrue(scope_source['manual_rules'][0]['manual_resolution_required'])
        second_scope = server.weapon_upgrade_compatibility(
            host, sniping, [rail_mod, scope_mod], owned)
        self.assertFalse(second_scope['allowed'])
        self.assertTrue(any('scope slots' in reason for reason in second_scope['reasons']))

    def test_underbarrel_rules_grant_separate_attack_profiles(self):
        grenade_rules = server.weapon_modification_rules_for_catalog('gun_upgrades-6')
        shotgun_rules = server.weapon_modification_rules_for_catalog('gun_upgrades-8')
        grenade = server.weapon_profiles_from_rules(grenade_rules)[0]
        shotgun = server.weapon_profiles_from_rules(shotgun_rules)[0]
        self.assertEqual((grenade['skill'], grenade['damage'], grenade['magazine']),
                         ('Heavy Weapons', '6d6', 1))
        self.assertEqual((shotgun['skill'], shotgun['damage'], shotgun['magazine']),
                         ('Shoulder Arms', '5d6', 2))
        self.assertEqual(grenade['hands_required'], 2)
        self.assertEqual(shotgun['ammo_kind'], 'shotgun')

    def test_pistol_autosear_and_configured_smg_autofire_profiles(self):
        standard = self.owned('guns-0', 'b' * 32)
        excellent = self.owned('guns-14', 'c' * 32)
        autosear = self.owned('gun_upgrades-20', 'd' * 32)
        autosear['state'] = 'installed'
        autosear_rules = server.weapon_modification_rules_for_catalog('gun_upgrades-20')
        modification = {
            'modification_id': 'f' * 32, 'host_instance_id': standard['instance_id'],
            'upgrade_instance_id': autosear['instance_id'], 'slots_used': 0, 'active': True,
            'configuration': {'effect_rules': autosear_rules, 'choices': {}},
        }
        standard_result = server.evaluate_effective_weapon(
            standard, [modification], {autosear['instance_id']: autosear},
            {'inventory': [standard, autosear], 'cyberware': []})
        self.assertEqual(standard_result['autofire_profiles'][0]['table'], 'Machine Pistol')
        self.assertEqual(standard_result['autofire_profiles'][0]['multiplier'], 3)
        self.assertTrue(standard_result['autofire_profiles'][0]['suppressive_fire'])
        modification['host_instance_id'] = excellent['instance_id']
        excellent_result = server.evaluate_effective_weapon(
            excellent, [modification], {autosear['instance_id']: autosear},
            {'inventory': [excellent, autosear], 'cyberware': []})
        self.assertEqual(excellent_result['autofire_profiles'][0]['multiplier'], 4)

        smg = self.owned('guns-3', 'e' * 32)
        cyclic = self.owned('gun_upgrades-22', '1' * 31 + '0')
        cyclic['state'] = 'installed'
        cyclic_rules = server.weapon_modification_rules_for_catalog('gun_upgrades-22')
        cyclic_mod = {
            'modification_id': '2' * 32, 'host_instance_id': smg['instance_id'],
            'upgrade_instance_id': cyclic['instance_id'], 'slots_used': 0, 'active': True,
            'configuration': {'effect_rules': cyclic_rules,
                              'choices': {'autofire_mode': 'machine_pistol4'}},
        }
        configured = server.evaluate_effective_weapon(
            smg, [cyclic_mod], {cyclic['instance_id']: cyclic},
            {'inventory': [smg, cyclic], 'cyberware': []})
        self.assertEqual(configured['autofire_profiles'][0]['table'], 'Machine Pistol')
        self.assertEqual(configured['autofire_profiles'][0]['multiplier'], 4)
        schema = server.weapon_modification_configuration_schema('gun_upgrades-22')[0]
        self.assertEqual(schema['key'], 'autofire_mode')
        self.assertEqual({choice['value'] for choice in schema['choices']},
                         {'smg4', 'machine_pistol4'})

    def test_rebuilds_grant_tags_requirements_and_manual_combat_rules(self):
        host = self.owned('guns-6', '3' * 32)
        power = self.owned('gun_upgrades-0', '4' * 32)
        smart = self.owned('gun_upgrades-1', '5' * 32)
        tech = self.owned('gun_upgrades-2', '6' * 32)
        for item in (power, smart, tech):
            item['state'] = 'installed'
        owned = {item['instance_id']: item for item in (host, power, smart, tech)}

        def modification(upgrade, marker):
            return {
                'modification_id': marker * 32,
                'host_instance_id': host['instance_id'],
                'upgrade_instance_id': upgrade['instance_id'],
                'slots_used': 2, 'active': True,
                'configuration': {
                    'effect_rules': server.weapon_modification_rules_for_catalog(
                        upgrade['catalog_item_id'])},
            }

        power_result = server.evaluate_effective_weapon(
            host, [modification(power, '7')], owned,
            {'inventory': [host, power], 'cyberware': []})
        self.assertIn('Power Weapon', power_result['tags'])
        power_source = next(source for source in power_result['sources']
                            if source['id'] == 'power-rebuild-effective')
        self.assertEqual(len(power_source['manual_rules']), 2)
        self.assertTrue(all(rule['manual_resolution_required']
                            for rule in power_source['manual_rules']))

        smart_mod = modification(smart, '8')
        smart_missing = server.evaluate_effective_weapon(
            host, [smart_mod], owned, {'inventory': [host, smart], 'cyberware': []})
        self.assertIn('Smart Weapon', smart_missing['tags'])
        self.assertEqual(smart_missing['attack_modifier'], 0)
        connected_character = {
            'inventory': [host, smart],
            'cyberware': [{
                'instance_id': '9' * 32, 'key': 'cyberware-61',
                'catalog_item_id': 'cyberware-61', 'name': 'Interface Plugs',
                'state': 'installed',
            }],
        }
        smart_connected = server.evaluate_effective_weapon(
            host, [smart_mod], owned, connected_character)
        self.assertEqual(smart_connected['attack_modifier'], 1)

        tech_result = server.evaluate_effective_weapon(
            host, [modification(tech, 'a')], owned,
            {'inventory': [host, tech], 'cyberware': []})
        self.assertIn('Tech Weapon', tech_result['tags'])
        tech_source = next(source for source in tech_result['sources']
                           if source['id'] == 'tech-rebuild-effective')
        self.assertEqual(len(tech_source['manual_rules']), 2)
        self.assertEqual(host['mechanics']['rof'], 1)

        conflict = server.weapon_upgrade_compatibility(
            host, smart, [modification(power, 'b')], owned)
        self.assertFalse(conflict['allowed'])
        self.assertTrue(any('Conflicts' in reason for reason in conflict['reasons']))

    def test_range_table_modification_uses_host_specific_configuration(self):
        pistol = self.owned('guns-0', 'c' * 32)
        upgrade = self.owned('gun_upgrades-19', 'd' * 32)
        upgrade['state'] = 'installed'
        pistol_info = server.weapon_range_table_info(pistol)
        self.assertEqual(pistol_info['base'], 'Pistol')
        self.assertEqual(pistol_info['choices'], ['Snubnose Pistol', 'Long Barrel Pistol'])
        schema = server.weapon_modification_configuration_schema('gun_upgrades-19', pistol)[0]
        self.assertEqual(schema['base_value'], 'Pistol')
        self.assertEqual([choice['value'] for choice in schema['choices']],
                         ['Snubnose Pistol', 'Long Barrel Pistol'])
        clean = server.clean_weapon_modification_choices(
            'gun_upgrades-19', {'range_table': 'Long Barrel Pistol'}, pistol)
        self.assertEqual(clean, {'range_table': 'Long Barrel Pistol'})
        with self.assertRaises(server.ApiError):
            server.clean_weapon_modification_choices(
                'gun_upgrades-19', {'range_table': 'Sniper Rifle'}, pistol)
        modification = {
            'modification_id': 'e' * 32, 'host_instance_id': pistol['instance_id'],
            'upgrade_instance_id': upgrade['instance_id'], 'slots_used': 0, 'active': True,
            'configuration': {
                'choices': clean,
                'effect_rules': server.weapon_modification_rules_for_catalog('gun_upgrades-19'),
            },
        }
        result = server.evaluate_effective_weapon(
            pistol, [modification], {upgrade['instance_id']: upgrade},
            {'inventory': [pistol, upgrade], 'cyberware': []})
        self.assertEqual(result['base']['range_table'], 'Pistol')
        self.assertEqual(result['effective']['range_table'], 'Long Barrel Pistol')
        self.assertEqual(result['base']['damage'], result['effective']['damage'])
        self.assertEqual(result['base']['magazine'], result['effective']['magazine'])

    def test_bayonet_concealability_has_manual_alternate_attack_rule(self):
        host = self.owned('guns-5', '5' * 32)  # Shotgun / Shoulder Arms
        bayonet = self.owned('gun_upgrades-3', '6' * 32)
        bayonet['state'] = 'installed'
        modification = {
            'modification_id': 'c' * 32, 'host_instance_id': host['instance_id'],
            'upgrade_instance_id': bayonet['instance_id'], 'slots_used': 1, 'active': True,
            'configuration': {'effect_rules': server.weapon_modification_rules_for_catalog('gun_upgrades-3')},
        }
        result = server.evaluate_effective_weapon(
            host, [modification], {host['instance_id']: host, bayonet['instance_id']: bayonet},
            {'inventory': [host, bayonet], 'cyberware': []})
        self.assertEqual(result['effective']['concealable'], 'NO')
        self.assertTrue(result['sources'][0]['manual_rules'][0]['manual_resolution_required'])
        self.assertEqual(result['sources'][0]['manual_rules'][0]['source'], 'CP:R 343')


class VehicleModificationTests(unittest.TestCase):
    def owned(self, catalog_id, instance_id, source='loot'):
        item = copy.deepcopy(server.item_by_id(catalog_id))
        item.update({'key': catalog_id, 'catalog_item_id': catalog_id,
                     'instance_id': instance_id, 'qty': 1, 'state': 'carried',
                     'acquisition_source': source})
        return item

    def test_shared_ammo_compatibility_is_profile_specific(self):
        basic = self.owned('ammo-0', 'a' * 32)
        incendiary = self.owned('ammo-6', 'b' * 32)
        smart = self.owned('ammo-10', 'c' * 32)
        for ammo in (basic, incendiary, smart):
            ammo['ammo_rounds'] = 10
        self.assertFalse(server.ammo_matches_requirement(
            basic, 'incendiary_shotgun'))
        self.assertTrue(server.ammo_matches_requirement(
            incendiary, 'incendiary_shotgun'))
        self.assertFalse(server.ammo_matches_requirement(basic, 'grenade'))
        self.assertFalse(server.ammo_matches_requirement(basic, 'rocket'))
        self.assertTrue(server.ammo_matches_requirement(smart, 'rocket'))
        rifle = self.owned('guns-6', 'd' * 32)
        self.assertTrue(server.ammo_matches_requirement(basic, weapon=rifle))
        self.assertTrue(server.ammo_matches_requirement(incendiary, weapon=rifle))

    def test_vehicle_repair_guidance_uses_damage_severity_and_vehicle_skill(self):
        self.assertEqual(server.vehicle_repair_severity(50, 50), 'minor')
        self.assertEqual(server.vehicle_repair_severity(25, 50), 'minor')
        self.assertEqual(server.vehicle_repair_severity(24, 50), 'major')
        self.assertEqual(server.vehicle_repair_severity(0, 50), 'destroyed')
        self.assertEqual(server.VEHICLE_REPAIR_RULES['minor']['dv'], 9)
        self.assertEqual(server.VEHICLE_REPAIR_RULES['major']['duration_key'], '1_day')
        self.assertEqual(server.VEHICLE_REPAIR_RULES['destroyed']['duration_key'], '1_week')
        self.assertEqual(server.vehicle_repair_skill(
            self.owned('vehicles-61', '0' * 32)), 'Basic Tech')
        self.assertEqual(server.vehicle_repair_skill(
            self.owned('vehicles-7', '1' * 32)), 'Sea Vehicle Tech')
        self.assertEqual(server.vehicle_repair_skill(
            self.owned('vehicles-13', '2' * 32)), 'Air Vehicle Tech')
        self.assertEqual(server.vehicle_repair_skill(
            self.owned('vehicles-2', '3' * 32)), 'Land Vehicle Tech')

    def test_effective_vehicle_separates_sdp_body_sp_glass_and_seats(self):
        vehicle = self.owned('vehicles-2', 'c' * 32)
        upgrades = [
            self.owned('vehicles_upgrades-9', 'd' * 32),
            self.owned('vehicles_upgrades-0', 'e' * 32),
            self.owned('vehicles_upgrades-1', 'f' * 32),
            self.owned('vehicles_upgrades-1', '1' * 31 + '0'),
            self.owned('vehicles_upgrades-6', '2' * 31 + '0'),
            self.owned('vehicles_upgrades-6', '3' * 31 + '0'),
        ]
        for item in upgrades:
            item['state'] = 'installed'
        owned = {item['instance_id']: item for item in [vehicle, *upgrades]}
        modifications = [{
            'modification_id': f'{index + 1:032x}',
            'host_instance_id': vehicle['instance_id'],
            'upgrade_instance_id': upgrade['instance_id'],
            'host_type': 'vehicle', 'active': True, 'slots_used': 0,
            'configuration': {
                'effect_rules': server.vehicle_modification_rules_for_catalog(
                    upgrade['catalog_item_id'])},
        } for index, upgrade in enumerate(upgrades)]
        result = server.evaluate_effective_vehicle(vehicle, modifications, owned)
        self.assertEqual(result['base']['sdp'], 50)
        self.assertEqual(result['effective']['sdp'], 70)
        self.assertEqual(result['base']['body_sp'], 0)
        self.assertEqual(result['effective']['body_sp'], 13)
        self.assertEqual(result['base']['glass_hp'], 0)
        self.assertEqual(result['effective']['glass_hp'], 30)
        self.assertEqual(result['base']['seats'], 4)
        self.assertEqual(result['effective']['seats'], 8)
        self.assertEqual(vehicle['mechanics']['sdp'], 50)
        glass_sources = [source for source in result['sources']
                         if source['id'] == 'bulletproof-glass-effective']
        self.assertEqual(len(glass_sources), 2)
        self.assertTrue(glass_sources[0]['manual_rules'][0]['manual_resolution_required'])

    def test_vehicle_nos_and_mounted_weapon_profiles_are_allowlisted_resources(self):
        vehicle = self.owned('vehicles-2', '4' * 32)
        nos = self.owned('vehicles_upgrades-3', '5' * 32)
        flamethrower = self.owned('vehicles_upgrades-4', '6' * 32)
        machinegun = self.owned('vehicles_upgrades-5', '7' * 32)
        rocket_pod = self.owned('vehicles_upgrades-10', '8' * 32)
        upgrades = (nos, flamethrower, machinegun, rocket_pod)
        for upgrade in upgrades:
            upgrade['state'] = 'installed'
        owned = {item['instance_id']: item for item in (vehicle, *upgrades)}
        modifications = []
        for index, upgrade in enumerate(upgrades):
            choices = {'orientation': 'side'} if upgrade is flamethrower else {}
            modifications.append({
                'modification_id': f'{index + 20:032x}',
                'host_instance_id': vehicle['instance_id'],
                'upgrade_instance_id': upgrade['instance_id'],
                'host_type': 'vehicle', 'active': True, 'slots_used': 0,
                'configuration': {
                    'choices': choices,
                    'effect_rules': server.vehicle_modification_rules_for_catalog(
                        upgrade['catalog_item_id']),
                },
            })
        vehicle['_modification_state'] = {
            modifications[0]['modification_id']: {
                'resource_type': 'nos_tank', 'profile_id': 'nos_tank',
                'uses_remaining': 0, 'uses_max': 1,
            },
            modifications[2]['modification_id']: {
                'resource_type': 'mounted_weapon',
                'profile_id': 'onboard_machinegun', 'magazine': 20,
                'magazine_max': 30, 'reserve': 10, 'ammo_cost': 10,
                'orientation': 'front',
            },
        }
        result = server.evaluate_effective_vehicle(vehicle, modifications, owned)
        self.assertEqual(len(result['nos_tanks']), 1)
        self.assertEqual(result['nos_tanks'][0]['state']['uses_remaining'], 0)
        self.assertEqual(len(result['mounted_weapons']), 3)
        by_id = {profile['id']: profile for profile in result['mounted_weapons']}
        self.assertEqual(by_id['onboard_flamethrower']['orientation'], 'side')
        self.assertEqual(by_id['onboard_flamethrower']['damage'], '3d6')
        self.assertEqual(by_id['onboard_machinegun']['kind'], 'autofire')
        self.assertEqual(by_id['onboard_machinegun']['state']['ammo_cost'], 10)
        self.assertEqual(by_id['onboard_rocket_pod']['magazine'], 3)
        self.assertTrue(all(source['automated'] for source in result['sources']))
        self.assertTrue(any(source['manual_rules'] for source in result['sources']))

        schemas = server.vehicle_modification_configuration_schema(
            flamethrower['catalog_item_id'])
        self.assertEqual(schemas[0]['key'], 'orientation')
        self.assertEqual(server.clean_vehicle_modification_choices(
            flamethrower['catalog_item_id'], {'orientation': 'rear'}),
            {'orientation': 'rear'})
        with self.assertRaises(server.ApiError):
            server.clean_vehicle_modification_choices(
                flamethrower['catalog_item_id'], {'orientation': 'top'})
        self.assertEqual(server.clean_vehicle_modification_choices(
            machinegun['catalog_item_id'], {}), {})
        authoritative = server.initial_vehicle_modification_state(
            server.vehicle_modification_rules_for_catalog(machinegun['catalog_item_id']),
            {'inventory': []}, {'orientation': 'front'})
        normalized = server.normalize_vehicle_modification_state({
            'resource_type': 'mounted_weapon', 'profile_id': 'tampered',
            'magazine': 999, 'magazine_max': 999, 'reserve': -5,
            'ammo_cost': 1, 'orientation': 'rear',
        }, authoritative)
        self.assertEqual(normalized['profile_id'], 'onboard_machinegun')
        self.assertEqual(normalized['magazine'], 30)
        self.assertEqual(normalized['reserve'], 0)
        self.assertEqual(normalized['ammo_cost'], 10)
        self.assertEqual(normalized['orientation'], 'front')

    def test_vehicle_heavy_mount_rooms_and_cargo_are_effective(self):
        vehicle = self.owned('vehicles-7', 'b' * 32)
        housing = self.owned('vehicles_upgrades-18', 'c' * 32)
        luxury = self.owned('vehicles_upgrades-25', 'd' * 32)
        complex_room = self.owned('vehicles_upgrades-26', 'e' * 32)
        smuggling = self.owned('vehicles_upgrades-8', 'f' * 32)
        mount = self.owned('vehicles_upgrades-11', '1' * 31 + '0')
        weapon = self.owned('guns-6', '2' * 31 + '0')
        upgrades = (housing, luxury, complex_room, smuggling, mount)
        for upgrade in upgrades:
            upgrade['state'] = 'installed'
        weapon.update({
            'state': 'installed', 'mounted_modification_id': '5' * 32,
            'mounted_vehicle_id': vehicle['instance_id'],
        })
        owned = {item['instance_id']: item for item in (vehicle, *upgrades, weapon)}
        modifications = []
        for index, upgrade in enumerate(upgrades, start=1):
            modification_id = '5' * 32 if upgrade is mount else f'{index:032x}'
            modifications.append({
                'modification_id': modification_id,
                'host_instance_id': vehicle['instance_id'],
                'upgrade_instance_id': upgrade['instance_id'],
                'host_type': 'vehicle', 'active': True, 'slots_used': 0,
                'configuration': {
                    'choices': {'purpose': 'cargo_bay'}
                        if upgrade is complex_room else {},
                    'effect_rules': server.vehicle_modification_rules_for_catalog(
                        upgrade['catalog_item_id']),
                },
            })
        vehicle['_modification_state'] = {
            '5' * 32: {
                'resource_type': 'heavy_weapon_mount',
                'profile_id': 'heavy_weapon_mount',
                'weapon_instance_id': weapon['instance_id'],
            },
        }
        character = {
            'inventory': list(owned.values()), 'cyberware': [],
            'weapon_state': {weapon['instance_id']: {
                'magazine': 12, 'magazine_max': 25, 'reserve': 20,
            }},
        }
        result = server.evaluate_effective_vehicle(
            vehicle, modifications, owned, character, modifications)
        self.assertEqual(result['base']['seats'], '2 per Room')
        self.assertEqual(result['effective']['seats'], 9)
        self.assertEqual(result['interior']['rooms_total'], 3)
        self.assertEqual(result['interior']['normal_rooms'], 1)
        self.assertEqual(result['interior']['luxury_rooms'], 1)
        self.assertEqual(result['interior']['complex_rooms'], 1)
        self.assertEqual(result['interior']['cargo_bays'], 1)
        self.assertEqual(result['interior']['hidden_cargo_spaces'], 1)
        self.assertEqual(result['cargo_modules'][0]['kind'], 'cargo_bay')
        self.assertEqual(result['cargo_modules'][1]['discovery_dv'], 17)
        self.assertEqual(len(result['weapon_mounts']), 1)
        bound = result['weapon_mounts'][0]['bound_weapon']
        self.assertEqual(bound['weapon_instance_id'], weapon['instance_id'])
        self.assertEqual(bound['skill'], 'Shoulder Arms')
        self.assertEqual(bound['damage'], '5d6')
        self.assertEqual(bound['state']['magazine'], 12)
        helix = self.owned('guns-133', '6' * 32)
        helix_character = {
            'inventory': [helix], 'cyberware': [],
            'weapon_state': {helix['instance_id']: {
                'magazine': 40, 'magazine_max': 40, 'reserve': 0,
            }},
        }
        helix_effective = server.evaluate_effective_weapon(
            helix, [], {helix['instance_id']: helix}, helix_character)
        helix_profile = server.bound_vehicle_weapon_profile(
            helix, helix_effective, helix_character)
        self.assertEqual(helix_profile['kind'], 'autofire')
        self.assertEqual(helix_profile['ammo_cost'], 20)
        self.assertEqual(helix_profile['autofire_multiplier'], 5)
        self.assertEqual(helix_profile['reload_actions'], 2)

        schema = server.vehicle_modification_configuration_schema(
            complex_room['catalog_item_id'])
        self.assertEqual(schema[0]['key'], 'purpose')
        self.assertEqual(server.clean_vehicle_modification_choices(
            complex_room['catalog_item_id'], {'purpose': 'bunkhouse'}),
            {'purpose': 'bunkhouse'})
        with self.assertRaises(server.ApiError):
            server.clean_vehicle_modification_choices(
                complex_room['catalog_item_id'], {'purpose': 'javascript'})

    def test_vehicle_availability_prerequisites_conflicts_and_role_access(self):
        car = self.owned('vehicles-2', '1' * 32)
        bike = self.owned('vehicles-0', '2' * 32)
        heavy = self.owned('vehicles_upgrades-9', '3' * 32)
        housing = self.owned('vehicles_upgrades-18', '4' * 32)
        owned = {item['instance_id']: item for item in (car, bike, heavy, housing)}
        physical = server.vehicle_upgrade_compatibility(
            car, heavy, [], owned, {'roles': [{'name': 'Solo', 'rank': 4}]})
        self.assertTrue(physical['allowed'])
        self.assertFalse(physical['role_access_item'])
        self.assertFalse(server.vehicle_upgrade_compatibility(
            bike, heavy, [], owned, {})['allowed'])
        missing = server.vehicle_upgrade_compatibility(car, housing, [], owned, {})
        self.assertFalse(missing['allowed'])
        self.assertTrue(any('Heavy Chassis' in reason for reason in missing['reasons']))
        heavy['state'] = 'installed'
        heavy_mod = {'modification_id': 'a' * 32, 'host_instance_id': car['instance_id'],
                     'upgrade_instance_id': heavy['instance_id'], 'active': True,
                     'slots_used': 0, 'configuration': {}}
        self.assertTrue(server.vehicle_upgrade_compatibility(
            car, housing, [heavy_mod], owned, {})['allowed'])

        access_heavy = self.owned('vehicles_upgrades-9', '5' * 32, 'role_access')
        access_owned = {**owned, access_heavy['instance_id']: access_heavy}
        denied = server.vehicle_upgrade_compatibility(
            car, access_heavy, [], access_owned,
            {'roles': [{'name': 'Nomad', 'rank': 0}]})
        allowed = server.vehicle_upgrade_compatibility(
            car, access_heavy, [], access_owned,
            {'roles': [{'name': 'Nomad', 'rank': 1}]})
        self.assertFalse(denied['allowed'])
        self.assertTrue(allowed['allowed'])
        self.assertTrue(allowed['nomad_access_met'])

        aerozep = self.owned('vehicles-13', '6' * 32)
        aerozep_upgrade = self.owned('vehicles_upgrades-19', '7' * 32)
        self.assertTrue(server.vehicle_upgrade_compatibility(
            aerozep, aerozep_upgrade, [], {}, {})['allowed'])
        self.assertFalse(server.vehicle_upgrade_compatibility(
            car, aerozep_upgrade, [], {}, {})['allowed'])

        bicycle = self.owned('vehicles-61', '8' * 32)
        enclosure = self.owned('vehicles_upgrades-31', '9' * 32)
        folding = self.owned('vehicles_upgrades-33', 'a' * 32)
        enclosure['state'] = 'installed'
        bicycle_owned = {item['instance_id']: item for item in (bicycle, enclosure, folding)}
        enclosure_mod = {'modification_id': 'b' * 32,
                         'host_instance_id': bicycle['instance_id'],
                         'upgrade_instance_id': enclosure['instance_id'],
                         'active': True, 'configuration': {}}
        conflict = server.vehicle_upgrade_compatibility(
            bicycle, folding, [enclosure_mod], bicycle_owned, {})
        self.assertFalse(conflict['allowed'])
        self.assertTrue(any('Enclosure' in reason for reason in conflict['reasons']))

        mount = self.owned('vehicles_upgrades-11', 'c' * 32)
        luxury = self.owned('vehicles_upgrades-25', 'd' * 32)
        expanded_owned = {**owned, mount['instance_id']: mount,
                          luxury['instance_id']: luxury}
        first_mount = server.vehicle_upgrade_compatibility(
            car, mount, [heavy_mod], expanded_owned, {})
        self.assertTrue(first_mount['allowed'])
        mount['state'] = 'installed'
        mount_mod = {
            'modification_id': 'e' * 32,
            'host_instance_id': car['instance_id'],
            'upgrade_instance_id': mount['instance_id'],
            'host_type': 'vehicle', 'active': True, 'configuration': {},
        }
        second_mount = self.owned('vehicles_upgrades-11', 'f' * 32)
        expanded_owned[second_mount['instance_id']] = second_mount
        blocked_second = server.vehicle_upgrade_compatibility(
            car, second_mount, [heavy_mod, mount_mod], expanded_owned, {})
        self.assertFalse(blocked_second['allowed'])
        self.assertTrue(any('Housing Groundcar' in reason
                            for reason in blocked_second['reasons']))
        housing['state'] = 'installed'
        housing_mod = {
            'modification_id': '1' * 30 + '22',
            'host_instance_id': car['instance_id'],
            'upgrade_instance_id': housing['instance_id'],
            'host_type': 'vehicle', 'active': True, 'configuration': {},
        }
        self.assertTrue(server.vehicle_upgrade_compatibility(
            car, second_mount, [heavy_mod, mount_mod, housing_mod],
            expanded_owned, {})['allowed'])
        self.assertTrue(server.vehicle_upgrade_compatibility(
            car, luxury, [heavy_mod, housing_mod], expanded_owned, {})['allowed'])
        luxury['state'] = 'installed'
        luxury_mod = {
            'modification_id': '2' * 32,
            'host_instance_id': car['instance_id'],
            'upgrade_instance_id': luxury['instance_id'],
            'host_type': 'vehicle', 'active': True, 'configuration': {},
        }
        another_luxury = self.owned('vehicles_upgrades-25', '3' * 32)
        expanded_owned[another_luxury['instance_id']] = another_luxury
        room_full = server.vehicle_upgrade_compatibility(
            car, another_luxury, [heavy_mod, housing_mod, luxury_mod],
            expanded_owned, {})
        self.assertFalse(room_full['allowed'])
        self.assertTrue(any('rooms already' in reason for reason in room_full['reasons']))


class CyberdeckModificationTests(unittest.TestCase):
    def owned(self, catalog_id, instance_id):
        item = copy.deepcopy(server.item_by_id(catalog_id))
        item.update({'key': catalog_id, 'catalog_item_id': catalog_id,
                     'instance_id': instance_id, 'qty': 1, 'state': 'carried'})
        return item

    def modification(self, host, item, index):
        return {
            'modification_id': f'{index:032x}', 'active': True,
            'host_instance_id': host['instance_id'],
            'upgrade_instance_id': item['instance_id'],
            'host_type': 'cyberdeck', 'slots_used': item.get('slots_used') or 1,
            'configuration': {},
        }

    def test_net_action_helpers_use_interface_and_path_direction(self):
        self.assertEqual([server.net_actions_for_interface(rank)
                          for rank in (1, 3, 4, 6, 7, 9, 10)],
                         [2, 2, 3, 3, 4, 4, 5])
        self.assertEqual(server.character_interface_rank({
            'roles': [{'name': 'Netrunner', 'rank': 4},
                      {'name': 'Solo', 'rank': 5}]}), 4)
        state = {'paths': [
            {'path_id': 'a' * 32, 'from_node_id': 'b' * 32,
             'to_node_id': 'c' * 32, 'direction': 'one_way', 'visible': True},
            {'path_id': 'd' * 32, 'from_node_id': 'c' * 32,
             'to_node_id': 'e' * 32, 'direction': 'bidirectional', 'visible': False},
        ]}
        self.assertIsNotNone(server.session_net_path_between(
            state, 'b' * 32, 'c' * 32))
        self.assertIsNone(server.session_net_path_between(
            state, 'c' * 32, 'b' * 32))
        self.assertIsNone(server.session_net_path_between(
            state, 'c' * 32, 'e' * 32))
        self.assertIsNotNone(server.session_net_path_between(
            state, 'e' * 32, 'c' * 32, require_visible=False))

    def test_session_net_architecture_state_sanitizes_nodes_paths_and_links(self):
        floor_id, access_id, password_id, path_id = (
            'a' * 32, 'b' * 32, 'c' * 32, 'd' * 32)
        state = server.session_net_state({
            'round': 2, 'active_turn': 1,
            'floors': [{'floor_id': floor_id, 'label': 'Lobby'}],
            'nodes': [
                {'node_id': access_id, 'floor_id': floor_id,
                 'type': 'access_point', 'label': 'Access', 'visible': True},
                {'node_id': password_id, 'floor_id': floor_id,
                 'type': 'password', 'label': 'Password', 'dv': 99,
                 'defense': -5, 'gm_note': 'secret'},
                {'node_id': 'e' * 32, 'floor_id': floor_id,
                 'type': 'javascript', 'label': 'Unsafe'},
            ],
            'paths': [
                {'path_id': path_id, 'from_node_id': access_id,
                 'to_node_id': password_id, 'direction': 'one_way',
                 'visible': True},
                {'path_id': 'f' * 32, 'from_node_id': access_id,
                 'to_node_id': access_id, 'direction': 'bidirectional'},
            ],
            'links': [],
        })
        self.assertEqual(len(state['nodes']), 2)
        self.assertEqual(state['nodes'][1]['dv'], 29)
        self.assertEqual(state['nodes'][1]['defense'], 0)
        self.assertFalse(state['nodes'][1]['visible'])
        self.assertEqual(len(state['paths']), 1)
        self.assertEqual(state['paths'][0]['direction'], 'one_way')

    def test_black_ice_effect_profiles_automate_only_unambiguous_rez_damage(self):
        killer = self.owned('programs-25', 'e' * 32)
        hellhound = self.owned('programs-17', 'f' * 32)
        asp = self.owned('programs-15', '1' * 31 + '0')
        raven = self.owned('programs-20', '2' * 31 + '0')
        liche = self.owned('programs-19', '7' * 32)
        scorpion = self.owned('programs-21', '8' * 32)
        killer_effect = server.black_ice_effect_profile(killer)
        hellhound_effect = server.black_ice_effect_profile(hellhound)
        self.assertEqual((killer_effect['resolution'], killer_effect['damage_dice']),
                         ('automated_rez_damage', 4))
        self.assertTrue(killer_effect['destroy_on_derez'])
        self.assertEqual(hellhound_effect['resolution'], 'manual_effect')
        self.assertIn('2d6 damage', hellhound_effect['manual_effect'])
        self.assertEqual(server.black_ice_effect_profile(asp)['resolution'],
                         'automated_random_destroy')
        self.assertEqual(server.black_ice_effect_profile(raven)['resolution'],
                         'automated_random_derez_plus_manual')
        for program in (liche, scorpion):
            profile = server.black_ice_effect_profile(program)
            self.assertEqual(profile['resolution'], 'automated_stat_penalty')
            self.assertEqual(profile['manual_effect'], '')
        rolled = server.roll_dice(4, 6)
        self.assertEqual(len(rolled['rolls']), 4)
        self.assertEqual(rolled['total'], sum(rolled['rolls']))
        self.assertTrue(all(1 <= value <= 6 for value in rolled['rolls']))

    def test_defense_sequencer_queues_manual_eligibility_trigger(self):
        deck = self.owned('net_stuff-1', '3' * 32)
        sequencer = self.owned('net_stuff-23', '4' * 32)
        armor_trigger = self.owned('programs-12', '5' * 32)
        armor_ready = self.owned('programs-12', '6' * 32)
        non_armor = self.owned('programs-0', '7' * 32)
        for item in (sequencer, armor_trigger, armor_ready, non_armor):
            item['state'] = 'installed'
        modifications = [
            self.modification(deck, sequencer, 1),
            self.modification(deck, armor_trigger, 2),
            self.modification(deck, armor_ready, 3),
        ]
        data = {
            'inventory': [deck, sequencer, armor_trigger, armor_ready, non_armor],
            'program_state': {
                armor_trigger['instance_id']: {'status': 'derezzed'},
                armor_ready['instance_id']: {'status': 'inactive'},
            },
        }
        self.assertEqual(server.queue_defense_sequencer_trigger(
            data, modifications, deck['instance_id'], non_armor['instance_id']), 0)
        self.assertNotIn('modification_state', data)
        count = server.queue_defense_sequencer_trigger(
            data, modifications, deck['instance_id'], armor_trigger['instance_id'])
        self.assertEqual(count, 1)
        pending = data['modification_state'][modifications[0]['modification_id']]
        self.assertTrue(pending['pending_armor_rez'])
        self.assertTrue(pending['manual_eligibility_required'])
        self.assertEqual(pending['eligible_armor_instance_ids'],
                         [armor_ready['instance_id']])
        resolved = server.resolve_defense_sequencer_trigger(
            data, modifications, deck['instance_id'], sequencer['instance_id'],
            armor_ready['instance_id'], now=100)
        self.assertTrue(resolved['manual_eligibility_confirmed'])
        self.assertEqual((resolved['rez_current'], resolved['rez_max']), (7, 7))
        ready_runtime = data['program_state'][armor_ready['instance_id']]
        self.assertEqual(ready_runtime['status'], 'rezzed')
        sequencer_state = data['modification_state'][modifications[0]['modification_id']]
        self.assertFalse(sequencer_state['pending_armor_rez'])
        self.assertEqual(sequencer_state['resolved_at'], 100)
        with self.assertRaisesRegex(server.ApiError, 'pending Armor trigger'):
            server.resolve_defense_sequencer_trigger(
                data, modifications, deck['instance_id'], sequencer['instance_id'],
                armor_ready['instance_id'])

    def test_black_ice_stat_penalty_floor_applies_after_stacked_modifiers(self):
        modifiers = [
            {'id': 'liche-a', 'target': 'character.stat.INT', 'operation': 'add',
             'value': -4, 'minimum_value': 1, 'stack_group': 'liche-a',
             'stack_policy': 'stack', 'priority': 400},
            {'id': 'liche-b', 'target': 'character.stat.INT', 'operation': 'add',
             'value': -5, 'minimum_value': 1, 'stack_group': 'liche-b',
             'stack_policy': 'stack', 'priority': 400},
        ]
        value, breakdown = server.apply_modifier_pipeline(6, modifiers)
        self.assertEqual(value, 1)
        self.assertEqual(len([item for item in breakdown if item['applied']]), 2)
        server.validate_effect_definition(modifiers[0])
        with self.assertRaisesRegex(RuntimeError, 'minimum_value'):
            server.validate_effect_definition({**modifiers[0], 'minimum_value': '1'})

    def test_black_ice_entity_snapshots_stats_mode_and_target_type(self):
        killer = self.owned('programs-25', 'f' * 32)
        waiting = server.initial_black_ice_entity(
            killer, 'd' * 32, 1, 'lie_in_wait', 'Floor 3')
        self.assertEqual(waiting['status'], 'lying_in_wait')
        self.assertEqual(waiting['target_type'], 'enemy_program_source')
        self.assertIsNone(waiting['initiative'])
        self.assertEqual((waiting['per'], waiting['spd'], waiting['atk'],
                          waiting['def'], waiting['rez_max']),
                         (4, 8, 6, 2, 20))
        deployed = server.initial_black_ice_entity(
            killer, 'd' * 32, 1, 'deploy_combat', 'Floor 3', 'Armor.exe')
        self.assertEqual(deployed['status'], 'hunting')
        self.assertEqual(deployed['target_label'], 'Armor.exe')
        self.assertGreaterEqual(deployed['initiative'], 9)
        self.assertLessEqual(deployed['initiative'], 18)

    def test_program_runtime_state_uses_program_class_and_rez(self):
        armor = self.owned('programs-12', '0' * 32)
        banhammer = self.owned('programs-0', '1' * 32)
        killer = self.owned('programs-25', '2' * 32)
        armor_state = server.initial_program_runtime_state(
            armor, 'd' * 32, 'a' * 32)
        attacker_state = server.initial_program_runtime_state(
            banhammer, 'd' * 32, 'b' * 32)
        ice_state = server.initial_program_runtime_state(
            killer, 'd' * 32, 'c' * 32)
        self.assertEqual((armor_state['category'], armor_state['rez_max']),
                         ('defender', 7))
        self.assertEqual((attacker_state['category'], attacker_state['rez_max']),
                         ('attacker', 0))
        self.assertEqual((ice_state['category'], ice_state['rez_max']),
                         ('black_ice', 20))

    def test_cyberdeck_slots_count_hardware_programs_and_black_ice(self):
        self.assertEqual(server.item_by_id('net_stuff-19')['host_type'], 'cyberdeck')
        self.assertEqual(server.item_by_id('net_stuff-19')['slots_used'], 2)
        self.assertEqual(server.item_by_id('net_stuff-20')['slots_used'], 3)
        self.assertEqual(server.item_by_id('programs-25')['slots_used'], 2)
        deck = self.owned('net_stuff-1', '1' * 32)
        backup = self.owned('net_stuff-19', '2' * 32)
        armor = self.owned('programs-12', '3' * 32)
        killer = self.owned('programs-25', '4' * 32)
        bushido = self.owned('net_stuff-20', '5' * 32)
        installed = (backup, armor, killer)
        for item in installed:
            item['state'] = 'installed'
        owned = {item['instance_id']: item for item in
                 (deck, backup, armor, killer, bushido)}
        modifications = [self.modification(deck, item, index)
                         for index, item in enumerate(installed, start=1)]
        usage = server.cyberdeck_slot_usage(deck, modifications, owned)
        self.assertEqual(usage['pools']['mixed'], {'total': 7, 'used': 5})
        self.assertEqual(usage['hardware_units'], 2)
        self.assertEqual(usage['program_units'], 3)
        self.assertEqual(next(row for row in usage['program_weights']
                              if row['name'] == 'Killer')['slots'], 2)
        allowed = server.cyberdeck_item_compatibility(
            deck, bushido, modifications, owned)
        self.assertFalse(allowed['allowed'])
        self.assertTrue(any('slots' in reason for reason in allowed['reasons']))

    def test_cyberdeck_model_specific_restrictions_and_perfume_shoppe(self):
        assault = self.owned('net_stuff-6', '6' * 32)
        armor = self.owned('programs-12', '7' * 32)
        killer = self.owned('programs-25', '8' * 32)
        owned = {item['instance_id']: item for item in (assault, armor, killer)}
        self.assertFalse(server.cyberdeck_item_compatibility(
            assault, armor, [], owned)['allowed'])
        self.assertTrue(server.cyberdeck_item_compatibility(
            assault, killer, [], owned)['allowed'])

        kerberos = self.owned('net_stuff-12', '9' * 32)
        hellhound = self.owned('programs-17', 'a' * 32)
        self.assertTrue(server.cyberdeck_item_compatibility(
            kerberos, hellhound, [], {hellhound['instance_id']: hellhound})['allowed'])
        self.assertFalse(server.cyberdeck_item_compatibility(
            kerberos, killer, [], {killer['instance_id']: killer})['allowed'])

        phoenix = self.owned('net_stuff-11', 'b' * 32)
        perfume = self.owned('net_stuff-30', 'c' * 32)
        skunks = [self.owned('programs-22', f'{index + 13:032x}') for index in range(4)]
        for item in (perfume, *skunks):
            item['state'] = 'installed'
        loadout = (perfume, *skunks)
        perfume_owned = {item['instance_id']: item for item in (phoenix, *loadout)}
        modifications = [self.modification(phoenix, item, index)
                         for index, item in enumerate(loadout, start=1)]
        with_perfume = server.cyberdeck_slot_usage(phoenix, modifications, perfume_owned)
        without_perfume = server.cyberdeck_slot_usage(
            phoenix, modifications[1:], perfume_owned)
        self.assertEqual(with_perfume['slots_used'], 6)
        self.assertFalse(with_perfume['overloaded'])
        self.assertEqual(without_perfume['slots_used'], 8)
        self.assertTrue(without_perfume['overloaded'])


class CreationValidationTests(unittest.TestCase):
    def test_valid_complete_package(self):
        char = valid_character()
        self.assertEqual(server.creation_skill_cost(char), 86)
        server.validate_creation(char)

    def test_all_ten_role_setups_and_lifepaths_validate(self):
        for role in server.ROLES:
            with self.subTest(role=role):
                server.validate_creation(valid_merged_character(role))

    def test_merged_lifepath_does_not_require_removed_social_rolls(self):
        char = valid_merged_character()
        self.assertFalse({'friends', 'enemies', 'love'} & set(char['lifepath']))
        server.validate_creation(char)

    def test_parent_pool_rejects_child_overallocation(self):
        char = valid_merged_character()
        char['skills']['Language (Streetslang)'] = 3
        with self.assertRaisesRegex(server.ApiError, 'parent-pool'):
            server.validate_creation(char)

    def test_specialized_parent_pool_can_exceed_six(self):
        char = valid_merged_character()
        char['skill_pools']['Language'] = 7
        donor = next(name for name, level in char['skills'].items()
                     if level == 6 and server.skill_base(name) not in server.SPECIALIZED_SKILLS)
        char['skills'][donor] = 1
        self.assertEqual(server.creation_skill_cost(char), 86)
        server.validate_creation(char)

    def test_cultural_language_can_advance_above_free_four(self):
        char = valid_merged_character()
        char['skills']['Language (Русский)'] = 5
        char['skill_pools']['Language'] = 3
        donor = next(name for name, level in char['skills'].items()
                     if level == 6 and server.skill_base(name) not in server.SPECIALIZED_SKILLS)
        char['skills'][donor] = 5
        self.assertEqual(server.creation_skill_cost(char), 86)
        server.validate_creation(char)

    def test_parent_pool_may_keep_unallocated_levels(self):
        char = valid_merged_character()
        char['skill_pools']['Language'] = 3
        # Move one point from an already purchased ordinary Skill into the parent pool.
        donor = next(name for name, level in char['skills'].items()
                     if level == 6 and server.skill_base(name) not in server.SPECIALIZED_SKILLS)
        char['skills'][donor] = 5
        self.assertEqual(server.creation_skill_cost(char), 86)
        server.validate_creation(char)

    def test_cyberware_options_require_a_host_and_respect_slots(self):
        arm = {'key': 'cyberware-109', 'instance_id': 'arm-1', 'name': 'Cyberarm'}
        launcher = {'key': 'cyberware-117', 'instance_id': 'launcher-1',
                    'host_instance': 'arm-1', 'name': 'Popup Grenade Launcher'}
        server.validate_cyberware_slots({'cyberware': [arm, launcher]})
        broken = copy.deepcopy(launcher)
        broken['host_instance'] = ''
        with self.assertRaisesRegex(server.ApiError, 'host'):
            server.validate_cyberware_slots({'cyberware': [arm, broken]})
        with self.assertRaisesRegex(server.ApiError, 'Option Slots'):
            server.validate_cyberware_slots({'cyberware': [arm, launcher, copy.deepcopy(launcher),
                                                           copy.deepcopy(launcher)]})

    def test_only_one_neuroport_is_allowed(self):
        char = valid_merged_character()
        char['cyberware'].append({
            'key': 'cyberware-0', 'name': 'Neuroport', 'hl': 7,
            'price': 1000, 'type': 'Neuralware',
        })
        char['cash'] = 1550
        with self.assertRaisesRegex(server.ApiError, 'только один Neuroport'):
            server.validate_creation(char)

    def test_requires_exact_stat_budget(self):
        char = valid_character()
        char['stats']['BODY'] = 6
        with self.assertRaisesRegex(server.ApiError, 'ровно 62'):
            server.validate_creation(char)

    def test_native_language_does_not_replace_streetslang(self):
        char = valid_character()
        del char['skills']['Language (Streetslang)']
        char['skills']['Accounting'] = 2
        with self.assertRaisesRegex(server.ApiError, 'Streetslang'):
            server.validate_creation(char)

    def test_native_language_matches_cultural_origin(self):
        char = valid_character()
        char['lifepath']['region'] = 'Северная Америка'
        with self.assertRaisesRegex(server.ApiError, 'соответствовать происхождению'):
            server.validate_creation(char)

    def test_skill_above_six_is_rejected(self):
        char = valid_character()
        char['skills']['Accounting'] = 7
        with self.assertRaisesRegex(server.ApiError, '0–6'):
            server.validate_creation(char)

    def test_science_requires_a_specialization(self):
        char = valid_character()
        del char['skills']['Conceal/Reveal Object']
        char['skills']['Science'] = 6
        with self.assertRaisesRegex(server.ApiError, 'конкретную специализацию'):
            server.validate_creation(char)

    def test_role_benefits_are_free_but_role_locked(self):
        char = valid_merged_character('Exec')
        char['inventory'].append({'key': 'role-exec-businesswear', 'name': 'Businesswear (Teamwork)',
                                  'role_benefit': True, 'price': 0, 'qty': 1})
        server.validate_creation(char)
        char['role'] = 'Solo'
        char['role_setup'] = {}
        char['role_lifepath'] = {key: 'test' for key in ('kind', 'moral', 'enemy', 'territory')}
        with self.assertRaisesRegex(server.ApiError, 'преимущество роли'):
            server.validate_creation(char)

    def test_role_setup_is_checked(self):
        char = valid_character('Tech')
        char['role_setup']['field'] = 1
        with self.assertRaisesRegex(server.ApiError, '8 рангов Maker'):
            server.validate_creation(char)

    def test_cannot_finish_creation_below_zero_humanity(self):
        char = valid_character()
        for _ in range(9):
            char['cyberware'].append({
                'key': 'cyberware-0', 'name': 'Neuroport',
                'hl': 7, 'price': 1000, 'type': 'Neuralware',
            })
        with self.assertRaisesRegex(server.ApiError, 'Humanity ниже 0'):
            server.validate_creation(char)

    def test_armor_location_variant_uses_catalog_price(self):
        char = valid_character()
        char['inventory'].append({
            'key': 'armor-3@body', 'source_key': 'armor-3', 'name': 'Light Armorjack',
            'cat': 'armor', 'location': 'body', 'price': 1, 'qty': 1,
        })
        char['armor']['body'] = {
            'key': 'armor-3@body', 'source_key': 'armor-3',
            'name': 'Light Armorjack', 'sp': 11, 'penalties': {},
        }
        char['cash'] = 2450
        server.validate_creation(char)

    def test_selling_soul_bonus_can_only_cover_chrome(self):
        char = valid_character()
        char['creation'].update({'sold_soul': True, 'patron': 'Corporation',
                                 'obligation': 'Three deniable operations'})
        char['cyberware'].append({
            'key': 'cyberware-3', 'name': 'Borgware Hardened Shielding',
            'hl': 14, 'price': 1000, 'type': 'Borgware',
        })
        # The authoritative catalog price is covered by the 1,500eb chrome-only fund.
        char['cash'] = 2550
        server.validate_creation(char)

    def test_paired_cyberware_uses_two_different_hosts(self):
        left = {'key': 'cyberware-65', 'instance_id': 'eye-left', 'name': 'Cybereye'}
        right = {'key': 'cyberware-65', 'instance_id': 'eye-right', 'name': 'Cybereye'}
        anti = {'key': 'cyberware-66', 'instance_id': 'anti-dazzle', 'name': 'Anti-Dazzle',
                'host_instance': 'eye-left', 'host_instances': ['eye-left', 'eye-right']}
        server.validate_cyberware_slots({'cyberware': [left, right, anti]})
        anti['host_instances'] = ['eye-left']
        with self.assertRaisesRegex(server.ApiError, 'hosts: 2'):
            server.validate_cyberware_slots({'cyberware': [left, right, anti]})

    def test_effective_cyberware_hosts_bind_paired_options_to_concrete_instances(self):
        left = {'key': 'cyberware-65', 'catalog_item_id': 'cyberware-65',
                'instance_id': '1' * 32, 'name': 'Cybereye', 'state': 'installed'}
        right = {'key': 'cyberware-65', 'catalog_item_id': 'cyberware-65',
                 'instance_id': '2' * 32, 'name': 'Cybereye', 'state': 'installed'}
        anti = {'key': 'cyberware-66', 'catalog_item_id': 'cyberware-66',
                'instance_id': '3' * 32, 'name': 'Anti-Dazzle',
                'state': 'installed', 'host_instance': left['instance_id'],
                'host_instances': [left['instance_id'], right['instance_id']]}
        data = {'cyberware': [left, right, anti]}
        loadout = server.effective_cyberware_loadout(data)
        self.assertEqual(len(loadout['hosts']), 2)
        self.assertEqual([host['slots_used'] for host in loadout['hosts']], [1, 1])
        self.assertEqual(loadout['options'][0]['status'], 'installed')
        self.assertEqual(loadout['options'][0]['hosts_required'], 2)
        denied = server.cyberware_option_compatibility(
            data, anti['instance_id'], [left['instance_id'], left['instance_id']])
        self.assertFalse(denied['allowed'])
        self.assertIn('2 different concrete hosts', denied['reasons'][0])

    def test_paired_cyberleg_foundation_exposes_two_physical_slot_hosts(self):
        legs = {'key': 'cyberware-158', 'catalog_item_id': 'cyberware-158',
                'instance_id': 'a' * 32, 'name': 'Romanova Cyberlegs',
                'state': 'installed'}
        right_id = server.cyberware_secondary_host_id(legs['instance_id'])
        grip = {'key': 'cyberware-127', 'catalog_item_id': 'cyberware-127',
                'instance_id': 'b' * 32, 'name': 'Grip Foot', 'state': 'installed',
                'host_instance': legs['instance_id'],
                'host_instances': [legs['instance_id'], right_id]}
        data = {'cyberware': [legs, grip], 'inventory': [], 'stats': {}}
        server.validate_cyberware_requirements(data)
        server.validate_cyberware_slots(data)
        loadout = server.effective_cyberware_loadout(data)
        self.assertEqual(len(loadout['hosts']), 2)
        self.assertEqual([host['physical_side'] for host in loadout['hosts']],
                         ['left', 'right'])
        self.assertEqual([host['slots_total'] for host in loadout['hosts']], [3, 3])
        self.assertEqual([host['slots_used'] for host in loadout['hosts']], [1, 1])
        self.assertTrue(all(host['foundation_instance_id'] == legs['instance_id']
                            for host in loadout['hosts']))
        zero_gravity = copy.deepcopy(server.item_by_id('cyberware-201'))
        self.assertEqual(server.cyberware_capacity(zero_gravity)['slots_used'], 2)

    def test_item_instance_regeneration_remaps_cyberware_host_bindings(self):
        data = {'inventory': [], 'cyberware': [
            {'key': 'cyberware-65', 'instance_id': 'temporary-eye',
             'name': 'Cybereye'},
            {'key': 'cyberware-67', 'instance_id': 'temporary-chyron',
             'name': 'Chyron', 'host_instance': 'temporary-eye',
             'host_instances': ['temporary-eye']},
        ]}
        server.ensure_character_item_instances(data, regenerate=True)
        eye, chyron = data['cyberware']
        self.assertRegex(eye['instance_id'], r'^[a-f0-9]{32}$')
        self.assertRegex(chyron['instance_id'], r'^[a-f0-9]{32}$')
        self.assertEqual(chyron['host_instance'], eye['instance_id'])
        self.assertEqual(chyron['host_instances'], [eye['instance_id']])
        server.validate_cyberware_slots(data)

        old_legs_id = 'temporary-paired-legs'
        paired = {'inventory': [], 'cyberware': [
            {'key': 'cyberware-158', 'instance_id': old_legs_id,
             'name': 'Romanova Cyberlegs'},
            {'key': 'cyberware-127', 'instance_id': 'd' * 32,
             'name': 'Grip Foot', 'host_instance': old_legs_id,
             'host_instances': [old_legs_id,
                                server.cyberware_secondary_host_id(old_legs_id)]},
        ]}
        server.ensure_character_item_instances(paired, regenerate=True)
        legs, grip = paired['cyberware']
        self.assertEqual(grip['host_instances'], [
            legs['instance_id'], server.cyberware_secondary_host_id(legs['instance_id'])])
        server.validate_cyberware_slots(paired)

    def test_concrete_armor_hosts_apply_sp_upgrade_and_parse_shield_hp(self):
        armor = copy.deepcopy(server.item_by_id('armor-3'))
        armor.update({'key': 'armor-3', 'catalog_item_id': 'armor-3',
                      'instance_id': '6' * 32, 'state': 'equipped'})
        shield = copy.deepcopy(server.item_by_id('armor-24'))
        shield.update({'key': 'armor-24', 'catalog_item_id': 'armor-24',
                       'instance_id': '7' * 32, 'state': 'carried'})
        data = {
            'inventory': [armor, shield],
            'armor': {'body': {'instance_id': armor['instance_id'],
                               'name': armor['name'], 'sp': 11,
                               'maximum': 11, 'current': 7}},
            'armor_tech_state': {armor['instance_id']: {
                'active': True, 'mode': 'sp_plus_one', 'tech_name': 'Maker'}},
        }
        hosts = server.effective_armor_hosts(data)['hosts']
        armor_host = next(item for item in hosts if item['instance_id'] == armor['instance_id'])
        shield_host = next(item for item in hosts if item['instance_id'] == shield['instance_id'])
        self.assertEqual((armor_host['base_sp'], armor_host['effective_sp']), (11, 12))
        self.assertEqual(shield_host['base_sdp'], 15)
        self.assertTrue(shield_host['manual_resolution_required'])
        executive = copy.deepcopy(server.item_by_id('armor-19'))
        executive.update({'key': 'armor-19', 'catalog_item_id': 'armor-19',
                          'instance_id': 'a' * 32, 'state': 'equipped'})
        scavenged = copy.deepcopy(server.item_by_id('armor-26'))
        scavenged.update({'key': 'armor-26', 'catalog_item_id': 'armor-26',
                          'instance_id': 'b' * 32, 'state': 'carried'})
        extra = server.effective_armor_hosts({
            'inventory': [executive, scavenged],
            'armor': {'body': {'instance_id': executive['instance_id'],
                               'current': 8, 'maximum': 11}},
        })['hosts']
        self.assertEqual(extra[0]['self_repair'], 'executive_armor_daily')
        self.assertTrue(extra[1]['unrepairable'])
        derived = server.derive(data)
        self.assertEqual(derived['sp_body'], 12)

    def test_curated_integrated_cyberweapon_profiles_are_allowlisted(self):
        expected = {
            'cyberware-15': ('ranged', '5d6', 2),
            'cyberware-42': ('melee', '3d6', 0),
            'cyberware-48': ('ranged_dual', '6d6 / 8d6', 1),
            'cyberware-117': ('ranged', '6d6', 1),
            'cyberware-133': ('melee', '3d6', 0),
        }
        for catalog_id, values in expected.items():
            item = copy.deepcopy(server.item_by_id(catalog_id))
            item.update({'key': catalog_id, 'catalog_item_id': catalog_id})
            profile = server.cyberware_weapon_profile(item)
            self.assertEqual((profile['kind'], profile['damage'],
                              profile.get('magazine') or 0), values)
        mantis = copy.deepcopy(server.item_by_id('cyberware-42'))
        mantis.update({'key': 'cyberware-42', 'catalog_item_id': 'cyberware-42'})
        self.assertEqual(server.cyberware_capacity(mantis)['slots_used'], 2)
        popup = copy.deepcopy(server.item_by_id('cyberware-118'))
        popup.update({'key': 'cyberware-118', 'catalog_item_id': 'cyberware-118'})
        medium = copy.deepcopy(server.item_by_id('melee-1'))
        medium.update({'key': 'melee-1', 'catalog_item_id': 'melee-1',
                       'instance_id': '9' * 32, 'state': 'carried'})
        self.assertTrue(server.popup_weapon_binding_compatibility(
            popup, medium)['allowed'])
        very_heavy = copy.deepcopy(server.item_by_id('melee-3'))
        very_heavy.update({'key': 'melee-3', 'catalog_item_id': 'melee-3',
                           'instance_id': '8' * 32, 'state': 'carried'})
        self.assertFalse(server.popup_weapon_binding_compatibility(
            popup, very_heavy)['allowed'])

    def test_curated_cyberware_payloads_and_sensor_array_slots(self):
        neural = copy.deepcopy(server.item_by_id('cyberware-58'))
        neural.update({'key': 'cyberware-58', 'catalog_item_id': 'cyberware-58',
                       'instance_id': '1' * 32, 'state': 'installed'})
        kerenzikov = copy.deepcopy(server.item_by_id('cyberware-62'))
        kerenzikov.update({
            'key': 'cyberware-62', 'catalog_item_id': 'cyberware-62',
            'instance_id': '2' * 32, 'state': 'installed',
            'host_instance': neural['instance_id'],
            'host_instances': [neural['instance_id']],
        })
        loadout = server.effective_cyberware_loadout(
            {'cyberware': [neural, kerenzikov]})
        self.assertEqual(loadout['initiative_modifier'], 2)
        self.assertIn('kerenzikov-initiative',
                      [item['id'] for item in loadout['active_payloads']])
        sandevistan = copy.deepcopy(server.item_by_id('cyberware-63'))
        sandevistan.update({
            'key': 'cyberware-63', 'catalog_item_id': 'cyberware-63',
            'instance_id': '3' * 32, 'state': 'installed',
            'host_instance': neural['instance_id'],
            'host_instances': [neural['instance_id']],
        })
        with self.assertRaisesRegex(server.ApiError, 'speedware'):
            server.validate_cyberware_payload_conflicts(
                {'cyberware': [neural, kerenzikov, sandevistan]})

        audio = copy.deepcopy(server.item_by_id('cyberware-81'))
        audio.update({'key': 'cyberware-81', 'catalog_item_id': 'cyberware-81',
                      'instance_id': '4' * 32, 'state': 'installed'})
        sensor = copy.deepcopy(server.item_by_id('cyberware-141'))
        sensor.update({
            'key': 'cyberware-141', 'catalog_item_id': 'cyberware-141',
            'instance_id': '5' * 32, 'state': 'installed',
            'host_instance': audio['instance_id'],
            'host_instances': [audio['instance_id']],
        })
        audio_options = []
        for index, catalog_id in enumerate(
                ('cyberware-76', 'cyberware-77', 'cyberware-78', 'cyberware-87'), start=6):
            option = copy.deepcopy(server.item_by_id(catalog_id))
            option.update({
                'key': catalog_id, 'catalog_item_id': catalog_id,
                'instance_id': f'{index:032x}', 'state': 'installed',
                'host_instance': audio['instance_id'],
                'host_instances': [audio['instance_id']],
            })
            audio_options.append(option)
        audio_data = {'cyberware': [audio, sensor, *audio_options]}
        audio_loadout = server.effective_cyberware_loadout(audio_data)
        host = audio_loadout['hosts'][0]
        self.assertEqual((host['slots_base'], host['slots_granted'],
                          host['slots_total'], host['slots_used']), (3, 5, 8, 4))
        sensor['state'] = 'carried'
        without_sensor = server.effective_cyberware_loadout(audio_data)
        self.assertTrue(without_sensor['hosts'][0]['overloaded'])

    def test_cyberware_runtime_audit_state_is_server_owned(self):
        char = valid_character()
        char['cyberware_state'] = {'forged': {'humanity_loss_events': 0}}
        char['therapy_state'] = {'active': {'forged': True}}
        cleaned = server.clean_character(char)
        self.assertNotIn('cyberware_state', cleaned)
        self.assertNotIn('therapy_state', cleaned)

    def test_cyberware_installation_profiles_and_sides_are_declarative(self):
        arm = copy.deepcopy(server.item_by_id('cyberware-109'))
        self.assertEqual(server.cyberware_installation_profile(arm)['required_site'],
                         'Hospital')
        biosystem = copy.deepcopy(server.item_by_id('cyberware-222'))
        profile = server.cyberware_installation_profile(biosystem)
        self.assertEqual(profile['required_site'], 'Hospital')
        self.assertTrue(profile['biosystem_required'])
        left = copy.deepcopy(arm)
        left.update({'instance_id': 'e' * 32, 'state': 'installed',
                     'installation_side': 'left'})
        right = copy.deepcopy(arm)
        right.update({'instance_id': 'f' * 32, 'state': 'installed',
                      'installation_side': 'right'})
        server.validate_cyberware_sides({'cyberware': [left, right]})
        right['installation_side'] = 'left'
        with self.assertRaisesRegex(server.ApiError, 'сторона left уже занята'):
            server.validate_cyberware_sides({'cyberware': [left, right]})

    def test_staged_cyberware_does_not_apply_humanity_loss(self):
        arm = copy.deepcopy(server.item_by_id('cyberware-109'))
        arm.update({'key': 'cyberware-109', 'catalog_item_id': 'cyberware-109',
                    'instance_id': '4' * 32, 'type': 'Cyberlimbs', 'state': 'carried'})
        char = {'stats': {'EMP': 6}, 'cyberware': [arm]}
        staged = server.derive(char)
        self.assertEqual((staged['humanity_cur'], staged['humanity_max'], staged['hl_total']),
                         (60, 60, 0))
        arm['state'] = 'installed'
        installed = server.derive(char)
        self.assertEqual((installed['humanity_cur'], installed['humanity_max'],
                          installed['hl_total']), (53, 58, 7))

    def test_explicit_cyberware_foundation_requirement_is_checked(self):
        char = valid_character()
        char['cyberware'].append({
            'key': 'cyberware-22', 'name': 'Ballpoint Cyberfinger',
            'hl': 0, 'price': 100, 'type': 'Cyberfingers',
        })
        char['cash'] = 2450
        with self.assertRaisesRegex(server.ApiError, 'Modular Finger Cyberhand'):
            server.validate_creation(char)


class ServerLocalizationTests(unittest.TestCase):
    def test_static_api_errors_have_english_messages(self):
        tree = ast.parse((ROOT / 'app/server.py').read_text(encoding='utf-8'))
        messages = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                    node.func.id == 'ApiError' and len(node.args) > 1):
                try:
                    message = ast.literal_eval(node.args[1])
                except (ValueError, TypeError):
                    continue
                if isinstance(message, str) and re.search(r'[А-Яа-яЁё]', message):
                    messages.append(message)
        untranslated = {
            message: server.server_error_message(message, 'en')
            for message in messages
            if re.search(r'[А-Яа-яЁё]', server.server_error_message(message, 'en'))
        }
        dynamic_messages = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                    node.func.id == 'ApiError' and len(node.args) > 1 and
                    isinstance(node.args[1], ast.JoinedStr)):
                dynamic_messages.append(''.join(
                    value.value if isinstance(value, ast.Constant) else 'X'
                    for value in node.args[1].values
                ))
        untranslated.update({
            message: server.server_error_message(message, 'en')
            for message in dynamic_messages
            if re.search(r'[А-Яа-яЁё]', server.server_error_message(message, 'en'))
        })
        self.assertEqual(untranslated, {})
        self.assertEqual(server.server_error_message('Персонаж не найден', 'ru'),
                         'Персонаж не найден')

    def test_english_metadata_has_no_cyrillic(self):
        metadata = [server.ROLE_DESC_EN, server.WOUND_STATES_EN,
                    server.CRIT_BODY_EN, server.CRIT_HEAD_EN]
        self.assertNotRegex(json.dumps(metadata, ensure_ascii=False), r'[А-Яа-яЁё]')


class CatalogArmorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = json.loads((ROOT / 'app/data/items.json').read_text(encoding='utf-8'))['items']
        cls.armor = {item['name']: item for item in cls.items if item['cat'] == 'armor'}

    def test_location_exceptions_from_sources(self):
        self.assertEqual(self.armor['MechaMan Motorcycle Helmet']['armor_locations'], ['head'])
        self.assertEqual(self.armor['The Dirk Combat Jacket']['armor_locations'], ['body'])
        self.assertEqual(self.armor['Bulletproof Shield']['armor_locations'], ['shield'])
        self.assertTrue(self.armor['Bodyweight Suit']['armor_bundled'])
        self.assertTrue(self.armor['Fire Brand Bunker Gear']['armor_bundled'])
        self.assertEqual(self.armor['Roller Derby Padding']['armor_locations'], ['body', 'head'])

    def test_distinct_penalties_are_preserved(self):
        self.assertEqual(
            self.armor['Hybrid Metalgear®']['penalties'],
            {'REF': -3, 'DEX': -4, 'MOVE': -4},
        )

    def test_catalog_expands_to_body_head_set_and_shield_variants(self):
        count = sum(1 if item['armor_bundled'] else len(item['armor_locations'])
                    for item in self.armor.values())
        self.assertEqual(count, 42)

    def test_catalog_contains_structured_mechanics_and_compatibility(self):
        by_name = {item['name']: item for item in self.items}
        pistol = by_name['Medium Pistol']
        self.assertEqual(pistol['mechanics']['damage'], {
            'notation': '2d6', 'dice': 2, 'sides': 6,
            'multiplier': 1, 'average': 7.0,
        })
        self.assertEqual(pistol['mechanics']['rof'], 2)
        self.assertEqual(pistol['mechanics']['magazine'], 12)
        self.assertEqual(pistol['mechanics']['hands'], 1)
        self.assertEqual(pistol['fields']['Mag'], '12')
        self.assertEqual(by_name['Banhammer']['mechanics']['atk'], 1)
        self.assertEqual(by_name['Banhammer']['mechanics']['def'], 0)
        shield = by_name['Bulletproof Shield']
        self.assertEqual(shield['mechanics']['armor_locations'], ['shield'])
        self.assertFalse(shield['mechanics']['armor_bundled'])
        self.assertIn('compatible_weapons', by_name['Basic']['mechanics'])
        self.assertEqual(by_name['Cyberarm']['capacity']['slots_total'], 4)
        self.assertEqual(by_name['Popup Grenade Launcher']['capacity']['host'], 'Cyberarm')
        self.assertEqual(by_name['Popup Grenade Launcher']['capacity']['slots_used'], 2)

    def test_catalog_has_curated_consumables_and_active_gear(self):
        items = {item['name']: item for item in server.catalog()['items']}
        flashlight = items['Flashlight']
        radio = items['Radio Communicator']
        self.assertTrue(flashlight['equippable'])
        self.assertEqual(flashlight['equip_modes'], ['held', 'ready'])
        self.assertEqual(flashlight['equip_slots'], ['hand', 'belt'])
        self.assertTrue(flashlight['activation_required'])
        self.assertTrue(radio['equippable'])
        self.assertIn('worn', radio['equip_modes'])
        self.assertEqual(radio['hands_required'], 0)
        for name in ('Antibiotic', 'Rapidetox', 'Speedheal', 'Stim'):
            item = items[name]
            self.assertTrue(item['consumable'])
            self.assertTrue(item['stackable'])
            self.assertEqual(item['consume_amount'], 1)
            self.assertEqual(item['use_effect']['kind'], 'manual')
            self.assertTrue(item['use_effect']['manual_resolution_required'])
            self.assertNotIn('javascript', json.dumps(item['use_effect']).lower())
        self.assertFalse(items['Carryall'].get('consumable', False))
        self.assertFalse(items['Carryall'].get('equippable', False))

    def test_gun_upgrades_have_normalized_host_slot_metadata(self):
        by_name = {item['name']: item for item in server.catalog()['items']
                   if item['cat'] == 'gun_upgrades'}
        self.assertEqual(by_name['Power Rebuild']['host_type'], 'weapon')
        self.assertEqual(by_name['Power Rebuild']['modification_kind'], 'rebuild')
        self.assertEqual(by_name['Power Rebuild']['slots_used'], 2)
        self.assertEqual(by_name['Smartgun Link']['slots_used'], 2)
        self.assertEqual(by_name['Drum Magazine']['slots_used'], 1)
        self.assertEqual(by_name['Drum Magazine']['modification_group'], 'weapon_magazine')
        self.assertEqual(by_name['Ammo Compatibity Internals']['slots_used'], 0)
        self.assertTrue(by_name['Ammo Compatibity Internals']['compatibility_manual'])
        self.assertTrue(by_name['Reinforced String']['permanent_installation'])
        self.assertEqual(by_name['Reinforced String']['compatibility_text'], 'Bows, Crossbows')
        self.assertEqual(by_name['Infrared Nightvision Scope']['slot_type'], 'scope')
        self.assertEqual(by_name['Sniping Scope']['slot_type'], 'scope')
        self.assertEqual(by_name['Compatibility Rail']['grants_slots'], {'scope': 1})
        self.assertEqual(by_name['Compatibility Rail']['slots_used'], 0)

    def test_vehicle_upgrades_have_access_prerequisite_and_conflict_metadata(self):
        by_name = {item['name']: item for item in server.catalog()['items']
                   if item['cat'] == 'vehicles_upgrades'}
        self.assertEqual(by_name['Heavy Chassis']['host_type'], 'vehicle')
        self.assertEqual(by_name['Heavy Chassis']['nomad_access_required'], 1)
        self.assertEqual(by_name['Bulletproof Glass']['repeatable_max'], 2)
        self.assertEqual(by_name['Onboard Rocket Pod']['prerequisite_upgrades'],
                         ['Heavy Chassis'])
        self.assertEqual(by_name['Housing Capacity']['prerequisite_host_names']['Heavy Chassis'],
                         ['Compact Groundcar', 'High Performance Groundcar'])
        self.assertTrue(by_name['Onboard Rocket Pod']['permanent_installation'])
        self.assertIn('Folding Frame', by_name['Enclosure (Bicycle)']['conflicting_upgrades'])
        self.assertIn('Enclosure', by_name['Folding Frame (Bicycle)']['conflicting_upgrades'])
        self.assertEqual(by_name['Seating Upgrade']['repeatable_max'], 99)
        vehicles = {item['name']: item for item in server.catalog()['items']
                    if item['cat'] == 'vehicles'}
        self.assertEqual(vehicles['SH-45 Patroller']['mechanics']['body_sp'], 0)
        self.assertEqual(vehicles['SH-45 Patroller']['mechanics']['glass_hp'], 15)
        self.assertEqual(vehicles['Zetatech AeroCop']['mechanics']['body_sp'], 13)
        self.assertEqual(vehicles['Zetatech AeroCop']['mechanics']['glass_hp'], 30)

    def test_night_market_is_grouped_by_deterministic_vendors(self):
        market = server.night_market()
        self.assertEqual(len(market['vendors']), len(server.NIGHT_MARKET_VENDORS))
        self.assertEqual(len(market['items']),
                         sum(len(vendor['items']) for vendor in market['vendors']))
        vendor_ids = {vendor['id'] for vendor in market['vendors']}
        self.assertEqual(len(vendor_ids), len(server.NIGHT_MARKET_VENDORS))
        self.assertTrue(all(item['vendor_id'] in vendor_ids for item in market['items']))
        self.assertTrue(all('mechanics' in item and 'desc' in item for item in market['items']))
        self.assertEqual(market, server.night_market())
        # 20.9: consumables live only at Street Pharmacy, never at Back-Alley.
        catalog_by_id = server.catalog()['_by_id']
        for vendor in market['vendors']:
            consumables = [item for item in vendor['items']
                           if catalog_by_id[item['id']].get('consumable')]
            if vendor['id'] == 'street-pharmacy':
                self.assertTrue(vendor['items'], 'Street Pharmacy should stock consumables')
                self.assertEqual(consumables, vendor['items'])
            else:
                self.assertEqual(consumables, [],
                                 f'{vendor["id"]} must not sell consumables')


if __name__ == '__main__':
    unittest.main()


class TechMakerModificationTests(unittest.TestCase):
    def tech_data(self):
        data = server.ensure_progression(valid_character('Tech'))
        return data

    def owned(self, catalog_id, instance_id, cat=None, state='carried'):
        item = copy.deepcopy(server.item_by_id(catalog_id))
        item.update({'key': catalog_id, 'catalog_item_id': catalog_id,
                     'instance_id': instance_id, 'qty': 1, 'state': state,
                     'cat': cat or item.get('cat')})
        return item

    def test_maker_ranks_follow_active_tech_role(self):
        data = self.tech_data()
        ranks = server.character_maker_ranks(data)
        self.assertEqual(ranks['upgrade'], 2)
        self.assertEqual(ranks['invention'], 2)
        solo = server.ensure_progression(valid_character('Solo'))
        self.assertEqual(server.character_maker_ranks(solo), {})

    def test_host_type_mapping(self):
        self.assertEqual(server.tech_maker_host_type({'cat': 'guns'}), 'weapon')
        self.assertEqual(server.tech_maker_host_type({'cat': 'armor'}), 'armor')
        self.assertEqual(server.tech_maker_host_type({'cat': 'vehicles'}), 'vehicle')
        self.assertEqual(server.tech_maker_host_type({'cat': 'cyberware'}), 'cyberware')
        self.assertIsNone(server.tech_maker_host_type({'cat': 'gear'}))

    def test_effect_allowlist_rejects_executable_or_out_of_range(self):
        self.assertEqual(server.clean_tech_maker_effect('weapon', {
            'target': 'weapon.attack_check', 'operation': 'add', 'value': 1}),
            {'target': 'weapon.attack_check', 'operation': 'add', 'value': 1})
        self.assertEqual(server.clean_tech_maker_effect('armor', {
            'target': 'armor.sp', 'operation': 'add', 'value': 1}),
            {'target': 'armor.sp', 'operation': 'add', 'value': 1})
        with self.assertRaises(server.ApiError):
            server.clean_tech_maker_effect('weapon', {
                'target': 'armor.sp', 'operation': 'add', 'value': 1})
        with self.assertRaises(server.ApiError):
            server.clean_tech_maker_effect('weapon', {
                'target': 'weapon.attack_check', 'operation': 'add', 'value': 99})
        with self.assertRaises(server.ApiError):
            server.clean_tech_maker_effect('weapon', {
                'target': 'weapon.damage', 'operation': 'set', 'value': '10d6'})
        with self.assertRaises(server.ApiError):
            server.clean_tech_maker_effect('weapon', {
                'target': 'weapon.attack_check', 'operation': 'add',
                'value': 1, 'javascript': 'alert(1)'})
        self.assertIsNone(server.clean_tech_maker_effect('weapon', None))

    def test_references_validate_against_owned_hosts(self):
        data = self.tech_data()
        data['tech_maker_state'] = {'modifications': {
            'a' * 32: {'active': True, 'host_instance_id': 'b' * 32},
        }, 'history': []}
        with self.assertRaises(server.ApiError):
            server.validate_tech_maker_references(data)
        weapon = self.owned('guns-0', 'b' * 32)
        data['inventory'] = [weapon]
        server.validate_tech_maker_references(data)

    def test_effective_weapon_applies_attack_and_magazine(self):
        host = self.owned('guns-0', '1' * 32)
        character = {
            'inventory': [host], 'cyberware': [],
            'tech_maker_state': {'modifications': {
                'a' * 32: {'active': True, 'host_instance_id': '1' * 32,
                           'name': 'Calibrated', 'source': 'Maker',
                           'modification_id': 'a' * 32,
                           'effect': {'target': 'weapon.attack_check',
                                      'operation': 'add', 'value': 1}},
                'b' * 32: {'active': True, 'host_instance_id': '1' * 32,
                           'name': 'Extended', 'source': 'Maker',
                           'modification_id': 'b' * 32,
                           'effect': {'target': 'weapon.magazine',
                                      'operation': 'add', 'value': 8}},
            }},
        }
        owned = {host['instance_id']: host}
        evaluated = server.evaluate_effective_weapon(host, [], owned, character)
        self.assertEqual(evaluated['attack_modifier'], 1)
        self.assertEqual(evaluated['effective']['magazine'], 20)
        self.assertEqual(host['mechanics']['magazine'], 12)
        maker_ids = {source['id'] for source in evaluated['sources']}
        self.assertIn('tech-maker:weapon.attack_check', maker_ids)

    def test_fabricable_categories_exclude_cyberware_and_services(self):
        self.assertTrue(server.tech_maker_fabricable_item(server.item_by_id('guns-0')))
        self.assertTrue(server.tech_maker_fabricable_item(server.item_by_id('armor-2')))
        self.assertFalse(server.tech_maker_fabricable_item(server.item_by_id('cyberware-42')))
        self.assertFalse(server.tech_maker_fabricable_item(server.item_by_id('services-31')))
        self.assertFalse(server.tech_maker_fabricable_item({'id': 'nope'}))

    def test_effective_armor_and_vehicle_apply_tech_maker(self):
        armor = self.owned('armor-2', '2' * 32)
        armor['armor_locations'] = ['body']
        char = {
            'inventory': [armor], 'cyberware': [], 'armor': {
                'body': {'instance_id': '2' * 32, 'sp': 7, 'maximum': 7, 'current': 7}},
            'tech_maker_state': {'modifications': {
                'c' * 32: {'active': True, 'host_instance_id': '2' * 32,
                           'name': 'Reinforced', 'source': 'Maker',
                           'modification_id': 'c' * 32,
                           'effect': {'target': 'armor.sp',
                                      'operation': 'add', 'value': 1}},
            }},
        }
        hosts = server.effective_armor_hosts(char)['hosts']
        self.assertEqual(hosts[0]['effective_sp'], 8)

        vehicle = self.owned('vehicles-0', '3' * 32)
        vehicle['_vehicle_state'] = {}
        vchar = {
            'inventory': [vehicle], 'cyberware': [], 'modification_state': {},
            'tech_maker_state': {'modifications': {
                'd' * 32: {'active': True, 'host_instance_id': '3' * 32,
                           'name': 'Uparmored', 'source': 'Maker',
                           'modification_id': 'd' * 32,
                           'effect': {'target': 'vehicle.sdp_max',
                                      'operation': 'add', 'value': 20}},
            }},
        }
        owned = {vehicle['instance_id']: vehicle}
        evaluated = server.evaluate_effective_vehicle(vehicle, [], owned, vchar)
        self.assertEqual(evaluated['effective']['sdp'],
                         evaluated['base']['sdp'] + 20)


class CampaignClockTests(unittest.TestCase):
    def test_duration_seconds_and_service_status(self):
        self.assertEqual(server.campaign_duration_seconds('1_hour'), 3600)
        self.assertEqual(server.campaign_duration_seconds('1_week'), 7 * 86400)
        self.assertIsNone(server.campaign_duration_seconds('manual'))
        status = server.campaign_service_status(1000, 1000 + 3600)
        self.assertFalse(status['ready'])
        self.assertEqual(status['label'], '1h')
        due = server.campaign_service_status(1000 + 7200, 1000 + 3600)
        self.assertTrue(due['ready'])
        self.assertEqual(due['label'], 'DUE')
        manual = server.campaign_service_status(1000, None)
        self.assertIsNone(manual['ready'])
        self.assertEqual(manual['label'], 'MANUAL TIME')

    def test_character_campaign_services_collects_active_work(self):
        now = 1_700_000_000.0
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript(server.CAMPAIGN_CLOCK_SCHEMA)
        conn.execute('INSERT INTO campaign_state(id,campaign_time,timezone,updated) '
                     'VALUES(1,?,?,?)', (now, 'Europe/Moscow', now))
        conn.commit()
        character = {
            'therapy_state': {'active': {
                'label': 'Therapy (Standard HL)', 'started_at': now,
                'campaign_due_at': now + 7 * 86400,
            }},
            'armor_repair_state': {'a' * 32: {'active': {
                'method': 'jeeves', 'started_at': now,
                'campaign_due_at': now + 3600,
            }}},
            'vehicle_state': {'b' * 32: {'repair': {
                'severity': 'major', 'started_at': now,
                'campaign_due_at': now + 86400,
            }}},
        }
        services = server.character_campaign_services(character, conn)
        kinds = {service['kind'] for service in services}
        self.assertEqual(kinds, {'therapy', 'armor_repair', 'vehicle_repair'})
        therapy = next(service for service in services if service['kind'] == 'therapy')
        self.assertFalse(therapy['ready'])
        conn.close()

    def test_vehicle_repair_severity_duration_key_maps(self):
        self.assertEqual(server.VEHICLE_REPAIR_RULES['minor']['duration_key'], '3_hours')
        self.assertEqual(server.VEHICLE_REPAIR_RULES['major']['duration_key'], '1_day')
        self.assertEqual(server.VEHICLE_REPAIR_RULES['destroyed']['duration_key'], '1_week')
        self.assertIsNotNone(server.campaign_duration_seconds(
            server.VEHICLE_REPAIR_RULES['destroyed']['duration_key']))


class CrewStashUnitTests(unittest.TestCase):
    def test_split_stack_preserves_ammo_rounds(self):
        entry = {
            'instance_id': 'a' * 32, 'cat': 'ammo', 'name': 'Basic Handgun Ammo',
            'qty': 3, 'mechanics': {'quantity_per_purchase': 10}, 'ammo_rounds': 25,
        }
        remaining, taken = server._split_stack(entry, 1)
        self.assertEqual(remaining['qty'], 2)
        self.assertEqual(taken['qty'], 1)
        self.assertEqual(taken['ammo_rounds'], 10)
        self.assertEqual(remaining['ammo_rounds'], 15)

    def test_split_stack_full_move_returns_none_remaining(self):
        entry = {'instance_id': 'a' * 32, 'cat': 'ammo', 'qty': 2,
                 'mechanics': {'quantity_per_purchase': 10}, 'ammo_rounds': 20}
        remaining, taken = server._split_stack(entry, 2)
        self.assertIsNone(remaining)
        self.assertEqual(taken['qty'], 2)

    def test_prepare_entry_for_holder_normalises_state_and_keeps_id(self):
        entry = {'instance_id': 'a' * 32, 'qty': 4, 'state': 'equipped',
                 'equipped_mode': 'held', 'active': True}
        stashed = server._prepare_entry_for_holder(entry, 'stash')
        self.assertEqual(stashed['state'], 'stored')
        self.assertEqual(stashed['qty'], 4)
        self.assertNotIn('equipped_mode', stashed)
        self.assertNotIn('active', stashed)
        self.assertEqual(stashed['instance_id'], 'a' * 32)
        carried = server._prepare_entry_for_holder(entry, 'char')
        self.assertEqual(carried['state'], 'carried')

    def test_detach_and_attach_runtime_state_roundtrip(self):
        source = {'weapon_state': {'a' * 32: {'magazine': 7, 'magazine_max': 12}},
                  'inventory': []}
        entry = {'instance_id': 'a' * 32}
        server._detach_runtime_state(source, entry, 'a' * 32)
        self.assertNotIn('a' * 32, source['weapon_state'])
        self.assertIn('_runtime', entry)
        target = {}
        server._attach_runtime_state(target, entry, 'a' * 32)
        self.assertEqual(target['weapon_state']['a' * 32]['magazine'], 7)
        self.assertNotIn('_runtime', entry)


class CharacterImportTests(unittest.TestCase):
    def _portable(self):
        return {
            'handle': 'V', 'role': 'Solo', 'role_rank': 4,
            'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}],
            'active_role': 'Solo',
            'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6,
                      'DEX': 7, 'REF': 7, 'TECH': 4, 'INT': 4, 'COOL': 4, 'EMP': 5},
            'skills': {'Handgun': 6, 'Evasion': 4, 'Language (Streetslang)': 2,
                       'Local Expert (Watson)': 2, 'Brawling': 2, 'Concentration': 2,
                       'Perception': 2, 'Stealth': 2, 'First Aid': 1},
            'native_language': 'Streetslang',
            'inventory': [
                {'key': 'guns-0', 'catalog_item_id': 'guns-0', 'instance_id': 'a' * 32,
                 'cat': 'guns', 'name': 'Medium Pistol', 'qty': 1, 'state': 'carried',
                 'price': 50},
                {'key': 'armor-5', 'catalog_item_id': 'armor-5', 'instance_id': 'c' * 32,
                 'cat': 'armor', 'name': 'Kevlar', 'qty': 1, 'state': 'equipped'},
            ],
            'cyberware': [],
            'armor': {'body': {'key': 'armor-5', 'catalog_item_id': 'armor-5',
                               'instance_id': 'c' * 32, 'name': 'Kevlar', 'sp': 7}},
            'cash': 500, 'ip_available': 10, 'ip_total_earned': 10,
            'ip_total_spent': 0, 'reputation': 3, 'luck_cur': 5,
        }

    def test_import_strips_runtime_state_and_forces_private(self):
        raw = self._portable()
        raw['weapon_state'] = {'a' * 32: {'magazine': 3, 'magazine_max': 12, 'reserve': 0}}
        raw['armor_tech_state'] = {'c' * 32: {'active': True, 'mode': 'sp_plus_one'}}
        raw['portrait_media_id'] = 'd' * 32
        raw['public'] = True
        raw['archived'] = True
        data = server.canonical_import_character(raw)
        self.assertFalse(data.get('public'))
        self.assertNotIn('portrait_media_id', data)
        self.assertNotIn('archived', data)
        self.assertNotIn('armor_tech_state', data)
        self.assertNotIn('cyberware_state', data)
        self.assertNotIn('tech_maker_state', data)
        # weapon_state is re-defaulted (fresh full magazine) under the new id.
        weapon = next(i for i in data['inventory'] if i['cat'] == 'guns')
        self.assertNotEqual(weapon['instance_id'], 'a' * 32)
        self.assertEqual(list(data['weapon_state'].keys()), [weapon['instance_id']])
        state = data['weapon_state'][weapon['instance_id']]
        self.assertEqual(state['magazine'], state['magazine_max'])

    def test_import_regenerates_ids_and_rebinds_armor(self):
        data = server.canonical_import_character(self._portable())
        ids = {i['instance_id'] for i in data['inventory']}
        self.assertNotIn('a' * 32, ids)
        self.assertNotIn('c' * 32, ids)
        armor_owned = next(i for i in data['inventory'] if i['cat'] == 'armor')
        self.assertEqual(data['armor']['body']['instance_id'], armor_owned['instance_id'])
        self.assertEqual(armor_owned['state'], 'equipped')

    def test_import_preserves_resources_and_quantity(self):
        data = server.canonical_import_character(self._portable())
        self.assertEqual(data['cash'], 500)
        self.assertEqual(data['ip_available'], 10)
        self.assertEqual(data['reputation'], 3)
        self.assertEqual(data['luck_cur'], 5)
        weapon = next(i for i in data['inventory'] if i['cat'] == 'guns')
        self.assertEqual(weapon['qty'], 1)
        self.assertEqual(weapon['price'], 50)

    def test_import_accepts_envelopes_and_strings(self):
        raw = self._portable()
        data = server.canonical_import_character({'id': 1, 'derived': {}, 'data': raw})
        self.assertEqual(data['handle'], 'V')
        data2 = server.canonical_import_character(json.dumps(raw))
        self.assertEqual(data2['handle'], 'V')

    def test_import_rejects_unknown_item_and_invalid_json(self):
        raw = self._portable()
        raw['inventory'].append({'key': 'not-real', 'name': 'Ghost'})
        with self.assertRaises(server.ApiError) as unknown:
            server.canonical_import_character(raw)
        self.assertEqual(unknown.exception.status, 400)
        with self.assertRaises(server.ApiError) as bad_json:
            server.canonical_import_character('{not valid json')
        self.assertEqual(bad_json.exception.status, 400)
        with self.assertRaises(server.ApiError) as not_object:
            server.canonical_import_character([1, 2, 3])
        self.assertEqual(not_object.exception.status, 400)


class MarketStockTests(unittest.TestCase):
    def test_night_market_exposes_finite_stock_and_availability(self):
        market = server.night_market()
        self.assertEqual(len(market['vendors']), len(server.NIGHT_MARKET_VENDORS))
        for item in market['items']:
            self.assertIsInstance(item['stock'], int)
            self.assertGreaterEqual(item['stock'], 1)
            self.assertLessEqual(item['stock'], 5)
            self.assertEqual(item['stock_remaining'], item['stock'])
            self.assertFalse(item['sold_out'])
            self.assertFalse(item['reserved'])
            self.assertIsNone(item['reserved_character_id'])
            self.assertIsInstance(item['new_today'], bool)
        self.assertTrue(all('location' in vendor for vendor in market['vendors']))
        self.assertTrue(all(vendor['location'] for vendor in market['vendors']))

    def test_night_market_rotation_is_deterministic_per_day(self):
        self.assertEqual(server.nm_rotation('2026-08-22'), server.nm_rotation('2026-08-22'))
        a = server.nm_rotation('2026-08-22')
        b = server.nm_rotation('2026-08-23')
        self.assertNotEqual(a['items'], b['items'])

    def test_nm_day_offset_rolls_forward_and_back(self):
        self.assertEqual(server.nm_day_offset('2026-08-22', -1), '2026-08-21')
        self.assertEqual(server.nm_day_offset('2026-08-22', 1), '2026-08-23')
        self.assertEqual(server.nm_day_offset('2026-03-01', -1), '2026-02-28')

    def test_stock_seed_is_bounded_and_deterministic(self):
        seed = server.nm_stock_seed('2026-08-22', 'gunmart-after-dark', 'guns-0')
        self.assertGreaterEqual(seed, 1)
        self.assertLessEqual(seed, 5)
        self.assertEqual(seed, server.nm_stock_seed('2026-08-22', 'gunmart-after-dark', 'guns-0'))

    def test_market_stock_seeding_is_idempotent(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript(server.MARKET_STOCK_SCHEMA)
        rotation = server.ensure_market_stock(conn, '2026-08-22')
        first_count = conn.execute('SELECT COUNT(*) n FROM market_stock').fetchone()['n']
        self.assertEqual(first_count, len(rotation['items']))
        # Re-seeding must not duplicate rows or reset already-decremented stock.
        conn.execute('UPDATE market_stock SET stock_remaining=stock_remaining-1 WHERE item_id=?',
                     (rotation['items'][0]['id'],))
        conn.commit()
        server.ensure_market_stock(conn, '2026-08-22')
        self.assertEqual(conn.execute('SELECT COUNT(*) n FROM market_stock').fetchone()['n'], first_count)
        first_item = rotation['items'][0]
        seed = server.nm_stock_seed('2026-08-22', first_item['vendor_id'], first_item['id'])
        remaining = conn.execute('SELECT stock_remaining FROM market_stock WHERE item_id=?',
                                 (first_item['id'],)).fetchone()['stock_remaining']
        self.assertEqual(remaining, seed - 1)
        conn.close()

    def test_night_market_with_conn_reflects_purchases_and_reservations(self):
        conn = sqlite3.connect(':memory:')
        conn.row_factory = sqlite3.Row
        conn.executescript(server.MARKET_STOCK_SCHEMA)
        rotation = server.ensure_market_stock(conn, '2026-08-22')
        target = rotation['items'][0]
        conn.execute('UPDATE market_stock SET stock_remaining=0,reserved_character_id=7,'
                     'reserved_note=\'held\' WHERE item_id=?', (target['id'],))
        conn.execute('CREATE TABLE IF NOT EXISTS characters('
                     'id INTEGER PRIMARY KEY, data TEXT NOT NULL)')
        conn.execute('INSERT INTO characters(id,data) VALUES(7,?)',
                     (json.dumps({'handle': 'Reserved V'}),))
        conn.commit()
        market = server.night_market(day='2026-08-22', conn=conn)
        item = next(i for i in market['items'] if i['id'] == target['id'])
        self.assertTrue(item['sold_out'])
        self.assertTrue(item['reserved'])
        self.assertEqual(item['reserved_character_id'], 7)
        self.assertEqual(item['reserved_handle'], 'Reserved V')
        conn.close()


class NPCStatblockTests(unittest.TestCase):
    def test_clean_statblock_normalizes_stats_skills_weapons(self):
        statblock = server.clean_npc_statblock({
            'stats': {'REF': 8, 'DEX': 7, 'BODY': 6, 'BOGUS': 99},
            'skills': {'Handgun': 6, 'Evasion': 7, 'Melee Weapon': 4},
            'weapons': [
                {'name': 'Medium Pistol', 'skill': 'Handgun', 'damage': '2d6', 'rof': '1'},
            ],
            'notes': 'Maelstrom guard',
        })
        self.assertNotIn('BOGUS', statblock['stats'])
        self.assertEqual(statblock['stats']['REF'], 8)
        self.assertEqual(statblock['skills']['Handgun'], 6)
        self.assertEqual(statblock['weapons'][0]['name'], 'Medium Pistol')
        self.assertEqual(statblock['notes'], 'Maelstrom guard')
        # Out-of-range values are bounded.
        self.assertEqual(server.clean_npc_statblock(
            {'stats': {'REF': 99}, 'skills': {'Handgun': 99}, 'weapons': []})['stats']['REF'], 20)
        self.assertEqual(server.clean_npc_statblock(
            {'stats': {}, 'skills': {'Handgun': 99}, 'weapons': []})['skills']['Handgun'], 10)

    def test_clean_statblock_rejects_unknown_skill_and_bad_weapons(self):
        with self.assertRaises(server.ApiError) as bad_skill:
            server.clean_npc_statblock({'stats': {}, 'skills': {'NotASkill': 3}, 'weapons': []})
        self.assertEqual(bad_skill.exception.status, 400)
        with self.assertRaises(server.ApiError) as bad_weapon:
            server.clean_npc_statblock({'stats': {}, 'skills': {}, 'weapons': ['oops']})
        self.assertEqual(bad_weapon.exception.status, 400)
        with self.assertRaises(server.ApiError) as no_name:
            server.clean_npc_statblock({'stats': {}, 'skills': {}, 'weapons': [{'skill': 'Handgun'}]})
        self.assertEqual(no_name.exception.status, 400)

    def test_derived_computes_attack_bases_and_saves(self):
        statblock = server.clean_npc_statblock({
            'stats': {'REF': 8, 'DEX': 7, 'BODY': 6},
            'skills': {'Handgun': 6, 'Evasion': 6, 'Brawling': 4},
            'weapons': [
                {'name': 'Medium Pistol', 'skill': 'Handgun', 'damage': '2d6'},
                {'name': 'Knife', 'skill': 'Melee Weapon', 'damage': '1d6'},
            ],
            'notes': '',
        })
        derived = server.npc_statblock_derived(statblock)
        pistol = next(a for a in derived['attacks'] if a['name'] == 'Medium Pistol')
        self.assertEqual(pistol['base'], 14)  # REF 8 + Handgun 6
        self.assertEqual(pistol['stat'], 'REF')
        self.assertEqual(derived['death_save'], 6)  # BODY
        self.assertEqual(derived['evasion_base'], 13)  # DEX 7 + Evasion 6
        skill_names = {s['name'] for s in derived['skills']}
        self.assertIn('Handgun', skill_names)

    def test_derived_empty_statblock_returns_zeros(self):
        derived = server.npc_statblock_derived({})
        self.assertEqual(derived['attacks'], [])
        self.assertEqual(derived['skills'], [])
        self.assertEqual(derived['death_save'], 0)
        self.assertEqual(derived['evasion_base'], 0)


class SessionRecapTests(unittest.TestCase):
    def test_clean_recap_input_normalizes_lists_and_fields(self):
        cleaned = server.clean_session_recap_input({
            'title': 'The Heist', 'session_date': 1700000000,
            'public_summary': 'Vault opened', 'gm_notes': 'NPC fled',
            'participants': [{'kind': 'npc', 'name': 'Guard'}, 'V'],
            'choices': ['Betrayed fixer', ''], 'loot': ['2000 eb'],
        })
        self.assertEqual(cleaned['title'], 'The Heist')
        self.assertEqual(cleaned['session_date'], 1700000000)
        self.assertEqual(cleaned['participants'],
                         [{'kind': 'npc', 'name': 'Guard'}, {'kind': 'character', 'name': 'V'}])
        self.assertEqual(cleaned['choices'], ['Betrayed fixer'])
        self.assertFalse(cleaned['published'])
        self.assertFalse(cleaned['publish_feed'])

    def test_clean_recap_input_requires_title(self):
        with self.assertRaises(server.ApiError) as err:
            server.clean_session_recap_input({'title': ''})
        self.assertEqual(err.exception.status, 400)
        with self.assertRaises(server.ApiError) as err2:
            server.clean_session_recap_input({'title': 'X', 'choices': 'not-a-list'})
        self.assertEqual(err2.exception.status, 400)

    def test_recap_text_list_bounded(self):
        values = [f'item {i}' for i in range(200)]
        cleaned = server._clean_recap_text_list(values)
        self.assertEqual(len(cleaned), server.RECAP_TEXT_LIST_LIMIT)

    def test_recap_public_payload_hides_private_fields(self):
        row = {
            'id': 1, 'session_date': 1700000000, 'title': 'Recap',
            'public_summary': 'summary', 'gm_notes': 'secret',
            'participants_json': '[]', 'locations_json': '["Watson"]',
            'choices_json': '["choice"]', 'loot_json': '["loot"]',
            'npc_changes_json': '[]', 'injuries_json': '[]', 'quotes_json': '[]',
            'session_id': 1, 'contract_id': 1, 'storyline_id': 1,
            'owner_user_id': 2, 'feed_post_id': 5, 'timeline_id': 7,
            'published': 1, 'created': 1, 'updated': 1,
        }
        public = server.recap_public_payload(row)
        self.assertNotIn('gm_notes', public)
        self.assertNotIn('loot', public)
        self.assertIn('locations', public)
        full = server.session_recap_payload(row, full=True)
        self.assertEqual(full['gm_notes'], 'secret')
        self.assertEqual(full['loot'], ['loot'])
        self.assertEqual(full['choices'], ['choice'])


class DowntimePlannerTests(unittest.TestCase):
    def test_activity_allowlist_validation(self):
        activity = server.clean_downtime_activity({'id': 'hustle', 'note': 'x'})
        self.assertEqual(activity['id'], 'hustle')
        self.assertEqual(activity['resolved'], False)
        with self.assertRaises(server.ApiError) as err:
            server.clean_downtime_activity({'id': 'not-real'})
        self.assertEqual(err.exception.status, 400)
        with self.assertRaises(server.ApiError) as err2:
            server.clean_downtime_activity('nope')
        self.assertEqual(err2.exception.status, 400)

    def test_activities_bounded(self):
        many = [{'id': 'other'} for _ in range(20)]
        with self.assertRaises(server.ApiError) as err:
            server.clean_downtime_activities(many)
        self.assertEqual(err.exception.status, 400)
        self.assertEqual(len(server.clean_downtime_activities(None)), 0)
        self.assertEqual(len(server.clean_downtime_activities([{'id': 'other'}])), 1)

    def test_downtime_payload_structure(self):
        data = {'downtime_state': {
            'active': {'downtime_id': 'x', 'started_at': 1, 'campaign_started_at': 1,
                       'campaign_due_at': None, 'duration_key': None, 'duration_label': None,
                       'note': 'off', 'created_by': 1, 'activities': [
                           {'id': 'hustle', 'note': '', 'resolved': False, 'resolution_note': ''}]},
            'history': [],
        }}
        payload = server.downtime_payload(data)
        self.assertIsNotNone(payload['active'])
        self.assertEqual(payload['active']['activities'][0]['kind'], 'hustle')
        self.assertEqual(payload['active']['status'], 'MANUAL TIME')
        self.assertIn('activities', payload)
        self.assertEqual(len(payload['activities']), len(server.DOWNTIME_ACTIVITIES))

    def test_downtime_state_not_accepted_on_creation(self):
        raw = {'handle': 'V', 'role': 'Solo', 'role_rank': 4,
               'roles': [{'name': 'Solo', 'rank': 4, 'primary': True}],
               'stats': {'BODY': 6, 'WILL': 6, 'LUCK': 5, 'MOVE': 6},
               'skills': {}, 'inventory': [], 'cyberware': [], 'armor': {},
               'downtime_state': {'active': {'note': 'sneaky'}}}
        cleaned = server.clean_character(raw)
        self.assertNotIn('downtime_state', cleaned)


class MapLocationsTests(unittest.TestCase):
    def test_clean_location_input_normalizes_and_bounds(self):
        cleaned = server.clean_location_input({
            'name_en': 'Crew Hideout', 'name_ru': 'База', 'kind': 'other',
            'district_id': 'heywood-wellsprings', 'x': 450, 'y': 560,
            'description_en': 'Our place', 'source': 'Campaign',
        })
        self.assertEqual(cleaned['name_en'], 'Crew Hideout')
        self.assertEqual(cleaned['kind'], 'other')
        self.assertEqual(cleaned['x'], 450.0)
        # Out-of-range coordinates are bounded to the map.
        bounded = server.clean_location_input({'name_en': 'Xx', 'x': 5000, 'y': -50})
        self.assertEqual(bounded['x'], 1000.0)
        self.assertEqual(bounded['y'], 0.0)

    def test_clean_location_input_rejects_invalid(self):
        with self.assertRaises(server.ApiError) as no_name:
            server.clean_location_input({'name_en': ''})
        self.assertEqual(no_name.exception.status, 400)
        with self.assertRaises(server.ApiError) as bad_kind:
            server.clean_location_input({'name_en': 'X', 'kind': 'not-a-kind'})
        self.assertEqual(bad_kind.exception.status, 400)
        with self.assertRaises(server.ApiError) as bad_district:
            server.clean_location_input({'name_en': 'X', 'district_id': 'mars'})
        self.assertEqual(bad_district.exception.status, 400)

    def test_seed_locations_have_valid_shape(self):
        self.assertGreaterEqual(len(server.NC_SEED_LOCATIONS), 15)
        ids = set()
        for item in server.NC_SEED_LOCATIONS:
            self.assertIn(item['kind'], server.LOCATION_KINDS)
            self.assertIn(item['district_id'], server.NC_LOCATION_IDS)
            self.assertTrue(0 <= item['x'] <= 1000)
            self.assertTrue(0 <= item['y'] <= 1000)
            self.assertNotIn(item['id'], ids)
            ids.add(item['id'])
            self.assertTrue(item['source'])


class MemorialTests(unittest.TestCase):
    def test_clean_memorial_input_normalizes(self):
        cleaned = server.clean_memorial_input({
            'status': 'deceased', 'handle': 'V', 'role': 'Solo', 'role_rank': 4,
            'death_date': 1700000000, 'cause': 'Flatlined', 'visibility': 'public',
        })
        self.assertEqual(cleaned['handle'], 'V')
        self.assertEqual(cleaned['status'], 'deceased')
        self.assertEqual(cleaned['death_date'], 1700000000)
        self.assertEqual(cleaned['visibility'], 'public')

    def test_clean_memorial_input_rejects_invalid(self):
        with self.assertRaises(server.ApiError) as bad_status:
            server.clean_memorial_input({'handle': 'V', 'status': 'zombie'})
        self.assertEqual(bad_status.exception.status, 400)
        with self.assertRaises(server.ApiError) as no_handle:
            server.clean_memorial_input({'status': 'deceased'})
        self.assertEqual(no_handle.exception.status, 400)

    def test_clean_legacy_input_requires_drink(self):
        cleaned = server.clean_legacy_input({'drink_name': 'The V', 'ingredients': 'Vodka'})
        self.assertEqual(cleaned['drink_name'], 'The V')
        self.assertEqual(cleaned['ingredients'], 'Vodka')
        with self.assertRaises(server.ApiError) as no_drink:
            server.clean_legacy_input({'drink_name': ''})
        self.assertEqual(no_drink.exception.status, 400)

    def test_memorial_payload_gates_private_fields(self):
        row = {
            'id': 1, 'character_id': 5, 'handle': 'V', 'role': 'Solo', 'role_rank': 4,
            'portrait_media_id': None, 'status': 'deceased', 'death_date': 1.0,
            'location': 'Night City', 'cause': 'Flatlined', 'epitaph': 'Bright',
            'last_words': '', 'obituary': 'Fell', 'gm_notes': 'Secret',
            'visibility': 'public', 'legacy_drink_name': 'The V',
            'legacy_ingredients': 'Vodka', 'legacy_preparation': '', 'legacy_glass': '',
            'legacy_garnish': '', 'legacy_quote': '', 'legacy_legend': '',
            'legacy_awarded_by': None, 'legacy_awarded_at': None, 'feed_post_id': None,
            'created_by': 1, 'created': 1.0, 'updated': 1.0,
        }
        public = server.memorial_payload(row)
        self.assertNotIn('gm_notes', public)
        self.assertNotIn('created_by', public)
        self.assertEqual(public['legacy']['drink_name'], 'The V')
        full = server.memorial_payload(row, full=True)
        self.assertEqual(full['gm_notes'], 'Secret')
        self.assertEqual(full['created_by'], 1)
        no_legacy = dict(row, legacy_drink_name='')
        self.assertIsNone(server.memorial_payload(no_legacy)['legacy'])
