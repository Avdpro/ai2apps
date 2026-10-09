const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const src=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
const env={URL};vm.runInNewContext(src.slice(src.indexOf('    function isSearchField('),src.indexOf('    function explorationActionNeedsConfirmation('))+'\nglobalThis.field=isSearchField;globalThis.search=requestedSearchInteraction;',env);
test('only observed search fields qualify for read-only query input',()=>{
 assert.equal(env.field({role:'searchbox'}),true);assert.equal(env.field({name:'搜索微博',role:'textbox'}),true);
 assert.equal(env.field({name:'有什么新鲜事想分享给大家',role:'textbox'}),false);assert.equal(env.field({name:'手机号',role:'textbox'}),false);
});
test('foundation search works on website search without allowing publishing or credentials',()=>{
 const step={operation:'input',target:{intent:'搜索微博'},description:'输入查询并按回车',arguments:{foundation_read_only:true,foundation_search_goal:'搜索数字人'}};
 assert.equal(env.search(step,'','https://weibo.com/'),true);
 assert.equal(env.search({...step,target:{intent:'发送微博'}},'','https://weibo.com/'),false);
 assert.equal(env.search({...step,target:{intent:'登录密码'}},'','https://weibo.com/'),false);
 assert.equal(env.search(step,'','file:///tmp/test'),false);
});

const strictURL=class extends URL {constructor(value){if(/^https?:\/\/[^/]*\*/.test(value))throw Error('Firefox rejects wildcard host');super(value);}};
const scopeEnv={URL:strictURL};vm.runInNewContext(src.slice(src.indexOf('    function scopeAllows('),src.indexOf('    async function client('))+'\nglobalThis.allows=scopeAllows;',scopeEnv);
test('wildcard foundation scopes work with Firefox URL parsing and retain boundaries',()=>{
 assert.equal(scopeEnv.allows('https://weibo.com/',['https://*/**']),true);
 assert.equal(scopeEnv.allows('https://s.weibo.com/weibo?q=test',['https://*.weibo.com/**']),true);
 assert.equal(scopeEnv.allows('https://evil.com/',['https://weibo.com/**']),false);
 assert.equal(scopeEnv.allows('https://weibo.com:8443/',['https://weibo.com/**']),false);
 assert.equal(scopeEnv.allows('file:///tmp/test',['https://*/**']),false);
});
