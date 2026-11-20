const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
function fixture(options={}){
 class El{constructor(tag){this.tag=tag;this.children=[];this.value='';this.classList={add(){},toggle(){}};this.listeners={};this.attributes={};}append(...xs){this.children.push(...xs)}replaceChildren(...xs){this.children=xs}setAttribute(k,v){this.attributes[k]=v}add(x){this.children.push(x);if(!this.value)this.value=x.value}addEventListener(k,v){this.listeners[k]=v}removeEventListener(k){delete this.listeners[k]}dispatchEvent(){}focus(){}click(){this.clicked=true}}
 const document={createElement:t=>new El(t)},window={matchMedia:()=>({matches:!!options.touch}),AI2AppsGalleryPicker:{acceptsDrop:t=>t.types.includes('application/x-ai2apps-gallery-asset'),droppedAssetIds:t=>{const id=t.getData('application/x-ai2apps-gallery-asset');return id?[id]:[];}}},errors=[],requests=[],urls=[],revoked=[];
 let recordingResolve;class Recorder{async start(){this.result=new Promise(r=>recordingResolve=r)}async stop(){recordingResolve();return {body:'audio',name:'recording.webm'}}dispose(){this.disposed=true}}
 window.AI2AppsStudioAudioRecorder=Recorder;
 const env={window,document,File:class{constructor(parts,name,options){this.name=name;this.size=3;this.type=options.type}},Event:class{},Option:class{constructor(text,value){this.text=text;this.value=value}},localStorage:{getItem:()=>'{"sttModel":"stt-ready"}'},URL:{createObjectURL:f=>{const u='blob:'+f.name;urls.push(u);return u},revokeObjectURL:u=>revoked.push(u)},FormData:class{append(){}},fetch:async(url,opts)=>{requests.push({url,opts});if(options.response)return options.response(url,opts);if(options.gallery&&url.includes('/gallery/assets/'))return {ok:true,json:async()=>({id:'gala_owned',name:'Owned Gallery image.png',media_type:'image/png',size_bytes:3}),blob:async()=>({size:3,type:'image/png'})};return {ok:true,json:async()=>url.includes('transcriptions')?{text:'transcribed words'}:{id:'att-'+requests.length}}}};
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_composer.js','utf8'),env);
 const form=new El('form'),input=new El('textarea'),send=new El('button'),cancel=new El('button');
 const api=window.AI2AppsBotComposer.create({form,input,send,cancel,inputPolicy:options.inputPolicy||{},sessionId:'own-session',models:options.models||[{id:'stt-ready',model_type:'audio_stt'}],label:(zh,en)=>en,onPoke:options.onPoke,onError:e=>errors.push(e.message),onChange(){}});
 return {api,form,input,send,requests,errors,urls,revoked,window};
}
const flush=()=>new Promise(r=>setImmediate(r));
test('selected files upload to exact session; removed previews release URLs and no IDs enter next turn',async()=>{const f=fixture(),picker=f.form.children.at(-1);picker.files=[{name:'photo.png',type:'image/png',size:12}];picker.onchange();assert.equal(f.api.blocked(),true);await flush();assert.equal(f.api.ids().length,1);assert.match(f.requests[0].url,/sessions\/own-session\/attachments\/upload$/);const preview=f.form.children[0];preview.children[0].children.at(-1).onclick();assert.equal(f.api.hasFiles(),false);assert.equal(f.revoked.length,1);f.api.dispose();assert.deepEqual(f.errors,[])});
test('speech fills editable draft and does not send a conversation turn',async()=>{const f=fixture(),mic=f.form.children[2].children[1];f.input.value='existing draft';await mic.onclick();assert.equal(f.api.blocked(),true);await mic.onclick();await flush();assert.equal(f.input.value,'existing draft transcribed words');assert.equal(f.api.blocked(),false);assert.equal(f.requests.length,1);assert.equal(f.requests[0].url,'/v1/audio/transcriptions');f.api.dispose();assert.deepEqual(f.errors,[])});
test('oversized files are rejected before any upload',async()=>{const f=fixture(),picker=f.form.children.at(-1);picker.files=[{name:'big.pdf',type:'application/pdf',size:30*1024*1024}];picker.onchange();await flush();assert.equal(f.requests.length,0);assert.equal(f.api.hasFiles(),false);assert.equal(f.errors.length,1);f.api.dispose()});

test('voice attachment selection is frozen while uploads finish and cannot absorb later files',async()=>{
 const f=fixture(),picker=f.form.children.at(-1);picker.files=[{name:'first.pdf',type:'application/pdf',size:12}];picker.onchange();const selected=f.api.captureAttachments();assert.equal(selected(),null);await flush();assert.equal(selected().length,1);const original=selected()[0];
 picker.files=[{name:'second.pdf',type:'application/pdf',size:12}];picker.onchange();await flush();assert.deepEqual(Array.from(selected()),[original]);assert.equal(f.api.ids().length,2);f.api.removeIds([original]);assert.throws(()=>selected(),/selection changed/);assert.equal(f.api.ids().length,1);f.api.dispose();
});

test('Gallery drag ignores supplied names and URLs, resolves owned asset ID and uploads to captured session',async()=>{const f=fixture({gallery:true});const transfer={types:['application/x-ai2apps-gallery-asset'],getData:key=>key==='application/x-ai2apps-gallery-asset'?'gala_owned':'https://untrusted.test/private'};f.form.listeners.drop({dataTransfer:transfer,preventDefault(){},stopPropagation(){}});await flush();await flush();assert.equal(f.requests[0].url,'/v1/platform/gallery/assets/gala_owned');assert.equal(f.requests[1].url,'/v1/platform/gallery/assets/gala_owned/content');assert.equal(f.requests[2].url,'/v1/platform/sessions/own-session/attachments/upload');assert.equal(f.api.ids().length,1);assert.deepEqual(f.errors,[]);f.api.dispose()});

test('missing ASR offers owner ACPF setup without recording, installing or sending automatically',async()=>{
 const f=fixture({models:[]});let setup;
 f.window.AI2AppsBotVoice={offerSetup:value=>setup=value};
 await f.form.children[2].children[1].onclick();assert.equal(setup.operation,'speech_recognition');assert.equal(f.requests.length,0);assert.equal(f.input.value,'');
 await setup.onConfigured({provider:{modelId:'new-asr'}});assert.equal(f.form.children[2].children[2].value,'new-asr');assert.equal(f.requests.length,0);
 f.api.dispose();assert.equal(setup.isCurrent(),false);
});
test('failed ASR retains original recording and draft; explicit retry uses configured model with no conversation submit',async()=>{
 let tries=0;const f=fixture({response:async()=>++tries===1?{ok:false,status:500,json:async()=>({detail:'Runtime missing'})}:{ok:true,json:async()=>({text:'recovered'})}});let setup;f.window.AI2AppsBotVoice={offerSetup:value=>setup=value};f.input.value='my draft';const mic=f.form.children[2].children[1];await mic.onclick();await mic.onclick();assert.equal(setup.operation,'speech_recognition');assert.equal(f.input.value,'my draft');assert.equal(f.requests.length,1);
 await setup.onConfigured({provider:{modelId:'fixed-asr'}});assert.equal(f.requests.length,1);
 const notice=f.form.children[3];await notice.children.at(-1).onclick();await flush();assert.equal(f.input.value,'my draft recovered');assert.equal(f.requests.length,2);assert.ok(f.requests.every(x=>x.url==='/v1/audio/transcriptions'));f.api.dispose();
});

test('desktop Enter submits the original form; Shift/IME/touch preserve newline and composition',()=>{
 for(const options of [{},{touch:true}]){
  const f=fixture(options);let submitted=0;f.form.requestSubmit=button=>{assert.equal(button,f.send);submitted++;};
  for(const flags of [{shiftKey:true},{isComposing:true},{keyCode:229},{defaultPrevented:true}]){
   let prevented=false;f.input.listeners.keydown({key:'Enter',...flags,preventDefault(){prevented=true;}});
   assert.equal(submitted,0);assert.equal(prevented,false);
  }
  let prevented=false;f.input.listeners.keydown({key:'Enter',preventDefault(){prevented=true;}});
  assert.equal(submitted,options.touch?0:1);assert.equal(prevented,!options.touch);
  f.api.dispose();assert.equal(f.input.listeners.keydown,undefined);
 }
});
test('Enter never submits while Send is disabled or composer is busy',()=>{
 const f=fixture();let submitted=0;f.form.requestSubmit=()=>submitted++;
 f.send.disabled=true;f.input.listeners.keydown({key:'Enter',preventDefault(){}});
 f.send.disabled=false;f.api.setBusy(true);f.input.listeners.keydown({key:'Enter',preventDefault(){}});
 assert.equal(submitted,0);f.api.dispose();
});

test('fixed text input disables attachment and voice paths before any upload or recording',async()=>{const f=fixture({inputPolicy:{attachments:false,voice:false}}),controls=f.form.children[2],picker=f.form.children.at(-1);assert.equal(controls.children[0].hidden,true);assert.equal(controls.children[1].hidden,true);picker.files=[{name:'photo.png',type:'image/png',size:12}];picker.onchange();await controls.children[1].onclick();await flush();assert.equal(f.requests.length,0);assert.equal(f.api.hasFiles(),false);f.api.dispose();});


test('Poke preserves the editable draft and is blocked during busy work',()=>{let pokes=0;const f=fixture({onPoke:()=>pokes++});f.input.value='unsent draft';const poke=f.form.children[2].children[2];assert.equal(poke.attributes['aria-label'],'Poke Bot');poke.onclick();assert.equal(pokes,1);assert.equal(f.input.value,'unsent draft');f.api.setBusy(true);poke.onclick();assert.equal(pokes,1);assert.equal(poke.disabled,true);f.api.dispose();});

test('Poke receipt lock disables only Poke and composes with the ordinary busy state',()=>{let pokes=0;const f=fixture({onPoke:()=>pokes++});const poke=f.form.children[2].children[2];f.api.setPokeBusy(true);assert.equal(poke.disabled,true);poke.onclick();assert.equal(pokes,0);f.api.setBusy(true);f.api.setPokeBusy(false);assert.equal(poke.disabled,true);f.api.setBusy(false);assert.equal(poke.disabled,false);poke.onclick();assert.equal(pokes,1);f.api.dispose();});
