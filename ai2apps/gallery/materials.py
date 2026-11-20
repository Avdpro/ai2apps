"""Gallery-owned source resolution for Session material handoff."""
import json

from ai2apps.core import ResourceNotFoundError
from ai2apps.gallery import GalleryError
from ai2apps.gallery.repository import STICKER_PACK_MIME
from ai2apps.gallery.sticker_packs import StickerPacks
from ai2apps.services.aaat import principal_for
from ai2apps.workspace.materials import MATERIAL_INPUT, MaterialFile, import_materials
from ai2apps.config import DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES


def save_artifact(repository, workspace, owner, session_id, artifact_id, *, name=None,
                  description=None, collection_id=None, source_app_id=None):
    """Same owner operation for the Gallery UI and AaAT; no paths from callers."""
    artifact = workspace.get_artifact(session_id, artifact_id)
    with workspace.artifact_path(artifact).open('rb') as stream:
        return repository.import_stream(
            owner, stream, name=artifact.name if name is None else name, media_type=artifact.media_type,
            description=description,
            collection_id=collection_id, source_app_id=source_app_id, source_ref=artifact.uri,
            metadata={'artifact_id': artifact.id, 'artifact_session_id': artifact.session_id,
                      'artifact_run_id': artifact.run_id},
            max_bytes=DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES,
        )


def install(runtime, register, repository):
    from ai2apps.gallery.character_tools import install as install_characters
    install_characters(runtime,register,repository)
    async def character_definitions(args, context):
        from ai2apps.gallery.characters import Characters
        items=Characters(repository(runtime),principal_for(runtime,context).actor_user_id).definitions()
        if args.get('character_id'):items=[item for item in items if item['id']==args['character_id']]
        return {'items':items}

    register(
        'gallery.character_definitions','ai2apps.gallery','引用角色形象 / Reusable character appearances',
        'List owned finalized character appearances for Apps, Mini-Apps and Bots. Each appearance contains '
        'exactly one definition_image_id (Gallery asset ID) and summary text. Use both together to preserve '
        'the chosen identity. Import the image with gallery.import_materials when another capability needs '
        'a Session image artifact. Does not return authoring reference images or generated history. '
        'No generation or user confirmation is performed; unfinished or unavailable definitions are omitted.',
        {'type':'object','properties':{'character_id':{'type':'string','minLength':1,'maxLength':100}},'additionalProperties':False},
        character_definitions,effects=('read',),provider_version='1',
        field_labels={'character_id':{'zh':'角色 ID（可选）','en':'Character ID (optional)'}},
        form_summary={'zh':'查询已定稿形象的定义图和说明，不生成图片。','en':'Read finalized definition images and guides without generation.'},
    )

    async def execute(args, context):
        owner = principal_for(runtime, context).actor_user_id
        gallery = repository(runtime)

        async def resolve(asset_id):
            try:
                asset, path = gallery.asset_path(owner, asset_id)
            except (ResourceNotFoundError, FileNotFoundError, GalleryError):
                return 'unavailable'
            if asset['status'] != 'active':
                return 'unavailable'
            if asset['media_type'] == STICKER_PACK_MIME:
                try:
                    manifest = StickerPacks.manifest(asset)
                except GalleryError:
                    return 'unavailable'
                return MaterialFile(asset['name'], STICKER_PACK_MIME,
                                    json.dumps(manifest, ensure_ascii=False).encode())
            return MaterialFile(asset['name'], asset['media_type'], path)

        return await import_materials(runtime.workspace, context.session_id, args['source_ids'], resolve)

    register(
        'gallery.import_materials', 'ai2apps.gallery', '导入素材 / Import Gallery materials',
        'Copy owned Gallery files into the current Session for another capability to use. '
        'Pass observed asset IDs from Gallery search or metadata. Supports images, audio, video, '
        'documents and other local files. Use the returned materials[].artifact_id and media_type.',
        MATERIAL_INPUT, execute, effects=('artifact.create',),
        field_labels={'source_ids': {'zh': '素材 ID', 'en': 'Asset IDs'}},
        form_summary={'zh': '将已有素材导入当前会话，供其它能力使用。', 'en': 'Import owned Gallery materials into the current Session.'},
    )

    async def save(args, context):
        owner = principal_for(runtime, context).actor_user_id
        asset, created = save_artifact(repository(runtime), runtime.workspace, owner,
                                      context.session_id, args['artifact_id'],
                                      name=args.get('name'), description=args.get('description'))
        return {'status': 'completed', 'created': created,
                'asset': {k: asset[k] for k in ('id', 'name', 'description', 'media_type', 'size_bytes', 'status')},
                'view': 'recent'}

    register(
        'gallery.save_material', 'ai2apps.gallery', '保存到素材库 / Save to Gallery',
        'Persist one actual artifact from the current owned Session into Gallery. '
        'Supports images, audio, video, documents and other files. Pass the artifact ID '
        'returned by the producing step. Saved assets appear in Recent, a virtual view, '
        'not a folder that needs creation. Optional name is the filename (keep its extension); '
        'omitting name preserves the artifact filename. Optional description is plain text, at most 4000 characters. '
        'Same owner, content and name reuse the existing asset without overwriting its description; '
        'the returned asset contains the actual saved name and description. '
        'This saves Session output to Gallery; import_materials does the reverse.',
        {'type': 'object', 'properties': {'artifact_id': {'type': 'string', 'minLength': 1,
         'maxLength': 256, 'x-ai2apps-asset': {'storage': 'artifact'}},
         'name': {'type': 'string', 'minLength': 1, 'maxLength': 512, 'description': 'Optional filename including extension; omitted uses artifact name.'},
         'description': {'type': 'string', 'maxLength': 4000, 'description': 'Plain-text asset description; omitted defaults to empty for new assets.'}},
         'required': ['artifact_id'], 'additionalProperties': False},
        save, effects=('write',), provider_version='2',
        field_labels={'artifact_id': {'zh': '会话产物 ID', 'en': 'Session artifact ID'},
                      'name': {'zh': '素材名称', 'en': 'Asset filename'},
                      'description': {'zh': '素材说明', 'en': 'Description'}},
        form_summary={'zh': '将当前会话的实际产物保存到素材库。', 'en': 'Save an actual Session artifact to Gallery.'},
    )
