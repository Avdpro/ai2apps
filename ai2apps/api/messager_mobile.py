"""Messager-owned Mobile surface over the existing durable Bot services.

Only the authenticated owner of this Mobile mount is used. No desktop principal,
admin cookie, arbitrary Platform proxy or new execution authority is created.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, Form
from typing import Literal
import logging
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import FileResponse
from ai2apps.api.identity import require_app_capability
from ai2apps.core import RepositoryError
from ai2apps.messager.creation import BotCreateDraft
from ai2apps.api.messager import BotDialogueTurn, BotReadPosition, BotConversationModel, CreateBot, BotGroupCreate, BotGroupUpdate, BotGroupOrder, BotOrder, BotTrimReview, BotTrimApply
from ai2apps.messager.conversation_profile import settings as model_settings

from ai2apps.api.messager import BotRealtimeSettings, BotRealtimeStart, BotRealtimeControl, BotRealtimeInput

APP='ai2apps.messager'
CHAT=APP+'.bots'

class Open(BaseModel):
    model_config=ConfigDict(extra='forbid')
    bot_id:str=Field(min_length=1,max_length=128)


class MobileTurn(BotDialogueTurn):
    model:str|None=Field(default=None,max_length=300)


class MobilePoke(BaseModel):
    session_id:str=Field(min_length=1,max_length=100)
    request_id:str=Field(min_length=1,max_length=100)
    language:str=Field(default='zh',max_length=20)

class MobileReadReply(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str=Field(min_length=1,max_length=100)
    text:str=Field(min_length=1,max_length=2000)


class MobileSpeech(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str=Field(min_length=1,max_length=100)
    voice_id:str=Field(min_length=1,max_length=100)
    controller:str=Field(min_length=16,max_length=100)
    text:str=Field(min_length=1,max_length=2000)


class MobileAnswer(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str=Field(min_length=1,max_length=100)
    response_id:str=Field(min_length=1,max_length=128)
    response:dict

def create_messager_mobile_router(runtime_provider, principal_provider):
    logging.getLogger(__name__).info("Mobile Bot voice API loaded from %s",__file__)
    async def owner(p=Depends(principal_provider)):
        if not p.is_core or p.authentication_type!='owner_home_lease' or p.client_scope!='owner-home':
            raise HTTPException(403,'Owner Mobile mount required')
        return p
    router=APIRouter(prefix='/messager-mobile',dependencies=[Depends(require_app_capability(principal_provider,'app.use')),Depends(owner)])
    def runtime():return runtime_provider()
    def call(fn):
        try:return fn()
        except (PermissionError,KeyError,RepositoryError) as exc:raise HTTPException(404,'Bot resource unavailable') from exc
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc
    def session(p,bot,sid):
        binding=runtime().app_chat.access(p,sid)
        if binding['registration']!=CHAT or binding['scope']!={'bot_id':bot}:raise PermissionError('Main Bot conversation required')
        runtime().messager_bots.scope(p.actor_user_id,{'bot_id':bot})
        return binding

    @router.get('/bots')
    def bots(language:Literal['en','zh']='en',p=Depends(owner)):
        from ai2apps.messager.creation import ensure_research
        directory=runtime().messager_bots;default=directory.ensure_default(p.actor_user_id)
        call(lambda:ensure_research(runtime(),p.actor_user_id,language))
        return {'items':[{**b,'is_default':b['id']==default} for b in directory.list(p.actor_user_id)]}

    @router.get('/creation/options')
    def creation_options(p=Depends(owner)):
        from ai2apps.messager.creation import options
        return options(runtime())

    from ai2apps.messager.flash_plans import CompileRequest,ActivateRequest

    @router.post('/flash-workflows/compile')
    async def compile_flash(body:CompileRequest,p=Depends(owner)):
        from ai2apps.messager.flash_plans import compile_plan
        try:return await compile_plan(runtime(),p,body)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    @router.post('/bots/{bot_id}/flash-workflow')
    def activate_flash(bot_id:str,body:ActivateRequest,p=Depends(owner)):
        from ai2apps.messager.flash_plans import activate
        return call(lambda:activate(runtime(),p.actor_user_id,bot_id,body))

    @router.post('/creation',status_code=201)
    def create_bot(body:BotCreateDraft,p=Depends(owner)):
        from ai2apps.messager.creation import create
        return call(lambda:create(runtime(),p.actor_user_id,body))

    @router.get('/models')
    async def models(p=Depends(owner)):
        from ai2apps.web import owner_home_gateway
        from ai2apps.web.mobile_model_catalog import desktop_catalog_projection
        from ai2apps.model_capabilities import agent_model_selectable
        if owner_home_gateway._models is None:raise HTTPException(503,'Model catalog unavailable')
        value=await owner_home_gateway._models(p)
        if hasattr(value,'model_dump'):value=value.model_dump(mode='json')
        rows=await desktop_catalog_projection(value.get('data',[]))
        manager=runtime().model_manager
        defaults=manager.default_models() if manager else {}
        policy=manager.cloud_default_policy() if manager else {}
        api=policy.get('apiDefault') or {}
        return {'data':[m for m in rows if agent_model_selectable(m)],
                'defaults':{k:defaults.get(k) for k in ('work_agent','work_standard','work_complex')},
                'api_default':api.get('modelId')}

    @router.post('/open')
    def open_bot(body:Open,p=Depends(owner)):
        def action():
            runtime().messager_bots.scope(p.actor_user_id,{'bot_id':body.bot_id})
            sid=runtime().app_chat.open(p,CHAT,{'bot_id':body.bot_id},{})
            return {'session_id':sid,'profile':model_settings(runtime(),p.actor_user_id,body.bot_id)}
        return call(action)


    @router.get('/bots/{bot}/voice/catalog')
    def voice_catalog(bot:str,p=Depends(owner)):
        from ai2apps.messager.mobile_voice import catalog
        return call(lambda:catalog(runtime(),p,bot))

    @router.get('/bots/{bot}/realtime/settings')
    def realtime_settings(bot:str,p=Depends(owner)):
        return call(lambda:runtime().messager_dialogue.realtime.get(p.actor_user_id,bot))

    @router.put('/bots/{bot}/realtime/settings')
    def realtime_save(bot:str,body:BotRealtimeSettings,p=Depends(owner)):
        return call(lambda:runtime().messager_dialogue.realtime.save(p.actor_user_id,bot,body.model_dump(exclude={'revision'}),body.revision))

    @router.post('/bots/{bot}/realtime/sessions')
    def realtime_start(bot:str,body:BotRealtimeStart,p=Depends(owner)):
        def action():
            session(p,bot,body.session_id)
            model=model_settings(runtime(),p.actor_user_id,bot)['effective_model']
            if body.model!=model:raise ValueError('Bot model changed; reload conversation')
            return runtime().messager_dialogue.realtime.start(p,bot,body.session_id,body.controller,body.revision,model,body.language,None)
        return call(action)

    @router.post('/bots/{bot}/realtime/sessions/{voice_id}/touch')
    def realtime_touch(bot:str,voice_id:str,body:BotRealtimeControl,p=Depends(owner)):
        return call(lambda:runtime().messager_dialogue.realtime.touch(p,bot,voice_id,body.controller))

    @router.post('/bots/{bot}/realtime/sessions/{voice_id}/close')
    def realtime_close(bot:str,voice_id:str,body:BotRealtimeControl,p=Depends(owner)):
        return call(lambda:runtime().messager_dialogue.realtime.close(p,bot,voice_id,body.controller))

    @router.post('/bots/{bot}/realtime/sessions/{voice_id}/inputs')
    def realtime_submit(bot:str,voice_id:str,body:BotRealtimeInput,p=Depends(owner)):
        return call(lambda:runtime().messager_dialogue.realtime.submit(p,bot,voice_id,body.controller,body.turn_id,body.text,body.attachments))

    @router.post('/bots/{bot}/voice/transcriptions')
    async def transcription(bot:str,session_id:str=Form(...,min_length=1,max_length=100),voice_id:str|None=Form(None,min_length=1,max_length=100),controller:str|None=Form(None,min_length=16,max_length=100),file:UploadFile=File(...),p=Depends(owner)):
        from ai2apps.messager.mobile_voice import transcribe
        try:return await transcribe(runtime(),p,bot,session_id,file,voice_id,controller)
        except (PermissionError,KeyError,RepositoryError) as error:raise HTTPException(404,'Voice conversation unavailable') from error
        except ValueError as error:raise HTTPException(409,str(error)) from error

    @router.post('/bots/{bot}/voice/speech')
    async def speech(bot:str,body:MobileSpeech,p=Depends(owner)):
        from ai2apps.messager.mobile_voice import speak
        try:return await speak(runtime(),p,bot,body.session_id,body.voice_id,body.controller,body.text)
        except (PermissionError,KeyError,RepositoryError) as error:raise HTTPException(404,'Voice conversation unavailable') from error
        except ValueError as error:raise HTTPException(409,str(error)) from error

    @router.post('/bots/{bot}/voice/read')
    async def read_reply(bot:str,body:MobileReadReply,p=Depends(owner)):
        from ai2apps.messager.mobile_voice import read_reply as narrate
        call(lambda:session(p,bot,body.session_id))
        try:return await narrate(runtime(),p,bot,body.session_id,body.text)
        except (PermissionError,KeyError,RepositoryError) as error:raise HTTPException(404,'Bot voice unavailable') from error
        except ValueError as error:raise HTTPException(409,str(error)) from error

    @router.get('/bots/{bot}/details')
    def details(bot:str,p=Depends(owner)):
        def action():
            r=runtime();actor=p.actor_user_id;directory=r.messager_bots
            identity=directory.identity(actor,{'bot_id':bot})
            from ai2apps.messager.voice import BotVoice
            from ai2apps.messager.statistics import statistics
            return {'identity':identity,'statistics':statistics(r,actor,bot),'model':model_settings(r,actor,bot),
                    'access':r.messager_bot_app_access.catalog(actor,bot),
                    'memories':directory.memory.list(actor,bot),
                    'voice':BotVoice(directory,r).get(actor,bot),
                    'notifications':r.messager_bot_notifications.policy(actor,bot)}
        return call(action)

    @router.patch('/bots/{bot}/profile')
    def profile(bot:str,body:CreateBot,p=Depends(owner)):
        return call(lambda:runtime().messager_bots.update(p.actor_user_id,bot,body.name,body.duty))

    @router.get('/bots/{bot}/reasoning-efforts')
    def reasoning_efforts(bot:str,model_id:str=Query(min_length=1,max_length=300),p=Depends(owner)):
        from ai2apps.messager.conversation_profile import supported_reasoning_efforts
        def action():
            r=runtime()
            r.messager_bots.scope(p.actor_user_id,{'bot_id':bot})
            return {'supported_reasoning_efforts':supported_reasoning_efforts(r,model_id)}
        return call(action)

    @router.put('/bots/{bot}/conversation-model')
    def save_model(bot:str,body:BotConversationModel,p=Depends(owner)):
        return call(lambda:model_settings(runtime(),p.actor_user_id,bot,expected_revision=body.revision,**body.model_dump(exclude_unset=True,exclude={'revision'})))

    @router.get('/bots/{bot}/messages')
    def messages(bot:str,session_id:str,before:int|None=Query(None,ge=1),after:int|None=Query(None,ge=0),p=Depends(owner)):
        def action():
            session(p,bot,session_id)
            return runtime().app_chat.message_page(p,session_id,50,before,after)
        return call(action)

    @router.get('/bots/{bot}/state')
    def state(bot:str,session_id:str,p=Depends(owner)):
        def action():
            session(p,bot,session_id)
            return {**runtime().messager_dialogue.snapshot(p,bot,session_id),
                    'unread':runtime().messager_bots.unread.state(p.actor_user_id,bot,session_id)}
        return call(action)

    @router.post('/bots/{bot}/runs/{run_id}/questions/{interaction_id}/respond')
    def answer_question(bot:str,run_id:str,interaction_id:str,body:MobileAnswer,p=Depends(owner)):
        def action():
            session(p,bot,body.session_id)
            snapshot=runtime().messager_dialogue.snapshot(p,bot,body.session_id)
            if not any(r['id']==run_id for r in snapshot['runs']):
                raise PermissionError('Question is outside this Bot conversation')
            item=next((i for i in runtime().agents.list_interactions(run_id) if i.id==interaction_id),None)
            if item is None or item.kind.value not in ('text','menu') or not item.request_key.startswith('question:'):
                raise PermissionError('Only original user questions may be answered here')
            runtime().agents.respond_interaction(run_id,interaction_id,response_id=body.response_id,response=body.response)
            runtime().agent_runtime.wake()
            return {'submitted':True}
        return call(action)

    @router.post('/bots/{bot}/read')
    def read(bot:str,body:BotReadPosition,p=Depends(owner)):
        return call(lambda:runtime().messager_bots.unread.state(p.actor_user_id,bot,body.session_id,body.through_sequence))

    @router.post('/bots/{bot}/turns',status_code=202)
    async def turn(bot:str,body:MobileTurn,request:Request,p=Depends(owner)):
        call(lambda:session(p,bot,body.session_id))
        if runtime().messager_bots.definition(p.actor_user_id,bot)['execution_mode']=='flash':
            from ai2apps.messager.flash_conversation import submit
            try:return await submit(runtime(),p,bot,body)
            except PermissionError as exc:raise HTTPException(404,'Bot conversation unavailable') from exc
            except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        def action():
            session(p,bot,body.session_id)
            model='fixed-workflow-no-model' if runtime().messager_bots.definition(p.actor_user_id,bot)['execution_mode']=='flash' else model_settings(runtime(),p.actor_user_id,bot)['effective_model']
            if not model:raise ValueError('请在 Bot Profile 中配置对话模型 / Configure a conversation model in Bot Profile')
            return {'run_id':runtime().messager_dialogue.submit(p,bot,body.session_id,body.request_id,body.text,model,body.attachments,body.task_session_id,body.language,client_timezone=request.headers.get('X-AI2Apps-Timezone'))}
        return call(action)

    @router.post('/bots/{bot}/conversation-trim/review')
    def trim_review(bot:str,body:BotTrimReview,p=Depends(owner)):
        def run():
            session(p,bot,body.session_id)
            return runtime().messager_bots.history.conversation_trim().review(p.actor_user_id,bot,body.session_id,body.message_id)
        return call(run)

    @router.post('/bots/{bot}/conversation-trim/apply')
    def trim_apply(bot:str,body:BotTrimApply,p=Depends(owner)):
        def run():
            session(p,bot,body.session_id)
            return runtime().messager_bots.history.conversation_trim().apply(p.actor_user_id,bot,body.session_id,body.message_id,body.review_hash)
        return call(run)

    @router.post('/bots/{bot}/poke',status_code=202)
    async def poke(bot:str,body:MobilePoke,request:Request,p=Depends(owner)):
        def action():
            session(p,bot,body.session_id)
            model=model_settings(runtime(),p.actor_user_id,bot)['effective_model']
            if not model:raise ValueError('Configure a conversation model in Bot Profile')
            return {'run_id':runtime().messager_dialogue.submit(p,bot,body.session_id,body.request_id,'👋 Poke',model,[],language=body.language,poke=True,client_timezone=request.headers.get('X-AI2Apps-Timezone'))}
        return call(action)

    @router.get('/bots/{bot}/statistics')
    def bot_statistics(bot:str,period:str='all',timezone_name:str='UTC',task_session_id:str|None=None,todo_task_id:str|None=None,p=Depends(owner)):
        from ai2apps.messager.statistics import statistics
        return call(lambda:statistics(runtime(),p.actor_user_id,bot,period=period,timezone_name=timezone_name,task_session_id=task_session_id,todo_task_id=todo_task_id))

    @router.get('/bot-groups')
    def groups(p=Depends(owner)):
        return {'items':runtime().messager_bots.groups.list(p.actor_user_id)}

    @router.put('/bot-groups-order')
    def order_groups(body:BotGroupOrder,p=Depends(owner)):
        call(lambda:runtime().messager_bots.groups.reorder(p.actor_user_id,body.ids))
        return {'items':runtime().messager_bots.groups.list(p.actor_user_id)}

    @router.post('/bot-groups')
    def new_group(body:BotGroupCreate,p=Depends(owner)):
        call(lambda:runtime().messager_bots.groups.create(p.actor_user_id,body.name))
        return {'items':runtime().messager_bots.groups.list(p.actor_user_id)}

    @router.patch('/bot-groups/{group}')
    def collapse_group(group:str,body:BotGroupUpdate,p=Depends(owner)):
        call(lambda:runtime().messager_bots.groups.update(p.actor_user_id,group,body.revision,collapsed=body.collapsed,name=body.name))
        return {'items':runtime().messager_bots.groups.list(p.actor_user_id)}

    @router.delete('/bot-groups/{group}')
    def remove_group(group:str,body:BotGroupUpdate,p=Depends(owner)):
        call(lambda:runtime().messager_bots.groups.update(p.actor_user_id,group,body.revision,delete=True))
        return {'items':runtime().messager_bots.groups.list(p.actor_user_id)}

    @router.put('/bots-order')
    def order(body:BotOrder,p=Depends(owner)):
        call(lambda:runtime().messager_bots.set_order(p.actor_user_id,body.ids,body.move.model_dump() if body.move else None))
        return {'items':runtime().messager_bots.list(p.actor_user_id)}

    @router.post('/bots/{bot}/jobs/{job}/cancel')
    async def cancel(bot:str,job:str,p=Depends(owner)):
        try:return await runtime().messager_dialogue.request_cancel(p.actor_user_id,bot,job)
        except (ValueError,PermissionError) as exc:raise HTTPException(409,str(exc)) from exc

    @router.get('/notices')
    def notices(p=Depends(owner)):
        return call(lambda:runtime().messager_bot_notifications.inbox(p.actor_user_id))

    @router.post('/notices/{ref}/read')
    def read_notice(ref:str,p=Depends(owner)):
        return call(lambda:runtime().messager_bot_notifications.read(p.actor_user_id,ref))

    @router.post('/bots/{bot}/attachments',status_code=201)
    async def upload(bot:str,session_id:str,file:UploadFile=File(...),p=Depends(owner)):
        from ai2apps.api.documents import store_uploaded_reference,_attachment
        call(lambda:session(p,bot,session_id))
        try:return _attachment(await store_uploaded_reference(runtime(),session_id,file))
        finally:await file.close()

    @router.get('/bots/{bot}/avatar')
    def avatar(bot:str,p=Depends(owner)):
        # Avatar lookup is scoped to the selected Bot, never a client Gallery path.
        def action():
            runtime().messager_bots.scope(p.actor_user_id,{'bot_id':bot})
            current=next((b['avatar'] for b in runtime().messager_bots.list(p.actor_user_id) if b['id']==bot),{})
            if current.get('kind')!='image':raise PermissionError('No uploaded avatar')
            from ai2apps.gallery import GalleryRepository
            gallery=GalleryRepository(runtime().database,runtime().config.paths.artifacts_path/'gallery',runtime().events)
            asset,path=gallery.asset_path(p.actor_user_id,current['asset_id'])
            return FileResponse(path,media_type=asset['media_type'],headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'})
        return call(action)

    @router.get('/bots/{bot}/files/{sid}/{kind}/{ref}')
    async def content(bot:str,sid:str,kind:str,ref:str,preview:bool=False,p=Depends(owner)):
        def action():
            session(p,bot,sid)
            if kind=='attachments':
                item=runtime().documents.get(sid,ref)
                path=runtime().documents.source_path(sid,ref);name=item.filename
            elif kind=='artifacts':
                item=runtime().workspace.get_artifact(sid,ref)
                path=runtime().workspace.artifact_path(item);name=item.name
            else:raise PermissionError('Unknown file type')
            media=item.media_type
            if preview:return (path,media)
            headers={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff'}
            if media in ('text/html','image/svg+xml','application/xhtml+xml'):
                headers['Content-Security-Policy']="default-src 'none'; sandbox"
            return FileResponse(path,filename=name,media_type=media,headers=headers)
        result=call(action)
        if preview:
            from ai2apps.web.mobile_image_preview import RASTER,preview_file,response
            path,media=result
            if media not in RASTER:raise HTTPException(422,'Mobile preview requires a raster image')
            return response(await preview_file(path))
        return result
    return router
