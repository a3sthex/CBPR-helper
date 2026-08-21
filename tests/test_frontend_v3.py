import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('cbpr_frontend_server', ROOT / 'app/server.py')
server = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server)


@unittest.skipUnless(shutil.which('node'), 'Node.js is required for frontend runtime contracts')
class FrontendV3Contracts(unittest.TestCase):
    def test_dossier_loading_placeholder_is_replaced(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        view_characters = source.split('async function viewCharacters(view) {', 1)[1].split(
            '/* ============================== редактор персонажа', 1)[0]
        self.assertIn('view.innerHTML = spinner();', view_characters)
        self.assertIn("const data = await api('/api/characters');", view_characters)
        self.assertIn('view.innerHTML = `', view_characters)
        self.assertNotIn("view.insertAdjacentHTML('afterbegin'", view_characters)

    def test_trust_editor_supports_custom_and_found_item_provenance(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('id="add-custom-item"', source)
        self.assertIn('function openCatalogAcquisitionModal', source)
        self.assertIn('function openOwnedItemEditor', source)
        self.assertIn('acquisition_source', source)
        self.assertIn('CUSTOM · MANUAL', source)
        self.assertIn("it.cat!=='cyberware'", source)

    def test_character_sheet_has_consumable_and_active_gear_actions(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('Active Gear / Loadout', source)
        self.assertIn('function chooseEquipMode', source)
        self.assertIn('performSheetItemAction', source)
        self.assertIn('data-item-use', source)
        self.assertIn('data-item-equip', source)
        self.assertIn("'deactivate':'activate'", source)

    def test_character_sheet_uses_structured_effect_breakdowns(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('Structured Effects & Synergies', source)
        self.assertIn('derived.effects?.skills?.[name]', source)
        self.assertIn('effective_check_base', source)
        self.assertIn('check_modifier', source)
        self.assertIn('effect-bonus', source)

    def test_catalog_and_sheet_distinguish_automated_and_manual_item_rules(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('AUTOMATED EFFECT', source)
        self.assertIn('MANUAL RULE', source)
        self.assertIn('Curated Item Effects', source)
        self.assertIn('item_sources', source)
        self.assertIn('effect_coverage', source)

    def test_weapon_hosts_have_instance_bound_upgrade_management(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('function openWeaponUpgradeManager', source)
        self.assertIn('data-manage-upgrades', source)
        self.assertIn('host_instance_id', source)
        self.assertIn('upgrade_instance_id', source)
        self.assertIn('manual_confirm', source)
        self.assertIn('/modifications', source)
        self.assertIn('effective_weapons', source)
        self.assertIn('attack_modifier', source)
        self.assertIn('Mag ${magBase}→${magEffective}', source)
        self.assertIn('requirements_met', source)
        self.assertIn('slot_pools', source)
        self.assertIn('MANUAL COMPATIBILITY CHECK REQUIRED', source)
        self.assertIn('alternate_attacks', source)
        self.assertIn('data-mod-weapon-action', source)
        self.assertIn('alternate-weapon-profile', source)
        self.assertIn('configuration_schemas', source)
        self.assertIn('data-upgrade-config', source)
        self.assertIn('autofire_profiles', source)
        self.assertIn('Autofire Check', source)
        self.assertIn('configuration_by_host', source)
        self.assertIn('Range ${esc(rangeBase)}→${esc(rangeEffective)}', source)
        self.assertIn('weaponEffective.tags', source)
        self.assertIn('effect-manual-text', source)

    def test_character_sheet_has_vehicle_garage_and_access_aware_upgrades(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('Vehicle Garage', source)
        self.assertIn('function openVehicleUpgradeManager', source)
        self.assertIn('vehicle_hosts', source)
        self.assertIn('vehicle_upgrades', source)
        self.assertIn('nomad_access_met', source)
        self.assertIn('data-manage-vehicle', source)
        self.assertIn('effective_vehicles', source)
        self.assertIn('Body SP', source)
        self.assertIn('HP/window', source)
        self.assertIn('data-vehicle-sdp', source)
        self.assertIn('vehicleGarageActionsHtml', source)
        self.assertIn('data-vehicle-mod-action', source)
        self.assertIn('Use NOS', source)
        self.assertIn('mounted_weapons', source)
        self.assertIn('data-vehicle-config', source)
        self.assertIn('weapon_mounts', source)
        self.assertIn('data-heavy-mount-select', source)
        self.assertIn('mount_weapon', source)
        self.assertIn('Interior, Rooms & Cargo', source)
        self.assertIn('complex_purposes', source)
        self.assertIn('Vehicle Repair Workflow', source)
        self.assertIn('data-vehicle-repair', source)
        self.assertIn('chooseAmmoStack', source)
        self.assertIn('ammo_rounds', source)
        self.assertIn('shared_ammo_available', source)

    def test_character_sheet_has_cyberdeck_host_loadout_management(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('Cyberdeck Loadout', source)
        self.assertIn('function openCyberdeckManager', source)
        self.assertIn('cyberdeck_hosts', source)
        self.assertIn('cyberdeck_items', source)
        self.assertIn('effective_cyberdecks', source)
        self.assertIn('data-manage-cyberdeck', source)
        self.assertIn('data-install-deck-item', source)
        self.assertIn('data-remove-deck-item', source)
        self.assertIn('PROGRAM EFFECTS AND BLACK ICE ATTACKS ARE MANUAL', source)
        self.assertIn('data-program-action', source)
        self.assertIn('data-backup-restore', source)
        self.assertIn('REZ damage', source)
        self.assertIn('data-black-ice-deploy', source)
        self.assertIn('data-net-entity-action', source)
        self.assertIn('blackIceRuntimeHtml', source)
        self.assertIn('Deploy in Combat', source)

    def test_consumable_use_distinguishes_automated_preset_and_manual_rules(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('created_effects', source)
        self.assertIn('manual_rules', source)
        self.assertIn('Use Resolution', source)
        self.assertIn('Full item description', source)

    def test_character_sheet_manages_temporary_custom_effects(self):
        source = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        self.assertIn('function openCustomEffectModal', source)
        self.assertIn('Active Effect Instances', source)
        self.assertIn('data-effect-action', source)
        self.assertIn('Advance 1 round', source)
        self.assertIn('duration_type', source)
        self.assertIn('/effects', source)

    def test_wizard_v3_runtime_contract(self):
        meta = {
            'stats': server.STATS,
            'roles': server.ROLES,
            'role_ru': server.ROLE_RU,
            'role_desc': server.ROLE_DESC,
            'role_desc_en': server.ROLE_DESC_EN,
            'skills': server.SKILLS,
            'must_skills': server.MUST_SKILLS,
            'stat_points': server.STAT_POINTS,
            'skill_points': server.SKILL_POINTS,
            'skill_max': server.SKILL_MAX_CREATION,
            'cats': [],
        }
        stub = r"""
global.__store = new Map();
global.document = {
  querySelector: () => null, querySelectorAll: () => [], addEventListener: () => {},
  documentElement: { style: { setProperty() {} }, classList: { toggle() {} } }, createElement: () => ({ click() {} }),
};
global.window = {
  addEventListener: () => {}, dispatchEvent: () => {}, scrollTo: () => {},
  confirm: () => true, print: () => {}, prompt: () => '1',
};
global.CustomEvent = function () {};
global.location = { hash: '' };
global.localStorage = {
  getItem: key => __store.get(key) || null,
  setItem: (key, value) => __store.set(key, value),
  removeItem: key => __store.delete(key),
};
global.history = { replaceState: () => {} };
global.fetch = async () => { throw new Error('fetch not expected'); };
global.URL = { createObjectURL: () => '', revokeObjectURL: () => {} };
global.Blob = function () {};
"""
        app = (ROOT / 'app/static/app.js').read_text(encoding='utf-8')
        app = app.split('/* ============================== запуск ============================== */')[0]
        test = f"""
state.meta = {json.dumps(meta, ensure_ascii=False)};
state.me = {{ id: 9, display_name: 'Player' }};
if (APP_I18N.current() !== 'en') throw new Error('English must be the default locale');
if (APP_I18N.translate('Профиль') !== 'Profile') throw new Error('known UI literal was not translated');
initWizard();
if (WIZARD_STEPS.length !== 6) throw new Error('expected six wizard steps');
if (MERGED_LIFEPATH_FIELDS.find(field => field.key === 'region').options.length !== 10) throw new Error('expected ten canonical cultural regions');
if (state.wizard.role !== '') throw new Error('new draft must not preselect a Role');
if (state.wizard.public !== false) throw new Error('new character must default to Private');
if (wizStatSpent() !== 50 || wizSkillSpent() !== 26) throw new Error('invalid defaults');
state.wizard.subSkills.push({{ base: 'Language', name: 'Russian', lvl: 5, native: true, free: true }});
if (wizSubAllocated('Language') !== 3) throw new Error('Cultural Language levels above 4 must consume parent-pool');
state.wizard.subSkills.pop();
if (!wizStepRoleHtml().includes('Choose a Role')) throw new Error('missing empty Role state');
if (!wizStepLifepathHtml().includes('creation-section')) throw new Error('Lifepath is not collapsible');
if (!wizStepStatsHtml().includes('data-stat-lock')) throw new Error('STAT locks missing');
if (!wizStepSkillsHtml().includes('data-skill-filter')) throw new Error('Skill filters missing');
if (!wizStepShoppingHtml().includes('shopping-layout')) throw new Error('Shopping was not merged');
if (!wizStepSummaryHtml().includes('Visibility')) throw new Error('Summary visibility missing');
if (!NC_LOCATIONS.find(location => location.id === 'orbital-air-space-center')) throw new Error('Orbital Air Space Center missing');
if (!ncLocationMatches('watson','watson-kabuki')) throw new Error('parent district filter does not include subdistrict');
if (!ncDistrictName('badlands-near-pacifica').includes('Near Pacifica')) throw new Error('subdistrict label missing');
if (!ncLocationOptions('westbrook-japantown').includes('optgroup')) throw new Error('grouped location options missing');
const hasCyrillic = value => /[А-Яа-яЁё]/.test(String(value));
const englishVisibleText = html => String(html)
  .replace(/<style[\\s\\S]*?<\\/style>/g, '')
  .replace(/<[^>]*>/g, '\\n').split('\\n')
  .map(value => APP_I18N.translate(value)).join(' ')
  .replace(/&[^;]+;/g, ' ').replace(/\\s+/g, ' ').trim();
const englishAttributes = html => [...String(html).matchAll(/(?:placeholder|title|aria-label)="([^"]*)"/g)]
  .map(match => APP_I18N.translate(match[1])).join(' ');
const ncContractHtml = ncContractCard({{
  id: 1, status: 'open', risk_level: 'high', title: 'Relay Run', teaser: 'Test',
  participants: [], district_id: 'watson', reward_mode: 'hidden', scheduled_at: null,
  crew_capacity: 4, crew_count: 1, waitlist_count: 0,
}});
const ncFeedHtml = ncFeedCard({{
  id: 1, format: 'short', author: {{display_name:'V',accent_color:'#00e5ff'}},
  body: 'Signal', created: 1,
}});
for (const html of [ncMapHtml([]), ncContractHtml, ncFeedHtml]) {{
  const visible = englishVisibleText(html) + ' ' + englishAttributes(html);
  if (hasCyrillic(visible)) throw new Error('untranslated English NC//NET surface: ' + visible);
}}
for (const field of MERGED_LIFEPATH_FIELDS) {{
  for (const option of field.options) if (hasCyrillic(displayKnownValue(option.value))) throw new Error('untranslated Common Lifepath option: ' + option.value);
}}
for (const [,, options] of [...CORE_LIFEPATH_FIELDS, ...CEMK_LIFEPATH_FIELDS]) {{
  for (const option of options) if (hasCyrillic(displayKnownValue(option))) throw new Error('untranslated legacy Lifepath option: ' + option);
}}
for (const role of Object.keys(state.meta.roles)) {{
  const abilityDescription = roleAbilityDisplayDescription(role);
  if (!abilityDescription.trim()) throw new Error('missing English Role Ability description: ' + role);
  if (hasCyrillic(abilityDescription)) throw new Error('untranslated English Role Ability description: ' + role);
  state.wizard.role = role;
  state.wizard.roleLifepath = {{}};
  for (const [key,, options] of lpRoleField(role)) state.wizard.roleLifepath[key] = typeof options[0] === 'object' ? options[0].value : options[0];
  for (const [key,, options] of lpFields()) state.wizard.lifepath[key] = typeof options[0] === 'object' ? options[0].value : options[0];
  state.wizard.nativeLanguage = languagesForRegion(state.wizard.lifepath.region)[0];
  for (const render of [wizStepRoleHtml, wizStepLifepathHtml, wizStepStatsHtml, wizStepSkillsHtml, wizStepShoppingHtml, wizStepSummaryHtml]) {{
    const html = render();
    const visible = englishVisibleText(html) + ' ' + englishAttributes(html);
    if (hasCyrillic(visible)) throw new Error(`untranslated English UI in ${{role}}/${{render.name}}: ${{visible.match(/.{{0,50}}[А-Яа-яЁё].{{0,80}}/g)}}`);
  }}
}}
state.wizard.skills.Language = 3;
if (wizSubFree('Language') !== 1) throw new Error('parent-pool free level incorrect');
saveWizardDraft(); state.wizard = null;
if (!loadWizardDraft() || state.wizard.skills.Language !== 3) throw new Error('v3 draft restore failed');
console.log('ok');
"""
        script = '\n'.join([
            stub,
            (ROOT / 'app/static/i18n.js').read_text(encoding='utf-8'),
            (ROOT / 'app/static/theme.js').read_text(encoding='utf-8'),
            (ROOT / 'app/static/creation-data.js').read_text(encoding='utf-8'),
            (ROOT / 'app/static/ncnet.js').read_text(encoding='utf-8'),
            app,
            test,
        ])
        with tempfile.NamedTemporaryFile('w', suffix='.js', encoding='utf-8') as handle:
            handle.write(script)
            handle.flush()
            result = subprocess.run(['node', handle.name], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('ok', result.stdout)


if __name__ == '__main__':
    unittest.main()
