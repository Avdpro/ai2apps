/* Portable series data rules belong to this Package, not the Host ZIP service. */
((root,factory)=>{const api=factory();if(typeof module==='object')module.exports=api;else root.ComicBackup=api;})(globalThis,()=>{
 'use strict';
 const schema='ai2apps.comic-series-backup/v1',clone=x=>JSON.parse(JSON.stringify(x));
 const text=(v,n)=>typeof v==='string'&&v.length<=n;
 function validate(d){
  if(d?.schema!==schema||!Array.isArray(d.series)||!d.series.length||d.series.length>100)throw Error('Choose a Comic Studio series ZIP');
  const assets=new Set(),ids=new Set();
  for(const s of d.series){
   if(!s||!text(s.id,100)||ids.has(s.id)||!text(s.name,80)||!s.name.trim()||!text(s.style,2000)||!text(s.world,4000)||!['1:1','4:3','3:4','16:9','9:16'].includes(s.ratio)||!Array.isArray(s.characters)||s.characters.length>100||!Array.isArray(s.episodes)||s.episodes.length>2000)throw Error('Invalid series data');
   ids.add(s.id);const chars=new Set();
   for(const c of s.characters){if(!c||!text(c.id,100)||chars.has(c.id)||!text(c.name,100)||!text(c.description,6000))throw Error('Invalid character data');chars.add(c.id);if(c.assetId){if(!/^[0-9a-f]{32}$/.test(c.assetId))throw Error('Invalid image reference');assets.add(c.assetId);}if(c.approved&&!c.assetId)throw Error('Character reference missing');}
   const episodes=[...s.episodes,...(s.draft?[s.draft]:[])];
   for(const e of episodes){if(!e||!text(e.id,100)||!text(e.title,120)||!Array.isArray(e.panels)||e.panels.length<2||e.panels.length>6)throw Error('Invalid episode');
    for(const p of e.panels)if(!text(p.scene,4000)||!text(p.caption,600)||!Array.isArray(p.characters)||p.characters.some(id=>!chars.has(id)))throw Error('Invalid episode character or text');
    if(!Array.isArray(e.assetIds)||e.assetIds.length!==0&&e.assetIds.length!==e.panels.length)throw Error('Incomplete panel images');
    for(const id of e.assetIds){if(!/^[0-9a-f]{32}$/.test(id))throw Error('Invalid image reference');assets.add(id);}
   }
  }return [...assets];
 }
 function episode(e){return {id:e.id,title:e.title||'',summary:e.summary||'',brief:e.brief||'',ratio:e.ratio,ratioOverride:e.ratioOverride||'',count:e.panels.length,panels:e.panels.map(p=>({scene:p.scene,caption:p.caption||'',characters:[...p.characters]})),status:e.status==='completed'?'completed':'draft',createdAt:e.createdAt,assetIds:[...(e.assetIds||[])],previous:e.previous??2};}
 function pack(series){const d={schema,series:series.map(s=>({id:s.id,name:s.name,style:s.style||'',world:s.world||'',ratio:s.ratio,model:s.model||'',useDate:!!s.useDate,location:s.location||'',characters:s.characters.map(c=>({id:c.id,name:c.name,description:c.description||'',assetId:c.assetId||null,approved:!!c.approved})),episodes:s.episodes.map(episode),...(s.draft?{draft:episode(s.draft)}:{})}))};validate(d);return d;}
 function restore(d,mapping,existing){const required=validate(d);if(required.some(id=>!mapping[id]))throw Error('Missing imported images');if(existing.length+d.series.length>100)throw Error('Limit: 100 series');
  const names=new Set(existing.map(s=>s.name)),uid=()=>globalThis.crypto.randomUUID().replaceAll('-','');
  return d.series.map(value=>{const s=clone(value),base=s.name;let n=2;while(names.has(s.name))s.name=base.slice(0,65)+` (${n++})`;names.add(s.name);s.id=uid();s.revision=1;
   const chars=Object.fromEntries(s.characters.map(c=>[c.id,uid()]));for(const c of s.characters){c.id=chars[c.id];c.assetId=c.assetId?mapping[c.assetId]:null;}
   const eps=new Map();for(const e of [...s.episodes,...(s.draft?[s.draft]:[])]){if(!eps.has(e.id))eps.set(e.id,uid());e.id=eps.get(e.id);e.seriesRevision=1;e.panels=e.panels.map(p=>({...p,characters:p.characters.map(id=>chars[id])}));e.assetIds=e.assetIds.map(id=>mapping[id]);}
   return s;});
 }
 return {schema,validate,pack,restore};
});
