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
  'quick-reference': viewCalc, 'gm-ref': viewGmRef, dossiers: viewCharacters, crew: viewRoster,
  stash: viewCrewStash,
  feed: viewCityFeed, contracts: viewContracts, personas: viewPersonas,
  chronicle: viewChronicle, map: viewMap, memorial: viewMemorial,
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
  const moreButton=$('#mobile-more-toggle');if(moreButton)moreButton.classList.toggle('active',['database','market','quick-reference','crew','stash','chronicle','map','memorial','personas','guides','profile','gm','admin'].includes(activeRoute));
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
    if (seg0 === 'map' && seg1) { await viewLocationDetail(view, seg1); return; }
    if (seg0 === 'actions' && seg1) { await viewActions(view, seg1); return; }
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
    <button class="btn-sm" id="notifications-btn" style="position:relative" title="${T('Notifications','Уведомления')}" aria-label="${T('Notifications','Уведомления')}">◉<span id="notif-badge" style="display:none;position:absolute;top:-4px;right:-4px;background:var(--red);color:#fff;font-size:9px;font-weight:700;border-radius:50%;width:16px;height:16px;display:none;align-items:center;justify-content:center"></span></button>
    <button class="btn-sm" id="logout-btn">${T('Sign out','Выйти')}</button>`;
  $('#userchip').onclick = () => go('/profile');
  if ($('#notifications-btn') && typeof openNotifications === 'function') $('#notifications-btn').onclick = openNotifications;
  $('#logout-btn').onclick = performLogout;
  // Poll notifications for badge
  if (state.me) {
    const pollNotifs = async () => {
      try {
        const nd = await api('/api/notifications');
        const badge = $('#notif-badge');
        if (badge) {
          if (nd.unread > 0) { badge.textContent = nd.unread > 9 ? '9+' : nd.unread; badge.style.display = 'flex'; }
          else { badge.style.display = 'none'; }
        }
      } catch (e) {}
    };
    pollNotifs();
    if (!window._notifInterval) window._notifInterval = setInterval(pollNotifs, 30000);
  }
}

function updateCityClock(){const clock=$('#city-clock');if(clock)clock.textContent=new Intl.DateTimeFormat(APP_I18N.current()==='ru'?'ru-RU':'en-GB',{timeZone:'Europe/Moscow',hour:'2-digit',minute:'2-digit',second:'2-digit',hour12:false}).format(new Date())+' NC';}

async function refreshShellDossiers(){
  const wrap=$('#active-dossier-wrap'),select=$('#active-dossier');if(!wrap||!select||!state.me){if(wrap)wrap.hidden=true;return;}
  try{const characters=(await api('/api/characters')).characters.filter(character=>!character.data.archived);if(!characters.length){wrap.hidden=true;return;}const saved=Number(localStorage.getItem('ncnet:active-dossier')),active=characters.some(character=>character.id===saved)?saved:characters[0].id;select.innerHTML=characters.map(character=>`<option value="${character.id}" ${character.id===active?'selected':''}>${esc(character.data.handle||T('Unnamed','Безымянный'))}</option>`).join('');wrap.hidden=false;localStorage.setItem('ncnet:active-dossier',String(active));select.onchange=()=>{localStorage.setItem('ncnet:active-dossier',select.value);go(`/char/${select.value}`);};}catch(error){wrap.hidden=true;}
}

function openCommandPalette(){
  const commands=[['','⌂',T('City Network','Городская сеть')],['contracts','◎',T('Contracts','Контракты')],['feed','≋',T('City Feed','Городская лента')],['dossiers','◇',T('Dossiers','Досье')],['database','▦',T('Database','База данных')],['market','◈',T('Night Market','Ночной рынок')],['quick-reference','◫',T('Quick Reference','Быстрые правила')],['crew','⌘',T('Crew Registry','Реестр команд')],['stash','🎒',T('Crew Stash','Общий склад')],['chronicle','📜',T('Chronicle','Хроника')],['map','🗺️',T('Map','Карта')],['memorial','🥃',T('Memorial','Мемориал')],['personas','◉','Personas'],['guides','▤',T('Archive','Архив')]];if(state.me?.is_gm)commands.push(['gm','⚙','GM OPS'],['gm-ref','⚔',T('GM Reference','Справка GM')]);if(state.me?.is_admin)commands.push(['admin','⚿',T('Admin Console','Панель Admin')]);
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
  const [stats, feed, contracts, locData, nmData] = await Promise.all([api('/api/stats'),api('/api/feed'),api('/api/contracts'),api('/api/locations'),api('/api/nightmarket')]);
  const transmissions=feed.posts.slice(0,5),activeContracts=contracts.contracts.filter(contract=>['open','crew_full','in_progress'].includes(contract.status)).slice(0,6);
  view.innerHTML=`<div class="page-head city-network-head"><div><div class="small muted">NC//NET // CITY NETWORK // RELAY 07</div><h1>${T('Night City Live Grid','Живая сеть Найт-Сити')}</h1><div class="sub">${T('Contracts, transmissions and operator traffic in one encrypted city layer.','Контракты, передачи и трафик операторов в одном зашифрованном слое города.')}</div></div><div class="row"><a class="btn-sm" href="#/feed">${T('TRANSMIT','ПЕРЕДАТЬ')} ↗</a><a class="btn-primary" href="#/contracts">${T('OPEN CONTRACTS','ОТКРЫТЬ CONTRACTS')} →</a></div></div><div class="network-telemetry-strip"><span><b>${nf.format(stats.open_contracts??stats.open_jobs)}</b>${T('OPEN SIGNALS','ОТКРЫТЫХ СИГНАЛОВ')}</span><span><b>${nf.format(stats.feed_posts??stats.news)}</b>${T('TRANSMISSIONS','ПЕРЕДАЧ')}</span><span><b>${nf.format(stats.characters)}</b>${T('DOSSIERS','ДОСЬЕ')}</span><span><b>${nf.format(stats.users)}</b>${T('OPERATORS','ОПЕРАТОРОВ')}</span><span><b>${nf.format(stats.items)}</b>${T('DATABASE OBJECTS','ОБЪЕКТОВ БАЗЫ')}</span></div><div class="city-network-grid"><section class="city-map-console"><div class="console-head"><span>GEOSPATIAL RELAY</span><span class="green">● LIVE</span></div><div id="home-city-map">${typeof ncLayeredMapHtml==='function'?ncLayeredMapHtml(activeContracts,(locData.locations||[]).filter(l=>!l.archived),(nmData.vendors||[])):''}</div></section><aside class="city-signal-column"><section class="signal-module"><div class="console-head"><span>${T('ACTIVE SIGNALS','АКТИВНЫЕ СИГНАЛЫ')}</span><a href="#/contracts">ALL →</a></div><div class="signal-stack">${activeContracts.length?activeContracts.map((contract,index)=>`<button class="city-signal" data-home-contract="${contract.id}"><span class="signal-index">${String(index+1).padStart(2,'0')}</span><span><b class="user-content">${esc(contract.title)}</b><small>${esc(typeof ncDistrictName==='function'?ncDistrictName(contract.district_id):contract.district_id||T('Classified','Секретно'))} · ${esc(typeof ncLabel==='function'?ncLabel(contract.risk_level):contract.risk_level)}</small></span><span class="tag">${contract.crew_count}/${contract.crew_capacity||'∞'}</span></button>`).join(''):`<div class="empty">${T('No active signals.','Нет активных сигналов.')}</div>`}</div></section><section class="signal-module"><div class="console-head"><span>${T('CITY FEED','ГОРОДСКАЯ ЛЕНТА')}</span><a href="#/feed">ALL →</a></div><div class="signal-stack">${transmissions.length?transmissions.map(post=>`<button class="feed-signal" data-home-feed="${post.id}"><span class="tag">${esc(post.format.toUpperCase())}</span><span><b class="user-content">${esc(post.headline||post.body.slice(0,70))}</b><small class="user-content">${esc(post.author?.display_name||'NC//NET')} · ${timeAgo(post.published_at||post.created)}</small></span></button>`).join(''):`<div class="empty">${T('No transmissions.','Нет передач.')}</div>`}</div></section></aside></div><div class="data-layer-strip"><span>DATA LAYER</span><a href="#/market">NIGHT MARKET</a><a href="#/database">DATABASE</a><a href="#/quick-reference">QUICK REF</a><a href="#/crew">CREW REGISTRY</a><a href="#/personas">PERSONAS</a></div>`;
  if(typeof ncBindActivation==='function')ncBindActivation('[data-contract-open]',view,element=>go(`/contracts/${element.dataset.contractOpen}`));
  if(typeof ncBindMapControls==='function')ncBindMapControls(view);
  if(typeof ncBindLayerToggles==='function')ncBindLayerToggles(view);
  if(typeof ncBindActivation==='function')ncBindActivation('[data-poi-open]',view,element=>go('/map/'+element.dataset.poiOpen));
  if(typeof ncBindActivation==='function')ncBindActivation('[data-vendor-open]',view,element=>go('/market'));
  ncBindActivation('[data-poi-open]',view,element=>go('/map/'+element.dataset.poiOpen));
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
            <span class="item-thumb-placeholder">${{'guns':'🔫','ammo':'📦','melee':'⚔️','armor':'🛡️','grenades':'💣','gear':'🔧','fashion':'👕','services':'💼','cyberware':'🦾','net_stuff':'💻','programs':'💾','vehicles':'🏍️','vehicles_upgrades':'⚙️','gun_upgrades':'🔧'}[it.cat]||'📦'}</span><span class="name" data-id="${it.id}">${esc(it.name)}</span>
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
    <button data-tab="fixer" class="${marketState.tab === 'fixer' ? 'active' : ''}">🕵️ ${T('Fixer Requests','Запросы Fixer')}</button>
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
  if (marketState.tab === 'fixer') return loadFixerTab(box);
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
  const itemCard=item=>{const reservedForOther=item.reserved&&selectedBuyer&&item.reserved_character_id!==selectedBuyer.id;const canBuy=!item.sold_out&&!reservedForOther;const stockLabel=item.sold_out?T('SOLD OUT','РАСПРОДАНО'):`${T('In stock','В наличии')}: ${item.stock_remaining}`;const buyLabel=item.sold_out?T('SOLD OUT','РАСПРОДАНО'):(reservedForOther?T('RESERVED','ЗАРЕЗЕРВИРОВАНО'):`${T('Add to Cart','В корзину')} · ${money(item.street_price)}`);return `<article class="card item-card ${canBuy?'':'unavailable'}"><div class="head">${itemThumb(item.cat)}<button class="item-name-button name" data-market-info="${item.id}">${esc(item.name)}</button><span>${item.discount?`<span class="market-price-old">${money(item.price)}</span>`:''}<span class="price">${money(item.street_price)}</span></span></div><div class="chips"><span class="chip">${esc(categoryName(item.cat))}</span>${itemMechanicChips(item)}${item.new_today?`<span class="tag">${T('NEW TODAY','НОВИНКА')}</span>`:''}<span class="chip">${stockLabel}</span>${item.reserved?`<span class="tag warn-tag">${T('RESERVED','РЕЗЕРВ')}${item.reserved_handle?` · ${esc(item.reserved_handle)}`:''}</span>`:''}</div>${item.desc?`<details class="desc-wrap"><summary>${T('Description','Описание')}</summary><div class="desc preserve-lines">${esc(itemDescription(item))}</div></details>`:''}<div class="small muted">${item.source?`📖 ${esc(item.source)} · `:''}${item.discount?`<span class="green-text">${Math.round((1-item.multiplier)*100)}% ${T('below list','ниже каталога')}</span>`:`${Math.round((item.multiplier-1)*100)}% ${T('markup','наценка')}`}</div><div class="row"><button class="info-btn" data-market-info="${item.id}" aria-label="${T('Item details','Описание предмета')}">i</button><button class="btn-sm btn-primary" data-buy-nm="${item.id}" data-price="${item.street_price}" ${canBuy?'':'disabled'}>${buyLabel}</button>${state.me?`<button class="btn-sm" data-fixer-request="${item.id}">${T('Ask Fixer','Через Fixer')}</button>`:''}${state.me&&state.me.is_gm?`<button class="btn-sm" data-market-reserve="${item.id}">${item.reserved?T('Release','Снять резерв'):T('Reserve','Резерв')}</button>`:''}</div></article>`;};
  const itemThumb=cat=>{const icons={'guns':'🔫','ammo':'📦','melee':'⚔️','armor':'🛡️','grenades':'💣','gear':'🔧','fashion':'👕','services':'📋','cyberware':'🦾','net_stuff':'💻','programs':'💾','vehicles':'🏍️','vehicles_upgrades':'⚙️','gun_upgrades':'🔧'};return `<div class="item-thumb" data-cat="${esc(cat)}">${icons[cat]||'📦'}</div>`;};
  const permanentItemCard=item=>`<article class="card item-card permanent"><div class="head">${itemThumb(item.cat)}<button class="item-name-button name" data-market-info="${item.id}">${esc(item.name)}</button><span><span class="price">${money(item.street_price)}</span></span></div><div class="chips"><span class="chip">${esc(categoryName(item.cat))}</span>${itemMechanicChips(item)}<span class="tag">📦 ${T('STOCK','СКЛАД')}</span></div>${item.desc?`<details class="desc-wrap"><summary>${T('Description','Описание')}</summary><div class="desc preserve-lines">${esc(itemDescription(item))}</div></details>`:''}<div class="row"><button class="info-btn" data-market-info="${item.id}">i</button><button class="btn-sm btn-primary" data-buy-nm="${item.id}" data-price="${item.street_price}" data-permanent="true">${T('Buy','Купить')} · ${money(item.street_price)}</button></div></article>`;
  const filterItems=vendor=>{
    const query=marketState.q.trim().toLowerCase();
    let items=vendor.items.filter(item=>(!marketState.cat||item.cat===marketState.cat)&&(!query||`${item.name} ${item.desc||''} ${item.source||''}`.toLowerCase().includes(query))&&(!marketState.affordable||!selectedBuyer||Number(item.street_price)<=Number(selectedBuyer.data.cash||0)));
    const compare={name:(a,b)=>a.name.localeCompare(b.name,APP_I18N.current()==='ru'?'ru':'en'),price_asc:(a,b)=>a.street_price-b.street_price,price_desc:(a,b)=>b.street_price-a.street_price,discount:(a,b)=>a.multiplier-b.multiplier||a.street_price-b.street_price,category:(a,b)=>categoryName(a.cat).localeCompare(categoryName(b.cat))||a.name.localeCompare(b.name)}[marketState.sort]||(()=>0);
    return [...items].sort(compare);
  };
  const visibleVendors=data.vendors.filter(vendor=>!marketState.vendor||vendor.id===marketState.vendor);
  box.innerHTML=`<div class="market-toolbar panel mb"><div class="grid cols-4"><label class="f"><span>${T('Vendor','Продавец')}</span><select id="nm-vendor"><option value="">${T('All Vendors','Все продавцы')}</option>${data.vendors.map(vendor=>`<option value="${vendor.id}" ${marketState.vendor===vendor.id?'selected':''}>${vendor.icon} ${esc(vendorName(vendor))}</option>`).join('')}</select></label><label class="f"><span>${T('Category','Категория')}</span><select id="nm-cat"><option value="">${T('All Categories','Все категории')}</option>${allCategories.map(id=>`<option value="${id}" ${marketState.cat===id?'selected':''}>${esc(categoryName(id))}</option>`).join('')}</select></label><label class="f"><span>${T('Sort','Сортировка')}</span><select id="nm-sort"><option value="discount" ${marketState.sort==='discount'?'selected':''}>${T('Best Deal','Лучшая цена')}</option><option value="price_asc" ${marketState.sort==='price_asc'?'selected':''}>${T('Price: Low to High','Цена: по возрастанию')}</option><option value="price_desc" ${marketState.sort==='price_desc'?'selected':''}>${T('Price: High to Low','Цена: по убыванию')}</option><option value="name" ${marketState.sort==='name'?'selected':''}>${T('Name','Название')}</option><option value="category" ${marketState.sort==='category'?'selected':''}>${T('Category','Категория')}</option></select></label>${characters.length?`<label class="f"><span>${T('Buyer','Покупатель')}</span><select id="nm-buyer">${characters.map(character=>`<option value="${character.id}" ${selectedBuyer?.id===character.id?'selected':''}>${esc(character.data.handle)} · ${money(character.data.cash)}</option>`).join('')}</select></label>`:'<div></div>'}</div><div class="searchbar"><input id="nm-q" value="${esc(marketState.q)}" placeholder="${T('Search current stock…','Поиск по текущему ассортименту…')}"><button id="nm-search">${T('Search','Найти')}</button><label class="checkbox"><input id="nm-affordable" type="checkbox" ${marketState.affordable?'checked':''}> ${T('Affordable only','Только доступное по цене')}</label><span class="small muted">${T('Stock date','Дата ассортимента')}: ${esc(data.date)}</span></div></div>${visibleVendors.map(vendor=>{const items=filterItems(vendor);return `<section class="market-vendor panel mb" style="--vendor:${esc(vendor.accent_color||'#00e5ff')}"><header class="market-vendor-head"><div><h2>${vendor.icon} ${esc(vendorName(vendor))}</h2><p class="muted user-content">${esc(vendorTagline(vendor))}</p></div><div class="row">${vendor.persona_id?`<a class="btn-sm" href="#/personas/${vendor.persona_id}">${T('Vendor Profile','Профиль продавца')}</a>`:''}${vendor.location?`<span class="chip">📍 ${esc(vendor.location)}</span>`:''}<span class="tag">${items.length} ${T('offers','предложений')}</span></div></header>${items.length?`<div class="item-grid">${items.map(itemCard).join('')}</div>`:`<div class="empty">${T('No stock matches these filters.','Нет товаров по выбранным фильтрам.')}</div>`}${vendor.permanent&&vendor.permanent.length?`<h3 class="mt">📦 ${T('Always in stock','Всегда в наличии')}</h3><div class="item-grid">${vendor.permanent.map(permanentItemCard).join('')}</div>`:''}</section>`;}).join('')}`;
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
  $$('[data-buy-nm]', box).forEach(button=>button.onclick=()=>{const card=button.closest('.item-card');addToCart(button.dataset.buyNm,Number(button.dataset.price),'nm',$('.name',card).textContent,button.dataset.permanent==='true');});
  $$('[data-fixer-request]', box).forEach(button=>button.onclick=()=>openFixerRequestModal(button.dataset.fixerRequest));
  $$('[data-market-reserve]', box).forEach(button=>button.onclick=()=>openMarketReserveModal(button.dataset.marketReserve, data));
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
    const inv = [...(ch.data.inventory || []),...(ch.data.cyberware || []).filter(item=>item.state!=='installed')];
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

async function marketCharacters() {
  if (!state.me) return [];
  if (state.me.is_gm) {
    const data = await api('/api/roster');
    return (data.characters || []).filter(c => !c.data.archived);
  }
  const data = await api('/api/characters');
  return (data.characters || []).filter(c => !c.data.archived);
}

async function openFixerRequestModal(itemId) {
  const chars = await marketCharacters();
  if (!chars.length) { toast(T('Create a Character first.','Сначала создайте персонажа.'), true); go('/char/new'); return; }
  const modal = openModal(`<h2>🕵️ ${T('Ask Fixer','Запрос через Fixer')}</h2>
    <p class="muted small">${T('Ask a Fixer to source this item. The GM reviews and fulfils the request.','Попросите Fixer достать этот предмет. ГМ рассматривает и выполняет запрос.')}</p>
    <label class="f"><span>${T('Character','Персонаж')}</span><select id="fxr-char">${chars.map(c=>`<option value="${c.id}">${esc(c.data.handle)}</option>`).join('')}</select></label>
    <label class="f"><span>${T('Note','Заметка')}</span><textarea id="fxr-note" maxlength="1000" rows="2"></textarea></label>
    <div class="row"><button id="fxr-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="fxr-send">${T('Send Request','Отправить')}</button></div>`, true);
  $('#fxr-cancel', modal).onclick = closeModal;
  $('#fxr-send', modal).onclick = async () => {
    try {
      await api('/api/fixer-requests', { method: 'POST', body: { char_id: Number($('#fxr-char', modal).value), item_id: itemId, note: $('#fxr-note', modal).value.trim() } });
      closeModal();
      toast(T('Request sent.','Запрос отправлен.'));
    } catch (e) { toast(e.message, true); }
  };
}

async function openMarketReserveModal(itemId, marketData) {
  const item = (marketData.items || []).find(i => i.id === itemId);
  if (!item) return;
  const chars = await marketCharacters();
  const modal = openModal(`<h2>${T('Reserve Item','Зарезервировать предмет')}</h2>
    <p class="muted small">${esc(item.name)} · ${money(item.street_price)}</p>
    ${item.reserved ? `<p class="small warn-text">${T('Currently reserved','Сейчас зарезервировано')}${item.reserved_handle ? ': ' + esc(item.reserved_handle) : ''}</p>` : ''}
    <label class="f"><span>${T('For character','Для персонажа')}</span><select id="rs-char"><option value="">— ${T('Release','Снять резерв')} —</option>${chars.map(c=>`<option value="${c.id}" ${item.reserved_character_id===c.id?'selected':''}>${esc(c.data.handle)}</option>`).join('')}</select></label>
    <label class="f"><span>${T('Note','Заметка')}</span><input id="rs-note" maxlength="200"></label>
    <div class="row"><button id="rs-cancel">${T('Cancel','Отмена')}</button><button class="btn-primary" id="rs-save">${T('Save','Сохранить')}</button></div>`, true);
  $('#rs-cancel', modal).onclick = closeModal;
  $('#rs-save', modal).onclick = async () => {
    const cid = $('#rs-char', modal).value;
    try {
      await api('/api/nightmarket/reserve', { method: 'POST', body: { item_id: itemId, character_id: cid ? Number(cid) : null, note: $('#rs-note', modal).value.trim() } });
      closeModal();
      toast(T('Reservation updated.','Резерв обновлён.'));
      const box = $('#market-body'); if (box) loadNightMarket(box);
    } catch (e) { toast(e.message, true); }
  };
}

function fixerRequestRow(r) {
  const statusLabel = { pending: T('PENDING','ОЖИДАЕТ'), fulfilled: T('FULFILLED','ВЫПОЛНЕНО'), declined: T('DECLINED','ОТКЛОНЕНО') }[r.status] || r.status;
  const isGm = state.me && state.me.is_gm;
  return `<div class="inv-row"><span class="iname">${esc(r.item_name || 'Item')}</span><span class="small muted">${esc(r.character_name || '')}</span><span class="tag">${esc(statusLabel)}</span>${r.note ? `<span class="small muted">${esc(r.note)}</span>` : ''}${isGm && r.status === 'pending' ? `<button class="btn-sm" data-fixer-resolve="${r.id}">${T('Resolve','Решить')}</button>` : ''}</div>`;
}

async function loadFixerTab(box) {
  if (!state.me) { box.innerHTML = `<div class="empty">${T('Sign in to work with Fixer requests.','Войдите, чтобы работать с запросами Fixer.')} <a href="#/login">${T('Sign in','Войти')}</a></div>`; return; }
  box.innerHTML = spinner();
  const data = await api('/api/fixer-requests');
  const chars = await marketCharacters();
  const requests = data.requests || [];
  box.innerHTML = `
    <div class="panel mb">
      <h2>🕵️ ${T('Request via Fixer','Запрос через Fixer')}</h2>
      <p class="muted small">${T('Ask a Fixer to source an item that is not in the current Night Market. The GM reviews and fulfils requests.','Попросите Fixer достать предмет, которого нет в текущем Night Market. ГМ рассматривает и выполняет запросы.')}</p>
      ${chars.length ? `<div class="row"><label class="f"><span>${T('Character','Персонаж')}</span><select id="fixer-char">${chars.map(c=>`<option value="${c.id}">${esc(c.data.handle)}</option>`).join('')}</select></label><label class="f"><span>${T('What do you need?','Что нужно?')}</span><input id="fixer-item" maxlength="160" placeholder="${T('Item name or description','Название или описание предмета')}"></label></div><label class="f"><span>${T('Note','Заметка')}</span><textarea id="fixer-note" maxlength="1000" rows="2"></textarea></label><div class="row"><button class="btn-primary" id="fixer-send">${T('Send Request','Отправить запрос')}</button></div>` : `<div class="empty">${T('Create a Character to request items.','Создайте персонажа, чтобы отправлять запросы.')}</div>`}
    </div>
    <div class="panel">
      <h3>${T('Requests','Запросы')} (${requests.length})</h3>
      ${requests.length ? requests.map(fixerRequestRow).join('') : `<div class="empty">${T('No requests yet.','Запросов пока нет.')}</div>`}
    </div>`;
  const send = $('#fixer-send', box);
  if (send) send.onclick = async () => {
    const itemName = $('#fixer-item', box).value.trim();
    if (itemName.length < 2) { toast(T('Describe the item.','Опишите предмет.'), true); return; }
    try {
      await api('/api/fixer-requests', { method: 'POST', body: { char_id: Number($('#fixer-char', box).value), item_name: itemName, note: $('#fixer-note', box).value.trim() } });
      toast(T('Request sent to the Fixer.','Запрос отправлен Fixer.'));
      loadFixerTab(box);
    } catch (e) { toast(e.message, true); }
  };
  $$('[data-fixer-resolve]', box).forEach(b => b.onclick = () => openFixerResolveModal(Number(b.dataset.fixerResolve), () => loadFixerTab(box)));
}

async function openFixerResolveModal(id, refresh) {
  const modal = openModal(`<h2>${T('Resolve Fixer Request','Обработать запрос Fixer')}</h2>
    <label class="f"><span>${T('Price (€$)','Цена (€$)')}</span><input id="fx-price" type="number" min="0" max="9999999" value="0"></label>
    <label class="f"><span>${T('Quantity','Количество')}</span><input id="fx-qty" type="number" min="1" max="99" value="1"></label>
    <label class="f"><span>${T('Grant Database item (optional)','Выдать предмет из Database (необязательно)')}</span><input id="fx-grant" maxlength="120" placeholder="${T('Search item name…','Поиск названия…')}"><div id="fx-results"></div></label>
    <label class="f"><span>${T('Note','Заметка')}</span><textarea id="fx-note" maxlength="1000" rows="2"></textarea></label>
    <div class="row"><button class="btn-danger" id="fx-decline">${T('Decline','Отклонить')}</button><button class="btn-primary" id="fx-fulfill">${T('Fulfill','Выполнить')}</button></div>`, true);
  let grantItemId = '';
  const grantInput = $('#fx-grant', modal);
  const search = async () => {
    const q = grantInput.value.trim();
    if (q.length < 2) { $('#fx-results', modal).innerHTML = ''; return; }
    try {
      const data = await api('/api/items?q=' + encodeURIComponent(q) + '&limit=8');
      $('#fx-results', modal).innerHTML = (data.items || []).map(it => `<button class="btn-sm" data-grant-pick="${esc(it.id)}" data-grant-name="${esc(it.name)}">${esc(it.name)} · ${money(it.price || 0)}</button>`).join('');
      $$('[data-grant-pick]', modal).forEach(b => b.onclick = () => { grantItemId = b.dataset.grantPick; grantInput.value = b.dataset.grantName; $('#fx-results', modal).innerHTML = `<span class="tag">${T('Granting','Выдаём')}: ${esc(b.dataset.grantName)}</span>`; });
    } catch (e) { /* пусто */ }
  };
  grantInput.oninput = () => { clearTimeout(grantInput._t); grantInput._t = setTimeout(search, 300); };
  $('#fx-fulfill', modal).onclick = async () => {
    try {
      const body = { action: 'fulfill', price: Number($('#fx-price', modal).value) || 0, qty: Number($('#fx-qty', modal).value) || 1, note: $('#fx-note', modal).value.trim() };
      if (grantItemId) body.grant_item_id = grantItemId;
      await api(`/api/fixer-requests/${id}/resolve`, { method: 'POST', body });
      closeModal();
      toast(T('Request fulfilled.','Запрос выполнен.'));
      refresh();
    } catch (e) { toast(e.message, true); }
  };
  $('#fx-decline', modal).onclick = async () => {
    try {
      await api(`/api/fixer-requests/${id}/resolve`, { method: 'POST', body: { action: 'decline', note: $('#fx-note', modal).value.trim() } });
      closeModal();
      toast(T('Request declined.','Запрос отклонён.'));
      refresh();
    } catch (e) { toast(e.message, true); }
  };
}

function addToCart(id, price, mode, name, permanent=false) {
  const ex = state.cart.find(c => c.id === id && c.mode === mode);
  if (ex) ex.qty++;
  else state.cart.push({ id, price, qty: 1, mode, name: name.replace(/ ·.*/, ''), permanent });
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

// viewCalc вынесена в views-quickref.js (P3-frontend, срез S1)

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

// Мастер создания персонажа (7 шагов) + общие render-хелперы: 1 702 строки,
// 14 top-level констант, ~144 функции — вынесены в views-shared.js (P3-frontend, срез S4).
// Внимание: SPECIALIZED_SKILL_BASES приходит из creation-data.js, поэтому файл грузится после него.
// Редактор персонажа (473 строки, 15 функций, const EDITOR_TABS / ACQUISITION_SOURCES)
// вынесен в views-editor.js (P3-frontend, срез S3)

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
    $$('[data-memorialize]', $('#ro-list')).forEach(el => el.onclick = () => {
      const c = chars.find(x => x.id === Number(el.dataset.memorialize));
      if (c) openMemorializeModal(c);
    });
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
    ${state.me?.is_gm && !ch.archived ? `<button class="btn-sm" data-memorialize="${c.id}">🥃 ${T('Memorial','Мемориал')}</button>` : ''}
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

async function openPersonalStashModal(charId) {
  const modal = openModal('<h2>📦 ' + T('Personal Stash','Личный тайник') + '</h2><div id="ps-list">' + spinner() + '</div>', true);
  try {
    const res = await api('/api/characters/' + charId + '/personal-stash');
    const stash = res.stash || [];
    $('#ps-list', modal).innerHTML = stash.length ? stash.map(item => {
      return '<div class="inv-row"><span class="iname">' + esc(item.custom_name || item.name || item.catalog_item_id) + (item.quantity > 1 ? ' ×' + item.quantity : '') + '</span><button class="btn-sm" data-ps-take="' + esc(item.instance_id) + '">' + T('Take','Взять') + '</button></div>';
    }).join('') : '<div class="empty">' + T('Personal stash is empty.','Личный тайник пуст.') + '</div>';
    $$('[data-ps-take]', modal).forEach(btn => btn.onclick = async () => {
      try { await api('/api/characters/' + charId + '/personal-stash', { method: 'POST', body: { action: 'take', instance_id: btn.dataset.psTake } }); toast(T('Item taken.','Предмет взят.')); closeModal(); viewSheet(charId); } catch (e) { toast(e.message, true); }
    });
  } catch (e) { $('#ps-list', modal).innerHTML = '<div class="empty">⚠️ ' + esc(e.message) + '</div>'; }
}
