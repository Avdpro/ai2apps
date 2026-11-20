/* Package owns series selection, story inheritance, compilation and history. */
((root,factory)=>{const api=factory(typeof module==='object'?require('./core.js'):root.ComicCore);if(typeof module==='object')module.exports=api;else root.ImageProject=api;})(globalThis,C=>{
 'use strict';
 const library=d=>C.restore(JSON.stringify(d));
 function find(d,key){const rows=d.series.filter(s=>s.id===key||s.name===key);if(rows.length!==1)throw Error(rows.length?'Series name is ambiguous; use its ID':'Series not found');return rows[0];}
 function details(s){return {id:s.id,name:s.name,revision:s.revision,style:s.style,world:s.world,ratio:s.ratio,model_id:s.model,useDate:!!s.useDate,currentDate:s.useDate?new Date().toLocaleDateString('sv-SE'):null,location:s.location,characters:s.characters.map(c=>({id:c.id,name:c.name,description:c.description,ready:!!(c.approved&&c.assetId)})),recent:s.episodes.slice(-20).map(e=>({id:e.id,title:e.title,summary:e.summary||e.panels.map(p=>p.scene).join(' '),status:e.status})),panel_count:s.draft?.panels.length||4,previous:s.draft?.previous??2};}
 function query({draft,args}){const d=library(draft);if(args.series)return {series:details(find(d,args.series))};return {items:d.series.map(s=>({id:s.id,name:s.name,revision:s.revision,style:s.style,ratio:s.ratio,episode_count:s.episodes.length}))};}
 function prepare({draft,args,catalog}){const d=library(draft),s=C.clone(find(d,args.series_id));if(d.pending)throw Error('A foreground task is still pending; inspect it before starting another episode');
  if(s.revision!==args.series_revision)throw Error('Series changed; query it again');
  const model=args.model_id||s.model||catalog.preferred,m=catalog.items.find(x=>x.id===model&&x.ready);if(!m)throw Error('Series drawing model is unavailable; no substitute selected');
  const e=C.parseScript(JSON.stringify({title:args.title,summary:args.summary||'',panels:args.panels}),s,args.panels.length);
  e.ratioOverride=args.ratio||'';e.ratio=e.ratioOverride||s.ratio;e.previous=args.previous??s.draft?.previous??2;e.status='draft';s.model=model;
  const plan=C.compile(s,e,{referenceLimit:Math.min(4,m.referenceLimit),previous:e.previous,columns:args.columns??2});
  plan.quality=m.qualities.includes('auto')?'auto':m.qualities[0];plan.resource_key=s.id;
  return {plan,episode:e,identity:{id:s.id,name:s.name,revision:s.revision,episode_id:e.id}};
 }
 function commit({draft,prepared,result}){const d=library(draft),s=find(d,prepared.identity.id),e=C.clone(prepared.episode),ids=result.result?.assetIds;
  if(!Array.isArray(ids)||ids.length!==e.panels.length||ids.some(id=>!/^[0-9a-f]{32}$/.test(id)))throw Error('Generated panel receipt is incomplete');
  if(s.episodes.some(x=>x.id===e.id))return d;
  e.assetIds=ids;e.status='completed';e.runId=result.studio_run_id;e.output=result.files;e.completedAt=new Date().toISOString();
  s.episodes.push(e);s.revision++;return d;
 }
 return {query,prepare,commit};
});
