const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict'),cp=require('node:child_process'),path=require('node:path');
const ctx={structuredClone,window:{},document:{documentElement:{lang:'en'}}};vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/imagine_studio.js','utf8'),ctx);
const app=ctx.window.imagineStudioApp();app.workflowContract=JSON.parse(fs.readFileSync(__dirname+'/../web/static/data/imagine_workflows.json','utf8'));
const cases=[
 ['extract-items',{target:'top',prompt:'Keep five black buttons.'},()=>{app.extractTarget='top';app.prompt='Keep five black buttons.';return app.extractPrompt();}],
 ['try-on',{interaction:'hold',pose:'custom',pose_description:'Stand next to a chair.',background:'room',prompt:'Keep the logo.'},()=>{app.tryOnInteraction='hold';app.tryOnPose='custom';app.tryOnPoseText='Stand next to a chair.';app.tryOnBackground='room';app.prompt='Keep the logo.';return app.tryOnPrompt();}],
 ['product-poster',{scene:'stone',lighting:'dramatic',composition:'right',setting_style:'minimal',prompt:'Keep the person.'},()=>{app.productScene='stone';app.productLight='dramatic';app.productComposition='right';app.productSettingStyle='minimal';app.prompt='Keep the person.';return app.productPhotoPrompt();}],
];
for(const [name,values,ui] of cases){
 const code='import json,sys;from ai2apps.images.commerce_workflows import compose;v=json.load(sys.stdin);print(compose(v["mini"],v["values"]),end="")';
 const server=cp.execFileSync(path.join(__dirname,'../../.venv/bin/python'),['-c',code],{cwd:path.join(__dirname,'../..'),input:JSON.stringify({mini:'ai2apps.imagine.'+name,values}),encoding:'utf8'});
 assert.equal(ui(),server,name);
}
console.log('Three commerce UI prompts match owner composition exactly');
