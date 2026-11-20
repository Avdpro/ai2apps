const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const {execFileSync}=require('node:child_process');
const repoRoot=path.resolve(__dirname,'../..');
const fixtureHTML=execFileSync(path.join(repoRoot,'.venv/bin/python'),['-c',`
import json,sys
from pathlib import Path
from jinja2 import Environment,FileSystemLoader
root=Path(sys.argv[1])/'ai2apps/web'
locale=json.loads((root/'i18n/en.json').read_text())
env=Environment(loader=FileSystemLoader(str(root/'templates')),autoescape=True)
print(env.get_template('system_apps/messager_mobile.html').render(current_lang='en',locale_json='{}',t=lambda key:locale.get(key,key),static=lambda name:'/assets/'+name,mobile_static=lambda name:'/assets/'+name,mobile_gateway_config={'apiPrefix':'/v1/platform/messager-mobile','bridge':'/bridge','resourceBase':'/resource/'}))
`,repoRoot],{cwd:repoRoot,encoding:'utf8'});
for(const setupReady of [false,true])test('Mobile setup '+setupReady+' single recording and conversation input keep draft, scoped transport and input-only mode',async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{const page=await browser.newPage({viewport:{width:390,height:844},isMobile:true,hasTouch:true});const requests=[],messages=[];let mediaCount=0;
 const config={configured:setupReady,ready:setupReady,revision:setupReady?1:0,stt_model_id:'asr',tts_model_id:'tts',voice:'one',profile_id:null};
 await page.route('https://voice.fixture/**',async route=>{
  const u=new URL(route.request().url());if(u.pathname==='/entry')return route.fulfill({contentType:'text/html',body:fixtureHTML});
  if(u.pathname.startsWith('/assets/')){const file=path.join(__dirname,'../web/static',u.pathname.slice(8));return fs.existsSync(file)?route.fulfill({path:file}):route.fulfill({body:''});}
  if(u.pathname!=='/bridge')return route.fulfill({body:''});
  const envelope=route.request().postDataJSON();requests.push(envelope);const p=new URL(envelope.path,'https://local').pathname;let value={};
  if(p.endsWith('/bots'))value={items:[{id:'bot',name:'AI2Apps',definition:{execution_mode:'agent'}}]};
  else if(p.endsWith('/bot-groups'))value={items:[]};
  else if(p.endsWith('/open'))value={session_id:'session-one',profile:{model_id:'fixture',effective_model:'fixture',revision:1}};
  else if(p.endsWith('/state'))value={runs:[],task_sessions:[],unread:{unread_count:0}};
  else if(p.endsWith('/messages'))value={items:messages,has_more:false,conversation_revision:0};
  else if(p.endsWith('/details'))value={identity:{name:'AI2Apps',duty:'Fixture role'},model:{effective_model:'fixture',model_id:'fixture',revision:1},access:{items:[]},memories:{items:[]},voice:{mode:'default'}};
  else if(p.endsWith('/statistics'))value={tasks:0,executions:0,completed:0,active:0,usage:{unreported_model_calls:0,input_tokens:0,output_tokens:0,currency_costs:{}},end:new Date().toISOString()};
  else if(p.endsWith('/voice/catalog'))value={stt:[{id:'asr',name:'Fixture ASR'}],tts:[{id:'tts',name:'Fixture TTS',voices:['one']}]};
  else if(p.endsWith('/realtime/settings')){if(envelope.verb==='PUT'){const body=JSON.parse(Buffer.from(envelope.body,'base64').toString());assert.equal(body.stt_model_id,'asr');assert.equal(body.tts_model_id,'tts');config.revision++;config.configured=true;config.ready=true;}value=config;}
  else if(p.endsWith('/realtime/sessions'))value={id:'voice-one',settings:config,lease_seconds:45};
  else if(p.endsWith('/transcriptions')){mediaCount++;value={text:mediaCount===1?'recorded words':'voice instruction'};assert.equal(envelope.verb,'POST');assert.match(envelope.headers['content-type'],/multipart/);}
  else if(p.endsWith('/inputs')){const body=JSON.parse(Buffer.from(envelope.body,'base64').toString());assert.equal(body.text,'voice instruction');value={state:'accepted',dialogue_run_id:'run-one'};messages.push({id:'reply-one',sequence:1,role:'assistant',content:'Task completed.'});}
  if(p.endsWith('/voice/read'))return route.fulfill({json:{status:200,contentType:'audio/wav',body:Buffer.from('manual read audio').toString('base64')}});
  if(p.endsWith('/voice/speech')){const body=JSON.parse(Buffer.from(envelope.body,'base64').toString());assert.equal(body.voice_id,'voice-one');assert.equal(body.session_id,'session-one');assert.equal(typeof body.controller,'string');return route.fulfill({json:{status:200,contentType:'audio/wav',body:Buffer.from('fixture audio').toString('base64')}});}
  return route.fulfill({json:{status:200,contentType:'application/json',body:Buffer.from(JSON.stringify(value)).toString('base64')}});
 });
 await page.goto('https://voice.fixture/entry');await page.getByRole('button',{name:'AI2Apps',exact:true}).waitFor();
 await page.evaluate(()=>{
  window.deviceClosed=0;window.audioPlayed=0;window.Audio=class extends EventTarget{play(){audioPlayed++;queueMicrotask(()=>this.onended?.());return Promise.resolve();}pause(){}};window.AI2AppsStudioAudioRecorder=class{async start(){this.result=new Promise(resolve=>this.finish=resolve);}async stop(){this.finish({body:new Blob(['recording'],{type:'audio/mp4'})});}dispose(){deviceClosed++;}};
  window.AI2AppsBotRealtimeAudio={capture:async emit=>{window.emitVoice=emit;return {close(){deviceClosed++;},mute(){}};}};
 });
 await page.getByRole('button',{name:'AI2Apps',exact:true}).click();await page.getByLabel('Message',{exact:true}).fill('keep draft');
 await page.getByRole('button',{name:'Voice input',exact:true}).click();await page.getByRole('button',{name:'Stop recording',exact:true}).click();
 await page.waitForFunction(()=>document.getElementById('mm-input').value==='keep draft recorded words');
 if(!setupReady){await page.getByRole('button',{name:'Conversation mode',exact:true}).click();await page.getByLabel('Recognition model').selectOption('asr');await page.getByLabel('Conversation voice model').selectOption('tts');await page.getByRole('button',{name:'Apply conversation settings'}).click();await page.getByText('Saved. Return to the conversation to start.',{exact:true}).waitFor();await page.getByRole('button',{name:'Back to conversation'}).click();}
 await page.getByRole('button',{name:'Conversation mode',exact:true}).click();await page.waitForFunction(()=>typeof emitVoice==='function');
 assert.equal(await page.getByRole('button',{name:'Voice input',exact:true}).isDisabled(),true);
 await page.getByRole('switch',{name:'Read replies'}).uncheck();
 await page.evaluate(()=>{emitVoice({type:'start',turn:'turn-one'});emitVoice({type:'partial',turn:'turn-one',audio:new Blob(['audio'])});});
 await page.locator('.bot-voice-caption').getByText('voice instruction',{exact:true}).waitFor();
 assert.equal(await page.getByLabel('Message',{exact:true}).inputValue(),'keep draft recorded words');
 await page.evaluate(()=>emitVoice({type:'final',turn:'turn-one',audio:new Blob(['audio'])}));await page.getByText('Task completed.',{exact:true}).waitFor();
 assert.equal(requests.filter(x=>x.path.endsWith('/voice/speech')).length,0);await page.getByRole('button',{name:'Read reply',exact:true}).click();await page.waitForFunction(()=>audioPlayed===1);assert.equal(requests.filter(x=>x.path.endsWith('/voice/read')).length,1);
 const left=await page.locator('.mm-voice-column').boundingBox(),ball=await page.locator('.bot-realtime-panel').boundingBox();assert.ok(left.x+left.width<=ball.x);
 await page.screenshot({path:'/tmp/mobile-bot-voice-390.png',fullPage:true});
 await page.getByRole('switch',{name:'Read replies'}).check();messages.push({id:'reply-two',sequence:2,role:'assistant',content:'A new result.'});await page.waitForFunction(()=>audioPlayed>1);assert.equal(requests.filter(x=>x.path.endsWith('/voice/speech')).length,1);
 await page.getByRole('button',{name:'End voice conversation'}).click();await page.locator('.bot-realtime-panel').waitFor({state:'hidden'});
 assert.equal(await page.getByRole('button',{name:'Voice input',exact:true}).isEnabled(),true);assert.equal(await page.getByLabel('Message',{exact:true}).inputValue(),'keep draft recorded words');
 assert.equal(requests.some(x=>x.path.includes('/cancel')),false);assert.equal(requests.some(x=>!x.path.startsWith('/v1/platform/messager-mobile')),false);
 await page.getByRole('button',{name:'Bot details and settings'}).click();await page.getByText('Voice and conversation',{exact:true}).click();await page.getByLabel('Recognition model').selectOption('asr');await page.getByLabel('Conversation voice model').selectOption('tts');await page.getByRole('button',{name:'Apply conversation settings'}).click();await page.getByText('Saved. Return to the conversation to start.',{exact:true}).waitFor();assert.equal(requests.filter(x=>x.path.endsWith('/realtime/settings')&&x.verb==='PUT').length,setupReady?1:2);
 await page.close();
 }finally{await browser.close();}
});
