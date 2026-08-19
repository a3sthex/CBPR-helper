import copy
import importlib.util
import json
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
        setup = {'moto_choices': ['Roadbike', 'Стекло', 'Тяжёлое шасси', 'Жилой модуль']}
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
                server.validate_creation(valid_character(role))

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
        char['creation']['sold_soul'] = True
        char['cyberware'].append({
            'key': 'cyberware-3', 'name': 'Borgware Hardened Shielding',
            'hl': 14, 'price': 1000, 'type': 'Borgware',
        })
        # The authoritative catalog price is covered by the 1,500eb chrome-only fund.
        char['cash'] = 2550
        server.validate_creation(char)

    def test_explicit_cyberware_foundation_requirement_is_checked(self):
        char = valid_character()
        char['cyberware'].append({
            'key': 'cyberware-22', 'name': 'Ballpoint Cyberfinger',
            'hl': 0, 'price': 100, 'type': 'Cyberfingers',
        })
        char['cash'] = 2450
        with self.assertRaisesRegex(server.ApiError, 'Modular Finger Cyberhand'):
            server.validate_creation(char)


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


if __name__ == '__main__':
    unittest.main()
