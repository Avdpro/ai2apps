"""Social owner adapters. DOM evidence only, using the existing BiDi page."""
from urllib.parse import urlsplit, quote
import re

PLATFORMS=('x','xiaohongshu','weibo')
XHS_ORIGINS=('https://www.rednote.com','https://www.xiaohongshu.com')
XHS_ALLOWED_ORIGINS=(*XHS_ORIGINS,'https://rednote.com','https://xiaohongshu.com')
SCOPES={'x':['https://x.com/**'],'xiaohongshu':[origin+'/**' for origin in XHS_ALLOWED_ORIGINS],'weibo':['https://weibo.com/**','https://s.weibo.com/**']}

def account_url(platform,handle,origin=None):
    patterns={'x':r'[A-Za-z0-9_]{1,15}','xiaohongshu':r'[a-fA-F0-9]{24}','weibo':r'\d{5,20}'}
    if platform not in patterns or not re.fullmatch(patterns[platform],handle):raise ValueError('Invalid social account identifier')
    if platform=='xiaohongshu' and origin is not None:
        if origin not in XHS_ALLOWED_ORIGINS:raise ValueError('Invalid social site origin')
        return origin+'/user/profile/'+handle
    return {'x':'https://x.com/','xiaohongshu':'https://www.xiaohongshu.com/user/profile/','weibo':'https://weibo.com/u/'}[platform]+handle

def explicit_account(platform,value):
    value=value.strip()
    if not value.startswith(('http://','https://')):return None
    u=urlsplit(value)
    if u.scheme!='https' or u.username or u.password:raise ValueError('Expected a trusted HTTPS account URL')
    hosts={'xiaohongshu':('www.xiaohongshu.com','xiaohongshu.com','www.rednote.com','rednote.com'),'weibo':('weibo.com','www.weibo.com')}
    if u.hostname not in hosts.get(platform,()):raise ValueError('Account URL does not match platform')
    pattern={'xiaohongshu':r'/user/profile/([a-fA-F0-9]{24})/?','weibo':r'/(?:u/)?(\d{5,20})/?'}[platform]
    m=re.fullmatch(pattern,u.path)
    if not m:raise ValueError('Expected an account Profile URL')
    return m[1]

def search_url(platform,query,origin=None):
    if platform=='xiaohongshu' and origin is not None:
        if origin not in XHS_ALLOWED_ORIGINS:raise ValueError('Invalid social site origin')
        return origin+'/search_result?type=51&keyword='+quote(query)
    return {'xiaohongshu':'https://www.xiaohongshu.com/search_result?type=51&keyword=','weibo':'https://s.weibo.com/user?q='}[platform]+quote(query)

ACCOUNT_SCRIPT=r'''function(platform){
 const xhs=platform==='xiaohongshu',host=xhs?/^(www\.)?(?:xiaohongshu|rednote)\.com$/:/^(s\.|www\.)?weibo\.com$/;
 if(!host.test(location.hostname)||location.protocol!=='https:')return {outside_scope:true,candidates:[]};
 const candidates=[],seen=new Set(),pattern=xhs?/^\/user\/profile\/([a-f0-9]{24})\/?$/i:/^\/(?:u\/)?(\d{5,20})\/?$/;
 const current=location.pathname.match(pattern),visible=n=>!!n&&n.getClientRects().length>0&&getComputedStyle(n).visibility!=='hidden';
 function add(root,link,source){let u;try{u=new URL(link.href)}catch{return}const m=u.pathname.match(pattern);
 if(!m||u.origin!==location.origin||seen.has(m[1])||link.closest('nav,aside,.side-bar,.sidebar,[role="navigation"]'))return;
 const name=(root.querySelector('.user-name,.name,.username,.user-nickname,.nickname')?.innerText||link.innerText||'').trim();
 if(!name||/^(我|Me|Profile)$/i.test(name))return;
 seen.add(m[1]);candidates.push({handle:m[1],name:name.slice(0,200),bio:(root.innerText||'').trim().slice(0,600),url:u.href,avatar:root.querySelector('img')?.src||'',identity_source:source});}
 if(current){
 const root=document.querySelector(xhs?'.user-info': '[class*="ProfileHeader_main"]');
 const name=root?.querySelector(xhs?'.user-name,.username,.user-nickname,.nickname': '[class*="ProfileHeader_name"]')?.innerText;
 if(root&&name)candidates.push({handle:current[1],name:name.trim(),bio:root.innerText.slice(0,600),url:location.href,avatar:root.querySelector('img')?.src||'',identity_source:'profile_header'});
 }else{
 const roots=document.querySelectorAll(xhs?'.user-item,.user-list-item,.user-info,.user':'.card-user-b,.card-user-a,.card-wrap .info,[class*="ProfileHeader_main"]');
 for(const root of roots)for(const link of root.querySelectorAll('a[href]'))add(root,link,'account_search');
 if(xhs)for(const note of document.querySelectorAll('section.note-item,.note-item')){
 for(const link of note.querySelectorAll('a[href*="/user/profile/"]'))add(link.closest('.author-wrapper,.author')||link,link,'post_author');}
 }
 const text=(document.body?.innerText||'').slice(0,12000);
 const wall=[...document.querySelectorAll(xhs?'.login-container,.login-modal,[class*="login-mask"]':'.woo-modal-main .LoginForm,.login-box')].some(visible);
 return {candidates:candidates.slice(0,10),login_required:wall,challenge:/安全验证|验证码|访问频次过高/.test(text)&&!candidates.length,url:location.href,time_zone:Intl.DateTimeFormat().resolvedOptions().timeZone};
}'''

async def resolve_xhs(page,query,origin,handle=None):
    """Bounded owner recovery stays in the same page and native Profile."""
    import asyncio
    attempts=[];observed={};last={}
    urls=[account_url('xiaohongshu',handle,origin)] if handle else [search_url('xiaohongshu',query,origin),origin+'/search_result?keyword='+quote(query)]
    for url in urls:
        await page.navigate(url)
        for index in range(8):
            last=await page.call_json(ACCOUNT_SCRIPT,['xiaohongshu'])
            if last.get('outside_scope') or last.get('login_required') or last.get('challenge'):return last
            for candidate in last.get('candidates',[]):observed.setdefault(candidate['handle'],candidate)
            if observed:break
            if index in (3,5):await page.scroll(650)
            await asyncio.sleep(.6)
        attempts.append({'url':url,'observed_candidates':len(observed)})
        if observed:break
    verified=[]
    ordered=sorted(observed.values(),key=lambda c:c.get('name','').strip().casefold()!=query.strip().casefold())
    for candidate in ordered[:5]:
        # Use only a just-observed, same-origin Profile link; preserve its signed query.
        parsed=urlsplit(candidate['url'])
        if parsed.scheme+'://'+parsed.netloc!=origin or parsed.path.rstrip('/')!='/user/profile/'+candidate['handle']:continue
        if not handle:await page.navigate(candidate['url'])
        for _ in range(6):
            identity=await page.call_json(ACCOUNT_SCRIPT,['xiaohongshu'])
            if identity.get('login_required') or identity.get('challenge'):return identity
            match=next((c for c in identity.get('candidates',[]) if c['handle']==candidate['handle'] and c.get('identity_source')=='profile_header'),None)
            if match:
                verified.append({**match,'identity_source':candidate.get('identity_source'),'identity_verified':True,'observed_author_name':candidate['name']});break
            await asyncio.sleep(.5)
    exact=[c for c in verified if c['name'].strip().casefold()==query.strip().casefold()]
    verified=exact or verified
    return {**last,'candidates':verified,'resolution_attempts':attempts,'status':'candidates' if verified else 'not_found'}

LIKE_METRIC_SCRIPT=r'''function(root,kind='likes'){
 const selectors={likes:'.like-wrapper .count,.like-wrapper .count-text,.like-wrapper,[data-testid="like"],[data-testid="unlike"],.woo-like-count,[node-type="like_status"]',comments:'.comment-wrapper .count,.comment-wrapper,[data-testid="reply"],.woo-comment-count',reposts:'.share-wrapper .count,.share-wrapper,[data-testid="retweet"],[data-testid="unretweet"],.woo-retweet-count'};
 const prefix=kind==='likes'?'like':kind;
 const node=root.querySelector(selectors[kind]);
 if(!node)return {count:null,display:null,status:'unavailable',reason:prefix+'_control_not_observed'};
 const raw=(node.innerText||node.textContent||node.getAttribute('aria-label')||'').trim();
 const m=raw.replace(/,/g,'').match(/^(\d+(?:\.\d+)?)\s*(万|亿|[kKmM])?(?:\+|\s|$)/);
 if(!m)return {count:null,display:raw.slice(0,100),status:'unavailable',reason:prefix+'_count_not_numeric'};
 const unit=m[2]||'',factor={'万':10000,'亿':100000000,k:1000,K:1000,m:1000000,M:1000000}[unit]||1;
 return {count:Math.round(Number(m[1])*factor),display:raw.slice(0,100),status:unit||raw.includes('+')?'approximate':'observed',reason:null};
}'''

POSTS_SCRIPT=r'''function(platform,handle){
 const xhs=platform==='xiaohongshu',host=xhs?/^(www\.)?(?:xiaohongshu|rednote)\.com$/:/^(www\.)?weibo\.com$/;
 if(!host.test(location.hostname))return {outside_scope:true,items:[]};
 const expected=xhs?'/user/profile/'+handle:'/u/'+handle;
 if(/\/(?:login|passport)(?:\/|$)/.test(location.pathname))return {login_required:true,items:[]};
 if(location.pathname!==expected&&location.pathname!==expected+'/'&&!(platform==='weibo'&&location.pathname==='/'+handle))return {outside_scope:true,items:[]};
 const likes=LIKE_METRIC;
 const items=[],roots=document.querySelectorAll(xhs?'section.note-item,.note-item':'[component-type="feed"],article,.card-wrap,[class*="Feed_wrap"]');
 const dateISO=(node)=>{const raw=node?.getAttribute('datetime')||node?.getAttribute('date')||node?.getAttribute('title')||node?.textContent?.trim()||'';const clean=raw.replace(/^编辑于\s*/, '');
 if(/^\d{13}$/.test(raw))return new Date(Number(raw)).toISOString();
 if(/^\d{10}$/.test(raw))return new Date(Number(raw)*1000).toISOString();
 let d;if(/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(clean))d=new Date(clean);else if(/^\d{4}[-/]\d{2}[-/]\d{2}/.test(clean))d=new Date(clean.match(/^\d{4}[-/]\d{2}[-/]\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?/)[0].replace(/-/g,'/').replace('T',' '));
 const now=new Date(),rel=clean.match(/^(\d+)\s*(秒|分钟|小时|天)前/);
 if(rel)d=new Date(now-Number(rel[1])*({'秒':1000,'分钟':60000,'小时':3600000,'天':86400000}[rel[2]]));
 if(/刚刚/.test(clean))d=now;
 const hm=clean.match(/^(今天|昨天)\s*(\d{1,2}):(\d{2})/);if(hm){d=new Date(now);d.setHours(+hm[2],+hm[3],0,0);if(hm[1]==='昨天')d.setDate(d.getDate()-1);}
 const md=clean.match(/^(\d{2})[-/](\d{2})(?:\s+(\d{2}):(\d{2}))?/);if(md){d=new Date(now.getFullYear(),+md[1]-1,+md[2],+(md[3]||0),+(md[4]||0));if(d>now)d.setFullYear(d.getFullYear()-1);}
 return d&&!isNaN(d)?d.toISOString():null;};
 for(const root of roots){const link=root.querySelector(xhs?'a[href*="/explore/"],a[href*="/discovery/item/"],a[href*="/search_result/"],a[href*="/user/profile/'+handle+'/"]':'a[href][date],a[class*="head-info_time"],.from a[href],a[href*="/'+handle+'/"]');
 if(!link)continue;let u;try{u=new URL(link.href)}catch{continue}if(!host.test(u.hostname))continue;
 let m;if(xhs){if(u.origin!==location.origin)continue;const nested=u.pathname.match(/^\/user\/profile\/([a-f0-9]{24})\/([a-f0-9]{24})\/?$/i);if(nested&&nested[1]!==handle)continue;m=nested?[nested[0],nested[2]]:u.pathname.match(/^\/(?:explore|discovery\/item|search_result)\/([a-f0-9]{24})\/?$/i);}else m=u.pathname.match(/^\/(\d{5,20})\/([A-Za-z0-9]+)\/?$/);if(!m)continue;
 if(!xhs&&m[1]!==handle)continue;
 const stamp=root.querySelector('time[datetime],[date],[class*="head-info_time"],.from a,.date,.publish-time');
 const text=root.querySelector(xhs?'.title,.desc':'[class*="Feed_detail"],.txt,[node-type="feed_list_content"]')?.innerText||root.innerText||'';
 items.push({likes:likes(root),metrics:Object.fromEntries(['likes','comments','reposts'].map(k=>[k,likes(root,k)])),id:xhs?m[1]:m[2],author:handle,url:u.href,published_at:dateISO(stamp),text:text.slice(0,12000),pinned:/^(置顶|置頂)(?:\s|$)/.test((root.innerText||'').trim())||/置顶|置頂/.test((root.querySelector('[title="置顶"],[title="置頂"],.top-tag,.pin-tag,[class*="head-info"],.badge')?.getAttribute('title')||'')+' '+(root.querySelector('.top-tag,.pin-tag,[class*="head-info"],.badge')?.innerText||'')),repost:false});}
 const body=(document.body?.innerText||'').slice(0,12000);
 return {items,url:location.href,login_required:!!document.querySelector(xhs?'.login-container,.login-modal':'.login-box,.LoginForm')&&!items.length,challenge:/安全验证|验证码|访问频次过高/.test(body)&&!items.length,time_zone:Intl.DateTimeFormat().resolvedOptions().timeZone};
}'''

from .social_media import EXTRACT as MEDIA_EXTRACT

DETAIL_SCRIPT=r'''function(platform,handle,id){
 const extractMedia=MEDIA_EXTRACT;
 const likes=LIKE_METRIC;
 if(platform!=='xiaohongshu'||!/^(www\.)?(?:xiaohongshu|rednote)\.com$/.test(location.hostname))return {};
 if(location.pathname.split('/').filter(Boolean).pop()!==id)return {};
 const root=[...document.querySelectorAll('#noteContainer,.note-container')].find(n=>n.getClientRects().length&&getComputedStyle(n).visibility!=='hidden');if(!root)return {};
 const author=[...root.querySelectorAll('a[href*="/user/profile/"]')].find(a=>new URL(a.href).origin===location.origin&&new URL(a.href).pathname.replace(/\/$/,'')==='/user/profile/'+handle);if(!author)return {};
 const dateISO=(node)=>{const raw=node?.getAttribute('datetime')||node?.getAttribute('date')||node?.getAttribute('title')||node?.textContent?.trim()||'';const clean=raw.replace(/^编辑于\s*/, '');
 if(/^\d{13}$/.test(raw))return new Date(Number(raw)).toISOString();
 if(/^\d{10}$/.test(raw))return new Date(Number(raw)*1000).toISOString();
 let d;if(/^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(clean))d=new Date(clean);else if(/^\d{4}[-/]\d{2}[-/]\d{2}/.test(clean))d=new Date(clean.match(/^\d{4}[-/]\d{2}[-/]\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?/)[0].replace(/-/g,'/').replace('T',' '));
 const now=new Date(),rel=clean.match(/^(\d+)\s*(秒|分钟|小时|天)前/);
 if(rel)d=new Date(now-Number(rel[1])*({'秒':1000,'分钟':60000,'小时':3600000,'天':86400000}[rel[2]]));
 if(/刚刚/.test(clean))d=now;
 const hm=clean.match(/^(今天|昨天)\s*(\d{1,2}):(\d{2})/);if(hm){d=new Date(now);d.setHours(+hm[2],+hm[3],0,0);if(hm[1]==='昨天')d.setDate(d.getDate()-1);}
 const md=clean.match(/^(\d{2})[-/](\d{2})(?:\s+(\d{2}):(\d{2}))?/);if(md){d=new Date(now.getFullYear(),+md[1]-1,+md[2],+(md[3]||0),+(md[4]||0));if(d>now)d.setFullYear(d.getFullYear()-1);}
 return d&&!isNaN(d)?d.toISOString():null;};
 const stamp=root.querySelector('.date,.publish-time,time[datetime]');
 return {likes:likes(root),metrics:Object.fromEntries(['likes','comments','reposts'].map(k=>[k,likes(root,k)])),id,author:handle,published_at:dateISO(stamp),text:(root.querySelector('#detail-desc,.note-text,.desc')?.innerText||'').slice(0,12000),url:location.href,images:extractMedia(root,'.swiper-slide img,.note-slider img,.media-container img,.slide-container img')};
}'''
POSTS_SCRIPT=POSTS_SCRIPT.replace('LIKE_METRIC',LIKE_METRIC_SCRIPT)
DETAIL_SCRIPT=DETAIL_SCRIPT.replace('MEDIA_EXTRACT',MEDIA_EXTRACT).replace('LIKE_METRIC',LIKE_METRIC_SCRIPT)

HOME_SCRIPT=r'''function(){
 const allowed=/^(www\.)?(?:xiaohongshu|rednote)\.com$/;
 if(!allowed.test(location.hostname)||location.protocol!=='https:')return {state:'outside_scope'};
 const visible=n=>!!n&&n.getClientRects().length>0&&getComputedStyle(n).visibility!=='hidden'&&getComputedStyle(n).display!=='none';
 const self=[...document.querySelectorAll('a[href*="/user/profile/"]')].some(a=>{try{const u=new URL(a.href);return allowed.test(u.hostname)&&/^\/user\/profile\/[a-f0-9]{24}\/?$/i.test(u.pathname)&&visible(a)&&/^(我|Me|Profile)$/i.test((a.innerText||a.textContent||'').trim());}catch{return false}});
 const wall=[...document.querySelectorAll('.login-container,.login-modal,[class*="login-mask"]')].some(visible);
 const login=[...document.querySelectorAll('button,a,[role="button"]')].some(n=>visible(n)&&/^(登录|登入|Log in|Sign in)$/i.test((n.innerText||n.textContent||'').trim()));
 return {origin:location.origin,state:self&&!wall?'logged_in':wall||login?'login_required':'unknown'};
}'''

async def choose_home(page,preferred=None):
    """Probe both homes in the same native Profile, without inspecting cookies."""
    import asyncio
    checks=[]
    for origin in XHS_ORIGINS:
        try:
            await page.navigate(origin+'/')
            state={}
            for attempt in range(5):
                state=await page.call_json(HOME_SCRIPT)
                if state.get('state') in ('logged_in','login_required'):break
                await asyncio.sleep(.6)
            actual=state.get('origin',origin)
            checks.append({'requested_origin':origin,'origin':actual if actual in XHS_ALLOWED_ORIGINS else origin,'state':state.get('state','unknown')})
        except Exception:
            checks.append({'requested_origin':origin,'origin':origin,'state':'unavailable'})
    available=[c['origin'] for c in checks if c['state']=='logged_in']
    if available:return (preferred if preferred in available else available[0]),checks
    uncertain=[c['origin'] for c in checks if c['state']=='unknown']
    if uncertain:return (preferred if preferred in uncertain else uncertain[0]),checks
    return None,checks
