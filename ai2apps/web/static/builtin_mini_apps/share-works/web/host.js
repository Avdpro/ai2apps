/* Package client: only the host's authenticated Studio MessageChannel owns tasks. */
(function(global){
    'use strict';
    let port=null, serial=0;
    const pending=new Map(), listeners=new Set();
    let resolveConnection;
    const connected=new Promise(resolve=>{resolveConnection=resolve;});
    const announce=()=>global.parent.postMessage({type:'ai2apps:studio-connect',version:1},'*');
    global.addEventListener('message',event=>{
        if(event.source!==global.parent || event.data?.type!=='ai2apps:studio-connected' || event.data.version!==1 || !event.ports?.[0] || port)return;
        port=event.ports[0];
        port.onmessage=message=>{
            const data=message.data;
            if(data?.type==='ai2apps:web-agent-task'){
                for(const listener of listeners){try{listener(data.task);}catch(error){global.console?.error(error);}}
                return;
            }
            const request=pending.get(data?.id);
            if(!request)return;
            pending.delete(data.id);global.clearTimeout(request.timer);
            data.error?request.reject(new Error(data.error)):request.resolve(data.value);
        };
        port.start?.();resolveConnection();
    });
    const sendRequest=async(operation,fields={})=>{
        let timer;
        await Promise.race([connected,new Promise((_,reject)=>{timer=global.setTimeout(()=>reject(new Error('Mini-App host connection timed out')),10000);})]).finally(()=>global.clearTimeout(timer));
        return new Promise((resolve,reject)=>{
            const id=++serial;
            const timer=global.setTimeout(()=>{pending.delete(id);reject(new Error('Mini-App request timed out'));},120000);
            pending.set(id,{resolve,reject,timer});port.postMessage({id,operation,...fields});
        });
    };
    // Host channels intentionally admit one operation at a time.
    let queue=Promise.resolve();
    const request=(operation,fields={})=>{const result=queue.then(()=>sendRequest(operation,fields));queue=result.catch(()=>{});return result;};
    global.ShareHost={request:(action,fields={})=>request('owner.request',{action,...fields})};
    // Connect after the iframe load event; the host revokes channels on navigation.
    if(global.document.readyState==='complete') global.setTimeout(announce,0);
    else global.addEventListener('load',()=>global.setTimeout(announce,0),{once:true});
})(window);
