const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const context={window:{addEventListener(){},},document:{documentElement:{lang:'en'}}};
vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/js/capability_provisioning.js','utf8'),context);
const select=context.window.AI2AppsCapabilities.miniAppPackageComponents;
test('ACPF Mini-App selection requires declared host placement',()=>{
 const reader={componentId:'reader',placements:['ai2apps.ai-browser']},image={componentId:'image',placements:['ai2apps.imagine-studio']};
 assert.equal(select({miniApps:[reader,image]},'ai2apps.ai-browser').length,1);
 assert.equal(select({manifest:{miniApps:[reader]}},'ai2apps.ai-browser')[0],reader);
 assert.equal(select({miniApps:[image]},'ai2apps.ai-browser').length,0);
 assert.equal(select({miniApps:[{componentId:'unknown'}]},'ai2apps.ai-browser').length,0);
 assert.equal(select({miniApps:'invalid'},'ai2apps.ai-browser').length,0);
});
