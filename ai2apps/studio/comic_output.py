"""Publish comic pages from the editor or the Agent through shared Studio Output."""
import json

from ai2apps.images.comic_translation import MINI_ID, load_image
from ai2apps.studio.repository import StudioRepository

MAX_PAGES = 50
MAX_OUTPUT = 64 * 1024 * 1024


def stage_page(directory, index, data, format):
    size = None
    if format == 'png':
        if not data.startswith(b'\x89PNG\r\n\x1a\n'):
            raise ValueError('Expected a PNG image')
        image = load_image(data)
        size = f'{image.width}x{image.height}'
    elif not data.startswith(b'<!doctype html>') or b'ai2apps-comic-reader/v1' not in data[:2048]:
        raise ValueError('Expected an offline comic reader')
    path = directory / str(index)
    path.mkdir()
    (path / 'output').write_bytes(data)
    metadata = {
        'kind': 'image' if format == 'png' else 'file',
        'format': format, 'size': size,
        'filename': f'comic-{index:02d}.png' if format == 'png' else 'comic-reader.html',
        'media_type': 'image/png' if format == 'png' else 'application/octet-stream',
    }
    (path / 'result.json').write_text(json.dumps(metadata))
    return path


def publish_comic(runtime, mini, binding, staged, format):
    repo = StudioRepository(runtime.database)
    title = 'Comic pages' if format == 'png' else 'Comic reader'
    run = repo.create_run(mini_app_id=MINI_ID, mini_app_version=mini['version'], placement='inline', title=title,
                          input_data={'format': format}, step_label='Export comic', **binding)
    job = {**binding, 'id': run['id'], 'mini_app_id': MINI_ID, 'kind': 'comic-export', 'run_id': run['id']}
    repo.update_run(run['id'], status='running', progress=90, **binding)
    try:
        outputs = [runtime.studio_jobs.publish(job, path, output_key=f"{job['id']}-{index}",
                                              complete=index == len(staged) - 1)
                   for index, path in enumerate(staged)]
    except Exception:
        repo.update_run(run['id'], status='failed', progress=90, detail='Comic export failed', **binding)
        raise
    return run['id'], outputs
