const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(__dirname+'/../browser/bilibili_content.js','utf8');
async function read({video={},videos=[],description='',resources=[],fetch,viewFetch,host='www.bilibili.com',part=1,maxChars=12000}={}){
 const context={URL,URLSearchParams,AbortSignal,TextDecoder,Uint8Array,ai2appsDOMVisible:()=>true,
 location:{href:`https://${host}/video/BV123456/`+(part===1?'':'?p='+part),hostname:host,pathname:'/video/BV123456/'},
 __INITIAL_STATE__:{videoData:{bvid:'BV123456',title:'回锅肉',...video}},
 performance:{getEntriesByType:()=>resources.map(name=>({name}))},fetch:(url,opts)=>url.startsWith('https://api.bilibili.com/x/web-interface/view?')?(viewFetch?viewFetch(url,opts):response({code:-404})):(fetch||(()=>{throw Error('unexpected fetch')}))(url,opts),
 document:{title:'回锅肉',querySelector:()=>null,querySelectorAll:s=>s==='video'?videos:s.includes('#v_desc')&&description?[{innerText:description}]:[]}};
 return vm.runInNewContext('('+source+')',context)(maxChars);
}
test('uses current video description and never duration/recommendation content',async()=>{
 const result=await read({video:{desc:'五花肉煮至八成熟，切薄片煸出油脂，加豆瓣酱炒出红油，最后下蒜苗。'}});
 assert.equal(result.content_kind,'description');assert.match(result.text,/豆瓣酱/);
 const empty=await read({description:'02:31 08:09 05:24 12:37'});assert.equal(empty.text,'');assert.equal(empty.reason,'video_content_unavailable');
});
test('subtitles precede description, exact page URL retained',async()=>{
 const result=await read({video:{desc:'这是当前视频的详细说明，内容超过最小阈值。'},videos:[{textTracks:[{cues:[{startTime:1,endTime:3.2,text:'先把带皮猪肉煮熟，再切成薄片，放入锅里煸炒出油。'}]}]}]});
 assert.equal(result.content_kind,'subtitles');assert.match(result.text,/00:00:01.000 --> 00:00:03.200/);assert.match(result.text,/视频说明/);assert.equal(result.url,'https://www.bilibili.com/video/BV123456/');
 assert.equal(result.subtitle_cues[0].start_ms,1000);assert.equal(result.subtitle_video_url,result.url);
});
test('ignores another video initial state and rejects non-Bilibili pages',async()=>{
 assert.equal((await read({video:{bvid:'BVother',desc:'这是推荐视频的说明，绝对不能当作当前视频的正文。'}})).text,'');
 assert.equal(await read({host:'bilibili.com.attacker.test'}),null);
});
test('observed subtitles are bounded and fetched without credentials/redirects',async()=>{
 let called=0;
 const result=await read({video:{subtitle:{list:[{subtitle_url:'https://evil.test/subtitle.json'},{subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}},fetch:async(url,options)=>{
 called++;assert.equal(options.credentials,'omit');assert.equal(options.redirect,'error');
 const bytes=new TextEncoder().encode(JSON.stringify({body:[{from:0,to:5,content:'猪肉煮八成熟后切片，先炒肉再炒豆瓣酱，最后加入蒜苗。'}]}));let sent=false;
 return {ok:true,body:{getReader:()=>({read:async()=>sent?{done:true}:(sent=true,{done:false,value:bytes}),cancel:async()=>{}})}};
 }});assert.equal(called,1);assert.equal(result.content_kind,'subtitles');
});
test('subtitle errors preserve cause and fall back to actual description',async()=>{
 const result=await read({video:{desc:'这是视频作者的食材说明，五花肉搭配蒜苗和郫县豆瓣酱。',subtitle:{list:[{subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}},fetch:async()=>({ok:false,status:403})});
 assert.equal(result.content_kind,'description');assert.equal(result.content_warnings[0].message,'http_403');
});
test('rejects HTML disguised as subtitles and records format error',async()=>{
 const bytes=new TextEncoder().encode('<html>登录后查看字幕，不能把错误页面当作视频正文。</html>');let sent=false;
 const result=await read({video:{subtitle:{list:[{subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}},fetch:async()=>({ok:true,body:{getReader:()=>({read:async()=>sent?{done:true}:(sent=true,{value:bytes}),cancel:async()=>{}})}})});
 assert.equal(result.text,'');assert.equal(result.content_warnings[0].message,'subtitle_invalid_format');
});
function response(value){const bytes=new TextEncoder().encode(typeof value==='string'?value:JSON.stringify(value));let sent=false;return {ok:true,body:{getReader:()=>({read:async()=>sent?{done:true}:(sent=true,{value:bytes}),cancel:async()=>{}})}};}
test('discovers bound player tracks then fetches timed full text and retains video URL',async()=>{
 const requests=[];
 const result=await read({video:{aid:10,cid:123},fetch:async(url,opts)=>{
  requests.push([url,opts.credentials]);
  if(url.startsWith('https://api.bilibili.com/')){const q=new URL(url);assert.equal(q.pathname,'/x/player/wbi/v2');assert.equal(q.searchParams.get('cid'),'123');assert.equal(q.searchParams.get('bvid'),'BV123456');return response({code:0,data:{cid:123,subtitle:{subtitles:[{id:8,lan:'zh-CN',lan_doc:'中文',subtitle_url:'//i0.hdslb.com/bfs/subtitle/caption.json'}]}}});}
  return response({body:[{from:0,to:2.5,content:'先煮肉。'},{from:3.125,to:6,content:'切成薄片再煸炒。'}]});
 }});
 assert.equal(requests.length,2);assert.equal(requests[0][1],'include');assert.equal(requests[1][1],'omit');
 assert.equal(result.content_kind,'subtitles');assert.equal(result.subtitle_discovery.status,'subtitles_loaded');
 assert.equal(result.subtitle_track.language,'zh-CN');assert.equal(result.subtitle_cues.length,2);assert.equal(result.subtitle_cues[1].start_ms,3125);
 assert.match(result.subtitle_text,/00:00:03.125 --> 00:00:06.000/);assert.equal(result.subtitle_video_url,result.url);
});
test('login requirement and API denial are distinct from a video without tracks',async()=>{
 for(const [payload,status] of [[{code:0,data:{need_login_subtitle:true}},'login_required'],[{code:0,data:{subtitle:{subtitles:[]}}},'no_tracks'],[{code:-403,message:'access denied'},'api_error']]){
  const result=await read({video:{cid:123},fetch:async()=>response(payload)});assert.equal(result.subtitle_discovery.status,status);assert.notEqual(result.content_kind,'subtitles');
 }
});
test('refuses a track response for another part or another video',async()=>{
 let n=0;const result=await read({video:{cid:123},fetch:async()=>{n++;return response({code:0,data:{cid:456,subtitle:{subtitles:[{lan:'zh',subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}}});}});
 assert.equal(n,1);assert.equal(result.subtitle_discovery.status,'discovery_failed');assert.match(result.subtitle_discovery.message,/identity_mismatch/);assert.equal(result.subtitle_cues,undefined);
});
test('preserves VTT timecodes and refuses invalid JSON cue times',async()=>{
 for(const [raw,valid] of [['WEBVTT\n\n00:00:01.125 --> 00:00:05.000\n先煮肉再切片，回锅煸炒出油。\n',true],['1\n00:00:01,125 --> 00:00:05,000\n先煮肉再切片，回锅煸炒出油。\n',true],[{body:[{from:5,to:1,content:'非法倒置时间'}]},false]]){
  const result=await read({video:{subtitle:{list:[{lan:'zh',subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}},fetch:async()=>response(raw)});
  if(valid){assert.equal(result.subtitle_cues[0].start_ms,1125);assert.equal(result.subtitle_cues[0].end_ms,5000);}
  else{assert.equal(result.subtitle_cues,undefined);assert.equal(result.content_warnings[0].message,'subtitle_invalid_cue');}
 }
});
test('uses selected part CID and preserves full timed cues beyond model preview',async()=>{
 const rows=Array.from({length:100},(_,i)=>({from:i,to:i+1,content:'回锅肉先煮后炒，薄切煸出油再加入豆瓣和蒜苗。'}));
 const result=await read({part:2,maxChars:100,video:{cid:111,pages:[{page:1,cid:111},{page:2,cid:222}]},fetch:async(url)=>{
  if(url.startsWith('https://api.bilibili.com/')){assert.equal(new URL(url).searchParams.get('cid'),'222');return response({code:0,data:{cid:222,subtitle:{subtitles:[{lan:'zh',subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}}});}
  return response({body:rows});
 }});
 assert.equal(result.subtitle_cues.length,100);assert.equal(result.subtitle_cues.at(-1).end_ms,100000);assert.ok(result.subtitle_text.length>100);assert.equal(result.text.length,100);assert.equal(result.truncated,true);assert.match(result.subtitle_video_url,/\?p=2$/);
 assert.equal(result.subtitle_discovery.cue_count,100);assert.equal(result.subtitle_discovery.start_ms,0);assert.equal(result.subtitle_discovery.end_ms,100000);
});
test('resolves missing page identity with exact video metadata before track lookup',async()=>{
 const result=await read({video:{bvid:'BVother'},viewFetch:async(url)=>{assert.equal(new URL(url).searchParams.get('bvid'),'BV123456');return response({code:0,data:{bvid:'BV123456',aid:10,cid:123,title:'当前视频'}});},fetch:async(url)=>url.includes('/x/player/wbi/v2?')?response({code:0,data:{cid:123,subtitle:{subtitles:[{lan:'zh',subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}}}):response({body:[{from:0,to:1,content:'实际字幕'}]})});
 assert.equal(result.subtitle_discovery.cid,123);assert.equal(result.content_kind,'subtitles');assert.equal(result.title,'当前视频');
});
test('AI language tracks retain automatic-caption provenance without ai_type',async()=>{
 const result=await read({video:{subtitle:{list:[{lan:'ai-zh',subtitle_url:'https://aisubtitle.hdslb.com/subtitle.json'}]}},fetch:async()=>response({body:[{from:0,to:1,content:'实际字幕'}]})});
 assert.equal(result.subtitle_track.automatic,true);assert.equal(result.subtitle_tracks[0].automatic,true);
});
