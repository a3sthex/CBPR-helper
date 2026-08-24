/* Per-user UI theme settings. */
'use strict';

const APP_THEME = (() => {
  const KEY = 'cbpr-helper:theme';
  const defaults = {
    preset: 'neon', bg: '#0b0e14', bg2: '#111624', panel: '#141a2a', panel2: '#1a2138',
    line: '#26304d', text: '#d7e3f4', muted: '#8fa0bd', primary: '#00e5ff',
    secondary: '#ffd500', accent: '#ff2d78', success: '#3cf28a', danger: '#ff5252', warning: '#ff9d45',
    fontScale: 1, density: 'comfortable', glow: 0.35, reducedMotion: false,
  };
  const presets = {
    neon: {},
    red: {primary:'#ff3b30',secondary:'#f6e652',accent:'#d90000',panel:'#191414',panel2:'#251919',line:'#57302e'},
    arasaka: {primary:'#e8e8e8',secondary:'#ff2435',accent:'#b90818',bg:'#090909',bg2:'#111111',panel:'#171717',panel2:'#202020',line:'#424242'},
    militech: {primary:'#8fb5c7',secondary:'#e0b85c',accent:'#51788c',bg:'#0c1114',bg2:'#131b20',panel:'#192329',panel2:'#22313a',line:'#38505c'},
    afterlife: {primary:'#3cf28a',secondary:'#e6ff70',accent:'#12a65c',bg:'#07110d',bg2:'#0d1d16',panel:'#10251b',panel2:'#163426',line:'#285d43'},
    contrast: {primary:'#00ffff',secondary:'#ffff00',accent:'#ff00ff',bg:'#000000',bg2:'#080808',panel:'#101010',panel2:'#181818',line:'#ffffff',text:'#ffffff',muted:'#d0d0d0'},
  };
  let value = {...defaults};
  try { value = {...defaults, ...JSON.parse(localStorage.getItem(KEY) || '{}')}; } catch (e) {}
  const hex = color => /^#[0-9a-f]{6}$/i.test(color || '');
  function luminance(color) { const rgb=[1,3,5].map(i=>parseInt(color.slice(i,i+2),16)/255).map(v=>v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)); return .2126*rgb[0]+.7152*rgb[1]+.0722*rgb[2]; }
  function contrast(a,b) { const x=luminance(a),y=luminance(b); return (Math.max(x,y)+.05)/(Math.min(x,y)+.05); }
  function apply(next) {
    if (next) value = {...defaults, ...next};
    const root=document.documentElement, vars={bg:'bg',bg2:'bg2',panel:'panel',panel2:'panel2',line:'line',text:'text',muted:'muted',primary:'cyan',secondary:'yellow',accent:'magenta',success:'green',danger:'red',warning:'orange'};
    Object.entries(vars).forEach(([key,css])=>{ if(hex(value[key])) root.style.setProperty(`--${css}`,value[key]); });
    root.style.setProperty('--font-scale',String(Math.max(.85,Math.min(1.3,Number(value.fontScale)||1))));
    root.style.setProperty('--density',value.density==='compact'?'.78':'1');
    root.style.setProperty('--glow-strength',String(Math.max(0,Math.min(1,Number(value.glow)||0))));
    root.classList.toggle('reduced-motion',!!value.reducedMotion);
    try { localStorage.setItem(KEY,JSON.stringify(value)); } catch(e) {}
  }
  function choosePreset(name) { value={...defaults,...(presets[name]||{}),preset:name}; apply(); return value; }
  function get(){return {...value};}
  function setFromProfile(theme){ if(theme&&Object.keys(theme).length){value={...defaults,...theme};apply();} }
  function valid(theme){return hex(theme.bg)&&hex(theme.text)&&contrast(theme.bg,theme.text)>=4.5&&contrast(theme.panel,theme.text)>=4.5;}
  apply();
  return {defaults,presets,apply,choosePreset,get,setFromProfile,contrast,valid};
})();
