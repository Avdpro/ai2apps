"""Trip Planner's visible result-card reader on the shared native BiDi SDK."""
import asyncio
from urllib.parse import urlsplit

ACTION = 'travel_results'
SCRIPT = r'''function(provider){
 const visible=n=>ai2appsDOMVisible(n);
 const text=n=>(n?.innerText||'').trim();
 const controls=[...document.querySelectorAll('input:not([type=password])')].filter(visible)
   .filter(n=>!n.type||!['email','hidden'].includes(n.type))
   .map(n=>({label:n.getAttribute('aria-label')||n.placeholder||n.name||'',value:n.value||''})).slice(0,15);
 for(const n of document.querySelectorAll('button,[role=button],[role=combobox]:not(input)')){
  if(!visible(n))continue;
  const label=n.getAttribute('aria-label')||'',value=text(n);
  if(/passenger|adult|travell?er|round trip|one way|economy|business|first class|check.?in|check.?out|date|departure|return|\b(?:Sun|Mon|Tue|Wed|Thu|Fri|Sat|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b|入住|退房|成人|间|单程|往返|舱|直飞|出发|到达|\d{1,2}月/i.test(label+' '+value))
   controls.push({label:label.slice(0,250),value:value.slice(0,250)});
  if(controls.length>=30)break;
 }
 let formText='';
 if(provider==='ctrip_flights'){
  const routeInputs=[...document.querySelectorAll('input')].filter(n=>visible(n)&&n.placeholder==='可输入城市或机场');
  for(let n=routeInputs[0]?.parentElement,i=0;n&&i<10;n=n.parentElement,i++){
   const value=text(n);
   if(value.length>4000)break;
   if(routeInputs.length===2&&n.contains(routeInputs[1])&&/出发日期/.test(value)){formText=value;break;}
  }
 }
 let roots=[];
 if(provider==='booking')roots=[...document.querySelectorAll('[data-testid="property-card"]')];
 else if(provider==='expedia_hotels')roots=[...document.querySelectorAll('[data-stid="property-listing"], [data-stid="lodging-card-responsive"]')];
 else if(provider==='ctrip_hotels'){
  // Follow visible semantic card controls, not CSS hashes or hidden app state.
  for(const button of document.querySelectorAll('button,[role=button]')){
   if(!visible(button)||text(button)!=='查看详情')continue;
   for(let n=button.parentElement,depth=0;n&&depth<8;n=n.parentElement,depth++){
    const value=text(n);if(value.length>5000)break;
    if(value.length>30&&/点评/.test(value)&&/查看地图/.test(value)){roots.push(n);break;}
   }
  }
 }
 else if(provider==='ctrip_flights'){
  if(location.pathname.startsWith('/online/list/')){
   roots=[...document.querySelectorAll('.flight-box')];
   for(const button of (roots.length?[]:document.querySelectorAll('button,[role=button],a,span,div'))){
    if(!visible(button)||!/^(?:订票|选择|预订|选为去程|选为返程)$/.test(text(button)))continue;
    for(let n=button.parentElement,depth=0;n&&depth<8;n=n.parentElement,depth++){
     const value=text(n);if(value.length>5000)break;
     if(value.length>40&&/\d{1,2}:\d{2}/.test(value)&&/[¥￥]/.test(value)&&/[A-Z0-9]{2}\d{3,4}/.test(value)){roots.push(n);break;}
    }
   }
  }
 }
 else roots=[...document.querySelectorAll('li,[data-test-id=offer-listing],[data-stid=flight-offer]')].filter(n=>{
   const t=text(n);return t.length>40&&t.length<5000&&/(?:[$€£¥￥]|USD|CNY)/.test(t)&&/(?:nonstop|stops?|\d\s*h\b|直飞|转机|小时)/i.test(t);
 });
 const seen=new Set(),items=[];
 for(const root of roots){
  if(!visible(root)||root.closest('nav,header,footer,[role=dialog]'))continue;
  const quote=text(root).slice(0,3000);if(quote.length<30||seen.has(quote))continue;seen.add(quote);
  const heading=root.querySelector('[data-testid="title"]')||root.querySelector('h3,h2,[role=heading]');
  const gallery=root.querySelector('[aria-label^="Photo gallery for"]');
  const title=(text(heading)||gallery?.getAttribute('aria-label')?.replace(/^Photo gallery for /,'')||quote.split('\n')[0]).replace(/\nOpens in new window$/i,'').slice(0,300);
  let url=location.href;
  if(provider==='booking'||provider==='expedia_hotels'){
   const link=root.querySelector('a[data-testid="title-link"],a[href*="/hotel/"],a[data-stid="open-hotel-information"]');
   if(link){try{const u=new URL(link.href);if(u.protocol==='https:'&&u.hostname===location.hostname){
     // Do not pass account/session/tracking parameters into the result view.
     for(const key of [...u.searchParams.keys()])if(!['checkin','checkout','group_adults','no_rooms','selected_currency'].includes(key))u.searchParams.delete(key);
     url=u.href;
   }}catch(_){}}
  }
  items.push({id:'option-'+items.length,title,quote,url});if(items.length>=12)break;
 }
 return {url:location.href,title:document.title,controls,observed_items:items,
   text:JSON.stringify(controls)+'\n'+formText+'\n'+items.map(i=>i.id+'\n'+i.quote).join('\n\n'),
   extraction_method:'visible-travel-cards',search_results_observed:items.length>0};
}'''


async def read(page, step, inputs, run):
    from .travel import PROVIDERS
    provider = inputs['provider']
    host = urlsplit(PROVIDERS[provider][1]).hostname
    current = urlsplit((await page.snapshot(100))['url'])
    if current.scheme != 'https' or current.hostname != host:
        return {'outcome':'restricted','evidence':{'reason':'travel_result_site_mismatch'}}
    access = await page.handle_access()
    if access['classification'] in ('needs_user','restricted'):
        return {'outcome':access['classification'],'evidence':{
            'reason':access.get('reason'),'assistance_kind':access.get('assistance_kind')}}
    await page.wait_stable(require_content=True)
    result = await page.call_json(SCRIPT, [provider])
    for _ in range(2):
        if result.get('observed_items'):
            break
        await asyncio.sleep(1)
        result = await page.call_json(SCRIPT, [provider])
    return {'outcome':'success','evidence':{'operation':'inspect','result':result}}


def register(runtime, caller):
    readers = getattr(runtime, 'browser_owner_readers', {})
    readers[(caller, ACTION)] = read
    runtime.browser_owner_readers = readers


def install(runtime):
    """Restore bindings for already installed Trip Planner instances on restart."""
    with runtime.database.transaction() as connection:
        rows = connection.execute('''SELECT i.id FROM app_instances i
            JOIN app_definitions d ON d.id=i.app_definition_id
            WHERE d.package_id IN ('ai2apps/trip-planner','ai2apps.trip-planner')''').fetchall()
    for row in rows:
        register(runtime, 'web-mini-app:' + row['id'] + ':ai2apps.trip-planner')
