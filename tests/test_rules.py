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
        self.assertEqual(data['schema_version'], 5)


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
        result = server.derive({'armor': {
            'body_outer': {'sp': 11, 'penalties': {'REF': 0, 'DEX': 0, 'MOVE': 0}},
            'body_inner': {'sp': 7, 'penalties': {'REF': -2, 'DEX': -3, 'MOVE': -4}},
            'head': {'sp': 13, 'penalties': {'REF': -3, 'DEX': -2, 'MOVE': -2}},
        }})
        self.assertEqual(result['sp_body'], 11)
        self.assertEqual(result['sp_head'], 13)
        self.assertEqual(result['armor_penalties'], {'REF': -3, 'DEX': -3, 'MOVE': -4})


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
