"""Bounded Package-declared image recipes on the existing system Task clock.

No Package Python, JavaScript, URLs or shell commands are executed here. Owners
supply prompts, schemas, reference IDs and a read-only path into their own draft.
"""
from __future__ import annotations
import asyncio
import hashlib
import json
import re
import time
import uuid
from datetime import datetime, timezone

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai2apps.studio.image_workflow import Plan, model_catalog, submit_plan, read_asset, asset_root
from ai2apps.studio.repository import StudioRepository
from ai2apps.system_tasks.service import TaskHandler
from ai2apps.system_tasks.sessions import execution_principal

CAPABILITY = 'image.workflow.schedule'


class Recipe(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    system: str = Field(min_length=1, max_length=12000)
    instruction: str = Field(min_length=1, max_length=16000)
    context: dict = Field(default_factory=dict)
    source_path: list[str] = Field(min_length=1, max_length=8)
    memory_field: str = Field(min_length=1, max_length=80)
    memory_keys: list[str] = Field(min_length=1, max_length=8)
    data_schema: dict
    reference_ids: list[str] = Field(default_factory=list, max_length=32)
    model: str = Field(min_length=1, max_length=255)
    size: str
    quality: str = 'auto'
    reference_limit: int = Field(default=4, ge=0, le=4)
    previous: int = Field(default=2, ge=0, le=2)
    columns: int = Field(default=2, ge=1, le=3)
    step_count: int = Field(ge=1, le=6)
    iterations: int = Field(default=1, ge=1, le=5)

    @model_validator(mode='after')
    def bounded(self):
        encoded=json.dumps(self.model_dump(),allow_nan=False)
        if len(encoded.encode())>96000:raise ValueError('Recipe exceeds 96 KiB')
        if any(not re.fullmatch(r'[0-9a-f]{32}',i) for i in self.reference_ids):raise ValueError('Invalid reference ID')
        pending=[self.data_schema]
        while pending:
            value=pending.pop()
            if isinstance(value,dict):
                if any(k in value for k in ('$ref','$dynamicRef')):raise ValueError('Schema references are not supported')
                pending.extend(value.values())
            elif isinstance(value,list):pending.extend(value)
        Draft202012Validator.check_schema(self.data_schema)
        if self.data_schema.get('type')!='object':raise ValueError('Result data must be an object')
        Plan(key='validation-key',title='Validation',model=self.model,size=self.size,
            quality=self.quality,reference_limit=self.reference_limit,steps=[{'prompt':'Validate','previous':0}])
        return self


class ScheduleSettings(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    enabled: bool = False
    name: str = Field(default='Image workflow',min_length=1,max_length=160)
    next_run: float | None = None
    interval_seconds: int = Field(default=86400,ge=3600,le=604800)
    recipe: Recipe | None = None


def source_value(draft,path):
    value=draft
    for part in path:
        if isinstance(value,list):
            value=next((item for item in value if isinstance(item,dict) and item.get('id')==part),None)
        elif isinstance(value,dict):value=value.get(part)
        else:value=None
        if value is None:raise ValueError('Scheduled source no longer exists')
    if not isinstance(value,dict):raise ValueError('Scheduled source must be an object')
    return value


class ImageWorkflowSchedules:
    def __init__(self,runtime):
        self.runtime=runtime;self.database=runtime.database;self.system=runtime.system_tasks
        with self.database.transaction(write=True) as db:
            db.execute('''CREATE TABLE IF NOT EXISTS studio_image_schedules(
                id TEXT PRIMARY KEY,owner TEXT NOT NULL,installation TEXT NOT NULL,
                studio TEXT NOT NULL,mini TEXT NOT NULL,provider TEXT NOT NULL,resource TEXT NOT NULL,
                revision INTEGER NOT NULL,enabled INTEGER NOT NULL,
                UNIQUE(owner,installation,studio,mini,provider,resource))''')
            db.execute('''CREATE TABLE IF NOT EXISTS studio_image_schedule_versions(
                schedule_id TEXT NOT NULL,revision INTEGER NOT NULL,body TEXT NOT NULL,
                PRIMARY KEY(schedule_id,revision))''')
            db.execute('''CREATE TABLE IF NOT EXISTS studio_image_schedule_results(
                schedule_id TEXT NOT NULL,item_id TEXT NOT NULL,data TEXT NOT NULL,
                created REAL NOT NULL,PRIMARY KEY(schedule_id,item_id))''')
            studios=[r[0] for r in db.execute('SELECT DISTINCT studio FROM studio_image_schedules')]
        for studio in studios:self.register(studio)

    def register(self,studio):
        kind='image-workflow:'+studio
        if kind not in self.system.handlers:
            self.system.register(kind,TaskHandler(studio,self.execute,self.cancel,self.authorize,resumable=True))
        return kind

    @staticmethod
    def binding(mounted,scope,principal):
        return {'provider':mounted.mount['app_key'],'provider_instance':mounted.mount['app_instance_id'],
            'digest':mounted.mount['effective_digest'],'mini_id':mounted.declaration['id'],
            'version':mounted.declaration['version'],'owner':principal.actor_user_id,
            'installation':principal.installation_id,'scope':scope,'llm_profile':mounted.declaration.get('llm',{}).get('profile','normal')}

    def row(self,owner,id):
        with self.database.transaction() as db:row=db.execute('SELECT * FROM studio_image_schedules WHERE id=? AND owner=?',(id,owner)).fetchone()
        if not row:raise KeyError('Schedule not found')
        return dict(row)

    def version(self,owner,payload):
        row=self.row(owner,payload['schedule_id'])
        with self.database.transaction() as db:
            saved=db.execute('SELECT body FROM studio_image_schedule_versions WHERE schedule_id=? AND revision=?',(row['id'],payload['revision'])).fetchone()
        if not saved:raise ValueError('Schedule revision unavailable')
        return row,json.loads(saved[0])

    def _authorize(self,binding):
        principal=execution_principal(self.runtime,binding['owner'])
        if principal.installation_id!=binding['installation']:raise ValueError('Installation changed')
        for instance in (binding['provider_instance'],binding['scope']['app_instance_id']):
            self.runtime.extension_manager.require_instance_access(instance,principal)
        from ai2apps.studio.capability_broker import _declared_capabilities
        current=next((item for item in self.runtime.extension_manager.list_studio_mini_apps(binding['scope']['studio_id'],principal=principal)
            if item['id']==binding['mini_id'] and item.get('provider',{}).get('appId')==binding['provider']
            and item.get('provider',{}).get('digest')==binding['digest']),None)
        if not current or not {'image.workflow','llm.text',CAPABILITY}<=set(_declared_capabilities(current)):
            raise ValueError('Package changed or scheduled workflow capability was revoked; save the schedule again')
        return principal

    def authorize(self,owner,payload):
        _,saved=self.version(owner,payload)
        principal=self._authorize(saved['binding'])
        self.context(saved,principal)

    def context(self,saved,principal):
        draft=StudioRepository(self.database).get_draft(**saved['binding']['scope'],mini_app_id=saved['binding']['mini_id'])
        if not draft:raise ValueError('Save the source settings before scheduling')
        return source_value(draft['draft'],saved['recipe']['source_path'])

    def identity(self,binding,resource):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',resource):raise ValueError('Invalid resource key')
        scope=binding['scope']
        return 'iwsch_'+hashlib.sha256(json.dumps([binding['owner'],binding['installation'],scope['studio_id'],binding['mini_id'],binding['provider'],resource]).encode()).hexdigest()[:32]

    async def configure(self,binding,resource,settings):
        id=self.identity(binding,resource);owner=binding['owner'];now=self.system.clock()
        if settings.enabled:
            principal=self._authorize(binding)
            if settings.recipe is None or settings.next_run is None or not now+60<=settings.next_run<=now+366*86400:
                raise ValueError('Choose a first run at least one minute in the future')
            recipe=settings.recipe.model_dump();self.context({'binding':binding,'recipe':recipe},principal)
            from ai2apps.task_llm import resolve_task_model,effective_profile
            text_model=resolve_task_model(self.runtime,'standard',effective_profile(self.runtime,'normal',binding.get('llm_profile','normal')))
            if not text_model:raise ValueError('Configure a standard task text model before enabling a schedule')
            choices=await model_catalog(self.runtime,principal)
            model=next((m for m in choices['items'] if m['id']==recipe['model'] and m['ready']),None)
            if not model or recipe['reference_limit']>model['referenceLimit']:raise ValueError('Drawing model unavailable or reference limit invalid')
            from ai2apps.images.parameters import validate_size
            validate_size(recipe['size'],model['size'])
            if recipe['quality'] not in model['qualities']:raise ValueError('Unsupported image quality')
            for ref in recipe['reference_ids']:read_asset(asset_root(self.runtime,principal,binding['provider']),ref)
        else:recipe=None;text_model=None
        self.register(binding['scope']['studio_id'])
        with self.database.transaction(write=True) as db:
            old=db.execute('SELECT revision FROM studio_image_schedules WHERE id=?',(id,)).fetchone()
            revision=(old[0] if old else 0)+1
            db.execute('INSERT INTO studio_image_schedules VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET revision=excluded.revision,enabled=excluded.enabled',
                (id,owner,binding['installation'],binding['scope']['studio_id'],binding['mini_id'],binding['provider'],resource,revision,int(settings.enabled)))
            saved={'binding':binding,'recipe':recipe,'text_model':text_model,'settings':settings.model_dump(exclude={'recipe'})}
            db.execute('INSERT INTO studio_image_schedule_versions VALUES(?,?,?)',(id,revision,json.dumps(saved,allow_nan=False)))
            # Same DB transaction freezes the accepted revision and its clock entry.
            self.system._write_schedule(db,owner,binding['scope']['studio_id'],id,
                'image-workflow:'+binding['scope']['studio_id'],settings.name,{'schedule_id':id,'revision':revision},
                next_run=settings.next_run or now+settings.interval_seconds,
                interval_seconds=settings.interval_seconds,enabled=settings.enabled,now=now)
        self.system._wake()
        return self.snapshot(binding,resource)

    def snapshot(self,binding,resource):
        id=self.identity(binding,resource)
        with self.database.transaction() as db:
            row=db.execute('SELECT * FROM studio_image_schedules WHERE id=?',(id,)).fetchone()
            if not row:return {'enabled':False,'results':[]}
            timer=db.execute('SELECT next_run,interval_seconds,enabled,error,last_task_id FROM system_task_schedules WHERE owner=? AND id=?',(binding['owner'],id)).fetchone()
            version=db.execute('SELECT body FROM studio_image_schedule_versions WHERE schedule_id=? AND revision=?',(id,row['revision'])).fetchone()
            results=db.execute('SELECT data FROM studio_image_schedule_results WHERE schedule_id=? ORDER BY created DESC LIMIT 100',(id,)).fetchall()
        saved=json.loads(version[0]);task=self.system.active_for(binding['owner'],binding['scope']['studio_id'],'schedule:'+id)
        if task is None:
            with self.database.transaction() as db:
                latest=db.execute('SELECT id FROM system_tasks WHERE owner=? AND app_id=? AND dedup_key=? ORDER BY created_at DESC LIMIT 1',
                    (binding['owner'],binding['scope']['studio_id'],'schedule:'+id)).fetchone()
            if latest:task=self.system.get(binding['owner'],latest['id'])
        return {'id':id,**dict(timer),'text_model':saved['text_model'],
            'iterations':(saved['recipe'] or {}).get('iterations',1),'step_count':(saved['recipe'] or {}).get('step_count'),
            'context':(saved['recipe'] or {}).get('context',{}),
            'model':(saved['recipe'] or {}).get('model'),'results':[json.loads(r[0]) for r in results],
            'task':{'id':task['id'],'status':task['status'],'message':task['message']} if task else None}

    async def text(self,saved,principal,prompt,request_id):
        from ai2apps.model_invocation import ModelInvocationContext,invoke_app_cloud_chat
        from ai2apps.task_llm import task_payload
        binding=saved['binding'];model=saved['text_model']
        body=task_payload(model,[{'role':'system','content':saved['recipe']['system']},{'role':'user','content':prompt}],'standard',max_tokens=12000)
        if model.startswith('cloud/'):
            response=await invoke_app_cloud_chat(self.runtime,body,principal=principal,session_id=request_id,
                app_instance_id=binding['provider_instance'],consumer_app_id=binding['mini_id'])
        else:
            response=await self.runtime.model_invocations.invoke_background_json(model,'chat_completions',body,request_id=request_id,
                context=ModelInvocationContext.from_principal(principal,session_id=request_id,
                    app_instance_id=binding['provider_instance'],consumer_app_id=binding['mini_id']))
        if response.status_code>=400:raise ValueError('Scheduled text model failed (HTTP '+str(response.status_code)+')')
        from ai2apps.studio.capability_broker import StudioCapabilityBroker
        value=json.loads(bytes(response.body))
        if any(c.get('finish_reason')=='length' for c in value.get('choices',[])):raise ValueError('Scheduled text result was truncated')
        return StudioCapabilityBroker._completion_text(value)

    async def execute(self,ctx):
        row,saved=self.version(ctx.owner,ctx.payload);recipe=Recipe.model_validate(saved['recipe'])
        principal=self._authorize(saved['binding']);binding=saved['binding'];checkpoint=ctx.checkpoint or {'items':[]}
        completed=[]
        try:
            for index in range(recipe.iterations):
                principal=self._authorize(binding)
                if getattr(self.runtime,'privacy_mode',False) and any(m.startswith('cloud/') for m in (saved['text_model'],recipe.model)):
                    raise ValueError('Privacy policy changed; update the scheduled model choices')
                while True:
                    with self.database.transaction() as db:
                        active=db.execute("SELECT id FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND mini_app_id=? AND kind='image-workflow' AND status IN ('queued','running','publishing') AND json_extract(request_json,'$.plan.resource_key')=?",
                            (principal.actor_user_id,principal.installation_id,binding['scope']['studio_id'],binding['mini_id'],row['resource'])).fetchone()
                    own=checkpoint['items'][index].get('job_id') if index<len(checkpoint['items']) else None
                    if not active or active['id']==own:break
                    ctx.report(state='waiting_resource',checkpoint=checkpoint,message='Waiting for the existing image task')
                    await asyncio.sleep(1)
                if index>=len(checkpoint['items']):
                    checkpoint['items'].append({'id':uuid.uuid4().hex})
                    ctx.report(checkpoint=checkpoint)
                item=checkpoint['items'][index]
                if 'plan' not in item:
                    if item.get('text_submitted'):raise ValueError('Text submission outcome is uncertain; automatic replay refused')
                    source=self.context(saved,principal);memory=source.get(recipe.memory_field,[])
                    if not isinstance(memory,list):raise ValueError('Source memory must be a list')
                    with self.database.transaction() as db:recent=[json.loads(r[0]) for r in db.execute('SELECT data FROM studio_image_schedule_results WHERE schedule_id=? ORDER BY created DESC LIMIT 20',(row['id'],))]
                    combined={r.get('id',str(i)):r for i,r in enumerate([*memory,*reversed(recent)]) if isinstance(r,dict)}
                    brief={'instruction':recipe.instruction,'context':recipe.context,'current_time':datetime.now().astimezone().isoformat(),
                        'recent':[{k:r.get(k) for k in recipe.memory_keys} for r in list(combined.values())[-20:]]}
                    prompt=json.dumps(brief,ensure_ascii=False)
                    if len(prompt)>100000:raise ValueError('Scheduled context exceeds 100000 characters')
                    item['text_submitted']=True;ctx.report(checkpoint=checkpoint,message=f'{index+1}/{recipe.iterations} · Preparing text')
                    text=await asyncio.wait_for(self.text(saved,principal,prompt,ctx.id+'-text-'+str(index)),150)
                    value=json.loads(re.sub(r'\s*```$','',re.sub(r'^```(?:json)?\s*','',text.strip())))
                    if set(value)!={'title','steps','data'} or not isinstance(value['data'],dict):raise ValueError('Invalid generated workflow record')
                    Draft202012Validator(recipe.data_schema).validate(value['data'])
                    if not isinstance(value['steps'],list) or len(value['steps'])!=recipe.step_count:raise ValueError('Generated step count differs from accepted recipe')
                    for step in value['steps']:
                        if set(step)-{'prompt','caption','references'}:raise ValueError('Generated step contains unauthorized controls')
                        if any(ref not in recipe.reference_ids for ref in step.get('references',[])):raise ValueError('Generated reference is outside the accepted allowlist')
                        step['previous']=recipe.previous
                    plan=Plan(key=item['id'],resource_key=row['resource'],title=value['title'],model=recipe.model,size=recipe.size,quality=recipe.quality,
                        columns=recipe.columns,reference_limit=recipe.reference_limit,steps=value['steps'])
                    item.update(plan=plan.model_dump(),data=value['data']);ctx.report(checkpoint=checkpoint)
                if not item.get('job_id'):
                    principal=self._authorize(binding)
                    if getattr(self.runtime,'privacy_mode',False) and recipe.model.startswith('cloud/'):
                        raise ValueError('Privacy policy changed; update the drawing model')
                    job=await submit_plan(self.runtime,principal,binding,binding['scope'],Plan.model_validate(item['plan']),parent_task_id=ctx.id)
                    item['job_id']=job['id'];ctx.report(checkpoint=checkpoint)
                while True:
                    job=self.runtime.studio_jobs.get(item['job_id'],principal)
                    if job['status']=='succeeded':break
                    if job['status'] in ('failed','interrupted','publish_failed','cancelled'):
                        raise ValueError('Image workflow '+job['status']+'; inspect the original task before retrying')
                    ctx.report(checkpoint=checkpoint,message=f'{index+1}/{recipe.iterations} · Rendering',progress={'image_job_id':job['id'],'completed':index,'total':recipe.iterations})
                    await asyncio.sleep(1)
                result={**item['data'],'id':item['id'],'title':item['plan']['title'],'status':'completed',
                    'createdAt':datetime.now(timezone.utc).isoformat(),'assetIds':job['result']['assetIds'],'runId':job['run_id']}
                with self.database.transaction(write=True) as db:
                    db.execute('INSERT OR IGNORE INTO studio_image_schedule_results VALUES(?,?,?,?)',(row['id'],item['id'],json.dumps(result,ensure_ascii=False),time.time()))
                completed.append(result['id']);ctx.report(checkpoint=checkpoint,message=f'{index+1}/{recipe.iterations} · Completed')
            return {'completed':completed}
        except asyncio.CancelledError:raise
        except Exception as error:
            if completed:return {'_status':'partial','completed':completed,'error':str(error)[:500]}
            raise

    async def cancel(self,ctx,force):
        _,saved=self.version(ctx.owner,ctx.payload);principal=execution_principal(self.runtime,ctx.owner)
        if principal.installation_id!=saved['binding']['installation']:raise ValueError('Installation changed')
        for item in ctx.checkpoint.get('items',[]):
            identifier=item.get('job_id')
            if not identifier and item.get('id'):
                with self.database.transaction() as db:
                    row=db.execute('SELECT id FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND mini_app_id=? AND idempotency_key=?',
                        (ctx.owner,principal.installation_id,saved['binding']['scope']['studio_id'],saved['binding']['mini_id'],
                        'image-workflow-'+saved['binding']['mini_id']+'-'+item['id'])).fetchone()
                identifier=row['id'] if row else None
            if identifier:
                job=self.runtime.studio_jobs.get(identifier,principal)
                if job['status'] in ('queued','running','publishing'):
                    self.runtime.studio_jobs.cancel(job['id'],principal)
        return True
