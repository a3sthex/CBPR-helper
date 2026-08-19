/* CBPR Helper — фронтенд (vanilla JS, без зависимостей) */
'use strict';

/* ============================== утилиты ============================== */

const $ = (s, el) => (el || document).querySelector(s);
const $$ = (s, el) => Array.from((el || document).querySelectorAll(s));

function esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

const nf = new Intl.NumberFormat('ru-RU');
const money = (n) => '€$ ' + nf.format(Math.round(Number(n) || 0));

function timeAgo(ts) {
  const d = (Date.now() / 1000 - ts);
  if (d < 60) return 'только что';
  if (d < 3600) return Math.floor(d / 60) + ' мин назад';
  if (d < 86400) return Math.floor(d / 3600) + ' ч назад';
  return new Date(ts * 1000).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
}

function toast(msg, isErr) {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = 'toast' + (isErr ? ' err' : '');
  el.textContent = msg;
  root.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .4s'; }, 3200);
  setTimeout(() => el.remove(), 3700);
}

function openModal(html, wide) {
  const root = $('#modal-root');
  root.innerHTML = `<div class="modal${wide ? ' wide' : ''}"><button class="close" title="Закрыть">✕</button>${html}</div>`;
  root.classList.add('open');
  $('.close', root).onclick = closeModal;
  root.onmousedown = (e) => { if (e.target === root) closeModal(); };
  return root.firstElementChild;
}
function closeModal() { const r = $('#modal-root'); r.classList.remove('open'); r.innerHTML = ''; }
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeModal(); });

async function api(path, opts) {
  const o = Object.assign({ headers: {} }, opts);
  if (o.body && typeof o.body !== 'string') {
    o.body = JSON.stringify(o.body);
    o.headers['Content-Type'] = 'application/json';
  }
  const res = await fetch(path, o);
  let data = null;
  try { data = await res.json(); } catch (e) { /* пусто */ }
  if (!res.ok) {
    const msg = (data && data.error) || ('HTTP ' + res.status);
    const err = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return data;
}

function spinner() { return '<div class="empty"><span class="spin"></span> Загрузка…</div>'; }

/* ============================== состояние ============================== */

const state = {
  me: null,
  meta: null,
  cart: [],           // корзина рынка: {id, name, qty, price, mode}
  editor: null,       // текущий редактируемый персонаж
};
let guidesTab = null; // активная вкладка гайдов

/* ============================== правила (зеркало сервера) ============================== */

function num(v) {
  if (v == null || v === '') return null;
  const n = parseInt(v, 10);
  return isNaN(n) ? null : n;
}

function armorPenalties(piece) {
  if (!piece) return {};
  if (piece.penalties && typeof piece.penalties === 'object') {
    return Object.fromEntries(['REF', 'DEX', 'MOVE'].map(s => [s, num(piece.penalties[s]) || 0]));
  }
  const legacy = num(piece.penalty) || 0;
  return legacy ? { REF: legacy, DEX: legacy, MOVE: legacy } : {};
}

function derive(char) {
  const st = char.stats || {};
  const out = {};
  const body = num(st.BODY), will = num(st.WILL);
  if (body != null && will != null) {
    out.hp_max = 10 + 5 * Math.ceil((body + will) / 2);
    out.seriously_wounded = Math.ceil(out.hp_max / 2);
    out.death_save = body;
  }
  let hl = 0, humCut = 0;
  for (const c of (char.cyberware || [])) {
    if (c.humanity_exempt && c.key === 'creation-neuroport') continue;
    hl += num(c.hl) || 0;
    const t = String(c.type || '').toLowerCase();
    if (t.includes('borgware')) humCut += 4;
    else if (!t.includes('fashionware')) humCut += 2;
  }
  const emp = num(st.EMP);
  if (emp != null) {
    const start = emp * 10;
    out.humanity_max = start - humCut;
    let cur = num(char.humanity_cur);
    if (cur == null) cur = start - hl;
    out.humanity_cur = Math.min(cur, out.humanity_max);
    out.emp_cur = Math.max(0, Math.floor(out.humanity_cur / 10));
    out.hl_total = hl;
    out.hum_cut = humCut;
  }
  const armor = char.armor || {};
  const bodyPieces = [armor.body, armor.body_outer, armor.body_inner].filter(Boolean);
  const headPieces = [armor.head].filter(Boolean);
  const bodySP = bodyPieces.map(a => num(a.sp)).filter(v => v != null);
  const headSP = headPieces.map(a => num(a.sp)).filter(v => v != null);
  if (bodySP.length) out.sp_body = Math.max(...bodySP);
  if (headSP.length) out.sp_head = Math.max(...headSP);
  const penalties = { REF: 0, DEX: 0, MOVE: 0 };
  for (const piece of [...bodyPieces, ...headPieces]) {
    const pp = armorPenalties(piece);
    for (const stat of Object.keys(penalties)) penalties[stat] = Math.min(penalties[stat], pp[stat] || 0);
  }
  out.armor_penalties = penalties;
  out.armor_penalty = Math.min(...Object.values(penalties));
  return out;
}

function blankChar() {
  return {
    handle: '', role: 'Solo', role_rank: 4, player: '',
    appearance: '', background: '', notes: '', languages: '',
    stats: { INT: 5, REF: 5, DEX: 5, TECH: 5, COOL: 5, WILL: 5, LUCK: 5, MOVE: 5, BODY: 5, EMP: 5 },
    humanity_cur: null, hp_cur: null, cash: 2550,
    skills: {}, inventory: [], cyberware: [], armor: { head: null, body: null },
    public: true,
  };
}

/* ============================== роутер ============================== */

const routes = {
  '': viewHome, codex: viewCodex, guides: viewGuides, market: viewMarket, calc: viewCalc,
  characters: viewCharacters, roster: viewRoster, news: viewNews, jobs: viewJobs,
  login: viewLogin, register: viewRegister, profile: viewProfile,
};

async function route() {
  const hash = location.hash.replace(/^#\/?/, '');
  const [seg0, seg1] = hash.split('/');
  const view = $('#view');
  $$('#nav a').forEach(a => a.classList.toggle('active', a.dataset.route === seg0));
  window.scrollTo(0, 0);
  closeModal();
  try {
    if (seg0 === 'char') {
      const raw = seg1 || '';
      const charId = raw.split('?')[0];
      const isEdit = raw.includes('?edit');
      if (!charId || charId === '' || charId === 'new') { await viewWizard(); return; }
      if (isEdit) { await viewEditor(charId); return; }
      await viewSheet(charId); return;
    }
    const fn = routes[seg0] || viewHome;
    await fn(view);
  } catch (e) {
    view.innerHTML = `<div class="empty">⚠️ ${esc(e.message)}</div>`;
  }
}

function go(path) { location.hash = path; }

/* ============================== шапка / юзер ============================== */

function renderUserbox() {
  const box = $('#userbox');
  if (!state.me) {
    box.innerHTML = `<a class="btn-primary" style="padding:7px 14px;border-radius:8px;color:#041018" href="#/login">Войти</a>`;
    return;
  }
  const ini = (state.me.display_name || state.me.username || '?').slice(0, 1).toUpperCase();
  box.innerHTML = `
    <span class="userchip" id="userchip" title="Профиль">
      <span class="avatar">${esc(ini)}</span>
      <span>${esc(state.me.display_name)}</span>
      ${state.me.is_gm ? '<span class="gm-badge">ГМ</span>' : ''}
    </span>
    <button class="btn-sm" id="logout-btn">Выйти</button>`;
  $('#userchip').onclick = () => go('/profile');
  $('#logout-btn').onclick = async () => {
    try { await api('/api/logout', { method: 'POST' }); } catch (e) {}
    state.me = null;
    renderUserbox();
    route();
    toast('Вы вышли из системы');
  };
}

/* ============================== главная ============================== */

async function viewHome(view) {
  view.innerHTML = spinner();
  const [stats, news, jobs] = await Promise.all([
    api('/api/stats'), api('/api/news'), api('/api/jobs'),
  ]);
  const lastNews = news.news.slice(0, 3);
  const openJobs = jobs.jobs.filter(j => j.status === 'open').slice(0, 3);
  view.innerHTML = `
  <div class="hero">
    <h1>Ночной город <span class="accent">онлайн</span></h1>
    <p>Создавай эджраннеров, закупайся на чёрном рынке, веди ростер всей партии,
       читай сводки с улиц и находи заказы. Всё для твоей кампании по Cyberpunk RED.</p>
    <div class="row">
      <button class="btn-primary" onclick="location.hash='#/characters'">Создать персонажа</button>
      <button onclick="location.hash='#/market'">Чёрный рынок</button>
      <button onclick="location.hash='#/codex'">Справочник</button>
    </div>
    <div class="statbar mt">
      <span class="sb"><span class="v">${nf.format(stats.items)}</span><span class="k">предметов</span></span>
      <span class="sb"><span class="v">${nf.format(stats.characters)}</span><span class="k">персонажей</span></span>
      <span class="sb"><span class="v">${nf.format(stats.users)}</span><span class="k">эджраннеров</span></span>
      <span class="sb"><span class="v">${nf.format(stats.news)}</span><span class="k">новостей</span></span>
      <span class="sb"><span class="v">${nf.format(stats.open_jobs)}</span><span class="k">открытых заказов</span></span>
    </div>
  </div>
  <div class="grid cols-2">
    <div class="panel">
      <div class="row" style="justify-content:space-between">
        <h2 style="margin:0">📡 Сводки с улиц</h2>
        <a href="#/news" class="small">все новости →</a>
      </div>
      ${lastNews.length ? lastNews.map(n => `
        <div class="post mt">
          <div class="meta">${n.tag ? `<span class="tag">${esc(n.tag)}</span>` : ''}<span>${esc(n.author)}</span>·<span>${timeAgo(n.created)}</span></div>
          <div class="title">${esc(n.title)}</div>
          <div class="desc" style="max-height:70px;overflow:hidden">${esc(n.body)}</div>
        </div>`).join('') : '<div class="empty mt">Пока тихо. Стань первым — <a href="#/news">опубликуй сводку</a>.</div>'}
    </div>
    <div class="panel">
      <div class="row" style="justify-content:space-between">
        <h2 style="margin:0">🎯 Горячие заказы</h2>
        <a href="#/jobs" class="small">вся доска →</a>
      </div>
      ${openJobs.length ? openJobs.map(j => `
        <div class="card job mt" style="cursor:pointer" onclick="location.hash='#/jobs'">
          <div class="meta"><span class="tag">${esc(j.system || 'Cyberpunk RED')}</span>${j.when_text ? `<span>⏱ ${esc(j.when_text)}</span>` : ''}<span>ГМ: ${esc(j.author)}</span></div>
          <h3 style="margin:4px 0">${esc(j.title)}</h3>
          <div class="small muted">${j.slots ? `слотов: ${j.signups}/${j.slots}` : 'без ограничений'} · записалось: ${j.signups}</div>
        </div>`).join('') : '<div class="empty mt">Заказов нет. ГМ, <a href="#/jobs">размещи анонс партии</a>!</div>'}
    </div>
  </div>
  <div class="feature-cards mt">
    <a class="card" href="#/characters"><div class="ico">🧬</div><h3>Создание персонажа</h3><div class="muted small">Полный лист: статы, навыки, хром, броня, снаряжение.</div></a>
    <a class="card" href="#/guides"><div class="ico">📖</div><h3>Мини-гайды</h3><div class="muted small">Создание персонажа, боёвка FNFF и нетраннинг — кратко и по делу.</div></a>
    <a class="card" href="#/market"><div class="ico">🕶️</div><h3>Чёрный рынок</h3><div class="muted small">Ночная распродажа каждый день, покупки и продажа хлама.</div></a>
    <a class="card" href="#/codex"><div class="ico">📚</div><h3>Справочник</h3><div class="muted small">1092 предмета из книг с источниками и страницами.</div></a>
    <a class="card" href="#/calc"><div class="ico">🎲</div><h3>Калькулятор</h3><div class="muted small">Урон, крит. травмы, автоогонь, DV-таблицы, броски костей.</div></a>
    <a class="card" href="#/roster"><div class="ico">📋</div><h3>Ростер партии</h3><div class="muted small">Все публичные персонажи всех игроков вместе.</div></a>
    <a class="card" href="#/jobs"><div class="ico">📞</div><h3>Доска заказов</h3><div class="muted small">Анонсы партий от ГМ-ов и запись в группу.</div></a>
  </div>`;
}

/* ============================== справочник ============================== */

const codexState = { cat: '', q: '', offset: 0, limit: 30 };

async function viewCodex(view) {
  const cats = state.meta.cats;
  view.innerHTML = `
  <div class="page-head"><div><h1>📚 Справочник</h1><div class="sub">Всё снаряжение из Data Pool: ${nf.format(state.meta._total || '')}</div></div></div>
  <div class="codex-layout">
    <div class="cat-list panel" style="padding:10px">
      <a href="javascript:void(0)" data-cat="" class="${codexState.cat === '' ? 'active' : ''}">🌐 Всё подряд</a>
      ${cats.map(c => `
        <a href="javascript:void(0)" data-cat="${c.id}" class="${codexState.cat === c.id ? 'active' : ''}">
          <span>${c.emoji} ${esc(c.ru)}</span><span class="cnt">${c.count}</span></a>`).join('')}
    </div>
    <div>
      <div class="searchbar">
        <input id="codex-q" placeholder="Поиск: имя, тип, описание…" value="${esc(codexState.q)}">
        <button id="codex-search">Найти</button>
      </div>
      <div id="codex-results">${spinner()}</div>
    </div>
  </div>`;
  $$('.cat-list a', view).forEach(a => a.onclick = () => {
    codexState.cat = a.dataset.cat; codexState.offset = 0;
    viewCodex(view);
  });
  const doSearch = () => {
    codexState.q = $('#codex-q').value;
    codexState.offset = 0;
    loadCodexItems();
  };
  $('#codex-search').onclick = doSearch;
  $('#codex-q').onkeydown = (e) => { if (e.key === 'Enter') doSearch(); };
  await loadCodexItems();
}

/* ============================== гайды ============================== */

function guideInline(s) {
  return esc(s).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>');
}

function guideBlock(b) {
  if (b.t === 'p') return `<p>${guideInline(b.x)}</p>`;
  if (b.t === 'note') return `<div class="guide-note">${guideInline(b.x)}</div>`;
  if (b.t === 'ul') return `<ul>${b.items.map(x => `<li>${guideInline(x)}</li>`).join('')}</ul>`;
  if (b.t === 'ol') return `<ol>${b.items.map(x => `<li>${guideInline(x)}</li>`).join('')}</ol>`;
  if (b.t === 'table') {
    return `<div class="table-scroll"><table class="rtable guide-table">
      ${b.head ? `<tr>${b.head.map(h => `<th>${esc(h)}</th>`).join('')}</tr>` : ''}
      ${b.rows.map(r => `<tr>${r.map(c => `<td>${guideInline(String(c))}</td>`).join('')}</tr>`).join('')}
    </table></div>`;
  }
  if (b.t === 'hp') {
    // Таблица HP: BODY 2–15 × WILL 2–10, HP = 10 + 5×⌈(BODY+WILL)/2⌉
    const bodies = [], wills = [];
    for (let i = 2; i <= 15; i++) bodies.push(i);
    for (let i = 2; i <= 10; i++) wills.push(i);
    return `<div class="table-scroll"><table class="rtable guide-table hp-table">
      <tr><th>BODY\\WILL</th>${bodies.map(v => `<th>${v}</th>`).join('')}</tr>
      ${wills.map(w => `<tr><th>${w}</th>${bodies.map(bd => `<td>${10 + 5 * Math.ceil((bd + w) / 2)}</td>`).join('')}</tr>`).join('')}
    </table></div>`;
  }
  if (b.t === 'img') {
    return `<figure class="guide-img"><img src="${esc(b.src)}" alt="${esc(b.alt || '')}" loading="lazy">${b.cap ? `<figcaption>${guideInline(b.cap)}</figcaption>` : ''}</figure>`;
  }
  return '';
}

function guideSectionHtml(s, idx) {
  const blocks = (s.blocks || []).map(guideBlock).join('');
  return `<details class="guide-section"${idx === 0 ? ' open' : ''}>
    <summary>${esc(s.h)}</summary>
    <div class="guide-body">${blocks}</div>
  </details>`;
}

function viewGuides(view) {
  const gs = typeof GUIDES !== 'undefined' ? GUIDES : [];
  if (!gs.length) { view.innerHTML = '<div class="empty">Гайды не загрузились</div>'; return; }
  const cur = guidesTab || gs[0].id;
  view.innerHTML = `
  <div class="page-head">
    <div><h1>📖 Мини-гайды</h1>
      <div class="sub">Краткие правила из «Spes Desperata»: создание персонажа, боёвка и нетраннинг.</div></div>
  </div>
  <div class="editor-tabs" style="margin-bottom:14px">
    ${gs.map(g => `<button data-g="${g.id}" class="${g.id === cur ? 'active' : ''}">${g.emoji} ${esc(g.title)}</button>`).join('')}
  </div>
  <div class="panel accent mb"><b>${gs.find(g => g.id === cur)?.emoji} ${esc(gs.find(g => g.id === cur)?.title || '')}.</b> ${esc(gs.find(g => g.id === cur)?.sub || '')}</div>
  <div id="guide-box">
    ${gs.filter(g => g.id === cur).map(g => g.sections.map((s, i) => guideSectionHtml(s, i)).join('')).join('')}
  </div>`;
  $$('[data-g]', view).forEach(b => b.onclick = () => { guidesTab = b.dataset.g; viewGuides(view); });
}


async function loadCodexItems() {
  const box = $('#codex-results');
  if (!box) return;
  box.innerHTML = spinner();
  const p = new URLSearchParams({ q: codexState.q, cat: codexState.cat, offset: codexState.offset, limit: codexState.limit });
  const data = await api('/api/items?' + p);
  const catName = (id) => { const c = state.meta.cats.find(x => x.id === id); return c ? c.emoji + ' ' + c.ru : id; };
  box.innerHTML = `
    <div class="muted small mb">Найдено: ${nf.format(data.total)}</div>
    <div class="item-grid">
      ${data.items.map(it => `
        <div class="card item-card">
          <div class="head">
            <span class="name" data-id="${it.id}">${esc(it.name)}</span>
            <span class="price">${it.price != null ? money(it.price) : '<span class="muted">—</span>'}</span>
          </div>
          <div class="chips"><span class="chip">${catName(it.cat)}</span>
            ${Object.entries(it.fields || {}).slice(0, 6).map(([k, v]) => `<span class="chip">${esc(shortField(k, v))}</span>`).join('')}
          </div>
          ${it.source ? `<div class="small muted">📖 ${esc(it.source)}</div>` : ''}
          ${it.desc ? `<details class="desc-wrap"><summary>Описание</summary><div class="desc">${esc(it.desc)}</div></details>` : ''}
        </div>`).join('')}
    </div>
    ${pagerHtml(data.total, data.offset, data.limit)}`;
  $$('.name', box).forEach(el => el.onclick = () => showItemModal(el.dataset.id));
  bindPager(box, () => { codexState.offset += data.limit; loadCodexItems(); },
    () => { codexState.offset = Math.max(0, codexState.offset - data.limit); loadCodexItems(); });
}

function shortField(k, v) {
  const labels = { Type: '', Skill: '', Damage: '', Mag: 'маг ', ROF: 'СКО ', Conceal: 'скрыт ', Quality: '', Install: '', HL: 'HL ', 'Suitable ammo / weapon': '', SP: 'SP ', Seats: 'мест ', Class: '' };
  v = String(v);
  if (v.length > 42) v = v.slice(0, 40) + '…';
  return labels[k] !== undefined ? labels[k] + v : v;
}

function pagerHtml(total, offset, limit) {
  if (total <= limit) return '';
  const from = offset + 1, to = Math.min(total, offset + limit);
  return `<div class="pager">
    <button class="btn-sm" ${offset <= 0 ? 'disabled' : ''} data-pg="prev">← Назад</button>
    <span class="muted small">${nf.format(from)}–${nf.format(to)} из ${nf.format(total)}</span>
    <button class="btn-sm" ${to >= total ? 'disabled' : ''} data-pg="next">Вперёд →</button></div>`;
}
function bindPager(box, onNext, onPrev) {
  const next = $('[data-pg="next"]', box), prev = $('[data-pg="prev"]', box);
  if (next) next.onclick = onNext;
  if (prev) prev.onclick = onPrev;
}

async function showItemModal(id) {
  const it = await api('/api/items/' + id);
  const c = state.meta.cats.find(x => x.id === it.cat);
  const m = openModal(`
    <h2>${esc(it.name)}</h2>
    <div class="chips mb">
      <span class="chip">${c ? c.emoji + ' ' + esc(c.ru) : it.cat}</span>
      ${it.price != null ? `<span class="tag price">${money(it.price)}</span>` : ''}
      ${it.source ? `<span class="chip">📖 ${esc(it.source)}</span>` : ''}
      ${it.hl ? `<span class="chip hl-badge">HL ${it.hl}</span>` : ''}
    </div>
    <div class="kv mb">
      ${Object.entries(it.fields || {}).map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join('')}
    </div>
    ${it.desc ? `<div class="desc">${esc(it.desc)}</div>` : '<div class="muted">Описание отсутствует.</div>'}
  `);
  return m;
}

/* ============================== чёрный рынок ============================== */

const marketState = { tab: 'nm', q: '', cat: '', offset: 0, limit: 30 };

async function viewMarket(view) {
  view.innerHTML = `
  <div class="page-head">
    <div><h1>🕶️ Чёрный рынок</h1>
    <div class="sub">Ночная витрина обновляется каждый день в 00:00 МСК. Уличные цены гуляют ±50%.</div></div>
    ${state.me && state.me.is_gm ? '<button id="payroll-btn">💰 Выплата (ГМ)</button>' : ''}
  </div>
  <div class="tabs">
    <button data-tab="nm" class="${marketState.tab === 'nm' ? 'active' : ''}">🌙 Ночная витрина</button>
    <button data-tab="catalog" class="${marketState.tab === 'catalog' ? 'active' : ''}">📦 Полный каталог</button>
    <button data-tab="sell" class="${marketState.tab === 'sell' ? 'active' : ''}">♻️ Скупка хлама</button>
  </div>
  <div id="market-body">${spinner()}</div>
  <div id="cart-slot"></div>`;
  $$('.tabs button', view).forEach(b => b.onclick = () => { marketState.tab = b.dataset.tab; marketState.offset = 0; viewMarket(view); });
  const pb = $('#payroll-btn');
  if (pb) pb.onclick = payrollModal;
  await loadMarketBody();
}

async function loadMarketBody() {
  const box = $('#market-body');
  if (!box) return;
  if (marketState.tab === 'nm') return loadNightMarket(box);
  if (marketState.tab === 'sell') return loadSellTab(box);
  return loadMarketCatalog(box);
}

async function loadNightMarket(box) {
  box.innerHTML = spinner();
  const data = await api('/api/nightmarket');
  box.innerHTML = `
    <div class="muted small mb">Витрина на ${data.date}. Товаров: ${data.items.length}. Цены уличные — на них и покупай.</div>
    <div class="item-grid">
      ${data.items.map(it => `
        <div class="card item-card">
          <div class="head">
            <span class="name">${esc(it.name)}</span>
            <span>
              ${it.discount ? `<span class="market-price-old">${money(it.price)}</span>` : ''}
              <span class="price">${money(it.street_price)}</span>
            </span>
          </div>
          <div class="chips">
            ${it.discount ? '<span class="tag disc">ВЫГОДНО</span>' : '<span class="tag">переплата</span>'}
            ${Object.entries(it.fields || {}).slice(0, 4).map(([k, v]) => `<span class="chip">${esc(shortField(k, v))}</span>`).join('')}
          </div>
          <div class="row">
            <button class="btn-sm btn-primary" data-buy-nm="${it.id}" data-price="${it.street_price}">В корзину · ${money(it.street_price)}</button>
          </div>
        </div>`).join('')}
    </div>`;
  $$('[data-buy-nm]', box).forEach(b => b.onclick = () => {
    const card = b.closest('.item-card');
    addToCart(b.dataset.buyNm, Number(b.dataset.price), 'nm', $('.name', card).textContent);
  });
  renderCart();
}

async function loadMarketCatalog(box) {
  box.innerHTML = `
    <div class="searchbar">
      <input id="mk-q" placeholder="Поиск по каталогу…" value="${esc(marketState.q)}">
      <select id="mk-cat">
        <option value="">Все категории</option>
        ${state.meta.cats.map(c => `<option value="${c.id}" ${marketState.cat === c.id ? 'selected' : ''}>${c.emoji} ${esc(c.ru)}</option>`).join('')}
      </select>
      <button id="mk-search">Найти</button>
    </div>
    <div id="mk-results">${spinner()}</div>`;
  const doSearch = () => {
    marketState.q = $('#mk-q').value;
    marketState.cat = $('#mk-cat').value;
    marketState.offset = 0;
    loadMarketCatalogItems();
  };
  $('#mk-search').onclick = doSearch;
  $('#mk-cat').onchange = doSearch;
  $('#mk-q').onkeydown = (e) => { if (e.key === 'Enter') doSearch(); };
  await loadMarketCatalogItems();
}

async function loadMarketCatalogItems() {
  const box = $('#mk-results');
  if (!box) return;
  box.innerHTML = spinner();
  const p = new URLSearchParams({ q: marketState.q, cat: marketState.cat, offset: marketState.offset, limit: marketState.limit });
  const data = await api('/api/items?' + p);
  const catName = (id) => { const c = state.meta.cats.find(x => x.id === id); return c ? c.emoji + ' ' + c.ru : id; };
  box.innerHTML = `
    <div class="muted small mb">Найдено: ${nf.format(data.total)} · цены каталожные</div>
    <div class="item-grid">
      ${data.items.filter(i => i.price != null).map(it => `
        <div class="card item-card">
          <div class="head"><span class="name">${esc(it.name)}</span><span class="price">${money(it.price)}</span></div>
          <div class="chips"><span class="chip">${catName(it.cat)}</span>
            ${Object.entries(it.fields || {}).slice(0, 4).map(([k, v]) => `<span class="chip">${esc(shortField(k, v))}</span>`).join('')}</div>
          ${it.source ? `<div class="small muted">📖 ${esc(it.source)}</div>` : ''}
          <div class="row"><button class="btn-sm btn-primary" data-buy="${it.id}" data-price="${it.price}">В корзину</button></div>
        </div>`).join('') || '<div class="empty">Нет товаров с ценой по этому запросу.</div>'}
    </div>
    ${pagerHtml(data.total, data.offset, data.limit)}`;
  $$('[data-buy]', box).forEach(b => b.onclick = () => {
    const card = b.closest('.item-card');
    addToCart(b.dataset.buy, Number(b.dataset.price), 'list', $('.name', card).textContent);
  });
  bindPager(box, () => { marketState.offset += data.limit; loadMarketCatalogItems(); },
    () => { marketState.offset = Math.max(0, marketState.offset - data.limit); loadMarketCatalogItems(); });
  renderCart();
}

async function loadSellTab(box) {
  if (!state.me) { box.innerHTML = '<div class="empty">Войдите, чтобы продавать хлам со склада своих персонажей. <a href="#/login">Войти</a></div>'; return; }
  box.innerHTML = spinner();
  const data = await api('/api/characters');
  const chars = data.characters;
  if (!chars.length) { box.innerHTML = '<div class="empty">Нет персонажей. <a href="#/char/new">Создать первого</a></div>'; return; }
  const sel = marketState.sellChar || chars[0].id;
  box.innerHTML = `
    <div class="row mb"><label class="f" style="margin:0"><span>Персонаж</span>
      <select id="sell-char">${chars.map(c => `<option value="${c.id}" ${c.id === sel ? 'selected' : ''}>${esc(c.data.handle)} — ${money(c.data.cash)}</option>`).join('')}</select></label>
    </div>
    <div id="sell-list">${spinner()}</div>`;
  $('#sell-char').onchange = (e) => { marketState.sellChar = Number(e.target.value); loadSellTab(box); };
  const renderList = (chars2) => {
    const ch = chars2.find(c => c.id === (marketState.sellChar || chars2[0].id)) || chars2[0];
    marketState.sellChar = ch.id;
    const inv = (ch.data.inventory || []);
    $('#sell-list').innerHTML = inv.length ? inv.map(i => `
      <div class="inv-row">
        <span class="iname">${esc(i.name)} ×${i.qty || 1}</span>
        <span class="muted small">куплено за ${money(i.price)}</span>
        <button class="btn-sm" data-sell="${esc(i.key)}">Продать 1 → ${money((i.price || 0) * 0.5)}</button>
      </div>`).join('') : '<div class="empty">Инвентарь пуст.</div>';
    $$('[data-sell]', $('#sell-list')).forEach(b => b.onclick = async () => {
      try {
        const r = await api('/api/sell', { method: 'POST', body: { char_id: ch.id, key: b.dataset.sell, qty: 1 } });
        toast(`Продано ${r.name} ×${r.qty} за ${money(r.got)}. Кэш: ${money(r.cash)}`);
        loadSellTab(box);
      } catch (e) { toast(e.message, true); }
    });
  };
  renderList(chars);
}

function addToCart(id, price, mode, name) {
  const ex = state.cart.find(c => c.id === id && c.mode === mode);
  if (ex) ex.qty++;
  else state.cart.push({ id, price, qty: 1, mode, name: name.replace(/ ·.*/, '') });
  renderCart();
  toast('Добавлено в корзину: ' + state.cart[state.cart.length - 1].name);
}

function cartTotal() { return state.cart.reduce((a, c) => a + c.price * c.qty, 0); }

function renderCart() {
  const slot = $('#cart-slot');
  if (!slot) return;
  if (!state.cart.length) { slot.innerHTML = ''; return; }
  slot.innerHTML = `
  <div class="cart-summary">
    <b>🛒 Корзина:</b>
    <span class="small muted grow">${state.cart.map(c => `${esc(c.name)}×${c.qty}`).join(', ')}</span>
    <b class="price">${money(cartTotal())}</b>
    <button class="btn-sm" id="cart-clear">Очистить</button>
    <button class="btn-primary" id="cart-buy">Купить</button>
  </div>`;
  $('#cart-clear').onclick = () => { state.cart = []; renderCart(); };
  $('#cart-buy').onclick = buyCart;
}

async function buyCart() {
  if (!state.me) { toast('Сначала войдите в систему', true); go('/login'); return; }
  try {
    const data = await api('/api/characters');
    const chars = data.characters;
    if (!chars.length) { toast('Сначала создайте персонажа', true); go('/char/new'); return; }
    const m = openModal(`
      <h2>Оформление покупки</h2>
      <p class="muted small">Итого: <b class="price">${money(cartTotal())}</b></p>
      <label class="f"><span>Покупатель</span>
        <select id="buy-char">${chars.map(c => `<option value="${c.id}">${esc(c.data.handle)} — ${money(c.data.cash)}</option>`).join('')}</select></label>
      <button class="btn-primary" id="buy-confirm">Купить за ${money(cartTotal())}</button>`);
    $('#buy-confirm', m).onclick = async () => {
      const cid = Number($('#buy-char', m).value);
      try {
        const r = await api('/api/buy', { method: 'POST', body: { char_id: cid, items: state.cart.map(c => ({ id: c.id, qty: c.qty, mode: c.mode })) } });
        state.cart = [];
        renderCart();
        closeModal();
        toast(`Сделка закрыта: −${money(r.total)}. Остаток: ${money(r.cash)}`);
      } catch (e) { toast(e.message, true); }
    };
  } catch (e) { toast(e.message, true); }
}

async function payrollModal() {
  try {
    const data = await api('/api/roster');
    const chars = data.characters;
    const m = openModal(`
      <h2>💰 Выплата / списание (ГМ)</h2>
      <p class="muted small">Начислить или списать евробаксы любому персонажу — награда за заказ, штраф или аванс.</p>
      <label class="f"><span>Персонаж</span>
        <select id="pay-char">${chars.map(c => `<option value="${c.id}">${esc(c.data.handle)} (${esc(c.owner_name)}) — ${money(c.data.cash)}</option>`).join('')}</select></label>
      <label class="f"><span>Сумма (€$, минус — списать)</span><input id="pay-amount" type="number" value="500" step="50"></label>
      <button class="btn-primary" id="pay-confirm">Провести</button>`);
    $('#pay-confirm', m).onclick = async () => {
      try {
        const r = await api('/api/payroll', { method: 'POST', body: { char_id: Number($('#pay-char', m).value), amount: Number($('#pay-amount', m).value) } });
        closeModal();
        toast('Готово. Теперь на счету: ' + money(r.cash));
      } catch (e) { toast(e.message, true); }
    };
  } catch (e) { toast(e.message, true); }
}

/* ============================== калькулятор ============================== */

function rollDice(expr) {
  const m = String(expr).replace(/\s+/g, '').toLowerCase().match(/^(\d*)d(\d+)([+-]\d+)?$/);
  if (!m) return null;
  const n = Math.min(50, parseInt(m[1] || '1', 10));
  const die = Math.min(1000, parseInt(m[2], 10));
  const mod = m[3] ? parseInt(m[3], 10) : 0;
  const rolls = [];
  for (let i = 0; i < n; i++) rolls.push(1 + Math.floor(Math.random() * die));
  return { rolls, mod, total: rolls.reduce((a, b) => a + b, 0) + mod, die };
}

async function viewCalc(view) {
  const [range, auto] = [state.meta.range_table, state.meta.autofire_table];
  view.innerHTML = `
  <div class="page-head"><div><h1>🎲 Калькулятор</h1><div class="sub">Урон против брони, броски костей, крит. травмы, автоогонь и таблицы DV.</div></div></div>
  <div class="grid cols-2">
    <div class="panel">
      <h2>💥 Расчёт урона</h2>
      <div class="row mb">
        <label class="f grow" style="margin:0"><span>Формула урона</span><input id="dc-expr" value="3d6" placeholder="3d6, 5d6, 2d6+3…"></label>
        <button class="btn-primary" id="dc-roll">Бросить</button>
      </div>
      <div class="row mb small muted" id="dc-presets">
        ${['2d6', '3d6', '4d6', '5d6', '6d6', '2d6+3'].map(d => `<button class="btn-sm" data-preset="${d}">${d}</button>`).join('')}
      </div>
      <div class="grid cols-2">
        <label class="f"><span>SP брони цели</span><input id="dc-sp" type="number" value="11" min="0" max="50"></label>
        <label class="f"><span>Max HP цели</span><input id="dc-hp" type="number" value="40" min="1"></label>
      </div>
      <label class="f"><span>Текущее HP цели</span><input id="dc-hpcur" type="number" value="40" min="0"></label>
      <label class="checkbox mb"><input type="checkbox" id="dc-melee"> Ближний бой / бронепробой (SP цели делится на 2, округление вверх)</label>
      <div id="dc-out" class="calc-out"></div>
    </div>
    <div class="panel">
      <h2>🎯 Броски костей</h2>
      <div class="row mb">
        <input id="dr-expr" value="1d10" style="flex:1">
        <button class="btn-primary" id="dr-roll">Бросить</button>
      </div>
      <div class="row small muted mb">${['1d10', '2d6', '3d6', '1d6+2'].map(d => `<button class="btn-sm" data-dpreset="${d}">${d}</button>`).join('')}</div>
      <div id="dr-out"></div>
      <hr>
      <h2>🛡️ Несколько слоёв брони</h2>
      <p class="small muted">SP не складывается: на локации действует только наибольший SP. При пробитии все надетые слои на этой локации абляируются одновременно.</p>
      <div class="grid cols-2">
        <label class="f"><span>SP верхнего</span><input id="ar-o" type="number" value="11"></label>
        <label class="f"><span>SP нижнего</span><input id="ar-i" type="number" value="7"></label>
      </div>
      <div class="calc-out" id="ar-out"></div>
    </div>
  </div>
  <div class="grid cols-2 mt">
    <div class="panel">
      <h2>☠️ Критические травмы</h2>
      <p class="small muted">2+ шестёрки на кубах урона атаки = крит. травма (+5 урона сразу по HP, броня не снижает). Брось 2d6 по локации; повторяй, пока не выпадет травма, которой у цели ещё нет.</p>
      <div class="row mb">
        <button class="btn-primary" id="ci-body">Бросить 2d6 — тело</button>
        <button id="ci-head">Бросить 2d6 — голова</button>
      </div>
      <div id="ci-out" class="calc-out"></div>
      <details class="guide-section small-details"><summary>Таблицы травм</summary>
        ${critTableHtml(state.meta.crit_body, 'Тело')}
        ${critTableHtml(state.meta.crit_head, 'Голова')}
      </details>
    </div>
    <div class="panel">
      <h2>🔥 Автоогонь</h2>
      <p class="small muted">Действие + 10 пуль. Навык Autofire, таблица автоогня. Урон = 2d6 × (бросок − DV), максимум множителя — у оружия.</p>
      <div class="grid cols-2">
        <label class="f"><span>Тип оружия</span><select id="af-type">
          <option value="3">SMG / Machine Pistol (×3)</option>
          <option value="4">Assault Rifle / Machine Gun (×4)</option>
        </select></label>
        <label class="f"><span>DV (по дистанции)</span><input id="af-dv" type="number" value="20" min="1"></label>
      </div>
      <label class="f"><span>REF + Autofire</span><input id="af-mod" type="number" value="14"></label>
      <button class="btn-primary mb" id="af-roll">Бросить атаку</button>
      <div id="af-out" class="calc-out"></div>
    </div>
  </div>
  <div class="grid cols-2 mt">
    <div class="panel">
      <h2>💀 Спасбросок от смерти</h2>
      <p class="small muted">В начале хода при смертельном ранении (HP &lt; 1): 1d10 ≤ BODY − штраф. 10 — всегда провал. Штраф растёт на +1 за каждый бросок.</p>
      <div class="grid cols-2">
        <label class="f"><span>BODY</span><input id="ds-body" type="number" value="6" min="1" max="15"></label>
        <label class="f"><span>Штраф (Death Save Penalty)</span><input id="ds-pen" type="number" value="0" min="0" max="20"></label>
      </div>
      <button class="btn-primary mb" id="ds-roll">Бросить 1d10</button>
      <div id="ds-out" class="calc-out"></div>
    </div>
    <div class="panel">
      <h2>🩹 Состояния ранений</h2>
      ${woundStatesHtml()}
    </div>
  </div>
  <div class="panel mt">
    <h2>📏 Таблица DV (дальность)</h2>
    <div style="overflow-x:auto">${tableHtml(range)}</div>
  </div>
  <div class="panel mt">
    <h2>🔥 Таблица DV (автоогонь)</h2>
    <div style="overflow-x:auto">${tableHtml(auto)}</div>
  </div>`;

  const doDamage = () => {
    const expr = $('#dc-expr').value.trim() || '3d6';
    const r = rollDice(expr);
    const out = $('#dc-out');
    if (!r) { out.innerHTML = '<span style="color:var(--red)">Не понял формулу. Пример: 3d6 или 2d6+3</span>'; return; }
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
    if (crit) lines.push('<div class="crit-hit">🔥 Две шестёрки! Критическая травма (+5 HP, броня не снижает) — брось 2d6 в панели «Критические травмы».</div>');
    if (net > 0) {
      lines.push(`<div>Урон: <b style="color:var(--magenta)">${net}</b> (SP ${sp}${spEff !== sp ? ' → ' + spEff : ''} вычтен). Броня пробита — SP абляируется на 1.</div>`);
      const newHp = Math.max(0, hpCur - net);
      const sw = Math.ceil(hpMax / 2);
      let stateTxt;
      if (newHp < 1) stateTxt = '<b style="color:var(--red)">Смертельное ранение (HP &lt; 1): −4 ко всем действиям, −6 MOVE. В начале хода — спасбросок от смерти. Стабилизация: Paramedic DV15 → 1 HP, без сознания.</b>';
      else if (newHp <= sw) stateTxt = `<b style="color:var(--orange)">Серьёзное ранение (HP ≤ ½ = ${sw}): −2 ко всем действиям. Стабилизация: DV13.</b>`;
      else stateTxt = '<b style="color:var(--green)">Лёгкое ранение: эффектов нет. Цель держится.</b>';
      lines.push(`<div>HP цели: ${hpCur} → <b>${newHp}</b>. ${stateTxt}</div>`);
    } else {
      lines.push(`<div>Броня держит (урон ${r.total} ≤ SP ${spEff}). HP не тратится, SP не абляируется.</div>`);
    }
    out.innerHTML = lines.join('');
  };
  $('#dc-roll').onclick = doDamage;
  $$('#dc-presets [data-preset]', view).forEach(b => b.onclick = () => { $('#dc-expr').value = b.dataset.preset; doDamage(); });

  const doRoll = () => {
    const r = rollDice($('#dr-expr').value.trim() || '1d10');
    const out = $('#dr-out');
    if (!r) { out.innerHTML = '<span style="color:var(--red)">Не понял формулу</span>'; return; }
    out.innerHTML = `<div class="calc-out"><span class="dice-face">🎲 ${r.rolls.join(', ')}</span> = <b>${r.total}</b></div>`;
  };
  $('#dr-roll').onclick = doRoll;
  $$('[data-dpreset]', view).forEach(b => b.onclick = () => { $('#dr-expr').value = b.dataset.dpreset; doRoll(); });

  const doArmor = () => {
    const o = num($('#ar-o').value) || 0, i = num($('#ar-i').value) || 0;
    const hi = Math.max(o, i);
    $('#ar-out').innerHTML = `Действующий SP: <b>${hi}</b> <span class="muted small">(максимум из ${o} и ${i}; SP не складывается)</span>`;
  };
  ['ar-o', 'ar-i'].forEach(id => $('#' + id).oninput = doArmor);

  // критическая травма
  const doCrit = (table, label) => {
    const r = rollDice('2d6');
    const row = (table || []).find(x => x[0] === r.total) || null;
    const out = $('#ci-out');
    if (!row) { out.innerHTML = 'Бросок вне таблицы (2d6: 2–12)'; return; }
    out.innerHTML = `
      <span class="dice-face">🎲 ${r.rolls.join(' + ')} = <b>${r.total}</b></span>
      <div><b style="color:var(--magenta)">${esc(row[1])}</b> <span class="tag">${esc(label)}</span></div>
      <div>${esc(row[2])}</div>
      <div class="small muted">Quick Fix: ${esc(row[3])} · Treatment: ${esc(row[4])} · +5 HP сразу.</div>`;
  };
  $('#ci-body').onclick = () => doCrit(state.meta.crit_body, 'тело');
  $('#ci-head').onclick = () => doCrit(state.meta.crit_head, 'голова');

  // автоогонь
  $('#af-roll').onclick = () => {
    const maxMul = num($('#af-type').value) || 3;
    const dv = num($('#af-dv').value) || 0;
    const mod = num($('#af-mod').value) || 0;
    const atk = rollDice('1d10');
    const total = atk.total + mod;
    const margin = total - dv;
    const out = $('#af-out');
    let lines = [`Атака: 🎲 ${atk.rolls[0]} + ${mod} = <b>${total}</b> против DV ${dv}.`];
    if (margin <= 0) {
      lines.push(`<div style="color:var(--red)">Промах (разница ${margin} ≤ 0). Пули ушли в стену.</div>`);
    } else {
      const dmg = rollDice('2d6');
      const mul = Math.min(margin, maxMul);
      const crit = dmg.rolls[0] === 6 && dmg.rolls[1] === 6;
      lines.push(`Попадание! Множитель: min(${margin}, ${maxMul}) = <b>${mul}</b>.`);
      lines.push(`<div>Урон автоогня: 2d6 (${dmg.rolls.join(' + ')}) × ${mul} = <b style="color:var(--magenta)">${dmg.total * mul}</b> (до вычета SP).</div>`);
      if (crit) lines.push('<div class="crit-hit">🔥 Обе шестёрки на кубах урона — плюс крит. травма!</div>');
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
      out.innerHTML = `🎲 <b>10</b> — <b style="color:var(--red)">автоматический провал. Ты мёртв.</b>`;
    } else if (r.rolls[0] <= body - pen) {
      out.innerHTML = `🎲 ${r.rolls[0]} ≤ ${body}${pen ? ' − ' + pen : ''} — <b style="color:var(--green)">держишься</b>. Следующий бросок со штрафом +1 (текущий станет ${pen + 1}).`;
    } else {
      out.innerHTML = `🎲 ${r.rolls[0]} > ${body}${pen ? ' − ' + pen : ''} — <b style="color:var(--red)">провал. Ты мёртв.</b>`;
    }
  };

  doDamage(); doArmor();
}

function critTableHtml(table, label) {
  if (!table || !table.length) return '';
  return `<div class="table-scroll"><table class="rtable guide-table">
    <tr><th>2d6</th><th>Травма (${esc(label)})</th><th>Эффект</th><th>Quick Fix</th><th>Treatment</th></tr>
    ${table.map(r => `<tr><td><b>${r[0]}</b></td><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td><td>${esc(r[4])}</td></tr>`).join('')}
  </table></div>`;
}

function woundStatesHtml() {
  const ws = state.meta.wound_states || [];
  if (!ws.length) return '<div class="muted">Нет данных</div>';
  return `<div class="table-scroll"><table class="rtable guide-table">
    <tr><th>Состояние</th><th>Порог</th><th>Эффект</th><th>Стабилизация</th></tr>
    ${ws.map(r => `<tr><td><b>${esc(r[0])}</b></td><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td></tr>`).join('')}
  </table></div>`;
}

function tableHtml(rows) {
  if (!rows || !rows.length) return '<div class="muted">Нет данных</div>';
  return `<table class="rtable">
    ${rows.map((r, ri) => `<tr>${r.map((c, ci) => ri === 0 || ci === 0 ? `<th>${esc(c)}</th>` : `<td>${esc(c)}</td>`).join('')}</tr>`).join('')}
  </table>`;
}

/* ============================== мастер создания персонажа (7 шагов) ============================== */

const WIZARD_STEPS = [
  ['role',     '🎭 Роль',           'Выбери роль — она даёт ролевую способность и определяет стиль игры.'],
  ['lifepath', '🧬 Lifepath',       'Общий Lifepath CP:R или CEMK плюс полный набор таблиц выбранной роли.'],
  ['stats',    '📊 Характеристики', 'Ровно 62 очка на 10 характеристик, каждая 2–8.'],
  ['skills',   '🎯 Навыки',         'Ровно 86 очков: обязательные минимумы, максимум 6 и специализированные навыки.'],
  ['style',    '🕶️ Стиль',          '800€$ на Fashion и весь Fashionware из Data Pool. Остаток сгорает.'],
  ['shopping', '🛒 Закупка',        '2550€$ на снаряжение и хром; броня разделена на голову и тело. Neuroport по CEMK бесплатен.'],
  ['summary',  '✅ Итог',           'Проверь лист, впиши псевдоним и создай персонажа.'],
];

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

/* ---------- Lifepath: 13 пунктов (CP:R стр. 43–48) ---------- */

function lpFields() {
  return MERGED_LIFEPATH_FIELDS.map(field => [field.key, field.label, field.options]);
}

function lpRoleField(role) {
  return ROLE_LIFEPATHS[role] || [];
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
    if (lp && lp[key] && !shown.has(key) && !LIFEPATH_KEY_ALIASES[key]) { out.push([label, lp[key]]); shown.add(key); }
  }
  for (const [key, label] of lpRoleField(role)) {
    if (roleLp && roleLp[key]) out.push(['Роль · ' + label, roleLp[key]]);
  }
  if ((!roleLp || !Object.keys(roleLp).length) && lp && lp.rolebg) out.push(['Ролевая предыстория', lp.rolebg]);
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
  const sourceText = sources && sources.length ? ` Источник варианта: ${sources.join(' + ')}.` : '';
  const prefix = roleSpecific ? 'Этот результат уточняет профессиональный опыт и связи выбранной роли.' : (common[key] || 'Этот результат задаёт конкретную деталь предыстории персонажа.');
  return `<div class="lp-result-info"><b>${esc(value)}</b><br>${esc(prefix)}${esc(sourceText)}</div>`;
}

/* ---------- суб-навыки ---------- */

const SUB_SKILL_BASES = SPECIALIZED_SKILL_BASES;
const WIZ_SUB_HIDDEN = new Set(SUB_SKILL_BASES.map(s => s[0]));

/* ---------- закупка: категории ---------- */

const WIZ_SHOP_CATS = [
  ['weapons',  '🔫 Оружие',      ['guns', 'melee', 'gun_upgrades']],
  ['armor',    '🛡️ Броня',       ['armor']],
  ['chrome',   '🦾 Хром',        ['cyberware']],
  ['programs', '💾 Программы',   ['programs', 'net_stuff']],
  ['ammo',     '📦 Боеприпасы',  ['ammo', 'grenades']],
  ['vehicles', '🏍️ Транспорт',   ['vehicles', 'vehicles_upgrades']],
  ['gear',     '🎒 Снаряжение и услуги', ['gear', 'services']],
];

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

const WIZARD_DRAFT_VERSION = 2;

function wizardDraftKey() {
  return state.me ? `cbpr-helper:wizard:${state.me.id}:v${WIZARD_DRAFT_VERSION}` : '';
}

function saveWizardDraft() {
  const key = wizardDraftKey();
  if (!key || !state.wizard || state.wizard.created) return;
  try {
    const clean = JSON.parse(JSON.stringify(state.wizard, (k, v) => k.startsWith('_') ? undefined : v));
    localStorage.setItem(key, JSON.stringify({ version: WIZARD_DRAFT_VERSION, saved_at: Date.now(), wizard: clean }));
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
  const role = (w && state.meta.roles[w.role]) ? w.role : 'Solo';
  const lp = Object.assign({}, (w && w.lifepath) || {});
  if (!lp.clothing && lp.wardrobe) lp.clothing = lp.wardrobe;
  if (!lp.hair && lp.hair_style) lp.hair = lp.hair_style;
  const skills = Object.assign({}, (w && w.skills) || {});
  const subSkills = Array.isArray(w && w.subSkills) ? w.subSkills.map(x => ({
    base: x.base, name: String(x.name || ''), lvl: Math.max(0, Math.min(6, num(x.lvl) || 0)), native: !!x.native,
  })) : [];
  if (!subSkills.some(x => x.base === 'Language' && x.name === 'Streetslang')) subSkills.unshift({ base: 'Language', name: 'Streetslang', lvl: 2 });
  if (!subSkills.some(x => x.base === 'Local Expert' && x.name === 'Свой район')) subSkills.push({ base: 'Local Expert', name: 'Свой район', lvl: 2 });
  for (const [base] of SUB_SKILL_BASES) {
    if (skills[base] == null) skills[base] = subSkills.filter(x => x.base === base && !x.native).reduce((a, x) => a + x.lvl, 0);
  }
  const out = Object.assign({
    step: 1, role, handle: '', firstName: '', lastName: '', stats, skills, subSkills,
    nativeLanguage: '', cyberware: [], fashionware: [], gear: [], fashion: [],
    armor: { body: null, head: null }, chromeCost: 0, gearCost: 0, fashionCost: 0,
    fashionBurned: false, soldSoul: false, freeNeuroport: true,
    lifepath: lp, roleLifepath: {}, roleSetup: defaultRoleSetup(role),
    shopTab: 'weapons', shopQ: '', styleQ: '', shopType: 'all', styleType: 'all',
    scrolls: {}, created: false,
  }, w || {});
  out.ownerId = state.me ? state.me.id : null;
  out.role = role;
  out.stats = stats;
  out.skills = skills;
  out.subSkills = subSkills;
  out.lifepath = lp;
  out.roleSetup = Object.assign(defaultRoleSetup(role), (w && w.roleSetup) || {});
  out.roleLifepath = Object.assign({}, (w && w.roleLifepath) || {});
  out.armor = Object.assign({ body: null, head: null }, (w && w.armor) || {});
  out.scrolls = Object.assign({}, (w && w.scrolls) || {});
  out.step = Math.max(1, Math.min(7, num(out.step) || 1));
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
  const key = wizardDraftKey();
  if (!key) return false;
  try {
    const raw = JSON.parse(localStorage.getItem(key) || 'null');
    if (!raw || raw.version !== WIZARD_DRAFT_VERSION || !raw.wizard) return false;
    state.wizard = normalizeWizard(raw.wizard);
    return true;
  } catch (e) { return false; }
}

function initWizard() {
  const stats = {};
  (state.meta ? state.meta.stats : ['INT','REF','DEX','TECH','COOL','WILL','LUCK','MOVE','BODY','EMP']).forEach(s => stats[s] = 5);
  state.wizard = normalizeWizard({
    step: 1,
    role: 'Solo',
    handle: '', firstName: '', lastName: '',
    stats,
    skills: {},
    subSkills: [
      { base: 'Language', name: 'Streetslang', lvl: 2 },
      { base: 'Local Expert', name: 'Свой район', lvl: 2 },
    ],
    nativeLanguage: '',
    cyberware: [],
    fashionware: [],
    gear: [], fashion: [], armor: { body: null, head: null },
    chromeCost: 0, gearCost: 0, fashionCost: 0,
    fashionBurned: false, soldSoul: false, freeNeuroport: true,
    lifepathMode: 'merged', lifepath: {}, roleLifepath: {},
    roleSetup: defaultRoleSetup('Solo'),
    shopTab: 'weapons', shopQ: '', styleQ: '', shopType: 'all', styleType: 'all',
    scrolls: {},
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
  }));
  const hasPaidNeuroport = purchasedChrome.some(c => String(c.name).toLowerCase() === 'neuroport');
  const cyberware = w.freeNeuroport && !hasPaidNeuroport
    ? [{ key: 'creation-neuroport', name: 'Neuroport', hl: 0, price: 0,
         type: 'Neuralware', desc: 'Бесплатный стартовый Neuroport по CEMK.',
         humanity_exempt: true, creation_free: true }, ...purchasedChrome]
    : purchasedChrome;
  return {
    handle: w.handle || 'Безымянный-07',
    first_name: w.firstName || '', last_name: w.lastName || '',
    role: w.role, role_rank: 4, role_setup: Object.assign({}, w.roleSetup),
    stats: Object.assign({}, w.stats),
    hp_cur: null, humanity_cur: null,
    skills, skill_pools: skillPools, native_language: w.nativeLanguage,
    cyberware,
    inventory: [...w.gear.map(i => ({ ...i })), ...w.fashion.map(i => ({ ...i }))],
    armor: { body: w.armor.body ? { ...w.armor.body } : null, head: w.armor.head ? { ...w.armor.head } : null },
    cash: Math.max(0, creationMainRemaining(w)),
    appearance: [lp.clothing, lp.hair, lp.hair_color, lp.affectation].filter(Boolean).join(' · '),
    background: lpText,
    lifepath_mode: 'merged',
    lifepath: lp, role_lifepath: Object.assign({}, w.roleLifepath),
    creation: { sold_soul: !!w.soldSoul, free_neuroport: !!w.freeNeuroport,
      gear_spent: w.gearCost, chrome_spent: w.chromeCost, fashion_spent: w.fashionCost },
    lifestyle: 'Kibble (100€$)',
    housing: w.role === 'Exec' ? 'Corporate Conapt (Teamwork)' : 'Studio Apartment (Rent, VEX)',
    notes: '', languages: langs, player: '',
    public: true,
  };
}

function wizDerived() {
  return derive(wizChar());
}

async function viewWizard() {
  if (!state.me) {
    $('#view').innerHTML = '<div class="empty">Нужен вход. <a href="#/login">Войти</a></div>';
    return;
  }
  if (!state.wizard || state.wizard.created || state.wizard.ownerId !== state.me.id) {
    if (!loadWizardDraft()) initWizard();
  }
  renderWizard();
}

function wizLiveHtml() {
  const wiz = state.wizard;
  const d = wizDerived();
  const remainingGear = creationMainRemaining(wiz);
  const remainingFashion = wiz.fashionBurned ? 0 : (FASHION_BUDGET - wiz.fashionCost);
  return `<div class="derived">
    <span class="dstat"><span class="v">${d.hp_max || '—'}</span><span class="k">HP макс</span></span>
    <span class="dstat"><span class="v">${d.seriously_wounded != null ? '≤ ' + d.seriously_wounded : '—'}</span><span class="k">Серьёзная рана</span></span>
    <span class="dstat"><span class="v">${d.humanity_max != null ? d.humanity_cur + '/' + d.humanity_max : '—'}</span><span class="k">Человечность</span></span>
    <span class="dstat ${d.emp_cur != null && d.emp_cur <= 2 ? 'warn' : ''}"><span class="v">${d.emp_cur != null ? d.emp_cur : '—'}</span><span class="k">EMP</span></span>
    <span class="dstat"><span class="v">${nf.format(remainingGear)}€$</span><span class="k">Бюджет закупки</span></span>
    <span class="dstat"><span class="v">${nf.format(remainingFashion)}€$</span><span class="k">Бюджет стиля${wiz.fashionBurned ? ' (сгорел)' : ''}</span></span>
  </div>`;
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
  if (wiz.step === 5) wiz.fashionBurned = false; // вернулись на шаг стиля — бюджет снова активен
  const stepEmojis = ['🎭', '🧬', '📊', '🎯', '🕶️', '🛒', '✅'];

  view.innerHTML = `
  <div class="wizard-wrap">
    <div class="page-head">
      <div><h1>🧬 Мастер создания персонажа</h1>
      <div class="sub">Пошаговое создание эджраннера в духе Cyberpunk RED Companion.</div></div>
      <button onclick="location.hash='#/characters'">← К моим персонажам</button>
    </div>
    <div class="wizard-nav">
      ${WIZARD_STEPS.map((s, i) => `
        <button class="wiz-step ${i + 1 === wiz.step ? 'active' : ''} ${i + 1 < wiz.step ? 'done' : ''}"
                onclick="wizGoTo(${i + 1})">
          <span class="wiz-num">${stepEmojis[i]}</span>
          <span class="wiz-label">${s[1]}</span>
        </button>`).join('')}
    </div>

    <div class="wiz-live" id="wiz-live">${wizLiveHtml()}</div>

    <div class="wiz-body" id="wiz-body">
      ${renderWizStep()}
    </div>

    <div class="wiz-footer">
      <div class="row" style="justify-content:space-between">
        <div>
          <button class="btn-sm" id="wiz-restart">⟳ Начать заново</button>
        </div>
        <div class="row">
          ${wiz.step > 1 ? '<button id="wiz-prev" class="btn-sm">← Назад</button>' : ''}
          ${wiz.step < 7 ? '<button id="wiz-next" class="btn-primary">Далее →</button>'
            : '<button class="btn-primary" id="wiz-create">🧬 Создать персонажа</button>'}
        </div>
      </div>
    </div>
  </div>`;

  const nxt = $('#wiz-next');
  if (nxt) nxt.onclick = wizNext;
  const prv = $('#wiz-prev');
  if (prv) prv.onclick = wizPrev;
  const crt = $('#wiz-create');
  if (crt) crt.onclick = wizCreate;
  $('#wiz-restart').onclick = wizReset;
  bindWizStep();
  saveWizardDraft();
}

function renderWizStep() {
  const wiz = state.wizard;
  const s = WIZARD_STEPS[wiz.step - 1];
  let html = `<div class="wiz-step-header"><h2>${s[1]}</h2><div class="muted small">${s[2]}</div></div>`;
  html += `<div class="wiz-content">${wizStepContent(wiz.step)}</div>`;
  return html;
}

function wizStepContent(step) {
  switch (step) {
    case 1: return wizStepRoleHtml();
    case 2: return wizStepLifepathHtml();
    case 3: return wizStepStatsHtml();
    case 4: return wizStepSkillsHtml();
    case 5: return wizStepStyleHtml();
    case 6: return wizStepShoppingHtml();
    case 7: return wizStepSummaryHtml();
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

function wizRoleSetupHtml() {
  const w = state.wizard, s = w.roleSetup || {};
  if (w.role === 'Tech') return `<div class="panel accent mt"><h3>Распределение Maker</h3>
    <div class="small muted mb">На старте Tech получает по 1 рангу в двух разных специализациях за каждый ранг Maker: всего 8, максимум 4 в одной.</div>
    <div class="grid cols-4">${[
      ['field','Field Expertise'],['upgrade','Upgrade Expertise'],['fabrication','Fabrication Expertise'],['invention','Invention Expertise']
    ].map(([k,n]) => `<label class="f"><span>${n}</span><input type="number" min="0" max="4" data-role-setup="${k}" value="${num(s[k]) || 0}"></label>`).join('')}</div>
    <div class="small">Распределено: <b>${['field','upgrade','fabrication','invention'].reduce((a,k)=>a+(num(s[k])||0),0)}</b> / 8</div></div>`;
  if (w.role === 'Medtech') return `<div class="panel accent mt"><h3>Распределение Medicine</h3>
    <div class="small muted mb">Распредели 4 ранга между Surgery, Pharmaceuticals и Cryosystem Operation.</div>
    <div class="grid cols-3">${[
      ['surgery','Surgery'],['pharma','Pharmaceuticals'],['cryo','Cryosystem Operation']
    ].map(([k,n]) => `<label class="f"><span>${n}</span><input type="number" min="0" max="4" data-role-setup="${k}" value="${num(s[k]) || 0}"></label>`).join('')}</div>
    <div class="small">Распределено: <b>${['surgery','pharma','cryo'].reduce((a,k)=>a+(num(s[k])||0),0)}</b> / 4</div></div>`;
  if (w.role === 'Exec') return `<div class="panel accent mt"><h3>Teamwork · стартовый сотрудник</h3>
    <select id="role-team"><option value="">— выбрать —</option>${['Телохранитель','Водитель','Личный помощник','Техник','Нетраннер','Скрытый оперативник'].map(x=>`<option ${s.team_member===x?'selected':''}>${x}</option>`).join('')}</select>
    <div class="small muted mt">Teamwork также предоставляет Businesswear и корпоративное жильё.</div></div>`;
  if (w.role === 'Nomad') return `<div class="panel accent mt"><h3>Moto · четыре стартовых выбора</h3>
    <div class="small muted mb">На каждом ранге выбери новый семейный транспорт доступного ранга или улучшение уже выбранной машины.</div>
    <div class="grid cols-2">${[0,1,2,3].map(i => `<label class="f"><span>Ранг ${i+1}</span><input data-moto-choice="${i}" value="${esc((s.moto_choices || [])[i] || '')}" placeholder="Транспорт или улучшение"></label>`).join('')}</div></div>`;
  return '';
}

function wizardRoleOrder() { return Object.keys(state.meta.roles || {}); }

function wizStepRoleHtml() {
  const wiz = state.wizard;
  const roles = wizardRoleOrder();
  const role = wiz.role;
  const ru = state.meta.role_ru[role];
  const ab = ROLE_ABILITIES[role] || { name: state.meta.roles[role], desc: '' };
  return `
    <div class="role-tabs mb" role="tablist" aria-label="Роли">
      ${roles.map(r => `<button role="tab" aria-selected="${wiz.role === r}" data-role="${r}" class="${wiz.role === r ? 'active' : ''}">${esc(r)}</button>`).join('')}
    </div>
    <div class="role-carousel" id="role-carousel">
      <button class="role-arrow" data-role-shift="-1" aria-label="Предыдущая роль">‹</button>
      <article class="role-card selected role-focus">
        <div class="role-index">${roles.indexOf(role) + 1} / ${roles.length}</div>
        <h2>${esc(role)} <span class="chip role">${esc(ru || '')}</span></h2>
        <p>${esc(ROLE_LONG_DESCRIPTIONS[role] || state.meta.role_desc[role] || '')}</p>
        <div class="ability-box">
          <div class="tag mb" style="display:inline-block;color:var(--yellow);border-color:rgba(255,213,0,.4)">⚡ ${esc(ab.name)}</div>
          <p class="small">${esc(ab.desc)}</p>
        </div>
      </article>
      <button class="role-arrow" data-role-shift="1" aria-label="Следующая роль">›</button>
    </div>
    <div class="small muted" style="text-align:center">Можно выбрать роль кнопками, стрелками или свайпом по карточке.</div>
    ${wizRoleSetupHtml()}`;
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
    const info = roleSpecific ? (ROLE_LIFEPATH_QUESTION_INFO[key] || 'Этот вопрос уточняет профессиональную историю, связи и привычки роли.') : (LIFEPATH_QUESTION_INFO[key] || 'Этот вопрос задаёт важную деталь предыстории персонажа.');
    return `<div class="lp-item">
      <div class="lp-label">${esc(label)}</div>
      <div class="small muted lp-question-info">${esc(info)}</div>
      <div class="row" style="align-items:center;gap:6px;flex-wrap:nowrap">
        <select ${attr}="${key}" style="flex:1;min-width:0">
          <option value="">— не выбрано —</option>
          ${opts.map(raw => {
            const value = typeof raw === 'object' ? raw.value : raw;
            const tag = typeof raw === 'object' ? ` · ${raw.sources.join('+')}` : '';
            return `<option value="${esc(value)}" ${selected === value ? 'selected' : ''}>${esc(value + tag)}</option>`;
          }).join('')}
        </select>
        <button class="btn-sm" ${diceAttr}="${key}" title="Случайный результат">🎲</button>
      </div>
      ${lifepathResultInfo(key, selected, sources, roleSpecific)}
    </div>`;
  }).join('');
}

function matchingNamePool(region) {
  const text = String(region || '');
  const direct = REGION_NAME_POOLS[text];
  if (direct) return direct;
  const key = Object.keys(REGION_NAME_POOLS).find(k => text.startsWith(k) || k.startsWith(text));
  return key ? REGION_NAME_POOLS[key] : REGION_NAME_POOLS['Северная Америка'];
}

function randomFrom(list) { return list[Math.floor(Math.random() * list.length)]; }
function generateWizardHandle() {
  const pools = Object.values(HANDLE_POOLS);
  state.wizard.handle = randomFrom(randomFrom(pools));
}
function generateWizardName() {
  const pool = matchingNamePool(state.wizard.lifepath.region);
  state.wizard.firstName = randomFrom(pool.first);
  state.wizard.lastName = randomFrom(pool.last);
}

function wizStepLifepathHtml() {
  const wiz = state.wizard;
  const fields = lpAllFields();
  const roleFields = lpRoleField(wiz.role);
  const langs = languagesForRegion(wiz.lifepath.region);
  return `
    <div class="panel accent mb identity-panel">
      <h3>Имя и Handle</h3>
      <div class="grid cols-3">
        <label class="f"><span>Handle *</span><div class="input-action"><input id="wiz-handle" maxlength="60" value="${esc(wiz.handle)}" placeholder="Neon, Выхлоп…"><button class="btn-sm" data-generate-handle title="Сгенерировать Handle">🎲</button></div></label>
        <label class="f"><span>Имя <span class="muted">(необязательно)</span></span><input id="wiz-first-name" maxlength="60" value="${esc(wiz.firstName)}"></label>
        <label class="f"><span>Фамилия <span class="muted">(необязательно)</span></span><div class="input-action"><input id="wiz-last-name" maxlength="60" value="${esc(wiz.lastName)}"><button class="btn-sm" data-generate-name title="Имя и фамилия по выбранному региону">🎲</button></div></label>
      </div>
      <div class="small muted mt">Генератор имени использует культурный регион, выбранный ниже. Handle генерируется независимо.</div>
    </div>
    <div class="panel accent mb">
      <b>Единый Lifepath CP:R + CEMK</b>
      <div class="small muted">Варианты объединены в одном списке и помечены источниками. Друзья, враги и трагическая любовь не входят в новый мастер.</div>
    </div>
    <div class="row mb" style="justify-content:space-between;align-items:center">
      <span class="muted small">Выбирай результат или используй случайную генерацию.</span>
      <button class="btn-primary btn-sm" id="lp-gen-all">🎲 Сгенерировать весь Lifepath</button>
    </div>
    <h3>Общий Lifepath · CP:R + CEMK</h3>
    <div class="lp-grid">${lifepathFieldsHtml(fields, wiz.lifepath, 'data-lp', 'data-lp-dice', false)}</div>
    <div class="panel mt mb">
      <label class="f"><span>Культурный язык · уровень 4 бесплатно</span>
        <select id="lp-native" ${langs.length ? '' : 'disabled'}><option value="">${langs.length ? '— выбрать язык —' : 'Сначала выбери регион'}</option>
        ${langs.map(x => `<option value="${esc(x)}" ${wiz.nativeLanguage === x ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select></label>
      <div class="small muted">Streetslang остаётся отдельным обязательным навыком уровня 2 и оплачивается из 86 очков.</div>
    </div>
    <h3>Ролевой Lifepath · ${esc(wiz.role)} · CP:R</h3>
    <div class="lp-grid">${lifepathFieldsHtml(roleFields, wiz.roleLifepath, 'data-role-lp', 'data-role-lp-dice', true)}</div>`;
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

function wizStepStatsHtml() {
  const wiz = state.wizard;
  const spent = wizStatSpent();
  const budget = state.meta.stat_points || 62;
  return `
    <div class="row mb" style="justify-content:space-between">
      <span class="muted small">Потрачено: <b id="wiz-st-spent" class="${spent !== budget ? 'warn-text' : ''}">${spent}</b> / <b>${budget}</b> очков (каждая стата 2–8, требуется ровно 62)</span>
      <div class="row">
        <button class="btn-sm" id="wiz-st-roll">🎲 Сгенерировать</button>
        <button class="btn-sm" id="wiz-st-reset">Сбросить все на 5</button>
      </div>
    </div>
    <div class="statgrid">
      ${state.meta.stats.map(s => {
        const v = num(wiz.stats[s]);
        const bad = v < 2 || v > 8;
        return `<div class="stat input${bad ? ' bad' : ''}">
          <span class="k">${s}</span>
          <input type="number" min="2" max="8" data-wiz-stat="${s}" value="${v != null ? v : 5}">
        </div>`;
      }).join('')}
    </div>
    <div class="small muted mt">HP = 10 + 5×⌈(BODY+WILL)/2⌉ · Человечность макс = EMP×10</div>`;
}

/* ---------- Шаг 4: Навыки + суб-навыки ---------- */

function wizSkillSpent() {
  const wiz = state.wizard;
  const dblCost = Object.fromEntries(state.meta.skills.map(s => [s[1], !!s[3]]));
  return Object.entries(wiz.skills).reduce((total, [name, lvl]) => total + (num(lvl) || 0) * (dblCost[name] ? 2 : 1), 0);
}

function wizSubAllocated(base) {
  return state.wizard.subSkills.filter(s => s.base === base && !s.native).reduce((a, s) => a + (num(s.lvl) || 0), 0);
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
  const meta = (state.meta.skills || []).find(s => s[1] === name);
  const detail = skillDetail(name);
  openModal(`<h2>${esc(name)}</h2>
    <div class="chips mb"><span class="chip">STAT ${esc(meta ? meta[2] : '—')}</span>${meta && meta[3] ? '<span class="tag">×2</span>' : '<span class="tag">×1</span>'}</div>
    <p>${esc(detail[0])}</p><div class="panel accent"><b>Примеры применения</b><p class="small">${esc(detail[1])}</p></div>`);
}

function wizSubRowsHtml(base, presets, stat, is2) {
  const wiz = state.wizard;
  const free = wizSubFree(base);
  const pool = num(wiz.skills[base]) || 0;
  const list = wiz.subSkills.map((sub, index) => [sub, index]).filter(([sub]) => sub.base === base);
  const dl = `wiz-dl-${base.replace(/\s+/g, '-')}`;
  return `<div class="subskill-pool">
    <div class="subskill-pool-head">
      <span>Распределено <b>${wizSubAllocated(base)}</b> / ${pool}; свободно <b class="${free ? 'green' : 'muted'}">${free}</b></span>
      ${free > 0 ? `<button class="btn-sm" data-sub-add="${esc(base)}">＋ Добавить специализацию</button>` : ''}
    </div>
    ${list.map(([sub, i]) => {
      const currentStat = stat === 'EMP' ? (wizDerived().emp_cur ?? wiz.stats.EMP) : wiz.stats[stat];
      return `<div class="skill-row subskill-row">
        <span class="sname subskill-name">↳ <input data-sub-name="${i}" list="${dl}" value="${esc(sub.name)}" placeholder="Название специализации" ${sub.native ? 'disabled' : ''}></span>
        <span class="sstat">${esc(stat)}</span>
        <span class="slvl"><button class="mini-step" data-sub-minus="${i}" ${sub.native || sub.lvl <= 0 ? 'disabled' : ''}>−</button><b>${sub.lvl || 0}</b><button class="mini-step" data-sub-plus="${i}" ${sub.native || free <= 0 || sub.lvl >= 6 ? 'disabled' : ''}>＋</button></span>
        <span class="sbase"><b>${(num(currentStat) || 0) + (sub.lvl || 0)}</b>${sub.native ? ' <span class="chip">бесплатно</span>' : ''}</span>
        ${sub.native ? '<span></span>' : `<button class="btn-sm btn-danger" data-sub-del="${i}" title="Удалить специализацию">✕</button>`}
      </div>`;
    }).join('')}
    <datalist id="${dl}">${presets.map(value => `<option value="${esc(value)}">`).join('')}</datalist>
  </div>`;
}

function wizStepSkillsHtml() {
  const wiz = state.wizard;
  const must = new Set(state.meta.must_skills || []);
  const budget = state.meta.skill_points || 86;
  const maxLvl = state.meta.skill_max || 6;
  const spent = wizSkillSpent();
  const specialized = Object.fromEntries(SUB_SKILL_BASES.map(row => [row[0], row]));
  const mustChips = (state.meta.must_skills || []).map(name => {
    const ok = wizMustOk(name);
    return `<span class="wiz-must-chip chip ${ok ? 'ok' : 'bad'}" data-must="${esc(name)}">${ok ? '✓' : '✗'} ${esc(name)}</span>`;
  }).join('');
  const recommended = (ROLE_RECOMMENDED_SKILLS[wiz.role] || []).map(name => `<span class="chip">${esc(name)}</span>`).join('');
  let lastCat = null;
  const rows = state.meta.skills.map(([cat, name, stat, is2]) => {
    const head = cat !== lastCat ? `<div class="skill-cat">${esc(cat)}</div>` : '';
    lastCat = cat;
    const lvl = num(wiz.skills[name]) || 0;
    const derived = wizDerived();
    const currentStat = stat === 'EMP' ? (derived.emp_cur ?? wiz.stats.EMP) : wiz.stats[stat];
    const subMeta = specialized[name];
    const allocated = subMeta ? wizSubAllocated(name) : 0;
    const options = [0,1,2,3,4,5,6].map(rank => `<option value="${rank}" ${lvl === rank ? 'selected' : ''} ${subMeta && rank < allocated ? 'disabled' : ''}>${rank}</option>`).join('');
    return head + `<div class="skill-row ${subMeta ? 'skill-parent' : ''}">
      <button class="skill-name-btn sname" data-skill-info="${esc(name)}">${must.has(name) ? '<span class="must-tag" title="Обязательный минимум">★</span>' : ''}${esc(name)}${is2 ? ' <span class="muted small">(×2)</span>' : ''}</button>
      <span class="sstat">${esc(stat)}</span>
      <span class="slvl"><select ${subMeta ? 'data-wiz-pool' : 'data-wiz-skill'}="${esc(name)}">${options}</select></span>
      <span class="sbase"><b>${(num(currentStat) || 0) + lvl}</b></span>
      <span></span>
    </div>${subMeta ? wizSubRowsHtml(name, subMeta[2], stat, is2) : ''}`;
  }).join('');
  const ab = ROLE_ABILITIES[wiz.role] || { name: state.meta.roles[wiz.role] || '—' };
  return `
    <div class="row mb" style="justify-content:space-between;align-items:center">
      <span class="muted small">Потрачено: <b id="wiz-sk-spent" class="${spent !== budget ? 'warn-text' : ''}">${spent}</b> / <b>${budget}</b>. Родительский уровень специализируемого навыка покупается из этого бюджета и распределяется между дочерними строками.</span>
    </div>
    <div class="muted small mb">Обязательные минимумы:</div><div class="must-list mb">${mustChips}</div>
    <div class="muted small mb">Рекомендации для ${esc(wiz.role)}:</div><div class="chips mb">${recommended}</div>
    <div class="skill-table-head"><span>Навык</span><span>STAT</span><span>LVL</span><span>BASE</span><span></span></div>
    <div class="skill-row role-skill-row"><span class="sname"><b>${esc(ab.name)}</b> <span class="tag role">роль</span></span><span class="sstat">—</span><span class="slvl"><b>4</b></span><span class="sbase">—</span><span></span></div>
    <div class="skill-list">${rows}</div>
    <div class="small muted mt">Культурный Language 4 бесплатен. Streetslang 2 и Local Expert 2 оплачиваются из родительских пулов. Нажми название навыка, чтобы открыть описание и примеры.</div>`;
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
  const f = item.fields || {};
  const rows = Object.entries(f).filter(([, value]) => value != null && String(value).trim()).map(([key, value]) => `<b>${esc(key)}</b><span>${esc(value)}</span>`).join('');
  openModal(`<h2>${esc(item.variant_name || item.display_name || item.name)}</h2>
    <div class="chips mb"><span class="chip">${esc(itemVisibleType(item, 'Предмет'))}</span>${item.source ? `<span class="tag">${esc(item.source)}</span>` : ''}${item.price != null ? `<span class="price">${money(item.price)}</span>` : ''}</div>
    ${item.desc ? `<p class="preserve-lines">${esc(item.desc)}</p>` : '<p class="muted">Описание в Data Pool не указано.</p>'}
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
  if (item.cat === 'armor' && wiz.gear.some(entry => entry.key === (item.variant_id || item.id))) return true;
  return false;
}

async function wizLoadShopList() {
  const wiz = state.wizard;
  const box = $('#wiz-shop-results');
  if (!box) return;
  const tab = WIZ_SHOP_CATS.find(t => t[0] === wiz.shopTab) || WIZ_SHOP_CATS[0];
  const scrollKey = `shop:${tab[0]}`;
  box.innerHTML = spinner();
  wiz._shopCache = wiz._shopCache || {};
  for (const cat of tab[2]) {
    if (!wiz._shopCache[cat]) {
      const response = await api('/api/items?' + new URLSearchParams({ cat, limit: 500 }));
      wiz._shopCache[cat] = response.items;
    }
  }
  let items = tab[2].flatMap(cat => wiz._shopCache[cat] || []).filter(item => item.price != null);
  if (tab[0] === 'chrome') items = items.filter(item => !String((item.fields || {}).Type || '').toLowerCase().includes('fashionware'));
  if (tab[0] === 'armor') items = armorPurchaseVariants(items);
  const q = (wiz.shopQ || '').trim().toLowerCase();
  if (q) items = items.filter(item => [item.variant_name, item.name, itemVisibleType(item)].some(value => String(value || '').toLowerCase().includes(q)));
  items.sort(byNameRu);

  const rowHtml = item => {
    const duplicate = isForbiddenDuplicate(wiz, item);
    const affordable = canAffordCreationItem(wiz, item, item.price || 0);
    const disabled = duplicate || !affordable;
    const requirement = String(item.desc || '').match(/Requires?\s+[^.;]+/i);
    return `<div class="inv-row catalog-row ${disabled ? 'unaffordable' : ''}">
      <span class="iname">${esc(item.variant_name || item.name)}</span>
      ${item.damage ? `<span class="weap-dmg">${esc(item.damage)}</span>` : ''}
      ${item.sp != null && item.purchase_location !== 'shield' ? `<span class="chip">SP ${item.sp}</span>` : ''}
      ${item.hl ? `<span class="hl-badge">HL ${item.hl}</span>` : ''}
      ${requirement ? `<span class="tag" title="${esc(requirement[0])}">требования</span>` : ''}
      <span class="${affordable ? 'price' : 'muted'}">${money(item.price)}</span>
      <button class="info-btn" data-shop-info="${esc(item.variant_id || item.id)}" title="Описание">i</button>
      <button class="btn-sm" data-shop-add="${esc(item.variant_id || item.id)}" ${disabled ? 'disabled' : ''} title="${duplicate ? 'Второй экземпляр запрещён' : ''}">＋</button>
    </div>`;
  };
  box.innerHTML = items.length ? groupedItemsHtml(items, rowHtml, tab[1]) : '<div class="empty">Ничего не нашлось.</div>';
  requestAnimationFrame(() => { box.scrollTop = (wiz.scrolls || {})[scrollKey] || 0; });
  box.onscroll = () => { wiz.scrolls[scrollKey] = box.scrollTop; };

  $$('[data-shop-info]', box).forEach(btn => btn.onclick = () => {
    const item = items.find(x => (x.variant_id || x.id) === btn.dataset.shopInfo);
    if (item) showCreationItemInfo(item);
  });
  $$('[data-shop-add]', box).forEach(btn => btn.onclick = () => {
    const item = items.find(x => (x.variant_id || x.id) === btn.dataset.shopAdd);
    if (!item) return;
    const price = item.price || 0;
    if (isForbiddenDuplicate(wiz, item)) { toast('Второй экземпляр этого предмета запрещён', true); return; }
    if (!canAffordCreationItem(wiz, item, price)) { toast('Не хватает стартового бюджета', true); return; }
    if (item.cat === 'cyberware') {
      wiz.cyberware.push({ id: item.id, name: item.name, hl: item.hl || 0, price,
        type: String((item.fields || {}).Type || 'Cyberware'), desc: item.desc || '', fields: item.fields || {}, source: item.source || '' });
      wiz.chromeCost += price;
    } else if (item.cat === 'armor') {
      const entry = { key: item.variant_id, source_key: item.id, cat: 'armor', name: item.name,
        display_name: item.variant_name, location: item.purchase_location, price, qty: 1,
        sp: item.sp != null ? item.sp : null, penalties: { ...(item.penalties || {}) },
        armor_bundled: !!item.armor_bundled, desc: item.desc || '', fields: item.fields || {}, source: item.source || '', type: itemVisibleType(item, 'Armor') };
      wiz.gear.push(entry);
      const piece = armorPieceFromItem(item);
      if (item.purchase_location === 'body' || item.purchase_location === 'set') wiz.armor.body = piece;
      if (item.purchase_location === 'head' || item.purchase_location === 'set') wiz.armor.head = piece;
      wiz.gearCost += price;
    } else {
      const existing = wiz.gear.find(x => x.key === item.id);
      if (existing) existing.qty = (existing.qty || 1) + 1;
      else wiz.gear.push({ key: item.id, cat: item.cat, name: item.name, price, qty: 1,
        damage: item.damage || null, sp: item.sp != null ? item.sp : null, desc: item.desc || '',
        fields: item.fields || {}, source: item.source || '', type: itemVisibleType(item, tab[1]) });
      wiz.gearCost += price;
    }
    renderWizard(); toast('Добавлено: ' + (item.variant_name || item.name));
  });
}

function cartSectionHtml(title, items) {
  return items.length ? `<section class="catalog-group"><h4 class="catalog-type">${esc(title)} <span>${items.length}</span></h4>${items.join('')}</section>` : '';
}

function wizStepShoppingHtml() {
  const wiz = state.wizard;
  const remaining = creationMainRemaining(wiz);
  const bonus = creationChromeBonus(wiz);
  const totalHl = wiz.cyberware.reduce((a, c) => a + (c.hl || 0), 0);
  const groupedChrome = [];
  const seen = new Set();
  wiz.cyberware.forEach((item, index) => {
    if (seen.has(item.id)) return;
    seen.add(item.id);
    const qty = wiz.cyberware.filter(x => x.id === item.id).length;
    const canPlus = String(item.name).toLowerCase() !== 'neuroport' && canAffordCreationItem(wiz, { cat: 'cyberware' }, item.price || 0);
    groupedChrome.push({ type: itemVisibleType(item, 'Cyberware'), html: `<div class="inv-row"><span class="iname">🦾 ${esc(item.name)}</span>${quantityControl('chrome', index, qty, canPlus)}<span class="hl-badge">HL ${(item.hl || 0) * qty}</span><span class="price">${money((item.price || 0) * qty)}</span><button class="info-btn" data-cart-info="chrome|${index}">i</button></div>` });
  });
  const groupedGear = wiz.gear.map((item, index) => ({ type: itemVisibleType(item, 'Снаряжение'), html: `<div class="inv-row"><span class="iname">${esc(item.display_name || item.name)}</span>${quantityControl('gear', index, item.qty || 1, item.cat !== 'armor' && canAffordCreationItem(wiz, item, item.price || 0))}${item.damage ? `<span class="weap-dmg">${esc(item.damage)}</span>` : ''}${item.sp != null ? `<span class="chip">SP ${item.sp}</span>` : ''}<span class="price">${money((item.price || 0) * (item.qty || 1))}</span><button class="info-btn" data-cart-info="gear|${index}">i</button></div>` }));
  const cartGroups = new Map();
  for (const row of [...groupedChrome, ...groupedGear]) { if (!cartGroups.has(row.type)) cartGroups.set(row.type, []); cartGroups.get(row.type).push(row.html); }
  const cartHtml = [...cartGroups.entries()].sort((a,b)=>a[0].localeCompare(b[0],'ru')).map(([type, rows]) => cartSectionHtml(type, rows)).join('');
  const paidPort = hasPaidNeuroport(wiz);
  const equipped = [['body','Тело'],['head','Голова']].map(([key,label]) => `<span class="chip"><b>${label}:</b> ${wiz.armor[key] ? esc(wiz.armor[key].name) + ' · SP ' + wiz.armor[key].sp : 'не выбрано'}</span>`).join('');
  return `
    <div class="panel accent mb">
      <label class="checkbox mb"><input type="checkbox" id="wiz-neuroport" ${wiz.freeNeuroport ? 'checked' : ''} ${paidPort ? 'disabled' : ''}>
        Бесплатный стартовый Neuroport по CEMK: 0€$, 0 HL, максимум Humanity не снижается${paidPort ? ' · отключён: куплен платный Neuroport' : ''}</label>
      <label class="checkbox"><input type="checkbox" id="wiz-soul" ${wiz.soldSoul ? 'checked' : ''}> Продаться армии, банде или корпорации: +1500€$ только на хром; остаток сгорает</label>
    </div>
    <div class="row mb" style="justify-content:space-between"><span class="muted small">Бюджет: <b>${money(GEAR_BUDGET)}</b> · Учтено: <b>${money(creationMainSpent(wiz))}</b> · Осталось: <b class="${remaining < 0 ? 'warn-text' : ''}">${money(remaining)}</b>${bonus ? ` · фонд хрома: ${money(bonus)}` : ''}</span><span class="muted small">Хром: ${wiz.cyberware.length} шт · HL <b class="hl-badge">${totalHl}</b></span></div>
    <div class="chips mb">${equipped}</div>
    <div class="tabs mb" id="wiz-shop-tabs">${WIZ_SHOP_CATS.map(([id, ru]) => `<button data-shop-tab="${id}" class="${wiz.shopTab === id ? 'active' : ''}">${ru}</button>`).join('')}</div>
    <div class="searchbar mb"><input id="wiz-shop-q" placeholder="Фильтр по названию или Type…" value="${esc(wiz.shopQ || '')}"></div>
    <div id="wiz-shop-results" class="catalog-scroll shop-scroll">${spinner()}</div>
    <div class="mt"><h3>📋 Корзина · по Type</h3></div><div id="wiz-shop-cart">${cartHtml || '<div class="empty small">Пока пусто.</div>'}</div>
    <div class="small muted mt">Кнопки − и + меняют количество с полным пересчётом цены, HL и Humanity. Neuroport виден в магазине, но бесплатный и платный варианты взаимоисключающие.</div>`;
}

/* ---------- Шаг 7: Итог ---------- */

function cyberwareRequirementErrors(w) {
  const chrome = [...w.cyberware, ...w.fashionware];
  const names = chrome.map(c => String(c.name || '').toLowerCase());
  const inventoryNames = [...w.gear, ...w.fashion].map(i => String(i.name || '').toLowerCase());
  const hasPort = w.freeNeuroport || names.includes('neuroport');
  const foundationNames = {
    cybereye: new Set(['cybereye', 'sponsored cybereye']),
    cyberarm: new Set(['cyberarm', 'neo-soviet cyberarm']),
    cyberleg: new Set(['cyberleg', 'romanova cyberlegs']),
    audio: new Set(['cyberaudio suite', 'discount cyberaudio suite']),
    socket: new Set(['chipware socket', 'budget chipware socket']),
  };
  const count = key => names.filter(name => foundationNames[key].has(name)).length;
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

function wizValidationErrors() {
  const w = state.wizard;
  const errors = [];
  const statSpent = wizStatSpent(), skillSpent = wizSkillSpent();
  if (statSpent !== (state.meta.stat_points || 62)) errors.push(`Характеристики: ${statSpent}/62 — нужно использовать ровно весь бюджет`);
  if (skillSpent !== (state.meta.skill_points || 86)) errors.push(`Навыки: ${skillSpent}/86 — нужно использовать ровно весь бюджет`);
  for (const s of (state.meta.must_skills || [])) if (!wizMustOk(s)) errors.push(`Обязательный навык не выполнен: ${s}`);
  for (const [name, lvl] of Object.entries(wizChar().skills)) if (lvl > (state.meta.skill_max || 6)) errors.push(`${name}: максимум создания — 6`);
  if (!w.nativeLanguage) errors.push('Не выбран культурный язык уровня 4');
  if (!w.handle || !w.handle.trim()) errors.push('Не заполнен Handle');
  const commonMissing = lpAllFields().filter(([key]) => !w.lifepath[key]).length;
  const roleMissing = lpRoleField(w.role).filter(([key]) => !w.roleLifepath[key]).length;
  if (commonMissing) errors.push(`Общий Lifepath: не заполнено полей — ${commonMissing}`);
  if (roleMissing) errors.push(`Lifepath роли ${w.role}: не заполнено полей — ${roleMissing}`);
  if (creationMainRemaining(w) < 0) errors.push('Превышен основной бюджет закупки');
  for (const [base] of SUB_SKILL_BASES) {
    const children = w.subSkills.filter(sub => sub.base === base && !sub.native && (sub.lvl || 0) > 0);
    const free = wizSubFree(base);
    if (free) errors.push(`${base}: распределите ещё ${free} ур. между специализациями`);
    if (children.some(sub => !String(sub.name || '').trim())) errors.push(`${base}: у каждой купленной специализации должно быть название`);
    const names = children.map(sub => String(sub.name).trim().toLowerCase());
    if (new Set(names).size !== names.length) errors.push(`${base}: названия специализаций не должны повторяться`);
  }
  const paidPorts = w.cyberware.filter(item => String(item.name).toLowerCase() === 'neuroport').length;
  if (paidPorts + (w.freeNeuroport ? 1 : 0) > 1) errors.push('Одновременно допустим только один Neuroport');
  if ((w.cyberware.length || w.fashionware.length || w.soldSoul) && !w.freeNeuroport && !paidPorts) errors.push('Хром 2070-х и сделка Sold Soul требуют Neuroport');
  errors.push(...cyberwareRequirementErrors(w));
  if (w.role === 'Tech') {
    const ranks = ['field','upgrade','fabrication','invention'].map(k => num(w.roleSetup[k]) || 0);
    if (ranks.reduce((a,b)=>a+b,0) !== 8 || ranks.some(x => x > 4)) errors.push('Tech должен распределить 8 рангов Maker, максимум 4 в специализации');
  }
  if (w.role === 'Medtech') {
    const ranks = ['surgery','pharma','cryo'].map(k => num(w.roleSetup[k]) || 0);
    if (ranks.reduce((a,b)=>a+b,0) !== 4) errors.push('Medtech должен распределить 4 ранга Medicine');
  }
  if (w.role === 'Exec' && !w.roleSetup.team_member) errors.push('Exec должен выбрать сотрудника Teamwork');
  if (w.role === 'Nomad' && (!Array.isArray(w.roleSetup.moto_choices) || w.roleSetup.moto_choices.length !== 4 || w.roleSetup.moto_choices.some(x => !String(x || '').trim()))) errors.push('Nomad должен заполнить все четыре стартовых выбора Moto');
  return errors;
}

function characterSkillLevel(char, name) {
  return Math.max(0, num((char.skills || {})[name]) || 0);
}

function specializedChildren(char, base) {
  const prefix = base + ' (';
  return Object.entries(char.skills || {}).filter(([name]) => name.startsWith(prefix) && name.endsWith(')'))
    .map(([name, lvl]) => ({ name: name.slice(prefix.length, -1), lvl: num(lvl) || 0 }))
    .sort((a, b) => a.name.localeCompare(b.name, 'ru'));
}

function characterSkillPool(char, base) {
  if (char.skill_pools && char.skill_pools[base] != null) return num(char.skill_pools[base]) || 0;
  return specializedChildren(char, base).filter(child => !(base === 'Language' && child.name === char.native_language && child.lvl === 4)).reduce((a, child) => a + child.lvl, 0);
}

function fullSkillsTableHtml(char, derived) {
  const specialized = new Set(SUB_SKILL_BASES.map(row => row[0]));
  let lastCat = null;
  const rows = [];
  for (const [cat, name, stat, is2] of state.meta.skills) {
    if (cat !== lastCat) { rows.push(`<div class="skill-cat">${esc(cat)}</div>`); lastCat = cat; }
    const lvl = specialized.has(name) ? characterSkillPool(char, name) : characterSkillLevel(char, name);
    const statValue = stat === 'EMP' ? (derived.emp_cur ?? (char.stats || {}).EMP) : (char.stats || {})[stat];
    rows.push(`<div class="skill-row ${specialized.has(name) ? 'skill-parent' : ''}">
      <button class="skill-name-btn sname" data-skill-info="${esc(name)}">${esc(name)} ${is2 ? '<span class="muted small">(×2)</span>' : '<span class="muted small">(×1)</span>'}</button>
      <span class="sstat">${esc(stat)} <b>${num(statValue) ?? 0}</b></span><span class="slvl"><b>${lvl}</b></span><span class="sbase"><b>${(num(statValue) || 0) + lvl}</b></span><span></span></div>`);
    if (specialized.has(name)) {
      for (const child of specializedChildren(char, name)) {
        rows.push(`<div class="skill-row subskill-row"><span class="sname subskill-name">↳ ${esc(child.name)}${name === 'Language' && child.name === char.native_language && child.lvl === 4 ? ' <span class="chip">культурный</span>' : ''}</span><span class="sstat">${esc(stat)} <b>${num(statValue) ?? 0}</b></span><span class="slvl"><b>${child.lvl}</b></span><span class="sbase"><b>${(num(statValue) || 0) + child.lvl}</b></span><span></span></div>`);
      }
    }
  }
  return `<div class="skill-table-head"><span>Навык</span><span>STAT</span><span>LVL</span><span>BASE</span><span></span></div><div class="skill-list full-skill-list">${rows.join('')}</div>`;
}

function chromeGroupedHtml(items, withInfo) {
  const rows = items.map((item, index) => ({ type: itemVisibleType(item, 'Cyberware'), html: `<div class="inv-row"><span class="iname">${esc(item.name)}</span><span class="hl-badge">HL ${item.hl || 0}</span>${item.price != null ? `<span class="price">${money(item.price)}</span>` : ''}${withInfo ? `<button class="info-btn" data-owned-chrome="${index}">i</button>` : ''}</div>` }));
  const groups = new Map();
  for (const row of rows) { if (!groups.has(row.type)) groups.set(row.type, []); groups.get(row.type).push(row.html); }
  return [...groups.entries()].sort((a,b)=>a[0].localeCompare(b[0],'ru')).map(([type, content]) => cartSectionHtml(type, content)).join('') || '<div class="empty small">— чист от хрома —</div>';
}

function wizStepSummaryHtml() {
  const wiz = state.wizard;
  const d = wizDerived();
  const c = wizChar();
  const errors = wizValidationErrors();
  const warnings = [];
  if (d.emp_cur != null && d.emp_cur <= 2) warnings.push('EMP ≤ 2 — персонаж близок к киберпсихозу');
  if (d.humanity_cur != null && d.humanity_cur < 0) errors.push('Текущая Humanity ниже 0 — персонаж в состоянии киберпсихоза');
  if (!wiz.armor.body) warnings.push('Не выбрана надетая броня для тела');
  if (!wiz.armor.head) warnings.push('Не выбрана надетая броня для головы');
  const totalCash = Math.max(0, creationMainRemaining(wiz));
  const statBlock = state.meta.stats.map(s => `<span class="chip"><b>${s}</b> ${wiz.stats[s] != null ? wiz.stats[s] : '—'}</span>`).join('');
  const allChrome = c.cyberware;
  const lpRows = lifepathNarrative(wiz.lifepath, wiz.role, wiz.roleLifepath);
  const ab = ROLE_ABILITIES[wiz.role] || { name: state.meta.roles[wiz.role] || '—', desc: '' };

  return `
    <div class="grid cols-2" style="gap:18px">
      <div>
        <div class="panel mb">
          <h3>🧬 ${esc(wiz.handle || 'Безымянный')}${wiz.firstName || wiz.lastName ? ` · ${esc([wiz.firstName, wiz.lastName].filter(Boolean).join(' '))}` : ''}</h3>
          <div class="chips mb">
            <span class="tag role">${esc(wiz.role)} · 4</span>
            <span class="tag price">${money(totalCash)}</span>
            <span class="chip">HP ${d.hp_max || '—'}</span>
            <span class="chip">HUM ${d.humanity_cur != null ? d.humanity_cur + '/' + d.humanity_max : '—'}</span>
            <span class="chip">EMP ${d.emp_cur != null ? d.emp_cur : '—'}</span>
          </div>
          <div class="small muted mb">Культурный язык: <b>${esc(wiz.nativeLanguage || '—')}</b> · Lifestyle: <b>${esc(c.lifestyle)}</b> · Жильё: <b>${esc(c.housing)}</b></div>
          <h4>📊 Характеристики</h4>
          <div class="statgrid mb">${statBlock}</div>
          <h4>🎯 Все навыки Corebook</h4>
          <div class="small muted mb">STAT — текущая характеристика; LVL — уровень; BASE = STAT + LVL. Для EMP используется значение после Humanity Loss.</div>
          ${fullSkillsTableHtml(c, d)}
          <h4>🛡️ Надетая броня</h4>
          <div class="chips mb"><span class="chip">Тело: ${wiz.armor.body ? esc(wiz.armor.body.name) + ' · SP ' + wiz.armor.body.sp : '—'}</span><span class="chip">Голова: ${wiz.armor.head ? esc(wiz.armor.head.name) + ' · SP ' + wiz.armor.head.sp : '—'}</span></div>
          <h4>🦾 Хром по категориям (HL ${allChrome.reduce((a, x) => a + (x.hl || 0), 0)})</h4>
          <div class="mb">${chromeGroupedHtml(allChrome, true)}</div>
          <h4>🎒 Инвентарь</h4>
          <div class="chips">${c.inventory.length ? c.inventory.map(i => `<span class="chip">${esc(i.name)}${(i.qty || 1) > 1 ? ' ×' + i.qty : ''}</span>`).join('') : '<span class="muted small">— пусто —</span>'}</div>
        </div>
        <div class="panel">
          <h3>🧬 Lifepath</h3>
          ${lpRows.length ? `<div class="kv">${lpRows.map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join('')}</div>` : '<div class="muted small">Lifepath не заполнен — вернись на шаг 2.</div>'}
        </div>
      </div>
      <div>
        <div class="panel"><h3>Identity</h3><div class="kv"><b>Handle</b><span>${esc(wiz.handle || '—')}</span><b>Имя</b><span>${esc(wiz.firstName || '—')}</span><b>Фамилия</b><span>${esc(wiz.lastName || '—')}</span></div><button class="btn-sm mt" onclick="wizGoTo(2)">Изменить в Lifepath</button></div>
        <div class="panel accent" style="margin-top:14px">
          <h3>🎭 ${esc(wiz.role)} — ${esc(state.meta.role_ru[wiz.role] || '')}</h3>
          <div class="small muted mb">${esc(state.meta.role_desc[wiz.role] || '')}</div>
          <div class="tag mb" style="display:inline-block;color:var(--yellow);border-color:rgba(255,213,0,.4)">⚡ ${esc(ab.name)}</div>
          <div class="small mt">${esc(ab.desc)}</div>
        </div>
        <div class="panel" style="margin-top:14px">
          <h3>⚠️ Проверки</h3>
          ${errors.map(w => `<div class="small mb" style="color:var(--red)">⛔ ${esc(w)}</div>`).join('')}
          ${warnings.map(w => `<div class="small mb" style="color:var(--orange)">⚠️ ${esc(w)}</div>`).join('')}
          ${!errors.length && !warnings.length ? '<div class="green small">✅ Все проверки пройдены! Можно создавать.</div>' : ''}
        </div>
        <div class="small muted mt">Остаток бюджета закупки записывается в наличные персонажа (${money(totalCash)}). Остаток бюджета стиля сгорел.</div>
      </div>
    </div>`;
}

/* ---------- биндинги шагов ---------- */

function hasRoleSpecificProgress(wiz) {
  const hasLifepath = Object.values(wiz.roleLifepath || {})
    .some(value => String(value || '').trim());
  const currentSetup = JSON.stringify(wiz.roleSetup || {});
  const defaultSetup = JSON.stringify(defaultRoleSetup(wiz.role));
  return hasLifepath || currentSetup !== defaultSetup;
}

function changeWizardRole(nextRole) {
  const wiz = state.wizard;
  if (!nextRole || nextRole === wiz.role) return;
  if (hasRoleSpecificProgress(wiz) &&
      !window.confirm(`Сменить роль ${wiz.role} на ${nextRole}? Заполненный ролевой Lifepath и изменённая настройка способности будут сброшены. Общие данные сохранятся.`)) return;
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
  for (const location of ['body', 'head']) if (wiz.armor[location] && wiz.armor[location].key === item.key) wiz.armor[location] = null;
}

function adjustShopCart(kind, index, delta) {
  const wiz = state.wizard;
  if (kind === 'chrome') {
    const sample = wiz.cyberware[index];
    if (!sample) return;
    if (delta > 0) {
      if (String(sample.name).toLowerCase() === 'neuroport') { toast('Второй Neuroport запрещён', true); return; }
      if (!canAffordCreationItem(wiz, { cat: 'cyberware' }, sample.price || 0)) { toast('Не хватает бюджета', true); return; }
      wiz.cyberware.push({ ...sample }); wiz.chromeCost += sample.price || 0;
    } else {
      const removeIndex = wiz.cyberware.findIndex(x => x.id === sample.id);
      const removed = wiz.cyberware[removeIndex];
      if (removed) { wiz.chromeCost = Math.max(0, wiz.chromeCost - (removed.price || 0)); wiz.cyberware.splice(removeIndex, 1); }
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
  const wiz = state.wizard;
  const step = wiz.step;
  const body = $('#wiz-body');
  if (!body) return;

  if (step === 1) {
    $$('[data-role]', body).forEach(btn => btn.onclick = () => changeWizardRole(btn.dataset.role));
    $$('[data-role-shift]', body).forEach(btn => btn.onclick = () => {
      const roles = wizardRoleOrder(); const next = (roles.indexOf(wiz.role) + Number(btn.dataset.roleShift) + roles.length) % roles.length;
      changeWizardRole(roles[next]);
    });
    const carousel = $('#role-carousel');
    if (carousel) {
      let touchX = null;
      carousel.ontouchstart = event => { touchX = event.changedTouches[0].clientX; };
      carousel.ontouchend = event => {
        if (touchX == null) return;
        const dx = event.changedTouches[0].clientX - touchX; touchX = null;
        if (Math.abs(dx) < 45) return;
        const roles = wizardRoleOrder(); const next = (roles.indexOf(wiz.role) + (dx < 0 ? 1 : -1) + roles.length) % roles.length;
        changeWizardRole(roles[next]);
      };
    }
    $$('[data-role-setup]', body).forEach(inp => inp.oninput = () => { wiz.roleSetup[inp.dataset.roleSetup] = Math.max(0, Math.min(4, num(inp.value) || 0)); });
    const team = $('#role-team'); if (team) team.onchange = () => { wiz.roleSetup.team_member = team.value; };
    $$('[data-moto-choice]', body).forEach(inp => inp.oninput = () => { wiz.roleSetup.moto_choices = wiz.roleSetup.moto_choices || ['', '', '', '']; wiz.roleSetup.moto_choices[Number(inp.dataset.motoChoice)] = inp.value; });
  }

  if (step === 2) {
    const handle = $('#wiz-handle'); if (handle) handle.oninput = () => { wiz.handle = handle.value; };
    const first = $('#wiz-first-name'); if (first) first.oninput = () => { wiz.firstName = first.value; };
    const last = $('#wiz-last-name'); if (last) last.oninput = () => { wiz.lastName = last.value; };
    $('[data-generate-handle]', body).onclick = () => { generateWizardHandle(); renderWizard(); };
    $('[data-generate-name]', body).onclick = () => { generateWizardName(); renderWizard(); };
    $$('[data-lp]', body).forEach(sel => sel.onchange = () => { wiz.lifepath[sel.dataset.lp] = sel.value; if (sel.dataset.lp === 'region') syncNativeLanguage(); renderWizard(); });
    $$('[data-role-lp]', body).forEach(sel => sel.onchange = () => { wiz.roleLifepath[sel.dataset.roleLp] = sel.value; renderWizard(); });
    $$('[data-lp-dice]', body).forEach(btn => btn.onclick = () => { wizRollLifepath(btn.dataset.lpDice, false); renderWizard(); });
    $$('[data-role-lp-dice]', body).forEach(btn => btn.onclick = () => { wizRollLifepath(btn.dataset.roleLpDice, true); renderWizard(); });
    const native = $('#lp-native'); if (native) native.onchange = () => { wiz.nativeLanguage = native.value; syncNativeLanguage(); renderWizard(); };
    const genAll = $('#lp-gen-all'); if (genAll) genAll.onclick = () => { lpAllFields().forEach(([key]) => wizRollLifepath(key, false)); lpRoleField(wiz.role).forEach(([key]) => wizRollLifepath(key, true)); syncNativeLanguage(); renderWizard(); toast('🎲 Общий и ролевой Lifepath сгенерированы'); };
  }

  if (step === 3) {
    $$('[data-wiz-stat]', body).forEach(inp => inp.oninput = () => { const key = inp.dataset.wizStat; const value = Math.max(2, Math.min(8, num(inp.value) || 2)); wiz.stats[key] = value; inp.value = value; updateWizStatBar(); wizRefreshLive(); });
    $('#wiz-st-roll').onclick = () => { const arr = [8,7,7,6,6,6,6,6,5,5]; for (let i=arr.length-1;i>0;i--){const j=Math.floor(Math.random()*(i+1));[arr[i],arr[j]]=[arr[j],arr[i]];} state.meta.stats.forEach((key,i)=>wiz.stats[key]=arr[i]); renderWizard(); };
    $('#wiz-st-reset').onclick = () => { state.meta.stats.forEach(key => wiz.stats[key] = 5); renderWizard(); };
    updateWizStatBar();
  }

  if (step === 4) {
    updateWizSkillHud();
    $$('[data-wiz-skill]', body).forEach(sel => sel.onchange = () => { wiz.skills[sel.dataset.wizSkill] = Number(sel.value); updateWizSkillHud(); wizRefreshLive(); });
    $$('[data-wiz-pool]', body).forEach(sel => sel.onchange = () => { const base = sel.dataset.wizPool; wiz.skills[base] = Math.max(wizSubAllocated(base), Number(sel.value)); renderWizard(); });
    $$('[data-sub-add]', body).forEach(btn => btn.onclick = () => { if (wizSubFree(btn.dataset.subAdd) <= 0) return; wiz.subSkills.push({ base: btn.dataset.subAdd, name: '', lvl: 1 }); renderWizard(); });
    $$('[data-sub-del]', body).forEach(btn => btn.onclick = () => { const item = wiz.subSkills[Number(btn.dataset.subDel)]; if (item && !item.native) wiz.subSkills.splice(Number(btn.dataset.subDel), 1); renderWizard(); });
    $$('[data-sub-name]', body).forEach(inp => inp.oninput = () => { const item = wiz.subSkills[Number(inp.dataset.subName)]; if (item && !item.native) item.name = inp.value; });
    $$('[data-sub-minus]', body).forEach(btn => btn.onclick = () => { const item = wiz.subSkills[Number(btn.dataset.subMinus)]; if (item && !item.native && item.lvl > 0) item.lvl--; renderWizard(); });
    $$('[data-sub-plus]', body).forEach(btn => btn.onclick = () => { const item = wiz.subSkills[Number(btn.dataset.subPlus)]; if (item && !item.native && item.lvl < 6 && wizSubFree(item.base) > 0) item.lvl++; renderWizard(); });
  }

  if (step === 5) {
    const query = $('#wiz-style-q'); if (query) query.oninput = () => { captureWizardScrolls(); wiz.styleQ = query.value; wiz.scrolls.style = 0; wiz.scrolls.fashionware = 0; wizLoadStyleLists(); };
    $$('[data-cart-qty]', body).forEach(btn => btn.onclick = () => { const [kind, index, delta] = btn.dataset.cartQty.split('|'); adjustStyleCart(kind, Number(index), Number(delta)); });
    $$('[data-cart-info]', body).forEach(btn => btn.onclick = () => { const [kind, index] = btn.dataset.cartInfo.split('|'); showCreationItemInfo(kind === 'style' ? wiz.fashion[Number(index)] : wiz.fashionware[Number(index)]); });
    wizLoadStyleLists();
  }

  if (step === 6) {
    const neuroport = $('#wiz-neuroport'); if (neuroport) neuroport.onchange = () => { if (neuroport.checked && hasPaidNeuroport(wiz)) { toast('Сначала удалите платный Neuroport', true); return; } wiz.freeNeuroport = neuroport.checked; renderWizard(); };
    const soul = $('#wiz-soul'); if (soul) soul.onchange = () => { wiz.soldSoul = soul.checked; renderWizard(); };
    $$('[data-shop-tab]', body).forEach(btn => btn.onclick = () => { captureWizardScrolls(); wiz.shopTab = btn.dataset.shopTab; renderWizard(); });
    const query = $('#wiz-shop-q'); if (query) query.oninput = () => { captureWizardScrolls(); wiz.shopQ = query.value; wiz.scrolls[`shop:${wiz.shopTab}`] = 0; wizLoadShopList(); };
    $$('[data-cart-qty]', body).forEach(btn => btn.onclick = () => { const [kind, index, delta] = btn.dataset.cartQty.split('|'); adjustShopCart(kind, Number(index), Number(delta)); });
    $$('[data-cart-info]', body).forEach(btn => btn.onclick = () => { const [kind, index] = btn.dataset.cartInfo.split('|'); showCreationItemInfo(kind === 'chrome' ? wiz.cyberware[Number(index)] : wiz.gear[Number(index)]); });
    wizLoadShopList();
  }

  $$('[data-skill-info]', body).forEach(btn => btn.onclick = () => showSkillInfo(btn.dataset.skillInfo));
  $$('[data-owned-chrome]', body).forEach(btn => btn.onclick = () => showCreationItemInfo(wizChar().cyberware[Number(btn.dataset.ownedChrome)]));
  body.addEventListener('input', saveWizardDraft);
  body.addEventListener('change', saveWizardDraft);
}

/* ---------- навигация ---------- */

function wizNext() {
  const wiz = state.wizard;
  if (wiz.step < 7) { wiz.step++; renderWizard(); }
  window.scrollTo(0, 0);
}

function wizPrev() {
  const wiz = state.wizard;
  if (wiz.step > 1) { wiz.step--; renderWizard(); }
  window.scrollTo(0, 0);
}

function wizGoTo(step) {
  state.wizard.step = Math.max(1, Math.min(7, step));
  renderWizard();
  window.scrollTo(0, 0);
}

function wizReset() {
  if (!window.confirm('Полностью очистить сохранённый draft и начать заново? Это действие нельзя отменить.')) return;
  clearWizardDraft();
  initWizard();
  renderWizard();
  toast('Draft очищен');
}

function wizRefreshLive() {
  const box = $('#wiz-live');
  if (!box) return;
  box.innerHTML = wizLiveHtml();
}

async function wizCreate() {
  const wiz = state.wizard;
  const errors = wizValidationErrors();
  if (errors.length) {
    toast(errors[0], true);
    return;
  }

  const char = wizChar();
  try {
    await api('/api/characters', { method: 'POST', body: { data: char } });
    wiz.created = true;
    clearWizardDraft();
    state.wizard = null;
    toast('🎉 Персонаж успешно создан!');
    location.hash = '#/characters';
  } catch (e) {
    toast(e.message, true);
  }
}

/* ============================== лист персонажа (просмотр) ============================== */

async function viewSheet(id) {
  const view = $('#view');
  view.innerHTML = spinner();
  let c;
  try {
    c = await api('/api/characters/' + id);
  } catch (e) {
    view.innerHTML = `<div class="empty">⚠️ ${esc(e.message)}</div>`;
    return;
  }
  const ch = c.data, d = c.derived;
  const mine = state.me && state.me.id === c.owner_id;
  const ab = ROLE_ABILITIES[ch.role] || { name: state.meta.roles[ch.role] || '', desc: '' };
  const hpCur = ch.hp_cur == null ? d.hp_max : ch.hp_cur;
  const cw = ch.cyberware || [];
  const inv = ch.inventory || [];
  const lpRows = ch.lifepath ? lifepathNarrative(ch.lifepath, ch.role, ch.role_lifepath, ch.lifepath_mode) : [];
  const armor = ch.armor || {};
  const armorSlots = [
    [armor.head, 'Голова'],
    [armor.body || armor.body_outer || armor.body_inner, 'Тело'],
  ].filter(([piece]) => piece);

  view.innerHTML = `
  <div class="page-head">
    <div><h1>📄 ${esc(ch.handle || 'Безымянный')}${ch.first_name || ch.last_name ? ` · ${esc([ch.first_name, ch.last_name].filter(Boolean).join(' '))}` : ''}</h1>
      <div class="sub">Лист персонажа · ${esc(ch.role || '—')} ${ch.role_rank || 4} · владелец: ${esc(c.owner_name || '—')}${ch.player ? ' · игрок: ' + esc(ch.player) : ''}</div></div>
    <div class="row">
      <button id="sheet-back">← К моим персонажам</button>
      ${mine ? `<button class="btn-primary" id="sheet-edit">✏️ Редактировать</button>
                <button class="btn-danger" id="sheet-del">🗑️ Удалить</button>` : ''}
    </div>
  </div>

  <div class="panel accent mb">
    <div class="derived">
      <span class="dstat"><span class="v">${d.hp_max != null ? hpCur + ' / ' + d.hp_max : '—'}</span><span class="k">HP</span></span>
      <span class="dstat"><span class="v">${d.seriously_wounded != null ? '≤ ' + d.seriously_wounded : '—'}</span><span class="k">Серьёзная рана</span></span>
      <span class="dstat ${d.humanity_max != null && d.humanity_cur <= 20 ? 'warn' : ''}"><span class="v">${d.humanity_max != null ? d.humanity_cur + ' / ' + d.humanity_max : '—'}</span><span class="k">Человечность</span></span>
      <span class="dstat ${d.emp_cur != null && d.emp_cur <= 2 ? 'warn' : ''}"><span class="v">${d.emp_cur != null ? d.emp_cur : '—'}</span><span class="k">EMP</span></span>
      <span class="dstat"><span class="v">${d.sp_body != null ? d.sp_body : '—'}</span><span class="k">Броня SP тело</span></span>
      <span class="dstat"><span class="v">${d.sp_head != null ? d.sp_head : '—'}</span><span class="k">Броня SP голова</span></span>
      <span class="dstat"><span class="v">${d.death_save != null ? d.death_save : '—'}</span><span class="k">Death Save</span></span>
      <span class="dstat"><span class="v">${money(ch.cash || 0)}</span><span class="k">Наличные</span></span>
    </div>
  </div>

  <div class="grid cols-2" style="gap:18px">
    <div>
      <div class="panel mb">
        <h2>🎭 ${esc(ch.role || '—')} — ${esc(state.meta.role_ru[ch.role] || '')}</h2>
        <div class="small muted mb">${esc(state.meta.role_desc[ch.role] || '')}</div>
        ${ab.name ? `<div class="tag mb" style="display:inline-block;color:var(--yellow);border-color:rgba(255,213,0,.4)">⚡ ${esc(ab.name)} · ранг ${ch.role_rank || 4}</div>` : ''}
        ${roleSetupSummary(ch.role, ch.role_setup) ? `<div class="chip mb">${esc(roleSetupSummary(ch.role, ch.role_setup))}</div>` : ''}
        ${ab.desc ? `<div class="small mt">${esc(ab.desc)}</div>` : ''}
      </div>
      <div class="panel mb">
        <h2>📊 Характеристики</h2>
        <div class="statgrid">${state.meta.stats.map(s => `
          <div class="stat"><div class="v">${(ch.stats || {})[s] != null ? ch.stats[s] : '—'}</div><div class="k">${s}</div></div>`).join('')}</div>
      </div>
      <div class="panel mb">
        <h2>🎯 Все навыки Corebook</h2>
        <div class="small muted mb">STAT · LVL · BASE = текущий STAT + LVL; EMP учитывает Humanity Loss.</div>
        ${fullSkillsTableHtml(ch, d)}
      </div>
      <div class="panel mb">
        <h2>🦾 Хром по категориям (HL ${cw.reduce((a, x) => a + (num(x.hl) || 0), 0)})</h2>
        ${chromeGroupedHtml(cw, true)}
      </div>
      <div class="panel mb">
        <h2>🎒 Инвентарь (${inv.length})</h2>
        ${inv.length ? groupedItemsHtml(inv.map((item, index) => ({ ...item, _sheetIndex: index })), i => `
          <div class="inv-row"><span class="iname">${esc(i.display_name || i.name)} ×${i.qty || 1}</span>
            ${i.damage ? `<span class="weap-dmg">${esc(i.damage)}</span>` : ''}
            ${i.sp != null ? `<span class="chip">SP ${i.sp}</span>` : ''}
            <span class="muted small">${money((i.price || 0) * (i.qty || 1))}</span><button class="info-btn" data-owned-item="${i._sheetIndex}">i</button>
          </div>`, 'Снаряжение') : '<div class="muted small">Пусто. Совсем.</div>'}
        ${armorSlots.length ? `<h3 class="mt">🛡️ Надетая броня</h3>${armorSlots.map(([piece, ru]) => `
          <div class="inv-row"><span class="iname">${ru}: ${esc(piece.name)}</span>
            <span class="chip">SP ${piece.sp}</span>
            ${Object.values(armorPenalties(piece)).some(v => v) ? `<span class="chip">${Object.entries(armorPenalties(piece)).map(([k,v]) => k + ' ' + v).join(' · ')}</span>` : ''}
          </div>`).join('')}` : ''}
      </div>
    </div>
    <div>
      <div class="panel mb">
        <h2>🧬 Lifepath</h2>
        ${lpRows.length ? `<div class="kv">${lpRows.map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join('')}</div>`
          : (ch.background ? `<div class="desc" style="white-space:pre-wrap">${esc(ch.background)}</div>` : '<div class="muted small">Lifepath не заполнен.</div>')}
      </div>
      ${ch.appearance ? `<div class="panel mb"><h2>🕶️ Внешность</h2><div class="desc">${esc(ch.appearance)}</div></div>` : ''}
      ${ch.languages ? `<div class="panel mb"><h2>🗣️ Языки</h2><div class="desc">${esc(ch.languages)}</div></div>` : ''}
      ${(ch.lifestyle || ch.housing) ? `<div class="panel mb"><h2>🏠 Жизнь</h2><div class="kv"><b>Lifestyle</b><span>${esc(ch.lifestyle || '—')}</span><b>Жильё</b><span>${esc(ch.housing || '—')}</span></div></div>` : ''}
      ${lpRows.length && ch.background ? `<div class="panel mb"><h2>📖 Предыстория</h2><div class="desc" style="white-space:pre-wrap">${esc(ch.background)}</div></div>` : ''}
      ${ch.notes ? `<div class="panel mb"><h2>📝 Заметки</h2><div class="desc" style="white-space:pre-wrap">${esc(ch.notes)}</div></div>` : ''}
    </div>
  </div>`;

  $$('[data-skill-info]', view).forEach(btn => btn.onclick = () => showSkillInfo(btn.dataset.skillInfo));
  $$('[data-owned-chrome]', view).forEach(btn => btn.onclick = () => showCreationItemInfo(cw[Number(btn.dataset.ownedChrome)]));
  $$('[data-owned-item]', view).forEach(btn => btn.onclick = () => showCreationItemInfo(inv[Number(btn.dataset.ownedItem)]));
  $('#sheet-back').onclick = () => go('/characters');
  const editBtn = $('#sheet-edit');
  if (editBtn) editBtn.onclick = () => { location.hash = '#/char/' + c.id + '?edit'; };
  const delBtn = $('#sheet-del');
  if (delBtn) delBtn.onclick = async () => {
    if (!confirm('Удалить персонажа навсегда?')) return;
    try {
      await api('/api/characters/' + c.id, { method: 'DELETE' });
      toast('Персонаж удалён');
      go('/characters');
    } catch (e) { toast(e.message, true); }
  };
}

/* ============================== мои персонажи ============================== */

async function viewCharacters(view) {
  if (!state.me) {
    view.innerHTML = `<div class="empty">Раздел только для вошедших. <a href="#/login">Войти</a> · <a href="#/register">Регистрация</a></div>`;
    return;
  }
  view.innerHTML = spinner();
  const data = await api('/api/characters');
  view.insertAdjacentHTML('afterbegin', `
    <div class="page-head">
      <div><h1>🧬 Мои персонажи</h1><div class="sub">Личное хранилище: ${data.characters.length}/50</div></div>
      <button class="btn-primary" onclick="location.hash='#/char/new'">+ Новый эджраннер</button>
    </div>`);
  const listEl = document.createElement('div');
  listEl.className = 'grid cols-3';
  view.appendChild(listEl);
  if (!data.characters.length) {
    listEl.outerHTML = '<div class="empty">Пока пусто. Создай первого эджраннера — процесс займёт пару минут.</div>';
    return;
  }
  listEl.innerHTML = data.characters.map(c => {
    const d = c.derived, ch = c.data;
    return `
    <div class="card" data-id="${c.id}">
      <div class="head row" style="justify-content:space-between">
        <h3 style="cursor:pointer" class="open">${esc(ch.handle || 'Безымянный')}</h3>
        <span class="muted small">${c.public ? '👁 публичный' : '🔒 приватный'}</span>
      </div>
      <div class="chips">
        <span class="tag role">${esc(ch.role || '—')} ${ch.role_rank || 4}</span>
        <span class="tag price">${money(ch.cash)}</span>
        ${d.hp_max ? `<span class="chip">HP ${d.hp_max}</span>` : ''}
        ${d.humanity_max != null ? `<span class="chip">HUM ${d.humanity_cur}/${d.humanity_max}</span>` : ''}
        ${ch.seed ? '<span class="tag seed">из Data Pool</span>' : ''}
      </div>
      <div class="muted small mt">обновлён ${timeAgo(c.updated)}</div>
      <div class="row mt">
        <button class="btn-sm btn-primary open">Открыть</button>
        <button class="btn-sm btn-danger del">Удалить</button>
      </div>
    </div>`;
  }).join('');
  $$('.card .open', view).forEach(el => el.onclick = () => go('/char/' + el.closest('.card').dataset.id));
  $$('.card .del', view).forEach(el => el.onclick = async () => {
    const card = el.closest('.card');
    if (!confirm('Удалить персонажа навсегда?')) return;
    try {
      await api('/api/characters/' + card.dataset.id, { method: 'DELETE' });
      toast('Персонаж удалён');
      viewCharacters(view);
    } catch (e) { toast(e.message, true); }
  });
}

/* ============================== редактор персонажа ============================== */

const EDITOR_TABS = [
  ['base', 'Основное'], ['stats', 'Характеристики'], ['skills', 'Навыки'],
  ['gear', 'Снаряжение и оружие'], ['chrome', 'Кибернетика'], ['armor', 'Броня'], ['notes', 'Прочее'],
];

async function viewEditor(id) {
  if (!state.me) { $('#view').innerHTML = '<div class="empty">Нужен вход. <a href="#/login">Войти</a></div>'; return; }
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
  state.editor = { id: payload.id, char: payload.data, tab: 'base', dirty: false };

  view.innerHTML = `
  <div class="page-head">
    <div><h1 id="ed-title">${payload.id ? '✏️ Редактор: ' + esc(payload.data.handle || '…') : '🧬 Новый эджраннер'}</h1>
      <div class="sub" id="ed-sub"></div></div>
    <div class="row">
      <button onclick="location.hash='#/characters'">← К моим</button>
      <button class="btn-primary" id="ed-save">💾 Сохранить</button>
    </div>
  </div>
  <div class="panel accent mb" id="ed-derived"></div>
  <div class="editor-tabs" id="ed-tabs">
    ${EDITOR_TABS.map(([k, ru]) => `<button data-tab="${k}" class="${state.editor.tab === k ? 'active' : ''}">${ru}</button>`).join('')}
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
  $('#ed-title').textContent = (ed.id ? '✏️ Редактор: ' : '🧬 Новый: ') + (c.handle || 'Безымянный');
  $('#ed-sub').innerHTML = `${esc(c.role || '—')} · ${money(c.cash)} · ${c.public ? '👁 публичный' : '🔒 приватный'}`;
  const box = $('#ed-derived');
  const stat = (k, v, warn) => `<span class="dstat${warn ? ' warn' : ''}"><span class="v">${v == null ? '—' : v}</span><span class="k">${k}</span></span>`;
  box.innerHTML = `<div class="derived">
    ${stat('HP макс', d.hp_max)}
    ${stat('Текущее HP', (() => { let h = c.hp_cur == null ? d.hp_max : c.hp_cur; return h; })())}
    ${stat('Серьёзная рана ≤', d.seriously_wounded)}
    ${stat('Спасбросок смерти', d.death_save)}
    ${stat('Человечность', d.humanity_max != null ? d.humanity_cur + '/' + d.humanity_max : null, d.humanity_max != null && d.humanity_cur <= 20)}
    ${stat('EMP текущий', d.emp_cur, d.emp_cur != null && d.emp_cur <= 2)}
    ${stat('SP тело', d.sp_body)}
    ${stat('SP голова', d.sp_head)}
    ${stat('Штраф брони', Object.entries(d.armor_penalties || {}).map(([k,v]) => `${k} ${v}`).join(' · '), Object.values(d.armor_penalties || {}).some(v => v < 0))}
  </div>
  ${d.hum_cut ? `<div class="small muted" style="margin-top:6px">Срез макс. человечности за хром: −${d.hum_cut} (по 2 за хром, 4 за боргвер; HL: −${d.hl_total || 0}).</div>` : ''}
  ${d.emp_cur != null && d.emp_cur <= 2 ? '<div class="small" style="color:var(--magenta);margin-top:6px">⚠️ EMP ≤ 2 — на грани киберпсихоза. Осторожно с хромом.</div>' : ''}`;
}

async function saveEditor() {
  const ed = state.editor;
  if (!ed) return;
  const c = ed.char;
  if (!c.handle || !c.handle.trim()) { toast('Заполни псевдоним (Handle) на вкладке «Основное»', true); state.editor.tab = 'base'; renderEditorTab(); return; }
  try {
    const body = { data: c };
    const r = ed.id
      ? await api('/api/characters/' + ed.id, { method: 'PUT', body })
      : await api('/api/characters', { method: 'POST', body });
    state.editor.id = r.id;
    state.editor.dirty = false;
    history.replaceState(null, '', '#/char/' + r.id + '?edit');
    toast('Сохранено ✓');
    renderDerived();
  } catch (e) { toast(e.message, true); }
}

function renderEditorTab() {
  const ed = state.editor;
  const box = $('#ed-body');
  const c = ed.char;
  if (ed.tab === 'base') {
    const roleDesc = (state.meta.role_desc || {})[c.role] || '';
    const roleAb = state.meta.roles[c.role] || '';
    box.innerHTML = `
    <div class="panel">
      <div class="grid cols-2">
        <label class="f"><span>Псевдоним (Handle) *</span><input id="f-handle" maxlength="60" value="${esc(c.handle)}" placeholder="Выхлоп, Neon, Slim…"></label>
        <label class="f"><span>Имя (необязательно)</span><input id="f-first-name" maxlength="60" value="${esc(c.first_name || '')}"></label>
        <label class="f"><span>Фамилия (необязательно)</span><input id="f-last-name" maxlength="60" value="${esc(c.last_name || '')}"></label>
        <label class="f"><span>Роль</span><select id="f-role">
          ${Object.keys(state.meta.roles).map(r => `<option value="${r}" ${c.role === r ? 'selected' : ''}>${r} — ${esc(state.meta.role_ru[r])}</option>`).join('')}
        </select></label>
        <label class="f"><span>Ранг роли (старт — 4)</span><input id="f-rank" type="number" min="1" max="10" value="${c.role_rank || 4}"></label>
        <label class="f"><span>Игрок (реальное имя)</span><input id="f-player" maxlength="60" value="${esc(c.player || '')}"></label>
      </div>
      <div class="small muted mb" id="f-role-note">${roleDesc ? esc(roleDesc) + ' Способность: <b>' + esc(roleAb) + '</b>.' : ''}</div>
      <label class="f"><span>Внешность</span><textarea id="f-appearance" maxlength="4000">${esc(c.appearance || '')}</textarea></label>
      <label class="f"><span>Биография / предыстория</span><textarea id="f-background" maxlength="4000">${esc(c.background || '')}</textarea></label>
      <label class="f"><span>Счёт (€$)</span><input id="f-cash" type="number" min="0" step="50" value="${c.cash || 0}"></label>
      <p class="small muted">Старт по гайду: <b>${state.meta.start_cash_gear ?? 2550}€$</b> на оружие/броню/снаряжение/хром + <b>${state.meta.start_cash_fashion ?? 800}€$</b> отдельно на Fashion и Fashionware. Подробнее — в <a href="#/guides">гайдах</a>.</p>
    </div>`;
    $('#f-handle').oninput = (e) => { c.handle = e.target.value; edChanged(); };
    $('#f-first-name').oninput = (e) => { c.first_name = e.target.value; edChanged(); };
    $('#f-last-name').oninput = (e) => { c.last_name = e.target.value; edChanged(); };
    $('#f-role').onchange = (e) => {
      c.role = e.target.value; edChanged();
      const rd = (state.meta.role_desc || {})[c.role] || '';
      const ra = state.meta.roles[c.role] || '';
      $('#f-role-note').innerHTML = rd ? esc(rd) + ' Способность: <b>' + esc(ra) + '</b>.' : '';
    };
    $('#f-rank').oninput = (e) => { c.role_rank = num(e.target.value) || 4; edChanged(); };
    $('#f-player').oninput = (e) => { c.player = e.target.value; edChanged(); };
    $('#f-appearance').oninput = (e) => { c.appearance = e.target.value; };
    $('#f-background').oninput = (e) => { c.background = e.target.value; };
    $('#f-cash').oninput = (e) => { c.cash = num(e.target.value) || 0; edChanged(); };
  }
  if (ed.tab === 'stats') {
    const st = c.stats;
    const spent = Object.values(st).reduce((a, b) => a + (num(b) || 0), 0);
    const budget = state.meta.stat_points || 62;
    box.innerHTML = `
    <div class="panel">
      <div class="row mb">
        <span class="muted small">Стандарт создания: <b>${budget} очков</b>, каждая стата <b>2–8</b>. Потрачено: <b id="st-spent" class="${spent !== budget ? 'warn-text' : ''}">${spent}</b>${spent > budget ? ' — перебор!' : ''}</span>
        <button class="btn-sm" id="st-roll">🎲 Случайно (массив 8,7,7,6,6,6,6,6,5,5)</button>
        <button class="btn-sm" id="st-reset">Сбросить все на 5</button>
      </div>
      <div class="statgrid mb">
        ${state.meta.stats.map(s => {
          const v = num(st[s]);
          const bad = v != null && (v < 2 || v > 8);
          return `<div class="stat input${bad ? ' bad' : ''}"><span class="k">${s}</span><input type="number" min="2" max="8" data-stat="${s}" value="${st[s] != null ? st[s] : ''}"></div>`;
        }).join('')}
      </div>
      <div class="grid cols-2">
        <label class="f"><span>Текущее HP (пусто = максимум)</span><input id="f-hpcur" type="number" min="0" value="${c.hp_cur != null ? c.hp_cur : ''}" placeholder="авто"></label>
        <label class="f"><span>Текущая человечность (пусто = максимум)</span><input id="f-humcur" type="number" min="0" value="${c.humanity_cur != null ? c.humanity_cur : ''}" placeholder="авто"></label>
      </div>
      <p class="small muted">HP = 10 + 5×⌈(BODY+WILL)/2⌉. Текущая Humanity при установке уменьшается на HL. Максимальная Humanity отдельно уменьшается на <b>2</b> за обычный хром и на <b>4</b> за Borgware; Fashionware и бесплатный стартовый Neuroport CEMK исключены. Текущий EMP = Humanity ÷ 10 (вниз).</p>
    </div>`;
    $$('[data-stat]', box).forEach(inp => inp.oninput = () => {
      c.stats[inp.dataset.stat] = num(inp.value);
      const v = num(inp.value);
      inp.parentElement.classList.toggle('bad', v != null && (v < 2 || v > 8));
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
      const head = cat !== lastCat ? `<div class="skill-cat">${esc(cat)}</div>` : '';
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
    box.innerHTML = `<div class="panel"><div class="row mb" style="justify-content:space-between"><span class="muted small">При создании ровно <b>86</b>, максимум <b>6</b>. После создания редактор допускает развитие до 10. Потрачено при пересчёте: <b id="sk-spent">${skillSpent()}</b></span></div>
      <div class="must-list mb">${mustChips}</div>
      <div class="panel mb"><div class="row" style="justify-content:space-between"><h3>Специализированные навыки</h3><button class="btn-sm" id="add-special-skill">＋ Добавить</button></div>
        <label class="f"><span>Культурный язык (4 уровня бесплатно при создании)</span><input id="ed-native" value="${esc(c.native_language || '')}"></label>
        ${specialRows || '<div class="muted small">Нет специализированных навыков.</div>'}</div>
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
        <button class="btn-primary" id="add-weapon">＋ Оружие</button>
        <button id="add-gear">＋ Снаряжение</button>
        <span class="muted small grow">Всё купленное на рынке тоже попадает сюда.</span>
      </div>
      <div id="inv-list"></div>
    </div>`;
    $('#add-weapon').onclick = () => pickItem(['guns', 'melee', 'grenades', 'ammo'], 'Оружие', (it) => {
      addInvItem(it); renderEditorTab();
    });
    $('#add-gear').onclick = () => pickItem(null, 'Снаряжение (все категории)', (it) => {
      addInvItem(it); renderEditorTab();
    });
    renderInventoryList();
  }
  if (ed.tab === 'chrome') {
    box.innerHTML = `
    <div class="panel">
      <div class="row mb">
        <button class="btn-primary" id="add-chrome">＋ Вшить хром</button>
        <span class="muted small grow">HL импланта вычитается из человечности; при создании бери среднее значение (в скобках).</span>
      </div>
      <p class="small muted">Правило гайда: каждый хром (кроме Fashionware) дополнительно режет <b>максимум</b> человечности на 2, Borgware — на 4.</p>
      <div id="chrome-list"></div>
    </div>`;
    $('#add-chrome').onclick = () => pickItem(['cyberware'], 'Кибернетика', (it) => {
      const c2 = state.editor.char;
      c2.cyberware = c2.cyberware || [];
      c2.cyberware.push({ key: it.id, name: it.name, hl: it.hl || 0, price: it.price, type: (it.fields && it.fields.Type) || '' });
      renderEditorTab(); edChanged();
    });
    renderChromeList();
  }
  if (ed.tab === 'armor') {
    box.innerHTML = `
    <div class="panel">
      <p class="small muted">Броня выбирается отдельно для головы и тела. SP слоёв не складывается: работает только наибольший SP локации, а все надетые слои абляируются вместе. Применяется один самый строгий штраф отдельно к REF, DEX и MOVE.</p>
      <div class="grid cols-2" id="armor-slots"></div>
    </div>`;
    renderArmorSlots();
  }
  if (ed.tab === 'notes') {
    box.innerHTML = `
    <div class="panel">
      <label class="f"><span>Языки</span><input id="f-lang" maxlength="200" value="${esc(c.languages || '')}" placeholder="Streetslang, русский, английский…"></label>
      <label class="f"><span>Заметки</span><textarea id="f-notes" maxlength="4000" style="min-height:160px">${esc(c.notes || '')}</textarea></label>
      <label class="checkbox"><input type="checkbox" id="f-public" ${c.public !== false ? 'checked' : ''}> Показывать персонажа в общем ростере партии</label>
    </div>`;
    $('#f-lang').oninput = (e) => { c.languages = e.target.value; };
    $('#f-notes').oninput = (e) => { c.notes = e.target.value; };
    $('#f-public').onchange = (e) => { c.public = e.target.checked; edChanged(); };
  }
}

function addInvItem(it) {
  const c = state.editor.char;
  c.inventory = c.inventory || [];
  const ex = c.inventory.find(x => x.key === it.id);
  if (ex) ex.qty = (ex.qty || 1) + 1;
  else c.inventory.push({
    key: it.id, cat: it.cat, name: it.name, price: it.price, qty: 1,
    damage: it.damage || null, sp: it.sp != null ? it.sp : null,
  });
  edChanged();
}

function renderInventoryList() {
  const box = $('#inv-list');
  if (!box) return;
  const c = state.editor.char;
  const inv = c.inventory || [];
  if (!inv.length) { box.innerHTML = '<div class="empty">Пусто. Совсем. Даже пушки нет.</div>'; return; }
  box.innerHTML = inv.map(i => `
    <div class="inv-row" data-key="${esc(i.key)}">
      <span class="iname">${esc(i.name)}</span>
      ${i.damage ? `<span class="weap-dmg">${esc(i.damage)}</span>` : ''}
      ${i.sp != null ? `<span class="chip">SP ${i.sp}</span>` : ''}
      <span class="muted small">${money(i.price || 0)}</span>
      <button class="btn-sm" data-act="minus">−</button>
      <b>${i.qty || 1}</b>
      <button class="btn-sm" data-act="plus">＋</button>
      <button class="btn-sm btn-danger" data-act="del">✕</button>
    </div>`).join('');
  $$('.inv-row', box).forEach(row => {
    const key = row.dataset.key;
    $$('button', row).forEach(b => b.onclick = () => {
      const item = c.inventory.find(x => x.key === key);
      if (!item) return;
      if (b.dataset.act === 'plus') item.qty = (item.qty || 1) + 1;
      if (b.dataset.act === 'minus') { item.qty = (item.qty || 1) - 1; if (item.qty < 1) item.qty = 1; }
      if (b.dataset.act === 'del') c.inventory = c.inventory.filter(x => x.key !== key);
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
      <span class="iname">${esc(i.name)}</span>
      <span class="hl-badge">HL ${i.hl || 0}</span>
      <span class="chip">${esc(i.type || 'хром')}</span>
      <button class="btn-sm btn-danger" data-idx="${idx}">✕ вырезать</button>
    </div>`).join('');
  $$('[data-idx]', box).forEach(b => b.onclick = () => {
    c.cyberware.splice(Number(b.dataset.idx), 1);
    renderChromeList(); edChanged();
  });
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
  const slotDefs = [['body', 'Тело'], ['head', 'Голова']];
  box.innerHTML = slotDefs.map(([slot, ru]) => {
    const a = c.armor[slot];
    const penalty = a ? Object.entries(armorPenalties(a)).filter(([,v]) => v).map(([k,v]) => `${k} ${v}`).join(' · ') : '';
    return `<div class="card">
      <h3>${ru}</h3>
      ${a ? `<div class="row" style="justify-content:space-between">
          <div><b>${esc(a.name)}</b><div class="small muted">SP ${a.sp}${penalty ? ' · ' + esc(penalty) : ''}</div></div>
          <button class="btn-sm btn-danger" data-clear="${slot}">✕</button></div>`
        : '<div class="muted small mb">— пусто —</div>'}
      <button class="btn-sm mt" data-pick="${slot}">Выбрать броню</button>
    </div>`;
  }).join('');
  $$('[data-pick]', box).forEach(b => {
    const slot = b.dataset.pick;
    b.onclick = () => pickItem(['armor'], `Броня: ${slot === 'body' ? 'тело' : 'голова'}`, (it) => {
      const piece = { key: it.id + (it.armor_bundled ? '@set' : '@' + slot), source_key: it.id,
        name: it.name, sp: it.sp || 0, penalties: { ...(it.penalties || {}) }, bundled: !!it.armor_bundled };
      if (it.armor_bundled) { c.armor.body = { ...piece }; c.armor.head = { ...piece }; }
      else c.armor[slot] = piece;
      renderArmorSlots(); edChanged();
    }, it => !(it.armor_locations || []).includes('shield') && (it.armor_locations || ['body','head']).includes(slot));
  });
  $$('[data-clear]', box).forEach(b => b.onclick = () => {
    const removed = c.armor[b.dataset.clear];
    delete c.armor[b.dataset.clear];
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
      if (it) { onPick(it); closeModal(); }
    });
  };
  $('#pk-go', m).onclick = load;
  $('#pk-q', m).onkeydown = (e) => { if (e.key === 'Enter') load(); };
  await load();
}

/* ============================== ростер ============================== */

async function viewRoster(view) {
  view.innerHTML = `
  <div class="page-head"><div><h1>📋 Ростер партии</h1><div class="sub">Все публичные персонажи всех игроков.</div></div></div>
  <div class="searchbar"><input id="ro-q" placeholder="Фильтр: псевдоним, роль, игрок…"><button id="ro-go">Фильтр</button></div>
  <div id="ro-list">${spinner()}</div>`;
  let q = '';
  const load = async () => {
    $('#ro-list').innerHTML = spinner();
    const data = await api('/api/roster' + (q ? ('?q=' + encodeURIComponent(q)) : ''));
    const chars = data.characters;
    if (!chars.length) { $('#ro-list').innerHTML = '<div class="empty">Никого. Пока что.</div>'; return; }
    const byOwner = {};
    chars.forEach(c => { (byOwner[c.owner_name] = byOwner[c.owner_name] || []).push(c); });
    $('#ro-list').innerHTML = Object.entries(byOwner).map(([owner, list]) => `
      <h2 class="mt" style="color:var(--yellow)">👤 ${esc(owner)} <span class="muted small">(${list.length})</span></h2>
      <div class="grid cols-3">${list.map(c => rosterCard(c)).join('')}</div>`).join('');
    $$('.ro-open', $('#ro-list')).forEach(el => el.onclick = () => showRosterModal(Number(el.dataset.id)));
  };
  $('#ro-go').onclick = async () => { q = $('#ro-q').value.trim(); load(); };
  $('#ro-q').onkeydown = (e) => { if (e.key === 'Enter') { q = $('#ro-q').value.trim(); load(); } };
  await load();
}

function rosterCard(c) {
  const d = c.derived, ch = c.data;
  const st = ch.stats || {};
  return `
  <div class="card">
    <div class="row" style="justify-content:space-between;align-items:baseline">
      <h3 class="ro-open" style="cursor:pointer">${esc(ch.handle || 'Безымянный')}</h3>
      ${ch.seed ? '<span class="tag seed">Data Pool</span>' : ''}
    </div>
    <div class="chips">
      <span class="tag role">${esc(ch.role || '—')}${ch.role_rank ? ' ' + ch.role_rank : ''}</span>
      ${d.hp_max ? `<span class="chip">HP ${d.hp_max}</span>` : ''}
      ${d.humanity_max != null ? `<span class="chip">HUM ${d.humanity_cur}/${d.humanity_max}</span>` : ''}
      ${d.sp_body ? `<span class="chip">SP ${d.sp_body}</span>` : ''}
      ${(ch.cyberware || []).length ? `<span class="chip">🦾 ${(ch.cyberware || []).length}</span>` : ''}
    </div>
    ${Object.keys(st).length ? `<div class="char-summary">${state.meta.stats.map(s => `<span class="chip"><b>${s}</b> ${st[s] != null ? st[s] : '—'}</span>`).join('')}</div>` : ''}
    ${ch.player ? `<div class="muted small">игрок: ${esc(ch.player)}</div>` : ''}
    <button class="btn-sm ro-open mt" data-id="${c.id}">Лист персонажа</button>
  </div>`;
}

async function showRosterModal(id) {
  const c = await api('/api/characters/' + id);
  const ch = c.data, d = c.derived;
  const skills = Object.entries(ch.skills || {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1]);
  const inv = ch.inventory || [];
  const cw = ch.cyberware || [];
  const extra = Object.entries(ch.extra || {});
  openModal(`
    <h2>${esc(ch.handle)}</h2>
    <div class="chips mb">
      <span class="tag role">${esc(ch.role || '—')}${ch.role_rank ? ' ' + ch.role_rank : ''}</span>
      <span class="chip">владелец: ${esc(c.owner_name)}</span>
      ${ch.player ? `<span class="chip">игрок: ${esc(ch.player)}</span>` : ''}
      <span class="tag price">${money(ch.cash || 0)}</span>
      ${d.death_save ? `<span class="chip">Death Save ${d.death_save}</span>` : ''}
    </div>
    ${Object.keys(ch.stats || {}).length ? `
      <div class="statgrid mb">${state.meta.stats.map(s => `<div class="stat"><div class="v">${ch.stats[s] != null ? ch.stats[s] : '—'}</div><div class="k">${s}</div></div>`).join('')}</div>
      <div class="derived mb">${[['HP', d.hp_max], ['HUM', d.humanity_max != null ? d.humanity_cur + '/' + d.humanity_max : null], ['EMP', d.emp_cur], ['SP тело', d.sp_body], ['SP голова', d.sp_head]]
        .filter(([, v]) => v != null).map(([k, v]) => `<span class="dstat"><span class="v">${v}</span><span class="k">${k}</span></span>`).join('')}</div>` : ''}
    ${extra.length ? `<div class="kv mb">${extra.map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join('')}</div>` : ''}
    ${ch.appearance ? `<p class="small"><b>Внешность:</b> ${esc(ch.appearance)}</p>` : ''}
    ${ch.background ? `<p class="small"><b>Биография:</b> ${esc(ch.background)}</p>` : ''}
    ${skills.length ? `<h3>Навыки</h3><div class="chips mb">${skills.map(([n, v]) => `<span class="chip">${esc(n)} <b>${v}</b></span>`).join('')}</div>` : ''}
    ${cw.length ? `<h3>Хром (${cw.reduce((a, x) => a + (x.hl || 0), 0)} HL)</h3><div class="chips mb">${cw.map(x => `<span class="chip">🦾 ${esc(x.name)} <b class="hl-badge">${x.hl || 0}</b></span>`).join('')}</div>` : ''}
    ${inv.length ? `<h3>Инвентарь</h3><div class="chips">${inv.map(x => `<span class="chip">${esc(x.name)}${x.qty > 1 ? ' ×' + x.qty : ''}</span>`).join('')}</div>` : ''}
    ${ch.notes ? `<hr><div class="desc">${esc(ch.notes)}</div>` : ''}
  `, true);
}

/* ============================== новости ============================== */

async function viewNews(view) {
  view.innerHTML = `
  <div class="page-head"><div><h1>📡 Сводки с улиц</h1><div class="sub">Краткие пересказы событий партий от разных источников.</div></div></div>
  <div id="news-compose"></div>
  <div id="news-list">${spinner()}</div>`;
  const composeBox = $('#news-compose');
  if (state.me) {
    composeBox.innerHTML = `
    <div class="panel mb">
      <div class="grid cols-2">
        <label class="f"><span>Заголовок</span><input id="nw-title" maxlength="140" placeholder="Перестрелка в Мегабилдинге H4"></label>
        <label class="f"><span>Источник / тег (партия, район…)</span><input id="nw-tag" maxlength="40" placeholder="Партия «С-Unit», Уотсон…"></label>
      </div>
      <label class="f"><span>Что случилось</span><textarea id="nw-body" maxlength="20000" placeholder="Кратко: кто, где, чем кончилось…"></textarea></label>
      <button class="btn-primary" id="nw-post">Опубликовать</button>
    </div>`;
    $('#nw-post').onclick = async () => {
      try {
        await api('/api/news', { method: 'POST', body: { title: $('#nw-title').value, tag: $('#nw-tag').value, body: $('#nw-body').value } });
        toast('Опубликовано');
        viewNews(view);
      } catch (e) { toast(e.message, true); }
    };
  } else {
    composeBox.innerHTML = '<div class="empty mb">Войди, чтобы публиковать сводки. <a href="#/login">Войти</a></div>';
  }
  const data = await api('/api/news');
  $('#news-list').innerHTML = data.news.length ? data.news.map(n => `
    <div class="card post" data-id="${n.id}">
      <div class="meta">
        ${n.tag ? `<span class="tag">${esc(n.tag)}</span>` : ''}
        <span>📰 ${esc(n.author)}</span><span>·</span><span>${timeAgo(n.created)}</span>
        ${n.mine || (state.me && state.me.is_gm) ? '<button class="btn-sm btn-danger" data-del style="margin-left:auto">✕</button>' : ''}
      </div>
      <div class="title">${esc(n.title)}</div>
      <div class="desc">${esc(n.body)}</div>
    </div>`).join('') : '<div class="empty">Сводок нет. Улицы молчат.</div>';
  $$('#news-list [data-del]').forEach(b => b.onclick = async () => {
    if (!confirm('Удалить сводку?')) return;
    try {
      await api('/api/news/' + b.closest('.post').dataset.id, { method: 'DELETE' });
      toast('Удалено');
      viewNews(view);
    } catch (e) { toast(e.message, true); }
  });
}

/* ============================== доска заказов ============================== */

async function viewJobs(view) {
  view.innerHTML = `
  <div class="page-head">
    <div><h1>📞 Доска заказов</h1><div class="sub">ГМ-ы анонсируют партии, эджраннеры записываются.</div></div>
    ${state.me && state.me.is_gm ? '<button class="btn-primary" id="jb-new">＋ Разместить заказ</button>' : ''}
  </div>
  ${state.me && !state.me.is_gm ? '<div class="muted small mb">Размещать заказы могут пользователи с ролью ГМ (включается в профиле).</div>' : ''}
  <div id="jb-list">${spinner()}</div>`;
  const nb = $('#jb-new');
  if (nb) nb.onclick = jobComposeModal;
  const data = await api('/api/jobs');
  $('#jb-list').innerHTML = data.jobs.length ? data.jobs.map(j => `
    <div class="card job ${j.status}" data-id="${j.id}">
      <div class="meta">
        <span class="tag">${j.status === 'open' ? '🟢 открыт' : '🔴 закрыт'}</span>
        <span class="tag">${esc(j.system || 'Cyberpunk RED')}</span>
        ${j.when_text ? `<span>⏱ ${esc(j.when_text)}</span>` : ''}
        <span>ГМ: ${esc(j.author)}</span>
        <span class="slots">${j.slots ? `${j.signups}/${j.slots} слотов` : `записалось: ${j.signups}`}</span>
      </div>
      <h3 style="margin:4px 0">${esc(j.title)}</h3>
      <div class="desc" style="max-height:80px;overflow:hidden">${esc(j.description)}</div>
      <div class="row mt">
        <button class="btn-sm btn-primary" data-open>Подробнее / записаться</button>
        ${j.mine ? `<button class="btn-sm" data-toggle>${j.status === 'open' ? 'Закрыть' : 'Открыть'}</button>
                    <button class="btn-sm btn-danger" data-delete>Удалить</button>` : ''}
        ${j.joined && !j.mine ? '<span class="tag role">вы записаны</span>' : ''}
      </div>
    </div>`).join('') : '<div class="empty">Заказов нет. ГМ, разместите первый!</div>';
  $$('#jb-list [data-open]').forEach(b => b.onclick = () => showJobModal(Number(b.closest('.job').dataset.id)));
  $$('#jb-list [data-toggle]').forEach(b => b.onclick = async () => {
    const card = b.closest('.job');
    const jobs = await api('/api/jobs');
    const j = jobs.jobs.find(x => x.id === Number(card.dataset.id));
    try {
      await api(`/api/jobs/${card.dataset.id}/status`, { method: 'POST', body: { status: j.status === 'open' ? 'closed' : 'open' } });
      viewJobs(view);
    } catch (e) { toast(e.message, true); }
  });
  $$('#jb-list [data-delete]').forEach(b => b.onclick = async () => {
    if (!confirm('Удалить заказ?')) return;
    try {
      await api('/api/jobs/' + b.closest('.job').dataset.id, { method: 'DELETE' });
      toast('Удалено');
      viewJobs(view);
    } catch (e) { toast(e.message, true); }
  });
}

function jobComposeModal() {
  const m = openModal(`
    <h2>Новый заказ</h2>
    <label class="f"><span>Название</span><input id="jb-title" maxlength="140" placeholder="Ограбление конвоя Милитех"></label>
    <div class="grid cols-2">
      <label class="f"><span>Когда</span><input id="jb-when" maxlength="80" placeholder="Сб, 20:00 МСК"></label>
      <label class="f"><span>Слотов (0 = без лимита)</span><input id="jb-slots" type="number" min="0" max="20" value="4"></label>
    </div>
    <label class="f"><span>Система</span><input id="jb-system" maxlength="40" value="Cyberpunk RED"></label>
    <label class="f"><span>Описание</span><textarea id="jb-desc" maxlength="8000" placeholder="Сеттинг, состав, что взять с собой, куда подходить…"></textarea></label>
    <button class="btn-primary" id="jb-submit">Разместить</button>`);
  $('#jb-submit', m).onclick = async () => {
    try {
      await api('/api/jobs', { method: 'POST', body: {
        title: $('#jb-title', m).value, when_text: $('#jb-when', m).value,
        system: $('#jb-system', m).value, slots: Number($('#jb-slots', m).value) || 0,
        description: $('#jb-desc', m).value,
      } });
      closeModal();
      toast('Заказ размещён');
      route();
    } catch (e) { toast(e.message, true); }
  };
}

async function showJobModal(id) {
  const j = await api('/api/jobs/' + id);
  const m = openModal(`
    <h2>${esc(j.title)}</h2>
    <div class="meta" style="color:var(--muted);font-size:13.5px;margin-bottom:8px">
      <span class="tag">${j.status === 'open' ? '🟢 открыт' : '🔴 закрыт'}</span>
      <span class="tag">${esc(j.system || 'Cyberpunk RED')}</span>
      ${j.when_text ? `<span>⏱ ${esc(j.when_text)}</span>` : ''}
      <span>ГМ: ${esc(j.author)}</span>
    </div>
    <div class="desc mb">${esc(j.description)}</div>
    ${j.signups_list && j.signups_list.length ? `
      <h3>Записались (${j.signups_list.length}${j.slots ? ' из ' + j.slots : ''})</h3>
      ${j.signups_list.map(s => `
        <div class="inv-row"><span class="iname">${esc(s.user)}${s.char_name ? ' → <b>' + esc(s.char_name) + '</b>' : ''}</span>
        ${s.note ? `<span class="muted small">${esc(s.note)}</span>` : ''}</div>`).join('')}` : '<div class="muted small mb">Пока никто не записался.</div>'}
    <div class="row mt" id="jm-actions"></div>`);
  const actions = $('#jm-actions', m);
  if (state.me && !j.mine && j.status === 'open') {
    if (j.joined) {
      actions.innerHTML = '<span class="tag role">Вы записаны ✓</span> <button class="btn-sm btn-danger" id="jm-leave">Отменить запись</button>';
      $('#jm-leave', m).onclick = async () => {
        try { await api(`/api/jobs/${id}/leave`, { method: 'POST' }); toast('Запись отменена'); closeModal(); route(); } catch (e) { toast(e.message, true); }
      };
    } else {
      let chars = [];
      try { chars = (await api('/api/characters')).characters; } catch (e) {}
      actions.innerHTML = `
        <select id="jm-char" style="flex:1">
          <option value="">— без персонажа —</option>
          ${chars.map(c => `<option value="${esc(c.data.handle)}">${esc(c.data.handle)} — ${esc(c.data.role || 'персонаж')}</option>`).join('')}
        </select>
        <button class="btn-primary" id="jm-join">Записаться</button>`;
      $('#jm-join', m).onclick = async () => {
        try {
          await api(`/api/jobs/${id}/join`, { method: 'POST', body: { char_name: $('#jm-char', m).value } });
          toast('Вы записаны! ГМ свяжется.');
          closeModal(); route();
        } catch (e) { toast(e.message, true); }
      };
    }
  } else if (!state.me) {
    actions.innerHTML = '<span class="muted small">Войдите, чтобы записаться. <a href="#/login">Войти</a></span>';
  }
}

/* ============================== вход / профиль ============================== */

function viewLogin(view) {
  view.innerHTML = `
  <div class="grid cols-2" style="max-width:900px;margin:0 auto">
    <div class="panel">
      <h2>Вход</h2>
      <label class="f"><span>Логин</span><input id="lg-u" autocomplete="username"></label>
      <label class="f"><span>Пароль</span><input id="lg-p" type="password" autocomplete="current-password"></label>
      <button class="btn-primary" id="lg-go">Войти</button>
    </div>
    <div class="panel accent">
      <h2>Регистрация</h2>
      <label class="f"><span>Логин (латиница)</span><input id="rg-u" autocomplete="username"></label>
      <label class="f"><span>Отображаемое имя</span><input id="rg-d" placeholder="как тебя знают в городе"></label>
      <label class="f"><span>Пароль</span><input id="rg-p" type="password" autocomplete="new-password"></label>
      <label class="checkbox mb"><input type="checkbox" id="rg-gm"> Я ГМ (могу размещать заказы и вести выплаты)</label>
      <button class="btn-primary" id="rg-go">Создать аккаунт</button>
    </div>
  </div>`;
  const doLogin = async () => {
    try {
      state.me = await api('/api/login', { method: 'POST', body: { username: $('#lg-u').value, password: $('#lg-p').value } });
      renderUserbox();
      toast('С возвращением, ' + state.me.display_name);
      go('/characters');
    } catch (e) { toast(e.message, true); }
  };
  $('#lg-go').onclick = doLogin;
  $('#lg-p').onkeydown = (e) => { if (e.key === 'Enter') doLogin(); };
  $('#rg-go').onclick = async () => {
    try {
      state.me = await api('/api/register', { method: 'POST', body: {
        username: $('#rg-u').value, display_name: $('#rg-d').value,
        password: $('#rg-p').value, is_gm: $('#rg-gm').checked } });
      renderUserbox();
      toast('Добро пожаловать в Ночной город');
      go('/characters');
    } catch (e) { toast(e.message, true); }
  };
}

function viewRegister(view) { viewLogin(view); }

async function viewProfile(view) {
  if (!state.me) { view.innerHTML = '<div class="empty">Нужен вход. <a href="#/login">Войти</a></div>'; return; }
  view.innerHTML = `
  <div class="panel" style="max-width:560px;margin:0 auto">
    <h2>Профиль</h2>
    <label class="f"><span>Отображаемое имя</span><input id="pf-d" value="${esc(state.me.display_name)}"></label>
    <label class="checkbox mb"><input type="checkbox" id="pf-gm" ${state.me.is_gm ? 'checked' : ''}> Роль ГМ: размещение заказов на доске, выплаты персонажам</label>
    <button class="btn-primary" id="pf-save">Сохранить</button>
  </div>`;
  $('#pf-save').onclick = async () => {
    try {
      state.me = await api('/api/profile', { method: 'POST', body: {
        display_name: $('#pf-d').value, is_gm: $('#pf-gm').checked } });
      renderUserbox();
      toast('Профиль обновлён');
    } catch (e) { toast(e.message, true); }
  };
}

/* ============================== запуск ============================== */

(async function init() {
  window.addEventListener('hashchange', route);
  try {
    const [me, meta] = await Promise.all([api('/api/me'), api('/api/meta')]);
    state.me = me.user;
    state.meta = meta;
    state.meta._total = meta.cats.reduce((a, c) => a + c.count, 0);
  } catch (e) {
    $('#view').innerHTML = '<div class="empty">⚠️ Сервер недоступен: ' + esc(e.message) + '</div>';
    return;
  }
  renderUserbox();
  route();
})();
