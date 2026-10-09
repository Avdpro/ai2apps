/* Site adapters compose shared BiDi helpers. Pace access; never bypass challenges. */
(() => {
'use strict';
const lt=window.IntelligenceI18n?.text||(s=>s),it=window.IntelligenceI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
function youtube(source){try{return ['youtube.com','www.youtube.com','m.youtube.com','youtu.be'].includes(new URL(source.url).hostname);}catch(_){return false;}}
function weibo(source){try{return ['weibo.com','www.weibo.com','s.weibo.com'].includes(new URL(source.url).hostname);}catch(_){return false;}}
function sourceURL(mode,value,currentURL=''){
 const query=value.trim();
 if(mode==='weibo-account'){
  if(/^[0-9]{5,20}$/.test(query))return 'https://weibo.com/u/'+query;
  let u;try{u=new URL(query);}catch(_){throw Error(lt('请输入微博账号主页链接或数字 UID'));}
  const match=u.pathname.match(/^\/(?:u\/)?([0-9]{5,20})\/?$/);
  if(!['weibo.com','www.weibo.com'].includes(u.hostname)||!match)throw Error(lt('请使用包含数字 UID 的微博账号主页链接'));
  return 'https://weibo.com/u/'+match[1];
 }
 if(mode==='weibo-topic'){
  const tag=query.replace(/^#|#$/g,'').trim();if(!tag||tag.length>98||tag.includes('#'))throw Error(lt('请输入 1–98 个字符的单个话题'));
  return 'https://s.weibo.com/weibo?'+new URLSearchParams({q:'#'+tag+'#'});
 }
 if(mode==='youtube-search'){
  if(!query||query.length>300)throw Error(lt('请输入 1–300 个字符的搜索关键词'));
  const url=new URL('https://www.youtube.com/results');url.searchParams.set('search_query',query);
  try{const old=new URL(currentURL);if(youtube({url:currentURL})&&old.pathname==='/results'&&old.searchParams.has('sp'))url.searchParams.set('sp',old.searchParams.get('sp'));}catch(_){}
  return url.href;
 }
 if(mode==='youtube-topic'){
  const tag=query.replace(/^#/, '');if(!tag||tag.length>100||/[\s/?#]/.test(tag))throw Error(lt('请输入不含空格的单个话题标签'));
  return 'https://www.youtube.com/hashtag/'+encodeURIComponent(tag);
 }
 return value.trim();
}
function supports(source){return source.kind==='social'||youtube(source)||weibo(source);}
function evidence(source,page,requested){return {source_id:source.id,url:page.url,requested_url:requested||page.url,title:page.title,text:page.text.slice(0,20000),
 content_type:page.content_type||'',duration_seconds:page.duration_seconds||null,page_count:page.page_count||null,
 image_url:page.cover_image?.url||'',images:page.images||[],platform:page.platform||'',post_id:page.post_id||'',author:page.author||'',published_at:page.published_at||'',coverage:page.coverage||''};}
async function collectYouTube({source,session,read,api,channelId,seenURLs,onProgress}){
 const direct=new URL(source.url).pathname==='/watch';let candidates=[];
 if(direct)candidates=[{url:source.url,title:source.name,text:''}];
 else{
  const first=await read(session,source.url,{youtube:'feed'});const items=new Map((first.items||[]).map(i=>[i.url,i]));
  for(let scroll=0;scroll<2&&items.size<24;scroll++){
   onProgress(lt('缓慢浏览视频列表 ')+(scroll+1)+'/2');await pause(3500);await session.client.scroll(650);
   await pause(1800);const access=await session.client.handlePageAccess();
   if(['needs_user','restricted'].includes(access.classification)){const e=Error(access.reason||lt('访问受限'));e.outcome=access.classification;if(e.outcome==='needs_user')session.retain=true;throw e;}
   const next=await session.client.extractYouTubeFeed();let added=0;for(const i of next.items||[]){if(!items.has(i.url)){items.set(i.url,i);added++;}}
   if(!added)break;
  }
  candidates=[...items.values()].slice(0,40);
  if(!candidates.length)throw Error(lt('未识别到视频列表；请检查频道地址、登录状态或页面结构'));
 }
 const pending=await api('/channels/'+channelId+'/pending-pages','POST',{candidates,seen_urls:seenURLs});
 const pages=[];let failures=[],outcome='success';
 for(const item of pending.candidates.slice(0,2)){
  onProgress(lt('停顿后读取视频：')+item.title);await pause(5000);
  try{const page=await read(session,item.url,{youtube:'video'});pages.push(evidence(source,page,item.url));}
  catch(error){failures.push(error.message);outcome=error.outcome||'failed';break;}
 }
 const descriptions=pages.filter(p=>p.coverage==='description').length;
 return {pages,skipped:pending.skipped,status:outcome,message:failures.join('；')||it`检查 ${candidates.length} 个视频，跳过 ${pending.skipped} 个已采集视频，读取 ${pages.length} 个；${descriptions} 个仅含标题与简介，${pages.length-descriptions} 个含网页文字稿`};
}
async function collectWeibo({source,session,api,channelId,seenURLs,onProgress}){
 const client=session.client,u=new URL(source.url),topic=u.hostname==='s.weibo.com';
 const guard=async()=>{const access=await client.handlePageAccess();if(['needs_user','restricted'].includes(access.classification)){const e=Error(access.reason||lt('微博需要登录或验证'));e.outcome=access.classification;if(e.outcome==='needs_user')session.retain=true;throw e;}};
 const opened=await client.readPage({url:topic?'https://s.weibo.com/':source.url,phase:'open',new_tab:false,delay_ms:1800});
 if(opened.outcome!=='success')throw Error(opened.reason||lt('微博页面无法打开'));await guard();
 if(topic){onProgress(lt('在微博搜索框输入话题'));try{await client.submitSocialSearch(u.searchParams.get('q'));await guard();}catch(error){session.retain=true;throw error;}}
 const listURL=(await client.pageState()).url;
 if(topic){const actual=new URL(listURL);if(actual.hostname!=='s.weibo.com'||actual.searchParams.get('q')!==u.searchParams.get('q'))throw Error(lt('微博搜索未进入目标话题，已停止'));}
 else{const actual=new URL(listURL);if(!['weibo.com','www.weibo.com'].includes(actual.hostname)||!['/'+u.pathname.split('/').pop(),'/u/'+u.pathname.split('/').pop()].includes(actual.pathname.replace(/\/$/,'')))throw Error(lt('微博未进入目标账号，已停止'));}
 const items=new Map();let pages=[],skipped=0;
 try{
  for(let round=0;round<3;round++){
   await guard();const found=await client.extractWeiboPosts();for(const item of found.items)items.set(item.url,item);
   if(items.size>=12||round===2)break;onProgress(lt('缓慢浏览微博列表'));await pause(3500);await client.scroll(550);await pause(1800);
  }
  if(!items.size)throw Error(lt('未识别到微博正文列表，请检查登录状态或页面结构'));
  const pending=await api('/channels/'+channelId+'/pending-pages','POST',{candidates:[...items.values()].slice(0,30),seen_urls:seenURLs});skipped=pending.skipped;
  const screened=await api('/channels/'+channelId+'/post-candidates/'+source.id,'POST',{candidates:pending.candidates});
  onProgress(lt('帖子初筛：过滤 ')+screened.filtered+lt(' 条'));
  for(const item of screened.candidates.slice(0,2)){
   onProgress(lt('点击微博正文：')+item.title);await pause(5000);
   const origin=await client.clickSocialPost(item.url);
   try{await guard();const page=await client.extractWeiboDetail(item.url);pages.push(evidence(source,page,item.url));}
   finally{if(!session.retain)await client.returnFromSocialPost(origin);}
   await guard();
  }
  return {pages,skipped,status:'success',message:it`检查 ${items.size} 条微博，跳过 ${skipped} 条，初筛过滤 ${screened.filtered} 条，点击读取 ${pages.length} 条正文；经站内点击进入并返回列表，未转录视频`};
 }catch(error){return {pages,skipped,status:error.outcome||'failed',message:error.message};}
 finally{session.context=client.contextId;}
}
window.IntelligenceSocial={youtube,weibo,sourceURL,supports,pause,collectYouTube,collectWeibo};
})();
