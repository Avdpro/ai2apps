/* Source format is separate from platform, section, and AI authorship. */
(() => {
'use strict';
const lt=window.IntelligenceI18n?.text||(s=>s),it=window.IntelligenceI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
const types={webpage:{label:lt('网页文章'),icon:'newspaper'},post:{label:lt('帖子'),icon:'messages-square'},video:{label:lt('视频'),icon:'video'},audio:{label:lt('音频'),icon:'headphones'},image:{label:lt('图片 / 图集'),icon:'images'},document:{label:lt('文档 / 报告'),icon:'file-text'}};
const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function safeURL(value){try{const u=new URL(value,String(value).startsWith('/v1/platform/intelligence/imports/')?location.origin:undefined);return /^https?:$/.test(u.protocol)?u.href:'';}catch(_){return '';}}
function isAvatar(url){try{return /^(?:tvax|tva|tvaxww)\d*\.sinaimg\.cn$/.test(new URL(url).hostname);}catch(_){return false;}}
function imageURL(article,url){
 const safe=safeURL(url);if(!safe||isAvatar(safe))return '';
 if(article.id&&/^wx[1-4]\.sinaimg\.cn$/.test(new URL(safe).hostname))return '/v1/platform/intelligence/articles/'+encodeURIComponent(article.id)+'/image?url='+encodeURIComponent(safe);
 return safe;
}
function typeOf(ref={}){
 if(types[ref.content_type])return ref.content_type;
 const p=(ref.platform||'').toLowerCase();
 if(['youtube','bilibili','vimeo'].includes(p))return 'video';
 if(['weibo','x','twitter','reddit','forum'].includes(p))return 'post';
 let u;try{u=new URL(ref.url);}catch(_){return 'webpage';}const h=u.hostname.toLowerCase(),path=u.pathname.toLowerCase();
 if(/\.(pdf|docx?|pptx?|xlsx?|epub)$/.test(path))return 'document';
 if(/\.(mp3|m4a|wav|ogg|flac)$/.test(path))return 'audio';
 if(/\.(png|jpe?g|webp|gif|avif)$/.test(path))return 'image';
 if(/\.(mp4|webm|mov)$/.test(path))return 'video';
 if(/(^|\.)(youtube\.com|youtu\.be|vimeo\.com|bilibili\.com)$/.test(h))return 'video';
 if(/(^|\.)(weibo\.com|x\.com|twitter\.com|reddit\.com)$/.test(h)||/\/(threads|topic|topics|discussion)\//.test(path))return 'post';
 if(h==='podcasts.apple.com')return 'audio';
 return 'webpage';
}
function platform(ref={}){
 const names={youtube:'YouTube',weibo:lt('微博'),x:'X',twitter:'X',reddit:'Reddit',bilibili:lt('哔哩哔哩'),vimeo:'Vimeo',forum:lt('论坛')};
 if(names[ref.platform])return names[ref.platform];
 try{const h=new URL(ref.url).hostname.replace(/^www\./,'');for(const [domain,name] of Object.entries({'youtube.com':'YouTube','youtu.be':'YouTube','weibo.com':lt('微博'),'x.com':'X','twitter.com':'X','reddit.com':'Reddit','bilibili.com':lt('哔哩哔哩')})){if(h===domain||h.endsWith('.'+domain))return name;}return ref.source_name||h;}catch(_){return ref.source_name||lt('来源待补充');}
}
function describe(article){
 const refs=article.sources||[],formats=[...new Set(refs.map(typeOf))];
 if(!formats.length)formats.push(types[article.content_type]?article.content_type:'webpage');
 return {kind:formats.length===1?formats[0]:'webpage',formats,mixed:formats.length>1,ref:refs[0]||{},refs};
}
function duration(value){return Number.isFinite(value)&&value>0?it`${Math.floor(value/60)}:${String(Math.floor(value%60)).padStart(2,'0')}`:'';}
function images(article,failed){const seen=new Set();return [article.cover_image,...(article.images||[])].filter(Boolean).filter(i=>safeURL(i.url)&&!isAvatar(i.url)&&!failed?.has(i.url)&&!seen.has(i.url)&&seen.add(i.url));}
function render(article,{selected=false,section='',updated='',failedImages=new Set()}={}){
 const {kind,formats,mixed,ref,refs}=describe(article),info=types[kind],photos=images(article,failedImages);
 const img=(photo,cls='')=>it`<img class="${cls}" src="${esc(imageURL(article,photo.url))}" alt="${esc(photo.alt||article.title)}" loading="lazy" decoding="async" referrerpolicy="no-referrer">`;
 const glyph=icon=>it`<i data-lucide="${icon}" aria-hidden="true"></i>`;
 const visual=(icon,label)=>it`<div class="intel-format-placeholder">${glyph(icon)}<span>${esc(label)}</span></div>`;
 const cover=photos[0]?it`<div class="intel-card-media">${img(photos[0])}</div>`:'';
 const badge=it`<span class="intel-format-badge">${glyph(info.icon)}${mixed?lt('混合来源'):info.label}</span>`;
 const provenance=it`<span>${article.image_ai_summary?lt('AI 图片总结'):article.manual_import?lt('手动收录'):refs.length>1?lt('AI 综合'):lt('AI 摘要')}${article.versions?.length?lt(' · 后续进展'):''}</span>`;
 const sourceLine=refs.length>1?it`${refs.length} 个引用来源 · ${[...new Set(refs.map(platform))].join(' / ')}`:[ref.author,platform(ref)].filter(Boolean).join(' · ');
 const meta=it`<div class="intel-story-meta">${article.read?'':lt('<span class="intel-unread" aria-label="未读"></span>')}${badge}${provenance}<span>${esc(section)}</span></div>`;
 const heading=it`<h2>${esc(article.title)}</h2><p class="intel-card-summary">${esc(article.summary)}</p>`;
 const footer=it`<div class="intel-story-footer"><span>${refs.length} 个引用来源</span><span>查看${kind==='video'?lt('视频情报'):kind==='post'?lt('帖子情报'):lt('情报')} ↗</span></div>`;
 const byline=it`<div class="intel-card-byline">${esc(sourceLine)}</div>`;
 const date=it`<div class="intel-card-date">${!mixed&&refs.length===1&&ref.published_at?lt('发布于 ')+esc(ref.published_at)+' · ':''}整理于 ${esc(updated)}</div>`;
 let body='';
 if(mixed){body=it`${meta}${byline}<div class="intel-card-format-list">${formats.map(t=>it`<span>${types[t].label}</span>`).join('')}</div>${heading}`;}
 else if(kind==='post'){
  const author=refs.length===1?(ref.author||ref.source_name||platform(ref)):lt('多来源帖子');
  body=it`${meta}<div class="intel-post-author"><span class="intel-author-mark" aria-hidden="true">${esc(Array.from(author)[0]||lt('帖'))}</span><div><strong>${esc(author)}</strong><small>${esc(refs.length===1?platform(ref):sourceLine)}</small></div></div>${heading}${photos.length?it`<div class="intel-post-photos intel-photos-${Math.min(photos.length,3)}">${photos.slice(0,9).map((photo,i)=>it`<div>${img(photo)}${i===8&&photos.length>9?it`<span class="intel-photo-count">+${photos.length-9}</span>`:''}</div>`).join('')}</div>`:''}`;
 }else if(kind==='video'){
  const coverage=refs.every(r=>r.coverage==='transcript')&&refs.length?lt('已读取网页文字稿'):refs.some(r=>r.coverage==='description')?lt('含仅标题与简介的来源'):lt('视频内容覆盖范围未记录');
  const length=refs.length===1?duration(ref.duration_seconds):'';
  body=it`${meta}<div class="intel-video-cover">${cover||visual('video',lt('视频来源'))}<span class="intel-video-symbol" aria-hidden="true">${glyph('play')}</span>${length?it`<span class="intel-duration">${length}</span>`:''}</div>${byline}${heading}<div class="intel-evidence-note">${glyph('file-check-2')}${esc(coverage)}</div>`;
 }else if(kind==='audio'){
  body=it`${meta}<div class="intel-audio-heading">${cover||visual('headphones',lt('音频来源'))}<div>${byline}<span class="intel-audio-label">${glyph('podcast')}音频内容摘要${refs.length===1&&duration(ref.duration_seconds)?' · '+duration(ref.duration_seconds):''}</span></div></div>${heading}`;
 }else if(kind==='image'){
  body=it`${meta}${byline}${photos.length?it`<div class="intel-gallery-cover">${img(photos[0])}<span class="intel-photo-count">${photos.length} 张已采集图片</span></div>`:visual('images',lt('尚未提取图片'))}${heading}`;
 }else if(kind==='document'){
  let extension=lt('文档');try{extension=new URL(ref.url).pathname.match(/\.(pdf|docx?|pptx?|xlsx?|epub)$/i)?.[1].toUpperCase()||extension;}catch(_){}
  body=it`${meta}<div class="intel-document-heading">${glyph('file-text')}<div><strong>${esc(extension)}</strong><small>${refs.length===1&&Number.isInteger(ref.page_count)&&ref.page_count>0?ref.page_count+lt(' 页'):lt('文档 / 报告')} · AI 内容摘要</small></div></div>${byline}${heading}`;
 }else{body=it`${meta}<div class="intel-web-layout"><div>${byline}${heading}</div>${cover}</div>`;}
 return it`<article class="intel-story intel-story-${kind}${selected?' selected':''}" data-article="${esc(article.id)}" tabindex="0" role="button" aria-label="${esc((mixed?lt('混合来源'):info.label)+'：'+article.title)}">${body}${date}${footer}</article>`;
}
window.IntelligenceCards={types,typeOf,describe,render,imageURL,isAvatar};
})();
