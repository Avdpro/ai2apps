/* Shared durable output cards. Metadata stays out of model content. */
(function(root){'use strict';
const words={zh:{download:'下载',gallery:'加入素材库',added:'已加入素材库',preview:'预览 / 打开',load:'加载试听',video:'加载视频',failed:'素材不可用，请重试',large:'文件较大，请下载后打开',unsupported:'此格式请下载后使用本机应用打开',close:'关闭预览'},en:{download:'Download',gallery:'Add to library',added:'Added to library',preview:'Preview / open',load:'Load audio',video:'Load video',failed:'Asset unavailable. Please retry.',large:'Large file: download to open',unsupported:'Download to open in a compatible app',close:'Close preview'}};
function label(key){return words[(root.document?.documentElement.lang||root.navigator?.language||'en').startsWith('zh')?'zh':'en'][key];}
function reference(url){if(typeof url!=='string')return null;const m=/^\/v1\/platform\/sessions\/([A-Za-z0-9_-]{1,256})\/artifacts\/([A-Za-z0-9_-]{1,256})\/download$/.exec(url);return m?{session:m[1],artifact:m[2]}:null;}
function render(node,records,options={}){
 const files=(Array.isArray(records)?records:[]).slice(0,64).filter(f=>reference(f?.url)&&!(options.imageUrls||[]).includes(f.url)&&(options.includeImages||!String(f.media_type).startsWith('image/')));
 const key=JSON.stringify([files,options.runId||'']);if(node._artifactKey===key)return;node._artifactKey=key;node._artifactDispose?.();node.replaceChildren();
 const cleanups=[];node._artifactDispose=()=>{cleanups.splice(0).forEach(f=>f());};
 async function request(file,action){
  const ref=reference(file.url);const headers=options.apiKey?{Authorization:'Bearer '+options.apiKey}:{};
  if(options.signed){if(!options.runId)throw Error(label('failed'));return root.AI2AppsAgentConnection.signedFetch('/v1/mobile/agent/files/'+encodeURIComponent(options.runId)+'/'+encodeURIComponent(ref.artifact)+(action==='gallery'?'/gallery':''),action==='gallery'?{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}:{});}
  return fetch(action==='gallery'?'/v1/platform/gallery/assets/import-artifact/'+ref.session+'/'+ref.artifact:file.url,{credentials:'same-origin',headers:{...headers,...(action==='gallery'?{'Content-Type':'application/json'}:{})},...(action==='gallery'?{method:'POST',body:'{}'}:{})});
 }
 for(const file of files){
  const card=document.createElement('section');card.className='chat-artifact-card';
  const kind=String(file.media_type||'application/octet-stream').split(';')[0];const title=document.createElement('strong');title.textContent=(kind.startsWith('audio/')?'♫ ':kind.startsWith('video/')?'▶ ':'▤ ')+(file.filename||file.artifact_id);card.append(title);
  const meta=document.createElement('small');meta.textContent=kind+(Number.isFinite(file.size_bytes)?' · '+(file.size_bytes/1024/1024).toFixed(1)+' MB':'');card.append(meta);
  const preview=document.createElement('div');preview.className='chat-artifact-preview';const actions=document.createElement('div');actions.className='chat-artifact-actions';const status=document.createElement('p');status.setAttribute('role','status');card.append(preview,actions,status);node.append(card);
  let url=null,blob=null,closed=false;const controller=new AbortController();cleanups.push(()=>{closed=true;controller.abort();preview.querySelectorAll('audio,video').forEach(m=>{m.pause();m.removeAttribute('src');m.load();});if(url)URL.revokeObjectURL(url);});
  async function load(){if(blob)return blob;const response=await request(file,'read');if(!response.ok)throw Error(label('failed')+' (HTTP '+response.status+')');blob=await response.blob();if(closed)throw Error(label('failed'));return blob;}
  function button(key,fn){const b=document.createElement('button');b.type='button';b.textContent=label(key);b.title=label(key);b.setAttribute('aria-label',label(key));b.onclick=async()=>{b.disabled=true;status.textContent='';try{await fn(b);}catch(e){status.textContent=e.message||label('failed');}finally{b.disabled=false;}};actions.append(b);return b;}
  const image=/^image\/(png|jpeg|webp|avif|gif)$/.test(kind),playable=/^(audio|video)\//.test(kind),pdf=kind==='application/pdf',text=/^text\/(plain|csv|markdown)$/.test(kind)||['application/json','application/xml'].includes(kind);
  if(image||playable||pdf||text)button(playable?(kind.startsWith('audio/')?'load':'video'):'preview',async b=>{
   if(preview.childNodes.length){preview.querySelectorAll('audio,video').forEach(m=>m.pause());preview.replaceChildren();b.textContent=label(playable?(kind.startsWith('audio/')?'load':'video'):'preview');return;}
   if(file.size_bytes>100*1024*1024){status.textContent=label('large');return;}
   const data=await load();if(data.type.split(';')[0]!==kind)throw Error(label('failed'));
   if(text){const pre=document.createElement('pre');pre.textContent=(await data.slice(0,256*1024).text())+(data.size>256*1024?'\n…':'');preview.append(pre);}
   else {if(!url)url=URL.createObjectURL(data);const media=document.createElement(image?'img':playable?(kind.startsWith('audio/')?'audio':'video'):'iframe');media.src=url;if(image){media.alt=file.filename||'';}else if(playable){media.controls=true;media.preload='metadata';media.onerror=()=>{status.textContent=label('unsupported');};}else{media.title=file.filename||label('preview');media.setAttribute('sandbox','');}preview.append(media);}
   b.textContent=label('close');
  });else status.textContent=label('unsupported');
  if(!options.signed){
   // Preserve trusted anchor navigation so Desktop opens its native Save As.
   const link=document.createElement('a');link.href=file.url;link.download=file.filename||'download';link.textContent=label('download');link.title=label('download');link.setAttribute('role','button');actions.append(link);
  }else button('download',async()=>{const data=await load(),link=document.createElement('a'),download=URL.createObjectURL(data);link.href=download;link.download=file.filename||'download';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(download),60000);});
  button('gallery',async b=>{const response=await request(file,'gallery');if(!response.ok)throw Error(label('failed')+' (HTTP '+response.status+')');status.textContent=label('added');b.textContent=label('added');root.dispatchEvent?.(new Event('ai2apps:gallery-changed'));});
 }
 if(files.length&&root.MutationObserver){const observer=new MutationObserver(()=>{if(!node.isConnected){node._artifactDispose?.();observer.disconnect();}});observer.observe(document.documentElement,{childList:true,subtree:true});cleanups.push(()=>observer.disconnect());}
}
root.AI2AppsChatArtifacts={render,reference,label};if(typeof module!=='undefined')module.exports={reference};
})(typeof window==='undefined'?globalThis:window);
