"""Imagine Mini-App-owned schemas and prompt composition for reference workflows."""
from copy import deepcopy
from jsonschema import Draft202012Validator
from ai2apps.services.capability_routing import ProviderIncompatible
from . import parameters

WORKFLOWS = {
    'ai2apps.imagine.group-photo': 'image.group_photo',
    'ai2apps.imagine.style-transfer': 'image.style_transfer',
    'ai2apps.imagine.reference-creation': 'image.reference_creation',
}

FORM_NAMES = {
    'ai2apps.imagine.group-photo': {'zh':'合影','en':'Group photo'},
    'ai2apps.imagine.reference-creation': {'zh':'参考图创作','en':'Reference creation'},
    'ai2apps.imagine.style-transfer': {'zh':'风格转换','en':'Style transfer'},
    'ai2apps.imagine.text-to-image': {'zh':'文生图','en':'Text to image'},
    'ai2apps.imagine.image-edit': {'zh':'修图','en':'Image editing'},
}

FORM_SUMMARIES = {
    'ai2apps.imagine.text-to-image':{'zh':'根据文字要求生成图片。','en':'Generate an image from your instructions.'},
    'ai2apps.imagine.image-edit':{'zh':'修改所选图片的内容、动作、物体或局部细节，保留未要求改变的风格与其余内容。','en':'Edit image content, actions, objects or local details; preserve the existing style and all unchanged elements.'},
    'ai2apps.imagine.group-photo': {'zh':'把多张人物、动物或角色图片合成到同一个场景，保留各自特征。','en':'Combine distinct people, animals or characters in one shared scene.'},
    'ai2apps.imagine.reference-creation': {'zh':'结合参考图片和文字要求，自由创作新的构图。','en':'Create a new composition from reference images and your instructions.'},
    'ai2apps.imagine.style-transfer': {'zh':'仅在要求改变视觉风格时使用，保留主体、动作和构图；内容或动作修改请用修图。','en':'Change visual style while preserving content, actions and composition; use image.edit for content or action changes.'},
}

WORKFLOW_DESCRIPTIONS = {
    'ai2apps.imagine.group-photo': 'Combine two or three distinct subjects (people, animals or characters) into one shared scene. Choose this for requests such as a photo of me with this panda. Collect missing subject images with this capability in app.collect_parameters; prefill all known subject IDs, background and pose. A subject image may also provide the background.',
    'ai2apps.imagine.reference-creation': 'Create a new composition inspired by reference images and a supplied prompt. For a group photo preserving two or three subjects, prefer image.group_photo. Prefill the requested creative prompt and known reference IDs before collecting missing inputs.',
    'ai2apps.imagine.style-transfer': 'Change visual style, not image content or subject actions. Use this only when the current request asks for a different visual style. Keeping an existing style while changing an action, object or local detail belongs to image.edit, even if the source came from this Tool. Prefill the source image ID and requested new style.',
}


def agent_context(mini=None):
    """Imagine owns reference selection semantics; shared AS only loads this contract."""
    instructions=[
        'Image artifacts returned by successful image operations are reusable source materials in their owning Session. Use the exact artifact.id from the result or a Generated artifact_id marker; never invent or rewrite IDs.',
        'When a user refers to an earlier generated or uploaded image, carry its known artifact ID into the declared reference field before opening app.collect_parameters. Mentioning that image only in a prompt does not attach it. If some sources are missing, prefill the known sources even when fewer than minItems, then let the user supply the rest in the form. Do not discard known sources or regenerate them just because the complete input is not ready.',
        'An unresolved user identity such as me requires their own reference photo. Do not use an animal/character source as the user photo, duplicate one ID to satisfy a minimum, or assume a source is the user. Keep explicit user source choices and removals authoritative.',
    ]
    instructions.append('Choose by the current requested change, not by the Tool that created the source: use image.edit for content, actions, objects or local changes while retaining the existing style; use image.style_transfer only for a requested change of visual style. A request to preserve the current style is not a new style-transfer request. Use the latest selected output as the source for sequential edits.')
    if mini=='ai2apps.imagine.group-photo':
        instructions.append('person_artifact_ids contains the distinct subject sources, including animals and characters, not only human portraits. For me with the panda just generated, prefill the actual panda artifact ID as one subject; ask for the missing user photo through the same form. background_artifact_id is only a scenery reference and does not replace a subject entry.')
    elif mini=='ai2apps.imagine.reference-creation':
        instructions.append('Prefill artifact_ids with the actual selected reference IDs, including already generated images referred to by the user. Preserve the creative request in prompt.')
    elif mini in ('ai2apps.imagine.style-transfer','ai2apps.imagine.image-edit'):
        instructions.append('Prefill artifact_id with the exact existing source selected by the user. Preserve the requested transformation or style; missing other parameters do not make the source unknown.')
    return {'schema':'ai2apps.aaat-declaration/v1','instructions':instructions,
        'entities':[{'type':'image_artifact','id_field':'id','label_field':'name'}],
        'result_semantics':{'artifact':'The artifact object identifies the actual output stored in the caller Session. Its id is the source reference for subsequent operations; a preview URL or a textual description is not an artifact ID.'}}

def schema(mini, base=None):
    result=deepcopy(base or parameters.base_schema());p=result['properties']
    p['prompt']={'type':'string','maxLength':16000,'default':''}
    result['required']=[]
    ref={'type':'string','minLength':1,'maxLength':256,'x-ai2apps-asset':{'storage':'artifact','accept':'image/png,image/jpeg,image/webp'}}
    if mini.endswith('group-photo'):
        p.update(person_artifact_ids={'type':'array','items':ref,'minItems':2,'maxItems':3,'uniqueItems':True},
            background_artifact_id=ref, background={'type':'string','maxLength':4000},
            atmosphere={'type':'string','maxLength':2000,'default':'natural, warm and believable'},
            pose={'type':'string','maxLength':2000,'default':'natural poses with comfortable spacing'})
        result['required']=['person_artifact_ids']
        result['anyOf']=[{'required':['background_artifact_id']},{'required':['background'],'properties':{'background':{'minLength':1}}}]
    elif mini.endswith('style-transfer'):
        p.update(artifact_id=ref,style={'type':'string','minLength':1,'maxLength':4000})
        result['required']=['artifact_id','style']
    else:
        p['artifact_ids']={'type':'array','items':ref,'minItems':1,'maxItems':4,'uniqueItems':True}
        p['prompt']={'type':'string','minLength':1,'maxLength':16000}
        result['required']=['artifact_ids','prompt']
    return result

async def describe(runtime,principal,mini,model=None):
    d=await parameters.describe(runtime,principal,True,model)
    # The workflow owns reference fields, rather than inheriting image.edit's single artifact.
    base=d['effective_schema'];base['properties'].pop('artifact_id',None)
    d['schema']=schema(mini);d['effective_schema']=schema(mini,base)
    if d.get('selection_required'):d['effective_schema']['required'].append('model')
    d['fields']=parameters.form_fields(d['effective_schema'])
    return d

async def prepare(runtime,principal,mini,arguments):
    try:
        d=await describe(runtime,principal,mini,arguments.get('model'))
        if d.get('selection_required'):raise ValueError('Model selection required; ask the user through app.collect_parameters. '+'; '.join(d['warnings']))
        values=deepcopy(arguments)
        for k,spec in d['effective_schema']['properties'].items():
            if k not in values and 'default' in spec:values[k]=deepcopy(spec['default'])
        Draft202012Validator(d['effective_schema']).validate(values)
        parameters.validate_size(values['size'],d['constraints']['size'])
        if not next(m for m in d['models'] if m['id']==values['model'])['ready']:raise ValueError('Selected model requires installation')
        return values
    except (ValueError,StopIteration) as e:raise ProviderIncompatible(str(e)) from e
    except Exception as e:
        from jsonschema import ValidationError
        if isinstance(e,ValidationError):raise ProviderIncompatible(e.message) from e
        raise

def reference_ids(mini,values):
    if mini.endswith('group-photo'):
        return list(dict.fromkeys(values['person_artifact_ids']+([values['background_artifact_id']] if values.get('background_artifact_id') else [])))
    if mini.endswith('style-transfer'):return [values['artifact_id']]
    return values['artifact_ids']

def compose(mini,values):
    if mini.endswith('group-photo'):
        count=len(values['person_artifact_ids'])
        background_id=values.get('background_artifact_id')
        if background_id in values['person_artifact_ids']:
            index=values['person_artifact_ids'].index(background_id)+1
            background_role=f'Input image {index} also supplies the background scenery. Preserve its subject exactly once alongside the other subjects; reuse its setting without duplicating its subject. '
        elif background_id:
            background_role='The last input image is the background reference. Do not treat it as a subject reference. '
        else:
            background_role=''
        return '\n\n'.join([
            'Create one natural, coherent group photograph containing every subject from the subject reference images exactly once. Preserve each subject\'s recognizable identity, facial features, apparent age, skin tone, hairstyle, and body characteristics. Keep the subjects distinct: do not merge identities, duplicate anyone, omit anyone, or introduce extra people. Make lighting, scale, perspective, shadows, eye lines, anatomy, and contact between people physically consistent.',
            f'The first {count} input images are distinct subject references (people, animals or characters), one subject per image. Preserve each subject in its own species and recognizable form.',
            background_role+'Background: '+values.get('background',''),
            'Atmosphere: '+values.get('atmosphere','natural'), 'Poses and interaction: '+values.get('pose','natural'),values.get('prompt','')])
    if mini.endswith('style-transfer'):
        return 'Transform the visual style of the reference image while preserving its subject, composition and recognizable details.\nStyle: '+values['style']+'\n'+values.get('prompt','')
    return values['prompt']
