/* Studio owner adapter over the single durable App Chat transport. */
(function(){
'use strict';
async function mount(owner,config){
 const mini=owner.currentMiniApp;
 if(!mini?.id||!window.AI2AppsAppChat)return;
 const key=mini.id;
 if(owner.chatController?.studioMiniId===key){owner.chatController.bind(owner.$refs.miniAppChat);return;}
 if(owner.studioChatOpening)return owner.studioChatOpening;
 owner.studioChatOpening=(async()=>{
  owner.chatController?.dispose();owner.chatController=null;
  const readUI=async()=>{
   const current=owner.currentMiniApp;
   if(current?.id!==key)throw Error('Mini-App changed; reopen its Chat');
   const declaration=await owner.describeMiniAppChat();
   // Read only structured data, never forward a page prompt/tool handler.
   const update=(declaration.tools||[]).find(t=>t.name==='update_current_draft');
   return {miniAppId:key,context:declaration.context||{},draftFields:update?.inputSchema?.properties||{},
    materials:config.materials?.(owner)||[],
    outputs:config.outputs(owner).slice(0,30).map(x=>({id:x.id,name:x.name||x.title||x.label||'',status:x.status})),
    capabilities:{ui:true,functional:'Only registered AaAT exports are available; the server lists them.'}};
  };
  const controller=await window.AI2AppsAppChat.create({appId:config.appId,registration:config.appId+'.chat',
   title:mini.name||'Studio Chat',scope:()=>({mini_app_id:key}),matchesScope:s=>s.mini_app_id===key,
   readUI,restoreLast:false,
   applyUI:async args=>{
    if(owner.currentMiniApp?.id!==key)throw Error('Mini-App changed before applying UI action');
    if(args.action==='update_draft'){
     const values=args.values;
     if(values.modelId){const models=owner.models||owner.providers||[];if(!models.some(m=>m.id===values.modelId))throw Error('Selected model is not available in this Mini-App');}
     await owner.invokeMiniAppChatTool('update_current_draft',values);
    }else if(args.action==='select_output'){
     if(!config.outputs(owner).some(x=>x.id===args.output_id))throw Error('Output is not in this Studio view');
     await config.selectOutput(owner,args.output_id);
    }else throw Error('Unsupported Studio UI action');
    return {applied:true,miniAppId:key};
   },onSettled:()=>config.refresh(owner),scopeNote:'仅限当前小应用；后台任务和共享输出由工作室保存。'});
  if(owner.currentMiniApp?.id!==key){controller.dispose();return;}
  owner.chatController={...controller,studioMiniId:key};
  owner.chatMiniUrl=controller.url();
  await new Promise(resolve=>owner.$nextTick(()=>{controller.bind(owner.$refs.miniAppChat);resolve();}));
 })();
 try{return await owner.studioChatOpening;}catch(error){owner.fail(error);}finally{owner.studioChatOpening=null;}
}
window.AI2AppsStudioChat={mount};
})();
