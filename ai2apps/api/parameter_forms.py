"""Authenticated parameter drafts and trusted audio transcription completion."""
import asyncio
import json
import hashlib
import weakref
import tempfile
from pathlib import Path
from datetime import datetime, UTC
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from pydantic import BaseModel, Field
from jsonschema import Draft202012Validator, ValidationError
from ai2apps.agents.parameter_forms import FORMS, resolve_form, schema_fields, diagnostics
from ai2apps.api.ownership import authorize_agent_run
from ai2apps.core import RepositoryError
from ai2apps.readaloud.materials import VoiceMaterials

class DraftInput(BaseModel):
    revision: int = Field(ge=0)
    values: dict

class GalleryInput(BaseModel):
    asset_id: str = Field(min_length=1,max_length=256)

class MaterialGalleryInput(GalleryInput):
    field: str = Field(min_length=1,max_length=256)

class SwitchInput(BaseModel):
    revision: int = Field(ge=0)
    provider: str = Field(min_length=1,max_length=256)

class LinkInput(BaseModel):
    studio_run_id: str = Field(min_length=1,max_length=256)
    app_instance_id: str = Field(min_length=1,max_length=256)

def create_parameter_forms_router(runtime_provider, principal_provider):
    router=APIRouter(prefix='/agent-runs/{run_id}/interactions/{interaction_id}/parameters',tags=['parameter-forms'])
    dep=Depends(principal_provider)
    locks=weakref.WeakValueDictionary()
    def resolve(run_id,interaction_id,principal,*,pending=True):
        runtime=runtime_provider();authorize_agent_run(runtime,principal,run_id)
        run=runtime.agents.get_run(run_id)
        item=next((i for i in runtime.agents.list_interactions(run_id) if i.id==interaction_id),None)
        if not item or item.request.get('control')!='parameter_form':raise HTTPException(404,'Form not found')
        from ai2apps.agents.form_continuation import selected_form
        try:form=selected_form(runtime.database,item)
        except RepositoryError as error:raise HTTPException(409,str(error)) from error
        if pending and (item.status.value!='pending' or run.status.value!='waiting_input' or item.deadline_at<=datetime.now(UTC)):raise HTTPException(409,'Form is no longer pending')
        return runtime,run,item,form
    def materials(runtime):return VoiceMaterials(runtime.database,runtime.config.paths.artifacts_path)
    def draft(runtime,item,form,principal):
        with runtime.database.transaction() as db:row=db.execute('SELECT revision,values_json FROM agent_parameter_drafts WHERE interaction_id=?',(item.id,)).fetchone()
        values={f['key']:f['default'] for f in form.fields if 'default' in f};values.update(item.request.get('values',item.request.get('initial_values',{})))
        if row:values=json.loads(row['values_json'])
        if form.prepare_values:
            try:values=form.prepare_values(runtime,principal,form,dict(values),item)
            except ValueError as error:raise HTTPException(422,str(error)) from error
            if not isinstance(values,dict):raise HTTPException(422,'Owner draft preparation must return an object')
        return {'revision':row['revision'] if row else 0,'values':values}
    def validate(runtime,principal,form,values,complete=False):
        if complete:
            try:Draft202012Validator(form.schema).validate(values)
            except ValidationError as e:raise HTTPException(422,{'field':'.'.join(str(p) for p in e.path),'message':e.message}) from e
        if form.validate: form.validate(runtime,principal,form,values)
    def alternatives(runtime,principal,form):
        allowed={form.capability or form.key,*form.related_capabilities}
        router=getattr(runtime,'app_capability_router',None)
        states={p['id']:p for p in router.inspect(principal.actor_user_id,principal.installation_id)} if router else {}
        result=[f for f in FORMS.values() if (f.capability or f.key) in allowed and
            (f.key not in states or (states[f.key].get('enabled',True) and states[f.key].get('status')!='cooldown'))]
        return sorted(result,key=lambda f:(f.key!=form.key,(f.capability or f.key)!=(form.capability or form.key),f.priority,f.key))
    def handoff_record(runtime,item):
        with runtime.database.transaction() as db:row=db.execute('SELECT * FROM agent_parameter_handoffs WHERE interaction_id=?',(item.id,)).fetchone()
        return dict(row) if row else None
    @router.post('/search/prepare')
    def prepare_search(run_id:str,interaction_id:str,body:DraftInput,principal=dep):
        from ai2apps.research import search_preparation as search
        from ai2apps.research.search_form import PROVIDER, mounted, begin_form
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        if form.key!=PROVIDER:raise HTTPException(422,'Not a Search All form')
        current=draft(runtime,item,form,principal)
        if body.revision!=current['revision'] or body.values!=current['values']:raise HTTPException(409,'Save the search draft first')
        try:
            return begin_form(runtime,principal,item,run,body.values,body.revision)
        except ValueError as error:raise HTTPException(422,str(error)) from error
    @router.get('/search/{preparation_id}')
    def search_preparation(run_id:str,interaction_id:str,preparation_id:str,principal=dep):
        from ai2apps.research import search_preparation as search
        from ai2apps.research.search_form import PROVIDER, mounted
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        if form.key!=PROVIDER:raise HTTPException(422,'Not a Search All form')
        try:return search.view(runtime,principal,mounted(runtime,principal,item,run.session_id),preparation_id,scope='interaction:'+item.id)
        except ValueError as error:raise HTTPException(422,str(error)) from error
    @router.get('')
    async def get(run_id:str,interaction_id:str,principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        current=draft(runtime,item,form,principal)
        extra=await form.describe(runtime,principal,form,current['values'],item) if form.describe else {}
        schema=extra.pop('schema',form.schema)
        # Use the same closed-schema preparation as Tool invocation, after owner
        # aliases and dynamic fields resolve. Persist the reviewed projection so
        # submit still compares exact canonical values and revision.
        from ai2apps.agents.tool_arguments import prepare_arguments
        from ai2apps.agents.artifact_outputs import bind_output_materials
        bound=bind_output_materials(runtime,principal,run.session_id,schema,current['values'])
        prepared,contract_error=prepare_arguments(schema,bound)
        if prepared!=current['values'] and not handoff_record(runtime,item):
            with runtime.database.transaction(write=True) as db:
                if db.execute('SELECT 1 FROM agent_parameter_handoffs WHERE interaction_id=?',(item.id,)).fetchone():
                    raise HTTPException(409,'Continue editing in the target App')
                row=db.execute('SELECT revision FROM agent_parameter_drafts WHERE interaction_id=?',(item.id,)).fetchone()
                revision=row['revision'] if row else 0
                status=db.execute('SELECT status FROM agent_interactions WHERE id=?',(item.id,)).fetchone()
                if revision!=current['revision'] or not status or status['status']!='pending':
                    raise HTTPException(409,'Draft changed; reload')
                db.execute('INSERT INTO agent_parameter_drafts VALUES (?,?,?) ON CONFLICT(interaction_id) DO UPDATE SET revision=excluded.revision,values_json=excluded.values_json',
                    (item.id,revision+1,json.dumps(prepared)))
            current={'revision':revision+1,'values':prepared}
        fields=extra.pop('fields',None) or (form.fields if schema==form.schema else schema_fields(schema)) or schema_fields(schema)
        from ai2apps.agents.form_continuation import ADAPTERS
        descriptions={t.qualified_name:t.description for t in runtime.services.list_tools(include_disabled=False)}
        choices=[{'provider':f.key,'capability':f.capability or f.key,'app_id':f.app_id,'mini_app_id':f.mini_app_id,
            'description':f.summary or descriptions.get(f.capability or f.key,''),'display_name':f.display_name} for f in alternatives(runtime,principal,form)]
        handoff=handoff_record(runtime,item)
        return {'descriptor':{'capability':form.capability or form.key,'provider':form.key,'app_id':form.app_id,
            'mini_app_id':form.mini_app_id,'display_name':form.display_name,'summary':form.summary,'fields':fields,'schema':schema},'alternatives':choices,
            'prompt_labels':form.prompt if isinstance(form.prompt,dict) else ({'zh':'确认调用参数','en':'Confirm call parameters'} if form.prompt=='填写参数 / Complete parameters' else None),
            'can_continue_in_app':form.continuation in ADAPTERS,'waiting_app':bool(handoff),
            'studio_run_id':handoff['studio_run_id'] if handoff else None,**current,
            'parameter_contract_error':json.loads(contract_error) if contract_error else None,
            **diagnostics(schema,current['values']), 'models':[], 'configure_only':form.mode=='configure',**extra}
    @router.get('/setup')
    async def setup(run_id:str,interaction_id:str,principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        if form.key in runtime.app_capability_router.disabled(principal.actor_user_id,principal.installation_id):
            raise HTTPException(409,'Provider disabled')
        current=draft(runtime,item,form,principal)
        descriptor=await form.describe(runtime,principal,form,current['values'],item) if form.describe else {}
        install=descriptor.get('install')
        if not isinstance(install,dict) or install.get('appId')!=(form.configuration_app_id or form.app_id) or not install.get('capability'):
            raise HTTPException(422,'This Provider has not declared an owning App configuration flow')
        with runtime.database.transaction() as db:
            origin=db.execute('''SELECT s.id session_id,i.id instance_id,d.package_id app_id FROM sessions s
                JOIN app_instances i ON i.id=s.app_instance_id JOIN app_definitions d ON d.id=i.app_definition_id
                WHERE s.id=?''',(run.session_id,)).fetchone()
        if not origin:raise HTTPException(409,'Origin Session unavailable')
        # Configuration never creates a business job or changes confirmation.
        # Stable action identity lets the existing ACPF resume after reconnect.
        install={**install,'actionId':'aaat-setup:'+item.id+':'+hashlib.sha256((form.key+str(form.provider_version)).encode()).hexdigest()[:16],
            'intent':{'returnTo':'/apps/'+origin['app_id'],'resumeToken':item.id,'completionPolicy':'configure_only'}}
        return {'run_id':run.id,'interaction_id':item.id,'provider':form.key,'provider_version':form.provider_version,
            'origin':dict(origin),'target':{'app_id':install['appId'],'mini_app_id':form.mini_app_id},
            'install':install,'revision':current['revision'],'desktop_required':True}

    async def configuration(run_id, interaction_id, principal):
        target = await setup(run_id, interaction_id, principal)
        runtime = runtime_provider()
        engine = runtime.provisioning
        if engine is None:
            raise HTTPException(503, 'ACPF is not initialized')
        install = target['install']
        # The durable ACPF record is the binding. Client-supplied session IDs,
        # App identities and installation plans never select a configuration.
        with runtime.database.transaction() as db:
            row = db.execute("""SELECT id FROM provisioning_sessions
                WHERE actor_id=? AND installation_id=? AND app_id=? AND action_id=?
                ORDER BY rowid DESC LIMIT 1""",
                (principal.actor_user_id, principal.installation_id,
                 install['appId'], install['actionId'])).fetchone()
        session = engine.repository.get(row['id']) if row else None
        if session and (session['capability'] != install['capability']
                or any(session['intent'].get(key) != install['intent'].get(key)
                       for key in ('resumeToken', 'returnTo', 'completionPolicy'))):
            raise HTTPException(409, 'Configuration binding changed; reopen setup')
        return runtime, engine, target, session

    @router.get('/setup/session')
    async def setup_session(run_id:str, interaction_id:str, principal=dep):
        runtime, engine, target, session = await configuration(run_id, interaction_id, principal)
        if session:
            session = await engine.resume_if_possible(session['id'])
        return {'session':session, 'desktop_required':True}

    @router.post('/setup/session')
    async def begin_setup(run_id:str, interaction_id:str, principal=dep):
        runtime, engine, target, session = await configuration(run_id, interaction_id, principal)
        if not principal.is_core:
            raise HTTPException(403, 'Installation owner required')
        if session and session['status'] != 'cancelled':
            return {'session':await engine.resume_if_possible(session['id'])}
        install = target['install']
        instance, _, _ = runtime.extension_manager.launch_app(install['appId'], principal=principal)
        refresh = getattr(engine, 'refresh_registry_status', None)
        if refresh: await refresh()
        result = engine.ensure(actor_id=principal.actor_user_id,
            installation_id=principal.installation_id, app_instance_id=instance.id,
            app_id=install['appId'], capability=install['capability'],
            action_id=install['actionId'], requirements=install.get('requirements', {}),
            intent=install['intent'])
        return result

    @router.post('/setup/session/{action}')
    async def setup_action(run_id:str, interaction_id:str, action:str, request:Request, principal=dep):
        runtime, engine, target, session = await configuration(run_id, interaction_id, principal)
        if not session: raise HTTPException(404, 'Configuration session not found')
        if not principal.is_core: raise HTTPException(403, 'Installation owner required')
        from ai2apps.api.provisioning import ProvisioningConfirmRequest, ProfileSelectionRequest
        from pydantic import ValidationError as InputError
        try:
            if action in ('confirm', 'retry'):
                if action == 'retry' and session['status'] != 'failed':
                    raise HTTPException(409, 'Only failed sessions can retry')
                body = ProvisioningConfirmRequest.model_validate(await request.json())
                return await engine.confirm(session['id'], [i.model_dump(by_alias=True) for i in body.license_consents])
            if action == 'select-profile':
                body = ProfileSelectionRequest.model_validate(await request.json())
                return engine.select_profile(session['id'], body.profile_id)
            if action == 'cancel': return await engine.cancel(session['id'])
            if action == 'acknowledge-return':
                if session['status'] != 'ready': raise HTTPException(409, 'Configuration is not ready')
                return engine.repository.acknowledge_return(session['id'])
        except (InputError, ValueError) as error:
            raise HTTPException(422, str(error)) from error
        raise HTTPException(404, 'Unknown configuration action')

    @router.put('')
    async def save(run_id:str,interaction_id:str,body:DraftInput,principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        if handoff_record(runtime,item):raise HTTPException(409,'Continue editing in the target App')
        if len(json.dumps(body.values))>16384:raise HTTPException(413,'Draft too large')
        extra=await form.describe(runtime,principal,form,body.values,item) if form.describe else {}
        from ai2apps.agents.tool_arguments import prepare_arguments
        active_schema=extra.get('schema',form.schema)
        from ai2apps.agents.parameter_contracts import problems
        if any(e['validator'] in ('additionalProperties','unevaluatedProperties') for e in problems(active_schema,body.values,partial=True)):
            _,error=prepare_arguments(active_schema,body.values)
            raise HTTPException(422,json.loads(error))
        from ai2apps.agents.artifact_outputs import bind_output_materials
        body.values=bind_output_materials(runtime,principal,run.session_id,active_schema,body.values)
        validate(runtime,principal,form,body.values)
        with runtime.database.transaction(write=True) as db:
            if db.execute('SELECT 1 FROM agent_parameter_handoffs WHERE interaction_id=?',(item.id,)).fetchone():raise HTTPException(409,'Continue editing in the target App')
            row=db.execute('SELECT revision FROM agent_parameter_drafts WHERE interaction_id=?',(item.id,)).fetchone()
            revision=row['revision'] if row else 0
            if revision!=body.revision:raise HTTPException(409,'Draft changed in another view; reload')
            db.execute('INSERT INTO agent_parameter_drafts VALUES (?,?,?) ON CONFLICT(interaction_id) DO UPDATE SET revision=excluded.revision,values_json=excluded.values_json',(item.id,revision+1,json.dumps(body.values)))
        return {'revision':revision+1,'values':body.values,**diagnostics(extra.get('schema',form.schema),body.values)}
    @router.post('/switch')
    async def switch(run_id:str,interaction_id:str,body:SwitchInput,principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        if handoff_record(runtime,item):raise HTTPException(409,'Cannot switch an active App continuation')
        target=next((f for f in alternatives(runtime,principal,form) if f.key==body.provider),None)
        if target is None:raise HTTPException(422,'This Provider is not a declared compatible alternative')
        current=draft(runtime,item,form,principal)
        if current['revision']!=body.revision:raise HTTPException(409,'Draft changed; reload')
        with runtime.database.transaction() as db:old=db.execute('SELECT drafts_json FROM agent_parameter_choices WHERE interaction_id=?',(item.id,)).fetchone()
        snapshots=json.loads(old['drafts_json']) if old else {}
        snapshots[form.key]=current['values']
        values=snapshots.get(target.key)
        if values is None:
            values=form.switch_values(runtime,run,form,target,current['values']) if form.switch_values else dict(current['values'])
            descriptor=await target.describe(runtime,principal,target,values,item) if target.describe else {}
            schema=descriptor.get('schema',target.schema)
            values={k:v for k,v in values.items() if k in schema.get('properties',{})}
        if len(json.dumps(values))>16384:raise HTTPException(413,'Draft too large')
        resolve(run_id,interaction_id,principal)
        with runtime.database.transaction() as db:
            if db.execute('SELECT 1 FROM agent_parameter_handoffs WHERE interaction_id=?',(item.id,)).fetchone():raise HTTPException(409,'Cannot switch an active App continuation')
            row=db.execute('SELECT revision FROM agent_parameter_drafts WHERE interaction_id=?',(item.id,)).fetchone()
            if (row['revision'] if row else 0)!=body.revision:raise HTTPException(409,'Draft changed; reload')
            db.execute('INSERT INTO agent_parameter_choices VALUES (?,?,?,?,?,?,?) ON CONFLICT(interaction_id) DO UPDATE SET provider=excluded.provider,version=excluded.version,app_id=excluded.app_id,mini_app_id=excluded.mini_app_id,provider_version=excluded.provider_version,drafts_json=excluded.drafts_json',
                (item.id,target.key,target.version,target.app_id,target.mini_app_id,target.provider_version,json.dumps(snapshots)))
            db.execute('INSERT INTO agent_parameter_drafts VALUES (?,?,?) ON CONFLICT(interaction_id) DO UPDATE SET revision=excluded.revision,values_json=excluded.values_json',(item.id,body.revision+1,json.dumps(values)))
        return {'revision':body.revision+1,'values':values}
    @router.post('/handoff')
    def begin_handoff(run_id:str,interaction_id:str,body:DraftInput,principal=dep):
        from ai2apps.agents.form_continuation import ADAPTERS, handoff_view
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        adapter=ADAPTERS.get(form.continuation)
        if not adapter:raise HTTPException(422,'This App has not declared a continuation adapter')
        if form.key in runtime.app_capability_router.disabled(principal.actor_user_id,principal.installation_id):raise HTTPException(409,'Provider disabled')
        current=draft(runtime,item,form,principal)
        if body.revision!=current['revision'] or body.values!=current['values']:raise HTTPException(409,'Save current parameters first')
        if not handoff_record(runtime,item):
            payload=adapter.begin(runtime,principal,run,item,form,current['values'])
            with runtime.database.transaction() as db:
                selected=db.execute('SELECT provider FROM agent_parameter_choices WHERE interaction_id=?',(item.id,)).fetchone()
                if (selected['provider'] if selected else item.ui_hints.get('provider'))!=form.key:raise HTTPException(409,'Provider changed')
                row=db.execute('SELECT revision FROM agent_parameter_drafts WHERE interaction_id=?',(item.id,)).fetchone()
                if (row['revision'] if row else 0)!=current['revision']:raise HTTPException(409,'Draft changed')
                db.execute('INSERT OR IGNORE INTO agent_parameter_handoffs(interaction_id,provider,payload_json,created_at) VALUES (?,?,?,?)',
                    (item.id,form.key,json.dumps(payload),datetime.now(UTC).isoformat()))
        runtime.agents.update_status_line(run.id,phase='app_handoff',text='等待 App 完成 / Waiting for App',presentation='pulse',
            content={'provider':form.key,'app_id':form.app_id,'mini_app_id':form.mini_app_id,'phase':'app'})
        return handoff_view(runtime,run_id,interaction_id)
    @router.post('/handoff/link')
    async def link_handoff(run_id:str,interaction_id:str,body:LinkInput,principal=dep):
        lock=locks.setdefault(interaction_id,asyncio.Lock())
        async with lock:
            from ai2apps.agents.form_continuation import ADAPTERS
            runtime,run,item,form=resolve(run_id,interaction_id,principal)
            record=handoff_record(runtime,item)
            if not record:raise HTTPException(409,'No active App continuation')
            adapter=ADAPTERS.get(form.continuation)
            if not adapter:raise HTTPException(409,'App continuation adapter changed')
            linked=adapter.link(runtime,principal,run,item,form,record,body)
            with runtime.database.transaction() as db:db.execute('UPDATE agent_parameter_handoffs SET studio_run_id=?,app_instance_id=? WHERE interaction_id=?',
                (linked['studio_run_id'],linked['app_instance_id'],item.id))
            return linked
    @router.post('/handoff/complete')
    async def complete_handoff(run_id:str,interaction_id:str,principal=dep):
        from ai2apps.agents.form_continuation import ADAPTERS
        lock=locks.setdefault(interaction_id,asyncio.Lock())
        async with lock:
            runtime,run,item,form=resolve(run_id,interaction_id,principal,pending=False)
            if item.status.value=='submitted':return item.response
            resolve(run_id,interaction_id,principal)
            record=handoff_record(runtime,item)
            adapter=ADAPTERS.get(form.continuation)
            if not record or not adapter:raise HTTPException(409,'No active App continuation')
            result=adapter.complete(runtime,principal,run,item,form,record)
            payload={'status':'completed','result':{**result,'user_confirmed':True}}
            runtime.agents.respond_interaction(run.id,item.id,response=payload,response_id='form-app:'+item.id,app_interaction_capability=item.request['capability'])
            runtime.agent_runtime.wake()
            return payload
    @router.post('/audio')
    async def upload(run_id:str,interaction_id:str,file:UploadFile=File(...),principal=dep):
        runtime,*_=resolve(run_id,interaction_id,principal)
        try:
            content=await file.read(64*1024*1024+1)
            resolve(run_id,interaction_id,principal)
            return {'asset':materials(runtime).save(principal.actor_user_id,content,file.filename or 'audio.wav',file.content_type or 'audio/wav')}
        except ValueError as e:raise HTTPException(422,str(e)) from e
        finally:await file.close()
    @router.post('/gallery')
    def gallery(run_id:str,interaction_id:str,body:GalleryInput,principal=dep):
        runtime,*_=resolve(run_id,interaction_id,principal)
        try:return {'asset':materials(runtime).import_gallery(principal.actor_user_id,body.asset_id)}
        except (RepositoryError,ValueError) as e:raise HTTPException(422,'Audio unavailable') from e
    async def asset_field(runtime,principal,item,form,field):
        values=draft(runtime,item,form,principal)['values']
        extra=await form.describe(runtime,principal,form,values,item) if form.describe else {}
        fields=extra.get('fields') or form.fields or schema_fields(extra.get('schema',form.schema))
        selected=next((f for f in fields if f['key']==field and f['type']=='asset' and f.get('storage')=='artifact'),None)
        if not selected:raise HTTPException(422,'Field is not a declared artifact slot')
        return selected
    def accepts(field,media):
        allowed=field.get('accept','').split(',')
        return not field.get('accept') or any(media==a.strip() or (a.strip().endswith('/*') and media.startswith(a.strip()[:-1])) for a in allowed)
    def artifact_info(run,artifact):
        return {'id':artifact.id,'name':artifact.name,'media_type':artifact.media_type,'size_bytes':artifact.size_bytes,
            'preview_url':f'/v1/platform/sessions/{run.session_id}/artifacts/{artifact.id}/download'}
    @router.get('/materials')
    async def list_materials(run_id:str,interaction_id:str,field:str,principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        spec=await asset_field(runtime,principal,item,form,field)
        items=[artifact_info(run,a) for a in runtime.workspace.list_artifacts(run.session_id) if accepts(spec,a.media_type)]
        if spec.get('references'):
            items.extend({'id':a.id,'name':a.filename,'media_type':a.media_type,'size_bytes':a.size_bytes,'storage':'reference',
                'preview_url':f'/v1/platform/sessions/{run.session_id}/attachments/{a.id}/content'}
                for a in runtime.documents.list(run.session_id) if accepts(spec,a.media_type))
        if spec.get('references'):
            # A selected Gallery ID is already an opaque platform resource.
            # Resolve metadata under the actor; never expose a storage path.
            selected=draft(runtime,item,form,principal)['values'].get(field)
            identifiers=selected if isinstance(selected,list) else [selected]
            from ai2apps.gallery import GalleryRepository
            gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
            for identifier in identifiers:
                if not isinstance(identifier,str) or not identifier.startswith('gala_'):continue
                try:asset=gallery.get_asset(principal.actor_user_id,identifier)
                except RepositoryError:continue
                if asset['status']=='active' and accepts(spec,asset['media_type']):
                    items.insert(0,{'id':asset['id'],'name':asset['name'],'media_type':asset['media_type'],
                        'size_bytes':asset['size_bytes'],'storage':'reference',
                        'preview_url':f"/v1/platform/gallery/assets/{asset['id']}/content"})
        return {'items':items[:200]}
    @router.post('/materials/reference')
    async def reference_material(run_id:str,interaction_id:str,field:str,body:dict,request:Request,principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        spec=await asset_field(runtime,principal,item,form,field)
        if not spec.get('references'):raise HTTPException(422,'This field does not accept references')
        if not principal.is_core or principal.client_scope!='desktop' or request.client.host not in {'127.0.0.1','::1','testclient'}:raise HTTPException(403,'Select this file on Desktop')
        media=str(body.get('media_type') or '')
        if not accepts(spec,media):raise HTTPException(422,'Material type not accepted')
        try:
            asset=runtime.documents.create_reference(run.session_id,Path(body.get('source_path','')),filename=body.get('filename'),media_type=media)
            return {'asset':{'id':asset.id,'name':asset.filename,'media_type':asset.media_type,'size_bytes':asset.size_bytes,'storage':'reference'}}
        except ValueError as error:raise HTTPException(422,str(error)) from error

    @router.post('/materials/upload')
    async def upload_material(run_id:str,interaction_id:str,field:str,file:UploadFile=File(...),principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        spec=await asset_field(runtime,principal,item,form,field)
        try:
            if spec.get('references'):
                from ai2apps.api.documents import store_uploaded_reference
                media=file.content_type or 'application/octet-stream'
                if not accepts(spec,media):raise HTTPException(422,'Material type is not accepted')
                asset=await store_uploaded_reference(runtime,run.session_id,file)
                return {'asset':{'id':asset.id,'name':asset.filename,'media_type':asset.media_type,'size_bytes':asset.size_bytes,'storage':'reference'}}
            content=await file.read(20*1024*1024+1)
            if not content or len(content)>20*1024*1024:raise HTTPException(413,'Material must be non-empty and at most 20 MiB')
            media=file.content_type or 'application/octet-stream'
            if media.startswith('image/'):
                import io
                from PIL import Image
                try:
                    with Image.open(io.BytesIO(content)) as image:
                        media={'PNG':'image/png','JPEG':'image/jpeg','WEBP':'image/webp'}.get(image.format,'')
                        if image.width*image.height>25_000_000:raise HTTPException(422,'Image exceeds 25 million pixels')
                        image.verify()
                except (ValueError,OSError) as error:raise HTTPException(422,'Invalid image') from error
            if not media or not accepts(spec,media):raise HTTPException(422,'Material type is not accepted by this field')
            resolve(run_id,interaction_id,principal)
            with tempfile.TemporaryDirectory(prefix='form-material-') as directory:
                path=Path(directory)/(Path(file.filename or 'material').name or 'material')
                path.write_bytes(content)
                artifact=runtime.workspace.import_artifact(run.session_id,path,name=path.name,media_type=media)
            return {'asset':artifact_info(run,artifact)}
        finally:await file.close()
    @router.post('/materials/gallery')
    async def import_material(run_id:str,interaction_id:str,body:MaterialGalleryInput,principal=dep):
        runtime,run,item,form=resolve(run_id,interaction_id,principal)
        spec=await asset_field(runtime,principal,item,form,body.field)
        from ai2apps.gallery import GalleryRepository
        gallery=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
        try:asset,path=gallery.asset_path(principal.actor_user_id,body.asset_id)
        except (RepositoryError,ValueError) as error:raise HTTPException(404,'Material unavailable') from error
        if not accepts(spec,asset['media_type']):raise HTTPException(422,'Material type is not accepted by this field')
        if spec.get('references'):
            record=runtime.documents.create_reference(run.session_id,path,filename=asset['name'],media_type=asset['media_type'],source='gallery',gallery_asset_id=asset['id'],owner_user_id=principal.actor_user_id)
            return {'asset':{'id':record.id,'name':record.filename,'media_type':record.media_type,'size_bytes':record.size_bytes,'storage':'reference'}}
        if path.stat().st_size>20*1024*1024:raise HTTPException(413,'Material exceeds 20 MiB')
        artifact=runtime.workspace.import_artifact(run.session_id,path,name=asset['name'],media_type=asset['media_type'])
        return {'asset':artifact_info(run,artifact)}
    @router.post('/submit')
    async def submit(run_id:str,interaction_id:str,body:DraftInput,principal=dep):
        # Serializes duplicate submissions within this Local. A restart may retry
        # computation, but only the durable Interaction response resumes the Run.
        lock=locks.setdefault(interaction_id,asyncio.Lock())
        async with lock:
            runtime,run,item,form=resolve(run_id,interaction_id,principal,pending=False)
            if item.status.value=='submitted':return item.response
            resolve(run_id,interaction_id,principal)
            if handoff_record(runtime,item):raise HTTPException(409,'Complete the task in the target App first')
            current=draft(runtime,item,form,principal)
            if body.revision!=current['revision'] or body.values!=current['values']:raise HTTPException(409,'Save the current draft before submitting')
            extra=await form.describe(runtime,principal,form,body.values,item) if form.describe else {}
            if extra.get('configuration_required'):raise HTTPException(409,{'code':'configuration_required','message':'Configure this capability in its Desktop App; parameters and materials are preserved'})
            schema=extra.get('schema',form.schema)
            values=dict(body.values)
            for key,spec in schema.get('properties',{}).items():
                if key not in values and 'default' in spec: values[key]=spec['default']
            try:Draft202012Validator(schema).validate(values)
            except ValidationError as e:raise HTTPException(422,{'field':'.'.join(map(str,e.path)),'message':e.message}) from e
            validate(runtime,principal,form,values)
            if form.complete:
                result=await form.complete(runtime,principal,form,values,run)
            else:
                result={'capability':form.capability or form.key,'provider':form.key,'arguments':values,'configure_only':True}
            resolve(run_id,interaction_id,principal)
            if draft(runtime,item,form,principal)!=current:raise HTTPException(409,'Draft changed; review and resubmit')
            payload={'status':'completed','result':{**result,'user_confirmed':True}}
            runtime.agents.respond_interaction(run_id,interaction_id,response=payload,response_id='form:'+interaction_id,app_interaction_capability=item.request['capability'])
            runtime.agent_runtime.wake()
            return payload
    return router
