(function(global){'use strict';
const lt=globalThis.MiniAppI18n?.text||(s=>s),it=globalThis.MiniAppI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
 function reviewInput(items){return items.map((item,index)=>({id:'r'+index,kind:item.kind,title:String(item.title).slice(0,280),url:item.url.slice(0,2048),summary:String(item.summary||'').slice(0,500),content:item.kind==='post'?String(item.content||'').slice(0,2400):''}));}
 function applyReview(items,result,excludeAds=false){
  const rows=result?.items;if(!Array.isArray(rows)||rows.length!==items.length)throw Error(lt('Incomplete AI result'));
  const originals=new Map(items.map((item,index)=>['r'+index,item])),seen=new Set();
  return rows.map(row=>{const item=originals.get(row?.id);if(!item||seen.has(row.id)||!['title','summary','reason'].every(key=>typeof row[key]==='string')||row.title.length>280||row.summary.length>1200||row.reason.length>280)throw Error(lt('Invalid AI result'));seen.add(row.id);
   if(excludeAds&&typeof row.is_ad!=='boolean')throw Error(lt('Missing AI ad classification'));
   if(row.translated===true&&(item.kind!=='post'||typeof row.translated_content!=='string'||!row.translated_content.trim()||row.translated_content.length>4800||typeof row.source_language!=='string'))throw Error(lt('Invalid post translation'));
   return {...item,...(item.kind==='post'?{source_language:row.source_language||'und',translated:row.translated===true,translated_content:row.translated===true?row.translated_content:''}:{}),is_ad:item.is_ad===true||row.is_ad===true,...(item.kind==='web'?{title:row.title||item.title,summary:(item.summary||item.content)?row.summary:(row.title||item.title)}:{}),ranking_reason:row.reason,ai_reviewed:true};}).filter(item=>!excludeAds||!item.is_ad);
 }
 function groups(items){return ['web','post','video'].map(kind=>({kind,items:items.filter(item=>item.kind===kind)})).filter(group=>group.items.length);}
 function imageURL(raw){if(typeof raw==='string'&&raw.length<=400000&&/^data:image\/(jpeg|png|webp);base64,[A-Za-z0-9+/]+={0,2}$/.test(raw))return raw;try{const u=new URL(raw);return u.protocol==='https:'&&!u.username&&!u.password?u.href:null;}catch(_){return null;}}
 global.SearchAllPresentation=Object.freeze({reviewInput,applyReview,groups,imageURL});
})(typeof window==='undefined'?globalThis:window);
