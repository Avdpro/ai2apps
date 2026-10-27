(function(options) {
const maxItems = options.maxItems;
const maxText = options.maxText;
const maxHtml = options.maxHtml;
const htmlMode = options.htmlMode;
const selector = [
  'a[href]', 'button', 'input:not([type="hidden"])', 'textarea', 'select',
  '[role="button"]', '[role="link"]', '[contenteditable="true"]',
  '[role="option"]', '[role="menuitem"]', '[role="treeitem"]', '[role="gridcell"]',
  '[tabindex]:not([tabindex="-1"])', '[onclick]', 'label'
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
const visible = (node, options={}) => ai2appsDOMVisible(node,{...options,controlIcons:true});
const items = [];
const observedElements = new Set();
const controlStructure = el => {
  const path=[];
  let node=el;
  for(;node && path.length<32;node=node.parentElement||node.getRootNode()?.host) {
    const siblings=node.parentElement?.children||node.getRootNode()?.children||[];
    path.push([node.tagName,node.getAttribute('role')||'',
      [...siblings].filter(n=>n.tagName===node.tagName).indexOf(node)]);
  }
  return node ? null : JSON.stringify(path);
};
if (!Number.isSafeInteger(window.__ai2appsNextElementRef)) {
  window.__ai2appsNextElementRef = 1;
}
if (!(window.__ai2appsElementRefs instanceof WeakMap)) {
  window.__ai2appsElementRefs = new WeakMap();
}
if (!(window.__ai2appsElementIdentities instanceof WeakMap)) {
  window.__ai2appsElementIdentities = new WeakMap();
}
if (!window.__ai2appsRefFingerprints || typeof window.__ai2appsRefFingerprints !== 'object') {
  window.__ai2appsRefFingerprints = Object.create(null);
}
const elementRef = (el) => {
  let ref = window.__ai2appsElementRefs.get(el);
  // Virtual lists reuse the same DOM node for a different option. A ref must
  // identify its observed meaning, not just the retained node/coordinates.
  const editable = el.matches('input,textarea,select,[contenteditable="true"]');
  const identity = JSON.stringify([el.tagName,el.getAttribute('role')||'',
    el.getAttribute('type')||'',el.getAttribute('aria-label')||'',
    el.getAttribute('placeholder')||'',el.tagName==='A'?el.href:'',
    editable?'':String(el.innerText||'').replace(/\s+/g,' ').trim().slice(0,300)]);
  if (!ref || window.__ai2appsElementIdentities.get(el) !== identity) {
    ref = `e${window.__ai2appsNextElementRef++}`;
    window.__ai2appsElementRefs.set(el, ref);
    window.__ai2appsElementIdentities.set(el, identity);
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
const candidates = new Set(queryAll(selector));
// Observe real native/user pointer input, not synthetic DOM events. This is
// only an observation anchor for roleless popups, never authority to click.
if (!window.__ai2appsPointerObserverInstalled) {
  window.addEventListener('pointerdown', event => {
    if (event.isTrusted) window.__ai2appsPointerAnchor = {node:event.composedPath()[0],at:Date.now()};
  }, true);
  window.__ai2appsPointerObserverInstalled = true;
}
// Some autocomplete widgets use an unfocusable sibling popup and delegated
// handlers, without roles or pointer cursors. Observe its rendered leaf rows
// only while its own editor has focus; ordinary page text is not a control.
const focusedEditor = document.activeElement;
const activePopups = new Set();
const anchors = [];
if (focusedEditor?.matches('input:not([type="password"]),textarea,[contenteditable="true"]')) anchors.push(focusedEditor);
const pointerAnchor=window.__ai2appsPointerAnchor;
if (pointerAnchor?.node?.isConnected && Date.now()-pointerAnchor.at < 120000) anchors.push(pointerAnchor.node);
for (const anchor of anchors) {
  const editorRect = anchor.getBoundingClientRect();
  for (const popup of queryAll('div,section,[tabindex="-1"]')) {
    if (!visible(popup) || popup.contains(anchor) ||
        popup.querySelector('input,textarea,[contenteditable="true"]')) continue;
    const style = getComputedStyle(popup), rect = popup.getBoundingClientRect();
    const siblingPopup = popup.getAttribute('tabindex') === '-1' &&
      !popup.parentElement?.matches('body,html') && popup.parentElement?.contains(anchor);
    const anchoredPopup = ['absolute','fixed'].includes(style.position) && Number(style.zIndex) > 0 &&
      rect.top >= editorRect.top - 32 && rect.top <= editorRect.bottom + 80 &&
      rect.right > editorRect.left && rect.left < editorRect.right;
    if (!siblingPopup && !anchoredPopup) continue;
    activePopups.add(popup);
    let count = 0;
    const visit = node => {
      if (count >= 80 || !visible(node)) return;
      const label = String(node.innerText || '').trim();
      if (!label) return;
      const blocks = [...node.children].filter(child =>
        ['DIV','UL','OL','LI','SECTION','ARTICLE','TABLE','TR'].includes(child.tagName));
      if (!blocks.length && label.length <= 300) {
        candidates.add(node); count++;
      } else {
        for (const child of node.children) visit(child);
      }
    };
    for (const child of popup.children) visit(child);
  }
}
// Framework event handlers often live on div/span controls without ARIA roles.
for (const el of queryAll('div,span,li,td,th,a,i,svg')) {
  if (!visible(el) || getComputedStyle(el).cursor !== 'pointer') continue;
  const label = String(el.innerText || el.getAttribute('aria-label') || '').trim();
  if (label.length > 80 || (!label && !el.matches('i,svg'))) continue;
  if (el.parentElement && el.parentElement.matches('div,span,li,td,th,a') && getComputedStyle(el.parentElement).cursor === 'pointer' &&
      String(el.parentElement.innerText || '').trim() === label) continue;
  candidates.add(el);
}
// Open overlays/listboxes own input focus. Do not truncate their controls
// behind long navigation or result lists in the background document.
const overlayRank = el => Number(![...activePopups].some(popup=>popup.contains(el)) &&
  !el.closest('[role="dialog"],[aria-modal="true"],[role="listbox"],[role="grid"],dialog[open]'));
const orderedCandidates = [...candidates].sort((a,b) =>
  overlayRank(a) - overlayRank(b) ||
  Number(!visible(a,{viewport:true})) - Number(!visible(b,{viewport:true})));
for (const el of orderedCandidates) {
  if (!visible(el) || items.length >= maxItems) continue;
  const ref = elementRef(el);
  observedElements.add(el);
  const password = el.matches('input[type="password"]') ||
    ['current-password', 'new-password', 'one-time-code'].includes(el.autocomplete);
  items.push({
    ref,
    tag: el.tagName.toLowerCase(),
    structure: controlStructure(el),
    role: el.getAttribute('role'),
    type: el.getAttribute('type'),
    text: password ? '[sensitive field]' :
      String(el.innerText || el.getAttribute('aria-label') ||
             el.getAttribute('placeholder') || el.value || '').trim().slice(0, 300),
    value: !password && el.matches('input,textarea,select') ? String(el.value || '').slice(0,300) : '',
    href: el.tagName === 'A' ? el.href : null,
    disabled: Boolean(el.disabled || el.getAttribute('aria-disabled') === 'true'),
    sensitive: password,
    editable: el.matches('input,textarea,[contenteditable="true"]'),
    rect: roundedRect(el),
  });
  window.__ai2appsRefFingerprints[ref] = {
    tag: el.tagName.toLowerCase(),
    structure: controlStructure(el),
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
const fileInputs = queryAll('input[type="file"]').slice(0,20).map(el => ({
  ref:elementRef(el), tag:'input', type:'file', accept:el.accept || '', multiple:Boolean(el.multiple),
  disabled:Boolean(el.disabled), text:el.getAttribute('aria-label') || el.getAttribute('name') ||
    el.closest('label')?.innerText || '', visible:visible(el), rect:roundedRect(el)
}));
const textParts = [];
let textLength = 0;
if (document.body) {
  const duplicateInteractive = [
    'a[href]', 'button', 'input', 'textarea', 'select',
    '[role="button"]', '[role="link"]', '[contenteditable="true"]',
  '[tabindex]:not([tabindex="-1"])', '[onclick]', 'label'
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
  if (observedElements.has(el)) attrs.push(`data-ai2apps-ref="${elementRef(el)}"`);
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
  const hardHidden = !visible(el, {requireBox:false});
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
  items, file_inputs:fileInputs,
  controls_truncated: orderedCandidates.filter(el=>visible(el)).length > items.length,
  text: textParts.join(' ').replace(/\s+/g, ' ').trim().slice(0, maxText),
  html,
  htmlMode,
  htmlTruncated,
};
})
