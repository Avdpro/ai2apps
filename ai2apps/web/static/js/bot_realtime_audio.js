/* Bounded local VAD + WAV transport for the existing authenticated ASR API. */
((root,factory)=>{const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;if(root)root.AI2AppsBotRealtimeAudio=api;})(typeof globalThis!=='undefined'?globalThis:this,()=>{
 'use strict';
 const processorUrl=typeof document!=='undefined'&&document.currentScript?.src?new URL('bot_realtime_processor.js',document.currentScript.src).href:'/admin/static/js/bot_realtime_processor.js';
 function wav(blocks,rate){const length=blocks.reduce((n,b)=>n+b.length,0),buffer=new ArrayBuffer(44+length*2),v=new DataView(buffer);let p=44;
  const str=(at,s)=>{for(let i=0;i<s.length;i++)v.setUint8(at+i,s.charCodeAt(i));};str(0,'RIFF');v.setUint32(4,36+length*2,true);str(8,'WAVE');str(12,'fmt ');v.setUint32(16,16,true);v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,rate,true);v.setUint32(28,rate*2,true);v.setUint16(32,2,true);v.setUint16(34,16,true);str(36,'data');v.setUint32(40,length*2,true);
  for(const block of blocks)for(const sample of block){v.setInt16(p,Math.round(Math.max(-1,Math.min(1,sample))*32767),true);p+=2;}return new Blob([buffer],{type:'audio/wav'});
 }
 class Vad {
  constructor(rate,emit){this.rate=rate;this.emit=emit;this.reset();}
  reset(){this.blocks=[];this.pre=[];this.samples=0;this.silence=0;this.voiced=0;this.lastPartial=0;this.turn=null;this.attack=0;}
  push(block){let power=0;for(const v of block)power+=v*v;const rms=Math.sqrt(power/block.length),voice=rms>.015,dt=block.length/this.rate;
   this.emit({type:'level',value:Math.min(1,rms*8)});
   if(!this.turn){this.pre.push(block);while(this.pre.length>Math.ceil(.2/dt))this.pre.shift();this.attack=voice?this.attack+dt:0;if(this.attack<.085)return;this.turn=crypto.randomUUID();this.blocks=this.pre.slice();this.pre=[];this.samples=this.blocks.reduce((n,b)=>n+b.length,0);this.voiced=this.attack;this.emit({type:'start',turn:this.turn});}
   else{this.blocks.push(block);this.samples+=block.length;if(voice)this.voiced+=dt;}
   this.silence=voice?0:this.silence+dt;
   const seconds=this.samples/this.rate;
   if(this.silence>=.7&&this.voiced<.24){this.reset();return;}
   if((this.silence>=.7&&this.voiced>=.24)||seconds>=18){const event={type:'final',turn:this.turn,audio:wav(this.blocks,this.rate)};this.reset();this.emit(event);}
   else if(seconds-this.lastPartial>=1.6){this.lastPartial=seconds;this.emit({type:'partial',turn:this.turn,audio:wav(this.blocks,this.rate)});}
  }
 }
 async function capture(emit,signal){let stream,context,node,source,unlock,closing;const close=()=>{if(closing)return closing;node?.disconnect();source?.disconnect();stream?.getTracks().forEach(t=>t.stop());const released=unlock?.();unlock=null;closing=Promise.all([context?.close().catch(()=>{}),released]);return closing;};
  try{unlock=await window.AI2AppsMicrophoneLease.acquire();if(signal.aborted)throw new DOMException('Aborted','AbortError');
   stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true,channelCount:1}});if(signal.aborted)throw new DOMException('Aborted','AbortError');
   context=new AudioContext();await context.audioWorklet.addModule(processorUrl);if(signal.aborted)throw new DOMException('Aborted','AbortError');
   const vad=new Vad(context.sampleRate,emit);source=context.createMediaStreamSource(stream);node=new AudioWorkletNode(context,'bot-realtime-capture');node.port.onmessage=e=>{if(!signal.aborted)vad.push(e.data);};source.connect(node);const gain=context.createGain();gain.gain.value=0;node.connect(gain);gain.connect(context.destination);await context.resume();
   const onEnded=()=>{if(!signal.aborted)emit({type:'error',error:Error('Microphone disconnected')});};stream.getAudioTracks().forEach(t=>t.addEventListener('ended',onEnded));signal.addEventListener('abort',close,{once:true});
   return {close(){signal.removeEventListener('abort',close);return close();},mute(value){stream.getAudioTracks().forEach(t=>t.enabled=!value);vad.reset();},settings:stream.getAudioTracks()[0].getSettings()};
  }catch(error){close();throw error;}
 }
 return {wav,Vad,capture};
});
