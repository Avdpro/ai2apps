const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.join(__dirname,'..');
const source=fs.readFileSync(path.join(root,'web/static/js/space.js'),'utf8');
const helper=source.split('// END GENERATED VISITOR I18N')[0];
const keys=JSON.parse(fs.readFileSync(path.join(root,'web/i18n/visitor-space-keys.json'),'utf8'));
const languages=['zh','zh-TW','en','ja','ko','fr','es','pt-BR','ru'];
function setup({publicPage=false,appLanguage='zh',browserLanguages=['en-US']}={}){
 const marked={textContent:'',getAttribute:()=> '保存草稿'};
 const user={textContent:'保存草稿',value:'AI2Apps 中文原稿 <b>test</b>'};
 const document={documentElement:{lang:appLanguage},querySelector:s=>s==='[data-visitor-public]'?publicPage:null,querySelectorAll:s=>s==='[data-vs-label]'?[marked]:[]};
 const context={document,navigator:{languages:browserLanguages},window:{}};
 vm.runInNewContext(helper,context);return{...context,marked,user,i18n:context.window.VisitorSpaceI18n};
}
test('editor uses AI2Apps locale, independent of visitor browser preferences',()=>{
 const q=setup({appLanguage:'ja',browserLanguages:['zh-CN']});assert.equal(q.i18n.language,'ja');assert.equal(q.marked.textContent,'下書きを保存');assert.equal(q.document.documentElement.lang,'ja');
});
test('public locale follows ordered browser preferences and supports regional aliases',()=>{
 for(const [prefs,expected] of [[['de-DE','fr-CA'],'fr'],[['zh-Hant-HK'],'zh-TW'],[['zh-HK'],'zh-TW'],[['zh-SG'],'zh'],[['pt-PT'],'pt-BR'],[['es-MX'],'es'],[['de-DE'],'en'],[[],'en']]){
  const q=setup({publicPage:true,appLanguage:'ja',browserLanguages:prefs});assert.equal(q.i18n.language,expected);assert.equal(q.document.documentElement.lang,expected);
 }
});
test('all nine catalogs are complete and parameter placeholders match',()=>{
 const en=JSON.parse(fs.readFileSync(path.join(root,'web/i18n/en.json'),'utf8'));
 for(const language of languages){
  const catalog=JSON.parse(fs.readFileSync(path.join(root,'web/i18n',language+'.json'),'utf8'));
  const q=setup({appLanguage:language});
  for(const [sourceText,key] of Object.entries(keys)){
   assert.equal(typeof catalog[key],'string',language+':'+key);assert.ok(catalog[key].length);
   assert.deepEqual(catalog[key].match(/\{\w+\}/g)||[],en[key].match(/\{\w+\}/g)||[]);
   assert.equal(q.i18n.t(sourceText),catalog[key],language+':'+key);
  }
  assert.ok(q.i18n.t('第 {n} 张',{n:3}).includes('3'));
 }
});
test('only marked system text is localized; user content and unknown diagnostics stay verbatim',()=>{
 const q=setup({appLanguage:'en'});assert.equal(q.marked.textContent,'Save draft');assert.equal(q.user.textContent,'保存草稿');assert.equal(q.user.value,'AI2Apps 中文原稿 <b>test</b>');assert.equal(q.i18n.t('raw diagnostic 500'),'raw diagnostic 500');
});
test('template markers and JS authored strings are all in the translation manifest',()=>{
 for(const filename of ['web/templates/space.html','web/templates/system_apps/visitor_space.html']){
  const template=fs.readFileSync(path.join(root,filename),'utf8');
  for(const match of template.matchAll(/data-vs-(?:label|aria|alt)="([^"]+)"/g))assert.ok(keys[match[1]],match[1]);
 }
 for(const script of [source.split('// END GENERATED VISITOR I18N')[1],fs.readFileSync(path.join(root,'web/static/js/visitor_space_editor.js'),'utf8')]){
  for(const match of script.matchAll(/\bt\("([^"]+)"/g))assert.ok(keys[match[1]],match[1]);
 }
});
