(() => {
 'use strict';
 // One interaction controller. Hosts supply authorized asset resolution, not URLs.
 function bind(root,options={}){
  if(root.assetSlot)return root.assetSlot;
  const kind=options.kind||'image';
  const input=root.querySelector('input[type=file]'),preview=kind==='video'?root.querySelector('video'):kind==='image'?root.querySelector('img'):null;
  const empty=root.querySelector('[data-slot-empty]')||root.querySelector('span'),filledNode=root.querySelector('[data-slot-filled]'),clear=root.querySelector('button');
  const filled=filledNode===empty?null:filledNode;
  if(!['image','video','audio'].includes(kind)||!input||!clear||(kind!=='audio'&&!preview))throw new Error('Asset Slot requires input, preview and clear controls');
  root.dataset.assetSlot=kind;root.tabIndex=0;root.setAttribute('role','button');
  let disabled=false;
  const locked=()=>disabled||!!options.disabled?.();
  // Read DataTransfer inside its event; browsers revoke access after dispatch.
  const invoke=fn=>{try{return Promise.resolve(fn()).catch(error=>options.error?.(error));}catch(error){options.error?.(error);}};
  const selectFiles=files=>options.selectFiles?options.selectFiles(files):options.select?.(files[0]);
  const choose=event=>{event.preventDefault();if(locked())return;if(options.choose)invoke(async()=>{const file=await options.choose(input);if(file&&!locked())await selectFiles([file]);});else input.click();};
  root.addEventListener('click',event=>{if(event.target===input||clear.contains(event.target))return;choose(event);});
  root.addEventListener('keydown',event=>{if(event.target===root&&['Enter',' '].includes(event.key))choose(event);});
  input.addEventListener('change',()=>{const files=Array.from(input.files||[]);input.value='';if(files.length&&!locked())invoke(()=>selectFiles(files));});
  clear.addEventListener('click',event=>{event.preventDefault();event.stopPropagation();if(!locked())invoke(()=>options.clear());});
  for(const type of ['dragenter','dragover'])root.addEventListener(type,event=>{event.preventDefault();event.stopPropagation();if(!locked()){root.classList.add('asset-slot-target');if(event.dataTransfer)event.dataTransfer.dropEffect='copy';}});
  root.addEventListener('dragleave',event=>{if(!root.contains(event.relatedTarget))root.classList.remove('asset-slot-target');});
  root.addEventListener('drop',event=>{event.preventDefault();event.stopPropagation();root.classList.remove('asset-slot-target');if(locked())return;const files=Array.from(event.dataTransfer?.files||[]);invoke(()=>files.length?selectFiles(files):options.drop?.(event));});
  const api={update(value={}){
   if('disabled'in value)disabled=!!value.disabled;
   root.setAttribute('aria-disabled',String(locked()));input.disabled=clear.disabled=locked();
   if('preview'in value||'name'in value||'count'in value){const src=value.preview||'',has=!!(src||value.name||value.count);if(preview){if(src)preview.src=src;else preview.removeAttribute('src');preview.hidden=!src;}clear.hidden=!has;if(empty)empty.hidden=has;if(filled){filled.hidden=!has;filled.textContent=has?(value.name||value.label||'')+(value.count>1?' · '+value.count:''):'';}root.classList.toggle('asset-slot-filled',has);}
   if(value.label){root.setAttribute('aria-label',value.label);input.setAttribute('aria-label',value.label);if(preview?.tagName==='IMG')preview.alt=value.label;}
   if(value.clearLabel)clear.setAttribute('aria-label',value.clearLabel);
  }};
  root.assetSlot=api;api.update();return api;
 }
 window.AI2AppsAssetSlot={bind};
})();
