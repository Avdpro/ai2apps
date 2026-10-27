/* Chat-owned data-only transfer. A source App cannot supply system roles or settings. */
(()=>{'use strict';
function normalize(value){
 if(!value||typeof value!=='object'||JSON.stringify(value).length>64000)throw Error('Invalid Chat context');
 const {title,legacy_thread_id,session_metadata:meta,legacy_messages:messages}=value;
 if(typeof title!=='string'||title.length>200||typeof legacy_thread_id!=='string'||legacy_thread_id.length>512||!legacy_thread_id)throw Error('Invalid Chat context identity');
 if(Object.keys(value).some(k=>!['title','legacy_thread_id','session_metadata','legacy_messages'].includes(k)))throw Error('Unsupported Chat context setting');
 if(!meta||meta.agentMode!==true||Object.keys(meta).some(k=>!['agentMode','starterSuggestions','sourceContext'].includes(k)))throw Error('Chat context cannot set execution policy');
 if(!Array.isArray(meta.starterSuggestions)||meta.starterSuggestions.length>5||meta.starterSuggestions.some(q=>typeof q!=='string'||!q.trim()||q.length>500))throw Error('Invalid Chat starter topics');
 if(meta.sourceContext&&JSON.stringify(meta.sourceContext).length>2048)throw Error('Source identity exceeds limit');
 if(!Array.isArray(messages)||!messages.length||messages.length>8||messages.some(m=>!['user','assistant'].includes(m.role)||typeof m.content!=='string'||m.content.length>50000))throw Error('Chat context must contain bounded user/assistant data');
 return {title,legacy_thread_id,session_metadata:{agentMode:true,starterSuggestions:[...meta.starterSuggestions],sourceContext:JSON.parse(JSON.stringify(meta.sourceContext||{}))},legacy_messages:messages.map(m=>({role:m.role,content:m.content,metadata:{}}))};
}
function forRecipient(value,appInstanceId){
 const seed=normalize(value);
 if(typeof appInstanceId!=='string'||!/^appi_[A-Za-z0-9_-]+$/.test(appInstanceId))throw Error('Chat recipient identity is unavailable');
 seed.legacy_thread_id='context:'+appInstanceId+':'+seed.legacy_thread_id;
 if(seed.legacy_thread_id.length>512)throw Error('Chat import identity exceeds limit');
 return seed;
}
window.AI2AppsChatContext={normalize,forRecipient};
})();
