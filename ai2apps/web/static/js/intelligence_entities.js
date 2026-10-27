/* Shared owner dossiers; render only escaped model output and linked evidence. */
(() => {
'use strict';
const lt=window.IntelligenceI18n?.text||(s=>s),it=window.IntelligenceI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const kinds={company:lt('公司'),brand:lt('品牌'),product:lt('产品 / 型号'),model:lt('型号'),person:lt('人物'),organization:lt('组织'),event:lt('事件'),industry:lt('行业')};
function kindLabel(e){return kinds[e.kind]||e.kind;}
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
function originalControl(group,source=null){
 const title=!source,label=title?group.article_title:articleSourceName(source);
 const attrs=title?`class="intel-related-article-title" aria-describedby="entity-article-tip-${esc(group.article_id)}"`:'';
 if(window.AI2APPS_MOBILE_SURFACE){
  const url=source?.url||group.sources?.[0]?.url||group.source_url;
  try{if(!/^https?:$/.test(new URL(url).protocol))throw Error();}
  catch{return `<span ${attrs}>${esc(label)}</span>`;}
  return `<a ${attrs} href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}${title?' ↗':''}</a>`;
 }
 return `<button ${attrs} data-entity-original="${esc(group.article_id)}"${source?` data-source-url="${esc(source.url)}"`:''}>${esc(label)}${title?' ↗':''}</button>`;
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
 return it`<h3>相关文章 · ${groups.size}</h3><p class="intel-help">${window.AI2APPS_MOBILE_SURFACE?lt('点击文章在手机浏览器中查看原文，下方为与该实体相关的图片。'):lt('点击文章在 AI 浏览器中查看原文，下方为与该实体相关的图片。')}</p>${[...groups.values()].map(group=>it`<section class="intel-entity-image-group"><header class="intel-related-article-header"><div class="intel-related-title-wrap">${originalControl(group)}<span class="intel-related-title-tip" id="entity-article-tip-${esc(group.article_id)}" role="tooltip">${esc(group.article_title)}</span></div><div class="intel-related-article-meta"><div class="intel-related-article-sources">${(group.sources||[]).length>1?group.sources.map(source=>originalControl(group,source)).join(' · '):esc(articleSourceName(group.sources?.[0]||{url:group.source_url}))}</div><span class="intel-related-image-count" aria-label="${group.images.length} 张图片" title="${group.images.length} 张图片"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="m21 15-5-5L5 21"/></svg><span>${group.images.length}</span></span></div></header><div class="intel-entity-images">${group.images.map(i=>it`<section><button data-entity-image-view="${esc(i.id)}" aria-label="放大图片">${imageHTML(i)}</button><div class="intel-entity-image-actions"><button data-entity-image-cover="${esc(i.id)}" ${e.cover_image?.id===i.id?'disabled':''}>${e.cover_image?.id===i.id?lt('当前封面'):lt('设为封面')}</button><button data-entity-image-remove="${esc(i.id)}">移除关联</button></div></section>`).join('')}</div></section>`).join('')||lt('<p>暂无相关文章。</p>')}`;
}

const attributeLabels={case_diameter:lt('表壳直径'),case_width:lt('表壳宽度'),case_thickness:lt('表壳厚度'),dial_diameter:lt('表盘直径'),dial_width:lt('表盘宽度'),strap_width:lt('表带宽度'),lug_width:lt('表耳宽度'),lug_to_lug:lt('表耳间距'),movement:lt('机芯型号'),power_reserve:lt('动力储存'),accuracy:lt('走时精度'),water_resistance:lt('防水深度'),case_material:lt('表壳材质'),parameters_total:lt('总参数量'),parameters_active:lt('激活参数量'),architecture:lt('模型架构'),context_window:lt('上下文长度'),memory_required:lt('所需内存'),memory_recommended:lt('推荐内存'),vram_required:lt('所需显存'),quantization:lt('量化与精度'),disk_size:lt('存储空间'),license:lt('许可证')};
function parameterLabel(group){return group.labels?.[String(window.IntelligenceI18n?.locale||'en').split('-')[0]]||attributeLabels[group.key]||group.label||group.key;}
function attributeHTML(e,open=true){
 const groups=e.attribute_groups||[];
 return it`<details class="intel-entity-fold" data-entity-fold="attributes" ${open?'open':''}><summary>属性与证据 · ${groups.length}</summary><p class="intel-help">仅列出文章明确支持的属性；缺失值不猜测。不同配置、实测与标称值分别保留。</p><button type="button" data-entity-attributes ${busy?'disabled':''}>提取 / 更新属性</button>${groups.map(group=>it`<section class="intel-attribute"><h3>${esc(parameterLabel(group))} ${group.conflicting?it`<span class="intel-status error">存在不同说法</span>`:''}</h3>${group.values.map(value=>it`<div class="intel-attribute-value"><strong>${esc(value.value)}</strong> ${value.historical?it`<span class="intel-help">历史版本</span>`:''}<p class="intel-help">${esc(value.conditions)}${value.conditions?' · ':''}${esc(({stated:lt('文章标称'),measured:lt('实测'),estimated:lt('估计')})[value.basis])}${value.status==='opinion'?' · '+lt('观点'):value.status==='rumour'?' · '+lt('传闻'):''}</p><details><summary>引用证据 · ${value.evidence.length}</summary>${value.evidence.map(ev=>it`<blockquote>${esc(ev.quote)}</blockquote>${ev.context_quote&&ev.context_quote!==ev.quote?it`<p class="intel-help">${esc(ev.context_quote)}</p>`:''}<button data-entity-article="${esc(ev.article_id)}">${esc(ev.article_title)}</button><small class="intel-help"> ${date(ev.observed_at)}${ev.historical?' · '+lt('历史版本'):''}</small>`).join('')}</details></div>`).join('')}</section>`).join('')||lt('<p class="intel-help">尚无结构化属性，可从已有引用文章中提取。</p>')}</details>`;
}

const articlePanels=new Map();
function articleEntityHTML(articleId,items){
 return it`<h2>本文实体与参数</h2>${items.map(e=>it`<section class="intel-article-entity"><h3>${esc(e.name)} <small>${esc(kindLabel(e))}${e.coverage==='mention'?' · '+lt('仅提及'):''}</small></h3>${e.brand?it`<p class="intel-help">${esc(e.brand)}${e.reference?' · '+esc(e.reference):''}</p>`:''}${e.attribute_groups.length?e.attribute_groups.map(g=>it`<div class="intel-article-parameter"><strong>${esc(parameterLabel(g))}</strong>${g.conflicting?it`<span class="intel-status error">存在不同说法</span>`:''}${g.values.map(v=>{const current=v.evidence.some(ev=>ev.article_id===articleId&&!ev.historical);return it`<p>${esc(v.value)} <small class="intel-help">${current?lt('本文证据'):lt('其它文章证据')} · ${esc(({stated:lt('文章标称'),measured:lt('实测'),estimated:lt('估计')})[v.basis])}${v.status==='opinion'?' · '+lt('观点'):v.status==='rumour'?' · '+lt('传闻'):''}${v.conditions?' · '+esc(v.conditions):''}</small></p><details><summary>引用证据 · ${v.evidence.length}</summary>${v.evidence.map(ev=>it`<blockquote>${esc(ev.quote)}</blockquote>${ev.context_quote&&ev.context_quote!==ev.quote?it`<p class="intel-help">${esc(ev.context_quote)}</p>`:''}<button data-article="${esc(ev.article_id)}">${esc(ev.article_title)}</button>${ev.historical?it`<small class="intel-help">历史版本</small>`:''}`).join('')}</details>`;}).join('')}</div>`).join(''):(['product','model'].includes(e.kind)?lt('<p class="intel-help">尚未提取参数。</p>'):'')}</section>`).join('')||lt('<p class="intel-help">本文尚未提取实体，可在实体档案中整理本频道。</p>')}`;
}
function renderArticle(target,article){
 if(!target)return;
 const key=article.id+':'+article.updated_at;target.dataset.entityArticleKey=key;
 let entry=articlePanels.get(key);
 if(!entry){
  entry={id:article.id,loading:true};articlePanels.set(key,entry);
  entry.request=host.api('/articles/'+article.id+'/entities').then(result=>{entry.items=result.items||[];entry.loading=false;}).catch(error=>{entry.error=error.message;entry.loading=false;});
 }
 const paint=()=>{
  if(target.isConnected===false||target.dataset.entityArticleKey!==key||articlePanels.get(key)!==entry)return;
  const markup=entry.loading?lt('<h2>本文实体与参数</h2><p class="intel-help">正在读取实体参数…</p>'):entry.error?it`<h2>本文实体与参数</h2><p class="intel-help">${esc(entry.error)}</p><button data-action="reload-article-entities">重试</button>`:articleEntityHTML(article.id,entry.items);
  if(target._entityMarkup!==markup){target.innerHTML=markup;target._entityMarkup=markup;}
 };
 paint();if(entry.loading)entry.request.then(paint);
}
function invalidateArticle(id){for(const [key,value] of articlePanels)if(value.id===id)articlePanels.delete(key);}

function paint(){
 if(!root||!['entities','opportunities'].includes(host.tab()))return;
 const e=entity(),detailRoot=host.detailRoot?.()||root;
 const expanded=new Set(renderedDetailId===e?.id?[...(detailRoot.querySelectorAll?.('details[data-entity-fold][open]')||[])].map(node=>node.dataset.entityFold):[]);
 const foldOpen=key=>expanded.has(key)?'open':'';
 if(!categoryOrder().includes(category)&&category!=='unclassified')category=defaultCategory();
 root.innerHTML=it`<div class="intel-entities-toolbar"><button data-entity-build ${busy?'disabled':''}>${busy?lt('AI 正在处理…'):lt('AI 整理本频道实体')}</button><button data-entity-backfill ${busy?'disabled':''}>补齐实体参数</button><button data-entity-reconcile ${busy?'disabled':''}>合并重复实体</button><button data-entity-evaluate ${busy?'disabled':''}>检查机会线索</button><button data-entity-plan ${busy?'disabled':''}>AI 规划实体分类</button><button data-entity-create>新建档案</button><button data-entity-dismissed>已忽略 (${(data.dismissed_entities||[]).length})</button></div><p class="intel-help">档案在你的频道之间共享。事实来自已采集文章，保留引用和时间；AI 整理不代表独立核验。机会线索用于后续研究。</p>`;
 const pendingCount=data.entities.filter(e=>e.channel_ids.includes(channelId)&&e.dossier_status==='pending').length;
 if(pendingCount)root.innerHTML+=it`<p class="intel-help">${pendingCount} 个旧档案待重新整理。点击“AI 整理本频道实体”按实质介绍与提及重新判断；暂不展示未确认的配图。</p>`;
 if(showDismissed){
 const dismissedPage=window.IntelligencePagination.page('dismissed',channelId,window.IntelligencePagination.newest(data.dismissed_entities||[]));
 root.innerHTML+=it`<p class="intel-help">不感兴趣的实体在你的所有频道隐藏，后续按名称及别名阻止重新加入。恢复后可再次收录。</p>${dismissedPage.items.map(e=>it`<section class="intel-topic"><strong>${esc(e.name)}</strong> <button data-entity-restore="${esc(e.id)}">恢复</button></section>`).join('')||lt('<p>暂无已忽略实体。</p>')}<button data-entity-dismissed>返回实体列表</button>`+window.IntelligencePagination.button('dismissed',dismissedPage.more);
 }else{
  root.innerHTML+=it`<div class="intel-entities-toolbar"><input id="entity-search" aria-label="搜索实体或机会" placeholder="搜索实体、别名或机会…" value="${esc(query)}"><label><input id="entity-all" type="checkbox" ${all?'checked':''}>跨频道查看全部</label></div>`;
  const scoped=data.entities.filter(e=>(showMentions||!['mention','pending'].includes(e.dossier_status))&&(all||e.channel_ids.includes(channelId)||e.manual)&&(!query||[e.name,...e.aliases].join(' ').toLowerCase().includes(query.toLowerCase())));
  if(mode==='entities'){
   const ordered=categoryOrder();if(scoped.some(e=>entityCategory(e)==='unclassified'))ordered.push('unclassified');
   const shown=categoriesExpanded?ordered:(category?[category]:[]);
   if(!taxonomy())root.innerHTML+=lt('<p class="intel-help">此频道尚未规划实体分类。点击“AI 规划实体分类”，根据频道内容建立分类并整理已有档案。</p>');
   root.innerHTML+=it`<nav class="intel-entity-categories" aria-label="实体类型">${shown.map(key=>it`<button type="button" data-entity-category="${key}" aria-pressed="${category===key}" class="${category===key?'active':''}">${esc(categoryName(key))} <span>${scoped.filter(e=>entityCategory(e)===key).length}</span></button>`).join('')}<button type="button" data-entity-expand aria-expanded="${categoriesExpanded}" aria-label="${categoriesExpanded?lt('收起分类'):lt('展开更多分类')}">${categoriesExpanded?lt('收起 ▴'):lt('展开 ▾')}</button></nav><div class="intel-entity-filter-row"><label class="intel-entity-watched"><input id="entity-mentions" type="checkbox" ${showMentions?'checked':''}>显示提及记录 / 待整理</label><label class="intel-entity-watched"><input id="entity-watched" type="checkbox" ${watchedOnly?'checked':''}>仅看已关注</label></div>`;
  }
  const visible=window.IntelligencePagination.newest(scoped.filter(e=>mode!=='entities'||((entityCategory(e)===category)&&(!watchedOnly||e.watched))));

  const scope=JSON.stringify([channelId,all,query,category,showMentions,watchedOnly]);
  const entityPage=window.IntelligencePagination.page('entities',scope,visible);
  if(mode==='entities')root.innerHTML+=entityPage.items.map(e=>it`<section class="intel-topic ${e.id===selected?'intel-entity-selected':''}">${e.cover_image?it`<button class="intel-entity-cover" data-entity-open="${esc(e.id)}" aria-label="查看实体图片">${imageHTML(e.cover_image)}</button>`:''}<div class="intel-entity-card-heading"><h2><button data-entity-open="${esc(e.id)}">${esc(e.name)}</button></h2><button data-entity-dismiss="${esc(e.id)}" title="在所有频道移除，并阻止再次收录">不感兴趣</button></div><p>${esc(categoryName(entityCategory(e))||kindLabel(e))}${statusLabel(e)?' · '+statusLabel(e):''} · ${e.watched?lt('已关注'):lt('未关注')} · ${e.facts.length} 条引用事实</p><p>${esc(e.aliases.join(' / '))}</p><p class="intel-help">来自：${esc(channels(e)||lt('手动档案'))}</p><p>${esc(facts(e)[0]?.text||lt('等待证据'))}</p></section>`).join('')||lt('<p>当前分类暂无实体。可展开分类选择其他类型，也可以点击“AI 整理本频道实体”补充档案。</p>');
  else{
   const ids=new Set(visible.map(e=>e.id));
   const leadPage=window.IntelligencePagination.page('opportunities',scope,window.IntelligencePagination.newest(data.opportunities.filter(l=>ids.has(l.entity_id))));
   root.innerHTML+=leadPage.items.map(l=>{const e=data.entities.find(e=>e.id===l.entity_id);return it`<section class="intel-topic"><small>${esc(({new:lt('新线索'),read:lt('已读'),ignored:lt('已忽略')})[l.status])}${l.stale?lt(' · 关注规则已变化，旧分析'):''} · ${date(l.created_at)}</small><h2>${esc(l.title)}</h2><button data-entity-open="${esc(e.id)}">${esc(e.name)}档案</button>${[['change',lt('证据中的变化')],['relevance',lt('与你的关联 · AI 推断')],['conditions',lt('成立条件')],['counterevidence',lt('反证与不确定性')],['next_steps',lt('下一步核实')]].map(([key,label])=>it`<h3>${label}</h3><p>${esc(l[key])}</p>`).join('')}<p>${citations(e,l.fact_ids)}</p><p>${esc(l.feedback_reason||'')}</p><button data-lead-read="${esc(l.id)}">标为已读</button><button data-lead-research="${esc(e.id)}">研究反面证据</button><form data-lead-ignore="${esc(l.id)}"><input name="reason" required maxlength="1000" placeholder="忽略理由，将用于后续判断"><button>忽略并记住理由</button></form></section>`;}).join('')||lt('<p>暂无机会线索。先在实体档案里关注实体并填写条件，再检查；没有符合证据的变化时不会强行生成。</p>');
   root.innerHTML+=window.IntelligencePagination.button('opportunities',leadPage.more);
  }
  if(mode==='entities')root.innerHTML+=window.IntelligencePagination.button('entities',entityPage.more);
 }
 if(detailRoot!==root){detailRoot.innerHTML=e?it`<section class="intel-topic"><h2><button type="button" class="intel-entity-name" data-entity-rename aria-controls="entity-identity-editor" aria-expanded="${editingIdentity===e.id}" title="编辑名称和别名">${esc(e.name)}</button></h2>${statusLabel(e)?it`<p class="intel-help">${statusLabel(e)} · ${esc(e.facts.find(f=>!f.historical)?.coverage_reason||lt('需按新规则重新整理，尚未确认有实质介绍。'))}</p>`:''}<p>${esc(categoryName(entityCategory(e))||kindLabel(e))} · ${esc(channels(e))}</p><form id="entity-settings"><div id="entity-identity-editor" ${editingIdentity===e.id?'':'hidden'}><div class="intel-identity-heading"><span>编辑名称与别名</span><button type="button" data-entity-rename-close class="intel-icon" aria-label="关闭名称编辑" title="关闭名称编辑">×</button></div><label>名称<input name="name" required maxlength="160" value="${esc(e.name)}"></label><label>别名（每行一个）<textarea name="aliases" rows="2" maxlength="3200">${esc(e.aliases.join('\n'))}</textarea></label></div><div class="intel-entity-preferences"><label><input name="watched" type="checkbox" ${e.watched?'checked':''}>关注这个实体</label><button type="button" data-entity-dismiss="${esc(e.id)}" ${busy?'disabled':''}>不感兴趣</button></div></form>${attributeHTML(e,renderedDetailId!==e.id||expanded.has('attributes'))}${imageGallery(e)}<details class="intel-entity-fold" data-entity-fold="conversation" ${foldOpen('conversation')}><summary>与实体对话</summary><form id="entity-question"><textarea name="question" required maxlength="3000" rows="2" placeholder="例如：有哪些矛盾说法？下一步应该核实什么？"></textarea><button ${busy?'disabled':''}>基于跨频道证据回答</button></form><div class="intel-entity-answer">${answer}</div></details><details class="intel-entity-fold" data-entity-fold="timeline" ${foldOpen('timeline')}><summary>事实与变化时间线 · ${e.facts.length}</summary><p class="intel-help">时间为文章整理时间，实际事件时间以引用为准。冲突说法并列保留；旧文章版本会标注。</p><div class="intel-entity-timeline">${facts(e).map(f=>it`<section class="intel-run"><label><input type="checkbox" name="fact" form="entity-move" value="${esc(f.id)}">${esc(({reported:lt('文章报道'),opinion:lt('观点'),rumour:lt('传闻')})[f.status])}${f.historical?lt(' · 历史版本'):''}</label><p>${esc(f.text)}</p><blockquote>${esc(f.quote)}</blockquote><small>${date(f.observed_at)}</small><p>${citations(e,[f.id])}</p></section>`).join('')||lt('<p>尚无引用事实，整理频道文章后会补充。</p>')}</div></details><details class="intel-entity-fold" data-entity-fold="rules" ${foldOpen('rules')}><summary>机会条件 / 关注规则</summary><form id="entity-rule-settings"><label class="intel-rule-input">关注条件<textarea name="rule" maxlength="2000" rows="3" placeholder="例如：关注新尺寸、具体长期使用反馈；投资线索需有业务变化证据，列出反证与待核实条件">${esc(e.rule)}</textarea></label><button ${busy?'disabled':''}>保存关注规则</button></form></details><details class="intel-entity-fold" data-entity-fold="ownership" ${foldOpen('ownership')}><summary>纠正归属</summary><form id="entity-move"><p class="intel-help">先展开事实与变化时间线，勾选需要移动的事实。</p><label>将勾选事实移到<select name="target"><option value="">选择另一个实体</option>${data.entities.filter(x=>x.id!==e.id).map(x=>it`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('')}</select></label><button ${busy?'disabled':''}>移动所选事实</button><p class="intel-help">可先新建档案再拆分；全选移动可合并已有事实。原文章保持不变。</p></form></details></section>`:'';host.entityAvailable?.(!!e);renderedDetailId=e?.id||null;}
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
  if(b.dataset.listMore){window.IntelligencePagination.more(b.dataset.listMore);paint();return;}
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
  if(b.hasAttribute('data-entity-backfill')){const target=channelId;await work(async()=>{const skip=[];let result;do{result=await host.api('/channels/'+target+'/entities/attributes','POST',{skip_ids:skip});data=result;skip.push(...result.failed.map(f=>f.id));host.notice(lt('实体属性已更新')+' · '+(result.entity_name||'')+' · '+result.remaining);}while(result.remaining>0&&!result.retry_later);articlePanels.clear();host.notice(result.retry_later?lt('模型调用超时，补齐已暂停，已完成的参数保留，可重试。'):skip.length?lt('部分实体参数提取失败，可重试')+' '+skip.length:lt('实体参数补齐完成'));});return;}
  if(b.hasAttribute('data-entity-attributes')){const id=selected;await work(async()=>{let result;do{result=await host.api('/entities/'+id+'/attributes','POST');data=result;host.notice(lt('实体属性已更新'));}while(result.remaining>0);});return;}
  if(b.hasAttribute('data-entity-reconcile')){const target=channelId;await work(async()=>{const result=await host.api('/channels/'+target+'/entities/reconcile','POST');data=result;host.notice(lt('已合并重复实体')+' '+result.merged+(result.unreviewed?lt(' · 待继续核对 ')+result.unreviewed:''));});return;}
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
window.IntelligenceEntities={renderArticle,invalidateArticle,init(value){host=value;},async render(target,tab,id){root=target;mode=tab;if(channelId!==id){showDismissed=false;showMentions=false;editingIdentity=null;selected=null;answer='';query='';watchedOnly=false;all=false;const preferred=categoryChoices.get(id)||savedCategory(id)||defaultCategory(id);category=preferred;categoriesExpanded=false;}channelId=id;const version=++requestVersion;root.innerHTML=lt('<p>正在读取共享档案…</p>');try{await load();if(version===requestVersion)paint();}catch(error){root.textContent=error.message;}},async afterCollection(){/* Legacy notification hook is read-only; extraction requires a user action. */await load();}};
})();
