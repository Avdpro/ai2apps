(() => {
'use strict';
const lt=window.IntelligenceI18n?.text||(s=>s),it=window.IntelligenceI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
const $ = s => document.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const when = s => s ? new Date(s).toLocaleString(window.IntelligenceI18n?.locale||'zh-CN',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : lt('尚未更新');
const labels = {running:lt('正在更新'),completed:lt('更新完成'),partial:lt('部分完成'),failed:lt('更新失败'),interrupted:lt('连接中断'),cancelled:lt('已停止'),success:lt('成功'),needs_user:lt('需要协助'),restricted:lt('访问受限'),deferred:lt('等待下次检查')};
let state = {channels:[],sources:[],articles:[],runs:[]}, channelId = null, selectedId = null, tab = 'articles', sectionId = '', busy = false, editing = null, editingSource = null, profiles = [{key:"default",name:"Default"}], noticeTimer;
let readerMode='chat', mobilePanel=false;
const conversations=new Map();
const conversationState=id=>{if(!conversations.has(id))conversations.set(id,{turns:[],draft:'',loading:false,loaded:false,sending:false,error:'',requestId:null});return conversations.get(id);};
const channel = () => state.channels.find(c => c.id === channelId);
const inChannel = table => state[table].filter(row => row.channel_id === channelId);
const icons = () => window.lucide?.createIcons();
async function api(path='', method='GET', body){
 const response = await fetch('/v1/platform/intelligence'+path, {method,credentials:'same-origin',headers:{'Content-Type':'application/json','X-Intelligence-Language':window.IntelligenceI18n?.locale||'en'},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const data = await response.json();
 if (!response.ok) throw Error(lt(typeof data.detail==='string'?data.detail:data.error?.message||it`请求失败 (${response.status})`));
 return data;
}
function notice(message){$('#intel-notice').textContent=message;$('#intel-notice').hidden=false;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('#intel-notice').hidden=true,12000);}
const safe = fn => async (...args) => {try{return await fn(...args);}catch(error){notice(error.message);}};
function link(url){try{const u=new URL(url,String(url).startsWith('/v1/platform/intelligence/imports/')?location.origin:undefined);return ['https:','http:'].includes(u.protocol)?esc(u.href):'#';}catch(_){return '#';}}
window.IntelligenceEntities.init({api,openOriginal:openEntityOriginal,detailRoot:()=>$('#intel-entity-reader'),showEntity:()=>{readerMode='entity';mobilePanel=true;renderChannelChat();},entityAvailable:available=>{$('#show-entity-detail').hidden=!available;if(!available&&readerMode==='entity')readerMode='chat';renderChannelChat();},viewImage:(id,url)=>{const article=state.articles.find(a=>a.id===id);if(!article)return;const images=articleImages(article),index=images.findIndex(i=>i.url===url);if(index<0)return;imagePreview={article,images,index};renderImagePreview();$('#article-image-dialog').showModal();},state:()=>state,tab:()=>tab,setTab:value=>{tab=value;document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-selected',String(b.dataset.tab===tab));});},notice,readArticle:async id=>{const a=state.articles.find(a=>a.id===id);if(a)channelId=a.channel_id;await readArticle(id);}});
async function refresh(){state=await api();if(!channel())channelId=state.channels[0]?.id||null;if(!state.articles.some(a=>a.id===selectedId))selectedId=null;render();}
function render(){
 $('#channel-list').innerHTML=state.channels.map(c=>it`<button data-channel="${c.id}" class="${c.id===channelId?'active':''}"><span class="intel-channel-symbol">◉</span><span class="channel-label">${esc(c.name)}</span><span class="count">${state.articles.filter(a=>a.channel_id===c.id&&!a.read).length||''}</span></button>`).join('');
 const c=channel();$('#channel-controls').hidden=!c;$('#channel-head-actions').hidden=!c;$('#channel-title').textContent=c?.name||lt('捕捉你关心的变化');$('#channel-description').textContent=c?.interests||lt('从一个兴趣开始，建立你的第一条情报频道。');
 $('#collect').disabled=busy||!inChannel('sources').some(s=>s.enabled)||inChannel('runs').some(r=>r.status==='running');$('#recommend').disabled=busy;$('#edit-channel').disabled=busy;
 $('#article-count').textContent=inChannel('articles').length||'';$('#source-count').textContent=inChannel('sources').length||'';
 document.querySelectorAll('[data-tab]').forEach(b=>{b.classList.toggle('active',b.dataset.tab===tab);b.setAttribute('aria-selected',String(b.dataset.tab===tab));});
 $('#search-articles').hidden=tab!=='articles';$('#article-filter').hidden=tab!=='articles';$('#article-type-filter').hidden=tab!=='articles';$('#add-source').hidden=tab!=='sources';$('#recommend').hidden=tab!=='sources';$('#write-channel-draft').hidden=tab!=='drafts';
 const sync=c?.knowledge_sync||{};$('#knowledge-sync-status').innerHTML=sync.failed?it`知识库同步失败 ${sync.failed} 项 <button data-action="sync-knowledge">重试同步</button>${sync.errors?.length?'<p>'+sync.errors.map(esc).join('；')+'</p>':''}`:'';
 renderSections();renderContent();renderReader();icons();
}
let sectionDrag=null,sectionOrderSaving=false;
const sectionFilters=$('#section-filters');
sectionFilters.addEventListener('dragstart',event=>{
 const button=event.target.closest('[data-section][draggable="true"]');
 if(!button||sectionOrderSaving){event.preventDefault();return;}
 sectionDrag={id:button.dataset.section,channelId};
 event.dataTransfer.effectAllowed='move';event.dataTransfer.setData('text/plain',button.dataset.section);
 button.classList.add('dragging');
});
function clearSectionDrag(){sectionDrag=null;sectionFilters.querySelectorAll('.dragging,.drop-before,.drop-after').forEach(b=>b.classList.remove('dragging','drop-before','drop-after'));}
sectionFilters.addEventListener('dragend',clearSectionDrag);
sectionFilters.addEventListener('dragover',event=>{
 const button=event.target.closest('[data-section][draggable="true"]');
 if(!button||!sectionDrag||sectionDrag.channelId!==channelId)return;
 event.preventDefault();event.dataTransfer.dropEffect='move';
 sectionFilters.querySelectorAll('.drop-before,.drop-after').forEach(b=>b.classList.remove('drop-before','drop-after'));
 const rect=button.getBoundingClientRect();button.classList.add(event.clientX<rect.left+rect.width/2?'drop-before':'drop-after');
});
sectionFilters.addEventListener('drop',async event=>{
 const button=event.target.closest('[data-section][draggable="true"]'),drag=sectionDrag;
 if(!button||!drag||drag.channelId!==channelId)return;
 event.preventDefault();const target=button.dataset.section,rect=button.getBoundingClientRect(),after=event.clientX>=rect.left+rect.width/2;
 clearSectionDrag();if(target===drag.id)return;
 const c=channel(),ids=c.sections.map(s=>s.id).filter(id=>id!==drag.id);
 ids.splice(ids.indexOf(target)+(after?1:0),0,drag.id);sectionOrderSaving=true;
 try{const saved=await api('/channels/'+drag.channelId+'/sections/order','PUT',{ids});const current=state.channels.find(c=>c.id===drag.channelId);if(current)current.sections=saved.sections;if(channelId===drag.channelId)renderSections();}
 catch(error){notice(error.message||lt('排序保存失败，请重试'));}
 finally{sectionOrderSaving=false;}
});
function sectionName(article){return channel()?.sections?.find(s=>s.id===article.section_id)?.name||lt('待归类');}
function renderSections(){
 const root=$('#section-filters'),sections=channel()?.sections||[];
 root.hidden=tab!=='articles'||!channel();
 if(!sections.some(s=>s.id===sectionId)&&sectionId!=='unassigned')sectionId='';
 if(!sections.length){sectionId='';root.innerHTML=it`<span class="intel-muted">为频道整理专属栏目</span><button data-action="create-sections" ${busy?'disabled':''}>✦ AI 创建栏目</button>`;return;}
 const articles=inChannel('articles'),unassigned=articles.filter(a=>!sections.some(s=>s.id===a.section_id)).length;
 root.innerHTML=[{id:'',name:lt('全部'),description:lt('全部情报')},...sections,...(unassigned?[{id:'unassigned',name:lt('待归类'),description:lt('尚未归入栏目的历史文章')}]:[])].map(s=>it`<button data-section="${esc(s.id)}" ${s.id&&s.id!=='unassigned'?'draggable="true"':''} class="${sectionId===s.id?'active':''}" aria-pressed="${sectionId===s.id}" title="${esc(s.description)}">${esc(s.name)} <span>${s.id==='unassigned'?unassigned:s.id?articles.filter(a=>a.section_id===s.id).length:articles.length}</span></button>`).join('')+(sectionId?it`<button data-write="section" data-scope-id="${esc(sectionId)}">为此栏目撰写稿件</button>`:'');
}
async function createSections(){
 if(busy||!channel())return;const target=channelId;busy=true;render();notice(lt('AI 正在规划栏目，并整理已有情报…'));
 try{await api('/channels/'+target+'/sections','POST');notice(lt('栏目已创建，已有情报已归类'));}
 finally{busy=false;await refresh();}
}
function empty(icon,title,text,actions=''){return it`<div class="intel-empty"><i data-lucide="${icon}"></i><h2>${esc(title)}</h2><p>${esc(text)}</p>${actions}</div>`;}
const failedCovers=new Set();
function coverHTML(a,detail=false){
 const url=articleImages(a)[0]?.url;if(!url||failedCovers.has(url)||link(url)==='#')return '';
 return it`<figure class="intel-cover ${detail?'intel-cover-detail':''}"><img src="${esc(window.IntelligenceCards.imageURL(a,url))}" alt="${esc(a.title)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">${detail?it`<figcaption><a href="${link(articleImages(a)[0]?.source_url)}" target="_blank" rel="noopener noreferrer">图片来自原文 ↗</a></figcaption>`:''}</figure>`;
}
document.addEventListener('error',event=>{const img=event.target;if(img.matches?.('.intel-cover img,.intel-story img')){failedCovers.add(img.src);const figure=img.closest('figure');if(figure)figure.hidden=true;else img.hidden=true;}},true);
async function extractArticleCover(){
 if(busy||!selectedId)return;const article=state.articles.find(a=>a.id===selectedId),id=selectedId;
 const reference=article.sources.find(r=>state.sources.some(s=>s.channel_id===article.channel_id&&(s.id===r.source_id||s.name===r.source_name)));
 if(!reference)throw Error(lt('原信息源已移除，无法确定采集 Profile。'));
 const source=state.sources.find(s=>s.channel_id===article.channel_id&&(s.id===reference.source_id||s.name===reference.source_name));
 let session;busy=true;render();notice(lt('正在从原文提取标题图…'));
 try{session=await browserSession(source.profile_key||'default');const page=await read(session,reference.url);
  if(!page.cover_image?.url)throw Error(lt('未找到合适的标题图，保留文字布局。'));
  failedCovers.delete(page.cover_image.url);
  await api('/articles/'+id+'/cover','PUT',{source_url:reference.url,image_url:page.cover_image.url});notice(lt('标题图已更新'));
 }finally{await closeBrowser(session);busy=false;await refresh();}
}
const topicRequests=new Set();
async function updateTopics(id=channelId){
 if(!id||topicRequests.has(id))return;topicRequests.add(id);if(channelId===id)renderContent();
 try{await api('/channels/'+id+'/topics','POST');await refresh();}
 catch(error){notice(lt('热点整理失败：')+error.message);}
 finally{topicRequests.delete(id);if(channelId===id){renderContent();icons();}}
}
function renderTopics(root){
 const c=channel(),data=c.hot_topics,items=data?.items||[],articles=inChannel('articles'),loading=topicRequests.has(c.id);
 const latest=articles.reduce((value,a)=>a.updated_at>value?a.updated_at:value,'');
 const stale=data&&latest>data.generated_at;
 root.innerHTML=it`<div class="intel-topics-head"><div><h2>频道热点</h2><p class="intel-help">近 7 天更新的最多 60 篇情报 · 按具体产品、事件聚合 · 至少 2 篇相关文章</p><p class="intel-help">${data?lt('整理于 ')+when(data.generated_at)+lt(' · 分析 ')+data.article_count+lt(' 篇'):''}${stale?lt(' · 有新文章，待更新热点'):''}</p></div><button data-action="update-topics" ${loading?'disabled':''}>${loading?lt('正在整理…'):lt('更新热点')}</button></div>`+
 (items.length?items.map(t=>{const related=t.article_ids.map(id=>articles.find(a=>a.id===id)).filter(Boolean);
 const cover=related.find(a=>a.cover_image);
 return it`<section class="intel-topic">${cover?coverHTML(cover):''}<div class="intel-story-meta">${related.length} 篇相关文章 · 最近进展 ${when(t.updated_at)}</div><h2>${esc(t.title)}</h2><button data-write="topic" data-scope-id="${esc(t.id)}">撰写稿件</button><p class="intel-topic-summary">${esc(t.summary)}</p><div class="intel-topic-articles">${related.map(a=>it`<button data-article="${esc(a.id)}"><span>${esc(a.title)}</span><small>${when(a.updated_at)}</small></button>`).join('')}</div></section>`;}).join(''):
 empty('flame',loading?lt('正在寻找文章之间的关联'):data?lt('暂未形成热点'):lt('把近期情报串成话题'),loading?lt('AI 正在归纳具体事件及相关报道。'):lt('点击更新热点；同一表款、AI 模型或赛事有多篇报道时，会归在一起。')));
}
function renderContent(){
 const root=$('#intel-content');root.onclick=null;root.onsubmit=null;
 if(!['entities','opportunities'].includes(tab)){$('#show-entity-detail').hidden=true;$('#intel-entity-reader').hidden=true;if(readerMode==='entity')readerMode='chat';}
 if(!channel()){root.innerHTML=empty('radar',lt('你的第一条情报频道'),lt('告诉 AI 你关心什么。让分散的网站和话题，汇聚成一份可以追溯来源的情报。'),lt('<div class="intel-starters"><button data-starter="腕表">⌚ 腕表</button><button data-starter="人工智能">✦ 人工智能</button><button data-starter="摄影">◎ 摄影</button></div><p style="margin-top:25px"><button data-action="create" class="intel-primary">＋ 自定义频道</button></p>'));return;}
 if(tab==='entities'||tab==='opportunities'){window.IntelligenceEntities.render(root,tab,channelId);return;}
 if(tab==='articles'){
  const q=$('#search-articles').value.trim().toLowerCase(),filter=$('#article-filter').value,typeFilter=$('#article-type-filter')?.value||'all';
  const articles=inChannel('articles').filter(a=>(typeFilter==='all'||window.IntelligenceCards.describe(a).formats.includes(typeFilter))&&(!sectionId||(sectionId==='unassigned'?!channel().sections?.some(s=>s.id===a.section_id):a.section_id===sectionId))&&(!q||(a.title+' '+a.summary+' '+a.body).toLowerCase().includes(q))&&(filter!=='unread'||!a.read)&&(filter!=='more'||a.feedback==='more')).sort((a,b)=>b.updated_at.localeCompare(a.updated_at));
  root.innerHTML=articles.map(a=>window.IntelligenceCards.render(a,{selected:a.id===selectedId,section:sectionName(a),updated:when(a.updated_at),failedImages:failedCovers})).join('')||empty('newspaper',q||filter!=='all'||typeFilter!=='all'||sectionId?lt('没有匹配的文章'):lt('等待第一份情报'),inChannel('sources').length?lt('点击“立即更新”，读取信息源并整理值得关注的内容。没有新变化时，不会生成重复文章。'):lt('先添加信息源，或让 AI 根据你的兴趣推荐网站。'),lt('<button data-action="sources">管理信息源 →</button>'));
 }else if(tab==='drafts'){
  renderDraftList(root);
 }else if(tab==='topics'){
  renderTopics(root);
 }else if(tab==='sources'){
  root.innerHTML=inChannel('sources').map(s=>it`<section class="intel-source"><header><h3>${esc(s.name)}</h3><span class="intel-status">${s.enabled?lt('监测中'):lt('已暂停')}</span></header><a href="${link(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)} ↗</a><footer><span>${s.kind==='social'?lt('社交账号 / 话题'):lt('网站 / 栏目')} · ${esc(profiles.find(p=>p.key===(s.profile_key||'default'))?.name||lt('Profile 已删除'))}</span>${s.kind==='social'?it`<span>间隔 ${s.social_interval_hours||6} 小时${s.social_next_at?lt(' · 下次 ')+when(s.social_next_at*1000):''}</span>${s.social_paused?it`<button data-resume-social="${s.id}">已处理验证，恢复采集</button>`:''}`:''}<button data-edit-source="${s.id}" ${busy?'disabled':''}>设置</button><button data-toggle-source="${s.id}" ${busy?'disabled':''}>${s.enabled?lt('暂停'):lt('启用')}</button><button data-delete-source="${s.id}" ${busy?'disabled':''}>移除</button></footer></section>`).join('')||empty('radio',lt('为频道接入信息源'),lt('添加网站栏目、社交账号或话题页。AI 推荐会读取真实搜索结果，供你选择。'),lt('<button data-action="recommend">✦ AI 推荐信息源</button>'));
 }else{
  root.innerHTML=lt('<p><button data-show-filtered>查看已过滤帖子</button></p>')+ (inChannel('runs').map(r=>it`<section class="intel-run"><header><h3>${r.scheduled?lt('定时更新'):lt('手动更新')}</h3><span class="intel-status ${['failed','partial','interrupted'].includes(r.status)?'error':''}">${labels[r.status]||esc(r.status)}</span></header><p>${esc(r.status==='interrupted'?lt('上次执行连接中断，可以重新更新。'):r.message)}</p><time>${when(r.started_at)}</time>${r.logs?.length?it`<details><summary>查看 ${r.logs.length} 个信息源的结果</summary>${r.logs.map(l=>it`<p>${esc(l.name)} · ${labels[l.status]} · ${l.pages} 篇<br>${esc(l.message)}</p>`).join('')}</details>`:''}</section>`).join('')||empty('history',lt('每次更新，都有记录'),lt('这里会显示采集结果、生成数量，以及需要登录或人工协助的信息源。')));
 }
}
function renderReader(){
 renderChannelChat();
 const a=state.articles.find(a=>a.id===selectedId&&a.channel_id===channelId);const root=$('#intel-article-reader');
 if(!a){root.classList.remove('open');root.innerHTML=lt('<div class="intel-reader-empty"><span><i data-lucide="book-open-text"></i></span><h2>每一条情报，都有来处</h2><p>选一篇文章，查看摘要、变化与原始来源。</p><div class="intel-reader-principles"><p>01　只关注与你有关的信息</p><p>02　合并重复报道，保留新进展</p><p>03　阅读文章，也能追溯原文</p></div></div>');return;}
 root.classList.add('open');root.innerHTML=it`<div class="intel-article-head"><span>${esc(sectionName(a))} · ${a.image_ai_summary?lt('AI 图片总结'):a.manual_import?lt('手动收录'):lt('AI 整理')} · ${when(a.updated_at)}</span><button data-write="article" data-scope-id="${esc(a.id)}">撰写稿件</button><button data-action="close-reader" class="intel-icon" aria-label="关闭文章">×</button></div>${coverHTML(a,true)}<h1>${esc(a.title)}</h1><div class="intel-lead">${esc(a.summary)}</div><div class="intel-body">${esc(a.body)}</div><section class="intel-citations"><h3>原始来源 · ${a.sources.length}</h3>${a.sources.map((s,i)=>it`<a href="${link(s.url)}" target="_blank" rel="noopener noreferrer">[${i+1}] ${esc(s.title||s.source_name)} ↗<small>${esc(s.source_name)} · 采集于 ${when(s.retrieved_at)}${s.coverage?' · '+(s.coverage==='transcript'?lt('网页文字稿'):lt('仅标题与简介')):''}</small></a>`).join('')}</section>${articleImagesHTML(a)}<div class="intel-feedback"><button data-action="extract-images" ${busy?'disabled':''}>提取文章图片</button><button data-action="extract-cover" ${busy?'disabled':''}>${a.cover_image?lt('重新提取标题图'):lt('提取标题图')}</button><button data-feedback="more" class="${a.feedback==='more'?'active':''}" aria-pressed="${a.feedback==='more'}">👍 顶</button><button data-feedback="less" class="${a.feedback==='less'?'active':''}" aria-pressed="${a.feedback==='less'}">👎 踩</button>${a.feedback==='less'?lt('<button data-action="edit-feedback">修改理由</button>'):''}</div>${a.feedback_reasons?.length?it`<p class="intel-help">踩的理由：${a.feedback_reasons.map(esc).join('；')}</p>`:''}<p class="intel-help">反馈保存在本机作为你的偏好，再次点击可撤销。AI 整理可能存在遗漏，关键事实请核对原文。</p>${a.versions?.length?it`<details class="intel-help"><summary>历史版本（${a.versions.length}）</summary>${a.versions.map(v=>it`<p>${when(v.updated_at)} · ${esc(v.title)}</p><div style="white-space:pre-wrap">${esc(v.body)}</div>`).join('<hr>')}</details>`:''}`;
}
function articleImages(article){
 const seen=new Set();return [...(article.cover_image?[{...article.cover_image,alt:article.title}]:[]),...(article.images||[])].filter(i=>i.url&&!window.IntelligenceCards.isAvatar(i.url)&&link(i.url)!=='#'&&!seen.has(i.url)&&seen.add(i.url));
}
function articleImagesHTML(article){
 const images=articleImages(article);if(!images.length)return '';
 return it`<section class="intel-article-images"><h3>文章图片 · ${images.length}</h3><div class="intel-image-grid">${images.map((image,index)=>it`<button data-image-index="${index}" aria-label="放大图片 ${index+1}"><img src="${esc(window.IntelligenceCards.imageURL(article,image.url))}" alt="${esc(image.alt||article.title)}" loading="lazy" referrerpolicy="no-referrer"></button>`).join('')}</div></section>`;
}
function imageSource(article,image){
 const ref=article.sources.find(r=>r.url===image.source_url);
 if(ref?.profile_key)return {name:ref.source_name,profile_key:ref.profile_key};
 const source=ref&&state.sources.find(s=>s.channel_id===article.channel_id&&(ref.source_id?s.id===ref.source_id:s.name===ref.source_name));
 if(!source)throw Error(lt('原信息源已移除，无法确定图片的采集 Profile。'));return source;
}
async function extractArticleImages(){
 if(busy||!selectedId)return;const article=state.articles.find(a=>a.id===selectedId);busy=true;render();let added=0,failures=[];
 try{for(const ref of article.sources){let session;
  try{const source=imageSource(article,{source_url:ref.url});notice(lt('正在提取 ')+source.name+lt(' 的文章图片…'));session=await browserSession(source.profile_key||'default');
   const page=window.IntelligenceSocial.weibo({url:ref.url})?(await read(session,ref.url,{phase:'open'}),await session.client.extractWeiboDetail(ref.url)):await read(session,ref.url);
   await api('/articles/'+article.id+'/images','PUT',{source_url:ref.url,images:page.images||[],image_url:page.cover_image?.url||''});added++;
  }catch(error){failures.push(error.message);}finally{await closeBrowser(session);}
 }notice((added?lt('已更新文章图片'):lt('未提取到图片'))+(failures.length?'；'+failures.join('；'):''));
 }finally{busy=false;await refresh();}
}
let imagePreview=null;
function openArticleImage(index){
 const article=state.articles.find(a=>a.id===selectedId),images=article?articleImages(article):[];
 if(!images[index])return;imagePreview={article,images,index};renderImagePreview();$('#article-image-dialog').showModal();
}
function renderImagePreview(){
 const preview=imagePreview;if(!preview)return;const item=preview.images[preview.index];
 $('#article-image-large').src=window.IntelligenceCards.imageURL(preview.article,item.url);$('#article-image-large').alt=item.alt||preview.article.title;
 $('#article-image-caption').textContent=(preview.index+1)+' / '+preview.images.length+' · '+(item.alt||preview.article.title);
 $('#article-image-origin').href=link(item.source_url);$('#article-image-status').textContent='';
 $('#article-image-prev').disabled=preview.index===0;$('#article-image-next').disabled=preview.index===preview.images.length-1;
}
$('#article-image-prev').onclick=()=>{if(imagePreview?.index>0){imagePreview.index--;renderImagePreview();}};
$('#article-image-next').onclick=()=>{if(imagePreview&&imagePreview.index<imagePreview.images.length-1){imagePreview.index++;renderImagePreview();}};
$('#article-image-large').onerror=()=>{$('#article-image-status').textContent=lt('图片加载失败，可查看原文或尝试加入图库。');};
$('#article-image-save').onclick=async()=>{
 const preview=imagePreview;if(!preview||busy)return;const image=preview.images[preview.index],button=$('#article-image-save');let session,transfer;
 busy=true;button.disabled=true;$('#article-image-status').textContent=lt('正在通过原信息源 Profile 读取图片…');
 try{const source=imageSource(preview.article,image);session=await browserSession(source.profile_key||'default');await read(session,image.source_url);
  try{transfer=await session.client.beginPageResourceTransfer([image.url],32*1024*1024,true);}
  catch(error){
   // Some CDNs omit CORS headers. A dedicated image document keeps the same Profile and permits a same-origin fetch.
   await session.connection.command('browsingContext.navigate',{context:session.context,url:image.url,wait:'complete'});
   transfer=await session.client.beginPageResourceTransfer([image.url],32*1024*1024,true);
  }
  if(!transfer.media_type.startsWith('image/'))throw Error(lt('来源返回的内容不是图片'));
  const parts=[];let offset=0;
  while(offset<transfer.size){const chunk=await session.client.readPageResourceChunk(transfer.token,offset);
   if(chunk.next_offset<=offset)throw Error(lt('图片读取中断，请重试'));parts.push(Uint8Array.from(atob(chunk.base64),c=>c.charCodeAt(0)));offset=chunk.next_offset;
  }
  const form=new FormData();form.append('file',new File(parts,transfer.name,{type:transfer.media_type}));form.append('sourceAppId','ai2apps.intelligence');form.append('sourceRef',image.source_url);
  const response=await fetch('/v1/platform/gallery/assets/import',{method:'POST',credentials:'same-origin',headers:{'X-Intelligence-Language':window.IntelligenceI18n?.locale||'en'},body:form}),result=await response.json();
  if(!response.ok)throw Error(result.error?.message||lt('保存到图库失败'));
  $('#article-image-status').textContent=result.created?lt('已加入图库'):lt('图库中已有这张图片');
 }catch(error){$('#article-image-status').textContent=error.message;}
 finally{if(transfer?.token&&session)await session.client.endPageResourceTransfer(transfer.token).catch(()=>{});await closeBrowser(session);busy=false;button.disabled=false;}
};
const writingKinds={short_post:lt('短 Post'),long_article:lt('长文'),video_script:lt('视频稿'),podcast:lt('播客稿'),newsletter:lt('简报')};
const draftLists=new Map();let writingSession=null;
async function loadDrafts(id){
 if(!id)return;try{const result=await api('/channels/'+id+'/drafts');draftLists.set(id,result.items);if(channelId===id&&tab==='drafts'){renderContent();icons();}}
 catch(error){notice(lt('读取稿件失败：')+error.message);}
}
function renderDraftList(root){
 const drafts=draftLists.get(channelId);
 root.innerHTML=drafts===undefined?lt('<p class="intel-help">正在读取稿件…</p>'):drafts.map(d=>it`<section class="intel-topic"><div class="intel-story-meta">${esc(writingKinds[d.kind])} · 第 ${d.revision} 版 · ${when(d.updated_at)}</div><h2>${esc(d.title)}</h2><p class="intel-help">${esc(d.scope_label)}</p><button data-draft="${esc(d.id)}">打开稿件 / 继续修改</button></section>`).join('')||empty('file-pen-line',lt('从情报写成稿件'),lt('选择文章、栏目、热点或整个频道，填写指导后开始撰写。'),'');
}
function startWriting(scope,scopeId){
 const c=channel();if(!c)return;
 const label=scope==='article'?state.articles.find(a=>a.id===scopeId)?.title:scope==='topic'?c.hot_topics?.items.find(t=>t.id===scopeId)?.title:scope==='section'?(c.sections?.find(s=>s.id===scopeId)?.name||lt('待归类')):c.name;
 writingSession={channelId:c.id,scope,scopeId,label,pending:false,requestId:null,draft:null};
 $('#writing-create-form').reset();$('#writing-error').textContent='';$('#writing-status').textContent='';$('#writing-revision-guidance').value='';renderWriting();$('#writing-dialog').showModal();
}
async function openDraft(id){
 const draft=await api('/drafts/'+id);writingSession={channelId:draft.channel_id,label:draft.scope_label,draft,pending:false,requestId:null};
 $('#writing-error').textContent='';$('#writing-status').textContent='';$('#writing-revision-guidance').value='';renderWriting();$('#writing-dialog').showModal();
}
function renderWriting(){
 const session=writingSession;if(!session)return;const draft=session.draft;
 $('#writing-heading').textContent=draft?lt('稿件 · ')+writingKinds[draft.kind]:lt('撰写稿件');
 $('#writing-scope').textContent=lt('资料范围：')+session.label+(draft?lt(' · 已选 ')+draft.evidence.length+' / '+draft.total_articles+lt(' 篇情报'):'');
 $('#writing-create-form').hidden=Boolean(draft);$('#writing-workspace').hidden=!draft;
 $('#writing-create-form button[type=submit]').disabled=session.pending;$('#writing-revise-form button[type=submit]').disabled=session.pending;
 $('#writing-guidance').disabled=session.pending;$('#writing-kind').disabled=session.pending;$('#writing-revision-guidance').disabled=session.pending;
 if(!draft)return;
 $('#writing-version').textContent=lt('第 ')+draft.revision+lt(' 版 · 自动保存于 ')+when(draft.updated_at);$('#writing-title').textContent=draft.current.title;$('#writing-content').textContent=draft.current.content;
 const used=new Set(draft.current.evidence_ids);
 $('#writing-references').innerHTML=draft.evidence.filter(e=>used.has(e.evidence_id)).map(e=>it`<button data-writing-article="${esc(e.id)}">[${e.evidence_id}] ${esc(e.title)}</button>`).join('');
 $('#writing-turns').innerHTML=draft.turns.map(t=>it`<div class="intel-chat-question">${esc(t.guidance)}</div><div class="intel-chat-answer">${esc(t.note)}</div>`).join('');
 $('#writing-turns').scrollTop=$('#writing-turns').scrollHeight;
}
$('#writing-guidance').oninput=$('#writing-kind').onchange=$('#writing-revision-guidance').oninput=()=>{if(writingSession&&!writingSession.pending)writingSession.requestId=null;};
async function submitWriting(event,revise){
 event.preventDefault();const session=writingSession;if(!session||session.pending)return;
 const guidance=$(revise?'#writing-revision-guidance':'#writing-guidance').value.trim();if(!guidance)return;
 session.requestId||=crypto.randomUUID();session.pending=true;$('#writing-error').textContent='';$('#writing-status').textContent=revise?lt('AI 正在修改，原稿保留…'):lt('AI 正在根据所选情报撰写…');renderWriting();
 try{const body={request_id:session.requestId,guidance,...(revise?{revision:session.draft.revision}:{scope:session.scope,scope_id:session.scopeId,kind:$('#writing-kind').value})};
  const result=await api(revise?'/drafts/'+session.draft.id+'/revise':'/channels/'+session.channelId+'/drafts','POST',body);
  session.draft=result;session.requestId=null;await loadDrafts(session.channelId);
  if(writingSession===session){$('#writing-status').textContent=lt('稿件已保存，可继续提出修改要求');$('#writing-revision-guidance').value='';}
 }catch(error){if(writingSession===session){$('#writing-error').textContent=error.message;$('#writing-status').textContent=lt('可重试；已有稿件保留。');}}
 finally{session.pending=false;if(writingSession===session)renderWriting();}
}
$('#writing-create-form').onsubmit=event=>submitWriting(event,false);$('#writing-revise-form').onsubmit=event=>submitWriting(event,true);
$('#writing-copy').onclick=safe(async()=>{const d=writingSession?.draft;if(d){await navigator.clipboard.writeText(d.current.title+'\n\n'+d.current.content);$('#writing-status').textContent=lt('已复制稿件');}});
let feedbackDraft=null;
function reasonOptions(reasons, selected=[]){
 return reasons.map(r=>it`<label class="intel-feedback-reason"><input type="checkbox" value="${esc(r)}" ${selected.includes(r)?'checked':''}><span>${esc(r)}</span></label>`).join('');
}
async function dislikeDialog(id){
 const article=state.articles.find(a=>a.id===id);if(!article)return;
 const draft={id,signature:null};feedbackDraft=draft;
 const dialog=$('#feedback-dialog'),submit=$('#feedback-form button[type=submit]');
 $('#feedback-article-title').textContent=article.title;$('#feedback-reasons').textContent=lt('AI 正在生成适合这篇文章的理由…');
 $('#feedback-form .intel-form-error').textContent='';$('#feedback-retry').hidden=true;submit.disabled=true;
 if(!dialog.open)dialog.showModal();
 try{const result=await api('/articles/'+id+'/feedback-reasons','POST');if(feedbackDraft!==draft||!dialog.open)return;
  draft.signature=result.signature;$('#feedback-reasons').innerHTML=reasonOptions(result.reasons,article.feedback_reasons||[]);
  submit.disabled=!$('#feedback-reasons input:checked');
 }catch(error){if(feedbackDraft!==draft||!dialog.open)return;$('#feedback-reasons').textContent=lt('尚未记录反馈');$('#feedback-form .intel-form-error').textContent=error.message;$('#feedback-retry').hidden=false;}
}
$('#feedback-dialog').addEventListener('close',()=>{feedbackDraft=null;});
$('#feedback-reasons').onchange=()=>{$('#feedback-form button[type=submit]').disabled=!feedbackDraft?.signature||!$('#feedback-reasons input:checked');};
$('#feedback-retry').onclick=safe(()=>feedbackDraft&&dislikeDialog(feedbackDraft.id));
$('#feedback-form').onsubmit=async event=>{
 event.preventDefault();const draft=feedbackDraft;if(!draft?.signature)return;
 const reasons=[...document.querySelectorAll('#feedback-reasons input:checked')].map(e=>e.value);if(!reasons.length)return;
 const button=event.submitter;button.disabled=true;
 try{await api('/articles/'+draft.id,'PATCH',{feedback:'less',reasons,reason_signature:draft.signature});
  if(feedbackDraft===draft)$('#feedback-dialog').close();await refresh();notice(lt('已保存踩的理由和用户偏好'));
 }catch(error){if(feedbackDraft===draft){$('#feedback-form .intel-form-error').textContent=error.message;$('#feedback-retry').hidden=false;}}
 finally{button.disabled=false;}
};
async function showFilteredPosts(id=channelId){
 const result=await api('/channels/'+id+'/filtered-posts');
 $('#filtered-posts-list').innerHTML=result.items.map(r=>it`<section class="intel-run"><h3>${esc(r.page.title||lt('帖子'))}</h3><a href="${link(r.page.url)}" target="_blank" rel="noopener noreferrer">查看原帖 ↗</a><p>${esc((r.page.text||'').slice(0,600))}</p><p>${r.stage==='list'?lt('列表初筛'):lt('正文判断')} · ${esc(r.reason)}</p><small>${when(r.updated_at)}</small> ${r.status==='restored'?lt('<span>已恢复 · 后续更新处理</span>'):it`<button data-restore-post="${esc(r.id)}" data-channel="${esc(id)}">恢复</button>`}</section>`).join('')||lt('<p>暂无过滤记录。</p>');
 $('#filtered-posts-dialog').showModal();
}
let sectionEdits=[],sectionBaseline=[];
function readSectionEditor(){
 return [...document.querySelectorAll('#channel-sections-preview [data-section-edit]')].map(row=>({id:row.dataset.sectionEdit,name:row.querySelector('[data-section-name]').value.trim(),description:row.querySelector('[data-section-description]').value.trim()}));
}
function renderSectionEditor(){
 const root=$('#channel-sections-preview');
 if(!editing){root.innerHTML=lt('创建时，AI 会根据频道兴趣自动规划 4–8 个专属栏目；创建后可在设置中编辑。');return;}
 root.innerHTML=lt('<div class="intel-section-editor-head"><strong>频道栏目</strong><button type="button" data-add-section>＋ 添加栏目</button></div><p>修改名称和说明会用于后续文章归类。删除栏目会保留文章，并转入待归类；保存频道后生效。</p>')+sectionEdits.map(s=>it`<div class="intel-section-editor-row" data-section-edit="${esc(s.id)}"><label>栏目名称<input data-section-name value="${esc(s.name)}" maxlength="24" required></label><button type="button" data-remove-section="${esc(s.id)}" aria-label="删除栏目 ${esc(s.name)}">删除</button><label class="intel-section-description">归类说明<textarea data-section-description maxlength="240" rows="2" required>${esc(s.description)}</textarea></label></div>`).join('');
}
$('#channel-sections-preview').addEventListener('click',event=>{
 const button=event.target.closest('button');if(!button)return;
 if(button.hasAttribute('data-add-section')){sectionEdits=readSectionEditor();if(sectionEdits.length>=32){notice(lt('最多添加 32 个栏目'));return;}sectionEdits.push({id:crypto.randomUUID(),name:'',description:''});renderSectionEditor();$('#channel-sections-preview [data-section-edit]:last-child input')?.focus();}
 if(button.dataset.removeSection){const row=button.closest('[data-section-edit]'),name=row.querySelector('[data-section-name]').value||lt('未命名栏目');if(!confirm(lt('删除“')+name+lt('”？文章会保留并转到待归类，保存频道后生效。')))return;sectionEdits=readSectionEditor().filter(s=>s.id!==button.dataset.removeSection);renderSectionEditor();}
});
async function channelDialog(c=null,starter=''){
 editing=c?.id||null;sectionEdits=(c?.sections||[]).map(s=>({...s}));sectionBaseline=sectionEdits.map(s=>({...s}));renderSectionEditor();$('#channel-dialog-title').textContent=c?lt('频道设置'):lt('创建情报频道');$('#channel-name').value=c?.name||starter;$('#channel-interests').value=c?.interests||({[lt('腕表')]:lt('关注机械腕表新品、独立制表与行业重要动态。'),[lt('人工智能')]:lt('关注人工智能模型、开源项目、产品发布与重要研究。'),[lt('摄影')]:lt('关注相机新品、镜头评测、摄影技术和行业动态。')}[starter]||'');$('#channel-excluded').value=c?.excluded||'';$('#channel-post-filter').value=c?.post_filter_level||'standard';$('#channel-post-guidance').value=c?.post_filter_guidance||'';$('#channel-output-language').value=c?.output_language||window.IntelligenceI18n?.locale||'en';$('#channel-interval').value=c?.interval_hours||0;$('#delete-channel').hidden=!c;$('#channel-dialog .intel-form-error').textContent='';$('#channel-dialog').showModal();
 const submit=$('#channel-form button[type=submit]');submit.disabled=true;$('#create-knowledge').disabled=true;$('#knowledge-buckets').textContent=lt('正在读取知识库…');$('#new-knowledge-name').value=(c?.name||starter)?(c?.name||starter)+lt('情报'):'';
 try{
  const {items}=await api('/knowledge/buckets'),selected=new Set(c?.knowledge_bucket_ids||[]);
  $('#knowledge-buckets').innerHTML=items.map(b=>bucketOption(b,selected.has(b.id))).join('')||lt('<p class="intel-help">暂无可选知识库，可以创建一个专用知识库。</p>');
  for(const id of selected)if(!items.some(b=>b.id===id))$('#knowledge-buckets').insertAdjacentHTML('beforeend',bucketOption({id,name:lt('原知识库不可用（取消勾选以解除关联）')},true));
  submit.disabled=false;$('#create-knowledge').disabled=false;
 }catch(error){$('#knowledge-buckets').textContent=lt('读取失败，请关闭后重试');$('#channel-dialog .intel-form-error').textContent=error.message;}

}
function bucketOption(b,selected){return it`<label class="intel-bucket-option"><input type="checkbox" value="${esc(b.id)}" ${selected?'checked':''}><span>${esc(b.name)} <small>${b.visibility==='installation'?lt('本机共享 · 其他本机用户可见'):lt('私有')}</small></span></label>`;}
$('#create-knowledge').onclick=async()=>{
 const button=$('#create-knowledge'),name=$('#new-knowledge-name').value.trim();if(!name){$('#channel-dialog .intel-form-error').textContent=lt('请输入新知识库名称');return;}button.disabled=true;
 try{const response=await fetch('/v1/platform/knowledge/buckets',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,scope:'private',imported:false})});const result=await response.json();if(!response.ok)throw Error(typeof result.detail==='string'?result.detail:lt('创建知识库失败'));$('#knowledge-buckets').insertAdjacentHTML('beforeend',bucketOption(result,true));$('#new-knowledge-name').value='';$('#channel-dialog .intel-form-error').textContent='';}
 catch(error){$('#channel-dialog .intel-form-error').textContent=error.message;}finally{button.disabled=false;}
};
$('#new-channel').onclick=$('#sidebar-create').onclick=safe(()=>channelDialog());$('#edit-channel').onclick=safe(()=>channelDialog(channel()));
$('#channel-form').onsubmit=async event=>{event.preventDefault();const submit=event.submitter;submit.disabled=true;const originalText=submit.textContent;submit.textContent=editing?lt('正在保存…'):lt('AI 正在规划栏目…');try{const value=await api('/channels'+(editing?'/'+editing:''),editing?'PUT':'POST',{...(editing?{sections:readSectionEditor(),expected_sections:sectionBaseline}:{}),name:$('#channel-name').value.trim(),interests:$('#channel-interests').value.trim(),excluded:$('#channel-excluded').value.trim(),post_filter_level:$('#channel-post-filter').value,post_filter_guidance:$('#channel-post-guidance').value.trim(),output_language:$('#channel-output-language').value,interval_hours:Number($('#channel-interval').value),knowledge_bucket_ids:[...document.querySelectorAll('#knowledge-buckets input:checked')].map(e=>e.value)});channelId=value.id;selectedId=null;sectionId='';tab='sources';$('#channel-dialog').close();await refresh();}catch(error){$('#channel-dialog .intel-form-error').textContent=error.message;}finally{submit.disabled=false;submit.textContent=originalText;}};
$('#delete-channel').onclick=safe(async()=>{if(!confirm(lt('删除此频道及其文章、信息源和更新记录？')))return;await api('/channels/'+editing,'DELETE');$('#channel-dialog').close();selectedId=null;await refresh();});
async function loadProfiles(){const response=await fetch('/v1/platform/client/browser-profiles',{credentials:'same-origin'});if(!response.ok)throw Error(lt('无法读取 AI Browser Profiles，请稍后重试。'));profiles=await response.json();}
function profileOptions(selected='default'){return profiles.map(p=>it`<option value="${esc(p.key)}" ${p.key===selected?'selected':''}>${esc(p.name)}${p.is_default?lt('（默认）'):''}</option>`).join('');}
async function sourceDialog(source=null){await loadProfiles();const agentChoices=await api('/source-agents');editingSource=source?.id||null;$('#source-form').reset();$('#source-dialog-title').textContent=source?lt('信息源设置'):lt('添加信息源');$('#source-form button[type=submit]').textContent=source?lt('保存设置'):lt('加入频道');$('#source-name').value=source?.name||'';$('#source-url').value=source?.url||'';$('#source-kind').value=source?.kind||'website';$('#source-social-interval').value=source?.social_interval_hours||6;$('#source-profile').innerHTML=profileOptions(source?.profile_key||'default');if(source&&!profiles.some(p=>p.key===(source.profile_key||'default'))){$('#source-profile').insertAdjacentHTML('afterbegin',it`<option value="" disabled selected>原 Profile 已删除，请重新选择</option>`);}for(const kind of ['list','article']){const selected=source?.[kind+'_agent_generation_id']||'';const field=$('#source-'+kind+'-agent');field.innerHTML=lt('<option value="">自动生成 / 复用</option>')+agentChoices.agents.map(a=>it`<option value="${esc(a.generation_id)}">${esc(a.name)}</option>`).join('');if(selected&&!agentChoices.agents.some(a=>a.generation_id===selected))field.insertAdjacentHTML('beforeend',it`<option value="${esc(selected)}">原指定版本不可用，请重新选择</option>`);field.value=selected;}$('#source-profile').required=true;$('#source-dialog .intel-form-error').textContent='';initSourceMode();$('#source-dialog').showModal();}
function updateSourceMode(){
 const mode=$('#source-mode').value,custom=mode!=='url';
 $('#source-query-label').hidden=!custom;$('#source-query').required=custom;$('#source-url').readOnly=custom;
 $('#source-query-title').textContent=mode==='weibo-account'?lt('账号主页链接或 UID'):mode.endsWith('topic')?lt('话题标签'):lt('搜索关键词');
 $('#source-query').placeholder=mode==='weibo-account'?lt('例如：https://weibo.com/u/1234567890'):mode==='weibo-topic'?lt('例如：腕表（无需 #）'):mode==='youtube-topic'?lt('例如：watches（无需 #）'):lt('例如：腕表、机械表评测');
 if(custom){$('#source-kind').value='social';try{$('#source-url').value=window.IntelligenceSocial.sourceURL(mode,$('#source-query').value,$('#source-url').value);}catch(_){$('#source-url').value='';}}
}
function initSourceMode(){
 $('#source-mode').value='url';$('#source-query').value='';
 try{const u=new URL($('#source-url').value);if(window.IntelligenceSocial.youtube({url:u.href})){
  if(u.pathname==='/results'){$('#source-mode').value='youtube-search';$('#source-query').value=u.searchParams.get('search_query')||'';}
  else if(u.pathname.startsWith('/hashtag/')){$('#source-mode').value='youtube-topic';$('#source-query').value=decodeURIComponent(u.pathname.slice(9));}
 }else if(window.IntelligenceSocial.weibo({url:u.href})){
  if(u.hostname!=='s.weibo.com'){$('#source-mode').value='weibo-account';$('#source-query').value=u.href;}else if(/^#[^#]+#$/.test(u.searchParams.get('q')||'')){$('#source-mode').value='weibo-topic';$('#source-query').value=u.searchParams.get('q').slice(1,-1);}
 }}catch(_){}updateSourceMode();
}
$('#source-mode').onchange=updateSourceMode;$('#source-query').oninput=updateSourceMode;
$('#add-source').onclick=safe(()=>sourceDialog());
$('#source-form').onsubmit=async event=>{event.preventDefault();event.submitter.disabled=true;try{await api(editingSource?'/sources/'+editingSource:'/channels/'+channelId+'/sources',editingSource?'PUT':'POST',{name:$('#source-name').value.trim(),url:$('#source-url').value.trim(),kind:$('#source-kind').value,social_interval_hours:Number($('#source-social-interval').value),profile_key:$('#source-profile').value,list_agent_generation_id:$('#source-list-agent').value,article_agent_generation_id:$('#source-article-agent').value,enabled:editingSource?state.sources.find(s=>s.id===editingSource).enabled:true});$('#source-dialog').close();await refresh();}catch(error){$('#source-dialog .intel-form-error').textContent=error.message;}finally{event.submitter.disabled=false;}};
async function loadConversation(id){
 const chat=conversationState(id);if(chat.loading)return;chat.loading=true;
 try{const result=await api('/channels/'+id+'/conversation');chat.turns=result.turns;chat.loaded=true;chat.error='';}
 catch(error){chat.error=error.message;}finally{chat.loading=false;if(channelId===id)renderChannelChat();}
}
function renderChannelChat(){
 const c=channel(),chat=c?conversationState(c.id):null;
 $('#intel-reader').classList.toggle('open',mobilePanel);
 $('#intel-entity-reader').hidden=readerMode!=='entity';
 $('#show-entity-detail').classList.toggle('active',readerMode==='entity');
 $('#intel-article-reader').hidden=readerMode!=='article';
 $('#channel-chat').hidden=readerMode!=='chat';
 $('#show-channel-chat').classList.toggle('active',readerMode==='chat');
 $('#show-channel-article').classList.toggle('active',readerMode==='article');
 $('#show-channel-article').disabled=!selectedId;
 const input=$('#channel-chat-question');
 if(input.dataset.channel!==channelId){input.value=chat?.draft||'';input.dataset.channel=channelId||'';}
 input.disabled=!c||!!chat?.sending;
 $('#send-channel-chat').disabled=!c||!!chat?.sending||!!chat?.loading||!chat?.loaded;
 const selected=state.articles.find(a=>a.id===selectedId&&a.channel_id===channelId);
 $('#channel-chat-context').textContent=selected?lt('结合当前文章：')+selected.title:lt('向频道提问');
 $('#channel-chat-status').textContent=chat?.sending?lt('正在阅读频道资料并回答…'):chat?.error||'';
 const root=$('#channel-chat-messages');
 const markup=chat?.turns.length?chat.turns.map(t=>it`<div class="intel-chat-question">${esc(t.question)}</div><div class="intel-chat-answer">${esc(t.answer)}<div class="intel-chat-refs">${(t.references||[]).map(r=>r.kind==='knowledge'?it`<details><summary>[${r.number}] 知识库 · ${esc(r.title)}</summary><p>${esc(r.excerpt||'')}</p></details>`:it`<button type="button" data-article="${esc(r.article_id)}">[${r.number}] ${esc(r.title)}</button>`).join('')}</div></div>`).join(''):empty('messages-square',c?lt('和这个频道聊聊'):lt('先选择一个频道'),c?lt('可以总结近期变化、比较产品，或打开一篇文章后继续追问。'):lt('创建频道并采集文章后即可提问。'));
 if(root.dataset.content!==markup){root.innerHTML=markup;root.dataset.content=markup;root.scrollTop=root.scrollHeight;icons();}
 if(c&&!chat.loaded&&!chat.loading&&!chat.error)loadConversation(c.id);
}
$('#channel-chat-question').oninput=()=>{if(channel()){const chat=conversationState(channelId);chat.draft=$('#channel-chat-question').value;chat.requestId=null;chat.requestArticle=undefined;}};
$('#show-entity-detail').onclick=()=>{readerMode='entity';mobilePanel=true;renderChannelChat();};
$('#show-channel-chat').onclick=()=>{readerMode='chat';renderReader();};
$('#show-channel-article').onclick=()=>{readerMode='article';renderReader();};
$('#open-channel-chat').onclick=()=>{readerMode='chat';mobilePanel=true;const chat=conversationState(channelId);if(!chat.loaded&&!chat.loading){chat.error='';loadConversation(channelId);}renderReader();$('#channel-chat-question').focus();};
$('#close-channel-panel').onclick=()=>{mobilePanel=false;renderReader();};
$('#channel-chat-form').onsubmit=async event=>{
 event.preventDefault();const id=channelId,chat=conversationState(id),question=$('#channel-chat-question').value.trim();
 if(!id||!question||chat.sending||!chat.loaded)return;
 chat.draft=question;chat.requestId=chat.requestId||crypto.randomUUID();chat.sending=true;chat.error='';
 // Keep retry identity and article context stable even if the user navigates while waiting.
 chat.requestArticle=chat.requestArticle===undefined?selectedId:chat.requestArticle;
 renderChannelChat();
 try{const turn=await api('/channels/'+id+'/conversation','POST',{question,request_id:chat.requestId,article_id:chat.requestArticle});
  if(!chat.turns.some(t=>t.id===turn.id))chat.turns.push(turn);
  chat.draft='';chat.requestId=null;chat.requestArticle=undefined;
  if(channelId===id)$('#channel-chat-question').value='';
 }catch(error){chat.error=error.message+lt('；可点击发送重试');}
 finally{chat.sending=false;if(channelId===id)renderChannelChat();}
};
async function readArticle(id){readerMode='article';mobilePanel=true;selectedId=id;await api('/articles/'+id,'PATCH',{read:true});await refresh();}
$('#search-articles').oninput=()=>{renderContent();icons();};$('#article-filter').onchange=()=>{renderContent();icons();};$('#article-type-filter').onchange=()=>{renderContent();icons();};$('#refresh-view').onclick=safe(refresh);
document.addEventListener('keydown',event=>{if(['Enter',' '].includes(event.key)&&event.target.matches('[data-article]')){event.preventDefault();safe(readArticle)(event.target.dataset.article);}});
document.addEventListener('click',safe(async event=>{
 const b=event.target.closest('button,[data-article]');if(!b||b.disabled)return;
 if(b.hasAttribute('data-show-filtered')){await showFilteredPosts();return;}
 if(b.dataset.restorePost){b.disabled=true;try{await api('/channels/'+b.dataset.channel+'/filtered-posts/'+b.dataset.restorePost+'/restore','POST');await showFilteredPosts(b.dataset.channel);notice(lt('已恢复，将在后续更新处理'));}finally{b.disabled=false;}return;}

 if(b.dataset.close){if(b.dataset.close==='import-dialog'&&importPending)return;$('#'+b.dataset.close).close();return;}
 if(b.dataset.channel){channelId=b.dataset.channel;readerMode='chat';mobilePanel=false;selectedId=null;sectionId='';render();if(tab==='drafts')await loadDrafts(channelId);return;}
 if(b.hasAttribute('data-section')){sectionId=b.dataset.section;selectedId=null;render();return;}
 if(b.dataset.action==='sync-knowledge'){b.disabled=true;try{await api('/channels/'+channelId+'/knowledge-sync','POST');await refresh();}finally{b.disabled=false;}return;}
 if(b.dataset.action==='update-topics'){await updateTopics();return;}
 if(b.dataset.imageIndex!==undefined){openArticleImage(Number(b.dataset.imageIndex));return;}
 if(b.dataset.action==='extract-images'){await extractArticleImages();return;}
 if(b.dataset.action==='extract-cover'){await extractArticleCover();return;}
 if(b.dataset.action==='create-sections'){await createSections();return;}
 if(b.dataset.write){startWriting(b.dataset.write,b.dataset.scopeId||'');return;}
 if(b.dataset.draft){await openDraft(b.dataset.draft);return;}
 if(b.dataset.writingArticle){$('#writing-dialog').close();await readArticle(b.dataset.writingArticle);return;}
 if(b.dataset.tab){tab=b.dataset.tab;render();if(tab==='topics')await updateTopics();if(tab==='drafts')await loadDrafts(channelId);return;}
 if(b.dataset.article){await readArticle(b.dataset.article);return;}
 if(b.dataset.starter){await channelDialog(null,b.dataset.starter);return;}
 if(b.dataset.action==='create')await channelDialog();
 if(b.dataset.action==='sources'){tab='sources';render();}
 if(b.dataset.action==='recommend')await recommend();
 if(b.dataset.action==='close-reader'){selectedId=null;readerMode='chat';mobilePanel=false;renderReader();}
 if(b.dataset.resumeSocial){await api('/sources/'+b.dataset.resumeSocial+'/social-resume','POST');await refresh();notice(lt('已恢复采集；仍遵守平台冷却时间'));return;}
 if(b.dataset.editSource){await sourceDialog(state.sources.find(s=>s.id===b.dataset.editSource));return;}
 if(b.dataset.toggleSource){const s=state.sources.find(s=>s.id===b.dataset.toggleSource);await api('/sources/'+s.id,'PUT',{name:s.name,url:s.url,kind:s.kind,social_interval_hours:s.social_interval_hours||6,profile_key:s.profile_key||'default',list_agent_generation_id:s.list_agent_generation_id||'',article_agent_generation_id:s.article_agent_generation_id||'',enabled:!s.enabled});await refresh();}
 if(b.dataset.deleteSource){if(!confirm(lt('从频道移除此信息源？已有文章会保留。')))return;await api('/sources/'+b.dataset.deleteSource,'DELETE');await refresh();}
 if(b.dataset.action==='edit-feedback'){await dislikeDialog(selectedId);return;}
 if(b.dataset.feedback){const a=state.articles.find(a=>a.id===selectedId);if(!a)return;
  if(b.dataset.feedback==='less'&&a.feedback!=='less'){await dislikeDialog(a.id);return;}
  b.disabled=true;try{await api('/articles/'+a.id,'PATCH',{feedback:a.feedback===b.dataset.feedback?'':b.dataset.feedback});await refresh();}finally{b.disabled=false;}
 }
}));
// Each operation owns an explicitly created context, never guesses the user's focused tab.
async function openEntityOriginal(id,sourceUrl){
 const article=state.articles.find(a=>a.id===id);
 if(!article)throw Error(lt('相关文章已移除，请刷新列表。'));
 const reference=sourceUrl?article.sources.find(s=>s.url===sourceUrl):article.sources[0];
 if(!reference||link(reference.url)==='#')throw Error(lt('此文章没有可用的原文地址。'));
 const source=imageSource(article,{source_url:reference.url});
 let session;
 try{
  session=await browserSession(source.profile_key||'default');
  await session.connection.command('browsingContext.navigate',{context:session.context,url:reference.url,wait:'interactive'});
  session.retain=true;
  await session.connection.command('browsingContext.activate',{context:session.context});
 }finally{await closeBrowser(session);}
}
let importChannelId=null,importPending=false;
$('#import-article').onclick=safe(async()=>{if(importPending)return;await loadProfiles();importChannelId=channelId;$('#import-form').reset();$('#import-profile').innerHTML=profileOptions();$('#import-mode').onchange();$('#import-file').onchange();$('#import-status').textContent='';$('#import-form .intel-form-error').textContent='';$('#import-dialog').showModal();});
$('#import-mode').onchange=()=>{const file=$('#import-mode').value==='file';$('#import-url-fields').hidden=file;$('#import-file-fields').hidden=!file;$('#import-url').required=!file;$('#import-file').required=file;};
$('#import-file').onchange=()=>{const image=/\.(png|jpe?g|webp|gif)$/i.test($('#import-file').files[0]?.name||'');$('#import-image-choice').hidden=!image;document.querySelectorAll('[name="image-summary"]').forEach(input=>{input.required=image&&$('#import-mode').value==='file';input.checked=false;});};
$('#import-mode').addEventListener('change',()=>$('#import-file').onchange());
$('#import-dialog').addEventListener('cancel',event=>{if(importPending)event.preventDefault();});
$('#import-form').onsubmit=async event=>{
 event.preventDefault();if(importPending)return;const target=importChannelId;importPending=true;
 const submit=$('#import-form button[type=submit]');submit.disabled=true;$('#import-form .intel-form-error').textContent='';let session;
 try{
  let result;
  if($('#import-mode').value==='url'){
   const url=$('#import-url').value.trim();if(!/^https?:$/.test(new URL(url).protocol))throw Error(lt('请输入 HTTP 或 HTTPS URL'));
   $('#import-status').textContent=lt('正在通过 AI 浏览器读取网页…');const profile=$('#import-profile').value;
   session=await browserSession(profile);const page=await read(session,url,{max_chars:20000});
   $('#import-status').textContent=lt('正在归类并收录…');
   result=await api('/channels/'+target+'/import-url','POST',{profile_key:profile,page:{source_id:'',url:page.url||url,title:page.title||url,text:page.text,images:(page.images||[]).slice(0,24),image_url:page.cover_image?.url||'',content_type:'webpage'}});
  }else{
   const file=$('#import-file').files[0];if(!file||file.size>20*1024*1024)throw Error(lt('请选择不超过 20MB 的文件'));
   $('#import-status').textContent=lt('正在读取文件并归类…');const form=new FormData();form.append('file',file);form.append('title',$('#import-title').value);form.append('summarize_image',String(!$('#import-image-choice').hidden&&document.querySelector('[name="image-summary"]:checked')?.value==='yes'));
   const response=await fetch('/v1/platform/intelligence/channels/'+target+'/import-file',{method:'POST',credentials:'same-origin',headers:{'X-Intelligence-Language':window.IntelligenceI18n?.locale||'en'},body:form});result=await response.json();if(!response.ok)throw Error(lt(typeof result.detail==='string'?result.detail:lt('收录失败')));
  }
  $('#import-dialog').close();await refresh();if(channelId===target){tab='articles';sectionId='';render();await readArticle(result.id);}notice(lt('文章已收录'));
 }catch(error){$('#import-form .intel-form-error').textContent=error.message;$('#import-status').textContent='';}
 finally{await closeBrowser(session);importPending=false;submit.disabled=false;}
};
async function browserSession(profileKey='default'){
 // Ask the existing actor-bound native lifecycle service for a page in the user's
 // default AI Browser Profile. Shell itself is not a Firefox tabbrowser.
 // The unique requested URL identifies only our newly opened page; never bind by focus/order.
 const marker=location.origin+'/admin/static/favicon.svg#intelligence-'+crypto.randomUUID();
 const launched=await fetch('/v1/platform/client/browser-profiles/'+encodeURIComponent(profileKey)+'/launch',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({initial_url:marker})});
 if(!launched.ok)throw Error(lt('无法启动此信息源的 AI Browser Profile。请在 AI 浏览器 App 中检查该 Profile，或在信息源设置中重新选择。'));
 const launch=await launched.json();
 const connection=new window.AI2AppsBiDi.AI2AppsBiDiConnection();
 let createdContext=null;
 try{
  await connection.connect();let contexts=[];
  for(let attempt=0;attempt<12;attempt++){
   const tree=await connection.command('browsingContext.getTree',{maxDepth:0});
   contexts=(tree.contexts||[]).filter(context=>context.url===marker);
   if(contexts.length)break;
   // Profile launch binds a native container; it need not open initial_url.
   // Create our own explicit tab in that container, never adopt a focused tab.
   if(launch.user_context){
    const reference=(tree.contexts||[]).find(item=>item.userContext===launch.user_context);
    if(reference){
     const created=await connection.command('browsingContext.create',{type:'tab',userContext:launch.user_context,referenceContext:reference.context,background:true});
     createdContext=created.context;
     const verified=await connection.command('browsingContext.getTree',{root:createdContext,maxDepth:0});
     if(verified.contexts?.[0]?.userContext!==launch.user_context)throw Error(lt('采集页面的 Profile 不匹配。'));
     await connection.command('browsingContext.navigate',{context:createdContext,url:marker,wait:'interactive'});
     contexts=[{context:createdContext,url:marker,userContext:launch.user_context}];break;
    }
   }
   await new Promise(resolve=>setTimeout(resolve,250));
  }
  if(contexts.length!==1)throw Error(lt('未找到本次采集专用页面，请稍后重试。'));
  const context=contexts[0].context;
  const client=new window.AI2AppsBiDi.AI2AppsPageClient({bidi_context:context,url:marker});client.connection=connection;client.contextId=context;
  return {client,connection,context,retain:false};
 }catch(error){if(createdContext)await connection.command('browsingContext.close',{context:createdContext}).catch(()=>{});await connection.close();throw error;}
}
async function closeBrowser(session){if(!session)return;try{if(!session.retain)await session.connection.command('browsingContext.close',{context:session.context});}catch(_){}finally{await session.connection.close();}}
async function read(session,url,options={}){
 const result=await session.client.readPage({url,new_tab:false,close_tab:false,delay_ms:1200,max_chars:10000,include_cover:true,include_images:true,...options});
 if(result.outcome!=='success'){
  if(result.outcome==='needs_user'){session.retain=true;await session.connection.command('browsingContext.activate',{context:session.context});}
  const error=Error(result.outcome==='needs_user'?(result.reason==='cookie_consent'?lt('Cookie 对话框尚未关闭，请在保留的 Profile 页面选择 Cookie 偏好后重新更新。'):lt('请在保留的浏览器标签页完成登录或验证，然后重新更新。')):result.reason||lt('网页不可读取'));error.outcome=result.outcome;throw error;
 }
 return result;
}
async function candidatesFrom(session,limit=30){const list=await session.client.extractArticleList(limit);return (list.items||[]).map(item=>({url:item.url||item.href,title:String(item.title||'').slice(0,500),text:String(item.text||item.snippet||item.summary||'').slice(0,1500)})).filter(item=>{try{return ['https:','http:'].includes(new URL(item.url).protocol);}catch(_){return false;}});}
async function recommend(profileKey=null){
 if(busy||!channel())return;
 if(!profileKey){await loadProfiles();$('#recommendations').innerHTML=it`<label>搜索使用的 AI Browser Profile<select id="recommend-profile">${profileOptions()}</select></label><p class="intel-help">将在指定 Profile 中搜索；加入的信息源默认沿用此 Profile，可单独修改。</p><button id="start-recommend" class="intel-primary">开始搜索推荐</button>`;$('#recommend-dialog').showModal();$('#start-recommend').onclick=safe(()=>recommend($('#recommend-profile').value));return;}
busy=true;render();const target=channel();let session;
 $('#recommendations').innerHTML=lt('<p class="intel-help">正在搜索与你的兴趣相关的网站与社交话题…</p>');if(!$('#recommend-dialog').open)$('#recommend-dialog').showModal();
 try{
  session=await browserSession(profileKey);await read(session,'https://www.google.com/search?q='+encodeURIComponent(target.name+' '+target.interests.slice(0,150)+lt(' 新闻 官网 媒体 社交')));
  const searchResults=await candidatesFrom(session,30);if(!searchResults.length)throw Error(lt('未从搜索页读取到结果。可以手动添加信息源，或在 AceFox 中检查搜索页面。'));
  const candidates=[],seen=new Set();
  for(const [index,item] of searchResults.slice(0,6).entries()){
   $('#recommendations').innerHTML=it`<p class="intel-help">正在核对实际网站地址 ${index+1} / ${Math.min(searchResults.length,6)}…</p>`;
   try{
    const page=await read(session,item.url),final=new URL(page.url);
    if(/(^|\.)google\.[a-z.]+$/.test(final.hostname))continue;
    // General publications are monitored at their verified origin. Social pages
    // retain their exact topic/account path; never invent an account handle.
    const social=/(^|\.)(weibo\.com|x\.com|twitter\.com|facebook\.com|instagram\.com|xiaohongshu\.com|reddit\.com|youtube\.com|bilibili\.com)$/i.test(final.hostname);
    const url=social?page.url:final.origin+'/';if(seen.has(url))continue;seen.add(url);
    candidates.push({url,title:item.title,text:(item.text+lt(' 已访问：')+page.title+'；'+page.text.slice(0,800)).slice(0,1500)});
   }catch(error){if(error.outcome==='needs_user')throw error;}
  }
  if(!candidates.length)throw Error(lt('候选页面目前无法读取。请手动添加信息源，或在指定 Profile 中完成登录后重试。'));
  $('#recommendations').innerHTML=lt('<p class="intel-help">已核对实际网站地址，AI 正在筛选推荐…</p>');
  const result=await api('/channels/'+target.id+'/recommend','POST',{candidates});
  const root=$('#recommendations');root.innerHTML=result.sources.map((s,i)=>it`<section class="intel-recommendation"><h3>${esc(s.name)}</h3><p>${esc(s.reason)}</p><a href="${link(s.url)}" target="_blank" rel="noopener noreferrer">${esc(s.url)} ↗</a><button data-recommend-index="${i}">＋ 加入频道</button></section>`).join('')||lt('<p class="intel-help">没有找到合适的信息源，请细化频道兴趣或手动添加。</p>');
  root.querySelectorAll('[data-recommend-index]').forEach(button=>button.onclick=async()=>{button.disabled=true;try{const s=result.sources[Number(button.dataset.recommendIndex)];await api('/channels/'+target.id+'/sources','POST',{name:s.name,url:s.url,kind:s.kind,profile_key:profileKey,enabled:true});button.textContent=lt('已加入');await refresh();}catch(error){button.disabled=false;notice(error.message);}});
 }catch(error){$('#recommendations').innerHTML=it`<p class="intel-form-error">${esc(error.message)}</p><p class="intel-help">也可以在“信息源”页直接添加网站或社交话题链接。</p>`;}
 finally{await closeBrowser(session);busy=false;render();}
}
$('#recommend').onclick=safe(()=>recommend());
async function collect(id,scheduled=false){
 if(busy)return;busy=true;render();
 try{await api('/channels/'+id+'/runs','POST',{scheduled});notice(lt('已提交后台采集；可以关闭此页面。'));tab='runs';}
 finally{busy=false;await refresh();}
}
$('#collect').onclick=safe(()=>collect(channelId));
// One shared actor-scoped SSE connection observes Task and collection events.
let collectionStream=null,refreshQueued=false;
function queueCollectionRefresh(){
 if(refreshQueued)return;refreshQueued=true;
 setTimeout(()=>{refreshQueued=false;safe(refresh)();},150);
}
function observeCollections(){
 collectionStream=new EventSource('/v1/platform/browser-workspace/events',{withCredentials:true});
 collectionStream.addEventListener('intelligence.collection.changed',queueCollectionRefresh);
 collectionStream.addEventListener('browser.workspace.snapshot',queueCollectionRefresh);
 collectionStream.onopen=queueCollectionRefresh;
}
window.addEventListener('pagehide',()=>collectionStream?.close());
window.addEventListener('focus',queueCollectionRefresh);
safe(async()=>{await loadProfiles();await refresh();observeCollections();})();
})();
