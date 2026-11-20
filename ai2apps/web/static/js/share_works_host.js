/* Owner adapter, authenticated by the shared mount channel before every call. */
(()=>{'use strict';
const bridges=window.AI2AppsMiniAppBridges ||= new Map();
bridges.set('ai2apps.share-works',async(request,{base,signal})=>{
 const root=base+'/share-works';let path,method='GET',body,headers;
 const key=value=>{if(!/^[A-Za-z0-9_-]{16,80}$/.test(value||''))throw Error('Invalid reference');return value;};
 switch(request.action){
 case 'social-open':{
  const url='https://creator.rednote.com/publish/publish';
  const mobile=window.AI2APPS_MOBILE_SURFACE===true||!!document.querySelector('.aib-mobile');
  if(!mobile){
   const result=await fetch('/v1/platform/client/browser-profiles/default/launch',{
    method:'POST',credentials:'same-origin',signal,headers:{'Content-Type':'application/json'},
    body:JSON.stringify({initial_url:url})});
   if(!result.ok)throw Error('rednote_browser_unavailable');
   return {opened_on:'desktop_profile'};
  }
  const dialog=document.createElement('dialog');
  const zh=(document.documentElement.lang||'').startsWith('zh');
  const link=document.createElement('a');
  link.href=url;link.target='_blank';link.rel='noopener noreferrer';
  link.textContent=zh?'打开 Rednote 创作中心':'Open Rednote Creator Center';
  const close=document.createElement('button');close.textContent=zh?'关闭':'Close';
  close.onclick=()=>dialog.close();
  dialog.addEventListener('close',()=>dialog.remove(),{once:true});
  dialog.append(link,' ',close);document.body.append(dialog);dialog.showModal();
  return {};
 }
 case 'social-prepare':{
  path='/social/drafts';method='POST';body=new FormData();
  for(const k of ['destination','title','body'])body.append(k,String(request[k]||''));
  const mobile=window.AI2APPS_MOBILE_SURFACE===true||!!document.querySelector('.aib-mobile');
  const files=request.files||[];
  const limit=(mobile?19:128)*1024*1024;
  if(!Array.isArray(files)||files.length>18||
     files.some(file=>!(file instanceof File))||
     files.reduce((total,file)=>total+file.size,0)>limit)
   throw Error(mobile?'mobile_artifact_size_limit':'artifact_size_limit');
  for(const file of files)body.append('files',file,file.name);
  break;
 }
 case 'social-history':path='/social/drafts';break;
 case 'social-publish':path='/social/drafts/'+key(request.draft_id)+'/publish';method='POST';
  body={digest:request.digest,confirmed:request.confirmed===true};break;
 case 'social-download':{
  if(!Number.isInteger(request.index)||request.index<0||request.index>=18)throw Error('Invalid media index');
  const url=root+'/social/drafts/'+key(request.draft_id)+'/media/'+request.index;
  const a=document.createElement('a');a.href=url;a.download='';a.click();
  return {};
 }
 case 'open':{
  if(!['share','space'].includes(request.target))throw Error('Invalid link target');
  const response=await fetch(root+'/publications/'+key(request.request_id),{credentials:'same-origin',signal,cache:'no-store'});
  if(!response.ok)throw Error('share_operation_failed');
  const record=await response.json();let url;
  if(request.target==='share'){
   url=new URL(record.result?.url);
   if(url.protocol!=='https:'||url.username||url.password||url.port)throw Error('Invalid public link');
   if(record.provider==='ms'){
    if(!/^[-\w.]+\/[-\w.]+$/.test(record.repo||'')||!(/^[0-9a-f]{32}$/).test(record.snapshot_id||''))throw Error('Invalid share');
    const expected='https://modelscope.cn/studios/'+record.repo+'?mode=full&app_path='+encodeURIComponent('/shares/'+record.snapshot_id+'/index.html');
    if(url.href!==expected)throw Error('Invalid public link');
   }else if(record.provider!=='hf'||!url.hostname.endsWith('.hf.space'))throw Error('Invalid public link');
  }else{
   if(!['hf','ms'].includes(record.provider)||!record.repo||!/^[-\w.]+\/[-\w.]+$/.test(record.repo))throw Error('Invalid space');
   url=new URL((record.provider==='hf'?'https://huggingface.co/spaces/':'https://modelscope.cn/studios/')+record.repo.split('/').map(encodeURIComponent).join('/'));
  }
  // Package frames cannot open popups. A host-owned, user-activated link
  // escapes the frame sandbox without granting the Package popup permission.
  const zh=(document.documentElement.lang||'').startsWith('zh');
  document.querySelector('dialog[data-share-link]')?.close();
  const dialog=document.createElement('dialog');dialog.dataset.shareLink='';dialog.style.cssText='box-sizing:border-box;width:calc(100vw - 40px);max-width:440px;border:1px solid #e7e5e4;border-radius:18px;padding:24px;color:#292524;background:white';
  const heading=document.createElement('h2');heading.textContent=zh?'打开分享链接':'Open share link';heading.style.cssText='font:600 20px system-ui;margin:0 0 12px';
  const detail=document.createElement('p');detail.textContent=url.hostname;detail.style.cssText='font:14px system-ui;color:#78716c;overflow-wrap:anywhere;margin:0 0 20px';
  const link=document.createElement('a');link.href=url.href;link.target='_blank';link.rel='noopener noreferrer';link.textContent=request.target==='space'?(zh?'打开管理空间':'Manage space'):(zh?'在浏览器打开':'Open in browser');link.style.cssText='display:block;text-align:center;text-decoration:none;background:#44403c;color:white;border-radius:10px;padding:13px 16px;font:16px system-ui';
  const close=document.createElement('button');close.textContent=zh?'关闭':'Close';close.style.cssText='display:block;margin:12px auto 0;border:0;background:transparent;color:#78716c;padding:10px;font:15px system-ui';close.onclick=()=>dialog.close();dialog.addEventListener('close',()=>dialog.remove(),{once:true});dialog.append(heading,detail,link,close);document.body.append(dialog);dialog.showModal();
  return {opened_on:'current_device',confirmation:true};
 }
 case 'check':path='/check';method='POST';body={provider:request.provider,repo:request.repo};break;
 case 'prepare':{
  path='/prepare';method='POST';body=new FormData();
  for(const k of ['provider','repo','application_url','title','export_id'])body.append(k,String(request[k]||''));
  if(request.file){const mobile=window.AI2APPS_MOBILE_SURFACE===true||(typeof document!=='undefined'&&!!document.querySelector('.aib-mobile'));if(mobile&&request.file.size>19*1024*1024)throw Error('mobile_artifact_size_limit');if(!(request.file instanceof Blob)||request.file.size>128*1024*1024)throw Error('artifact_size_limit');body.append('file',request.file,request.filename||'site.html');}break;}
 case 'preview':path='/snapshots/'+key(request.snapshot_id)+'/preview';break;
 case 'publish':path='/publish';method='POST';body={snapshot_id:key(request.snapshot_id),request_id:key(request.request_id),confirmed:request.confirmed===true};break;
 case 'preferences':path='/preferences';break;
 case 'history':path='/history';break;
 case 'status':path='/publications/'+key(request.request_id);break;
 case 'verify':case 'cancel':path='/publications/'+key(request.request_id)+'/'+request.action;method='POST';break;
 default:throw Error('Unsupported owner operation');
 }
 if(body && !(body instanceof FormData)){headers={'Content-Type':'application/json'};body=JSON.stringify(body);}
 const response=await fetch(root+path,{method,headers,body,credentials:'same-origin',signal,cache:'no-store'});
 const value=await response.json();if(!response.ok)throw Error(typeof value.detail==='string'?value.detail:'share_operation_failed');return value;
});})();
