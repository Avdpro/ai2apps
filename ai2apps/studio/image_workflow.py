"""Bounded image sequences and contact sheets; no project/story semantics.

Packages compile prompts, ordered references and captions. Local owns execution,
private image storage and one final Studio output, using existing durable jobs.
"""
from __future__ import annotations

import asyncio
import hashlib
import io
import json
import re
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ai2apps.studio.image_jobs import checkpoint, generate_image

CAPABILITY = 'image.workflow'
ID = re.compile(r'^[0-9a-f]{32}$')
MAX_IMAGE_BYTES = 20 * 1024 * 1024


class SubmissionConflict(ValueError):
    pass


async def model_catalog(runtime, principal):
    from ai2apps.images.parameters import models
    from ai2apps.model_providers import list_package_models
    generation, editing = await asyncio.gather(models(runtime, principal, False), models(runtime, principal, True))
    editable = {item['id'] for item in editing[0]}
    local = {item.id: item for item in list_package_models(runtime)}
    result = []
    for item in generation[0]:
        limit = 4 if item['id'] in editable else 0
        if item['id'] in local:
            limit = min(limit, (local[item['id']].image_capabilities or {}).get('inputs', {}).get('reference_images', {}).get('maximum', 0))
        result.append({**item, 'referenceLimit': limit})
    from ai2apps.images.service import _default_image_model
    manager = getattr(runtime, 'model_manager', None)
    return {'items': result, 'preferred': _default_image_model(manager) if manager is not None else '',
            'warnings': list(dict.fromkeys(generation[1] + editing[1]))}


async def submit_plan(runtime, principal, binding, scope, body, *, parent_task_id=None):
    """Same bounded submission for foreground mounts and admitted system work."""
    from ai2apps.studio.repository import StudioRepository
    from ai2apps.studio.extended_jobs import submit
    from ai2apps.images.parameters import validate_size
    if not hasattr(runtime, '_image_workflow_submission_lock'):
        runtime._image_workflow_submission_lock = asyncio.Lock()
    plan = body.model_dump()
    key = 'image-workflow-' + binding['mini_id'] + '-' + body.key
    async with runtime._image_workflow_submission_lock:
        with runtime.database.transaction() as db:
            old = db.execute('SELECT * FROM studio_background_jobs WHERE actor_id=? AND installation_id=? AND studio_id=? AND idempotency_key=?',
                (principal.actor_user_id, principal.installation_id, scope['studio_id'], key)).fetchone()
        if old:
            if old['app_instance_id'] != scope['app_instance_id'] or json.loads(old['request_json']).get('plan') != plan:
                raise SubmissionConflict('Submission key already used for another plan')
            return runtime.studio_jobs.public(old)
        if any(not step.image for step in body.steps):
            choices = await model_catalog(runtime, principal)
            selected = next((item for item in choices['items'] if item['id'] == body.model and item['ready']), None)
            if not selected: raise ValueError('Select an available drawing model')
            validate_size(body.size, selected['size'])
            if body.quality not in selected['qualities'] or 'png' not in selected['formats']:
                raise ValueError('Selected model does not support requested quality or PNG output')
            if body.reference_limit > selected['referenceLimit']:
                raise ValueError('Reference limit exceeds selected model capability')
        root = asset_root(runtime, principal, binding['provider'])
        files = {ref: read_asset(root, ref) for step in body.steps for ref in [*step.references, *([step.image] if step.image else [])]}
        if sum(map(len, files.values())) > 64 * 1024 * 1024: raise ValueError('References exceed 64 MiB')
        schedules=getattr(runtime,'image_workflow_schedules',None)
        if schedules is not None and body.resource_key:
            scheduled=schedules.system.active_for(principal.actor_user_id,scope['studio_id'],
                'schedule:'+schedules.identity({**binding,'owner':principal.actor_user_id,'installation':principal.installation_id,'scope':scope},body.resource_key))
            if scheduled and scheduled['id']!=parent_task_id:
                raise SubmissionConflict('This resource already has an automatic task: '+scheduled['id'])
        repository = StudioRepository(runtime.database)
        run = repository.create_run(**scope, mini_app_id=binding['mini_id'], mini_app_version=binding['version'],
            placement='inline', title=body.title, input_data={'workflowKey': body.key, 'model': body.model,
                'size': body.size, 'steps': len(body.steps)}) if body.publish else None
        try:
            return submit(runtime, principal, scope['app_instance_id'], scope['studio_id'], binding['mini_id'],
                'image-workflow', {'plan': plan, 'provider': binding['provider']}, files=files,
                run_id=run['id'] if run else None, key=key)
        except Exception:
            if run: repository.update_run(run['id'], **scope, status='failed', progress=100, detail='Submission failed')
            raise


class Step(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    prompt: str = Field(default='', max_length=16000)
    image: str | None = None
    caption: str = Field(default='', max_length=600)
    references: list[str] = Field(default_factory=list, max_length=4)
    previous: int = Field(default=2, ge=0, le=2)

    @model_validator(mode='after')
    def source(self):
        if self.image is not None and not ID.fullmatch(self.image): raise ValueError('Invalid source image')
        if not self.image and not self.prompt.strip(): raise ValueError('Image prompt is required')
        return self

    @field_validator('references')
    @classmethod
    def valid_references(cls, value):
        if any(not ID.fullmatch(item) for item in value) or len(value) != len(set(value)):
            raise ValueError('Invalid image reference')
        return value


class Plan(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    schema_version: str = Field(default='ai2apps.image-sequence/v1', pattern='^ai2apps\\.image-sequence/v1$')
    key: str = Field(min_length=8, max_length=100, pattern=r'^[a-zA-Z0-9_-]+$')
    resource_key: str | None = Field(default=None, min_length=1, max_length=100, pattern=r'^[A-Za-z0-9_-]+$')
    title: str = Field(min_length=1, max_length=160)
    model: str = Field(min_length=1, max_length=255)
    size: str = Field(pattern=r'^\d{2,4}x\d{2,4}$')
    quality: str = Field(default='auto', max_length=30)
    reference_limit: int = Field(default=4, ge=0, le=4)
    columns: int = Field(default=2, ge=1, le=3)
    publish: bool = True
    steps: list[Step] = Field(min_length=1, max_length=6)

    @model_validator(mode='after')
    def bounded(self):
        width, height = map(int, self.size.split('x'))
        if min(width, height) < 256 or max(width, height) > 2048 or width * height > 4194304:
            raise ValueError('Image dimensions exceed workflow limits')
        if any(len(step.references) > self.reference_limit for step in self.steps):
            raise ValueError('Required references exceed the selected model limit')
        measure = ImageDraw.Draw(Image.new('RGB', (1, 1)))
        if any(len(wrapped(step.caption, measure, _font(25), 740)) > 12 for step in self.steps):
            raise ValueError('Caption too long for the page; shorten it before drawing')
        return self


def asset_root(runtime, principal, provider):
    scope = hashlib.sha256(json.dumps([principal.actor_user_id, principal.installation_id, provider]).encode()).hexdigest()
    root = runtime.config.paths.artifacts_path / 'package-image-workflows' / scope
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def image_bytes(data):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise ValueError('PNG/JPEG/WebP image must be between 1 byte and 20 MiB')
    with Image.open(io.BytesIO(data)) as source:
        if source.format not in ('PNG', 'JPEG', 'WEBP') or source.width * source.height > 25000000:
            raise ValueError('Unsupported image format or dimensions')
        source.load()
        image = ImageOps.exif_transpose(source).convert('RGB')
        out = io.BytesIO(); image.save(out, format='PNG')
    result = out.getvalue()
    if len(result) > MAX_IMAGE_BYTES: raise ValueError('Decoded image exceeds 20 MiB')
    return result


def save_asset(root, data):
    data = image_bytes(data)
    identifier = hashlib.sha256(data).hexdigest()[:32]
    destination = root / (identifier + '.png')
    if not destination.exists():
        temp = root / (uuid.uuid4().hex + '.tmp')
        temp.write_bytes(data); temp.chmod(0o600); temp.replace(destination)
    return identifier


def read_asset(root, identifier):
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise ValueError('Invalid image reference')
    source = root / (identifier + '.png')
    if not source.is_file() or source.is_symlink():
        raise FileNotFoundError('Image is unavailable in this Package scope')
    return source.read_bytes()


def data_url(data, thumbnail=False):
    import base64
    if thumbnail:
        with Image.open(io.BytesIO(data)) as image:
            image.thumbnail((512, 512)); out = io.BytesIO(); image.convert('RGB').save(out, 'JPEG', quality=85)
        return 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode()
    return 'data:image/png;base64,' + base64.b64encode(data).decode()


def _font(size):
    # Native font collection supports CJK; Linux falls back to installed fonts.
    for path in ['/System/Library/Fonts/PingFang.ttc', '/System/Library/Fonts/Supplemental/Arial Unicode.ttf',
                 '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf']:
        try: return ImageFont.truetype(path, size)
        except OSError: pass
    return ImageFont.load_default()


def wrapped(text, draw, font, width):
    lines, line = [], ''
    for character in text:
        if character == '\n': lines.append(line); line = ''; continue
        if line and draw.textbbox((0, 0), line + character, font=font)[2] > width:
            lines.append(line); line = character
        else: line += character
    lines.append(line)
    return lines


def compose(images, captions, title, columns):
    """Preserve image aspect; separate captions are rendered without an LLM."""
    cells = [Image.open(io.BytesIO(data)).convert('RGB') for data in images]
    if not cells or len(cells) > 6 or len(captions) != len(cells): raise ValueError('Invalid contact sheet')
    width = 768; columns = min(columns, len(cells)); margin = 24
    height = round(width * cells[0].height / cells[0].width)
    font, heading = _font(25), _font(34)
    measure = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    lines = [wrapped(text, measure, font, width - 28) for text in captions]
    if any(len(value) > 12 for value in lines): raise ValueError('Caption too long; shorten text before export')
    caption_height = max((len(value) * 35 + 24 if ''.join(value) else 0) for value in lines)
    rows = (len(cells) + columns - 1) // columns
    sheet_width = columns * (width + margin) + margin
    titles = wrapped(title, measure, heading, sheet_width - 2 * margin)
    header = 32 + len(titles) * 46
    sheet = Image.new('RGB', (sheet_width, header + margin + rows * (height + caption_height + margin)), 'white')
    draw = ImageDraw.Draw(sheet)
    for n, line in enumerate(titles):
        draw.text((margin, 16 + n * 46), line, font=heading, fill='#202024')
    for index, image in enumerate(cells):
        x, y = margin + index % columns * (width + margin), header + index // columns * (height + caption_height + margin)
        fitted = ImageOps.contain(image, (width, height)); sheet.paste(fitted, (x + (width-fitted.width)//2, y+(height-fitted.height)//2))
        draw.rectangle((x, y, x + width, y + height), outline='#202024', width=2)
        for line_index, line in enumerate(lines[index]):
            draw.text((x + 12, y + height + 10 + line_index * 35), line, font=font, fill='#202024')
    out = io.BytesIO(); sheet.save(out, 'PNG'); return out.getvalue()


async def execute(manager, job, principal, payload):
    plan = Plan.model_validate(payload['plan'])
    root = asset_root(manager.runtime, principal, payload['provider'])
    directory = manager.root / job['id']; directory.mkdir(exist_ok=True)
    input_root = Path(payload['input_root'])
    accepted = []
    for index, step in enumerate(plan.steps):
        if manager.get(job['id'], principal)['status'] == 'cancelled': raise asyncio.CancelledError()
        target = directory / str(index)
        if step.image and not (target / 'result.json').exists():
            data = (input_root / step.image / 'output').read_bytes()
            checkpoint(target, data, {'assetId': step.image})
        if (target / 'result.json').exists():
            accepted.append((target / 'output').read_bytes()); continue
        # Freeze source assets at submission; don't follow later mutable references.
        references = [(input_root / ref / 'output').read_bytes() for ref in step.references]
        room = plan.reference_limit - len(references)
        previous = accepted[-min(step.previous, room):] if step.previous and room else []
        urls = [data_url(data) for data in references] + [data_url(data, True) for data in reversed(previous)]
        body = {'model': plan.model, 'prompt': step.prompt, 'size': plan.size,
                'quality': plan.quality, 'outputFormat': 'png',
                'source': 'cloud' if plan.model.startswith('cloud/') else 'local'}
        if urls: body['imageDataUrls'] = urls
        # A durable submission marker makes process death explicit, not a free retry.
        marker = directory / (str(index) + '.submitted')
        if marker.exists(): raise ValueError('Previous image submission outcome is uncertain; do not replay automatically')
        marker.write_text(job['id'] + '-' + str(index))
        data, _ = await generate_image(manager.runtime, principal, job, body, job['id'] + '-' + str(index))
        data = image_bytes(data); identifier = save_asset(root, data)
        checkpoint(target, data, {'assetId': identifier})
        accepted.append(data)
        manager._update(job['id'], 'running', result={'completed': index + 1, 'total': len(plan.steps)})
        from ai2apps.studio.repository import StudioRepository
        if job['run_id']:
            StudioRepository(manager.database).update_run(job['run_id'], **manager.scope(job), status='running',
                progress=round((index + 1) / len(plan.steps) * 90), detail=f'{index+1}/{len(plan.steps)}')
    result = await asyncio.to_thread(compose, accepted, [step.caption for step in plan.steps], plan.title, plan.columns)
    ids = [json.loads((directory / str(i) / 'result.json').read_text())['assetId'] for i in range(len(plan.steps))]
    return result, {'media_type': 'image/png', 'filename': 'sequence.png', 'model': plan.model,
                    'imageWorkflowAssets': ids, 'title': plan.title, 'imageWorkflowPrivate': not plan.publish}
