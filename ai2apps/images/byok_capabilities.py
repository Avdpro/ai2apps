"""Image API contracts shared by discovery, Studio and the BYOK adapter.

Do not infer a new model version's geometry from the ``gpt-image-`` prefix.
The reference-image maximum is our current transport limit, not a vendor limit.
"""
from copy import deepcopy
import re


def model_name(model_id):
    # Compatible gateways can namespace IDs. Preserve the full ID on the wire.
    return model_id.lower().rsplit('/', 1)[-1]


def image_options(model_id):
    name = model_name(model_id)
    gpt = name.startswith('gpt-image-') or name == 'chatgpt-image-latest'
    flexible = bool(re.fullmatch(r'gpt-image-(?:2|2\.[56]-(?:flare|sunburst))(?:-\d{4}-\d{2}-\d{2})?', name))
    enhanced = bool(re.fullmatch(r'gpt-image-2\.[56]-(?:flare|sunburst)(?:-\d{4}-\d{2}-\d{2})?', name))
    size = {'mode': 'fixed', 'default': '1024x1024', 'auto': gpt,
            'presets': ['1024x1024', '1536x1024', '1024x1536'] if gpt else ['1024x1024']}
    known = gpt and (flexible or bool(re.fullmatch(r'gpt-image-1(?:\.5|-mini)?(?:-\d{4}-\d{2}-\d{2})?', name)) or name == 'chatgpt-image-latest')
    if not known and name not in ('dall-e-2', 'dall-e-3'):
        # Unknown compatible gateways must validate their own geometry. A guessed
        # square-only limit must never become evidence that 4:3 is unsupported.
        size = {'mode': 'bounded-custom', 'default': '1024x1024', 'auto': False,
                'presets': ['1024x1024'], 'validation': 'provider',
                'width': {'min': 1, 'max': 16384, 'multipleOf': 1},
                'height': {'min': 1, 'max': 16384, 'multipleOf': 1},
                'minPixels': 1, 'maxPixels': 268435456, 'maxAspectRatio': 16384,
                'experimentalAbovePixels': 268435456}
    if flexible:
        size.update(mode='bounded-custom', width={'min': 16, 'max': 3840, 'multipleOf': 16},
                    height={'min': 16, 'max': 3840, 'multipleOf': 16},
                    minPixels=655360, maxPixels=8294400, maxAspectRatio=3,
                    experimentalAbovePixels=3686400)
        size['presets'] += ['1536x1152', '1152x1536']
    if name == 'dall-e-2':
        size['presets'] = ['256x256', '512x512', '1024x1024']
    elif name == 'dall-e-3':
        size['presets'] = ['1024x1024', '1792x1024', '1024x1792']
    return {'size': size, 'background': ['auto', 'opaque', 'transparent'] if known else [],
            'quality': (['auto', 'low', 'medium', 'high'] + (['xhigh', 'max'] if enhanced else [])) if gpt
                       else (['standard', 'hd'] if name == 'dall-e-3' else ['standard']),
            'outputFormat': ['png', 'jpeg', 'webp'] if gpt else ['png']}


def byok_contract(model):
    from ai2apps.model_capabilities import cloud_model_capabilities
    caps = cloud_model_capabilities(model)
    name = str(model.get('id') or model.get('model_id') or '')
    operations = [op for op in ('image_generation', 'image_edit') if op in caps]
    if model_name(name) == 'dall-e-3':
        operations = [op for op in operations if op != 'image_edit']
    return {'imageOptions': deepcopy(image_options(name)), 'capabilities': operations,
            'referenceLimits': {'minimum': 1, 'maximum': 1 if model_name(name) == 'dall-e-2' else 4}}


def validate_request(model_id, payload, *, edit):
    from ai2apps.images.parameters import validate_size
    options = image_options(model_id)
    if edit and model_name(model_id) == 'dall-e-3':
        raise ValueError('dall-e-3 does not support image editing')
    validate_size(str(payload.get('size') or options['size']['default']), options['size'])
    quality = str(payload.get('quality') or options['quality'][0])
    output = str(payload.get('outputFormat') or options['outputFormat'][0])
    if quality not in options['quality']:
        raise ValueError('Quality not supported by selected model: ' + quality)
    if output not in options['outputFormat']:
        raise ValueError('Output format not supported by selected model: ' + output)
    if payload.get('outputCompression') is not None and output not in ('jpeg', 'webp'):
        raise ValueError('Output compression requires jpeg or webp')
    from ai2apps.images.background import validate_background
    validate_background(payload.get('background'), output, options['background'])
    return options
