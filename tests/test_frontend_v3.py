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
