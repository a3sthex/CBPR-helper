// Character Editor — редактор досье (вкладки General/Stats/Skills/Gear/Chrome).
// P3-frontend, срез S3: вынесено из app.js. Классические скрипты делят глобальную область;
// порядок загрузки в index.html: views-editor.js → app.js (инфра-функции остаются в app.js).

/* ============================== редактор персонажа ============================== */

const EDITOR_TABS = [
  ['base', 'General', 'Основное'], ['stats', 'Characteristics', 'Характеристики'], ['skills', 'Skills', 'Навыки'],
  ['gear', 'Gear & Weapons', 'Снаряжение и оружие'], ['chrome', 'Cyberware', 'Кибернетика'], ['armor', 'Armor', 'Броня'], ['notes', 'Other', 'Прочее'],
];

async function viewEditor(id) {
  if (!state.me) { $('#view').innerHTML = `<div class="empty">Нужен вход. <a href="#/login">${T('Sign in','Войти')}</a></div>`; return; }
  const view = $('#view');
  let payload;
  if (id === 'new') {
    payload = { id: null, data: blankChar(), derived: derive(blankChar()) };
  } else {
    view.innerHTML = spinner();
    payload = await api('/api/characters/' + id);
    if (payload.owner_id !== state.me.id) {
      view.innerHTML = `<div class="empty">Это персонаж игрока ${esc(payload.owner_name)}. Смотреть его можно в <a href="#/roster">ростере</a>.</div>`;
      return;
    }
  }
  state.editor = {
    id: payload.id, revision: payload.revision || 0,
    char: JSON.parse(JSON.stringify(payload.data)),
    baseline: JSON.parse(JSON.stringify(payload.data)), tab: 'base', dirty: false,
  };

  view.innerHTML = `
  <div class="page-head">
    <div><h1 id="ed-title">${payload.id ? `✏️ ${T('Editor:','Редактор:')} <span class="user-content">${esc(payload.data.handle || '…')}</span>` : `🧬 ${T('New Edgerunner','Новый эджраннер')}`}</h1>
      <div class="sub" id="ed-sub"></div></div>
    <div class="row">
      <button onclick="location.hash='#/characters'">← ${T('My Characters','К моим')}</button>
      <button class="btn-primary" id="ed-save">💾 ${T('Save','Сохранить')}</button>
    </div>
  </div>
  ${payload.id?`<div class="panel accent mb"><b>TRUST + AUDIT</b> · ${T('You may edit your sheet freely. Every save requires a reason and records a readable before/after change set in the Dossier Ledger.','Вы можете свободно редактировать лист. Каждое сохранение требует причину и записывает понятный набор изменений «до → после» в журнал Dossier.')}</div>`:''}
  <div class="panel accent mb" id="ed-derived"></div>
  <div class="editor-tabs" id="ed-tabs">
    ${EDITOR_TABS.map(([k, en, ru]) => `<button data-tab="${k}" class="${state.editor.tab === k ? 'active' : ''}">${T(en,ru)}</button>`).join('')}
  </div>
  <div id="ed-body"></div>`;

  $('#ed-save').onclick = saveEditor;
  $$('#ed-tabs button').forEach(b => b.onclick = () => {
    state.editor.tab = b.dataset.tab;
    $$('#ed-tabs button').forEach(x => x.classList.toggle('active', x === b));
    renderEditorTab();
  });
  renderEditorTab();
  renderDerived();
}

function edChanged() {
  if (state.editor) state.editor.dirty = true;
  renderDerived();
}

function renderDerived() {
  const ed = state.editor;
  if (!ed) return;
  const d = derive(ed.char);
  const c = ed.char;
  $('#ed-title').innerHTML = `${ed.id ? `✏️ ${T('Editor:','Редактор:')}` : `🧬 ${T('New:','Новый:')}`} <span class="user-content">${esc(c.handle || T('Unnamed','Безымянный'))}</span>`;
  $('#ed-sub').innerHTML = `${esc(c.role || '—')} · ${money(c.cash)} · ${c.public ? T('👁 public','👁 публичный') : T('🔒 private','🔒 приватный')}`;
  const box = $('#ed-derived');
  const stat = (k, v, warn) => `<span class="dstat${warn ? ' warn' : ''}"><span class="v">${v == null ? '—' : v}</span><span class="k">${k}</span></span>`;
  box.innerHTML = `<div class="derived">
    ${stat(T('Max HP','HP макс'), d.hp_max)}
    ${stat(T('Current HP','Текущее HP'), (() => { let h = c.hp_cur == null ? d.hp_max : c.hp_cur; return h; })())}
    ${stat(T('Seriously Wounded ≤','Серьёзная рана ≤'), d.seriously_wounded)}
    ${stat(T('Death Save','Спасбросок смерти'), d.death_save)}
    ${stat(T('Humanity','Человечность'), d.humanity_max != null ? d.humanity_cur + '/' + d.humanity_max : null, d.humanity_max != null && d.humanity_cur <= 20)}
    ${stat(T('Current EMP','EMP текущий'), d.emp_cur, d.emp_cur != null && d.emp_cur <= 2)}
    ${stat(T('Body SP','SP тело'), d.sp_body)}
    ${stat(T('Head SP','SP голова'), d.sp_head)}
    ${stat(T('Armor Penalty','Штраф брони'), Object.entries(d.armor_penalties || {}).map(([k,v]) => `${k} ${v}`).join(' · '), Object.values(d.armor_penalties || {}).some(v => v < 0))}
  </div>
  ${d.hum_cut ? `<div class="small muted" style="margin-top:6px">Срез макс. человечности за хром: −${d.hum_cut} (по 2 за хром, 4 за боргвер; HL: −${d.hl_total || 0}).</div>` : ''}
  ${d.emp_cur != null && d.emp_cur <= 2 ? '<div class="small" style="color:var(--magenta);margin-top:6px">⚠️ EMP ≤ 2 — на грани киберпсихоза. Осторожно с хромом.</div>' : ''}`;
}

function editorChangePreview(before,after){
  const groups=[
    [T('Identity & biography','Личность и биография'),['handle','first_name','last_name','player','appearance','background','languages','lifestyle','housing','notes','public']],
    [T('Role','Роль'),['role','role_rank','roles','active_role']],[T('Characteristics','Характеристики'),['stats','hp_cur','humanity_cur','luck_cur']],
    [T('Skills','Навыки'),['skills','skill_pools','native_language']],[T('Resources','Ресурсы'),['cash','ip_available','reputation']],
    ['Inventory',['inventory']],['Cyberware',['cyberware']],[T('Armor','Броня'),['armor']],
  ];
  return groups.filter(([,keys])=>keys.some(key=>JSON.stringify(before[key])!==JSON.stringify(after[key]))).map(([label])=>label);
}

async function saveEditor() {
  const ed = state.editor;
  if (!ed) return;
  const c = ed.char;
  if (!c.handle || !c.handle.trim()) { toast('Заполни псевдоним (Handle) на вкладке «Основное»', true); state.editor.tab = 'base'; renderEditorTab(); return; }
  if (!ed.id) {
    try {
      const r = await api('/api/characters', { method: 'POST', body: {data:c} });
      state.editor.id = r.id; state.editor.revision=r.revision||0;
      state.editor.baseline=JSON.parse(JSON.stringify(r.data));state.editor.char=JSON.parse(JSON.stringify(r.data));
      state.editor.dirty = false;history.replaceState(null, '', '#/char/' + r.id + '?edit');
      toast(T('Saved.','Сохранено ✓'));renderDerived();
    } catch (e) { toast(e.message, true); }
    return;
  }
  const changed=editorChangePreview(ed.baseline,c);
  if(!changed.length){toast(T('There are no changes to save.','Нет изменений для сохранения.'),true);return;}
  const modal=openModal(`<h2>${T('Save Character Sheet','Сохранить Character Sheet')}</h2><div class="panel accent mb"><b>TRUST + AUDIT</b><p class="small">${T('The following sections changed:','Изменены разделы:')} ${changed.map(esc).join(' · ')}</p></div><label class="f"><span>${T('Reason for changes *','Причина изменений *')}</span><textarea id="sheet-edit-reason" maxlength="500" rows="3" placeholder="${T('Loot from session, correction, downtime…','Добыча с сессии, исправление, downtime…')}" autofocus></textarea></label><p class="small muted">${T('The server will validate the sheet and record readable before/after changes.','Сервер проверит лист и запишет понятные изменения «до → после».')}</p><div class="row"><button id="sheet-edit-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="sheet-edit-confirm">${T('Save and record','Сохранить и записать')}</button></div>`);
  $('#sheet-edit-cancel',modal).onclick=closeModal;
  $('#sheet-edit-confirm',modal).onclick=async()=>{
    const reason=$('#sheet-edit-reason',modal).value.trim();
    if(reason.length<3){toast(T('Describe why the sheet changed.','Опишите причину изменения листа.'),true);return;}
    const button=$('#sheet-edit-confirm',modal);button.disabled=true;
    try{
      const saved=await api(`/api/characters/${ed.id}/sheet`,{method:'PUT',body:{revision:ed.revision,reason,data:c}});
      ed.revision=saved.revision;ed.char=JSON.parse(JSON.stringify(saved.data));ed.baseline=JSON.parse(JSON.stringify(saved.data));ed.dirty=false;
      closeModal();toast(T('Sheet saved and recorded in the Ledger.','Лист сохранён и записан в журнал.'));renderEditorTab();renderDerived();
    }catch(error){button.disabled=false;toast(error.message,true);}
  };
}

function renderEditorTab() {
  const ed = state.editor;
  const box = $('#ed-body');
  const c = ed.char;
  if (ed.tab === 'base') {
    const roleDesc = ((APP_I18N.current() === 'en' ? state.meta.role_desc_en : state.meta.role_desc) || {})[c.role] || '';
    const roleAb = state.meta.roles[c.role] || '';
    box.innerHTML = `
    <div class="panel">
      <div class="grid cols-2">
        <label class="f"><span>${T('Handle *','Псевдоним (Handle) *')}</span><input id="f-handle" maxlength="60" value="${esc(c.handle)}" placeholder="${T('Neon, Slim, Switch…','Выхлоп, Neon, Slim…')}"></label>
        <label class="f"><span>Имя (необязательно)</span><input id="f-first-name" maxlength="60" value="${esc(c.first_name || '')}"></label>
        <label class="f"><span>Фамилия (необязательно)</span><input id="f-last-name" maxlength="60" value="${esc(c.last_name || '')}"></label>
        <label class="f"><span>Роль</span><select id="f-role">
          ${Object.keys(state.meta.roles).map(r => `<option value="${r}" ${c.role === r ? 'selected' : ''}>${r}${APP_I18N.current()==='ru' ? ' — '+esc(state.meta.role_ru[r]) : ''}</option>`).join('')}
        </select></label>
        <label class="f"><span>${T('Role Rank (starts at 4)','Ранг роли (старт — 4)')}</span><input id="f-rank" type="number" min="1" max="10" value="${c.role_rank || 4}"></label>
        <label class="f"><span>Игрок (реальное имя)</span><input id="f-player" maxlength="60" value="${esc(c.player || '')}"></label>
      </div>
      <div class="small muted mb" id="f-role-note">${roleDesc ? esc(roleDesc) + ` ${T('Ability:','Способность:')} <b>` + esc(roleAb) + '</b>.' : ''}</div>
      <label class="f"><span>Внешность</span><textarea id="f-appearance" maxlength="4000">${esc(c.appearance || '')}</textarea></label>
      <label class="f"><span>Биография / предыстория</span><textarea id="f-background" maxlength="4000">${esc(c.background || '')}</textarea></label>
      <div class="grid cols-3"><label class="f"><span>Cash (€$)</span><input id="f-cash" type="number" min="0" step="1" value="${c.cash || 0}"></label><label class="f"><span>${T('Available IP','Доступные IP')}</span><input id="f-ip" type="number" min="0" step="1" value="${c.ip_available||0}"></label><label class="f"><span>Reputation</span><input id="f-reputation" type="number" min="0" max="10" step="1" value="${c.reputation||0}"></label></div>
      <p class="small muted">${T('Trust mode allows resource corrections, but the reason and exact before/after values are always written to the Ledger.','Trust mode разрешает исправлять ресурсы, но причина и точные значения «до → после» всегда записываются в журнал.')}</p>
    </div>`;
    $('#f-handle').oninput = (e) => { c.handle = e.target.value; edChanged(); };
    $('#f-first-name').oninput = (e) => { c.first_name = e.target.value; edChanged(); };
    $('#f-last-name').oninput = (e) => { c.last_name = e.target.value; edChanged(); };
    $('#f-role').onchange = (e) => {
      c.role = e.target.value; edChanged();
      const rd = ((APP_I18N.current() === 'en' ? state.meta.role_desc_en : state.meta.role_desc) || {})[c.role] || '';
      const ra = state.meta.roles[c.role] || '';
      $('#f-role-note').innerHTML = rd ? esc(rd) + ` ${T('Ability:','Способность:')} <b>` + esc(ra) + '</b>.' : '';
    };
    $('#f-rank').oninput = (e) => { c.role_rank = num(e.target.value) || 4; edChanged(); };
    $('#f-player').oninput = (e) => { c.player = e.target.value; edChanged(); };
    $('#f-appearance').oninput = (e) => { c.appearance = e.target.value; edChanged(); };
    $('#f-background').oninput = (e) => { c.background = e.target.value; edChanged(); };
    $('#f-cash').oninput = (e) => { c.cash = num(e.target.value) || 0; edChanged(); };
    $('#f-ip').oninput = (e) => { c.ip_available = num(e.target.value) || 0; edChanged(); };
    $('#f-reputation').oninput = (e) => { c.reputation = num(e.target.value) || 0; edChanged(); };
  }
  if (ed.tab === 'stats') {
    const st = c.stats;
    const spent = Object.values(st).reduce((a, b) => a + (num(b) || 0), 0);
    const budget = state.meta.stat_points || 62, statMax=ed.id?13:8;
    box.innerHTML = `
    <div class="panel">
      <div class="row mb">
        <span class="muted small">${ed.id?T('Post-creation Trust edit: values 1–13; every change is audited.','Trust-редактирование после создания: значения 1–13; каждое изменение записывается.'):T('Creation standard: 62 points, each Characteristic 2–8.','Стандарт создания: 62 очка, каждая характеристика 2–8.')} ${T('Current total:','Текущая сумма:')} <b id="st-spent">${spent}</b></span>
        <button class="btn-sm" id="st-roll">🎲 ${T('Random (array 8,7,7,6,6,6,6,6,5,5)','Случайно (массив 8,7,7,6,6,6,6,6,5,5)')}</button>
        <button class="btn-sm" id="st-reset">${T('Reset all to 5','Сбросить все на 5')}</button>
      </div>
      <div class="statgrid mb">
        ${state.meta.stats.map(s => {
          const v = num(st[s]);
          const bad = v != null && (v < (ed.id?1:2) || v > statMax);
          return `<div class="stat input${bad ? ' bad' : ''}"><span class="k">${s}</span><input type="number" min="${ed.id?1:2}" max="${statMax}" data-stat="${s}" value="${st[s] != null ? st[s] : ''}"></div>`;
        }).join('')}
      </div>
      <div class="grid cols-2">
        <label class="f"><span>Текущее HP (пусто = максимум)</span><input id="f-hpcur" type="number" min="-1000" max="1000" value="${c.hp_cur != null ? c.hp_cur : ''}" placeholder="авто"></label>
        <label class="f"><span>Текущая человечность (пусто = максимум)</span><input id="f-humcur" type="number" min="0" max="100" value="${c.humanity_cur != null ? c.humanity_cur : ''}" placeholder="авто"></label>
      </div>
      <p class="small muted">${T('HP = 10 + 5×⌈(BODY+WILL)/2⌉. Current Humanity decreases by HL when Cyberware is installed. Maximum Humanity separately decreases by','HP = 10 + 5×⌈(BODY+WILL)/2⌉. Текущая Humanity при установке уменьшается на HL. Максимальная Humanity отдельно уменьшается на')} <b>2</b> ${T('for ordinary Cyberware and','за обычный хром и на')} <b>4</b> ${T('for Borgware; Fashionware and the free starting CEMK Neuroport are excluded. Current EMP = Humanity ÷ 10, rounded down.','за Borgware; Fashionware и бесплатный стартовый Neuroport CEMK исключены. Текущий EMP = Humanity ÷ 10 (вниз).')}</p>
    </div>`;
    $$('[data-stat]', box).forEach(inp => inp.oninput = () => {
      c.stats[inp.dataset.stat] = num(inp.value);
      const v = num(inp.value);
      inp.parentElement.classList.toggle('bad', v != null && (v < (ed.id?1:2) || v > statMax));
      const sp = Object.values(c.stats).reduce((a, b) => a + (num(b) || 0), 0);
      $('#st-spent').textContent = sp;
      $('#st-spent').classList.toggle('warn-text', sp > budget);
      edChanged();
    });
    $('#st-roll').onclick = () => {
      const arr = [8, 7, 7, 6, 6, 6, 6, 6, 5, 5];
      for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1));[arr[i], arr[j]] = [arr[j], arr[i]]; }
      state.meta.stats.forEach((s, i) => c.stats[s] = arr[i]);
      renderEditorTab(); edChanged();
    };
    $('#st-reset').onclick = () => {
      state.meta.stats.forEach(s => c.stats[s] = 5);
      renderEditorTab(); edChanged();
    };
    $('#f-hpcur').oninput = (e) => { c.hp_cur = e.target.value === '' ? null : num(e.target.value); edChanged(); };
    $('#f-humcur').oninput = (e) => { c.humanity_cur = e.target.value === '' ? null : num(e.target.value); edChanged(); };
  }
  if (ed.tab === 'skills') {
    c.skills = c.skills || {};
    const allSkills = state.meta.skills;
    const specialBases = new Set(SPECIALIZED_SKILL_BASES.map(x => x[0]));
    const skills = allSkills.filter(([,name]) => !specialBases.has(name));
    const byBase = Object.fromEntries(allSkills.map(x => [x[1], x]));
    const baseOf = (name) => Object.keys(byBase).find(base => name === base || name.startsWith(base + ' ('));
    const specialized = Object.entries(c.skills).filter(([name]) => specialBases.has(baseOf(name)))
      .map(([name, lvl]) => ({ name, base: baseOf(name), spec: name === baseOf(name) ? 'без специализации' : name.slice(baseOf(name).length + 2, -1), lvl }));
    const skillSpent = () => {
      let total = 0;
      for (const [name, value] of Object.entries(c.skills)) {
        const base = baseOf(name), lvl = num(value) || 0;
        total += lvl * (base && byBase[base][3] ? 2 : 1);
        if (c.native_language && name === `Language (${c.native_language})`) total -= Math.min(4, lvl);
      }
      return total;
    };
    const requiredOk = (name) => {
      if (name === 'Language') return (num(c.skills['Language (Streetslang)']) || 0) >= 2;
      if (name === 'Local Expert') return Object.entries(c.skills).some(([k,v]) => baseOf(k) === name && (num(v)||0) >= 2);
      return (num(c.skills[name]) || 0) >= 2;
    };
    let lastCat = null;
    const rows = skills.map(([cat, name, stat, is2]) => {
      const head = cat !== lastCat ? `<div class="skill-cat">${esc(skillCategoryLabel(cat))}</div>` : '';
      lastCat = cat;
      const lvl = c.skills[name] || 0;
      return head + `<div class="skill-row"><button class="skill-name-btn sname" data-skill-info="${esc(name)}">${(state.meta.must_skills||[]).includes(name) ? '<span class="must-tag">★</span>' : ''}${esc(name)}${is2 ? ' <span class="muted small">(×2)</span>' : ''}</button>
        <span class="sstat">${stat}</span><select data-rank="${esc(name)}">${[0,1,2,3,4,5,6,7,8,9,10].map(r=>`<option value="${r}" ${lvl===r?'selected':''}>${r||'—'}</option>`).join('')}</select></div>`;
    }).join('');
    const specialRows = specialized.map((s, i) => `<div class="skill-row">
      <button class="skill-name-btn sname" data-skill-info="${esc(s.base)}"><b>${esc(s.base)}</b> (${esc(s.spec)})${byBase[s.base][3] ? ' <span class="muted small">×2</span>' : ''}${c.native_language === s.spec && s.base === 'Language' ? ' <span class="chip">родной</span>' : ''}</button>
      <span class="sstat">${byBase[s.base][2]}</span>
      <select data-spec-rank="${i}">${[0,1,2,3,4,5,6,7,8,9,10].map(r=>`<option value="${r}" ${(num(s.lvl)||0)===r?'selected':''}>${r||'—'}</option>`).join('')}</select>
      <button class="btn-sm btn-danger" data-spec-del="${i}">✕</button></div>`).join('');
    const mustChips = (state.meta.must_skills || []).map(name => `<span class="must-chip ${requiredOk(name)?'ok':'bad'}">${requiredOk(name)?'✓':'✗'} ${esc(name === 'Language' ? 'Language (Streetslang)' : name)}</span>`).join('');
    box.innerHTML = `<div class="panel"><div class="row mb" style="justify-content:space-between"><span class="muted small">${T('Creation requires exactly','При создании ровно')} <b>86</b> ${T('points with a maximum Level of','очков, максимум')} <b>6</b>. ${T('After creation, the editor supports advancement to Level 10. Recalculated spent points:','После создания редактор допускает развитие до 10. Потрачено при пересчёте:')} <b id="sk-spent">${skillSpent()}</b></span></div>
      <div class="must-list mb">${mustChips}</div>
      <div class="panel mb"><div class="row" style="justify-content:space-between"><h3>${T('Specialized Skills','Специализированные навыки')}</h3><button class="btn-sm" id="add-special-skill">＋ ${T('Add','Добавить')}</button></div>
        <label class="f"><span>${T('Cultural Language (4 Levels free at creation)','Культурный язык (4 уровня бесплатно при создании)')}</span><input id="ed-native" value="${esc(c.native_language || '')}"></label>
        ${specialRows || `<div class="muted small">${T('No specialized Skills.','Нет специализированных навыков.')}</div>`}</div>
      <div class="skill-list">${rows}</div></div>`;
    const refresh = () => { const el=$('#sk-spent'); if(el) el.textContent=skillSpent(); edChanged(); };
    $$('[data-skill-info]', box).forEach(btn => btn.onclick = () => showSkillInfo(btn.dataset.skillInfo));
    $$('[data-rank]', box).forEach(sel => sel.onchange = () => { c.skills[sel.dataset.rank]=Number(sel.value); refresh(); });
    $$('[data-spec-rank]', box).forEach(sel => sel.onchange = () => { const x=specialized[Number(sel.dataset.specRank)]; if(x)c.skills[x.name]=Number(sel.value); refresh(); });
    $$('[data-spec-del]', box).forEach(btn => btn.onclick = () => { const x=specialized[Number(btn.dataset.specDel)]; if(x)delete c.skills[x.name]; renderEditorTab(); edChanged(); });
    $('#ed-native').oninput = e => { c.native_language=e.target.value.trim(); refresh(); };
    $('#add-special-skill').onclick = () => {
      const base = prompt('Базовый навык: Language, Local Expert, Martial Arts, Science или Play Instrument');
      if (!base || !specialBases.has(base)) { if(base)toast('Неизвестный специализированный навык',true); return; }
      const spec = prompt('Конкретный язык, район, стиль, наука или инструмент');
      if (!spec || !spec.trim()) return;
      c.skills[`${base} (${spec.trim()})`] = 1;
      renderEditorTab(); edChanged();
    };
  }
  if (ed.tab === 'gear') {
    box.innerHTML = `
    <div class="panel">
      <div class="row mb">
        <button class="btn-primary" id="add-weapon">＋ ${T('Weapon from Database','Оружие из Database')}</button>
        <button id="add-gear">＋ ${T('Item from Database','Предмет из Database')}</button>
        <button id="add-custom-item">＋ ${T('Custom / Found Item','Custom / найденный предмет')}</button>
        <span class="muted small grow">${T('Items added here require an acquisition source and are recorded by Trust + Audit.','Добавленные здесь предметы требуют источник получения и записываются через Trust + Audit.')}</span>
      </div>
      <div id="inv-list"></div>
    </div>`;
    $('#add-weapon').onclick = () => pickItem(['guns', 'melee', 'grenades', 'ammo'], T('Weapon from Database','Оружие из Database'), it => openCatalogAcquisitionModal(it,meta=>{addInvItem(it,meta);renderEditorTab();}));
    $('#add-gear').onclick = () => pickItem(null, T('Item from Database','Предмет из Database'), it => openCatalogAcquisitionModal(it,meta=>{addInvItem(it,meta);renderEditorTab();}),it=>it.cat!=='cyberware');
    $('#add-custom-item').onclick=()=>openOwnedItemEditor(null,item=>{c.inventory=c.inventory||[];c.inventory.push(item);renderEditorTab();edChanged();});
    renderInventoryList();
  }
  if (ed.tab === 'chrome') {
    box.innerHTML = `
    <div class="panel">
      <div class="row mb">
        <button class="btn-primary" id="add-chrome">＋ ${T('Install Cyberware','Вшить хром')}</button>
        <span class="muted small grow">${T('Cyberware HL is subtracted from Humanity; at creation use the average value shown in parentheses.','HL импланта вычитается из человечности; при создании бери среднее значение (в скобках).')}</span>
      </div>
      <p class="small muted">${T('Guide rule: each piece of Cyberware except Fashionware also reduces','Правило гайда: каждый хром (кроме Fashionware) дополнительно режет')} <b>${T('maximum','максимум')}</b> ${T('Humanity by 2, or by 4 for Borgware.','человечности на 2, Borgware — на 4.')}</p>
      <div id="chrome-list"></div>
    </div>`;
    $('#add-chrome').onclick = () => pickItem(['cyberware'], T('Cyberware from Database','Кибернетика из Database'), it => openCatalogAcquisitionModal(it,meta=>{
      const c2 = state.editor.char;c2.cyberware=c2.cyberware||[];
      c2.cyberware.push({key:it.id,catalog_item_id:it.id,cat:'cyberware',name:it.name,custom_name:meta.custom_name||'',hl:it.hl||0,price:it.price,type:(it.fields&&it.fields.Type)||'',qty:1,state:'carried',fields:{...(it.fields||{})},mechanics:{...(it.mechanics||{})},requirements:[...(it.requirements||[])],capacity:it.capacity?{...it.capacity}:null,source:it.source||'',acquisition_source:meta.acquisition_source,acquisition_note:meta.acquisition_note||''});
      renderEditorTab();edChanged();
    },{quantity:false}));
    renderChromeList();
  }
  if (ed.tab === 'armor') {
    box.innerHTML = `
    <div class="panel">
      <p class="small muted">${T('Armor is selected separately for Head and Body. Layer SP does not stack: only the highest SP at a location applies, and every worn layer at that location ablates together. Apply the single most severe penalty separately to REF, DEX, and MOVE.','Броня выбирается отдельно для головы и тела. SP слоёв не складывается: работает только наибольший SP локации, а все надетые слои абляируются вместе. Применяется один самый строгий штраф отдельно к REF, DEX и MOVE.')}</p>
      <div class="grid cols-2" id="armor-slots"></div>
    </div>`;
    renderArmorSlots();
  }
  if (ed.tab === 'notes') {
    box.innerHTML = `
    <div class="panel">
      <label class="f"><span>${T('Languages','Языки')}</span><input id="f-lang" maxlength="200" value="${esc(c.languages || '')}" placeholder="${T('Streetslang, Spanish, English…','Streetslang, русский, английский…')}"></label>
      <label class="f"><span>Заметки</span><textarea id="f-notes" maxlength="4000" style="min-height:160px">${esc(c.notes || '')}</textarea></label>
      <label class="checkbox"><input type="checkbox" id="f-public" ${c.public !== false ? 'checked' : ''}> Показывать персонажа в общем ростере партии</label>
    </div>`;
    $('#f-lang').oninput = (e) => { c.languages = e.target.value; edChanged(); };
    $('#f-notes').oninput = (e) => { c.notes = e.target.value; edChanged(); };
    $('#f-public').onchange = (e) => { c.public = e.target.checked; edChanged(); };
  }
}

const ACQUISITION_SOURCES=[
  ['loot','Loot','Добыча'],['gift','Gift','Подарок'],['crafted','Crafted','Создано'],
  ['role_access','Role Access','Доступ роли'],['gm_award','GM Award','Награда GM'],
  ['custom','Custom','Custom'],['other','Other','Другое'],
];
function acquisitionSourceOptions(selected,allowEmpty=false){return `${allowEmpty?`<option value="">${T('Keep recorded source','Сохранить текущий источник')}</option>`:''}${ACQUISITION_SOURCES.map(([id,en,ru])=>`<option value="${id}" ${selected===id?'selected':''}>${T(en,ru)}</option>`).join('')}`;}
function acquisitionSourceLabel(source){const row=ACQUISITION_SOURCES.find(([id])=>id===source);return row?T(row[1],row[2]):source||'';}

function openCatalogAcquisitionModal(item,onConfirm,options={}){
  const modal=openModal(`<h2>${T('Add found item','Добавить найденный предмет')}</h2><div class="panel accent mb"><b>${esc(item.name)}</b><div class="small muted">${esc(item.source||'Database')} · ${item.price!=null?money(item.price):'—'}</div></div><div class="grid cols-2"><label class="f"><span>${T('Acquisition source *','Источник получения *')}</span><select id="acq-source">${acquisitionSourceOptions('loot')}</select></label>${options.quantity===false?'':`<label class="f"><span>${T('Quantity','Количество')}</span><input id="acq-qty" type="number" min="1" max="99" value="1"></label>`}<label class="f"><span>${T('Personal name (optional)','Собственное имя (необязательно)')}</span><input id="acq-name" maxlength="120" placeholder="${esc(item.name)}"></label></div><label class="f"><span>${T('Where did it come from?','Откуда предмет?')}</span><textarea id="acq-note" maxlength="500" rows="3" placeholder="${T('Found during the warehouse run…','Найден во время дела на складе…')}"></textarea></label><div class="row"><button id="acq-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="acq-add">${T('Add to Inventory','Добавить в Inventory')}</button></div>`);
  $('#acq-cancel',modal).onclick=closeModal;
  $('#acq-add',modal).onclick=()=>{const source=$('#acq-source',modal).value;if(!source)return;const qty=options.quantity===false?1:Math.max(1,Math.min(99,Number($('#acq-qty',modal).value)||1));const result={acquisition_source:source,acquisition_note:$('#acq-note',modal).value.trim(),custom_name:$('#acq-name',modal).value.trim(),qty};closeModal();onConfirm(result);};
}

function openOwnedItemEditor(item,onSave){
  const isNew=!item,isCustom=isNew||!!item.is_custom,draft=JSON.parse(JSON.stringify(item||{}));
  const categories=[['custom',T('Custom / Story Item','Custom / сюжетный предмет')],...(state.meta.cats||[]).filter(cat=>cat.id!=='cyberware').map(cat=>[cat.id,`${cat.emoji} ${catalogCategoryName(cat)}`])];
  const selectedSource=draft.acquisition_source||(isNew?'loot':'');
  const modal=openModal(`<h2>${isNew?T('Create Custom / Found Item','Создать Custom / найденный предмет'):T('Edit Item Instance','Редактировать экземпляр')}</h2>${isCustom?'<span class="tag">CUSTOM · MANUAL</span>':'<span class="tag">DATABASE ITEM</span>'}<div class="grid cols-2 mt"><label class="f"><span>${isCustom?T('Name *','Название *'):T('Personal name (optional)','Собственное имя (необязательно)')}</span><input id="owned-name" maxlength="120" value="${esc(isCustom?(draft.custom_name||draft.name||''):(draft.custom_name||''))}" placeholder="${esc(draft.name||'')}"></label>${isCustom?`<label class="f"><span>${T('Category','Категория')}</span><select id="owned-cat">${categories.map(([id,label])=>`<option value="${id}" ${(draft.cat||'custom')===id?'selected':''}>${esc(label)}</option>`).join('')}</select></label><label class="f"><span>${T('Reference value','Оценочная стоимость')}</span><input id="owned-price" type="number" min="0" max="9999999" step="1" value="${draft.price||0}"></label><label class="checkbox"><input id="owned-stackable" type="checkbox" ${draft.stackable?'checked':''}> ${T('Stackable quantity','Складывается в stack')}</label>`:`<div class="f"><span>${T('Database item','Предмет Database')}</span><b>${esc(draft.name||'')}</b></div>`}<label class="f"><span>${T('Quantity','Количество')}</span><input id="owned-qty" type="number" min="1" max="999" value="${draft.qty||1}" ${!isCustom&&draft.cat!=='ammo'?'disabled':''}></label><label class="f"><span>${T('Acquisition source','Источник получения')}</span><select id="owned-source">${acquisitionSourceOptions(selectedSource,!isNew)}</select></label></div>${isCustom?`<label class="f"><span>${T('Public description','Описание')}</span><textarea id="owned-desc" maxlength="4000" rows="4">${esc(draft.desc||'')}</textarea></label>`:''}<label class="f"><span>${T('Acquisition details','Обстоятельства получения')}</span><textarea id="owned-acq-note" maxlength="500" rows="2">${esc(draft.acquisition_note||'')}</textarea></label><label class="f"><span>${T('Private item notes','Личные заметки предмета')}</span><textarea id="owned-notes" maxlength="2000" rows="3">${esc(draft.notes||'')}</textarea></label><p class="small muted">${isCustom?T('Custom items are narrative/manual until Structured Effects are added. They cannot inject weapon, armor, or Cyberware mechanics.','Custom items остаются narrative/manual до Structured Effects и не могут подменять механику оружия, брони или Cyberware.'):T('Database mechanics are server-controlled; only this owned instance metadata can change.','Механика Database контролируется сервером; меняются только данные этого экземпляра.')}</p><div class="row"><button id="owned-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="owned-save">${T('Save Item','Сохранить предмет')}</button></div>`,true);
  $('#owned-cancel',modal).onclick=closeModal;
  $('#owned-save',modal).onclick=()=>{const name=$('#owned-name',modal).value.trim();if(isCustom&&!name){toast(T('Item name is required.','Укажите название предмета.'),true);return;}const source=$('#owned-source',modal).value;if(isNew&&!source){toast(T('Choose an acquisition source.','Выберите источник получения.'),true);return;}const result={...draft,custom_name:name,qty:Math.max(1,Math.min(999,Number($('#owned-qty',modal).value)||1)),notes:$('#owned-notes',modal).value.trim(),acquisition_source:source,acquisition_note:$('#owned-acq-note',modal).value.trim()};if(isCustom)Object.assign(result,{is_custom:true,key:draft.key||'custom',name,cat:$('#owned-cat',modal).value,price:Math.max(0,Number($('#owned-price',modal).value)||0),stackable:$('#owned-stackable',modal).checked,desc:$('#owned-desc',modal).value.trim(),state:draft.state||'carried',manual_resolution_required:true});closeModal();onSave(result);};
}

function addInvItem(it,meta={}) {
  const c = state.editor.char;c.inventory=c.inventory||[];
  const qty=Math.max(1,Math.min(99,Number(meta.qty)||1)),stackable=it.stackable===true||it.cat==='ammo';
  const base={key:it.id,catalog_item_id:it.id,cat:it.cat,name:it.name,custom_name:meta.custom_name||'',price:it.price,qty:stackable?qty:1,state:'carried',damage:it.damage||null,sp:it.sp!=null?it.sp:null,hl:it.hl||0,fields:{...(it.fields||{})},mechanics:{...(it.mechanics||{})},source:it.source||'',acquisition_source:meta.acquisition_source||'loot',acquisition_note:meta.acquisition_note||''};
  if(stackable){const ex=c.inventory.find(x=>x.key===it.id&&(x.custom_name||'')===base.custom_name&&(x.state||'carried')==='carried'&&x.acquisition_source===base.acquisition_source&&String(x.acquisition_note||'')===String(base.acquisition_note||''));if(ex)ex.qty=(ex.qty||1)+qty;else c.inventory.push(base);}else for(let index=0;index<qty;index++)c.inventory.push({...base});
  edChanged();
}

function renderInventoryList() {
  const box = $('#inv-list');
  if (!box) return;
  const c = state.editor.char;
  const inv = c.inventory || [];
  if (!inv.length) { box.innerHTML = '<div class="empty">Пусто. Совсем. Даже пушки нет.</div>'; return; }
  box.innerHTML = inv.map((i,index) => `
    <div class="inv-row" data-index="${index}">
      <span class="iname">${esc(i.custom_name||i.name)}</span>${i.is_custom?'<span class="tag">CUSTOM · MANUAL</span>':''}<span class="chip">${esc(i.state||'carried')}</span>
      ${i.damage ? `<span class="weap-dmg">${esc(i.damage)}</span>` : ''}
      ${i.sp != null ? `<span class="chip">SP ${i.sp}</span>` : ''}
      ${i.acquisition_source?`<span class="chip">${esc(acquisitionSourceLabel(i.acquisition_source))}</span>`:''}<span class="muted small">${money(i.price || 0)}</span>
      ${(i.stackable||i.cat==='ammo')?`<button class="btn-sm" data-act="minus">−</button><b>${i.qty || 1}</b><button class="btn-sm" data-act="plus">＋</button>`:'<b>×1</b>'}
      <button class="btn-sm" data-act="edit">✎</button><button class="btn-sm btn-danger" data-act="del">✕</button>
    </div>`).join('');
  $$('.inv-row', box).forEach(row => {
    $$('button', row).forEach(b => b.onclick = () => {
      const index=Number(row.dataset.index),item=c.inventory[index];
      if (!item) return;
      if(b.dataset.act==='edit'){openOwnedItemEditor(item,updated=>{c.inventory[index]=updated;renderInventoryList();edChanged();});return;}
      if (b.dataset.act === 'plus') item.qty = (item.qty || 1) + 1;
      if (b.dataset.act === 'minus') item.qty = Math.max(1,(item.qty || 1) - 1);
      if (b.dataset.act === 'del') {
        c.inventory.splice(index,1);
        for(const location of ['head','body','shield'])if(c.armor?.[location]?.instance_id&&c.armor[location].instance_id===item.instance_id)delete c.armor[location];
      }
      renderInventoryList(); edChanged();
    });
  });
}

function renderChromeList() {
  const box = $('#chrome-list');
  if (!box) return;
  const c = state.editor.char;
  const cw = c.cyberware || [];
  if (!cw.length) { box.innerHTML = '<div class="empty">Ты ещё чист от хрома. Пока что.</div>'; return; }
  box.innerHTML = cw.map((i, idx) => `
    <div class="inv-row">
      <span class="iname">${esc(i.custom_name||i.name)}</span><span class="hl-badge">HL ${i.hl || 0}</span><span class="chip">${esc(i.type || 'Cyberware')}</span><span class="tag">${i.state==='installed'?T('INSTALLED','УСТАНОВЛЕНО'):T('STAGED','ПОДГОТОВЛЕНО')}</span>${i.acquisition_source?`<span class="chip">${esc(acquisitionSourceLabel(i.acquisition_source))}</span>`:''}
      <button class="btn-sm" data-chrome-edit="${idx}">✎</button>${i.state==='installed'?`<span class="small muted">${T('Use audited Uninstall on the Dossier','Используйте audited Uninstall в Dossier')}</span>`:`<button class="btn-sm btn-danger" data-chrome-del="${idx}">✕ ${T('remove','удалить')}</button>`}
    </div>`).join('');
  $$('[data-chrome-edit]',box).forEach(button=>button.onclick=()=>{const index=Number(button.dataset.chromeEdit);openOwnedItemEditor(c.cyberware[index],updated=>{c.cyberware[index]=updated;renderChromeList();edChanged();});});
  $$('[data-chrome-del]', box).forEach(b => b.onclick = () => {c.cyberware.splice(Number(b.dataset.chromeDel), 1);renderChromeList();edChanged();});
}

function renderArmorSlots() {
  const box = $('#armor-slots');
  if (!box) return;
  const c = state.editor.char;
  c.armor = c.armor || {};
  if (!c.armor.body && (c.armor.body_outer || c.armor.body_inner)) {
    const old = [c.armor.body_outer, c.armor.body_inner].filter(Boolean);
    c.armor.body = old.sort((a, b) => (num(b.sp) || 0) - (num(a.sp) || 0))[0] || null;
  }
  const slotDefs = [['body', T('Body','Тело')], ['head', T('Head','Голова')]];
  box.innerHTML = slotDefs.map(([slot, ru]) => {
    const a = c.armor[slot];
    const penalty = a ? Object.entries(armorPenalties(a)).filter(([,v]) => v).map(([k,v]) => `${k} ${v}`).join(' · ') : '';
    return `<div class="card">
      <h3>${ru}</h3>
      ${a ? `<div class="row" style="justify-content:space-between">
          <div><b>${esc(a.name)}</b><div class="small muted">SP ${a.sp}${penalty ? ' · ' + esc(penalty) : ''}</div></div>
          <button class="btn-sm btn-danger" data-clear="${slot}">✕</button></div>`
        : `<div class="muted small mb">${T('— empty —','— пусто —')}</div>`}
      <button class="btn-sm mt" data-pick="${slot}">${T('Choose Armor','Выбрать броню')}</button>
    </div>`;
  }).join('');
  $$('[data-pick]', box).forEach(b => {
    const slot = b.dataset.pick;
    b.onclick = () => pickItem(['armor'], `Броня: ${slot === 'body' ? 'тело' : 'голова'}`, it => {
      c.inventory=c.inventory||[];
      let owned=c.inventory.find(entry=>entry.cat==='armor'&&(entry.catalog_item_id||String(entry.key||'').split('@')[0])===it.id&&!['equipped','installed'].includes(entry.state));
      const equip=meta=>{if(!owned){addInvItem(it,meta);owned=c.inventory[c.inventory.length-1];}owned.state='equipped';const piece={key:it.id+(it.armor_bundled?'@set':'@'+slot),source_key:it.id,catalog_item_id:it.id,instance_id:owned.instance_id,name:it.name,sp:it.sp||0,penalties:{...(it.penalties||{})},bundled:!!it.armor_bundled};if(it.armor_bundled){c.armor.body={...piece};c.armor.head={...piece};}else c.armor[slot]=piece;renderArmorSlots();edChanged();};
      if(owned)equip({});else openCatalogAcquisitionModal(it,equip,{quantity:false});
    }, it => !(it.armor_locations || []).includes('shield') && (it.armor_locations || ['body','head']).includes(slot));
  });
  $$('[data-clear]', box).forEach(b => b.onclick = () => {
    const removed = c.armor[b.dataset.clear];
    delete c.armor[b.dataset.clear];
    if(removed?.instance_id){const owned=(c.inventory||[]).find(item=>item.instance_id===removed.instance_id);if(owned)owned.state='carried';}
    if (removed && removed.bundled) {
      for (const slot of ['body','head']) if (c.armor[slot] && c.armor[slot].key === removed.key) delete c.armor[slot];
    }
    renderArmorSlots(); edChanged();
  });
}

/* выбор предмета из каталога */
async function pickItem(cats, title, onPick, predicate) {
  const m = openModal(`
    <h2>${esc(title)}</h2>
    <div class="searchbar"><input id="pk-q" placeholder="Поиск…" autofocus><button id="pk-go">Найти</button></div>
    <div id="pk-list" style="max-height:55vh;overflow:auto">${spinner()}</div>`, true);
  const load = async () => {
    const q = $('#pk-q', m).value;
    const p = new URLSearchParams({ q, limit: 40 });
    if (cats && cats.length === 1) p.set('cat', cats[0]);
    const data = await api('/api/items?' + p);
    let items = data.items;
    if (cats && cats.length > 1) items = items.filter(i => cats.includes(i.cat));
    if (predicate) items = items.filter(predicate);
    $('#pk-list', m).innerHTML = items.length ? items.map(it => `
      <div class="inv-row" style="cursor:pointer" data-id="${it.id}">
        <span class="iname">${esc(it.name)}</span>
        ${it.damage ? `<span class="weap-dmg">${esc(it.damage)}</span>` : ''}
        ${it.hl ? `<span class="hl-badge">HL ${it.hl}</span>` : ''}
        <span class="muted small">${it.price != null ? money(it.price) : '—'}</span>
      </div>`).join('') : '<div class="empty">Ничего не нашлось.</div>';
    $$('.inv-row', m).forEach(row => row.onclick = () => {
      const it = items.find(x => x.id === row.dataset.id);
      if (it) { closeModal(); onPick(it); }
    });
  };
  $('#pk-go', m).onclick = load;
  $('#pk-q', m).onkeydown = (e) => { if (e.key === 'Enter') load(); };
  await load();
}
