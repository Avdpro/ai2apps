"""Import owner-resolved files into the current Session's artifact store."""
from contextlib import nullcontext
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from ai2apps.workspace.models import WorkspaceError


MATERIAL_INPUT = {
    'type': 'object',
    'properties': {
        'source_ids': {
            'type': 'array', 'minItems': 1, 'maxItems': 8, 'uniqueItems': True,
            'items': {'type': 'string', 'minLength': 1, 'maxLength': 256},
        },
    },
    'required': ['source_ids'],
    'additionalProperties': False,
}
MAX_BATCH_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True)
class MaterialFile:
    name: str
    media_type: str
    content: Path | bytes


async def import_materials(workspace, session_id, source_ids, resolve):
    """Resolve one item at a time through the caller's trusted owner adapter."""
    materials, unavailable = [], []
    remaining = MAX_BATCH_BYTES
    for source_id in source_ids:
        if remaining == 0:
            unavailable.append({'source_id': source_id, 'reason': 'size_limit'})
            continue
        material = await resolve(source_id)
        if isinstance(material, str):
            unavailable.append({'source_id': source_id, 'reason': material})
            continue
        path = material.content
        staging = TemporaryDirectory(prefix='ai2apps-material-') if isinstance(path, bytes) else nullcontext()
        with staging as directory:
            try:
                size = len(path) if isinstance(path, bytes) else path.stat().st_size
                if size > remaining:
                    unavailable.append({'source_id': source_id, 'reason': 'size_limit'})
                    continue
                if isinstance(path, bytes):
                    path = Path(directory) / 'material'
                    path.write_bytes(material.content)
                artifact = workspace.import_artifact(
                    session_id, path, name=material.name, media_type=material.media_type,
                )
            except (FileNotFoundError, WorkspaceError) as error:
                if isinstance(error, WorkspaceError) and error.code != 'not_file':
                    raise
                unavailable.append({'source_id': source_id, 'reason': 'unavailable'})
                continue
        remaining -= size
        materials.append({
            'source_id': source_id, 'artifact_id': artifact.id,
            'filename': artifact.name, 'media_type': artifact.media_type,
            'size_bytes': artifact.size_bytes,
            'url': f'/v1/platform/sessions/{session_id}/artifacts/{artifact.id}/download',
        })
    return {
        'status': ('partial' if materials else 'unavailable') if unavailable else 'completed',
        'materials': materials, 'unavailable': unavailable,
    }
