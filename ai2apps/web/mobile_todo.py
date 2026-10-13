"""Mobile Todo: explicit data operations, no execution or desktop bridge."""
import json
import logging
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator
from ai2apps.todo.models import TaskInput, validate_emoji
from ai2apps.api.todo import EmojiRequest, generate_task_emoji, attachment_response


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
    status: Literal['not_started','in_progress','completed','paused'] = 'not_started'
    progress: int = Field(default=0, ge=0, le=100)
    highlight: Literal['','lime','yellow','peach','pink','blue','lavender'] = ''


class MobileEmojiRequest(EmojiRequest):
    task_id: str | None = None


class TaskCreate(TaskEdit):
    directory_id: str
    parent_id: str | None = None


class TaskUpdate(TaskEdit):
    revision: int = Field(ge=1)


class DirectoryCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=1, max_length=200)


FIELDS = ('id','directory_id','parent_id','title','description','emoji','priority','status','progress','highlight','position','revision','updated_at')
def project(task):
    return {key: task.get(key) for key in FIELDS}


def create_mobile_todo_router(runtime_provider, principal_provider, renderer):
    router = APIRouter()
    dep = Depends(principal_provider)

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
    def snapshot(principal=dep):
        data = store(principal).snapshot(principal.actor_user_id)
        tasks = [t for t in data['tasks'] if not t.get('archived_at') and not t.get('deleted_at')]
        ids = {t['id'] for t in tasks}
        return {'directories': data['directories'], 'tasks': [project(t) for t in tasks],
                'attachments': [a for a in data['attachments'] if a['task_id'] in ids],
                'runs': [{k: r.get(k) for k in ('id','task_id','status','output','error','finished_at')}
                         for r in data['runs'] if r['task_id'] in ids]}

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
