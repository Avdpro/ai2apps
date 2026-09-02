"""Conservative, user-configured handling for blocking cookie banners."""

from __future__ import annotations

COOKIE_CONSENT_SCRIPT = r"""
const policy = String(arguments[0] || 'all');
const normalize = value => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
const visible = element => {
  if (!element || element.closest('[hidden],[aria-hidden="true"],[inert]')) return false;
  const style = getComputedStyle(element);
  const rect = element.getBoundingClientRect();
  return style.display !== 'none' && style.visibility !== 'hidden' &&
    style.opacity !== '0' && rect.width > 0 && rect.height > 0;
};
const roots = [document];
for (let index = 0; index < roots.length; index++) {
  for (const host of roots[index].querySelectorAll('*')) {
    if (host.shadowRoot && host.shadowRoot.mode === 'open') roots.push(host.shadowRoot);
  }
}
const bannerPattern = /cookie|cookies|consent|privacy|gdpr|tracking|饼干|隐私|同意|쿠키|クッキー/i;
const allPatterns = [
  /^accept all(?: cookies)?$/i, /^allow all$/i, /^agree(?: and continue)?$/i,
  /^i agree$/i, /^got it$/i, /^同意全部$/i, /^全部接受$/i, /^接受所有(?: cookie)?$/i,
  /^すべて(?:のcookieを)?許可$/i, /^모두 허용$/i,
];
const necessaryPatterns = [
  /^only necessary$/i, /^necessary only$/i, /^accept necessary$/i,
  /^reject all$/i, /^continue without accepting$/i, /^仅必要$/i,
  /^只接受必要(?: cookie)?$/i, /^拒绝全部$/i,
];
const patterns = policy === 'necessary' ? necessaryPatterns : allPatterns;
const candidates = roots.flatMap(root => [
  ...root.querySelectorAll('button,[role="button"],input[type="button"],input[type="submit"],a[href]')
]);
for (const element of candidates) {
  if (!visible(element)) continue;
  const label = normalize(element.innerText || element.value || element.getAttribute('aria-label'));
  if (!label || !patterns.some(pattern => pattern.test(label))) continue;
  const container = element.closest(
    '[id*="cookie" i],[class*="cookie" i],[id*="consent" i],[class*="consent" i],'
    + '[aria-label*="cookie" i],[aria-label*="consent" i],[role="dialog"]'
  );
  const context = normalize(container?.innerText || element.parentElement?.innerText || '');
  const labelIsExplicit = /cookie|cookies|同意全部|全部接受|仅必要|拒绝全部|쿠키|クッキー/i.test(label);
  if (!labelIsExplicit && !bannerPattern.test(context)) continue;
  element.click();
  return {handled: true, policy, label: label.slice(0, 160)};
}
return {handled: false, policy, label: null};
"""
