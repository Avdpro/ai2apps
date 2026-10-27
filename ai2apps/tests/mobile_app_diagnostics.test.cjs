const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium,webkit}=require('playwright');const root=path.join(__dirname,'..');
test('Mobile diagnostics identify relay failure, persist offline metadata and upload on recovery',async()=>{
 const browser=await(process.env.INTELLIGENCE_TEST_WEBKIT?webkit.launch({headless:true}):chromium.launch({channel:'chrome',headless:true}));
 try{
  const page=await browser.newPage();
  await page.route('https://diagnostic.test/**',r=>r.fulfill({contentType:'text/html',body:'<script id="mobile-app-gateway" type="application/json">{"apiPrefix":"/v1/platform/intelligence","bridge":"/bridge","resourceBase":"/resource/"}</script>'}));
  await page.goto('https://diagnostic.test');
  async function install(){
   await page.evaluate(()=>{
    window.reports=[];window.requests=[];window.plans=[];window.t=()=> 'Unable to connect';
    window.fetch=async(url,options)=>{
     const body=JSON.parse(options.body);requests.push(body);
     if(body.path.endsWith('/client-diagnostics')){
      if(body.verb==='GET')return new Response(JSON.stringify({status:200,contentType:'application/json',body:btoa('{"version":1}')}));
      const report=JSON.parse(atob(body.body));reports.push(report);
      return new Response(JSON.stringify({status:200,contentType:'application/json',body:btoa(JSON.stringify({accepted:report.events.map(e=>e.event_id)}))}));
     }
     const plan=plans.shift();if(plan.error)throw new TypeError('Network failed');return new Response(plan.body,{status:plan.status,headers:{'Content-Type':plan.type||'text/html'}});
    };
   });
   await page.addScriptTag({content:fs.readFileSync(path.join(root,'web/static/js/mobile_app_gateway.js'),'utf8')});
   await page.evaluate(()=>MobileAppDiagnostics.context=()=>({view:'channel',tab:'runs'}));
  }
  await install();
  const initial=await page.evaluate(async()=>{
   plans.push({status:200,body:'<html>private-response-secret</html>'},{status:401,body:'<html>auth</html>'},{error:true});
   const r=await fetch('/v1/platform/intelligence?token=query-secret');const value=await r.json();
   await fetch('/v1/platform/intelligence/channels/id/runs');
   try{await fetch('/v1/platform/intelligence');}catch(_){}
   return {value,events:MobileAppDiagnostics.pending()};
  });
  assert.equal(initial.events.length,3);assert.equal(initial.events[0].phase,'relay_json');assert.equal(initial.events[0].relay_status,200);assert.equal(initial.events[0].response_kind,'html');
  assert.equal(initial.events[0].tab,'runs');assert.equal(initial.value.error.request_id,initial.events[0].request_id);
  assert.equal(initial.events[1].phase,'relay_http');assert.equal(initial.events[1].status,401);assert.equal(initial.events[2].phase,'network');
  assert.doesNotMatch(JSON.stringify(initial.events),/query-secret|private-response-secret|token=/);
  await page.reload();await install();assert.equal(await page.evaluate(()=>MobileAppDiagnostics.pending().length),3);
  await page.evaluate(async()=>{plans.push({status:200,type:'application/json',body:JSON.stringify({status:200,contentType:'application/json',body:btoa('{"ok":true}')})});await fetch('/v1/platform/intelligence');});
  await page.waitForFunction(()=>MobileAppDiagnostics.pending().length===0);
  assert.equal(await page.evaluate(()=>reports[0].events.length),3);assert.equal(await page.evaluate(()=>reports[0].events[0].request_id),initial.events[0].request_id);
  const appSource=fs.readFileSync(path.join(root,'web/static/js/intelligence.js'),'utf8');
  await page.addScriptTag({content:"const lt=s=>s;const it=(parts,...values)=>parts.reduce((s,p,i)=>s+p+(values[i]??''),'');"+appSource.slice(appSource.indexOf('async function requestJSON('),appSource.indexOf('async function api('))});
  const recovered=await page.evaluate(async()=>{
   reports=[];requests=[];
   plans.push({status:200,body:'<html>relay reconnect</html>'},{status:200,type:'application/json',body:JSON.stringify({status:200,contentType:'application/json',body:btoa('{"ok":true}')})});
   const value=await requestJSON('/v1/platform/intelligence');
   await new Promise(resolve=>setTimeout(resolve,30));await MobileAppDiagnostics.flush();
   return {value,reports,requests};
  });
  assert.equal(recovered.value.ok,true);
  const attempts=recovered.requests.filter(r=>r.path==='/v1/platform/intelligence');assert.equal(attempts.length,2);
  assert.equal(attempts[0].headers['x-ai2apps-request-id'],attempts[1].headers['x-ai2apps-request-id']);
  assert.deepEqual(attempts.map(r=>r.headers['x-ai2apps-request-attempt']),['0','1']);
  const phases=recovered.reports.flatMap(r=>r.events).map(e=>e.phase);assert.ok(phases.includes('relay_json')&&phases.includes('app_http')&&phases.includes('recovered'));
  const frpRecovery=await page.evaluate(async()=>{
   reports=[];requests=[];
   plans.push({status:404,body:'<html>FRP upstream unavailable</html>'},{status:200,type:'application/json',body:JSON.stringify({status:200,contentType:'application/json',body:btoa('{"ok":true}')})});
   const value=await requestJSON('/v1/platform/intelligence?view=channels');
   await new Promise(resolve=>setTimeout(resolve,30));await MobileAppDiagnostics.flush();
   return {value,reports,requests};
  });
  assert.equal(frpRecovery.value.ok,true);
  assert.equal(frpRecovery.requests.filter(r=>r.path.includes('?view=channels')).length,2);
  const frpEvents=frpRecovery.reports.flatMap(r=>r.events);
  assert.ok(frpEvents.some(e=>e.phase==='relay_http'&&e.status===404&&e.response_kind==='html'));
  assert.ok(frpEvents.some(e=>e.phase==='app_http'&&e.status===502&&e.relay_status===404));
  assert.ok(frpEvents.some(e=>e.phase==='recovered'));
  const real404=await page.evaluate(async()=>{
   requests=[];plans.push({status:200,type:'application/json',body:JSON.stringify({status:404,contentType:'application/json',body:btoa('{"detail":"Article missing"}')})});
   try{await requestJSON('/v1/platform/intelligence/articles/missing');}catch(error){return {requests,message:error.message};}
  });
  assert.equal(real404.requests.filter(r=>r.path.endsWith('/articles/missing')).length,1);
  assert.match(real404.message,/Article missing/);
  const mutation=await page.evaluate(async()=>{
   requests=[];plans.push({status:404,body:'<html>FRP upstream unavailable</html>'});
   try{await requestJSON('/v1/platform/intelligence/articles/id',{method:'PATCH',body:'{"favorite":true}'});}catch(error){return {message:error.message,id:error.requestId,requests};}
  });
  assert.equal(mutation.requests.filter(r=>r.path.includes('/articles/')).length,1);assert.ok(mutation.message.includes(mutation.id.slice(0,8)));
  await page.evaluate(()=>{for(let i=0;i<50;i++)MobileAppDiagnostics.record({request_id:'a'.repeat(32),method:'GET',path:'/v1/platform/intelligence',phase:'network',code:'test',response_body:'must-not-save'});});
  assert.equal(await page.evaluate(()=>MobileAppDiagnostics.pending().length),40);assert.doesNotMatch(await page.evaluate(()=>JSON.stringify(MobileAppDiagnostics.pending())),/must-not-save/);
  await page.reload();
  await page.evaluate(()=>{window.sent=[];window.fetch=async(url,options)=>{const value=JSON.parse(options.body);sent.push(value);return new Response(JSON.stringify(value.path.endsWith('/client-diagnostics')?{status:404,contentType:'application/json',body:btoa('{"detail":"Not Found"}')}:{status:200,contentType:'application/json',body:btoa('{"ok":true}')}));};});
  await page.addScriptTag({content:fs.readFileSync(path.join(root,'web/static/js/mobile_app_gateway.js'),'utf8')});
  await page.evaluate(async()=>{await fetch('/v1/platform/intelligence',{headers:{'X-AI2Apps-Request-Id':'a'.repeat(32),'X-AI2Apps-Request-Attempt':'0'}});});
  const legacy=await page.evaluate(()=>sent.find(r=>r.path==='/v1/platform/intelligence'));
  assert.equal(legacy.headers['x-ai2apps-request-id'],undefined);assert.equal(legacy.headers['x-ai2apps-request-attempt'],undefined);
  await page.close();
 }finally{await browser.close();}
});
