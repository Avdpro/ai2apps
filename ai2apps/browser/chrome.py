"""Visible Chrome runtime with a WebDriver BiDi event connection."""

from __future__ import annotations

import json
import math
import platform
import random
import re
import threading
import time
from collections import deque
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any

from .cookies import COOKIE_CONSENT_SCRIPT
from .models import (
    AuthenticationChallenge,
    BrowserArticle,
    BrowserError,
    BrowserRuntimeConfig,
    BrowserSnapshot,
)

_READABILITY_SOURCE = Path(__file__).with_name("readability.js").read_text(
    encoding="utf-8"
)

_SNAPSHOT_SCRIPT = r"""
const options = arguments[0];
const maxItems = options.maxItems;
const maxText = options.maxText;
const maxHtml = options.maxHtml;
const htmlMode = options.htmlMode;
const selector = [
  'a[href]', 'button', 'input:not([type="hidden"])', 'textarea', 'select',
  '[role="button"]', '[role="link"]', '[contenteditable="true"]'
].join(',');
const allRoots = (root = document) => {
  const roots = [root];
  for (const el of root.querySelectorAll('*')) {
    if (el.shadowRoot && el.shadowRoot.mode === 'open') {
      roots.push(...allRoots(el.shadowRoot));
    }
  }
  return roots;
};
const queryAll = selector => allRoots().flatMap(root => [...root.querySelectorAll(selector)]);
const visible = (el) => {
  if (!el || el.closest('[hidden],[aria-hidden="true"],[inert]')) return false;
  if (typeof el.checkVisibility === 'function' && !el.checkVisibility({
    checkOpacity: true,
    checkVisibilityCSS: true,
  })) return false;
  const style = getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' &&
    style.opacity !== '0' && style.contentVisibility !== 'hidden' &&
    rect.width > 0 && rect.height > 0;
};
const items = [];
if (!Number.isSafeInteger(window.__ai2appsNextElementRef)) {
  window.__ai2appsNextElementRef = 1;
}
if (!(window.__ai2appsElementRefs instanceof WeakMap)) {
  window.__ai2appsElementRefs = new WeakMap();
}
if (!window.__ai2appsRefFingerprints || typeof window.__ai2appsRefFingerprints !== 'object') {
  window.__ai2appsRefFingerprints = Object.create(null);
}
const elementRef = (el) => {
  let ref = window.__ai2appsElementRefs.get(el);
  if (!ref) {
    ref = `e${window.__ai2appsNextElementRef++}`;
    window.__ai2appsElementRefs.set(el, ref);
  }
  if (el.getAttribute('data-ai2apps-ref') !== ref) {
    el.setAttribute('data-ai2apps-ref', ref);
  }
  return ref;
};
const roundedRect = (el) => {
  const rect = el.getBoundingClientRect();
  return [rect.x, rect.y, rect.width, rect.height].map(
    value => Math.round(value * 10) / 10
  );
};
for (const el of queryAll(selector)) {
  if (!visible(el) || items.length >= maxItems) continue;
  const ref = elementRef(el);
  const password = el.matches('input[type="password"]') ||
    ['current-password', 'new-password', 'one-time-code'].includes(el.autocomplete);
  items.push({
    ref,
    tag: el.tagName.toLowerCase(),
    role: el.getAttribute('role'),
    type: el.getAttribute('type'),
    text: password ? '[sensitive field]' :
      String(el.innerText || el.getAttribute('aria-label') ||
             el.getAttribute('placeholder') || el.value || '').trim().slice(0, 300),
    href: el.tagName === 'A' ? el.href : null,
    disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true'),
    sensitive: password,
    rect: roundedRect(el),
  });
  window.__ai2appsRefFingerprints[ref] = {
    tag: el.tagName.toLowerCase(),
    role: el.getAttribute('role') || '',
    type: el.getAttribute('type') || '',
    text: password ? '' : String(
      el.innerText || el.getAttribute('aria-label') ||
      el.getAttribute('placeholder') || el.value || ''
    ).replace(/\s+/g, ' ').trim().slice(0, 300),
    ariaLabel: el.getAttribute('aria-label') || '',
    placeholder: el.getAttribute('placeholder') || '',
    href: el.tagName === 'A' ? el.href : '',
    rect: roundedRect(el),
  };
}
const textParts = [];
let textLength = 0;
if (document.body) {
  const duplicateInteractive = [
    'a[href]', 'button', 'input', 'textarea', 'select',
    '[role="button"]', '[role="link"]', '[contenteditable="true"]'
  ].join(',');
  for (const root of allRoots(document.body)) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    while (walker.nextNode() && textLength < maxText) {
      const node = walker.currentNode;
      const parent = node.parentElement;
      if (!parent || !visible(parent) || parent.closest(duplicateInteractive)) continue;
      if (parent.closest('script,style,noscript,template')) continue;
      const value = String(node.nodeValue || '').replace(/\s+/g, ' ').trim();
      if (value) {
        textParts.push(value);
        textLength += value.length + 1;
      }
    }
  }
}
const escapeText = (value) => String(value)
  .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;');
const escapeAttr = (value) => escapeText(value).replaceAll('"', '&quot;');
const excludedTags = new Set([
  'SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'HEAD', 'META', 'LINK', 'BASE'
]);
const voidTags = new Set([
  'AREA', 'BASE', 'BR', 'COL', 'EMBED', 'HR', 'IMG', 'INPUT', 'LINK',
  'META', 'PARAM', 'SOURCE', 'TRACK', 'WBR'
]);
const keptAttributes = new Set([
  'id', 'name', 'type', 'role', 'href', 'src', 'alt', 'title', 'placeholder',
  'for', 'action', 'method', 'target', 'rel', 'contenteditable', 'tabindex'
]);
const serializeAttributes = (el) => {
  const attrs = [];
  for (const attr of el.attributes) {
    const name = attr.name.toLowerCase();
    if (name.startsWith('on') || name === 'style' || name === 'class' ||
        name === 'value' || name === 'data-ai2apps-ref') continue;
    if (!keptAttributes.has(name) && !name.startsWith('aria-')) continue;
    attrs.push(`${name}="${escapeAttr(attr.value)}"`);
  }
  if (el.disabled) attrs.push('disabled=""');
  if (el.checked) attrs.push('checked=""');
  if (el.selected) attrs.push('selected=""');
  if (el.matches(selector)) attrs.push(`data-ai2apps-ref="${elementRef(el)}"`);
  attrs.push(`data-ai2apps-rect="${roundedRect(el).join(',')}"`);
  return attrs.length ? ' ' + attrs.join(' ') : '';
};
const textIsRendered = (node) => {
  const parent = node.parentElement;
  if (!parent || !visible(parent)) return false;
  const range = document.createRange();
  range.selectNodeContents(node);
  return [...range.getClientRects()].some(rect => rect.width > 0 && rect.height > 0);
};
const snapElement = (el) => {
  if (excludedTags.has(el.tagName)) return '';
  const style = getComputedStyle(el);
  const hardHidden = el.closest('[hidden],[aria-hidden="true"],[inert]') ||
    style.display === 'none' || style.opacity === '0' ||
    style.contentVisibility === 'hidden';
  if (hardHidden) return '';
  const children = [];
  for (const child of el.childNodes) {
    if (child.nodeType === Node.TEXT_NODE) {
      if (textIsRendered(child)) {
        const value = String(child.nodeValue || '').replace(/\s+/g, ' ').trim();
        if (value) children.push(escapeText(value));
      }
    } else if (child.nodeType === Node.ELEMENT_NODE) {
      const value = snapElement(child);
      if (value) children.push(value);
    }
  }
  if (el.shadowRoot && el.shadowRoot.mode === 'open') {
    const shadowChildren = [];
    for (const child of el.shadowRoot.childNodes) {
      if (child.nodeType === Node.TEXT_NODE) {
        const value = String(child.nodeValue || '').replace(/\s+/g, ' ').trim();
        if (value) shadowChildren.push(escapeText(value));
      } else if (child.nodeType === Node.ELEMENT_NODE) {
        const value = snapElement(child);
        if (value) shadowChildren.push(value);
      }
    }
    if (shadowChildren.length) {
      children.push(`<template data-ai2apps-shadow-root="open">${shadowChildren.join('')}</template>`);
    }
  }
  // A zero-sized or visibility-hidden wrapper may contain positioned children
  // which are rendered. Promote those children instead of deleting the subtree.
  if (!visible(el)) return children.join('');
  const tag = el.tagName.toLowerCase();
  const attrs = serializeAttributes(el);
  if (voidTags.has(el.tagName)) return `<${tag}${attrs}>`;
  return `<${tag}${attrs}>${children.join('')}</${tag}>`;
};
let html;
let htmlTruncated = false;
if (htmlMode === 'full') {
  const clone = document.documentElement.cloneNode(true);
  for (const field of clone.querySelectorAll(
    'input[type="password"],[autocomplete="current-password"],'+
    '[autocomplete="new-password"],[autocomplete="one-time-code"]')) {
    field.removeAttribute('value');
  }
  html = '<!doctype html>\n' + clone.outerHTML;
  if (html.length > 2000000) {
    throw new Error('full_html_too_large: document exceeds 2,000,000 characters');
  }
} else {
  html = document.body ? snapElement(document.body) : '';
  if (html.length > maxHtml) {
    html = html.slice(0, maxHtml) + '<!-- ai2apps:truncated -->';
    htmlTruncated = true;
  }
}
return {
  url: location.href,
  title: document.title,
  items,
  text: textParts.join(' ').replace(/\s+/g, ' ').trim().slice(0, maxText),
  html,
  htmlMode,
  htmlTruncated,
};
"""

_AUTH_SCRIPT = r"""
const roots = [document];
for (let index = 0; index < roots.length; index++) {
  for (const host of roots[index].querySelectorAll('*')) {
    if (host.shadowRoot) roots.push(host.shadowRoot);
  }
}
const visible = (el) => {
  if (!el) return false;
  const style = getComputedStyle(el);
  const rect = el.getBoundingClientRect();
  return style.visibility !== 'hidden' && style.display !== 'none' &&
    rect.width > 0 && rect.height > 0;
};
const firstVisible = (selector) => roots.flatMap(
  root => [...root.querySelectorAll(selector)]
).find(visible);
const password = firstVisible('input[type="password"],'+
  'input[autocomplete="current-password"],input[autocomplete="new-password"]');
if (password) return {kind: 'login', reason: 'A password field is present'};
const otp = firstVisible('input[autocomplete="one-time-code"],'+
  'input[name*="otp" i],input[id*="otp" i],input[name*="verification" i]');
if (otp) return {kind: 'two_factor', reason: 'A verification-code field is present'};
const captcha = firstVisible(
  'iframe[src*="captcha" i],iframe[title*="captcha" i],'+
  '[id*="captcha" i],[class*="captcha" i],'+
  '[id*="challenge" i][role], [class*="challenge" i][role]');
if (captcha) return {kind: 'captcha', reason: 'A CAPTCHA or browser challenge is present'};
return null;
"""

_ARTICLE_SCRIPT = r"""
const options = arguments[0];
const liveDocument = document;
const clone = document.cloneNode(true);
const warnings = [];
let hiddenNodesRemoved = 0;

const hardHidden = (el) => {
  if (!el || !el.isConnected) return false;
  if (el.closest('[hidden],[aria-hidden="true"],[inert]')) return true;
  const style = getComputedStyle(el);
  return style.display === 'none' || style.visibility === 'hidden' ||
    style.visibility === 'collapse' || style.opacity === '0' ||
    style.contentVisibility === 'hidden';
};

// The live and cloned trees have identical child ordering at this point. Use
// computed style from the rendered page while deleting only from the clone.
const pruneHiddenPair = (liveNode, cloneNode) => {
  const liveChildren = [...liveNode.childNodes];
  const cloneChildren = [...cloneNode.childNodes];
  for (let index = liveChildren.length - 1; index >= 0; index--) {
    const liveChild = liveChildren[index];
    const cloneChild = cloneChildren[index];
    if (!cloneChild) continue;
    if (liveChild.nodeType === Node.ELEMENT_NODE && hardHidden(liveChild)) {
      cloneChild.remove();
      hiddenNodesRemoved += 1;
      continue;
    }
    if (liveChild.nodeType === Node.ELEMENT_NODE) {
      pruneHiddenPair(liveChild, cloneChild);
    }
  }
};
if (liveDocument.body && clone.body) pruneHiddenPair(liveDocument.body, clone.body);

const canonical = liveDocument.querySelector('link[rel~="canonical"][href]');
const canonicalUrl = canonical ? canonical.href : null;
const sourceForFallback = clone.cloneNode(true);
let parsed = null;
let extractionMethod = 'readability';

if (options.selector) {
  let selected;
  try {
    selected = clone.querySelector(options.selector);
  } catch (error) {
    throw new Error(`invalid_article_selector: ${error.message}`);
  }
  if (!selected) throw new Error('article_selector_not_found');
  parsed = {
    title: liveDocument.title || null,
    byline: null,
    dir: selected.getAttribute('dir') || liveDocument.dir || null,
    lang: selected.getAttribute('lang') || liveDocument.documentElement.lang || null,
    content: selected.innerHTML,
    textContent: selected.textContent || '',
    excerpt: null,
    siteName: null,
    publishedTime: null,
  };
  extractionMethod = 'selector';
} else {
  const Reader = globalThis.__ai2appsReadability;
  if (typeof Reader !== 'function') throw new Error('readability_not_loaded');
  for (const code of clone.querySelectorAll('pre code')) {
    const languageClass = [...code.classList].find(
      value => value.startsWith('language-') || value.startsWith('lang-')
    );
    if (languageClass) {
      code.setAttribute(
        'data-ai2apps-code-lang', languageClass.replace(/^(language-|lang-)/, '')
      );
    }
  }
  try {
    parsed = new Reader(clone, {
      charThreshold: options.charThreshold,
      maxElemsToParse: options.maxElements,
      keepClasses: false,
    }).parse();
  } catch (error) {
    if (options.mode === 'strict') throw error;
    warnings.push(`Readability failed (${error.message}); visible-content fallback was used.`);
  }
}

if (!parsed) {
  if (options.mode === 'strict') throw new Error('article_not_found');
  const fallback = sourceForFallback.querySelector(
    'article,main,[role="main"]'
  ) || sourceForFallback.body;
  if (!fallback) throw new Error('article_not_found');
  parsed = {
    title: liveDocument.title || null,
    byline: null,
    dir: fallback.getAttribute('dir') || liveDocument.dir || null,
    lang: fallback.getAttribute('lang') || liveDocument.documentElement.lang || null,
    content: fallback.innerHTML,
    textContent: fallback.textContent || '',
    excerpt: null,
    siteName: null,
    publishedTime: null,
  };
  extractionMethod = fallback === sourceForFallback.body ? 'visible-body' : 'semantic-main';
  warnings.push('Readability did not find an article; semantic visible-content fallback was used.');
}

const holder = liveDocument.createElement('div');
holder.innerHTML = parsed.content || '';
const forbidden = new Set([
  'SCRIPT','STYLE','NOSCRIPT','TEMPLATE','FORM','INPUT','BUTTON','TEXTAREA',
  'SELECT','OPTION','IFRAME','FRAME','OBJECT','EMBED','APPLET','PORTAL','DIALOG'
]);
const allowed = new Set([
  'A','ABBR','ADDRESS','ARTICLE','ASIDE','AUDIO','B','BDI','BDO','BLOCKQUOTE',
  'BR','CAPTION','CITE','CODE','COL','COLGROUP','DD','DEL','DETAILS','DFN','DIV',
  'DL','DT','EM','FIGCAPTION','FIGURE','H1','H2','H3','H4','H5','H6','HEADER',
  'HGROUP','HR','I','IMG','INS','KBD','LI','MAIN','MARK','MATH','OL','P','PICTURE',
  'PRE','Q','S','SAMP','SECTION','SMALL','SOURCE','SPAN','STRONG','SUB','SUMMARY',
  'SUP','TABLE','TBODY','TD','TFOOT','TH','THEAD','TIME','TR','U','UL','VAR','VIDEO'
]);
const globalAttrs = new Set(['title','lang','dir']);
const attrsByTag = {
  A: new Set(['href','rel']), IMG: new Set(['src','srcset','alt','width','height']),
  SOURCE: new Set(['src','srcset','type','media']), VIDEO: new Set(['src','poster','controls']),
  AUDIO: new Set(['src','controls']), TIME: new Set(['datetime']),
  OL: new Set(['start','reversed']), LI: new Set(['value']),
  TD: new Set(['colspan','rowspan','headers']), TH: new Set(['colspan','rowspan','scope','headers']),
  CODE: new Set(['data-ai2apps-code-lang'])
};
const safeUrl = (value, image) => {
  const normalized = String(value || '').trim().toLowerCase();
  if (!normalized) return false;
  if (normalized.startsWith('javascript:') || normalized.startsWith('vbscript:')) return false;
  if (normalized.startsWith('data:')) return image && normalized.startsWith('data:image/');
  return true;
};
const unwrap = (node) => {
  const parent = node.parentNode;
  if (!parent) return;
  while (node.firstChild) parent.insertBefore(node.firstChild, node);
  node.remove();
};

for (const node of [...holder.querySelectorAll('*')].reverse()) {
  if (forbidden.has(node.tagName)) {
    node.remove();
    continue;
  }
  if (!allowed.has(node.tagName)) {
    unwrap(node);
    continue;
  }
  if (!options.includeImages && ['IMG','PICTURE','SOURCE'].includes(node.tagName)) {
    node.remove();
    continue;
  }
  if (!options.includeLinks && node.tagName === 'A') {
    unwrap(node);
    continue;
  }
  for (const attr of [...node.attributes]) {
    const name = attr.name.toLowerCase();
    const tagAttrs = attrsByTag[node.tagName] || new Set();
    if (!globalAttrs.has(name) && !tagAttrs.has(name)) {
      node.removeAttribute(attr.name);
      continue;
    }
    if (['href','src','poster'].includes(name) &&
        !safeUrl(attr.value, node.tagName === 'IMG')) {
      node.removeAttribute(attr.name);
    }
  }
  if (node.tagName === 'A' && node.hasAttribute('href')) {
    node.setAttribute('rel', 'noopener noreferrer');
  }
}

let truncated = false;
const fullText = String(holder.textContent || '').replace(/\s+/g, ' ').trim();
if (fullText.length > options.maxChars) {
  truncated = true;
  warnings.push(`Article was truncated to ${options.maxChars} text characters.`);
  let remaining = options.maxChars;
  const walker = liveDocument.createTreeWalker(holder, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);
  for (const textNode of textNodes) {
    if (remaining <= 0) {
      textNode.remove();
      continue;
    }
    const value = textNode.nodeValue || '';
    if (value.length <= remaining) {
      remaining -= value.length;
      continue;
    }
    let cut = value.slice(0, remaining);
    const boundary = cut.lastIndexOf(' ');
    if (boundary > remaining * 0.75) cut = cut.slice(0, boundary);
    textNode.nodeValue = cut + '…';
    remaining = 0;
  }
  for (const empty of [...holder.querySelectorAll('*')].reverse()) {
    if (!empty.textContent.trim() && !empty.querySelector('img,video,audio,hr,br')) empty.remove();
  }
}

const text = String(holder.textContent || '').replace(/\s+/g, ' ').trim();
const cjkCount = (text.match(/[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]/g) || []).length;
const latinCount = (text.replace(/[\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff\uac00-\ud7af]/g, ' ').match(/[\p{L}\p{N}]+/gu) || []).length;
const readingUnits = cjkCount + latinCount;
let confidence = 'low';
if (extractionMethod === 'readability' && text.length >= 1000) confidence = 'high';
else if (extractionMethod === 'readability' || text.length >= options.charThreshold) confidence = 'medium';

return {
  url: location.href,
  canonicalUrl,
  title: parsed.title || liveDocument.title || null,
  byline: parsed.byline || null,
  siteName: parsed.siteName || null,
  publishedAt: parsed.publishedTime || null,
  language: parsed.lang || liveDocument.documentElement.lang || null,
  direction: parsed.dir || liveDocument.dir || null,
  excerpt: parsed.excerpt || null,
  html: holder.innerHTML,
  text,
  textLength: text.length,
  readingTimeMinutes: Math.max(1, Math.ceil(readingUnits / 250)),
  extractionMethod,
  confidence,
  truncated,
  warnings,
  hiddenNodesRemoved,
};
"""

_TARGET_INFO_SCRIPT = r"""
const target = arguments[0];
const selector = target && /^e\d+$/.test(target)
  ? `[data-ai2apps-ref="${CSS.escape(target)}"]` : target;
const deepFind = (root, selector) => {
  const found = root.querySelector(selector);
  if (found) return found;
  for (const host of root.querySelectorAll('*')) {
    if (host.shadowRoot) {
      const nested = deepFind(host.shadowRoot, selector);
      if (nested) return nested;
    }
  }
  return null;
};
const el = selector ? deepFind(document, selector) : document.activeElement;
if (!el) return null;
return {
  tag: el.tagName.toLowerCase(),
  type: String(el.getAttribute('type') || '').toLowerCase(),
  autocomplete: String(el.getAttribute('autocomplete') || '').toLowerCase(),
  text: String(el.innerText || el.value || el.getAttribute('aria-label') || '').trim().slice(0, 300),
  submits: Boolean(
    el.matches('button[type="submit"],input[type="submit"],input[type="image"]') ||
    el.closest('form')
  ),
};
"""

_RELOCATE_SCRIPT = r"""
const ref = arguments[0];
const fingerprint = window.__ai2appsRefFingerprints?.[ref];
if (!fingerprint) return {status:'missing_fingerprint'};
const selector = [
  'a[href]', 'button', 'input:not([type="hidden"])', 'textarea', 'select',
  '[role="button"]', '[role="link"]', '[contenteditable="true"]'
].join(',');
const allRoots = (root = document) => {
  const roots = [root];
  for (const el of root.querySelectorAll('*')) {
    if (el.shadowRoot) roots.push(...allRoots(el.shadowRoot));
  }
  return roots;
};
const normalize = value => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
const tokens = value => new Set(normalize(value).split(/[^\p{L}\p{N}]+/u).filter(Boolean));
const similarity = (left, right) => {
  left = normalize(left); right = normalize(right);
  if (!left || !right) return 0;
  if (left === right) return 1;
  const a = tokens(left), b = tokens(right);
  const intersection = [...a].filter(value => b.has(value)).length;
  const union = new Set([...a, ...b]).size;
  return union ? intersection / union : 0;
};
const visible = el => {
  if (!el || el.closest('[hidden],[aria-hidden="true"],[inert]')) return false;
  const style = getComputedStyle(el), rect = el.getBoundingClientRect();
  return style.display !== 'none' && style.visibility !== 'hidden' &&
    style.opacity !== '0' && rect.width > 0 && rect.height > 0;
};
const scored = [];
for (const root of allRoots()) for (const el of root.querySelectorAll(selector)) {
  if (!visible(el)) continue;
  const rect = el.getBoundingClientRect();
  const candidate = {
    tag: el.tagName.toLowerCase(), role: el.getAttribute('role') || '',
    type: el.getAttribute('type') || '',
    text: String(el.innerText || el.getAttribute('aria-label') ||
      el.getAttribute('placeholder') || el.value || '').slice(0, 300),
    ariaLabel: el.getAttribute('aria-label') || '',
    placeholder: el.getAttribute('placeholder') || '',
    href: el.tagName === 'A' ? el.href : '',
  };
  let score = candidate.tag === fingerprint.tag ? 3 : -5;
  if (fingerprint.role) score += candidate.role === fingerprint.role ? 2 : -1;
  if (fingerprint.type) score += candidate.type === fingerprint.type ? 2 : -1;
  if (fingerprint.href) score += candidate.href === fingerprint.href ? 5 : -1;
  score += similarity(candidate.text, fingerprint.text) * 6;
  score += similarity(candidate.ariaLabel, fingerprint.ariaLabel) * 3;
  score += similarity(candidate.placeholder, fingerprint.placeholder) * 3;
  if (fingerprint.rect?.length === 4) {
    const oldX = fingerprint.rect[0] + fingerprint.rect[2] / 2;
    const oldY = fingerprint.rect[1] + fingerprint.rect[3] / 2;
    const distance = Math.hypot(rect.left + rect.width / 2 - oldX,
      rect.top + rect.height / 2 - oldY);
    score += Math.max(0, 2 - distance / 400);
  }
  scored.push({el, score, candidate});
}
scored.sort((a, b) => b.score - a.score);
const best = scored[0], second = scored[1];
if (!best || best.score < 8) {
  return {status:'not_found', bestScore:best?.score || 0};
}
if (second && best.score - second.score < 2.5) {
  return {
    status:'ambiguous', bestScore:best.score, secondScore:second.score,
    candidates:scored.slice(0, 3).map(item => ({
      tag:item.candidate.tag, text:item.candidate.text, score:item.score
    }))
  };
}
best.el.setAttribute('data-ai2apps-ref', ref);
window.__ai2appsElementRefs?.set(best.el, ref);
window.__ai2appsRefFingerprints[ref] = {
  ...fingerprint, ...best.candidate,
  rect:[best.el.getBoundingClientRect().x, best.el.getBoundingClientRect().y,
        best.el.getBoundingClientRect().width, best.el.getBoundingClientRect().height]
};
return {status:'relocated', score:best.score, tag:best.candidate.tag,
        text:best.candidate.text};
"""

_FIND_TARGET_SCRIPT = r"""
const selector = arguments[0];
const deepFind = (root) => {
  const found = root.querySelector(selector);
  if (found) return found;
  for (const host of root.querySelectorAll('*')) {
    if (host.shadowRoot) {
      const nested = deepFind(host.shadowRoot);
      if (nested) return nested;
    }
  }
  return null;
};
return deepFind(document);
"""

_INSTALL_STABILITY_OBSERVER_SCRIPT = r"""
if (!window.__ai2appsDomStability) {
  window.__ai2appsDomStability = {lastMutation: performance.now(), count: 0};
  new MutationObserver(() => {
    window.__ai2appsDomStability.lastMutation = performance.now();
    window.__ai2appsDomStability.count += 1;
  }).observe(document.documentElement, {subtree:true, childList:true, attributes:true, characterData:true});
}
return {readyState:document.readyState,
        quietMs:performance.now()-window.__ai2appsDomStability.lastMutation,
        mutations:window.__ai2appsDomStability.count};
"""


class _BiDiEventClient:
    """Small event-only BiDi client; commands remain standards-based WebDriver."""

    def __init__(self, url: str) -> None:
        self.url = url
        self.events: deque[dict[str, Any]] = deque(maxlen=100)
        self._socket = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        try:
            import websocket
        except ImportError as exc:  # provided by selenium
            raise BrowserError(
                "browser_dependency_missing",
                "websocket-client is required for WebDriver BiDi events",
            ) from exc
        self._socket = websocket.create_connection(self.url, timeout=5)
        self._socket.send(
            json.dumps(
                {
                    "id": 1,
                    "method": "session.subscribe",
                    "params": {
                        "events": [
                            "browsingContext.navigationStarted",
                            "browsingContext.domContentLoaded",
                            "browsingContext.load",
                        ]
                    },
                }
            )
        )
        response = json.loads(self._socket.recv())
        if response.get("error"):
            raise BrowserError("bidi_subscribe_failed", str(response))
        self._socket.settimeout(0.5)
        self._thread = threading.Thread(
            target=self._listen, name="ai2apps-browser-bidi", daemon=True
        )
        self._thread.start()

    def _listen(self) -> None:
        while not self._stop.is_set() and self._socket is not None:
            try:
                message = json.loads(self._socket.recv())
            except Exception as exc:
                if type(exc).__name__ == "WebSocketTimeoutException":
                    continue
                return
            if "method" in message:
                params = message.get("params") or {}
                self.events.append(
                    {
                        "method": message["method"],
                        "url": params.get("url"),
                        "timestamp": params.get("timestamp"),
                    }
                )

    def close(self) -> None:
        self._stop.set()
        if self._socket is not None:
            with suppress(Exception):
                self._socket.close()
        if self._thread is not None:
            self._thread.join(timeout=2)

    @property
    def connected(self) -> bool:
        return self._socket is not None and bool(
            self._thread is not None and self._thread.is_alive()
        )


class ChromeBrowserBackend:
    """Selenium creates the session; the session exposes a real BiDi socket."""

    engine = "chromium"

    def __init__(self, config: BrowserRuntimeConfig) -> None:
        self.config = config
        self.driver = None
        self.bidi: _BiDiEventClient | None = None
        self._pointer_position: tuple[int, int] | None = None
        self._download_directory: Path | None = None
        self._context_refs: dict[str, tuple[tuple[int, ...], str]] = {}
        self._context_frame_elements: dict[str, tuple[Any, ...]] = {}

    def set_download_directory(self, path: str | Path) -> None:
        resolved = Path(path).expanduser().resolve()
        resolved.mkdir(parents=True, exist_ok=True)
        if self.driver is not None and resolved != self._download_directory:
            raise BrowserError(
                "download_directory_locked",
                "Chrome must be restarted before changing its Session download directory",
            )
        self._download_directory = resolved

    def start(self) -> None:
        if self.driver is not None:
            return
        try:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            from selenium.webdriver.chrome.service import Service
        except ImportError as exc:
            raise BrowserError(
                "browser_dependency_missing",
                "Install AI2Apps with the browser extra: pip install 'ai2apps[browser]'",
            ) from exc
        profile = Path(self.config.profile_path).expanduser().resolve()
        profile.mkdir(parents=True, exist_ok=True)
        options = Options()
        if self.config.binary_path:
            options.binary_location = self.config.binary_path
        options.web_socket_url = True
        options.add_argument(f"--user-data-dir={profile}")
        options.add_argument("--no-first-run")
        options.add_argument("--no-default-browser-check")
        if self.config.headless:
            options.add_argument("--headless=new")
        options.add_experimental_option(
            "prefs",
            {
                "credentials_enable_service": False,
                "profile.password_manager_enabled": False,
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True,
                **(
                    {"download.default_directory": str(self._download_directory)}
                    if self._download_directory is not None
                    else {}
                ),
            },
        )
        service = Service(executable_path=self.config.driver_path)
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(self.config.page_load_timeout_seconds)
            bidi_url = self.driver.capabilities.get("webSocketUrl")
            if not bidi_url:
                raise BrowserError(
                    "bidi_unavailable",
                    "ChromeDriver did not expose a WebDriver BiDi URL",
                )
            self.bidi = _BiDiEventClient(str(bidi_url))
            self.bidi.start()
        except Exception:
            self.stop()
            raise

    @property
    def bidi_connected(self) -> bool:
        return self.bidi is not None and self.bidi.connected

    def recent_events(self) -> list[dict[str, Any]]:
        return [] if self.bidi is None else list(self.bidi.events)

    def stop(self) -> None:
        if self.bidi is not None:
            self.bidi.close()
            self.bidi = None
        if self.driver is not None:
            try:
                self.driver.quit()
            finally:
                self.driver = None

    def navigate(self, url: str) -> None:
        self._driver().get(url)
        self._pointer_position = None
        self._context_refs.clear()
        self._context_frame_elements.clear()

    def current(self) -> tuple[str, str]:
        driver = self._driver()
        return driver.current_url, driver.title

    def tabs(self) -> list[dict[str, Any]]:
        driver = self._driver()
        active = driver.current_window_handle
        result = []
        for handle in driver.window_handles:
            driver.switch_to.window(handle)
            result.append(
                {
                    "id": handle,
                    "url": driver.current_url,
                    "title": driver.title,
                    "active": handle == active,
                }
            )
        if active in driver.window_handles:
            driver.switch_to.window(active)
        return result

    def open_tab(self, url: str | None = None) -> str:
        driver = self._driver()
        driver.switch_to.new_window("tab")
        self._pointer_position = None
        if url:
            driver.get(url)
        return driver.current_window_handle

    def switch_tab(self, tab_id: str) -> None:
        driver = self._driver()
        if tab_id not in driver.window_handles:
            raise BrowserError("tab_not_found", f"Browser tab not found: {tab_id}")
        driver.switch_to.window(tab_id)
        self._pointer_position = None

    def close_tab(self, tab_id: str) -> str:
        driver = self._driver()
        handles = driver.window_handles
        if tab_id not in handles:
            raise BrowserError("tab_not_found", f"Browser tab not found: {tab_id}")
        if len(handles) == 1:
            raise BrowserError("last_tab", "The final browser tab cannot be closed")
        driver.switch_to.window(tab_id)
        driver.close()
        remaining = driver.window_handles
        driver.switch_to.window(remaining[-1])
        self._pointer_position = None
        return driver.current_window_handle

    def detect_authentication(self) -> AuthenticationChallenge | None:
        from selenium.webdriver.common.by import By

        driver = self._driver()
        driver.switch_to.default_content()

        def inspect() -> dict[str, Any] | None:
            result = driver.execute_script(_AUTH_SCRIPT)
            if result:
                return result
            for frame in driver.find_elements(By.CSS_SELECTOR, "iframe,frame"):
                switched = False
                try:
                    driver.switch_to.frame(frame)
                    switched = True
                    nested = inspect()
                    if nested:
                        return nested
                except Exception:
                    pass
                finally:
                    if switched:
                        driver.switch_to.parent_frame()
            return None

        try:
            result = inspect()
        finally:
            driver.switch_to.default_content()
        if not result:
            return None
        return AuthenticationChallenge(str(result["kind"]), str(result["reason"]))

    def accept_cookie_consent(self, policy: str = "all") -> dict[str, Any]:
        result = self._driver().execute_script(COOKIE_CONSENT_SCRIPT, policy)
        return dict(result or {})

    def _rendered_text_all_contexts(self) -> str:
        from selenium.webdriver.common.by import By

        driver = self._driver()
        driver.switch_to.default_content()
        parts: list[str] = []

        def collect() -> None:
            value = driver.execute_script(
                """
                const roots=[document];
                for(let i=0;i<roots.length;i++) for(const host of roots[i].querySelectorAll('*'))
                  if(host.shadowRoot) roots.push(host.shadowRoot);
                return roots.map(root => root.body?.innerText || root.host?.shadowRoot?.textContent || '')
                  .filter(Boolean).join(' ');
                """
            )
            if value:
                parts.append(str(value))
            for frame in driver.find_elements(By.CSS_SELECTOR, "iframe,frame"):
                switched = False
                try:
                    driver.switch_to.frame(frame)
                    switched = True
                    collect()
                except Exception:
                    pass
                finally:
                    if switched:
                        driver.switch_to.parent_frame()

        try:
            collect()
        finally:
            driver.switch_to.default_content()
        return " ".join(parts)

    def snapshot(
        self,
        *,
        max_items: int,
        max_text: int,
        html_mode: str,
        max_html: int,
    ) -> BrowserSnapshot:
        from selenium.webdriver.common.by import By

        driver = self._driver()
        driver.switch_to.default_content()
        page_url, page_title = driver.current_url, driver.title
        items: list[dict[str, Any]] = []
        text_parts: list[str] = []
        frame_html: list[str] = []
        self._context_refs = {}
        self._context_frame_elements = {}

        def capture(
            path: tuple[int, ...],
            offset_x: float,
            offset_y: float,
            frame_chain: tuple[Any, ...],
        ) -> dict:
            remaining_items = max(0, max_items - len(items))
            remaining_text = max(0, max_text - sum(len(value) for value in text_parts))
            result = driver.execute_script(
                _SNAPSHOT_SCRIPT,
                {
                    "maxItems": remaining_items,
                    "maxText": remaining_text,
                    "htmlMode": html_mode,
                    "maxHtml": max_html,
                },
            )
            context_name = ".".join(str(value) for value in path)
            prefix = f"f{context_name}:" if path else ""
            context_html = str(result["html"])
            for raw in result["items"]:
                item = dict(raw)
                local_ref = str(item["ref"])
                public_ref = prefix + local_ref
                self._context_refs[public_ref] = (path, local_ref)
                self._context_frame_elements[public_ref] = frame_chain
                item["ref"] = public_ref
                item["context"] = "top" if not path else f"frame:{context_name}"
                rect = list(item.get("rect") or ())
                if len(rect) == 4:
                    rect[0] = round(float(rect[0]) + offset_x, 1)
                    rect[1] = round(float(rect[1]) + offset_y, 1)
                    item["rect"] = rect
                items.append(item)
                if prefix:
                    context_html = context_html.replace(
                        f'data-ai2apps-ref="{local_ref}"',
                        f'data-ai2apps-ref="{public_ref}"',
                    )
            if result.get("text"):
                text_parts.append(str(result["text"]))
            frames = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
            for index, frame in enumerate(frames):
                if len(items) >= max_items:
                    break
                rect = driver.execute_script(
                    "const r=arguments[0].getBoundingClientRect();"
                    "return {x:r.x,y:r.y,w:r.width,h:r.height};",
                    frame,
                )
                switched = False
                try:
                    driver.switch_to.frame(frame)
                    switched = True
                    child_path = path + (index,)
                    child = capture(
                        child_path,
                        offset_x + float(rect["x"]),
                        offset_y + float(rect["y"]),
                        frame_chain + (frame,),
                    )
                    child_name = ".".join(str(value) for value in child_path)
                    frame_html.append(
                        f'<template data-ai2apps-frame-context="{child_name}">'
                        f'{child["html"]}</template>'
                    )
                except Exception:
                    # A detached or browser-internal frame is simply unavailable.
                    pass
                finally:
                    if switched:
                        driver.switch_to.parent_frame()
            return result | {"html": context_html}

        result = capture((), 0, 0, ())
        driver.switch_to.default_content()
        html = str(result["html"])
        if frame_html:
            html += "<ai2apps-frames>" + "".join(frame_html) + "</ai2apps-frames>"
        html_truncated = bool(result["htmlTruncated"])
        if len(html) > max_html and html_mode != "full":
            html = html[:max_html] + "<!-- ai2apps:truncated -->"
            html_truncated = True
        return BrowserSnapshot(
            url=page_url,
            title=page_title,
            items=tuple(items),
            text=" ".join(text_parts).replace("  ", " ")[:max_text],
            html=html,
            html_mode=result["htmlMode"],
            html_truncated=html_truncated,
        )

    def read_article(
        self,
        *,
        mode: str,
        selector: str | None,
        include_images: bool,
        include_links: bool,
        max_chars: int,
        char_threshold: int,
        max_elements: int,
    ) -> BrowserArticle:
        driver = self._driver()
        loaded = driver.execute_script(
            "return typeof globalThis.__ai2appsReadability === 'function';"
        )
        if not loaded:
            driver.execute_script(_READABILITY_SOURCE + "\nsetReadablility();")
        try:
            result = driver.execute_script(
                _ARTICLE_SCRIPT,
                {
                    "mode": mode,
                    "selector": selector,
                    "includeImages": include_images,
                    "includeLinks": include_links,
                    "maxChars": max_chars,
                    "charThreshold": char_threshold,
                    "maxElements": max_elements,
                },
            )
        except Exception as exc:
            message = str(exc)
            code = "article_extraction_failed"
            for known in (
                "invalid_article_selector",
                "article_selector_not_found",
                "article_not_found",
            ):
                if known in message:
                    code = known
                    break
            raise BrowserError(code, message) from exc
        return BrowserArticle(
            url=str(result["url"]),
            canonical_url=result.get("canonicalUrl"),
            title=result.get("title"),
            byline=result.get("byline"),
            site_name=result.get("siteName"),
            published_at=result.get("publishedAt"),
            language=result.get("language"),
            direction=result.get("direction"),
            excerpt=result.get("excerpt"),
            html=str(result.get("html") or ""),
            text=str(result.get("text") or ""),
            text_length=int(result.get("textLength") or 0),
            reading_time_minutes=int(result.get("readingTimeMinutes") or 1),
            extraction_method=str(result.get("extractionMethod") or "unknown"),
            confidence=str(result.get("confidence") or "low"),
            truncated=bool(result.get("truncated")),
            warnings=tuple(str(item) for item in result.get("warnings", ())),
            hidden_nodes_removed=int(result.get("hiddenNodesRemoved") or 0),
        )

    def target_info(self, target: str | None) -> dict[str, Any]:
        if target is None:
            self._driver().switch_to.default_content()
            result = self._driver().execute_script(_TARGET_INFO_SCRIPT, None)
        else:
            with self._element_context(target) as (element, _x, _y):
                result = self._driver().execute_script(
                    _TARGET_INFO_SCRIPT, self._local_target(target)
                )
                if result is None:
                    result = self._driver().execute_script(
                        "return arguments[0] ? {tag:arguments[0].tagName.toLowerCase(),"
                        "type:String(arguments[0].type||'').toLowerCase(),"
                        "autocomplete:String(arguments[0].autocomplete||'').toLowerCase(),"
                        "text:String(arguments[0].innerText||arguments[0].value||'').slice(0,300),"
                        "submits:Boolean(arguments[0].form)} : null;",
                        element,
                    )
        if result is None:
            raise BrowserError(
                "target_not_found", f"Browser target not found: {target or 'active element'}"
            )
        return dict(result)

    @staticmethod
    def _is_element_ref(target: str) -> bool:
        return bool(re.fullmatch(r"(?:f\d+(?:\.\d+)*:)?e\d+", target))

    def _local_target(self, target: str) -> str:
        return self._context_refs.get(target, ((), target))[1]

    def _switch_to_context(
        self, path: tuple[int, ...], frame_chain: tuple[Any, ...] = ()
    ) -> tuple[float, float]:
        from selenium.webdriver.common.by import By

        driver = self._driver()
        driver.switch_to.default_content()
        offset_x = offset_y = 0.0
        try:
            for depth, index in enumerate(path):
                if frame_chain:
                    frame = frame_chain[depth]
                else:
                    frames = driver.find_elements(By.CSS_SELECTOR, "iframe,frame")
                    if index >= len(frames):
                        raise BrowserError(
                            "frame_not_found", f"Frame path is stale: {path}"
                        )
                    frame = frames[index]
                rect = driver.execute_script(
                    "const r=arguments[0].getBoundingClientRect();return {x:r.x,y:r.y};",
                    frame,
                )
                offset_x += float(rect["x"])
                offset_y += float(rect["y"])
                driver.switch_to.frame(frame)
        except BrowserError:
            raise
        except Exception as exc:
            raise BrowserError(
                "frame_not_found",
                "The iframe containing this target was replaced or detached; take a new snapshot",
            ) from exc
        return offset_x, offset_y

    @contextmanager
    def _element_context(self, target: str):
        path, local_target = self._context_refs.get(target, ((), target))
        frame_chain = self._context_frame_elements.get(target, ())
        offset_x, offset_y = self._switch_to_context(path, frame_chain)
        try:
            yield self._element_in_current(local_target), offset_x, offset_y
        finally:
            self._driver().switch_to.default_content()

    def _element_in_current(self, target: str):
        from selenium.common.exceptions import NoSuchElementException

        selector = (
            f'[data-ai2apps-ref="{target}"]'
            if re.fullmatch(r"e\d+", target)
            else target
        )
        self._last_relocation = None
        try:
            element = self._driver().execute_script(_FIND_TARGET_SCRIPT, selector)
            if element is None:
                raise NoSuchElementException(selector)
            return element
        except NoSuchElementException as exc:
            if not re.fullmatch(r"e\d+", target):
                raise BrowserError(
                    "target_not_found", f"Browser target not found: {target}"
                ) from exc
            relocation = self._driver().execute_script(_RELOCATE_SCRIPT, target)
            status = relocation.get("status")
            if status == "ambiguous":
                raise BrowserError(
                    "target_relocation_ambiguous",
                    "Multiple elements match the stale reference: "
                    + json.dumps(relocation.get("candidates", []), ensure_ascii=False),
                ) from exc
            if status != "relocated":
                raise BrowserError(
                    "target_not_found",
                    f"Browser target {target} is stale and no high-confidence replacement exists",
                ) from exc
            self._last_relocation = dict(relocation)
            element = self._driver().execute_script(_FIND_TARGET_SCRIPT, selector)
            if element is None:
                raise BrowserError(
                    "target_not_found", f"Relocated browser target disappeared: {target}"
                ) from exc
            return element

    def wait_for(
        self,
        *,
        condition: str,
        target: str | None,
        state: str,
        text: str | None,
        url_contains: str | None,
        timeout_ms: int,
        poll_ms: int,
        stable_ms: int,
    ) -> dict[str, Any]:
        start = time.monotonic()
        deadline = start + timeout_ms / 1000
        driver = self._driver()
        detail: dict[str, Any] = {}
        last_error: str | None = None
        while True:
            try:
                satisfied = False
                if condition == "element":
                    try:
                        with self._element_context(target or "") as (
                            element,
                            _offset_x,
                            _offset_y,
                        ):
                            present = True
                            visible = element.is_displayed()
                            enabled = visible and element.is_enabled()
                    except BrowserError as exc:
                        element = None
                        last_error = str(exc)
                        present = visible = enabled = False
                    satisfied = {
                        "present": present,
                        "visible": visible,
                        "hidden": not visible,
                        "enabled": enabled,
                        "clickable": enabled,
                        "absent": not present,
                    }[state]
                    detail = {
                        "state": state,
                        "present": present,
                        "visible": bool(visible),
                        "enabled": bool(enabled),
                        "relocation": self._last_relocation,
                    }
                elif condition == "text":
                    if target:
                        with self._element_context(target) as (
                            element,
                            _offset_x,
                            _offset_y,
                        ):
                            haystack = (
                                element.text or element.get_attribute("value") or ""
                            )
                    else:
                        haystack = self._rendered_text_all_contexts()
                    satisfied = (text or "") in haystack
                    detail = {"text": text, "target": target}
                elif condition == "url":
                    current_url = driver.current_url
                    satisfied = (url_contains or "") in current_url
                    detail = {"url": current_url, "url_contains": url_contains}
                else:
                    stability = driver.execute_script(
                        _INSTALL_STABILITY_OBSERVER_SCRIPT
                    )
                    satisfied = (
                        stability["readyState"] == "complete"
                        and stability["quietMs"] >= stable_ms
                    )
                    detail = {
                        "ready_state": stability["readyState"],
                        "quiet_ms": round(stability["quietMs"]),
                        "mutations": stability["mutations"],
                    }
                if satisfied:
                    return {
                        "satisfied": True,
                        "condition": condition,
                        "elapsed_ms": round((time.monotonic() - start) * 1000),
                        "detail": detail,
                    }
            except Exception as exc:  # DOM may be replaced between poll operations
                last_error = str(exc)
            if time.monotonic() >= deadline:
                return {
                    "satisfied": False,
                    "condition": condition,
                    "elapsed_ms": round((time.monotonic() - start) * 1000),
                    "detail": detail,
                    "last_error": last_error,
                }
            time.sleep(poll_ms / 1000)

    def _pointer_destination(
        self,
        *,
        target: str | None,
        x: int | None = None,
        y: int | None = None,
    ) -> tuple[int, int, int, int]:
        driver = self._driver()
        if target is not None:
            with self._element_context(target) as (element, offset_x, offset_y):
                result = driver.execute_script(
                    """
                    arguments[0].scrollIntoView({block:'center', inline:'center'});
                    const rect = arguments[0].getBoundingClientRect();
                    return {x: rect.left + rect.width / 2, y: rect.top + rect.height / 2};
                    """,
                    element,
                )
                x = round(float(result["x"]) + offset_x)
                y = round(float(result["y"]) + offset_y)
            viewport = driver.execute_script(
                "return {width: innerWidth, height: innerHeight};"
            )
            width, height = int(viewport["width"]), int(viewport["height"])
        else:
            viewport = driver.execute_script(
                "return {width: innerWidth, height: innerHeight};"
            )
            width, height = int(viewport["width"]), int(viewport["height"])
        if x is None or y is None:
            raise BrowserError(
                "pointer_destination_required", "Provide a target or viewport x/y"
            )
        return (
            max(0, min(int(x), max(0, width - 1))),
            max(0, min(int(y), max(0, height - 1))),
            width,
            height,
        )

    def move_pointer(
        self,
        *,
        target: str | None,
        x: int | None = None,
        y: int | None = None,
        duration_ms: int | None = None,
    ) -> dict[str, int]:
        from selenium.webdriver.remote.command import Command

        driver = self._driver()
        end_x, end_y, width, height = self._pointer_destination(
            target=target, x=x, y=y
        )
        if self._pointer_position is None:
            self._pointer_position = (width // 2, height // 2)
        start_x, start_y = self._pointer_position
        distance = math.hypot(end_x - start_x, end_y - start_y)
        total_ms = duration_ms or round(max(180, min(1200, 180 + distance * 0.75)))
        steps = max(8, min(60, round(total_ms / 16)))
        perpendicular_x = -(end_y - start_y)
        perpendicular_y = end_x - start_x
        norm = max(distance, 1.0)
        curve = min(48.0, distance * 0.08)
        direction = -1 if (start_x + start_y + end_x + end_y) % 2 else 1
        actions = []
        previous = (start_x, start_y)
        for index in range(1, steps + 1):
            t = index / steps
            eased = t * t * (3 - 2 * t)
            bend = math.sin(math.pi * t) * curve * direction
            point_x = start_x + (end_x - start_x) * eased + perpendicular_x / norm * bend
            point_y = start_y + (end_y - start_y) * eased + perpendicular_y / norm * bend
            point = (
                max(0, min(round(point_x), max(0, width - 1))),
                max(0, min(round(point_y), max(0, height - 1))),
            )
            if point == previous and index != steps:
                continue
            actions.append(
                {
                    "type": "pointerMove",
                    "duration": max(5, round(total_ms / steps)),
                    "x": point[0],
                    "y": point[1],
                    "origin": "viewport",
                }
            )
            previous = point
        driver.execute(
            Command.W3C_ACTIONS,
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "ai2apps-mouse",
                        "parameters": {"pointerType": "mouse"},
                        "actions": actions,
                    }
                ]
            },
        )
        self._pointer_position = (end_x, end_y)
        return {"x": end_x, "y": end_y, "duration_ms": total_ms}

    def hover(self, target: str, *, duration_ms: int | None = None) -> dict[str, int]:
        result = self.move_pointer(target=target, duration_ms=duration_ms)
        time.sleep(0.08)
        return result

    def click(self, target: str, *, duration_ms: int | None = None) -> None:
        from selenium.webdriver.remote.command import Command

        self.move_pointer(target=target, duration_ms=duration_ms)
        self._driver().execute(
            Command.W3C_ACTIONS,
            {
                "actions": [
                    {
                        "type": "pointer",
                        "id": "ai2apps-mouse",
                        "parameters": {"pointerType": "mouse"},
                        "actions": [
                            {"type": "pointerDown", "button": 0},
                            {
                                "type": "pause",
                                "duration": random.SystemRandom().randint(45, 110),
                            },
                            {"type": "pointerUp", "button": 0},
                        ],
                    }
                ]
            },
        )

    def type_text(
        self,
        target: str,
        text: str,
        *,
        clear: bool,
        input_mode: str = "natural",
        delay_ms: int | None = None,
    ) -> None:
        from selenium.webdriver.common.keys import Keys

        with self._element_context(target) as (element, _offset_x, _offset_y):
            if clear:
                if input_mode == "natural":
                    select_modifier = (
                        Keys.META if platform.system() == "Darwin" else Keys.CONTROL
                    )
                    element.send_keys(select_modifier, "a")
                    element.send_keys(Keys.BACKSPACE)
                else:
                    element.clear()
            if input_mode == "instant":
                element.send_keys(text)
                return
            randomizer = random.SystemRandom()
            base_delay = max(0, min(delay_ms if delay_ms is not None else 32, 500))
            for character in text:
                element.send_keys(character)
                factor = 1.8 if character in " .,;:!?\n" else 1.0
                jitter = randomizer.uniform(0.65, 1.35)
                time.sleep(base_delay * factor * jitter / 1000)

    @staticmethod
    def _key_value(key: str) -> str:
        from selenium.webdriver.common.keys import Keys

        aliases = {
            "COMMAND": "META",
            "CMD": "META",
            "CTRL": "CONTROL",
            "ESC": "ESCAPE",
            "RETURN": "ENTER",
            "ARROWDOWN": "ARROW_DOWN",
            "ARROWUP": "ARROW_UP",
            "ARROWLEFT": "ARROW_LEFT",
            "ARROWRIGHT": "ARROW_RIGHT",
            "PAGEDOWN": "PAGE_DOWN",
            "PAGEUP": "PAGE_UP",
            "SPACE": "SPACE",
        }
        normalized = aliases.get(key.upper().replace("-", "_"), key.upper().replace("-", "_"))
        value = getattr(Keys, normalized, None)
        if value is not None:
            return value
        if len(key) == 1:
            return key
        raise BrowserError("unsupported_key", f"Unsupported key: {key}")

    def key_press(
        self,
        *,
        key: str,
        modifiers: tuple[str, ...],
        target: str | None,
        repeat: int,
    ) -> None:
        from selenium.webdriver.common.action_chains import ActionChains

        @contextmanager
        def action_context():
            if target:
                with self._element_context(target) as value:
                    yield value[0]
            else:
                self._driver().switch_to.default_content()
                yield None

        with action_context() as element:
            actions = ActionChains(self._driver())
            if element is not None:
                self._driver().execute_script(
                    "arguments[0].focus({preventScroll:false});", element
                )
            modifier_values = [self._key_value(value) for value in modifiers]
            for value in modifier_values:
                actions.key_down(value)
            for _ in range(repeat):
                actions.send_keys(self._key_value(key))
            for value in reversed(modifier_values):
                actions.key_up(value)
            actions.perform()

    def clipboard_action(self, action: str, *, target: str | None) -> None:
        modifier = "META" if platform.system() == "Darwin" else "CONTROL"
        key = {"copy": "c", "cut": "x", "paste": "v"}[action]
        self.key_press(key=key, modifiers=(modifier,), target=target, repeat=1)

    def upload_file(self, target: str, path: str | Path) -> None:
        with self._element_context(target) as (element, _offset_x, _offset_y):
            if str(element.get_attribute("type") or "").lower() != "file":
                raise BrowserError("not_file_input", "Upload target is not a file input")
            element.send_keys(str(Path(path).resolve(strict=True)))

    def staged_downloads(self, *, wait_ms: int = 0) -> dict[str, Any]:
        if self._download_directory is None:
            raise BrowserError(
                "downloads_unavailable", "No Session download directory is configured"
            )
        deadline = time.monotonic() + wait_ms / 1000
        while True:
            entries = [
                item
                for item in self._download_directory.iterdir()
                if item.is_file() and not item.is_symlink()
            ]
            in_progress = [item for item in entries if item.name.endswith(".crdownload")]
            complete = [item for item in entries if not item.name.endswith(".crdownload")]
            if complete or (entries and not in_progress) or time.monotonic() >= deadline:
                return {
                    "complete": [
                        {
                            "name": item.name,
                            "size_bytes": item.stat().st_size,
                            "modified_at": item.stat().st_mtime,
                        }
                        for item in sorted(complete, key=lambda value: value.stat().st_mtime)
                    ],
                    "in_progress": [item.name for item in in_progress],
                }
            time.sleep(0.1)

    def scroll(self, delta_y: int) -> None:
        self._driver().execute_script("window.scrollBy(0, arguments[0])", delta_y)

    def screenshot(self) -> str:
        return self._driver().get_screenshot_as_base64()

    def _driver(self):
        if self.driver is None:
            raise BrowserError("browser_not_running", "Chrome is not running")
        return self.driver
