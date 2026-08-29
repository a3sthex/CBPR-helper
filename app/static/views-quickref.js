// Quick Reference — страница быстрой справки.
// P3-frontend, срез S1: вынесена из app.js. Классические скрипты делят глобальную область;
// порядок загрузки в index.html: app.js → views-quickref.js (инфра-функции остаются в app.js).

async function viewCalc(view) {
  const [range, auto] = [state.meta.range_table, state.meta.autofire_table];
  view.innerHTML = `
  <div class="page-head"><div><h1>🎲 ${T('Calculator','Калькулятор')}</h1><div class="sub">${T('Damage, Armor, dice, Critical Injuries, Autofire, and Range DVs.','Урон, броня, кости, критические травмы, автоогонь и DV дистанции.')}</div></div></div>
  <div class="grid cols-2">
    <div class="panel">
      <h2>💥 ${T('Damage Calculation','Расчёт урона')}</h2>
      <div class="row mb">
        <label class="f grow" style="margin:0"><span>${T('Damage Formula','Формула урона')}</span><input id="dc-expr" value="3d6" placeholder="3d6, 5d6, 2d6+3…"></label>
        <button class="btn-primary" id="dc-roll">${T('Roll','Бросить')}</button>
      </div>
      <div class="row mb small muted" id="dc-presets">
        ${['2d6', '3d6', '4d6', '5d6', '6d6', '2d6+3'].map(d => `<button class="btn-sm" data-preset="${d}">${d}</button>`).join('')}
      </div>
      <div class="grid cols-2">
        <label class="f"><span>${T('Target Armor SP','SP брони цели')}</span><input id="dc-sp" type="number" value="11" min="0" max="50"></label>
        <label class="f"><span>${T('Target Max HP','Max HP цели')}</span><input id="dc-hp" type="number" value="40" min="1"></label>
      </div>
      <label class="f"><span>${T('Target Current HP','Текущее HP цели')}</span><input id="dc-hpcur" type="number" value="40" min="0"></label>
      <label class="checkbox mb"><input type="checkbox" id="dc-melee"> ${T('Melee / Armor Piercing (target SP is halved, rounded up)','Ближний бой / бронепробой (SP цели делится на 2, округление вверх)')}</label>
      <div id="dc-out" class="calc-out"></div>
    </div>
    <div class="panel">
      <h2>🎯 ${T('Dice Rolls','Броски костей')}</h2>
      <div class="row mb">
        <input id="dr-expr" value="1d10" style="flex:1">
        <button class="btn-primary" id="dr-roll">${T('Roll','Бросить')}</button>
      </div>
      <div class="row small muted mb">${['1d10', '2d6', '3d6', '1d6+2'].map(d => `<button class="btn-sm" data-dpreset="${d}">${d}</button>`).join('')}</div>
      <div id="dr-out"></div>
      <hr>
      <h2>🛡️ ${T('Multiple Armor Layers','Несколько слоёв брони')}</h2>
      <p class="small muted">${T('SP does not stack: only the highest SP at a location applies. When penetrated, all worn layers at that location ablate together.','SP не складывается: на локации действует только наибольший SP. При пробитии все надетые слои на этой локации абляируются одновременно.')}</p>
      <div class="grid cols-2">
        <label class="f"><span>${T('Outer SP','SP верхнего')}</span><input id="ar-o" type="number" value="11"></label>
        <label class="f"><span>${T('Inner SP','SP нижнего')}</span><input id="ar-i" type="number" value="7"></label>
      </div>
      <div class="calc-out" id="ar-out"></div>
    </div>
  </div>
  <div class="grid cols-2 mt">
    <div class="panel">
      <h2>☠️ ${T('Critical Injuries','Критические травмы')}</h2>
      <p class="small muted">${T('Two or more sixes on attack damage dice cause a Critical Injury (+5 damage directly to HP; Armor does not reduce it). Roll 2d6 for the location; repeat if the target already has that injury.','2+ шестёрки на кубах урона атаки = крит. травма (+5 урона сразу по HP, броня не снижает). Брось 2d6 по локации; повторяй, пока не выпадет травма, которой у цели ещё нет.')}</p>
      <div class="row mb">
        <button class="btn-primary" id="ci-body">${T('Roll 2d6 — Body','Бросить 2d6 — тело')}</button>
        <button id="ci-head">${T('Roll 2d6 — Head','Бросить 2d6 — голова')}</button>
      </div>
      <div id="ci-out" class="calc-out"></div>
      <details class="guide-section small-details"><summary>${T('Injury Tables','Таблицы травм')}</summary>
        ${critTableHtml(state.meta.crit_body, T('Body','Тело'))}
        ${critTableHtml(state.meta.crit_head, T('Head','Голова'))}
      </details>
    </div>
    <div class="panel">
      <h2>🔥 ${T('Autofire','Автоогонь')}</h2>
      <p class="small muted">${T('An Action plus 10 bullets. Use the Autofire Skill and Autofire table. Damage is 2d6 × (Check − DV), limited by the weapon’s maximum multiplier.','Действие + 10 пуль. Навык Autofire, таблица автоогня. Урон = 2d6 × (бросок − DV), максимум множителя — у оружия.')}</p>
      <div class="grid cols-2">
        <label class="f"><span>${T('Weapon Type','Тип оружия')}</span><select id="af-type">
          <option value="3">SMG / Machine Pistol (×3)</option>
          <option value="4">Assault Rifle / Machine Gun (×4)</option>
        </select></label>
        <label class="f"><span>${T('DV (by range)','DV (по дистанции)')}</span><input id="af-dv" type="number" value="20" min="1"></label>
      </div>
      <label class="f"><span>REF + Autofire</span><input id="af-mod" type="number" value="14"></label>
      <button class="btn-primary mb" id="af-roll">${T('Roll Attack','Бросить атаку')}</button>
      <div id="af-out" class="calc-out"></div>
    </div>
  </div>
  <div class="grid cols-2 mt">
    <div class="panel">
      <h2>💀 ${T('Death Save','Спасбросок от смерти')}</h2>
      <p class="small muted">${T('At the start of a Turn while Mortally Wounded (HP &lt; 1), roll 1d10 ≤ BODY − penalty. A 10 always fails. The penalty increases by 1 after every roll.','В начале хода при смертельном ранении (HP < 1): 1d10 ≤ BODY − штраф. 10 — всегда провал. Штраф растёт на +1 за каждый бросок.')}</p>
      <div class="grid cols-2">
        <label class="f"><span>BODY</span><input id="ds-body" type="number" value="6" min="1" max="15"></label>
        <label class="f"><span>${T('Death Save Penalty','Штраф (Death Save Penalty)')}</span><input id="ds-pen" type="number" value="0" min="0" max="20"></label>
      </div>
      <button class="btn-primary mb" id="ds-roll">${T('Roll 1d10','Бросить 1d10')}</button>
      <div id="ds-out" class="calc-out"></div>
    </div>
    <div class="panel">
      <h2>🩹 ${T('Wound States','Состояния ранений')}</h2>
      ${woundStatesHtml()}
    </div>
  </div>
  <div class="panel mt">
    <h2>📏 ${T('DV Table (Range)','Таблица DV (дальность)')}</h2>
    <div style="overflow-x:auto">${tableHtml(range)}</div>
  </div>
  <div class="panel mt">
    <h2>🔥 ${T('DV Table (Autofire)','Таблица DV (автоогонь)')}</h2>
    <div style="overflow-x:auto">${tableHtml(auto)}</div>
  </div>
  <div class="panel mt">
    <div class="row" style="justify-content:space-between"><h2>◈ ${T('General Difficulty Values','Общие уровни сложности')}</h2><span class="tag source">CP:R p. 129</span></div>
    <div class="table-scroll"><table class="rtable"><tr><th>${T('Difficulty','Сложность')}</th><th>DV</th><th>${T('Guidance','Ориентир')}</th></tr>${[
      ['Simple','Простая',9,'Most people can do it without thinking.','Большинство делает это не задумываясь.'],
      ['Everyday','Повседневная',13,'No special training is normally required.','Обычно не требует специальной подготовки.'],
      ['Difficult','Трудная',15,'Training or natural talent is important.','Важны подготовка или природный талант.'],
      ['Professional','Профессиональная',17,'Requires professional-level training.','Требует профессиональной подготовки.'],
      ['Heroic','Героическая',21,'Only highly trained specialists succeed reliably.','Надёжно справляются только отличные специалисты.'],
      ['Incredible','Невероятная',24,'A feat for the very best in the field.','Достижение для лучших в профессии.'],
      ['Legendary','Легендарная',29,'The kind of feat people tell stories about.','О таком достижении будут рассказывать истории.'],
    ].map(([en,ru,dv,de,dr])=>`<tr><td><b>${T(en,ru)}</b></td><td>${dv}</td><td>${T(de,dr)}</td></tr>`).join('')}</table></div>
  </div>`;

  const doDamage = () => {
    const expr = $('#dc-expr').value.trim() || '3d6';
    const r = rollDice(expr);
    const out = $('#dc-out');
    if (!r) { out.innerHTML = `<span style="color:var(--red)">${T('Formula not recognized. Example: 3d6 or 2d6+3','Не понял формулу. Пример: 3d6 или 2d6+3')}</span>`; return; }
    const sp = Math.max(0, num($('#dc-sp').value) || 0);
    const spEff = $('#dc-melee').checked ? Math.ceil(sp / 2) : sp;
    const net = r.total - spEff;
    const hpMax = num($('#dc-hp').value) || 0;
    let hpCur = num($('#dc-hpcur').value);
    if (hpCur == null) hpCur = hpMax;
    const crit = r.die === 6 && r.rolls.filter(x => x === 6).length >= 2;
    let lines = [
      `<span class="dice-face">🎲 ${r.rolls.join(' + ')}${r.mod ? (r.mod > 0 ? ' + ' : ' − ') + Math.abs(r.mod) : ''} = ${r.total}</span>`,
    ];
    if (crit) lines.push(`<div class="crit-hit">🔥 ${T('Two sixes! Critical Injury (+5 HP; Armor does not reduce it) — roll 2d6 in the Critical Injuries panel.','Две шестёрки! Критическая травма (+5 HP, броня не снижает) — брось 2d6 в панели «Критические травмы».')}</div>`);
    if (net > 0) {
      lines.push(`<div>${T('Damage:','Урон:')} <b style="color:var(--magenta)">${net}</b> (${T('SP','SP')} ${sp}${spEff !== sp ? ' → ' + spEff : ''} ${T('subtracted','вычтен')}). ${T('Armor penetrated — SP ablates by 1.','Броня пробита — SP абляируется на 1.')}</div>`);
      const newHp = Math.max(0, hpCur - net);
      const sw = Math.ceil(hpMax / 2);
      let stateTxt;
      if (newHp < 1) stateTxt = `<b style="color:var(--red)">${T('Mortally Wounded (HP &lt; 1): −4 to all Actions and −6 MOVE. Make a Death Save at the start of each Turn. Stabilization: Paramedic DV15 → 1 HP and unconscious.','Смертельное ранение (HP &lt; 1): −4 ко всем действиям, −6 MOVE. В начале хода — спасбросок от смерти. Стабилизация: Paramedic DV15 → 1 HP, без сознания.')}</b>`;
      else if (newHp <= sw) stateTxt = `<b style="color:var(--orange)">${T(`Seriously Wounded (HP ≤ half = ${sw}): −2 to all Actions. Stabilization: DV13.`,`Серьёзное ранение (HP ≤ ½ = ${sw}): −2 ко всем действиям. Стабилизация: DV13.`)}</b>`;
      else stateTxt = `<b style="color:var(--green)">${T('Lightly Wounded: no effect. The target is still standing.','Лёгкое ранение: эффектов нет. Цель держится.')}</b>`;
      lines.push(`<div>${T('Target HP:','HP цели:')} ${hpCur} → <b>${newHp}</b>. ${stateTxt}</div>`);
    } else {
      lines.push(`<div>${T(`Armor holds (damage ${r.total} ≤ SP ${spEff}). HP and SP are unchanged.`,`Броня держит (урон ${r.total} ≤ SP ${spEff}). HP не тратится, SP не абляируется.`)}</div>`);
    }
    out.innerHTML = lines.join('');
  };
  $('#dc-roll').onclick = doDamage;
  $$('#dc-presets [data-preset]', view).forEach(b => b.onclick = () => { $('#dc-expr').value = b.dataset.preset; doDamage(); });

  const doRoll = () => {
    const r = rollDice($('#dr-expr').value.trim() || '1d10');
    const out = $('#dr-out');
    if (!r) { out.innerHTML = `<span style="color:var(--red)">${T('Formula not recognized','Не понял формулу')}</span>`; return; }
    out.innerHTML = `<div class="calc-out"><span class="dice-face">🎲 ${r.rolls.join(', ')}</span> = <b>${r.total}</b></div>`;
  };
  $('#dr-roll').onclick = doRoll;
  $$('[data-dpreset]', view).forEach(b => b.onclick = () => { $('#dr-expr').value = b.dataset.dpreset; doRoll(); });

  const doArmor = () => {
    const o = num($('#ar-o').value) || 0, i = num($('#ar-i').value) || 0;
    const hi = Math.max(o, i);
    $('#ar-out').innerHTML = `${T('Effective SP:','Действующий SP:')} <b>${hi}</b> <span class="muted small">${T(`(maximum of ${o} and ${i}; SP does not stack)`,`(максимум из ${o} и ${i}; SP не складывается)`)}</span>`;
  };
  ['ar-o', 'ar-i'].forEach(id => $('#' + id).oninput = doArmor);

  // критическая травма
  const doCrit = (table, label) => {
    const r = rollDice('2d6');
    const row = (table || []).find(x => x[0] === r.total) || null;
    const out = $('#ci-out');
    if (!row) { out.innerHTML = T('Roll is outside the table (2d6: 2–12)','Бросок вне таблицы (2d6: 2–12)'); return; }
    out.innerHTML = `
      <span class="dice-face">🎲 ${r.rolls.join(' + ')} = <b>${r.total}</b></span>
      <div><b style="color:var(--magenta)">${esc(row[1])}</b> <span class="tag">${esc(label)}</span></div>
      <div>${esc(row[2])}</div>
      <div class="small muted">Quick Fix: ${esc(row[3])} · Treatment: ${esc(row[4])} · ${T('+5 HP immediately.','+5 HP сразу.')}</div>`;
  };
  $('#ci-body').onclick = () => doCrit(state.meta.crit_body, T('Body','тело'));
  $('#ci-head').onclick = () => doCrit(state.meta.crit_head, T('Head','голова'));

  // автоогонь
  $('#af-roll').onclick = () => {
    const maxMul = num($('#af-type').value) || 3;
    const dv = num($('#af-dv').value) || 0;
    const mod = num($('#af-mod').value) || 0;
    const atk = rollDice('1d10');
    const total = atk.total + mod;
    const margin = total - dv;
    const out = $('#af-out');
    let lines = [`${T('Attack:','Атака:')} 🎲 ${atk.rolls[0]} + ${mod} = <b>${total}</b> ${T('against DV','против DV')} ${dv}.`];
    if (margin <= 0) {
      lines.push(`<div style="color:var(--red)">${T(`Miss (margin ${margin} ≤ 0). The bullets hit the wall.`,`Промах (разница ${margin} ≤ 0). Пули ушли в стену.`)}</div>`);
    } else {
      const dmg = rollDice('2d6');
      const mul = Math.min(margin, maxMul);
      const crit = dmg.rolls[0] === 6 && dmg.rolls[1] === 6;
      lines.push(`${T('Hit! Multiplier:','Попадание! Множитель:')} min(${margin}, ${maxMul}) = <b>${mul}</b>.`);
      lines.push(`<div>${T('Autofire damage:','Урон автоогня:')} 2d6 (${dmg.rolls.join(' + ')}) × ${mul} = <b style="color:var(--magenta)">${dmg.total * mul}</b> ${T('(before SP).','(до вычета SP).')}</div>`);
      if (crit) lines.push(`<div class="crit-hit">🔥 ${T('Both damage dice are sixes — add a Critical Injury!','Обе шестёрки на кубах урона — плюс крит. травма!')}</div>`);
    }
    out.innerHTML = lines.join('');
  };

  // спасбросок смерти
  $('#ds-roll').onclick = () => {
    const body = num($('#ds-body').value) || 0;
    const pen = num($('#ds-pen').value) || 0;
    const r = rollDice('1d10');
    const out = $('#ds-out');
    if (r.rolls[0] === 10) {
      out.innerHTML = `🎲 <b>10</b> — <b style="color:var(--red)">${T('automatic failure. You are dead.','автоматический провал. Ты мёртв.')}</b>`;
    } else if (r.rolls[0] <= body - pen) {
      out.innerHTML = `🎲 ${r.rolls[0]} ≤ ${body}${pen ? ' − ' + pen : ''} — <b style="color:var(--green)">${T('you hold on','держишься')}</b>. ${T(`The next roll has +1 penalty (new penalty ${pen + 1}).`,`Следующий бросок со штрафом +1 (текущий станет ${pen + 1}).`)}`;
    } else {
      out.innerHTML = `🎲 ${r.rolls[0]} > ${body}${pen ? ' − ' + pen : ''} — <b style="color:var(--red)">${T('failure. You are dead.','провал. Ты мёртв.')}</b>`;
    }
  };

  doDamage(); doArmor();
}
