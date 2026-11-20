/* Full-size media is requested only by an explicit open action. */
(root=>{'use strict';if(!root.document)return;const document=root.document;const openViews=new Set();
 async function open({load,alt=''}){
  const dialog=document.createElement('dialog'),close=document.createElement('button'),status=document.createElement('p'),image=document.createElement('img'),control=new AbortController();let resource;
  dialog.className='mobile-original-image';dialog.style.cssText='max-width:95vw;max-height:92dvh;border:1px solid #ddd;border-radius:14px;padding:12px';
  close.type='button';close.textContent=document.documentElement.lang.startsWith('zh')?'关闭':'Close';status.textContent=document.documentElement.lang.startsWith('zh')?'正在加载原图…':'Loading original image…';
  image.alt=alt;image.style.cssText='display:block;max-width:100%;max-height:80dvh;object-fit:contain';close.onclick=()=>dialog.close();
  dialog.onclose=()=>{control.abort();resource?.dispose?.();openViews.delete(dialog);dialog.remove();};dialog.append(close,status);document.body.append(dialog);openViews.add(dialog);dialog.showModal();
  try{resource=await load(control.signal);if(control.signal.aborted||!dialog.isConnected){resource?.dispose?.();return;}image.src=resource.url;image.onload=()=>status.remove();image.onerror=()=>{status.textContent='Image unavailable';};dialog.append(image);}
  catch(error){if(!control.signal.aborted)status.textContent=error.message||'Image unavailable';}
 }
 const closeAll=()=>{for(const dialog of [...openViews])dialog.close();};root.addEventListener?.('pagehide',closeAll);document.addEventListener?.('visibilitychange',()=>{if(document.hidden)closeAll();});
 root.AI2AppsMobileImages={open,closeAll};
})(typeof window!=='undefined'?window:globalThis);

/* Shared durable output cards. Metadata stays out of model content. */
(function(root){'use strict';
const words={zh:{download:'下载',gallery:'加入素材库',added:'已加入素材库',preview:'预览 / 打开',load:'加载试听',video:'加载视频',failed:'素材不可用，请重试',large:'文件较大，请下载后打开',unsupported:'此格式请下载后使用本机应用打开',close:'关闭预览'},en:{download:'Download',gallery:'Add to library',added:'Added to library',preview:'Preview / open',load:'Load audio',video:'Load video',failed:'Asset unavailable. Please retry.',large:'Large file: download to open',unsupported:'Download to open in a compatible app',close:'Close preview'}};
function label(key){return words[(root.document?.documentElement.lang||root.navigator?.language||'en').startsWith('zh')?'zh':'en'][key];}
function reference(url){if(typeof url!=='string')return null;const m=/^\/v1\/platform\/sessions\/([A-Za-z0-9_-]{1,256})\/artifacts\/([A-Za-z0-9_-]{1,256})\/download$/.exec(url);if(m)return {session:m[1],artifact:m[2]};const a=/^\/v1\/platform\/sessions\/([A-Za-z0-9_-]{1,256})\/attachments\/([A-Za-z0-9_-]{1,256})\/content$/.exec(url);return a?{session:a[1],attachment:a[2]}:null;}
function render(node,records,options={}){
 const files=(Array.isArray(records)?records:[]).slice(0,64).filter(f=>reference(f?.url)&&(!options.signed||!reference(f.url).attachment)&&!(options.imageUrls||[]).includes(f.url)&&(options.includeImages||!String(f.media_type).startsWith('image/')));
 const key=JSON.stringify([files,options.runId||'']);if(node._artifactKey===key)return;node._artifactKey=key;node._artifactDispose?.();node.replaceChildren();
 const cleanups=[];node._artifactDispose=()=>{cleanups.splice(0).forEach(f=>f());};
 async function request(file,action,signal){
  if(typeof options.request==='function'){const custom=options.request(file,action,signal);if(custom)return custom;}
  const ref=reference(file.url);const headers=options.apiKey?{Authorization:'Bearer '+options.apiKey}:{};
  if(options.signed){if(!options.runId)throw Error(label('failed'));return root.AI2AppsAgentConnection.signedFetch('/v1/mobile/agent/files/'+encodeURIComponent(options.runId)+'/'+encodeURIComponent(ref.artifact)+(action==='gallery'?'/gallery':action==='thumbnail'?'?preview=mobile':''),action==='gallery'?{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}:{signal});}
  return fetch(action==='gallery'?'/v1/platform/gallery/assets/import-'+(ref.attachment?'attachment':'artifact')+'/'+ref.session+'/'+(ref.attachment||ref.artifact):file.url,{credentials:'same-origin',headers:{...headers,...(action==='gallery'?{'Content-Type':'application/json'}:{})},...(action==='gallery'?{method:'POST',body:JSON.stringify(options.sourceAppId?{sourceAppId:options.sourceAppId}:{})}:{})});
 }
 for(const file of files){
  const card=document.createElement('section');card.className='chat-artifact-card';
  const kind=String(file.media_type||'application/octet-stream').split(';')[0];const title=document.createElement('strong');title.textContent=(kind.startsWith('audio/')?'♫ ':kind.startsWith('video/')?'▶ ':'▤ ')+(file.filename||file.artifact_id);card.append(title);
  const meta=document.createElement('small');meta.textContent=kind+(Number.isFinite(file.size_bytes)?' · '+(file.size_bytes/1024/1024).toFixed(1)+' MB':'');card.append(meta);
  const preview=document.createElement('div');preview.className='chat-artifact-preview';const actions=document.createElement('div');actions.className='chat-artifact-actions';const status=document.createElement('p');status.setAttribute('role','status');card.append(preview,actions,status);node.append(card);
  let url=null,blob=null,closed=false,thumbUrl=null,thumbnailOnly=false;const controller=new AbortController();cleanups.push(()=>{closed=true;controller.abort();preview.querySelectorAll('audio,video').forEach(m=>{m.pause();m.removeAttribute('src');m.load();});if(url)URL.revokeObjectURL(url);if(thumbUrl)URL.revokeObjectURL(thumbUrl);});
  async function load(){if(blob)return blob;const response=await request(file,'read',controller.signal);if(!response.ok)throw Error(label('failed')+' (HTTP '+response.status+')');blob=await response.blob();if(closed)throw Error(label('failed'));return blob;}
  function button(key,fn){const b=document.createElement('button');b.type='button';b.textContent=label(key);b.title=label(key);b.setAttribute('aria-label',label(key));b.onclick=async()=>{b.disabled=true;status.textContent='';try{await fn(b);}catch(e){status.textContent=e.message||label('failed');}finally{b.disabled=false;}};actions.append(b);return b;}
  const image=/^image\/(png|jpeg|webp|avif|gif)$/.test(kind),playable=/^(audio|video)\//.test(kind),pdf=kind==='application/pdf',text=/^text\/(plain|csv|markdown)$/.test(kind)||['application/json','application/xml'].includes(kind);
  let previewButton;
  if(image||playable||pdf||text)previewButton=button(playable?(kind.startsWith('audio/')?'load':'video'):'preview',async b=>{
   if(image&&options.mobile&&options.openImage){await options.openImage(file);return;}
   if(options.onPreview){options.onPreview(file);return;}
   if(preview.childNodes.length&&!thumbnailOnly){preview.querySelectorAll('audio,video').forEach(m=>m.pause());preview.replaceChildren();b.textContent=label(playable?(kind.startsWith('audio/')?'load':'video'):'preview');return;}
   if(file.size_bytes>100*1024*1024){status.textContent=label('large');return;}
   const data=await load();if(thumbnailOnly){thumbnailOnly=false;preview.replaceChildren();}if(data.type.split(';')[0]!==kind)throw Error(label('failed'));
   if(text){const pre=document.createElement('pre');pre.textContent=(await data.slice(0,256*1024).text())+(data.size>256*1024?'\n…':'');preview.append(pre);}
   else {if(!url)url=URL.createObjectURL(data);const media=document.createElement(image?'img':playable?(kind.startsWith('audio/')?'audio':'video'):'iframe');media.src=url;if(image){media.alt=file.filename||'';}else if(playable){media.controls=true;media.preload='metadata';media.onerror=()=>{status.textContent=label('unsupported');};}else{media.title=file.filename||label('preview');media.setAttribute('sandbox','');}preview.append(media);}
   b.textContent=label('close');
  });else status.textContent=label('unsupported');
  if(image&&options.mobile&&(options.signed||options.request)){
   const thumbnail=document.createElement('img');thumbnail.alt=file.filename||'';thumbnail.loading='lazy';thumbnail.style.cursor='zoom-in';thumbnail.setAttribute('role','button');thumbnail.tabIndex=0;
   thumbnail.onclick=()=>previewButton.click();thumbnail.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();previewButton.click();}};
   preview.append(thumbnail);preview.style.minHeight='48px';thumbnailOnly=true;
   const fetchThumbnail=async()=>{try{const response=await request(file,'thumbnail',controller.signal);if(!response.ok)throw Error(label('failed'));const data=await response.blob();if(!/^image\/(jpeg|png|webp|avif|gif)$/.test(data.type))throw Error(label('failed'));if(closed)return;thumbUrl=URL.createObjectURL(data);thumbnail.src=thumbUrl;thumbnail.onerror=()=>{thumbnail.remove();status.textContent=label('failed');};thumbnail.onload=()=>{preview.style.minHeight='';};}catch(error){if(!closed){thumbnail.remove();status.textContent=label('failed');}}};
   if(root.IntersectionObserver){const observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){observer.disconnect();void fetchThumbnail();}},{rootMargin:'200px'});observer.observe(card);cleanups.push(()=>observer.disconnect());}else void fetchThumbnail();
  }
  if(!options.signed&&!options.request){
   // Preserve trusted anchor navigation so Desktop opens its native Save As.
   const link=document.createElement('a');link.href=file.url;link.download=file.filename||'download';link.textContent=label('download');link.title=label('download');link.setAttribute('role','button');actions.append(link);
  }else button('download',async()=>{const data=await load(),link=document.createElement('a'),download=URL.createObjectURL(data);link.href=download;link.download=file.filename||'download';document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(download),60000);});
  button('gallery',async b=>{const response=await request(file,'gallery');if(!response.ok)throw Error(label('failed')+' (HTTP '+response.status+')');status.textContent=label('added');b.textContent=label('added');root.dispatchEvent?.(new Event('ai2apps:gallery-changed'));options.onGalleryAdded?.();});
 }
 if(files.length&&!options.manualLifecycle&&root.MutationObserver){const observer=new MutationObserver(()=>{if(!node.isConnected){node._artifactDispose?.();observer.disconnect();}});observer.observe(document.documentElement,{childList:true,subtree:true});cleanups.push(()=>observer.disconnect());}
}
root.AI2AppsChatArtifacts={render,reference,label};if(typeof module!=='undefined')module.exports={reference};
})(typeof window==='undefined'?globalThis:window);
