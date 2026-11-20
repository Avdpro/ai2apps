/* Owner settings: ASR + original Bot + selected TTS, configured via existing ACPF. */
(()=>{'use strict';
 const path=id=>'/v1/platform/messager/bots/'+encodeURIComponent(id)+'/realtime/settings';
 async function json(url,options={}){const r=await fetch(url,{credentials:'same-origin',...options});const v=await r.json();if(!r.ok)throw Error(v.error?.message||v.detail||'Realtime settings failed');return v;}
 async function catalog(){const [models,profiles]=await Promise.all([json('/admin/api/models'),json('/v1/platform/readaloud/voice-profiles')]);const ready=(models.models||[]).filter(m=>m.checkpoint_ready!==false&&!m.is_hidden&&!m.load_failed&&(!(m.source_type==='package'||m.engine_type==='package')||m.checkpoint_ready===true));return {stt:ready.filter(m=>m.model_type==='audio_stt'),tts:ready.filter(m=>m.model_type==='audio_tts'),profiles:(profiles.items||[]).filter(p=>p.status==='ready')};}
 function clean(s){return {stt_model_id:s.stt_model_id||null,tts_model_id:s.tts_model_id||null,voice:s.voice||null,profile_id:s.profile_id||null,revision:s.revision};}
 window.AI2AppsBotRealtimeSettings={catalog,load:id=>json(path(id)),save:(id,s)=>json(path(id),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(clean(s))})};
})();
