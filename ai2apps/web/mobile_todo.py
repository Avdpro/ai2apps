"""Owner-scoped mobile Todo and explicit authorized execution controls."""
import json
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ai2apps.todo.models import TaskInput, validate_emoji
from ai2apps.api.todo import EmojiRequest, RunReviewRequest, generate_task_emoji, attachment_response, DesktopBindingRequest, bind_desktop_task


class NavigationEvent(BaseModel):
    model_config = ConfigDict(extra='forbid')
    event: Literal['ready','touchstart','touchmove','touchend','touchcancel','popstate','pageshow','pagehide','hashchange','frame1','frame2','visibility','view-change']
    document_id: str | None = Field(default=None, pattern=r'^[a-f0-9-]{36}$')
    persisted: bool | None = None
    navigation: Literal['navigate','reload','back_forward','prerender'] = 'navigate'
    seq: int = Field(ge=1, le=1000)
    at: float = Field(ge=0, allow_inf_nan=False)
    mono: float = Field(ge=0, allow_inf_nan=False)
    list: bool | None = None
    detail: bool | None = None
    stage: bool | None = None
    loading: bool | None = None
    route: Literal['list','detail','other']
    visible: bool


class NavigationTrace(BaseModel):
    model_config = ConfigDict(extra='forbid')
    session: str = Field(pattern=r'^[a-f0-9-]{36}$')
    surface: Literal['todo','shell']
    events: list[NavigationEvent] = Field(min_length=1, max_length=40)


class TaskEdit(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default='', max_length=100000)
    emoji: str = Field(default="", max_length=32)
    _valid_emoji = field_validator("emoji")(validate_emoji)
    priority: Literal['U','S','A','B','C','D'] = 'C'
    status: Literal['not_started','in_progress','awaiting_acceptance','completed','paused'] = 'not_started'
    progress: int = Field(default=0, ge=0, le=100)
    highlight: Literal['','lime','yellow','peach','pink','blue','lavender'] = ''


class MobileEmojiRequest(EmojiRequest):
    task_id: str | None = None


class TaskCreate(TaskEdit):
    directory_id: str
    parent_id: str | None = None


class TaskUpdate(TaskEdit):
    revision: int = Field(ge=1)


class ExecutionSettings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    revision: int = Field(ge=1)
    executor: Literal['internal','codex','claude','codex_desktop']
    model: str = Field(default='', max_length=300)
    working_directory: str = Field(default='', max_length=4096)


class DirectoryCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)


FIELDS = ('id','directory_id','parent_id','title','description','emoji','priority','status','progress','highlight','position','revision','updated_at')
def project(task):
    return {key: task.get(key) for key in FIELDS}


def create_mobile_todo_router(runtime_provider, principal_provider, renderer):
    router = APIRouter()
    dep = Depends(principal_provider)
    from ai2apps.api.system_tasks import install_system_task_routes
    install_system_task_routes(router,runtime_provider,principal_provider,prefix='/v1/mobile/todo')

    def store(principal):
        from ai2apps.apps.access import has_app_capability
        if not has_app_capability(principal, 'app.use'):
            raise HTTPException(403, 'Todo access required')
        service = getattr(runtime_provider(), 'todo', None)
        if service is None:
            raise HTTPException(503, 'Todo is unavailable')
        return service.store

    def checked(fn, *args):
        try:
            return fn(*args)
        except KeyError:
            raise HTTPException(404, 'Task or directory not found') from None
        except ValueError as error:
            raise HTTPException(409 if 'refresh before saving' in str(error) else 422, str(error)) from None

    @router.get('/mobile/todo')
    def page(request: Request, principal=dep):
        store(principal)
        return renderer(request, principal)

    @router.get('/v1/mobile/todo')
    def snapshot(q: str = "", principal=dep):
        data = store(principal).mobile_list(principal.actor_user_id, q.strip())
        return {**({'search_matches':data['search_matches']} if 'search_matches' in data else {}), 'directories':data['directories'], 'tasks':[
            {key:task.get(key) for key in FIELDS if key != 'description'} for task in data['tasks']]}

    @router.get('/v1/mobile/todo/tasks/{task_id}/detail')
    def detail(task_id: str, principal=dep):
        data = checked(store(principal).mobile_detail, principal.actor_user_id, task_id)
        return {'task':project(data['task']), 'attachments':data['attachments'],
                'runs':[{k:r.get(k) for k in ('id','task_id','status','output','error','finished_at','review')} for r in data['runs']]}

    def execution_service(principal):
        store(principal)
        from ai2apps.apps.access import APP_CODER_USE, has_app_capability
        if not has_app_capability(principal, APP_CODER_USE):
            raise HTTPException(403, 'Coder permission required')
        return runtime_provider().todo

    @router.get('/v1/mobile/todo/executors')
    def executors(principal=dep):
        return execution_service(principal).executors()

    @router.get('/v1/mobile/todo/codex/projects')
    async def projects(principal=dep):
        execution_service(principal)
        try:
            return await runtime_provider().codex.projects()
        except (ValueError, OSError, TimeoutError) as error:
            raise HTTPException(503, str(error) or 'Codex is unavailable') from error

    @router.get('/v1/mobile/todo/codex/threads')
    async def threads(cwd: str, cursor: str | None = None, principal=dep):
        execution_service(principal)
        try:
            return await runtime_provider().codex.threads(cwd, cursor)
        except (ValueError, OSError, TimeoutError) as error:
            raise HTTPException(503, str(error) or 'Codex is unavailable') from error

    @router.get('/v1/mobile/todo/tasks/{task_id}/execution')
    def execution_read(task_id: str, principal=dep):
        task = checked(execution_service(principal).store.get, principal.actor_user_id, task_id)
        return {k: task[k] for k in ('executor','model','working_directory','codex','revision')}

    @router.put('/v1/mobile/todo/tasks/{task_id}/execution')
    def execution_settings(task_id: str, body: ExecutionSettings, principal=dep):
        s = execution_service(principal).store
        old = checked(s.get, principal.actor_user_id, task_id)
        data = {k: old[k] for k in TaskInput.model_fields}
        data.update(body.model_dump(exclude={'revision'}))
        return project(checked(s.save, principal.actor_user_id, data, task_id, body.revision))

    @router.put('/v1/mobile/todo/tasks/{task_id}/codex/desktop')
    async def bind(task_id: str, body: DesktopBindingRequest, principal=dep):
        s = execution_service(principal)
        try:
            return project(await bind_desktop_task(s, principal, task_id, body))
        except KeyError as error:
            raise HTTPException(404, str(error)) from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @router.post('/v1/mobile/todo/tasks/{task_id}/run')
    def run(task_id: str, principal=dep):
        return checked(execution_service(principal).launch, principal.actor_user_id, task_id, None, principal)

    @router.post('/v1/mobile/todo/tasks/{task_id}/attachments')
    async def upload(task_id: str, file: UploadFile = File(...), principal=dep):
        s = store(principal)
        checked(s.get, principal.actor_user_id, task_id)
        content = await file.read(32 * 1024 * 1024 + 1)
        await file.close()
        if len(content) > 32 * 1024 * 1024:
            raise HTTPException(413, 'Maximum attachment size is 32 MiB')
        return checked(s.add_attachment, principal.actor_user_id, task_id, file.filename or 'attachment', content)

    @router.post('/v1/mobile/todo/runs/{run_id}/review')
    def review(run_id: str, body: RunReviewRequest, principal=dep):
        return checked(store(principal).review_run, principal.actor_user_id, run_id, body.decision, body.revision)

    @router.get('/v1/mobile/todo/attachments/{attachment_id}')
    def attachment(attachment_id: str, preview: bool = False, principal=dep):
        s = store(principal)
        item, path = checked(s.attachment, principal.actor_user_id, attachment_id)
        task = checked(s.get, principal.actor_user_id, item['task_id'])
        if task.get('archived_at') or task.get('deleted_at'):
            raise HTTPException(404, 'Attachment not available')
        return attachment_response(item, path, preview)

    @router.post('/v1/mobile/todo/emoji/suggest')
    async def emoji_suggest(body: MobileEmojiRequest, request: Request, principal=dep):
        s = store(principal)
        if body.task_id:
            checked(s.get, principal.actor_user_id, body.task_id)
        return await generate_task_emoji(runtime_provider(), s, principal, request, body, body.task_id)

    @router.post('/v1/mobile/todo/navigation-trace')
    def navigation_trace(body: NavigationTrace, principal=dep):
        store(principal)  # Same authenticated owner/App capability as Todo.
        logging.getLogger(__name__).info('MOBILE_NAV_TRACE %s', json.dumps(body.model_dump(), separators=(',', ':')))
        return {'accepted': len(body.events)}

    @router.post('/v1/mobile/todo/directories')
    def directory(body: DirectoryCreate, principal=dep):
        return checked(store(principal).directory, principal.actor_user_id, body.title)

    @router.post('/v1/mobile/todo/tasks')
    def create(body: TaskCreate, principal=dep):
        data = body.model_dump()
        data.update(completed=body.status == 'completed', progress=100 if body.status == 'completed' else body.progress)
        return project(checked(store(principal).save, principal.actor_user_id, data))

    @router.put('/v1/mobile/todo/tasks/{task_id}')
    def update(task_id: str, body: TaskUpdate, principal=dep):
        s = store(principal)
        old = checked(s.get, principal.actor_user_id, task_id)
        data = {k: old[k] for k in TaskInput.model_fields}
        patch = body.model_dump(exclude={'revision'})
        if 'description' not in body.model_fields_set:
            patch.pop('description')  # List quick edits do not load the description.
        if 'progress' not in body.model_fields_set:
            patch.pop('progress')  # Older mobile clients must not reset saved progress.
        if 'highlight' not in body.model_fields_set:
            patch.pop('highlight')
        if 'emoji' not in body.model_fields_set:
            patch.pop('emoji')  # Quick edits and older clients preserve the saved Emoji.
        data.update(patch)
        data['completed'] = body.status == 'completed'
        if body.status == 'completed': data['progress'] = 100
        elif old['status'] == 'completed' and 'progress' not in body.model_fields_set: data['progress'] = 0
        return project(checked(s.save, principal.actor_user_id, data, task_id, body.revision))

    return router
