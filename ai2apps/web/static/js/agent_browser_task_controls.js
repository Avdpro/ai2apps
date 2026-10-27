/* Run-bound controls observe and resume the existing owner Browser Task. */
(() => {'use strict';
window.AI2AppsBrowserTaskControls=request=>({
 task:null,interactions:[],busy:false,error:'',key:'',generation:0,path:'',responses:{},
 async sync(run,taskId,waiting,reason){
  const key=JSON.stringify([run.id,taskId,waiting,reason]);if(this.key===key)return;
  this.key=key;const generation=++this.generation;this.task=null;this.interactions=[];this.error='';
  if(!taskId||!waiting)return;
  this.path='/agent-runs/'+encodeURIComponent(run.id)+'/browser-tasks/'+encodeURIComponent(taskId);
  try{const task=await request(this.path);if(generation!==this.generation)return;this.task=task;this.interactions=task.interactions||[];}
  catch(e){if(generation===this.generation){this.error=e.message;this.key='';}}
 },
 async act(action,interaction=null,approve=true){
  if(this.busy||!this.task)return;this.busy=true;this.error='';
  try{
   if(action==='continue'&&(!interaction||!this.interactions.some(i=>i.id===interaction.id)))throw Error('协助请求已变化，请刷新。');
   const task=await request(this.path,{method:'POST',body:JSON.stringify({action,interaction_id:interaction?.id||null,response_id:(this.responses[action+':'+interaction?.id+':'+approve]||=crypto.randomUUID()),approve})});
   this.task=task;this.interactions=task.interactions||[];
  }catch(e){this.error=e.message;}finally{this.busy=false;}
 }
});})();
