import asyncio,json,tempfile
from pathlib import Path
from ai2apps.config import PlatformConfig
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.chat import ChatRepository
from ai2apps.agents import ToolCallAction,CompleteAction
from ai2apps.capabilities import PolicyEffect
from ai2apps.identity import IdentityRepository, OrganizationType

async def main():
 base=Path(tempfile.mkdtemp(prefix='ai2apps-composition-'))
 runtime=PlatformRuntime(PlatformConfig.from_base_path(base)); runtime.start()
 identities=IdentityRepository(runtime.database)
 identities.bind_installation(installation_id='acceptance-installation',cloud_device_id='acceptance-device',organization_id='acceptance-org',organization_type=OrganizationType.HOUSEHOLD,core_user_id='acceptance-user',billing_account_id='acceptance-billing',access_epoch=1)
 principal=identities.principal_for('acceptance-user')
 thread,_=ChatRepository(runtime.database,runtime.events,principal=principal).create_thread(title='App composition acceptance: product brief')
 parent='acceptance.compose'; child='acceptance.writer'
 for key in (parent,child):
  runtime.agents.ensure_definition(agent_key=key,package_version='1.0.0',display_name=key,executor_key=key,max_steps=15,timeout_seconds=90)
 # These policies exist only in this disposable acceptance database.
 for name,cap in [('knowledge.add_text','knowledge.write'),('workspace.write','workspace.write'),('artifact.create','artifact.create')]:
  for key in (parent,child):
   runtime.capabilities.upsert_policy(policy_key='acceptance:'+key+':'+cap,effect=PolicyEffect.ALLOW,capability_pattern=cap,agent_pattern=key,tool_pattern=name,priority=1000,source='local')
 brief='COMPOSE20261017: AI2Apps App capabilities should be callable by Harness. The first workflow saves a private knowledge note, retrieves it, creates a Markdown brief, and exports an immutable Artifact. Acceptance: stable citations and traceable parent/child Runs. No external publishing.'
 def parent_executor(c):
  if c.step('save') is None:return ToolCallAction('save','knowledge.add_text',{'title':'COMPOSE20261017 product brief','text':brief})
  if c.step('search') is None:return ToolCallAction('search','knowledge.search',{'query':'COMPOSE20261017','limit':5})
  hits=c.step('search').output['items']
  if not hits:raise RuntimeError('Saved knowledge is not discoverable by the calling App')
  if c.step('read') is None:return ToolCallAction('read','knowledge.get',{'item_id':hits[0]['item']['id']})
  item=c.step('read').output
  if c.step('delegate') is None:return ToolCallAction('delegate','agent.delegate',{'agent':child,'task':'Create a cited brief Artifact','request_key':'brief','parameters':{'text':item['text'],'citation':item['citation']['uri']}})
  return CompleteAction({'knowledge':item['id'],'result':c.step('delegate').output})
 def writer(c):
  params=c.run.input['parameters']; content='# App Composition Brief\n\n'+params['text']+'\n\nSource: '+params['citation']+'\n'
  if c.step('write') is None:return ToolCallAction('write','workspace.write',{'path':'output/composition-brief.md','content':content})
  if c.step('artifact') is None:return ToolCallAction('artifact','artifact.create',{'path':'output/composition-brief.md','name':'App Composition Brief','media_type':'text/markdown'})
  return CompleteAction({'artifact':c.step('artifact').output})
 runtime.agent_runtime.bind_executor(parent,parent_executor);runtime.agent_runtime.bind_executor(child,writer)
 run,_=runtime.agents.create_run(session_id=thread.session.id,agent_key=parent,input={})
 await runtime.agent_runtime.start()
 try:
  for _ in range(450):
   await asyncio.sleep(.2);r=runtime.agents.get_run(run.id)
   if r.status.value in ('completed','failed','waiting_input','waiting_capability','cancelled','interrupted'):break
  runs=[r,*runtime.agents.list_children(r.id)]
  evidence={'base_path':str(base),'session_id':thread.session.id,'planning':'deterministic acceptance executors; no LLM','status':r.status.value,'runs':[{'id':v.id,'status':v.status.value,'error':v.error,'output':v.output,'steps':[{'tool':s.tool_name if hasattr(s,'tool_name') else s.name if hasattr(s,'name') else s.action_key,'status':s.status.value,'input':s.input,'output':s.output,'error':s.error} for s in runtime.agents.list_steps(v.id)]} for v in runs],'tools':[{'name':t.qualified_name,'capabilities':t.required_capabilities} for t in runtime.services.list_tools()]}
  path=base/'evidence.json';path.write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str));print(json.dumps({'status':r.status.value,'evidence':str(path),'runs':[v.id for v in runs],'error':r.error}))
 finally:
  await runtime.agent_runtime.stop();runtime.stop()
asyncio.run(main())
