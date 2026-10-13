"""Read-only, observed-link recovery for Mini-App list layout drift."""
from urllib.parse import urlsplit


CANDIDATES_SCRIPT = r'''function(excludeAds=true){
 const items=[],seen=new Set();
 for(const a of document.querySelectorAll('a[href]')){
  const r=a.getBoundingClientRect(),s=getComputedStyle(a);
  if(!ai2appsDOMVisible(a)||a.closest('nav,header,footer,[role=navigation]'))continue;
  const card=a.closest('article,[role=article],li,section')||a.parentElement;
  const is_ad=!!a.closest('[data-text-ad],[data-ad],.b_ad,.result--ad,[data-type="ad"],[data-testid="ad"]')||/^(Sponsored|Promoted|广告|赞助)(?:\b|\s|$)/im.test(card?.innerText||'');
  if(excludeAds&&is_ad)continue;
  let u;try{u=new URL(a.href,location.href);}catch{continue;}
  if(!/^https?:$/.test(u.protocol)||u.username||u.password||seen.has(u.href))continue;
  const title=(a.innerText||a.getAttribute('aria-label')||a.querySelector('img')?.alt||'').trim().slice(0,500);
  if(!title)continue;
  seen.add(u.href);
  let image_url='';try{const im=card?.querySelector('img');const x=new URL(im?.currentSrc||im?.src||'',location.href);if(im&&/^https?:$/.test(x.protocol))image_url=x.href;}catch{}
  items.push({id:'c'+items.length,url:u.href,title,content:(card?.innerText||title).trim().slice(0,2000),image_url,is_ad});
  if(items.length>=100)break;
 }
 return {page_url:location.href,page_title:document.title,items};
}'''


def eligible(candidate, provider):
    """Keep observed canonical content links; never manufacture destinations."""
    try:
        u = urlsplit(candidate.get('url', ''))
        if u.scheme not in ('http', 'https') or not u.hostname or u.username or u.password:
            return False
    except ValueError:
        return False
    host, path = u.hostname.lower(), u.path
    rules = {
        'x': (('x.com', 'twitter.com'), '/status/'),
        'xiaohongshu': (('xiaohongshu.com','rednote.com'), ('/explore/', '/discovery/item/')),
        'weibo': (('weibo.com', 'weibo.cn'), None),
        'youtube': (('youtube.com', 'youtu.be'), ('/watch', '/shorts/', '/live/')),
        'bilibili': (('bilibili.com',), '/video/'),
        'wikipedia': (('wikipedia.org',), '/wiki/'),
    }
    if provider in rules:
        hosts, paths = rules[provider]
        if not any(host == h or host.endswith('.' + h) for h in hosts):
            return False
        if paths and not any(p in path for p in ((paths,) if isinstance(paths, str) else paths)):
            return False
        if provider == 'weibo':
            import re
            return bool(re.fullmatch(r'/\d+/[A-Za-z0-9]+', path))
    return True


def selected_result(observed, selections, args):
    if not isinstance(selections, list) or not selections or len(selections) > 50:
        raise ValueError('Recovery requires observed result IDs')
    candidates = {item['id']: item for item in observed['items']}
    if any(not isinstance(key, str) or key not in candidates for key in selections) or len(set(selections)) != len(selections):
        raise ValueError('Recovery selected an unknown or duplicate result')
    items = []
    for key in selections[:min(50, max(1, int(args.get('limit', 10))))]:
        c = candidates[key]
        items.append({k: c[k] for k in ('url', 'title', 'content', 'image_url', 'is_ad')})
        items[-1]['summary'] = c['content']
        if args.get('kind') in ('web', 'post', 'video'):
            items[-1]['kind'] = args['kind']
    return {'items': items, 'page_url': observed['page_url'], 'page_title': observed['page_title'],
            'provider': args.get('search_provider', ''), 'recovery': 'observed_links_ai',
            'metadata_status': 'layout_recovery_partial'}
