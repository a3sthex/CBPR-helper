// Shared render helpers + character creation wizard (7 шагов).
// P3-frontend, срез S4: вынесено из app.js целиком (1 702 строки) — внутри блока
// перемешаны общие render-хелперы (используются views-dossiers.js / views-editor.js)
// и сам мастер создания; разделение на views-shared.js + views-wizard.js — срез S5.
// Порядок загрузки в index.html: views-shared.js → … → app.js.

/* ============================== мастер создания персонажа (7 шагов) ============================== */

const WIZARD_STEPS = [
  ['role', '🎭 Role', '🎭 Роль', 'Choose a Role and configure its Rank 4 benefits.', 'Выберите роль и настройте преимущества Rank 4.'],
  ['lifepath', '🧬 Lifepath', '🧬 Lifepath', 'Build identity, origin, values, and Role-Based Lifepath.', 'Создайте личность, происхождение, ценности и Role-Based Lifepath.'],
  ['stats', '📊 Characteristics', '📊 Характеристики', 'Allocate exactly 62 points; each STAT ranges from 2 to 8.', 'Распределите ровно 62 очка; каждая характеристика от 2 до 8.'],
  ['skills', '🎯 Skills', '🎯 Навыки', 'Allocate 86 points across Corebook Skills and specializations.', 'Распределите 86 очков между навыками и специализациями Corebook.'],
  ['shopping', '🛒 Shopping', '🛒 Закупка', 'Build the complete starting loadout, Fashion, and Cyberware.', 'Соберите стартовое снаряжение, Fashion и Cyberware.'],
  ['summary', '✅ Summary', '✅ Итог', 'Resolve blocking issues and preview the final Character Sheet.', 'Исправьте ошибки и проверьте готовый Character Sheet.'],
];

function wizardStepLabel(step) { return T(step[1], step[2]); }
function wizardStepDescription(step) { return T(step[3], step[4]); }

/* ---------- подробные описания ролевых способностей ---------- */

const ROLE_ABILITIES = {
  Solo: {
    name: 'Combat Awareness (Боевое чутьё)',
    desc: 'При начале боя, вне боя или Действием в бою Соло распределяет очки Combat Awareness: Threat Detection даёт +1 к Perception за очко; Initiative Reaction — +1 к броску инициативы; Precision Attack — +1 к атакам за 3 очка; Spot Weakness — +1 к урону первой успешной атаки раунда за очко; Damage Deflection уменьшает первый полученный урон раунда на 1 за 2 очка; Fumble Recovery за 4 очка позволяет игнорировать критический провал атаки.',
  },
  Rockerboy: {
    name: 'Charismatic Impact (Харизматическое воздействие)',
    desc: 'Раз в неделю Рокербой может воздействовать на аудиторию силой своего выступления, слова или образа: убедить фанатов сделать что-то для него — пропустить за сцену, спрятать от погони, выйти на протест или даже устроить бунт. Чем выше ранг роли, тем шире аудитория (от одного преданного фаната до многотысячной толпы) и тем более рискованные просьбы она готова выполнить. Бросок: 1d10 + ранг роли против сложности, зависящей от просьбы.',
  },
  Netrunner: {
    name: 'Interface (Интерфейс)',
    desc: 'Позволяет погружаться в NET-архитектуры через кибердек и «глубокое погружение». Даёт доступ к NET-действиям: Backdoor (взлом паролей), Cloak (скрытие следов), Control (управление устройствами), Eye-Dee (опознание данных), Pathfinder (карта архитектуры), Scanner (поиск), Slide (побег от ICE), Virus и Zap (кибератака). Ранг роли определяет число NET-действий за ход (3 на ранге 4+) и добавляется к броскам Interface. Нетраннер — единственный, кто может сражаться с Чёрным ICE и выживать.',
  },
  Tech: {
    name: 'Maker (Мастер)',
    desc: 'За каждый ранг Maker Tech получает по 1 рангу в двух разных специализациях. На старте это 8 распределений между Field Expertise, Upgrade Expertise, Fabrication Expertise и Invention Expertise, максимум 4 в каждой. Техник чинит, улучшает, изготавливает и изобретает предметы.',
  },
  Medtech: {
    name: 'Medicine (Медицина)',
    desc: 'Каждый ранг Medicine даёт 1 распределение между Surgery, Pharmaceuticals и Cryosystem Operation — 4 на старте. Каждый ранг Surgery даёт +2 к эксклюзивному навыку Surgery; Pharmaceuticals и Cryosystems вместе образуют навык Medical Tech и открывают препараты и криооборудование.',
  },
  Media: {
    name: 'Credibility (Авторитет)',
    desc: 'Способность быть услышанным и добывать правду. Чем выше ранг — тем шире аудитория публикаций (от локального блога до международных новостных сетей) и тем весомее твоё слово: люди верят твоим материалам, источники сами выходят на связь, охрана пропускает на закрытые события. Ранг роли добавляется к броскам на поиск слухов, компромата и скрытых фактов, а публикация разоблачения может уничтожить репутацию банды или корпората.',
  },
  Exec: {
    name: 'Teamwork (Командная работа)',
    desc: 'Корпорация выделяет Корпорату команду и ресурсы. С ростом ранга растёт число и качество сотрудников (телохранитель, ассистент, техник, нетраннер — до целого отдела), а также привилегии: корпоративное жильё, транспорт, оперативный бюджет и «прикрытие» при проблемах с законом. Члены команды выполняют приказы в рамках лояльности корпорации. Взамен корпорация ждёт результатов — и жестоко спрашивает за провалы.',
  },
  Lawman: {
    name: 'Backup (Подкрепление)',
    desc: 'Законник может вызвать подкрепление, находясь при исполнении. Чем выше ранг — тем быстрее прибывает помощь и тем она серьёзнее: от пары патрульных до тяжёлого отряда и спецназа MaxTac. Кроме того, ранг отражает полномочия: доступ к полицейским базам данных, право на обыск и арест, связи в участках. Подкрепление рискует жизнью за тебя — но злоупотребление вызовами подрывает доверие коллег.',
  },
  Fixer: {
    name: 'Operator (Делец)',
    desc: 'Фиксер знает нужных людей — и нужные люди знают Фиксера. Operator позволяет: доставать редкие и нелегальные товары (чем выше ранг, тем дороже и экзотичнее доступный товар), находить покупателей и продавцов, сводить клиентов со специалистами (соло, нетраннеры, риппердоки), узнавать уличные слухи и торговаться о ценах на Ночном рынке. Ранг роли добавляется к броскам Trading и определяет уровень твоих связей в преступном мире.',
  },
  Nomad: {
    name: 'Moto (Мото)',
    desc: 'Каждый ранг Moto добавляет в семейный автопарк доступный транспорт или одно улучшение уже выбранного транспорта. Стартовый Nomad последовательно делает четыре таких выбора для рангов 1–4. Moto также добавляется к проверкам управления и ремонта транспорта; одновременно у Номада обычно находится одна семейная машина.',
  },
};

function roleAbilityDisplayName(role) {
  const ability = ROLE_ABILITIES[role] || {};
  return APP_I18N.current() === 'en' ? (state.meta.roles[role] || ability.name || '') : (ability.name || state.meta.roles[role] || '');
}
function roleAbilityDisplayDescription(role) {
  const ability = ROLE_ABILITIES[role] || {};
  const rules = (typeof ROLE_COREBOOK_V3 !== 'undefined' && ROLE_COREBOOK_V3[role]) || {};
  return APP_I18N.current() === 'en'
    ? ((rules.en && `${rules.en.play} ${rules.en.rank4}`) || '')
    : (ability.desc || '');
}

/* ---------- Lifepath: 13 пунктов (CP:R стр. 43–48) ---------- */

function displayKnownValue(value) { return APP_I18N.current() === 'en' ? (LEGACY_DISPLAY_EN[value] || APP_I18N.translate(value)) : value; }
function lpFields() {
  return MERGED_LIFEPATH_FIELDS.map(field => [field.key, APP_I18N.current() === 'en' ? (LIFEPATH_LABEL_EN[field.key] || field.label) : field.label, field.options]);
}

function lpRoleField(role) {
  return (ROLE_LIFEPATHS[role] || []).map(([key, label, options]) => [key, APP_I18N.current() === 'en' ? (LIFEPATH_LABEL_EN[key] || label) : label, options]);
}

function lpAllFields() {
  return lpFields();
}

function lifepathNarrative(lp, role, roleLp) {
  const out = [];
  const values = Object.assign({}, lp || {});
  if (!values.clothing && values.wardrobe) values.clothing = values.wardrobe;
  if (!values.hair && values.hair_style) values.hair = values.hair_style;
  const shown = new Set();
  for (const [key, label] of lpAllFields()) {
    if (values[key]) { out.push([label, values[key]]); shown.add(key); }
  }
  // Старые персонажи сохраняют социальные поля прежних схем, хотя новый мастер их больше не требует.
  for (const [key, label] of [...CORE_LIFEPATH_FIELDS, ...CEMK_LIFEPATH_FIELDS]) {
    if (lp && lp[key] && !shown.has(key) && !LIFEPATH_KEY_ALIASES[key]) { out.push([APP_I18N.current()==='en' ? (LIFEPATH_LABEL_EN[key] || APP_I18N.translate(label)) : label, lp[key]]); shown.add(key); }
  }
  for (const [key, label] of lpRoleField(role)) {
    if (roleLp && roleLp[key]) out.push([T('Role · ','Роль · ') + label, roleLp[key]]);
  }
  if ((!roleLp || !Object.keys(roleLp).length) && lp && lp.rolebg) out.push([T('Role Background','Ролевая предыстория'), lp.rolebg]);
  return out;
}

function lifepathResultInfo(key, value, sources, roleSpecific) {
  if (!value) return '';
  const common = {
    region: 'Эта культура формирует происхождение персонажа и определяет доступный культурный язык.',
    personality: 'Используй это как обычную реакцию персонажа, особенно при первой встрече или под давлением.',
    clothing: 'Это ведущая эстетика образа; отдельные вещи могут относиться и к другим стилям.',
    hair: 'Это узнаваемая часть силуэта персонажа, которую можно адаптировать под хром.',
    hair_color: 'Цвет и украшения дополняют причёску и делают образ заметным в Ночном городе.',
    affectation: 'Эта деталь помогает другим узнавать персонажа и может стать частью его репутации.',
    value: 'Потеря или угроза этой ценности — сильный личный конфликт для персонажа.',
    people: 'Это его исходная установка к незнакомцам, а не окончательное мнение о каждом человеке.',
    person: 'Этот человек или группа остаются эмоционально значимыми и могут стать связью или уязвимостью.',
    possession: 'Важность вещи эмоциональная: она связывает персонажа с прошлым, обещанием или утратой.',
    family: 'Происхождение объясняет привычки, связи и ресурсы семьи до начала самостоятельной жизни.',
    environment: 'Эта среда дала персонажу ранние навыки, страхи и представление о нормальной жизни.',
    crisis: 'Кризис объясняет разрыв с прежней стабильностью и один из мотивов выйти на Улицу.',
    goal: 'Цель задаёт долгосрочное направление и повод принимать опасные заказы.',
  };
  const isEn = APP_I18N.current() === 'en';
  const sourceText = sources && sources.length ? (isEn ? ` Source: ${sources.join(' + ')}.` : ` Источник: ${sources.join(' + ')}.`) : '';
  const prefix = isEn
    ? (roleSpecific ? 'This result refines the Role’s professional experience and connections.' : (LIFEPATH_QUESTION_EN[key] || 'This result establishes a specific part of the character’s history.'))
    : (roleSpecific ? 'Этот результат уточняет профессиональный опыт и связи выбранной роли.' : (common[key] || 'Этот результат задаёт конкретную деталь предыстории персонажа.'));
  return `<div class="lp-result-info"><b>${esc(displayKnownValue(value))}</b><br>${esc(prefix)}${esc(sourceText)}</div>`;
}

/* ---------- суб-навыки ---------- */

const SUB_SKILL_BASES = SPECIALIZED_SKILL_BASES;
const WIZ_SUB_HIDDEN = new Set(SUB_SKILL_BASES.map(s => s[0]));

/* ---------- закупка: категории ---------- */

const WIZ_SHOP_CATS = [
  ['weapons', '🔫 Weapons', '🔫 Оружие', ['guns', 'melee', 'gun_upgrades']],
  ['armor', '🛡️ Armor', '🛡️ Броня', ['armor']],
  ['chrome', '🦾 Cyberware', '🦾 Хром', ['cyberware']],
  ['fashion', '🧥 Fashion', '🧥 Одежда', ['fashion']],
  ['fashionware', '💠 Fashionware', '💠 Fashionware', ['cyberware']],
  ['programs', '💾 Programs & NET', '💾 Программы и NET', ['programs', 'net_stuff']],
  ['ammo', '📦 Ammunition', '📦 Боеприпасы', ['ammo', 'grenades']],
  ['vehicles', '🏍️ Vehicles', '🏍️ Транспорт', ['vehicles', 'vehicles_upgrades']],
  ['gear', '🎒 Gear & Services', '🎒 Снаряжение и услуги', ['gear', 'services']],
];
function shopCategoryLabel(tab) { return T(tab[1], tab[2]); }

const GEAR_BUDGET = 2550;
const FASHION_BUDGET = 800;

function byNameRu(a, b) {
  return String(a.name).localeCompare(String(b.name), ['ru', 'en'], { sensitivity: 'base' });
}

/* ===================== мастер: состояние ===================== */

function defaultRoleSetup(role) {
  if (role === 'Tech') return { field: 2, upgrade: 2, fabrication: 2, invention: 2 };
  if (role === 'Medtech') return { surgery: 2, pharma: 1, cryo: 1 };
  if (role === 'Exec') return { team_member: '' };
  if (role === 'Nomad') return { moto_choices: ['', '', '', ''] };
  return {};
}

function creationChromeBonus(wiz) { return wiz.soldSoul ? 1500 : 0; }
function creationMainSpent(wiz) { return wiz.gearCost + Math.max(0, wiz.chromeCost - creationChromeBonus(wiz)); }
function creationMainRemaining(wiz) { return GEAR_BUDGET - creationMainSpent(wiz); }

const WIZARD_DRAFT_VERSION = 3;

function wizardDraftKey(version = WIZARD_DRAFT_VERSION) {
  return state.me ? `cbpr-helper:wizard:${state.me.id}:v${version}` : '';
}

function saveWizardDraft() {
  const key = wizardDraftKey();
  if (!key || !state.wizard || state.wizard.created) return;
  try {
    state.wizard.lastSaved = Date.now();
    const clean = JSON.parse(JSON.stringify(state.wizard, (k, v) => k.startsWith('_') ? undefined : v));
    localStorage.setItem(key, JSON.stringify({ version: WIZARD_DRAFT_VERSION, saved_at: state.wizard.lastSaved, wizard: clean }));
  } catch (e) { /* приватный режим или переполненное хранилище */ }
}

function clearWizardDraft() {
  const key = wizardDraftKey();
  if (!key) return;
  try { localStorage.removeItem(key); } catch (e) { /* localStorage недоступен */ }
}

function normalizeWizard(w) {
  const stats = {};
  (state.meta ? state.meta.stats : ['INT','REF','DEX','TECH','COOL','WILL','LUCK','MOVE','BODY','EMP'])
    .forEach(key => stats[key] = Math.max(2, Math.min(8, num(w && w.stats && w.stats[key]) || 5)));
  const role = (w && state.meta.roles[w.role]) ? w.role : '';
  const lp = Object.assign({}, (w && w.lifepath) || {});
  if (!lp.clothing && lp.wardrobe) lp.clothing = lp.wardrobe;
  if (!lp.hair && lp.hair_style) lp.hair = lp.hair_style;
  const skills = Object.assign({}, (w && w.skills) || {});
  const subSkills = Array.isArray(w && w.subSkills) ? w.subSkills.map(x => ({
    base: x.base, name: String(x.name || ''), lvl: Math.max(0, Math.min(6, num(x.lvl) || 0)), native: !!x.native,
  })) : [];
  if (!subSkills.some(x => x.base === 'Language' && x.name === 'Streetslang')) subSkills.unshift({ base: 'Language', name: 'Streetslang', lvl: 2 });
  const legacyHome = subSkills.find(x => x.base === 'Local Expert' && x.name === 'Свой район');
  if (legacyHome) legacyHome.name = 'Your Home';
  if (!subSkills.some(x => x.base === 'Local Expert')) subSkills.push({ base: 'Local Expert', name: 'Your Home', lvl: 2 });
  for (const [base] of SUB_SKILL_BASES) {
    if (skills[base] == null) skills[base] = subSkills.filter(x => x.base === base && !x.native).reduce((a, x) => a + x.lvl, 0);
  }
  const out = Object.assign({
    step: 1, role, handle: '', firstName: '', lastName: '', portraitMedia: null, stats, skills, subSkills,
    nativeLanguage: '', cyberware: [], fashionware: [], gear: [], fashion: [],
    armor: { body: null, head: null, shield: null }, chromeCost: 0, gearCost: 0, fashionCost: 0,
    fashionBurned: false, soldSoul: false, freeNeuroport: true,
    lifepath: lp, lifepathIds: {}, roleLifepath: {}, roleSetup: defaultRoleSetup(role), roleBenefits: [],
    shopTab: 'weapons', shopQ: '', shopFilters: {}, shopState: {}, styleQ: '', shopType: 'all', styleType: 'all',
    scrolls: {}, statLocks: {}, lifepathOpen: { identity: true, origin: true },
    skillOpen: {}, skillFilter: 'all', skillQ: '', compareItems: [],
    patron: '', obligation: '', public: false,
    player: state.me ? (state.me.display_name || '') : '', created: false,
  }, w || {});
  out.ownerId = state.me ? state.me.id : null;
  out.role = role;
  out.stats = stats;
  out.skills = skills;
  out.subSkills = subSkills;
  out.lifepath = lp;
  out.lifepathIds = Object.assign({}, (w && w.lifepathIds) || {});
  for (const field of MERGED_LIFEPATH_FIELDS) { const value=canonicalLifepathValue(field.key,lp[field.key]); if(value){lp[field.key]=value;const option=field.options.find(item=>item.value===value||(item.aliases||[]).includes(lp[field.key]));if(option)out.lifepathIds[field.key]=option.id;} }
  out.roleSetup = Object.assign(defaultRoleSetup(role), (w && w.roleSetup) || {});
  out.roleLifepath = Object.assign({}, (w && w.roleLifepath) || {});
  out.armor = Object.assign({ body: null, head: null, shield: null }, (w && w.armor) || {});
  out.scrolls = Object.assign({}, (w && w.scrolls) || {});
  out.step = Math.max(1, Math.min(6, num(out.step) || 1));
  out.firstName = String(out.firstName || '');
  out.lastName = String(out.lastName || '');
  out.lifepathMode = 'merged';
  delete out.created;
  // обязательные минимумы для обычных навыков сохраняются только при новом/пустом draft.
  for (const skill of (state.meta.must_skills || [])) {
    if (!WIZ_SUB_HIDDEN.has(skill) && out.skills[skill] == null) out.skills[skill] = 2;
  }
  return out;
}

function loadWizardDraft() {
  if (!state.me) return false;
  try {
    let raw = JSON.parse(localStorage.getItem(wizardDraftKey()) || 'null');
    if (!raw) {
      raw = JSON.parse(localStorage.getItem(wizardDraftKey(2)) || 'null');
      if (raw && raw.wizard) {
        const oldStep = num(raw.wizard.step) || 1;
        raw.wizard.step = oldStep <= 4 ? oldStep : (oldStep <= 6 ? 5 : 6);
      }
    }
    if (!raw || ![2, 3].includes(raw.version) || !raw.wizard) return false;
    state.wizard = normalizeWizard(raw.wizard);
    saveWizardDraft();
    if (raw.version === 2) localStorage.removeItem(wizardDraftKey(2));
    return true;
  } catch (e) { return false; }
}

function initWizard() {
  const stats = {};
  (state.meta ? state.meta.stats : ['INT','REF','DEX','TECH','COOL','WILL','LUCK','MOVE','BODY','EMP']).forEach(s => stats[s] = 5);
  state.wizard = normalizeWizard({
    step: 1,
    role: '',
    handle: '', firstName: '', lastName: '', portraitMedia: null,
    stats,
    skills: {},
    subSkills: [
      { base: 'Language', name: 'Streetslang', lvl: 2 },
      { base: 'Local Expert', name: 'Your Home', lvl: 2 },
    ],
    nativeLanguage: '',
    cyberware: [],
    fashionware: [],
    gear: [], fashion: [], armor: { body: null, head: null, shield: null },
    chromeCost: 0, gearCost: 0, fashionCost: 0,
    fashionBurned: false, soldSoul: false, freeNeuroport: true,
    lifepathMode: 'merged', lifepath: {}, lifepathIds: {}, roleLifepath: {},
    roleSetup: defaultRoleSetup(''), roleBenefits: [],
    shopTab: 'weapons', shopQ: '', shopFilters: {}, shopState: {}, styleQ: '', shopType: 'all', styleType: 'all',
    scrolls: {}, statLocks: {}, lifepathOpen: { identity: true, origin: true },
    skillOpen: {}, skillFilter: 'all', skillQ: '', compareItems: [],
    patron: '', obligation: '', public: false, player: state.me ? (state.me.display_name || '') : '',
  });
}

function wizChar() {
  const w = state.wizard;
  const lp = Object.fromEntries(Object.entries(w.lifepath || {}).filter(([key]) => !LIFEPATH_REMOVED_KEYS.has(key)));
  const skills = Object.fromEntries(Object.entries(w.skills || {}).filter(([name]) => !WIZ_SUB_HIDDEN.has(name)));
  for (const sub of w.subSkills) {
    if (!sub.name || !(sub.lvl > 0)) continue;
    skills[`${sub.base} (${sub.name})`] = sub.lvl;
  }
  const skillPools = Object.fromEntries(SUB_SKILL_BASES.map(([base]) => [base, num(w.skills[base]) || 0]));
  const langs = w.subSkills.filter(sub => sub.base === 'Language' && sub.name && sub.lvl > 0)
    .map(sub => `${sub.name} (${sub.lvl})`).join(', ');
  const lpText = lifepathNarrative(lp, w.role, w.roleLifepath)
    .map(([k, v]) => `${k}: ${v}`).join('\n');
  const purchasedChrome = [...w.cyberware, ...w.fashionware.flatMap(c => Array.from({ length: c.qty || 1 }, () => c))].map(c => ({
    key: c.id, name: c.name, hl: c.hl || 0, price: c.price, type: c.type || '',
    desc: c.desc || '', source: c.source || '', fields: c.fields || {},
    mechanics: c.mechanics || {}, requirements: c.requirements || [], capacity: c.capacity || {},
    instance_id: c.instance_id || c.id, installation_side: c.installation_side || '', host_instance: c.host_instance || '', host_instances: c.host_instances || (c.host_instance ? [c.host_instance] : []),
  }));
  const hasPaidNeuroport = purchasedChrome.some(c => String(c.name).toLowerCase() === 'neuroport');
  const cyberware = w.freeNeuroport && !hasPaidNeuroport
    ? [{ key: 'creation-neuroport', instance_id: 'creation-neuroport', name: 'Neuroport', hl: 0, price: 0,
         type: 'Neuralware', desc: 'CEMK Starting Neuroport.', capacity: { slots_total: 5 },
         humanity_exempt: true, creation_free: true }, ...purchasedChrome]
    : purchasedChrome;
  return {
    handle: w.handle || 'Unnamed-07',
    first_name: w.firstName || '', last_name: w.lastName || '',
    portrait_media_id: w.portraitMedia ? w.portraitMedia.id : '',
    role: w.role, role_rank: 4, role_setup: Object.assign({}, w.roleSetup),
    stats: Object.assign({}, w.stats),
    hp_cur: null, humanity_cur: null, luck_cur: w.stats.LUCK,
    skills, skill_pools: skillPools,
    skill_specializations: w.subSkills.map(sub => ({ base: sub.base, name: sub.name, lvl: sub.lvl || 0, native: !!sub.native })),
    native_language: w.nativeLanguage,
    cyberware,
    inventory: [...w.gear.map(i => ({ ...i })), ...w.fashion.map(i => ({ ...i })), ...roleBenefitItems(w).map(i => ({ ...i, role_benefit: true, price: 0 }))],
    armor: { body: w.armor.body ? { ...w.armor.body } : null, head: w.armor.head ? { ...w.armor.head } : null, shield: w.armor.shield ? { ...w.armor.shield } : null },
    cash: Math.max(0, creationMainRemaining(w)),
    appearance: [lp.clothing, lp.hair, lp.hair_color, lp.affectation].filter(Boolean).join(' · '),
    background: lpText,
    lifepath_mode: 'merged',
    lifepath: lp, lifepath_ids: Object.assign({}, w.lifepathIds || {}), role_lifepath: Object.assign({}, w.roleLifepath),
    creation: { sold_soul: !!w.soldSoul, free_neuroport: !!w.freeNeuroport,
      patron: w.patron || '', obligation: w.obligation || '',
      gear_spent: w.gearCost, chrome_spent: w.chromeCost, fashion_spent: w.fashionCost },
    lifestyle: 'Kibble (100eb)',
    housing: w.role === 'Exec' ? 'Corporate Conapt (Teamwork)' : 'Studio Apartment (Rent, VEX)',
    notes: '', languages: langs, player: w.player || '',
    public: !!w.public,
  };
}

function wizDerived() {
  return derive(wizChar());
}

async function viewWizard() {
  if (!state.me) {
    $('#view').innerHTML = `<div class="empty">Нужен вход. <a href="#/login">${T('Sign in','Войти')}</a></div>`;
    return;
  }
  if (!state.wizard || state.wizard.created || state.wizard.ownerId !== state.me.id) {
    if (!loadWizardDraft()) initWizard();
  }
  renderWizard();
}

function wizLiveHtml() {
  const wiz=state.wizard,d=wizDerived(),gear=creationMainRemaining(wiz),style=FASHION_BUDGET-wiz.fashionCost;
  return `<div class="derived"><span class="dstat"><span class="v">${d.hp_max||'—'}</span><span class="k">Max HP</span></span><span class="dstat"><span class="v">${d.humanity_max!=null?d.humanity_cur+'/'+d.humanity_max:'—'}</span><span class="k">Humanity</span></span><span class="dstat ${d.emp_cur!=null&&d.emp_cur<=2?'warn':''}"><span class="v">${d.emp_cur??'—'}</span><span class="k">Current EMP</span></span><span class="dstat"><span class="v">${money(gear)}</span><span class="k">${T('Main Budget','Основной бюджет')}</span></span><span class="dstat"><span class="v">${money(style)}</span><span class="k">Style Budget</span></span></div>`;
}

function captureWizardScrolls() {
  if (!state.wizard) return;
  state.wizard.scrolls = state.wizard.scrolls || {};
  const style = $('#wiz-style-clothes');
  const chrome = $('#wiz-style-fw');
  const shop = $('#wiz-shop-results');
  if (style) state.wizard.scrolls.style = style.scrollTop;
  if (chrome) state.wizard.scrolls.fashionware = chrome.scrollTop;
  if (shop) state.wizard.scrolls[`shop:${state.wizard.shopTab}`] = shop.scrollTop;
}

function renderWizard() {
  captureWizardScrolls();
  const wiz = state.wizard;
  const view = $('#view');
  const stepEmojis = ['🎭', '🧬', '📊', '🎯', '🛒', '✅'];

  view.innerHTML = `
  <div class="wizard-wrap">
    <div class="page-head">
      <div><h1>🧬 ${T('Character Creation','Создание персонажа')}</h1><div class="sub">${T('Complete Package · Cyberpunk RED','Complete Package · Cyberpunk RED')} · <span class="draft-status">${T('Draft saved automatically','Draft сохраняется автоматически')}${wiz.lastSaved ? ' · ' + new Date(wiz.lastSaved).toLocaleTimeString(APP_I18N.current()==='ru'?'ru-RU':'en-US',{hour:'2-digit',minute:'2-digit'}) : ''}</span></div></div><button onclick="location.hash='#/characters'">← ${T('Characters','Персонажи')}</button>
    </div>
    <div class="wizard-nav">
      ${WIZARD_STEPS.map((s, i) => `
        <button class="wiz-step ${i + 1 === wiz.step ? 'active' : ''} ${i + 1 < wiz.step ? 'done' : ''}"
                onclick="wizGoTo(${i + 1})">
          <span class="wiz-num">${stepEmojis[i]}</span>
          <span class="wiz-label">${wizardStepLabel(s)}</span>
        </button>`).join('')}
    </div>

    <details class="wiz-live panel" id="wiz-live-panel" ${wiz.liveOpen!==false?'open':''}><summary>${T('Character Snapshot','Сводка персонажа')}</summary><div id="wiz-live">${wizLiveHtml()}</div></details>

    <div class="wiz-body" id="wiz-body">
      ${renderWizStep()}
    </div>

    <div class="wiz-footer">
      <div class="row" style="justify-content:space-between">
        <div>
          <button class="btn-sm" id="wiz-restart">⟳ ${T('Reset draft','Начать заново')}</button>
        </div>
        <div class="row">
          ${wiz.step > 1 ? `<button id="wiz-prev" class="btn-sm">← ${T('Back','Назад')}</button>` : ''}
          ${wiz.step < 6 ? `<button id="wiz-next" class="btn-primary">${T('Next','Далее')} →</button>` : `<button class="btn-primary" id="wiz-create">🧬 ${T('Create Character','Создать персонажа')}</button>`}
        </div>
      </div>
    </div>
  </div>`;

  const nxt = $('#wiz-next');
  if (nxt) nxt.onclick = wizNext;
  const prv = $('#wiz-prev');
  if (prv) prv.onclick = wizPrev;
  const crt = $('#wiz-create');
  if (crt) { const blocking = wizValidationErrors(); crt.disabled = blocking.length > 0; crt.title = blocking[0] || ''; crt.onclick = wizCreate; }
  $('#wiz-restart').onclick = wizReset;
  const livePanel=$('#wiz-live-panel');if(livePanel)livePanel.ontoggle=()=>{wiz.liveOpen=livePanel.open;saveWizardDraft();};
  bindWizStep();
  saveWizardDraft();
}

function renderWizStep() {
  const wiz = state.wizard;
  const s = WIZARD_STEPS[wiz.step - 1];
  let html = `<div class="wiz-step-header"><h2>${wizardStepLabel(s)}</h2><div class="muted small">${wizardStepDescription(s)}</div></div>`;
  html += `<div class="wiz-content">${wizStepContent(wiz.step)}</div>`;
  return html;
}

function wizStepContent(step) {
  switch (step) {
    case 1: return wizStepRoleHtml();
    case 2: return wizStepLifepathHtml();
    case 3: return wizStepStatsHtml();
    case 4: return wizStepSkillsHtml();
    case 5: return wizStepShoppingHtml();
    case 6: return wizStepSummaryHtml();
    default: return '';
  }
}

/* ---------- Шаг 1: Роль ---------- */

function roleSetupSummary(role, setup) {
  setup = setup || {};
  if (role === 'Tech') return `Field ${setup.field || 0} · Upgrade ${setup.upgrade || 0} · Fabrication ${setup.fabrication || 0} · Invention ${setup.invention || 0}`;
  if (role === 'Medtech') return `Surgery ${setup.surgery || 0} · Pharmaceuticals ${setup.pharma || 0} · Cryosystems ${setup.cryo || 0}`;
  if (role === 'Exec') return setup.team_member ? `Сотрудник: ${setup.team_member}` : '';
  if (role === 'Nomad') return Array.isArray(setup.moto_choices) ? `Moto: ${setup.moto_choices.filter(Boolean).join(' → ')}` : '';
  return '';
}

function wizardRoleOrder() { return Object.keys(state.meta.roles || {}); }

const EXEC_TEAM_MEMBERS = [
  ['Bodyguard', 'Телохранитель'], ['Driver', 'Водитель'], ['Personal Assistant', 'Личный помощник'],
  ['Technician', 'Техник'], ['Netrunner', 'Нетраннер'], ['Covert Operative', 'Скрытый оперативник'],
];
const NOMAD_MOTO_CHOICES = [
  ['Roadbike',1], ['Compact Groundcar',1], ['Jetski',1], ['Gyrocopter',1],
  ['Tanson Bellhop',1], ['AmeriCar EconoCompact',1], ['The Harvey 100',1], ['Makigai Ebi',1],
  ['Zonda Molly 1K',1], ['Zonda Metrocar',1], ['Zonda R400 Trail',1],
  ['SH-45 Patroller',2], ['AmeriCar Family Star Van',2], ['The Harriet 100',2], ["Yang’s Wheels Rickshaw",2],
  ['SH-45 Patroller Law',4], ['Diego Motors Chupacabra',4], ['Diego Motors Range Trike',4], ['The Grundy',4],
  ['The Harvey Merc',4], ['Militech Gorgon Security Van',4], ['Zacatzontli Pickup Truck',4], ['Zonda Sliver',4],
  ['Militech F-152 Autocopter',4], ['Hydrosubsidium Bimac',4],
  ['Bulletproof Glass',1], ['Communications Center',1], ['NOS',1], ['Onboard Flamethrower',1],
  ['Onboard Machinegun',1], ['Seating Upgrade',1], ['Smuggling Upgrade',1], ['Heavy Chassis',1],
  ['Onboard Melee Weapon',1], ['Combat Plow',1], ['Deployable Spike Strip',1], ['Housing Capacity',1],
  ['Reinforced Hull/Tires',1], ['Sealed Environment',1],
];

function roleStepper(key, label, value, max) {
  return `<div class="allocation-card"><b>${esc(label)}</b><span class="qty-control"><button class="mini-step" data-role-step="${key}|-1" ${value <= 0 ? 'disabled' : ''}>−</button><strong>${value}</strong><button class="mini-step" data-role-step="${key}|1" ${value >= max ? 'disabled' : ''}>＋</button></span></div>`;
}

function wizRoleSetupHtml() {
  const w = state.wizard, setup = w.roleSetup || {};
  if (w.role === 'Tech') {
    const keys = [['field','Field Expertise'],['upgrade','Upgrade Expertise'],['fabrication','Fabrication Expertise'],['invention','Invention Expertise']];
    const spent = keys.reduce((sum,[key])=>sum+(num(setup[key])||0),0);
    return `<section class="panel accent mt role-setup"><h3>${T('Maker Rank 4 allocation','Распределение Maker Rank 4')}</h3><p class="small muted">${T('Allocate exactly 8 Specialty Points; maximum 4 in one specialty.','Распределите ровно 8 Specialty Points; максимум 4 в одну специализацию.')}</p><div class="allocation-grid">${keys.map(([key,label])=>roleStepper(key,label,num(setup[key])||0,4)).join('')}</div><b class="${spent===8?'green':'warn-text'}">${T('Remaining','Осталось')}: ${8-spent}</b></section>`;
  }
  if (w.role === 'Medtech') {
    const keys = [['surgery','Surgery'],['pharma','Pharmaceuticals'],['cryo','Cryosystem Operation']];
    const spent = keys.reduce((sum,[key])=>sum+(num(setup[key])||0),0);
    return `<section class="panel accent mt role-setup"><h3>${T('Medicine Rank 4 allocation','Распределение Medicine Rank 4')}</h3><p class="small muted">${T('Allocate exactly 4 Specialty Points.','Распределите ровно 4 Specialty Points.')}</p><div class="allocation-grid">${keys.map(([key,label])=>roleStepper(key,label,num(setup[key])||0,4)).join('')}</div><b class="${spent===4?'green':'warn-text'}">${T('Remaining','Осталось')}: ${4-spent}</b></section>`;
  }
  if (w.role === 'Exec') return `<section class="panel accent mt role-setup"><h3>${T('Teamwork Rank 4 Team Member','Team Member для Teamwork Rank 4')}</h3><div class="choice-card-grid">${EXEC_TEAM_MEMBERS.map(([en,ru])=>`<button class="choice-card ${setup.team_member===en?'selected':''}" data-team-member="${esc(en)}"><b>${esc(T(en,ru))}</b><span>${T('Corporate team specialist','Специалист корпоративной команды')}</span></button>`).join('')}</div><p class="small muted">${T('Corporate housing and applicable starting benefits are added to the Character Sheet automatically.','Корпоративное жильё и стартовые преимущества добавляются в лист автоматически.')}</p></section>`;
  if (w.role === 'Nomad') return `<section class="panel accent mt role-setup"><h3>${T('Moto Rank 4 choices','Выборы Moto Rank 4')}</h3><p class="small muted">${T('Make four sequential vehicle or upgrade choices from the Corebook access list.','Сделайте четыре последовательных выбора транспорта или улучшений из списка Corebook.')}</p><div class="grid cols-2">${[0,1,2,3].map(i=>`<label class="f"><span>Rank ${i+1}</span><select data-moto-choice="${i}"><option value="">${T('Choose…','Выберите…')}</option>${NOMAD_MOTO_CHOICES.filter(([,access])=>access<=i+1).map(([value,access])=>`<option value="${esc(value)}" ${(setup.moto_choices||[])[i]===value?'selected':''}>${esc(value)} · Access ${access}</option>`).join('')}</select></label>`).join('')}</div></section>`;
  return `<div class="panel mt small muted">${T('This Role has no permanent Rank 4 allocation during character creation.','У этой роли нет постоянного распределения Rank 4 при создании персонажа.')}</div>`;
}

function wizStepRoleHtml() {
  const wiz = state.wizard;
  const roles = wizardRoleOrder();
  if (!wiz.role) return `<div class="role-tabs mb" role="tablist">${roles.map(role=>`<button role="tab" data-role="${role}">${esc(role)}${APP_I18N.current()==='ru'?' · '+esc(state.meta.role_ru[role]||''):''}</button>`).join('')}</div><div class="empty role-empty"><div class="big-icon">🎭</div><h2>${T('Choose a Role','Выберите роль')}</h2><p>${T('No Role is selected by default. Choose deliberately to open its Corebook description and Rank 4 setup.','Роль по умолчанию не выбрана. Выберите её осознанно, чтобы открыть описание Corebook и настройку Rank 4.')}</p></div>`;
  const source = ROLE_COREBOOK_V3[wiz.role];
  const localized = source[APP_I18N.current()];
  const ability = ROLE_ABILITIES[wiz.role] || {name:state.meta.roles[wiz.role],desc:''};
  return `<div class="role-tabs mb" role="tablist">${roles.map(role=>`<button role="tab" aria-selected="${wiz.role===role}" data-role="${role}" class="${wiz.role===role?'active':''}">${esc(role)}${APP_I18N.current()==='ru'?' · '+esc(state.meta.role_ru[role]||''):''}</button>`).join('')}</div>
    <div class="role-carousel" id="role-carousel" tabindex="0"><button class="role-arrow" data-role-shift="-1" aria-label="${T('Previous Role','Предыдущая роль')}">‹</button>
      <article class="role-card selected role-focus role-v3">
        <div class="role-index">${roles.indexOf(wiz.role)+1} / ${roles.length}</div>
        <div class="role-art"><img src="/role-art/${wiz.role.toLowerCase()}.webp" alt="" onerror="this.hidden=true"><span>${source.icon}</span></div>
        <div><h2>${esc(wiz.role)}${APP_I18N.current()==='ru'?` <span class="chip role">${esc(state.meta.role_ru[wiz.role]||'')}</span>`:''}</h2><span class="tag source">${esc(source.pages)}</span>
        <section><h3>${T('Who you are','Кто вы')}</h3><p>${esc(localized.identity)}</p></section>
        <section><h3>${T('How the Role plays','Стиль игры')}</h3><p>${esc(localized.play)}</p></section>
        <section class="ability-box"><h3>⚡ ${esc(T(state.meta.roles[wiz.role], ability.name))}</h3><p>${esc(localized.rank4)}</p>${APP_I18N.current()==='ru'?`<details><summary>Полная справка способности</summary><p class="small">${esc(ability.desc)}</p></details>`:''}</section></div>
      </article><button class="role-arrow" data-role-shift="1" aria-label="${T('Next Role','Следующая роль')}">›</button></div>
    <p class="small muted center">${T('Use the tabs, arrow keys, buttons, or swipe.','Используйте вкладки, клавиши-стрелки, кнопки или свайп.')}</p>${wizRoleSetupHtml()}`;
}

/* ---------- Шаг 2: Lifepath ---------- */

function languagesForRegion(region) {
  const text = String(region || '');
  const key = Object.keys(CULTURAL_LANGUAGES).find(k => text === k || text.startsWith(k));
  return key ? CULTURAL_LANGUAGES[key] : [];
}

function syncNativeLanguage() {
  const w = state.wizard;
  const langs = languagesForRegion(w.lifepath.region);
  if (!langs.includes(w.nativeLanguage)) w.nativeLanguage = langs[0] || '';
  let native = w.subSkills.find(s => s.native);
  if (!native && w.nativeLanguage) {
    native = { base: 'Language', name: w.nativeLanguage, lvl: 4, free: true, native: true };
    w.subSkills.push(native);
  }
  if (native) {
    native.name = w.nativeLanguage;
    native.lvl = 4;
    native.free = true;
  }
}

function wizRollLifepath(key, roleSpecific) {
  const wiz = state.wizard;
  const fields = roleSpecific ? lpRoleField(wiz.role) : lpAllFields();
  const field = fields.find(f => f[0] === key);
  if (!field || !field[2].length) return;
  const picked = field[2][Math.floor(Math.random() * field[2].length)];
  (roleSpecific ? wiz.roleLifepath : wiz.lifepath)[key] = typeof picked === 'object' ? picked.value : picked;
  if (!roleSpecific && key === 'region') syncNativeLanguage();
}

function lifepathFieldsHtml(fields, values, attr, diceAttr, roleSpecific) {
  return fields.map(([key, label, opts]) => {
    const selected = values[key] || '';
    const selectedOpt = opts.find(o => (typeof o === 'object' ? o.value : o) === selected);
    const sources = selectedOpt && typeof selectedOpt === 'object' ? selectedOpt.sources : (roleSpecific ? ['CP:R'] : []);
    const info = APP_I18N.current() === 'en'
      ? (roleSpecific ? 'This question refines the Role’s professional history, habits, and connections.' : (LIFEPATH_QUESTION_EN[key] || 'This question establishes an important part of the character’s history.'))
      : (roleSpecific ? (ROLE_LIFEPATH_QUESTION_INFO[key] || 'Этот вопрос уточняет профессиональную историю, связи и привычки роли.') : (LIFEPATH_QUESTION_INFO[key] || 'Этот вопрос задаёт важную деталь предыстории персонажа.'));
    return `<div class="lp-item">
      <div class="lp-label">${esc(label)}</div>
      <div class="small muted lp-question-info">${esc(info)}</div>
      <div class="row" style="align-items:center;gap:6px;flex-wrap:nowrap">
        <select ${attr}="${key}" style="flex:1;min-width:0">
          <option value="">— не выбрано —</option>
          ${opts.map(raw => {
            const value = typeof raw === 'object' ? raw.value : raw;
            const tag = typeof raw === 'object' ? ` · ${raw.sources.join('+')}` : '';
            return `<option value="${esc(value)}" ${selected === value ? 'selected' : ''}>${esc(displayKnownValue(value) + tag)}</option>`;
          }).join('')}
        </select>
        <button class="btn-sm" ${diceAttr}="${key}" title="Случайный результат">🎲</button>
      </div>
      ${lifepathResultInfo(key, selected, sources, roleSpecific)}
    </div>`;
  }).join('');
}

function matchingNamePool(region) {
  const text = canonicalLifepathValue('region', String(region || ''));
  const direct = REGION_GENDERED_NAME_POOLS[text];
  if (direct) return direct;
  const key = Object.keys(REGION_GENDERED_NAME_POOLS).find(regionKey => text.startsWith(regionKey) || regionKey.startsWith(text));
  return key ? REGION_GENDERED_NAME_POOLS[key] : null;
}
function randomFrom(list) { return list[Math.floor(Math.random() * list.length)]; }
function genderedNames(pool, gender) { return pool ? (pool[gender] || pool.neutral || []) : []; }
function generateWizardHandle() {
  const style=state.wizard.handleStyle||'any',pools=style==='any'?Object.values(HANDLE_POOLS):[HANDLE_POOLS[style]||HANDLE_POOLS.street];
  state.wizard.handle = randomFrom(randomFrom(pools));
}
function generateWizardName(part) {
  const wiz = state.wizard, pool = matchingNamePool(wiz.lifepath.region);
  if (!pool) { toast(T('Choose a cultural region first.','Сначала выберите культурный регион.'), true); return; }
  if (part !== 'last') wiz.firstName = randomFrom(genderedNames(pool, wiz.nameGender || 'neutral'));
  if (part !== 'first') wiz.lastName = randomFrom(pool.surnames);
}
function setLifepathValue(key,value) {
  const wiz=state.wizard,canonical=canonicalLifepathValue(key,value);wiz.lifepath[key]=canonical;wiz.lifepathIds=wiz.lifepathIds||{};const field=MERGED_LIFEPATH_FIELDS.find(item=>item.key===key),option=field&&field.options.find(item=>item.value===canonical||(item.aliases||[]).includes(value));if(option)wiz.lifepathIds[key]=option.id;if(key==='region')syncNativeLanguage();
}

function wizRollHybrid(key, roleSpecific) {
  const fields = roleSpecific ? lpRoleField(state.wizard.role) : lpAllFields();
  const field = fields.find(row => row[0] === key);
  if (!field) return;
  const options = field[2];
  if (roleSpecific || typeof options[0] !== 'object') return wizRollLifepath(key, roleSpecific);
  const sources = [...new Set(options.flatMap(option => option.sources || []))];
  const source = randomFrom(sources);
  const aliases = Object.entries(LIFEPATH_KEY_ALIASES).filter(([, mapped]) => mapped === key).map(([raw]) => raw);
  const sourceFields = source === 'CEMK' ? CEMK_LIFEPATH_FIELDS : CORE_LIFEPATH_FIELDS;
  const original = sourceFields.find(([rawKey]) => rawKey === key || aliases.includes(rawKey));
  if (original && original[2].length) {
    const index = source === 'CEMK' && original[2].length >= 11
      ? (1 + Math.floor(Math.random() * 6)) + (1 + Math.floor(Math.random() * 6)) - 2
      : Math.floor(Math.random() * original[2].length);
    setLifepathValue(key, original[2][Math.min(index, original[2].length - 1)]);
  } else {
    const candidates = options.filter(option => (option.sources || []).includes(source));
    setLifepathValue(key, randomFrom(candidates).value);
  }
}
function lifepathProgress(fields, values) { return fields.filter(([key]) => String(values[key] || '').trim()).length; }
function lifepathSectionHtml(id, en, ru, keys, fields, values, roleSpecific) {
  const selected = fields.filter(([key]) => keys.includes(key));
  const complete = lifepathProgress(selected, values);
  const open = !!(state.wizard.lifepathOpen || {})[id];
  return `<details class="creation-section" data-lp-section="${id}" ${open ? 'open' : ''}><summary><span>${esc(T(en,ru))}</span><span class="section-progress ${complete===selected.length?'ok':''}">${complete}/${selected.length}</span></summary><div class="section-body lp-grid">${lifepathFieldsHtml(selected, values, roleSpecific?'data-role-lp':'data-lp', roleSpecific?'data-role-lp-dice':'data-lp-dice', roleSpecific)}</div></details>`;
}

function wizStepLifepathHtml() {
  const wiz = state.wizard, fields = lpAllFields(), roleFields = wiz.role ? lpRoleField(wiz.role) : [];
  const langs = languagesForRegion(wiz.lifepath.region);
  const commonDone = lifepathProgress(fields, wiz.lifepath), roleDone = lifepathProgress(roleFields, wiz.roleLifepath);
  wiz.nameGender = wiz.nameGender || 'neutral';
  return `<div class="lifepath-progress panel accent mb"><b>${T('Common Lifepath','Общий Lifepath')}: ${commonDone}/${fields.length}</b><b>${T('Role-Based','Ролевой')}: ${wiz.role ? roleDone+'/'+roleFields.length : T('choose a Role','выберите роль')}</b><div class="row"><button class="btn-sm" id="lp-fill-missing">🎲 ${T('Fill Missing','Заполнить пустые')}</button><button class="btn-primary btn-sm" id="lp-gen-all">🎲 ${T('Reroll All','Перебросить всё')}</button></div></div>
    <details class="creation-section" data-lp-section="identity" ${(wiz.lifepathOpen||{}).identity?'open':''}><summary><span>Identity</span><span class="section-progress ${wiz.handle?'ok':''}">${wiz.handle?'✓':'0/1'}</span></summary><div class="section-body">
      <div class="portrait-editor mb">${wiz.portraitMedia?`<img src="${esc(wiz.portraitMedia.url)}" alt="Character Portrait"><div class="row"><label class="btn-sm">${T('Replace','Заменить')}<input type="file" id="wiz-portrait-file" accept="image/jpeg,image/png,image/webp" hidden></label><button class="btn-sm btn-danger" id="wiz-portrait-remove">${T('Remove','Удалить')}</button></div>`:`<label class="portrait-empty"><span>🖼️</span><b>${T('Upload Character Portrait','Загрузить портрет персонажа')}</b><small>JPEG · PNG · WebP · 10 MB</small><input type="file" id="wiz-portrait-file" accept="image/jpeg,image/png,image/webp" hidden></label>`}</div>
      <div class="grid cols-3"><label class="f"><span>Handle *</span><select id="wiz-handle-style">${[['any','Any'],['street','Street'],['combat','Combat'],['net','Netrunner'],['stage','Stage'],['speed','Speed'],['neon','Neon']].map(([id,label])=>`<option value="${id}" ${(wiz.handleStyle||'any')===id?'selected':''}>${label}</option>`).join('')}</select><div class="input-action"><input id="wiz-handle" maxlength="60" value="${esc(wiz.handle)}"><button class="btn-sm" data-generate-handle>🎲</button></div></label>
      <label class="f"><span>${T('First name (optional)','Имя (необязательно)')}</span><div class="input-action"><input id="wiz-first-name" maxlength="60" value="${esc(wiz.firstName)}"><button class="btn-sm" data-generate-name="first" ${wiz.lifepath.region?'':'disabled'}>🎲</button></div></label>
      <label class="f"><span>${T('Last name (optional)','Фамилия (необязательно)')}</span><div class="input-action"><input id="wiz-last-name" maxlength="60" value="${esc(wiz.lastName)}"><button class="btn-sm" data-generate-name="last" ${wiz.lifepath.region?'':'disabled'}>🎲</button></div></label></div>
      <div class="segmented mt" role="group">${[['masculine','Masculine','Мужское'],['feminine','Feminine','Женское'],['neutral','Neutral','Нейтральное']].map(([id,en,ru])=>`<button data-name-gender="${id}" class="${wiz.nameGender===id?'active':''}">${T(en,ru)}</button>`).join('')}<button data-generate-name="both" ${wiz.lifepath.region?'':'disabled'}>🎲 ${T('Generate full name','Сгенерировать имя')}</button></div>
      ${wiz.lifepath.region?'':`<p class="small muted">${T('Choose Origin → Cultural Region to enable regional names.','Выберите Происхождение → Культурный регион для генератора имён.')}</p>`}
    </div></details>
    ${LIFEPATH_SECTIONS_V3.map(([id,en,ru,keys])=>lifepathSectionHtml(id,en,ru,keys,fields,wiz.lifepath,false)).join('')}
    <details class="creation-section" data-lp-section="language" ${(wiz.lifepathOpen||{}).language?'open':''}><summary><span>${T('Cultural Language','Культурный язык')}</span><span class="section-progress ${wiz.nativeLanguage?'ok':''}">${wiz.nativeLanguage?'✓':'0/1'}</span></summary><div class="section-body"><label class="f"><span>${T('Cultural Language · Level 4 free','Культурный язык · уровень 4 бесплатно')}</span><select id="lp-native" ${langs.length?'':'disabled'}><option value="">${langs.length?T('Choose…','Выберите…'):T('Choose a region first','Сначала выберите регион')}</option>${langs.map(value=>`<option value="${esc(value)}" ${wiz.nativeLanguage===value?'selected':''}>${esc(displayKnownValue(value))}</option>`).join('')}</select></label><p class="small muted">Streetslang 2 ${T('is paid from the 86-point Skill budget.','оплачивается из бюджета 86 очков.')}</p></div></details>
    ${wiz.role ? lifepathSectionHtml('role',`${wiz.role} Role-Based Lifepath`,`Ролевой Lifepath · ${wiz.role}`,roleFields.map(row=>row[0]),roleFields,wiz.roleLifepath,true) : `<div class="panel empty"><h3>${T('Choose a Role first','Сначала выберите роль')}</h3><p>${T('Role-Based Lifepath opens after a Role is selected. Common Lifepath remains available.','Role-Based Lifepath откроется после выбора роли. Общий Lifepath уже доступен.')}</p><button class="btn-sm" onclick="wizGoTo(1)">${T('Go to Role','Перейти к роли')}</button></div>`}`;
}

/* ---------- Шаг 3: Статы ---------- */

function wizStatSpent() {
  const wiz = state.wizard;
  return Object.values(wiz.stats).reduce((a, b) => a + (num(b) || 0), 0);
}

function updateWizStatBar() {
  const spent = wizStatSpent();
  const budget = state.meta.stat_points || 62;
  const el = $('#wiz-st-spent');
  if (el) {
    el.textContent = spent;
    el.classList.toggle('warn-text', spent !== budget);
  }
}

const ROLE_STAT_PRIORITIES = {
  Rockerboy:['COOL','EMP','DEX'], Solo:['REF','DEX','BODY','MOVE'], Netrunner:['INT','REF','TECH'],
  Tech:['TECH','INT','LUCK'], Medtech:['TECH','INT','EMP'], Media:['INT','COOL','EMP'],
  Exec:['COOL','INT','EMP'], Lawman:['COOL','REF','BODY'], Fixer:['COOL','EMP','INT'], Nomad:['REF','TECH','MOVE'],
};
function randomizeWizardStats() {
  const wiz=state.wizard, keys=state.meta.stats, unlocked=keys.filter(key=>!wiz.statLocks[key]);
  const lockedTotal=keys.filter(key=>wiz.statLocks[key]).reduce((sum,key)=>sum+(num(wiz.stats[key])||0),0);
  let remaining=(state.meta.stat_points||62)-lockedTotal-unlocked.length*2;
  if (!unlocked.length || remaining<0 || remaining>unlocked.length*6) { toast(T('Unlock more Characteristics: an exact 62-point spread is impossible.','Разблокируйте характеристики: распределение на 62 невозможно.'),true); return; }
  unlocked.forEach(key=>wiz.stats[key]=2);
  const mode=wiz.statRandomMode||'any';let focus=null;
  while(remaining>0){let candidates=unlocked.filter(key=>wiz.stats[key]<8);let key;if(mode==='balanced'){const min=Math.min(...candidates.map(k=>wiz.stats[k]));key=randomFrom(candidates.filter(k=>wiz.stats[k]<=min+1));}else if(mode==='wide'){if(!focus||wiz.stats[focus]>=8||Math.random()<.22)focus=randomFrom(candidates);key=focus;}else key=randomFrom(candidates);wiz.stats[key]++;remaining--;}
}
function showStatInfo(stat) {
  const row=STAT_DETAILS_V3[stat]; if(!row)return;
  const related=(state.meta.skills||[]).filter(skill=>skill[2]===stat).map(skill=>skill[1]);
  const base=state.wizard?state.wizard.stats[stat]:null,penalty=state.wizard?(wizDerived().armor_penalties||{})[stat]||0:0;
  openModal(`<h2>${stat} · ${esc(T(row[0],row[1]))}</h2><div class="chips mb"><span class="chip">Base ${base??'—'}</span>${penalty?`<span class="chip warn-text">Armor ${penalty}</span><span class="chip">Effective ${(base||0)+penalty}</span>`:''}<span class="tag source">${esc(row[4])}</span></div><p>${esc(T(row[2],row[3]))}</p><div class="panel"><b>${T('Related Skills','Связанные навыки')}</b><div class="chips mt">${related.map(name=>`<span class="chip">${esc(name)}</span>`).join('')||'—'}</div></div>${stat==='LUCK'?`<p class="guide-note">${T('LUCK is a spendable pool. Current LUCK is tracked separately from the maximum STAT after character creation.','LUCK — расходуемый пул. После создания текущее значение хранится отдельно от максимума.')}</p>`:''}`);
}
function wizStepStatsHtml() {
  const wiz=state.wizard, spent=wizStatSpent(), budget=state.meta.stat_points||62, remaining=budget-spent, derived=wizDerived();
  const priorities=ROLE_STAT_PRIORITIES[wiz.role]||[];
  return `<div class="sticky-budget panel accent mb"><div><b>${T('Allocated','Распределено')}: <span id="wiz-st-spent">${spent}</span> / ${budget}</b><span class="budget-remaining ${remaining===0?'ok':remaining<0?'bad':''}">${T('Points remaining','Осталось')}: ${remaining}</span></div><div class="row"><select id="wiz-st-mode"><option value="balanced" ${wiz.statRandomMode==='balanced'?'selected':''}>Balanced</option><option value="wide" ${wiz.statRandomMode==='wide'?'selected':''}>Wide</option><option value="any" ${!wiz.statRandomMode||wiz.statRandomMode==='any'?'selected':''}>Any legal spread</option></select><button class="btn-sm" id="wiz-st-roll">🎲 ${T('Randomize unlocked','Сгенерировать незакреплённые')}</button><button class="btn-sm" id="wiz-st-reset">${T('Reset all to 5','Сбросить все на 5')}</button></div></div>
    ${wiz.role?`<div class="panel mb"><b>${T('Suggested priorities for','Рекомендуемые приоритеты для')} ${esc(wiz.role)}:</b> ${priorities.map(stat=>`<span class="chip">${stat}</span>`).join('')}</div>`:''}
    <div class="stat-cards">${state.meta.stats.map(stat=>{const value=num(wiz.stats[stat])||5,locked=!!wiz.statLocks[stat],info=STAT_DETAILS_V3[stat];return `<article class="stat-card ${priorities.includes(stat)?'recommended':''}"><button class="skill-name-btn stat-name" data-stat-info="${stat}"><b>${stat}</b><span>${esc(T(info[0],info[1]))}</span></button><button class="stat-lock ${locked?'locked':''}" data-stat-lock="${stat}" title="${T('Preserve during random generation','Сохранить при генерации')}">${locked?'🔒':'🔓'}</button><div class="stat-stepper"><button class="mini-step" data-stat-step="${stat}|-1" ${value<=2?'disabled':''}>−</button><strong>${value}</strong><button class="mini-step" data-stat-step="${stat}|1" ${value>=8||spent>=budget?'disabled':''}>＋</button></div><small>${T('Range','Диапазон')} 2–8${['REF','DEX','MOVE'].includes(stat)&&((derived.armor_penalties||{})[stat]||0)?` · Effective ${value+derived.armor_penalties[stat]}`:''}</small>${stat==='LUCK'?`<span class="luck-pips preview">${Array.from({length:value},()=>'<i class="filled"></i>').join('')}</span>`:''}</article>`;}).join('')}</div>
    <p class="small muted">${T('Locks only affect random generation. BODY and WILL determine HP; EMP determines starting Humanity.','Замки влияют только на генерацию. BODY и WILL определяют HP; EMP определяет начальную Humanity.')}</p>`;
}

/* ---------- Шаг 4: Навыки + суб-навыки ---------- */

function wizSkillSpent() {
  const wiz = state.wizard;
  const dblCost = Object.fromEntries(state.meta.skills.map(s => [s[1], !!s[3]]));
  return Object.entries(wiz.skills).reduce((total, [name, lvl]) => total + (num(lvl) || 0) * (dblCost[name] ? 2 : 1), 0);
}

function wizSubAllocated(base) {
  return state.wizard.subSkills.filter(s => s.base === base).reduce((total, skill) => {
    const level = num(skill.lvl) || 0;
    return total + (skill.native ? Math.max(0, level - 4) : level);
  }, 0);
}

function wizSubFree(base) {
  return Math.max(0, (num(state.wizard.skills[base]) || 0) - wizSubAllocated(base));
}

function wizMustOk(name) {
  const wiz = state.wizard;
  if (name === 'Language') {
    return wiz.subSkills.some(s => s.base === 'Language' && s.name === 'Streetslang' && (s.lvl || 0) >= 2);
  }
  if (name === 'Local Expert') {
    return wiz.subSkills.some(s => s.base === 'Local Expert' && !s.native && (s.lvl || 0) >= 2);
  }
  return (wiz.skills[name] || 0) >= 2;
}

function updateWizSkillHud() {
  const spent = wizSkillSpent();
  const budget = state.meta.skill_points || 86;
  const el = $('#wiz-sk-spent');
  if (el) {
    el.textContent = spent;
    el.classList.toggle('warn-text', spent !== budget);
  }
  $$('.wiz-must-chip').forEach(chip => {
    const ok = wizMustOk(chip.dataset.must);
    chip.classList.toggle('ok', ok);
    chip.classList.toggle('bad', !ok);
    chip.textContent = (ok ? '✓ ' : '✗ ') + chip.dataset.must;
  });
}

function skillDetail(name) {
  return SKILL_DETAILS[name] || ['Описание навыка пока не добавлено.', 'ГМ определяет подходящий пример и сложность проверки.'];
}

function showSkillInfo(name) {
  const meta = (state.meta.skills || []).find(s => s[1] === name), detail = skillDetail(name), isEn = APP_I18N.current() === 'en';
  const description = isEn ? `${name} is a Corebook ${meta ? meta[0] : ''} Skill linked to ${meta ? meta[2] : 'the relevant STAT'}. Each named specialization is tracked separately where applicable.` : detail[0];
  const example = isEn ? `Example: make a ${name} Check when the declared action directly relies on this training; the GM sets the DV or uses an opposed Check.` : detail[1];
  openModal(`<h2>${esc(name)}</h2><div class="chips mb"><span class="chip">STAT ${esc(meta ? meta[2] : '—')}</span>${meta && meta[3] ? '<span class="tag">×2</span>' : '<span class="tag">×1</span>'}<span class="tag source">CP:R pp. 130–142</span></div><p>${esc(description)}</p><div class="panel accent"><b>${T('Example','Пример')}</b><p class="small">${esc(example)}</p></div>`);
}

function wizSubRowsHtml(base, presets, stat, is2) {
  const wiz = state.wizard;
  const free = wizSubFree(base);
  const pool = num(wiz.skills[base]) || 0;
  const parentMeta = state.meta.skills.find(row => row[1] === base);
  const parentCost = parentMeta && parentMeta[3] ? 2 : 1;
  const canGrowParent = (state.meta.skill_points || 86) - wizSkillSpent() >= parentCost;
  const list = wiz.subSkills.map((sub, index) => [sub, index]).filter(([sub]) => sub.base === base);
  const dl = `wiz-dl-${base.replace(/\s+/g, '-')}`;
  return `<div class="subskill-pool">
    <div class="subskill-pool-head">
      <span>${T('Allocated','Распределено')} <b>${wizSubAllocated(base)}</b> / ${pool}; ${T('free','свободно')} <b class="${free ? 'green' : 'muted'}">${free}</b></span>
      ${free > 0 ? `<button class="btn-sm" data-sub-add="${esc(base)}">＋ ${T('Add specialization','Добавить специализацию')}</button>` : ''}
    </div>
    ${list.map(([sub, i]) => {
      const currentStat = stat === 'EMP' ? (wizDerived().emp_cur ?? wiz.stats.EMP) : wiz.stats[stat];
      return `<div class="skill-row subskill-row">
        <span class="sname subskill-name">↳ <input data-sub-name="${i}" list="${dl}" value="${esc(sub.name)}" placeholder="${T('Specialization name','Название специализации')}" ${sub.native ? 'disabled' : ''}></span>
        <span class="sstat">${esc(stat)}</span>
        <span class="slvl"><button class="mini-step" data-sub-minus="${i}" ${sub.lvl <= (sub.native ? 4 : 0) ? 'disabled' : ''}>−</button><b>${sub.lvl || 0}</b><button class="mini-step" data-sub-plus="${i}" ${sub.lvl >= 6 || (free <= 0 && !canGrowParent) ? 'disabled' : ''} title="${free > 0 ? T('Uses 1 free parent point','Использует 1 свободное очко parent') : T(`Increases parent pool for ${parentCost} Skill Point${parentCost > 1 ? 's' : ''}`,`Увеличит parent-pool за ${parentCost} очк.`)}">＋</button></span>
        <span class="sbase"><b>${(num(currentStat) || 0) + (sub.lvl || 0)}</b>${sub.native ? ` <span class="chip">${T('Cultural 4 free','Культурный 4 бесплатно')}${sub.lvl > 4 ? ` · ${sub.lvl - 4} ${T('paid','оплачено')}` : ''}</span>` : ''}</span>
        ${sub.native ? '<span></span>' : `<button class="btn-sm btn-danger" data-sub-del="${i}" title="${T('Remove specialization','Удалить специализацию')}">✕</button>`}
      </div>`;
    }).join('')}
    <datalist id="${dl}">${presets.map(value => `<option value="${esc(value)}">`).join('')}</datalist>
  </div>`;
}

const SKILL_CATEGORY_EN = {'Осознание':'Awareness','Тело':'Body','Управление':'Control','Образование':'Education','Бой':'Fighting','Выступление':'Performance','Стрелковое':'Ranged Weapon','Социальные':'Social','Технические':'Technique'};
function skillCategoryLabel(category) { return APP_I18N.current() === 'en' ? (SKILL_CATEGORY_EN[category] || category) : category; }
function skillLevelStepper(name, lvl, is2, allocatedFloor, isParent) {
  const remaining=(state.meta.skill_points||86)-wizSkillSpent(), cost=is2?2:1;
  return `<span class="slvl skill-stepper"><button class="mini-step" data-wiz-skill-step="${esc(name)}|-1" ${lvl<=Math.max(0,allocatedFloor||0)?'disabled':''}>−</button><b>${lvl}</b><button class="mini-step" data-wiz-skill-step="${esc(name)}|1" ${(!isParent&&lvl>=6)||remaining<cost?'disabled':''}>＋</button></span>`;
}
function wizStepSkillsHtml() {
  const wiz=state.wizard, budget=state.meta.skill_points||86, spent=wizSkillSpent(), remaining=budget-spent;
  const recommended=new Set(ROLE_RECOMMENDED_SKILLS[wiz.role]||[]), required=new Set(state.meta.must_skills||[]);
  const specialized=Object.fromEntries(SUB_SKILL_BASES.map(row=>[row[0],row]));
  const query=String(wiz.skillQ||'').trim().toLowerCase(), filter=wiz.skillFilter||'all';
  const requiredDone=[...required].filter(wizMustOk).length;
  const include=([cat,name,,is2])=>{
    if(query&&!name.toLowerCase().includes(query))return false;
    if(filter==='required'&&!required.has(name))return false;
    if(filter==='recommended'&&!recommended.has(name))return false;
    if(filter==='allocated'&&!(num(wiz.skills[name])||0)&&!wiz.subSkills.some(sub=>sub.base===name&&sub.lvl>0))return false;
    if(filter==='x2'&&!is2)return false;
    return true;
  };
  const groups=new Map();
  for(const row of state.meta.skills.filter(include)){if(!groups.has(row[0]))groups.set(row[0],[]);groups.get(row[0]).push(row);}
  const derived=wizDerived();
  const groupHtml=[...groups.entries()].map(([cat,rows])=>{
    const open=wiz.skillOpen[cat]!==false;
    const content=rows.map(([_,name,stat,is2])=>{
      const lvl=num(wiz.skills[name])||0, statValue=stat==='EMP'?(derived.emp_cur??wiz.stats.EMP):wiz.stats[stat];
      const sub=specialized[name], allocated=sub?wizSubAllocated(name):0, ok=!required.has(name)||wizMustOk(name);
      return `<div class="skill-row ${sub?'skill-parent':''} ${recommended.has(name)?'recommended':''} ${ok?'':'requirement-missing'}"><button class="skill-name-btn sname" data-skill-info="${esc(name)}">${esc(name)} ${is2?'<span class="tag">×2</span>':'<span class="muted small">×1</span>'}${required.has(name)?` <span class="tag ${ok?'ok':'bad'}">${ok?'Required ✓':'Required 2'}</span>`:''}${recommended.has(name)?` <span class="tag recommended-tag">${T('Recommended','Рекомендуется')}</span>`:''}</button><span class="sstat">${stat} <b>${statValue}</b></span>${skillLevelStepper(name,lvl,is2,allocated,!!sub)}<span class="sbase"><b>${(num(statValue)||0)+lvl}</b></span><span></span></div>${sub?wizSubRowsHtml(name,sub[2],stat,is2):''}`;
    }).join('');
    return `<details class="skill-category creation-section" data-skill-category="${esc(cat)}" ${open?'open':''}><summary><span>${esc(skillCategoryLabel(cat))}</span><span>${rows.length}</span></summary><div class="section-body"><div class="skill-table-head"><span>Skill</span><span>STAT</span><span>LVL</span><span>BASE</span><span></span></div>${content}</div></details>`;
  }).join('');
  const ability=wiz.role?ROLE_ABILITIES[wiz.role]:null;
  return `<div class="sticky-budget panel accent mb"><div><b>${T('Allocated','Распределено')}: <span id="wiz-sk-spent">${spent}</span> / ${budget}</b><span class="budget-remaining ${remaining===0?'ok':''}">${T('Points remaining','Осталось')}: ${remaining}</span></div><b>${T('Required Skills','Обязательные навыки')}: ${requiredDone}/${required.size}</b></div>
    ${ability?`<div class="panel role-ability-banner mb"><div><small>${T('Role Ability — not a Skill','Ролевая способность — не навык')}</small><h3>${esc(roleAbilityDisplayName(wiz.role))} · Rank 4</h3></div><button class="btn-sm" onclick="wizGoTo(1)">${T('View Role','Открыть роль')}</button></div>`:''}
    <div class="skill-tools mb"><input id="wiz-skill-q" value="${esc(wiz.skillQ||'')}" placeholder="${T('Search Skills…','Поиск навыков…')}"><div class="segmented">${[['all','All','Все'],['required','Required','Обязательные'],['recommended','Recommended','Рекомендуемые'],['allocated','Allocated','Купленные'],['x2','×2','×2']].map(([id,en,ru])=>`<button data-skill-filter="${id}" class="${filter===id?'active':''}">${T(en,ru)}</button>`).join('')}</div></div>
    ${groupHtml||`<div class="empty">${T('No Skills match these filters.','Нет навыков по выбранным фильтрам.')}</div>`}
    <p class="small muted">${T('Parent pools may retain unallocated levels. Child levels may never exceed the purchased parent pool. Cultural Language 4 is free.','В parent-pool можно оставлять свободные уровни. Сумма дочерних уровней не превышает купленный пул. Cultural Language 4 бесплатен.')}</p>`;
}

/* ---------- Шаг 5: Стиль и внешность ---------- */

function itemVisibleType(item, fallback) {
  const raw = String((item.fields || {}).Type || item.type || '').trim();
  if (raw) return raw.split(/\n|\//)[0].trim();
  if (item.cat === 'fashion') {
    const styles = ['Bag Lady Chic', 'Generic Chic', 'High Fashion', 'Nomad Leathers', 'Urban Flash',
      'Asia Pop', 'Bohemian', 'Businesswear', 'Gang Colors', 'Leisurewear'];
    return styles.find(style => String(item.name).startsWith(style)) || 'Fashion';
  }
  return fallback || item.cat || 'Другое';
}

function groupedItemsHtml(items, rowHtml, fallback) {
  const groups = new Map();
  for (const item of items) {
    const type = itemVisibleType(item, fallback);
    if (!groups.has(type)) groups.set(type, []);
    groups.get(type).push(item);
  }
  return [...groups.entries()].sort((a, b) => a[0].localeCompare(b[0], 'ru')).map(([type, rows]) =>
    `<section class="catalog-group"><h4 class="catalog-type">${esc(type)} <span>${rows.length}</span></h4>${rows.map(rowHtml).join('')}</section>`
  ).join('');
}

function showCreationItemInfo(item) {
  if (!item) return;
  const f = item.fields || {}, mechanics = item.mechanics || {};
  const rows = [...Object.entries(mechanics), ...Object.entries(f).filter(([key]) => !(key in mechanics))]
    .filter(([, value]) => value != null && String(value).trim())
    .map(([key, value]) => `<b>${esc(key.replace(/_/g, ' '))}</b><span>${esc(value && typeof value === 'object' ? (value.notation || JSON.stringify(value)) : value)}</span>`).join('');
  const requirements = (item.requirements || []).map(req => req.kind === 'stat' ? `${req.stat} ${req.minimum}+` : req.value);
  openModal(`<h2>${esc(item.variant_name || item.display_name || item.name)}</h2>
    <div class="chips mb"><span class="chip">${esc(itemVisibleType(item, T('Item','Предмет')))}</span>${item.is_custom?'<span class="tag">CUSTOM · MANUAL</span>':''}${item.source ? `<span class="tag source">${esc(item.source)}</span>` : ''}${item.acquisition_source?`<span class="chip">${esc(acquisitionSourceLabel(item.acquisition_source))}</span>`:''}${item.price != null ? `<span class="price">${money(item.price)}</span>` : ''}</div>
    <div class="mechanic-chips mb">${itemMechanicChips(item)}</div>
    ${requirements.length ? `<div class="panel accent mb"><b>${T('Requirements','Требования')}</b><p>${requirements.map(esc).join(' · ')}</p></div>` : ''}
    ${item.desc ? `<p class="preserve-lines">${esc(item.desc)}</p>` : `<p class="muted">${T('No description is available in Data Pool.','Описание в Data Pool не указано.')}</p>`}
    ${rows ? `<div class="kv mt">${rows}</div>` : ''}`, true);
}

async function wizLoadStyleLists() {
  const wiz = state.wizard;
  const boxC = $('#wiz-style-clothes');
  const boxF = $('#wiz-style-fw');
  if (!boxC || !boxF) return;
  wiz.scrolls = wiz.scrolls || {};
  if (!wiz._styleCache) {
    boxC.innerHTML = spinner(); boxF.innerHTML = spinner();
    const [fash, cyber] = await Promise.all([
      api('/api/items?' + new URLSearchParams({ cat: 'fashion', limit: 500 })),
      api('/api/items?' + new URLSearchParams({ cat: 'cyberware', limit: 500 })),
    ]);
    wiz._styleCache = {
      clothes: fash.items.filter(i => i.price != null).sort(byNameRu),
      fashionware: cyber.items.filter(i => (num(i.hl) || 0) === 0 && String((i.fields || {}).Type || '').toLowerCase().includes('fashionware')).sort(byNameRu),
    };
  }
  const remaining = FASHION_BUDGET - wiz.fashionCost;
  const q = (wiz.styleQ || '').trim().toLowerCase();
  let clothes = wiz._styleCache.clothes;
  let fashionware = wiz._styleCache.fashionware;
  if (q) {
    clothes = clothes.filter(i => String(i.name).toLowerCase().includes(q));
    fashionware = fashionware.filter(i => String(i.name).toLowerCase().includes(q));
  }
  const rowHtml = kind => it => {
    const affordable = (it.price || 0) <= remaining;
    return `<div class="inv-row catalog-row ${affordable ? '' : 'unaffordable'}">
      <span class="iname">${esc(it.name)}</span>${kind === 'fw' ? '<span class="hl-badge">0 HL</span>' : ''}
      <span class="${affordable ? 'price' : 'muted'}">${money(it.price)}</span>
      <button class="info-btn" data-style-info="${kind}|${esc(it.id)}" title="Описание">i</button>
      <button class="btn-sm" data-style-add="${kind}|${esc(it.id)}" ${affordable ? '' : 'disabled'}>＋</button>
    </div>`;
  };
  boxC.innerHTML = clothes.length ? groupedItemsHtml(clothes, rowHtml('cl'), 'Fashion') : '<div class="empty small">Ничего не нашлось.</div>';
  boxF.innerHTML = fashionware.length ? groupedItemsHtml(fashionware, rowHtml('fw'), 'Fashionware') : '<div class="empty small">Fashionware не найден.</div>';
  requestAnimationFrame(() => { boxC.scrollTop = wiz.scrolls.style || 0; boxF.scrollTop = wiz.scrolls.fashionware || 0; });
  boxC.onscroll = () => { wiz.scrolls.style = boxC.scrollTop; };
  boxF.onscroll = () => { wiz.scrolls.fashionware = boxF.scrollTop; };

  $$('[data-style-info]', $('#wiz-body')).forEach(btn => btn.onclick = e => {
    e.stopPropagation();
    const [kind, id] = btn.dataset.styleInfo.split('|');
    showCreationItemInfo((kind === 'fw' ? wiz._styleCache.fashionware : wiz._styleCache.clothes).find(x => x.id === id));
  });
  $$('[data-style-add]', $('#wiz-body')).forEach(btn => btn.onclick = () => {
    const [kind, id] = btn.dataset.styleAdd.split('|');
    const src = kind === 'fw' ? wiz._styleCache.fashionware : wiz._styleCache.clothes;
    const item = src.find(x => x.id === id);
    if (!item) return;
    const price = item.price || 0;
    if (wiz.fashionCost + price > FASHION_BUDGET) { toast('Не хватает бюджета стиля (800€$)', true); return; }
    if (kind === 'fw') {
      const existing = wiz.fashionware.find(x => x.id === item.id);
      if (existing) existing.qty = (existing.qty || 1) + 1;
      else wiz.fashionware.push({ id: item.id, name: item.name, hl: 0, price, qty: 1, type: String((item.fields || {}).Type || 'Fashionware'), desc: item.desc || '', fields: item.fields || {}, source: item.source || '' });
    } else {
      const existing = wiz.fashion.find(x => x.key === item.id);
      if (existing) existing.qty = (existing.qty || 1) + 1;
      else wiz.fashion.push({ key: item.id, cat: item.cat, name: item.name, price, qty: 1, desc: item.desc || '', fields: item.fields || {}, source: item.source || '', type: itemVisibleType(item, 'Fashion') });
    }
    wiz.fashionCost += price;
    renderWizard(); toast('Добавлено: ' + item.name);
  });
}

function quantityControl(kind, index, qty, canPlus) {
  return `<span class="qty-control"><button class="mini-step" data-cart-qty="${kind}|${index}|-1">−</button><b>${qty}</b><button class="mini-step" data-cart-qty="${kind}|${index}|1" ${canPlus ? '' : 'disabled'}>＋</button></span>`;
}

function wizStepStyleHtml() {
  const wiz = state.wizard;
  const remaining = FASHION_BUDGET - wiz.fashionCost;
  const rows = [];
  wiz.fashion.forEach((item, i) => rows.push({ type: itemVisibleType(item, 'Fashion'), html: `<div class="inv-row"><span class="iname">🧥 ${esc(item.name)}</span>${quantityControl('style', i, item.qty || 1, remaining >= (item.price || 0))}<span class="price">${money((item.price || 0) * (item.qty || 1))}</span><button class="info-btn" data-cart-info="style|${i}">i</button></div>` }));
  wiz.fashionware.forEach((item, i) => rows.push({ type: itemVisibleType(item, 'Fashionware'), html: `<div class="inv-row"><span class="iname">💠 ${esc(item.name)}</span>${quantityControl('fashionware', i, item.qty || 1, remaining >= (item.price || 0))}<span class="hl-badge">0 HL</span><span class="price">${money((item.price || 0) * (item.qty || 1))}</span><button class="info-btn" data-cart-info="fashionware|${i}">i</button></div>` }));
  const groups = new Map();
  for (const row of rows) { if (!groups.has(row.type)) groups.set(row.type, []); groups.get(row.type).push(row.html); }
  const cartHtml = [...groups.entries()].sort((a,b)=>a[0].localeCompare(b[0],'ru')).map(([type, content]) => cartSectionHtml(type, content)).join('');
  return `
    <div class="row mb" style="justify-content:space-between">
      <span class="muted small">Бюджет стиля: <b>${money(FASHION_BUDGET)}</b> · Потрачено: <b>${money(wiz.fashionCost)}</b> · Осталось: <b class="${remaining < 0 ? 'warn-text' : ''}">${money(remaining)}</b></span>
      <span class="tag" style="color:var(--orange)">⚠️ Остаток сгорает после создания</span>
    </div>
    <div class="searchbar mb"><input id="wiz-style-q" placeholder="Фильтр одежды и Fashionware…" value="${esc(wiz.styleQ || '')}"></div>
    <div class="grid cols-2 style-catalogs">
      <div class="panel"><h3>🧥 Одежда · по Type</h3><div id="wiz-style-clothes" class="catalog-scroll">${spinner()}</div></div>
      <div class="panel"><h3>💠 Fashionware · по Type</h3><div id="wiz-style-fw" class="catalog-scroll">${spinner()}</div></div>
    </div>
    <div class="mt"><h3>📋 Выбранный стиль</h3></div>
    <div id="wiz-style-cart">${cartHtml || '<div class="empty small">Пока ничего не выбрано.</div>'}</div>`;
}

/* ---------- Шаг 6: Закупка снаряжения ---------- */

function armorPurchaseVariants(items) {
  const variants = [];
  for (const location of ['body', 'head']) {
    for (const item of items) {
      const locs = item.armor_locations || ['body', 'head'];
      if (item.armor_bundled || !locs.includes(location)) continue;
      variants.push({ ...item, variant_id: `${item.id}@${location}`, purchase_location: location,
        variant_name: `${item.name} — ${location === 'body' ? 'тело' : 'голова'}` });
    }
  }
  for (const item of items.filter(i => i.armor_bundled)) {
    variants.push({ ...item, variant_id: `${item.id}@set`, purchase_location: 'set',
      variant_name: `${item.name} — комплект голова + тело` });
  }
  for (const item of items.filter(i => (i.armor_locations || []).includes('shield'))) {
    variants.push({ ...item, variant_id: `${item.id}@shield`, purchase_location: 'shield',
      variant_name: `${item.name} — щит` });
  }
  return variants;
}

function canAffordCreationItem(wiz, item, price) {
  if (item.cat === 'cyberware') {
    return wiz.gearCost + Math.max(0, wiz.chromeCost + price - creationChromeBonus(wiz)) <= GEAR_BUDGET;
  }
  return creationMainSpent(wiz) + price <= GEAR_BUDGET;
}

function armorPieceFromItem(it) {
  return { key: it.variant_id, source_key: it.id, name: it.name, sp: it.sp || 0,
    penalties: { ...(it.penalties || {}) }, bundled: !!it.armor_bundled };
}

function hasPaidNeuroport(wiz) {
  return wiz.cyberware.some(item => String(item.name).toLowerCase() === 'neuroport');
}

function isForbiddenDuplicate(wiz, item) {
  if (String(item.name).toLowerCase() === 'neuroport') return wiz.freeNeuroport || hasPaidNeuroport(wiz);
  if ((item.capacity || {}).unique && [...wiz.cyberware, ...wiz.fashionware].some(entry => entry.id === item.id)) return true;
  if (item.cat === 'armor' && wiz.gear.some(entry => entry.key === (item.variant_id || item.id))) return true;
  return false;
}

function itemMechanicChips(item) {
  const m=item.mechanics||{},chips=[];
  const clean=value=>String(value).replace(/\.0(?=\b)/g,'');
  if(m.damage){const average=Number(m.damage.average),avg=Number.isInteger(average)?average:String(average);chips.push(`<span class="weap-dmg">${esc(m.damage.notation)} · ${m.damage.dice}d${m.damage.sides} · ${avg} ${T('avg','сред.')}</span>`);}
  const labels={rof:['ROF','Скорострельность'],hands:['Hands','Руки'],magazine:['Mag','Магазин'],skill:['Skill','Навык'],quality:['Quality','Качество'],concealable:['Conceal','Скрываемое'],sp:['SP','SP'],sdp:['SDP','SDP'],seats:['Seats','Места'],combat_speed:['Combat','Боевая скорость'],narrative_speed:['Narrative','Скорость в мире'],installation:['Install','Установка'],slots_used:['Slots','Слоты'],program_class:['Class','Класс'],per:['PER','PER'],spd:['SPD','SPD'],atk:['ATK','ATK'],def:['DEF','DEF'],rez:['REZ','REZ'],nomad_access:['Nomad','Доступ Nomad']};
  for(const [key,pair] of Object.entries(labels))if(m[key]!=null&&key!=='sp')chips.push(`<span class="chip"><b>${T(pair[0],pair[1])}</b> ${esc(clean(m[key]))}</span>`);
  if(m.sp!=null||item.sp!=null)chips.push(`<span class="chip"><b>SP</b> ${esc(clean(m.sp??item.sp))}</span>`);
  const locations=item.armor_locations||m.armor_locations||[];
  if(locations.length){const locationLabel=locations.includes('shield')?T('SHIELD','ЩИТ'):(item.armor_bundled||m.armor_bundled?T('HEAD + BODY SET','КОМПЛЕКТ ГОЛОВА + ТЕЛО'):locations.map(location=>T(location.toUpperCase(),location==='head'?'ГОЛОВА':'ТЕЛО')).join(' / '));chips.push(`<span class="chip armor-location"><b>${esc(locationLabel)}</b></span>`);if(locations.length>1&&!item.armor_bundled&&!m.armor_bundled)chips.push(`<span class="chip">${T('purchased separately','покупается раздельно')}</span>`);}
  if(item.hl)chips.push(`<span class="hl-badge">HL ${item.hl}</span>`);
  if(item.consumable)chips.push(`<span class="chip"><b>${T('Consumable','Расходник')}</b></span>`);
  if(item.equippable)chips.push(`<span class="chip"><b>${T('Equippable','Экипируемый')}</b></span>`);
  if(item.effect_coverage?.automated)chips.push(`<span class="chip effect-auto"><b>${T('AUTOMATED EFFECT','АВТОМАТИЧЕСКИЙ ЭФФЕКТ')}</b></span>`);
  if(item.effect_coverage?.manual||item.use_effect?.manual_resolution_required)chips.push(`<span class="chip effect-manual"><b>${T('MANUAL RULE','РУЧНОЕ ПРАВИЛО')}</b></span>`);
  if(m.quantity_per_purchase)chips.push(`<span class="chip">${m.quantity_per_purchase} ${T('per purchase','за покупку')}</span>`);
  return chips.join('');
}
function selectedWeaponTypes(wiz) {
  return wiz.gear.filter(item=>['guns','melee'].includes(item.cat)).map(item=>String((item.mechanics||{}).type||item.fields?.Type||'').toLowerCase()).filter(Boolean);
}
function ammoCompatibility(item,wiz) {
  const suitable=String((item.mechanics||{}).compatible_weapons||item.fields?.['Suitable ammo / weapon']||'').toLowerCase();
  if(!suitable)return [];
  return selectedWeaponTypes(wiz).filter(type => {
    if (suitable.includes('all except')) return !(['grenade', 'rocket'].some(token => type.includes(token)));
    return suitable.includes(type) || type.includes(suitable.replace(/ ammunition.*/, '').trim());
  });
}
function cyberFoundationNames(host) {
  const map={Cyberarm:['cyberarm','neo-soviet cyberarm'],Cyberleg:['cyberleg','romanova cyberlegs','rocklin augmentics skydrivers'],Cybereye:['cybereye','sponsored cybereye'],'Cyberaudio Suite':['cyberaudio suite','discount cyberaudio suite'],'Neural Link or Neuroport':['neural link','neuroport']};
  return map[host]||[];
}
function clientInstanceId(){if(globalThis.crypto?.randomUUID)return crypto.randomUUID().replaceAll('-','').toLowerCase();return Array.from({length:32},()=>Math.floor(Math.random()*16).toString(16)).join('');}
function pairedCyberlegFoundation(item){return String(item?.desc||'').toLowerCase().includes('paired cyberlegs');}
function cyberFoundationKind(item){const name=String(item?.name||'').toLowerCase();if(['cyberarm','neo-soviet cyberarm'].includes(name))return 'Cyberarm';if(['cyberleg'].includes(name)||pairedCyberlegFoundation(item))return 'Cyberleg';if(['cybereye','sponsored cybereye'].includes(name))return 'Cybereye';return '';}
function cyberSideRequired(item){return !!cyberFoundationKind(item)&&!pairedCyberlegFoundation(item);}
function chooseCyberSide(wiz,item){if(pairedCyberlegFoundation(item))return 'paired';if(!cyberSideRequired(item))return '';const kind=cyberFoundationKind(item),occupied=new Set(wiz.cyberware.filter(other=>cyberFoundationKind(other)===kind).map(other=>other.installation_side).filter(Boolean)),available=['left','right'].filter(side=>!occupied.has(side));if(!available.length){toast(T(`Both ${kind} sides are occupied.`,`Обе стороны ${kind} заняты.`),true);return null;}const answer=available.length===1?available[0]:(prompt(`${T('Choose installation side','Выберите сторону установки')}: ${available.join(' / ')}`,available[0])||'').toLowerCase();return available.includes(answer)?answer:null;}
function pairedCyberHostId(instanceId){const value=String(instanceId||'').toLowerCase();if(/^[a-f0-9]{32}$/.test(value))return value.slice(0,-1)+((parseInt(value.at(-1),16)+1)%16).toString(16);return `${value}:paired-2`;}
function cyberHostIds(item){return item.host_instances&&item.host_instances.length?item.host_instances:(item.host_instance?[item.host_instance]:[]);}
function cyberOptionSlots(item){const parsed=String(item?.desc||'').match(/(?:takes?|uses?|requires?)\s+(?:up\s+)?(\d+)\s+(?:cyberware\s+)?option slots?/i);return Number(parsed?.[1])||Number(item?.capacity?.slots_used)||0;}
function cyberPhysicalHosts(wiz){const all=[...wiz.cyberware];if(wiz.freeNeuroport)all.unshift({id:'creation-neuroport',instance_id:'creation-neuroport',name:'Neuroport',capacity:{slots_total:5}});return all.flatMap(candidate=>{if(!pairedCyberlegFoundation(candidate))return [candidate];const parent=candidate.instance_id||candidate.id,total=Number(String(candidate.desc||'').match(/each cyberleg has\s+(\d+)\s+option slots?/i)?.[1])||Number(candidate.capacity?.slots_total)||1;return [{...candidate,instance_id:parent,name:`${candidate.name} · Left`,capacity:{...(candidate.capacity||{}),host:null,slots_total:total}},{...candidate,instance_id:pairedCyberHostId(parent),name:`${candidate.name} · Right`,capacity:{...(candidate.capacity||{}),host:null,slots_total:total}}];});}
function availableCyberHosts(wiz,item) {
  const host=item.capacity&&item.capacity.host;if(!host)return [];
  const accepted=cyberFoundationNames(host),all=cyberPhysicalHosts(wiz);
  return all.filter(candidate=>accepted.some(name=>String(candidate.name||'').toLowerCase().startsWith(name))).filter(candidate=>{
    const total=num(candidate.capacity&&candidate.capacity.slots_total)||4;
    const used=wiz.cyberware.filter(option=>cyberHostIds(option).includes(candidate.instance_id||candidate.id)).reduce((sum,option)=>sum+cyberOptionSlots(option),0);
    return total-used>=cyberOptionSlots(item);
  });
}
async function chooseCyberHost(hosts, item) {
  const required=item.capacity?.hosts_required||1;
  if (hosts.length < required) return null;
  if (hosts.length === required) return required===1?hosts[0]:hosts.slice(0,required);
  return new Promise(resolve=>{const selected=new Set(),modal=openModal(`<h2>${T('Choose host','Выберите host')} · ${esc(item.name)}</h2><p>${T(`Select ${required} different foundations.`,`Выберите разные foundations: ${required}.`)}</p><div class="choice-card-grid">${hosts.map((host,index)=>{const id=host.instance_id||host.id,total=num(host.capacity?.slots_total)||4,used=state.wizard.cyberware.filter(option=>(option.host_instances||[option.host_instance]).includes(id)).reduce((sum,option)=>sum+cyberOptionSlots(option),0),after=used+cyberOptionSlots(item);return `<button class="choice-card" data-host-index="${index}"><b>${esc(host.custom_name||host.name)} #${index+1}</b><span>Slots ${used}/${total} → ${after}/${total}</span></button>`;}).join('')}</div><div class="row mt"><button id="host-cancel">${T('Cancel','Отмена')}</button><button id="host-confirm" class="btn-primary" disabled>${T('Install','Установить')}</button></div>`,true);$$('[data-host-index]',modal).forEach(button=>button.onclick=()=>{const index=Number(button.dataset.hostIndex);if(selected.has(index))selected.delete(index);else if(selected.size<required)selected.add(index);button.classList.toggle('selected',selected.has(index));$('#host-confirm',modal).disabled=selected.size!==required;});$('#host-confirm',modal).onclick=()=>{const result=[...selected].map(index=>hosts[index]);closeModal();resolve(required===1?result[0]:result);};$('#host-cancel',modal).onclick=()=>{closeModal();resolve(null);};});
}

function catalogRequirementStatus(wiz,item) {
  const failures=[];
  if(item.capacity&&item.capacity.host&&!pairedCyberlegFoundation(item)&&availableCyberHosts(wiz,item).length<(item.capacity.hosts_required||1))failures.push(`${T('Requires available','Требуется доступный')} ${(item.capacity.hosts_required||1)}× ${item.capacity.host}`);
  const names=[...wiz.cyberware.map(x=>x.name.toLowerCase()),...(wiz.freeNeuroport?['neuroport']:[])];
  for(const req of item.requirements||[]){if(req.kind==='stat'&&(num(wiz.stats[req.stat])||0)<req.minimum)failures.push(`${req.stat} ${req.minimum}`);if(req.kind==='item'){const wanted=req.value.toLowerCase().replace(/^2×\s*/,'');if(!names.some(name=>wanted.includes(name)||name.includes(wanted)))failures.push(req.value);}}
  return failures;
}
function isStyleTab(tab){return tab[0]==='fashion'||tab[0]==='fashionware';}
function canAffordShopItem(wiz,item,tab){return isStyleTab(tab)?wiz.fashionCost+(item.price||0)<=FASHION_BUDGET:canAffordCreationItem(wiz,item,item.price||0);}
function itemSelected(wiz,item){const id=item.variant_id||item.id;return wiz.gear.some(x=>x.key===id)||wiz.fashion.some(x=>x.key===id)||wiz.cyberware.some(x=>x.id===item.id)||wiz.fashionware.some(x=>x.id===item.id);}
function renderCompareModal(items){if(items.length<2){toast(T('Select at least two items to compare.','Выберите минимум два предмета.'),true);return;}const keys=[...new Set(items.flatMap(item=>Object.keys(item.mechanics||{})))];openModal(`<h2>${T('Compare Items','Сравнение предметов')}</h2><div class="table-scroll"><table class="rtable compare-table"><tr><th>Stat</th>${items.map(item=>`<th>${esc(item.name)}</th>`).join('')}</tr><tr><th>Price</th>${items.map(item=>`<td>${money(item.price)}</td>`).join('')}</tr>${keys.map(key=>`<tr><th>${esc(key.replace(/_/g,' '))}</th>${items.map(item=>{const value=(item.mechanics||{})[key];return `<td>${esc(value&&typeof value==='object'?(value.notation||JSON.stringify(value)):(value??'—'))}</td>`;}).join('')}</tr>`).join('')}</table></div>`,true);}

async function wizLoadShopList() {
  const wiz=state.wizard,box=$('#wiz-shop-results');if(!box)return;
  const tab=WIZ_SHOP_CATS.find(row=>row[0]===wiz.shopTab)||WIZ_SHOP_CATS[0], scrollKey=`shop:${tab[0]}`;
  box.innerHTML=spinner();wiz._shopCache=wiz._shopCache||{};
  for(const cat of tab[3])if(!wiz._shopCache[cat]){const response=await api('/api/items?'+new URLSearchParams({cat,limit:500}));wiz._shopCache[cat]=response.items;}
  let items=tab[3].flatMap(cat=>wiz._shopCache[cat]||[]).filter(item=>item.price!=null);
  if(tab[0]==='chrome'){items=items.filter(item=>!String(item.fields?.Type||'').toLowerCase().includes('fashionware'));const mode=wiz.cyberFilter||'all';if(['foundation','option','standalone'].includes(mode))items=items.filter(item=>item.cyberware_class===mode);if(mode==='installed')items=items.filter(item=>wiz.cyberware.some(selected=>selected.id===item.id));if(mode==='missing')items=items.filter(item=>catalogRequirementStatus(wiz,item).length>0);}
  if(tab[0]==='fashionware')items=items.filter(item=>String(item.fields?.Type||'').toLowerCase().includes('fashionware'));
  if(tab[0]==='fashion')items=items.filter(item=>item.cat==='fashion');
  if(tab[0]==='armor')items=armorPurchaseVariants(items);
  const query=String(wiz.shopQ||'').trim().toLowerCase(),filters=wiz.shopFilters||{};
  if(query)items=items.filter(item=>[item.variant_name,item.name,itemVisibleType(item),item.desc].some(value=>String(value||'').toLowerCase().includes(query)));
  if(filters.affordable)items=items.filter(item=>canAffordShopItem(wiz,item,tab));
  if(filters.selected)items=items.filter(item=>itemSelected(wiz,item));
  if(filters.type&&filters.type!=='all')items=items.filter(item=>itemVisibleType(item)===filters.type);
  if(filters.source&&filters.source!=='all')items=items.filter(item=>String(item.source||'').split(/\n/).some(source=>source.startsWith(filters.source)));
  if(num(filters.maxPrice)!=null)items=items.filter(item=>(item.price||0)<=num(filters.maxPrice));
  const sort = filters.sort || 'name';
  items.sort((a,b) => {
    if(tab[0]==='chrome'){const rank={foundation:0,option:1,standalone:2},diff=(rank[a.cyberware_class]??3)-(rank[b.cyberware_class]??3);if(diff)return diff;}
    if (sort === 'price') return (a.price||0)-(b.price||0) || byNameRu(a,b);
    if (sort === 'damage') return ((b.mechanics?.damage?.average)||0)-((a.mechanics?.damage?.average)||0) || byNameRu(a,b);
    if (sort === 'rof') return (num(b.mechanics?.rof)||0)-(num(a.mechanics?.rof)||0) || byNameRu(a,b);
    if (sort === 'sp') return (num(b.sp ?? b.mechanics?.sp)||0)-(num(a.sp ?? a.mechanics?.sp)||0) || byNameRu(a,b);
    if (sort === 'hl') return (num(a.hl)||0)-(num(b.hl)||0) || byNameRu(a,b);
    return byNameRu(a,b);
  });wiz._currentShopItems=items;
  const selectedTypes=[...new Set(items.map(item=>itemVisibleType(item)))].sort();
  const typeSelect=$('#wiz-shop-type');if(typeSelect&&typeSelect.options.length<=1){typeSelect.insertAdjacentHTML('beforeend',selectedTypes.map(type=>`<option value="${esc(type)}" ${filters.type===type?'selected':''}>${esc(type)}</option>`).join(''));}
  const sources=[...new Set(items.flatMap(item=>String(item.source||'').split(/\n/).map(source=>source.split(/\s+\d/)[0]).filter(Boolean)))].sort();
  const sourceSelect=$('#wiz-shop-source');if(sourceSelect&&sourceSelect.options.length<=1)sourceSelect.insertAdjacentHTML('beforeend',sources.map(source=>`<option value="${esc(source)}" ${filters.source===source?'selected':''}>${esc(source)}</option>`).join(''));
  const rowHtml=item=>{const duplicate=isForbiddenDuplicate(wiz,item),affordable=canAffordShopItem(wiz,item,tab),requirements=tab[0]==='chrome'?catalogRequirementStatus(wiz,item):[],disabled=duplicate||!affordable||requirements.length>0,suggested=tab[0]==='fashion'&&String(wiz.lifepath.clothing||'')&&[item.name,item.mechanics?.fashion_style].some(value=>String(value||'').toLowerCase().includes(String(wiz.lifepath.clothing).toLowerCase()));const compatible=(tab[0]==='ammo'||item.cat==='gun_upgrades')?ammoCompatibility(item,wiz):(item.cat==='vehicles_upgrades'&&wiz.gear.some(selected=>selected.cat==='vehicles')?[T('selected vehicle','выбранный транспорт')]:(item.cat==='programs'&&wiz.gear.some(selected=>selected.cat==='net_stuff'&&String(selected.name).toLowerCase().includes('cyberdeck'))?[T('selected Cyberdeck','выбранный Cyberdeck')]:[]));const compared=(wiz.compareItems||[]).includes(item.id);return `<article class="catalog-card ${disabled?'unaffordable':''}"><div style="display:flex;gap:8px">${itemThumb(item.cat)} ${compatible.length?'compatible':''} ${suggested?'recommended':''}"><div class="catalog-card-main"><label class="compare-check"><input type="checkbox" data-compare-id="${esc(item.id)}" ${compared?'checked':''}> ${T('Compare','Сравнить')}</label><h4>${esc(item.variant_name||item.name)}${suggested?` <span class="tag recommended-tag">${T('Lifepath Style','Стиль Lifepath')}</span>`:''}</h4><div class="mechanic-chips">${itemMechanicChips(item)}${item.mechanics?.skill?(()=>{const meta=state.meta.skills.find(row=>row[1]===item.mechanics.skill),stat=meta&&meta[2],statValue=stat==='EMP'?(wizDerived().emp_cur??wiz.stats.EMP):wiz.stats[stat];return `<span class="chip character-aware"><b>${esc(item.mechanics.skill)} BASE</b> ${(num(statValue)||0)+(num(wiz.skills[item.mechanics.skill])||0)}</span>`;})():''}</div>${compatible.length?`<div class="compatibility-ok">✓ ${T('Compatible with selected loadout','Совместимо с выбранным снаряжением')}: ${compatible.map(esc).join(', ')}</div>`:''}${requirements.length?`<div class="requirement-fail">⛔ ${requirements.map(esc).join(' · ')}${item.capacity?.host?` <button class="btn-sm" data-show-foundation="${esc(item.capacity.host)}">${T('View Foundations','Показать Foundations')}</button>`:''}</div>`:''}<div class="small muted">${esc(item.source||'')}</div></div></div><div class="catalog-card-actions"><span class="price">${money(item.price)}</span><button class="info-btn" data-shop-info="${esc(item.variant_id||item.id)}">i</button><button class="btn-sm" data-shop-add="${esc(item.variant_id||item.id)}" ${disabled?'disabled':''}>＋</button></div></article>`;};
  box.innerHTML=items.length?groupedItemsHtml(items,rowHtml,shopCategoryLabel(tab)):`<div class="empty">${T('Nothing matches these filters.','Ничего не найдено.')}</div>`;
  requestAnimationFrame(()=>box.scrollTop=(wiz.scrolls||{})[scrollKey]||0);box.onscroll=()=>{wiz.scrolls[scrollKey]=box.scrollTop;};
  $$('[data-compare-id]',box).forEach(input=>input.onchange=()=>{wiz.compareItems=wiz.compareItems||[];if(input.checked&&!wiz.compareItems.includes(input.dataset.compareId)){if(wiz.compareItems.length>=3){input.checked=false;toast(T('Compare supports up to three items.','Можно сравнить не более трёх предметов.'),true);return;}wiz.compareItems.push(input.dataset.compareId);}if(!input.checked)wiz.compareItems=wiz.compareItems.filter(id=>id!==input.dataset.compareId);saveWizardDraft();const count=$('#compare-count');if(count)count.textContent=wiz.compareItems.length;});
  $$('[data-show-foundation]',box).forEach(btn=>btn.onclick=()=>{wiz.cyberFilter='foundation';wiz.shopQ=btn.dataset.showFoundation;renderWizard();});
  $$('[data-shop-info]',box).forEach(btn=>btn.onclick=()=>{const item=items.find(x=>(x.variant_id||x.id)===btn.dataset.shopInfo);if(item)showCreationItemInfo(item);});
  $$('[data-shop-add]',box).forEach(btn=>btn.onclick=async()=>{const item=items.find(x=>(x.variant_id||x.id)===btn.dataset.shopAdd);if(!item)return;const price=item.price||0;if(isForbiddenDuplicate(wiz,item)||!canAffordShopItem(wiz,item,tab))return;
    const shared={desc:item.desc||'',fields:item.fields||{},source:item.source||'',mechanics:item.mechanics||{},requirements:item.requirements||[],capacity:item.capacity||{}};
    if(tab[0]==='fashion'){const existing=wiz.fashion.find(x=>x.key===item.id);if(existing)existing.qty=(existing.qty||1)+1;else wiz.fashion.push({key:item.id,cat:item.cat,name:item.name,price,qty:1,type:itemVisibleType(item,'Fashion'),...shared});wiz.fashionCost+=price;}
    else if(tab[0]==='fashionware'){const existing=wiz.fashionware.find(x=>x.id===item.id);if(existing)existing.qty=(existing.qty||1)+1;else wiz.fashionware.push({id:item.id,name:item.name,hl:item.hl||0,price,qty:1,type:String(item.fields?.Type||'Fashionware'),...shared});wiz.fashionCost+=price;}
    else if(item.cat==='cyberware'){const needsHost=(item.capacity||{}).host&&!pairedCyberlegFoundation(item),hosts=needsHost?availableCyberHosts(wiz,item):[],host=needsHost?await chooseCyberHost(hosts,item):null;if(needsHost&&!host)return;const side=chooseCyberSide(wiz,item);if(cyberSideRequired(item)&&!side)return;const instance=clientInstanceId();wiz.cyberware.push({id:item.id,instance_id:instance,name:item.name,hl:item.hl||0,price,type:String(item.fields?.Type||'Cyberware'),installation_side:side||'',host_instance:host?(Array.isArray(host)?(host[0].instance_id||host[0].id):(host.instance_id||host.id)):'',host_instances:host?(Array.isArray(host)?host.map(value=>value.instance_id||value.id):[host.instance_id||host.id]):[],...shared});wiz.chromeCost+=price;}
    else if(item.cat==='armor'){wiz.gear.push({key:item.variant_id,source_key:item.id,cat:'armor',name:item.name,display_name:item.variant_name,location:item.purchase_location,price,qty:1,sp:item.sp,penalties:{...(item.penalties||{})},armor_bundled:!!item.armor_bundled,type:itemVisibleType(item,'Armor'),...shared});wiz.gearCost+=price;}
    else{const existing=wiz.gear.find(x=>x.key===item.id);if(existing)existing.qty=(existing.qty||1)+1;else wiz.gear.push({key:item.id,cat:item.cat,name:item.name,price,qty:1,damage:item.damage||null,sp:item.sp,type:itemVisibleType(item,shopCategoryLabel(tab)),...shared});wiz.gearCost+=price;}
    renderWizard();toast(`${T('Added','Добавлено')}: ${item.variant_name||item.name}`);});
}

function roleBenefitItems(wiz){const out=[];if(wiz.role==='Exec')out.push({key:'role-exec-businesswear',name:'Businesswear (Teamwork)',type:'Role Benefit',qty:1,price:0,role_benefit:true,desc:'Corporate clothing supplied by Teamwork.'});if(wiz.role==='Nomad')for(const choice of (wiz.roleSetup.moto_choices||[]).filter(Boolean))out.push({key:'role-nomad-'+choice,name:choice,type:'Nomad Family Access',qty:1,price:0,role_benefit:true});return out;}
function equipmentWarnings(wiz){const warnings=[];const weapons=wiz.gear.filter(item=>item.cat==='guns'),ammo=wiz.gear.filter(item=>item.cat==='ammo');for(const weapon of weapons){const type=String(weapon.mechanics?.type||weapon.fields?.Type||'').toLowerCase();if(!ammo.some(item=>ammoCompatibility(item,wiz).includes(type)))warnings.push(`${weapon.name}: ${T('no compatible ammunition selected','не выбраны совместимые боеприпасы')}`);}if(!wiz.armor.body)warnings.push(T('No Body Armor equipped','Не надета броня для тела'));if(!wiz.armor.head)warnings.push(T('No Head Armor equipped','Не надета броня для головы'));return warnings;}
async function generateRandomOutfit(){const wiz=state.wizard;wiz._shopCache=wiz._shopCache||{};if(!wiz._shopCache.fashion){const response=await api('/api/items?'+new URLSearchParams({cat:'fashion',limit:500}));wiz._shopCache.fashion=response.items;}const preferred=String(wiz.outfitStyle||wiz.lifepath.clothing||'').toLowerCase();let pool=wiz._shopCache.fashion.filter(item=>item.price!=null);const matching=pool.filter(item=>item.name.toLowerCase().includes(preferred)||String(item.mechanics?.fashion_style||'').toLowerCase()===preferred);if(matching.length)pool=matching;pool=[...pool].sort(()=>Math.random()-.5);const picked=[];let spent=0;for(const item of pool){if(picked.length>=6)break;if(spent+(item.price||0)<=FASHION_BUDGET){picked.push(item);spent+=item.price||0;}}if(!picked.length){toast(T('No affordable outfit found.','Не удалось подобрать комплект.'),true);return;}if(!confirm(`${T('Replace current Fashion selection with','Заменить выбранную одежду на')} ${picked.map(x=>x.name).join(', ')}?`))return;wiz.fashion=picked.map(item=>({key:item.id,cat:'fashion',name:item.name,price:item.price,qty:1,type:itemVisibleType(item,'Fashion'),desc:item.desc||'',fields:item.fields||{},source:item.source||'',mechanics:item.mechanics||{}}));wiz.fashionCost=spent+wiz.fashionware.reduce((sum,item)=>sum+(item.price||0)*(item.qty||1),0);renderWizard();}
function cartSectionHtml(title,items){return items.length?`<section class="catalog-group"><h4 class="catalog-type">${esc(title)} <span>${items.length}</span></h4>${items.join('')}</section>`:'';}
function combinedCartHtml(wiz){const rows=[];for(const item of roleBenefitItems(wiz))rows.push({type:item.type,html:`<div class="inv-row role-benefit"><span class="iname">🎁 ${esc(item.name)}</span><span class="tag">Role Benefit</span><span class="price">${money(0)}</span></div>`});
  const seen=new Set();wiz.cyberware.forEach((item,index)=>{if(seen.has(item.id))return;seen.add(item.id);const qty=wiz.cyberware.filter(x=>x.id===item.id).length;rows.push({type:itemVisibleType(item,'Cyberware'),html:`<div class="inv-row"><span class="iname">🦾 ${esc(item.name)}</span>${quantityControl('chrome',index,qty,String(item.name).toLowerCase()!=='neuroport'&&!(item.capacity||{}).unique&&(!(item.capacity||{}).host||pairedCyberlegFoundation(item)||availableCyberHosts(wiz,item).length>0))}<span class="hl-badge">HL ${(item.hl||0)*qty}</span><span class="price">${money((item.price||0)*qty)}</span><button class="info-btn" data-cart-info="chrome|${index}">i</button></div>`});});
  wiz.fashionware.forEach((item,index)=>rows.push({type:'Fashionware',html:`<div class="inv-row"><span class="iname">💠 ${esc(item.name)}</span>${quantityControl('fashionware',index,item.qty||1,true)}<span class="price">${money((item.price||0)*(item.qty||1))}</span><button class="info-btn" data-cart-info="fashionware|${index}">i</button></div>`}));
  wiz.fashion.forEach((item,index)=>rows.push({type:itemVisibleType(item,'Fashion'),html:`<div class="inv-row"><span class="iname">🧥 ${esc(item.name)}</span>${quantityControl('style',index,item.qty||1,true)}<span class="price">${money((item.price||0)*(item.qty||1))}</span><button class="info-btn" data-cart-info="style|${index}">i</button></div>`}));
  wiz.gear.forEach((item,index)=>{const equip=item.cat==='armor'?`<button class="btn-sm" data-equip-armor="${index}">${T('Equip','Надеть')}</button>`:'';rows.push({type:itemVisibleType(item,'Gear'),html:`<div class="inv-row"><span class="iname">${esc(item.display_name||item.name)}</span>${quantityControl('gear',index,item.qty||1,item.cat!=='armor')}${itemMechanicChips(item)}<span class="price">${money((item.price||0)*(item.qty||1))}</span>${equip}<button class="info-btn" data-cart-info="gear|${index}">i</button></div>`});});
  const groups=new Map();for(const row of rows){if(!groups.has(row.type))groups.set(row.type,[]);groups.get(row.type).push(row.html);}return [...groups.entries()].map(([type,content])=>cartSectionHtml(type,content)).join('')||`<div class="empty">${T('No starting gear selected.','Стартовое снаряжение не выбрано.')}</div>`;}

function wizStepShoppingHtml(){const wiz=state.wizard,d=wizDerived(),remaining=creationMainRemaining(wiz),styleRemaining=FASHION_BUDGET-wiz.fashionCost,warnings=equipmentWarnings(wiz),paidPort=hasPaidNeuroport(wiz);return `<div class="shopping-budgets sticky-budget panel accent mb"><div><b>Main</b><span>${money(remaining)} ${T('remaining','осталось')}</span></div><div><b>Style</b><span>${money(styleRemaining)} ${T('remaining','осталось')}</span></div><div><b>Humanity</b><span>${d.humanity_cur??'—'} / ${d.humanity_max??'—'} · EMP ${d.emp_cur??'—'}</span></div></div>
  <div class="neuroport-choices mb"><article class="choice-card ${wiz.freeNeuroport?'selected':''} ${paidPort?'disabled':''}"><h3>CEMK Starting Neuroport</h3><p>0eb · 0 HL · Humanity exempt</p><button data-neuro-choice="free" ${paidPort?'disabled':''}>${wiz.freeNeuroport?T('Selected','Выбран'):T('Select','Выбрать')}</button></article><article class="choice-card ${paidPort?'selected':''} ${wiz.freeNeuroport?'disabled':''}"><h3>Standard Neuroport</h3><p>1,000eb · 7 HL</p><button data-shop-tab-jump="chrome">${paidPort?T('Purchased','Куплен'):T('Find in Cyberware','Найти в Cyberware')}</button></article></div>
  <details class="panel mb sold-soul" ${wiz.soldSoul?'open':''}><summary><label class="checkbox"><input type="checkbox" id="wiz-soul" ${wiz.soldSoul?'checked':''}> Sell Your Soul · +1,500eb Cyberware-only</label></summary><div class="grid cols-2 mt"><label class="f"><span>Patron *</span><select id="wiz-patron"><option value="">${T('Choose…','Выберите…')}</option>${['Corporation','Military','Gang','Government Agency','Other Organization'].map(value=>`<option ${wiz.patron===value?'selected':''}>${value}</option>`).join('')}</select></label><label class="f"><span>Obligation *</span><input id="wiz-obligation" value="${esc(wiz.obligation||'')}" placeholder="${T('What do you owe them?','Что вы им должны?')}"></label></div></details>
  <div class="shopping-layout"><div class="shopping-catalog"><div class="tabs mb" id="wiz-shop-tabs">${WIZ_SHOP_CATS.map(tab=>`<button data-shop-tab="${tab[0]}" class="${wiz.shopTab===tab[0]?'active':''}">${shopCategoryLabel(tab)}</button>`).join('')}</div>${wiz.shopTab==='chrome'?`<div class="segmented cyber-filters mb">${[['all','All'],['foundation','Foundations'],['option','Options'],['standalone','Standalone'],['installed','Installed'],['missing','Requirements Missing']].map(([id,label])=>`<button data-cyber-filter="${id}" class="${(wiz.cyberFilter||'all')===id?'active':''}">${label}</button>`).join('')}</div>`:''}<div class="shop-tools"><input id="wiz-shop-q" value="${esc(wiz.shopQ||'')}" placeholder="${T('Search name, description, or Type…','Поиск по названию, описанию или Type…')}"><select id="wiz-shop-type"><option value="all">All Types</option></select><select id="wiz-shop-source"><option value="all">All Sources</option></select><input id="wiz-shop-max-price" type="number" min="0" step="50" value="${esc(wiz.shopFilters?.maxPrice||'')}" placeholder="Max eb" style="width:100px"><select id="wiz-shop-sort"><option value="name">Name</option><option value="price" ${wiz.shopFilters?.sort==='price'?'selected':''}>Price</option><option value="damage" ${wiz.shopFilters?.sort==='damage'?'selected':''}>Damage</option><option value="rof" ${wiz.shopFilters?.sort==='rof'?'selected':''}>ROF</option><option value="sp" ${wiz.shopFilters?.sort==='sp'?'selected':''}>SP</option><option value="hl" ${wiz.shopFilters?.sort==='hl'?'selected':''}>HL</option></select><label><input type="checkbox" id="shop-affordable" ${wiz.shopFilters?.affordable?'checked':''}> ${T('Affordable','Доступные')}</label><label><input type="checkbox" id="shop-selected" ${wiz.shopFilters?.selected?'checked':''}> ${T('Selected','Выбранные')}</label><button class="btn-sm" id="compare-items">${T('Compare','Сравнить')} (<span id="compare-count">${(wiz.compareItems||[]).length}</span>)</button>${wiz.shopTab==='fashion'?`<select id="outfit-style"><option value="">${T('Lifepath Style','Стиль Lifepath')}</option>${['Bag Lady Chic','Generic Chic','Leisurewear','Urban Flash','Businesswear','High Fashion','Bohemian','Asia Pop','Gang Colors','Nomad Leathers'].map(style=>`<option value="${style}" ${wiz.outfitStyle===style?'selected':''}>${style}</option>`).join('')}</select><button class="btn-sm" id="random-outfit">🎲 ${T('Generate Outfit','Создать комплект')}</button>`:''}</div><div id="wiz-shop-results" class="catalog-scroll shop-scroll">${spinner()}</div></div>
  <aside class="shopping-cart"><h3>${T('Selected Starting Gear','Выбранное снаряжение')}</h3><div class="equipped-summary"><span><b>Body:</b> ${wiz.armor.body?esc(wiz.armor.body.name):'—'}</span><span><b>Head:</b> ${wiz.armor.head?esc(wiz.armor.head.name):'—'}</span></div>${warnings.length?`<div class="readiness-warnings">${warnings.map(w=>`<div>⚠ ${esc(w)}</div>`).join('')}${warnings.some(w=>w.includes('ammunition')||w.includes('боеприпасы'))?`<button class="btn-sm mt" data-shop-tab="ammo">${T('Find compatible ammunition','Найти совместимые боеприпасы')}</button>`:''}</div>`:''}<div id="wiz-shop-cart">${combinedCartHtml(wiz)}</div></aside></div>`;}

/* ---------- Шаг 7: Итог ---------- */

function cyberwareRequirementErrors(w) {
  const chrome = [...w.cyberware, ...w.fashionware];
  const names = chrome.map(c => String(c.name || '').toLowerCase());
  const inventoryNames = [...w.gear, ...w.fashion].map(i => String(i.name || '').toLowerCase());
  const hasPort = w.freeNeuroport || names.includes('neuroport');
  const foundationNames = {
    cybereye: new Set(['cybereye', 'sponsored cybereye']),
    cyberarm: new Set(['cyberarm', 'neo-soviet cyberarm']),
    cyberleg: new Set(['cyberleg', 'romanova cyberlegs', 'rocklin augmentics skydrivers']),
    audio: new Set(['cyberaudio suite', 'discount cyberaudio suite']),
    socket: new Set(['chipware socket', 'budget chipware socket']),
  };
  const count = key => names.filter(name => foundationNames[key].has(name)).reduce((total,name)=>total+(key==='cyberleg'&&['romanova cyberlegs','rocklin augmentics skydrivers'].includes(name)?2:1),0);
  const errors = [], body = num(w.stats.BODY) || 0;
  for (const item of chrome) {
    const d = String(item.desc || '').toLowerCase().replace(/\n/g, ' ');
    let missing = '';
    if (d.includes('requires a modular finger cyberhand') && !names.includes('modular finger cyberhand')) missing = 'Modular Finger Cyberhand';
    else if ((d.includes('requires a cyberaudio suite') || d.includes('cyberaudio option')) && !count('audio')) missing = 'Cyberaudio Suite';
    else if (d.includes('cybereye option') && !count('cybereye')) missing = 'Cybereye';
    else if (d.includes('cyberarm option') && !d.includes('can be installed as the only piece of cyberware in a meat arm') && !count('cyberarm')) missing = 'Cyberarm';
    else if (d.includes('cyberleg option') && !count('cyberleg')) missing = 'Cyberleg';
    else if (d.includes('cyberlimb option') && !(count('cyberarm') || count('cyberleg'))) missing = 'Cyberarm или Cyberleg';
    else if (d.includes('neuralware option') && !(hasPort || names.includes('neural link'))) missing = 'Neural Link или Neuroport';
    else if ((d.includes('requires chipware socket') || d.includes('requires a chipware socket')) && !count('socket')) missing = 'Chipware Socket';
    else if ((d.includes('requires neural link') || d.includes('requires interface plugs and neural link')) && !(hasPort || names.includes('neural link'))) missing = 'Neural Link или Neuroport';
    else if (d.includes('requires neuroport cyberdeck port') && !names.includes('neuroport cyberdeck port')) missing = 'Neuroport Cyberdeck Port';
    else if (d.includes('requires neuroport') && !hasPort) missing = 'Neuroport';
    else if (d.includes('requires two cybereyes') && count('cybereye') < 2) missing = 'две Cybereye';
    else if (d.includes('requires a cybereye') && !count('cybereye')) missing = 'Cybereye';
    else if (d.includes('requires two cyberlegs') && count('cyberleg') < 2) missing = 'две Cyberleg';
    else if (d.includes('requires a cyberarm or cyberleg') && !(count('cyberarm') || count('cyberleg'))) missing = 'Cyberarm или Cyberleg';
    else if (d.includes('requires a cyberarm') && !count('cyberarm')) missing = 'Cyberarm';
    else if (d.includes('requires biomonitor') && !(hasPort || names.includes('biomonitor'))) missing = 'Biomonitor или Neuroport';
    else if (d.includes('requires skinweave or subdermal armor') && !(names.includes('skinweave') || names.includes('subdermal armor'))) missing = 'Skinweave или Subdermal Armor';
    else if (d.includes('requires a scrambler/descrambler') && !inventoryNames.some(n => n.includes('scrambler/descrambler'))) missing = 'Scrambler/Descrambler';
    else if (d.includes('requires chyron') && !(hasPort || names.includes('chyron'))) missing = 'Chyron или Neuroport';
    const bm = d.match(/requires body\s+(\d+)/);
    if (bm && body < Number(bm[1])) missing = `BODY ${bm[1]}`;
    const lm = d.match(/requires body\s+\d+\s+and\s+(two|2|3)\s+(?:installations of )?grafted muscle/);
    if (lm) {
      const needed = lm[1] === '3' ? 3 : 2;
      if (names.filter(n => n === 'grafted muscle & bone lace').length < needed) missing = `${needed} установки Grafted Muscle & Bone Lace`;
    }
    if (missing) errors.push(`${item.name} требует: ${missing}`);
  }
  return errors;
}

function cyberSlotErrors(wiz) {
  const errors=[];
  for(const item of wiz.cyberware){if(item.capacity&&item.capacity.host&&!pairedCyberlegFoundation(item)&&!item.host_instance)errors.push(`${item.name}: ${T('no compatible cyberware host','нет совместимого host')}`);}
  const hosts=cyberPhysicalHosts(wiz);
  for(const host of hosts){const id=host.instance_id||host.id,total=num(host.capacity&&host.capacity.slots_total)||0;if(!total)continue;const used=wiz.cyberware.filter(item=>cyberHostIds(item).includes(id)).reduce((sum,item)=>sum+cyberOptionSlots(item),0);if(used>total)errors.push(`${host.name}: Option Slots ${used}/${total}`);}
  return errors;
}
function wizValidationErrors() {
  const w=state.wizard,errors=[],statSpent=wizStatSpent(),skillSpent=wizSkillSpent();
  if(!w.role)errors.push(T('Role: choose a Role','Роль: выберите роль'));
  if(statSpent!==(state.meta.stat_points||62))errors.push(`${T('Characteristics','Характеристики')}: ${statSpent}/62`);
  if(skillSpent!==(state.meta.skill_points||86))errors.push(`${T('Skills','Навыки')}: ${skillSpent}/86`);
  for(const skill of state.meta.must_skills||[])if(!wizMustOk(skill))errors.push(`${T('Required Skill','Обязательный навык')}: ${skill} 2+`);
  for(const [name,lvl] of Object.entries(wizChar().skills))if(lvl>(state.meta.skill_max||6))errors.push(`${name}: ${T('maximum at creation is 6','максимум при создании — 6')}`);
  if(!w.nativeLanguage)errors.push(T('Lifepath: choose a Cultural Language','Lifepath: выберите культурный язык'));
  if(!String(w.handle||'').trim())errors.push('Identity: Handle');
  const commonMissing=lpAllFields().filter(([key])=>!w.lifepath[key]).length;if(commonMissing)errors.push(`${T('Common Lifepath missing','Не заполнен общий Lifepath')}: ${commonMissing}`);
  if(w.role){const missing=lpRoleField(w.role).filter(([key])=>!w.roleLifepath[key]).length;if(missing)errors.push(`${w.role} Role-Based Lifepath: ${missing}`);}
  if(creationMainRemaining(w)<0)errors.push(T('Shopping: Main Budget exceeded','Закупка: превышен основной бюджет'));
  if(w.fashionCost>FASHION_BUDGET)errors.push(T('Shopping: Style Budget exceeded','Закупка: превышен Style Budget'));
  for(const [base] of SUB_SKILL_BASES){const children=w.subSkills.filter(sub=>sub.base===base&&!sub.native&&(sub.lvl||0)>0);if(children.some(sub=>!String(sub.name||'').trim()))errors.push(`${base}: ${T('a non-zero specialization needs a name','ненулевой специализации нужно название')}`);const names=children.map(sub=>String(sub.name).trim().toLowerCase());if(new Set(names).size!==names.length)errors.push(`${base}: ${T('duplicate specialization','дублирующаяся специализация')}`);if(wizSubAllocated(base)>(num(w.skills[base])||0))errors.push(`${base}: children > parent pool`);}
  const paidPorts=w.cyberware.filter(item=>String(item.name).toLowerCase()==='neuroport').length;if(paidPorts+(w.freeNeuroport?1:0)>1)errors.push(T('Only one Neuroport is allowed','Допустим только один Neuroport'));if((w.cyberware.length||w.fashionware.length||w.soldSoul)&&!w.freeNeuroport&&!paidPorts)errors.push(T('Cyberware requires a Neuroport','Для Cyberware нужен Neuroport'));
  errors.push(...cyberwareRequirementErrors(w),...cyberSlotErrors(w));
  if(w.soldSoul&&(!w.patron||!String(w.obligation||'').trim()))errors.push(T('Sell Your Soul: choose a Patron and Obligation','Sell Your Soul: выберите покровителя и обязательство'));
  if(w.role==='Tech'){const ranks=['field','upgrade','fabrication','invention'].map(key=>num(w.roleSetup[key])||0);if(ranks.reduce((a,b)=>a+b,0)!==8||ranks.some(value=>value>4))errors.push('Tech: Maker 8 / max 4');}
  if(w.role==='Medtech'){const ranks=['surgery','pharma','cryo'].map(key=>num(w.roleSetup[key])||0);if(ranks.reduce((a,b)=>a+b,0)!==4)errors.push('Medtech: Medicine 4');}
  if(w.role==='Exec'&&!w.roleSetup.team_member)errors.push('Exec: Team Member');
  if(w.role==='Nomad'&&(!Array.isArray(w.roleSetup.moto_choices)||w.roleSetup.moto_choices.length!==4||w.roleSetup.moto_choices.some(value=>!value)))errors.push('Nomad: four Moto choices');
  return errors;
}
function validationTarget(message){if(/Role|Tech|Medtech|Exec|Nomad/.test(message)&&!/Lifepath/.test(message))return 1;if(/Lifepath|Identity|Language/.test(message))return 2;if(/Characteristics/.test(message))return 3;if(/Skill|Language \(|Local Expert|Martial Arts|Science|Instrument|parent pool/.test(message))return 4;return 5;}

function characterSkillLevel(char, name) {
  return Math.max(0, num((char.skills || {})[name]) || 0);
}

function specializedChildren(char, base) {
  const prefix = base + ' (';
  const children = Object.entries(char.skills || {}).filter(([name]) => name.startsWith(prefix) && name.endsWith(')'))
    .map(([name, lvl]) => ({ name: name.slice(prefix.length, -1), lvl: num(lvl) || 0 }));
  for (const saved of (char.skill_specializations || []).filter(row => row.base === base)) {
    if (!children.some(child => child.name === saved.name)) children.push({ name: saved.name, lvl: num(saved.lvl) || 0, native: !!saved.native });
  }
  return children.sort((a, b) => a.name.localeCompare(b.name, 'ru'));
}

function paidSpecializationLevel(char, base, child) { return base==='Language'&&child.name===char.native_language?Math.max(0,child.lvl-4):child.lvl; }

function characterSkillPool(char, base) {
  if (char.skill_pools && char.skill_pools[base] != null) return num(char.skill_pools[base]) || 0;
  return specializedChildren(char, base).filter(child => !(base === 'Language' && child.name === char.native_language && child.lvl === 4)).reduce((a, child) => a + child.lvl, 0);
}

function rollD10Exploding() {
  const first=1+Math.floor(Math.random()*10);let total=first,detail=`${first}`;
  if(first===10){const extra=1+Math.floor(Math.random()*10);total+=extra;detail+=` + ${extra}`;}
  if(first===1){const extra=1+Math.floor(Math.random()*10);total-=extra;detail+=` − ${extra}`;}
  return {total,detail};
}
function showCheckRoll(name,base){const roll=rollD10Exploding(),total=roll.total+base;openModal(`<h2>🎲 ${esc(name)}</h2><div class="roll-result"><b>${total}</b><span>1d10 (${esc(roll.detail)}) + BASE ${base}</span></div>`);}

function fullSkillsTableHtml(char, derived, interactive) {
  const specialized = new Set(SUB_SKILL_BASES.map(row => row[0]));
  let lastCat = null;
  const rows = [];
  for (const [cat, name, stat, is2] of state.meta.skills) {
    if (cat !== lastCat) { rows.push(`<div class="skill-cat">${esc(skillCategoryLabel(cat))}</div>`); lastCat = cat; }
    const lvl = specialized.has(name) ? characterSkillPool(char, name) : characterSkillLevel(char, name);
    const statBase=(char.stats||{})[stat],statBreakdown=derived.effects?.stats?.[stat];
    const statValue=statBreakdown?.effective??(stat==='EMP'?(derived.emp_cur??statBase):statBase);
    const skillEffect=derived.effects?.skills?.[name],checkModifier=num(skillEffect?.check_modifier)||0,checkBase=(num(statValue)||0)+lvl+checkModifier;
    const statDisplay=statBreakdown&&statBreakdown.base!==statBreakdown.effective?`${statBreakdown.base}→${statBreakdown.effective}`:`${num(statValue)??0}`;
    rows.push(`<div class="skill-row ${specialized.has(name) ? 'skill-parent' : ''} ${lvl === 0 ? 'zero-level' : ''} ${checkModifier?'modified':''}">
      <button class="skill-name-btn sname" data-skill-info="${esc(name)}">${esc(name)} ${is2 ? '<span class="muted small">(×2)</span>' : '<span class="muted small">(×1)</span>'}</button>
      <span class="sstat">${esc(stat)} <b>${esc(statDisplay)}</b></span><span class="slvl"><b>${lvl}</b></span>${specialized.has(name)?`<span class="sbase"><small>Allocated ${specializedChildren(char,name).reduce((sum,child)=>sum+paidSpecializationLevel(char,name,child),0)} · Free ${Math.max(0,lvl-specializedChildren(char,name).reduce((sum,child)=>sum+paidSpecializationLevel(char,name,child),0))}</small></span><span></span>`:`<span class="sbase"><b>${checkBase}</b>${checkModifier?` <span class="chip effect-bonus">${checkModifier>0?'+':''}${checkModifier}</span>`:''}</span>${interactive?`<button class="mini-step" data-roll-check="${esc(name)}|${checkBase}">🎲</button>`:'<span></span>'}`}</div>`);
    if (specialized.has(name)) {
      for (const child of specializedChildren(char, name)) {
        rows.push(`<div class="skill-row subskill-row ${child.lvl === 0 ? 'zero-level' : ''}"><span class="sname subskill-name">↳ ${esc(child.name)}${name === 'Language' && child.name === char.native_language && child.lvl === 4 ? ' <span class="chip">культурный</span>' : ''}</span><span class="sstat">${esc(stat)} <b>${num(statValue) ?? 0}</b></span><span class="slvl"><b>${child.lvl}</b></span><span class="sbase"><b>${(num(statValue) || 0) + child.lvl}</b></span>${interactive?`<button class="mini-step" data-roll-check="${esc(name+' ('+child.name+')')}|${(num(statValue)||0)+child.lvl}">🎲</button>`:'<span></span>'}</div>`);
      }
    }
  }
  return `<div class="skill-table-head"><span>${T('Skill','Навык')}</span><span>STAT</span><span>${T('BASE LVL','БАЗ. УР.')}</span><span>${T('CHECK BASE','БАЗА ПРОВЕРКИ')}</span><span></span></div><div class="skill-list full-skill-list">${rows.join('')}</div>`;
}

function chromeGroupedHtml(items, withInfo) {
  const rows = items.map((item, index) => ({ type: itemVisibleType(item, 'Cyberware'), html: `<div class="inv-row"><span class="iname">${esc(item.name)}</span><span class="hl-badge">HL ${item.hl || 0}</span>${item.price != null ? `<span class="price">${money(item.price)}</span>` : ''}${withInfo ? `<button class="info-btn" data-owned-chrome="${index}">i</button>` : ''}</div>` }));
  const groups = new Map();
  for (const row of rows) { if (!groups.has(row.type)) groups.set(row.type, []); groups.get(row.type).push(row.html); }
  return [...groups.entries()].sort((a,b)=>a[0].localeCompare(b[0],'ru')).map(([type, content]) => cartSectionHtml(type, content)).join('') || '<div class="empty small">— чист от хрома —</div>';
}

function summaryInventoryHtml(items) {
  if(!items.length)return `<div class="empty">${T('None','Нет')}</div>`;
  return groupedItemsHtml(items.map((item,index)=>({...item,_summaryIndex:index})),item=>`<div class="inv-row"><span class="iname">${esc(item.display_name||item.name)}${(item.qty||1)>1?' ×'+item.qty:''}</span>${itemMechanicChips(item)}<span class="price">${money((item.price||0)*(item.qty||1))}</span><button class="info-btn" data-summary-item="${item._summaryIndex}">i</button></div>`,'Gear');
}
function cyberwareTreeHtml(items) {
  if (!items.length) return `<div class="empty">${T('No Cyberware','Нет Cyberware')}</div>`;
  const physicalParent=new Map();items.forEach(item=>{if(pairedCyberlegFoundation(item)){const id=item.instance_id||item.id;physicalParent.set(pairedCyberHostId(id),id);}});
  const children = new Map();
  items.forEach((item,index) => { const host=cyberHostIds(item)[0],parent=physicalParent.get(host)||host;if(parent){if(!children.has(parent))children.set(parent,[]);children.get(parent).push([item,index]);} });
  const roots = items.map((item,index)=>[item,index]).filter(([item])=>!item.host_instance);
  const row = (item,index,nested) => { const id=item.instance_id||item.key||item.id,total=num(item.capacity?.slots_total)||0,used=(children.get(id)||[]).reduce((sum,[child])=>sum+cyberOptionSlots(child),0),uses=cyberOptionSlots(item);return `<div class="cyber-tree-row ${nested?'nested':''}"><span class="iname">${nested?'↳ ':''}${esc(item.name)}</span>${total?`<span class="chip">Slots ${used}/${total}</span>`:''}${uses?`<span class="chip">Uses ${uses}</span>`:''}<span class="hl-badge">HL ${item.hl||0}</span><button class="info-btn" data-owned-chrome="${index}">i</button></div>${(children.get(id)||[]).map(([child,childIndex])=>row(child,childIndex,true)).join('')}`; };
  return roots.map(([item,index])=>row(item,index,false)).join('');
}

function cyberwareLifecycleHtml(items,loadout,mine) {
  if(!items.length)return `<div class="empty">${T('No Cyberware','Нет Cyberware')}</div>`;
  if(!loadout)return cyberwareTreeHtml(items);
  const byId=Object.fromEntries(items.map((item,index)=>[item.instance_id,{item,index}]));
  const info=id=>{const row=byId[id];return row?`<button class="info-btn" data-owned-chrome="${row.index}">i</button>`:'';};
  const installTag=profile=>`<span class="chip">${T('Install','Установка')}: ${esc(profile?.source_installation||'Manual')}</span>`;
  const payloadTag=payload=>payload?`<span class="chip ${payload.kind==='numeric_modifier'||payload.kind==='host_slot_grant'?'effect-auto':'effect-manual'}">${esc(payload.label||payload.id)} · ${payload.kind==='numeric_modifier'||payload.kind==='host_slot_grant'?T('AUTOMATED','АВТОМАТИЧЕСКИ'):T('MANUAL CONTEXT','КОНТЕКСТ ВРУЧНУЮ')}</span>`:'';
  const action=(id,hasOptions=false)=>!mine?'':`<div class="row">${hasOptions?'':`<button class="btn-sm" data-cyberware-action="${id}|uninstall">${T('Uninstall','Извлечь')}</button>`}${info(id)}</div>`;
  const hosts=(loadout.hosts||[]).map(host=>{
    const foundationId=host.foundation_instance_id||host.instance_id;
    const siblingHosts=(loadout.hosts||[]).filter(other=>(other.foundation_instance_id||other.instance_id)===foundationId);
    const foundationOccupied=siblingHosts.some(other=>other.options?.length);
    const side=`<span class="chip ${host.side_status==='conflict'?'warn-text':''}">${T('Side','Сторона')}: ${esc(host.physical_side||T('UNASSIGNED','НЕ НАЗНАЧЕНА'))}</span>`;
    const controls=host.paired_foundation&&host.physical_side==='right'?'':(mine?`<div class="row">${host.side_required?`<button class="btn-sm" data-cyberware-action="${foundationId}|configure">${T('Set Side','Назначить сторону')}</button>`:''}${host.quick_change_mount?`<button class="btn-sm btn-primary" data-cyberware-action="${foundationId}|quick_detach">${T('Quick Detach','Быстро отсоединить')}</button>`:''}${action(foundationId,foundationOccupied)}</div>`:info(foundationId));
    return `<article class="cyber-host-card ${host.overloaded||host.side_status==='conflict'?'invalid':''}"><header><div><b>${esc(host.name)}</b><span class="small muted">${esc(host.host_kind)}</span></div><span class="chip">Slots ${host.slots_used}/${host.slots_total}${host.slots_granted?` · +${host.slots_granted}`:''}</span></header><div class="mechanic-chips">${side}${installTag(host.installation_profile)}${host.quick_change_mount?'<span class="tag">QUICK CHANGE</span>':''}</div><div class="cyber-host-options">${host.options.length?host.options.map(option=>`<div class="program-runtime-row"><span>↳ ${esc(option.name)} · ${option.slots_used} ${T('slots','слотов')}${option.paired?` · ${T('PAIRED','ПАРНЫЙ')}`:''}</span>${payloadTag(option.curated_payload)}${mine?`<div class="row">${option.popup_binding_kind&&!option.bound_weapon_instance_id?`<button class="btn-sm btn-primary" data-popup-weapon-bind="${option.instance_id}|${option.popup_binding_kind}">${T('Bind Weapon','Привязать оружие')}</button>`:''}<button class="btn-sm" data-cyberware-action="${option.instance_id}|rebind">${T('Rebind','Сменить host')}</button><button class="btn-sm" data-cyberware-action="${option.instance_id}|uninstall">${T('Uninstall','Извлечь')}</button>${info(option.instance_id)}</div>`:info(option.instance_id)}</div>`).join(''):`<span class="small muted">${T('No installed options.','Нет установленных опций.')}</span>`}</div>${controls}</article>`;
  }).join('');
  const issues=(loadout.options||[]).filter(option=>['unbound','invalid'].includes(option.status)).map(option=>`<div class="inv-row cyberware-invalid"><span class="iname">⚠ ${esc(option.name)}</span><span class="tag">${esc(option.status.toUpperCase())}</span><span class="small warn-text">${esc((option.reasons||[]).join(' · '))}</span>${mine?`<button class="btn-sm btn-primary" data-cyberware-action="${option.instance_id}|rebind">${T('Bind Hosts','Привязать hosts')}</button><button class="btn-sm" data-cyberware-action="${option.instance_id}|uninstall">${T('Uninstall','Извлечь')}</button>`:''}${info(option.instance_id)}</div>`).join('');
  const standalone=(loadout.standalone||[]).map(item=>`<div class="inv-row"><span class="iname">${esc(item.name)}</span><span class="chip">${T('INSTALLED','УСТАНОВЛЕНО')}</span>${installTag(item.installation_profile)}<span class="hl-badge">HL ${item.hl||0}</span>${action(item.instance_id)}</div>`).join('');
  const payloads=(loadout.active_payloads||[]).length?`<div class="panel accent mb"><b>${T('Curated Cyberware Payloads','Курируемые payloads Cyberware')}</b><div class="mechanic-chips">${(loadout.active_payloads||[]).map(payloadTag).join('')}</div>${loadout.initiative_modifier?`<div class="small green-text">${T('Effective Initiative modifier','Effective модификатор Initiative')}: +${loadout.initiative_modifier}</div>`:''}</div>`:'';
  const cyberweapons=(loadout.weapon_profiles||[]).length?`<div class="panel mt mb"><h3>⚔ ${T('Integrated Cyberweapons','Интегрированные Cyberweapons')}</h3>${(loadout.weapon_profiles||[]).map(profile=>{const ws=profile.state||{},ranged=['ranged','ranged_dual'].includes(profile.kind);return `<div class="inv-row"><span class="iname"><b>${esc(profile.name)}</b><span class="small muted">${esc(profile.weapon_type)} · ${esc(profile.skill)} · ${esc(profile.effective_damage||profile.damage)} · ROF ${profile.rof}${profile.quality?` · ${esc(profile.quality)}`:''}</span></span>${profile.reach_m?`<span class="chip">Reach ${profile.reach_m}m</span>`:''}${ranged?`<span class="chip">Mag ${ws.magazine||0}/${ws.magazine_max||0}${profile.special_ammo?(ws.loaded_payload?` · ${esc(ws.loaded_payload)}`:' · SPECIAL'):` · Ammo ${profile.shared_ammo_available||0}`}</span>`:''}<span class="tag">${ws.deployed?T('DEPLOYED','РАЗВЁРНУТО'):T('STOWED','УБРАНО')}</span>${ws.revved?'<span class="tag">REVVed</span>':''}${profile.manual_effect?`<span class="small warn-text">${esc(profile.manual_effect)} · ${T('MANUAL EFFECT','ЭФФЕКТ ВРУЧНУЮ')}</span>`:''}${mine?`<div class="row">${profile.deployable?`<button class="btn-sm" data-cyberweapon-action="${profile.instance_id}|${ws.deployed?'stow':'deploy'}">${ws.deployed?T('Stow','Убрать'):T('Deploy','Развернуть')}</button>`:''}${profile.rev_action&&ws.deployed?`<button class="btn-sm" data-cyberweapon-action="${profile.instance_id}|${ws.revved?'rev_down':'rev'}">${ws.revved?'Rev Down':'Rev Up'}</button>`:''}${ranged?`<button class="btn-sm" data-cyberweapon-action="${profile.instance_id}|reload">Reload</button><button class="btn-sm btn-primary" data-cyberweapon-action="${profile.instance_id}|fire">Fire</button>`:''}</div>`:''}</div>`;}).join('')}</div>`:'';
  const popupShields=(loadout.popup_shields||[]).length?`<div class="panel mt mb"><h3>🛡 Popup Shield</h3>${(loadout.popup_shields||[]).map(profile=>`<div class="inv-row"><span class="iname">${profile.installed?esc(profile.shield_name):T('No concrete Bulletproof Shield installed','Concrete Bulletproof Shield не установлен')}</span>${profile.installed?`<span class="chip">HP ${profile.hp_current}/${profile.hp_max}</span><span class="tag">${profile.destroyed?T('DESTROYED','УНИЧТОЖЕН'):(profile.deployed?T('DEPLOYED','РАЗВЁРНУТ'):T('STOWED','УБРАН'))}</span>`:''}${mine?`<div class="row">${profile.installed?`<button data-popup-shield-action="${profile.option_instance_id}|${profile.deployed?'stow':'deploy'}">${profile.deployed?T('Stow','Убрать'):T('Deploy','Развернуть')}</button><button data-popup-shield-action="${profile.option_instance_id}|damage">Damage</button><button data-popup-shield-action="${profile.option_instance_id}|remove">${T('Remove / Replace','Извлечь / заменить')}</button>`:`<button data-popup-shield-action="${profile.option_instance_id}|install">${T('Install Bulletproof Shield','Установить Bulletproof Shield')}</button>`}</div>`:''}</div>`).join('')}</div>`:'';
  const staged=(loadout.staged||[]).map(item=>`<div class="inv-row"><span class="iname">${esc(item.name)}</span><span class="tag">${item.quick_change_detached?T('QUICK CHANGE DETACHED','QUICK CHANGE ОТСОЕДИНЁН'):T('STAGED · NOT INSTALLED','ПОДГОТОВЛЕНО · НЕ УСТАНОВЛЕНО')}</span>${installTag(item.installation_profile)}${item.installation_side?`<span class="chip">${T('Side','Сторона')}: ${esc(item.installation_side)}</span>`:''}<span class="hl-badge">HL ${item.hl||0}</span>${mine?`<button class="btn-sm btn-primary" data-cyberware-action="${item.instance_id}|${item.quick_change_detached?'quick_attach':'install'}">${item.quick_change_detached?T('Quick Attach','Быстро присоединить'):(item.expected_host?T('Install into Host','Установить в host'):T('Install','Установить'))}</button>`:''}${info(item.instance_id)}</div>`).join('');
  return `${payloads}${issues?`<div class="cyberware-issues mb"><b>${T('Host binding requires attention','Требуется исправить привязку host')}</b>${issues}</div>`:''}${hosts?`<div class="cyber-host-grid">${hosts}</div>`:''}${cyberweapons}${popupShields}${standalone?`<h3 class="mt">${T('Installed Standalone Cyberware','Установленная самостоятельная Cyberware')}</h3>${standalone}`:''}${staged?`<h3 class="mt">${T('Staged Cyberware','Подготовленная Cyberware')}</h3>${staged}`:''}`;
}

function armorHostLifecycleHtml(loadout,mine){
  const hosts=loadout?.hosts||[];if(!hosts.length)return '';
  return `<h3 class="mt">🛡️ ${T('Concrete Armor / Shield Hosts','Concrete hosts брони / щитов')}</h3><div class="cyber-host-grid">${hosts.map(host=>`<article class="cyber-host-card"><header><div><b>${esc(host.name)}</b><span class="small muted">${esc(host.host_kind.toUpperCase())} · ${host.equipped_locations.length?host.equipped_locations.join(' / '):T('not equipped','не экипировано')}</span></div>${host.host_kind==='shield'?`<span class="chip">HP ${host.base_sdp||0}</span>`:`<span class="chip">SP ${host.base_sp??'—'}${host.effective_sp!==host.base_sp?`→${host.effective_sp}`:''}</span>`}</header>${Object.keys(host.current_by_location||{}).length?`<div class="mechanic-chips">${Object.entries(host.current_by_location).map(([location,current])=>`<span class="chip">${esc(location)} ${current}/${host.host_kind==='shield'?(host.effective_sdp||0):(host.effective_sp||0)}</span>`).join('')}</div>`:''}${host.tech_upgrade?`<div class="small ${host.tech_upgrade.manual_resolution_required?'warn-text':'green-text'}">${host.tech_upgrade.manual_resolution_required?T('MANUAL SHIELD TECH UPGRADE','SHIELD TECH UPGRADE ВРУЧНУЮ'):T('AUTOMATED SP +1','АВТОМАТИЧЕСКИ SP +1')} · ${esc(host.tech_upgrade.tech_name||'Tech')} · ${esc(host.tech_upgrade.source||'')}</div>`:(mine&&host.tech_upgrade_available?`<button class="btn-sm" data-armor-tech-upgrade="${host.instance_id}">${host.automated_upgrade_available?T('Tech Upgrade · SP +1','Tech Upgrade · SP +1'):T('Record Manual Shield Upgrade','Записать Shield Upgrade вручную')}</button>`:'')}${host.host_kind==='shield'?`<div class="small warn-text">${T('DESTROYED AT 0 HP · NOT REPAIRABLE','УНИЧТОЖЕН ПРИ 0 HP · НЕ РЕМОНТИРУЕТСЯ')}</div>`:''}${host.repair_state?.active?`<div class="panel accent"><b>${T('REPAIR ACTIVE','РЕМОНТ АКТИВЕН')}</b><div class="small">${esc(host.repair_state.active.method)} · ${esc(host.repair_state.active.duration_label)}</div>${mine?`<div class="row"><button data-armor-repair="${host.instance_id}|resolve">${T('Complete Repair','Завершить ремонт')}</button><button data-armor-repair="${host.instance_id}|cancel">${T('Cancel','Отменить')}</button></div>`:''}</div>`:(mine&&host.damaged&&host.repairable?`<button data-armor-repair="${host.instance_id}|start">${T('Start Armor Repair','Начать ремонт брони')}</button>`:'')}${mine&&host.damaged&&host.self_repair?`<button data-armor-repair="${host.instance_id}|self_repair_tick">${T('Daily Self-Repair +1','Ежедневный саморемонт +1')}</button>`:''}</article>`).join('')}</div>`;
}

function therapyLifecycleHtml(character,derived,mine){
  const state=character.therapy_state||{},active=state.active,history=state.history||[];
  if(active)return `<div class="panel accent mt"><div class="row" style="justify-content:space-between"><div><b>🧠 ${esc(active.label)}</b><div class="small muted">${esc(active.therapist||'—')} · ${active.duration_days} ${T('days','дней')} · ${money(active.cost)} · ${esc(active.source||'')}</div></div><span class="tag">${T('ACTIVE · MANUAL WEEK','АКТИВНО · НЕДЕЛЯ ВРУЧНУЮ')}</span></div>${mine?`<div class="row mt"><button class="btn-primary" data-therapy-action="resolve">${T('Complete Therapy','Завершить Therapy')}</button><button class="btn-danger" data-therapy-action="cancel">${T('Cancel · no refund','Отменить · без возврата')}</button></div>`:''}</div>`;
  const latest=history.at(-1),latestHtml=latest?`<div class="small muted mt">${T('Latest Therapy','Последняя Therapy')}: ${esc(latest.label)} · ${esc(latest.status)}${latest.humanity_restored!=null?` · Humanity +${latest.humanity_restored} (${latest.humanity_before}→${latest.humanity_after}/${latest.humanity_maximum})`:''}</div>`:'';
  return `<div class="therapy-panel mt"><div class="row" style="justify-content:space-between"><div><b>🧠 Therapy</b><div class="small muted">${T('One campaign week · server Humanity roll · capped by Maximum Humanity','Одна игровая неделя · серверный бросок Humanity · не выше Maximum Humanity')}</div></div>${mine?`<button data-therapy-action="start">${T('Start Therapy','Начать Therapy')}</button>`:''}</div>${latestHtml}</div>`;
}

function campaignServicesHtml(d){
  const services=(d.campaign_services||[]).filter(service=>service.ready!==null);
  if(!services.length)return '';
  const nowLabel=d.campaign_time?` · ${T('clock','часы')} ${new Date(d.campaign_time*1000).toLocaleString(APP_I18N.current()==='ru'?'ru-RU':'en-US',{dateStyle:'medium',timeStyle:'short'})}`:'';
  return `<div class="panel mb" id="sheet-campaign-services"><h2>⏳ ${T('Campaign Clock','Campaign Clock')}</h2><div class="small muted mb">${T('Active services are tracked against campaign time. Completion checks are still resolved at the table.','Активные сервисы отслеживаются по игровому времени. Проверки завершения по-прежнему выполняются за столом.')}${esc(nowLabel)}</div>${services.map(service=>`<div class="inv-row"><span class="iname"><b>${esc(service.label)}</b></span>${service.ready===true?`<span class="tag">${T('DUE','ГОТОВО')}</span>`:service.ready===false?`<span class="tag">${T('IN PROGRESS','ИДЁТ')} · ${esc(service.status)}</span>`:`<span class="tag">${T('MANUAL','ВРУЧНУЮ')}</span>`}${service.due_label?`<span class="small muted">${esc(service.due_label)}</span>`:''}</div>`).join('')}</div>`;
}

function downtimeActivityLabel(activity){
  const name=APP_I18N.current()==='ru'?(activity.label_ru||activity.label_en):(activity.label_en||activity.id);
  return name;
}

function downtimeSheetHtml(c,d,canManage){
  const dt=d.downtime||{};
  const active=dt.active||null;
  const history=dt.history||[];
  const activeRow=active?`<div class="inv-row"><span class="iname"><b>${T('Downtime','Downtime')}</b><span class="small muted">${active.duration_label?esc(active.duration_label):T('Manual','Вручную')} · ${active.status==='MANUAL TIME'?T('MANUAL TIME','ВРУЧНУЮ'):esc(active.status)}</span>${active.note?`<div class="small muted">${esc(active.note)}</div>`:''}</span>${active.ready===true?`<span class="tag">${T('DUE','ГОТОВО')}</span>`:''}<div class="row">${active.activities.map(activity=>`<div class="inv-row" style="margin:0"><span class="iname">${activity.resolved?'✓ ':''}${esc(downtimeActivityLabel(activity))}</span>${activity.resolution_note?`<span class="small muted">${esc(activity.resolution_note)}</span>`:''}${canManage&&!activity.resolved&&['hustle','recover_hp','other'].includes(activity.kind)?`<button class="btn-sm" data-downtime-resolve="${esc(activity.id)}|${esc(activity.kind)}">${T('Resolve','Решить')}</button>`:''}</div>`).join('')}</div>${canManage?`<div class="row mt"><button class="btn-sm btn-primary" data-downtime-complete>${T('Complete Downtime','Завершить Downtime')}</button><button class="btn-sm" data-downtime-abandon>${T('Abandon','Отменить')}</button></div>`:''}</div>`:'';
  const startRow=canManage&&!active?`<div class="row"><button class="btn-primary" data-downtime-start>＋ ${T('Start Downtime','Начать Downtime')}</button></div>`:'';
  const historyHtml=history.length?`<details class="mt"><summary>${T('Downtime history','История downtime')} · ${history.length}</summary>${history.map(item=>`<div class="inv-row"><span class="iname"><b>${item.duration_label?esc(item.duration_label):T('Manual','Вручную')}</b><div class="small muted">${item.campaign_started_at?new Date(item.campaign_started_at*1000).toLocaleDateString():''}${item.summary?` · ${esc(item.summary)}`:''}</div></span>${item.activities.map(activity=>`<span class="chip">${activity.resolved?'✓ ':''}${esc(downtimeActivityLabel(activity))}</span>`).join('')}</div>`).join('')}</details>`:'';
  if(!active&&!history.length&&!canManage)return '';
  return `<div class="panel mb" id="sheet-downtime"><h2>🛌 ${T('Downtime Planner','Downtime Planner')}</h2><div class="small muted mb">${T('Record what the character does between sessions. Rolls resolve at the table; only the outcome is recorded.','Запишите, чем персонаж занят между сессиями. Броски выполняются за столом — записывается только результат.')}</div>${activeRow}${startRow}${historyHtml}</div>`;
}

async function openDowntimeStartModal(c){
  let catalog=[];
  try{catalog=(await api('/api/downtime/activities')).activities||[];}catch(e){/* empty */}
  const modal=openModal(`<h2>🛌 ${T('Start Downtime','Начать Downtime')}</h2><p class="muted small">${T('Choose a duration and the activities for this downtime period.','Выберите длительность и занятия на этот период downtime.')}</p><label class="f"><span>${T('Duration','Длительность')}</span><select id="dt-duration"><option value="">${T('Manual (no due)','Вручную (без срока)')}</option>${Object.entries({ '1_day':'1 Day','1_week':'1 Week','2_weeks':'2 Weeks' }).map(([k,v])=>`<option value="${k}">${v}</option>`).join('')}</select></label><div class="mt">${catalog.map(item=>`<label class="checkbox"><input type="checkbox" data-dt-activity="${esc(item.id)}"> <b>${esc(downtimeActivityLabel(item))}</b> <span class="small muted">${esc(APP_I18N.current()==='ru'?item.desc_ru:item.desc_en)}</span></label>`).join('')}</div><label class="f"><span>${T('Note','Заметка')}</span><input id="dt-note" maxlength="1000" placeholder="${T('Week off, side hustle…','Неделя отдыха, подработка…')}"></label><div class="row"><button id="dt-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="dt-save">${T('Start','Начать')}</button></div>`,true);
  $('#dt-cancel',modal).onclick=closeModal;
  $('#dt-save',modal).onclick=async()=>{
    const activities=$$('[data-dt-activity]',modal).filter(input=>input.checked).map(input=>({id:input.dataset.dtActivity}));
    const body={revision:c.revision,duration_key:$('#dt-duration',modal).value||null,activities,note:$('#dt-note',modal).value.trim()};
    try{await api(`/api/characters/${c.id}/downtime/start`,{method:'POST',body});closeModal();toast(T('Downtime started.','Downtime начат.'));viewSheet(c.id);}catch(e){toast(e.message,true);}
  };
}

async function performDowntimeAction(c,action,extra){
  const body={revision:c.revision,action,...extra};
  try{await api(`/api/characters/${c.id}/downtime/action`,{method:'POST',body});toast(T('Downtime updated.','Downtime обновлён.'));viewSheet(c.id);}catch(e){toast(e.message,true);}
}

function makerRanks(ch){
  const roles=ch.roles||[];
  const active=ch.active_role||ch.role;
  let role=roles.find(r=>r.name===active);
  if(!role||role.name!=='Tech')role=roles.find(r=>r.name==='Tech');
  if(!role||role.name!=='Tech')return null;
  const setup=role.setup||{};
  const ranks={field:num(setup.field)||0,upgrade:num(setup.upgrade)||0,fabrication:num(setup.fabrication)||0,invention:num(setup.invention)||0};
  if(!ranks.field&&!ranks.upgrade&&!ranks.fabrication&&!ranks.invention)return null;
  return ranks;
}

function techMakerEffectLabel(effect){
  if(!effect)return '';
  const target=String(effect.target||'');
  const labels={
    'weapon.attack_check':['Attack Check','Бросок атаки'],
    'weapon.magazine':['Magazine','Магазин'],
    'weapon.concealable':['Concealable','Скрываемость'],
    'armor.sp':['Stopping Power','Stopping Power'],
    'vehicle.sdp_max':['Max SDP','Макс. SDP'],
  };
  const pair=labels[target]||[target,target];
  const label=APP_I18N.current()==='ru'?pair[1]:pair[0];
  const value=effect.operation==='set'?effect.value:`${effect.value>0?'+':''}${effect.value}`;
  return `${label} ${effect.operation} ${value}`;
}

function techMakerSheetHtml(ch,d,mine){
  const tm=d.tech_maker||{};
  const mods=tm.modifications||[];
  const fabrications=tm.fabrications||[];
  const ranks=makerRanks(ch);
  if(!mods.length&&!fabrications.length&&!mine)return '';
  const manualTag=T('MANUAL','ВРУЧНУЮ'),autoTag=T('AUTOMATED','АВТОМАТИЧЕСКИ');
  const rows=mods.map(mod=>{
    const tag=mod.manual_resolution_required?`<span class="tag">${esc(manualTag)}</span>`:`<span class="tag">${esc(autoTag)}</span>`;
    return `<div class="inv-row"><span class="iname"><b>${esc(mod.name)}</b><span class="small muted">${esc(mod.host_name||'')} · ${esc(mod.maker_specialty||'')}${mod.maker_rank?` rank ${mod.maker_rank}`:''}${mod.tech_name?' · '+esc(mod.tech_name):''}</span></span>${mod.effect?`<span class="chip">${esc(techMakerEffectLabel(mod.effect))}</span>`:''}${tag}${mod.manual_rule?`<span class="small warn-text">${esc(mod.manual_rule)}</span>`:''}${mod.source?`<span class="chip">📖 ${esc(mod.source)}</span>`:''}${mod.reason?`<span class="small user-content">${esc(mod.reason)}</span>`:''}${mine&&mod.active?`<button class="btn-sm btn-danger" data-tech-maker-action="${mod.modification_id}|remove">${T('Remove','Снять')}</button>`:''}</div>`;
  }).join('');
  const fabRows=fabrications.map(fab=>{
    const costLabel=fab.material_cost!=null?` · ${money(fab.material_cost)}`:'';
    return `<div class="inv-row"><span class="iname"><b>${esc(fab.name)}</b><span class="small muted">×${fab.qty||1} · ${esc(fab.maker_specialty||'')}${fab.maker_rank?` rank ${fab.maker_rank}`:''}${fab.tech_name?' · '+esc(fab.tech_name):''}${fab.blueprint_catalog_id?' · blueprint':' · custom'}${costLabel}</span></span>${fab.source?`<span class="chip">📖 ${esc(fab.source)}</span>`:''}${fab.reason?`<span class="small user-content">${esc(fab.reason)}</span>`:''}</div>`;
  }).join('');
  const emptyRow=`<div class="muted small">${T('No Tech Maker modifications recorded.','Tech Maker modifications не записаны.')}</div>`;
  const createBtn=mine&&ranks?`<button class="btn-sm mt" data-tech-maker-create>＋ ${T('Create Tech Maker Modification','Создать Tech Maker Modification')}</button>`:'';
  const fabricateBtn=mine&&ranks?`<button class="btn-sm mt" data-tech-maker-fabricate>＋ ${T('Fabricate / Invent Item','Изготовить / изобрести предмет')}</button>`:'';
  const fabSection=fabrications.length?`<h3 class="mt">${T('Fabricated / Invented Items','Изготовленные / изобретённые предметы')}</h3>${fabRows}`:'';
  return `<div class="panel mt" id="sheet-tech-maker">
    <h2>🔧 ${T('Tech Maker','Tech Maker')}</h2>
    <div class="small muted mb">${T('Custom Upgrade/Invention/Fabrication Expertise work. Automated effects are allowlisted and bounded; ambiguous results stay manual.','Работа Upgrade/Invention/Fabrication Expertise. Автоматические эффекты ограничены allowlist; неоднозначные результаты остаются ручными.')}</div>
    ${mods.length?rows:emptyRow}
    ${fabSection}
    <div class="row">${createBtn}${fabricateBtn}</div>
  </div>`;
}

const TECH_MAKER_HOST_TYPES={guns:'weapon',armor:'armor',vehicles:'vehicle',cyberware:'cyberware'};
const TECH_MAKER_EFFECTS=[
  {target:'weapon.attack_check',host:'weapon',kind:'number',min:-3,max:3,labelEn:'Attack Check',labelRu:'Бросок атаки'},
  {target:'weapon.magazine',host:'weapon',kind:'number',min:1,max:20,labelEn:'Magazine capacity',labelRu:'Ёмкость магазина'},
  {target:'weapon.concealable',host:'weapon',kind:'choice',choices:['YES','NO'],labelEn:'Concealability',labelRu:'Скрываемость'},
  {target:'armor.sp',host:'armor',kind:'number',min:1,max:1,labelEn:'Stopping Power',labelRu:'Stopping Power'},
  {target:'vehicle.sdp_max',host:'vehicle',kind:'number',min:1,max:50,labelEn:'Maximum SDP',labelRu:'Максимальный SDP'},
];
function openTechMakerCreateModal(c){
  const ch=c.data||{};
  const ranks=makerRanks(ch);
  const inv=(ch.inventory||[]).filter(item=>TECH_MAKER_HOST_TYPES[item.cat]&&item.state!=='stored'&&item.state!=='broken');
  const cw=(ch.cyberware||[]).filter(item=>item.state==='installed');
  const hosts=[...inv,...cw.map(item=>({...item,cat:'cyberware'}))];
  const modal=openModal(`<h2>🔧 ${T('Create Tech Maker Modification','Создать Tech Maker Modification')}</h2><div class="panel accent mb"><p class="small">${T('Maker specialties for the active Tech role:','Специализации Maker активной роли Tech:')} ${Object.entries(ranks||{}).map(([k,v])=>`${esc(k)} ${v}`).join(' · ')||'—'}</p><p class="small muted">${T('Automated effects are allowlisted and bounded. Ambiguous results stay MANUAL.','Автоматические эффекты ограничены allowlist. Неоднозначные результаты остаются MANUAL.')}</p></div><div class="grid cols-2"><label class="f"><span>${T('Modification name *','Название modification *')}</span><input id="tm-name" maxlength="120" placeholder="Custom Smart Weapon Calibration"></label><label class="f"><span>${T('Tech performing the work *','Tech, выполняющий работу *')}</span><input id="tm-tech" maxlength="120" value="${esc(ch.handle||'')}"></label></div><div class="grid cols-2"><label class="f"><span>${T('Host instance *','Host instance *')}</span><select id="tm-host">${hosts.map((item,index)=>`<option value="${esc(item.instance_id)}" data-host-type="${TECH_MAKER_HOST_TYPES[item.cat]}">${esc(item.custom_name||item.name)} · ${esc(TECH_MAKER_HOST_TYPES[item.cat])}</option>`).join('')}</select></label><label class="f"><span>${T('Maker specialty *','Специализация Maker *')}</span><select id="tm-specialty"><option value="upgrade">${T('Upgrade Expertise','Upgrade Expertise')}${ranks?` (${ranks.upgrade||0})`:''}</option><option value="invention">${T('Invention Expertise','Invention Expertise')}${ranks?` (${ranks.invention||0})`:''}</option></select></label></div><label class="f"><span>${T('Effect (optional)','Эффект (необязательно)')}</span><select id="tm-effect"><option value="">— ${T('Manual only','Только вручную')} —</option></select></label><div class="grid cols-2" id="tm-effect-value-wrap" hidden><label class="f"><span id="tm-effect-value-label">Value</span><input id="tm-effect-value" type="number" step="1"></label><label class="f"><span>${T('Description','Описание')}</span><input id="tm-description" maxlength="2000"></label></div><label class="f"><span>${T('Manual rule (required if no effect)','Ручное правило (обязательно без эффекта)')}</span><textarea id="tm-manual-rule" maxlength="1000" rows="2" placeholder="${T('e.g. +2 only while stabilized on a bipod','например: +2 только с сошек')}"></textarea></label><label class="checkbox"><input id="tm-confirm" type="checkbox"> ${T('Confirm the successful Maker Check was resolved at the table.','Подтвердите успешный Maker Check за столом.')}</label><label class="f"><span>${T('Reason *','Причина *')}</span><textarea id="tm-reason" maxlength="500" rows="2" placeholder="${T('Upgrade Expertise result during downtime…','Результат Upgrade Expertise во время downtime…')}"></textarea></label><div class="row"><button id="tm-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="tm-submit">${T('Create','Создать')}</button></div>`,true);
  const hostSelect=$('#tm-host',modal),effectSelect=$('#tm-effect',modal),valueWrap=$('#tm-effect-value-wrap',modal),valueInput=$('#tm-effect-value',modal),valueLabel=$('#tm-effect-value-label',modal);
  const refreshEffects=()=>{const hostType=hostSelect.selectedOptions[0]?.dataset.hostType||'weapon';const options=TECH_MAKER_EFFECTS.filter(effect=>effect.host===hostType);effectSelect.innerHTML=`<option value="">— ${T('Manual only','Только вручную')} —</option>`+options.map((effect,index)=>`<option value="${index}">${esc(APP_I18N.current()==='ru'?effect.labelRu:effect.labelEn)}</option>`).join('');refreshValue();};
  const refreshValue=()=>{const index=Number(effectSelect.value);if(Number.isNaN(index)||effectSelect.value===''){valueWrap.hidden=true;return;}const effect=TECH_MAKER_EFFECTS[index];valueWrap.hidden=false;if(effect.kind==='choice'){valueInput.outerHTML=`<select id="tm-effect-value">${effect.choices.map(choice=>`<option value="${choice}">${choice}</option>`).join('')}</select>`;valueLabel.textContent=effect.labelRu||effect.labelEn;}else{valueLabel.textContent=`${effect.labelEn} (${effect.min}…${effect.max})`;}};
  hostSelect.onchange=refreshEffects;effectSelect.onchange=refreshValue;refreshEffects();
  $('#tm-cancel',modal).onclick=closeModal;
  $('#tm-submit',modal).onclick=async()=>{
    const name=$('#tm-name',modal).value.trim(),tech=$('#tm-tech',modal).value.trim(),host=$('#tm-host',modal).value,specialty=$('#tm-specialty',modal).value,reason=$('#tm-reason',modal).value.trim(),manualRule=$('#tm-manual-rule',modal).value.trim(),description=$('#tm-description',modal).value.trim();
    if(name.length<2||tech.length<2||reason.length<3){toast(T('Fill name, Tech and reason.','Заполните название, Tech и причину.'),true);return;}
    const index=Number(effectSelect.value),effectDef=Number.isInteger(index)&&effectSelect.value!==''?TECH_MAKER_EFFECTS[index]:null;
    let effect=null;
    if(effectDef){const valueEl=$('#tm-effect-value',modal);const value=effectDef.kind==='choice'?valueEl.value:Number(valueEl.value);if(effectDef.kind==='number'&&(!Number.isInteger(value)||value<effectDef.min||value>effectDef.max)){toast(T('Effect value is out of the allowed range.','Значение эффекта вне допустимого диапазона.'),true);return;}if(!$('#tm-confirm',modal).checked){toast(T('Confirm the successful Maker Check.','Подтвердите успешный Maker Check.'),true);return;}effect={target:effectDef.target,operation:effectDef.kind==='choice'?'set':'add',value};}
    if(!effect&&manualRule.length<3){toast(T('Provide a manual rule when there is no automated effect.','Укажите ручное правило, если нет автоматического эффекта.'),true);return;}
    const body={revision:c.revision,name,tech_name:tech,host_instance_id:host,maker_specialty:specialty,effect,manual_rule:manualRule,description,manual_confirm:!!effect,reason};
    const submit=$('#tm-submit',modal);submit.disabled=true;
    try{await api(`/api/characters/${c.id}/tech-maker/modifications`,{method:'POST',body});closeModal();toast(T('Tech Maker modification created.','Tech Maker modification создана.'));viewSheet(c.id);}catch(error){submit.disabled=false;toast(error.message,true);}
  };
}

function openTechMakerFabricateModal(c){
  const ch=c.data||{};
  const ranks=makerRanks(ch)||{};
  const modal=openModal(`<h2>🔩 ${T('Fabricate / Invent Item','Изготовить / изобрести предмет')}</h2><div class="panel accent mb"><p class="small">${T('Maker specialties for the active Tech role:','Специализации Maker активной роли Tech:')} ${Object.entries(ranks).map(([k,v])=>`${esc(k)} ${v}`).join(' · ')||'—'}</p><p class="small muted">${T('Fabrication reproduces a Database blueprint. Invention creates a new custom item. Both are recorded in the Dossier Ledger.','Fabrication воспроизводит blueprint из Database. Invention создаёт новый custom item. Оба действия записываются в журнал Dossier.')}</p></div><div class="grid cols-2"><label class="f"><span>${T('Item name *','Название предмета *')}</span><input id="tf-name" maxlength="120" placeholder="Custom Smart Ammo"></label><label class="f"><span>${T('Tech performing the work *','Tech, выполняющий работу *')}</span><input id="tf-tech" maxlength="120" value="${esc(ch.handle||'')}"></label></div><div class="grid cols-2"><label class="f"><span>${T('Maker specialty *','Специализация Maker *')}</span><select id="tf-specialty"><option value="fabrication">${T('Fabrication Expertise','Fabrication Expertise')}${ranks?` (${ranks.fabrication||0})`:''}</option><option value="invention">${T('Invention Expertise','Invention Expertise')}${ranks?` (${ranks.invention||0})`:''}</option></select></label><label class="f"><span>${T('Quantity','Количество')}</span><input id="tf-qty" type="number" min="1" max="99" value="1"></label></div><label class="f"><span>${T('Blueprint from Database (fabrication only)','Blueprint из Database (только fabrication)')}</span><input id="tf-blueprint" maxlength="120" placeholder="guns-0 · Medium Pistol"></label><label class="f"><span>${T('Description (custom item)','Описание (custom item)')}</span><textarea id="tf-description" maxlength="4000" rows="2"></textarea></label><div class="grid cols-2"><label class="f"><span>${T('Reference value (custom item)','Оценочная стоимость (custom item)')}</span><input id="tf-price" type="number" min="0" max="9999999" value="0"></label><label class="f"><span>${T('Material cost (€$)','Стоимость материалов (€$)')}</span><input id="tf-cost" type="number" min="0" max="9999999" value="0"></label></div><label class="checkbox"><input id="tf-confirm" type="checkbox"> ${T('Confirm the successful Maker Check was resolved at the table.','Подтвердите успешный Maker Check за столом.')}</label><label class="f"><span>${T('Reason *','Причина *')}</span><textarea id="tf-reason" maxlength="500" rows="2" placeholder="${T('Fabrication Expertise result during downtime…','Результат Fabrication Expertise во время downtime…')}"></textarea></label><div class="row"><button id="tf-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="tf-submit">${T('Fabricate','Изготовить')}</button></div>`,true);
  $('#tf-cancel',modal).onclick=closeModal;
  $('#tf-submit',modal).onclick=async()=>{
    const name=$('#tf-name',modal).value.trim(),tech=$('#tf-tech',modal).value.trim(),specialty=$('#tf-specialty',modal).value,reason=$('#tf-reason',modal).value.trim(),blueprint=$('#tf-blueprint',modal).value.trim(),description=$('#tf-description',modal).value.trim();
    if(name.length<2||tech.length<2||reason.length<3){toast(T('Fill name, Tech and reason.','Заполните название, Tech и причину.'),true);return;}
    if(!$('#tf-confirm',modal).checked){toast(T('Confirm the successful Maker Check.','Подтвердите успешный Maker Check.'),true);return;}
    const body={revision:c.revision,name,tech_name:tech,maker_specialty:specialty,qty:Math.max(1,Math.min(99,Number($('#tf-qty',modal).value)||1)),description,material_cost:Math.max(0,Math.min(9999999,Number($('#tf-cost',modal).value)||0)),manual_confirm:true,reason};
    if(blueprint){body.blueprint_catalog_id=blueprint;}else{body.category='custom';body.price=Math.max(0,Math.min(9999999,Number($('#tf-price',modal).value)||0));}
    const submit=$('#tf-submit',modal);submit.disabled=true;
    try{await api(`/api/characters/${c.id}/tech-maker/fabricate`,{method:'POST',body});closeModal();toast(T('Item fabricated and recorded.','Предмет изготовлен и записан.'));viewSheet(c.id);}catch(error){submit.disabled=false;toast(error.message,true);}
  };
}

function wizStepSummaryHtml() {
  const wiz=state.wizard,c=wizChar(),d=wizDerived(),errors=wizValidationErrors(),warnings=equipmentWarnings(wiz);
  if(d.emp_cur!=null&&d.emp_cur<=2)warnings.push(T('EMP is 2 or lower','EMP не выше 2'));
  if(wiz.fashionCost < FASHION_BUDGET) warnings.push(`${T('Unused Style Budget will be lost','Неиспользованный Style Budget сгорит')}: ${money(FASHION_BUDGET-wiz.fashionCost)}`);
  for(const [base] of SUB_SKILL_BASES){const free=wizSubFree(base);if(free)warnings.push(`${base}: ${free} ${T('parent levels remain unallocated','уровней parent-pool не распределено')}`);}
  const slotHosts=cyberPhysicalHosts(wiz);for(const host of slotHosts){const total=num(host.capacity?.slots_total)||0;if(!total)continue;const used=wiz.cyberware.filter(item=>cyberHostIds(item).includes(host.instance_id||host.id)).reduce((sum,item)=>sum+cyberOptionSlots(item),0);if(total>used)warnings.push(`${host.name}: ${total-used} Option Slots ${T('unused','свободно')}`);}
  const lpRows=lifepathNarrative(wiz.lifepath,wiz.role,wiz.roleLifepath),roleSource=ROLE_COREBOOK_V3[wiz.role];
  const statBlock=state.meta.stats.map(stat=>`<button class="chip skill-name-btn" data-stat-info="${stat}"><b>${stat}</b> ${wiz.stats[stat]}</button>`).join('');
  const weaponRows=wiz.gear.filter(item=>['guns','melee'].includes(item.cat)).map(item=>`<div class="inv-row"><span class="iname">${esc(item.name)}</span>${itemMechanicChips(item)}${item.mechanics?.skill?`<span class="chip">${esc(item.mechanics.skill)} BASE ${characterSkillLevel(c,item.mechanics.skill)+(num(c.stats[state.meta.skills.find(row=>row[1]===item.mechanics.skill)?.[2]])||0)}</span>`:''}</div>`).join('');
  return `<div class="summary-status panel accent mb"><div><h2>${errors.length?`⛔ ${errors.length} ${T('blocking issues','блокирующих ошибок')}`:`✅ ${T('Ready to create','Готов к созданию')}`}</h2><p>⚠ ${warnings.length} ${T('warnings','предупреждений')}</p></div><div class="row"><button class="btn-sm" id="summary-print">🖨️ Print</button><button class="btn-sm" id="summary-json">⬇ JSON</button></div></div>
  <details class="creation-section validation-section" open><summary><span>Validation</span><span>${errors.length+warnings.length}</span></summary><div class="section-body">${errors.map(error=>`<button class="validation-row error" data-validation-step="${validationTarget(error)}">⛔ <span>${esc(error)}</span><b>${T('Fix','Исправить')} →</b></button>`).join('')}${warnings.map(warning=>`<div class="validation-row warning">⚠ <span>${esc(warning)}</span></div>`).join('')}${!errors.length&&!warnings.length?`<div class="green">✓ ${T('All checks passed.','Все проверки пройдены.')}</div>`:''}</div></details>
  <details class="creation-section" open><summary><span>Identity & Role</span></summary><div class="section-body summary-identity">${wiz.portraitMedia?`<img class="sheet-portrait" src="${esc(wiz.portraitMedia.url)}" alt="${esc(wiz.handle)}">`:''}<div><h2>${esc(wiz.handle||'—')}</h2><p>${esc([wiz.firstName,wiz.lastName].filter(Boolean).join(' ')||'—')}</p><div class="chips"><span class="tag role">${esc(wiz.role||T('No Role','Роль не выбрана'))}${wiz.role?' · Rank 4':''}</span>${roleSource?`<span class="tag source">${esc(roleSource.pages)}</span>`:''}</div></div>${wiz.role?`<div><h3>${ROLE_COREBOOK_V3[wiz.role].icon} ${esc(state.meta.roles[wiz.role])}</h3><p>${esc(ROLE_COREBOOK_V3[wiz.role][APP_I18N.current()].rank4)}</p><div>${esc(roleSetupSummary(wiz.role,wiz.roleSetup))}</div></div>`:''}<button class="btn-sm" onclick="wizGoTo(1)">${T('Edit Role','Изменить роль')}</button></div></details>
  <details class="creation-section"><summary><span>Lifepath</span><span>${lpRows.length}</span></summary><div class="section-body">${lpRows.length?`<div class="kv">${lpRows.map(([key,value])=>`<b>${esc(key)}</b><span>${esc(displayKnownValue(value))}</span>`).join('')}</div>`:`<div class="empty">${T('Not completed','Не заполнен')}</div>`}<button class="btn-sm mt" onclick="wizGoTo(2)">${T('Edit Lifepath','Изменить Lifepath')}</button></div></details>
  <details class="creation-section" open><summary><span>Characteristics</span><span>${wizStatSpent()}/62</span></summary><div class="section-body"><div class="statgrid mb">${statBlock}</div><div class="derived"><span class="dstat"><b>${d.hp_max??'—'}</b><small>Max HP</small></span><span class="dstat"><b>${d.death_save??'—'}</b><small>Death Save</small></span><span class="dstat"><b>${d.humanity_cur??'—'} / ${d.humanity_max??'—'}</b><small>Humanity</small></span><span class="dstat"><b>${d.emp_cur??'—'}</b><small>Current EMP</small></span></div></div></details>
  <details class="creation-section"><summary><span>Skills</span><span>${wizSkillSpent()}/86</span></summary><div class="section-body"><label class="checkbox mb"><input type="checkbox" id="summary-zero-skills" checked> ${T('Show zero-level Skills','Показывать навыки уровня 0')}</label>${fullSkillsTableHtml(c,d)}</div></details>
  <details class="creation-section"><summary><span>Combat Loadout</span><span>${wiz.gear.filter(item=>['guns','melee'].includes(item.cat)).length}</span></summary><div class="section-body">${weaponRows||`<div class="empty">${T('No weapons selected','Оружие не выбрано')}</div>`}<h3>Armor</h3><div class="chips"><span class="chip"><b>Body</b> ${wiz.armor.body?esc(wiz.armor.body.name):'—'}</span><span class="chip"><b>Head</b> ${wiz.armor.head?esc(wiz.armor.head.name):'—'}</span></div></div></details>
  <details class="creation-section"><summary><span>Cyberware</span><span>HL ${d.hl_total||0}</span></summary><div class="section-body"><div class="humanity-breakdown panel mb"><span>Base ${wiz.stats.EMP*10}</span><span>HL −${d.hl_total||0}</span><span>Max reduction −${d.hum_cut||0}</span><b>${d.humanity_cur}/${d.humanity_max} · EMP ${d.emp_cur}</b></div>${cyberwareTreeHtml(c.cyberware)}${wiz.soldSoul?`<div class="panel accent mt"><b>Sell Your Soul</b><p>${esc(wiz.patron)} · ${esc(wiz.obligation)}</p></div>`:''}</div></details>
  <details class="creation-section"><summary><span>Inventory, Fashion & Role Benefits</span><span>${c.inventory.length}</span></summary><div class="section-body">${summaryInventoryHtml(c.inventory)}</div></details>
  <details class="creation-section" open><summary><span>Finances & Visibility</span></summary><div class="section-body"><div class="finance-grid"><div><b>Main Budget</b><span>${money(GEAR_BUDGET)}</span><small>${T('Spent','Потрачено')} ${money(creationMainSpent(wiz))}</small><strong>${T('Starting Cash','Стартовые наличные')} ${money(Math.max(0,creationMainRemaining(wiz)))}</strong></div><div><b>Style Budget</b><span>${money(FASHION_BUDGET)}</span><small>${T('Spent','Потрачено')} ${money(wiz.fashionCost)}</small><strong>${T('Lost','Сгорит')} ${money(Math.max(0,FASHION_BUDGET-wiz.fashionCost))}</strong></div><div><b>Cyberware Bonus</b><span>${money(creationChromeBonus(wiz))}</span><small>Sell Your Soul</small></div><div><b>Role Benefits</b><span>${roleBenefitItems(wiz).length}</span><small>${money(0)} paid</small></div></div><div class="grid cols-2 mt"><label class="f"><span>Player</span><input id="summary-player" value="${esc(wiz.player||'')}"></label><label class="f"><span>Visibility</span><select id="summary-public"><option value="private" ${!wiz.public?'selected':''}>Private</option><option value="public" ${wiz.public?'selected':''}>Public</option></select></label></div></div></details>`;
}

/* ---------- биндинги шагов ---------- */

function hasRoleSpecificProgress(wiz) {
  const hasLifepath = Object.values(wiz.roleLifepath || {})
    .some(value => String(value || '').trim());
  const currentSetup = JSON.stringify(wiz.roleSetup || {});
  const defaultSetup = JSON.stringify(defaultRoleSetup(wiz.role));
  return hasLifepath || currentSetup !== defaultSetup;
}

function charHasRole(ch, roleName) {
  return Boolean((ch && ch.roles || []).some(role => role.name === roleName));
}

function changeWizardRole(nextRole) {
  const wiz = state.wizard;
  if (!nextRole || nextRole === wiz.role) return;
  if (hasRoleSpecificProgress(wiz) &&
      !window.confirm(T(`Change Role from ${wiz.role} to ${nextRole}? Filled Role-Based Lifepath and modified Role setup will be reset. Shared data stays.`,`Сменить роль ${wiz.role} на ${nextRole}? Ролевой Lifepath и настройка роли будут сброшены. Общие данные сохранятся.`))) return;
  wiz.role = nextRole;
  wiz.roleLifepath = {};
  wiz.roleSetup = defaultRoleSetup(nextRole);
  renderWizard();
}

function adjustStyleCart(kind, index, delta) {
  const wiz = state.wizard;
  const list = kind === 'style' ? wiz.fashion : wiz.fashionware;
  const item = list[index];
  if (!item) return;
  if (delta > 0 && wiz.fashionCost + (item.price || 0) > FASHION_BUDGET) { toast('Не хватает бюджета стиля', true); return; }
  if (delta > 0) { item.qty = (item.qty || 1) + 1; wiz.fashionCost += item.price || 0; }
  else {
    wiz.fashionCost = Math.max(0, wiz.fashionCost - (item.price || 0));
    item.qty = (item.qty || 1) - 1;
    if (item.qty <= 0) list.splice(index, 1);
  }
  renderWizard();
}

function clearArmorForEntry(wiz, item) {
  for (const location of ['body', 'head', 'shield']) if (wiz.armor[location] && wiz.armor[location].key === item.key) wiz.armor[location] = null;
}

async function adjustShopCart(kind, index, delta) {
  const wiz = state.wizard;
  if (kind === 'chrome') {
    const sample = wiz.cyberware[index];
    if (!sample) return;
    if (delta > 0) {
      if (String(sample.name).toLowerCase() === 'neuroport' || (sample.capacity || {}).unique) { toast(T('A second installation is not allowed.','Вторая установка запрещена.'), true); return; }
      const needsHost=(sample.capacity||{}).host&&!pairedCyberlegFoundation(sample),hosts=needsHost?availableCyberHosts(wiz,sample):[];
      if (needsHost && !hosts.length) { toast(T('No compatible host has enough Option Slots.','У совместимых hosts нет свободных Option Slots.'), true); return; }
      if (!canAffordCreationItem(wiz, { cat: 'cyberware' }, sample.price || 0)) { toast(T('Not enough Main Budget.','Недостаточно основного бюджета.'), true); return; }
      const host = needsHost?await chooseCyberHost(hosts,sample):null;if(needsHost&&!host)return;
      const side=chooseCyberSide(wiz,sample);if(cyberSideRequired(sample)&&!side)return;
      wiz.cyberware.push({ ...sample, instance_id: clientInstanceId(), installation_side:side||'', host_instance: host ? (Array.isArray(host) ? (host[0].instance_id || host[0].id) : (host.instance_id || host.id)) : '', host_instances: host ? (Array.isArray(host) ? host.map(value => value.instance_id || value.id) : [host.instance_id || host.id]) : [] }); wiz.chromeCost += sample.price || 0;
    } else {
      const removeIndex = wiz.cyberware.findIndex(x => x.id === sample.id);
      const removed = wiz.cyberware[removeIndex];
      if (removed) {
        const hostId = removed.instance_id || removed.id,removedIds=new Set([hostId]);if(pairedCyberlegFoundation(removed))removedIds.add(pairedCyberHostId(hostId));
        const dependents = wiz.cyberware.filter(item => cyberHostIds(item).some(id=>removedIds.has(id)));
        if (dependents.length && !window.confirm(T(`Remove ${removed.name} and ${dependents.length} installed options?`,`Удалить ${removed.name} и установленные опции (${dependents.length})?`))) return;
        wiz.cyberware = wiz.cyberware.filter(item => item !== removed && !cyberHostIds(item).some(id=>removedIds.has(id)));
        wiz.chromeCost = Math.max(0, wiz.chromeCost - (removed.price || 0) - dependents.reduce((sum,item)=>sum+(item.price||0),0));
      }
    }
  } else {
    const item = wiz.gear[index];
    if (!item) return;
    if (delta > 0) {
      if (item.cat === 'armor') { toast('Второй экземпляр этой брони запрещён', true); return; }
      if (!canAffordCreationItem(wiz, item, item.price || 0)) { toast('Не хватает бюджета', true); return; }
      item.qty = (item.qty || 1) + 1; wiz.gearCost += item.price || 0;
    } else {
      item.qty = (item.qty || 1) - 1; wiz.gearCost = Math.max(0, wiz.gearCost - (item.price || 0));
      if (item.qty <= 0) { clearArmorForEntry(wiz, item); wiz.gear.splice(index, 1); }
    }
  }
  renderWizard();
}

function bindWizStep() {
  const wiz=state.wizard,step=wiz.step,body=$('#wiz-body');if(!body)return;
  if(step===1){
    $$('[data-role]',body).forEach(button=>button.onclick=()=>changeWizardRole(button.dataset.role));
    const shift=delta=>{const roles=wizardRoleOrder(),index=Math.max(0,roles.indexOf(wiz.role));changeWizardRole(roles[(index+delta+roles.length)%roles.length]);};
    $$('[data-role-shift]',body).forEach(button=>button.onclick=()=>shift(Number(button.dataset.roleShift)));
    const carousel=$('#role-carousel');if(carousel){let touchX=null;carousel.ontouchstart=e=>touchX=e.changedTouches[0].clientX;carousel.ontouchend=e=>{if(touchX==null)return;const dx=e.changedTouches[0].clientX-touchX;touchX=null;if(Math.abs(dx)>=45)shift(dx<0?1:-1);};carousel.onkeydown=e=>{if(e.key==='ArrowLeft')shift(-1);if(e.key==='ArrowRight')shift(1);};}
    $$('[data-role-step]',body).forEach(button=>button.onclick=()=>{const [key,raw]=button.dataset.roleStep.split('|'),delta=Number(raw),keys=wiz.role==='Tech'?['field','upgrade','fabrication','invention']:['surgery','pharma','cryo'],limit=wiz.role==='Tech'?8:4,total=keys.reduce((sum,k)=>sum+(num(wiz.roleSetup[k])||0),0),current=num(wiz.roleSetup[key])||0;if(delta>0&&(total>=limit||current>=4))return;wiz.roleSetup[key]=Math.max(0,current+delta);renderWizard();});
    $$('[data-team-member]',body).forEach(button=>button.onclick=()=>{wiz.roleSetup.team_member=button.dataset.teamMember;renderWizard();});
    $$('[data-moto-choice]',body).forEach(select=>select.onchange=()=>{wiz.roleSetup.moto_choices=wiz.roleSetup.moto_choices||['','','',''];wiz.roleSetup.moto_choices[Number(select.dataset.motoChoice)]=select.value;saveWizardDraft();});
  }
  if(step===2){
    $$('[data-lp-section]',body).forEach(details=>details.ontoggle=()=>{wiz.lifepathOpen[details.dataset.lpSection]=details.open;saveWizardDraft();});
    const portrait=$('#wiz-portrait-file');if(portrait)portrait.onchange=()=>openImageCrop(portrait.files[0],'character_portrait',media=>{wiz.portraitMedia=media;renderWizard();});const removePortrait=$('#wiz-portrait-remove');if(removePortrait)removePortrait.onclick=async()=>{if(wiz.portraitMedia){try{await api('/api/media/'+wiz.portraitMedia.id,{method:'DELETE'});}catch(e){}wiz.portraitMedia=null;renderWizard();}};
    const handle=$('#wiz-handle'),first=$('#wiz-first-name'),last=$('#wiz-last-name');if(handle)handle.oninput=()=>wiz.handle=handle.value;if(first)first.oninput=()=>wiz.firstName=first.value;if(last)last.oninput=()=>wiz.lastName=last.value;
    const handleStyle=$('#wiz-handle-style');if(handleStyle)handleStyle.onchange=()=>{wiz.handleStyle=handleStyle.value;saveWizardDraft();};$('[data-generate-handle]',body).onclick=()=>{generateWizardHandle();renderWizard();};
    $$('[data-name-gender]',body).forEach(button=>button.onclick=()=>{wiz.nameGender=button.dataset.nameGender;renderWizard();});
    $$('[data-generate-name]',body).forEach(button=>button.onclick=()=>{generateWizardName(button.dataset.generateName);renderWizard();});
    $$('[data-lp]',body).forEach(select=>select.onchange=()=>{setLifepathValue(select.dataset.lp,select.value);renderWizard();});
    $$('[data-role-lp]',body).forEach(select=>select.onchange=()=>{wiz.roleLifepath[select.dataset.roleLp]=select.value;renderWizard();});
    $$('[data-lp-dice]',body).forEach(button=>button.onclick=()=>{wizRollHybrid(button.dataset.lpDice,false);renderWizard();});
    $$('[data-role-lp-dice]',body).forEach(button=>button.onclick=()=>{wizRollHybrid(button.dataset.roleLpDice,true);renderWizard();});
    const native=$('#lp-native');if(native)native.onchange=()=>{wiz.nativeLanguage=native.value;syncNativeLanguage();renderWizard();};
    $('#lp-fill-missing').onclick=()=>{lpAllFields().forEach(([key])=>{if(!wiz.lifepath[key])wizRollHybrid(key,false);});if(wiz.role)lpRoleField(wiz.role).forEach(([key])=>{if(!wiz.roleLifepath[key])wizRollHybrid(key,true);});syncNativeLanguage();renderWizard();toast(T('Missing Lifepath fields filled.','Пустые поля Lifepath заполнены.'));};$('#lp-gen-all').onclick=()=>{if(Object.keys(wiz.lifepath||{}).length&&!window.confirm(T('Replace every Lifepath result?','Заменить все результаты Lifepath?')))return;lpAllFields().forEach(([key])=>wizRollHybrid(key,false));if(wiz.role)lpRoleField(wiz.role).forEach(([key])=>wizRollHybrid(key,true));syncNativeLanguage();renderWizard();toast(T('Hybrid Lifepath generated.','Hybrid Lifepath сгенерирован.'));};
  }
  if(step===3){
    $$('[data-stat-step]',body).forEach(button=>button.onclick=()=>{const [stat,raw]=button.dataset.statStep.split('|'),delta=Number(raw),current=num(wiz.stats[stat])||5;if(delta>0&&wizStatSpent()>=62)return;wiz.stats[stat]=Math.max(2,Math.min(8,current+delta));renderWizard();});
    $$('[data-stat-lock]',body).forEach(button=>button.onclick=()=>{wiz.statLocks[button.dataset.statLock]=!wiz.statLocks[button.dataset.statLock];renderWizard();});
    $$('[data-stat-info]',body).forEach(button=>button.onclick=()=>showStatInfo(button.dataset.statInfo));
    const statMode=$('#wiz-st-mode');if(statMode)statMode.onchange=()=>{wiz.statRandomMode=statMode.value;saveWizardDraft();};$('#wiz-st-roll').onclick=()=>{randomizeWizardStats();renderWizard();};$('#wiz-st-reset').onclick=()=>{const previous={...wiz.stats};state.meta.stats.forEach(stat=>wiz.stats[stat]=5);renderWizard();toastUndo(T('Characteristics reset.','Характеристики сброшены.'),()=>{state.wizard.stats=previous;renderWizard();});};
  }
  if(step===4){
    const query=$('#wiz-skill-q');if(query)query.oninput=()=>{wiz.skillQ=query.value;renderWizard();};
    $$('[data-skill-filter]',body).forEach(button=>button.onclick=()=>{wiz.skillFilter=button.dataset.skillFilter;renderWizard();});
    $$('[data-skill-category]',body).forEach(details=>details.ontoggle=()=>{wiz.skillOpen[details.dataset.skillCategory]=details.open;saveWizardDraft();});
    $$('[data-wiz-skill-step]',body).forEach(button=>button.onclick=()=>{const [name,raw]=button.dataset.wizSkillStep.split('|'),delta=Number(raw),meta=state.meta.skills.find(row=>row[1]===name),cost=meta&&meta[3]?2:1,current=num(wiz.skills[name])||0,floor=WIZ_SUB_HIDDEN.has(name)?wizSubAllocated(name):0;if(delta>0&&((state.meta.skill_points||86)-wizSkillSpent()<cost||(!WIZ_SUB_HIDDEN.has(name)&&current>=6)))return;if(delta<0&&current<=floor)return;wiz.skills[name]=Math.max(floor,WIZ_SUB_HIDDEN.has(name)?current+delta:Math.min(6,current+delta));renderWizard();});
    $$('[data-sub-add]',body).forEach(button=>button.onclick=()=>{if(wizSubFree(button.dataset.subAdd)<=0)return;wiz.subSkills.push({base:button.dataset.subAdd,name:'',lvl:1});renderWizard();});
    $$('[data-sub-del]',body).forEach(button=>button.onclick=()=>{const item=wiz.subSkills[Number(button.dataset.subDel)];if(item&&!item.native)wiz.subSkills.splice(Number(button.dataset.subDel),1);renderWizard();});
    $$('[data-sub-name]',body).forEach(input=>input.oninput=()=>{const item=wiz.subSkills[Number(input.dataset.subName)];if(item&&!item.native)item.name=input.value;});
    $$('[data-sub-minus]',body).forEach(button=>button.onclick=()=>{const item=wiz.subSkills[Number(button.dataset.subMinus)],minimum=item&&item.native?4:0;if(item&&item.lvl>minimum)item.lvl--;renderWizard();});
    $$('[data-sub-plus]',body).forEach(button=>button.onclick=()=>{const item=wiz.subSkills[Number(button.dataset.subPlus)];if(!item||item.lvl>=6)return;if(wizSubFree(item.base)<=0){const meta=state.meta.skills.find(row=>row[1]===item.base),cost=meta&&meta[3]?2:1;if((state.meta.skill_points||86)-wizSkillSpent()<cost){toast(T('Not enough Skill Points to increase the parent pool.','Недостаточно очков для увеличения parent-pool.'),true);return;}wiz.skills[item.base]=(num(wiz.skills[item.base])||0)+1;}item.lvl++;renderWizard();});
  }
  if(step===5){
    $$('[data-cyber-filter]',body).forEach(button=>button.onclick=()=>{wiz.cyberFilter=button.dataset.cyberFilter;renderWizard();});
    $$('[data-shop-tab]',body).forEach(button=>button.onclick=()=>{captureWizardScrolls();wiz.shopState=wiz.shopState||{};wiz.shopState[wiz.shopTab]={q:wiz.shopQ,filters:{...(wiz.shopFilters||{})}};wiz.shopTab=button.dataset.shopTab;const saved=wiz.shopState[wiz.shopTab]||{};wiz.shopQ=saved.q||'';wiz.shopFilters={...(saved.filters||{})};renderWizard();});
    $$('[data-shop-tab-jump]',body).forEach(button=>button.onclick=()=>{const dependents=wiz.cyberware.filter(item=>cyberHostIds(item).includes('creation-neuroport'));if(dependents.length&&!window.confirm(T('Removing the free Neuroport will also remove its installed options. Continue?','Удаление бесплатного Neuroport также удалит его опции. Продолжить?')))return;wiz.cyberware=wiz.cyberware.filter(item=>!cyberHostIds(item).includes('creation-neuroport'));wiz.chromeCost=Math.max(0,wiz.chromeCost-dependents.reduce((sum,item)=>sum+(item.price||0),0));wiz.shopTab=button.dataset.shopTabJump;wiz.freeNeuroport=false;renderWizard();});
    $$('[data-neuro-choice]',body).forEach(button=>button.onclick=()=>{if(button.dataset.neuroChoice!=='free'||hasPaidNeuroport(wiz))return;if(wiz.freeNeuroport){const dependents=wiz.cyberware.filter(item=>cyberHostIds(item).includes('creation-neuroport'));if(dependents.length&&!window.confirm(T(`Remove the free Neuroport and ${dependents.length} installed options?`,`Удалить бесплатный Neuroport и установленные опции (${dependents.length})?`)))return;wiz.cyberware=wiz.cyberware.filter(item=>!cyberHostIds(item).includes('creation-neuroport'));wiz.chromeCost=Math.max(0,wiz.chromeCost-dependents.reduce((sum,item)=>sum+(item.price||0),0));}wiz.freeNeuroport=!wiz.freeNeuroport;renderWizard();});
    const soul=$('#wiz-soul');if(soul)soul.onchange=()=>{wiz.soldSoul=soul.checked;renderWizard();};const patron=$('#wiz-patron');if(patron)patron.onchange=()=>wiz.patron=patron.value;const obligation=$('#wiz-obligation');if(obligation)obligation.oninput=()=>wiz.obligation=obligation.value;
    const query=$('#wiz-shop-q');if(query)query.oninput=()=>{captureWizardScrolls();wiz.shopQ=query.value;wiz.scrolls[`shop:${wiz.shopTab}`]=0;wizLoadShopList();};
    const type=$('#wiz-shop-type');if(type)type.onchange=()=>{wiz.shopFilters.type=type.value;wizLoadShopList();};const source=$('#wiz-shop-source');if(source)source.onchange=()=>{wiz.shopFilters.source=source.value;wizLoadShopList();};const maxPrice=$('#wiz-shop-max-price');if(maxPrice)maxPrice.onchange=()=>{wiz.shopFilters.maxPrice=maxPrice.value;wizLoadShopList();};const sort=$('#wiz-shop-sort');if(sort)sort.onchange=()=>{wiz.shopFilters.sort=sort.value;wizLoadShopList();};const affordable=$('#shop-affordable');if(affordable)affordable.onchange=()=>{wiz.shopFilters.affordable=affordable.checked;wizLoadShopList();};const selected=$('#shop-selected');if(selected)selected.onchange=()=>{wiz.shopFilters.selected=selected.checked;wizLoadShopList();};
    const compare=$('#compare-items');if(compare)compare.onclick=()=>{const all=Object.values(wiz._shopCache||{}).flat();renderCompareModal((wiz.compareItems||[]).map(id=>all.find(item=>item.id===id)).filter(Boolean));};const outfitStyle=$('#outfit-style');if(outfitStyle)outfitStyle.onchange=()=>wiz.outfitStyle=outfitStyle.value;const outfit=$('#random-outfit');if(outfit)outfit.onclick=generateRandomOutfit;
    $$('[data-cart-qty]',body).forEach(button=>button.onclick=()=>{const [kind,index,delta]=button.dataset.cartQty.split('|');if(kind==='style'||kind==='fashionware')adjustStyleCart(kind,Number(index),Number(delta));else adjustShopCart(kind,Number(index),Number(delta));});
    $$('[data-cart-info]',body).forEach(button=>button.onclick=()=>{const [kind,index]=button.dataset.cartInfo.split('|'),lists={chrome:wiz.cyberware,gear:wiz.gear,style:wiz.fashion,fashionware:wiz.fashionware};showCreationItemInfo(lists[kind][Number(index)]);});
    $$('[data-equip-armor]',body).forEach(button=>button.onclick=()=>{const item=wiz.gear[Number(button.dataset.equipArmor)];if(!item)return;const piece={key:item.key,source_key:item.source_key,name:item.name,sp:item.sp||0,penalties:{...(item.penalties||{})},bundled:!!item.armor_bundled};if(item.location==='body'||item.location==='set')wiz.armor.body=piece;if(item.location==='head'||item.location==='set')wiz.armor.head=piece;if(item.location==='shield')wiz.armor.shield=piece;renderWizard();});
    wizLoadShopList();
  }
  if(step===6){
    $$('[data-validation-step]',body).forEach(button=>button.onclick=()=>wizGoTo(Number(button.dataset.validationStep)));
    $$('[data-stat-info]',body).forEach(button=>button.onclick=()=>showStatInfo(button.dataset.statInfo));$$('[data-skill-info]',body).forEach(button=>button.onclick=()=>showSkillInfo(button.dataset.skillInfo));
    $$('[data-owned-chrome]',body).forEach(button=>button.onclick=()=>showCreationItemInfo(wizChar().cyberware[Number(button.dataset.ownedChrome)]));$$('[data-summary-item]',body).forEach(button=>button.onclick=()=>showCreationItemInfo(wizChar().inventory[Number(button.dataset.summaryItem)]));
    const player=$('#summary-player');if(player)player.oninput=()=>wiz.player=player.value;const visibility=$('#summary-public');if(visibility)visibility.onchange=()=>wiz.public=visibility.value==='public';
    const zero=$('#summary-zero-skills');if(zero)zero.onchange=()=>$('.full-skill-list',body).classList.toggle('hide-zero-skills',!zero.checked);
    $('#summary-print').onclick=()=>window.print();$('#summary-json').onclick=()=>{const blob=new Blob([JSON.stringify(wizChar(),null,2)],{type:'application/json'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`${(wiz.handle||'character').replace(/[^a-z0-9_-]+/gi,'-')}.json`;a.click();URL.revokeObjectURL(a.href);};
  }
  $$('[data-skill-info]',body).forEach(button=>button.onclick=()=>showSkillInfo(button.dataset.skillInfo));
  body.addEventListener('input',saveWizardDraft);body.addEventListener('change',saveWizardDraft);
}

/* ---------- навигация ---------- */

function wizNext() {
  const wiz = state.wizard;
  if (wiz.step < 6) { wiz.step++; renderWizard(); }
  window.scrollTo(0, 0);
}

function wizPrev() {
  const wiz = state.wizard;
  if (wiz.step > 1) { wiz.step--; renderWizard(); }
  window.scrollTo(0, 0);
}

function wizGoTo(step) {
  state.wizard.step = Math.max(1, Math.min(6, step));
  renderWizard();
  window.scrollTo(0, 0);
}

function wizReset() {
  if (!window.confirm(T('Permanently clear this saved draft and start over?','Полностью очистить сохранённый draft и начать заново?'))) return;
  clearWizardDraft(); initWizard(); renderWizard();
  toast(T('Draft cleared.','Draft очищен.'));
}

function wizRefreshLive() {
  const box = $('#wiz-live');
  if (!box) return;
  box.innerHTML = wizLiveHtml();
}

async function wizCreate() {
  const wiz = state.wizard;
  if (wiz.creating) return;
  const errors = wizValidationErrors();
  if (errors.length) { toast(errors[0], true); return; }
  wiz.creating = true;
  const button = $('#wiz-create'); if (button) { button.disabled = true; button.textContent = T('Creating…','Создание…'); }
  try {
    await api('/api/characters', { method: 'POST', body: { data: wizChar() } });
    wiz.created = true; clearWizardDraft(); state.wizard = null;
    toast(T('🎉 Character created!','🎉 Персонаж создан!'));
    location.hash = '#/characters';
  } catch (e) {
    wiz.creating = false; if (button) button.disabled = false;
    toast(e.message, true);
  }
}

// Кластер досье (лист персонажа, мои персонажи, 644 строки, 40 функций) вынесен
// в views-dossiers.js (P3-frontend, срез S2)
