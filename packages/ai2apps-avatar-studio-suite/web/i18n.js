(() => {
  'use strict';
  const catalogs = window.AvatarLocales;
  let locale = 'en';
  function normalize(value) {
    const tag = String(value || '').replaceAll('_', '-').toLowerCase();
    if (/^zh-(tw|hk|hant)/.test(tag)) return 'zh-TW';
    if (tag.startsWith('zh')) return 'zh';
    if (tag.startsWith('pt')) return 'pt-BR';
    return Object.keys(catalogs).find(key => key.toLowerCase() === tag) ||
      (catalogs[tag.split('-')[0]] ? tag.split('-')[0] : 'en');
  }
  function t(key, values = {}) {
    return (catalogs[locale][key] || catalogs.en[key] || key)
      .replace(/\{(\w+)\}/g, (_, name) => String(values[name] ?? `{${name}}`));
  }
  function setLocale(value) {
    locale = normalize(value);
    document.documentElement.lang = locale;
    document.querySelectorAll('[data-i18n]').forEach(el => { el.textContent = t(el.dataset.i18n); });
    for (const attr of ['aria-label', 'alt']) {
      document.querySelectorAll(`[data-i18n-${attr}]`).forEach(el => el.setAttribute(attr, t(el.getAttribute(`data-i18n-${attr}`))));
    }
    window.dispatchEvent(new Event('avatar-locale-changed'));
  }
  function presetLabel(label) {
    const match = /^(Standard|Quality|Fast) \((\d+) steps\)$/.exec(label);
    if (match) return t('steps', {name:t(match[1].toLowerCase()), count:match[2]});
    return {'Exact':t('exact'), 'Fast':t('fastPlain'), 'Quality (FP32)':`${t('quality')} (FP32)`, 'Standard':t('standard'), 'Quality':t('quality'), 'Fast (mixed precision)':t('fast')}[label] || label;
  }
  window.AvatarI18n = {t, setLocale, normalize, presetLabel};
  setLocale(new URLSearchParams(window.location.search).get('locale') || navigator.language);
  window.addEventListener('message', event => {
    if (event.source === window.parent && event.data?.type === 'ai2apps.host.context') setLocale(event.data.locale);
  });
})();
