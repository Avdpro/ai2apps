const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync(__dirname+'/../web/static/js/gallery_picker.js','utf8');
function setup() {
 class Element {
  constructor(tag){this.tag=tag;this.children=[];this.attrs={};this.value='';this.handlers={};}
  append(...items){this.children.push(...items);}
  add(item){this.children.push(item);}
  setAttribute(key,value){this.attrs[key]=value;}
  replaceChildren(){this.children=[];}
  addEventListener(key,handler){this.handlers[key]=handler;}
  showModal(){this.open=true;}
  close(){this.open=false;}
  remove(){this.removed=true;}
  focus(){this.focused=true;}
 }
 const body=new Element('body');const focus=new Element('button');
 const context={window:{}, document:{documentElement:{lang:'zh'},body,activeElement:focus,createElement:tag=>new Element(tag)}, Option:function(text,value){this.text=text;this.value=value;},crypto:{randomUUID:()=> 'test'},setTimeout,clearTimeout,URLSearchParams, fetch: async url=>({ok:true,json:async()=>url.includes('/collections')?{items:[]}:{items:[{id:'a',name:'One.txt',kind:'file'},{id:'b',name:'Two.txt',kind:'file'}]}})};
 vm.runInNewContext(source,context);
 return {picker:context.window.AI2AppsGalleryPicker,body,focus};
}
const settle=()=>new Promise(resolve=>setImmediate(resolve));
test('Gallery drag accepts multiple references and deduplicates IDs',()=>{
 const {picker}=setup();
 const transfer={types:['application/x-ai2apps-gallery-assets'],getData:type=>type.endsWith('assets')?'["a","b","a"]':''};
 assert.equal(picker.acceptsDrop(transfer),true);
 assert.deepEqual([...picker.droppedAssetIds(transfer)],['a','b']);
 assert.throws(()=>picker.droppedAssetIds({getData:()=> '[{"id":"a"}]'}));
 assert.equal(picker.acceptsDrop({types:['text/plain']}),false);
 assert.equal(picker.acceptsDrop({types:['Files']}),true);
});
test('Picker returns several selected files only after confirm and restores focus',async()=>{
 const {picker,body,focus}=setup(); const result=picker.open({multiple:true,maxSelection:2});await settle();
 const dialog=body.children[0],grid=dialog.children[3],footer=dialog.children[4];
 grid.children[0].onclick();grid.children[1].onclick();
 assert.equal(grid.children[0].attrs['aria-pressed'],'true');
 footer.children[2].onclick();
 assert.deepEqual([...await result].map(asset=>asset.id),['a','b']);
 assert.equal(dialog.removed,true);assert.equal(focus.focused,true);
});
test('Picker enforces selection limit and Escape discards selection',async()=>{
 const {picker,body}=setup();const result=picker.open({maxSelection:1});await settle();
 const dialog=body.children[0],grid=dialog.children[3];grid.children[0].onclick();grid.children[1].onclick();
 assert.equal(grid.children[1].attrs['aria-pressed'],'false');
 assert.match(dialog.children[2].textContent,/1/);
 dialog.handlers.cancel({preventDefault(){}});assert.equal((await result).length,0);
});

test('Agent resolves Gallery drag IDs through owner API and avoids duplicate references',async()=>{
 const agent=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
 const calls=[];
 const context={state:{attachments:[{asset_id:'a',name:'Existing'}]}, API:'/v1/platform',tr:key=>key,renderAttachments(){},api:async path=>{calls.push(path);return {id:'b',name:'Trusted.txt',media_type:'text/plain',size_bytes:1};},uploadAgentFile:async()=>({asset_id:'b'})};
 vm.runInNewContext(agent.slice(agent.indexOf('    function fileReference('),agent.indexOf('    async function chooseGalleryAttachments('))+'\nglobalThis.add=addAgentAttachments;',context);
 await context.add([],['a','b','b']);
 assert.deepEqual(calls,['/gallery/assets/b']);assert.equal(context.state.attachments.length,2);
 assert.equal(context.state.attachments[1].name,'Trusted.txt');
 await context.add([{}]);assert.equal(context.state.attachments.length,2);
});
test('Agent rejects over-limit attachments before import or lookup',async()=>{
 const agent=fs.readFileSync(__dirname+'/../web/static/js/agent_mini.js','utf8');
 const context={state:{attachments:Array.from({length:8},(_,i)=>({asset_id:String(i)}))},API:'/v1/platform',tr:key=>key,renderAttachments(){},api:async()=>assert.fail('must not look up'),uploadAgentFile:async()=>assert.fail('must not upload')};
 vm.runInNewContext(agent.slice(agent.indexOf('    function fileReference('),agent.indexOf('    async function chooseGalleryAttachments('))+'\nglobalThis.add=addAgentAttachments;',context);
 await assert.rejects(context.add([],['new']),/too_many_files/);
});
