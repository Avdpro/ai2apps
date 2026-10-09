const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
test('creation initializes goal form without saving an empty draft or connecting browser',async()=>{
 const start=source.indexOf('    async function initialize('),end=source.indexOf('            await client();',start);
 const elements=new Map();const $=key=>{if(!elements.has(key))elements.set(key,{focus(){this.focused=true;}});return elements.get(key);};
 const classes=new Set();let created=0,mode;
 const env={URL,location:{href:'https://local/admin/agent-mini?workspace_editor=1&workspace_create=1'},state:{context:{url:'https://example.com/',title:'example.com'}},refreshDrafts:async()=>{},loadBuilderModels:async()=>{},loadWorkspaceProfiles:async()=>{},document:{documentElement:{classList:{add:value=>classes.add(value)}}},switchMode:value=>mode=value,$,tr:key=>key,setContextPinned(){},notice(){},createDraft:()=>{created++;},openDraft:()=>{throw Error('unexpected draft');}};
 vm.runInNewContext(source.slice(start,end)+'        }\n    }\nglobalThis.init=initialize;',env);
 await env.init();assert.equal(created,0);assert.equal(mode,'run');assert.ok(classes.has('agent-workspace-create'));
 assert.equal($('#agent-quick-input').focused,true);assert.equal($('#agent-quick-form button[type=submit]').textContent,'agent.mini.start_build');
});
