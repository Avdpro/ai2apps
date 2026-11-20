const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const ctx={window:{t:key=>key},document:{documentElement:{lang:'en'}},crypto:{randomUUID:()=> 'fixture'}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync(__dirname+'/../web/static/js/video_studio.js','utf8'),ctx);
const app=ctx.window.videoStudioApp();
app.providers=[{id:'byok/volcengine/model',sourceType:'byok',byokProvider:'volcengine',resolutionSemantics:'documented-pixels',
 resolutionOptions:[{value:'1112x834',label:'720p · 1112x834 · 4:3'},{value:'3326x2494',label:'4k · 3326x2494 · 4:3'}],
 videoCapabilities:{geometry:{resolutions:['1112x834','3326x2494'],ratios:['16:9','4:3','1:1']},defaults:{framespersecond:24}}}];
app.modelId=app.providers[0].id;app.resolution='1112x834';app.prompt='test';
assert.equal(app.resolutions.length,2);assert.match(app.resolutionLabel(app.resolution),/720p/);
assert.equal(app.requestPayload().ratio,'4:3');assert.equal(app.requestPayload().resolution,'1112x834');
app.providers=[{id:'byok/minimax/model',sourceType:'byok',byokProvider:'minimax',resolutionSemantics:'tier-and-ratio',
 resolutionOptions:[{value:'1366x768',label:'768P'},{value:'2048x1152',label:'2K'}],
 videoCapabilities:{geometry:{resolutions:['1366x768','768x1366','2048x1152','1152x2048'],ratios:['16:9','4:3','1:1']},defaults:{framespersecond:24}}}];
app.modelId=app.providers[0].id;app.resolution='2048x1152';app.byokRatio='4:3';
assert.equal(app.resolutions.length,2);assert.equal(app.resolutionLabel(app.resolution),'2K');
assert.equal(app.requestPayload().ratio,'4:3');assert.equal(app.requestPayload().resolution,'2048x1152');
console.log('BYOK video resolution options and tier/ratio submission passed');
