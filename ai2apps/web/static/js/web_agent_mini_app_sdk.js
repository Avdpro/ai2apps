/* Package client: only the host's authenticated Studio MessageChannel owns tasks. */
(function(global){
    'use strict';
    let port=null, serial=0, mobile=false;
    const pending=new Map(), listeners=new Set();
    let resolveConnection;
    const connected=new Promise(resolve=>{resolveConnection=resolve;});
    const announce=()=>global.parent.postMessage({type:'ai2apps:studio-connect',version:1},'*');
    global.addEventListener('message',event=>{
        if(event.source!==global.parent || event.data?.type!=='ai2apps:studio-connected' || event.data.version!==1 || !event.ports?.[0] || port)return;
        port=event.ports[0];
        mobile=event.data.mobile===true;
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
            const timer=global.setTimeout(()=>{pending.delete(id);reject(new Error('Mini-App request timed out'));},30000);
            pending.set(id,{resolve,reject,timer});port.postMessage({id,operation,...fields});
        });
    };
    // Host channels intentionally admit one operation at a time.
    let queue=Promise.resolve();
    const request=(operation,fields={})=>{const result=queue.then(()=>sendRequest(operation,fields));queue=result.catch(()=>{});return result;};
    global.AI2AppsNotifications=Object.freeze({
        send:notification=>request('notifications.send',{notification}),
        onRoute:handler=>{
            const params=new URLSearchParams(location.hash.slice(1)),id=params.get('notification-id');
            if(!id || !params.get('notification-route'))return;
            Promise.resolve().then(()=>handler({route:params.get('notification-route'),id:params.get('notification-resource')})).then(()=>report('opened'),()=>report('failed'));
            function report(status){global.parent.postMessage({type:'ai2apps.notification.result',id,status,mountToken:params.get('ai2apps-mount')},'*');}
        },
    });
    global.AI2AppsWebAgent=Object.freeze({
        get isMobile(){return mobile;},
        probe:()=>request('probe'),
        startup:()=>request('web-agent.startup'),
        searchConfig:config=>request('web-agent.search-config',config?{config}:{}),
        cloudSearchRequest:(taskId,action='read')=>request('web-agent.cloud-search-request',{taskId,action}),
        prepareSearch:body=>request('web-agent.search-preparation',{body}),
        searchPreparation:preparationId=>request('web-agent.search-preparation',{preparationId}),
        startSearch:body=>request('web-agent.search-workflow',{body}),
        searchWorkflow:preparationId=>request('web-agent.search-workflow',{preparationId}),
        customSources:options=>request('web-agent.custom-sources',options||{}),
        profiles:()=>request('web-agent.profiles'),
        productImages:taskIds=>request('web-agent.product-images',{taskIds}),
        draft:()=>request('draft.get'),
        saveDraft:value=>request('draft.set',{value:JSON.stringify(value)}),
        submit:(capability,parameters={},options={})=>request('web-agent.submit',{capability,parameters,profile:options.profile||'default',retainPages:options.retainPages===true,requestId:options.requestId||global.crypto.randomUUID(),...(options.batchId?{batchId:options.batchId,batchSize:options.batchSize}: {})}),
        openResult:(taskId,url)=>request('web-agent.open-result',{taskId,url}),
        deleteShoppingHistory:confirmation=>request('web-agent.delete-shopping-history',{confirmation}),
        retainedTasks:()=>request('web-agent.retained-tasks'),
        pages:(taskId,action='list')=>request('web-agent.pages',{taskId,action}),
        task:taskId=>request('web-agent.task',{taskId}),
        watch:taskId=>request('web-agent.watch',{taskId}),
        onTask:listener=>{listeners.add(listener);return()=>listeners.delete(listener);},
    });
    // Connect after the iframe load event; the host revokes channels on navigation.
    if(global.document.readyState==='complete') global.setTimeout(announce,0);
    else global.addEventListener('load',()=>global.setTimeout(announce,0),{once:true});
})(window);
