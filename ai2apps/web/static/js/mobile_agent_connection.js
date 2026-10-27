/* desktop-mobile-agent-v1: origin-bound keys, isolated signatures, no bearer in JS. */
(function(root){'use strict';
const prefix='/v1/mobile/agent',uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const enc=new TextEncoder(),b64=data=>btoa(String.fromCharCode(...new Uint8Array(data))).replaceAll('+','-').replaceAll('/','_').replaceAll('=','');
const hex=data=>Array.from(new Uint8Array(data),x=>x.toString(16).padStart(2,'0')).join('');
const hash=async data=>crypto.subtle.digest('SHA-256',data);
const native=()=>root.webkit?.messageHandlers?.mobileAgentKey;
async function database(){return new Promise((resolve,reject)=>{const r=indexedDB.open('ai2apps.mobile-agent.v1',1);r.onupgradeneeded=()=>r.result.createObjectStore('connections');r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}
async function storage(key,value,remove=false){const db=await database();try{return await new Promise((resolve,reject)=>{const tx=db.transaction('connections',value===undefined&&!remove?'readonly':'readwrite'),store=tx.objectStore('connections');const r=remove?store.delete(key):value===undefined?store.get(key):store.put(value,key);tx.oncomplete=()=>resolve(r.result);tx.onerror=()=>reject(tx.error);});}finally{db.close();}}
async function key(connection,create=false){if(!uuid.test(connection))throw Error('Invalid connection');if(native())return native().postMessage({operation:'key',connection,create});let value=await storage(connection);if(value)return value;if(!create)throw Error('连接私钥已丢失，请重新扫码。');
 const pair=await crypto.subtle.generateKey({name:'ECDSA',namedCurve:'P-256'},false,['sign','verify']);const raw=await crypto.subtle.exportKey('jwk',pair.publicKey);const jwk={crv:raw.crv,kty:raw.kty,x:raw.x,y:raw.y};const jkt=b64(await hash(enc.encode(JSON.stringify(jwk))));value={privateKey:pair.privateKey,jwk,jkt};await storage(connection,value);return value;}
async function sign(connection,operation,fields){if(native())return native().postMessage({operation,connection,...fields});const value=await key(connection);let input;
 if(operation==='claim')input=['ai2apps-mobile-agent-claim-v1',fields.ticket,value.jkt].join('\n');
 else if(operation==='proof')input=['ai2apps-mobile-agent-proof-v1',fields.action,connection,fields.nonce,value.jkt].join('\n');
 else if(operation==='local')input=['ai2apps-mobile-agent-local-v1',connection,fields.jti,fields.method,fields.target,fields.digest,fields.nonce].join('\n');
 else throw Error('Unknown signing operation');return b64(await crypto.subtle.sign({name:'ECDSA',hash:'SHA-256'},value.privateKey,enc.encode(input)));}
async function json(url,options={}){const response=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});const data=await response.json().catch(()=>({}));if(!response.ok){const error=Error(typeof data.detail==='string'?data.detail:data.error?.message||'连接请求失败');error.status=response.status;throw error;}return data;}
let unified=false;
let connection=null,lease=null,renewing=null,chain=Promise.resolve(),agentReady=false,expectedAgent=false,appsReady=false,connectionError=null,handoffFailed=false;
const post=(url,data)=>json(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
async function renew(){if(renewing)return renewing;renewing=(async()=>{const value=await key(connection);const challenge=await post(prefix+'/connections/'+connection+'/challenge',{action:'lease'});if(challenge.clientKeyThumbprint!==value.jkt)throw Error('连接公钥不匹配');const signature=await sign(connection,'proof',{action:'lease',nonce:challenge.nonce});lease=await post(prefix+'/connections/'+connection+'/lease',{nonce:challenge.nonce,signature,publicKey:value.jwk});lease.until=performance.now()+1000*Math.max(0,Math.min(60,lease.expiresIn??((Date.parse(lease.expiresAt)-Date.now())/1000)));return lease;})().finally(()=>renewing=null);return renewing;}
function target(url){const parsed=new URL(url,location.origin);if(parsed.origin!==location.origin)throw Error('Agent target origin denied');if(parsed.pathname.startsWith(prefix+'/'))return parsed.pathname+parsed.search;
 if(parsed.pathname.startsWith('/v1/platform/agent-runs/'))return prefix+parsed.pathname.slice('/v1/platform'.length)+parsed.search;
 const p=parsed.pathname;if(p==='/v1/mobile/chat/notification-target')return prefix+'/chat/notification-target';if(p==='/v1/mobile/models')return prefix+'/models';if(p==='/v1/mobile/chat/state')return prefix+'/chat/state';
 if(p==='/v1/mobile/agents'||p.startsWith('/v1/mobile/chat/threads')||p.startsWith('/v1/mobile/agent-runs/'))return prefix+p.slice('/v1/mobile'.length)+parsed.search;
 throw Error('Agent operation not allowed');}
async function signedFetch(url,options={}){if(unified){const path=target(url).replace(prefix+'/','/v1/mobile/owner-agent/');return fetch(path,{...options,credentials:'same-origin',cache:'no-store'});}if(!connection)throw Error('Agent connection unavailable');const path=target(url),method=(options.method||'GET').toUpperCase();if(!['GET','POST','PUT'].includes(method))throw Error('Agent method denied');
 // Each signed payload uses the exact body sent, including multipart boundaries.
 const request=new Request(location.origin+path,{method,body:options.body,headers:options.headers});const bytes=new Uint8Array(await request.arrayBuffer());
 const action=async()=>{if(!lease||lease.until-performance.now()<10000)await renew();const challenge=await post(prefix+'/connections/'+connection+'/nonce',{});if(challenge.jti!==lease.jti){lease=null;throw Error('连接租约已变化，请重新连接。');}
 const signature=await sign(connection,'local',{jti:lease.jti,method,target:path,digest:hex(await hash(bytes)),nonce:challenge.nonce});
 const headers=new Headers(request.headers);headers.set('X-AI2Apps-Agent-Connection',connection);headers.set('X-AI2Apps-Agent-Nonce',challenge.nonce);headers.set('X-AI2Apps-Agent-Signature',signature);
 const response=await fetch(path,{method,headers,body:method==='GET'?undefined:bytes,credentials:'same-origin',cache:'no-store'});if(response.status===401||response.status===403)lease=null;return response;};
 // Cloud challenges are not shared across requests; no automatic write retries.
 const result=chain.then(action,action);chain=result.then(()=>{},()=>{});return result;}
async function ownerSession(){try{const status=await json('/v1/mobile/owner-home/status');unified=status.authorized===true&&status.agentAuthorized===true;return unified;}catch(_){unified=false;return false;}}
async function resume(){if(await ownerSession()){agentReady=true;appsReady=true;return true;}connection=await storage('active');if(!connection||!uuid.test(connection))return false;try{await key(connection);await renew();agentReady=true;return true;}catch(error){lease=null;throw error;}}
// A saved connection is only a navigation hint. Proof and authorization remain
// on the native signer's existing top-level /mobile/home boundary.
async function restoreShellEntry(){
 if(root.top!==root||location.pathname!=='/mobile')return false;
 const params=new URLSearchParams(location.hash.slice(1));
 if(['handoff','agent_pair','agent_connection','apps_connection','apps_handoff'].some(k=>params.has(k)))return false;
 try{
  const owner=await ownerSession();const saved=owner?null:await storage('active');if(!owner&&!uuid.test(saved||''))return false;
  const app=params.get('app'),route=new URLSearchParams();
  if(app&&/^[A-Za-z0-9_.-]+$/.test(app))route.set('app',app);
  location.replace('/mobile/home'+(route.size?'#'+route:''));return true;
 }catch(_){return false;}
}
async function disconnect(){if(!connection)return;lease=null;let failure;try{const value=await key(connection),challenge=await post(prefix+'/connections/'+connection+'/challenge',{action:'revoke'});const signature=await sign(connection,'proof',{action:'revoke',nonce:challenge.nonce});await post(prefix+'/connections/'+connection+'/revoke',{nonce:challenge.nonce,signature,publicKey:value.jwk});}catch(error){if(![403,410].includes(error.status))failure=error;}finally{if(!failure){if(native())await native().postMessage({operation:'delete',connection});else await storage(connection,undefined,true);await storage('active',undefined,true);connection=null;}}if(failure)throw failure;}
async function pairPage(){
 const note=document.querySelector('[data-agent-pair-note]');if(!note)return false;
 agentReady=false;expectedAgent=false;appsReady=false;connectionError=null;handoffFailed=false;
 let appRequested=false;
 const params=new URLSearchParams(location.hash.slice(1));if(['agent_pair','agent_connection','apps_connection','apps_handoff'].some(k=>params.has(k)))history.replaceState(null,'',location.pathname);
 try{
  if(params.has('agent_pair')){
   const bootstrap=await json(prefix+'/bootstrap');if(!bootstrap.enabled)throw Error('Desktop 尚未启用手机 Agent 配对。');
   const ticket=params.get('agent_pair');if(!/^mag1\.[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/.test(ticket))throw Error('二维码无效');
   const cid=ticket.split('.')[1],value=await key(cid,true),signature=await sign(cid,'claim',{ticket});
   await storage('pending',cid);note.textContent='正在前往 Cloud 登录并申请 Desktop 确认…';
   location.replace('https://coder.ai2apps.com/mobile/agent-pair#'+new URLSearchParams({ticket,client_jwk:JSON.stringify(value.jwk),signature}));return false;
  }
  const hasApps=params.has('apps_handoff')||params.has('apps_connection');
  const agent=params.get('agent_connection');
  if(hasApps){
   appRequested=true;
   const cid=params.get('apps_connection'),handoff=params.get('apps_handoff');
   if(!uuid.test(cid||'')||!/^oh1\.[0-9a-f-]{36}\.[A-Za-z0-9_-]{43}$/.test(handoff||'')||(agent&&agent!==cid))throw Error('App 授权交接不匹配，请返回本次扫码确认页面。');
   note.textContent='正在完成此 Desktop 的应用授权…';
   // Both authorities are independently checked on Local. Never persist a handoff.
   await post('/v1/mobile/member-session/exchange',{handoff,mobileConnectionId:cid,appHandoffProtocol:'desktop-mobile-app-handoff-v1'});
   appsReady=true;
  }
  // App-only handoff does not revoke a previously approved Agent connection.
  // A saved ID is only a candidate: key possession and the live lease still decide.
  if(await ownerSession()){appsReady=true;agentReady=true;note.textContent='应用与 Agent 均已连接。';return true;}
  const cid=agent||await storage('active');
  if(cid){if(!uuid.test(cid))throw Error('连接无效');expectedAgent=true;await key(cid);connection=cid;await renew();agentReady=true;await storage('active',cid);}
  note.textContent=agentReady?(appsReady?'应用与 Agent 均已连接。':'Desktop 已批准，可以使用 Agent。'):(appsReady?'应用已连接。':'正在检查已有应用授权…');
  return appsReady||agentReady;
 }catch(error){agentReady=false;connectionError=error.message;handoffFailed=appRequested&&!appsReady;note.textContent=error.message;note.setAttribute('role','alert');return appsReady;}
}
async function downloadFile(run, artifact, filename){const response=await signedFetch(prefix+'/files/'+encodeURIComponent(run)+'/'+encodeURIComponent(artifact));if(!response.ok)throw Error('Download unavailable');const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');link.href=url;link.download=filename||'download';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
async function imageBlob(path){const response=await signedFetch(path);if(!response.ok){const detail=await response.json().catch(()=>({}));throw Error('图片读取失败（HTTP '+response.status+'）：'+(typeof detail.detail==='string'?detail.detail:'资源不可用'));}const blob=await response.blob();if(!['image/jpeg','image/png','image/webp','image/avif','image/gif'].includes(blob.type))throw Error('图片类型不可用');const url=URL.createObjectURL(blob);return {url,dispose:()=>URL.revokeObjectURL(url),async paint(canvas){const bitmap=await createImageBitmap(blob);try{canvas.width=bitmap.width;canvas.height=bitmap.height;canvas.getContext('2d').drawImage(bitmap,0,0);}finally{bitmap.close();}}};}
const resultImage=(run,index,item)=>imageBlob(prefix+'/assets/'+encodeURIComponent(run)+'/'+index+'/'+item);
const artifactImage=(run,artifact)=>imageBlob(prefix+'/artifacts/'+encodeURIComponent(run)+'/'+encodeURIComponent(artifact));
root.AI2AppsAgentConnection={status:()=>({agent:agentReady,expectedAgent,apps:appsReady,error:connectionError,handoffFailed}),resume,signedFetch,downloadFile,disconnect,resultImage,artifactImage,pairPage,restoreShellEntry,sign,key,target};
if(typeof module!=='undefined')module.exports={target};
if(typeof document!=='undefined'){root.AI2AppsAgentConnection.ready=pairPage();root.addEventListener('hashchange',()=>{if(new URLSearchParams(location.hash.slice(1)).has('agent_pair')||new URLSearchParams(location.hash.slice(1)).has('apps_handoff'))root.AI2AppsAgentConnection.ready=pairPage().then(result=>{root.dispatchEvent(new Event('ai2apps-agent-connection-ready'));return result;});});}
})(typeof window==='undefined'?globalThis:window);
