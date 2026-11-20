const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),{chromium}=require('playwright');
const source=name=>fs.readFileSync(__dirname+'/../web/static/js/'+name+'.js','utf8');
const mounts={todo:['function mountTodoAppState(){','safe(async()=>{await refresh(true);'],intelligence:['function mountIntelligenceAppState(){','safe(async()=>{observeCollections();'],mobile_todo:['    function mountTodoAppState(){',"    for(const id of ['directory','show-completed'])"]};
for(const width of [1280,390])for(const kind of ['gallery','knowledge','todo','intelligence','mobile_todo'])test(kind+' restores declared view through shared panel at '+width,async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
 const page=await browser.newPage({viewport:{width,height:844}});
 await page.route('https://core-state.fixture/**',route=>route.fulfill({contentType:'text/html',body:'<html lang="en"><div id="root"><button id="presets">Presets</button><button id="todo-state-presets"></button><button id="intel-state-presets"></button><select id="directory"><option value="first">First</option><option value="second">Second</option></select><input id="article-filter" value="unread"><input id="article-type-filter" value="all"><input id="search-articles"><input id="channel-chat-question"></div></html>'}));
 await page.goto('https://core-state.fixture/#ai2apps-instance=fixture-instance');
 await page.addStyleTag({content:fs.readFileSync(__dirname+'/../web/static/css/app_state.css','utf8')});
 await page.evaluate(kind=>{
  const appId='ai2apps.'+(kind==='mobile_todo'?'todo':kind);window.saved=[];window.calls=[];window.writes=0;window.failRead=false;
  const fields={gallery:['collection_id','kind','view'],knowledge:['bucket_id','kind','view'],todo:['directory_id'],intelligence:['channel_id','tab','article_filter','article_type']};
  window.fetch=async(url,options={})=>{const body=options.body&&JSON.parse(options.body);calls.push({url,method:options.method||'GET',body});let v={};
   if(url.includes('/app-state/')){
    if(url.includes('/contract?'))v={contract_version:1,name:'View settings',contract_digest:'a'.repeat(64),schema:{properties:Object.fromEntries(fields[kind==='mobile_todo'?'todo':kind].map(k=>[k,{}]))}};
    else if(url.endsWith('/validate'))v={packet:body.packet,contract_digest:'a'.repeat(64)};
    else if(url.endsWith('/presets')&&options.method==='POST'){saved.push({name:body.name,packet:body.packet});v={id:'preset'};}
    else if(url.includes('/presets?'))v={items:saved};else if(url.endsWith('/applications'))v={id:'apply',status:'prepared'};else if(url.endsWith('/complete'))v={status:body.status};
   }else{
    if(options.method&&options.method!=='GET')writes++;
    if(url.endsWith('/collections')||url.endsWith('/buckets'))v={items:[{id:'first'},{id:'second'}]};
    else if(url.includes('/assets?')){if(failRead)throw Error('read failed');v={items:[{id:'asset'}]};}
    else if(url.includes('/items?')){if(failRead)throw Error('read failed');v={items:[]};}else v={items:[]};
   }
   return {ok:true,status:200,json:async()=>v};
  };
  window.base={loading:false,busy:false,$root:document.querySelector('#root'),$nextTick:async()=>{},fail(e){window.failure=e.message;}};
  window.kindUnderTest=kind;
 },kind);
 await page.addScriptTag({content:source('app_state')});
 if(kind==='gallery'||kind==='knowledge'){
  await page.addScriptTag({content:source(kind)});
  await page.evaluate(kind=>{
   window.owner=Object.assign(window[kind+'App'](),base);
   if(kind==='gallery')Object.assign(owner,{selectedCollectionId:'first',kind:'image',view:'grid',search:'PRIVATE QUERY',selectedIds:[],notifyActiveCollection(){}});
   else Object.assign(owner,{selectedBucketId:'first',kind:'note',view:'library',query:'',askInput:'PRIVATE DRAFT',draft:{text:'PRIVATE MATERIAL'}});
   owner.mountAppState();document.querySelector('#presets').onclick=()=>owner.openAppState();
  },kind);
 }else{
  await page.evaluate(kind=>{
   const root=document.querySelector('#root');root.id=kind==='todo'?'todo-app':kind==='intelligence'?'intel-app':'mobile-todo';
   Object.assign(window,{$:kind==='mobile_todo'?id=>document.getElementById(id):s=>document.querySelector(s),sdk:null,appStateBinding:null,zh:false,safe:f=>f,notice:()=>{},handoffText:(zh,en)=>en,mt:s=>s,mountParams:new URLSearchParams(location.hash.slice(1)),shellDetail:false,
    state:{directories:[{id:'first'},{id:'second'}]},data:{directories:[{id:'first'},{id:'second'}]},directoryId:'first',aggregateId:null,selectedId:null,dirty:false,busy:false,fieldSavePending:false,fieldSaveEpoch:0,reorderBusy:false,draftTask:null,chatController:null,searchQuery:'PRIVATE QUERY',current:null,
    channelId:'first',tab:'articles',sectionId:'',readerMode:'chat',mobilePanel:false,mobilePage:'channel',previewDraft:null,appHandoff:null,refreshInFlight:null,appStateRestoring:false,
    api:async()=>({directories:[{id:'first'},{id:'second'}],channels:[{id:'first'},{id:'second'}]}),renderDirectory(){},renderTree(){},renderDetail(){},render(){},progressiveData:()=>false});
  },kind);
  const [start,end]=mounts[kind],text=source(kind);assert(text.includes(start)&&text.includes(end));await page.addScriptTag({content:text.slice(text.indexOf(start),text.indexOf(end,text.indexOf(start)))});
  await page.evaluate(kind=>{if(kind==='intelligence')mountIntelligenceAppState();else mountTodoAppState();const b=document.querySelector(kind==='intelligence'?'#intel-state-presets':'#todo-state-presets');document.querySelector('#presets').onclick=()=>b.click();},kind);
 }
 await page.getByRole('button',{name:'Presets',exact:true}).click();await page.getByPlaceholder('Preset name').fill('First view');await page.getByRole('button',{name:'Save current settings',exact:true}).click();await page.getByRole('button',{name:'First view',exact:true}).waitFor();
 assert(!JSON.stringify(await page.evaluate(()=>saved)).includes('PRIVATE'));
 await page.evaluate(kind=>{if(kind==='gallery')owner.selectedCollectionId='second';else if(kind==='knowledge')owner.selectedBucketId='second';else if(kind==='todo')directoryId='second';else if(kind==='intelligence')channelId='second';else document.getElementById('directory').value='second';},kind);
 await page.getByRole('button',{name:'First view',exact:true}).click();
 if(kind==='gallery'||kind==='knowledge')await page.getByRole('button',{name:'Restore these settings',exact:true}).click();
 await page.waitForFunction(kind=>kind==='gallery'?owner.selectedCollectionId==='first':kind==='knowledge'?owner.selectedBucketId==='first':kind==='todo'?directoryId==='first':kind==='intelligence'?channelId==='first':document.getElementById('directory').value==='first',kind);
 assert.equal(await page.evaluate(()=>writes),0);assert.equal(await page.evaluate(()=>document.querySelector('#root,#todo-app,#intel-app,#mobile-todo').inert),false);
 if(kind==='gallery')assert.equal(await page.evaluate(()=>owner.search),'PRIVATE QUERY');
 if(kind==='knowledge')assert.equal(await page.evaluate(()=>owner.draft.text),'PRIVATE MATERIAL');
 if(kind==='gallery'||kind==='knowledge'){
  await page.evaluate(kind=>{failRead=true;if(kind==='gallery')owner.selectedCollectionId='second';else owner.selectedBucketId='second';},kind);
  await page.getByRole('button',{name:'First view',exact:true}).click();await page.getByRole('button',{name:'Restore these settings',exact:true}).click();await page.getByText('read failed',{exact:true}).waitFor();
  assert.equal(await page.evaluate(kind=>kind==='gallery'?owner.selectedCollectionId:owner.selectedBucketId,kind),'second');assert.equal(await page.evaluate(()=>owner.$root.inert),false);
  await page.evaluate(()=>{failRead=false;});
 }
 const before=await page.evaluate(()=>calls.filter(x=>x.url.endsWith('/applications')).length);
 await page.evaluate(kind=>{const f={gallery:'collection_id',knowledge:'bucket_id',todo:'directory_id',intelligence:'channel_id',mobile_todo:'directory_id'}[kind];saved[0].packet.values[f]='missing';},kind);
 await page.getByRole('button',{name:'First view',exact:true}).click();await page.getByText(/unavailable/).waitFor();assert.equal(await page.evaluate(()=>calls.filter(x=>x.url.endsWith('/applications')).length),before);
 }finally{await browser.close();}
});
