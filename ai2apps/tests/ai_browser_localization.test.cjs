const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'../web');
const locales=['zh','en','zh-TW','ja','ko','fr','es','pt-BR','ru'];
const dictionaries=Object.fromEntries(locales.map(lang=>[lang,JSON.parse(fs.readFileSync(path.join(root,'i18n',lang+'.json'),'utf8'))]));
const files=['static/js/ai_browser.js','static/js/agent_mini.js','templates/system_apps/ai_browser.html','templates/system_apps/agent_mini.html'];
const keys=new Set(files.flatMap(file=>Array.from(fs.readFileSync(path.join(root,file),'utf8').matchAll(/['"]((?:ai_browser|agent\.mini)\.[A-Za-z0-9_.]+)['"]/g),m=>m[1]).filter(k=>!/[_.]$/.test(k))));
for(const type of ['string','integer','number','boolean','object','array','file','files'])keys.add('agent.mini.type_'+type);
for(const status of ['running','awaiting_review','approved','committed','failed','interrupted','cancelled','completed','needs_user','restricted','budget_exhausted'])keys.add('agent.mini.status_'+status);
const placeholders=text=>Array.from(new Set(Array.from(text.matchAll(/\{([\w.]+)\}/g),m=>m[1]))).sort();
test('all nine languages cover workspace and editor including dynamic types and statuses',()=>{
 for(const lang of locales)for(const key of keys){
  assert.equal(typeof dictionaries[lang][key],'string',`${lang}: ${key}`);
  assert.ok(dictionaries[lang][key].trim(),`${lang}: empty ${key}`);
  assert.deepEqual(placeholders(dictionaries[lang][key]),placeholders(dictionaries.en[key]),`${lang}: placeholders in ${key}`);
 }
});
test('English task view localizes backend status and messages while preserving user text',()=>{
 const context={window:{t:key=>dictionaries.en[key]||key},crypto:{randomUUID:()=> 'test'},Map,URL,URLSearchParams,console};
 vm.runInNewContext(fs.readFileSync(path.join(root,'static/js/ai_browser.js'),'utf8'),context);
 const app=context.aiBrowserApp();
 assert.equal(app.statusLabel('waiting_input',{status_label:'等待浏览器响应'}),'Waiting for browser');
 assert.equal(app.statusLabel('completed'),'Completed');
 assert.equal(app.localTaskText('自定义的用户任务内容'),'自定义的用户任务内容');
 assert.equal(app.tr('agent.mini.step_name_prefix',{number:3}),'Step-3: ');
 assert.equal(app.tr('agent.mini.return_failed',{error:'Connection closed'}),'Test finished, but returning to the main window failed: Connection closed');
});
