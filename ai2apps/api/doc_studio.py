"""Local Doc Studio project, task and output routes."""
from contextlib import contextmanager
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Response, UploadFile

from ai2apps.doc_studio import service, translation
from ai2apps.doc_studio.models import CreateProject, Edit, Export, GalleryImage, Generate, Import, ProjectTitle, RewriteBlock
from ai2apps.doc_studio.repository import Repository
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.studio.repository import StudioRepository
from ai2apps.intelligence.article_chat import conversation_models

BASE = '/v1/platform/doc-studio'
PRIVATE = {'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'}


@contextmanager
def errors():
    try:
        yield
    except PermissionError as error:
        raise HTTPException(403, str(error)) from error
    except KeyError as error:
        raise HTTPException(404, 'Doc Studio record unavailable') from error
    except ValueError as error:
        raise HTTPException(409, str(error)) from error


def create_doc_studio_router(runtime_provider, principal_provider):
    router = APIRouter(prefix='/doc-studio', tags=['doc-studio'])

    def principal(value=Depends(principal_provider)):
        with errors():
            service.require_access(value)
        return value

    dep = Depends(principal)

    def repo():
        return Repository(runtime_provider().database)

    @router.get('/mini-app-outputs')
    def mini_app_outputs(instance_id: str = Header(alias='X-AI2Apps-App-Instance'), actor=dep):
        runtime = runtime_provider()
        authorize_app_instance(runtime, actor, instance_id)
        entry = runtime.extension_manager.instance_entry(instance_id, principal=actor)
        if entry.get('app_key') != service.APP_ID:
            raise HTTPException(404, 'Doc Studio instance unavailable')
        runs = StudioRepository(runtime.database).list_runs(
            actor_id=actor.actor_user_id, installation_id=actor.installation_id,
            app_instance_id=instance_id, studio_id=service.APP_ID, limit=100,
        )
        return {'items': [
            {'id': artifact['id'], 'name': artifact['name'], 'target': artifact['mediaType'],
             'media_type': artifact['mediaType'], 'preview_url': artifact['previewUrl'],
             'download_url': artifact['downloadUrl'], 'created_at': artifact['createdAt']}
            for run in runs if run['status'] == 'succeeded'
            for artifact in run['artifacts'] if artifact['final']
        ]}

    @router.get('/packs/{pack_id}')
    def pack(pack_id: str, actor=dep):
        with errors():
            return service.pack_summary(repo().pack(actor.actor_user_id, pack_id))

    @router.get('/projects')
    def projects(actor=dep):
        return repo().projects(actor.actor_user_id)

    @router.post('/projects', status_code=201)
    def create_project(body: CreateProject, actor=dep):
        with errors():
            return service.create_project(repo(), actor.actor_user_id, body)

    @router.patch('/projects/{project_id}')
    def rename_project(project_id: str, body: ProjectTitle, actor=dep):
        with errors():
            return repo().rename_project(actor.actor_user_id, project_id, body.title)

    @router.delete('/projects/{project_id}', status_code=204)
    def delete_project(project_id: str, actor=dep):
        with errors():
            service.delete_project(repo(), actor.actor_user_id, project_id)
        return Response(status_code=204)

    @router.post('/imports', status_code=202)
    async def import_pack(body: Import, actor=dep):
        with errors():
            return submit('import', None, body, actor)

    @router.get('/projects/{project_id}')
    def project(project_id: str, actor=dep):
        owner = actor.actor_user_id
        repository = repo()
        with errors():
            result = repository.project(owner, project_id)
            materials = repository.materials(owner, project_id)
            outputs = repository.outputs(owner, project_id)
            for item in materials:
                item.pop('body')
                item.pop('original_content', None)
                item.pop('paragraphs', None)
                item.pop('source_originals', None)
                for image in item['images']:
                    asset = image.get('asset_id')
                    if asset:
                        image['preview_url'] = f'{BASE}/projects/{project_id}/images/{asset}'
            for item in outputs:
                url = f'{BASE}/projects/{project_id}/outputs/{item["id"]}'
                item.update(preview_url=url, download_url=url + '?download=true')
            return {**result, 'materials': materials, 'outputs': outputs,
                    'versions': repository.versions(owner, project_id), 'tasks': repository.tasks(owner, project_id)}

    @router.get('/projects/{project_id}/versions/{version_id}')
    def version(project_id: str, version_id: str, actor=dep):
        with errors():
            value = repo().version(actor.actor_user_id, project_id, version_id)
            return {key: value[key] for key in ('id', 'created_at', 'title', 'content', 'style', 'target',
                                                'language', 'guidance', 'note', 'origin', 'parent_version_id', 'blocks')}

    @router.post('/projects/{project_id}/versions/{version_id}')
    def edit(project_id: str, version_id: str, body: Edit, actor=dep):
        with errors():
            return {'id': service.edit(repo(), actor.actor_user_id, project_id, version_id, body)['id']}

    def submit(operation, project_id, body, actor):
        runtime = runtime_provider()
        task = service.submit(runtime, actor, operation, project_id, body)
        return service.task(runtime, actor.actor_user_id, task['id'])

    @router.post('/projects/{project_id}/generate', status_code=202)
    async def generate(project_id: str, body: Generate, actor=dep):
        with errors():
            return submit('generate', project_id, body, actor)

    @router.post('/projects/{project_id}/export', status_code=202)
    async def export(project_id: str, body: Export, actor=dep):
        with errors():
            return submit('export', project_id, body, actor)

    @router.post('/projects/{project_id}/rewrite-block', status_code=202)
    async def rewrite_block(project_id: str, body: RewriteBlock, actor=dep):
        with errors():
            return submit('rewrite_block', project_id, body, actor)

    @router.post('/projects/{project_id}/images/gallery', status_code=201)
    def gallery_image(project_id: str, body: GalleryImage, actor=dep):
        with errors():
            return service.import_gallery_image(runtime_provider(), actor.actor_user_id, project_id, body.asset_id)

    @router.get('/tasks/{task_id}')
    def task(task_id: str, actor=dep):
        with errors():
            return service.task(runtime_provider(), actor.actor_user_id, task_id)

    def translations():
        return translation.Repository(runtime_provider().database)

    @router.get('/translation')
    def translation_overview(actor=dep):
        result = translations().overview(actor.actor_user_id)
        for item in result['outputs']:
            url = f'{BASE}/translation/outputs/{item["id"]}'
            item.update(preview_url=url, download_url=url + '?download=true')
        return result

    @router.get('/translation/models')
    async def translation_models(actor=dep):
        return {**await conversation_models(runtime_provider(), actor), 'layout_formats': list(translation.MEDIA_TYPES),
                'pdf_form': True}

    @router.get('/translation/profiles')
    def translation_profiles(actor=dep):
        return translations().profiles(actor.actor_user_id)

    @router.post('/translation/profiles', status_code=201)
    def create_translation_profile(body: translation.Profile, actor=dep):
        return translations().save_profile(actor.actor_user_id, body)

    @router.put('/translation/profiles/{profile_id}')
    def update_translation_profile(profile_id: str, body: translation.Profile, actor=dep):
        with errors():
            return translations().save_profile(actor.actor_user_id, body, profile_id)

    @router.delete('/translation/profiles/{profile_id}', status_code=204)
    def delete_translation_profile(profile_id: str, actor=dep):
        with errors():
            translations().delete_profile(actor.actor_user_id, profile_id)
        return Response(status_code=204)

    @router.post('/translation', status_code=202)
    async def translate(
        options: str = Form(), text: str = Form(''), markdown: bool = Form(False),
        output_format: str = Form('layout'),
        file: UploadFile | None = File(None), actor=dep,
    ):
        try:
            settings = translation.Options.model_validate_json(options)
        except ValueError as error:
            raise HTTPException(422, '翻译参数无效 / Invalid translation settings.') from error
        with errors():
            try:
                source = (file.filename or '', await file.read(translation.MAX_FILE_BYTES + 1)) if file else None
            finally:
                if file:
                    await file.close()
            return await translation.submit(runtime_provider(), actor, settings, text=text, markdown=markdown,
                                            output_format=output_format, source=source, catalog_loader=conversation_models)

    @router.post('/translation/tasks/{task_id}/resume', status_code=202)
    def resume_translation(task_id: str, actor=dep):
        runtime = runtime_provider()
        owner = actor.actor_user_id
        with errors():
            task = runtime.system_tasks.get(owner, task_id)
            if task['app_id'] != translation.APP_ID or task['kind'] != translation.KIND:
                raise KeyError(task_id)
            if task['status'] not in {'failed', 'interrupted'}:
                raise ValueError('此任务不能继续 / This translation cannot be resumed.')
            resumed = runtime.system_tasks.submit(
                owner, task['app_id'], task['kind'], task['name'], task['payload'],
                checkpoint=task['checkpoint'], receipt_key='translate-resume:' + task_id,
            )
            return service.task(runtime, owner, resumed['id'])

    @router.get('/translation/outputs/{output_id}')
    def translation_output(output_id: str, download: bool = False, actor=dep):
        with errors():
            info, data = translations().output(actor.actor_user_id, output_id)
        headers = dict(PRIVATE)
        if download or info['suffix'] == 'docx':
            filename = quote(info['name'] + '.' + info['suffix'], safe='')
            headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{filename}"
        return Response(data, media_type=info['media_type'], headers=headers)

    @router.post('/tasks/{task_id}/cancel')
    async def cancel(task_id: str, actor=dep):
        with errors():
            runtime = runtime_provider()
            owner = actor.actor_user_id
            service.task(runtime, owner, task_id)
            runtime.system_tasks.cancel(owner, task_id)
            return service.task(runtime, owner, task_id)

    @router.get('/projects/{project_id}/images/{asset_id}')
    def image(project_id: str, asset_id: str, actor=dep):
        with errors():
            data, mime = repo().image(actor.actor_user_id, project_id, asset_id)
        return Response(data, media_type=mime, headers=PRIVATE)

    @router.get('/projects/{project_id}/outputs/{output_id}')
    def output(project_id: str, output_id: str, download: bool = False, actor=dep):
        with errors():
            info, data = repo().output(actor.actor_user_id, project_id, output_id)
        headers = {**PRIVATE, 'Content-Security-Policy':
                   "sandbox; default-src 'none'; img-src data:; style-src 'unsafe-inline'; frame-ancestors 'self'"}
        if download:
            filename = quote(info['name'].replace('/', '_').replace(chr(92), '_') + '.' + info['suffix'], safe='')
            headers['Content-Disposition'] = f"attachment; filename*=UTF-8''{filename}"
        return Response(data, media_type=info['media_type'], headers=headers)

    return router
