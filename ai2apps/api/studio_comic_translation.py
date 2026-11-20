"""Mount-scoped host services for the Comic Translation Package."""
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from ai2apps.api.ownership import authorize_app_instance
from ai2apps.core import ResourceNotFoundError
from ai2apps.extensions import ExtensionError
from ai2apps.images import comic_translation as comic
from ai2apps.studio.capability_broker import StudioCapabilityBroker, StudioCapabilityError
from ai2apps.images.comic_translation import models
from ai2apps.studio.comic_output import MAX_OUTPUT, MAX_PAGES, publish_comic, stage_page

Text = Annotated[str, Field(min_length=1, max_length=1500)]


class GlossaryEntry(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    source: str = Field(min_length=1, max_length=100)
    translation: str = Field(min_length=1, max_length=150)
    kind: Literal['person', 'place', 'item', 'other']


class Translation(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    model: str = Field(min_length=1, max_length=255)
    language: Literal['zh', 'en', 'ja', 'ko', 'es', 'fr']
    texts: list[Text] = Field(min_length=1, max_length=comic.MAX_REGIONS)
    before: list[Text] = Field(default_factory=list, max_length=8)
    after: list[Text] = Field(default_factory=list, max_length=8)
    targets: list[int] | None = Field(default=None, min_length=1, max_length=comic.MAX_REGIONS)
    nearby_pairs: list[int] = Field(default_factory=list, max_length=comic.MAX_REGIONS - 1)
    glossary: list[GlossaryEntry] | None = Field(default=None, max_length=500)
    bubble_candidates: list[tuple[int, int, bool]] = Field(default_factory=list, max_length=64)
    bubble_boxes: list[tuple[float, float, float, float]] = Field(default_factory=list, max_length=comic.MAX_REGIONS)
    vertical: bool = False


def create_comic_translation_router(runtime_provider, principal_provider):
    router = APIRouter(prefix='/{studio_id}/mini-app-mounts/{mount_id}/comic-translation')
    principal_dep = Depends(principal_provider)
    export_slot = asyncio.Lock()

    def scope(studio_id, mount_id, principal):
        runtime = runtime_provider()
        try:
            mounted = StudioCapabilityBroker(runtime).mounted_mini_app(studio_id, mount_id, principal=principal)
        except StudioCapabilityError as error:
            raise HTTPException(error.status_code, str(error)) from error
        except (ExtensionError, ResourceNotFoundError) as error:
            raise HTTPException(404, 'Mini-App unavailable') from error
        if (studio_id != comic.STUDIO_ID or mounted.mount.get('app_key') != comic.APP_ID
                or mounted.declaration['id'] != comic.MINI_ID or comic.CAPABILITY not in mounted.capabilities):
            raise HTTPException(403, 'Comic Translation capability required')
        instance = mounted.mount['context']['studioInstanceId']
        authorize_app_instance(runtime, principal, instance)
        if runtime.extension_manager.instance_entry(instance, principal=principal).get('app_key') != studio_id:
            raise HTTPException(404, 'Imagine Studio unavailable')
        return runtime, mounted, dict(actor_id=principal.actor_user_id, installation_id=principal.installation_id,
                                      app_instance_id=instance, studio_id=studio_id)

    @router.get('/models')
    async def get_models(studio_id: str, mount_id: str, principal=principal_dep):
        runtime, _, _ = scope(studio_id, mount_id, principal)
        try:
            return {**await models(runtime), 'ocrReady': comic.ocr_ready(runtime)}
        except comic.ModelInvocationError as error:
            raise HTTPException(503, str(error)) from error

    @router.post('/image/{action}')
    async def process(studio_id: str, mount_id: str, action: Literal['analyze', 'recognize', 'recognize-vertical'],
                      file: Annotated[UploadFile, File()], principal=principal_dep):
        runtime, _, binding = scope(studio_id, mount_id, principal)
        content = await file.read(comic.MAX_IMAGE + 1)
        if len(content) > comic.MAX_IMAGE:
            raise HTTPException(413, 'Image exceeds 16 MiB')
        try:
            image = await asyncio.to_thread(comic.load_image, content)
            if action == 'analyze':
                return await asyncio.to_thread(comic.analyze, image)
            context = comic.context_for(principal, binding['app_instance_id'])
            return {'text': await comic.recognize(runtime, context, image, vertical=action == 'recognize-vertical')}
        except LookupError as error:
            raise HTTPException(409, str(error)) from error
        except (ValueError, OSError) as error:
            raise HTTPException(422, str(error)) from error
        except TimeoutError as error:
            raise HTTPException(504, 'OXR timed out') from error
        except comic.ModelInvocationError as error:
            raise HTTPException(502, str(error)) from error

    @router.post('/translate')
    async def translate(studio_id: str, mount_id: str, body: Translation, principal=principal_dep):
        runtime, _, binding = scope(studio_id, mount_id, principal)
        try:
            if body.model not in {item['id'] for item in (await models(runtime))['items']}:
                raise HTTPException(409, 'Selected translation model is unavailable under the current model policy')
            if sum(map(len, [*body.texts, *body.before, *body.after])) > 20_000:
                raise HTTPException(413, 'Dialogue and context exceed 20,000 characters')
            scope(studio_id, mount_id, principal)
            context = comic.context_for(principal, binding['app_instance_id'])
            result = await comic.translate(runtime, context, body.texts, body.language,
                model=body.model, before=body.before, after=body.after,
                targets=body.targets, nearby_pairs=body.nearby_pairs,
                glossary=None if body.glossary is None else [term.model_dump() for term in body.glossary],
                bubble_candidates=body.bubble_candidates, bubble_boxes=body.bubble_boxes, vertical=body.vertical)
            return result if body.glossary is not None else {'translations': result}
        except ValueError as error:
            raise HTTPException(422, str(error)) from error
        except TimeoutError as error:
            raise HTTPException(504, 'Translation timed out') from error
        except comic.ModelInvocationError as error:
            raise HTTPException(502, str(error)) from error

    @router.post('/export/{format}')
    async def export(studio_id: str, mount_id: str, format: Literal['png', 'html'],
                     files: Annotated[list[UploadFile], File()], principal=principal_dep):
        runtime, mounted, binding = scope(studio_id, mount_id, principal)
        kind = 'image' if format == 'png' else 'file'
        if not any(output.get('kind') == kind and output.get('final', True)
                   for output in mounted.declaration.get('outputs', ())):
            raise HTTPException(403, 'Output kind was not declared')
        if not 1 <= len(files) <= (MAX_PAGES if format == 'png' else 1):
            raise HTTPException(422, 'Invalid number of files')
        if export_slot.locked():
            raise HTTPException(409, 'Another comic export is running')
        async with export_slot:
            with TemporaryDirectory(prefix='comic-translation-') as directory:
                staged = []
                remaining = MAX_OUTPUT
                for index, upload in enumerate(files, 1):
                    data = await upload.read(remaining + 1)
                    remaining -= len(data)
                    if remaining < 0:
                        raise HTTPException(413, 'Export exceeds 64 MiB')
                    try:
                        staged.append(await asyncio.to_thread(stage_page, Path(directory), index, data, format))
                    except (OSError, ValueError) as error:
                        raise HTTPException(422, str(error)) from error
                scope(studio_id, mount_id, principal)
                publication = asyncio.create_task(asyncio.to_thread(
                    publish_comic, runtime, mounted.declaration, binding, staged, format))
                try:
                    _, outputs = await asyncio.shield(publication)
                except asyncio.CancelledError:
                    await publication
                    raise
                return outputs[-1]

    return router
