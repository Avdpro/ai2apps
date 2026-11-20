/* Drag only durable resource identities; Gallery performs the ownership check. */
(()=>{
 'use strict';
 const encode=encodeURIComponent;
 function reference(url){try{const value=new URL(url,location.origin);if(value.origin!==location.origin)return null;
  let m=value.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/artifacts\/([^/]+)\/(download|preview)$/);
  if(m)return {type:'application/x-ai2apps-session-artifact',value:{sessionId:decodeURIComponent(m[1]),artifactId:decodeURIComponent(m[2]),sourceAppId:'ai2apps.messager'}};
  m=value.pathname.match(/^\/v1\/platform\/sessions\/([^/]+)\/attachments\/([^/]+)\/content$/);
  if(m)return {type:'application/x-ai2apps-session-attachment',value:{sessionId:decodeURIComponent(m[1]),attachmentId:decodeURIComponent(m[2])}};
  m=value.pathname.match(/^\/v1\/platform\/gallery\/assets\/([^/]+)\/content$/);
  if(m)return {type:'application/x-ai2apps-gallery-asset',value:decodeURIComponent(m[1])};
 }catch(_){}return null;}
 function bind(node,url,name){const ref=reference(url);const dataImage=String(url).startsWith('data:image/')&&String(url).length<12*1024*1024;if(!ref&&!dataImage)return;
  node.draggable=true;node.title=name;node.addEventListener('dragstart',event=>{event.stopPropagation();event.dataTransfer.effectAllowed='copy';if(ref)event.dataTransfer.setData(ref.type,typeof ref.value==='string'?ref.value:JSON.stringify({...ref.value,name}));else event.dataTransfer.setData('text/uri-list',url);event.dataTransfer.setData('text/plain',name);});}
 function refreshGallery(){document.querySelector('.messager-gallery-frame')?.contentWindow?.postMessage({type:'ai2apps.gallery.refresh'},location.origin);}
 function label(zh,en){return (document.documentElement?.lang||'en').startsWith('zh')?zh:en;}
 function canonical(url){const ref=reference(url);return ref?.type==='application/x-ai2apps-session-artifact'?'/v1/platform/sessions/'+encode(ref.value.sessionId)+'/artifacts/'+encode(ref.value.artifactId)+'/download':url;}
 function materialPreview(card){
  const host=card.closest('.bot-message-stream')||card.parentElement||card;
  const records=Array.from(host.querySelectorAll('.bot-material-card,.bot-file-card')).map(n=>n._botMaterial).filter(Boolean);
  const selected=records.indexOf(card._botMaterial);
  if(selected<0)return;
  window.dispatchEvent(new CustomEvent('bot-preview-material',{detail:{items:records,index:selected}}));
 }
 function card({url,name,media_type,size_bytes}){
  const card=document.createElement('div');url=canonical(url);
  card._botMaterial={id:url,name,kind:media_type?.split('/')[0]||'file',previewUrl:url,downloadUrl:url,size_bytes};
  if(media_type?.startsWith('image/')){
   card.className='bot-material-card chat-image-card';
   const image=document.createElement('img');image.src=url;image.alt=name||label('图片','Image');image.loading='lazy';image.tabIndex=0;image.setAttribute('role','button');image.setAttribute('aria-label',label('预览图片：','Preview image: ')+(name||''));
   image.onclick=()=>materialPreview(card);image.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();materialPreview(card);}};card.append(image);
   const actions=document.createElement('div');actions.className='chat-image-actions';const notice=document.createElement('p');notice.setAttribute('role','status');notice.className='bot-material-notice';
   const save=document.createElement('button');save.type='button';save.textContent=window.AI2AppsChatImages?.label('save')||label('保存图片','Save image');save.title=save.textContent;
   const gallery=document.createElement('button');gallery.type='button';gallery.textContent=window.AI2AppsChatImages?.label('add_gallery')||label('加入素材库','Add to Gallery');gallery.title=gallery.textContent;
   function action(fn){return async()=>{save.disabled=gallery.disabled=true;notice.textContent='';try{await fn();}catch(error){notice.textContent=error.message;}finally{save.disabled=gallery.disabled=false;}};}
   save.onclick=action(()=>window.AI2AppsChatImages.save(url));
   gallery.onclick=action(async()=>{await window.AI2AppsChatImages.addToGallery(url,null,{sourceAppId:'ai2apps.messager'});notice.textContent=window.AI2AppsChatImages.label('added');refreshGallery();window.dispatchEvent(new Event('ai2apps:gallery-changed'));});
   actions.append(save,gallery);card.append(actions,notice);
  }else{
   card.className='bot-file-card';
   window.AI2AppsChatArtifacts?.render(card,[{url,filename:name,media_type,size_bytes}],{includeImages:true,sourceAppId:'ai2apps.messager',onGalleryAdded:refreshGallery,onPreview:()=>materialPreview(card),manualLifecycle:true});
  }
  bind(card,url,name);return card;
 }
 function attachments(node,items,sid){if(!items?.length)return;const list=document.createElement('div');list.className='bot-message-attachments';for(const item of items)list.append(card({url:'/v1/platform/sessions/'+encode(sid)+'/attachments/'+encode(item.id)+'/content',name:item.filename,media_type:item.media_type,size_bytes:item.size_bytes}));node.append(list);}
 function outputs(node,items){if(!items?.length)return;const list=document.createElement('div');list.className='bot-message-attachments';for(const item of items){const ref=reference(item.url);if(!ref)continue;const key=JSON.stringify(ref);if(Array.from(node.querySelectorAll?.('img[src],audio[src],video[src]')||[]).some(media=>JSON.stringify(reference(media.getAttribute?.('src')||media.src))===key))continue;list.append(card({url:item.url,name:item.filename,media_type:item.media_type,size_bytes:item.size_bytes}));}if(list.children.length)node.append(list);}
 function enhance(node){for(const image of node.querySelectorAll('img[src]')){const url=image.getAttribute('src');if((reference(url)||(String(url).startsWith('data:image/')&&url.length<12*1024*1024))&&!image.closest('.chat-image-card,.chat-artifact-card'))image.replaceWith(card({url,name:image.alt||label('图片','Image'),media_type:'image/png'}));}for(const item of node.querySelectorAll('a[href],img[src],video[src],audio[src]')){const url=item.getAttribute('href')||item.getAttribute('src');bind(item,url,item.getAttribute('alt')||item.textContent||'Bot material');}}
 function createFeed(root,sid,label){let signature='';return {update(items){const shown=(items||[]).slice(0,50).reverse();const key=JSON.stringify(shown.map(i=>[i.id,i.name,i.content_hash]));if(signature===key)return;signature=key;root.replaceChildren();if(!shown.length)return;const title=document.createElement('h3');title.textContent=label('对话素材','Conversation materials');root.append(title);for(const item of shown)root.append(card({url:'/v1/platform/sessions/'+encode(sid)+'/artifacts/'+encode(item.id)+'/download',name:item.name,media_type:item.media_type,size_bytes:item.size_bytes}));}};}
 window.AI2AppsBotMaterials={reference,bind,card,attachments,outputs,enhance,createFeed,dispose(root){root.querySelectorAll('.bot-file-card').forEach(n=>n._artifactDispose?.());}};
})();
