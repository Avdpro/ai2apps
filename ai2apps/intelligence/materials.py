"""Import the reading preview of a saved article's owner-resolved cover."""
from fastapi import HTTPException

from ai2apps.services.aaat import principal_for
from ai2apps.workspace.materials import MATERIAL_INPUT, MaterialFile, import_materials

from .images import load_article_thumbnail


def install(runtime, register, store, app_id):
    async def execute(args, context):
        owner = principal_for(runtime, context).actor_user_id
        database = store(runtime)

        async def resolve(article_id):
            try:
                article = database.get('articles', owner, article_id)
            except KeyError:
                return 'unavailable'
            try:
                data, media_type = await load_article_thumbnail(article)
            except HTTPException as error:
                if error.status_code in (422, 502):
                    return 'no_supported_cover' if error.status_code == 422 else 'source_unavailable'
                raise
            return MaterialFile(f'{article_id}-cover.jpg', media_type, data)

        return await import_materials(runtime.workspace, context.session_id, args['source_ids'], resolve)

    register(
        'intelligence.import_materials', app_id, '导入文章封面 / Import article covers',
        'Import reading-size cover previews of owned saved articles into the current Session. '
        'Pass observed article IDs from saved news or search. Use materials[].artifact_id as an image '
        'reference for downstream capabilities. Reports unavailable covers separately.',
        MATERIAL_INPUT, execute, effects=('network', 'external_read', 'artifact.create'),
        timeout_ms=120000, field_labels={'source_ids': {'zh': '文章 ID', 'en': 'Article IDs'}},
        form_summary={'zh': '将已保存文章的封面预览导入当前会话。', 'en': 'Import saved article cover previews into the current Session.'},
    )
