const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const root=__dirname+'/../web/static/builtin_mini_apps/web-reader/web/';
const html=fs.readFileSync(root+'index.html','utf8'),script=fs.readFileSync(root+'reader.js','utf8');
function setup(locale,submit){
 const nodes=new Map(),texts=[...html.matchAll(/data-text="([^"]+)"/g)].map(m=>({dataset:{text:m[1]},textContent:''}));
 for(const id of ['reader','capability','status','result','limit-row','run','url','limit','profile'])nodes.set(id,{value:'',textContent:'',setAttribute(k,v){this[k]=v;}});
 nodes.get('capability').value='list';nodes.get('url').value='https://watchesbysjx.com/';nodes.get('limit').value='20';nodes.get('profile').value='work';
 let listener;const document={documentElement:{lang:'en'},title:'',getElementById:id=>nodes.get(id),querySelectorAll:()=>texts};
 const context={document,location:{search:'?locale='+locale},URLSearchParams,AI2AppsWebAgent:{onTask:fn=>listener=fn,submit:submit||(async()=>({id:'one',status:'queued'}))}};
 vm.runInNewContext(script,context);return {document,nodes,texts,task:task=>listener(task)};
}
const titles={'en':'Web Reader','zh':'网页阅读器','zh-TW':'網頁閱讀器','de':'Web-Leser','es':'Lector web','fr':'Lecteur web','ja':'ウェブリーダー','ko':'웹 리더','pt-BR':'Leitor web','ru':'Веб-ридер'};
for(const [locale,title] of Object.entries(titles))test(locale+' localizes every field, task status and timeout',async()=>{
 const c=setup(locale);assert.equal(c.document.title,title);assert.equal(c.document.documentElement.lang,locale);
 for(const node of c.texts){assert.equal(typeof node.textContent,'string',node.dataset.text);assert.ok(node.textContent.trim());assert.ok(!node.textContent.includes(' / '));}
 assert.equal(c.nodes.get('capability')['aria-label'],c.texts.find(n=>n.dataset.text==='capability').textContent);
 await c.nodes.get('reader').onsubmit({preventDefault(){}});
 for(const state of ['queued','starting','running','waiting_input','interrupted','completed','failed','cancelled','cancelling','finishing','paused','waiting_browser']){
  c.task({id:'one',status:state});assert.ok(c.nodes.get('status').textContent);assert.notEqual(c.nodes.get('status').textContent,state);
 }
 const err=setup(locale,async()=>{throw Error('Mini-App host connection timed out');});
 await err.nodes.get('reader').onsubmit({preventDefault(){}});assert.ok(err.nodes.get('status').textContent);if(locale!=='en')assert.notEqual(err.nodes.get('status').textContent,'Mini-App host connection timed out');
});
test('regional locales and unknown languages have deterministic fallbacks',()=>{
 for(const [code,expected] of [['en-US','en'],['zh_CN','zh'],['zh-Hant-HK','zh-TW'],['de-DE','de'],['pt-PT','pt-BR'],['ja-JP','ja'],['unknown','en']])assert.equal(setup(code).document.documentElement.lang,expected);
});
test('submission, user content and raw result identity remain unchanged',async()=>{
 let call,resolve;const c=setup('ja-JP',(...args)=>{call=args;return new Promise(r=>resolve=r);});
 const pending=c.nodes.get('reader').onsubmit({preventDefault(){}});assert.equal(c.nodes.get('run').disabled,true);assert.equal(c.nodes.get('run').textContent,'送信中…');
 assert.equal(JSON.stringify(call),JSON.stringify(['list',{url:'https://watchesbysjx.com/',limit:20},{profile:'work'}]));
 resolve({id:'one',status:'queued'});await pending;assert.equal(c.nodes.get('run').disabled,false);assert.equal(c.nodes.get('run').textContent,'実行');
 const result={text:'中文 English 日本語',url:'https://example.com/'};c.task({id:'one',status:'completed',message:'User message 保持原样',result});
 assert.ok(c.nodes.get('status').textContent.endsWith('User message 保持原样'));assert.equal(c.nodes.get('result').textContent,JSON.stringify(result,null,2));
 c.task({id:'other',status:'failed'});assert.ok(c.nodes.get('status').textContent.startsWith('完了'));
 c.nodes.get('capability').value='article';c.nodes.get('capability').onchange();assert.equal(c.nodes.get('limit-row').hidden,true);
});
test('locale coverage matches all system UI dictionaries',()=>{
 const locales=fs.readdirSync(__dirname+'/../web/i18n').filter(n=>n.endsWith('.json')&&n!=='visitor-space-keys.json').map(n=>n.slice(0,-5)).sort();
 assert.deepEqual(Object.keys(titles).sort(),locales);
 assert.ok(!/Web Reader \/|Capability \/|Run \/|Maximum links \//.test(html));
});
