/* Reuses compiled WebAgent generations; all DOM work stays in the shared BiDi client. */
(() => {
'use strict';
const lt=window.IntelligenceI18n?.text||(s=>s),it=window.IntelligenceI18n?.template||((parts,...values)=>parts.reduce((s,p,i)=>s+p+(i<values.length?values[i]:''),''));
class IntelligenceSiteAgents {
 constructor({api,source,client}){this.api=api;this.source=source;this.client=client;this.recipes={};this.attempted=new Set();this.stats={reused:0,learned:0,fallback:0,learning_calls:0,extraction_ms:0};}
 endpoint(path){return '/sources/'+this.source.id+'/site-agent/'+path;}
 async load(){for(const kind of ['list','article']){try{this.recipes[kind]=(await this.api(this.endpoint(kind))).recipe;}catch(_){this.recipes[kind]=null;}}}
 rule(kind){return this.recipes[kind]?.ir?.steps?.[0]?.arguments?.site_extraction;}
 async invalidate(kind){const old=this.recipes[kind];this.recipes[kind]=null;this.stats.fallback++;
  if(old)await this.api(this.endpoint('invalidate'),'POST',{kind,generation_id:old.generation_id}).catch(()=>{});
 }
 async list(generic){
  const started=performance.now();
  try{
   if(this.recipes.list){try{const result=await this.client.executeExtractionStep(this.recipes.list.ir.steps[0]);this.stats.reused++;return result.items;}catch(_){await this.invalidate('list');}}
   const items=await generic();if(items.length)await this.learn('list',{items});return items;
  }finally{this.stats.extraction_ms+=Math.round(performance.now()-started);}
 }
 async article(page){
  if(this.recipes.article){if(page.extraction_method==='compiled-site-agent')this.stats.reused++;
   else if(page.extraction_fallback)await this.invalidate('article');}
  if(!this.recipes.article)await this.learn('article',page);
 }
 async learn(kind,baseline){
  if(this.attempted.has(kind))return;this.attempted.add(kind);
  try{
   const observation=await this.client.observeExtractionRegions(kind,kind==='list'?baseline.items.map(i=>i.url):[]);if(!observation.regions.length)return;
   this.stats.learning_calls++;
   const candidate=await this.api(this.endpoint('learn'),'POST',{kind,...observation});
   const result=await this.client.executeExtractionStep(candidate.ir.steps[0]);
   let samples,matched;
   if(kind==='list'){
    const urls=new Set(baseline.items.map(i=>i.url));const sample=result.items.slice(0,10);
    samples=sample.length;matched=sample.filter(i=>urls.has(i.url)).length;
    if(matched<Math.min(2,samples)||matched/samples<.6)throw Error('list_validation_failed');
   }else{
    const normalize=s=>String(s).replace(/\s+/g,'');const expected=normalize(baseline.text),actual=normalize(result.text);
    const excerpts=[0,.25,.5].map(n=>expected.slice(Math.floor(expected.length*n),Math.floor(expected.length*n)+50));
    samples=excerpts.length;matched=excerpts.filter(s=>s.length&&actual.includes(s)).length;
    if(actual.length<Math.min(expected.length*.6,500)||matched<2)throw Error('body_validation_failed');
   }
   this.recipes[kind]=await this.api(this.endpoint('activate'),'POST',{generation_id:candidate.generation_id,samples,matched});this.stats.learned++;
  }catch(error){this.stats.fallback++;this.lastFailure=String(error.message||error).slice(0,100);}
 }
 summary(){return it`WebAgent：复用 ${this.stats.reused} 次，学习 ${this.stats.learned} 条规则，回退 ${this.stats.fallback} 次，学习请求 ${this.stats.learning_calls} 次${this.lastFailure?'（'+this.lastFailure+'）':''}`;}
}
window.IntelligenceSiteAgents=IntelligenceSiteAgents;
})();
