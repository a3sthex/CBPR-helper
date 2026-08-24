/* Player Actions panel — separate page reachable from Dossier (23.3) */
async function viewActions(view, charId) {
  if (!state.me) { view.innerHTML = '<div class="empty">Sign in.</div>'; return; }
  view.innerHTML = '<div class="page-head"><div><h1>🎲 Actions</h1></div><button class="btn-sm" onclick="history.back()">← Back</button></div>' + spinner();
  try {
    const c = await api('/api/characters/' + charId);
    const ch = c.data, d = c.derived;
    const mine = c.owner || (state.me && state.me.is_gm);
    const hpCur = ch.hp_cur == null ? d.hp_max : ch.hp_cur;
    const luckMax = (ch.stats || {}).LUCK || 0;
    const reload = () => viewActions(view, charId);

    view.innerHTML = `
    <div class="page-head">
      <div><h1>🎲 ${T('Actions','Действия')} · ${esc(ch.handle||'—')}</h1>
      <div class="sub">${(ch.roles||[]).map(r=>esc(r.name)+' '+r.rank).join(' · ')||esc(ch.role||'')}</div></div>
      <div class="row"><a class="btn-sm" href="#/char/${charId}">📄 ${T('Dossier','Досье')}</a></div>
    </div>
    <div class="panel accent mb">
      <div class="derived">
        <span class="dstat resource-stat"><span class="v">${hpCur} / ${d.hp_max||'—'}</span><span class="k">HP</span>
          ${mine?`<span class="resource-actions"><button data-ra="hp|-5">−5</button><button data-ra="hp|-1">−1</button><button data-ra="hp|1">+1</button><button data-ra="hp|5">+5</button></span>`:''}</span>
        <span class="dstat resource-stat"><span class="v">${ch.luck_cur||0} / ${luckMax}</span><span class="k">LUCK</span>
          <span class="luck-pips">${Array.from({length:luckMax},(_,i)=>'<i class="'+(i<(ch.luck_cur||0)?'filled':'')+'"></i>').join('')}</span>
          ${mine?`<span class="resource-actions"><button data-ra="luck|-1">${T('Spend','Потратить')}</button><button data-ra="luck|1">+1</button><button data-ra="luck|reset">${T('Reset','Сброс')}</button></span>`:''}</span>
        <span class="dstat resource-stat"><span class="v">${ch.reputation||0}</span><span class="k">${T('Reputation','Репутация')}</span>
          ${mine?`<span class="resource-actions"><button data-ra="reputation|-1">−1</button><button data-ra="reputation|1">+1</button></span>`:''}</span>
        <span class="dstat"><span class="v">${d.humanity_cur!=null?d.humanity_cur+'/'+d.humanity_max:'—'}</span><span class="k">${T('Humanity','Человечность')}</span></span>
        <span class="dstat"><span class="v">${d.sp_body!=null?d.sp_body:'—'}</span><span class="k">${T('Body SP','Броня тело')}</span></span>
        <span class="dstat"><span class="v">${d.sp_head!=null?d.sp_head:'—'}</span><span class="k">${T('Head SP','Броня голова')}</span></span>
      </div>
    </div>
    <div class="grid cols-2 sheet-layout" style="gap:18px">
      <div>
        <div class="panel mb">
          <h2>🎲 ${T('Skill Rolls','Броски навыков')}</h2>
          <div class="kv">
            ${(state.meta.skills||[]).filter(s=>{const lvl=(ch.skills||{})[s[1]]||0;return lvl>0;}).map(s=>{
              const lvl=(ch.skills||{})[s[1]]||0;
              const statVal=(d.effective_stats||{})[s[2]]||(ch.stats||{})[s[2]]||0;
              const base=statVal+lvl;
              return '<div><b>'+esc(s[1])+'</b><span>'+esc(s[2])+' '+statVal+' + '+lvl+' = <b>'+base+'</b> <button class="btn-sm" data-skill-roll="'+esc(s[1])+'|'+base+'">🎲 1d10+'+base+'</button></span></div>';
            }).join('')||'<div class="muted small">'+T('No skills above 0 yet.','Нет навыков выше 0.')+'</div>'}
          </div>
          <div id="roll-result" class="mt"></div>
        </div>
      </div>
      <div>
        <div class="panel mb">
          <h2>🎒 ${T('Quick Items','Быстрые предметы')}</h2>
          <div class="kv">
            ${(ch.inventory||[]).filter(i=>i.consumable||i.equippable).slice(0,20).map(i=>{
              return '<div><b>'+esc(i.custom_name||i.name)+'</b><span>'+(i.consumable?'×'+(i.qty||1)+' <button class="btn-sm" data-quick-use="'+esc(i.instance_id)+'">'+T('Use','Использовать')+'</button>':'')+'</span></div>';
            }).join('')||'<div class="muted small">'+T('No usable items.','Нет расходников.')+'</div>'}
          </div>
        </div>
        <div class="panel mb">
          <h2>🎲 ${T('Quick Dice','Быстрый куб')}</h2>
          <div class="row">
            ${['1d10','2d6','3d6','1d6'].map(expr=>'<button class="btn-sm" data-quick-roll="'+expr+'">'+expr+' 🎲</button>').join('')}
          </div>
          <div id="quick-dice-result" class="mt"></div>
        </div>
      </div>
    </div>`;

    // Resource buttons
    view.querySelectorAll('[data-ra]').forEach(btn => {
      btn.onclick = async () => {
        const [resource, action] = btn.dataset.ra.split('|');
        const body = { revision: c.revision, resource };
        if (action === 'reset') body.action = 'reset';
        else { body.action = 'delta'; body.value = Number(action); }
        try {
          await api('/api/characters/' + charId + '/resource', { method: 'POST', body });
          reload();
        } catch (e) { toast(e.message, true); }
      };
    });

    // Skill rolls
    view.querySelectorAll('[data-skill-roll]').forEach(btn => {
      btn.onclick = () => {
        const [skill, base] = btn.dataset.skillRoll.split('|');
        const die = Math.floor(Math.random() * 10) + 1;
        const total = Number(base) + die;
        $('#roll-result', view).innerHTML = '<div class="panel accent"><b>' + esc(skill) + '</b>: 🎲 ' + die + ' + ' + base + ' = <b>' + total + '</b></div>';
      };
    });

    // Quick use
    view.querySelectorAll('[data-quick-use]').forEach(btn => {
      btn.onclick = async () => {
        try {
          await api('/api/characters/' + charId + '/items/' + btn.dataset.quickUse + '/action', { method: 'POST', body: { revision: c.revision, action: 'use', amount: 1 } });
          toast(T('Item used.','Предмет использован.'));
          reload();
        } catch (e) { toast(e.message, true); }
      };
    });

    // Quick dice
    view.querySelectorAll('[data-quick-roll]').forEach(btn => {
      btn.onclick = () => {
        const expr = btn.dataset.quickRoll;
        const m = expr.match(/(\d+)d(\d+)/);
        if (!m) return;
        const n = Number(m[1]), s = Number(m[2]);
        const rolls = Array.from({ length: n }, () => Math.floor(Math.random() * s) + 1);
        const sum = rolls.reduce((a, b) => a + b, 0);
        $('#quick-dice-result', view).innerHTML = '<div class="panel accent">' + expr + ': [' + rolls.join(', ') + '] = <b>' + sum + '</b></div>';
      };
    });

  } catch (e) {
    view.innerHTML = '<div class="empty">⚠️ ' + esc(e.message) + '</div>';
  }
}
