"""Missing native Studio AaAT exports using their existing task managers."""
import asyncio
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for

VIDEO='ai2apps.video-studio'
VOICE='ai2apps.readaloud'
VIDEO_SCHEMA={'type':'object','additionalProperties':False,'required':['prompt','model'], 'properties':{
 'prompt':{'type':'string','minLength':1,'maxLength':8000},'model':{'type':'string','minLength':1},
 'resolution':{'type':'string','default':'480p'},'duration':{'type':'number','minimum':.5,'maximum':60,'default':3},
 'steps':{'type':'integer','minimum':1,'maximum':60,'default':4},'seed':{'type':'integer','minimum':0,'maximum':2147483647,'default':0}}}
VOICE_SCHEMA={'type':'object','additionalProperties':False,'required':['project_id','model_id'],'properties':{
 'project_id':{'type':'string','minLength':1},'model_id':{'type':'string','minLength':1},
 'segment_ids':{'type':'array','items':{'type':'string'},'minItems':1,'maxItems':1000},'merge_output':{'type':'boolean','default':True}}}

async def video(runtime,args,context):
 principal=principal_for(runtime,context)
 if not context.invocation_id:raise ToolProviderError('Generation requires a durable invocation')
 task=await runtime.video_tasks.create({'model':args['model'],'content':[{'type':'text','role':'prompt','text':args['prompt']}],
  'resolution':args.get('resolution','480p'),'duration':args.get('duration',3),'steps':args.get('steps',4),'seed':args.get('seed',0),
  'metadata':{'mode':'t2v','pipeline_id':'ai2apps.video.text-to-video','label':args['prompt'][:120],'prompt':args['prompt']}},
  actor_id=principal.actor_user_id,idempotency_key='aaat:'+context.invocation_id)
 try:
  while task['status'] not in ('succeeded','failed','cancelled','interrupted'):
   await context.report_progress('视频生成 · '+task['status'],content={'video_task_id':task['id']})
   await asyncio.sleep(1);task=runtime.video_tasks.get(task['id'],actor_id=principal.actor_user_id)
 except asyncio.CancelledError:
  await runtime.video_tasks.cancel(task['id'],actor_id=principal.actor_user_id);raise
 if task['status']!='succeeded':raise ToolProviderError('Video task '+task['id']+': '+str(task.get('error') or task['status']))
 return {'video_task_id':task['id'],'status':'completed','result':task.get('result'),'shared_output':True}

async def render(runtime,args,context,mini):
 from ai2apps.readaloud import ReadAloudRepository
 from ai2apps.studio.repository import StudioRepository
 principal=principal_for(runtime,context)
 if not context.invocation_id:raise ToolProviderError('Rendering requires a durable invocation')
 project=ReadAloudRepository(runtime.database,runtime.events).get_project(principal.actor_user_id,args['project_id'])
 if project.get('miniAppId',project.get('mini_app_id','ai2apps.audio.audiobook'))!=mini:raise ToolProviderError('Project belongs to another Mini-App')
 instance,_,_=runtime.extension_manager.launch_app(VOICE,principal=principal)
 scope={'actor_id':principal.actor_user_id,'installation_id':principal.installation_id,'app_instance_id':instance.id,'studio_id':VOICE}
 repository=StudioRepository(runtime.database)
 # Durable request-to-run receipt prevents a second render after reconnect.
 import json
 signature=json.dumps([principal.actor_user_id,context.session_id,args,mini],sort_keys=True)
 with runtime.database.transaction(write=True) as db:
  db.execute('CREATE TABLE IF NOT EXISTS studio_chat_render_receipts(invocation TEXT PRIMARY KEY,signature TEXT NOT NULL,run_id TEXT)')
  old=db.execute('SELECT signature,run_id FROM studio_chat_render_receipts WHERE invocation=?',(context.invocation_id,)).fetchone()
  if old and old['signature']!=signature:raise ToolProviderError('Render invocation belongs to different input')
  if not old:db.execute('INSERT INTO studio_chat_render_receipts VALUES(?,?,NULL)',(context.invocation_id,signature))
 if old:
  if not old['run_id']:raise ToolProviderError('Earlier render admission is uncertain; inspect Studio tasks before retrying')
  run=repository.get_run(old['run_id'],**scope)
  try:runtime.readaloud_tasks.get(run['id'],owner_user_id=principal.actor_user_id)
  except Exception as error:raise ToolProviderError('Earlier render submission is uncertain; do not replay') from error
 else:
  run=repository.create_run(**scope,mini_app_id=mini,mini_app_version='1',placement=VOICE,title=project['title'],input_data={'projectId':args['project_id'],'modelId':args['model_id']})
  with runtime.database.transaction(write=True) as db:db.execute('UPDATE studio_chat_render_receipts SET run_id=? WHERE invocation=?',(run['id'],context.invocation_id))
  await runtime.readaloud_tasks.create(owner_user_id=principal.actor_user_id,project_id=args['project_id'],model_id=args['model_id'],segment_ids=args.get('segment_ids'),mini_app_id=mini,placement=VOICE,run_id=run['id'],merge_output=args.get('merge_output',True))
 try:
  while run['status'] not in ('succeeded','failed','cancelled','expired'):
   await context.report_progress('语音渲染 · '+run['status'],content={'studio_run_id':run['id']})
   await asyncio.sleep(1);run=repository.get_run(run['id'],**scope)
 except asyncio.CancelledError:
  await runtime.readaloud_tasks.cancel(run['id'],owner_user_id=principal.actor_user_id);raise
 if run['status']!='succeeded':raise ToolProviderError('Voice render '+run['id']+': '+str(run.get('error') or run['status']))
 return {'studio_run_id':run['id'],'status':'completed','shared_output':True,'artifacts':run.get('artifacts',[])}

def install(runtime,register):
 labels={k:{'zh':z,'en':e} for k,z,e in [('prompt','提示词','Prompt'),('model','模型','Model'),('resolution','分辨率','Resolution'),('duration','时长','Duration'),('steps','步数','Steps'),('seed','种子','Seed'),('project_id','项目','Project'),('model_id','模型','Model'),('segment_ids','片段','Segments'),('merge_output','合并输出','Merge output')]}
 declaration={'schema':'ai2apps.aaat-declaration/v1','instructions':['Use the selected current Mini-App model, actual resource IDs and existing task manager. Never invent model availability. Project narration requires reviewed/approved segments and the original voice rights; this Tool does not approve segments. Published results belong to the Studio shared Output.']}
 register('video.generate',VIDEO,'生成视频 / Generate video','Generate text-to-video through the existing durable video task queue and shared Output.',VIDEO_SCHEMA,lambda a,c:video(runtime,a,c),mini='ai2apps.video.text-to-video',effects=('artifact.create',),timeout_ms=900000,field_labels=labels,agent_context=declaration,form_summary={'zh':'使用现有视频队列文生视频。','en':'Generate text-to-video using the existing queue.'})
 for mini in ('ai2apps.audio.audiobook','ai2apps.audio.ensemble-drama'):
  register('voice.render_project',VOICE,'渲染语音项目 / Render voice project','Render reviewed segments in the current audiobook/drama project through the existing queue and shared Output.',VOICE_SCHEMA,lambda a,c,m=mini:render(runtime,a,c,m),mini=mini,provider_id_override=mini+'.voice.render_project',effects=('artifact.create',),timeout_ms=900000,field_labels=labels,agent_context=declaration,form_summary={'zh':'使用现有语音队列渲染已审阅的项目。','en':'Render reviewed project segments through the Voice queue.'})
