/* Product localization. Guides intentionally remain in their original Russian. */
'use strict';

const APP_I18N = (() => {
  const STORAGE_KEY = 'cbpr-helper:language';
  let language = 'en';
  try { language = localStorage.getItem(STORAGE_KEY) === 'ru' ? 'ru' : 'en'; } catch (e) {}

  function text(en, ru) { return language === 'ru' ? ru : en; }

  function apply(root) {
    const scope = root || document;
    scope.querySelectorAll('[data-en][data-ru]').forEach(el => {
      el.textContent = language === 'ru' ? el.dataset.ru : el.dataset.en;
    });
    scope.querySelectorAll('[data-placeholder-en][data-placeholder-ru]').forEach(el => {
      el.placeholder = language === 'ru' ? el.dataset.placeholderRu : el.dataset.placeholderEn;
    });
    document.documentElement.lang = language;
    const button = document.querySelector('#language-toggle');
    if (button) {
      button.textContent = language === 'en' ? 'RU' : 'EN';
      button.title = language === 'en' ? 'Переключить на русский' : 'Switch to English';
      button.setAttribute('aria-label', button.title);
    }
  }

  function set(next) {
    language = next === 'ru' ? 'ru' : 'en';
    try { localStorage.setItem(STORAGE_KEY, language); } catch (e) {}
    apply();
    window.dispatchEvent(new CustomEvent('app-language-change', { detail: { language } }));
  }

  function toggle() { set(language === 'en' ? 'ru' : 'en'); }
  function current() { return language; }

  return { text, apply, set, toggle, current };
})();

const T = (en, ru) => APP_I18N.text(en, ru);
