/* Real Chrome/Alpine/component integration; media and inference are fixtures. */
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{chromium}=require('playwright');
const asset=name=>fs.readFileSync(path.join(__dirname,'../web/static',name),'utf8');
const template=fs.readFileSync(path.join(__dirname,'../web/templates/system_apps/messager.html'),'utf8');
const settings=template.match(/<section class="bot-realtime-settings"[\s\S]*?<\/section>/)[0];
test('actual settings/ACPF, composer, caption bubble and close work at desktop and narrow widths',{timeout:30000},async()=>{
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{for(const width of [1200,390]){
  const page=await browser.newPage({viewport:{width,height:900}}),errors=[];page.setDefaultTimeout(5000);page.on('pageerror',e=>errors.push(e.message));
  const initial={configured:false,ready:false,revision:0,stt_model_id:null,tts_model_id:null,voice:null,profile_id:null};let saved={...initial};const calls=[];
  await page.route('https://bot.fixture/**',async route=>{const r=route.request(),u=new URL(r.url());calls.push({path:u.pathname,method:r.method(),body:r.headers()['content-type']?.includes('application/json')?r.postDataJSON():null});
   if(u.pathname==='/')return route.fulfill({contentType:'text/html',body:'<!doctype html><html lang="zh"><head><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;background:#fff;font:14px system-ui}.layout{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:20px;padding:20px}aside{padding:16px;border:1px solid #ddd;border-radius:16px}.stage{display:flex;flex-direction:column;justify-content:end;min-height:600px}.bot-composer{margin:0!important;width:100%!important}.messager-bot-settings{display:grid;gap:10px}.messager-bot-settings label{display:grid;gap:6px}@media(max-width:600px){.layout{grid-template-columns:1fr;padding:14px}.stage{min-height:340px}}</style></head><body><div class="layout"><main class="stage"><p>当前 Bot 的回复和任务仍显示在原聊天中</p><form id="composer" class="bot-composer"><textarea id="draft">尚未发送的文字</textarea><button id="cancel">停止任务</button><button id="send" type="submit">发送</button></form></main><aside x-data="realtimeTestSettings()">'+settings+'</aside></div></body></html>'});
   if(u.pathname==='/admin/api/models')return route.fulfill({json:{models:[{id:'asr-one',display_name:'识别模型 A',model_type:'audio_stt',checkpoint_ready:true},{id:'tts-one',display_name:'声音模型 A',model_type:'audio_tts',checkpoint_ready:true,audio_capabilities:{tts:{named_voices:{voices:['one','two']}}}}]}});
   if(u.pathname.endsWith('/voice-profiles'))return route.fulfill({json:{items:[]}});
   if(u.pathname.endsWith('/realtime/settings')){if(r.method()==='PUT')saved={...r.postDataJSON(),revision:saved.revision+1,configured:true,ready:true};return route.fulfill({json:saved});}
   if(u.pathname.endsWith('/realtime/sessions'))return route.fulfill({json:{id:'voice-one',settings:saved}});
   if(u.pathname.endsWith('/inputs'))return route.fulfill({json:{state:'accepted',dialogue_run_id:'original-bot-run'}});
   if(u.pathname==='/v1/audio/transcriptions')return route.fulfill({json:{text:'请让 Bot 整理这些资料'}});
   return route.fulfill({json:{}});
  });
  await page.goto('https://bot.fixture/');await page.addStyleTag({content:asset('css/messager.css')});
  for(const file of ['bot_voice.js','bot_realtime_settings.js','messager.js','bot_composer.js','streaming_tts.js','bot_realtime.js'])await page.addScriptTag({content:asset('js/'+file)});
  await page.evaluate(()=>{
   window.acpf=[];window.accepted=[];window.deviceStops=0;
   window.AI2AppsCapabilities={ensure:async(request,options)=>{acpf.push({request,options});return {outcome:'configured',provider:{modelId:'tts-one'}};},acknowledge:async()=>{}};
   window.realtimeTestSettings=()=>{const settings=messagerApp();settings.init=function(){this.currentBot={id:'bot-one',definition:{execution_mode:'agent'}};return this.loadRealtimeVoice();};return settings;};
   window.AI2AppsBotRealtimeAudio={capture:async emit=>{window.captureEmit=emit;return {close(){deviceStops++;},mute(){}};}};
   const form=document.querySelector('#composer'),input=document.querySelector('#draft'),send=document.querySelector('#send'),cancel=document.querySelector('#cancel');
   window.composer=AI2AppsBotComposer.create({form,input,send,cancel,sessionId:'session-one',models:[{id:'asr-one',model_type:'audio_stt'}],label:(zh,en)=>zh,onError:e=>{throw e;},onChange(){}});
   window.live=AI2AppsBotRealtime.create({botId:'bot-one',sessionId:'session-one',composer,form,getModel:()=> 'bot-execution-model',request:async(p,method='GET',body)=>{const r=await fetch('/v1/platform'+p,{method,headers:{'Content-Type':'application/json'},...(body?{body:JSON.stringify(body)}:{})});return r.json();},onAccepted:r=>accepted.push(r),label:(zh,en)=>zh,onError:e=>{throw e;}});
  });
  await page.addScriptTag({content:asset('js/alpine.min.js')});
  try{await page.getByLabel('对话声音模型').selectOption('__install__');}catch(error){console.error('PAGE ERRORS',errors,'ASIDE',await page.locator('aside').innerText());throw error;}
  await page.waitForFunction(()=>acpf.length===1);assert.equal(await page.evaluate(()=>acpf[0].request.capability),'audio.speech_generation');assert.equal(await page.evaluate(()=>acpf[0].request.intent.completionPolicy),'configure_only');
  await page.locator('aside').getByLabel('识别模型').selectOption('asr-one');
  await page.waitForFunction(()=>!document.querySelector('.bot-realtime-toggle').hidden);
  await page.getByRole('button',{name:'对话模式',exact:true}).click();await page.waitForFunction(()=>typeof captureEmit==='function');
  assert.equal(await page.getByRole('button',{name:'对话模式正在使用麦克风'}).isDisabled(),true);
  await page.evaluate(()=>{captureEmit({type:'start',turn:'voice-turn'});captureEmit({type:'partial',turn:'voice-turn',audio:new Blob(['fixture audio'])});});
  await page.getByText('请让 Bot 整理这些资料',{exact:true}).waitFor();
  assert.equal(await page.locator('#draft').inputValue(),'尚未发送的文字');
  const inputBox=await page.locator('#draft').boundingBox(),bubble=await page.locator('.bot-voice-caption').boundingBox();assert.ok(bubble.x>=0&&bubble.x+bubble.width<=width);assert.ok(bubble.y+bubble.height<=inputBox.y+1);
  const controls=await page.locator('.bot-composer-controls').boundingBox(),panel=await page.locator('.bot-realtime-panel').boundingBox();
  assert.ok(controls.x+controls.width<=panel.x,'the entire button row stays in the left column');
  assert.ok(inputBox.x+inputBox.width<=panel.x,'the text editor stays in the left column');
  assert.ok(panel.y<=inputBox.y+1&&panel.y+panel.height>=controls.y+controls.height-1,'the voice column spans editor and controls together');
  assert.equal(await page.locator('.bot-realtime-compose-column > textarea').count(),1);
  assert.equal(await page.locator('.bot-realtime-compose-column > .bot-composer-controls').count(),1);
  const readSwitch=page.getByRole('switch',{name:'读出回复'});assert.equal(await readSwitch.isChecked(),true);await readSwitch.uncheck();assert.equal(await page.getByRole('button',{name:'停止播报'}).isVisible(),false);
  assert.equal(await page.locator('.bot-realtime-read').isVisible(),true);
  await page.locator('#draft').fill('继续保留的文字草稿');
  await page.screenshot({path:'/tmp/bot-realtime-'+width+'.png',fullPage:true});
  await page.evaluate(()=>captureEmit({type:'final',turn:'voice-turn',audio:new Blob(['fixture audio'])}));await page.waitForFunction(()=>accepted.length===1);assert.equal(calls.filter(c=>c.path.endsWith('/inputs')).length,1);
  const body=calls.find(c=>c.path.endsWith('/inputs')).body;assert.equal(body.text,'请让 Bot 整理这些资料');assert.equal(body.turn_id,'voice-turn');
  await page.getByRole('button',{name:'结束语音对话'}).click();await page.locator('.bot-realtime-panel').waitFor({state:'hidden'});assert.equal(await page.locator('.bot-realtime-panel').isVisible(),false);assert.equal(await page.locator('#draft').inputValue(),'继续保留的文字草稿');assert.equal(await page.getByRole('button',{name:'语音输入',exact:true}).isEnabled(),true);assert.equal(await page.evaluate(()=>deviceStops),1);assert.deepEqual(errors,[]);await page.close();
 }}finally{await browser.close();}
});
