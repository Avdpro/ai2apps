const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
test('Bot access writes one binary relation and reloads the authoritative pair views',async()=>{
 const calls=[],window={};let revision=1;
 const state=()=>({revision,mode:'public',outgoing:[{id:'private-target',name:'Private',enabled:true}],incoming:[],candidates:[],caller_candidates:[]});
 const fetch=async(url,options={})=>{calls.push({url,options});if(options.method==='PUT')revision++;return {ok:true,json:async()=>state()};};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/static/js/messager.js'),'utf8'),{window,fetch,document:{documentElement:{lang:'en'}},URL,Blob,AbortController,console,setTimeout,clearTimeout,setInterval,clearInterval});
 const app=window.messagerApp();Object.assign(app,{currentBot:{id:'caller'},botUseAccess:state(),fail:e=>{throw e;}});
 await app.setBotUse('targets','private-target',true);
 const put=calls.find(c=>c.options.method==='PUT');assert.equal(put.url,'/v1/platform/messager/bots/caller/bot-access/targets/private-target');assert.deepEqual(JSON.parse(put.options.body),{revision:1,enabled:true});assert.equal(app.botUseAccess.revision,2);
 app.botUseAccess.mode='private';await app.setBotUse('exposure');const modes=calls.filter(c=>c.options.method==='PUT');assert.deepEqual(JSON.parse(modes[1].options.body),{revision:2,mode:'private'});
 const html=fs.readFileSync(path.join(__dirname,'../web/templates/system_apps/messager.html'),'utf8');const section=html.split('<section data-bot-use-access>')[1].split('</section>')[0];assert.match(section,/target.enabled/);assert.doesNotMatch(section,/target\.read|target\.write/);assert.match(html,/setBotUse\('callers',caller.id,false\)/);
});
