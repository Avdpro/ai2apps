const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');const c={URL};vm.runInNewContext(fs.readFileSync(__dirname+'/../web/static/builtin_mini_apps/search-all/web/modes.js','utf8'),c);
const plan={sources:['xiaohongshu','bilibili'],x_sort:'top',xiaohongshu_sort:'likes',limit:5,reason:'菜谱优先参考高赞实践和烹饪演示'};
test('preferred recipe strategy retains chosen source order and likes',()=>{assert.equal(c.SearchAllModes.validatePlan(plan),plan)});
test('unknown sources, duplicate sources and unsupported sorting cannot execute',()=>{for(const bad of [{sources:['unknown']},{sources:['x','x']},{x_sort:'likes'},{xiaohongshu_sort:'random'},{limit:30}])assert.throws(()=>c.SearchAllModes.validatePlan({...plan,...bad}),/Invalid/)});
test('preferred permits only owner-loaded custom source IDs',()=>{const id='custom_test';assert.equal(c.SearchAllModes.validatePlan({...plan,sources:[id]},[id]).sources[0],id);assert.throws(()=>c.SearchAllModes.validatePlan({...plan,sources:['custom_foreign']},[id]),/Invalid/);});
test('website candidates preserve choices but reject dangerous or duplicate URLs',()=>{
 const site={name:'GitHub',url:'https://github.com/',reason:'Official site'};
 const result=c.SearchAllModes.validateSites({question:'Choose website',candidates:[site,{...site},{...site,url:'javascript:alert(1)'}]});
 assert.equal(result.length,1);assert.equal(result[0].url,site.url);
 assert.equal(c.SearchAllModes.validateSites({question:'Clarify',candidates:[]}).length,0);
 assert.throws(()=>c.SearchAllModes.validateSites({question:'',candidates:[site,site,site,site]}),/Invalid/);
});
