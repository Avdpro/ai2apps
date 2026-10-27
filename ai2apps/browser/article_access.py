"""Classify observed access notices; never retrieve or unlock hidden content."""
import re

LABELS = {
    'paywall': '付费墙：需要订阅才能阅读全文',
    'login_required': '需要登录后才能阅读全文',
    'access_verification_pending': '访问验证未完成，尚未获得完整正文',
}

def classify(text, reason=''):
    text = text or ''
    if reason in LABELS:
        return reason
    if re.search(r'create a free account or log in|register to (?:read|continue)|登录或注册', text, re.I):
        return 'login_required'
    if re.search(r'checking your access|verify access|confirmed access|正在验证.*访问|访问验证', text, re.I):
        return 'access_verification_pending'
    if re.search(r'(subscribe|subscription|订阅|付费).{0,60}(continue reading|read (?:the )?(?:full|this) article|阅读全文)|(?:subscribe to (?:keep|continue) reading)|订阅后阅读', text, re.I):
        return 'paywall'
    if re.search(r'(log ?in|sign ?in).{0,40}(continue reading|read (?:this|the) article)|登录后.{0,10}阅读', text, re.I):
        return 'login_required'
    return {'subscription_required':'paywall','login':'login_required','authentication_required':'login_required','paywall':'paywall'}.get(reason,'')

# Read already-loaded article DOM, including paragraphs behind access overlays.
# Never remove a gate, fetch more content, or inspect script/metadata payloads.
VISIBLE_ARTICLE = r'''function(){
 const visible=e=>{for(let n=e;n&&n.nodeType===1;n=n.parentElement){const s=getComputedStyle(n);if(n.hidden||(n.getAttribute('aria-hidden')==='true'&&!n.hasAttribute('data-paywall-inert'))||s.display==='none'||s.visibility==='hidden'||s.opacity==='0')return false;}return !!e.getClientRects().length;};
 const root=document.querySelector('section[name="articleBody"]')||document.querySelector('article')||document.querySelector('[role="main"]')||document.querySelector('main');
 const paragraphs=root?[...root.querySelectorAll('p')].filter(visible).filter(e=>!e.closest('nav,footer,aside,[role="dialog"]')).map(e=>e.innerText.trim()).filter(Boolean):[];
 return {url:location.href,title:document.title,notice:document.body.innerText.slice(0,40000),access_hint:document.querySelector('[role="dialog"][aria-label]')?.getAttribute('aria-label')||'',paragraphs};
}'''

def preview(observed, reason):
    paragraphs=[]
    for text in observed.get('paragraphs', []):
        if classify(text) or re.search(r'Thank you for your patience|If you are in Reader mode|subscribe|sign in|log in|订阅|登录', text, re.I):
            continue
        if len(text.strip()) >= 35:
            paragraphs.append(text.strip())
    body='\n\n'.join(paragraphs)
    if len(body)<160:
        return None
    return dict(url=observed['url'],title=observed.get('title',''),text=body[:20000],
                coverage='preview',access_reason=reason,extraction_method='loaded-dom-incomplete-preview')
