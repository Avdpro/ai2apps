const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),path=require('path'),{execFileSync}=require('child_process');
const {chromium}=require('playwright');const base=path.resolve(__dirname,'..'),git=path.resolve(base,'..');
function html(){return execFileSync(git+'/.venv/bin/python',['-c',`from jinja2 import Environment,FileSystemLoader\ne=Environment(loader=FileSystemLoader('${base}/web/templates'))\ne.globals['mobile_static']=lambda name:'/assets/'+name\nprint(e.get_template('mobile_chat.html').render(current_lang='zh',owner_home=False,mobile_agent_ready=True))`],{encoding:'utf8'});}
test('Mobile uploads 30 MiB with progress, retains IDs, preserves missing-model form on reload',async()=>{
 const browser=await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
 try{
 const page=await browser.newPage({viewport:{width:390,height:844}});let received=0,submitted=null,runs=[],revision=0,uploads=0,transferred=0;
 const values={video_id:'attc_video',target_language:'zh'};
 const run={id:'r_video',session_id:'thread',status:'waiting_input',steps:[],input:{text:'翻译视频字幕'},status_line:{text:'确认字幕参数'},interactions:[{id:'i_video',status:'pending',kind:'form',prompt:'配置视频字幕',request:{control:'parameter_form'},ui_hints:{control:'parameter_form'}}]};
 await page.route('**/*',async route=>{const req=route.request(),u=new URL(req.url()),p=u.pathname,m=req.method();let data;
  if(p.startsWith('/assets/')){const file=path.join(base,'web/static',p.slice(8));return route.fulfill({contentType:p.endsWith('.js')?'text/javascript':'text/css',body:fs.readFileSync(file)});}
  if(p==='/')return route.fulfill({contentType:'text/html',body:html()});
  if(p==='/v1/mobile/chat/state')data={selected_thread_id:'thread'};
  else if(p==='/v1/mobile/models')data={data:[{id:'fixture',display_name:'Fixture model',model_type:'llm',capabilities:['work_standard','tool_calling_reliable','conversation']}]};
  else if(p==='/v1/mobile/agents')data={items:[{agent_key:'ai2apps.general-agent',status:'enabled',discoverable:true}]};
  else if(p==='/v1/mobile/apps')data={items:[]};
  else if(p==='/v1/mobile/chat/threads')data={items:[{id:'thread',title:'Subtitle upload'}]};
  else if(p.endsWith('/content'))data={thread:{id:'thread',title:'Subtitle upload'},messages:[],revision:0,session_metadata:{}};
  else if(p.endsWith('/uploads')&&m==='POST'){uploads++;received=0;assert.equal(req.postDataJSON().size_bytes,(uploads===1?30:26)*1024**2);data={id:'a'.repeat(32),chunk_bytes:4*1024**2};}
  else if(p.endsWith('/uploads/'+'a'.repeat(32))&&m==='PUT'){assert.equal(Number(u.searchParams.get('offset')),received);const body=req.postDataBuffer();assert.ok(body.length<=4*1024**2);received+=body.length;await new Promise(r=>setTimeout(r,70));data={received_bytes:received};}
  else if(p.endsWith('/complete')){assert.equal(received,(uploads===1?30:26)*1024**2);transferred+=received;data={id:uploads===1?'attc_video':'attc_second',filename:'video.mp4',media_type:'video/mp4',size_bytes:received,metadata:{gallery_asset_id:'gala_video'}};}
  else if(p.endsWith('/agent-runs')){if(m==='POST'){submitted=req.postDataJSON();runs=[run];data=run;}else data={items:runs};}
  else if(p==='/v1/mobile/agent-runs/r_video')data=run;
  else if(p.endsWith('/parameters/materials'))data={items:[{id:'attc_video',name:'large-video.mp4',media_type:'video/mp4',storage:'reference'},{id:'attc_second',name:'replacement.mp4',media_type:'video/mp4',storage:'reference'}]};
  else if(p.endsWith('/parameters/setup/session'))data={session:null};
  else if(p.endsWith('/parameters')){if(m==='PUT'){Object.assign(values,req.postDataJSON().values);revision++;}data={revision,values,models:[],configuration_required:true,install:{appId:'fixture.owner'},descriptor:{capability:'fixture.subtitles',schema:{required:['target_language']},fields:[{key:'video_id',label:'视频',type:'asset',storage:'artifact',references:true,accept:'video/*'},{key:'target_language',label:'目标语言',type:'text'}]}};}
  else return route.fulfill({status:404,json:{detail:'Not exposed'}});
  if(p.endsWith('/parameters'))data.prompt_labels={zh:'配置视频字幕',en:'Configure video subtitles'};
  return route.fulfill({json:data});
 });
 await page.goto('https://fixture.test');await page.getByRole('button',{name:'Agent',exact:true}).click();
 await page.locator('[data-mobile-chat-file]').setInputFiles({name:'large-video.mp4',mimeType:'video/mp4',buffer:Buffer.alloc(30*1024**2)});
 await page.locator('[data-mobile-chat-input]').fill('翻译视频字幕');await page.locator('[data-mobile-chat-send]').click();
 await page.getByText('Uploading to Gallery',{exact:true}).waitFor();await page.locator('.agent-parameter-title').waitFor();assert.match(await page.locator('.agent-parameter-title').innerText(),/^配置视频字幕/);
 const file=submitted.input.content.find(p=>p.type==='file').file;assert.equal(file.file_id,'attc_video');assert.equal(file.gallery_asset_id,'gala_video');assert.ok(!file.file_data);
 await page.locator('[data-run-id] input[type=file]').setInputFiles({name:'replacement.mp4',mimeType:'video/mp4',buffer:Buffer.alloc(26*1024**2)});
 await page.getByText('replacement.mp4',{exact:true}).first().waitFor();
 await page.getByRole('button',{name:'查看 Desktop 配置说明'}).click();await page.getByText(/请到 Desktop 配置/).waitFor();
 await page.reload();await page.locator('.agent-parameter-title').waitFor();assert.match(await page.locator('.agent-parameter-title').innerText(),/^配置视频字幕/);assert.equal(await page.getByLabel('目标语言').inputValue(),'zh');
 assert.equal(transferred,56*1024**2);assert.equal(values.video_id,'attc_second');
 }finally{await browser.close();}
});
