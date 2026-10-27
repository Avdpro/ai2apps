const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');const vm=require('node:vm');
const context={document:{documentElement:{lang:'zh'}},window:{AI2APPS_SHELL_BOOT:{apps:[{id:'studio',icon:'palette',name:'画坊'}]}}};
vm.runInNewContext(fs.readFileSync('web/static/js/capability_tree.js','utf8'),context);
const api=context.window.AI2AppsCapabilityTree;
const tools=['image.generate','image.edit'].map(name=>({name,description:'mentions image.generate',capabilities:['workspace.write'],input_schema:{},output_schema:{},effects:[],enabled:true,service:'api',service_status:'enabled'}));
const providers=[{id:'mini-gen',capability:'image.generate',app_id:'studio',mini_app_id:'mini',priority:50,rank:1},{id:'legacy',capability:'image.generate',app_id:'legacy',priority:100,rank:2},{id:'mini-edit',capability:'image.edit',app_id:'studio',mini_app_id:'edit',priority:50,rank:1}];
test('functional tree does not derive membership from permissions',()=>{
 const root=api.build({tools,providers},'');assert(!root.children.has('workspace'));assert.equal(root.children.get('image').children.get('edit').providers.length,1);
});
test('capability/provider searches retain the complete mapping without description false positives',()=>{
 for(const q of ['image.generate','mini-gen']) {
  const image=api.build({tools,providers},q).children.get('image');
  assert(!image.children.has('edit'));assert.equal(image.children.get('generate').providers.length,2);
 }
});
test('App icons and API Tool icons are distinct; permissions stay inside details',()=>{
 const html=api.render(api.build({tools,providers},''),'','');
 assert(html.includes('data-lucide="palette"'));assert(!html.includes('使用此权限的 Tool'));
 const direct=api.render(api.build({tools,providers:[]},''),'','');assert(direct.includes('data-lucide="plug"'));assert(direct.includes('API-Tool'));assert(direct.indexOf('所需权限')>direct.indexOf('</summary>'));
});
