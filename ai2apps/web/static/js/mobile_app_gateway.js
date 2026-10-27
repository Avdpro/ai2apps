/* Trusted host App requests stay inside the manifest's API scope and mount. */
(() => {
 'use strict';
 const config=JSON.parse(document.getElementById('mobile-app-gateway').textContent);
 const nativeFetch=window.fetch.bind(window);
 const uid=()=>crypto.randomUUID?.()||Array.from(crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,'0')).join('');
 const encode=bytes=>{let s='';for(let i=0;i<bytes.length;i+=8192)s+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(s);};
 const kind=text=>!text?'empty':/^\s*</.test(text)?'html':/^\s*[\[{]/.test(text)?'json':'other';
 let diagnosticSupport,diagnosticProbe;
 async function supportsDiagnostics(){
  if(config.apiPrefix!=='/v1/platform/intelligence')return false;
  if(diagnosticSupport!==undefined)return diagnosticSupport;
  if(diagnosticProbe)return diagnosticProbe;
  diagnosticProbe=(async()=>{
   try{
    const response=await nativeFetch(config.bridge,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({method:'request',verb:'GET',path:config.apiPrefix+'/client-diagnostics',headers:{},body:''})});
    if(!response.ok)return false;
    const envelope=JSON.parse(await response.text());
    if(envelope.status===404){diagnosticSupport=false;return false;}
    if(envelope.status!==200||typeof envelope.body!=='string')return false;
    diagnosticSupport=JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(envelope.body),c=>c.charCodeAt(0)))).version===1;
    return diagnosticSupport;
   }catch(_){return false;}
   finally{diagnosticProbe=null;}
  })();
  return diagnosticProbe;
 }
 const key='ai2apps.mobile-diagnostics.v1:'+config.apiPrefix;
 let events=[],flushing=false;
 try{events=JSON.parse(sessionStorage.getItem(key)||'[]').filter(e=>Date.now()-Date.parse(e.timestamp)<86400000).slice(-40);}catch(_){}
 const persist=()=>{try{sessionStorage.setItem(key,JSON.stringify(events));}catch(_){}};
 const diagnostic={
  context:()=>({}),
  record(value){
   if(config.apiPrefix!=='/v1/platform/intelligence'||value.path?.endsWith('/client-diagnostics'))return;
   const context=diagnostic.context?.()||{};
   const event={event_id:uid(),timestamp:new Date().toISOString(),online:navigator.onLine,visibility:document.visibilityState,...context,...value};
   // Metadata only: never retain response bodies, query strings or credentials.
   const allowed=['event_id','timestamp','online','visibility','view','tab','request_id','method','path','phase','code','status','relay_status','content_type','response_bytes','response_path','redirected','response_kind','elapsed_ms','attempt'];
   events.push(Object.fromEntries(allowed.filter(k=>event[k]!==undefined).map(k=>[k,event[k]])));events=events.slice(-40);persist();
  },
  pending:()=>events.map(e=>({...e})),
  async flush(){
   if(flushing||!events.length||config.apiPrefix!=='/v1/platform/intelligence'||!await supportsDiagnostics())return;
   events=events.filter(e=>Date.now()-Date.parse(e.timestamp)<86400000);persist();
   if(!events.length)return;
   flushing=true;const batch=events.slice(0,20);
   try{
    const id=uid(),body=encode(new TextEncoder().encode(JSON.stringify({events:batch})));
    const response=await nativeFetch(config.bridge,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({method:'request',verb:'POST',path:config.apiPrefix+'/client-diagnostics',headers:{'content-type':'application/json','x-ai2apps-request-id':id},body})});
    if(!response.ok)return;
    const result=JSON.parse(await response.text());if(result.status!==200||typeof result.body!=='string')return;
    const accepted=new Set(JSON.parse(new TextDecoder().decode(Uint8Array.from(atob(result.body),c=>c.charCodeAt(0)))).accepted||[]);
    events=events.filter(e=>!accepted.has(e.event_id));persist();
   }catch(_){/* Keep the bounded queue until a real request succeeds again. */}
   finally{flushing=false;}
  },
 };
 window.MobileAppDiagnostics=diagnostic;
 const transportFailure=(status=502,code='mobile_gateway_invalid_response',id='',relayStatus=0)=>new Response(JSON.stringify({detail:window.t?.('ai_browser.network_error')||'Unable to connect. Check your connection and try again.',error:{code,request_id:id}}),{status,headers:{'Content-Type':'application/json','X-AI2Apps-Request-Id':id,'X-AI2Apps-Relay-Status':String(relayStatus)}});
 window.MobileAppResource=url=>{
  const u=new URL(url,location.origin);
  return u.origin===location.origin&&u.pathname.startsWith(config.apiPrefix+'/')?config.resourceBase+'api/'+u.pathname.slice(config.apiPrefix.length+1)+u.search:url;
 };
 window.fetch=async(input,options)=>{
  const request=new Request(input,options),url=new URL(request.url);
  if(url.origin!==location.origin||!(url.pathname===config.apiPrefix||url.pathname.startsWith(config.apiPrefix+'/')))return nativeFetch(request);
  const traced=await supportsDiagnostics();
  const headers={};for(const name of ['content-type','x-intelligence-language','x-ai2apps-app-instance'])if(request.headers.has(name))headers[name]=request.headers.get(name);
  const id=request.headers.get('x-ai2apps-request-id')||uid(),attempt=Number(request.headers.get('x-ai2apps-request-attempt')||0);
  if(traced){headers['x-ai2apps-request-id']=id;headers['x-ai2apps-request-attempt']=String(attempt);}
  const started=performance.now(),base={request_id:id,method:request.method,path:url.pathname,attempt};
  const report=(phase,code,response,text='')=>diagnostic.record({...base,phase,code,response_path:response?.url?new URL(response.url).pathname.split('/').map(part=>part.length>32||/^[a-f0-9-]{16,}$/i.test(part)?':id':part).join('/').slice(0,500):'',redirected:!!response?.redirected,status:response?.status||0,relay_status:response?.status||0,content_type:(response?.headers.get('content-type')||'').slice(0,128),response_bytes:Math.min(33554432,new TextEncoder().encode(text).length),response_kind:kind(text),elapsed_ms:Math.min(600000,Math.round(performance.now()-started))});
  let response;
  try{
   response=await nativeFetch(config.bridge,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({method:'request',verb:request.method,path:url.pathname+url.search,headers,body:encode(new Uint8Array(await request.arrayBuffer()))})});
  }catch(error){report('network','mobile_gateway_network_error');throw error;}
  let text;
  try{text=await response.text();}catch(error){report('network','mobile_gateway_body_interrupted',response);throw error;}
  if(!response.ok){
   report('relay_http','mobile_gateway_http_error',response,text);
   try{const parsed=JSON.parse(text);if(parsed&&typeof parsed==='object')return new Response(text,{status:response.status,headers:{'Content-Type':'application/json','X-AI2Apps-Request-Id':id,'X-AI2Apps-Relay-Status':String(response.status)}});}catch(_){}
   // FRPS 0.62.1 also emits its HTML 404 page for upstream EOF. This is
   // outside the App response envelope, not an article/mount business 404.
   // Expose a gateway failure so the caller's bounded GET-only retry applies.
   // Preserve authentication failures and genuine JSON/enveloped App errors.
   if(response.status===404&&kind(text)==='html')return transportFailure(502,'mobile_gateway_upstream_unavailable',id,response.status);
   return transportFailure(response.status,'mobile_gateway_http_error',id,response.status);
  }
  let result;
  try{result=JSON.parse(text);}catch(_){report('relay_json','mobile_gateway_invalid_json',response,text);return transportFailure(502,'mobile_gateway_invalid_json',id,response.status);}
  if(!result||!Number.isInteger(result.status)||result.status<200||result.status>599||typeof result.body!=='string'||typeof result.contentType!=='string'){
   report('relay_envelope','mobile_gateway_invalid_envelope',response,text);return transportFailure(502,'mobile_gateway_invalid_envelope',id,response.status);
  }
  try{
   const bytes=Uint8Array.from(atob(result.body),c=>c.charCodeAt(0));
   const decoded=new Response([204,205,304].includes(result.status)?null:bytes,{status:result.status,headers:{'Content-Type':result.contentType,'X-AI2Apps-Request-Id':id,'X-AI2Apps-Relay-Status':String(response.status)}});
   if(!url.pathname.endsWith('/client-diagnostics'))void diagnostic.flush();
   return decoded;
  }catch(_){report('relay_body','mobile_gateway_invalid_body',response);return transportFailure(502,'mobile_gateway_invalid_body',id,response.status);}
 };
})();
