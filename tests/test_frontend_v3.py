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
