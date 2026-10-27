"""UI control only targets an observed task under its authorized originating Run."""
from pathlib import Path
import subprocess

def test_browser_task_controls_only_call_run_bound_routes():
    source=Path(__file__).resolve().parents[1]/'web/static/js/agent_browser_task_controls.js'
    script=r'''
const assert=require('node:assert/strict');global.window={};global.crypto={randomUUID:()=> 'stable'};require(SOURCE);
(async()=>{for(const provider of ['alpha','beta']){
 const calls=[],task={id:provider,status:'waiting_input',requires_user:true,interactions:[{id:'help',request:{control:'browser_user_assistance'}}]};
 async function request(path,options){calls.push([path,options]);return task;}
 const ui=window.AI2AppsBrowserTaskControls(request);await ui.sync({id:'origin'},provider,true,'Help');
 assert.equal(ui.interactions.length,1);assert.equal(calls[0][0],`/agent-runs/origin/browser-tasks/${provider}`);
 await ui.act('continue',task.interactions[0]);const payload=JSON.parse(calls[1][1].body);assert.equal(typeof payload.response_id,'string');delete payload.response_id;assert.deepEqual(payload,{action:'continue',interaction_id:'help',approve:true});
 await ui.act('open');await ui.act('cancel');assert(calls.every(c=>c[0]===calls[0][0]));
 const before=calls.length;await ui.act('continue',{id:'foreign'});assert(ui.error);assert.equal(calls.length,before);
}})().catch(e=>{console.error(e);process.exit(1)});
'''.replace('SOURCE',repr(str(source)))
    result=subprocess.run(['node','-e',script],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
