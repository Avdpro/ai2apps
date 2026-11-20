"""Sticker Workshop discovery and reuse through the standard App tool adapters."""

import asyncio
import logging
from weakref import WeakValueDictionary

from ai2apps.gallery.materials import save_artifact
from ai2apps.gallery.sticker_packs import FACING, FRAMING, STATES, StickerEntry, StickerPacks, Variant, normalize, prompt
from ai2apps.services import ToolProviderError
from ai2apps.services.aaat import principal_for
from ai2apps.workspace.materials import MaterialFile, import_materials

from .agent_providers import mini_app_handler
from .parameters import prepare
from .service import _default_image_model


from .capabilities import STICKER_GENERATE_CAPABILITY

APP = 'ai2apps.imagine-studio'
MINI = 'ai2apps.imagine.sticker-workshop'
VARIANT = {
    'background': {'enum':['white','transparent'], 'default':'white', 'description':'Transparent requires native alpha support and PNG output. Saved white and transparent variants are distinct.'},
    'state': {'enum': list(STATES)},
    'framing': {'enum': list(FRAMING)},
    'facing': {'enum': list(FACING)},
}
LABELS = {
    'background': {'zh':'背景','en':'Background'},
    'character': {'zh': '角色名称', 'en': 'Character name'},
    'pack_id': {'zh': '表情包 ID', 'en': 'Sticker pack ID'},
    'state': {'zh': '表情或状态', 'en': 'Expression or state'},
    'framing': {'zh': '取景', 'en': 'Framing'},
    'facing': {'zh': '朝向', 'en': 'Facing'},
    'model': {'zh': '绘制模型', 'en': 'Image model'},
}
OPTIONS = {
    'background': {'white':{'zh':'白底','en':'White'},'transparent':{'zh':'透明','en':'Transparent'}},
    'state': {key: {'zh': value[0], 'en': value[1]} for key, value in STATES.items()},
    'framing': {'half': {'zh': '半身', 'en': 'Waist up'}, 'full': {'zh': '全身', 'en': 'Full body'}},
    'facing': {'center': {'zh': '正面', 'en': 'Forward'}, 'left': {'zh': '朝左', 'en': 'Left'},
               'right': {'zh': '朝右', 'en': 'Right'}},
}
DECLARATION = {
    'schema': 'ai2apps.aaat-declaration/v1',
    'instructions': [
        'Use sticker.lookup first when the user wants a named character sticker. Map the '
        'requested expression and composition to the declared state, framing and facing. '
        'Use background=transparent for transparent stickers; default white is a separate variant. '
        'Leave framing and facing unset unless specified so compatible saved variants can be reused.',
        'A found sticker is ready for another image tool via materials[].artifact_id. '
        'On a missing variant, use sticker.generate only with the observed pack ID and '
        'when the request authorizes drawing. A missing or ambiguous character needs user '
        'selection or a character pack created in Sticker Workshop.',
    ],
}


def install(runtime, register, repository):
    logging.getLogger(__name__).info('Sticker Workshop AaAT adapters loaded from %s', __file__)
    locks = WeakValueDictionary()
    draw = mini_app_handler(lambda: runtime, runtime.workspace, _default_image_model, edit=True, mini_id=MINI)

    def service(context):
        principal = principal_for(runtime, context)
        return principal, StickerPacks(repository(runtime), principal.actor_user_id)

    def variant_for(args):
        return Variant.model_validate({key: args[key] for key in VARIANT if key in args})

    async def material(context, pack, match, *, status):
        item, asset, path = match

        async def resolve(_):
            return MaterialFile(asset['name'], asset['media_type'], path)

        imported = await import_materials(runtime.workspace, context.session_id, [asset['id']], resolve)
        if not imported['materials']:
            raise ToolProviderError('The sticker image became unavailable.')
        return {**imported, 'status': status, 'pack_id': pack['id'], 'sticker': item}

    async def lookup(args, context):
        _, packs = service(context)
        variant = variant_for(args)
        if args.get('pack_id'):
            pack = packs.get(args['pack_id'])
        else:
            found = [
                candidate for candidate in packs.list()
                if normalize(candidate['character']['name']) == normalize(args['character'])
            ]
            if not found:
                return {'status': 'pack_not_found'}
            if len(found) > 1:
                return {'status': 'ambiguous', 'packs': [
                    {'id': item['id'], 'name': item['character']['name'],
                     'description': item['character']['description'][:200]} for item in found[:10]
                ]}
            pack = found[0]
        match = packs.find(pack, variant, flexible=True)
        if match:
            return await material(context, pack, match, status='found')
        return {'status': 'variant_not_found', 'pack_id': pack['id'], **variant.model_dump()}

    async def generate(args, context):
        principal, packs = service(context)
        variant = variant_for(args)
        key = (principal.actor_user_id, args['pack_id'], variant.state, variant.framing, variant.facing, variant.background)
        lock = locks.setdefault(key, asyncio.Lock())
        async with lock:
            pack = packs.get(args['pack_id'])
            match = packs.find(pack, variant, flexible=True)
            if match:
                return await material(context, pack, match, status='found')
            character = pack['character']
            refs = {}
            for reference in character['references']:
                asset, path = packs.image(reference['id'])
                if asset['content_hash'] != reference['content_hash']:
                    raise ToolProviderError('A character reference was replaced. Choose or create a pack with valid references.')
                if asset['size_bytes'] > 9 * 1024 * 1024:
                    raise ToolProviderError('A character reference exceeds the image-edit reference size limit.')
                refs[asset['id']] = MaterialFile(asset['name'], asset['media_type'], path)
            if not refs:
                raise ToolProviderError('This character pack has no usable reference images.')
            values = {'prompt': prompt(variant, character), 'artifact_id': 'pending-reference'}
            if variant.background == 'transparent':
                values.update(background_mode='transparent', format='png')
            if args.get('model'):
                values['model'] = args['model']
            values = await prepare(runtime, principal, values, edit=True)

            async def resolve(identifier):
                return refs[identifier]

            imported = await import_materials(runtime.workspace, context.session_id, list(refs), resolve)
            if imported['status'] != 'completed':
                raise ToolProviderError('A character reference became unavailable.')
            reference_ids = [item['artifact_id'] for item in imported['materials']]
            values['artifact_id'] = reference_ids[0]
            result = await draw(values, context, reference_artifact_ids=reference_ids)
            artifact = result['artifact']
            asset, _ = save_artifact(packs.gallery, runtime.workspace, principal.actor_user_id,
                                     context.session_id, artifact['id'], source_app_id=APP)
            entry = StickerEntry(**variant.model_dump(), asset_id=asset['id'],
                                 description=STATES[variant.state][0])
            saved = packs.append(pack['id'], entry)
            return {**result, 'status': 'generated', 'pack_id': pack['id'], 'sticker': saved,
                    'materials': [{'source_id': asset['id'], 'artifact_id': artifact['id'],
                                   'filename': artifact['name'], 'media_type': artifact['media_type'],
                                   'size_bytes': artifact['size_bytes'], 'url': artifact['download_url']}]}

    identifier = {'type': 'string', 'minLength': 1, 'maxLength': 100}
    lookup_schema = {
        'type': 'object',
        'properties': {**VARIANT, 'character': identifier, 'pack_id': identifier},
        'required': ['state'], 'oneOf': [{'required': ['character']}, {'required': ['pack_id']}],
        'additionalProperties': False,
    }
    generate_schema = {
        'type': 'object',
        'properties': {**VARIANT, 'pack_id': identifier,
                       'model': {'type': 'string', 'minLength': 1, 'maxLength': 255}},
        'required': ['pack_id', 'state'], 'additionalProperties': False,
    }
    register('sticker.lookup', APP, '查找角色贴纸 / Find character sticker',
             'Find a saved character sticker by state and any specified framing or facing, then make it available in the current Session.',
             lookup_schema, lookup, mini=MINI, effects=('artifact.create',),
             agent_context=DECLARATION, field_labels=LABELS, option_labels=OPTIONS,
             form_summary={'zh': '查找已保存的角色贴纸，供当前会话使用。', 'en': 'Find and reuse a saved character sticker.'})
    register(STICKER_GENERATE_CAPABILITY, APP, '补绘角色贴纸 / Draw missing character sticker',
             'Reuse an exact match when available. Otherwise draw one sticker from the selected pack’s references and save it back.',
             generate_schema, generate, mini=MINI,
             effects=('network', 'ai.usage', 'workspace.write', 'artifact.create', 'write'),
             capabilities=('image.edit', 'workspace.write', 'artifact.create'),
             timeout_ms=300000, agent_context=DECLARATION, field_labels=LABELS, option_labels=OPTIONS,
             form_summary={'zh': '按角色参考图补绘缺少的状态，并存回表情包。', 'en': 'Draw a missing state from character references and save it.'})
