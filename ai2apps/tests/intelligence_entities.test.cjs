const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const script=fs.readFileSync(__dirname+'/../web/static/js/intelligence_entities.js','utf8');
function setup(api,confirm=()=>false){const env={confirm,window:{},document:{querySelector:()=>null},Date,Set,FormData};vm.createContext(env);vm.runInContext(script,env);let tab='entities';const opened=[];const root={innerHTML:'',querySelector:()=>null},detail={innerHTML:'',querySelector:()=>null};env.window.IntelligenceEntities.init({api,openOriginal:(...args)=>opened.push(args),detailRoot:()=>detail,state:()=>({channels:[{id:'c',name:'Football'}]}),tab:()=>tab,notice:()=>{},readArticle:()=>{}});return {ui:env.window.IntelligenceEntities,root,detail,opened,setTab:t=>tab=t};}
const entity={id:'e',kind:'organization',name:'<Club>',aliases:[],channel_ids:['c'],facts:[],watched:false};
const data={entities:[entity],opportunities:[],channel_taxonomies:{c:{categories:[{id:'clubs',name:'俱乐部'},{id:'players',name:'球员'}],default_id:'clubs',assignments:{e:'clubs'}}}};
test('AI-defined category controls default, ordering, filtering and escaping',async()=>{
 const {ui,root}=setup(async()=>data);await ui.render(root,'entities','c');
 assert(root.innerHTML.includes('俱乐部'));assert(root.innerHTML.includes('&lt;Club&gt;'));assert(!root.innerHTML.includes('data-entity-category="all"'));
 assert.equal((root.innerHTML.match(/data-entity-category=/g)||[]).length,1);
 await root.onclick({target:{closest:()=>({dataset:{},hasAttribute:key=>key==='data-entity-expand'})}});
 assert(root.innerHTML.indexOf('data-entity-category="clubs"')<root.innerHTML.indexOf('data-entity-category="players"'));
 await root.onclick({target:{closest:()=>({dataset:{entityCategory:'players'},hasAttribute:()=>false})}});
 assert(!root.innerHTML.includes('&lt;Club&gt;'));assert.equal((root.innerHTML.match(/data-entity-category=/g)||[]).length,1);
 await ui.render(root,'entities','x');await ui.render(root,'entities','c');assert(root.innerHTML.includes('data-entity-category="players" aria-pressed="true"'));
});
test('legacy channel requests AI planning without inventing fixed categories',async()=>{
 const {ui,root}=setup(async()=>({entities:[entity],opportunities:[]}));await ui.render(root,'entities','c');
 assert(root.innerHTML.includes('尚未规划实体分类'));assert(!root.innerHTML.includes('data-entity-category="model"'));
});
test('late response does not overwrite articles',async()=>{
 let resolve;const {ui,root,setTab}=setup(()=>new Promise(r=>resolve=r));const task=ui.render(root,'entities','c');setTab('articles');root.innerHTML='Article list';resolve(data);await task;assert.equal(root.innerHTML,'Article list');
});

test('dismiss requires confirmation; cancel sends no mutation and detail control is not a submit',async()=>{
 let mutations=0,accept=false,prompt='';
 const {ui,root,detail}=setup(async(path,method)=>{if(method==='POST')mutations++;return data;},text=>{prompt=text;return accept;});
 await ui.render(root,'entities','c');
 const click=dataset=>root.onclick({target:{closest:()=>({dataset,hasAttribute:()=>false})}});
 await click({entityOpen:'e'});
 assert(detail.innerHTML.includes('class="intel-entity-preferences"'));
 assert(detail.innerHTML.includes('type="button" data-entity-dismiss="e"'));
 await click({entityDismiss:'e'});assert.equal(mutations,0);assert(prompt.includes('<Club>'));assert(prompt.includes('所有频道'));assert(prompt.includes('已忽略'));
 accept=true;await click({entityDismiss:'e'});assert.equal(mutations,1);
});

test('entity image controls show provenance and cancel removal without mutation',async()=>{
 const image={id:'photo',url:'https://example.com/a.jpg',article_id:'a',article_title:'Source <title>'};
 let mutations=0,accept=false;
 const result={...data,entities:[{...entity,images:[image],cover_image:image}]};
 const {ui,root,detail}=setup(async(path,method)=>{if(method)mutations++;return result;},()=>accept);
 const click=dataset=>root.onclick({target:{closest:()=>({dataset,hasAttribute:()=>false})}});
 await ui.render(root,'entities','c');assert(root.innerHTML.includes('intel-entity-cover'));
 await click({entityOpen:'e'});assert(detail.innerHTML.includes('Source &lt;title&gt;'));
 assert(detail.innerHTML.includes('当前封面'));
 await click({entityImageRemove:'photo'});assert.equal(mutations,0);
 accept=true;await click({entityImageRemove:'photo'});assert.equal(mutations,1);
});

test('entity opens in sidebar and preserves list',async()=>{
 const {ui,root,detail}=setup(async()=>data);
 await ui.render(root,'entities','c');
 await root.onclick({target:{closest:()=>({dataset:{entityOpen:'e'},hasAttribute:()=>false})}});
 assert(root.innerHTML.includes('data-entity-open="e"'));
 assert(root.innerHTML.includes('intel-entity-selected'));
 assert(!root.innerHTML.includes('entity-settings'));
 assert(detail.innerHTML.includes('entity-settings'));
 assert(!detail.innerHTML.includes('data-entity-back'));
 assert.equal(typeof detail.onclick,'function');assert.equal(typeof detail.onsubmit,'function');
 await ui.render(root,'entities','other');assert.equal(detail.innerHTML,'');
});

test('incidental and unreviewed entities stay out of the default list',async()=>{
 for(const dossier_status of ['mention','pending']){
  const {ui,root}=setup(async()=>({...data,entities:[{...entity,dossier_status}]}));
  await ui.render(root,'entities','c');assert(!root.innerHTML.includes('data-entity-open="e"'));
 }
});

test('related articles include text-only evidence and open originals through host',async()=>{
 const fact={article_id:'a',article_title:'Text-only article',observed_at:'2026-01-01',sources:[{url:'https://example.com/original'}]};
 const {ui,root,detail,opened}=setup(async()=>({...data,entities:[{...entity,facts:[fact,{...fact,id:'second'}]}]}));
 await ui.render(root,'entities','c');
 await root.onclick({target:{closest:()=>({dataset:{entityOpen:'e'},hasAttribute:()=>false})}});
 assert.equal((detail.innerHTML.match(/data-entity-original="a"/g)||[]).length,1);
 await detail.onclick({target:{closest:()=>({dataset:{entityOriginal:'a'},hasAttribute:()=>false})}});
 assert.equal(opened[0][0],'a');
});
