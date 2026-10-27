const test=require('node:test'),assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync(__dirname+'/../web/static/js/mobile_chat.js','utf8');
function functionSource(name,next){const a=source.indexOf('    async function '+name+'(');return source.slice(a,source.indexOf('    async function '+next+'(',a));}
test('large video selection retains File without whole-file read or base64',async()=>{
 const ctx={busy:false,attachments:[],fileInput:{value:'selected'},notify:()=>assert.fail(),renderAttachments(){}};
 vm.runInNewContext(functionSource('addFiles','uploadAttachment')+';this.addFiles=addFiles;',ctx);
 const file={name:'large.mp4',size:3*1024**3};await ctx.addFiles([file]);assert.equal(ctx.attachments[0].file,file);assert.equal(ctx.attachments[0].data,undefined);
});
test('bounded signed upload shows committed progress and reuses the uploaded reference',async()=>{
 const writes=[],progress=[],slices=[];let received=0;
 const item={file:{name:'video.mp4',type:'video/mp4',size:9*1024**2,slice(a,b){assert.ok(b-a<=4*1024**2);slices.push([a,b]);return {a,b};}}};
 const ctx={current:{id:'session'},encodeURIComponent,Math,JSON,working:(...x)=>progress.push(x),request:async(url,opt)=>{
  writes.push([url,opt]);if(url.endsWith('/uploads'))return {id:'upload',chunk_bytes:4*1024**2};
  if(url.endsWith('/complete'))return {id:'attc_ref',metadata:{gallery_asset_id:'gala_ref'}};
  assert.equal(new URL(url,'https://test').searchParams.get('offset'),String(received));received=opt.body.b;return {received_bytes:received};
 }};
 vm.runInNewContext(functionSource('uploadAttachment','buildContent')+';this.upload=uploadAttachment;',ctx);
 const result=await ctx.upload(item);assert.equal(result.id,'attc_ref');assert.equal(slices.length,3);assert.ok(progress.some(p=>p[1].includes('100%')));
 await ctx.upload(item);assert.equal(writes.length,5);
});
test('failed chunks cancel temporary upload and never complete it',async()=>{
 const calls=[];const ctx={current:{id:'s'},encodeURIComponent,Math,JSON,working(){},request:async(url)=>{calls.push(url);if(url.endsWith('/uploads'))return {id:'u',chunk_bytes:4};if(url.includes('?offset='))throw Error('network');return {};}};
 vm.runInNewContext(functionSource('uploadAttachment','buildContent')+';this.upload=uploadAttachment;',ctx);
 await assert.rejects(()=>ctx.upload({file:{name:'x',size:8,slice:()=>({})}}),/network/);
 assert.ok(calls.at(-1).endsWith('/cancel'));assert.ok(!calls.some(p=>p.endsWith('/complete')));
});
test('video content persists only IDs and metadata; file selector accepts video',()=>{
 const body=functionSource('buildContent','persist');assert.ok(!body.includes('file_data'));
 assert.match(body,/storage:'reference'/);assert.match(body,/gallery_asset_id/);
 assert.match(fs.readFileSync(__dirname+'/../web/templates/mobile_chat_content.html','utf8'),/video\/\*/);
});
