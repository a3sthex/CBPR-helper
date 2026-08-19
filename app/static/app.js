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

function derive(char) {
  const st = char.stats || {};
  const out = {};
  const body = num(st.BODY), will = num(st.WILL);
  if (body != null && will != null) {
    out.hp_max = 10 + 5 * Math.ceil((body + will) / 2);
    out.seriously_wounded = Math.ceil(out.hp_max / 2);
    out.death_save = body;
  }
  const hl = (char.cyberware || []).reduce((a, c) => a + (num(c.hl) || 0), 0);
  // срез максимума человечности: фэшнвер 0, боргвер 4, прочий хром 2
  let humCut = 0;
  for (const c of (char.cyberware || [])) {
    const t = String(c.type || '').toLowerCase();
    if (t.includes('borgware')) humCut += 4;
    else if (!t.includes('fashionware')) humCut += 2;
  }
  const emp = num(st.EMP);
  if (emp != null) {
    out.humanity_max = emp * 10 - hl - humCut;
    let cur = num(char.humanity_cur);
    if (cur == null) cur = out.humanity_max;
    out.humanity_cur = Math.max(0, Math.min(cur, Math.max(0, out.humanity_max)));
    out.emp_cur = Math.floor(out.humanity_cur / 10);
    out.hl_total = hl;
    out.hum_cut = humCut;
  }
  const armor = char.armor || {};
  let penalty = 0;
  const sps = [];
  for (const slot of ['body_outer', 'body_inner']) {
    const a = armor[slot];
    if (a && num(a.sp) != null) { sps.push(num(a.sp)); penalty += num(a.penalty) || 0; }
  }
  if (sps.length) {
    sps.sort((a, b) => b - a);
    out.sp_body = sps[0] + (sps.length > 1 ? Math.ceil(sps[1] / 2) : 0);
  }
  if (armor.head && num(armor.head.sp) != null) {
    out.sp_head = num(armor.head.sp);
    penalty += num(armor.head.penalty) || 0;
  }
  out.armor_penalty = penalty || 0;
  return out;
}

function blankChar() {
  return {
    handle: '', role: 'Solo', role_rank: 4, player: '',
    appearance: '', background: '', notes: '', languages: '',
    stats: { INT: 6, REF: 6, DEX: 6, TECH: 6, COOL: 6, WILL: 6, LUCK: 6, MOVE: 6, BODY: 6, EMP: 6 },
    humanity_cur: null, hp_cur: null, cash: 2550,
    skills: {}, inventory: [], cyberware: [], armor: { head: null, body_outer: null, body_inner: null },
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
      <h2>🛡️ Наслоение брони</h2>
      <p class="small muted">Верхний слой + нижний слой: итоговый SP = больший SP + половина меньшего (вверх).</p>
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
    const hi = Math.max(o, i), lo = Math.min(o, i);
    $('#ar-out').innerHTML = `SP: <b>${hi + Math.ceil(lo / 2)}</b> <span class="muted small">(${hi} + ⌈${lo}/2⌉)</span>`;
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
  ['lifepath', '🧬 Lifepath',       'Прошлое персонажа: 13 пунктов. Выбери из списков или брось кости 🎲.'],
  ['stats',    '📊 Характеристики', '62 очка на 10 статов, каждая 2–8. По умолчанию все по 5.'],
  ['skills',   '🎯 Навыки',         '86 очков: обязательные минимумы по 2, макс. 6 + суб-навыки (языки, боевые искусства, локальные эксперты).'],
  ['style',    '🕶️ Стиль',          '800€$ на одежду и косметические импланты (0 HL). Неиспользованный остаток сгорает.'],
  ['shopping', '🛒 Закупка',        '2550€$ на оружие, броню, хром, программы, боеприпасы, одежду, транспорт и снаряжение.'],
  ['summary',  '✅ Итог',           'Проверь лист, впиши псевдоним и создай персонажа.'],
];

/* ---------- подробные описания ролевых способностей ---------- */

const ROLE_ABILITIES = {
  Solo: {
    name: 'Combat Awareness (Боевое чутьё)',
    desc: 'В начале каждого своего хода Соло распределяет очки Боевого чутья (равные рангу роли) между боевыми эффектами: Precision Attack (+1..+3 к атакам), Spot Weakness (снижение SP брони цели на 1..3), Damage Deflection (перенос попадания в руку/ногу), Fumble Recovery (защита от провалов на 1), Initiative Reaction (+ к инициативе) и Threat Detection (автоматическое обнаружение засад и слежки). Очки можно перераспределять каждый ход, подстраиваясь под ситуацию — Соло всегда на шаг впереди в бою.',
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
    desc: 'Ранг роли распределяется между четырьмя специализациями: Field Expertise (полевой ремонт чего угодно, даже без инструментов), Upgrade Expertise (улучшение предметов — точность оружию, SP броне, новые функции), Fabrication Expertise (изготовление предметов с нуля дешевле рыночной цены) и Invention Expertise (изобретение уникальных вещей, которых нет в каталогах). Техник — человек, который заставляет Тёмное Будущее работать: чинит, апгрейдит и создаёт.',
  },
  Medtech: {
    name: 'Medicine (Медицина)',
    desc: 'Ранг роли распределяется между тремя специализациями: Surgery (хирургия — единственный способ лечить тяжёлые критические травмы и устанавливать хром), Medical Tech / Pharmaceuticals (изготовление препаратов: стимуляторы, антибиотики, противоядия) и Cryosystem Operation (работа с криокамерами и криотанками — возвращение людей практически с того света). Медтех лечит и мясо, и хром, без лицензии и лишних вопросов.',
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
    desc: 'Семья Номада даёт ему доступ к транспорту. Ранг роли распределяется между количеством и классом машин (от байка до AV и яхты), которые семья готова предоставить, и бонусами к их использованию: вождение, ремонт и апгрейд силами клана. Номад может вызвать свой транспорт, поменять его на другой из гаража семьи, а при потере — со временем получить замену. Клан также подстрахует запчастями, ночлегом и парой крепких кулаков.',
  },
};

/* ---------- Lifepath: 13 пунктов (CP:R стр. 43–48) ---------- */

const LP_FIELDS = [
  ['region', 'Регион и культурный язык', [
    'Северная Америка (языки: английский, испанский, навахо, кри, креольский)',
    'Южная / Центральная Америка (языки: испанский, португальский, гуарани, кечуа)',
    'Западная Европа (языки: английский, французский, немецкий, итальянский, испанский, норвежский)',
    'Восточная Европа (языки: русский, украинский, польский, финский, румынский)',
    'Ближний Восток / Северная Африка (языки: арабский, иврит, персидский, турецкий, берберский)',
    'Африка южнее Сахары (языки: суахили, хауса, лингала, зулу, эве)',
    'Южная Азия (языки: хинди, бенгальский, урду, тамильский, непальский)',
    'Юго-Восточная Азия (языки: вьетнамский, тайский, индонезийский, тагальский, кхмерский)',
    'Восточная Азия (языки: китайский, японский, корейский, монгольский)',
    'Океания / Тихоокеанские острова (языки: английский, маори, гавайский, самоанский, таитянский)',
  ]],
  ['personality', 'Характер', [
    'Застенчивый и скрытный',
    'Бунтарь: антисоциальный и жестокий',
    'Высокомерный, гордый и отчуждённый',
    'Угрюмый, порывистый и упрямый',
    'Придирчивый, суетливый и нервный',
    'Спокойный и серьёзный',
    'Легкомысленный и взбалмошный',
    'Хитрый и лживый',
    'Интеллектуал, отстранённый от мира',
    'Дружелюбный и открытый',
  ]],
  ['clothing', 'Стиль одежды', [
    'Generic Chic (универсальный масс-маркет)',
    'Leisurewear (спортивный комфорт)',
    'Urban Flash (уличный неон и кибермода)',
    'Businesswear (деловой стиль)',
    'High Fashion (высокая мода)',
    'Bohemian (богемный стиль)',
    'Bag Lady Chic (нарочитое рваньё)',
    'Gang Colors (цвета своей банды)',
    'Nomad Leathers (кожа и пыль дорог)',
    'Asia Pop (азиатский поп-стиль)',
  ]],
  ['hair', 'Причёска', [
    'Ирокез',
    'Длинные и растрёпанные',
    'Короткие и торчащие',
    'Дикие, во все стороны',
    'Бритая голова',
    'Полосатые пряди',
    'Дикие яркие цвета',
    'Аккуратные и короткие',
    'Короткие кудри',
    'Длинные и прямые',
  ]],
  ['affectation', 'Особенность внешности', [
    'Татуировки',
    'Зеркальные очки',
    'Ритуальные шрамы',
    'Перчатки с шипами',
    'Кольцо в носу',
    'Пирсинг языка или другой пирсинг',
    'Странные ногти',
    'Ботинки или каблуки с шипами',
    'Перчатки без пальцев',
    'Странные контактные линзы',
  ]],
  ['value', 'Высшая ценность', [
    'Деньги', 'Честь', 'Своё слово', 'Честность', 'Знания',
    'Месть', 'Любовь', 'Власть', 'Семья', 'Дружба',
  ]],
  ['people', 'Отношение к людям', [
    'Я люблю почти всех',
    'Я ненавижу почти всех',
    'Люди — инструменты: используй их для своих целей',
    'Каждый человек ценен, каждая жизнь важна',
    'Люди — препятствия, которые нужно сокрушать',
    'Люди — овцы, а я волк',
    'Хорошие люди есть — их просто нужно найти',
    'Люди приятны, пока не разочаруют',
    'Никому нельзя доверять до конца',
    'Я держусь нескольких друзей, остальные — фон',
  ]],
  ['person', 'Ценный человек', [
    'Возлюбленный / возлюбленная',
    'Родитель',
    'Брат или сестра',
    'Ребёнок',
    'Наставник',
    'Лучший друг',
    'Питомец',
    'Группа, банда или семья',
    'Кумир или историческая личность',
    'Никого — ты ни к кому не привязываешься',
  ]],
  ['possession', 'Ценный предмет', [
    'Оружие', 'Инструмент', 'Предмет одежды', 'Фотография', 'Дневник',
    'Письмо', 'Украшение', 'Игрушка', 'Книга', 'Транспорт',
  ]],
  ['family', 'Происхождение семьи', [
    'Корпоративные управленцы (Corporate Execs)',
    'Корпоративные служащие (Corporate Managers)',
    'Корпоративные техники (Corporate Technicians)',
    'Номад-клан (Nomad Pack)',
    'Банда-«семья» (Ganger Family)',
    'Жители Боевой Зоны (Combat Zoners)',
    'Городская беднота (Urban Homeless)',
    'Обитатели мегабашни (Megastructure Warren Rats)',
    'Реклэймеры — пионеры заброшенных городов (Reclaimers)',
    'Эджраннеры (Edgerunners)',
  ]],
  ['crisis', 'Семейный кризис', [
    'Семья потеряла всё из-за предательства',
    'Семья потеряла всё из-за катастрофической ошибки',
    'Семью убили или разогнали — выжил только ты',
    'Семья в заложниках, тюрьме или рабстве у корпорации / банды',
    'Ты сам порвал с семьёй и ушёл',
    'Семья в бегах — вы скрываетесь',
    'Семья изгнана из родного дома',
    'Семья вымирает — ты последний носитель имени',
    'Семья ведёт вендетту, и ты в неё втянут',
    'Семья разбросана по миру — ты ищешь родных',
  ]],
  ['goal', 'Жизненная цель', [
    'Избавиться от дурной репутации',
    'Обрести власть и контроль',
    'Выбраться с Улицы',
    'Причинять боль и страдания тем, кто это заслужил',
    'Изжить и забыть своё прошлое',
    'Выследить виновных в твоих бедах',
    'Получить то, что принадлежит тебе по праву',
    'Спасти важного для тебя человека',
    'Добиться славы и признания',
    'Стать тем, кого боятся и уважают',
  ]],
];

/* ---------- ролевые предыстории (13-й пункт Lifepath) ---------- */

const LP_ROLE = {
  Rockerboy:  ['Твой первый концерт / выступление', [
    'Подпольный клуб в Боевой Зоне — тебя чуть не застрелили на сцене',
    'Корпоративная вечеринка — ты выступал перед богатыми ублюдками',
    'Уличный фестиваль — тебя услышали и позвали на запись',
    'Похороны друга — ты пел, все плакали',
    'ТВ-шоу — пять минут славы, которые едва не убили твою карьеру',
    'Тюремный концерт — для сокамерников и охраны',
    'Запись в подвале — демка, разошедшаяся по Сети',
    'Прямой эфир взлома — ты пел, пока нетраннеры отвлекали корпов',
    'Бар в Даунтауне — ты играл за еду и ночлег',
    'Свадьба номадов — трёхдневный джем в движущемся караване',
  ]],
  Solo: ['Твой первый урок / кто тебя тренировал', [
    'Отставной военный — бывший майор корпоративной армии',
    'Уличный ветеран — старый соло из Боевой Зоны',
    'Отец / мать — которые научили тебя держать ствол',
    'Банда — ты прошёл обряд посвящения с боем',
    'Спецшкола — корпоративная академия для будущих убийц',
    'Тренировочный полигон армии НСША — ты дезертир',
    'Монастырь боевых искусств — дзен и сталь',
    'Самоучка — метод проб и ошибок, ошибок было много',
    'Наставник-киборг — полчеловека, полмашины',
    'Голодиски с тренировками — и никакой морали',
  ]],
  Netrunner: ['Как ты получил свой первый дек / взломал первую сеть', [
    'Нашёл сломанный дек в мусоре — починил и вломился в сеть школы',
    'Украл у корпората — и сразу заработал срок в розыске',
    'Купил на улице за копейки — продавец не знал, что продаёт',
    'Подарок от друга-нетраннера — тот погиб в Сети через неделю',
    'Выиграл в карты / в кибер-бойне',
    'Наследство от старого нетраннера, который «ушёл в Сеть»',
    'Собрал сам из запчастей — работало через раз, но работало',
    'Получил в корпоративной школе — за успехи в программировании',
    'Военная разработка — ты тестировщик боевых программ',
    'Заказ на взлом — первый заказ, который определил твою карьеру',
  ]],
  Tech: ['Что ты починил / создал впервые', [
    'Свой первый хром — перепаял сломанный нейропорт',
    'Тостер, который взорвал кухню — но ты понял, КАК он работает',
    'Дрон-курьер — он прожил целых три дня до аварии',
    'Кибердек — да, ты собрал дек с нуля',
    'Оружие — самодельный пистолет из водопроводных труб',
    'Броню — перешил кевларовый жилет под себя',
    'Музыкальный синтезатор — для рокербоя из соседнего района',
    'Генератор — в Мегабашне вечно отключают свет',
    'Экзоскелет — строительный, но на него поставили пушку',
    'Медицинский сканер — ты думал, это спасёт жизни. Ошибался.',
  ]],
  Medtech: ['Твой первый пациент / операция', [
    'Уличная драка — друг с ножом в боку, ты ковырялся в ране на коленке',
    'Передозировка — ты откачал наркомана в переулке',
    'Роды — ты принимал роды прямо в такси',
    'Киберпсихоз — пришлось отключать хром живьём',
    'Падение с высоты — ты собирал по частям тело с тротуара',
    'Ожоги — ты лечил ребёнка, который выбежал из горящего здания',
    'Огнестрел — первое пулевое ранение, ты перевязывал себя сам',
    'Ампутация — срочно, на кухонном столе, без наркоза',
    'Эпидемия — ты работал во время вспышки неизвестного вируса',
    'Легальная практика — ты работал в клинике, пока корпы не закрыли её',
  ]],
  Media: ['Твой первый материал / репортаж', [
    'Блог — ты написал пост, который собрал миллион просмотров',
    'Стрим перестрелки — ты оказался в нужном месте в нужное время',
    'Интервью с сенсеем — ты поговорил с культовым эджраннером',
    'Расследование — ты раскрыл коррупцию в местном участке',
    'Фото — снимок, который напечатали на первой полосе',
    'Подкаст — твои истории услышали тысячи людей',
    'Провокация — ты написал фейк, который взорвал инфополе',
    'Военкор — ты снимал бой из окопа',
    'Рецензия — твой обзор хрома разошёлся на цитаты',
    'Заказной материал — корпы заплатили, ты написал, что надо',
  ]],
  Exec: ['В какой корпорации ты начинал и почему ушёл', [
    'Kang Tao — конкуренты предложили больше',
    'Arasaka — ты был пешкой в большой игре и сбежал',
    'Militech — тебя подставили и уволили с волчьим билетом',
    'Biotechnica — ты узнал слишком много о генной инженерии',
    'Xzotto — лотерейная корпорация, ты понял, что это лохотрон',
    'CitiNet — бюрократия сожрала твою душу',
    'Zetatech — отдел кибербезопасности, ты взламывал их же системы',
    'Trauma Team — ты ушёл, потому что не вывозил видеть смерти',
    'Orion Security — частная армия, ты был связным',
    'Независимый консультант — ты никогда не работал на корпов. Пока что.',
  ]],
  Lawman: ['Кто был твоим первым напарником', [
    'Ветеран — старый законник, который научил тебя выживать на улицах',
    'Молодой идеалист — ты учил его, а он погиб в первой перестрелке',
    'Коррумпированный коп — ты долго не замечал, а потом всё вскрылось',
    'Инсайдер — твой напарник был агентом корпорации',
    'Женщина-коп — ты влюбился, и это чуть не убило вас обоих',
    'Робот-напарник — дрон-компаньон, который стал другом',
    'Соло под прикрытием — эджраннер, который на самом деле работал на вас',
    'Лучший друг детства — вы пошли в полицию вместе',
    'Служебная собака — K9, верный друг, который спас тебе жизнь',
    'Без напарника — ты всегда работал один, так проще',
  ]],
  Fixer: ['Твоя первая сделка', [
    'Оружие — продал ствол уличному гангеру, который застрелил копа',
    'Информация — продал данные, которые привели к смерти человека',
    'Хром — впарил бракованный нейропорт доверчивому клиенту',
    'Наркотики — мелкий дилер, ты подсадил на иглу десяток школьников',
    'Услуги — нашёл соло для опасного заказа, тот не вернулся',
    'Броня — сбывал списанные армейские бронежилеты',
    'Контрабанда — перевёз груз через блокпосты',
    'Искусство — продал украденную картину коллекционеру',
    'Живой товар — ты помог людям бежать из города нелегально',
    'Легальный бизнес — ты начал с мелкой лавки и торговал хламом',
  ]],
  Nomad: ['Из какого ты клана / каравана', [
    'Клан «Металлические Псы» — перевозчики оружия по пустошам',
    'Семья «Шоссейные Призраки» — контрабандисты, знающие все маршруты',
    'Братство «Ветряные Крылья» — AV-пилоты и дальнобойщики',
    'Караван «Соляные Псы» — торговцы водой и припасами',
    'Клан «Разбитые Шины» — байкеры, живущие на скорости',
    'Семья «Тихие Волны» — моряки и речники',
    'Караван «Огненные Колёса» — пиротехники и каскадёры',
    'Клан «Стальные Когти» — охотники за головами в пустошах',
    'Одиночка — ты сам по себе, клан погиб или ты его покинул',
    'Корпоративный транспортный отдел — ты бывший водитель корпов',
  ]],
};

function lpRoleField(role) {
  const t = LP_ROLE[role];
  return t ? ['rolebg', 'Ролевая предыстория: ' + t[0], t[1]] : ['rolebg', 'Ролевая предыстория', ['—']];
}

function lpAllFields(role) {
  return [...LP_FIELDS, lpRoleField(role)];
}

function lifepathNarrative(lp, role) {
  const out = [];
  for (const [key, label] of lpAllFields(role)) {
    if (lp && lp[key]) out.push([label, lp[key]]);
  }
  return out;
}

/* ---------- суб-навыки ---------- */

const SUB_SKILL_BASES = [
  ['Language', 'Языки', ['Streetslang', 'Английский', 'Русский', 'Испанский', 'Японский', 'Китайский', 'Немецкий', 'Французский', 'Арабский', 'Корейский', 'Португальский', 'Хинди', 'Иврит', 'Польский', 'Итальянский', 'Суахили', 'Тагальский', 'Вьетнамский', 'Турецкий', 'Навахо']],
  ['Martial Arts', 'Боевые искусства', ['Karate', 'Judo', 'Taekwondo', 'Aikido']],
  ['Local Expert', 'Локальные эксперты', ['Свой район', 'Уотсон', 'Сити-центр', 'Боевая Зона', 'Мегабашня H4', 'Пустоши', 'Пасифика', 'Хейвуд', 'Санто-Доминго', 'Норт-Оук']],
];

const WIZ_SUB_HIDDEN = new Set(['Language', 'Martial Arts', 'Local Expert']);

/* ---------- закупка: 8 категорий ---------- */

const WIZ_SHOP_CATS = [
  ['weapons',  '🔫 Оружие',      ['guns', 'melee', 'gun_upgrades']],
  ['armor',    '🛡️ Броня',       ['armor']],
  ['chrome',   '🦾 Хром',        ['cyberware']],
  ['programs', '💾 Программы',   ['programs', 'net_stuff']],
  ['ammo',     '📦 Боеприпасы',  ['ammo', 'grenades']],
  ['clothes',  '🧥 Одежда',      ['fashion']],
  ['vehicles', '🏍️ Транспорт',   ['vehicles', 'vehicles_upgrades']],
  ['gear',     '🎒 Снаряжение',  ['gear', 'services']],
];

const WIZ_FASHIONWARE = ['biomonitor', 'chemskin', 'shift tacts', 'skinwatch', 'techhair', 'emp threading', 'light tattoo'];

const GEAR_BUDGET = 2550;
const FASHION_BUDGET = 800;

function byNameRu(a, b) {
  return String(a.name).localeCompare(String(b.name), ['ru', 'en'], { sensitivity: 'base' });
}

/* ===================== мастер: состояние ===================== */

function initWizard() {
  const stats = {};
  (state.meta ? state.meta.stats : ['INT','REF','DEX','TECH','COOL','WILL','LUCK','MOVE','BODY','EMP']).forEach(s => stats[s] = 5);
  state.wizard = {
    step: 1,
    role: 'Solo',
    handle: '',
    stats,
    skills: {},
    subSkills: [
      { base: 'Language', name: 'Streetslang', lvl: 4, free: true },
      { base: 'Local Expert', name: 'Свой район', lvl: 2 },
    ],
    cyberware: [],       // хром из закупки {id, name, hl, price, type}
    fashionware: [],     // косметика из шага «Стиль» {id, name, hl:0, price, type}
    gear: [], fashion: [],
    chromeCost: 0, gearCost: 0, fashionCost: 0,
    fashionBurned: false,
    lifepath: {},
    shopTab: 'weapons', shopQ: '', styleQ: '',
    created: false,
  };
  // обязательные минимумы (кроме суб-навыковых)
  for (const s of (state.meta.must_skills || [])) {
    if (!WIZ_SUB_HIDDEN.has(s)) state.wizard.skills[s] = 2;
  }
}

function wizChar() {
  const w = state.wizard;
  const lp = w.lifepath || {};
  const skills = Object.assign({}, w.skills);
  for (const s of w.subSkills) {
    if (!s.name || !(s.lvl > 0)) continue;
    skills[`${s.base} (${s.name})`] = s.lvl;
  }
  const langs = w.subSkills.filter(s => s.base === 'Language' && s.name && s.lvl > 0)
    .map(s => `${s.name} (${s.lvl})`).join(', ');
  const lpText = lifepathNarrative(lp, w.role).map(([k, v]) => `${k}: ${v}`).join('\n');
  return {
    handle: w.handle || 'Безымянный-07',
    role: w.role, role_rank: 4,
    stats: Object.assign({}, w.stats),
    hp_cur: null, humanity_cur: null,
    skills,
    cyberware: [...w.cyberware, ...w.fashionware].map(c => ({ key: c.id, name: c.name, hl: c.hl || 0, price: c.price, type: c.type || '' })),
    inventory: [...w.gear.map(i => ({ ...i })), ...w.fashion.map(i => ({ ...i }))],
    armor: {},
    cash: Math.max(0, GEAR_BUDGET - w.chromeCost - w.gearCost),
    appearance: [lp.clothing, lp.hair, lp.affectation].filter(Boolean).join(' · '),
    background: lpText,
    lifepath: Object.assign({}, lp),
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
  if (!state.wizard || state.wizard.created) initWizard();
  renderWizard();
}

function wizLiveHtml() {
  const wiz = state.wizard;
  const d = wizDerived();
  const remainingGear = GEAR_BUDGET - wiz.chromeCost - wiz.gearCost;
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

function renderWizard() {
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
                onclick="wizGoTo(${i + 1})" ${i + 1 > wiz.step ? 'disabled' : ''}>
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
          <button class="btn-sm" id="wiz-full-editor" title="Открыть полный редактор">✏️ Полный редактор</button>
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
  const fullEd = $('#wiz-full-editor');
  if (fullEd) fullEd.onclick = () => { state.wizard = null; viewEditor('new'); };

  bindWizStep();
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

function wizStepRoleHtml() {
  const wiz = state.wizard;
  return `
    <div class="mb"><label class="f" style="margin:0"><span>Псевдоним (Handle) — можно заполнить и на шаге «Итог»</span>
      <input id="wiz-handle" maxlength="60" value="${esc(wiz.handle)}" placeholder="Выхлоп, Neon, Slim…" style="max-width:400px"></label></div>
    <div class="role-grid">
      ${Object.keys(state.meta.roles).map(r => {
        const ru = state.meta.role_ru[r];
        const desc = state.meta.role_desc[r];
        const ab = ROLE_ABILITIES[r] || { name: state.meta.roles[r], desc: '' };
        return `<div class="role-card ${wiz.role === r ? 'selected' : ''}" data-role="${r}" style="cursor:pointer">
          <h3>${esc(r)} <span class="chip role">${esc(ru || '')}</span></h3>
          <div class="small muted">${esc(desc || '')}</div>
          <div class="tag mb mt" style="display:inline-block;color:var(--yellow);border-color:rgba(255,213,0,.4)">⚡ ${esc(ab.name)}</div>
          <div class="small" style="margin-top:6px">${esc(ab.desc)}</div>
        </div>`;
      }).join('')}
    </div>`;
}

/* ---------- Шаг 2: Lifepath ---------- */

function wizRollLifepath(key) {
  const wiz = state.wizard;
  const field = lpAllFields(wiz.role).find(f => f[0] === key);
  if (!field) return;
  const opts = field[2];
  wiz.lifepath[key] = opts[Math.floor(Math.random() * opts.length)];
}

function wizStepLifepathHtml() {
  const wiz = state.wizard;
  const lp = wiz.lifepath;
  const fields = lpAllFields(wiz.role);
  return `
    <div class="row mb" style="justify-content:space-between;align-items:center">
      <span class="muted small">13 пунктов прошлого. Выбирай из списков или жми 🎲 у каждого пункта.</span>
      <button class="btn-primary btn-sm" id="lp-gen-all">🎲 Сгенерировать весь Lifepath</button>
    </div>
    <div class="lp-grid">
      ${fields.map(([key, label, opts]) => `
        <div class="lp-item">
          <div class="lp-label">${esc(label)}</div>
          <div class="row" style="align-items:center;gap:6px;flex-wrap:nowrap">
            <select data-lp="${key}" style="flex:1;min-width:0">
              <option value="">— не выбрано —</option>
              ${opts.map(o => `<option value="${esc(o)}" ${lp[key] === o ? 'selected' : ''}>${esc(o)}</option>`).join('')}
            </select>
            <button class="btn-sm" data-lp-dice="${key}" title="Бросить 1d10">🎲</button>
          </div>
        </div>`).join('')}
    </div>`;
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
    el.classList.toggle('warn-text', spent > budget);
  }
}

function wizStepStatsHtml() {
  const wiz = state.wizard;
  const spent = wizStatSpent();
  const budget = state.meta.stat_points || 62;
  return `
    <div class="row mb" style="justify-content:space-between">
      <span class="muted small">Потрачено: <b id="wiz-st-spent" class="${spent > budget ? 'warn-text' : ''}">${spent}</b> / <b>${budget}</b> очков (каждая стата 2–8, по умолчанию 5)</span>
      <div class="row">
        <button class="btn-sm" id="wiz-st-roll">🎲 Сгенерировать</button>
        <button class="btn-sm" id="wiz-st-reset">Сброс на 5</button>
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
  let total = 0;
  for (const [name, lvl] of Object.entries(wiz.skills)) {
    total += (lvl || 0) * (dblCost[name] ? 2 : 1);
  }
  for (const s of wiz.subSkills) {
    let lvl = s.lvl || 0;
    if (s.free) lvl = Math.max(0, lvl - 4); // родной язык: 4 уровня бесплатно
    total += lvl * (s.base === 'Martial Arts' ? 2 : 1);
  }
  return total;
}

function wizMustOk(name) {
  const wiz = state.wizard;
  if (WIZ_SUB_HIDDEN.has(name)) {
    return wiz.subSkills.some(s => s.base === name && (s.lvl || 0) >= 2);
  }
  return (wiz.skills[name] || 0) >= 2;
}

function updateWizSkillHud() {
  const spent = wizSkillSpent();
  const budget = state.meta.skill_points || 86;
  const el = $('#wiz-sk-spent');
  if (el) {
    el.textContent = spent;
    el.classList.toggle('warn-text', spent > budget);
  }
  $$('.wiz-must-chip').forEach(chip => {
    const ok = wizMustOk(chip.dataset.must);
    chip.classList.toggle('ok', ok);
    chip.classList.toggle('bad', !ok);
    chip.textContent = (ok ? '✓ ' : '✗ ') + chip.dataset.must;
  });
}

function wizSubSkillsHtml() {
  const wiz = state.wizard;
  const maxLvl = state.meta.skill_max || 6;
  return `
    <div class="panel mb">
      <h3 style="margin-top:0">🧩 Суб-навыки</h3>
      <div class="small muted mb">Языки и локальные эксперты — обязательные минимумы (хотя бы один уровня 2). Родной язык — 4 уровня бесплатно. Боевые искусства — ×2 стоимость.</div>
      ${SUB_SKILL_BASES.map(([base, ru, presets]) => {
        const list = wiz.subSkills.map((s, i) => [s, i]).filter(([s]) => s.base === base);
        return `
        <div class="mb">
          <div class="row" style="justify-content:space-between;align-items:center">
            <b>${esc(ru)} <span class="muted small">(${esc(base)}${base === 'Martial Arts' ? ' ×2' : ''})</span></b>
            <button class="btn-sm" data-sub-add="${esc(base)}">＋ Добавить</button>
          </div>
          ${list.length ? list.map(([s, i]) => `
            <div class="row mt" style="align-items:center;gap:6px">
              <input data-sub-name="${i}" list="wiz-dl-${esc(base).replace(/\s+/g, '-')}" value="${esc(s.name)}" placeholder="Название…" style="flex:1;min-width:0">
              <select data-sub-lvl="${i}" style="width:90px">
                ${[0, 1, 2, 3, 4, 5, 6].map(r => `<option value="${r}" ${(s.lvl || 0) === r ? 'selected' : ''}>${r === 0 ? '—' : 'ур. ' + r}</option>`).join('')}
              </select>
              ${s.free ? '<span class="chip" title="Родной язык — 4 уровня бесплатно">родной</span>' : ''}
              <button class="btn-sm btn-danger" data-sub-del="${i}">✕</button>
            </div>`).join('') : '<div class="muted small mt">— пусто —</div>'}
          <datalist id="wiz-dl-${esc(base).replace(/\s+/g, '-')}">${presets.map(p => `<option value="${esc(p)}">`).join('')}</datalist>
        </div>`;
      }).join('')}
      <div class="small muted">Уровень навыка при создании — не выше ${maxLvl}.</div>
    </div>`;
}

function wizStepSkillsHtml() {
  const wiz = state.wizard;
  const skills = state.meta.skills.filter(s => !WIZ_SUB_HIDDEN.has(s[1]));
  const must = new Set((state.meta.must_skills || []).filter(s => !WIZ_SUB_HIDDEN.has(s)));
  const budget = state.meta.skill_points || 86;
  const maxLvl = state.meta.skill_max || 6;
  const spent = wizSkillSpent();

  const mustChips = (state.meta.must_skills || []).map(s => {
    const ok = wizMustOk(s);
    return `<span class="wiz-must-chip chip ${ok ? 'ok' : 'bad'}" data-must="${esc(s)}">${ok ? '✓' : '✗'} ${esc(s)}</span>`;
  }).join('');

  let lastCat = null;
  const rows = skills.map(([cat, name, stat, is2]) => {
    const head = cat !== lastCat ? `<div class="skill-cat">${esc(cat)}</div>` : '';
    lastCat = cat;
    const lvl = wiz.skills[name] || 0;
    const isMust = must.has(name);
    return head + `<div class="skill-row">
      <span class="sname">${isMust ? '<span class="must-tag" title="Обязательный минимум: 2 очка">★</span>' : ''}${esc(name)}${is2 ? ' <span class="muted small">(×2)</span>' : ''}</span>
      <span class="sstat">${stat}</span>
      <select data-wiz-skill="${esc(name)}" class="${lvl > maxLvl ? 'over-max' : ''}">
        ${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(r => `<option value="${r}" ${lvl === r ? 'selected' : ''}>${r === 0 ? '—' : r}</option>`).join('')}
      </select>
    </div>`;
  }).join('');

  const ab = ROLE_ABILITIES[wiz.role] || { name: state.meta.roles[wiz.role] || '—' };
  return `
    <div class="row mb" style="justify-content:space-between;align-items:center">
      <span class="muted small">Потрачено: <b id="wiz-sk-spent" class="${spent > budget ? 'warn-text' : ''}">${spent}</b> / <b>${budget}</b> очков. Макс. в навыке: <b>${maxLvl}</b></span>
    </div>
    <div class="muted small mb">Обязательные минимумы (по 2 очка):</div>
    <div class="must-list mb">${mustChips}</div>
    ${wizSubSkillsHtml()}
    <div class="skill-row" style="border-bottom:1px solid var(--line)">
      <span class="sname"><b>${esc(ab.name)}</b> <span class="tag role">способность роли · ${esc(wiz.role)} · старт — 4</span></span>
      <span class="sstat"></span>
      <select disabled><option>4</option></select>
    </div>
    <div class="skill-list">${rows}</div>
    <div class="small muted mt">×2-навыки стоят 2 очка за уровень. Языки, боевые искусства и локальные эксперты добавляются в блоке «Суб-навыки» выше.</div>`;
}

/* ---------- Шаг 5: Стиль и внешность ---------- */

async function wizLoadStyleLists() {
  const wiz = state.wizard;
  const boxC = $('#wiz-style-clothes');
  const boxF = $('#wiz-style-fw');
  if (!boxC || !boxF) return;
  if (!wiz._styleCache) {
    boxC.innerHTML = spinner();
    boxF.innerHTML = spinner();
    const [fash, cyber] = await Promise.all([
      api('/api/items?' + new URLSearchParams({ cat: 'fashion', limit: 500 })),
      api('/api/items?' + new URLSearchParams({ cat: 'cyberware', limit: 500 })),
    ]);
    wiz._styleCache = {
      clothes: fash.items.filter(i => i.price != null).sort(byNameRu),
      fashionware: cyber.items.filter(i =>
        (num(i.hl) || 0) === 0 &&
        String((i.fields || {}).Type || '').toLowerCase().includes('fashionware') &&
        WIZ_FASHIONWARE.some(n => String(i.name).toLowerCase().includes(n))
      ).sort(byNameRu),
    };
  }
  const remaining = FASHION_BUDGET - wiz.fashionCost;
  const q = (wiz.styleQ || '').trim().toLowerCase();
  let clothes = wiz._styleCache.clothes;
  if (q) clothes = clothes.filter(i => String(i.name).toLowerCase().includes(q));

  const rowHtml = (it, kind) => `
    <div class="inv-row" style="cursor:pointer;${(it.price || 0) > remaining ? 'opacity:.5' : ''}" data-style-add="${kind}|${it.id}">
      <span class="iname">${esc(it.name)}</span>
      ${kind === 'fw' ? '<span class="hl-badge">0 HL</span>' : ''}
      <span class="${(it.price || 0) > remaining ? 'muted' : 'price'}">${money(it.price)}</span>
      ${(it.price || 0) > remaining ? '<span class="tag" style="color:var(--red)">не хватает</span>' : ''}
    </div>`;

  boxC.innerHTML = clothes.length ? clothes.map(it => rowHtml(it, 'cl')).join('') : '<div class="empty small">Ничего не нашлось.</div>';
  boxF.innerHTML = wiz._styleCache.fashionware.length
    ? wiz._styleCache.fashionware.map(it => rowHtml(it, 'fw')).join('')
    : '<div class="empty small">Fashionware не найден.</div>';

  $$('[data-style-add]').forEach(row => row.onclick = () => {
    const [kind, id] = row.dataset.styleAdd.split('|');
    const src = kind === 'fw' ? wiz._styleCache.fashionware : wiz._styleCache.clothes;
    const it = src.find(x => x.id === id);
    if (!it) return;
    const price = it.price || 0;
    if (wiz.fashionCost + price > FASHION_BUDGET) { toast('Не хватает бюджета стиля (800€$)', true); return; }
    if (kind === 'fw') {
      if (wiz.fashionware.some(x => x.id === it.id)) { toast('Этот имплант уже вживлён', true); return; }
      wiz.fashionware.push({ id: it.id, name: it.name, hl: 0, price, type: 'Fashionware' });
    } else {
      const ex = wiz.fashion.find(x => x.key === it.id);
      if (ex) ex.qty = (ex.qty || 1) + 1;
      else wiz.fashion.push({ key: it.id, cat: it.cat, name: it.name, price, qty: 1 });
    }
    wiz.fashionCost += price;
    renderWizard();
    toast('Добавлено: ' + it.name);
  });
}

function wizStepStyleHtml() {
  const wiz = state.wizard;
  const remaining = FASHION_BUDGET - wiz.fashionCost;
  const cartHtml = () => {
    const rows = [];
    wiz.fashion.forEach((item, i) => rows.push(`
      <div class="inv-row"><span class="iname">🧥 ${esc(item.name)} ×${item.qty || 1}</span>
        <span class="price">${money((item.price || 0) * (item.qty || 1))}</span>
        <button class="btn-sm btn-danger" data-style-del="cl|${i}">✕</button>
      </div>`));
    wiz.fashionware.forEach((item, i) => rows.push(`
      <div class="inv-row"><span class="iname">💠 ${esc(item.name)}</span>
        <span class="hl-badge">0 HL</span>
        <span class="price">${money(item.price)}</span>
        <button class="btn-sm btn-danger" data-style-del="fw|${i}">✕</button>
      </div>`));
    return rows.length ? rows.join('') : '<div class="empty small">Пока ничего не выбрано.</div>';
  };
  return `
    <div class="row mb" style="justify-content:space-between">
      <span class="muted small">Бюджет стиля: <b>${money(FASHION_BUDGET)}</b> · Потрачено: <b>${money(wiz.fashionCost)}</b> · Осталось: <b class="${remaining < 0 ? 'warn-text' : ''}">${money(remaining)}</b></span>
      <span class="tag" style="color:var(--orange)">⚠️ Неиспользованный остаток сгорит при переходе дальше</span>
    </div>
    <div class="grid cols-2" style="grid-template-columns:1fr 1fr;gap:18px">
      <div class="panel">
        <h3>🧥 Одежда (Fashion)</h3>
        <div class="searchbar mb" style="margin-bottom:8px">
          <input id="wiz-style-q" placeholder="Фильтр по одежде…" value="${esc(wiz.styleQ || '')}">
        </div>
        <div id="wiz-style-clothes" style="max-height:300px;overflow:auto">${spinner()}</div>
      </div>
      <div class="panel">
        <h3>💠 Косметические импланты (Fashionware, 0 HL)</h3>
        <div class="small muted mb">Biomonitor, Chemskin, Shift Tacts, Skinwatch, Techhair, EMP Threading, Light Tattoo — не снижают человечность.</div>
        <div id="wiz-style-fw" style="max-height:300px;overflow:auto">${spinner()}</div>
      </div>
    </div>
    <div class="mt"><h3>📋 Выбранный стиль</h3></div>
    <div id="wiz-style-cart">${cartHtml()}</div>`;
}

/* ---------- Шаг 6: Закупка снаряжения ---------- */

async function wizLoadShopList() {
  const wiz = state.wizard;
  const box = $('#wiz-shop-results');
  if (!box) return;
  const tab = WIZ_SHOP_CATS.find(t => t[0] === wiz.shopTab) || WIZ_SHOP_CATS[0];
  box.innerHTML = spinner();
  wiz._shopCache = wiz._shopCache || {};
  for (const cid of tab[2]) {
    if (!wiz._shopCache[cid]) {
      const d = await api('/api/items?' + new URLSearchParams({ cat: cid, limit: 500 }));
      wiz._shopCache[cid] = d.items;
    }
  }
  let items = tab[2].flatMap(cid => wiz._shopCache[cid] || []).filter(i => i.price != null);
  const q = (wiz.shopQ || '').trim().toLowerCase();
  if (q) items = items.filter(i => String(i.name).toLowerCase().includes(q));
  items.sort(byNameRu); // строго по алфавиту A-Z / А-Я
  const remaining = GEAR_BUDGET - wiz.chromeCost - wiz.gearCost;

  box.innerHTML = items.length
    ? items.map(it => `
      <div class="inv-row" style="cursor:pointer;${(it.price || 0) > remaining ? 'opacity:.5' : ''}" data-shop-add="${it.id}">
        <span class="iname">${esc(it.name)}</span>
        ${it.damage ? `<span class="weap-dmg">${esc(it.damage)}</span>` : ''}
        ${it.sp != null ? `<span class="chip">SP ${it.sp}</span>` : ''}
        ${it.hl ? `<span class="hl-badge">HL ${it.hl}</span>` : ''}
        <span class="${(it.price || 0) > remaining ? 'muted' : 'price'}">${money(it.price)}</span>
        ${(it.price || 0) > remaining ? '<span class="tag" style="color:var(--red)">не хватает</span>' : ''}
      </div>`).join('')
    : '<div class="empty">Ничего не нашлось.</div>';

  const flat = items;
  $$('[data-shop-add]', box).forEach(row => row.onclick = () => {
    const it = flat.find(x => x.id === row.dataset.shopAdd);
    if (!it) return;
    const price = it.price || 0;
    if (wiz.chromeCost + wiz.gearCost + price > GEAR_BUDGET) { toast('Не хватает бюджета закупки (2550€$)', true); return; }
    if (it.cat === 'cyberware') {
      wiz.cyberware.push({ id: it.id, name: it.name, hl: it.hl || 0, price, type: (it.fields && it.fields.Type) || '' });
      wiz.chromeCost += price;
    } else {
      const ex = wiz.gear.find(x => x.key === it.id);
      if (ex) ex.qty = (ex.qty || 1) + 1;
      else wiz.gear.push({ key: it.id, cat: it.cat, name: it.name, price, qty: 1, damage: it.damage || null, sp: it.sp != null ? it.sp : null });
      wiz.gearCost += price;
    }
    renderWizard();
    toast('Добавлено: ' + it.name);
  });
}

function wizStepShoppingHtml() {
  const wiz = state.wizard;
  const remaining = GEAR_BUDGET - wiz.chromeCost - wiz.gearCost;
  const totalHl = wiz.cyberware.reduce((a, c) => a + (c.hl || 0), 0);

  const cartRows = [];
  wiz.cyberware.forEach((c, i) => cartRows.push(`
    <div class="inv-row"><span class="iname">🦾 ${esc(c.name)}</span>
      <span class="hl-badge">HL ${c.hl || 0}</span>
      <span class="chip">${esc(c.type || 'хром')}</span>
      <span class="price">${money(c.price)}</span>
      <button class="btn-sm btn-danger" data-shopdel="chrome|${i}">✕</button>
    </div>`));
  wiz.gear.forEach((item, i) => cartRows.push(`
    <div class="inv-row"><span class="iname">${esc(item.name)} ×${item.qty || 1}</span>
      ${item.damage ? `<span class="weap-dmg">${esc(item.damage)}</span>` : ''}
      ${item.sp != null ? `<span class="chip">SP ${item.sp}</span>` : ''}
      <span class="price">${money((item.price || 0) * (item.qty || 1))}</span>
      <button class="btn-sm btn-danger" data-shopdel="gear|${i}">✕</button>
    </div>`));

  return `
    <div class="row mb" style="justify-content:space-between">
      <span class="muted small">Бюджет закупки: <b>${money(GEAR_BUDGET)}</b> · Потрачено: <b>${money(wiz.chromeCost + wiz.gearCost)}</b> · Осталось: <b class="${remaining < 0 ? 'warn-text' : ''}">${money(remaining)}</b></span>
      <span class="muted small">Хром: ${wiz.cyberware.length} шт · HL <b class="hl-badge">${totalHl}</b></span>
    </div>
    <div class="tabs mb" id="wiz-shop-tabs">
      ${WIZ_SHOP_CATS.map(([id, ru]) => `<button data-shop-tab="${id}" class="${wiz.shopTab === id ? 'active' : ''}">${ru}</button>`).join('')}
    </div>
    <div class="searchbar mb" style="margin-bottom:8px">
      <input id="wiz-shop-q" placeholder="Фильтр внутри категории…" value="${esc(wiz.shopQ || '')}">
    </div>
    <div id="wiz-shop-results" style="max-height:320px;overflow:auto">${spinner()}</div>
    <div class="mt"><h3>📋 Корзина закупки</h3></div>
    <div id="wiz-shop-cart">${cartRows.length ? cartRows.join('') : '<div class="empty small">Пока пусто. Даже пушки нет.</div>'}</div>
    <div class="small muted mt">Каждый имплант (кроме Fashionware) режет максимум человечности на 2, Borgware — на 4. HL вычитается из человечности напрямую. Остаток бюджета закупки станет наличными персонажа.</div>`;
}

/* ---------- Шаг 7: Итог ---------- */

function wizStepSummaryHtml() {
  const wiz = state.wizard;
  const d = wizDerived();
  const c = wizChar();
  const warnings = [];

  const statSpent = wizStatSpent();
  const budgetStats = state.meta.stat_points || 62;
  if (statSpent > budgetStats) warnings.push('⚠️ Перерасход характеристик: ' + statSpent + '/' + budgetStats);
  if (statSpent < budgetStats) warnings.push(`💡 Неиспользовано ${budgetStats - statSpent} очков характеристик`);

  const skillSpent = wizSkillSpent();
  const budgetSkills = state.meta.skill_points || 86;
  if (skillSpent > budgetSkills) warnings.push('⚠️ Перерасход навыков: ' + skillSpent + '/' + budgetSkills);
  if (skillSpent < budgetSkills) warnings.push(`💡 Неиспользовано ${budgetSkills - skillSpent} очков навыков`);

  for (const s of (state.meta.must_skills || [])) {
    if (!wizMustOk(s)) warnings.push(`⚠️ Обязательный минимум не выполнен: ${s} (нужен уровень 2)`);
  }

  const maxLvl = state.meta.skill_max || 6;
  for (const [name, lvl] of Object.entries(c.skills)) {
    if (lvl > maxLvl) warnings.push(`⚠️ Навык ${name} превышает максимум создания (${maxLvl})`);
  }

  if (d.emp_cur != null && d.emp_cur <= 2) warnings.push('⚠️ EMP ≤ 2 — вы на грани киберпсихоза');
  if (d.humanity_max != null && d.humanity_max < 0) warnings.push('⚠️ Отрицательная человечность — киберпсихоз');
  if (!wiz.handle || !wiz.handle.trim()) warnings.push('⚠️ Заполни псевдоним (Handle)');

  const lpMissing = lpAllFields(wiz.role).filter(([key]) => !wiz.lifepath[key]).length;
  if (lpMissing) warnings.push(`💡 Lifepath заполнен не полностью (${13 - lpMissing}/13)`);

  const totalCash = Math.max(0, GEAR_BUDGET - wiz.chromeCost - wiz.gearCost);
  const statBlock = state.meta.stats.map(s => `<span class="chip"><b>${s}</b> ${wiz.stats[s] != null ? wiz.stats[s] : '—'}</span>`).join('');
  const skillChips = Object.entries(c.skills).filter(([, v]) => v > 0)
    .sort((a, b) => a[0].localeCompare(b[0], 'ru'))
    .map(([n, v]) => `<span class="chip">${esc(n)} <b>${v}</b></span>`).join('');
  const armorItems = wiz.gear.filter(i => i.cat === 'armor');
  const allChrome = [...wiz.cyberware, ...wiz.fashionware];
  const lpRows = lifepathNarrative(wiz.lifepath, wiz.role);
  const ab = ROLE_ABILITIES[wiz.role] || { name: state.meta.roles[wiz.role] || '—', desc: '' };

  return `
    <div class="grid cols-2" style="gap:18px">
      <div>
        <div class="panel mb">
          <h3>🧬 ${esc(wiz.handle || 'Безымянный')}</h3>
          <div class="chips mb">
            <span class="tag role">${esc(wiz.role)} · 4</span>
            <span class="tag price">${money(totalCash)}</span>
            <span class="chip">HP ${d.hp_max || '—'}</span>
            <span class="chip">HUM ${d.humanity_cur != null ? d.humanity_cur + '/' + d.humanity_max : '—'}</span>
            <span class="chip">EMP ${d.emp_cur != null ? d.emp_cur : '—'}</span>
          </div>
          <h4>📊 Характеристики</h4>
          <div class="statgrid mb">${statBlock}</div>
          <h4>🎯 Навыки (${Object.values(c.skills).filter(v => v > 0).length})</h4>
          <div class="chips mb">${skillChips || '<span class="muted small">—</span>'}</div>
          <h4>🛡️ Броня</h4>
          <div class="chips mb">${armorItems.length ? armorItems.map(i => `<span class="chip">${esc(i.name)}${i.sp != null ? ' · SP ' + i.sp : ''} ×${i.qty || 1}</span>`).join('') : '<span class="muted small">— без брони —</span>'}</div>
          <h4>🦾 Хром (HL ${allChrome.reduce((a, x) => a + (x.hl || 0), 0)})</h4>
          <div class="chips mb">${allChrome.length ? allChrome.map(x => `<span class="chip">${esc(x.name)} <b class="hl-badge">${x.hl || 0}</b></span>`).join('') : '<span class="muted small">— чист от хрома —</span>'}</div>
          <h4>🎒 Инвентарь</h4>
          <div class="chips">${c.inventory.length ? c.inventory.map(i => `<span class="chip">${esc(i.name)}${(i.qty || 1) > 1 ? ' ×' + i.qty : ''}</span>`).join('') : '<span class="muted small">— пусто —</span>'}</div>
        </div>
        <div class="panel">
          <h3>🧬 Lifepath</h3>
          ${lpRows.length ? `<div class="kv">${lpRows.map(([k, v]) => `<b>${esc(k)}</b><span>${esc(v)}</span>`).join('')}</div>` : '<div class="muted small">Lifepath не заполнен — вернись на шаг 2.</div>'}
        </div>
      </div>
      <div>
        <label class="f"><span>Псевдоним (Handle) *</span>
          <input id="wiz-summary-handle" maxlength="60" value="${esc(wiz.handle)}" placeholder="Выхлоп, Neon, Slim…"></label>
        <div class="panel accent" style="margin-top:14px">
          <h3>🎭 ${esc(wiz.role)} — ${esc(state.meta.role_ru[wiz.role] || '')}</h3>
          <div class="small muted mb">${esc(state.meta.role_desc[wiz.role] || '')}</div>
          <div class="tag mb" style="display:inline-block;color:var(--yellow);border-color:rgba(255,213,0,.4)">⚡ ${esc(ab.name)}</div>
          <div class="small mt">${esc(ab.desc)}</div>
        </div>
        <div class="panel" style="margin-top:14px">
          <h3>⚠️ Проверки</h3>
          ${warnings.length ? warnings.map(w => `<div class="small mb">${w}</div>`).join('') : '<div class="green small">✅ Все проверки пройдены! Можно создавать.</div>'}
        </div>
        <div class="small muted mt">Остаток бюджета закупки записывается в наличные персонажа (${money(totalCash)}). Остаток бюджета стиля сгорел.</div>
      </div>
    </div>`;
}

/* ---------- биндинги шагов ---------- */

function bindWizStep() {
  const wiz = state.wizard;
  const step = wiz.step;
  const body = $('#wiz-body');
  if (!body) return;

  if (step === 1) {
    const hdl = $('#wiz-handle');
    if (hdl) hdl.oninput = (e) => { wiz.handle = e.target.value; };
    $$('.role-card', body).forEach(card => card.onclick = () => {
      wiz.role = card.dataset.role;
      $$('.role-card', body).forEach(c => c.classList.toggle('selected', c.dataset.role === wiz.role));
    });
  }

  if (step === 2) {
    $$('[data-lp]', body).forEach(sel => sel.onchange = () => {
      wiz.lifepath[sel.dataset.lp] = sel.value;
    });
    $$('[data-lp-dice]', body).forEach(btn => btn.onclick = () => {
      wizRollLifepath(btn.dataset.lpDice);
      renderWizard();
    });
    const genAll = $('#lp-gen-all');
    if (genAll) genAll.onclick = () => {
      lpAllFields(wiz.role).forEach(([key]) => wizRollLifepath(key));
      renderWizard();
      toast('🎲 Lifepath сгенерирован полностью');
    };
  }

  if (step === 3) {
    $$('[data-wiz-stat]', body).forEach(inp => inp.oninput = () => {
      const s = inp.dataset.wizStat;
      const v = Math.max(2, Math.min(8, num(inp.value) || 2));
      wiz.stats[s] = v;
      inp.value = v;
      updateWizStatBar();
      wizRefreshLive();
    });
    $('#wiz-st-roll').onclick = () => {
      const arr = [8, 7, 7, 6, 6, 6, 6, 6, 5, 5];
      for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; }
      state.meta.stats.forEach((s, i) => wiz.stats[s] = arr[i]);
      renderWizard();
    };
    $('#wiz-st-reset').onclick = () => { state.meta.stats.forEach(s => wiz.stats[s] = 5); renderWizard(); };
    updateWizStatBar();
  }

  if (step === 4) {
    updateWizSkillHud();
    $$('[data-wiz-skill]', body).forEach(sel => sel.onchange = () => {
      wiz.skills[sel.dataset.wizSkill] = Number(sel.value);
      sel.classList.toggle('over-max', Number(sel.value) > (state.meta.skill_max || 6));
      updateWizSkillHud();
      wizRefreshLive();
    });
    $$('[data-sub-add]', body).forEach(btn => btn.onclick = () => {
      wiz.subSkills.push({ base: btn.dataset.subAdd, name: '', lvl: 2 });
      renderWizard();
    });
    $$('[data-sub-del]', body).forEach(btn => btn.onclick = () => {
      wiz.subSkills.splice(Number(btn.dataset.subDel), 1);
      renderWizard();
    });
    $$('[data-sub-name]', body).forEach(inp => inp.oninput = () => {
      const s = wiz.subSkills[Number(inp.dataset.subName)];
      if (s) s.name = inp.value;
      updateWizSkillHud();
    });
    $$('[data-sub-lvl]', body).forEach(sel => sel.onchange = () => {
      const s = wiz.subSkills[Number(sel.dataset.subLvl)];
      if (s) s.lvl = Number(sel.value);
      updateWizSkillHud();
      wizRefreshLive();
    });
  }

  if (step === 5) {
    const qInp = $('#wiz-style-q');
    if (qInp) qInp.oninput = () => { wiz.styleQ = qInp.value; wizLoadStyleLists(); };
    $$('[data-style-del]', body).forEach(btn => btn.onclick = () => {
      const [kind, idxStr] = btn.dataset.styleDel.split('|');
      const idx = Number(idxStr);
      if (kind === 'fw') {
        const item = wiz.fashionware[idx];
        if (item) wiz.fashionCost = Math.max(0, wiz.fashionCost - (item.price || 0));
        wiz.fashionware.splice(idx, 1);
      } else {
        const item = wiz.fashion[idx];
        if (item) wiz.fashionCost = Math.max(0, wiz.fashionCost - (item.price || 0) * (item.qty || 1));
        wiz.fashion.splice(idx, 1);
      }
      renderWizard();
    });
    wizLoadStyleLists();
  }

  if (step === 6) {
    $$('[data-shop-tab]', body).forEach(btn => btn.onclick = () => {
      wiz.shopTab = btn.dataset.shopTab;
      wiz.shopQ = '';
      renderWizard();
    });
    const qInp = $('#wiz-shop-q');
    if (qInp) qInp.oninput = () => { wiz.shopQ = qInp.value; wizLoadShopList(); };
    $$('[data-shopdel]', body).forEach(btn => btn.onclick = () => {
      const [kind, idxStr] = btn.dataset.shopdel.split('|');
      const idx = Number(idxStr);
      if (kind === 'chrome') {
        const item = wiz.cyberware[idx];
        if (item) wiz.chromeCost = Math.max(0, wiz.chromeCost - (item.price || 0));
        wiz.cyberware.splice(idx, 1);
      } else {
        const item = wiz.gear[idx];
        if (item) wiz.gearCost = Math.max(0, wiz.gearCost - (item.price || 0) * (item.qty || 1));
        wiz.gear.splice(idx, 1);
      }
      renderWizard();
    });
    wizLoadShopList();
  }

  if (step === 7) {
    const hdl2 = $('#wiz-summary-handle');
    if (hdl2) hdl2.oninput = (e) => { wiz.handle = e.target.value; };
  }
}

/* ---------- навигация ---------- */

function wizNext() {
  const wiz = state.wizard;
  if (wiz.step === 5 && !wiz.fashionBurned) {
    const rest = FASHION_BUDGET - wiz.fashionCost;
    wiz.fashionBurned = true;
    if (rest > 0) toast(`Остаток бюджета стиля сгорел: ${money(rest)} 🔥`);
  }
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
  initWizard();
  renderWizard();
}

function wizRefreshLive() {
  const box = $('#wiz-live');
  if (!box) return;
  box.innerHTML = wizLiveHtml();
}

async function wizCreate() {
  const wiz = state.wizard;
  if (!wiz.handle || !wiz.handle.trim()) { toast('Заполни псевдоним (Handle)', true); return; }

  const statSpent = wizStatSpent();
  const budgetStats = state.meta.stat_points || 62;
  if (statSpent > budgetStats) { toast(`Перерасход характеристик: ${statSpent}/${budgetStats}`, true); return; }

  const skillSpent = wizSkillSpent();
  const budgetSkills = state.meta.skill_points || 86;
  if (skillSpent > budgetSkills) { toast(`Перерасход навыков: ${skillSpent}/${budgetSkills}`, true); return; }

  for (const s of (state.meta.must_skills || [])) {
    if (!wizMustOk(s)) { toast(`Обязательный навык ${s} должен быть минимум 2`, true); return; }
  }

  const char = wizChar();
  try {
    await api('/api/characters', { method: 'POST', body: { data: char } });
    wiz.created = true;
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
  const skills = Object.entries(ch.skills || {}).filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'ru'));
  const cw = ch.cyberware || [];
  const inv = ch.inventory || [];
  const lpRows = ch.lifepath ? lifepathNarrative(ch.lifepath, ch.role) : [];
  const armor = ch.armor || {};
  const armorSlots = [['head', 'Голова'], ['body_outer', 'Тело: верхний слой'], ['body_inner', 'Тело: нижний слой']]
    .filter(([slot]) => armor[slot]);

  view.innerHTML = `
  <div class="page-head">
    <div><h1>📄 ${esc(ch.handle || 'Безымянный')}</h1>
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
        ${ab.desc ? `<div class="small mt">${esc(ab.desc)}</div>` : ''}
      </div>
      <div class="panel mb">
        <h2>📊 Характеристики</h2>
        <div class="statgrid">${state.meta.stats.map(s => `
          <div class="stat"><div class="v">${(ch.stats || {})[s] != null ? ch.stats[s] : '—'}</div><div class="k">${s}</div></div>`).join('')}</div>
      </div>
      <div class="panel mb">
        <h2>🎯 Навыки (${skills.length})</h2>
        ${skills.length ? `<div class="chips">${skills.map(([n, v]) => `<span class="chip">${esc(n)} <b>${v}</b></span>`).join('')}</div>` : '<div class="muted small">Навыки не заполнены.</div>'}
      </div>
      <div class="panel mb">
        <h2>🦾 Хром (HL ${cw.reduce((a, x) => a + (num(x.hl) || 0), 0)})</h2>
        ${cw.length ? cw.map(x => `
          <div class="inv-row"><span class="iname">${esc(x.name)}</span>
            <span class="hl-badge">HL ${x.hl || 0}</span>
            <span class="chip">${esc(x.type || 'хром')}</span>
          </div>`).join('') : '<div class="muted small">Чист от хрома. Пока что.</div>'}
      </div>
      <div class="panel mb">
        <h2>🎒 Инвентарь (${inv.length})</h2>
        ${inv.length ? inv.map(i => `
          <div class="inv-row"><span class="iname">${esc(i.name)} ×${i.qty || 1}</span>
            ${i.damage ? `<span class="weap-dmg">${esc(i.damage)}</span>` : ''}
            ${i.sp != null ? `<span class="chip">SP ${i.sp}</span>` : ''}
            <span class="muted small">${money(i.price || 0)}</span>
          </div>`).join('') : '<div class="muted small">Пусто. Совсем.</div>'}
        ${armorSlots.length ? `<h3 class="mt">🛡️ Надетая броня</h3>${armorSlots.map(([slot, ru]) => `
          <div class="inv-row"><span class="iname">${ru}: ${esc(armor[slot].name)}</span>
            <span class="chip">SP ${armor[slot].sp}</span>
            ${armor[slot].penalty ? `<span class="chip">штраф ${armor[slot].penalty}</span>` : ''}
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
      ${lpRows.length && ch.background ? `<div class="panel mb"><h2>📖 Предыстория</h2><div class="desc" style="white-space:pre-wrap">${esc(ch.background)}</div></div>` : ''}
      ${ch.notes ? `<div class="panel mb"><h2>📝 Заметки</h2><div class="desc" style="white-space:pre-wrap">${esc(ch.notes)}</div></div>` : ''}
    </div>
  </div>`;

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
    ${stat('Штраф брони', d.armor_penalty || 0, d.armor_penalty > 0)}
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
        <span class="muted small">Стандарт создания: <b>${budget} очков</b>, каждая стата <b>2–8</b>. Потрачено: <b id="st-spent" class="${spent > budget ? 'warn-text' : ''}">${spent}</b>${spent > budget ? ' — перебор!' : ''}</span>
        <button class="btn-sm" id="st-roll">🎲 Случайно (массив 8,7,7,6,6,6,6,6,5,5)</button>
        <button class="btn-sm" id="st-reset">Сброс на 6</button>
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
      <p class="small muted">HP = 10 + 5×⌈(BODY+WILL)/2⌉. Серьёзная рана = ½ HP (вверх), спасбросок смерти = BODY. Максимум человечности = EMP×10 − HL хрома − <b>2</b> за каждый хром (кроме фэшнвера, <b>4</b> за боргвер). Текущий EMP = человечность ÷ 10 (вниз).</p>
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
    $('#st-reset').onclick = () => { state.meta.stats.forEach(s => c.stats[s] = 6); renderEditorTab(); edChanged(); };
    $('#f-hpcur').oninput = (e) => { c.hp_cur = e.target.value === '' ? null : num(e.target.value); edChanged(); };
    $('#f-humcur').oninput = (e) => { c.humanity_cur = e.target.value === '' ? null : num(e.target.value); edChanged(); };
  }
  if (ed.tab === 'skills') {
    const skills = state.meta.skills;
    const dblCost = Object.fromEntries(skills.map(([cat, name, stat, is2]) => [name, !!is2]));
    const must = new Set(state.meta.must_skills || []);
    const budget = state.meta.skill_points || 86;
    const maxLvl = state.meta.skill_max || 6;
    const skillSpent = () => Object.entries(c.skills || {}).reduce((a, [k, v]) => a + (v || 0) * (dblCost[k] ? 2 : 1), 0);
    let lastCat = null;
    const rows = skills.map(([cat, name, stat, is2]) => {
      const head = cat !== lastCat ? `<div class="skill-cat">${esc(cat)}</div>` : '';
      lastCat = cat;
      const lvl = c.skills[name] || 0;
      const over = lvl > maxLvl;
      return head + `
        <div class="skill-row" data-skill="${esc(name)}">
          <span class="sname">${must.has(name) ? '<span class="must-tag" title="Обязательный минимум: 2 очка">★</span>' : ''}${esc(name)}${is2 ? ' <span class="muted small">(×2)</span>' : ''}${name === 'Language' ? ' <span class="muted small">· родной — 4 бесплатно</span>' : ''}</span>
          <span class="sstat">${stat}</span>
          <select data-rank="${esc(name)}" class="${over ? 'over-max' : ''}">
            ${[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map(r => `<option value="${r}" ${lvl === r ? 'selected' : ''}>${r === 0 ? '—' : r}</option>`).join('')}
          </select>
        </div>`;
    }).join('');
    const roleAbility = state.meta.roles[c.role] || '';
    const refreshSkHud = () => {
      const spent = skillSpent();
      const el = $('#sk-spent');
      if (el) {
        el.textContent = spent;
        el.classList.toggle('warn-text', spent > budget);
      }
      $$('.must-chip', box).forEach(chip => {
        const ok = (c.skills[chip.dataset.must] || 0) >= 2;
        chip.classList.toggle('ok', ok);
        chip.classList.toggle('bad', !ok);
        chip.innerHTML = (ok ? '✓ ' : '✗ ') + esc(chip.dataset.must);
      });
    };
    const mustChips = (state.meta.must_skills || []).map(s =>
      `<span class="must-chip ${(c.skills[s] || 0) >= 2 ? 'ok' : 'bad'}" data-must="${esc(s)}">${(c.skills[s] || 0) >= 2 ? '✓' : '✗'} ${esc(s)}</span>`).join('');
    box.innerHTML = `
    <div class="panel">
      <div class="row mb" style="justify-content:space-between;align-items:center">
        <span class="muted small">При создании: <b>${budget} очков</b>. ×2-навыки стоят 2 за уровень, максимум <b>${maxLvl}</b> в навыке. Потрачено: <b id="sk-spent">${skillSpent()}</b></span>
      </div>
      <div class="muted small mb">Обязательные минимумы (по 2 очка, итого 26):</div>
      <div class="must-list mb">${mustChips}</div>
      <div class="skill-row" style="border-bottom:1px solid var(--line)">
        <span class="sname"><b>${esc(roleAbility || '—')}</b> <span class="tag role">способность роли · ${esc(c.role)} · старт — 4</span></span>
        <span class="sstat"></span>
        <select id="sk-role"><option>${c.role_rank || 4}</option></select>
      </div>
      <div class="skill-list mt">${rows}</div>
    </div>`;
    $$('[data-rank]', box).forEach(sel => sel.onchange = () => {
      c.skills[sel.dataset.rank] = Number(sel.value);
      sel.classList.toggle('over-max', Number(sel.value) > maxLvl);
      refreshSkHud();
      edChanged();
    });
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
      <p class="small muted">Слоты: голова, тело (верхний слой), тело (нижний слой). Наслоение: больший SP + половина меньшего (вверх). Штрафы брони суммируются и режут REF/DEX/MOVE.</p>
      <div class="grid cols-3" id="armor-slots"></div>
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
  const slotDefs = [['head', 'Голова'], ['body_outer', 'Тело: верхний слой'], ['body_inner', 'Тело: нижний слой']];
  box.innerHTML = slotDefs.map(([slot, ru]) => {
    const a = c.armor[slot];
    return `<div class="card">
      <h3>${ru}</h3>
      ${a ? `<div class="row" style="justify-content:space-between">
          <div><b>${esc(a.name)}</b><div class="small muted">SP ${a.sp} · штраф ${a.penalty || 0}</div></div>
          <button class="btn-sm btn-danger" data-clear="${slot}">✕</button></div>`
        : '<div class="muted small mb">— пусто —</div>'}
      <button class="btn-sm mt" data-pick="${slot}">Выбрать броню</button>
    </div>`;
  }).join('');
  $$('[data-pick]', box).forEach(b => b.onclick = () => pickItem(['armor'], 'Броня', (it) => {
    const penalty = num((it.fields || {}).Penalty) || 0;
    state.editor.char.armor[b.dataset.pick] = { key: it.id, name: it.name, sp: it.sp || 0, penalty };
    renderArmorSlots(); edChanged();
  }));
  $$('[data-clear]', box).forEach(b => b.onclick = () => {
    delete state.editor.char.armor[b.dataset.clear];
    renderArmorSlots(); edChanged();
  });
}

/* выбор предмета из каталога */
async function pickItem(cats, title, onPick) {
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
    $('#pk-list', m).innerHTML = items.length ? items.map(it => `
      <div class="inv-row" style="cursor:pointer" data-id="${it.id}">
        <span class="iname">${esc(it.name)}</span>
        ${it.damage ? `<span class="weap-dmg">${esc(it.damage)}</span>` : ''}
        ${it.hl ? `<span class="hl-badge">HL ${it.hl}</span>` : ''}
        <span class="muted small">${it.price != null ? money(it.price) : '—'}</span>
      </div>`).join('') : '<div class="empty">Ничего не нашлось.</div>';
    $$('.inv-row', m).forEach(row => row.onclick = () => {
      const it = items.find(x => x.id === row.dataset.id);
      if (it) { onPick(it); }
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
