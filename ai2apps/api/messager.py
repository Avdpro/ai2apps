"""Principal-isolated Local Messager history APIs."""

from __future__ import annotations
from ai2apps.messager.flash_plans import CompileRequest, ActivateRequest

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field,ConfigDict
from typing import Literal
from fastapi.responses import JSONResponse

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.core import RepositoryError
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.identity import RequestPrincipal
from ai2apps.messager import MessagerRepository
from ai2apps.messager.peer_service import MessagerPeerError
from ai2apps.peer.broker import PeerBrokerError
from ai2apps.messager.notifications import NotificationPolicy
from ai2apps.messager.creation import BotCreateDraft
from ai2apps.skills.library import principal_owner
from ai2apps.http_security import enforce_same_origin_cookie_request


class BotSkillSetting(BaseModel):
    enabled: bool


def _message_payload(row: dict) -> dict:
    return {
        "id": row["id"],
        "peerUserId": row["peer_user_id"],
        "direction": row["direction"],
        "transport": row["transport"],
        "status": row["status"],
        "body": row["body"],
        "clientMessageId": row["client_message_id"],
        "remoteMessageId": row["remote_message_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "attachment": (
            None
            if row["attachment_id"] is None
            else {
                "id": row["attachment_id"],
                "mediaType": row["attachment_media_type"],
                "byteSize": row["attachment_byte_size"],
                "width": row["attachment_width"],
                "height": row["attachment_height"],
                "contentPath": row["attachment_content_path"],
            }
        ),
    }


class BotGroupMove(BaseModel):
    bot_id: str
    group_id: str | None = None


class BotTrimReview(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id: str = Field(min_length=1,max_length=100)
    message_id: str = Field(min_length=1,max_length=100)


class BotTrimApply(BotTrimReview):
    review_hash: str = Field(min_length=64,max_length=64)


class BotPoke(BaseModel):
    session_id: str = Field(min_length=1,max_length=100)
    request_id: str = Field(min_length=1,max_length=100)
    model: str = Field(min_length=1,max_length=200)
    language: str = Field(default='zh',max_length=20)


class BotGroupOrder(BaseModel):
    ids: list[str] = Field(max_length=5000)


class BotGroupCreate(BaseModel):
    name: str = Field(min_length=1,max_length=64)


class BotGroupUpdate(BaseModel):
    revision: int = Field(ge=1)
    collapsed: bool | None = None
    name: str | None = Field(default=None,min_length=1,max_length=64)


class BotOrder(BaseModel):
    ids: list[str] = Field(max_length=5000)
    move: BotGroupMove | None = None


class BotReadPosition(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    session_id:str=Field(min_length=1,max_length=256)
    through_sequence:int=Field(ge=0)


class BotDialogueTurn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    session_id:str=Field(min_length=1,max_length=256)
    request_id:str=Field(min_length=8,max_length=128)
    text:str=Field(min_length=1,max_length=16000)
    model:str=Field(min_length=1,max_length=300)
    attachments:list[str]=Field(default_factory=list,max_length=8)
    task_session_id:str|None=Field(default=None,max_length=128)
    language:str=Field(default='zh',max_length=20)


class BotConversationModel(BaseModel):
    model_config=ConfigDict(extra='forbid')
    model_id:str=Field(min_length=1,max_length=300)
    revision:int=Field(ge=0)
    reasoning_effort:str|None=Field(default=None,max_length=16)


class CreateBot(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    duty: str = Field(min_length=1, max_length=600)


class BotVoiceUsed(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=0)


class BotVoiceSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['default','model','profile'] = 'default'
    model_id: str | None = Field(default=None,max_length=255)
    voice: str | None = Field(default=None,max_length=255)
    profile_id: str | None = Field(default=None,max_length=255)
    revision: int = Field(ge=0)


class BotRealtimeSettings(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    stt_model_id: str|None=Field(default=None,min_length=1,max_length=255)
    tts_model_id: str|None=Field(default=None,min_length=1,max_length=255)
    voice: str|None=Field(default=None,max_length=255)
    profile_id: str|None=Field(default=None,max_length=255)
    revision: int=Field(ge=0)


class BotRealtimeControl(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    controller: str=Field(min_length=16,max_length=100)


class BotRealtimeStart(BotRealtimeControl):
    session_id: str=Field(min_length=1,max_length=100)
    revision: int=Field(ge=1)
    model: str=Field(min_length=1,max_length=255)
    language: str=Field(default='zh',min_length=1,max_length=32)


class BotRealtimeInput(BotRealtimeControl):
    turn_id: str=Field(min_length=1,max_length=64,pattern=r'^[A-Za-z0-9_-]+$')
    text: str=Field(min_length=1,max_length=16000)
    attachments: list[str]=Field(default_factory=list,max_length=8)


class BotMemoryNote(BaseModel):
    model_config=ConfigDict(extra='forbid')
    text: str=Field(min_length=1,max_length=2000)
    revision: int|None=Field(default=None,ge=1)
    deleted: bool=False


class BotRestore(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)


class BotNotificationSettings(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0)
    policy:NotificationPolicy


class BotUseChoice(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    enabled:bool=Field(strict=True)


class BotExposureChoice(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=1)
    mode:Literal['public','private']


class BotTaskDecision(BaseModel):
    model_config=ConfigDict(extra='forbid')
    review_hash: str = Field(pattern=r'^[0-9a-f]{64}$')


class BotPlanAccessDecision(BotTaskDecision):
    access_mode:Literal['fixed','auto','inherit']|None=None
    access_apps:list[str]|None=Field(default=None,max_length=32)
    access_bots:list[str]|None=Field(default=None,max_length=32)


class BotCleanupDecision(BotTaskDecision):
    clear_memory: bool = Field(default=False, strict=True)
    revoke_access: bool = Field(default=False, strict=True)
    delete_tasks: bool = Field(default=False, strict=True)


class BotTaskResponse(BotTaskDecision):
    response_id: str = Field(min_length=1,max_length=128)
    response: dict


class BotAccessChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str = Field(min_length=1, max_length=100)
    foreground: bool
    background: bool


class BotAccessUpdate(BaseModel):
    review_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    grants: list[BotAccessChoice] = Field(max_length=30)


class BotAppChoice(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    app_id: str = Field(min_length=1,max_length=255)
    enabled: bool

class BotAppUpdate(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    review_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    apps: list[BotAppChoice] = Field(max_length=300)

class BotApprovalRuleUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    mode: Literal['manual', 'ai', 'always']
    revision: int = Field(ge=0)

class BotAppAllow(BaseModel):
    model_config=ConfigDict(extra='forbid')
    request_hash: str = Field(pattern=r'^[0-9a-f]{64}$')
    existing_access_only: bool = Field(default=False, strict=True)

class BotTaskAssignment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    task_id: str = Field(min_length=1, max_length=100)


class BotAvatar(BaseModel):
    model_config=ConfigDict(extra='forbid')
    kind:Literal['preset','image']='preset'
    preset:Literal['spark','robot','orbit','flower','sun','moon','cat','owl','leaf','rocket','compass','heart']='spark'
    color:str=Field(default='#6366f1',pattern=r'^#[0-9a-fA-F]{6}$')
    asset_id:str|None=Field(default=None,max_length=100)


def create_messager_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/messager", tags=["platform-messager"])
    principal_dependency = Depends(principal_provider)

    def bots():
        directory = getattr(runtime_provider(), "messager_bots", None)
        if directory is None:
            raise HTTPException(404, "Bots unavailable")
        return directory

    bot_access = Depends(require_app_capability(principal_provider, "app.use"))

    @router.get("/bots", dependencies=[bot_access])
    def list_bots(language: Literal['en','zh']='en',principal: RequestPrincipal = principal_dependency):
        from ai2apps.messager.creation import ensure_research
        default=bots().ensure_default(principal.actor_user_id)
        task_call(lambda:ensure_research(runtime_provider(),principal.actor_user_id,language))
        return {"items": [{**b,"is_default":b["id"]==default} for b in bots().list(principal.actor_user_id)]}

    @router.get('/bots/{bot_id}/unread',dependencies=[bot_access])
    def bot_unread(bot_id:str,session_id:str,principal:RequestPrincipal=principal_dependency):
        try:return bots().unread.state(principal.actor_user_id,bot_id,session_id)
        except PermissionError as exc:raise HTTPException(404,'Bot conversation unavailable') from exc

    @router.post('/bots/{bot_id}/read',dependencies=[bot_access])
    def read_bot(bot_id:str,body:BotReadPosition,principal:RequestPrincipal=principal_dependency):
        try:return bots().unread.state(principal.actor_user_id,bot_id,body.session_id,body.through_sequence)
        except PermissionError as exc:raise HTTPException(404,'Bot conversation unavailable') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    @router.get('/bot-creation/options',dependencies=[bot_access])
    def bot_creation_options(principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.creation import options
        return options(runtime_provider())

    @router.post('/flash-workflows/compile',dependencies=[bot_access])
    async def compile_flash(body:CompileRequest,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        from ai2apps.messager.flash_plans import compile_plan
        try:return await compile_plan(runtime_provider(),principal,body)
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    @router.post('/bots/{bot_id}/flash-workflow',dependencies=[bot_access])
    def activate_flash(bot_id:str,body:ActivateRequest,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        from ai2apps.messager.flash_plans import activate
        return task_call(lambda:activate(runtime_provider(),principal.actor_user_id,bot_id,body))

    @router.post('/bot-creation',status_code=201,dependencies=[bot_access])
    def create_configured_bot(body:BotCreateDraft,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.creation import create
        return task_call(lambda:create(runtime_provider(),principal.actor_user_id,body))

    @router.post("/bots", status_code=201, dependencies=[bot_access])
    def create_bot(body: CreateBot, principal: RequestPrincipal = principal_dependency):
        try:
            return bots().create(principal.actor_user_id, body.name, body.duty)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @router.put('/bots-order',dependencies=[bot_access])
    def save_bot_order(body:BotOrder,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        directory=bots()
        task_call(lambda:directory.set_order(principal.actor_user_id,body.ids,body.move.model_dump() if body.move else None))
        return {'items':directory.list(principal.actor_user_id)}

    @router.get('/bot-groups',dependencies=[bot_access])
    def bot_groups(principal:RequestPrincipal=principal_dependency):
        return {'items':bots().groups.list(principal.actor_user_id)}

    @router.get('/bots/{bot_id}/statistics',dependencies=[bot_access])
    def bot_statistics(bot_id:str,period:Literal['all','today','7d','30d']='all',timezone_name:str='UTC',task_session_id:str|None=None,todo_task_id:str|None=None,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.statistics import statistics
        return task_call(lambda:statistics(runtime_provider(),principal.actor_user_id,bot_id,period=period,timezone_name=timezone_name,task_session_id=task_session_id,todo_task_id=todo_task_id))

    @router.put('/bot-groups-order',dependencies=[bot_access])
    def order_groups(body:BotGroupOrder,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        task_call(lambda:bots().groups.reorder(principal.actor_user_id,body.ids))
        return {'items':bots().groups.list(principal.actor_user_id)}

    @router.post('/bot-groups',dependencies=[bot_access])
    def create_group(body:BotGroupCreate,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        task_call(lambda:bots().groups.create(principal.actor_user_id,body.name))
        return {'items':bots().groups.list(principal.actor_user_id)}

    @router.patch('/bot-groups/{group_id}',dependencies=[bot_access])
    def update_group(group_id:str,body:BotGroupUpdate,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        task_call(lambda:bots().groups.update(principal.actor_user_id,group_id,body.revision,collapsed=body.collapsed,name=body.name))
        return {'items':bots().groups.list(principal.actor_user_id)}

    @router.delete('/bot-groups/{group_id}',dependencies=[bot_access])
    def delete_group(group_id:str,body:BotGroupUpdate,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        task_call(lambda:bots().groups.update(principal.actor_user_id,group_id,body.revision,delete=True))
        return {'items':bots().groups.list(principal.actor_user_id)}

    @router.patch('/bots/{bot_id}',dependencies=[bot_access])
    def update_bot(bot_id:str,body:CreateBot,principal:RequestPrincipal=principal_dependency):
        try:return bots().update(principal.actor_user_id,bot_id,body.name,body.duty)
        except PermissionError as exc:raise HTTPException(404,'Bot unavailable') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc

    def skill_library(principal, bot_id):
        if bots().definition(principal.actor_user_id, bot_id)['execution_mode'] != 'agent':
            raise ValueError('Skills are available for conversational Bots')
        return runtime_provider().messager_skills.library

    @router.get('/bots/{bot_id}/skills',dependencies=[bot_access])
    def bot_skills(bot_id: str, principal: RequestPrincipal = principal_dependency):
        return task_call(lambda: {"items": skill_library(principal, bot_id).bot_items(
            principal_owner(principal), bot_id
        )})

    @router.put('/bots/{bot_id}/skills/{skill_id}',dependencies=[bot_access])
    def set_bot_skill(bot_id: str, skill_id: str, body: BotSkillSetting, request: Request,
                      principal: RequestPrincipal = principal_dependency):
        enforce_same_origin_cookie_request(request)
        def save():
            library = skill_library(principal, bot_id)
            owner = principal_owner(principal)
            try:
                library.set_bot_skill(owner, bot_id, skill_id, body.enabled)
            except LookupError as exc:
                raise HTTPException(404, 'Installed Skill unavailable') from exc
            return {"items": library.bot_items(owner, bot_id)}
        return task_call(save)

    @router.delete('/bots/{bot_id}/skills/{skill_id}',dependencies=[bot_access])
    def remove_bot_skill(bot_id: str, skill_id: str, request: Request,
                         principal: RequestPrincipal = principal_dependency):
        enforce_same_origin_cookie_request(request)
        def remove():
            library = skill_library(principal, bot_id)
            owner = principal_owner(principal)
            library.remove_bot_skill(owner, bot_id, skill_id)
            return {"items": library.bot_items(owner, bot_id)}
        return task_call(remove)

    @router.get('/bots/{bot_id}/conversation-model',dependencies=[bot_access])
    def conversation_model(bot_id:str,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.conversation_profile import settings
        return task_call(lambda:settings(runtime_provider(),principal.actor_user_id,bot_id))

    @router.put('/bots/{bot_id}/conversation-model',dependencies=[bot_access])
    def save_conversation_model(bot_id:str,body:BotConversationModel,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.conversation_profile import settings
        return task_call(lambda:settings(runtime_provider(),principal.actor_user_id,bot_id,expected_revision=body.revision,**body.model_dump(exclude_unset=True,exclude={'revision'})))

    @router.get('/bots/{bot_id}/voice',dependencies=[bot_access])
    def get_bot_voice(bot_id:str,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.voice import BotVoice
        try:return BotVoice(bots(),runtime_provider()).get(principal.actor_user_id,bot_id)
        except PermissionError as exc:raise HTTPException(404,'Bot unavailable') from exc

    @router.get('/bots/{bot_id}/voice/playback',dependencies=[bot_access])
    def bot_voice_playback(bot_id:str,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.voice import BotVoice
        try:return BotVoice(bots(),runtime_provider()).playback(principal.actor_user_id,bot_id)
        except PermissionError as exc:raise HTTPException(404,'Bot unavailable') from exc

    @router.post('/bots/{bot_id}/voice/used',dependencies=[bot_access])
    def bot_voice_used(bot_id:str,body:BotVoiceUsed,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.voice import BotVoice
        try:return BotVoice(bots(),runtime_provider()).used(principal.actor_user_id,bot_id,body.revision)
        except PermissionError as exc:raise HTTPException(404,'Bot unavailable') from exc
        except (ValueError,RepositoryError) as exc:raise HTTPException(409,'Voice settings unavailable') from exc

    @router.put('/bots/{bot_id}/voice',dependencies=[bot_access])
    def set_bot_voice(bot_id:str,body:BotVoiceSettings,principal:RequestPrincipal=principal_dependency):
        from ai2apps.messager.voice import BotVoice
        try:return BotVoice(bots(),runtime_provider()).save(principal.actor_user_id,bot_id,body.model_dump(exclude={'revision'}),body.revision)
        except PermissionError as exc:raise HTTPException(404,'Bot unavailable') from exc
        except RepositoryError as exc:raise HTTPException(404,'Voice character unavailable') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except RuntimeError as exc:raise HTTPException(409,str(exc)) from exc

    @router.get('/bots/{bot_id}/realtime/settings',dependencies=[bot_access])
    def realtime_settings(bot_id:str,principal:RequestPrincipal=principal_dependency):
        bots()
        return task_call(lambda:runtime_provider().messager_dialogue.realtime.get(principal.actor_user_id,bot_id))

    @router.put('/bots/{bot_id}/realtime/settings',dependencies=[bot_access])
    def save_realtime_settings(bot_id:str,body:BotRealtimeSettings,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        bots()
        return task_call(lambda:runtime_provider().messager_dialogue.realtime.save(principal.actor_user_id,bot_id,body.model_dump(exclude={'revision'}),body.revision))

    @router.post('/bots/{bot_id}/realtime/sessions',dependencies=[bot_access])
    def start_realtime(bot_id:str,body:BotRealtimeStart,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        bots()
        return task_call(lambda:runtime_provider().messager_dialogue.realtime.start(principal,bot_id,body.session_id,body.controller,body.revision,body.model,body.language,request.headers.get('X-AI2Apps-Timezone')))

    @router.post('/bots/{bot_id}/realtime/sessions/{voice_id}/touch',dependencies=[bot_access])
    def touch_realtime(bot_id:str,voice_id:str,body:BotRealtimeControl,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_dialogue.realtime.touch(principal,bot_id,voice_id,body.controller))

    @router.post('/bots/{bot_id}/realtime/sessions/{voice_id}/close',dependencies=[bot_access])
    def close_realtime(bot_id:str,voice_id:str,body:BotRealtimeControl,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_dialogue.realtime.close(principal,bot_id,voice_id,body.controller))

    @router.post('/bots/{bot_id}/realtime/sessions/{voice_id}/inputs',dependencies=[bot_access])
    def input_realtime(bot_id:str,voice_id:str,body:BotRealtimeInput,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_dialogue.realtime.submit(principal,bot_id,voice_id,body.controller,body.turn_id,body.text,body.attachments))

    @router.put('/bots/{bot_id}/avatar',dependencies=[bot_access])
    def set_bot_avatar(bot_id:str,body:BotAvatar,principal:RequestPrincipal=principal_dependency):
        try:
            bots().scope(principal.actor_user_id,{'bot_id':bot_id})
            if body.kind=='image':
                from ai2apps.gallery import GalleryRepository
                r=runtime_provider()
                asset=GalleryRepository(r.database,r.config.paths.artifacts_path/'gallery').get_asset(principal.actor_user_id,body.asset_id or '')
                if asset['media_type'] not in ('image/png','image/jpeg','image/webp') or asset.get('size_bytes',0)>5*1024*1024:raise ValueError('Choose a PNG, JPEG or WebP image up to 5 MiB')
            elif body.asset_id:raise ValueError('Preset avatars cannot reference an asset')
            return bots().set_avatar(principal.actor_user_id,bot_id,body.model_dump())
        except PermissionError as exc:raise HTTPException(404,'Bot unavailable') from exc
        except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        except RepositoryError as exc:raise HTTPException(404,'Avatar image unavailable') from exc

    def task_execution():
        bots()
        value=getattr(runtime_provider(),'messager_task_execution',None)
        if value is None:raise HTTPException(503,'Bot tasks unavailable')
        return value

    def task_host(request,principal):
        if principal.client_scope!='desktop' or request.headers.get('origin')!=str(request.base_url).rstrip('/'):
            raise HTTPException(403,'Task decisions require the same-origin desktop host')

    def task_call(call):
        try:return call()
        except (PermissionError,KeyError) as exc:raise HTTPException(404,'Bot task unavailable') from exc
        except (ValueError,RepositoryError) as exc:raise HTTPException(409,str(exc)) from exc

    def notifications():
        bots()
        value=getattr(runtime_provider(),'messager_bot_notifications',None)
        if value is None:raise HTTPException(503,'Bot notifications unavailable')
        return value

    @router.get('/notices',dependencies=[bot_access])
    def bot_notices(principal:RequestPrincipal=principal_dependency):
        return task_call(lambda:notifications().inbox(principal.actor_user_id))

    @router.post('/notices/read-all',dependencies=[bot_access])
    def bot_notices_read_all(request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:notifications().read_all(principal.actor_user_id))

    @router.post('/notices/{notice_id}/open',dependencies=[bot_access])
    def open_bot_notice(notice_id:str,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:notifications().read(principal.actor_user_id,notice_id))

    @router.get('/bots/{bot_id}/notification-policy',dependencies=[bot_access])
    def bot_notification_policy(bot_id:str,principal:RequestPrincipal=principal_dependency):
        return task_call(lambda:notifications().policy(principal.actor_user_id,bot_id))

    @router.put('/bots/{bot_id}/notification-policy',dependencies=[bot_access])
    def save_bot_notification_policy(bot_id:str,body:BotNotificationSettings,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:notifications().save_policy(principal.actor_user_id,bot_id,body.revision,body.policy.model_dump()))

    @router.get('/bots/{bot_id}/memories',dependencies=[bot_access])
    def bot_memories(bot_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        return task_call(lambda:bots().memory.list(principal.actor_user_id,bot_id))

    @router.post('/bots/{bot_id}/memories',dependencies=[bot_access])
    def add_bot_memory(bot_id:str,body:BotMemoryNote,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        if body.revision or body.deleted:raise HTTPException(422,'New memories require text only')
        with runtime_provider().app_chat.lock:
            return task_call(lambda:bots().memory.save(principal.actor_user_id,bot_id,body.text))

    @router.put('/bots/{bot_id}/memories/{memory_id}',dependencies=[bot_access])
    def edit_bot_memory(bot_id:str,memory_id:str,body:BotMemoryNote,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        with runtime_provider().app_chat.lock:
            return task_call(lambda:bots().memory.save(principal.actor_user_id,bot_id,body.text,ref=memory_id,revision=body.revision,deleted=body.deleted))

    @router.get('/bots/{bot_id}/cleanup',dependencies=[bot_access])
    def bot_cleanup_review(bot_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        return task_call(lambda:runtime_provider().messager_bot_lifecycle.review(principal.actor_user_id,bot_id))

    @router.post('/bots/{bot_id}/cleanup/{action}',dependencies=[bot_access])
    async def bot_cleanup(bot_id:str,action:Literal['clear_memory','clear_dialogue','restore_dialogue','archive','reset'],body:BotCleanupDecision,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        try:return await runtime_provider().messager_bot_lifecycle.apply(principal.actor_user_id,bot_id,action,body.review_hash,clear_memory=body.clear_memory,revoke_access=body.revoke_access,delete_tasks=body.delete_tasks)
        except PermissionError as exc:raise HTTPException(404,'Bot unavailable') from exc
        except ValueError as exc:raise HTTPException(409,str(exc)) from exc

    @router.get('/bots-archive',dependencies=[bot_access])
    def bot_archive(principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        return runtime_provider().messager_bot_lifecycle.archived(principal.actor_user_id)

    @router.post('/bots-archive/{bot_id}/restore',dependencies=[bot_access])
    def restore_bot(bot_id:str,body:BotRestore,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_lifecycle.restore(principal.actor_user_id,bot_id,body.revision))

    @router.post('/bots/{bot_id}/dialogue/turns',dependencies=[bot_access],status_code=202)
    async def bot_dialogue_turn(bot_id:str,body:BotDialogueTurn,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        runtime=runtime_provider()
        if runtime.messager_bots.definition(principal.actor_user_id,bot_id)['execution_mode']=='flash':
            from ai2apps.messager.flash_conversation import submit
            try:return await submit(runtime,principal,bot_id,body)
            except PermissionError as exc:raise HTTPException(404,'Bot conversation unavailable') from exc
            except ValueError as exc:raise HTTPException(422,str(exc)) from exc
        return task_call(lambda:{'run_id':runtime.messager_dialogue.submit(principal,bot_id,body.session_id,body.request_id,body.text,body.model,body.attachments,body.task_session_id,body.language,client_timezone=request.headers.get('X-AI2Apps-Timezone'))})

    @router.post('/bots/{bot_id}/conversation-trim/review',dependencies=[bot_access])
    def review_bot_trim(bot_id:str,body:BotTrimReview,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bots.history.conversation_trim().review(principal.actor_user_id,bot_id,body.session_id,body.message_id))

    @router.post('/bots/{bot_id}/conversation-trim/apply',dependencies=[bot_access])
    def apply_bot_trim(bot_id:str,body:BotTrimApply,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bots.history.conversation_trim().apply(principal.actor_user_id,bot_id,body.session_id,body.message_id,body.review_hash))

    @router.post('/bots/{bot_id}/poke',dependencies=[bot_access],status_code=202)
    async def poke_bot(bot_id:str,body:BotPoke,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:{'run_id':runtime_provider().messager_dialogue.submit(principal,bot_id,body.session_id,body.request_id,'👋 Poke',body.model,[],language=body.language,poke=True,client_timezone=request.headers.get('X-AI2Apps-Timezone'))})

    @router.post('/bots/{bot_id}/dialogue/jobs/{job_id}/cancel',dependencies=[bot_access])
    async def cancel_bot_dialogue(bot_id:str,job_id:str,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        try:return await runtime_provider().messager_dialogue.request_cancel(principal.actor_user_id,bot_id,job_id)
        except (ValueError,PermissionError) as error:raise HTTPException(409,str(error))

    @router.get('/bots/{bot_id}/dialogue/state',dependencies=[bot_access])
    def bot_dialogue_state(bot_id:str,session_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        return task_call(lambda:runtime_provider().messager_dialogue.snapshot(principal,bot_id,session_id))

    @router.get('/bots/{bot_id}/task-sessions',dependencies=[bot_access])
    def list_bot_task_sessions(bot_id:str,session_id:str,archived:bool=False,offset:int=0,query:str|None=None,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        def listing():
            service=runtime_provider().messager_dialogue
            binding=service.runtime.app_chat.access(principal,session_id)
            if binding['registration']!='ai2apps.messager.bots' or binding['scope']!={'bot_id':bot_id}:raise PermissionError('Open the main Bot conversation')
            if query is not None:
                return {'items':service.sessions.search_references(binding['owner'],bot_id,session_id,query),'has_more':False}
            items=service.sessions.recent(binding['owner'],bot_id,session_id,archived=archived,limit=21,offset=offset)
            return {'items':items[:20],'has_more':len(items)>20}
        return task_call(listing)

    @router.get('/bots/{bot_id}/task-sessions/{ref}',dependencies=[bot_access])
    def bot_task_session(bot_id:str,ref:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        def details():
            service=runtime_provider().messager_dialogue;value=service.sessions.get(principal.actor_user_id,bot_id,ref)
            from ai2apps.messager.statistics import statistics
            return {**value, **service.sessions.project(value, include_runs=True), 'summary':value['summary'],'statistics':statistics(runtime_provider(),principal.actor_user_id,bot_id,task_session_id=ref)}
        return task_call(details)

    @router.post('/bots/{bot_id}/task-sessions/{ref}/{action}',dependencies=[bot_access])
    def manage_bot_task_session(bot_id:str,ref:str,action:Literal['pin','unpin','archive','restore'],request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_dialogue.sessions.manage(principal.actor_user_id,bot_id,ref,action))

    @router.post('/bots/{bot_id}/plan-changes/{ref}/{decision}',dependencies=[bot_access])
    def decide_bot_plan_change(bot_id:str,ref:str,decision:Literal['approve','reject'],body:BotPlanAccessDecision,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_dialogue.plans.decide(principal.actor_user_id,bot_id,ref,body.review_hash,decision,body.access_mode,body.access_apps,body.access_bots))

    @router.get('/bots/{bot_id}/work',dependencies=[bot_access])
    def bot_work(bot_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        return task_call(lambda:{**task_execution().work(principal.actor_user_id,bot_id),
            'configurations':runtime_provider().messager_bot_configuration.pending(principal.actor_user_id,bot_id),'plan_changes':runtime_provider().messager_dialogue.plans.pending(principal.actor_user_id,bot_id),
            'communications':runtime_provider().messager_bot_communication.work(principal.actor_user_id,bot_id),
            'collaboration_plans':runtime_provider().messager_bot_collaboration.work(principal.actor_user_id,bot_id),
            'delegations':runtime_provider().messager_bot_delegation.work(principal.actor_user_id,bot_id)})

    @router.post('/bots/{bot_id}/collaboration-plans/{ref}/decisions/{decision}',dependencies=[bot_access])
    def decide_collaboration_plan(bot_id:str,ref:str,decision:Literal['approve','reject'],body:BotTaskDecision,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_collaboration.decide(principal.actor_user_id,bot_id,ref,body.review_hash,decision))

    @router.post('/bots/{bot_id}/collaboration-plans/{ref}/pause',dependencies=[bot_access])
    def pause_collaboration_plan(bot_id:str,ref:str,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_collaboration.pause(principal.actor_user_id,bot_id,ref))

    @router.post('/bots/{bot_id}/delegations/{ref}/decisions/{decision}',dependencies=[bot_access])
    async def decide_bot_delegation(bot_id:str,ref:str,decision:Literal['approve','reject'],body:BotTaskDecision,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_delegation.decide(principal.actor_user_id,bot_id,ref,body.review_hash,decision))

    @router.post('/bots/{bot_id}/delegations/{ref}/cancel',dependencies=[bot_access])
    async def cancel_bot_delegation(bot_id:str,ref:str,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        try:return await runtime_provider().messager_bot_delegation.cancel(principal.actor_user_id,bot_id,ref)
        except PermissionError as exc:raise HTTPException(404,'Delegation unavailable') from exc

    @router.get('/bots/{bot_id}/bot-access',dependencies=[bot_access])
    def bot_use_catalog(bot_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        return task_call(lambda:runtime_provider().messager_bot_access.catalog(principal.actor_user_id,bot_id))

    @router.put('/bots/{bot_id}/bot-access/exposure',dependencies=[bot_access])
    def bot_exposure(bot_id:str,body:BotExposureChoice,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        service=runtime_provider().messager_bot_access
        task_call(lambda:service.set_mode(principal.actor_user_id,bot_id,body.mode,body.revision))
        return task_call(lambda:service.catalog(principal.actor_user_id,bot_id))

    @router.put('/bots/{bot_id}/bot-access/targets/{target_id}',dependencies=[bot_access])
    def bot_use_target(bot_id:str,target_id:str,body:BotUseChoice,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        service=runtime_provider().messager_bot_access
        task_call(lambda:service.set_link(principal.actor_user_id,bot_id,target_id,body.enabled,body.revision))
        return task_call(lambda:service.catalog(principal.actor_user_id,bot_id))

    @router.delete('/bots/{bot_id}/bot-access/targets/{target_id}',dependencies=[bot_access])
    def remove_bot_use_target(bot_id:str,target_id:str,body:BotUseChoice,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        service=runtime_provider().messager_bot_access
        task_call(lambda:service.remove_link(principal.actor_user_id,bot_id,target_id,body.revision))
        return task_call(lambda:service.catalog(principal.actor_user_id,bot_id))

    @router.put('/bots/{bot_id}/bot-access/callers/{source_id}',dependencies=[bot_access])
    def bot_use_caller(bot_id:str,source_id:str,body:BotUseChoice,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        service=runtime_provider().messager_bot_access
        task_call(lambda:service.set_link(principal.actor_user_id,source_id,bot_id,body.enabled,body.revision))
        return task_call(lambda:service.catalog(principal.actor_user_id,bot_id))

    @router.get('/bots/{bot_id}/communication/targets',dependencies=[bot_access])
    def bot_communication_targets(bot_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Open the Local desktop host')
        return task_call(lambda:{'items':runtime_provider().messager_bot_communication.targets(principal.actor_user_id,bot_id)})

    @router.post('/bots/{bot_id}/communication/{ref}/decisions/{decision}',dependencies=[bot_access])
    def bot_communication_decision(bot_id:str,ref:str,decision:Literal['approve','reject'],body:BotTaskDecision,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_communication.decide(principal.actor_user_id,bot_id,ref,body.review_hash,decision))

    @router.post('/bots/{bot_id}/communication/{ref}/cancel',dependencies=[bot_access])
    async def bot_communication_cancel(bot_id:str,ref:str,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        try:return await runtime_provider().messager_bot_communication.cancel(principal.actor_user_id,bot_id,ref)
        except PermissionError as exc:raise HTTPException(404,'Consultation unavailable') from exc

    @router.post('/bots/{bot_id}/configurations/{proposal_id}/{decision}',dependencies=[bot_access])
    async def decide_bot_configuration(bot_id:str,proposal_id:str,decision:Literal['approve','reject'],body:BotTaskDecision,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_configuration.decide(principal.actor_user_id,bot_id,proposal_id,body.review_hash,decision))

    @router.post('/bots/{bot_id}/task-access/{proposal_id}/revoke',dependencies=[bot_access])
    def revoke_bot_task_access(bot_id:str,proposal_id:str,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:task_execution().access.revoke(principal.actor_user_id,bot_id,proposal_id))

    @router.post('/bots/{bot_id}/task-proposals/{proposal_id}/{decision}',dependencies=[bot_access])
    async def decide_bot_task(bot_id:str,proposal_id:str,decision:Literal['approve','reject'],body:BotPlanAccessDecision,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:task_execution().decide(principal.actor_user_id,bot_id,proposal_id,body.review_hash,decision,body.access_mode,body.access_apps,body.access_bots))

    @router.post('/bots/{bot_id}/task-runs/{todo_run_id}/interactions/{interaction_id}/respond',dependencies=[bot_access])
    async def respond_bot_task(bot_id:str,todo_run_id:str,interaction_id:str,body:BotTaskResponse,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:task_execution().respond(principal.actor_user_id,bot_id,todo_run_id,interaction_id,body.review_hash,body.response_id,body.response))

    @router.post('/bots/{bot_id}/task-runs/{todo_run_id}/cancel',dependencies=[bot_access])
    async def cancel_bot_task(bot_id:str,todo_run_id:str,request:Request,principal:RequestPrincipal=principal_dependency):
        import json
        task_host(request,principal)
        service=task_execution()
        task_call(lambda:service.directory.scope(principal.actor_user_id,{'bot_id':bot_id}))
        with service.todo().store.connect() as db:
            row=db.execute('SELECT data FROM runs WHERE owner=? AND id=?',(principal.actor_user_id,todo_run_id)).fetchone()
        binding=json.loads(row['data']).get('execution_binding') if row else None
        from ai2apps.messager.tasks import ADAPTER
        if not binding or binding['registration']!=ADAPTER or binding['binding']['bot_id']!=bot_id:raise HTTPException(404,'Bot task unavailable')
        try:await service.todo().cancel(principal.actor_user_id,todo_run_id)
        except (ValueError,KeyError) as exc:raise HTTPException(409,str(exc)) from exc
        return {'status':'cancel_requested'}

    @router.get('/bots/{bot_id}/app-access',dependencies=[bot_access])
    def bot_app_access(bot_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Use the desktop host')
        return task_call(lambda:runtime_provider().messager_bot_app_access.catalog(principal.actor_user_id,bot_id))

    @router.put('/bots/{bot_id}/app-access/approval-rule', dependencies=[bot_access])
    def update_bot_approval_rule(bot_id: str, body: BotApprovalRuleUpdate, request: Request,
                                 principal: RequestPrincipal = principal_dependency):
        task_host(request, principal)
        return task_call(lambda: runtime_provider().messager_bot_app_access.set_approval_rule(
            principal.actor_user_id, bot_id, body.mode, body.revision))

    @router.put('/bots/{bot_id}/app-access',dependencies=[bot_access])
    def update_bot_app_access(bot_id:str,body:BotAppUpdate,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_app_access.save(principal.actor_user_id,bot_id,body.revision,body.review_hash,[a.model_dump() for a in body.apps]))

    @router.get('/bots/{bot_id}/app-access/requests/{run_id}/{interaction_id}',dependencies=[bot_access])
    def bot_app_request(bot_id:str,run_id:str,interaction_id:str,principal:RequestPrincipal=principal_dependency):
        if principal.client_scope!='desktop':raise HTTPException(403,'Use the desktop host')
        return task_call(lambda:runtime_provider().messager_bot_app_access.request(principal.actor_user_id,bot_id,run_id,interaction_id))

    @router.post('/bots/{bot_id}/app-access/requests/{run_id}/{interaction_id}',dependencies=[bot_access])
    def allow_bot_app(bot_id:str,run_id:str,interaction_id:str,body:BotAppAllow,request:Request,principal:RequestPrincipal=principal_dependency):
        task_host(request,principal)
        return task_call(lambda:runtime_provider().messager_bot_app_access.allow(principal.actor_user_id,bot_id,run_id,interaction_id,body.request_hash,existing_access_only=body.existing_access_only))

    @router.get('/bots/{bot_id}/access', dependencies=[bot_access])
    def bot_access_settings(bot_id: str, principal: RequestPrincipal = principal_dependency):
        if principal.client_scope != 'desktop':raise HTTPException(403, 'Review Bot access in the Local desktop host')
        bots()
        try:
            return runtime_provider().messager_bot_permissions.catalog(principal.actor_user_id, bot_id)
        except PermissionError as exc:
            raise HTTPException(404, 'Bot unavailable') from exc

    @router.put('/bots/{bot_id}/access', dependencies=[bot_access])
    def save_bot_access(bot_id: str, body: BotAccessUpdate, request: Request, principal: RequestPrincipal = principal_dependency):
        if principal.client_scope != 'desktop' or request.headers.get('origin') != str(request.base_url).rstrip('/'):
            raise HTTPException(403, 'Bot access decisions require the same-origin desktop host')
        bots()
        try:
            return runtime_provider().messager_bot_permissions.save(principal.actor_user_id, bot_id,
                body.revision, [g.model_dump() for g in body.grants], review_hash=body.review_hash)
        except PermissionError as exc:
            raise HTTPException(404, 'Bot unavailable') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    def task_links():
        bots()
        links = getattr(runtime_provider(), 'messager_bot_tasks', None)
        if links is None or not links.available:
            raise HTTPException(503, 'Todo tasks unavailable')
        return links

    def task_result(action):
        try:
            return action()
        except (PermissionError, KeyError) as exc:
            raise HTTPException(404, 'Bot or Todo task unavailable') from exc
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc

    @router.get('/bots/{bot_id}/tasks', dependencies=[bot_access])
    def bot_tasks(bot_id: str, principal: RequestPrincipal = principal_dependency):
        return task_result(lambda: task_links().list(principal.actor_user_id, bot_id))

    @router.get('/bots/{bot_id}/task-candidates', dependencies=[bot_access])
    def bot_task_candidates(bot_id: str, principal: RequestPrincipal = principal_dependency):
        return task_result(lambda: task_links().candidates(principal.actor_user_id, bot_id))

    @router.post('/bots/{bot_id}/tasks', dependencies=[bot_access])
    def assign_bot_task(bot_id: str, body: BotTaskAssignment, principal: RequestPrincipal = principal_dependency):
        return task_result(lambda: task_links().assign(principal.actor_user_id, bot_id, body.task_id))

    @router.delete('/bots/{bot_id}/tasks/{task_id}', dependencies=[bot_access])
    def remove_bot_task(bot_id: str, task_id: str, principal: RequestPrincipal = principal_dependency):
        return task_result(lambda: task_links().assign(principal.actor_user_id, bot_id, task_id, remove=True))

    def repository() -> MessagerRepository | JSONResponse:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        events = None if runtime is None else getattr(runtime, "events", None)
        if database is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Messager persistence is not ready.",
                retryable=True,
            )
        return MessagerRepository(database, events)

    @router.get("/conversations")
    def list_conversations(
        limit: int = Query(default=100, ge=1, le=100),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        items = selected.list_conversations(principal.actor_user_id, limit=limit)
        return {
            "items": [
                {
                    "id": row["id"],
                    "peerUserId": row["peer_user_id"],
                    "lastBody": row["last_body"],
                    "lastStatus": row["last_status"],
                    "createdAt": row["created_at"],
                    "updatedAt": row["updated_at"],
                }
                for row in items
            ]
        }

    @router.get("/conversations/{peer_user_id}/messages")
    def list_messages(
        peer_user_id: str,
        limit: int = Query(default=200, ge=1, le=500),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = repository()
        if isinstance(selected, JSONResponse):
            return selected
        return {
            "items": [
                _message_payload(row)
                for row in selected.list_messages(
                    principal.actor_user_id,
                    peer_user_id,
                    limit=limit,
                )
            ]
        }

    @router.post("/send")
    async def send_local_first(
        payload: dict,
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        peer_v1 = None if runtime is None else getattr(runtime, "messager_peer", None)
        peer_v2 = None if runtime is None else getattr(runtime, "messager_peer_v2", None)
        if peer_v1 is None:
            return platform_error_response(
                status_code=503,
                code="messager_not_ready",
                message="Messager peer transport is not ready.",
                retryable=True,
            )
        required = {"recipientUserId", "clientMessageId", "body"}
        if set(payload) != required or not all(
            isinstance(payload.get(name), str) and payload[name]
            for name in required
        ) or len(payload["body"]) > 4000:
            return platform_error_response(
                status_code=422,
                code="messager_request_invalid",
                message="Messager send fields are invalid.",
            )
        try:
            if peer_v2 is None:
                return await peer_v1.send_local(
                    principal=principal, recipient_user_id=payload["recipientUserId"],
                    client_message_id=payload["clientMessageId"], body=payload["body"],
                )
            return await peer_v2.send_local(
                principal=principal,
                recipient_user_id=payload["recipientUserId"],
                client_message_id=payload["clientMessageId"],
                body=payload["body"],
            )
        except PeerBrokerError as error:
            if error.code != "PEER_POLICY_DISABLED":
                return platform_error_response(
                    status_code=error.status_code, code=error.code.lower(),
                    message=str(error), retryable=error.retryable,
                )
            try:
                return await peer_v1.send_local(
                    principal=principal, recipient_user_id=payload["recipientUserId"],
                    client_message_id=payload["clientMessageId"], body=payload["body"],
                )
            except MessagerPeerError as error:
                return platform_error_response(
                    status_code=error.status_code, code=error.code.lower(),
                    message=str(error), retryable=error.retryable,
                )
        except MessagerPeerError as error:
            if error.code != "MESSAGER_RESULT_UNKNOWN" and error.retryable:
                try:
                    return await peer_v1.send_local(
                        principal=principal, recipient_user_id=payload["recipientUserId"],
                        client_message_id=payload["clientMessageId"], body=payload["body"],
                    )
                except MessagerPeerError as fallback_error:
                    error = fallback_error
            return platform_error_response(
                status_code=error.status_code,
                code=error.code.lower(),
                message=str(error),
                retryable=error.retryable,
            )

    @router.post(
        "/device-key/rotate",
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ],
    )
    async def rotate_device_key(
        principal: RequestPrincipal = principal_dependency,
    ):
        runtime = runtime_provider()
        peer = None if runtime is None else getattr(runtime, "messager_peer", None)
        if peer is None:
            return platform_error_response(
                status_code=503,
                code="messager_not_ready",
                message="Messager peer transport is not ready.",
                retryable=True,
            )
        try:
            registered = await peer.rotate_device_key(principal)
        except MessagerPeerError as error:
            return platform_error_response(
                status_code=error.status_code,
                code=error.code.lower(),
                message=str(error),
                retryable=error.retryable,
            )
        return JSONResponse(
            {
                "deviceId": registered["deviceId"],
                "keyId": registered.get("keyId"),
                "status": registered["status"],
            },
            headers={"Cache-Control": "no-store"},
        )

    from .bot_knowledge import add_routes as add_knowledge_routes
    add_knowledge_routes(router,runtime_provider,principal_dependency,bot_access,task_host,task_call)
    return router
