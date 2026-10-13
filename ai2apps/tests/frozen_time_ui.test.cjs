const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const web=path.resolve(__dirname,'../../packages/ai2apps-frozen-time/web');
test('model setup is hidden only when selected geometry and Meridian are ready, including rendering',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time.js'),'utf8');
 const fn=source.match(/ function state\(\)\{[^\n]+\}/)[0];
 const controls=Object.fromEntries(['slot','audio-slot','preview-motion','generate','setup','cancel','progress','mode','depth','amplitude','output','long_edge','seed','random-seed','reference-speedup','image','clear','audio','audio-clear'].map(id=>[id,{value:id==='depth'?'vggt':'orbit'}]));
 const state={run:null,motion:null,busy:false,image:null,soundtrack:null,preview:'',t:key=>key,ready:{meridian:true,depth:{vggt:true,da:false}},window:{frozenEditor:{lock(){},valid:()=>true}},conversionState(){},$:id=>controls[id]};
 vm.createContext(state);vm.runInContext(fn,state);state.state();assert.equal(controls.setup.hidden,true);
 state.run={status:'running'};state.state();assert.equal(controls.setup.hidden,true);assert.equal(controls.setup.disabled,true);
 state.run=null;controls.depth.value='da';state.state();assert.equal(controls.setup.hidden,false);assert.equal(controls.setup.disabled,false);
 controls.depth.value='vggt';state.ready.meridian=false;state.state();assert.equal(controls.setup.hidden,false);
 state.ready={};state.state();assert.equal(controls.setup.hidden,false);
});
test('named movements retain editable keys and restore independently of built-in presets',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time-editor.js'),'utf8');
 const restore=source.match(/ function restoreKeys\(value\)\{[^\n]+\}/)[0];
 const origin={pitch:0,yaw:0,roll:0,radius:1,blur:0,saturation:1,exposure:0,brightness:1};
 const ranges={pitch:[-20,20],yaw:[-20,20],roll:[-20,20],radius:[.6,1.4],blur:[0,12],saturation:[0,2],exposure:[-2,2],brightness:[0,2]};
 const controls={'curve-frames':{},'key-count':{},'return-origin':{}};
 const state={keys:[],selected:2,origin,ranges,structuredClone,snapTimes(){},$:id=>controls[id]};vm.createContext(state);vm.runInContext(restore,state);
 const draft={frames:90,return_origin:true,keys:[{...origin,t:0,yaw:-10,transition:'linear'},{...origin,t:44/89},{...origin,t:1,yaw:10,blur:2,transition:'smooth'}]};
 assert.equal(state.restoreKeys(JSON.stringify(draft)),true);assert.equal(controls['curve-frames'].value,90);assert.equal(state.keys[0].transition,'linear');assert.equal(state.keys[2].blur,2);
 assert.equal(state.keys[1].transition,'linear');assert.equal(state.keys[2].transition,'smooth');
 draft.keys[0].yaw=100;assert.equal(state.keys[0].yaw,-10);assert.equal(state.restoreKeys(draft),false);
 const nine={frames:73,return_origin:true,keys:Array.from({length:9},(_,i)=>({...origin,t:i/8,transition:i%2?'smooth':'linear'}))};
 assert.equal(state.restoreKeys(JSON.stringify(nine)),true);assert.equal(state.keys.length,9);assert.equal(controls['key-count'].value,9);
 for(const count of [11,13,15]){
  const saved={...nine,keys:Array.from({length:count},(_,i)=>({...origin,t:i/(count-1),transition:'linear'}))};
  assert.equal(state.restoreKeys(JSON.stringify(saved)),true);assert.equal(state.keys.length,count);assert.equal(controls['key-count'].value,count);
  assert.ok(source.includes(`<option>${count}</option>`));
 }
 assert.equal(state.restoreKeys({...nine,keys:Array.from({length:17},(_,i)=>({...origin,t:i/16}))}),false);
 assert.match(source,/<option>7<\/option><option>9<\/option>/);
 const main=fs.readFileSync(path.join(web,'frozen-time.js'),'utf8');assert.match(main,/motionPresets:window.frozenEditor.presets\(\)/);assert.ok(main.indexOf('restorePresets(draft.motionPresets)')<main.indexOf("for(const id of ['depth','mode'",main.indexOf('restorePresets(draft.motionPresets)')));
 assert.match(source,/createElement\('details'\)/);assert.ok(!source.includes('section.open=true'));
});
test('save movement uses selected name when blank and confirms named overwrites',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time-editor.js'),'utf8');
 assert.ok(!source.includes('preset-rename'));
 const fn=source.match(/ function savePreset\(\)\{[^\n]+\}/)[0];
 const controls={'preset-name':{value:''},mode:{value:'saved:one',selectedOptions:[{textContent:'Orbit'}]},'preset-status':{}};
 const original={id:'one',name:'My orbit',trajectory:{old:true}};
 let confirmed=false,prompts=0,events=0;
 const state={locked:false,valid:()=>true,savedPresets:[original],$:id=>controls[id],text:k=>k==='overwrite'?'Overwrite {name}?':k,presetMenu(){},crypto:{randomUUID:()=>`id-${events}`},Event,
 window:{confirm:()=>{prompts++;return confirmed;},frozenEditor:{serialize:()=>JSON.stringify({keys:[1,2,3]})},dispatchEvent:()=>events++}};
 vm.createContext(state);vm.runInContext(fn,state);
 state.savePreset();assert.equal(state.savedPresets.length,1);assert.deepEqual(Array.from(original.trajectory.keys),[1,2,3]);assert.equal(prompts,0);assert.equal(events,1);
 controls['preset-name'].value='MY ORBIT';state.savePreset();assert.equal(events,1);assert.equal(prompts,1);assert.equal(controls['preset-name'].value,'MY ORBIT');
 confirmed=true;state.savePreset();assert.equal(events,2);assert.equal(state.savedPresets.length,1);assert.equal(original.id,'one');
 controls.mode.value='orbit';controls['preset-name'].value='';state.savePreset();assert.equal(state.savedPresets.length,2);assert.equal(state.savedPresets[1].name,'Orbit');assert.equal(controls.mode.value,'saved:id-2');
 controls.mode.value='orbit';state.savePreset();assert.equal(state.savedPresets.length,2);assert.equal(prompts,3);
 controls['preset-name'].value='New action';state.savePreset();assert.equal(state.savedPresets.length,3);
 state.locked=true;controls['preset-name'].value='Locked';state.savePreset();assert.equal(state.savedPresets.length,3);
});
test('offline 3D camera uses geometry convention and source/export frame order',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time-scene.js'),'utf8');
 assert.ok(source.includes("$('curve-editor').before(panel)"));
 const math=source.slice(source.indexOf(' const sub='),source.indexOf(' function box('));
 const state={};vm.createContext(state);vm.runInContext(math,state);
 const pose=state.camera({yaw:0,pitch:0,roll:0,radius:1});assert.deepEqual(Array.from(state.project([0,0,5],pose)),[360,180,5]);
 const yaw=state.camera({yaw:10,pitch:0,roll:0,radius:1});assert.ok(yaw.eye[0]>0);assert.ok(Math.abs(state.project([0,0,5],yaw)[0]-360)<1e-9);
 const far=state.camera({yaw:0,pitch:0,roll:0,radius:1.2});assert.equal(state.project([1,0,5],far)[0],360+440/6);
 const fn=source.match(/ function plan\(\)\{[^\n]+\}/)[0];const payload={frames:[{},{}],playback:[0,1,0]};state.window={frozenEditor:{renderPlan:()=>JSON.stringify(payload)}};let output='mp4';state.$=()=>({value:output});vm.runInContext(fn,state);assert.equal(state.plan().order.length,3);output='html';assert.equal(state.plan().order.length,2);
 assert.ok(!source.includes('fetch('));assert.match(source,/if\(!panel.open\)stop\(\)/);assert.match(source,/document.hidden\)stop\(\)/);
});
test('Package computes render frames, poster and return playback independently of Host',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time-editor.js'),'utf8');
 const sample=source.match(/ function sample\(list,t\)\{[^\n]+\}/)[0];
 const render=source.match(/ function renderPlan\(\)\{[^\n]+\}/)[0];
 const origin={pitch:0,yaw:0,roll:0,radius:1,blur:0,saturation:1,exposure:0,brightness:1};
 const state={origin,keys:[{...origin,t:0,yaw:-10,transition:'linear'},{...origin,t:.5},{...origin,t:1,yaw:10}],steps:()=>72,atOrigin:k=>Object.keys(origin).every(f=>Math.abs(k[f]-origin[f])<1e-8),clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),$:()=>({checked:true}),text:()=>''};
 vm.createContext(state);vm.runInContext(sample+render,state);
 const data=JSON.parse(state.renderPlan());assert.equal(data.frames.length,73);assert.equal(data.frames[9].yaw,-7.5);assert.equal(data.playback.length,109);assert.equal(data.playback.at(-1),36);assert.equal(data.poster,36);
 state.keys[0].transition='smooth';assert.equal(JSON.parse(state.renderPlan()).frames[9].yaw,-8.4375);
});
test('all Package presets, amplitudes, key counts and supported frame budgets compile bounded plans',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time-editor.js'),'utf8');
 const fns=source.slice(source.indexOf(' function sample('),source.indexOf(' function valid('));
 const render=source.match(/ function renderPlan\(\)\{[^\n]+\}/)[0];
 const origin={pitch:0,yaw:0,roll:0,radius:1,blur:0,saturation:1,exposure:0,brightness:1};
 const controls={'mode':{value:'orbit'},amplitude:{value:'medium'},'key-count':{value:5},'return-origin':{checked:true}};
 let frames=73;
 const state={origin,keys:[],savedPresets:[],selected:0,steps:()=>frames-1,atOrigin:k=>Object.keys(origin).every(f=>Math.abs(k[f]-origin[f])<1e-8),clamp:(x,a,b)=>Math.max(a,Math.min(b,x)),draw(){},$:id=>controls[id],text:()=>''};
 vm.createContext(state);vm.runInContext(fns+render,state);
 for(const mode of ['orbit','arc','push-orbit','push-orbit2','vertical','diagonal','float'])for(const amp of ['small','medium','large'])for(const count of [3,5,7,9,11,13,15])for(const n of [73,90,107,124,141,158,175,243])for(const back of [true,false]){
  frames=n;controls.mode.value=mode;controls.amplitude.value=amp;controls['key-count'].value=count;controls['return-origin'].checked=back;state.preset();
  assert.equal(state.keys.length,count);assert.ok(state.keys.every(k=>k.transition==='linear'));
  const data=JSON.parse(state.renderPlan());assert.equal(data.frames.length,n);assert.deepEqual(data.playback.slice(0,n),Array.from({length:n},(_,i)=>i));
  assert.ok(data.playback.length<=2*n);assert.ok(data.frames.every(k=>Object.values(k).every(Number.isFinite)));if(back)assert.ok(state.atOrigin(data.frames[data.playback.at(-1)]));
 }
});
test('conversion is hidden for history, preview and running; shown after current render',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time.js'),'utf8');
 const fn=source.match(/ function conversionState\(\)\{[^\n]+\}/)[0];
 const elements=Object.fromEntries(['convert-panel','convert-open','convert-save','save-pvt','audio-section','output','convert-options','convert-format'].map(id=>[id,{}]));
 elements.output.value='live-photo';elements['convert-format'].value='mp4';elements['convert-options'].hidden=true;
 const state={run:{id:'old',status:'succeeded',artifacts:[{name:'LivePhoto.mov'}]},renderRunId:null,conversionReady:false,completedRun:null,busy:false,motion:null,$:id=>elements[id]};
 vm.createContext(state);vm.runInContext(fn,state);state.conversionState();
 assert.equal(elements['convert-panel'].hidden,true);assert.equal(elements['save-pvt'].hidden,true);
 state.run={id:'new',status:'running'};state.conversionState();assert.equal(elements['convert-panel'].hidden,true);
 state.run={id:'new',status:'succeeded',artifacts:[{name:'LivePhoto.mov'}]};state.conversionState();
 assert.equal(elements['convert-panel'].hidden,false);assert.equal(elements['save-pvt'].hidden,false);
 state.run={id:'converted',status:'succeeded',artifacts:[]};state.conversionState();
 assert.equal(state.completedRun,'converted');assert.equal(elements['convert-panel'].hidden,false);assert.equal(elements['save-pvt'].hidden,true);
 assert.equal(elements['audio-section'].hidden,true);
 elements['convert-options'].hidden=false;state.conversionState();assert.equal(elements['audio-section'].hidden,false);
 elements['convert-format'].value='html';state.conversionState();assert.equal(elements['audio-section'].hidden,true);
 elements.output.value='mp4';state.conversionState();assert.equal(elements['audio-section'].hidden,false);
 assert.ok(!source.includes("call('frozen.latest')"));
});
test('new output defaults to native Live Photo',()=>{
 const html=fs.readFileSync(path.join(web,'frozen-time.html'),'utf8');
 assert.match(html,/<select id="output"><option value="live-photo"[^>]*selected>/);
});
test('optional audio material is sent only for MP4 render and conversion',()=>{
 const html=fs.readFileSync(path.join(web,'frozen-time.html'),'utf8');
 const source=fs.readFileSync(path.join(web,'frozen-time.js'),'utf8');
 const bridge=fs.readFileSync(path.resolve(__dirname,'../web/static/js/studio_mini_apps.js'),'utf8');
 assert.match(html,/<div id="audio-slot"[^>]*><input id="audio" type="file" accept="audio\/\*">/);
 assert.match(source,/kind:'audio',select:file=>/);
 assert.match(source,/audio:\$\('output'\)\.value==='mp4'\?soundtrack:null/);
 assert.match(source,/audio:output==='mp4'\?soundtrack:null/);
 assert.match(bridge,/request\.operation === 'frozen\.run'[\s\S]*?body\.append\('audio',request\.audio/);
 assert.match(bridge,/request\.operation === 'frozen\.convert'[\s\S]*?body\.append\('audio',request\.audio/);
});
test('reference speedup defaults on, persists and invalidates preview on toggle',()=>{
 const html=fs.readFileSync(path.join(web,'frozen-time.html'),'utf8');
 const source=fs.readFileSync(path.join(web,'frozen-time.js'),'utf8');
 assert.match(html,/<input id="reference-speedup" type="checkbox" checked>/);
 assert.match(source,/reference_speedup:\$\('reference-speedup'\)\.checked/g);
 assert.ok(source.includes("$('reference-speedup').checked=draft?.reference_speedup!==false"));
 assert.ok(source.includes("$('reference-speedup').onchange=async()=>{invalidateMotion();state();"));
 const bridge=fs.readFileSync(path.resolve(__dirname,'../web/static/js/studio_mini_apps.js'),'utf8');
 assert.equal((bridge.match(/body.append\('reference_speedup',String\(request.options\?\.reference_speedup\?\?true\)\)/g)||[]).length,2);
});
test('canvas interpolation supports smooth and linear per departing key',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time-editor.js'),'utf8');
 const fn=source.match(/ function sample\(list,t\)\{[^\n]+\}/)[0];
 const state={origin:{yaw:0},clamp:(x,a,b)=>Math.max(a,Math.min(b,x))};vm.createContext(state);vm.runInContext(fn,state);
 const keys=[{t:0,yaw:-10,transition:'linear'},{t:.5,yaw:0},{t:1,yaw:10}];
 assert.equal(state.sample(keys,.125).yaw,-7.5);
 keys[0].transition='smooth';assert.equal(state.sample(keys,.125).yaw,-8.4375);
 delete keys[0].transition;assert.equal(state.sample(keys,.125).yaw,-7.5);assert.equal(state.sample(keys,.125).transition,'linear');
});
test('canvas draws shallow time grid and seven dashed background curves before active curve',()=>{
 const source=fs.readFileSync(path.join(web,'frozen-time-editor.js'),'utf8');
 const fn=source.slice(source.indexOf(' function draw()'),source.indexOf(" const canvas=$('curve-canvas');"));
 const ranges={pitch:[-20,20],yaw:[-20,20],roll:[-20,20],radius:[.6,1.4],blur:[0,12],saturation:[0,2],exposure:[-2,2],brightness:[0,2]};
 const key={t:0,pitch:0,yaw:0,roll:0,radius:1,blur:0,saturation:1,exposure:0,brightness:1};
 const strokes=[],dashes=[];const ctx={clearRect(){},fillRect(){},fillText(){},beginPath(){},moveTo(){},lineTo(){},arc(){},fill(){},save(){},restore(){},stroke(){strokes.push({color:this.strokeStyle});},setLineDash(x){dashes.push(x);}};
 const elements={'curve-canvas':{getContext:()=>ctx},'curve-parameter':{value:'yaw'},'curve-value':{},'curve-error':{},'curve-transition':{}};
 const state={ranges,colors:Object.fromEntries(Object.keys(ranges).map(x=>[x,x])),keys:[key,{...key,t:1}],selected:0,locked:false,sample:(_,t)=>({...key,t}),valid:()=>true,text:()=>'', $:id=>elements[id]};
 vm.createContext(state);vm.runInContext(fn,state);state.draw();
 assert.equal(strokes.filter(x=>x.color==='#e5e5ea').length,11);
 assert.equal(dashes[0].join(','),'5,5');
 assert.deepEqual(strokes.slice(16,23).map(x=>x.color),['pitch','roll','radius','blur','saturation','exposure','brightness']);
 assert.equal(strokes[23].color,'#8256ff');
});
