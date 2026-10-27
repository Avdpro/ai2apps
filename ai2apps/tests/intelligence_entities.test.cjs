const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const script=fs.readFileSync(__dirname+'/../web/static/js/intelligence_entities.js','utf8');
function setup(api,confirm=()=>false,mobile=false){const env={URL,confirm,window:{AI2APPS_MOBILE_SURFACE:mobile},document:{querySelector:()=>null},Date,Set,FormData};vm.createContext(env);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/intelligence_cards.js','utf8'),env);vm.runInContext(script,env);let tab='entities';const opened=[];const root={innerHTML:'',querySelector:()=>null},detail={innerHTML:'',querySelector:()=>null};env.window.IntelligenceEntities.init({api,openOriginal:(...args)=>opened.push(args),detailRoot:()=>detail,state:()=>({channels:[{id:'c',name:'Football'}]}),tab:()=>tab,notice:()=>{},readArticle:()=>{}});return {ui:env.window.IntelligenceEntities,root,detail,opened,setTab:t=>tab=t};}
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
test('entity attributes show separate values with exact escaped evidence and article links',async()=>{
 const enriched={...entity,attribute_groups:[{key:'case_thickness',domain:'watch',conflicting:true,values:[{value:'12.98 mm',conditions:'',basis:'stated',status:'reported',historical:false,evidence:[{article_id:'a1',article_title:'First report',quote:'Thickness 12.98 mm <script>',observed_at:'2026-10-15'},{article_id:'a2',article_title:'Second report',quote:'Thickness 12.98 mm',observed_at:'2026-10-15'}]},{value:'13.1 mm',conditions:'',basis:'stated',status:'reported',historical:false,evidence:[{article_id:'a3',article_title:'Third report',quote:'Thickness 13.1 mm',observed_at:'2026-10-15'}]}]}]};
 const {ui,root,detail}=setup(async()=>({...data,entities:[enriched]}));await ui.render(root,'entities','c');
 await root.onclick({target:{closest:()=>({dataset:{entityOpen:'e'},hasAttribute:()=>false})}});
 assert.match(detail.innerHTML,/data-entity-attributes/);assert.match(detail.innerHTML,/存在不同说法/);
 assert.match(detail.innerHTML,/12\.98 mm/);assert.match(detail.innerHTML,/13\.1 mm/);
 assert.match(detail.innerHTML,/&lt;script&gt;/);assert.match(detail.innerHTML,/data-entity-article="a1"/);assert.match(detail.innerHTML,/data-entity-article="a2"/);
});
test('article footer lists entity parameters and scopes evidence without repeating requests',async()=>{
 let calls=0,resolve;const promise=new Promise(r=>resolve=r);
 const {ui}=setup(async()=>{calls++;return promise;});
 const target={dataset:{},isConnected:true,innerHTML:''},article={id:'a',updated_at:'v1'};
 ui.renderArticle(target,article);ui.renderArticle(target,article);assert.equal(calls,1);
 resolve({items:[{id:'e',name:'Watch <X>',kind:'model',coverage:'substantive',attribute_groups:[{key:'case_thickness',conflicting:false,values:[{value:'11mm',basis:'stated',conditions:'',status:'reported',evidence:[{article_id:'a',article_title:'This article',quote:'Case is 11mm thick.',historical:false}]},{value:'12mm',basis:'measured',conditions:'',status:'reported',evidence:[{article_id:'b',article_title:'Other article',quote:'Measured 12mm.',historical:false}]}]}]}]});
 await promise;await new Promise(r=>setImmediate(r));
 assert.match(target.innerHTML,/Watch &lt;X&gt;/);assert.match(target.innerHTML,/11mm/);assert.match(target.innerHTML,/本文证据/);assert.match(target.innerHTML,/其它文章证据/);assert.match(target.innerHTML,/data-article="b"/);
 const first=target.innerHTML;ui.renderArticle(target,article);assert.equal(calls,1);assert.equal(target.innerHTML,first);
});
test('late article entity response cannot overwrite a newly selected article',async()=>{
 const pending={};const {ui}=setup(url=>new Promise(resolve=>pending[url]=resolve));
 const target={dataset:{},isConnected:true,innerHTML:''};
 ui.renderArticle(target,{id:'a',updated_at:'v1'});ui.renderArticle(target,{id:'b',updated_at:'v1'});
 pending['/articles/b/entities']({items:[]});await new Promise(r=>setImmediate(r));const latest=target.innerHTML;
 pending['/articles/a/entities']({items:[{id:'e',name:'Old article entity',kind:'model',coverage:'mention',attribute_groups:[]}]});await new Promise(r=>setImmediate(r));
 assert.equal(target.innerHTML,latest);assert.doesNotMatch(target.innerHTML,/Old article entity/);
});

test('article entity types distinguish watch and AI models and omit inapplicable empty parameters',async()=>{
 const items=[{name:'Onyx',kind:'model',attribute_domain:'watch'},{name:'LLM',kind:'model',attribute_domain:'ai_model'},{name:'Brand',kind:'brand'},{name:'Person',kind:'person'}].map(e=>({...e,attribute_groups:[]}));
 const {ui}=setup(async()=>({items}));const target={dataset:{},isConnected:true};
 ui.renderArticle(target,{id:'a'});await new Promise(r=>setImmediate(r));
 assert.doesNotMatch(target.innerHTML,/腕表型号|AI 模型/);assert.equal((target.innerHTML.match(/<small>型号/g)||[]).length,2);
 assert.equal((target.innerHTML.match(/尚未提取参数/g)||[]).length,2);
});

test('article parameters display extensible field labels safely',async()=>{
 const {ui}=setup(async()=>({items:[{id:'car',name:'Car A',kind:'model',attribute_domain:'automotive',attribute_groups:[{key:'turning_radius',label:'Turning radius <script>',values:[{value:'5.4 m',basis:'stated',evidence:[{article_id:'a',quote:'Turning radius is 5.4 m.'}]}]}]}]}));
 const target={dataset:{},isConnected:true};ui.renderArticle(target,{id:'a'});await new Promise(r=>setImmediate(r));
 assert.match(target.innerHTML,/Turning radius &lt;script&gt;/);assert.match(target.innerHTML,/5\.4 m/);
 assert.doesNotMatch(target.innerHTML,/AI 模型/);
});

test('Mobile entity original links stay on the phone, with no Desktop launch control',async()=>{
 const fact={article_id:'a',article_title:'Original article',sources:[{url:'https://example.com/one',source_name:'One'},{url:'https://example.com/two',source_name:'Two'}]};
 const {ui,root,detail,opened}=setup(async()=>({...data,entities:[{...entity,facts:[fact]}]}),()=>false,true);
 await ui.render(root,'entities','c');
 await root.onclick({target:{closest:()=>({dataset:{entityOpen:'e'},hasAttribute:()=>false})}});
 assert.equal((detail.innerHTML.match(/target="_blank" rel="noopener noreferrer"/g)||[]).length,3);
 assert.match(detail.innerHTML,/href="https:\/\/example.com\/one"/);
 assert.match(detail.innerHTML,/href="https:\/\/example.com\/two"/);
 assert(!detail.innerHTML.includes('data-entity-original='));assert.equal(opened.length,0);
});

test('legacy after-collection hook refreshes dossiers without starting model work',async()=>{
 const requests=[];
 const {ui}=setup(async(path,method='GET')=>{requests.push({path,method});return data;});
 await ui.afterCollection('c');
 assert.deepEqual(requests,[{path:'/entities',method:'GET'}]);
});
