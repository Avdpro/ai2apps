const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const repoRoot=path.resolve(__dirname,'../..');
const fixtureHTML=execFileSync(path.join(repoRoot,'.venv/bin/python'),['-c',`
import json,sys
from pathlib import Path
from jinja2 import Environment,FileSystemLoader
root=Path(sys.argv[1])/'ai2apps/web'
locale=json.loads((root/'i18n/en.json').read_text())
env=Environment(loader=FileSystemLoader(str(root/'templates')),autoescape=True)
print(env.get_template('system_apps/messager_mobile.html').render(current_lang='en',locale_json='{}',t=lambda key:locale.get(key,key),static=lambda name:'/assets/'+name,mobile_static=lambda name:'/assets/'+name,mobile_gateway_config={'apiPrefix':'/v1/platform/messager-mobile','bridge':'/bridge','resourceBase':'/resource/'}))
`,repoRoot],{cwd:repoRoot,encoding:'utf8'});
test('Mobile groups react immediately, coalesce writes and recover background refresh',async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
  const faults=[];page.on('pageerror',e=>faults.push(e.message));
  await page.addInitScript(()=>{const interval=window.setInterval;window.setInterval=(fn,ms,...args)=>{if(ms===5000){window.listTick=fn;return interval(fn,1000000,...args);}return interval(fn,ms,...args);};});
  let group={id:'quick',name:'Quick Bots',permanent:true,collapsed:false,revision:1},held=true,active=0,maxActive=0,failedReads=0,readCalls=0,loseAck=false;
  const writes=[],releases=[];
  await page.route('https://group.fixture/**',async route=>{
   const u=new URL(route.request().url());
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:fixtureHTML});
   if(u.pathname.startsWith('/assets/')){const f=path.join(repoRoot,'ai2apps/web/static',u.pathname.slice(8));return route.fulfill({contentType:f.endsWith('.css')?'text/css':'application/javascript',body:fs.readFileSync(f)});}
   if(u.pathname!=='/bridge')return route.fulfill({status:404,body:''});
   const body=route.request().postDataJSON(),payload=body.body?JSON.parse(Buffer.from(body.body,'base64')):{},p=new URL(body.path,'https://app.local').pathname;let value={};
   if(p.endsWith('/bots')){readCalls++;if(failedReads>0){failedReads--;return route.fulfill({status:502,contentType:'text/html',body:'<html>Upstream temporarily unavailable</html>'});}value={items:[{id:'bot',name:'A Bot',group_id:'quick',definition:{execution_mode:'standard'},avatar:{kind:'preset'}}]};}
   else if(p.endsWith('/bot-groups'))value={items:[{...group}]};
   else if(p.endsWith('/bot-groups/quick')){
    writes.push(payload);active++;maxActive=Math.max(maxActive,active);
    if(held)await new Promise(resolve=>releases.push(resolve));
    active--;
    if(payload.revision!==group.revision){return route.fulfill({contentType:'application/json',body:JSON.stringify({status:409,contentType:'application/json',body:Buffer.from(JSON.stringify({detail:'Group changed; review it again'})).toString('base64')})});}
    group={...group,collapsed:payload.collapsed,revision:group.revision+1};value={items:[{...group}]};
    if(loseAck){loseAck=false;return route.fulfill({status:502,contentType:'text/html',body:'<html>Lost acknowledgement</html>'});}
   }
   return route.fulfill({contentType:'application/json',body:JSON.stringify({status:200,contentType:'application/json',body:Buffer.from(JSON.stringify(value)).toString('base64')})});
  });
  const until=async predicate=>{const end=Date.now()+5000;while(!predicate()){if(Date.now()>end)throw Error('Fixture did not settle');await new Promise(r=>setTimeout(r,10));}};
  await page.goto('https://group.fixture/');const toggle=page.locator('[data-bot-group-id="quick"] .mm-group-heading > button').first();await toggle.waitFor();
  const click=()=>page.evaluate(()=>document.querySelector('[data-bot-group-id="quick"] .mm-group-heading > button').click());
  const expanded=()=>toggle.getAttribute('aria-expanded');
  await click();assert.equal(await expanded(),'false');assert.equal(await page.locator('.mm-bot').isVisible(),false);assert.equal(writes.length,0,'paint does not wait for save debounce or network');
  await until(()=>releases.length===1);
  await page.evaluate(()=>{const button=document.querySelector('[data-bot-group-id="quick"] .mm-group-heading > button');button.click();button.click();button.click();});
  assert.equal(await expanded(),'true');assert.equal(writes.length,1,'clicks while pending do not race revisions');
  await page.evaluate(()=>{listTick();listTick();});await until(()=>readCalls===2);await page.waitForTimeout(50);assert.equal(await expanded(),'true','poll cannot undo pending intent');
  releases.shift()();await until(()=>releases.length===1);assert.equal(writes[1].revision,2);assert.equal(writes[1].collapsed,false);releases.shift()();await until(()=>group.revision===3);await page.waitForTimeout(80);
  assert.equal(maxActive,1);assert.equal(await expanded(),'true');assert.equal(await page.locator('.mm-bot').isVisible(),true);assert.equal(await page.locator('#mm-notice').isVisible(),false);
  held=false;group={...group,revision:4};await click();await until(()=>group.revision===5);await page.waitForTimeout(80);assert.equal(writes.at(-1).revision,4);assert.equal(await expanded(),'false');assert.equal(await page.locator('#mm-notice').isVisible(),false);
  const previous=writes.length;loseAck=true;await click();await until(()=>group.revision===6);await page.waitForTimeout(100);assert.equal(writes.length,previous+1,'lost acknowledgement reads back without replaying mutation');assert.equal(await expanded(),'true');assert.equal(await page.locator('#mm-notice').isVisible(),false);
  const tick=async()=>{const count=readCalls;await page.evaluate(()=>listTick());await until(()=>readCalls>count);await page.waitForTimeout(80);};
  failedReads=1;await tick();assert.equal(await page.locator('#mm-notice').isVisible(),false,'one transient background error does not toast');await tick();
  failedReads=2;await tick();await tick();assert.equal(await page.locator('#mm-notice').isVisible(),true,'persistent failures remain visible');await tick();assert.equal(await page.locator('#mm-notice').isVisible(),false,'recovery clears connectivity notice');
  assert.deepEqual(faults,[]);await page.screenshot({path:'/tmp/mobile-group-responsive-390.png'});
 }finally{await browser.close();}
});
