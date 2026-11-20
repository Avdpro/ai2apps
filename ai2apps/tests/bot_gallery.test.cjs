const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const window={};vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_materials.js','utf8'),{window,location:{origin:'http://127.0.0.1:1234'},URL});
const materials=window.AI2AppsBotMaterials;
test('material dragging carries owned resource identity for every media type, never arbitrary paths or remote URLs',()=>{
 for(const suffix of ['png','mp4','wav','pdf','html']){const r=materials.reference('/v1/platform/sessions/ses_1/artifacts/art_'+suffix+'/download');assert.equal(r.type,'application/x-ai2apps-session-artifact');assert.equal(r.value.sessionId,'ses_1');}
 assert.equal(materials.reference('/v1/platform/sessions/ses_a/attachments/att_a/content').value.attachmentId,'att_a');
 assert.equal(materials.reference('/v1/platform/gallery/assets/gala_a/content').value,'gala_a');
 for(const bad of ['https://untrusted.test/v1/platform/sessions/s/artifacts/a/download','file:///private/secret','/private/file','javascript:alert(1)'])assert.equal(materials.reference(bad),null);
});
test('dragging an attachment never exposes its bytes or filesystem path',()=>{
 const events={},node={addEventListener:(name,fn)=>events[name]=fn};materials.bind(node,'/v1/platform/sessions/ses_a/attachments/att_a/content','selected.pdf');const data={};events.dragstart({stopPropagation(){},dataTransfer:{setData:(key,v)=>data[key]=v}});const ref=JSON.parse(data['application/x-ai2apps-session-attachment']);assert.equal(ref.attachmentId,'att_a');assert.equal(ref.sessionId,'ses_a');assert.equal(ref.name,'selected.pdf');assert.equal(Object.keys(data).length,2);
});
test('right sidebar keeps Tasks open and first while settings default closed; Gallery uses system Mini-Entry',()=>{
 const html=fs.readFileSync(__dirname+'/../web/templates/system_apps/messager.html','utf8'),js=fs.readFileSync(__dirname+'/../web/static/js/messager.js','utf8');
 const groups=[...html.matchAll(/<details class="bot-settings-group"( open)?>/g)];assert.equal(groups.length,7);assert.equal(groups[0][1],' open');assert.ok(groups.slice(1).every(m=>!m[1]));assert.ok(html.includes("ui('语音','Voice')"));assert.ok(html.indexOf("'Task · 任务'")<html.indexOf("'Profile · 身份设定'"));
 assert.ok(js.includes("appId:'ai2apps.gallery',placement:'sidebar',requestedBy:'ai2apps.messager'"));assert.ok(html.includes('x-ref="botGallery"'));assert.ok(html.includes("reviewCleanup(currentBot.is_default?'reset':'archive')"));
});

test('output previews do not duplicate canonical media already embedded in the message',()=>{
 const w={};function node(tag){return {tag,children:[],setAttribute(){},append(...v){this.children.push(...v);},addEventListener(){}};}
 vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/bot_materials.js','utf8'),{window:w,location:{origin:'http://127.0.0.1:1234'},URL,document:{createElement:node}});
 const shown='/v1/platform/sessions/session/artifacts/already/preview',missing='/v1/platform/sessions/session/artifacts/new/download';
 const root=node('article');root.querySelectorAll=()=>[{getAttribute:()=>shown}];
 w.AI2AppsBotMaterials.outputs(root,[{url:shown.replace('/preview','/download'),filename:'existing.png',media_type:'image/png'},{url:missing,filename:'new.png',media_type:'image/png'}]);
 assert.equal(root.children.length,1);assert.equal(root.children[0].children.length,1);assert.equal(root.children[0].children[0].children[0].src,missing);
 const only=node('article');only.querySelectorAll=root.querySelectorAll;w.AI2AppsBotMaterials.outputs(only,[{url:shown,filename:'existing.png',media_type:'image/png'}]);assert.equal(only.children.length,0);
});
