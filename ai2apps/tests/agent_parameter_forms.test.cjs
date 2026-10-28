const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_parameter_forms.js','utf8').replace('window.AI2AppsParameterForms=','window.FormView=FormView;window.AI2AppsParameterForms=');
function setup(fetch){const ctx={window:{},document:{documentElement:{lang:'zh'}},fetch,console,setTimeout,clearTimeout};vm.runInNewContext(source,ctx);return ctx;}
test('new search preparation discards an inherited confirmation receipt',async()=>{
 const writes=[];const ctx=setup(async()=>({ok:true,json:async()=>({id:'new-prep',status:'completed',query:'回锅肉',limit:5,sources:['google','bilibili']})}));
 const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{url:'/form',state:{revision:0},values:{confirmation_id:'old-confirmation'},save:async()=>writes.push(JSON.parse(JSON.stringify(f.values))),render(){}});
 await f.prepareSearch();assert.ok(writes.every(v=>!('confirmation_id' in v)));assert.equal(f.values.preparation_id,'new-prep');assert.equal(f.values.preparation_ready,true);
});
test('draft writes serialize revisions and snapshot edits',async()=>{
 const bodies=[];const ctx=setup(async(url,opts)=>{const b=JSON.parse(opts.body);bodies.push(b);return {ok:true,json:async()=>({revision:b.revision+1})};});
 const form=Object.create(ctx.window.FormView.prototype);Object.assign(form,{values:{language:'zh'},state:{revision:0},url:'/form',chain:Promise.resolve()});
 const a=form.save();form.values.language='en';const b=form.save();await Promise.all([a,b]);
 assert.deepEqual(bodies,[{revision:0,values:{language:'zh'}},{revision:1,values:{language:'en'}}]);
});
test('install saves then creates an owner-bound configuration card without switching Apps',async()=>{
 const calls=[];const ctx=setup();ctx.window.ai2appsShell={openSetup:()=>assert.fail('stay in Chat')};ctx.window.AI2AppsCapabilities={runSession(){}};
 const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{url:'/form',state:{install:{appId:'fixture.owner'}},save:async()=>calls.push('save'),request:async(url,options)=>{calls.push([url,options.method]);return {session:{id:'configured'}};},showSetup:async session=>calls.push(session.id)});await f.install();assert.equal(calls[0],'save');assert.deepEqual(calls[1],['/form/setup/session','POST']);assert.equal(calls[2],'configured');
});
test('Mobile keeps draft and explains Desktop setup; re-opening Chat does not run ACPF',async()=>{
 const ctx=setup();ctx.window.AI2APPS_MOBILE_SURFACE=true;ctx.window.AI2AppsCapabilities={ensure:()=>assert.fail(),resume:()=>assert.fail()};ctx.window.ai2appsShell={openSetup:()=>assert.fail()};
 const f=Object.create(ctx.window.FormView.prototype);let saved=false;Object.assign(f,{state:{install:{appId:'fixture'}},save:async()=>saved=true,errorNode:{}});await f.install();assert.ok(saved);assert.match(f.errorNode.textContent,/Desktop/);await f.resume();
});
test('both parent and delegated child render structured form within interaction scope',()=>{
 const chat=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');for(const who of ['run','child']) {const start=chat.indexOf(`interaction in pendingAgentInteractions(${who})`);const end=chat.indexOf("interaction.kind === 'menu'",start);assert.ok(chat.slice(start,end).includes(`mount($el, ${who}, interaction`));}
});
test('ordinary Chat voice resume cannot consume parameter-form sessions',()=>{
 const chat=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
 const start=chat.indexOf('async resumeAudioCapabilitySetups()');
 assert.match(chat.slice(start,start+1000),/capability: spec\.capability, actionId: spec\.actionId/);
});
test('Gallery drops import an owned asset and save the resulting ID',async()=>{
 const requests=[];const ctx=setup(async(url,options)=>{requests.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({asset:{id:'private-audio',name:'sample.wav'}})};});
 const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{url:'/form',values:{},perform:fn=>fn(),save:async()=>requests.push('save'),render:()=>requests.push('render')});
 await f.drop({preventDefault(){},dataTransfer:{files:[],getData:type=>type==='application/x-ai2apps-gallery-asset'?'gallery-audio':''}});
 assert.deepEqual(requests,[['/form/gallery',{asset_id:'gallery-audio'}],'save','render']);assert.equal(f.values.audio,'private-audio');
});
test('Finder drops use the same upload and draft path',async()=>{
 const ctx=setup();const file={name:'finder.wav'};let uploaded;
 const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{perform:fn=>fn(),audio:async value=>uploaded=value});
 await f.drop({preventDefault(){},dataTransfer:{files:[file]}});assert.equal(uploaded,file);
});
test('stopping recording disposes microphone and uploads captured audio',async()=>{
 const ctx=setup();ctx.File=class {constructor(parts,name,options){this.parts=parts;this.name=name;this.type=options.type;}};
 const body={type:'audio/webm'};let disposed=false,uploaded;
 const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{recorder:{stop:async()=>({body,name:'recording.webm'}),dispose:()=>disposed=true},audio:async file=>uploaded=file});
 await f.record();assert.equal(f.recorder,null);assert.ok(disposed);assert.equal(uploaded.parts[0],body);assert.equal(uploaded.name,'recording.webm');
});
test('sidebar-only Gallery Mini-Entry is mounted in its declared placement',async()=>{
 const chat=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');const start=chat.indexOf('async mountMiniApp(');const end=chat.indexOf('async openKnowledgeSidebar()',start);
 let request;const ctx={window:{ai2appsShell:{mountMiniEntry:async value=>{request=value;return value;}}}};
 vm.runInNewContext('handler=({'+chat.slice(start,end)+'}).mountMiniApp',ctx);
 await ctx.handler.call({latestUserMessageId:()=> 'msg1',currentChatId:'ses1',attachMiniEntry(){}},{app_key:'ai2apps.gallery',mini_entry:{placements:['sidebar']}},'inline');
 assert.equal(request.placement,'sidebar');assert.equal(request.sessionId,'ses1');
});
test('material arrays preserve order, deduplicate and enforce slot capacity',async()=>{
 const ctx=setup();const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{values:{refs:['art_first']},save:async()=>{},loadMaterials:async()=>{},render(){}});
 await f.addMaterials({key:'refs',multiple:true,maxItems:2},[{id:'art_second'},{id:'art_first'}]);
 assert.equal(JSON.stringify(f.values.refs),'["art_first","art_second"]');
 await assert.rejects(()=>f.addMaterials({key:'refs',multiple:true,maxItems:2},[{id:'art_third'}]));
 await f.addMaterials({key:'subject',multiple:false},[{id:'art_one'}]);
 await f.addMaterials({key:'subject',multiple:false},[{id:'art_two'}]);
 assert.equal(f.values.subject,'art_two');
 assert.equal(JSON.stringify(f.assetIds({key:'subject'})),'["art_two"]');
});
test('form identifies Tool Agent App Mini-App and declared material previews',()=>{
 for(const text of ["kind:'Tool'","kind:'Agent'","kind:'App'","kind:'Mini-App'",'renderIdentity(form)','this.artifactSlot(group,f)','Choose from Gallery','droppedAssetIds','materialPreview(asset)'])assert.ok(source.includes(text),text);
});
test('App continuation saves the draft before handoff and never submits generation',async()=>{
 const calls=[];const ctx=setup(async(url,options)=>{calls.push(url);return {ok:true,json:async()=>({})};});
 ctx.window.ai2appsShell={openHandoff:async(...args)=>calls.push(args)};
 const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{url:'/form',run:{id:'r'},item:{id:'i'},state:{revision:7},values:{prompt:'keep'},save:async()=>calls.push('save'),render:()=>calls.push('render')});
 await f.continueInApp();assert.equal(f.state.waiting_app,true);
 assert.deepEqual(calls,['save','/form/handoff','render',['r','i',false]]);
 calls.length=0;await f.continueInApp();assert.deepEqual(calls,[['r','i',false]]);
});
test('switching saves first then refreshes the Provider schema',async()=>{
 const calls=[];const ctx=setup(async(url,options)=>{calls.push([url,JSON.parse(options.body)]);return {ok:true,json:async()=>({})};});
 const f=Object.create(ctx.window.FormView.prototype);Object.assign(f,{url:'/form',state:{revision:2},save:async()=>calls.push('save'),refreshForm:async()=>calls.push('refresh')});
 await f.switchProvider('other');assert.deepEqual(calls,['save',['/form/switch',{revision:2,provider:'other'}],'refresh']);
});
test('material filenames expose full text on hover and keyboard focus without native title',()=>{
 const ctx=setup();const elements=[];
 ctx.window.innerWidth=360;
 ctx.document.createElement=tag=>{const el={tagName:tag.toUpperCase(),style:{},children:[],attributes:{},hidden:false,open:false,setAttribute(key,value){this.attributes[key]=value;},append(...items){this.children.push(...items);},getBoundingClientRect(){return this.attributes.role==='tooltip'?{width:250,height:48}:{left:300,top:120};},showPopover(){this.open=true;},hidePopover(){this.open=false;},matches(){return this.open;}};elements.push(el);return el;};
 const filename='a-very-long-original-material-name-that-must-be-readable.png';
 const card=Object.create(ctx.window.FormView.prototype).materialPreview({id:'asset',name:filename,media_type:'image/png',preview_url:'/preview'});
 const [image,name,tip]=card.children;
 assert.match(card.style.cssText,/width:132px/);assert.match(image.style.cssText,/height:108px/);
 assert.equal(name.title,undefined);assert.equal(tip.textContent,filename);assert.equal(tip.hidden,true);
 name.onmouseenter();assert.equal(tip.open,true);assert.equal(tip.hidden,false);assert.equal(tip.style.left,'102px');assert.equal(tip.style.top,'66px');
 name.onmouseleave();assert.equal(tip.open,false);assert.equal(tip.hidden,true);
 name.onfocus();assert.equal(tip.open,true);name.onkeydown({key:'Escape'});assert.equal(tip.hidden,true);
 name.onfocus();name.onblur();assert.equal(tip.open,false);
});
test('form explains declared target, required fields and confirmation before editing',()=>{
 const ctx=setup();ctx.document.createElement=()=>({style:{}});
 const view=Object.create(ctx.window.FormView.prototype);
 view.identity=[{kind:'App',name:'Example App'},{kind:'Mini-App',name:'Example action'}];
 view.state={descriptor:{capability:'arbitrary.action',fields:[{key:'title',label:'项目标题'}]},missing:['title'],invalid:[]};
 let explanation;view.renderExplanation({append:value=>explanation=value});
 assert.ok(explanation.textContent.includes('Example App / Example action'));
 assert.ok(explanation.textContent.includes('请补充或修正：项目标题'));
 assert.ok(explanation.textContent.includes('取消则不会执行'));
 view.state.missing=[];view.renderExplanation({append:value=>explanation=value});
 assert.ok(explanation.textContent.includes('调用参数已预填，请检查并按需调整'));
});

test('record quantity edits preserve nested draft snapshots while saves serialize',async()=>{
 const bodies=[];const ctx=setup(async(url,opts)=>{const b=JSON.parse(opts.body);bodies.push(b);return {ok:true,json:async()=>({revision:b.revision+1})};});
 const form=Object.create(ctx.window.FormView.prototype);Object.assign(form,{values:{rows:[{key:'one',count:2}]},state:{revision:0},url:'/form',chain:Promise.resolve()});
 const first=form.save();form.values.rows[0].count=3;const second=form.save();await Promise.all([first,second]);
 assert.deepEqual(bodies.map(b=>b.values.rows[0].count),[2,3]);
});

test('approval titles localize existing records without expanding tool authority',()=>{const ctx=setup();const prompt=ctx.window.AI2AppsParameterForms.prompt;assert.equal(prompt({kind:'approval',request:{tool_name:'fixture.alpha.read'},prompt:'Old English prompt'}),'允许调用工具 fixture.alpha.read？');ctx.document.documentElement.lang='fr';assert.equal(prompt({kind:'approval',request:{tool_name:'fixture.beta.read'}}),'Allow tool fixture.beta.read?');});

test('waiting capability card uses the localized pending approval title',()=>{
 const html=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
 const method=html.slice(html.indexOf('    agentStatusView(run) {'),html.indexOf('    agentStatusText(view) {'));
 const ctx=setup();const view=vm.runInNewContext('({'+method+'})',{window:ctx.window,document:ctx.document,agentStatusRenderers:{resolve:line=>({...line,effect:'none'})}});
 const result=view.agentStatusView({status:'waiting_capability',status_line:{text:'Old English'},interactions:[{status:'pending',kind:'approval',ui_hints:{control:'approval'},request:{tool_name:'fixture.alpha.read'}}]});
 assert.equal(result.text,'允许调用工具 fixture.alpha.read？');
});
test('configuration return releases the old mount before restoring the conversation',()=>{
 const ctx=setup();ctx.window.AI2AppsParameterForms.release('not-mounted');
 const chat=fs.readFileSync(__dirname+'/../web/templates/chat.html','utf8');
 const start=chat.indexOf("if(intent.kind==='capability_setup')");
 const code=chat.slice(start,chat.indexOf('return;}',start));
 assert.ok(code.indexOf('release(intent.interactionId)')<code.indexOf('loadChat(intent.sessionId)'));
 assert.ok(!code.includes('submitAgentInteraction'));
});
test('Mobile reference material slot delegates bounded upload without multipart body',async()=>{
 const ctx=setup();ctx.window.AI2APPS_MOBILE_SURFACE=true;
 const f=Object.create(ctx.window.FormView.prototype),file={name:'video.mp4',size:3*1024**3};let selected;
 Object.assign(f,{run:{id:'r',session_id:'s'},values:{},request:()=>assert.fail('must not multipart the video'),
  uploadMaterial:async(source,run)=>{assert.equal(source,file);assert.equal(run.session_id,'s');return {id:'attc_ref'};},
  addMaterials:async(field,assets)=>selected=assets});
 await f.importMaterials({key:'input',references:true},{files:[file]});assert.equal(selected[0].id,'attc_ref');
});
test('file picker retains the busy guard without disabling the input or uploading before selection',()=>{
 const ctx=setup();ctx.document.createElement=()=>({});let cancelled=0,clicked=0;
 const f=Object.create(ctx.window.FormView.prototype),input={disabled:false,click(){assert.equal(this.disabled,false);clicked++;}};
 Object.assign(f,{inputs:[input],busy:false,cancelAutoSubmit(){cancelled++;},perform(){assert.fail('opening a picker must not enter the upload lock');}});
 const button=f.filePickerButton('Upload material',input);button.onclick();assert.equal(clicked,1);assert.equal(f.busy,false);
 f.busy=true;button.onclick();assert.equal(clicked,1);assert.equal(cancelled,2);
});
