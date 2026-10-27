async function(maxChars) {
  const maximum=Math.min(100000,Math.max(100,Number(maxChars)||20000)),url=location.href;
  const videoId=location.pathname.match(/^\/video\/(BV\w+|av\d+)/i)?.[1];
  if(!['www.bilibili.com','m.bilibili.com'].includes(location.hostname)||!videoId)return null;
  const clean=v=>typeof v==='string'?v.replace(/\r/g,'').trim():'';
  const meaningful=v=>clean(v).replace(/\b\d{1,2}:\d{2}(?::\d{2})?\b/g,'').replace(/[\d\s\p{P}\p{S}]/gu,'').length>=12;
  const visibleText=s=>Array.from(document.querySelectorAll(s)).filter(ai2appsDOMVisible).map(n=>clean(n.innerText||n.textContent)).filter(Boolean).join('\n');
  let state=globalThis.__INITIAL_STATE__||{};
  if(!state.videoData)for(const node of document.querySelectorAll('script')){
    const match=(node.textContent||'').match(/(?:window\.)?__INITIAL_STATE__\s*=\s*([\s\S]*?);\s*(?:\(function|$)/);
    if(match)try{state=JSON.parse(match[1]);}catch(_){}
  }
  const candidate=state.videoData||state.videoInfo||{};
  let identityMatches=candidate.bvid===videoId||'av'+candidate.aid===videoId;
  let video=identityMatches?candidate:{};
  const part=Math.max(1,Number(new URL(url).searchParams.get('p')||1));
  let page=Array.isArray(video.pages)?video.pages.find(p=>Number(p.page)===part):null;
  let cid=Number(page?.cid||(part===1?video.cid:0));
  let title=clean(video.title)||clean(document.querySelector('h1')?.textContent)||document.title;
  const warnings=[],tracks=[],sections=[];
  let discovery={status:'identity_unavailable',bvid:video.bvid||null,cid:Number.isSafeInteger(cid)&&cid>0?cid:null,part};
  async function download(resource,credentials){
    const response=await fetch(resource,{credentials,redirect:'error',signal:AbortSignal.timeout(8000)});
    if(!response.ok)throw new Error('http_'+response.status);
    const reader=response.body.getReader();let size=0,chunks=[];
    try{for(;;){const {done,value}=await reader.read();if(done)break;size+=value.byteLength;if(size>1048576)throw new Error('response_too_large');chunks.push(value);}}
    finally{await reader.cancel();}
    const bytes=new Uint8Array(size);let offset=0;for(const chunk of chunks){bytes.set(chunk,offset);offset+=chunk.byteLength;}
    return new TextDecoder().decode(bytes);
  }
  // SPA/hydration layouts may omit INITIAL_STATE. Resolve identity through the
  // fixed official video metadata endpoint, never a URL supplied by page text.
  if(!identityMatches||!Number.isSafeInteger(cid)||cid<=0){
    try{
      const query=new URLSearchParams(videoId.startsWith('BV')?{bvid:videoId}:{aid:videoId.slice(2)});
      const info=JSON.parse(await download('https://api.bilibili.com/x/web-interface/view?'+query,'include'));
      const data=info.data||{};
      if(info.code!==0)throw new Error('metadata_api_'+info.code);
      if(!(data.bvid===videoId||'av'+data.aid===videoId))throw new Error('metadata_video_identity_mismatch');
      page=Array.isArray(data.pages)?data.pages.find(p=>Number(p.page)===part):null;
      const resolved=Number(page?.cid||(part===1?data.cid:0));
      if(!Number.isSafeInteger(resolved)||resolved<=0)throw new Error('metadata_part_unavailable');
      video=data;identityMatches=true;cid=resolved;title=clean(video.title)||title;
      discovery={status:'identity_resolved',bvid:video.bvid||null,cid,part};
    }catch(error){discovery.metadata_error=String(error.message||error).slice(0,200);}
  }
  function addTrack(t,origin){
    const raw=t?.subtitle_url||t?.src;
    if(typeof raw!=='string')return;
    try{
      const r=new URL(raw,url);
      const allowed=r.hostname==='aisubtitle.hdslb.com'||r.hostname==='subtitle.bilibili.com'||
        (['i0.hdslb.com','i1.hdslb.com','i2.hdslb.com'].includes(r.hostname)&&/^\/bfs\/(?:ai_)?subtitle\//.test(r.pathname));
      if(r.protocol!=='https:'||r.username||r.password||r.port||!allowed)return;
      if(!tracks.some(t=>t.url===r.href))tracks.push({id:String(t.id_str||t.id||tracks.length+1),language:clean(t.lan||t.srclang),label:clean(t.lan_doc||t.label),automatic:!!t.ai_type||/^ai-/i.test(clean(t.lan||t.srclang)),url:r.href,discovered_by:origin});
    }catch(_){}
  }
  // Discover tracks for exactly this video's selected part. Authentication stays
  // inside its existing browser Profile; cookies are never read or exported.
  if(identityMatches&&Number.isSafeInteger(cid)&&cid>0){
    const query=new URLSearchParams({cid:String(cid),...(video.bvid?{bvid:video.bvid}:{aid:String(video.aid)})});
    try{
      const data=JSON.parse(await download('https://api.bilibili.com/x/player/wbi/v2?'+query,'include'));
      if(data.code!==0){discovery.status=data.code===-101?'login_required':'api_error';discovery.code=data.code;discovery.message=clean(data.message).slice(0,200);}
      else{
        const info=data.data||{};
        // Some responses include identity fields; any mismatch is a hard error.
        if((info.cid!=null&&Number(info.cid)!==cid)||(info.bvid&&video.bvid&&info.bvid!==video.bvid)||(info.aid!=null&&video.aid&&Number(info.aid)!==Number(video.aid)))throw new Error('subtitle_video_identity_mismatch');
        for(const t of info.subtitle?.subtitles||[])addTrack(t,'player_api');
        discovery.status=tracks.length?'tracks_found':info.need_login_subtitle?'login_required':'no_tracks';
        discovery.need_login=!!info.need_login_subtitle;
      }
    }catch(error){discovery.status='discovery_failed';discovery.message=String(error.message||error).slice(0,200);}
  }
  for(const t of video.subtitle?.list||[])addTrack(t,'video_state');
  if(identityMatches)for(const t of globalThis.__playinfo__?.data?.subtitle?.subtitles||[])addTrack(t,'player_state');
  for(const t of document.querySelectorAll('track[src]'))addTrack({src:t.src,srclang:t.srclang,label:t.label},'text_track');
  // Performance entries are accepted only when they match a discovered track,
  // avoiding stale subtitle resources from a previous SPA video.
  const score=t=>(/^(?:zh|ai-zh|cn)/i.test(t.language)?0:10)+(t.automatic?1:0);
  tracks.sort((a,b)=>score(a)-score(b));
  function cue(from,to,text){
    if(typeof from!=='number'||typeof to!=='number'||!Number.isFinite(from)||!Number.isFinite(to)||from<0||to<from||to>259200||!clean(text))throw new Error('subtitle_invalid_cue');
    return {start_ms:Math.round(from*1000),end_ms:Math.round(to*1000),text:clean(text)};
  }
  function parse(raw){
    try{const data=JSON.parse(raw);if(!Array.isArray(data.body)||!data.body.length||data.body.length>20000)throw new Error('subtitle_invalid_body');return data.body.map(c=>cue(c.from,c.to,c.content));}
    catch(error){
      if(error.message?.startsWith('subtitle_'))throw error;
      if(!/^WEBVTT\b/.test(raw)&&!/\d{2}:\d{2}[.,]\d{3}\s*-->/.test(raw))throw new Error('subtitle_invalid_format');
      const seconds=t=>t.replace(',','.').split(':').reduce((n,v)=>n*60+Number(v),0),out=[];
      for(const block of raw.replace(/\r/g,'').split(/\n\s*\n/)){
        const lines=block.split('\n'),i=lines.findIndex(l=>l.includes('-->'));if(i<0)continue;
        const m=lines[i].match(/^\s*((?:\d+:)?\d{2}:\d{2}[.,]\d{3})\s*-->\s*((?:\d+:)?\d{2}:\d{2}[.,]\d{3})/);
        if(!m)throw new Error('subtitle_invalid_timing');out.push(cue(seconds(m[1]),seconds(m[2]),lines.slice(i+1).join('\n').replace(/<[^>]*>/g,'')));
      }
      if(!out.length)throw new Error('subtitle_empty');return out;
    }
  }
  let cues=[],selected=null;
  for(const t of tracks.slice(0,4)){
    try{cues=parse(await download(t.url,'omit'));selected=t;break;}
    catch(error){warnings.push({phase:'subtitle_download',track_id:t.id,language:t.language,message:String(error.message||error).slice(0,200)});}
  }
  if(!cues.length)for(const media of document.querySelectorAll('video'))for(const track of Array.from(media.textTracks||[])){
    try{const native=Array.from(track.cues||[]).map(c=>cue(c.startTime,c.endTime,c.text));if(native.length>cues.length){cues=native;selected={id:String(track.id||'native'),language:track.language||'',label:track.label||'',discovered_by:'text_track_cues'};}}
    catch(error){warnings.push({phase:'text_track',message:String(error.message||error).slice(0,200)});}
  }
  const stamp=ms=>{const h=Math.floor(ms/3600000),m=Math.floor(ms/60000)%60,s=Math.floor(ms/1000)%60;return [h,m,s].map(v=>String(v).padStart(2,'0')).join(':')+'.'+String(ms%1000).padStart(3,'0');};
  const subtitleText=cues.map(c=>'['+stamp(c.start_ms)+' --> '+stamp(c.end_ms)+'] '+c.text).join('\n');
  if(cues.length){sections.push({kind:'subtitles',text:subtitleText});Object.assign(discovery,{status:'subtitles_loaded',
    language:selected?.language||'',cue_count:cues.length,
    start_ms:cues.reduce((n,c)=>Math.min(n,c.start_ms),Infinity),end_ms:cues.reduce((n,c)=>Math.max(n,c.end_ms),0)});}
  const transcript=visibleText('.video-transcript, [data-testid="video-transcript"], .bpx-player-transcript-panel');
  if(!cues.length&&meaningful(transcript))sections.push({kind:'transcript',text:transcript});
  const descriptions=[clean(video.desc),(Array.isArray(video.desc_v2)?video.desc_v2.map(x=>clean(x.raw_text)).join(''):''),visibleText('#v_desc .basic-desc-info, .video-desc-container .basic-desc-info, .video-desc .desc-info-text, .video-desc')];
  const description=descriptions.filter(s=>s!==title&&meaningful(s)).sort((a,b)=>b.length-a.length)[0]||'';
  if(description)sections.push({kind:'description',text:description});
  const full=sections.map(s=>(s.kind==='description'?'视频说明':'字幕/转录')+'\n'+s.text).join('\n\n');
  return {url,title,text:full.slice(0,maximum),truncated:full.length>maximum,content_kind:sections[0]?.kind||'unavailable',
    content_sections:sections.map(s=>({kind:s.kind,text:s.text.slice(0,maximum)})),extraction_method:'bilibili-video-content',content_warnings:warnings,
    subtitle_discovery:discovery,subtitle_tracks:tracks.map(({url,...t})=>t),
    ...(cues.length?{subtitle_cues:cues,subtitle_text:subtitleText,subtitle_track:selected,subtitle_video_url:url}:{}),
    ...(full?{}:{reason:discovery.status==='login_required'?'subtitle_login_required':'video_content_unavailable',fallback_reason:'No usable subtitle/transcript or description; '+discovery.status+(discovery.code!=null?' ('+discovery.code+')':'')+(discovery.message?': '+discovery.message:'')})};
}
