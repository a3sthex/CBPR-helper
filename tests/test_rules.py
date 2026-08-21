import ast
import copy
import importlib.util
import json
import re
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
        self.assertEqual(len(market['vendors']), 6)
        self.assertEqual(len(market['items']),
                         sum(len(vendor['items']) for vendor in market['vendors']))
        vendor_ids = {vendor['id'] for vendor in market['vendors']}
        self.assertEqual(len(vendor_ids), 6)
        self.assertTrue(all(item['vendor_id'] in vendor_ids for item in market['items']))
        self.assertTrue(all('mechanics' in item and 'desc' in item for item in market['items']))
        self.assertEqual(market, server.night_market())


if __name__ == '__main__':
    unittest.main()
