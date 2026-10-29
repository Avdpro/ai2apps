const form=document.getElementById('reader'),capability=document.getElementById('capability'),status=document.getElementById('status'),result=document.getElementById('result');
let selectedTask='';
capability.onchange=()=>{document.getElementById('limit-row').hidden=capability.value!=='list';};
function display(task){if(task.id!==selectedTask)return;status.textContent=task.status+(task.message?' · '+task.message:'');if(task.result)result.textContent=JSON.stringify(task.result,null,2);}
AI2AppsWebAgent.onTask(display);
form.onsubmit=async event=>{event.preventDefault();const button=document.getElementById('run');button.disabled=true;try{const parameters={url:document.getElementById('url').value};if(capability.value==='list')parameters.limit=Number(document.getElementById('limit').value);const task=await AI2AppsWebAgent.submit(capability.value,parameters,{profile:document.getElementById('profile').value});selectedTask=task.id;result.textContent='';display(task);}catch(error){status.textContent=error.message;}finally{button.disabled=false;}};
