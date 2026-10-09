/* Shared owner dossiers; render only escaped model output and linked evidence. */
(() => {
'use strict';
const lt=window.IntelligenceI18n?.text||(s=>s),it=window.IntelligenceI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kinds={company:lt('公司'),brand:lt('品牌'),product:lt('产品 / 型号'),model:lt('AI 模型'),person:lt('人物'),organization:lt('组织'),event:lt('事件'),industry:lt('行业')};
let host,data={entities:[],opportunities:[]},root,mode,channelId,selected=null,all=false,query='',busy=false,answer='',requestVersion=0;
const categoryChoices=new Map();
let showDismissed=false,showMentions=false,editingIdentity=null;
let settingsQueue=Promise.resolve();
let renderedDetailId=null;
function saveSettings(target,patch){
 const task=settingsQueue.then(async()=>{
  const current=data.entities.find(e=>e.id===target.id)||target;
  const fields={name:current.name,aliases:current.aliases,watched:current.watched,rule:current.rule||'',...patch};
  const saved=await host.api('/entities/'+current.id,'PUT',{...fields,revision:current.revision});
  Object.assign(current,fields,{revision:saved.revision});
 });
 settingsQueue=task.catch(()=>{});return task;
}
let category='product',watchedOnly=false,categoriesExpanded=false;
function entityKind(e){return e.kind;}
function taxonomy(){return data.channel_taxonomies?.[channelId];}
function categoryOrder(){return (taxonomy()?.categories||[]).map(c=>c.id);}
function defaultCategory(){return taxonomy()?.default_id||'';}
function categoryName(id){return id==='unclassified'?lt('待分类'):taxonomy()?.categories.find(c=>c.id===id)?.name||'';}
function entityCategory(e){return taxonomy()?.assignments?.[e.id]||'unclassified';}
function savedCategory(id){try{return localStorage.getItem('intel.entity-category.'+id);}catch{return null;}}
function chooseCategory(value){if(value!=='unclassified'&&!categoryOrder().includes(value))return;category=value;categoriesExpanded=false;categoryChoices.set(channelId,value);try{localStorage.setItem('intel.entity-category.'+channelId,value);}catch{}paint();}
const date=s=>s?new Date(s).toLocaleString(window.IntelligenceI18n?.locale||'zh-CN'):'';
const entity=()=>data.entities.find(e=>e.id===selected);
const channels=e=>e.channel_ids.map(id=>host.state().channels.find(c=>c.id===id)?.name||lt('频道')).join('、');
const statusLabel=e=>e.dossier_status==='mention'?lt('仅提及'):e.dossier_status==='pending'?lt('待重新整理'):'';
const facts=e=>[...e.facts].sort((a,b)=>b.observed_at.localeCompare(a.observed_at));
function citations(e,ids){return ids.map(id=>e.facts.find(f=>f.id===id)).filter(Boolean).map(f=>it`<button data-entity-article="${esc(f.article_id)}">${esc(f.article_title)}</button>`).join('');}
function badge(){const b=document.querySelector('#entity-opportunity-count');if(b)b.textContent=data.opportunities.filter(l=>l.status==='new'&&!l.stale).length||'';}
async function load(){data=await host.api('/entities');badge();}
function imageHTML(i){const url=window.IntelligenceCards?.imageURL({id:i.article_id},i.url);return url?it`<img src="${esc(url)}" alt="${esc(i.alt||lt('来源文章图片'))}" loading="lazy" referrerpolicy="no-referrer">`:'';}
function articleSourceName(source){
 if(source.source_name)return source.source_name;
 try{return new URL(source.url).hostname.replace(/^www\./,'');}catch{return lt('原始来源');}
}
function imageGallery(e){
 const groups=new Map();
 for(const fact of facts(e)){
  if(!groups.has(fact.article_id))groups.set(fact.article_id,{article_id:fact.article_id,article_title:fact.article_title,sources:fact.sources||[],images:[]});
 }
 for(const image of e.images||[]){
  for(const origin of image.origins?.length?image.origins:[image]){
   if(!groups.has(origin.article_id))groups.set(origin.article_id,{...origin,images:[]});
   const group=groups.get(origin.article_id);
   if(!group.images.some(i=>i.id===image.id))group.images.push(image);
  }
 }
 return it`<h3>相关文章 · ${groups.size}</h3><p class="intel-help">点击文章在 AI 浏览器中查看原文，下方为与该实体相关的图片。</p>${[...groups.values()].map(group=>it`<section class="intel-entity-image-group"><header class="intel-related-article-header"><div class="intel-related-title-wrap"><button class="intel-related-article-title" data-entity-original="${esc(group.article_id)}" aria-describedby="entity-article-tip-${esc(group.article_id)}">${esc(group.article_title)} ↗</button><span class="intel-related-title-tip" id="entity-article-tip-${esc(group.article_id)}" role="tooltip">${esc(group.article_title)}</span></div><div class="intel-related-article-meta"><div class="intel-related-article-sources">${(group.sources||[]).length>1?group.sources.map(source=>it`<button data-entity-original="${esc(group.article_id)}" data-source-url="${esc(source.url)}">${esc(articleSourceName(source))}</button>`).join(' · '):esc(articleSourceName(group.sources?.[0]||{url:group.source_url}))}</div><span class="intel-related-image-count" aria-label="${group.images.length} 张图片" title="${group.images.length} 张图片"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg><span>${group.images.length}</span></span></div></header><div class="intel-entity-images">${group.images.map(i=>it`<section><button data-entity-image-view="${esc(i.id)}" aria-label="放大图片">${imageHTML(i)}</button><div class="intel-entity-image-actions"><button data-entity-image-cover="${esc(i.id)}" ${e.cover_image?.id===i.id?'disabled':''}>${e.cover_image?.id===i.id?lt('当前封面'):lt('设为封面')}</button><button data-entity-image-remove="${esc(i.id)}">移除关联</button></div></section>`).join('')}</div></section>`).join('')||lt('<p>暂无相关文章。</p>')}`;
}

function paint(){
 if(!root||!['entities','opportunities'].includes(host.tab()))return;
 const e=entity(),detailRoot=host.detailRoot?.()||root;
 const expanded=new Set(renderedDetailId===e?.id?[...(detailRoot.querySelectorAll?.('details[data-entity-fold][open]')||[])].map(node=>node.dataset.entityFold):[]);
 const foldOpen=key=>expanded.has(key)?'open':'';
 if(!categoryOrder().includes(category)&&category!=='unclassified')category=defaultCategory();
 root.innerHTML=it`<div class="intel-entities-toolbar"><button data-entity-build ${busy?'disabled':''}>${busy?lt('AI 正在处理…'):lt('AI 整理本频道实体')}</button><button data-entity-evaluate ${busy?'disabled':''}>检查机会线索</button><button data-entity-plan ${busy?'disabled':''}>AI 规划实体分类</button><button data-entity-create>新建档案</button><button data-entity-dismissed>已忽略 (${(data.dismissed_entities||[]).length})</button></div><p class="intel-help">档案在你的频道之间共享。事实来自已采集文章，保留引用和时间；AI 整理不代表独立核验。机会线索用于后续研究。</p>`;
 const pendingCount=data.entities.filter(e=>e.channel_ids.includes(channelId)&&e.dossier_status==='pending').length;
 if(pendingCount)root.innerHTML+=it`<p class="intel-help">${pendingCount} 个旧档案待重新整理。点击“AI 整理本频道实体”按实质介绍与提及重新判断；暂不展示未确认的配图。</p>`;
 if(showDismissed){
 root.innerHTML+=it`<p class="intel-help">不感兴趣的实体在你的所有频道隐藏，后续按名称及别名阻止重新加入。恢复后可再次收录。</p>${(data.dismissed_entities||[]).map(e=>it`<section class="intel-topic"><strong>${esc(e.name)}</strong> <button data-entity-restore="${esc(e.id)}">恢复</button></section>`).join('')||lt('<p>暂无已忽略实体。</p>')}<button data-entity-dismissed>返回实体列表</button>`;
 }else{
  root.innerHTML+=it`<div class="intel-entities-toolbar"><input id="entity-search" aria-label="搜索实体或机会" placeholder="搜索实体、别名或机会…" value="${esc(query)}"><label><input id="entity-all" type="checkbox" ${all?'checked':''}>跨频道查看全部</label></div>`;
  const scoped=data.entities.filter(e=>(showMentions||!['mention','pending'].includes(e.dossier_status))&&(all||e.channel_ids.includes(channelId)||e.manual)&&(!query||[e.name,...e.aliases].join(' ').toLowerCase().includes(query.toLowerCase())));
  if(mode==='entities'){
   const ordered=categoryOrder();if(scoped.some(e=>entityCategory(e)==='unclassified'))ordered.push('unclassified');
   const shown=categoriesExpanded?ordered:(category?[category]:[]);
   if(!taxonomy())root.innerHTML+=lt('<p class="intel-help">此频道尚未规划实体分类。点击“AI 规划实体分类”，根据频道内容建立分类并整理已有档案。</p>');
   root.innerHTML+=it`<nav class="intel-entity-categories" aria-label="实体类型">${shown.map(key=>it`<button type="button" data-entity-category="${key}" aria-pressed="${category===key}" class="${category===key?'active':''}">${esc(categoryName(key))} <span>${scoped.filter(e=>entityCategory(e)===key).length}</span></button>`).join('')}<button type="button" data-entity-expand aria-expanded="${categoriesExpanded}" aria-label="${categoriesExpanded?lt('收起分类'):lt('展开更多分类')}">${categoriesExpanded?lt('收起 ▴'):lt('展开 ▾')}</button></nav><div class="intel-entity-filter-row"><label class="intel-entity-watched"><input id="entity-mentions" type="checkbox" ${showMentions?'checked':''}>显示提及记录 / 待整理</label><label class="intel-entity-watched"><input id="entity-watched" type="checkbox" ${watchedOnly?'checked':''}>仅看已关注</label></div>`;
  }
  const visible=scoped.filter(e=>mode!=='entities'||((entityCategory(e)===category)&&(!watchedOnly||e.watched)));

  if(mode==='entities')root.innerHTML+=visible.map(e=>it`<section class="intel-topic ${e.id===selected?'intel-entity-selected':''}">${e.cover_image?it`<button class="intel-entity-cover" data-entity-open="${esc(e.id)}" aria-label="查看实体图片">${imageHTML(e.cover_image)}</button>`:''}<div class="intel-entity-card-heading"><h2><button data-entity-open="${esc(e.id)}">${esc(e.name)}</button></h2><button data-entity-dismiss="${esc(e.id)}" title="在所有频道移除，并阻止再次收录">不感兴趣</button></div><p>${esc(categoryName(entityCategory(e))||kinds[entityKind(e)])}${statusLabel(e)?' · '+statusLabel(e):''} · ${e.watched?lt('已关注'):lt('未关注')} · ${e.facts.length} 条引用事实</p><p>${esc(e.aliases.join(' / '))}</p><p class="intel-help">来自：${esc(channels(e)||lt('手动档案'))}</p><p>${esc(facts(e)[0]?.text||lt('等待证据'))}</p></section>`).join('')||lt('<p>当前分类暂无实体。可展开分类选择其他类型，也可以点击“AI 整理本频道实体”补充档案。</p>');
  else{
   const ids=new Set(visible.map(e=>e.id));
   root.innerHTML+=data.opportunities.filter(l=>ids.has(l.entity_id)).map(l=>{const e=data.entities.find(e=>e.id===l.entity_id);return it`<section class="intel-topic"><small>${esc(({new:lt('新线索'),read:lt('已读'),ignored:lt('已忽略')})[l.status])}${l.stale?lt(' · 关注规则已变化，旧分析'):''} · ${date(l.created_at)}</small><h2>${esc(l.title)}</h2><button data-entity-open="${esc(e.id)}">${esc(e.name)}档案</button>${[['change',lt('证据中的变化')],['relevance',lt('与你的关联 · AI 推断')],['conditions',lt('成立条件')],['counterevidence',lt('反证与不确定性')],['next_steps',lt('下一步核实')]].map(([key,label])=>it`<h3>${label}</h3><p>${esc(l[key])}</p>`).join('')}<p>${citations(e,l.fact_ids)}</p><p>${esc(l.feedback_reason||'')}</p><button data-lead-read="${esc(l.id)}">标为已读</button><button data-lead-research="${esc(e.id)}">研究反面证据</button><form data-lead-ignore="${esc(l.id)}"><input name="reason" required maxlength="1000" placeholder="忽略理由，将用于后续判断"><button>忽略并记住理由</button></form></section>`;}).join('')||lt('<p>暂无机会线索。先在实体档案里关注实体并填写条件，再检查；没有符合证据的变化时不会强行生成。</p>');
  }
 }
 if(detailRoot!==root){detailRoot.innerHTML=e?it`<section class="intel-topic"><h2><button type="button" class="intel-entity-name" data-entity-rename aria-controls="entity-identity-editor" aria-expanded="${editingIdentity===e.id}" title="编辑名称和别名">${esc(e.name)}</button></h2>${statusLabel(e)?it`<p class="intel-help">${statusLabel(e)} · ${esc(e.facts.find(f=>!f.historical)?.coverage_reason||lt('需按新规则重新整理，尚未确认有实质介绍。'))}</p>`:''}<p>${esc(categoryName(entityCategory(e))||kinds[entityKind(e)])} · ${esc(channels(e))}</p><form id="entity-settings"><div id="entity-identity-editor" ${editingIdentity===e.id?'':'hidden'}><div class="intel-identity-heading"><span>编辑名称与别名</span><button type="button" data-entity-rename-close class="intel-icon" aria-label="关闭名称编辑" title="关闭名称编辑">×</button></div><label>名称<input name="name" required maxlength="160" value="${esc(e.name)}"></label><label>别名（每行一个）<textarea name="aliases" rows="2" maxlength="3200">${esc(e.aliases.join('\n'))}</textarea></label></div><div class="intel-entity-preferences"><label><input name="watched" type="checkbox" ${e.watched?'checked':''}>关注这个实体</label><button type="button" data-entity-dismiss="${esc(e.id)}" ${busy?'disabled':''}>不感兴趣</button></div></form>${imageGallery(e)}<details class="intel-entity-fold" data-entity-fold="conversation" ${foldOpen('conversation')}><summary>与实体对话</summary><form id="entity-question"><textarea name="question" required maxlength="3000" rows="2" placeholder="例如：有哪些矛盾说法？下一步应该核实什么？"></textarea><button ${busy?'disabled':''}>基于跨频道证据回答</button></form><div class="intel-entity-answer">${answer}</div></details><details class="intel-entity-fold" data-entity-fold="timeline" ${foldOpen('timeline')}><summary>事实与变化时间线 · ${e.facts.length}</summary><p class="intel-help">时间为文章整理时间，实际事件时间以引用为准。冲突说法并列保留；旧文章版本会标注。</p><div class="intel-entity-timeline">${facts(e).map(f=>it`<section class="intel-run"><label><input type="checkbox" name="fact" form="entity-move" value="${esc(f.id)}">${esc(({reported:lt('文章报道'),opinion:lt('观点'),rumour:lt('传闻')})[f.status])}${f.historical?lt(' · 历史版本'):''}</label><p>${esc(f.text)}</p><blockquote>${esc(f.quote)}</blockquote><small>${date(f.observed_at)}</small><p>${citations(e,[f.id])}</p></section>`).join('')||lt('<p>尚无引用事实，整理频道文章后会补充。</p>')}</div></details><details class="intel-entity-fold" data-entity-fold="rules" ${foldOpen('rules')}><summary>机会条件 / 关注规则</summary><form id="entity-rule-settings"><label class="intel-rule-input">关注条件<textarea name="rule" maxlength="2000" rows="3" placeholder="例如：关注新尺寸、具体长期使用反馈；投资线索需有业务变化证据，列出反证与待核实条件">${esc(e.rule)}</textarea></label><button ${busy?'disabled':''}>保存关注规则</button></form></details><details class="intel-entity-fold" data-entity-fold="ownership" ${foldOpen('ownership')}><summary>纠正归属</summary><form id="entity-move"><p class="intel-help">先展开事实与变化时间线，勾选需要移动的事实。</p><label>将勾选事实移到<select name="target"><option value="">选择另一个实体</option>${data.entities.filter(x=>x.id!==e.id).map(x=>it`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label><button ${busy?'disabled':''}>移动所选事实</button><p class="intel-help">可先新建档案再拆分；全选移动可合并已有事实。原文章保持不变。</p></form></details></section>`:'';host.entityAvailable?.(!!e);renderedDetailId=e?.id||null;}
 detailRoot.querySelector('#entity-settings')?.addEventListener('change',async event=>{
  const field=event.target;if(!['name','aliases','watched'].includes(field.name))return;
  if(!field.checkValidity())return;
  const value=field.name==='watched'?field.checked:field.name==='aliases'?field.value.split('\n').map(x=>x.trim()).filter(Boolean):field.value;
  try{await saveSettings(e,{[field.name]:value});if(selected===e.id){const title=detailRoot.querySelector('[data-entity-rename]');if(title)title.textContent=e.name;}host.notice(lt('档案已自动保存'));}catch(error){host.notice(error.message);}
 });
 root.querySelector('#entity-mentions')?.addEventListener('change',event=>{showMentions=event.target.checked;paint();});
 root.querySelector('#entity-watched')?.addEventListener('change',event=>{watchedOnly=event.target.checked;paint();});
 root.querySelector('#entity-search')?.addEventListener('change',event=>{query=event.target.value;paint();});
 root.querySelector('#entity-all')?.addEventListener('change',event=>{all=event.target.checked;paint();});
 const onClick=async event=>{const b=event.target.closest('button');if(!b||b.type==='submit'&&b.closest('form')||busy)return;try{
  if(b.hasAttribute('data-entity-rename')||b.hasAttribute('data-entity-rename-close')){
   const open=b.hasAttribute('data-entity-rename');editingIdentity=open?selected:null;
   const editor=detailRoot.querySelector('#entity-identity-editor'),trigger=detailRoot.querySelector('[data-entity-rename]');
   if(editor)editor.hidden=!open;trigger?.setAttribute('aria-expanded',String(open));
   if(open)editor?.querySelector('[name="name"]')?.focus();else trigger?.focus();return;
  }
  if(b.dataset.entityImageView){const i=entity()?.images.find(i=>i.id===b.dataset.entityImageView);if(i)host.viewImage?.(i.article_id,i.url);return;}
  if(b.dataset.entityImageCover||b.dataset.entityImageRemove){const id=entity().id,imageId=b.dataset.entityImageCover||b.dataset.entityImageRemove,action=b.dataset.entityImageRemove?'remove':'cover';if(action==='remove'&&!confirm(lt('移除这张图片与该实体的关联？原文章图片保留，后续整理不会再次加入这张图片。')))return;await work(async()=>{await host.api('/entities/'+id+'/images','POST',{image_id:imageId,action});await load();});return;}
  if(b.hasAttribute('data-entity-dismissed')){showDismissed=!showDismissed;selected=null;paint();return;}
  if(b.dataset.entityDismiss||b.dataset.entityRestore){const id=b.dataset.entityDismiss||b.dataset.entityRestore;const action=b.dataset.entityDismiss?'dismiss':'restore';if(action==='dismiss'){const target=data.entities.find(e=>e.id===id);if(!target||!confirm(lt('将“')+target.name+lt('”标记为不感兴趣？\n\n该实体会在你的所有频道隐藏，后续按名称及已知别名阻止再次收录。原文章保留。\n可以在“已忽略”中恢复。')))return;}await work(async()=>{await host.api('/entities/'+id+'/'+action,'POST');if(selected===id)selected=null;await load();host.notice(action==='dismiss'?lt('已移除并记住偏好，后续不再自动收录；可在“已忽略”中恢复'):lt('已恢复实体'));});return;}
  if(b.hasAttribute('data-entity-plan')){const target=channelId;await work(async()=>{data=await host.api('/channels/'+target+'/entity-categories','POST');if(channelId===target){category=defaultCategory();categoryChoices.delete(target);try{localStorage.removeItem('intel.entity-category.'+target);}catch{}categoriesExpanded=false;}host.notice(lt('AI 已规划频道分类并整理实体'));});return;}
  if(b.hasAttribute('data-entity-expand')){categoriesExpanded=!categoriesExpanded;paint();return;}
  if(b.dataset.entityCategory){chooseCategory(b.dataset.entityCategory);return;}
  if(b.dataset.entityOriginal){await host.openOriginal(b.dataset.entityOriginal,b.dataset.sourceUrl);return;}
  if(b.dataset.entityArticle){await host.readArticle(b.dataset.entityArticle);return;}
  if(b.dataset.entityOpen){selected=b.dataset.entityOpen;editingIdentity=null;answer='';paint();host.showEntity?.();return;}
  if(b.hasAttribute('data-entity-create')){root.innerHTML=lt('<form id="entity-create"><h2>新建实体档案</h2><label>名称<input name="name" required maxlength="160"></label><label>类型<select name="kind">')+Object.entries(kinds).map(([k,v])=>it`<option value="${k}">${v}</option>`).join('')+lt('</select></label><button>创建</button></form>');return;}
  if(busy)return;
  if(b.hasAttribute('data-entity-build')){const buildChannel=channelId;await work(async()=>{let result;try{do{result=await host.api('/channels/'+buildChannel+'/entities','POST');data=result;host.notice(lt('已整理 ')+result.processed+lt(' 篇，剩余 ')+result.remaining+lt(' 篇'));}while(result.remaining>0);}finally{await load();}});return;}
  if(b.hasAttribute('data-entity-evaluate')){await work(async()=>{const result=await host.api('/entities/opportunities/evaluate','POST');data=result;mode='opportunities';host.setTab?.(mode);selected=null;host.notice(lt('已检查 ')+result.evaluated+lt(' 个关注实体'));});return;}
  if(b.dataset.leadRead){await host.api('/entities/opportunities/'+b.dataset.leadRead,'PATCH',{status:'read'});await load();paint();return;}
  if(b.dataset.leadResearch){selected=b.dataset.leadResearch;paint();host.showEntity?.();detailRoot.querySelector('[data-entity-fold="conversation"]').open=true;detailRoot.querySelector('#entity-question textarea').value=lt('针对目前机会线索，逐条检查反面证据、缺失信息和判断失效条件。');return;}
 }catch(error){host.notice(error.message);}};
 const onSubmit=async event=>{event.preventDefault();const form=event.target,values=new FormData(form),targetEntity=entity();if(busy)return;try{
  if(form.id==='entity-create'){const result=await host.api('/entities','POST',{name:values.get('name'),kind:values.get('kind')});await load();selected=result.id;mode='entities';host.setTab?.(mode);paint();host.showEntity?.();}
  else if(form.id==='entity-settings'){return;}
  else if(form.id==='entity-rule-settings'){
   await work(async()=>{await saveSettings(targetEntity,{rule:values.get('rule')});await load();host.notice(lt('关注规则已保存'));});
  }
  else if(form.id==='entity-question')await work(async()=>{const result=await host.api('/entities/'+targetEntity.id+'/question','POST',{question:values.get('question')});answer='<p>'+esc(result.text)+'</p>'+citations(targetEntity,result.fact_ids);});
  else if(form.id==='entity-move')await work(async()=>{await host.api('/entities/'+targetEntity.id+'/move-facts','POST',{target_id:values.get('target'),fact_ids:values.getAll('fact')});await load();});
  else if(form.dataset.leadIgnore){await host.api('/entities/opportunities/'+form.dataset.leadIgnore,'PATCH',{status:'ignored',reason:values.get('reason')});await load();paint();}
 }catch(error){host.notice(error.message);}};
 root.onclick=onClick;root.onsubmit=onSubmit;
 if(detailRoot!==root){detailRoot.onclick=onClick;detailRoot.onsubmit=onSubmit;}
}
async function work(fn){busy=true;paint();try{await fn();}finally{busy=false;paint();}}
window.IntelligenceEntities={init(value){host=value;},async render(target,tab,id){root=target;mode=tab;if(channelId!==id){showDismissed=false;showMentions=false;editingIdentity=null;selected=null;answer='';query='';watchedOnly=false;all=false;const preferred=categoryChoices.get(id)||savedCategory(id)||defaultCategory(id);category=preferred;categoriesExpanded=false;}channelId=id;const version=++requestVersion;root.innerHTML=lt('<p>正在读取共享档案…</p>');try{await load();if(version===requestVersion)paint();}catch(error){root.textContent=error.message;}},async afterCollection(id){let result;do{result=await host.api('/channels/'+id+'/entities','POST');}while(result.remaining>0);data=await host.api('/entities/opportunities/evaluate','POST');badge();const count=data.opportunities.filter(l=>l.status==='new'&&!l.stale).length;if(count)host.notice(lt('发现 ')+count+lt(' 条待查看机会线索'));}};
})();
