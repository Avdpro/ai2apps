/* Canonical Package UI adapter. Functional execution belongs exclusively to AaAT. */
(function(){'use strict';
 const REQUEST='ai2apps.mini-app-chat.provider-request',RESPONSE='ai2apps.mini-app-chat.provider-response';
 function install(options){
  const fields=options.fields||{};
  function element(key){const el=document.getElementById(key);if(!el||['file','password','hidden','submit','button'].includes(el.type))throw Error('Unavailable declared UI field: '+key);return el;}
  function value(key){const el=element(key);return el.type==='checkbox'?el.checked:el.type==='number'?Number(el.value):el.value;}
  function validate(key,v){const spec=fields[key];if(!spec)throw Error('Undeclared UI field: '+key);
   if(spec.type==='boolean'?typeof v!=='boolean':spec.type==='number'||spec.type==='integer'?!Number.isFinite(v)||(spec.type==='integer'&&!Number.isInteger(v)):typeof v!=='string')throw Error('Invalid UI value');
   if(typeof v==='string'&&v.length>(spec.maxLength||8000))throw Error('UI text too long');
   if(spec.enum&&!spec.enum.includes(v))throw Error('Unknown UI choice');
   if(typeof v==='number'&&((spec.minimum!=null&&v<spec.minimum)||(spec.maximum!=null&&v>spec.maximum)))throw Error('UI value outside bounds');
   const el=element(key);if(el.disabled)throw Error('UI is busy or field is disabled');
   if(el.tagName==='SELECT'&&![...el.options].some(o=>o.value===v&&!o.disabled&&v!=='__install_model__'))throw Error('Unavailable UI choice');
  }
  async function context(){const values={},choices={};for(const key of Object.keys(fields)){try{const el=element(key);values[key]=value(key);if(el.tagName==='SELECT')choices[key]=[...el.options].filter(o=>o.value!=='__install_model__').map(o=>({id:o.value,label:o.textContent,disabled:o.disabled}));}catch(_){}}
   return {miniAppId:options.miniAppId,values,choices,...(await options.readExtra?.()||{})};}
  async function invoke(name,args){if(name!=='update_current_draft')throw Error('UI bridge cannot execute functions');
   // Validate the whole patch before mutating any field.
   for(const [key,v] of Object.entries(args))validate(key,v);
   for(const [key,v] of Object.entries(args)){const el=element(key);if(el.type==='checkbox')el.checked=v;else el.value=String(v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));}
   await options.afterPatch?.(args);return {updated:true,context:await context()};}
  const listener=async event=>{const m=event.data||{};if(event.source!==parent||event.origin!==location.origin||m.type!==REQUEST||!m.channel||!m.id)return;
   try{let result;if(m.method==='context')result=await context();else if(m.method==='invoke')result=await invoke(m.payload?.name,m.payload?.arguments||{});else if(m.method==='help')result={content:options.help||'Use the current Mini-App AaAT for functional execution.'};else throw Error('Unsupported Package UI method');
    if(new TextEncoder().encode(JSON.stringify(result)).length>40000)throw Error('UI snapshot exceeds limit');
    event.source.postMessage({type:RESPONSE,channel:m.channel,id:m.id,ok:true,result},event.origin);
   }catch(error){event.source.postMessage({type:RESPONSE,channel:m.channel,id:m.id,ok:false,error:error.message},event.origin);}};
  window.addEventListener('message',listener);return {context,invoke,dispose:()=>window.removeEventListener('message',listener)};
 }
 window.AI2AppsPackageChat={install};
})();
