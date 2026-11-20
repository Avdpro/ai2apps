/* Mini-App client helper. rpc belongs to the existing host MessageChannel. */
(function(root){
    'use strict';
    root.AI2AppsMiniAppEvents={
        async watch(port,rpc,consume,{signal}={}){
            const pending=new Set();let closed=false;
            const listener=async event=>{
                const message=event.data;
                if(closed||message?.type!=='ai2apps:event-deliveries'||message.version!==1)return;
                for(const item of message.items||[]){
                    if(closed||pending.has(item.delivery_id))continue;
                    pending.add(item.delivery_id);
                    try{
                        await consume(item);
                        if(!closed)await rpc('events.ack',{deliveryId:item.delivery_id});
                    }catch(error){root.dispatchEvent?.(new CustomEvent('ai2apps:event-consumer-error',{detail:{deliveryId:item.delivery_id,message:String(error.message||error)}}));}
                    finally{pending.delete(item.delivery_id);}
                }
            };
            const close=()=>{closed=true;port.removeEventListener('message',listener);};
            if(signal?.aborted){close();return close;}
            port.addEventListener('message',listener);port.start?.();
            signal?.addEventListener('abort',close,{once:true});
            try{await rpc('events.watch',{});}catch(error){close();throw error;}
            return close;
        }
    };
})(typeof window==='undefined'?globalThis:window);
