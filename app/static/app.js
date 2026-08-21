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
  const d = (Date.now() / 1000 - ts), isRu = typeof APP_I18N !== 'undefined' && APP_I18N.current() === 'ru';
  if (d < 60) return isRu ? 'только что' : 'just now';
  if (d < 3600) return Math.floor(d / 60) + (isRu ? ' мин назад' : ' min ago');
  if (d < 86400) return Math.floor(d / 3600) + (isRu ? ' ч назад' : ' hr ago');
  return new Date(ts * 1000).toLocaleDateString(isRu ? 'ru-RU' : 'en-US', { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
}

function toast(msg, isErr) {
  const root = $('#toast-root');
  const el = document.createElement('div');
  el.className = 'toast' + (isErr ? ' err' : '');
  el.textContent = APP_I18N.translate(msg);
  root.appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .4s'; }, 3200);
  setTimeout(() => el.remove(), 3700);
}

function toastUndo(message, undo) {
  const root=$('#toast-root'),el=document.createElement('div');el.className='toast';el.innerHTML=`<span>${esc(message)}</span> <button class="btn-sm">Undo</button>`;root.appendChild(el);$('button',el).onclick=()=>{undo();el.remove();};setTimeout(()=>el.remove(),7000);
}

let modalSequence = 0;
const MODAL_FOCUSABLE = 'button:not([disabled]),a[href],input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';
const topModal = root => root && root.lastElementChild;

function openModal(html, wide) {
  const root = $('#modal-root');
  const previous = topModal(root);
  const returnFocus = document.activeElement;
  if (previous) {
    previous.hidden = true;
    previous.setAttribute('aria-hidden', 'true');
    previous.setAttribute('aria-modal', 'false');
  }
  root.insertAdjacentHTML('beforeend', `<div class="modal${wide ? ' wide' : ''}" role="dialog" aria-modal="true" tabindex="-1"><button class="close" type="button" aria-label="${T('Close','Закрыть')}" title="${T('Close','Закрыть')}">✕</button>${html}</div>`);
  const modal = topModal(root);
  modal._returnFocus = returnFocus;
  root.classList.add('open');
  root.setAttribute('aria-hidden', 'false');
  APP_I18N.apply(modal);
  $('.close', modal).onclick = () => closeModal();
  root.onmousedown = event => { if (event.target === root) closeModal(); };
  const heading = $('h1,h2,h3', modal);
  if (heading) {
    heading.id = heading.id || `modal-title-${++modalSequence}`;
    modal.setAttribute('aria-labelledby', heading.id);
  } else {
    modal.setAttribute('aria-label', T('Dialog','Диалог'));
  }
  setTimeout(() => {
    if (!modal.isConnected || modal.hidden) return;
    const target = $('[autofocus]', modal) || $('input:not([disabled]),select:not([disabled]),textarea:not([disabled])', modal) || $(MODAL_FOCUSABLE, modal) || modal;
    if (target && target.focus) target.focus();
  }, 0);
  return modal;
}
function closeModal(all = false) {
  const root = $('#modal-root');
  if (!root) return;
  const current = topModal(root);
  if (!current) return;
  const outermost = root.firstElementChild;
  const target = all ? outermost?._returnFocus : current._returnFocus;
  if (all) root.innerHTML = '';
  else current.remove();
  const previous = topModal(root);
  if (previous) {
    previous.hidden = false;
    previous.setAttribute('aria-hidden', 'false');
    previous.setAttribute('aria-modal', 'true');
  } else {
    root.classList.remove('open');
    root.setAttribute('aria-hidden', 'true');
  }
  const fallback = previous && ($(MODAL_FOCUSABLE, previous) || previous);
  const focusTarget = target && target.isConnected && target.offsetParent !== null ? target : fallback;
  if (focusTarget && focusTarget.focus) focusTarget.focus();
}
document.addEventListener('keydown', event => {
  const root = $('#modal-root'), modal = topModal(root);
  if (!root || !root.classList.contains('open') || !modal) return;
  if (event.key === 'Escape') { event.preventDefault(); closeModal(); return; }
  if (event.key !== 'Tab') return;
  const focusable = $$(MODAL_FOCUSABLE, modal).filter(element => element.offsetParent !== null);
  if (!focusable.length) { event.preventDefault(); modal.focus(); return; }
  const first = focusable[0], last = focusable[focusable.length - 1];
  if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
  else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
});

async function openThemeSettings() {
  const current=APP_THEME.get(), labels={bg:'Background',bg2:'Secondary Background',panel:'Panel',panel2:'Raised Panel',line:'Borders',text:'Text',muted:'Muted Text',primary:'Primary Accent',secondary:'Secondary Accent',accent:'Accent',success:'Success',danger:'Danger',warning:'Warning'};
  const modal=openModal(`<h2>🎨 ${T('Appearance','Оформление')}</h2><div class="theme-grid mb">${Object.keys(APP_THEME.presets).map(name=>`<button class="theme-preset ${current.preset===name?'active':''}" data-theme-preset="${name}"><b>${name[0].toUpperCase()+name.slice(1)}</b></button>`).join('')}</div><h3>Custom Theme</h3><div class="theme-grid">${Object.entries(labels).map(([key,label])=>`<label class="theme-color"><span>${label}</span><input type="color" data-theme-color="${key}" value="${esc(current[key])}"></label>`).join('')}</div><div class="grid cols-3 mt"><label class="f"><span>Font Scale</span><input type="range" id="theme-font" min=".85" max="1.3" step=".05" value="${current.fontScale}"></label><label class="f"><span>Density</span><select id="theme-density"><option value="comfortable">Comfortable</option><option value="compact" ${current.density==='compact'?'selected':''}>Compact</option></select></label><label class="f"><span>Glow</span><input type="range" id="theme-glow" min="0" max="1" step=".1" value="${current.glow}"></label></div><label class="checkbox mt"><input id="theme-motion" type="checkbox" ${current.reducedMotion?'checked':''}> Reduced motion</label><div id="theme-contrast" class="mt"></div><div class="row mt"><button id="theme-reset">Reset</button><button class="btn-primary" id="theme-save">Save Theme</button></div>`,true);
  let draft={...current};
  const preview=()=>{draft.fontScale=Number($('#theme-font',modal).value);draft.density=$('#theme-density',modal).value;draft.glow=Number($('#theme-glow',modal).value);draft.reducedMotion=$('#theme-motion',modal).checked;APP_THEME.apply(draft);const ratio=Math.min(APP_THEME.contrast(draft.bg,draft.text),APP_THEME.contrast(draft.panel,draft.text));const out=$('#theme-contrast',modal);out.className=ratio>=4.5?'contrast-ok mt':'contrast-bad mt';out.textContent=`Contrast ${ratio.toFixed(2)}:1 · ${ratio>=4.5?'AA ✓':'Too low'}`;};
  $$('[data-theme-preset]',modal).forEach(btn=>btn.onclick=()=>{draft=APP_THEME.choosePreset(btn.dataset.themePreset);closeModal();openThemeSettings();});
  $$('[data-theme-color]',modal).forEach(input=>input.oninput=()=>{draft[input.dataset.themeColor]=input.value;draft.preset='custom';preview();});
  ['#theme-font','#theme-density','#theme-glow','#theme-motion'].forEach(sel=>$(sel,modal).oninput=preview);
  $('#theme-reset',modal).onclick=()=>{draft={...APP_THEME.defaults};APP_THEME.apply(draft);closeModal();openThemeSettings();};
  $('#theme-save',modal).onclick=async()=>{if(!APP_THEME.valid(draft)){toast(T('Text contrast must be at least 4.5:1.','Контраст текста должен быть минимум 4.5:1.'),true);return;}APP_THEME.apply(draft);if(state.me){try{state.me=await api('/api/profile',{method:'POST',body:{theme:draft}});}catch(e){toast(e.message,true);return;}}closeModal();toast(T('Theme saved.','Тема сохранена.'));};
  preview();
}

function openImageCrop(file, kind, onUploaded) {
  if (!file || !/^image\/(jpeg|png|webp)$/.test(file.type) || file.size > 10_000_000) {
    toast(T('Choose a JPEG, PNG, or WebP file up to 10 MB.','Выберите JPEG, PNG или WebP до 10 MB.'),true);return;
  }
  const flexible = kind === 'feed_image' || kind === 'news_image' || kind === 'contract_image';
  const reader = new FileReader();
  reader.onerror = () => toast(T('Could not read the image.','Не удалось прочитать изображение.'),true);
  reader.onload = () => {
    const image = new Image();
    image.onerror = () => toast(T('Could not decode the image.','Не удалось декодировать изображение.'),true);
    image.onload = () => {
      const originalScale = Math.min(1, 2400 / Math.max(image.width, image.height));
      const originalSize = [Math.max(64, Math.round(image.width * originalScale)), Math.max(64, Math.round(image.height * originalScale))];
      const presets = flexible ? {
        original: originalSize, '16:9': [1920,1080], '3:2': [1800,1200],
        '4:3': [1600,1200], '1:1': [1400,1400], '4:5': [1200,1500],
      } : {'4:5':[1000,1250], '1:1':[1000,1000]};
      let mode = flexible ? 'original' : (kind === 'account_avatar' ? '1:1' : '4:5');
      let [outputWidth,outputHeight] = presets[mode];
      let zoom=1,rotation=0,dx=0,dy=0,drag=null;
      const presetButtons = Object.keys(presets).map(id=>`<button type="button" data-crop-preset="${id}" class="${mode===id?'active':''}">${id==='original'?T('Original','Оригинал'):id}</button>`).join('');
      const modal = openModal(`<h2>${T('Crop Image','Обрезка изображения')}</h2><div class="image-crop-stage"><canvas id="crop-canvas" width="400" height="400"></canvas></div><div class="segmented mt crop-presets">${presetButtons}${flexible?`<button type="button" data-crop-preset="custom">${T('Custom','Свои')}</button>`:''}<button type="button" id="crop-rotate">↻ 90°</button></div>${flexible?`<div class="grid cols-2 mt"><label class="f"><span>${T('Output Width','Ширина результата')}</span><input id="crop-output-width" type="number" min="64" max="4000" step="1" value="${outputWidth}"></label><label class="f"><span>${T('Output Height','Высота результата')}</span><input id="crop-output-height" type="number" min="64" max="4000" step="1" value="${outputHeight}"></label></div><p class="small muted">${T('Feed and Contract images may use any ratio from 1:5 to 5:1 and up to 12 megapixels.','Для Feed и Contracts разрешено любое соотношение от 1:5 до 5:1 и до 12 мегапикселей.')}</p>`:''}<label class="f mt"><span>Zoom</span><input id="crop-zoom" type="range" min="1" max="3" step=".01" value="1"></label><p id="crop-output-info" class="small muted"></p><p class="small muted">${T('Drag the image to reposition it.','Перетаскивайте изображение для позиционирования.')}</p><div class="row"><button id="crop-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="crop-upload">${T('Upload','Загрузить')}</button></div>`,true);
      const canvas=$('#crop-canvas',modal);
      const ratio=()=>outputWidth/outputHeight;
      const validSize=()=>outputWidth>=64&&outputHeight>=64&&outputWidth<=4000&&outputHeight<=4000&&outputWidth*outputHeight<=12_000_000&&ratio()>=.2&&ratio()<=5;
      const updateInfo=()=>{const info=$('#crop-output-info',modal);info.textContent=`${outputWidth} × ${outputHeight}px · ${(outputWidth/outputHeight).toFixed(3)}:1 · ${((outputWidth*outputHeight)/1_000_000).toFixed(2)} MP`;info.className=validSize()?'small muted':'small warn-text';};
      const draw=(target=canvas)=>{
        const preview=target===canvas,w=preview?400:outputWidth,h=preview?Math.max(1,Math.round(w/ratio())):outputHeight;
        if(target.width!==w)target.width=w;if(target.height!==h)target.height=h;
        const context=target.getContext('2d');context.clearRect(0,0,w,h);context.save();
        const previewHeight=Math.max(1,Math.round(400/ratio()));
        context.translate(w/2+dx*(w/400),h/2+dy*(h/previewHeight));context.rotate(rotation*Math.PI/180);
        const rotated=rotation%180!==0,effectiveWidth=rotated?image.height:image.width,effectiveHeight=rotated?image.width:image.height;
        const scale=Math.max(w/effectiveWidth,h/effectiveHeight)*zoom;
        context.drawImage(image,-image.width*scale/2,-image.height*scale/2,image.width*scale,image.height*scale);context.restore();
      };
      const selectMode=id=>{if(presets[id]){mode=id;[outputWidth,outputHeight]=presets[id];if(flexible){$('#crop-output-width',modal).value=outputWidth;$('#crop-output-height',modal).value=outputHeight;}}else mode='custom';$$('[data-crop-preset]',modal).forEach(button=>button.classList.toggle('active',button.dataset.cropPreset===mode));dx=dy=0;draw();updateInfo();};
      draw();updateInfo();
      canvas.onpointerdown=event=>{drag={x:event.clientX,y:event.clientY,dx,dy};canvas.setPointerCapture(event.pointerId);};
      canvas.onpointermove=event=>{if(!drag)return;dx=drag.dx+event.clientX-drag.x;dy=drag.dy+event.clientY-drag.y;draw();};
      canvas.onpointerup=()=>drag=null;
      $$('[data-crop-preset]',modal).forEach(button=>button.onclick=()=>selectMode(button.dataset.cropPreset));
      if(flexible){const customSize=()=>{outputWidth=Math.round(Number($('#crop-output-width',modal).value)||0);outputHeight=Math.round(Number($('#crop-output-height',modal).value)||0);mode='custom';$$('[data-crop-preset]',modal).forEach(button=>button.classList.toggle('active',button.dataset.cropPreset==='custom'));dx=dy=0;if(validSize())draw();updateInfo();};$('#crop-output-width',modal).onchange=customSize;$('#crop-output-height',modal).onchange=customSize;}
      $('#crop-zoom',modal).oninput=event=>{zoom=Number(event.target.value);draw();};
      $('#crop-rotate',modal).onclick=()=>{rotation=(rotation+90)%360;dx=dy=0;draw();};
      $('#crop-cancel',modal).onclick=closeModal;
      $('#crop-upload',modal).onclick=async()=>{
        if(!validSize()){toast(T('Choose dimensions between 64 and 4000 px, no more than 12 MP, and an aspect ratio between 1:5 and 5:1.','Выберите размеры от 64 до 4000 px, не более 12 MP и соотношение сторон от 1:5 до 5:1.'),true);return;}
        const out=document.createElement('canvas');out.width=outputWidth;out.height=outputHeight;draw(out);
        const button=$('#crop-upload',modal);button.disabled=true;button.textContent=T('Encoding…','Кодирование…');
        try{
          let dataUrl='',quality=.9,bytes=Infinity;
          while(quality>=.5&&bytes>2_300_000){dataUrl=out.toDataURL('image/webp',quality);const comma=dataUrl.indexOf(',');bytes=Math.ceil((dataUrl.length-comma-1)*3/4);quality-=.1;}
          if(bytes>2_300_000)throw new Error(T('The selected resolution cannot fit the processed-image limit. Reduce width or height.','Выбранное разрешение не помещается в лимит обработанного изображения. Уменьшите ширину или высоту.'));
          button.textContent=T('Uploading…','Загрузка…');
          const media=await api('/api/media',{method:'POST',body:{kind,data_url:dataUrl}});closeModal();onUploaded(media);
        }catch(error){button.disabled=false;button.textContent=T('Upload','Загрузить');toast(error.message,true);}
      };
    };
    image.src=reader.result;
  };
  reader.readAsDataURL(file);
}

async function api(path, opts) {
  const o = Object.assign({ headers: {} }, opts);
  o.headers = Object.assign({ 'Accept-Language': typeof APP_I18N !== 'undefined' ? APP_I18N.current() : 'en' }, o.headers || {});
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

function spinner() { return `<div class="empty"><span class="spin"></span> ${T('Loading…','Загрузка…')}</div>`; }

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
    public: false,
  };
}

/* ============================== роутер ============================== */

const routeAliases = {
  codex: 'database', calc: 'quick-reference', characters: 'dossiers',
  roster: 'crew', news: 'feed', jobs: 'contracts',
};
const routes = {
  '': viewHome, database: viewCodex, guides: viewGuides, market: viewMarket,
  'quick-reference': viewCalc, dossiers: viewCharacters, crew: viewRoster,
  feed: viewCityFeed, contracts: viewContracts, personas: viewPersonas,
  gm: viewGMOperations, session: viewSessionPlayer, admin: viewAdmin,
  // Compatibility aliases keep old bookmarks and links working during migration.
  codex: viewCodex, calc: viewCalc, characters: viewCharacters,
  roster: viewRoster, news: viewNews, jobs: viewJobs,
  login: viewLogin, register: viewRegister, profile: viewProfile,
};

async function route() {
  const hash = location.hash.replace(/^#\/?/, '');
  const [seg0, seg1] = hash.split('/');
  const view = $('#view');
  const activeRoute = routeAliases[seg0] || seg0;
  $$('[data-route]').forEach(anchor => {
    const active = anchor.dataset.route === activeRoute;
    anchor.classList.toggle('active', active);
    if (active) anchor.setAttribute('aria-current', 'page');
    else anchor.removeAttribute('aria-current');
  });
  document.body.dataset.workspace = activeRoute === 'gm' ? 'gm' : 'network';
  const moreButton=$('#mobile-more-toggle');if(moreButton)moreButton.classList.toggle('active',['database','market','quick-reference','crew','personas','guides','profile','gm','admin'].includes(activeRoute));
  $$('[data-workspace]').forEach(button=>button.classList.toggle('active',button.dataset.workspace===(activeRoute==='gm'?'gm':'network')));
  const mobileMore=$('#mobile-more-menu');if(mobileMore)mobileMore.hidden=true;
  window.scrollTo(0, 0);
  closeModal(true);
  view.setAttribute('aria-busy', 'true');
  try {
    if (seg0 === 'contracts' && seg1) { await viewContractDetail(view, seg1); return; }
    if (seg0 === 'feed' && seg1) { await viewFeedDetail(view, seg1); return; }
    if (seg0 === 'personas' && seg1) { await viewPersonaDetail(view, seg1); return; }
    if (seg0 === 'session' && seg1) { await viewSessionPlayer(view, seg1); return; }
    if (seg0 === 'char') {
      const raw = seg1 || '';
      const charId = raw.split('?')[0];
      if (!charId || charId === '' || charId === 'new') { await viewWizard(); return; }
      if (raw.includes('?edit')) { await viewEditor(charId); return; }
      await viewSheet(charId); return;
    }
    const fn = routes[activeRoute] || viewHome;
    await fn(view);
  } catch (e) {
    view.innerHTML = `<div class="empty">⚠️ ${esc(APP_I18N.translate(e.message))}</div>`;
  } finally {
    APP_I18N.apply(view);
    view.setAttribute('aria-busy', 'false');
  }
}

function go(path) { location.hash = path; }

/* ============================== шапка / юзер ============================== */

async function performLogout(){try{await api('/api/logout',{method:'POST'});}catch(error){}state.me=null;renderUserbox();route();toast(T('Signed out.','Вы вышли из системы.'));}

function renderUserbox() {
  const box = $('#userbox'),workspace=$('#workspace-switch'),dossier=$('#active-dossier-wrap'),mobileGm=$('#mobile-gm-link'),mobileLogout=$('#mobile-logout');
  if (!state.me) {
    if(workspace)workspace.hidden=true;if(dossier)dossier.hidden=true;if(mobileGm)mobileGm.hidden=true;if(mobileLogout)mobileLogout.hidden=true;
    box.innerHTML = `<a class="btn-primary" style="padding:7px 14px;border-radius:8px;color:#041018" href="#/login">${T('Sign in','Войти')}</a>`;
    return;
  }
  if(workspace)workspace.hidden=!state.me.is_gm;if(mobileGm)mobileGm.hidden=!state.me.is_gm;if(mobileLogout){mobileLogout.hidden=false;mobileLogout.onclick=performLogout;}
  const ini = (state.me.display_name || state.me.username || '?').slice(0, 1).toUpperCase();
  box.innerHTML = `
    <button class="userchip" id="userchip" type="button" title="${T('Profile','Профиль')}" aria-label="${T('Open Profile','Открыть профиль')}">
      ${state.me.avatar_media_id?`<img class="avatar" src="/api/media/${esc(state.me.avatar_media_id)}" alt="">`:`<span class="avatar">${esc(ini)}</span>`}
      <span>${esc(state.me.display_name)}</span>
      ${state.me.is_admin ? '<span class="gm-badge">ADMIN</span>' : (state.me.is_gm ? `<span class="gm-badge">${T('GM','ГМ')}</span>` : '')}
    </button>
    <button class="btn-sm" id="notifications-btn" title="${T('Notifications','Уведомления')}" aria-label="${T('Notifications','Уведомления')}">◉</button>
    <button class="btn-sm" id="logout-btn">${T('Sign out','Выйти')}</button>`;
  $('#userchip').onclick = () => go('/profile');
  if ($('#notifications-btn') && typeof openNotifications === 'function') $('#notifications-btn').onclick = openNotifications;
  $('#logout-btn').onclick = performLogout;
}

function updateCityClock(){const clock=$('#city-clock');if(clock)clock.textContent=new Intl.DateTimeFormat(APP_I18N.current()==='ru'?'ru-RU':'en-GB',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date())+' NC';}

async function refreshShellDossiers(){
  const wrap=$('#active-dossier-wrap'),select=$('#active-dossier');if(!wrap||!select||!state.me){if(wrap)wrap.hidden=true;return;}
  try{const characters=(await api('/api/characters')).characters.filter(character=>!character.data.archived);if(!characters.length){wrap.hidden=true;return;}const saved=Number(localStorage.getItem('ncnet:active-dossier')),active=characters.some(character=>character.id===saved)?saved:characters[0].id;select.innerHTML=characters.map(character=>`<option value="${character.id}" ${character.id===active?'selected':''}>${esc(character.data.handle||T('Unnamed','Безымянный'))}</option>`).join('');wrap.hidden=false;localStorage.setItem('ncnet:active-dossier',String(active));select.onchange=()=>{localStorage.setItem('ncnet:active-dossier',select.value);go(`/char/${select.value}`);};}catch(error){wrap.hidden=true;}
}

function openCommandPalette(){
  const commands=[['','⌂',T('City Network','Городская сеть')],['contracts','◎',T('Contracts','Контракты')],['feed','≋',T('City Feed','Городская лента')],['dossiers','◇',T('Dossiers','Досье')],['database','▦',T('Database','База данных')],['market','◈',T('Night Market','Ночной рынок')],['quick-reference','◫',T('Quick Reference','Быстрые правила')],['crew','⌘',T('Crew Registry','Реестр команд')],['personas','◉','Personas'],['guides','▤',T('Archive','Архив')]];if(state.me?.is_gm)commands.push(['gm','⚙','GM OPS']);if(state.me?.is_admin)commands.push(['admin','⚿',T('Admin Console','Панель Admin')]);
  const modal=openModal(`<h2>${T('Command Palette','Командная строка')}</h2><input id="command-search" type="search" autofocus placeholder="${T('Jump to a network module…','Перейти к модулю сети…')}" aria-label="${T('Search commands','Поиск команд')}"><div id="command-list" class="command-list mt">${commands.map(([route,icon,label])=>`<button data-command-route="${route}" data-command-search="${esc(label.toLowerCase())}"><span>${icon}</span><b>${esc(label)}</b><small>#/${route}</small></button>`).join('')}</div>`);const search=$('#command-search',modal);search.oninput=()=>{const query=search.value.trim().toLowerCase();$$('[data-command-route]',modal).forEach(button=>button.hidden=Boolean(query&&!button.dataset.commandSearch.includes(query)));};$$('[data-command-route]',modal).forEach(button=>button.onclick=()=>{closeModal();go('/'+button.dataset.commandRoute);});
}

function initShellControls(){
  updateCityClock();setInterval(updateCityClock,1000);
  const command=$('#command-toggle');if(command)command.onclick=openCommandPalette;
  document.addEventListener('keydown',event=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='k'){event.preventDefault();openCommandPalette();}});
  $$('[data-workspace]').forEach(button=>button.onclick=()=>go(button.dataset.workspace==='gm'?'/gm':'/'));
  const more=$('#mobile-more-toggle'),menu=$('#mobile-more-menu');if(more&&menu)more.onclick=()=>{menu.hidden=!menu.hidden;};
  $$('#mobile-more-menu a').forEach(link=>link.onclick=()=>{menu.hidden=true;});
}

/* ============================== главная ============================== */

async function viewHome(view) {
  view.innerHTML = spinner();
  const [stats, feed, contracts] = await Promise.all([api('/api/stats'),api('/api/feed'),api('/api/contracts')]);
  const transmissions=feed.posts.slice(0,5),activeContracts=contracts.contracts.filter(contract=>['open','crew_full','in_progress'].includes(contract.status)).slice(0,6);
  view.innerHTML=`<div class="page-head city-network-head"><div><div class="small muted">NC//NET // CITY NETWORK // RELAY 07</div><h1>${T('Night City Live Grid','Живая сеть Найт-Сити')}</h1><div class="sub">${T('Contracts, transmissions and operator traffic in one encrypted city layer.','Контракты, передачи и трафик операторов в одном зашифрованном слое города.')}</div></div><div class="row"><a class="btn-sm" href="#/feed">${T('TRANSMIT','ПЕРЕДАТЬ')} ↗</a><a class="btn-primary" href="#/contracts">${T('OPEN CONTRACTS','ОТКРЫТЬ CONTRACTS')} →</a></div></div><div class="network-telemetry-strip"><span><b>${nf.format(stats.open_contracts??stats.open_jobs)}</b>${T('OPEN SIGNALS','ОТКРЫТЫХ СИГНАЛОВ')}</span><span><b>${nf.format(stats.feed_posts??stats.news)}</b>${T('TRANSMISSIONS','ПЕРЕДАЧ')}</span><span><b>${nf.format(stats.characters)}</b>${T('DOSSIERS','ДОСЬЕ')}</span><span><b>${nf.format(stats.users)}</b>${T('OPERATORS','ОПЕРАТОРОВ')}</span><span><b>${nf.format(stats.items)}</b>${T('DATABASE OBJECTS','ОБЪЕКТОВ БАЗЫ')}</span></div><div class="city-network-grid"><section class="city-map-console"><div class="console-head"><span>GEOSPATIAL RELAY</span><span class="green">● LIVE</span></div><div id="home-city-map">${typeof ncMapHtml==='function'?ncMapHtml(activeContracts):''}</div></section><aside class="city-signal-column"><section class="signal-module"><div class="console-head"><span>${T('ACTIVE SIGNALS','АКТИВНЫЕ СИГНАЛЫ')}</span><a href="#/contracts">ALL →</a></div><div class="signal-stack">${activeContracts.length?activeContracts.map((contract,index)=>`<button class="city-signal" data-home-contract="${contract.id}"><span class="signal-index">${String(index+1).padStart(2,'0')}</span><span><b class="user-content">${esc(contract.title)}</b><small>${esc(typeof ncDistrictName==='function'?ncDistrictName(contract.district_id):contract.district_id||T('Classified','Секретно'))} · ${esc(typeof ncLabel==='function'?ncLabel(contract.risk_level):contract.risk_level)}</small></span><span class="tag">${contract.crew_count}/${contract.crew_capacity||'∞'}</span></button>`).join(''):`<div class="empty">${T('No active signals.','Нет активных сигналов.')}</div>`}</div></section><section class="signal-module"><div class="console-head"><span>${T('CITY FEED','ГОРОДСКАЯ ЛЕНТА')}</span><a href="#/feed">ALL →</a></div><div class="signal-stack">${transmissions.length?transmissions.map(post=>`<button class="feed-signal" data-home-feed="${post.id}"><span class="tag">${esc(post.format.toUpperCase())}</span><span><b class="user-content">${esc(post.headline||post.body.slice(0,70))}</b><small class="user-content">${esc(post.author?.display_name||'NC//NET')} · ${timeAgo(post.published_at||post.created)}</small></span></button>`).join(''):`<div class="empty">${T('No transmissions.','Нет передач.')}</div>`}</div></section></aside></div><div class="data-layer-strip"><span>DATA LAYER</span><a href="#/market">NIGHT MARKET</a><a href="#/database">DATABASE</a><a href="#/quick-reference">QUICK REF</a><a href="#/crew">CREW REGISTRY</a><a href="#/personas">PERSONAS</a></div>`;
  if(typeof ncBindActivation==='function')ncBindActivation('[data-contract-open]',view,element=>go(`/contracts/${element.dataset.contractOpen}`));
  if(typeof ncBindMapControls==='function')ncBindMapControls(view);
  $$('[data-home-contract]',view).forEach(button=>button.onclick=()=>go(`/contracts/${button.dataset.homeContract}`));
  $$('[data-home-feed]',view).forEach(button=>button.onclick=()=>go(`/feed/${button.dataset.homeFeed}`));
}

/* ============================== справочник ============================== */

function catalogCategoryName(category) { return APP_I18N.current() === 'en' ? (category.en || category.sheet || category.id) : category.ru; }
const ITEM_DESC_EN = {
  'VEX Megatower (Rent)': '“Choose any megatower and, as if by magic, you will find a keycard for an empty apartment in the nearest parcel locker.” Apartments supplied by the Netrunner VEX. His goals are unclear, but an apartment is an apartment.',
};
function itemDescription(item) {
  const value = APP_I18N.current() === 'en' ? (item.desc_en || ITEM_DESC_EN[item.name] || item.desc || '') : (item.desc_ru || item.desc || '');
  return APP_I18N.current() === 'en' ? String(value).replace(/сost/g, 'cost') : value;
}
const codexState = { cat: '', q: '', offset: 0, limit: 30 };

async function viewCodex(view) {
  const cats = state.meta.cats;
  view.innerHTML = `
  <div class="page-head"><div><h1>📚 ${T('Codex','Справочник')}</h1><div class="sub">${T('All equipment from Data Pool','Всё снаряжение из Data Pool')}: ${nf.format(state.meta._total || '')}</div></div></div>
  <div class="codex-layout">
    <div class="cat-list panel" style="padding:10px">
      <a href="javascript:void(0)" data-cat="" class="${codexState.cat === '' ? 'active' : ''}">🌐 ${T('All Categories','Всё подряд')}</a>
      ${cats.map(c => `
        <a href="javascript:void(0)" data-cat="${c.id}" class="${codexState.cat === c.id ? 'active' : ''}">
          <span>${c.emoji} ${esc(catalogCategoryName(c))}</span><span class="cnt">${c.count}</span></a>`).join('')}
    </div>
    <div>
      <div class="searchbar">
        <input id="codex-q" placeholder="${T('Search by name, type, or description…','Поиск: имя, тип, описание…')}" value="${esc(codexState.q)}">
        <button id="codex-search">${T('Search','Найти')}</button>
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
  if (!gs.length) { view.innerHTML = `<div class="empty">${T('Guides failed to load','Гайды не загрузились')}</div>`; return; }
  const cur = guidesTab || gs[0].id;
  view.innerHTML = `
  <div class="page-head">
    <div><h1>📖 ${T('Mini Guides','Мини-гайды')} ${APP_I18N.current()==='en'?'<span class="tag">Russian only</span>':''}</h1>
      <div class="sub">${T('These reference guides remain in their original Russian.','Краткие правила из «Spes Desperata»: создание персонажа, боёвка и нетраннинг.')}</div></div>
  </div>
  <div data-no-auto-translate>
  <div class="editor-tabs" style="margin-bottom:14px">
    ${gs.map(g => `<button data-g="${g.id}" class="${g.id === cur ? 'active' : ''}">${g.emoji} ${esc(g.title)}</button>`).join('')}
  </div>
  <div class="panel accent mb"><b>${gs.find(g => g.id === cur)?.emoji} ${esc(gs.find(g => g.id === cur)?.title || '')}.</b> ${esc(gs.find(g => g.id === cur)?.sub || '')}</div>
  </div>
  <div id="guide-box" data-no-auto-translate>
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
  const catName = (id) => { const c = state.meta.cats.find(x => x.id === id); return c ? c.emoji + ' ' + catalogCategoryName(c) : id; };
  box.innerHTML = `
    <div class="muted small mb">${T('Found:','Найдено:')} ${nf.format(data.total)}</div>
    <div class="item-grid">
      ${data.items.map(it => `
        <div class="card item-card">
          <div class="head">
            <span class="name" data-id="${it.id}">${esc(it.name)}</span>
            <span class="price">${it.price != null ? money(it.price) : '<span class="muted">—</span>'}</span>
          </div>
          <div class="chips"><span class="chip">${catName(it.cat)}</span>${itemMechanicChips(it)}</div>
          ${it.source ? `<div class="small muted">📖 ${esc(it.source)}</div>` : ''}
          ${it.desc ? `<details class="desc-wrap"><summary>${T('Description','Описание')}</summary><div class="desc">${esc(itemDescription(it))}</div></details>` : ''}
        </div>`).join('')}
    </div>
    ${pagerHtml(data.total, data.offset, data.limit)}`;
  $$('.name', box).forEach(el => el.onclick = () => showItemModal(el.dataset.id));
  bindPager(box, () => { codexState.offset += data.limit; loadCodexItems(); },
    () => { codexState.offset = Math.max(0, codexState.offset - data.limit); loadCodexItems(); });
}

const ITEM_FIELD_LABELS={Type:['Type','Тип'],Skill:['Skill','Навык'],Damage:['Damage','Урон'],Mag:['Magazine','Магазин'],ROF:['ROF','Скорострельность'],Hands:['Hands','Руки'],Conceal:['Concealable','Скрываемое'],Quality:['Quality','Качество'],Install:['Install','Установка'],HL:['HL','HL'],'Suitable ammo / weapon':['Compatibility','Совместимость'],SP:['SP','SP'],SDP:['SDP','SDP'],Seats:['Seats','Места'],Class:['Class','Класс'],Penalty:['Penalty','Штраф'],Available:['Compatibility','Совместимость'],Availability:['Availability','Доступность'],'Nomad Access':['Nomad Access','Доступ Nomad'],PER:['PER','PER'],SPD:['SPD','SPD'],ATK:['ATK','ATK'],DEF:['DEF','DEF'],REZ:['REZ','REZ']};
function itemFieldLabel(key){const labels=ITEM_FIELD_LABELS[key];return labels?(APP_I18N.current()==='ru'?labels[1]:labels[0]):key;}

function pagerHtml(total, offset, limit) {
  if (total <= limit) return '';
  const from = offset + 1, to = Math.min(total, offset + limit);
  return `<div class="pager">
    <button class="btn-sm" ${offset <= 0 ? 'disabled' : ''} data-pg="prev">← ${T('Back','Назад')}</button>
    <span class="muted small">${nf.format(from)}–${nf.format(to)} ${T('of','из')} ${nf.format(total)}</span>
    <button class="btn-sm" ${to >= total ? 'disabled' : ''} data-pg="next">${T('Next →','Вперёд →')}</button></div>`;
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
      <span class="chip">${c ? c.emoji + ' ' + esc(catalogCategoryName(c)) : it.cat}</span>
      ${it.price != null ? `<span class="tag price">${money(it.price)}</span>` : ''}
      ${it.source ? `<span class="chip">📖 ${esc(it.source)}</span>` : ''}
      ${it.hl ? `<span class="chip hl-badge">HL ${it.hl}</span>` : ''}
    </div>
    <div class="mechanic-chips mb">${itemMechanicChips(it)}</div>
    <div class="kv mb">
      ${Object.entries(it.fields || {}).map(([k, v]) => `<b>${esc(itemFieldLabel(k))}</b><span>${esc(String(v).replace(/\.0(?=\b)/g,''))}</span>`).join('')}
    </div>
    ${it.desc ? `<div class="desc">${esc(itemDescription(it))}</div>` : `<div class="muted">${T('No description available.','Описание отсутствует.')}</div>`}
  `);
  return m;
}

/* ============================== чёрный рынок ============================== */

const marketState = { tab: 'nm', vendor: '', q: '', cat: '', sort: 'discount', affordable: false, sellChar: null };

async function viewMarket(view) {
  view.innerHTML = `
  <div class="page-head">
    <div><h1>🕶️ ${T('Night Market','Чёрный рынок')}</h1>
    <div class="sub">${T('Independent vendors refresh their stock every day at 00:00 Moscow time.','Независимые продавцы обновляют ассортимент каждый день в 00:00 МСК.')}</div></div>
    <div class="row"><a class="btn-sm" href="#/database">📚 ${T('Open Item Database','Открыть базу предметов')}</a>${state.me && state.me.is_gm ? `<button id="payroll-btn">💰 ${T('Payout (GM)','Выплата (ГМ)')}</button>` : ''}</div>
  </div>
  <div class="tabs">
    <button data-tab="nm" class="${marketState.tab === 'nm' ? 'active' : ''}">🌙 ${T('Night Market Vendors','Продавцы Night Market')}</button>
    <button data-tab="sell" class="${marketState.tab === 'sell' ? 'active' : ''}">♻️ ${T('Sell Used Gear','Скупка хлама')}</button>
  </div>
  <div id="market-body">${spinner()}</div>
  <div id="cart-slot"></div>`;
  $$('.tabs button', view).forEach(b => b.onclick = () => { marketState.tab = b.dataset.tab; viewMarket(view); });
  const pb = $('#payroll-btn');
  if (pb) pb.onclick = payrollModal;
  await loadMarketBody();
}

async function loadMarketBody() {
  const box = $('#market-body');
  if (!box) return;
  if (marketState.tab === 'sell') return loadSellTab(box);
  return loadNightMarket(box);
}

async function loadNightMarket(box) {
  box.innerHTML = spinner();
  const data = await api('/api/nightmarket');
  let characters=[];
  if(state.me)try{characters=(await api('/api/characters')).characters.filter(character=>!character.data.archived);}catch(e){}
  const selectedBuyer=characters.find(character=>character.id===Number(marketState.buyerChar))||characters.find(character=>character.id===Number(localStorage.getItem('ncnet:active-dossier')))||characters[0]||null;
  if(selectedBuyer)marketState.buyerChar=selectedBuyer.id;
  const allCategories=[...new Set(data.vendors.flatMap(vendor=>vendor.categories))];
  const vendorName=vendor=>APP_I18N.current()==='ru'?vendor.name_ru:vendor.name_en;
  const vendorTagline=vendor=>APP_I18N.current()==='ru'?vendor.tagline_ru:vendor.tagline_en;
  const categoryName=id=>{const category=state.meta.cats.find(item=>item.id===id);return category?`${category.emoji} ${catalogCategoryName(category)}`:id;};
  const filterItems=vendor=>{
    const query=marketState.q.trim().toLowerCase();
    let items=vendor.items.filter(item=>(!marketState.cat||item.cat===marketState.cat)&&(!query||`${item.name} ${item.desc||''} ${item.source||''}`.toLowerCase().includes(query))&&(!marketState.affordable||!selectedBuyer||Number(item.street_price)<=Number(selectedBuyer.data.cash||0)));
    const compare={name:(a,b)=>a.name.localeCompare(b.name,APP_I18N.current()==='ru'?'ru':'en'),price_asc:(a,b)=>a.street_price-b.street_price,price_desc:(a,b)=>b.street_price-a.street_price,discount:(a,b)=>a.multiplier-b.multiplier||a.street_price-b.street_price,category:(a,b)=>categoryName(a.cat).localeCompare(categoryName(b.cat))||a.name.localeCompare(b.name)}[marketState.sort]||(()=>0);
    return [...items].sort(compare);
  };
  const visibleVendors=data.vendors.filter(vendor=>!marketState.vendor||vendor.id===marketState.vendor);
  box.innerHTML=`<div class="market-toolbar panel mb"><div class="grid cols-4"><label class="f"><span>${T('Vendor','Продавец')}</span><select id="nm-vendor"><option value="">${T('All Vendors','Все продавцы')}</option>${data.vendors.map(vendor=>`<option value="${vendor.id}" ${marketState.vendor===vendor.id?'selected':''}>${vendor.icon} ${esc(vendorName(vendor))}</option>`).join('')}</select></label><label class="f"><span>${T('Category','Категория')}</span><select id="nm-cat"><option value="">${T('All Categories','Все категории')}</option>${allCategories.map(id=>`<option value="${id}" ${marketState.cat===id?'selected':''}>${esc(categoryName(id))}</option>`).join('')}</select></label><label class="f"><span>${T('Sort','Сортировка')}</span><select id="nm-sort"><option value="discount" ${marketState.sort==='discount'?'selected':''}>${T('Best Deal','Лучшая цена')}</option><option value="price_asc" ${marketState.sort==='price_asc'?'selected':''}>${T('Price: Low to High','Цена: по возрастанию')}</option><option value="price_desc" ${marketState.sort==='price_desc'?'selected':''}>${T('Price: High to Low','Цена: по убыванию')}</option><option value="name" ${marketState.sort==='name'?'selected':''}>${T('Name','Название')}</option><option value="category" ${marketState.sort==='category'?'selected':''}>${T('Category','Категория')}</option></select></label>${characters.length?`<label class="f"><span>${T('Buyer','Покупатель')}</span><select id="nm-buyer">${characters.map(character=>`<option value="${character.id}" ${selectedBuyer?.id===character.id?'selected':''}>${esc(character.data.handle)} · ${money(character.data.cash)}</option>`).join('')}</select></label>`:'<div></div>'}</div><div class="searchbar"><input id="nm-q" value="${esc(marketState.q)}" placeholder="${T('Search current stock…','Поиск по текущему ассортименту…')}"><button id="nm-search">${T('Search','Найти')}</button><label class="checkbox"><input id="nm-affordable" type="checkbox" ${marketState.affordable?'checked':''}> ${T('Affordable only','Только доступное по цене')}</label><span class="small muted">${T('Stock date','Дата ассортимента')}: ${esc(data.date)}</span></div></div>${visibleVendors.map(vendor=>{const items=filterItems(vendor);return `<section class="market-vendor panel mb" style="--vendor:${esc(vendor.accent_color||'#00e5ff')}"><header class="market-vendor-head"><div><h2>${vendor.icon} ${esc(vendorName(vendor))}</h2><p class="muted user-content">${esc(vendorTagline(vendor))}</p></div><div class="row">${vendor.persona_id?`<a class="btn-sm" href="#/personas/${vendor.persona_id}">${T('Vendor Profile','Профиль продавца')}</a>`:''}<span class="tag">${items.length} ${T('offers','предложений')}</span></div></header>${items.length?`<div class="item-grid">${items.map(item=>`<article class="card item-card"><div class="head"><button class="item-name-button name" data-market-info="${item.id}">${esc(item.name)}</button><span>${item.discount?`<span class="market-price-old">${money(item.price)}</span>`:''}<span class="price">${money(item.street_price)}</span></span></div><div class="chips"><span class="chip">${esc(categoryName(item.cat))}</span>${itemMechanicChips(item)}</div>${item.desc?`<details class="desc-wrap"><summary>${T('Description','Описание')}</summary><div class="desc preserve-lines">${esc(itemDescription(item))}</div></details>`:''}<div class="small muted">${item.source?`📖 ${esc(item.source)} · `:''}${item.discount?`<span class="green-text">${Math.round((1-item.multiplier)*100)}% ${T('below list','ниже каталога')}</span>`:`${Math.round((item.multiplier-1)*100)}% ${T('markup','наценка')}`}</div><div class="row"><button class="info-btn" data-market-info="${item.id}" aria-label="${T('Item details','Описание предмета')}">i</button><button class="btn-sm btn-primary" data-buy-nm="${item.id}" data-price="${item.street_price}">${T('Add to Cart','В корзину')} · ${money(item.street_price)}</button></div></article>`).join('')}</div>`:`<div class="empty">${T('No stock matches these filters.','Нет товаров по выбранным фильтрам.')}</div>`}</section>`;}).join('')}`;
  const reload=()=>loadNightMarket(box);
  $('#nm-vendor').onchange=event=>{marketState.vendor=event.target.value;reload();};
  $('#nm-cat').onchange=event=>{marketState.cat=event.target.value;reload();};
  $('#nm-sort').onchange=event=>{marketState.sort=event.target.value;reload();};
  if($('#nm-buyer'))$('#nm-buyer').onchange=event=>{marketState.buyerChar=Number(event.target.value);localStorage.setItem('ncnet:active-dossier',event.target.value);reload();};
  $('#nm-affordable').onchange=event=>{marketState.affordable=event.target.checked;reload();};
  const runSearch=()=>{marketState.q=$('#nm-q').value;reload();};
  $('#nm-search').onclick=runSearch;
  $('#nm-q').onkeydown=event=>{if(event.key==='Enter')runSearch();};
  $$('[data-market-info]',box).forEach(button=>button.onclick=()=>showItemModal(button.dataset.marketInfo));
  $$('[data-buy-nm]', box).forEach(button=>button.onclick=()=>{const card=button.closest('.item-card');addToCart(button.dataset.buyNm,Number(button.dataset.price),'nm',$('.name',card).textContent);});
  renderCart();
}


async function loadSellTab(box) {
  if (!state.me) { box.innerHTML = `<div class="empty">Войдите, чтобы продавать хлам со склада своих персонажей. <a href="#/login">${T('Sign in','Войти')}</a></div>`; return; }
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
    $('#sell-list').innerHTML = inv.length ? inv.map(i => {const locked=['equipped','installed'].includes(i.state);return `
      <div class="inv-row">
        <span class="iname">${esc(i.custom_name||i.name)} ×${i.qty || 1}</span>
        <span class="chip">${esc(i.state||'carried')}</span>
        <span class="muted small">${T('bought for','куплено за')} ${money(i.price)}</span>
        <button class="btn-sm" data-sell-instance="${esc(i.instance_id||'')}" data-sell-key="${esc(i.key)}" ${locked?'disabled':''}>${locked?T('Unequip first','Сначала снять'):T('Sell 1','Продать 1')+' → '+money((i.price||0)*0.5)}</button>
      </div>`;}).join('') : `<div class="empty">${T('Inventory is empty.','Инвентарь пуст.')}</div>`;
    $$('[data-sell-instance]', $('#sell-list')).forEach(b => b.onclick = async () => {
      try {
        const r = await api('/api/sell', { method: 'POST', body: { char_id: ch.id, instance_id: b.dataset.sellInstance, key: b.dataset.sellKey, qty: 1 } });
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

function critTableHtml(table, label) {
  if (!table || !table.length) return '';
  return `<div class="table-scroll"><table class="rtable guide-table">
    <tr><th>2d6</th><th>${T('Injury','Травма')} (${esc(label)})</th><th>${T('Effect','Эффект')}</th><th>Quick Fix</th><th>Treatment</th></tr>
    ${table.map(r => `<tr><td><b>${r[0]}</b></td><td>${esc(r[1])}</td><td>${esc(r[2])}</td><td>${esc(r[3])}</td><td>${esc(r[4])}</td></tr>`).join('')}
  </table></div>`;
}

function woundStatesHtml() {
  const ws = state.meta.wound_states || [];
  if (!ws.length) return `<div class="muted">${T('No data','Нет данных')}</div>`;
  return `<div class="table-scroll"><table class="rtable guide-table">
    <tr><th>${T('State','Состояние')}</th><th>${T('Threshold','Порог')}</th><th>${T('Effect','Эффект')}</th><th>${T('Stabilization','Стабилизация')}</th></tr>
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
    instance_id: c.instance_id || c.id, host_instance: c.host_instance || '', host_instances: c.host_instances || (c.host_instance ? [c.host_instance] : []),
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
  const map={Cyberarm:['cyberarm','neo-soviet cyberarm'],Cyberleg:['cyberleg','romanova cyberlegs'],Cybereye:['cybereye','sponsored cybereye'],'Cyberaudio Suite':['cyberaudio suite','discount cyberaudio suite'],'Neural Link or Neuroport':['neural link','neuroport']};
  return map[host]||[];
}
function cyberHostIds(item){return item.host_instances&&item.host_instances.length?item.host_instances:(item.host_instance?[item.host_instance]:[]);}
function availableCyberHosts(wiz,item) {
  const host=item.capacity&&item.capacity.host;if(!host)return [];
  const accepted=cyberFoundationNames(host), all=[...wiz.cyberware];
  if(wiz.freeNeuroport)all.unshift({id:'creation-neuroport',instance_id:'creation-neuroport',name:'Neuroport',capacity:{slots_total:5}});
  return all.filter(candidate=>accepted.includes(String(candidate.name||'').toLowerCase())).filter(candidate=>{
    const total=num(candidate.capacity&&candidate.capacity.slots_total)||4;
    const used=wiz.cyberware.filter(option=>cyberHostIds(option).includes(candidate.instance_id||candidate.id)).reduce((sum,option)=>sum+(num(option.capacity&&option.capacity.slots_used)||0),0);
    return total-used>=(num(item.capacity&&item.capacity.slots_used)||0);
  });
}
async function chooseCyberHost(hosts, item) {
  const required=item.capacity?.hosts_required||1;
  if (hosts.length < required) return null;
  if (hosts.length === required) return required===1?hosts[0]:hosts.slice(0,required);
  return new Promise(resolve=>{const selected=new Set(),modal=openModal(`<h2>${T('Choose host','Выберите host')} · ${esc(item.name)}</h2><p>${T(`Select ${required} different foundations.`,`Выберите разные foundations: ${required}.`)}</p><div class="choice-card-grid">${hosts.map((host,index)=>{const id=host.instance_id||host.id,total=num(host.capacity?.slots_total)||4,used=state.wizard.cyberware.filter(option=>(option.host_instances||[option.host_instance]).includes(id)).reduce((sum,option)=>sum+(num(option.capacity?.slots_used)||0),0),after=used+(num(item.capacity?.slots_used)||0);return `<button class="choice-card" data-host-index="${index}"><b>${esc(host.custom_name||host.name)} #${index+1}</b><span>Slots ${used}/${total} → ${after}/${total}</span></button>`;}).join('')}</div><div class="row mt"><button id="host-cancel">${T('Cancel','Отмена')}</button><button id="host-confirm" class="btn-primary" disabled>${T('Install','Установить')}</button></div>`,true);$$('[data-host-index]',modal).forEach(button=>button.onclick=()=>{const index=Number(button.dataset.hostIndex);if(selected.has(index))selected.delete(index);else if(selected.size<required)selected.add(index);button.classList.toggle('selected',selected.has(index));$('#host-confirm',modal).disabled=selected.size!==required;});$('#host-confirm',modal).onclick=()=>{const result=[...selected].map(index=>hosts[index]);closeModal();resolve(required===1?result[0]:result);};$('#host-cancel',modal).onclick=()=>{closeModal();resolve(null);};});
}

function catalogRequirementStatus(wiz,item) {
  const failures=[];
  if(item.capacity&&item.capacity.host&&availableCyberHosts(wiz,item).length<(item.capacity.hosts_required||1))failures.push(`${T('Requires available','Требуется доступный')} ${(item.capacity.hosts_required||1)}× ${item.capacity.host}`);
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
  const rowHtml=item=>{const duplicate=isForbiddenDuplicate(wiz,item),affordable=canAffordShopItem(wiz,item,tab),requirements=tab[0]==='chrome'?catalogRequirementStatus(wiz,item):[],disabled=duplicate||!affordable||requirements.length>0,suggested=tab[0]==='fashion'&&String(wiz.lifepath.clothing||'')&&[item.name,item.mechanics?.fashion_style].some(value=>String(value||'').toLowerCase().includes(String(wiz.lifepath.clothing).toLowerCase()));const compatible=(tab[0]==='ammo'||item.cat==='gun_upgrades')?ammoCompatibility(item,wiz):(item.cat==='vehicles_upgrades'&&wiz.gear.some(selected=>selected.cat==='vehicles')?[T('selected vehicle','выбранный транспорт')]:(item.cat==='programs'&&wiz.gear.some(selected=>selected.cat==='net_stuff'&&String(selected.name).toLowerCase().includes('cyberdeck'))?[T('selected Cyberdeck','выбранный Cyberdeck')]:[]));const compared=(wiz.compareItems||[]).includes(item.id);return `<article class="catalog-card ${disabled?'unaffordable':''} ${compatible.length?'compatible':''} ${suggested?'recommended':''}"><div class="catalog-card-main"><label class="compare-check"><input type="checkbox" data-compare-id="${esc(item.id)}" ${compared?'checked':''}> ${T('Compare','Сравнить')}</label><h4>${esc(item.variant_name||item.name)}${suggested?` <span class="tag recommended-tag">${T('Lifepath Style','Стиль Lifepath')}</span>`:''}</h4><div class="mechanic-chips">${itemMechanicChips(item)}${item.mechanics?.skill?(()=>{const meta=state.meta.skills.find(row=>row[1]===item.mechanics.skill),stat=meta&&meta[2],statValue=stat==='EMP'?(wizDerived().emp_cur??wiz.stats.EMP):wiz.stats[stat];return `<span class="chip character-aware"><b>${esc(item.mechanics.skill)} BASE</b> ${(num(statValue)||0)+(num(wiz.skills[item.mechanics.skill])||0)}</span>`;})():''}</div>${compatible.length?`<div class="compatibility-ok">✓ ${T('Compatible with selected loadout','Совместимо с выбранным снаряжением')}: ${compatible.map(esc).join(', ')}</div>`:''}${requirements.length?`<div class="requirement-fail">⛔ ${requirements.map(esc).join(' · ')}${item.capacity?.host?` <button class="btn-sm" data-show-foundation="${esc(item.capacity.host)}">${T('View Foundations','Показать Foundations')}</button>`:''}</div>`:''}<div class="small muted">${esc(item.source||'')}</div></div><div class="catalog-card-actions"><span class="price">${money(item.price)}</span><button class="info-btn" data-shop-info="${esc(item.variant_id||item.id)}">i</button><button class="btn-sm" data-shop-add="${esc(item.variant_id||item.id)}" ${disabled?'disabled':''}>＋</button></div></article>`;};
  box.innerHTML=items.length?groupedItemsHtml(items,rowHtml,shopCategoryLabel(tab)):`<div class="empty">${T('Nothing matches these filters.','Ничего не найдено.')}</div>`;
  requestAnimationFrame(()=>box.scrollTop=(wiz.scrolls||{})[scrollKey]||0);box.onscroll=()=>{wiz.scrolls[scrollKey]=box.scrollTop;};
  $$('[data-compare-id]',box).forEach(input=>input.onchange=()=>{wiz.compareItems=wiz.compareItems||[];if(input.checked&&!wiz.compareItems.includes(input.dataset.compareId)){if(wiz.compareItems.length>=3){input.checked=false;toast(T('Compare supports up to three items.','Можно сравнить не более трёх предметов.'),true);return;}wiz.compareItems.push(input.dataset.compareId);}if(!input.checked)wiz.compareItems=wiz.compareItems.filter(id=>id!==input.dataset.compareId);saveWizardDraft();const count=$('#compare-count');if(count)count.textContent=wiz.compareItems.length;});
  $$('[data-show-foundation]',box).forEach(btn=>btn.onclick=()=>{wiz.cyberFilter='foundation';wiz.shopQ=btn.dataset.showFoundation;renderWizard();});
  $$('[data-shop-info]',box).forEach(btn=>btn.onclick=()=>{const item=items.find(x=>(x.variant_id||x.id)===btn.dataset.shopInfo);if(item)showCreationItemInfo(item);});
  $$('[data-shop-add]',box).forEach(btn=>btn.onclick=async()=>{const item=items.find(x=>(x.variant_id||x.id)===btn.dataset.shopAdd);if(!item)return;const price=item.price||0;if(isForbiddenDuplicate(wiz,item)||!canAffordShopItem(wiz,item,tab))return;
    const shared={desc:item.desc||'',fields:item.fields||{},source:item.source||'',mechanics:item.mechanics||{},requirements:item.requirements||[],capacity:item.capacity||{}};
    if(tab[0]==='fashion'){const existing=wiz.fashion.find(x=>x.key===item.id);if(existing)existing.qty=(existing.qty||1)+1;else wiz.fashion.push({key:item.id,cat:item.cat,name:item.name,price,qty:1,type:itemVisibleType(item,'Fashion'),...shared});wiz.fashionCost+=price;}
    else if(tab[0]==='fashionware'){const existing=wiz.fashionware.find(x=>x.id===item.id);if(existing)existing.qty=(existing.qty||1)+1;else wiz.fashionware.push({id:item.id,name:item.name,hl:item.hl||0,price,qty:1,type:String(item.fields?.Type||'Fashionware'),...shared});wiz.fashionCost+=price;}
    else if(item.cat==='cyberware'){const hosts=availableCyberHosts(wiz,item),host=await chooseCyberHost(hosts,item);if((item.capacity||{}).host&&!host)return;const instance=`${item.id}:${Date.now()}:${Math.random().toString(16).slice(2)}`;wiz.cyberware.push({id:item.id,instance_id:instance,name:item.name,hl:item.hl||0,price,type:String(item.fields?.Type||'Cyberware'),host_instance:host?(Array.isArray(host)?(host[0].instance_id||host[0].id):(host.instance_id||host.id)):'',host_instances:host?(Array.isArray(host)?host.map(value=>value.instance_id||value.id):[host.instance_id||host.id]):[],...shared});wiz.chromeCost+=price;}
    else if(item.cat==='armor'){wiz.gear.push({key:item.variant_id,source_key:item.id,cat:'armor',name:item.name,display_name:item.variant_name,location:item.purchase_location,price,qty:1,sp:item.sp,penalties:{...(item.penalties||{})},armor_bundled:!!item.armor_bundled,type:itemVisibleType(item,'Armor'),...shared});wiz.gearCost+=price;}
    else{const existing=wiz.gear.find(x=>x.key===item.id);if(existing)existing.qty=(existing.qty||1)+1;else wiz.gear.push({key:item.id,cat:item.cat,name:item.name,price,qty:1,damage:item.damage||null,sp:item.sp,type:itemVisibleType(item,shopCategoryLabel(tab)),...shared});wiz.gearCost+=price;}
    renderWizard();toast(`${T('Added','Добавлено')}: ${item.variant_name||item.name}`);});
}

function roleBenefitItems(wiz){const out=[];if(wiz.role==='Exec')out.push({key:'role-exec-businesswear',name:'Businesswear (Teamwork)',type:'Role Benefit',qty:1,price:0,role_benefit:true,desc:'Corporate clothing supplied by Teamwork.'});if(wiz.role==='Nomad')for(const choice of (wiz.roleSetup.moto_choices||[]).filter(Boolean))out.push({key:'role-nomad-'+choice,name:choice,type:'Nomad Family Access',qty:1,price:0,role_benefit:true});return out;}
function equipmentWarnings(wiz){const warnings=[];const weapons=wiz.gear.filter(item=>item.cat==='guns'),ammo=wiz.gear.filter(item=>item.cat==='ammo');for(const weapon of weapons){const type=String(weapon.mechanics?.type||weapon.fields?.Type||'').toLowerCase();if(!ammo.some(item=>ammoCompatibility(item,wiz).includes(type)))warnings.push(`${weapon.name}: ${T('no compatible ammunition selected','не выбраны совместимые боеприпасы')}`);}if(!wiz.armor.body)warnings.push(T('No Body Armor equipped','Не надета броня для тела'));if(!wiz.armor.head)warnings.push(T('No Head Armor equipped','Не надета броня для головы'));return warnings;}
async function generateRandomOutfit(){const wiz=state.wizard;wiz._shopCache=wiz._shopCache||{};if(!wiz._shopCache.fashion){const response=await api('/api/items?'+new URLSearchParams({cat:'fashion',limit:500}));wiz._shopCache.fashion=response.items;}const preferred=String(wiz.outfitStyle||wiz.lifepath.clothing||'').toLowerCase();let pool=wiz._shopCache.fashion.filter(item=>item.price!=null);const matching=pool.filter(item=>item.name.toLowerCase().includes(preferred)||String(item.mechanics?.fashion_style||'').toLowerCase()===preferred);if(matching.length)pool=matching;pool=[...pool].sort(()=>Math.random()-.5);const picked=[];let spent=0;for(const item of pool){if(picked.length>=6)break;if(spent+(item.price||0)<=FASHION_BUDGET){picked.push(item);spent+=item.price||0;}}if(!picked.length){toast(T('No affordable outfit found.','Не удалось подобрать комплект.'),true);return;}if(!confirm(`${T('Replace current Fashion selection with','Заменить выбранную одежду на')} ${picked.map(x=>x.name).join(', ')}?`))return;wiz.fashion=picked.map(item=>({key:item.id,cat:'fashion',name:item.name,price:item.price,qty:1,type:itemVisibleType(item,'Fashion'),desc:item.desc||'',fields:item.fields||{},source:item.source||'',mechanics:item.mechanics||{}}));wiz.fashionCost=spent+wiz.fashionware.reduce((sum,item)=>sum+(item.price||0)*(item.qty||1),0);renderWizard();}
function cartSectionHtml(title,items){return items.length?`<section class="catalog-group"><h4 class="catalog-type">${esc(title)} <span>${items.length}</span></h4>${items.join('')}</section>`:'';}
function combinedCartHtml(wiz){const rows=[];for(const item of roleBenefitItems(wiz))rows.push({type:item.type,html:`<div class="inv-row role-benefit"><span class="iname">🎁 ${esc(item.name)}</span><span class="tag">Role Benefit</span><span class="price">${money(0)}</span></div>`});
  const seen=new Set();wiz.cyberware.forEach((item,index)=>{if(seen.has(item.id))return;seen.add(item.id);const qty=wiz.cyberware.filter(x=>x.id===item.id).length;rows.push({type:itemVisibleType(item,'Cyberware'),html:`<div class="inv-row"><span class="iname">🦾 ${esc(item.name)}</span>${quantityControl('chrome',index,qty,String(item.name).toLowerCase()!=='neuroport'&&!(item.capacity||{}).unique&&(!(item.capacity||{}).host||availableCyberHosts(wiz,item).length>0))}<span class="hl-badge">HL ${(item.hl||0)*qty}</span><span class="price">${money((item.price||0)*qty)}</span><button class="info-btn" data-cart-info="chrome|${index}">i</button></div>`});});
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

function cyberSlotErrors(wiz) {
  const errors=[];
  for(const item of wiz.cyberware){if(item.capacity&&item.capacity.host&&!item.host_instance)errors.push(`${item.name}: ${T('no compatible cyberware host','нет совместимого host')}`);}
  const hosts=[...wiz.cyberware];if(wiz.freeNeuroport)hosts.push({instance_id:'creation-neuroport',name:'Neuroport',capacity:{slots_total:5}});
  for(const host of hosts){const id=host.instance_id||host.id,total=num(host.capacity&&host.capacity.slots_total)||0;if(!total)continue;const used=wiz.cyberware.filter(item=>cyberHostIds(item).includes(id)).reduce((sum,item)=>sum+(num(item.capacity&&item.capacity.slots_used)||0),0);if(used>total)errors.push(`${host.name}: Option Slots ${used}/${total}`);}
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
  const children = new Map();
  items.forEach((item,index) => { if (item.host_instance) { if (!children.has(item.host_instance)) children.set(item.host_instance,[]); children.get(item.host_instance).push([item,index]); } });
  const roots = items.map((item,index)=>[item,index]).filter(([item])=>!item.host_instance);
  const row = (item,index,nested) => { const id=item.instance_id||item.key||item.id,total=num(item.capacity?.slots_total)||0,used=(children.get(id)||[]).reduce((sum,[child])=>sum+(num(child.capacity?.slots_used)||0),0);return `<div class="cyber-tree-row ${nested?'nested':''}"><span class="iname">${nested?'↳ ':''}${esc(item.name)}</span>${total?`<span class="chip">Slots ${used}/${total}</span>`:''}${item.capacity?.slots_used?`<span class="chip">Uses ${item.capacity.slots_used}</span>`:''}<span class="hl-badge">HL ${item.hl||0}</span><button class="info-btn" data-owned-chrome="${index}">i</button></div>${(children.get(id)||[]).map(([child,childIndex])=>row(child,childIndex,true)).join('')}`; };
  return roots.map(([item,index])=>row(item,index,false)).join('');
}

function wizStepSummaryHtml() {
  const wiz=state.wizard,c=wizChar(),d=wizDerived(),errors=wizValidationErrors(),warnings=equipmentWarnings(wiz);
  if(d.emp_cur!=null&&d.emp_cur<=2)warnings.push(T('EMP is 2 or lower','EMP не выше 2'));
  if(wiz.fashionCost < FASHION_BUDGET) warnings.push(`${T('Unused Style Budget will be lost','Неиспользованный Style Budget сгорит')}: ${money(FASHION_BUDGET-wiz.fashionCost)}`);
  for(const [base] of SUB_SKILL_BASES){const free=wizSubFree(base);if(free)warnings.push(`${base}: ${free} ${T('parent levels remain unallocated','уровней parent-pool не распределено')}`);}
  const slotHosts=[...wiz.cyberware];if(wiz.freeNeuroport)slotHosts.push({instance_id:'creation-neuroport',name:'Neuroport',capacity:{slots_total:5}});for(const host of slotHosts){const total=num(host.capacity?.slots_total)||0;if(!total)continue;const used=wiz.cyberware.filter(item=>cyberHostIds(item).includes(host.instance_id||host.id)).reduce((sum,item)=>sum+(num(item.capacity?.slots_used)||0),0);if(total>used)warnings.push(`${host.name}: ${total-used} Option Slots ${T('unused','свободно')}`);}
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
      const hosts = availableCyberHosts(wiz, sample);
      if ((sample.capacity || {}).host && !hosts.length) { toast(T('No compatible host has enough Option Slots.','У совместимых hosts нет свободных Option Slots.'), true); return; }
      if (!canAffordCreationItem(wiz, { cat: 'cyberware' }, sample.price || 0)) { toast(T('Not enough Main Budget.','Недостаточно основного бюджета.'), true); return; }
      const host = await chooseCyberHost(hosts, sample); if ((sample.capacity || {}).host && !host) return;
      wiz.cyberware.push({ ...sample, instance_id: `${sample.id}:${Date.now()}:${Math.random().toString(16).slice(2)}`, host_instance: host ? (Array.isArray(host) ? (host[0].instance_id || host[0].id) : (host.instance_id || host.id)) : '', host_instances: host ? (Array.isArray(host) ? host.map(value => value.instance_id || value.id) : [host.instance_id || host.id]) : [] }); wiz.chromeCost += sample.price || 0;
    } else {
      const removeIndex = wiz.cyberware.findIndex(x => x.id === sample.id);
      const removed = wiz.cyberware[removeIndex];
      if (removed) {
        const hostId = removed.instance_id || removed.id;
        const dependents = wiz.cyberware.filter(item => cyberHostIds(item).includes(hostId));
        if (dependents.length && !window.confirm(T(`Remove ${removed.name} and ${dependents.length} installed options?`,`Удалить ${removed.name} и установленные опции (${dependents.length})?`))) return;
        const removedIds = new Set([hostId]);
        wiz.cyberware = wiz.cyberware.filter(item => item !== removed && !removedIds.has(item.host_instance));
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

/* ============================== лист персонажа (просмотр) ============================== */

async function sheetResource(characterId, resource, value) {
  const action=value==='reset'?'reset':'delta';
  try { await api(`/api/characters/${characterId}/resource`,{method:'POST',body:{resource,action,value:value==='reset'?0:Number(value)}}); await viewSheet(characterId); }
  catch(e){toast(e.message,true);}
}
function improvementCost(kind,subject,ch){
  if(kind==='skill'){const current=num((ch.skills||{})[subject])||0,meta=state.meta.skills.find(row=>row[1]===subject);return (current+1)*(meta&&meta[3]?40:20);}
  if(kind==='parent'){const current=num((ch.skill_pools||{})[subject])||0,meta=state.meta.skills.find(row=>row[1]===subject);return (current+1)*(meta&&meta[3]?40:20);}
  if(kind==='role'){const role=(ch.roles||[]).find(row=>row.name===subject);return ((role?role.rank:0)+1)*60;}return 0;
}
async function progressionRoleSetup(role, rank, existing) {
  existing=JSON.parse(JSON.stringify(existing||{}));
  if(!['Tech','Medtech','Nomad','Exec'].includes(role))return existing;
  return new Promise(resolve=>{let content='';
    if(role==='Tech')content=`<p>Allocate ${rank*2} Maker Points; maximum ${rank} per specialty.</p><div class="grid cols-4">${[['field','Field'],['upgrade','Upgrade'],['fabrication','Fabrication'],['invention','Invention']].map(([key,label])=>`<label class="f"><span>${label}</span><input type="number" min="0" max="${rank}" data-progress-setup="${key}" value="${num(existing[key])||0}"></label>`).join('')}</div>`;
    if(role==='Medtech')content=`<p>Allocate ${rank} Medicine Points.</p><div class="grid cols-3">${[['surgery','Surgery'],['pharma','Pharmaceuticals'],['cryo','Cryosystems']].map(([key,label])=>`<label class="f"><span>${label}</span><input type="number" min="0" max="${rank}" data-progress-setup="${key}" value="${num(existing[key])||0}"></label>`).join('')}</div>`;
    if(role==='Nomad'){const choices=existing.moto_choices||[];content=`<p>Complete ${rank} sequential Moto choices.</p>${Array.from({length:rank},(_,i)=>`<label class="f"><span>Rank ${i+1}</span><select data-progress-moto="${i}"><option value="">Choose…</option>${NOMAD_MOTO_CHOICES.filter(([,access])=>access<=i+1).map(([name,access])=>`<option value="${esc(name)}" ${choices[i]===name?'selected':''}>${esc(name)} · Access ${access}</option>`).join('')}</select></label>`).join('')}`;}
    if(role==='Exec')content=`<p>Select at least one Team Member.</p><select id="progress-exec"><option value="">Choose…</option>${EXEC_TEAM_MEMBERS.map(([en])=>`<option value="${en}" ${(existing.team_members||[existing.team_member]).includes(en)?'selected':''}>${en}</option>`).join('')}</select>`;
    const modal=openModal(`<h2>${role} · Rank ${rank} Setup</h2>${content}<div id="progress-setup-error" class="warn-text mt"></div><div class="row mt"><button id="progress-setup-cancel">Cancel</button><button id="progress-setup-ok" class="btn-primary">Continue</button></div>`);
    $('#progress-setup-cancel',modal).onclick=()=>{closeModal();resolve(null);};$('#progress-setup-ok',modal).onclick=()=>{let setup={...existing},valid=true;if(role==='Tech'||role==='Medtech'){$$('[data-progress-setup]',modal).forEach(input=>setup[input.dataset.progressSetup]=Number(input.value)||0);const keys=role==='Tech'?['field','upgrade','fabrication','invention']:['surgery','pharma','cryo'],needed=role==='Tech'?rank*2:rank;valid=keys.reduce((sum,key)=>sum+setup[key],0)===needed;}if(role==='Nomad'){setup.moto_choices=Array.from($$('[data-progress-moto]',modal)).map(input=>input.value);valid=setup.moto_choices.length===rank&&setup.moto_choices.every(Boolean);}if(role==='Exec'){const value=$('#progress-exec',modal).value;setup.team_member=value;setup.team_members=value?[value]:[];valid=!!value;}if(!valid){$('#progress-setup-error',modal).textContent='Complete the required Rank setup.';return;}closeModal();resolve(setup);};
  });
}

function openIpAdjustment(characterId, onDone) { const modal=openModal(`<h2>Adjust Improvement Points</h2><label class="f"><span>Amount (+ or −)</span><input id="quick-ip-amount" type="number"></label><label class="f"><span>Reason *</span><input id="quick-ip-reason" maxlength="500"></label><button class="btn-primary" id="quick-ip-save">Record immutable entry</button>`);$('#quick-ip-save',modal).onclick=async()=>{try{await api(`/api/characters/${characterId}/ip`,{method:'POST',body:{amount:Number($('#quick-ip-amount',modal).value),reason:$('#quick-ip-reason',modal).value}});closeModal();onDone();}catch(e){toast(e.message,true);}}; }

async function openImprovementModal(characterPayload){
  const ch=characterPayload.data,id=characterPayload.id,roles=ch.roles||[],active=roles.find(role=>role.name===ch.active_role),canMulticlass=!active||active.rank>=4;
  const ordinary=state.meta.skills.filter(row=>!WIZ_SUB_HIDDEN.has(row[1]));
  const modal=openModal(`<h2>Improvement</h2><div class="ip-summary"><b>${ch.ip_available||0} IP available</b><span>Total earned ${ch.ip_total_earned||0}</span><span>Total spent ${ch.ip_total_spent||0}</span></div><details class="creation-section" open><summary>Adjust IP</summary><div class="section-body grid cols-3"><input id="ip-amount" type="number" placeholder="+80 or -20"><input id="ip-reason" placeholder="Reason" maxlength="500"><button id="ip-adjust">Record Adjustment</button></div></details><details class="creation-section" open><summary>Skills</summary><div class="section-body improvement-list">${ordinary.map(row=>{const current=num((ch.skills||{})[row[1]])||0,cost=improvementCost('skill',row[1],ch);return `<div><span><b>${esc(row[1])}</b> ${current} → ${current+1}</span><button data-improve="skill|${esc(row[1])}" ${current>=10||cost>(ch.ip_available||0)?'disabled':''}>${cost} IP</button></div>`;}).join('')}</div></details><details class="creation-section"><summary>Specialized Parent Pools</summary><div class="section-body improvement-list">${SUB_SKILL_BASES.map(([base])=>{const current=num((ch.skill_pools||{})[base])||0,cost=improvementCost('parent',base,ch);return `<div><span><b>${esc(base)} Pool</b> ${current} → ${current+1}</span><button data-improve="parent|${esc(base)}" ${cost>(ch.ip_available||0)?'disabled':''}>${cost} IP</button></div>`;}).join('')}</div></details><details class="creation-section"><summary>Allocate Specializations</summary><div class="section-body">${SUB_SKILL_BASES.map(([base])=>{const pool=num((ch.skill_pools||{})[base])||0,children=specializedChildren(ch,base),allocated=children.reduce((sum,child)=>sum+paidSpecializationLevel(ch,base,child),0);return `<div class="panel mb"><div class="row" style="justify-content:space-between"><b>${esc(base)} Pool ${pool}</b><span>Allocated ${allocated} · Free ${Math.max(0,pool-allocated)}</span></div>${children.map(child=>`<div class="inv-row"><span class="iname">${esc(child.name)}</span><button data-spec-change="${esc(base)}|${esc(child.name)}|-1" ${child.lvl<=(base==='Language'&&child.name===ch.native_language?4:0)?'disabled':''}>−</button><b>${child.lvl}</b><button data-spec-change="${esc(base)}|${esc(child.name)}|1" ${child.lvl>=10||allocated>=pool?'disabled':''}>＋</button></div>`).join('')}<div class="row"><input data-new-spec="${esc(base)}" placeholder="New specialization"><button data-add-spec="${esc(base)}" ${allocated>=pool?'disabled':''}>Add at Level 1</button></div></div>`;}).join('')}</div></details><details class="creation-section"><summary>Roles & Multiclass</summary><div class="section-body improvement-list">${roles.map(role=>{const cost=(role.rank+1)*60;return `<div><span><b>${esc(role.name)}</b> Rank ${role.rank}${role.name===ch.active_role?' · Active':''}</span><span class="row"><button data-improve="role|${role.name}" ${role.name!==ch.active_role||role.rank>=10||cost>(ch.ip_available||0)?'disabled':''}>Rank ${role.rank+1} · ${cost} IP</button>${role.name!==ch.active_role&&canMulticlass?`<button data-improve="activate_role|${role.name}">Make Active</button>`:''}</span></div>`;}).join('')}${canMulticlass?Object.keys(state.meta.roles).filter(name=>!roles.some(role=>role.name===name)).map(name=>`<div><span><b>New Role: ${name}</b> Rank 1</span><button data-improve="role|${name}" ${(ch.ip_available||0)<60?'disabled':''}>60 IP</button></div>`).join(''):`<p class="muted">Active Role must reach Rank 4 before multiclassing.</p>`}</div></details><button id="ip-history">View immutable IP History</button>`,true);
  $('#ip-adjust',modal).onclick=async()=>{try{const result=await api(`/api/characters/${id}/ip`,{method:'POST',body:{amount:Number($('#ip-amount',modal).value),reason:$('#ip-reason',modal).value}});closeModal();toast('IP ledger updated.');viewSheet(id);}catch(e){toast(e.message,true);}};
  $$('[data-improve]',modal).forEach(button=>button.onclick=async()=>{const [kind,subject]=button.dataset.improve.split('|');const existingRole=(ch.roles||[]).find(role=>role.name===subject),targetRank=kind==='role'?(existingRole?existingRole.rank+1:1):0;let setup=null;if(kind==='role'){setup=await progressionRoleSetup(subject,targetRank,existingRole&&existingRole.setup);if(setup===null)return;}if(!confirm(`Spend ${improvementCost(kind,subject,ch)} IP to improve ${subject}?`))return;try{await api(`/api/characters/${id}/improve`,{method:'POST',body:{kind,subject,setup}});closeModal();toast('Improvement purchased.');viewSheet(id);}catch(e){toast(e.message,true);}});
  $$('[data-spec-change]',modal).forEach(button=>button.onclick=async()=>{const [parent,name,delta]=button.dataset.specChange.split('|');try{await api(`/api/characters/${id}/specialization`,{method:'POST',body:{parent,name,delta:Number(delta)}});closeModal();viewSheet(id);}catch(e){toast(e.message,true);}});$$('[data-add-spec]',modal).forEach(button=>button.onclick=async()=>{const parent=button.dataset.addSpec,input=$(`[data-new-spec="${parent}"]`,modal),name=input&&input.value.trim();if(!name)return;try{await api(`/api/characters/${id}/specialization`,{method:'POST',body:{parent,name,delta:1}});closeModal();viewSheet(id);}catch(e){toast(e.message,true);}});
  $('#ip-history',modal).onclick=async()=>{try{const data=await api(`/api/characters/${id}/ip`);openModal(`<h2>IP History</h2>${data.entries.length?data.entries.map(entry=>`<div class="ledger-row"><b class="${entry.amount>=0?'green':'warn-text'}">${entry.amount>=0?'+':''}${entry.amount} IP</b><span>${esc(entry.reason)}</span><small>${esc(entry.actor)} · ${new Date(entry.created*1000).toLocaleString()}</small></div>`).join(''):'<div class="empty">No entries.</div>'}`,true);}catch(e){toast(e.message,true);}};
}

function combatSheetHtml(ch, derived, mine) {
  const weapons=(ch.inventory||[]).filter(item=>['guns','melee'].includes(item.cat)),states=ch.weapon_state||{},modifications=derived.modifications||[];
  const weaponRows=weapons.map(item=>{const key=String(item.instance_id||item.key||item.source_key||item.name),state=states[key]||{},skill=item.mechanics?.skill||'',meta=stateMetaSkill(skill),stat=meta&&meta[2],statValue=stat==='EMP'?(derived.emp_cur??ch.stats.EMP):(ch.stats||{})[stat],rawBase=(num(statValue)||0)+(num((ch.skills||{})[skill])||0),skillBase=derived.effects?.skills?.[skill]?.effective_check_base??rawBase,weaponEffective=derived.effective_weapons?.[item.instance_id]||{base:item.mechanics||{},effective:item.mechanics||{},attack_modifier:0,sources:[]},base=skillBase+(num(weaponEffective.attack_modifier)||0),damage=weaponEffective.effective?.damage||item.mechanics?.damage,installed=modifications.filter(mod=>mod.host_instance_id===item.instance_id),slotsUsed=weaponEffective.slots_used??installed.reduce((sum,mod)=>sum+(num(mod.slots_used)||0),0),slotsTotal=weaponEffective.slots_total??3,magBase=num(weaponEffective.base?.magazine)||0,magEffective=num(weaponEffective.effective?.magazine)||0,concealBase=weaponEffective.base?.concealable,concealEffective=weaponEffective.effective?.concealable,rangeBase=weaponEffective.base?.range_table,rangeEffective=weaponEffective.effective?.range_table,alternateHtml=(weaponEffective.alternate_attacks||[]).map(profile=>{const match=String(profile.damage||'').match(/(\d+)d(\d+)/),profileBase=derived.effects?.skills?.[profile.skill]?.effective_check_base??((num((ch.stats||{})[stateMetaSkill(profile.skill)?.[2]])||0)+(num((ch.skills||{})[profile.skill])||0)),resource=profile.state||{};return `<div class="alternate-weapon-profile"><div><b>${esc(APP_I18N.current()==='ru'?profile.label_ru:profile.label_en)}</b><span>${esc(profile.skill)} BASE ${profileBase} · ${esc(profile.damage)} · ROF ${profile.rof} · Hands ${profile.hands_required}</span></div><div class="weapon-controls"><b>Mag ${resource.magazine||0}/${resource.magazine_max||profile.magazine}</b><span>Reserve ${resource.reserve||0}</span>${mine?`<button data-mod-weapon-action="${profile.modification_id}|fire" ${(resource.magazine||0)<=0?'disabled':''}>Fire</button><button data-mod-weapon-action="${profile.modification_id}|reload" ${(resource.magazine||0)>=(resource.magazine_max||profile.magazine)||(resource.reserve||0)<=0?'disabled':''}>Reload</button><button data-attack-roll="${esc(profile.label_en)}|${profileBase}">Attack 🎲</button>`:''}${match?`<button data-damage-roll="${esc(profile.label_en)}|${match[1]}|${match[2]}|1">Damage 🎲</button>`:''}</div></div>`;}).join(''),autofireHtml=(weaponEffective.autofire_profiles||[]).map(profile=>{const autofireBase=derived.effects?.skills?.Autofire?.effective_check_base??((num((ch.stats||{}).REF)||0)+(num((ch.skills||{}).Autofire)||0));return `<div class="alternate-weapon-profile"><div><b>${esc(APP_I18N.current()==='ru'?profile.label_ru:profile.label_en)}</b><span>Autofire BASE ${autofireBase} · ${esc(profile.table)} · Max ×${profile.multiplier} · Ammo ${profile.ammo_cost}${profile.suppressive_fire?' · Suppressive Fire':''}</span></div>${mine?`<div class="weapon-controls"><button data-attack-roll="${esc(profile.label_en)}|${autofireBase}">Autofire Check 🎲</button></div>`:''}</div>`;}).join('');return `<article class="weapon-sheet-card"><div><h3>${esc(item.custom_name||item.name)}</h3><div class="mechanic-chips">${itemMechanicChips(item)}${skill?`<span class="chip">${esc(skill)} BASE ${rawBase!==base?`${rawBase}→${base}`:base}</span>`:''}${weaponEffective.attack_modifier?`<span class="chip effect-auto">Attack ${weaponEffective.attack_modifier>0?'+':''}${weaponEffective.attack_modifier}</span>`:''}${(weaponEffective.tags||[]).map(tag=>`<span class="tag effect-auto">${esc(tag)}</span>`).join('')}${magBase&&magEffective!==magBase?`<span class="chip effect-auto">Mag ${magBase}→${magEffective}</span>`:''}${concealEffective&&concealEffective!==concealBase?`<span class="chip effect-auto">Conceal ${esc(concealBase)}→${esc(concealEffective)}</span>`:''}${rangeEffective&&rangeEffective!==rangeBase?`<span class="chip effect-auto">Range ${esc(rangeBase)}→${esc(rangeEffective)}</span>`:''}${item.cat==='guns'?`<span class="chip">Slots ${slotsUsed}/${slotsTotal}</span>`:''}${installed.map(mod=>`<span class="chip">🔧 ${esc(mod.configuration?.upgrade_name||'Upgrade')}</span>`).join('')}</div>${(weaponEffective.sources||[]).map(source=>`<div class="small ${source.active?'green-text':'warn-text'}">${source.automated?T('AUTOMATED','АВТОМАТИЧЕСКИ'):T('MANUAL','ВРУЧНУЮ')} · ${esc(APP_I18N.current()==='ru'?source.label_ru:source.label_en)}${source.requirements_met===false?` · ${esc(APP_I18N.current()==='ru'?source.requirement_label_ru:source.requirement_label_en)}`:''}</div>${(source.manual_rules||[]).map(rule=>`<div class="small effect-manual-text">${esc(APP_I18N.current()==='ru'?rule.text_ru:rule.text_en)} · ${esc(rule.source||'')}</div>`).join('')}`).join('')}</div><div class="weapon-controls">${state.magazine_max?`<b>Mag ${state.magazine}/${magEffective||state.magazine_max}</b><span>Reserve ${state.reserve||0}</span>${mine?`<button data-weapon-action="${esc(key)}|fire">Fire</button><button data-weapon-action="${esc(key)}|reload">Reload</button>`:''}`:''}${mine&&skill?`<button data-attack-roll="${esc(item.custom_name||item.name)}|${base}">Attack 🎲</button>`:''}${damage?`<button data-damage-roll="${esc(item.custom_name||item.name)}|${damage.dice}|${damage.sides}|${damage.multiplier||1}">Damage 🎲</button>`:''}${mine&&item.cat==='guns'?`<button data-manage-upgrades="${item.instance_id}">${T('Manage Upgrades','Управление апгрейдами')}</button>`:''}</div>${alternateHtml}${autofireHtml}</article>`;}).join('');
  const armor=['head','body','shield'].map(location=>{const piece=(ch.armor||{})[location];if(!piece)return '';return `<div class="armor-resource"><b>${location[0].toUpperCase()+location.slice(1)} · ${esc(piece.name)}</b><span>${piece.current??piece.sp??piece.sdp} / ${piece.maximum??piece.sp??piece.sdp} ${location==='shield'?'SDP':'SP'}</span>${mine?`<div><button data-armor-action="${location}|-1">Ablate</button><button data-armor-action="${location}|1">Repair 1</button><button data-armor-action="${location}|reset">Reset</button></div>`:''}</div>`;}).join('');
  return `<div class="combat-sheet-grid"><section><h2>Weapons</h2>${weaponRows||'<div class="empty">No weapons.</div>'}</section><section><h2>Armor</h2>${armor||'<div class="empty">No equipped armor.</div>'}</section></div>`;
}
function stateMetaSkill(name){return (state.meta.skills||[]).find(row=>row[1]===name);}
function rollDamage(name,dice,sides,multiplier){const rolls=Array.from({length:dice},()=>1+Math.floor(Math.random()*sides)),total=rolls.reduce((a,b)=>a+b,0)*multiplier;openModal(`<h2>💥 ${esc(name)}</h2><div class="roll-result"><b>${total}</b><span>${rolls.join(' + ')}${multiplier>1?' × '+multiplier:''}</span></div>`);}
function equipModeLabel(mode){return ({held:T('Held','В руках'),worn:T('Worn','Надето'),ready:T('Ready','Наготове'),workspace:T('Workspace','Рабочее место'),mounted:T('Mounted','Закреплено')})[mode]||mode;}
async function performSheetItemAction(character,item,action,extra={}){
  try{
    const result=await api(`/api/characters/${character.id}/items/${item.instance_id}/action`,{method:'POST',body:{revision:character.revision,action,...extra}});
    await viewSheet(character.id);toast(T('Item state updated.','Состояние предмета обновлено.'));
    if((result.created_effects||[]).length||(result.manual_rules||[]).length){openModal(`<h2>${T('Use Resolution','Результат использования')}</h2><div class="panel accent mb"><b>${esc(item.custom_name||item.name)}</b>${(result.created_effects||[]).map(effect=>`<div class="inv-row"><span class="tag effect-auto">${T('AUTOMATED EFFECT','АВТОМАТИЧЕСКИЙ ЭФФЕКТ')}</span><span class="iname">${esc(effect.label)}</span><span>${esc(effectTargetLabel(effect.definition?.target))} ${effect.definition?.value>0?'+':''}${esc(effect.definition?.value??'')} · ${esc(effectDurationLabel(effect))}</span></div>`).join('')||''}</div>${(result.manual_rules||[]).map(rule=>`<div class="panel mb"><span class="tag effect-manual">${T('MANUAL RULE','РУЧНОЕ ПРАВИЛО')}</span><p>${esc(APP_I18N.current()==='ru'?rule.text_ru:rule.text_en)}</p><small>${esc(rule.source||'')}</small></div>`).join('')}${result.effect?.text?`<details><summary>${T('Full item description','Полное описание предмета')}</summary><p class="preserve-lines">${esc(result.effect.text)}</p></details>`:''}`,true);}else if(result.effect){openModal(`<h2>${T('Manual Use Effect','Ручной эффект использования')}</h2><div class="panel accent"><b>${esc(item.custom_name||item.name)}</b><p class="preserve-lines">${esc(result.effect.text||T('Resolve using the item description.','Примените эффект по описанию предмета.'))}</p>${result.effect.manual_resolution_required?`<span class="tag">${T('MANUAL RESOLUTION','РУЧНОЕ ПРИМЕНЕНИЕ')}</span>`:''}</div>`);}
  }catch(error){toast(error.message,true);}
}
function chooseEquipMode(character,item){const modes=item.equip_modes||['ready'];if(modes.length===1){performSheetItemAction(character,item,'equip',{mode:modes[0]});return;}const modal=openModal(`<h2>${T('Equip','Экипировать')} · ${esc(item.custom_name||item.name)}</h2><p class="small muted">${T('Choose how this item is prepared. Held gear may occupy a hand.','Выберите способ подготовки. Режим Held может занимать руку.')}</p><div class="choice-card-grid">${modes.map(mode=>`<button class="choice-card" data-equip-mode="${esc(mode)}"><b>${esc(equipModeLabel(mode))}</b><span>${mode==='held'?T('Uses a hand','Занимает руку'):T('No hand required','Не занимает руку')}</span></button>`).join('')}</div><button id="equip-cancel" class="mt">${T('Cancel','Отмена')}</button>`);$$('[data-equip-mode]',modal).forEach(button=>button.onclick=()=>{const mode=button.dataset.equipMode;closeModal();performSheetItemAction(character,item,'equip',{mode});});$('#equip-cancel',modal).onclick=closeModal;}
async function openWeaponUpgradeManager(character,hostInstanceId){try{const data=await api(`/api/characters/${character.id}/modifications`),host=data.hosts.find(item=>item.instance_id===hostInstanceId);if(!host){toast(T('Weapon host not found.','Оружие-host не найдено.'),true);return;}const installed=data.modifications.filter(item=>item.host_instance_id===hostInstanceId),available=data.upgrades.filter(item=>item.state==='carried'),modal=openModal(`<h2>${T('Manage Upgrades','Управление апгрейдами')} · ${esc(host.name)}</h2><div class="panel accent mb"><b>${T('Attachment Slots','Слоты модификаций')}: ${host.slots_used}/${host.slots_total}</b><div class="chips mt">${Object.entries(host.slot_pools||{}).map(([name,pool])=>`<span class="chip">${esc(name)} ${pool.used}/${pool.total}</span>`).join('')}</div><p class="small muted">${esc(host.weapon_type||'Weapon')} · ${esc(host.skill||'—')}${host.exotic?' · EXOTIC':''}</p></div><h3>${T('Installed','Установлено')}</h3>${installed.length?installed.map(mod=>`<div class="inv-row"><span class="iname">${esc(mod.upgrade_name||'Upgrade')}</span><span class="chip">Slots ${mod.slots_used}</span>${mod.permanent?`<span class="tag">${T('PERMANENT','НЕСЪЁМНЫЙ')}</span>`:`<button class="btn-sm" data-remove-mod="${mod.modification_id}">${T('Remove','Снять')}</button>`}</div>`).join(''):`<div class="empty small">${T('No installed upgrades.','Нет установленных апгрейдов.')}</div>`}<h3 class="mt">${T('Available in Inventory','Доступно в Inventory')}</h3>${available.length?available.map(upgrade=>{const compatibility=upgrade.compatibility[hostInstanceId]||{},blocked=!compatibility.allowed;return `<article class="panel mb ${blocked?'unaffordable':''}"><div class="row" style="justify-content:space-between"><b>${esc(upgrade.name)}</b><span class="chip">${T('Slots','Слоты')} ${upgrade.slots_used}</span></div><p class="small muted">${esc(upgrade.compatibility_text||'')}</p>${compatibility.reasons?.length?`<div class="warn-text small">${compatibility.reasons.map(esc).join(' · ')}</div>`:''}${compatibility.manual_resolution_required?`<div class="small warn-text">${T('MANUAL COMPATIBILITY CHECK REQUIRED','ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА СОВМЕСТИМОСТИ')}</div>`:''}${(upgrade.configuration_by_host?.[hostInstanceId]||upgrade.configuration_schemas||[]).map(schema=>`<label class="f mt"><span>${esc(APP_I18N.current()==='ru'?schema.label_ru:schema.label_en)}</span><select data-upgrade-config="${upgrade.instance_id}|${schema.key}"><option value="">${T('Choose…','Выберите…')}</option>${schema.choices.map(choice=>`<option value="${choice.value}">${esc(APP_I18N.current()==='ru'?choice.label_ru:choice.label_en)}</option>`).join('')}</select></label>`).join('')}<button class="btn-sm mt" data-install-upgrade="${upgrade.instance_id}" ${blocked?'disabled':''}>${T('Install','Установить')} · ${compatibility.slot_pool?esc(compatibility.slot_pool)+' '+compatibility.slot_pool_after+'/'+compatibility.slot_pool_total:compatibility.slots_after+'/'+compatibility.slots_total}</button></article>`;}).join(''):`<div class="empty small">${T('No weapon upgrades in Inventory.','В Inventory нет апгрейдов оружия.')}</div>`}<button id="upgrade-close" class="mt">${T('Close','Закрыть')}</button>`,true);$('#upgrade-close',modal).onclick=closeModal;$$('[data-install-upgrade]',modal).forEach(button=>button.onclick=async()=>{const upgrade=data.upgrades.find(item=>item.instance_id===button.dataset.installUpgrade),compatibility=upgrade.compatibility[hostInstanceId],reason=prompt(T('Installation reason / source','Причина / источник установки'),T('Installed from Character Inventory','Установлено из Inventory персонажа'))||'';if(reason.trim().length<3)return;let manualConfirm=false;if(compatibility.manual_resolution_required){manualConfirm=confirm(T('This compatibility rule needs manual resolution. Confirm installation under Trust + Audit?','Это сложное правило совместимости требует ручной проверки. Подтвердить установку через Trust + Audit?'));if(!manualConfirm)return;}const configuration={};for(const schema of upgrade.configuration_by_host?.[hostInstanceId]||upgrade.configuration_schemas||[]){const input=$(`[data-upgrade-config="${upgrade.instance_id}|${schema.key}"]`,modal),value=input?.value||'';if(schema.required&&!value){toast(T('Choose the required upgrade configuration.','Выберите обязательную конфигурацию upgrade.'),true);return;}if(value)configuration[schema.key]=value;}button.disabled=true;try{await api(`/api/characters/${character.id}/modifications`,{method:'POST',body:{revision:data.revision,host_instance_id:hostInstanceId,upgrade_instance_id:upgrade.instance_id,manual_confirm:manualConfirm,configuration,reason}});closeModal();toast(T('Upgrade installed.','Апгрейд установлен.'));viewSheet(character.id);}catch(error){button.disabled=false;toast(error.message,true);}});$$('[data-remove-mod]',modal).forEach(button=>button.onclick=async()=>{const reason=prompt(T('Removal reason','Причина снятия'),T('Removed from host','Снято с host'))||'';if(reason.trim().length<3)return;button.disabled=true;try{await api(`/api/characters/${character.id}/modifications/${button.dataset.removeMod}/action`,{method:'POST',body:{revision:data.revision,action:'remove',reason}});closeModal();toast(T('Upgrade removed.','Апгрейд снят.'));viewSheet(character.id);}catch(error){button.disabled=false;toast(error.message,true);}});}catch(error){toast(error.message,true);}}
function effectTargetLabel(target){return String(target||'').replace(/^character\.stat\./,'STAT ').replace(/^skill\./,'').replace(/\.check$/,' Check');}
function effectDurationLabel(effect){if(effect.duration_type==='real_time')return effect.status==='expired'?T('Expired','Истёк'):`${Math.ceil((effect.remaining_seconds||0)/60)} min`;if(effect.duration_type==='campaign_time'){const minutes=Number(effect.context?.campaign_minutes)||0,label=minutes%60===0?`${minutes/60} h`:`${minutes} min`;return `${label} ${T('campaign time','игрового времени')} · ${T('manual clock','ручной отсчёт')}`;}if(effect.duration_type==='rounds')return `${effect.remaining_rounds||0} ${T('rounds','раундов')} · ${T('manual tick','ручной отсчёт')}`;return T('Until manually disabled','До ручного отключения');}
async function performEffectAction(character,effect,action){if(action==='archive'&&!confirm(T('Archive this effect instance?','Архивировать этот эффект?')))return;try{await api(`/api/characters/${character.id}/effects/${effect.effect_id}/action`,{method:'POST',body:{revision:character.revision,action}});toast(T('Effect updated.','Эффект обновлён.'));viewSheet(character.id);}catch(error){toast(error.message,true);}}
function openCustomEffectModal(character){const statOptions=(state.meta.stats||[]).map(stat=>`<option value="character.stat.${stat}">STAT ${stat}</option>`).join(''),skillOptions=(state.meta.skills||[]).map(row=>`<option value="skill.${esc(row[1])}.check">${esc(row[1])} Check</option>`).join('');const modal=openModal(`<h2>${T('Add Custom Effect','Добавить Custom Effect')}</h2><div class="panel accent mb"><b>TRUST + AUDIT</b><p class="small">${T('Only allowlisted numeric modifiers are accepted. No JavaScript or executable expressions.','Разрешены только числовые модификаторы из allowlist. JavaScript и исполняемые выражения запрещены.')}</p></div><div class="grid cols-2"><label class="f"><span>${T('Effect name *','Название эффекта *')}</span><input id="effect-label" maxlength="120" placeholder="Tech optics calibration"></label><label class="f"><span>Target</span><select id="effect-target"><optgroup label="STATs">${statOptions}</optgroup><optgroup label="Skill Checks">${skillOptions}</optgroup></select></label><label class="f"><span>Operation</span><select id="effect-operation">${['add','set','minimum','maximum','multiply'].map(value=>`<option value="${value}">${value}</option>`).join('')}</select></label><label class="f"><span>Value</span><input id="effect-value" type="number" min="-100" max="100" step="0.1" value="1"></label><label class="f"><span>Stacking</span><select id="effect-stack-policy">${['stack','highest','lowest','unique','replace'].map(value=>`<option value="${value}">${value}</option>`).join('')}</select></label><label class="f"><span>${T('Stack group (optional)','Stack group (необязательно)')}</span><input id="effect-stack-group" maxlength="80" placeholder="night_vision_bonus"></label><label class="f"><span>${T('Duration','Длительность')}</span><select id="effect-duration"><option value="manual">${T('Manual','Ручная')}</option><option value="real_time">${T('Real time, minutes','Реальное время, минуты')}</option><option value="rounds">${T('Rounds, manual tick','Раунды, ручной отсчёт')}</option></select></label><label class="f" id="effect-duration-value-wrap" hidden><span id="effect-duration-value-label">Value</span><input id="effect-duration-value" type="number" min="1" max="10080" value="1"></label></div><label class="f"><span>${T('Reason *','Причина *')}</span><textarea id="effect-reason" maxlength="500" rows="3" placeholder="Session effect, Tech upgrade, GM ruling…"></textarea></label><div class="row"><button id="effect-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="effect-create">${T('Create Effect','Создать эффект')}</button></div>`,true);const duration=$('#effect-duration',modal),wrap=$('#effect-duration-value-wrap',modal),durationValue=$('#effect-duration-value',modal),durationLabel=$('#effect-duration-value-label',modal);duration.onchange=()=>{wrap.hidden=duration.value==='manual';durationValue.max=duration.value==='real_time'?'10080':'100';durationLabel.textContent=duration.value==='real_time'?T('Minutes','Минуты'):T('Rounds','Раунды');};$('#effect-cancel',modal).onclick=closeModal;$('#effect-create',modal).onclick=async()=>{const body={revision:character.revision,label:$('#effect-label',modal).value.trim(),target:$('#effect-target',modal).value,operation:$('#effect-operation',modal).value,value:Number($('#effect-value',modal).value),stack_policy:$('#effect-stack-policy',modal).value,stack_group:$('#effect-stack-group',modal).value.trim(),duration_type:duration.value,duration_value:duration.value==='manual'?null:Number(durationValue.value),reason:$('#effect-reason',modal).value.trim()};const button=$('#effect-create',modal);button.disabled=true;try{await api(`/api/characters/${character.id}/effects`,{method:'POST',body});closeModal();toast(T('Effect created.','Эффект создан.'));viewSheet(character.id);}catch(error){button.disabled=false;toast(error.message,true);}};}

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
  const owner = state.me && state.me.id === c.owner_id;
  const mine = owner && !ch.archived;
  const ab = ROLE_ABILITIES[ch.role] || { name: state.meta.roles[ch.role] || '', desc: '' };
  const hpCur = ch.hp_cur == null ? d.hp_max : ch.hp_cur;
  const cw = ch.cyberware || [];
  const inv = ch.inventory || [];
  const activeGear=inv.filter(item=>item.state==='equipped'&&item.equippable);
  const synergies=d.effects?.synergies||[],itemEffectSources=d.effects?.item_sources||[],effectInstances=d.effects?.instances||[];
  const canManageEffects=!!(state.me&&!ch.archived&&(owner||state.me.is_gm));
  const lpRows = ch.lifepath ? lifepathNarrative(ch.lifepath, ch.role, ch.role_lifepath, ch.lifepath_mode) : [];
  const armor = ch.armor || {};
  const armorSlots = [
    [armor.head, T('Head','Голова')],
    [armor.body || armor.body_outer || armor.body_inner, T('Body','Тело')],
  ].filter(([piece]) => piece);

  view.innerHTML = `
  <div class="page-head official-sheet-head">
    ${ch.portrait_media_id?`<img class="sheet-portrait" src="/api/media/${esc(ch.portrait_media_id)}" alt="${esc(ch.handle||'Character')}">`:''}
    <div><h1>📄 <span class="user-content">${esc(ch.handle || T('Unnamed','Безымянный'))}${ch.first_name || ch.last_name ? ` · ${esc([ch.first_name, ch.last_name].filter(Boolean).join(' '))}` : ''}</span>${ch.archived?` <span class="tag">${T('ARCHIVED','АРХИВ')}</span>`:''}</h1>
      <div class="sub">Character Sheet · ${(ch.roles||[]).map(role=>`${esc(role.name)} ${role.rank}${role.name===ch.active_role?' ★':''}`).join(' · ')||`${esc(ch.role||'—')} ${ch.role_rank||4}`} · ${T('owner','владелец')}: <span class="user-content">${esc(c.owner_name||'—')}</span>${ch.player?' · '+T('player','игрок')+': <span class="user-content">'+esc(ch.player)+'</span>':''}</div></div>
    <div class="row">
      <button id="sheet-back">← ${T('Characters','Персонажи')}</button>
      <button class="btn-sm" id="sheet-print">🖨️ Print</button><button class="btn-sm" id="sheet-json">⬇ JSON</button><button class="btn-sm" id="sheet-network">◎ ${T('Network','Сеть')}</button>${owner||state.me?.is_gm?`<button class="btn-sm" id="sheet-ledger">◫ ${T('Ledger','Журнал')}</button>`:''}
      ${mine ? `<button class="btn-primary" id="sheet-edit">✏️ ${T('Edit Sheet','Редактировать лист')}</button><label class="btn-sm">🖼️ Portrait<input id="sheet-portrait-file" type="file" accept="image/jpeg,image/png,image/webp" hidden></label><button class="btn-sm" id="sheet-privacy">◉ ${T('Dossier Privacy','Приватность Dossier')}</button>
                <button class="btn-danger" id="sheet-del">🗑️ ${T('Delete','Удалить')}</button>` : ''}
    </div>
  </div>

  <nav class="sheet-tabs"><button data-sheet-jump="sheet-overview">Overview</button><button data-sheet-jump="sheet-skills">Skills</button><button data-sheet-jump="sheet-combat">Combat</button><button data-sheet-jump="sheet-gear">Gear</button><button data-sheet-jump="sheet-cyberware">Cyberware</button><button data-sheet-jump="sheet-lifepath">Lifepath</button></nav>
  <div class="panel accent mb">
    <div class="derived">
      <span class="dstat resource-stat"><span class="v">${d.hp_max != null ? hpCur + ' / ' + d.hp_max : '—'}</span><span class="k">HP</span>${mine?`<span class="resource-actions"><button data-resource="hp|-5">−5</button><button data-resource="hp|-1">−1</button><button data-resource="hp|1">+1</button><button data-resource="hp|5">+5</button></span>`:''}</span>
      <span class="dstat resource-stat"><span class="v">${ch.luck_cur} / ${(ch.stats||{}).LUCK||0}</span><span class="k">LUCK</span><span class="luck-pips">${Array.from({length:(ch.stats||{}).LUCK||0},(_,i)=>`<i class="${i<ch.luck_cur?'filled':''}"></i>`).join('')}</span>${mine?`<span class="resource-actions"><button data-resource="luck|-1">Spend</button><button data-resource="luck|1">+1</button><button data-resource="luck|reset">Reset</button></span>`:''}</span>
      <span class="dstat"><span class="v">${d.seriously_wounded != null ? '≤ ' + d.seriously_wounded : '—'}</span><span class="k">Серьёзная рана</span></span>
      <span class="dstat ${d.humanity_max != null && d.humanity_cur <= 20 ? 'warn' : ''}"><span class="v">${d.humanity_max != null ? d.humanity_cur + ' / ' + d.humanity_max : '—'}</span><span class="k">Человечность</span></span>
      <span class="dstat ${d.emp_cur != null && d.emp_cur <= 2 ? 'warn' : ''}"><span class="v">${d.emp_cur != null ? d.emp_cur : '—'}</span><span class="k">EMP</span></span>
      <span class="dstat"><span class="v">${d.sp_body != null ? d.sp_body : '—'}</span><span class="k">${T('Body Armor SP','Броня SP тело')}</span></span>
      <span class="dstat"><span class="v">${d.sp_head != null ? d.sp_head : '—'}</span><span class="k">${T('Head Armor SP','Броня SP голова')}</span></span>
      <span class="dstat"><span class="v">${d.death_save != null ? d.death_save : '—'}</span><span class="k">Death Save</span></span>
      <span class="dstat"><span class="v">${money(ch.cash || 0)}</span><span class="k">Cash</span></span>
      <span class="dstat"><span class="v">${ch.ip_available||0}</span><span class="k">Improvement Points</span>${mine?`<button class="btn-sm" id="sheet-improve">Improve</button>`:(state.me&&state.me.is_gm&&!ch.archived?`<button class="btn-sm" id="sheet-ip-gm">Adjust IP</button>`:'')}</span>
      <span class="dstat resource-stat"><span class="v">${ch.reputation||0}</span><span class="k">Reputation</span>${mine?`<span class="resource-actions"><button data-resource="reputation|-1">−1</button><button data-resource="reputation|1">+1</button></span>`:''}</span>
    </div>
  </div>

  <div class="panel mb" id="sheet-combat">${combatSheetHtml(ch,d,mine)}</div>
  <div class="grid cols-2 sheet-layout" style="gap:18px">
    <div>
      <div class="panel mb" id="sheet-overview">
        <h2>🎭 Roles & Abilities</h2>${(ch.roles||[]).map(role=>`<div class="role-sheet-entry ${role.name===ch.active_role?'active':''}"><div class="row"><span class="tag role">${esc(role.name)} · Rank ${role.rank}</span>${role.primary?'<span class="chip">Primary</span>':''}${role.name===ch.active_role?'<span class="chip">Active</span>':''}</div><h3>⚡ ${esc(roleAbilityDisplayName(role.name))}</h3>${roleSetupSummary(role.name,role.setup)?`<div class="chip">${esc(roleSetupSummary(role.name,role.setup))}</div>`:''}<p class="small muted">${esc(roleAbilityDisplayDescription(role.name))}</p></div>`).join('')}
      </div>
      <div class="panel mb">
        <h2>📊 ${T('Characteristics','Характеристики')}</h2>
        <div class="statgrid">${state.meta.stats.map(s => {const effect=d.effects?.stats?.[s],base=(ch.stats||{})[s],effective=effect?.effective??base,modified=base!=null&&effective!==base;return `<div class="stat ${modified?'modified':''}"><div class="v">${modified?`${base}→${effective}`:(base??'—')}</div><div class="k">${s}</div>${modified?`<small>${esc((effect.modifiers||[]).filter(item=>item.applied).map(item=>`${item.value>0?'+':''}${item.value} ${item.source||item.id}`).join(' · '))}</small>`:''}</div>`;}).join('')}</div>
      </div>
      ${(synergies.length||itemEffectSources.length||effectInstances.length||mine)?`<div class="panel mb effect-panel"><div class="row" style="justify-content:space-between"><h2>✨ ${T('Structured Effects & Synergies','Структурированные эффекты и синергии')}</h2>${mine?`<button class="btn-sm" id="add-custom-effect">＋ ${T('Custom Effect','Custom Effect')}</button>`:''}</div><div class="small muted mb">${T('Base values are never overwritten. Active modifiers are applied only to effective checks.','Базовые значения не перезаписываются. Активные модификаторы применяются только к effective checks.')} · ${esc(d.effects.rules_version||'')}</div>${synergies.map(rule=>{const label=APP_I18N.current()==='ru'?rule.label_ru:rule.label_en,progress=rule.requirements.map(req=>`${req.label} ${req.current}/${req.required}`).join(' · '),effects=rule.effects.map(effect=>`${effect.target.replace(/^skill\.|\.check$/g,'')} ${effect.value>0?'+':''}${effect.value}`).join(' · ');return `<article class="synergy-row ${rule.active?'active':'inactive'}"><div><b>${esc(label)}</b><span>${esc(progress)}</span></div><span class="tag">${rule.active?T('ACTIVE','АКТИВНО'):T('INACTIVE','НЕАКТИВНО')}</span>${rule.active?`<strong>${esc(effects)}</strong>`:''}</article>`;}).join('')}${itemEffectSources.length?`<h3 class="mt">${T('Curated Item Effects','Курируемые эффекты предметов')}</h3>${itemEffectSources.map(source=>{const label=APP_I18N.current()==='ru'?source.label_ru:source.label_en,effects=(source.effects||[]).map(effect=>`${effectTargetLabel(effect.target)} ${effect.value>0?'+':''}${effect.value}`).join(' · ');return `<article class="synergy-row ${source.active?'active':'inactive'}"><div><b>${esc(label)}</b><span>${source.active?esc(effects):T('Equip and activate the required item.','Экипируйте и включите нужный предмет.')}</span>${(source.manual_rules||[]).map(rule=>`<small class="effect-manual-text"><b>${T('MANUAL RULE','РУЧНОЕ ПРАВИЛО')}:</b> ${esc(APP_I18N.current()==='ru'?rule.text_ru:rule.text_en)} · ${esc(rule.source||'')}</small>`).join('')}</div><span class="tag">${source.active?T('AUTOMATED','АВТОМАТИЧЕСКИ'):T('INACTIVE','НЕАКТИВНО')}</span></article>`;}).join('')}`:''}${effectInstances.length?`<h3 class="mt">${T('Active Effect Instances','Экземпляры активных эффектов')}</h3>${effectInstances.map(effect=>{const definition=effect.definition||{},amount=`${definition.operation||''} ${definition.value>0?'+':''}${definition.value??''}`;return `<article class="effect-instance ${effect.effective_active?'active':'inactive'}"><div><b>${esc(effect.label||'Effect')}</b><span>${esc(effectTargetLabel(definition.target))} · ${esc(amount)} · ${esc(effectDurationLabel(effect))}</span>${effect.reason?`<small class="user-content">${esc(effect.reason)}${effect.actor?' · '+esc(effect.actor):''}</small>`:''}${(effect.context?.manual_rules||[]).map(rule=>`<small class="effect-manual-text"><b>${T('MANUAL RULE','РУЧНОЕ ПРАВИЛО')}:</b> ${esc(APP_I18N.current()==='ru'?rule.text_ru:rule.text_en)} · ${esc(rule.source||'')}</small>`).join('')}</div><span class="tag">${esc(String(effect.status||'').toUpperCase())}</span>${canManageEffects?`<div class="row">${effect.status==='active'?`<button class="btn-sm" data-effect-action="${effect.effect_id}|disable">${T('Disable','Отключить')}</button>`:''}${effect.status==='disabled'?`<button class="btn-sm" data-effect-action="${effect.effect_id}|enable">${T('Enable','Включить')}</button>`:''}${effect.status==='active'&&effect.duration_type==='rounds'?`<button class="btn-sm" data-effect-action="${effect.effect_id}|tick">${T('Advance 1 round','Минус 1 раунд')}</button>`:''}<button class="btn-sm btn-danger" data-effect-action="${effect.effect_id}|archive">${T('Archive','Архивировать')}</button></div>`:''}</article>`;}).join('')}`:''}</div>`:''}
      <div class="panel mb" id="sheet-skills">
        <h2>🎯 Skills</h2>
        <div class="small muted mb">${T('STAT · LVL · BASE = current STAT + LVL; EMP reflects Humanity Loss.','STAT · LVL · BASE = текущий STAT + LVL; EMP учитывает Humanity Loss.')}</div>
        ${fullSkillsTableHtml(ch, d, true)}
      </div>
      <div class="panel mb" id="sheet-cyberware">
        <h2>🦾 Cyberware (HL ${cw.reduce((a, x) => a + (num(x.hl) || 0), 0)})</h2>
        ${cyberwareTreeHtml(cw)}
      </div>
      <div class="panel mb" id="sheet-gear">
        <h2>⚡ ${T('Active Gear / Loadout','Активное снаряжение')}</h2>
        ${activeGear.length?`<div class="active-gear-grid mb">${activeGear.map(item=>`<article class="active-gear-card ${item.active?'online':''}"><div><b>${esc(item.custom_name||item.name)}</b><span>${esc(equipModeLabel(item.equipped_mode||'ready'))} · ${esc(item.equipped_slot||'—')}</span></div><span class="tag">${item.activation_required?(item.active?T('ACTIVE','ВКЛЮЧЕНО'):T('OFF','ВЫКЛЮЧЕНО')):T('READY','ГОТОВО')}</span>${(item.active_actions||[]).length?`<div class="small muted">${item.active_actions.map(esc).join(' · ')}</div>`:''}${mine?`<div class="row">${item.activation_required?`<button class="btn-sm" data-item-action="${item.instance_id}|${item.active?'deactivate':'activate'}">${item.active?T('Deactivate','Выключить'):T('Activate','Включить')}</button>`:''}<button class="btn-sm" data-item-action="${item.instance_id}|unequip">${T('Unequip','Убрать')}</button></div>`:''}</article>`).join('')}</div>`:`<div class="muted small mb">${T('No gear is equipped. Carried items do not provide equipment-only actions.','Нет экипированного снаряжения. Предметы в состоянии carried не дают equipment-only actions.')}</div>`}
        <h2>🎒 Inventory (${inv.length})</h2>
        ${inv.length ? groupedItemsHtml(inv.map((item, index) => ({ ...item, _sheetIndex: index })), i => `
          <div class="inv-row"><span class="iname">${esc(i.custom_name || i.display_name || i.name)} ×${i.qty || 1}</span>${i.is_custom?'<span class="tag">CUSTOM · MANUAL</span>':''}
            ${itemMechanicChips(i)}<span class="chip">${esc(i.state||'carried')}</span>${i.consumable?`<span class="tag">${T('CONSUMABLE','РАСХОДНИК')}</span>`:''}${i.equippable?`<span class="tag">${T('EQUIPPABLE','ЭКИПИРУЕТСЯ')}</span>`:''}${i.acquisition_source?`<span class="chip">${esc(acquisitionSourceLabel(i.acquisition_source))}</span>`:''}
            ${i.sp != null && !(i.mechanics || {}).sp ? `<span class="chip">SP ${i.sp}</span>` : ''}
            ${i.is_custom&&i.desc?`<span class="small muted user-content">${esc(i.desc)}</span>`:''}<span class="muted small">${money((i.price || 0) * (i.qty || 1))}</span><button class="info-btn" data-owned-item="${i._sheetIndex}">i</button>${mine&&i.consumable&&i.state!=='stored'?`<button class="btn-sm" data-item-use="${i.instance_id}">${T('Use','Использовать')}</button>`:''}${mine&&i.equippable&&i.state==='carried'?`<button class="btn-sm" data-item-equip="${i.instance_id}">${T('Equip','Экипировать')}</button>`:''}
          </div>`, T('Gear','Снаряжение')) : `<div class="muted small">${T('Empty.','Пусто. Совсем.')}</div>`}
        ${armorSlots.length ? `<h3 class="mt">🛡️ ${T('Equipped Armor','Надетая броня')}</h3>${armorSlots.map(([piece, ru]) => `
          <div class="inv-row"><span class="iname">${ru}: ${esc(piece.name)}</span>
            <span class="chip">SP ${piece.sp}</span>
            ${Object.values(armorPenalties(piece)).some(v => v) ? `<span class="chip">${Object.entries(armorPenalties(piece)).map(([k,v]) => k + ' ' + v).join(' · ')}</span>` : ''}
          </div>`).join('')}` : ''}
      </div>
    </div>
    <div>
      <div class="panel mb" id="sheet-lifepath">
        <h2>🧬 Lifepath</h2>
        ${lpRows.length ? `<div class="kv">${lpRows.map(([k, v]) => `<b>${esc(k)}</b><span>${esc(displayKnownValue(v))}</span>`).join('')}</div>`
          : (ch.background ? `<div class="desc user-content" style="white-space:pre-wrap">${esc(ch.background)}</div>` : `<div class="muted small">${T('Lifepath is incomplete.','Lifepath не заполнен.')}</div>`)}
      </div>
      ${ch.appearance ? `<div class="panel mb"><h2>🕶️ ${T('Appearance','Внешность')}</h2><div class="desc user-content">${esc(ch.appearance)}</div></div>` : ''}
      ${ch.languages ? `<div class="panel mb"><h2>🗣️ ${T('Languages','Языки')}</h2><div class="desc user-content">${esc(ch.languages)}</div></div>` : ''}
      ${(ch.lifestyle || ch.housing) ? `<div class="panel mb"><h2>🏠 ${T('Lifestyle','Жизнь')}</h2><div class="kv"><b>Lifestyle</b><span class="user-content">${esc(ch.lifestyle || '—')}</span><b>${T('Housing','Жильё')}</b><span class="user-content">${esc(ch.housing || '—')}</span></div></div>` : ''}
      ${lpRows.length && ch.background ? `<div class="panel mb"><h2>📖 ${T('Background','Предыстория')}</h2><div class="desc user-content" style="white-space:pre-wrap">${esc(ch.background)}</div></div>` : ''}
      <div class="panel mb"><h2>📝 Notes</h2>${mine?`<textarea id="sheet-notes" maxlength="20000" rows="8">${esc(ch.notes||'')}</textarea><div class="small muted" id="sheet-notes-status">Autosaves after typing</div>`:`<div class="desc user-content" style="white-space:pre-wrap">${esc(ch.notes||'—')}</div>`}</div>
    </div>
  </div>`;

  const addEffectButton=$('#add-custom-effect');if(addEffectButton)addEffectButton.onclick=()=>openCustomEffectModal(c);
  $$('[data-effect-action]',view).forEach(button=>button.onclick=()=>{const [effectId,action]=button.dataset.effectAction.split('|'),effect=effectInstances.find(item=>item.effect_id===effectId);if(effect)performEffectAction(c,effect,action);});
  $$('[data-skill-info]', view).forEach(btn => btn.onclick = () => showSkillInfo(btn.dataset.skillInfo));
  $$('[data-owned-chrome]', view).forEach(btn => btn.onclick = () => showCreationItemInfo(cw[Number(btn.dataset.ownedChrome)]));
  $$('[data-owned-item]', view).forEach(btn => btn.onclick = () => showCreationItemInfo(inv[Number(btn.dataset.ownedItem)]));
  $$('[data-item-action]',view).forEach(button=>button.onclick=()=>{const [instanceId,action]=button.dataset.itemAction.split('|'),item=inv.find(entry=>entry.instance_id===instanceId);if(item)performSheetItemAction(c,item,action);});
  $$('[data-item-equip]',view).forEach(button=>button.onclick=()=>{const item=inv.find(entry=>entry.instance_id===button.dataset.itemEquip);if(item)chooseEquipMode(c,item);});
  $$('[data-item-use]',view).forEach(button=>button.onclick=()=>{const item=inv.find(entry=>entry.instance_id===button.dataset.itemUse);if(!item)return;const maximum=Math.max(1,Number(item.qty)||1),amount=maximum>1?Number(prompt(T(`How many uses? 1–${maximum}`,`Сколько использовать? 1–${maximum}`),'1')):1;if(!Number.isInteger(amount)||amount<1||amount>maximum)return;if(confirm(`${T('Use','Использовать')} ${item.custom_name||item.name} ×${amount}?`))performSheetItemAction(c,item,'use',{amount});});
  $$('[data-sheet-jump]',view).forEach(button=>button.onclick=()=>document.getElementById(button.dataset.sheetJump)?.scrollIntoView({behavior:'smooth',block:'start'}));
  $$('[data-manage-upgrades]',view).forEach(button=>button.onclick=()=>openWeaponUpgradeManager(c,button.dataset.manageUpgrades));
  $$('[data-mod-weapon-action]',view).forEach(button=>button.onclick=async()=>{const [modificationId,action]=button.dataset.modWeaponAction.split('|');button.disabled=true;try{await api(`/api/characters/${c.id}/modifications/${modificationId}/action`,{method:'POST',body:{revision:c.revision,action}});viewSheet(c.id);}catch(error){button.disabled=false;toast(error.message,true);}});
  $$('[data-attack-roll]',view).forEach(button=>button.onclick=()=>{const split=button.dataset.attackRoll.lastIndexOf('|');showCheckRoll(button.dataset.attackRoll.slice(0,split),Number(button.dataset.attackRoll.slice(split+1)));});$$('[data-damage-roll]',view).forEach(button=>button.onclick=()=>{const [name,dice,sides,multiplier]=button.dataset.damageRoll.split('|');rollDamage(name,Number(dice),Number(sides),Number(multiplier));});$$('[data-weapon-action]',view).forEach(button=>button.onclick=async()=>{const [subject,action]=button.dataset.weaponAction.split('|');try{await api(`/api/characters/${c.id}/resource`,{method:'POST',body:{resource:'weapon',subject,action,value:1}});viewSheet(c.id);}catch(e){toast(e.message,true);}});$$('[data-armor-action]',view).forEach(button=>button.onclick=async()=>{const [subject,value]=button.dataset.armorAction.split('|');try{await api(`/api/characters/${c.id}/resource`,{method:'POST',body:{resource:'armor',subject,action:value==='reset'?'reset':'delta',value:value==='reset'?0:Number(value)}});viewSheet(c.id);}catch(e){toast(e.message,true);}});
  $$('[data-roll-check]', view).forEach(button => button.onclick = () => { const split=button.dataset.rollCheck.lastIndexOf('|');showCheckRoll(button.dataset.rollCheck.slice(0,split),Number(button.dataset.rollCheck.slice(split+1))); });
  $$('[data-resource]', view).forEach(button => button.onclick = () => { const [resource,value]=button.dataset.resource.split('|'); sheetResource(c.id,resource,value); });
  const improveBtn=$('#sheet-improve');if(improveBtn)improveBtn.onclick=()=>openImprovementModal(c);const gmIp=$('#sheet-ip-gm');if(gmIp)gmIp.onclick=()=>openIpAdjustment(c.id,()=>viewSheet(c.id));
  const editSheet=$('#sheet-edit');if(editSheet)editSheet.onclick=()=>go(`/char/${c.id}?edit`);
  const notes=$('#sheet-notes');if(notes){let timer;notes.oninput=()=>{clearTimeout(timer);$('#sheet-notes-status').textContent='Saving…';timer=setTimeout(async()=>{try{ch.notes=notes.value;const saved=await api('/api/characters/'+c.id,{method:'PUT',body:{revision:c.revision,patch:{notes:notes.value}}});c.revision=saved.revision;$('#sheet-notes-status').textContent='Saved';}catch(e){$('#sheet-notes-status').textContent=e.message;}},700);};}
  const portraitInput=$('#sheet-portrait-file');if(portraitInput)portraitInput.onchange=()=>openImageCrop(portraitInput.files[0],'character_portrait',async media=>{try{await api('/api/characters/'+c.id,{method:'PUT',body:{revision:c.revision,patch:{portrait_media_id:media.id}}});viewSheet(c.id);}catch(e){toast(e.message,true);}});
  const networkButton=$('#sheet-network');
  if(networkButton)networkButton.onclick=async()=>{
    try{
      const network=await api(`/api/characters/${c.id}/network`);
      openModal(`<h2>${T('NC//NET Activity','Активность NC//NET')}</h2><h3>${T('Contracts','Контракты')}</h3>${network.contracts.map(item=>`<a class="inv-row" href="#/contracts/${item.id}"><span class="iname user-content">${esc(item.title)}</span><span class="tag">${esc(item.signup_status)}</span></a>`).join('')||'<div class="empty">—</div>'}<h3>${T('Transmissions','Передачи')}</h3>${network.posts.map(item=>`<a class="inv-row" href="#/feed/${item.id}"><span class="iname user-content">${esc(item.headline||item.body.slice(0,80))}</span></a>`).join('')||'<div class="empty">—</div>'}`,true);
    }catch(e){toast(e.message,true);}
  };
  const ledgerButton=$('#sheet-ledger');
  if(ledgerButton)ledgerButton.onclick=async()=>{
    try{
      const history=await api(`/api/characters/${c.id}/ledger`);
      const rows=history.entries.length?history.entries.map(entry=>{
        const changes=(entry.changes||[]).map(change=>`<div class="ledger-change"><b>${esc(change.label)}</b><span>${esc(String(change.before??'—'))} → ${esc(String(change.after??'—'))}</span></div>`).join('');
        return `<article class="panel mb ledger-entry"><div class="row" style="justify-content:space-between"><span class="tag">${esc(entry.category)}</span><span class="small muted">${timeAgo(entry.created)} · ${esc(entry.actor)}</span></div><b class="user-content">${esc(entry.reason||'')}</b>${changes?`<div class="ledger-changes mt">${changes}</div>`:''}${entry.can_revert?`<button class="btn-sm mt" data-ledger-revert="${entry.id}">↶ ${T('Revert this change set','Откатить этот набор изменений')}</button>`:''}</article>`;
      }).join(''):`<div class="empty">${T('No permanent changes recorded.','Постоянные изменения не записаны.')}</div>`;
      const modal=openModal(`<h2>${T('Dossier Ledger','Журнал досье')}</h2><p class="small muted">${T('Trust + Audit records who changed what, when, and why. Only the latest reversible change can be undone safely.','Trust + Audit записывает кто, что, когда и почему изменил. Безопасно откатить можно только последнее обратимое изменение.')}</p>${rows}`,true);
      $$('[data-ledger-revert]',modal).forEach(button=>button.onclick=async()=>{if(!confirm(T('Revert the entire change set?','Откатить весь набор изменений?')))return;const reason=prompt(T('Reason for revert','Причина отката'))||'';button.disabled=true;try{await api(`/api/characters/${c.id}/ledger/${button.dataset.ledgerRevert}/revert`,{method:'POST',body:{revision:history.current_revision,reason}});closeModal();toast(T('Change set reverted.','Набор изменений отменён.'));viewSheet(c.id);}catch(error){button.disabled=false;toast(error.message,true);}});
    }catch(e){toast(e.message,true);}
  };
  $('#sheet-print').onclick = () => window.print();
  $('#sheet-json').onclick = () => { const blob = new Blob([JSON.stringify(ch, null, 2)], {type:'application/json'}), a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `${(ch.handle || 'character').replace(/[^a-z0-9_-]+/gi,'-')}.json`; a.click(); URL.revokeObjectURL(a.href); };
  $('#sheet-back').onclick = () => go('/dossiers');
  const privacyBtn = $('#sheet-privacy');
  if (privacyBtn) privacyBtn.onclick = () => {
    const defaults=state.meta.character_visibility_defaults||{},visibility={...defaults,...(ch.visibility||{})};
    const fields=[
      ['portrait','Portrait','Портрет'],['identity','Identity / real name','Имя персонажа'],
      ['biography','Biography / appearance','Биография / внешность'],['stats','Characteristics','Характеристики'],
      ['skills','Skills','Навыки'],['lifepath','Lifepath','Lifepath'],
      ['equipment','Inventory / Cyberware / Armor','Инвентарь / Cyberware / броня'],
      ['combat','Combat values','Боевые показатели'],['player_name','Player name','Имя игрока'],
    ];
    const modal=openModal(`<h2>${T('Dossier Privacy','Приватность Dossier')}</h2><label class="checkbox mb"><input id="dossier-public" type="checkbox" ${c.public?'checked':''}> <b>${T('List this Dossier in Crew Registry','Показывать Dossier в Crew Registry')}</b></label><div class="panel"><p class="small muted">${T('Notes, Cash, IP and private service data are never included in the public Dossier.','Notes, Cash, IP и служебные данные никогда не входят в публичный Dossier.')}</p>${fields.map(([key,en,ru])=>`<label class="checkbox"><input data-dossier-visibility="${key}" type="checkbox" ${visibility[key]?'checked':''}> ${T(en,ru)}</label>`).join('')}</div><div class="row mt"><button id="dossier-privacy-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="dossier-privacy-save">${T('Save Privacy','Сохранить приватность')}</button></div>`,true);
    $('#dossier-privacy-cancel',modal).onclick=closeModal;
    $('#dossier-privacy-save',modal).onclick=async()=>{const next={};$$('[data-dossier-visibility]',modal).forEach(input=>next[input.dataset.dossierVisibility]=input.checked);try{await api('/api/characters/'+c.id,{method:'PUT',body:{revision:c.revision,patch:{public:$('#dossier-public',modal).checked,visibility:next}}});closeModal();viewSheet(c.id);toast(T('Dossier privacy updated.','Приватность Dossier обновлена.'));}catch(e){toast(e.message,true);}};
  };
  const delBtn = $('#sheet-del');
  if (delBtn) delBtn.onclick = async () => {
    if (!confirm(T('Delete this Character? Dossiers with NC//NET history will be archived instead.','Удалить Character? Досье с историей NC//NET будет перемещено в архив.'))) return;
    try {
      const result = await api('/api/characters/' + c.id, { method: 'DELETE' });
      toast(result.archived ? T('Dossier archived to preserve NC//NET history.','Досье архивировано для сохранения истории NC//NET.') : T('Character deleted.','Персонаж удалён.'));
      go('/dossiers');
    } catch (e) { toast(e.message, true); }
  };
}

/* ============================== мои персонажи ============================== */

async function viewCharacters(view) {
  if (!state.me) {
    view.innerHTML = `<div class="empty">Раздел только для вошедших. <a href="#/login">${T('Sign in','Войти')}</a> · <a href="#/register">Регистрация</a></div>`;
    return;
  }
  view.innerHTML = spinner();
  const data = await api('/api/characters');
  const activeCount = data.characters.filter(character => !character.data.archived).length;
  const archivedCount = data.characters.length - activeCount;
  view.innerHTML = `
    <div class="page-head">
      <div><h1>🧬 ${T('My Characters','Мои персонажи')}</h1><div class="sub">${T('Active Dossiers','Активные досье')}: ${activeCount}/50${archivedCount ? ` · ${archivedCount} ${T('archived','в архиве')}` : ''}</div></div>
      <button class="btn-primary" onclick="location.hash='#/char/new'">+ ${T('New Edgerunner','Новый эджраннер')}</button>
    </div>`;
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
    <div class="card ${ch.archived?'archived':''}" data-id="${c.id}">
      <div class="head row" style="justify-content:space-between">
        <h3 style="cursor:pointer" class="open user-content">${esc(ch.handle || T('Unnamed','Безымянный'))}</h3>
        <span class="muted small">${ch.archived ? `◫ ${T('ARCHIVED','АРХИВ')}` : (c.public ? T('👁 public','👁 публичный') : T('🔒 private','🔒 приватный'))}</span>
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
        <button class="btn-sm btn-primary open">${T('Open','Открыть')}</button>
        ${ch.archived ? '' : `<button class="btn-sm btn-danger del">${T('Delete','Удалить')}</button>`}
      </div>
    </div>`;
  }).join('');
  $$('.card .open', view).forEach(el => el.onclick = () => go('/char/' + el.closest('.card').dataset.id));
  $$('.card .del', view).forEach(el => el.onclick = async () => {
    const card = el.closest('.card');
    if (!confirm(T('Delete this Character? Dossiers with NC//NET history will be archived instead.','Удалить Character? Досье с историей NC//NET будет перемещено в архив.'))) return;
    try {
      const result = await api('/api/characters/' + card.dataset.id, { method: 'DELETE' });
      toast(result.archived ? T('Dossier archived to preserve NC//NET history.','Досье архивировано для сохранения истории NC//NET.') : T('Character deleted.','Персонаж удалён.'));
      viewCharacters(view);
    } catch (e) { toast(e.message, true); }
  });
}

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
      c2.cyberware.push({key:it.id,catalog_item_id:it.id,cat:'cyberware',name:it.name,custom_name:meta.custom_name||'',hl:it.hl||0,price:it.price,type:(it.fields&&it.fields.Type)||'',qty:1,state:'installed',fields:{...(it.fields||{})},mechanics:{...(it.mechanics||{})},requirements:[...(it.requirements||[])],capacity:it.capacity?{...it.capacity}:null,source:it.source||'',acquisition_source:meta.acquisition_source,acquisition_note:meta.acquisition_note||''});
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
      <span class="iname">${esc(i.custom_name||i.name)}</span><span class="hl-badge">HL ${i.hl || 0}</span><span class="chip">${esc(i.type || 'Cyberware')}</span>${i.acquisition_source?`<span class="chip">${esc(acquisitionSourceLabel(i.acquisition_source))}</span>`:''}
      <button class="btn-sm" data-chrome-edit="${idx}">✎</button><button class="btn-sm btn-danger" data-chrome-del="${idx}">✕ ${T('remove','извлечь')}</button>
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

/* ============================== ростер ============================== */

async function viewRoster(view) {
  view.innerHTML = `
  <div class="page-head"><div><h1>📋 ${T('Campaign Roster','Ростер партии')}</h1><div class="sub">${T('All Public characters.','Все публичные персонажи.')}</div></div></div>
  <div class="searchbar"><input id="ro-q" placeholder="Фильтр: псевдоним, роль, игрок…"><button id="ro-go">Фильтр</button></div>
  <div id="ro-list">${spinner()}</div>`;
  let q = '';
  const load = async () => {
    $('#ro-list').innerHTML = spinner();
    const data = await api('/api/roster' + (q ? ('?q=' + encodeURIComponent(q)) : ''));
    const chars = data.characters;
    if (!chars.length) { $('#ro-list').innerHTML = '<div class="empty">Никого. Пока что.</div>'; return; }
    const byOwner = {};
    chars.forEach(c => { const owner=c.owner_name||T('Private operator','Приватный оператор');(byOwner[owner] = byOwner[owner] || []).push(c); });
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
  <div class="card roster-card">
    <img class="roster-portrait" src="${ch.portrait_media_id?`/api/media/${esc(ch.portrait_media_id)}`:`/role-art/${esc(String(ch.role||'solo').toLowerCase())}.webp`}" alt="${esc(ch.handle||T('Character portrait','Портрет персонажа'))}" loading="lazy">
    <div class="row" style="justify-content:space-between;align-items:baseline">
      <h3 class="ro-open user-content" style="cursor:pointer">${esc(ch.handle || T('Unnamed','Безымянный'))}</h3>
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
    ${ch.player ? `<div class="muted small">${T('player:','игрок:')} <span class="user-content">${esc(ch.player)}</span></div>` : ''}
    <button class="btn-sm ro-open mt" data-id="${c.id}">${T('Character Sheet','Лист персонажа')}</button>
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
    <div class="roster-modal-head"><img class="roster-modal-portrait" src="${ch.portrait_media_id?`/api/media/${esc(ch.portrait_media_id)}`:`/role-art/${esc(String(ch.role||'solo').toLowerCase())}.webp`}" alt=""><h2 class="user-content">${esc(ch.handle)}</h2></div>
    <div class="chips mb">
      <span class="tag role">${esc(ch.role || '—')}${ch.role_rank ? ' ' + ch.role_rank : ''}</span>
      ${c.owner_name?`<span class="chip">${T('owner:','владелец:')} <span class="user-content">${esc(c.owner_name)}</span></span>`:''}
      ${ch.player ? `<span class="chip">${T('player:','игрок:')} <span class="user-content">${esc(ch.player)}</span></span>` : ''}
      ${ch.cash!=null?`<span class="tag price">${money(ch.cash)}</span>`:''}
      ${d.death_save ? `<span class="chip">Death Save ${d.death_save}</span>` : ''}
    </div>
    ${Object.keys(ch.stats || {}).length ? `
      <div class="statgrid mb">${state.meta.stats.map(s => `<div class="stat"><div class="v">${ch.stats[s] != null ? ch.stats[s] : '—'}</div><div class="k">${s}</div></div>`).join('')}</div>
      <div class="derived mb">${[['HP', d.hp_max], ['HUM', d.humanity_max != null ? d.humanity_cur + '/' + d.humanity_max : null], ['EMP', d.emp_cur], ['SP тело', d.sp_body], ['SP голова', d.sp_head]]
        .filter(([, v]) => v != null).map(([k, v]) => `<span class="dstat"><span class="v">${v}</span><span class="k">${k}</span></span>`).join('')}</div>` : ''}
    ${extra.length ? `<div class="kv mb">${extra.map(([k, v]) => `<b>${esc(displayKnownValue(k))}</b><span class="user-content">${esc(v)}</span>`).join('')}</div>` : ''}
    ${ch.appearance ? `<p class="small"><b>${T('Appearance:','Внешность:')}</b> <span class="user-content">${esc(ch.appearance)}</span></p>` : ''}
    ${ch.background ? `<p class="small"><b>${T('Biography:','Биография:')}</b> <span class="user-content">${esc(ch.background)}</span></p>` : ''}
    ${skills.length ? `<h3>Навыки</h3><div class="chips mb">${skills.map(([n, v]) => `<span class="chip">${esc(n)} <b>${v}</b></span>`).join('')}</div>` : ''}
    ${cw.length ? `<h3>Хром (${cw.reduce((a, x) => a + (x.hl || 0), 0)} HL)</h3><div class="chips mb">${cw.map(x => `<span class="chip">🦾 ${esc(x.name)} <b class="hl-badge">${x.hl || 0}</b></span>`).join('')}</div>` : ''}
    ${inv.length ? `<h3>Инвентарь</h3><div class="chips">${inv.map(x => `<span class="chip">${esc(x.name)}${x.qty > 1 ? ' ×' + x.qty : ''}</span>`).join('')}</div>` : ''}
    ${ch.notes ? `<hr><div class="desc user-content">${esc(ch.notes)}</div>` : ''}
  `, true);
}

/* ============================== новости ============================== */

async function viewNews(view) {
  view.innerHTML = `
  <div class="page-head"><div><h1>📡 ${T('Legacy City Archive','Архив старой городской ленты')}</h1><div class="sub">${T('Compatibility view for posts created before the NC//NET City Feed migration.','Режим совместимости для постов, созданных до миграции City Feed NC//NET.')}</div></div></div>
  <div id="news-compose"></div>
  <div id="news-list">${spinner()}</div>`;
  const composeBox = $('#news-compose');
  if (state.me) {
    composeBox.innerHTML = `
    <div class="panel mb">
      <div class="grid cols-2">
        <label class="f"><span>Заголовок</span><input id="nw-title" maxlength="140" placeholder="Перестрелка в Мегабилдинге H4"></label>
        <label class="f"><span>Источник / тег (партия, район…)</span><input id="nw-tag" maxlength="40" placeholder="${T('Campaign C-Unit, Watson…','Партия «С-Unit», Уотсон…')}"></label>
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
    composeBox.innerHTML = `<div class="empty mb">Войди, чтобы публиковать сводки. <a href="#/login">${T('Sign in','Войти')}</a></div>`;
  }
  const data = await api('/api/news');
  $('#news-list').innerHTML = data.news.length ? data.news.map(n => `
    <div class="card post" data-id="${n.id}">
      <div class="meta">
        ${n.tag ? `<span class="tag user-content">${esc(n.tag)}</span>` : ''}
        <span class="user-content">📰 ${esc(n.author)}</span><span>·</span><span>${timeAgo(n.created)}</span>
        ${n.mine || (state.me && state.me.is_gm) ? '<button class="btn-sm btn-danger" data-del style="margin-left:auto">✕</button>' : ''}
      </div>
      <div class="title user-content">${esc(n.title)}</div>
      <div class="desc user-content">${esc(n.body)}</div>
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
    <div><h1>📞 ${T('Contracts','Контракты')}</h1><div class="sub">${T('Operations relayed by Night City contacts. Legacy announcements remain available during migration.','Операции от контактов Найт-Сити. Старые объявления доступны во время миграции.')}</div></div>
    ${state.me && state.me.is_gm ? `<button class="btn-primary" id="jb-new">＋ ${T('Post a Contract','Разместить контракт')}</button>` : ''}
  </div>
  ${state.me && !state.me.is_gm ? `<div class="muted small mb">${T('Only accounts assigned GM access by an NC//NET Admin can post Contracts.','Размещать контракты могут только аккаунты, которым Admin NC//NET назначил доступ GM.')}</div>` : ''}
  <div id="jb-list">${spinner()}</div>`;
  const nb = $('#jb-new');
  if (nb) nb.onclick = jobComposeModal;
  const data = await api('/api/jobs');
  $('#jb-list').innerHTML = data.jobs.length ? data.jobs.map(j => `
    <div class="card job ${j.status}" data-id="${j.id}">
      <div class="meta">
        <span class="tag">${j.status === 'open' ? '🟢 открыт' : '🔴 закрыт'}</span>
        <span class="tag user-content">${esc(j.system || 'Cyberpunk RED')}</span>
        ${j.when_text ? `<span class="user-content">⏱ ${esc(j.when_text)}</span>` : ''}
        <span>${T('GM:','ГМ:')} <span class="user-content">${esc(j.author)}</span></span>
        <span class="slots">${j.slots ? `${j.signups}/${j.slots} слотов` : `записалось: ${j.signups}`}</span>
      </div>
      <h3 class="user-content" style="margin:4px 0">${esc(j.title)}</h3>
      <div class="desc user-content" style="max-height:80px;overflow:hidden">${esc(j.description)}</div>
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
    <h2 class="user-content">${esc(j.title)}</h2>
    <div class="meta" style="color:var(--muted);font-size:13.5px;margin-bottom:8px">
      <span class="tag">${j.status === 'open' ? T('🟢 open','🟢 открыт') : T('🔴 closed','🔴 закрыт')}</span>
      <span class="tag user-content">${esc(j.system || 'Cyberpunk RED')}</span>
      ${j.when_text ? `<span class="user-content">⏱ ${esc(j.when_text)}</span>` : ''}
      <span>${T('GM:','ГМ:')} <span class="user-content">${esc(j.author)}</span></span>
    </div>
    <div class="desc mb user-content">${esc(j.description)}</div>
    ${j.signups_list && j.signups_list.length ? `
      <h3>Записались (${j.signups_list.length}${j.slots ? ' из ' + j.slots : ''})</h3>
      ${j.signups_list.map(s => `
        <div class="inv-row user-content"><span class="iname">${esc(s.user)}${s.char_name ? ' → <b>' + esc(s.char_name) + '</b>' : ''}</span>
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
          <option value="">${T('— without a character —','— без персонажа —')}</option>
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
    actions.innerHTML = `<span class="muted small">Войдите, чтобы записаться. <a href="#/login">${T('Sign in','Войти')}</a></span>`;
  }
}

/* ============================== вход / профиль ============================== */

function viewLogin(view) {
  const registrationMode=state.meta?.registration_mode||'invite';
  view.innerHTML = `
  <div class="grid cols-2" style="max-width:900px;margin:0 auto">
    <div class="panel">
      <h2>${T('Sign in','Вход')}</h2>
      <label class="f"><span>${T('Username','Логин')}</span><input id="lg-u" autocomplete="username"></label>
      <label class="f"><span>${T('Password','Пароль')}</span><input id="lg-p" type="password" autocomplete="current-password"></label>
      <button class="btn-primary" id="lg-go">${T('Sign in','Войти')}</button>
    </div>
    <div class="panel accent">
      ${registrationMode==='closed'?`<h2>${T('Registration closed','Регистрация закрыта')}</h2><p class="muted">${T('An NC//NET Admin creates new accounts.','Новые аккаунты создаёт Admin NC//NET.')}</p>`:`<h2>${T('Register','Регистрация')}</h2>
      ${registrationMode==='invite'?`<label class="f"><span>${T('Invite code','Код приглашения')}</span><input id="rg-invite" autocomplete="one-time-code" placeholder="NCNET-XXXX-XXXX-XXXX-XXXX"></label>`:''}
      <label class="f"><span>${T('Username (Latin letters)','Логин (латиница)')}</span><input id="rg-u" autocomplete="username"></label>
      <label class="f"><span>${T('Display name','Отображаемое имя')}</span><input id="rg-d" placeholder="${T('How Night City knows you','Как тебя знают в городе')}"></label>
      <label class="f"><span>${T('Password (8+ characters)','Пароль (от 8 символов)')}</span><input id="rg-p" type="password" minlength="8" autocomplete="new-password"></label>
      <p class="small muted">${T('New accounts receive Player access. NC//NET Admins assign GM permissions.','Новые аккаунты получают доступ Player. Права GM назначают администраторы NC//NET.')}</p>
      <button class="btn-primary" id="rg-go">${T('Create account','Создать аккаунт')}</button>`}
    </div>
  </div>`;
  const doLogin = async () => {
    try {
      state.me = await api('/api/login', { method: 'POST', body: { username: $('#lg-u').value, password: $('#lg-p').value } });
      if(state.me.theme)APP_THEME.setFromProfile(state.me.theme);
      renderUserbox();
      refreshShellDossiers();
      toast(T('Welcome back, ','С возвращением, ') + state.me.display_name);
      go('/dossiers');
    } catch (e) { toast(e.message, true); }
  };
  $('#lg-go').onclick = doLogin;
  $('#lg-p').onkeydown = (e) => { if (e.key === 'Enter') doLogin(); };
  if ($('#rg-go')) $('#rg-go').onclick = async () => {
    try {
      state.me = await api('/api/register', { method: 'POST', body: {
        username: $('#rg-u').value, display_name: $('#rg-d').value,
        password: $('#rg-p').value,invite_code:$('#rg-invite')?.value||'' } });
      if(state.me.theme)APP_THEME.setFromProfile(state.me.theme);
      renderUserbox();
      refreshShellDossiers();
      toast(T('Welcome to Night City.','Добро пожаловать в Ночной город.'));
      go('/dossiers');
    } catch (e) { toast(e.message, true); }
  };
}

function viewRegister(view) { viewLogin(view); }

async function viewProfile(view) {
  if (!state.me) { view.innerHTML = `<div class="empty">${T('Sign in required.','Нужен вход.')} <a href="#/login">${T('Sign in','Войти')}</a></div>`; return; }
  const role = String(state.me.account_role || (state.me.is_gm ? 'gm' : 'player')).toUpperCase();
  let avatarMediaId = state.me.avatar_media_id || null;
  let accountSessions=[];try{accountSessions=(await api('/api/account/sessions')).sessions;}catch(e){}
  view.innerHTML = `
  <div class="panel" style="max-width:620px;margin:0 auto">
    <div class="row" style="justify-content:space-between"><h2>${T('NC//NET Profile','Профиль NC//NET')}</h2><span class="tag role">${esc(role)}</span></div>
    <div class="profile-avatar-editor mb"><div id="pf-avatar-preview">${avatarMediaId?`<img src="/api/media/${esc(avatarMediaId)}" alt="">`:`<span>${esc((state.me.display_name||state.me.username||'?').slice(0,1).toUpperCase())}</span>`}</div><div><label class="btn-sm">${T('Upload Account Avatar','Загрузить аватар аккаунта')}<input id="pf-avatar-file" type="file" accept="image/jpeg,image/png,image/webp" hidden></label>${avatarMediaId?`<button class="btn-sm" id="pf-avatar-remove">${T('Remove Avatar','Удалить аватар')}</button>`:''}<p class="small muted">${T('Square crop recommended. Avatar visibility follows display-name privacy.','Рекомендуется квадратная обрезка. Видимость аватара следует настройке display name.')}</p></div></div>
    <label class="f"><span>${T('Display name','Отображаемое имя')}</span><input id="pf-d" value="${esc(state.me.display_name)}"></label>
    <label class="f"><span>${T('Network access','Доступ к сети')}</span><input value="${esc(role)}" disabled></label>
    <label class="checkbox mb"><input type="checkbox" id="pf-show-name" ${state.me.show_display_name ? 'checked' : ''}> ${T('Show my account display name to other members of my Contracts','Показывать display name аккаунта другим участникам моих контрактов')}</label>
    <div class="panel mb"><label class="f"><span>${T('NC//NET Audio Volume','Громкость NC//NET')}</span><input id="pf-audio-volume" type="range" min="0" max="1" step=".05" value="${typeof NC_AUDIO!=='undefined'?NC_AUDIO.getVolume():.55}"></label></div>
    <div class="panel mb"><div class="row" style="justify-content:space-between"><div><b>VK</b><div class="small muted">${state.me.vk_linked ? T('Connected for NC//NET mentions','Подключён для упоминаний NC//NET') : T('Connect VK to allow mentions in the campaign conversation.','Подключите VK для упоминаний в беседе кампании.')}</div></div>${state.me.vk_linked?'✓':`<button class="btn-sm" id="pf-vk-connect">${T('Connect VK','Подключить VK')}</button>`}</div></div>
    <details class="panel mb"><summary><b>${T('Change Password','Сменить пароль')}</b></summary><div class="mt"><label class="f"><span>${T('Current Password','Текущий пароль')}</span><input id="pf-current-password" type="password" autocomplete="current-password"></label><label class="f"><span>${T('New Password (8+ characters)','Новый пароль (от 8 символов)')}</span><input id="pf-new-password" type="password" minlength="8" autocomplete="new-password"></label><label class="f"><span>${T('Repeat New Password','Повторите новый пароль')}</span><input id="pf-repeat-password" type="password" minlength="8" autocomplete="new-password"></label><button id="pf-change-password">${T('Change Password','Сменить пароль')}</button></div></details>
    <details class="panel mb"><summary><b>${T('Active Login Sessions','Активные сеансы входа')} · ${accountSessions.length}</b></summary><div class="mt">${accountSessions.map(session=>`<div class="inv-row"><div class="iname"><b>${session.current?T('This device','Это устройство'):T('Other device','Другое устройство')}</b><div class="small muted">${esc(session.ip_address||T('unknown IP','неизвестный IP'))} · ${new Date(session.last_seen*1000).toLocaleString()}</div><div class="small muted session-agent">${esc(session.user_agent||T('Unknown browser','Неизвестный браузер'))}</div></div>${session.current?'<span class="tag">CURRENT</span>':`<button class="btn-danger" data-session-revoke="${session.id}">${T('Revoke','Завершить')}</button>`}</div>`).join('')||`<div class="empty">${T('No active sessions.','Нет активных сеансов.')}</div>`}<button class="btn-danger mt" id="pf-logout-all">${T('Sign Out Everywhere','Выйти на всех устройствах')}</button></div></details>
    <div class="row"><button class="btn-primary" id="pf-save">${T('Save','Сохранить')}</button>${state.me.is_admin ? `<a class="btn-sm" href="#/admin">${T('Admin Console','Панель Admin')}</a>` : ''}</div>
  </div>`;
  $('#pf-avatar-file').onchange=()=>openImageCrop($('#pf-avatar-file').files[0],'account_avatar',media=>{avatarMediaId=media.id;$('#pf-avatar-preview').innerHTML=`<img src="${esc(media.url)}" alt="">`;toast(T('Account avatar ready. Save the profile to apply it.','Аватар аккаунта готов. Сохраните профиль, чтобы применить его.'));});
  if ($('#pf-avatar-remove')) $('#pf-avatar-remove').onclick=()=>{avatarMediaId=null;$('#pf-avatar-preview').innerHTML=`<span>${esc((state.me.display_name||state.me.username||'?').slice(0,1).toUpperCase())}</span>`;$('#pf-avatar-remove').disabled=true;};
  if ($('#pf-audio-volume') && typeof NC_AUDIO !== 'undefined') $('#pf-audio-volume').oninput = event => NC_AUDIO.setVolume(event.target.value);
  if ($('#pf-vk-connect')) $('#pf-vk-connect').onclick = async () => {
    try { const result = await api('/api/vk/oauth/start', { method: 'POST' }); location.href = result.url; }
    catch (e) { toast(e.message, true); }
  };
  $('#pf-change-password').onclick=async()=>{const current=$('#pf-current-password').value,next=$('#pf-new-password').value,repeat=$('#pf-repeat-password').value;if(next!==repeat){toast(T('New passwords do not match.','Новые пароли не совпадают.'),true);return;}try{await api('/api/account/password',{method:'POST',body:{current_password:current,new_password:next}});$('#pf-current-password').value='';$('#pf-new-password').value='';$('#pf-repeat-password').value='';toast(T('Password changed. Other sessions were revoked.','Пароль изменён. Остальные сеансы завершены.'));await viewProfile(view);}catch(e){toast(e.message,true);}};
  $$('[data-session-revoke]',view).forEach(button=>button.onclick=async()=>{try{await api(`/api/account/sessions/${button.dataset.sessionRevoke}`,{method:'DELETE'});toast(T('Session revoked.','Сеанс завершён.'));await viewProfile(view);}catch(e){toast(e.message,true);}});
  $('#pf-logout-all').onclick=async()=>{if(!confirm(T('Sign out on every device, including this one?','Выйти на всех устройствах, включая это?')))return;try{await api('/api/account/logout-all',{method:'POST'});}catch(e){}state.me=null;renderUserbox();go('/login');toast(T('All sessions were revoked.','Все сеансы завершены.'));};
  $('#pf-save').onclick = async () => {
    try {
      state.me = await api('/api/profile', { method: 'POST', body: {
        display_name: $('#pf-d').value,
        show_display_name: $('#pf-show-name').checked,
        avatar_media_id: avatarMediaId,
      } });
      renderUserbox();
      toast(T('Profile updated','Профиль обновлён'));
    } catch (e) { toast(e.message, true); }
  };
}

async function viewAdmin(view) {
  if (!state.me || !state.me.is_admin) {
    view.innerHTML = `<div class="empty">⛔ ${T('NC//NET Admin access required.','Требуется доступ Admin NC//NET.')}</div>`;
    return;
  }
  view.innerHTML = spinner();
  const [data,inviteData,backupData] = await Promise.all([api('/api/admin/users'),api('/api/admin/invites'),api('/api/admin/backups')]);
  const counts = Object.fromEntries(['player','gm','admin'].map(role=>[role,data.users.filter(user=>user.account_role===role).length]));
  const invitePanel=`<section class="panel mt"><div class="row" style="justify-content:space-between"><div><h2>${T('Registration Invites','Приглашения')}</h2><div class="small muted">${T('Mode','Режим')}: ${esc(inviteData.registration_mode)}</div></div><button id="admin-invite-new">＋ ${T('Create Invite','Создать приглашение')}</button></div>${inviteData.invites.length?inviteData.invites.map(invite=>`<div class="inv-row"><div class="iname"><b class="user-content">${esc(invite.label||T('Campaign invite','Приглашение в кампанию'))}</b><div class="small muted">${invite.uses}/${invite.max_uses} · ${invite.expires_at?new Date(invite.expires_at*1000).toLocaleString():T('no expiry','без срока')} · ${invite.active?T('active','активно'):T('inactive','неактивно')}</div></div>${invite.active?`<button class="btn-danger" data-invite-revoke="${invite.id}">${T('Revoke','Отозвать')}</button>`:''}</div>`).join(''):`<div class="empty">${T('No invites yet.','Приглашений пока нет.')}</div>`}</section>`;
  const backupPanel=`<section class="panel mt"><div class="row" style="justify-content:space-between"><div><h2>${T('Campaign Backups','Резервные копии кампании')}</h2><div class="small muted">${T('Online SQLite snapshot + uploads · retained','Online snapshot SQLite + uploads · хранится')}: ${backupData.retention}</div></div><button id="admin-backup-create">＋ ${T('Create Backup','Создать копию')}</button></div><p class="small warn-text">${T('Backup bundles contain private campaign data and password hashes. Store downloads securely.','Backup содержит приватные данные кампании и хеши паролей. Храните скачанные файлы безопасно.')}</p>${backupData.backups.length?backupData.backups.map(backup=>`<div class="inv-row"><div class="iname"><b>${esc(backup.name)}</b><div class="small muted">${new Date(backup.created_at*1000).toLocaleString()} · ${(Number(backup.size||0)/1_000_000).toFixed(1)} MB · ${backup.uploads??0} uploads · ${backup.readable?T('readable','читается'):T('damaged','повреждено')}</div></div><a class="btn-sm" href="/api/admin/backups/${encodeURIComponent(backup.name)}/download">${T('Download','Скачать')}</a><button data-backup-verify="${esc(backup.name)}">${T('Verify','Проверить')}</button></div>`).join(''):`<div class="empty">${T('No campaign backups yet.','Резервных копий пока нет.')}</div>`}</section>`;
  view.innerHTML = `<div class="page-head"><div><h1>⚙️ ${T('NC//NET Administration','Администрирование NC//NET')}</h1><div class="sub">${T('Role changes require an explicit reason and are written to the immutable access audit.','Для изменения роли нужна явная причина; действие записывается в неизменяемый журнал доступа.')}</div></div><a class="btn-sm" href="#/gm">GM OPS →</a></div><div class="admin-summary-grid"><div class="panel"><b>${data.users.length}</b><span>${T('Accounts','Аккаунты')}</span></div><div class="panel"><b>${counts.player}</b><span>PLAYER</span></div><div class="panel"><b>${counts.gm}</b><span>GM</span></div><div class="panel"><b>${counts.admin}</b><span>ADMIN</span></div></div><div class="panel mt"><div class="admin-toolbar"><input id="admin-user-search" type="search" placeholder="${T('Search account…','Поиск аккаунта…')}" aria-label="${T('Search accounts','Поиск аккаунтов')}"><select id="admin-role-filter" aria-label="${T('Filter by role','Фильтр по роли')}"><option value="">${T('All roles','Все роли')}</option><option value="player">PLAYER</option><option value="gm">GM</option><option value="admin">ADMIN</option></select><span id="admin-visible-count" class="small muted"></span></div><div class="table-scroll"><table class="rtable admin-users"><thead><tr><th>${T('Account','Аккаунт')}</th><th>${T('Characters','Персонажи')}</th><th>${T('Privacy','Приватность')}</th><th>${T('Network access','Доступ к сети')}</th><th>${T('Required reason','Обязательная причина')}</th><th></th></tr></thead><tbody>${data.users.map(user=>`<tr data-admin-user="${user.id}" data-admin-original-role="${user.account_role}" data-admin-disabled="${user.disabled?'1':'0'}" class="${user.disabled?'disabled-account':''}" data-admin-filter-role="${user.account_role}" data-admin-search="${esc(`${user.display_name} ${user.username} ${user.id}`.toLowerCase())}"><td><b class="user-content">${esc(user.display_name)}</b>${user.disabled?` <span class="tag">${T('DISABLED','ОТКЛЮЧЁН')}</span>`:''}${user.id===state.me.id?` <span class="tag">${T('YOU','ВЫ')}</span>`:''}<div class="small muted">@${esc(user.username)} · #${user.id} · ${new Date(user.created*1000).toLocaleDateString()}</div></td><td>${user.character_count}</td><td>${user.show_display_name?T('Name visible','Имя видно'):T('Hidden','Скрыто')}${user.vk_linked?' · VK ✓':''}</td><td><select data-admin-role aria-label="${T('Role for ','Роль для ')+esc(user.username)}">${['player','gm','admin'].map(role=>`<option value="${role}" ${user.account_role===role?'selected':''}>${role.toUpperCase()}</option>`).join('')}</select><div class="small warn-text" data-admin-self-warning hidden>${T('Changing your own access may close this console.','Изменение собственной роли может закрыть эту панель.')}</div></td><td><input data-admin-reason maxlength="500" placeholder="${T('Why is access changing?','Почему меняется доступ?')}"></td><td><div class="row"><button class="btn-sm" data-admin-apply disabled>${T('Apply Role','Применить роль')}</button><button class="${user.disabled?'btn-sm':'btn-danger'}" data-admin-status>${user.disabled?T('Enable','Включить'):T('Disable','Отключить')}</button></div></td></tr>`).join('')}</tbody></table></div><div id="admin-no-results" class="empty" hidden>${T('No matching accounts.','Подходящих аккаунтов нет.')}</div></div>${invitePanel}${backupPanel}${(data.role_audit||[]).length?`<details class="panel mt" open><summary>${T('Access Audit','Журнал доступа')} · ${data.role_audit.length}</summary><div class="admin-toolbar mt"><input id="admin-audit-search" type="search" placeholder="${T('Search audit…','Поиск по журналу…')}" aria-label="${T('Search access audit','Поиск по журналу доступа')}"></div><div id="admin-audit-list">${data.role_audit.map(entry=>`<div class="admin-audit-row" data-audit-search="${esc(`${entry.target_username} ${entry.actor_username} ${entry.role_before} ${entry.role_after} ${entry.reason}`.toLowerCase())}"><div><b class="user-content">@${esc(entry.target_username)}</b><div class="small muted">${timeAgo(entry.created)}</div></div><span class="tag">${esc(entry.role_before.toUpperCase())} → ${esc(entry.role_after.toUpperCase())}</span><span class="user-content">${esc(entry.reason)}</span><span class="small user-content">${T('by','от')} @${esc(entry.actor_username)}</span></div>`).join('')}</div></details>`:''}${(data.security_audit||[]).length?`<details class="panel mt"><summary>${T('Security Audit','Журнал безопасности')} · ${data.security_audit.length}</summary><div class="mt">${data.security_audit.map(entry=>`<div class="admin-audit-row"><div><b class="user-content">@${esc(entry.target_username)}</b><div class="small muted">${timeAgo(entry.created)}</div></div><span class="tag">${esc(entry.event_type.replaceAll('_',' ').toUpperCase())}</span><span class="user-content">${esc(entry.detail||'—')}</span><span class="small user-content">${T('by','от')} @${esc(entry.actor_username)}</span></div>`).join('')}</div></details>`:''}`;
  $('#admin-invite-new',view).onclick=()=>{const modal=openModal(`<h2>${T('Create Registration Invite','Создать приглашение')}</h2><label class="f"><span>${T('Label','Название')}</span><input id="invite-label" maxlength="120" placeholder="${T('Player name or purpose','Имя игрока или назначение')}"></label><div class="grid cols-2"><label class="f"><span>${T('Maximum uses','Количество использований')}</span><input id="invite-uses" type="number" min="1" max="100" value="1"></label><label class="f"><span>${T('Expires in days','Срок в днях')}</span><input id="invite-days" type="number" min="1" max="365" value="7"></label></div><button class="btn-primary" id="invite-create">${T('Create Invite','Создать приглашение')}</button>`);$('#invite-create',modal).onclick=async()=>{try{const created=await api('/api/admin/invites',{method:'POST',body:{label:$('#invite-label',modal).value,max_uses:Number($('#invite-uses',modal).value)||1,expires_days:Number($('#invite-days',modal).value)||7}});closeModal();prompt(T('Copy this code now. It is shown only once.','Скопируйте код сейчас. Он показывается только один раз.'),created.code);await viewAdmin(view);}catch(e){toast(e.message,true);}};};
  $$('[data-invite-revoke]',view).forEach(button=>button.onclick=async()=>{if(!confirm(T('Revoke this invite?','Отозвать это приглашение?')))return;try{await api(`/api/admin/invites/${button.dataset.inviteRevoke}`,{method:'DELETE'});await viewAdmin(view);}catch(e){toast(e.message,true);}});
  $('#admin-backup-create',view).onclick=async()=>{const reason=prompt(T('Backup label/reason','Название/причина backup'),'manual')||'manual';const button=$('#admin-backup-create',view);button.disabled=true;try{const created=await api('/api/admin/backups',{method:'POST',body:{reason}});toast(T('Campaign backup created: ','Резервная копия создана: ')+created.name);await viewAdmin(view);}catch(e){button.disabled=false;toast(e.message,true);}};
  $$('[data-backup-verify]',view).forEach(button=>button.onclick=async()=>{button.disabled=true;try{const result=await api(`/api/admin/backups/${encodeURIComponent(button.dataset.backupVerify)}/verify`,{method:'POST'});const counts=result.manifest.counts||{};openModal(`<h2>✓ ${T('Backup Verified','Backup проверен')}</h2><p><b>${esc(result.name)}</b></p><div class="kv">${Object.entries(counts).map(([key,value])=>`<b>${esc(key)}</b><span>${value}</span>`).join('')}<b>SHA-256</b><span class="small">${esc(result.sha256)}</span></div><p class="small muted">${T('SQLite integrity and every bundled checksum are valid.','SQLite integrity и все checksum в bundle корректны.')}</p>`,true);}catch(e){toast(e.message,true);}finally{button.disabled=false;}});
  const filterUsers=()=>{const query=$('#admin-user-search',view).value.trim().toLowerCase(),role=$('#admin-role-filter',view).value;let visible=0;$$('[data-admin-user]',view).forEach(row=>{const show=(!query||row.dataset.adminSearch.includes(query))&&(!role||row.dataset.adminFilterRole===role);row.hidden=!show;if(show)visible++;});$('#admin-visible-count',view).textContent=`${visible}/${data.users.length}`;$('#admin-no-results',view).hidden=visible!==0;};
  $('#admin-user-search',view).oninput=filterUsers;$('#admin-role-filter',view).onchange=filterUsers;filterUsers();
  if($('#admin-audit-search',view))$('#admin-audit-search',view).oninput=event=>{const query=event.target.value.trim().toLowerCase();$$('[data-audit-search]',view).forEach(row=>row.hidden=Boolean(query&&!row.dataset.auditSearch.includes(query)));};
  $$('[data-admin-user]',view).forEach(row=>{const role=$('[data-admin-role]',row),reason=$('[data-admin-reason]',row),apply=$('[data-admin-apply]',row),status=$('[data-admin-status]',row),selfWarning=$('[data-admin-self-warning]',row);const validate=()=>{const changed=role.value!==row.dataset.adminOriginalRole,hasReason=reason.value.trim().length>0;apply.disabled=!(changed&&hasReason);status.disabled=!hasReason;if(selfWarning)selfWarning.hidden=!(Number(row.dataset.adminUser)===state.me.id&&changed);};role.onchange=validate;reason.oninput=validate;apply.onclick=async()=>{apply.disabled=true;try{const updated=await api(`/api/admin/users/${row.dataset.adminUser}/role`,{method:'POST',body:{account_role:role.value,reason:reason.value.trim()}});if(state.me.id===Number(row.dataset.adminUser)){state.me=updated;renderUserbox();}toast(T('Network access updated.','Доступ к сети обновлён.'));await viewAdmin(view);}catch(error){validate();toast(error.message,true);}};status.onclick=async()=>{const disabled=row.dataset.adminDisabled!=='1';if(!confirm(disabled?T('Disable this account and revoke all sessions?','Отключить аккаунт и завершить все сеансы?'):T('Enable this account?','Включить аккаунт?')))return;status.disabled=true;try{await api(`/api/admin/users/${row.dataset.adminUser}/status`,{method:'POST',body:{disabled,reason:reason.value.trim()}});toast(disabled?T('Account disabled.','Аккаунт отключён.'):T('Account enabled.','Аккаунт включён.'));await viewAdmin(view);}catch(error){validate();toast(error.message,true);}};validate();});
}

/* ============================== запуск ============================== */

(async function init() {
  window.addEventListener('hashchange', route);
  window.addEventListener('beforeunload', saveWizardDraft);
  initShellControls();
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') saveWizardDraft(); });
  const themeToggle = $('#theme-toggle');
  if (themeToggle) themeToggle.onclick = openThemeSettings;
  const audioToggle = $('#audio-toggle');
  if (audioToggle && typeof NC_AUDIO !== 'undefined') audioToggle.onclick = () => NC_AUDIO.toggle();
  if (typeof NC_AUDIO !== 'undefined') NC_AUDIO.maybeGate();
  const languageToggle = $('#language-toggle');
  if (languageToggle) languageToggle.onclick = () => APP_I18N.toggle();
  window.addEventListener('app-language-change', async () => {
    APP_I18N.apply();
    updateCityClock();
    try {
      const meta = await api('/api/meta');
      state.meta = meta;
      state.meta._total = meta.cats.reduce((sum, category) => sum + category.count, 0);
    } catch (e) { /* Keep the last metadata snapshot if refresh fails. */ }
    route();
  });
  APP_I18N.apply();
  try {
    const [me, meta] = await Promise.all([api('/api/me'), api('/api/meta')]);
    state.me = me.user;
    if (state.me && state.me.theme) APP_THEME.setFromProfile(state.me.theme);
    state.meta = meta;
    state.meta._total = meta.cats.reduce((a, c) => a + c.count, 0);
  } catch (e) {
    $('#view').innerHTML = `<div class="empty">⚠️ ${T('Server unavailable: ','Сервер недоступен: ')}${esc(APP_I18N.translate(e.message))}</div>`;
    return;
  }
  renderUserbox();
  refreshShellDossiers();
  route();
})();
