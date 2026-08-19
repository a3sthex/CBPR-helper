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
      const charId = seg1 ? seg1.split('?')[0] : '';
      if (!charId || charId === '') { await viewWizard(); return; }
      await viewEditor(charId); return;
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

/* ============================== мастер создания персонажа (Companion-style) ============================== */

const WIZARD_STEPS = [
  ['role',     '🎭 Роль',        'Выбери роль — она даёт ролевую способность и определяет стиль игры.'],
  ['lifepath', '🧬 Lifepath',    'Броски 1d10 по CP:R стр. 43: прошлое, семья, события жизни.'],
  ['stats',    '📊 Характеристики', '62 очка на 10 статов, каждая 2–8. HP/человечность обновляются на лету.'],
  ['skills',   '🎯 Навыки',       '86 очков: 13 обязательных минимумов по 2, макс. 6 в навыке, ×2 навыки.'],
  ['chrome',   '🦾 Хром',         'Импланты из категории «Кибернетика» за счёт бюджета снаряжения.'],
  ['shopping', '🛒 Закупка',      '2550€$ на всё + 800€$ на Fashion и Fashionware.'],
  ['summary',  '✅ Итог',         'Проверь лист, поправь предупреждения и создай персонажа.'],
];

/* ---------- таблицы Lifepath (CP:R стр. 43) ---------- */

const LP_CHILDHOOD = [
  [1,  'Улицы (Running on the Edge)', 'Ты рос на улице — быстрая еда, случайные ночлеги, умение за себя постоять.'],
  [2,  'Улицы (Running on the Edge)', ''],
  [3,  'Корпоративная зона (Corporate Zone)', 'Детство среди небоскрёбов, охраны и чистых улиц.'],
  [4,  'Корпоративная зона (Corporate Zone)', ''],
  [5,  'Номад-клановый табор (Nomad Pack)', 'Вольная жизнь в караване: ремонт, перегон грузов, семейственность.'],
  [6,  'Номад-клановый табор (Nomad Pack)', ''],
  [7,  'Боевая зона (Combat Zone)', 'Район боевых действий: взрывы, банды, трупы — обычное дело.'],
  [8,  'Боевая зона (Combat Zone)', ''],
  [9,  'Мегабашня (Megastructure)', 'Многоэтажные трущобы: сотни тысяч людей в одном здании.'],
  [10, 'Мегабашня (Megastructure)', ''],
];

const LP_FAMILY = [
  [1,  'Корпоративные управленцы (Corporate Execs)', ''],
  [2,  'Номад-клан (Nomad Pack)', ''],
  [3,  'Законники (Lawmen)', ''],
  [4,  'Уличные фиксеры (Street Fixers)', ''],
  [5,  'Бандиты (Gangers)', ''],
  [6,  'Журналисты / Медиа (Media)', ''],
  [7,  'Техники / Инженеры (Techies)', ''],
  [8,  'Бустеры-гангеры (Boostergangers)', ''],
  [9,  'Соло (Solos)', ''],
  [10, 'Эджраннеры (Edgerunners)', ''],
];

const LP_MOST_VALUED_PERSON = [
  [1,  'Любимый человек (A Lover)', ''],
  [2,  'Родитель (A Parent)', ''],
  [3,  'Сестра или брат (A Sibling)', ''],
  [4,  'Ребёнок (A Child)', ''],
  [5,  'Наставник (A Mentor)', ''],
  [6,  'Лучший друг (A Best Friend)', ''],
  [7,  'Питомец (A Pet)', ''],
  [8,  'Группа / банда / семья (A Group)', ''],
  [9,  'Историческая личность (A Historical Figure)', ''],
  [10, 'Никого — ты не привязываешься к людям', ''],
];

const LP_MOST_VALUED_POSSESSION = [
  [1,  'Оружие (A Weapon)', ''],
  [2,  'Инструмент (A Tool)', ''],
  [3,  'Предмет одежды (A Piece of Clothing)', ''],
  [4,  'Фотография (A Photo)', ''],
  [5,  'Дневник (A Diary)', ''],
  [6,  'Письмо (A Letter)', ''],
  [7,  'Украшение (A Piece of Jewelry)', ''],
  [8,  'Игрушка (A Toy)', ''],
  [9,  'Книга (A Book)', ''],
  [10, 'Транспорт (A Vehicle)', ''],
];

const LP_LIFE_EVENTS = [
  [1,  'Едва не погиб', 'Ты пережил что-то смертельное — пуля прошла в миллиметре, падение с высоты, отказ хрома.'],
  [2,  'Большая любовь', 'Ты влюбился — и, возможно, до сих пор страдаешь от этого.'],
  [3,  'Удачная находка', 'Ты нашёл или украл что-то ценное — информацию, предмет, деньги.'],
  [4,  'Новый друг', 'Кто-то вошёл в твою жизнь и остался.'],
  [5,  'Новый враг', 'Ты перешёл дорогу опасным людям. Или они — тебе.'],
  [6,  'Психологическая травма', 'Ты пережил насилие, потерю или предательство, которое оставило шрам на психике.'],
  [7,  'Наставник', 'Кто-то опытный взял тебя под крыло и научил выживать.'],
  [8,  'Криминальное дело', 'Ты участвовал в ограблении, перестрелке или другом опасном деле.'],
  [9,  'Потеря близкого', 'Кто-то, кого ты любил, умер или исчез.'],
  [10, 'Смена идентичности', 'Ты начал жизнь с чистого листа — новое имя, новая внешность, новая роль.'],
];

const LP_ROLE = {
  Rockerboy:  ['Твой первый концерт / выступление', [
    [1,'Подпольный клуб в Боевой Зоне — тебя чуть не застрелили на сцене'],
    [2,'Корпоративная вечеринка — ты выступал перед богатыми ублюдками'],
    [3,'Уличный фестиваль — тебя услышали и позвали на запись'],
    [4,'Похороны друга — ты пел, все плакали'],
    [5,'ТВ-шоу — пять минут славы, которые едва не убили твою карьеру'],
    [6,'Тюремный концерт — для сокамерников и охраны'],
    [7,'Запись в подвале — демка, разошедшаяся по Сети'],
    [8,'Прямой эфир взлома — ты спел, пока нетраннеры отвлекали корпов'],
    [9,'Бар в Даунтауне — ты играл за еду и ночлег'],
    [10,'Свадьба номадов — трёхдневный джем в движущемся караване'],
  ]],
  Solo: ['Твой первый урок / кто тебя тренировал', [
    [1,'Отставной военный — бывший майор корпоративной армии'],
    [2,'Уличный ветеран — старый соло из Боевой Зоны'],
    [3,'Отец / мать — которые научили тебя держать ствол'],
    [4,'Банда — ты прошёл обряд посвящения с боем'],
    [5,'Спецшкола — корпоративная академия для будущих убийц'],
    [6,'Тренировочный полигон армии НСША — ты дезертир'],
    [7,'Монастырь боевых искусств — дзен и сталь'],
    [8,'Самоучка — метод проб и ошибок, ошибок было много'],
    [9,'Наставник-киборг — полчеловека, полмашины'],
    [10,'Голодиски с тренировками — и никакой морали'],
  ]],
  Netrunner: ['Как ты получил свой первый дек / взломал первую сеть', [
    [1,'Нашёл сломанный дек в мусоре — починил и вломился в сеть школы'],
    [2,'Украл у корпората — и сразу заработал срок в розыске'],
    [3,'Купил на улице за копейки — продавец не знал, что продаёт'],
    [4,'Подарок от друга-нетраннера — тот погиб в Сети через неделю'],
    [5,'Выиграл в карты / в кибер-бойне'],
    [6,'Наследство от старого нетраннера, который «ушёл в Сеть»'],
    [7,'Собрал сам из запчастей — работало через раз, но работало'],
    [8,'Получил в корпоративной школе — за успехи в программировании'],
    [9,'Военная разработка — ты тестировщик боевых программ'],
    [10,'Заказ на взлом — первый заказ, который определил твою карьеру'],
  ]],
  Tech: ['Что ты починил / создал впервые', [
    [1,'Свой первый хром — перепаял сломанный нейропорт'],
    [2,'Тостер, который взорвал кухню — но ты понял, КАК он работает'],
    [3,'Дрон-курьер — он прожил целых три дня до аварии'],
    [4,'Кибердек — да, ты собрал дек с нуля'],
    [5,'Оружие — самодельный пистолет из водопроводных труб'],
    [6,'Броню — перешил кевларовый жилет под себя'],
    [7,'Музыкальный синтезатор — для рокербоя из соседнего района'],
    [8,'Генератор — в Мегабашне вечно отключают свет'],
    [9,'Экзоскелет — строительный, но на него поставили пушку'],
    [10,'Медицинский сканер — ты думал, это спасёт жизни. Ошибался.'],
  ]],
  Medtech: ['Твой первый пациент / операция', [
    [1,'Уличная драка — друг с ножом в боку, ты ковырялся в ране на коленке'],
    [2,'Передозировка — ты откачал наркомана в переулке'],
    [3,'Роды — ты принимал роды прямо в такси'],
    [4,'Киберпсихоз — пришлось отключать хром живьём'],
    [5,'Падение с высоты — ты собирал по частям тело с тротуара'],
    [6,'Ожоги — ты лечил ребёнка, который выбежал из горящего здания'],
    [7,'Огнестрел — первое пулевое ранение, ты перевязывал себя сам'],
    [8,'Ампутация — срочно, на кухонном столе, без наркоза'],
    [9,'Эпидемия — ты работал во время вспышки неизвестного вируса'],
    [10,'Легальная практика — ты работал в клинике, пока корпы не закрыли её'],
  ]],
  Media: ['Твой первый материал / репортаж', [
    [1,'Блог — ты написал пост, который собрал миллион просмотров'],
    [2,'Стрим перестрелки — ты оказался в нужном месте в нужное время'],
    [3,'Интервью с сенсеем — ты поговорил с культовым эджраннером'],
    [4,'Расследование — ты раскрыл коррупцию в местном участке'],
    [5,'Фото — снимок, который напечатали на первой полосе'],
    [6,'Подкаст — твои истории услышали тысячи людей'],
    [7,'Провокация — ты написал фейк, который взорвал инфополе'],
    [8,'Военкор — ты снимал бой из окопа'],
    [9,'Рецензия — твой обзор хрома разошёлся на цитаты'],
    [10,'Заказной материал — корпы заплатили, ты написал, что надо'],
  ]],
  Exec: ['В какой корпорации ты начинал и почему ушёл', [
    [1,'Kang Tao — конкуренты предложили больше'],
    [2,'Arasaka — ты был пешкой в большой игре и сбежал'],
    [3,'Militech — тебя подставили и уволили с волчьим билетом'],
    [4,'Biotechnica — ты узнал слишком много о генной инженерии'],
    [5,'Xzotto — лотерейная корпорация, ты понял, что это лохотрон'],
    [6,'CitiNet — бюрократия сожрала твою душу'],
    [7,'Zetatech — отдел кибербезопасности, ты взламывал их же системы'],
    [8,'Trauma Team — ты ушёл, потому что не вывозил видеть смерти'],
    [9,'Orion Security — частная армия, ты был связным'],
    [10,'Независимый консультант — ты никогда не работал на корпов. Пока что.'],
  ]],
  Lawman: ['Кто был твоим первым напарником', [
    [1,'Ветеран — старый законник, который научил тебя выживать на улицах'],
    [2,'Молодой идеалист — ты учил его, а он погиб в первой перестрелке'],
    [3,'Коррумпированный коп — ты долго не замечал, а потом всё вскрылось'],
    [4,'Инсайдер — твой напарник был агентом корпорации'],
    [5,'Женщина-коп — ты влюбился, и это чуть не убило вас обоих'],
    [6,'Робот-напарник — дрон-компаньон, который стал другом'],
    [7,'Соло под прикрытием — эджраннер, который на самом деле работал на вас'],
    [8,'Лучший друг детства — вы пошли в полицию вместе'],
    [9,'Служебная собака — K9, верный друг, который спас тебе жизнь'],
    [10,'Без напарника — ты всегда работал один, так проще'],
  ]],
  Fixer: ['Твоя первая сделка', [
    [1,'Оружие — продал ствол уличному гангеру, который застрелил копа'],
    [2,'Информация — продал данные, которые привели к смерти человека'],
    [3,'Хром — впарил бракованный нейропорт доверчивому клиенту'],
    [4,'Наркотики — мелкий дилер, ты подсадил на иглу десяток школьников'],
    [5,'Услуги — нашёл соло для опасного заказа, тот не вернулся'],
    [6,'Броня — сбывал списанные армейские бронежилеты'],
    [7,'Контрабанда — перевёз груз через блокпосты'],
    [8,'Искусство — продал украденную картину коллекционеру'],
    [9,'Живой товар — ты помог людям бежать из города нелегально'],
    [10,'Легальный бизнес — ты начал с мелкой лавки и торговал хламом'],
  ]],
  Nomad: ['Из какого ты клана / каравана', [
   [1,'Клан «Металлические Псы» — перевозчики оружия по пустошам'],
    [2,'Семья «Шоссейные Призраки» — контрабандисты, знающие все маршруты'],
    [3,'Братство «Ветряные Крылья» — AV-пилоты и дальнобойщики'],
    [4,'Караван «Соляные Псы» — торговцы водой и припасами'],
    [5,'Клан «Разбитые Шины» — байкеры, живущие на скорости'],
    [6,'Семья «Тихие Волны» — моряки и речники'],
    [7,'Караван «Огненные Колёса» — пиротехники и каскадёры'],
    [8,'Клан «Стальные Когти» — охотники за головами в пустошах'],
    [9,'Одиночка — ты сам по себе, клан погиб или ты его покинул'],
    [10,'Корпоративный транспортный отдел — ты бывший водитель корпов'],
  ]],
};

/* ===================== мастер: состояние и рендер ===================== */

function initWizard() {
  state.wizard = {
    step: 1,
    role: 'Solo',
    handle: '',
    roleDesc: '',
    roleAbility: '',
    stats: { INT: 6, REF: 6, DEX: 6, TECH: 6, COOL: 6, WILL: 6, LUCK: 6, MOVE: 6, BODY: 6, EMP: 6 },
    hpCur: null,
    humCur: null,
   skills: {},
    cyberware: [],
    gear: [],     fashion: [],
    chromeCost: 0, gearCost: 0, fashionCost: 0,
    lifepath: {},   created: false,
 };
}

function wizChar() {
  const w = state.wizard;
  return {
   handle: w.handle || 'Безымянный-07',
    role: w.role,       role_rank: 4,
    stats: Object.assign({}, w.stats),
    hp_cur: w.hpCur,   humanity_cur: w.humCur,
    skills: Object.assign({}, w.skills),
   cyberware: w.cyberware.map(c => ({key: c.id, name: c.name, hl: c.hl || 0, price: c.price, type: c.type || ''})),
    inventory: [...w.gear.map(i => ({...i})), ...w.fashion.map(i => ({...i}))],
    armor: {},  cash: Math.max(0, (2550 - w.chromeCost - w.gearCost) + (800 - w.fashionCost)),
    appearance: '', background: '', notes: '', languages: 'Streetslang (родной, 4)', player: '',
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

function renderWizard() {
  const wiz = state.wizard;
  const view = $('#view');
  const d = wizDerived();
  const stepEmojis = ['🎭','🧬','📊','🎯','🦾','🛒','✅'];
  const totalGearBudget = 2550;
  const totalFashionBudget = 800;
  const spentGear = wiz.chromeCost + wiz.gearCost;
  const remainingGear = totalGearBudget - spentGear;
  const remainingFashion = totalFashionBudget - wiz.fashionCost;

  view.innerHTML = `
  <div class="wizard-wrap">
    <div class="wizard-nav">
      ${WIZARD_STEPS.map((s, i) => `
        <button class="wiz-step ${i+1 === wiz.step ? 'active' : ''} ${i+1 < wiz.step ? 'done' : ''}"
                onclick="wizGoTo(${i+1})" ${i+1 > wiz.step ? 'disabled' : ''}>
          <span class="wiz-num">${stepEmojis[i]}</span>
          <span class="wiz-label">${s[1]}</span>
        </button>`).join('')}
    </div>

    <div class="wiz-live" id="wiz-live">
      <div class="derived">
        <span class="dstat"><span class="v">${d.hp_max || '—'}</span><span class="k">HP макс</span></span>
        <span class="dstat"><span class="v">${d.seriously_wounded != null ? '≤ '+d.seriously_wounded : '—'}</span><span class="k">Серьёзная рана</span></span>
        <span class="dstat"><span class="v">${d.humanity_max != null ? d.humanity_cur+'/'+d.humanity_max : '—'}</span><span class="k">Человечность</span></span>
        <span class="dstat ${d.emp_cur != null && d.emp_cur <= 2 ? 'warn' : ''}"><span class="v">${d.emp_cur != null ? d.emp_cur : '—'}</span><span class="k">EMP</span></span>
        <span class="dstat"><span class="v">${nf.format(remainingGear)}€$</span><span class="k">Бюджет снаряжения</span></span>
        <span class="dstat"><span class="v">${nf.format(remainingFashion)}€$</span><span class="k">Бюджет стиля</span></span>
      </div>
    </div>

    <div class="wiz-body" id="wiz-body">
      ${renderWizStep()}
    </div>

    <div class="wiz-footer">
      <div class="row" style="justify-content:space-between">
        <div>
          <button class="btn-sm" onclick="wizGoTo(1)">⟳ Начать заново</button>
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

  // bind navigation
  const nxt = $('#wiz-next');
  if (nxt) nxt.onclick = wizNext;
  const prv = $('#wiz-prev');
  if (prv) prv.onclick = wizPrev;
  const crt = $('#wiz-create');
  if (crt) crt.onclick = wizCreate;
  const fullEd = $('#wiz-full-editor');
  if (fullEd) fullEd.onclick = () => { state.wizard = null; viewEditor('new'); };

  // bind step-specific handlers
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
  const wiz = state.wizard;
  switch (step) {
    case 1: return wizStepRoleHtml();
    case 2: return wizStepLifepathHtml();
    case 3: return wizStepStatsHtml();
    case 4: return wizStepSkillsHtml();
    case 5: return wizStepChromeHtml();
    case 6: return wizStepShoppingHtml();
    case 7: return wizStepSummaryHtml();
    default: return '';
  }
}

/* ---------- Step 1: Role ---------- */

function wizStepRoleHtml() {
  const wiz = state.wizard;
  return `
    <div class="mb"><label class="f" style="margin:0"><span>Псевдоним (Handle) — как тебя знают на улицах</span>
      <input id="wiz-handle" maxlength="60" value="${esc(wiz.handle)}" placeholder="Выхлоп, Neon, Slim…" style="max-width:400px"></label></div>
    <div class="role-grid">
      ${Object.keys(state.meta.roles).map(r => {
        const ab = state.meta.roles[r];
        const ru = state.meta.role_ru[r];
        const desc = state.meta.role_desc[r];
        return `<div class="role-card ${wiz.role === r ? 'selected' : ''}" data-role="${r}" style="cursor:pointer">
          <h3>${esc(r)} <span class="chip role">${esc(ru || '')}</span></h3>
          <div class="small muted">${esc(desc || '')}</div>
          <div class="tag mb mt" style="display:inline-block;color:var(--yellow);border-color:rgba(255,213,0,.4)">${esc(ab)}</div>
        </div>`;
      }).join('')}
    </div>`;
}

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
    const lp = wiz.lifepath;
    $$('[data-lp-roll]', body).forEach(btn => btn.onclick = () => {
      const cat = btn.dataset.lpRoll;
      wizRollLifepath(cat);
      renderWizard();
    });
    $$('[data-lp-role-roll]', body).forEach(btn => btn.onclick = () => {
      const r = wiz.role;
      const table = LP_ROLE[r];
      if (!table) return;
      const roll = 1 + Math.floor(Math.random() * 10);
      const row = table[1].find(x => x[0] === roll);
      wiz.lifepath.role_roll = roll;
      wiz.lifepath.role_result = row ? row[1] : '';
      renderWizard();
    });
    if (!lp._rolled) {
      // auto-roll first time
      ['childhood', 'family', 'person', 'possession'].forEach(k => wizRollLifepath(k));
      wiz.lifepath.events = [];
      for (let i = 0; i < 3; i++) wizRollLifepath('events');
      lp._rolled = true;
    }
  }

  if (step === 3) {
    $$('[data-wiz-stat]', body).forEach(inp => inp.oninput = () => {
      const s = inp.dataset.wizStat;
      const v = Math.max(2, Math.min(8, num(inp.value) || 2));
      wiz.stats[s] = v;
      inp.value = v;
      updateWizStatBar();
    });
    $('#wiz-st-roll').onclick = () => {
      const arr = [8,7,7,6,6,6,6,6,5,5];
      for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; }
      state.meta.stats.forEach((s, i) => wiz.stats[s] = arr[i]);
      renderWizard();
    };
    $('#wiz-st-reset').onclick = () => { state.meta.stats.forEach(s => wiz.stats[s] = 6); renderWizard(); };
    updateWizStatBar();
  }

  if (step === 4) {
    const spent = wizSkillSpent();
    updateWizSkillHud(spent);
    $$('[data-wiz-skill]', body).forEach(sel => sel.onchange = () => {
      const name = sel.dataset.wizSkill;
      wiz.skills[name] = Number(sel.value);
      const sp = wizSkillSpent();
      updateWizSkillHud(sp);
      wizRefreshLive();
    });
  }

  if (step === 5) {
    const searchBtn = $('#wiz-chrome-search');
    const qInp = $('#wiz-chrome-q');
    if (searchBtn) searchBtn.onclick = () => wizLoadChromeItems(qInp ? qInp.value : '');
    if (qInp) qInp.onkeydown = (e) => { if (e.key === 'Enter') wizLoadChromeItems(qInp.value); };
    $$('[data-chrome-del]', body).forEach(btn => btn.onclick = () => {
      const idx = Number(btn.dataset.chromeDel);
      const item = wiz.cyberware[idx];
      if (item) wiz.chromeCost = Math.max(0, wiz.chromeCost - (item.price || 0));
      wiz.cyberware.splice(idx, 1);
      renderWizard();
    });
  }

  if (step === 6) {
    const qGear = $('#wiz-shop-gear-q');
    const sGear = $('#wiz-shop-gear-btn');
    if (sGear) sGear.onclick = () => wizLoadShopItems('gear', qGear ? qGear.value : '');
    if (qGear) qGear.onkeydown = (e) => { if (e.key === 'Enter') wizLoadShopItems('gear', qGear.value); };

    const qFash = $('#wiz-shop-fashion-q');
    const sFash = $('#wiz-shop-fashion-btn');
    if (sFash) sFash.onclick = () => wizLoadShopItems('fashion', qFash ? qFash.value : '');
    if (qFash) qFash.onkeydown = (e) => { if (e.key === 'Enter') wizLoadShopItems('fashion', qFash.value); };

    $$('[data-shop-del]', body).forEach(btn => btn.onclick = () => {
      const list = btn.dataset.shopDel === 'gear' ? wiz.gear : wiz.fashion;
      const idx = Number(btn.dataset.shopIdx);
      const item = list[idx];
      if (item) {
        if (btn.dataset.shopDel === 'gear') wiz.gearCost = Math.max(0, wiz.gearCost - (item.price || 0) * (item.qty || 1));
        else wiz.fashionCost = Math.max(0, wiz.fashionCost - (item.price || 0) * (item.qty || 1));
      }
      list.splice(idx, 1);
      renderWizard();
    });
  }

  if (step === 7) {
    const hdl2 = $('#wiz-summary-handle');
    if (hdl2) hdl2.oninput = (e) => { wiz.handle = e.target.value; };
  }
}

/* ---------- Step 2: Lifepath ---------- */

function wizRollLifepath(cat) {
  const wiz = state.wizard;
  const roll = 1 + Math.floor(Math.random() * 10);
  if (cat === 'childhood') {
    const row = LP_CHILDHOOD.find(x => x[0] === roll);
    wiz.lifepath.childhood = { roll, title: row ? row[1] : '', desc: row ? row[2] : '' };
  } else if (cat === 'family') {
    const row = LP_FAMILY.find(x => x[0] === roll);
    wiz.lifepath.family = { roll, title: row ? row[1] : '', desc: row ? row[2] : '' };
  } else if (cat === 'person') {
    const row = LP_MOST_VALUED_PERSON.find(x => x[0] === roll);
    wiz.lifepath.person = { roll, title: row ? row[1] : '', desc: row ? row[2] : '' };
  } else if (cat === 'possession') {
    const row = LP_MOST_VALUED_POSSESSION.find(x => x[0] === roll);
    wiz.lifepath.possession = { roll, title: row ? row[1] : '', desc: row ? row[2] : '' };
  } else if (cat === 'events') {
    const row = LP_LIFE_EVENTS.find(x => x[0] === roll);
    const evt = { roll, title: row ? row[1] : '', desc: row ? row[2] : '' };
    if (!wiz.lifepath.events) wiz.lifepath.events = [];
    wiz.lifepath.events.push(evt);
  }
}

function wizStepLifepathHtml() {
  const wiz = state.wizard;
  const lp = wiz.lifepath;

  const lpSection = (label, key, table) => {
    const val = lp[key];
    const roller = `<button class="btn-sm" data-lp-roll="${key}">🎲 Бросить 1d10</button>`;
    return `<div class="lp-item">
      <div class="lp-label">${label}</div>
      ${val ? `<div class="lp-result"><span class="dice-face">${val.roll}</span> <b>${esc(val.title)}</b>${val.desc ? '<div class="small muted">'+esc(val.desc)+'</div>' : ''}</div>` : '<div class="muted small">— не брошено —</div>'}
      <div class="lp-actions">${roller}</div>
    </div>`;
  };

  const roleLp = LP_ROLE[wiz.role];
  const roleVal = lp.role_roll ? { roll: lp.role_roll, title: lp.role_result } : null;

  return `
    <div class="lp-grid">
      ${lpSection('Детство (Childhood Environment)', 'childhood', LP_CHILDHOOD)}
      ${lpSection('Семья (Family Background)', 'family', LP_FAMILY)}
      ${lpSection('Самый важный человек (Most Valued Person)', 'person', LP_MOST_VALUED_PERSON)}
      ${lpSection('Самая ценная вещь (Most Valued Possession)', 'possession', LP_MOST_VALUED_POSSESSION)}
      <div class="lp-item">
        <div class="lp-label">События жизни (Life Events) — 3 броска</div>
        <div class="lp-events">
          ${(lp.events || []).map(e => `<span class="chip"><b>${e.roll}</b> ${esc(e.title)}</span>`).join('') || '<span class="muted small">—</span>'}
        </div>
        <div class="lp-actions"><button class="btn-sm" data-lp-roll="events">🎲 + Событие</button></div>
      </div>
      ${roleLp ? `<div class="lp-item">
        <div class="lp-label">Ролевой Lifepath: ${esc(roleLp[0])}</div>
        ${roleVal ? `<div class="lp-result"><span class="dice-face">${roleVal.roll}</span> <b>${esc(roleVal.title)}</b></div>` : '<div class="muted small">— не брошено —</div>'}
        <div class="lp-actions"><button class="btn-sm" data-lp-role-roll="1">🎲 Бросить 1d10</button></div>
      </div>` : ''}
    </div>`;
}

/* ---------- Step 3: Stats ---------- */

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
      <span class="muted small">Потрачено: <b id="wiz-st-spent" class="${spent > budget ? 'warn-text' : ''}">${spent}</b> / <b>${budget}</b> очков (каждая стата 2–8)</span>
      <div class="row">
        <button class="btn-sm" id="wiz-st-roll">🎲 Случайно</button>
        <button class="btn-sm" id="wiz-st-reset">Сброс на 6</button>
      </div>
    </div>
    <div class="statgrid">
      ${state.meta.stats.map(s => {
        const v = num(wiz.stats[s]);
        const bad = v < 2 || v > 8;
        return `<div class="stat input${bad ? ' bad' : ''}">
          <span class="k">${s}</span>
          <input type="number" min="2" max="8" data-wiz-stat="${s}" value="${v != null ? v : 6}">
        </div>`;
      }).join('')}
    </div>
    <div class="small muted mt">HP = 10 + 5×⌈(BODY+WILL)/2⌉ · Человечность макс = EMP×10</div>`;
}

/* ---------- Step 4: Skills ---------- */

function wizSkillSpent() {
  const wiz = state.wizard;
  const dblCost = Object.fromEntries(state.meta.skills.map(s => [s[1], !!s[3]]));
  let total = 0;
  for (const [name, lvl] of Object.entries(wiz.skills)) {
    total += (lvl || 0) * (dblCost[name] ? 2 : 1);
  }
  return total;
}

function updateWizSkillHud(spent) {
  const budget = state.meta.skill_points || 86;
  const el = $('#wiz-sk-spent');
  if (el) {
    el.textContent = spent;
    el.classList.toggle('warn-text', spent > budget);
  }
  const maxLvl = state.meta.skill_max || 6;
  $$('.wiz-must-chip').forEach(chip => {
    const ok = (state.wizard.skills[chip.dataset.must] || 0) >= 2;
    chip.classList.toggle('ok', ok);
    chip.classList.toggle('bad', !ok);
    chip.textContent = (ok ? '✓ ' : '✗ ') + chip.dataset.must;
  });
}

function wizStepSkillsHtml() {
  const wiz = state.wizard;
  const skills = state.meta.skills;
  const dblCost = Object.fromEntries(skills.map(s => [s[1], !!s[3]]));
  const must = new Set(state.meta.must_skills || []);
  const budget = state.meta.skill_points || 86;
  const maxLvl = state.meta.skill_max || 6;
  const spent = wizSkillSpent();

  // Обязательные минимумы
  let mustChips = (state.meta.must_skills || []).map(s => {
    const ok = (wiz.skills[s] || 0) >= 2;
    return `<span class="wiz-must-chip chip ${ok ? 'ok' : 'bad'}" data-must="${esc(s)}">${ok ? '✓' : '✗'} ${esc(s)}</span>`;
  }).join('');

  // Для навыков, которые ещё не установлены, ставим обязательные минимумы по умолчанию
  if (!wiz._skillsInit) {
    for (const s of (state.meta.must_skills || [])) {
      if (!wiz.skills[s] || wiz.skills[s] < 2) wiz.skills[s] = 2;
    }
    // родной язык — 4 бесплатно
    if (!wiz.skills['Language']) wiz.skills['Language'] = 4;
    wiz._skillsInit = true;
  }

  let lastCat = null;
  const rows = skills.map(([cat, name, stat, is2]) => {
    const head = cat !== lastCat ? `<div class="skill-cat">${esc(cat)}</div>` : '';
    lastCat = cat;
    const lvl = wiz.skills[name] || 0;
    const isMust = must.has(name);
    const isLang = name === 'Language';
    const free4 = isLang && lvl >= 4;
    return head + `<div class="skill-row">
      <span class="sname">${isMust ? '<span class="must-tag" title="Обязательный минимум: 2 очка">★</span>' : ''}${esc(name)}${is2 ? ' <span class="muted small">(×2)</span>' : ''}${free4 ? ' <span class="muted small">· 4 б/пл</span>' : ''}</span>
      <span class="sstat">${stat}</span>
      <select data-wiz-skill="${esc(name)}" class="${lvl > maxLvl ? 'over-max' : ''}">
        ${[0,1,2,3,4,5,6,7,8,9,10].map(r => `<option value="${r}" ${lvl === r ? 'selected' : ''}>${r === 0 ? '—' : r}</option>`).join('')}
      </select>
    </div>`;
  }).join('');

  const roleAbility = state.meta.roles[wiz.role] || '';
  return `
    <div class="row mb" style="justify-content:space-between;align-items:center">
      <span class="muted small">Потрачено: <b id="wiz-sk-spent" class="${spent > budget ? 'warn-text' : ''}">${spent}</b> / <b>${budget}</b> очков. Макс. в навыке: <b>${maxLvl}</b></span>
    </div>
    <div class="muted small mb">Обязательные минимумы (по 2 очка, итого 26):</div>
    <div class="must-list mb">${mustChips}</div>
    <div class="skill-row" style="border-bottom:1px solid var(--line)">
      <span class="sname"><b>${esc(roleAbility || '—')}</b> <span class="tag role">способность роли · ${esc(wiz.role)} · старт — 4</span></span>
      <span class="sstat"></span>
      <select disabled><option>4</option></select>
    </div>
    <div class="skill-list">${rows}</div>
    <div class="small muted mt">×2-навыки стоят 2 очка за уровень. Родной язык — уровень 4 бесплатно.</div>`;
}

/* ---------- Step 5: Chrome ---------- */

async function wizLoadChromeItems(q) {
  const box = $('#wiz-chrome-results');
  if (!box) return;
  box.innerHTML = spinner();
  const p = new URLSearchParams({ q, cat: 'cyberware', limit: 40 });
  const data = await api('/api/items?' + p);
  const wiz = state.wizard;
  const remainingGear = 2550 - wiz.chromeCost - wiz.gearCost;
  box.innerHTML = data.items.length
    ? data.items.map(it => `
        <div class="inv-row" style="cursor:pointer;${it.price > remainingGear ? 'opacity:.5' : ''}" data-chrome-add="${it.id}">
          <span class="iname">${esc(it.name)}</span>
          <span class="hl-badge">HL ${it.hl || 0}</span>
          <span class="chip">${esc((it.fields && it.fields.Type) || 'хром')}</span>
          <span class="${it.price > remainingGear ? 'muted' : 'price'}">${money(it.price)}</span>
          ${it.price > remainingGear ? '<span class="tag" style="color:var(--red)">нет бюджета</span>' : ''}
        </div>`).join('')
    : '<div class="empty">Ничего не нашлось в категории «Кибернетика».</div>';
  $$('[data-chrome-add]', box).forEach(row => row.onclick = () => {
    const id = row.dataset.chromeAdd;
    const it = data.items.find(x => x.id === id);
    if (!it) return;
    const price = it.price || 0;
    if (wiz.chromeCost + wiz.gearCost + price > 2550) { toast('Не хватает бюджета снаряжения', true); return; }
    wiz.cyberware.push({ id: it.id, name: it.name, hl: it.hl || 0, price, type: (it.fields && it.fields.Type) || '' });
    wiz.chromeCost += price;
    renderWizard();
    toast('Добавлен: ' + it.name);
  });
}

function wizStepChromeHtml() {
  const wiz = state.wizard;
  const remainingGear = 2550 - wiz.chromeCost - wiz.gearCost;
  const totalHl = wiz.cyberware.reduce((a, c) => a + (c.hl || 0), 0);
  return `
    <div class="row mb" style="justify-content:space-between">
      <span class="muted small">Установлено: <b>${wiz.cyberware.length}</b> имплантов · HL: <b class="hl-badge">${totalHl}</b> · Потрачено: <b>${money(wiz.chromeCost)}</b></span>
      <span class="muted small">Остаток бюджета: <b>${money(remainingGear)}</b></span>
    </div>
    <div class="searchbar"><input id="wiz-chrome-q" placeholder="Поиск хрома…"><button id="wiz-chrome-search">Найти</button></div>
    <div id="wiz-chrome-results">${spinner()}</div>
    <div class="mt"><h3>📋 Выбранный хром</h3></div>
    <div id="wiz-chrome-list">
      ${wiz.cyberware.length ? wiz.cyberware.map((c, i) => `
        <div class="inv-row"><span class="iname">${esc(c.name)}</span>
          <span class="hl-badge">HL ${c.hl || 0}</span>
          <span class="chip">${esc(c.type || 'хром')}</span>
          <span class="price">${money(c.price)}</span>
          <button class="btn-sm btn-danger" data-chrome-del="${i}">✕</button>
        </div>`).join('') : '<div class="empty">Пока не вживил ни одного импланта.</div>'}
    </div>
    <div class="small muted mt">Каждый имплант (кроме Fashionware) режет максимум человечности на 2, Borgware — на 4. HL вычитается из человечности напрямую.</div>`;
}

/* ---------- Step 6: Shopping ---------- */

async function wizLoadShopItems(type, q) {
  const boxId = type === 'gear' ? 'wiz-shop-gear-results' : 'wiz-shop-fashion-results';
  const box = $(`#${boxId}`);
  if (!box) return;
  box.innerHTML = spinner();
  const cat = type === 'fashion' ? 'fashion' : ''; // gear = all non-fashion, fashion restricted
  const p = new URLSearchParams({ q, limit: 40 });
  if (cat) p.set('cat', cat);
  const data = await api('/api/items?' + p);
  const wiz = state.wizard;
  let items = data.items;
  if (!cat) items = items.filter(i => i.cat !== 'fashion' && i.price != null);
  const remaining = type === 'gear'
    ? (2550 - wiz.chromeCost - wiz.gearCost)
    : (800 - wiz.fashionCost);

  box.innerHTML = items.length
    ? items.map(it => `
        <div class="inv-row" style="cursor:pointer;${it.price > remaining ? 'opacity:.5' : ''}" data-shop-add="${type}|${it.id}">
          <span class="iname">${esc(it.name)}</span>
          ${it.damage ? `<span class="weap-dmg">${esc(it.damage)}</span>` : ''}
          ${it.hl ? `<span class="hl-badge">HL ${it.hl}</span>` : ''}
          <span class="${it.price > remaining ? 'muted' : 'price'}">${money(it.price)}</span>
          ${it.price > remaining ? '<span class="tag" style="color:var(--red)">не хватает</span>' : ''}
        </div>`).join('')
    : '<div class="empty">Ничего не нашлось.</div>';

  $$('[data-shop-add]', box).forEach(row => {
    row.onclick = () => {
      const [t, id] = row.dataset.shopAdd.split('|');
      const it = data.items.find(x => x.id === id);
      if (!it) return;
      const price = it.price || 0;
      let list, costField, maxBudget;
      if (t === 'gear') {
        list = wiz.gear;
        costField = 'gearCost';
        maxBudget = 2550 - wiz.chromeCost;
      } else {
        list = wiz.fashion;
        costField = 'fashionCost';
        maxBudget = 800;
      }
      if (wiz[costField] + price > maxBudget) { toast('Не хватает бюджета', true); return; }
      const ex = list.find(x => x.key === it.id);
      if (ex) { ex.qty = (ex.qty || 1) + 1; wiz[costField] += price; }
      else {
        list.push({ key: it.id, cat: it.cat, name: it.name, price, qty: 1 });
        wiz[costField] += price;
      }
      renderWizard();
      toast('Добавлено: ' + it.name);
    };
  });
}

function wizStepShoppingHtml() {
  const wiz = state.wizard;
  const remainingGear = 2550 - wiz.chromeCost - wiz.gearCost;
  const remainingFashion = 800 - wiz.fashionCost;

  const listHtml = (list, type) => list.length
    ? list.map((item, i) => `
        <div class="inv-row"><span class="iname">${esc(item.name)} ×${item.qty || 1}</span>
          <span class="price">${money((item.price || 0) * (item.qty || 1))}</span>
          <button class="btn-sm btn-danger" data-shop-del="${type}" data-shop-idx="${i}">✕</button>
        </div>`).join('')
    : '<div class="empty small">Пусто</div>';

  return `
    <div class="grid cols-2" style="grid-template-columns:1fr 1fr;gap:18px">
      <div class="panel">
        <h3>🎒 Снаряжение (2550€$)</h3>
        <div class="muted small mb">Потрачено: <b>${money(wiz.chromeCost + wiz.gearCost)}</b> · Осталось: <b class="${remainingGear < 0 ? 'warn-text' : ''}">${money(remainingGear)}</b></div>
        <div class="searchbar mb" style="margin-bottom:8px">
          <input id="wiz-shop-gear-q" placeholder="Оружие, броня, снаряжение…">
          <button class="btn-sm" id="wiz-shop-gear-btn">Найти</button>
        </div>
        <div id="wiz-shop-gear-results" style="max-height:200px;overflow:auto">— поищи что-нибудь —</div>
        <h4 class="mt">📋 Корзина</h4>
        <div id="wiz-shop-gear-list">${listHtml(wiz.gear, 'gear')}</div>
      </div>
      <div class="panel">
        <h3>🧥 Стиль (800€$)</h3>
        <div class="muted small mb">Потрачено: <b>${money(wiz.fashionCost)}</b> · Осталось: <b class="${remainingFashion < 0 ? 'warn-text' : ''}">${money(remainingFashion)}</b></div>
        <div class="searchbar mb" style="margin-bottom:8px">
          <input id="wiz-shop-fashion-q" placeholder="Fashion, Fashionware…">
          <button class="btn-sm" id="wiz-shop-fashion-btn">Найти</button>
        </div>
        <div id="wiz-shop-fashion-results" style="max-height:200px;overflow:auto">— поищи что-нибудь —</div>
        <h4 class="mt">📋 Корзина</h4>
        <div id="wiz-shop-fashion-list">${listHtml(wiz.fashion, 'fashion')}</div>
      </div>
    </div>
    <div class="small muted mt">Хром уже занял ${money(wiz.chromeCost)} из бюджета снаряжения.</div>`;
}

/* ---------- Step 7: Summary ---------- */

function wizStepSummaryHtml() {
  const wiz = state.wizard;
  const d = wizDerived();
  const warnings = [];

  // Проверки
  const statSpent = wizStatSpent();
  const budgetStats = state.meta.stat_points || 62;
  if (statSpent > budgetStats) warnings.push('⚠️ Перерасход характеристик: ' + statSpent + '/' + budgetStats);
  if (statSpent < budgetStats) warnings.push(`💡 Неиспользовано ${budgetStats - statSpent} очков характеристик`);

  const skillSpent = wizSkillSpent();
  const budgetSkills = state.meta.skill_points || 86;
  if (skillSpent > budgetSkills) warnings.push('⚠️ Перерасход навыков: ' + skillSpent + '/' + budgetSkills);
  if (skillSpent < budgetSkills) warnings.push(`💡 Неиспользовано ${budgetSkills - skillSpent} очков навыков`);

  for (const s of (state.meta.must_skills || [])) {
    if ((wiz.skills[s] || 0) < 2) warnings.push(`⚠️ Обязательный минимум не выполнен: ${s} (нужен 2)`);
  }

  const maxLvl = state.meta.skill_max || 6;
  for (const [name, lvl] of Object.entries(wiz.skills)) {
    if (lvl > maxLvl) warnings.push(`⚠️ Навык ${name} превышает максимум создания (${maxLvl})`);
  }

  if (d.emp_cur != null && d.emp_cur <= 2) warnings.push('⚠️ EMP ≤ 2 — вы на грани киберпсихоза');
  if (d.humanity_max != null && d.humanity_max < 0) warnings.push('⚠️ Отрицательная человечность — киберпсихоз');

  const totalCash = Math.max(0, (2550 - wiz.chromeCost - wiz.gearCost) + (800 - wiz.fashionCost));
  if (!wiz.handle || !wiz.handle.trim()) warnings.push('⚠️ Заполни псевдоним (Handle)');

  const statBlock = state.meta.stats.map(s => `<span class="chip"><b>${s}</b> ${wiz.stats[s] != null ? wiz.stats[s] : '—'}</span>`).join('');

  return `
    <div class="grid cols-2" style="gap:18px">
      <div class="panel">
        <h3>🧬 ${esc(wiz.handle || 'Безымянный')}</h3>
        <div class="chips mb">
          <span class="tag role">${esc(wiz.role)} · 4</span>
          <span class="tag price">${money(totalCash)}</span>
          <span class="chip">HP ${d.hp_max || '—'}</span>
          <span class="chip">HUM ${d.humanity_cur != null ? d.humanity_cur+'/'+d.humanity_max : '—'}</span>
          <span class="chip">EMP ${d.emp_cur != null ? d.emp_cur : '—'}</span>
        </div>
        <div class="statgrid mb">${statBlock}</div>
        <div class="derived mb">
          <span class="dstat"><span class="v">${d.sp_body || '—'}</span><span class="k">SP тело</span></span>
          <span class="dstat"><span class="v">${d.sp_head || '—'}</span><span class="k">SP голова</span></span>
          <span class="dstat"><span class="v">${d.death_save || '—'}</span><span class="k">Death Save</span></span>
        </div>
        ${wiz.cyberware.length ? `<div><b>Хром:</b> ${wiz.cyberware.map(c => esc(c.name)).join(', ')}</div>` : ''}
        ${wiz.gear.length ? `<div class="mt"><b>Снаряжение:</b> ${wiz.gear.map(i => esc(i.name) + ' ×' + (i.qty || 1)).join(', ')}</div>` : ''}
        ${wiz.fashion.length ? `<div class="mt"><b>Стиль:</b> ${wiz.fashion.map(i => esc(i.name) + ' ×' + (i.qty || 1)).join(', ')}</div>` : ''}
      </div>
      <div>
        <label class="f"><span>Псевдоним (Handle) *</span>
          <input id="wiz-summary-handle" maxlength="60" value="${esc(wiz.handle)}" placeholder="Выхлоп, Neon, Slim…"></label>
        <div class="panel" style="margin-top:14px">
          <h3>⚠️ Проверки</h3>
          ${warnings.length ? warnings.map(w => `<div class="small mb">${w}</div>`).join('') : '<div class="green small">✅ Все проверки пройдены! Можно создавать.</div>'}
        </div>
        <div class="small muted mt">Остаток бюджета записывается в cash персонажа (${money(totalCash)}).</div>
      </div>
    </div>`;
}

/* ---------- навигация ---------- */

function wizNext() {
  const wiz = state.wizard;
  // валидация перед переходом
  if (wiz.step === 1 && !wiz.handle.trim()) { toast('Заполни псевдоним (Handle)', true); return; }
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
  const d = wizDerived();
  const wiz = state.wizard;
  const remainingGear = 2550 - wiz.chromeCost - wiz.gearCost;
  const remainingFashion = 800 - wiz.fashionCost;
  box.innerHTML = `<div class="derived">
    <span class="dstat"><span class="v">${d.hp_max || '—'}</span><span class="k">HP макс</span></span>
    <span class="dstat"><span class="v">${d.seriously_wounded != null ? '≤ '+d.seriously_wounded : '—'}</span><span class="k">Серьёзная рана</span></span>
    <span class="dstat"><span class="v">${d.humanity_max != null ? d.humanity_cur+'/'+d.humanity_max : '—'}</span><span class="k">Человечность</span></span>
    <span class="dstat ${d.emp_cur != null && d.emp_cur <= 2 ? 'warn' : ''}"><span class="v">${d.emp_cur != null ? d.emp_cur : '—'}</span><span class="k">EMP</span></span>
    <span class="dstat"><span class="v">${nf.format(remainingGear)}€$</span><span class="k">Бюджет снаряжения</span></span>
    <span class="dstat"><span class="v">${nf.format(remainingFashion)}€$</span><span class="k">Бюджет стиля</span></span>
  </div>`;
}

async function wizCreate() {
  const wiz = state.wizard;
  if (!wiz.handle || !wiz.handle.trim()) { toast('Заполни псевдоним (Handle)', true); return; }

  // проверки
  const statSpent = wizStatSpent();
  const budgetStats = state.meta.stat_points || 62;
  if (statSpent > budgetStats) { toast(`Перерасход характеристик: ${statSpent}/${budgetStats}`, true); return; }

  const skillSpent = wizSkillSpent();
  const budgetSkills = state.meta.skill_points || 86;
  if (skillSpent > budgetSkills) { toast(`Перерасход навыков: ${skillSpent}/${budgetSkills}`, true); return; }

  for (const s of (state.meta.must_skills || [])) {
    if ((wiz.skills[s] || 0) < 2) { toast(`Обязательный навык ${s} должен быть минимум 2`, true); return; }
  }

  const char = wizChar();
  try {
    const result = await api('/api/characters', { method: 'POST', body: { data: char } });
    wiz.created = true;
    toast('Персонаж создан! 🎉');
    location.hash = '#/char/' + result.id;
  } catch (e) {
    toast(e.message, true);
  }
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
    history.replaceState(null, '', '#/char/' + r.id);
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
