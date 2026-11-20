"""Provider-owned image parameter negotiation; shared by inspection and execution."""
from copy import deepcopy
import re
from jsonschema import Draft202012Validator
from ai2apps.services import ToolProviderError


COMMERCE_LABELS=[('person_artifact_id','人物原图','Person reference'),('item_artifact_id','物品参考图','Item reference'),('target','提取目标','Extraction target'),('target_description','目标描述','Target description'),('interaction','交互方式','Interaction'),('pose_description','姿势描述','Pose description'),('background_description','背景描述','Background description'),('scene','场景','Scene'),('scene_description','场景描述','Scene description'),('lighting','光线','Lighting'),('composition','构图','Composition'),('setting_style','场景风格','Setting style')]
FORM_LABELS={k:{'zh':z,'en':e} for k,z,e in [('prompt','创作要求','Prompt'),('model','模型','Model'),('size','图片尺寸','Image size'),('quality','图片质量','Image quality'),('format','输出格式','Output format'),('artifact_id','源图片','Source image'),('artifact_ids','参考图片','Reference images'),('person_artifact_ids','人物、动物或角色图片','Subject images'),('background_artifact_id','背景参考图','Background reference'),('background','背景描述','Background description'),('atmosphere','氛围','Atmosphere'),('pose','姿势','Pose'),('style','目标风格','Target style')]}

FORM_LABELS['background_mode']={'zh':'背景模式','en':'Background mode'}
FORM_LABELS.update({k:{'zh':zh,'en':en} for k,zh,en in COMMERCE_LABELS})

def form_fields(schema):
    from ai2apps.agents.parameter_forms import schema_fields, present_fields
    return present_fields(schema_fields(schema),FORM_LABELS,{'quality':{k:{'zh':z,'en':e} for k,z,e in [('auto','自动','Auto'),('low','低','Low'),('medium','中','Medium'),('high','高','High'),('xhigh','极高','Extra high'),('max','最高','Maximum'),('standard','标准','Standard')]},'size':{'auto':{'zh':'自动','en':'Auto'}}})


def base_schema(edit=False):
    properties = {'prompt': {'type':'string','minLength':1,'maxLength':32000},
                  'model': {'type':'string','minLength':1},
                  'size': {'type':'string','minLength':1},
                  'quality': {'type':'string'}, 'format': {'type':'string'},
                  'background_mode': {'type':'string','enum':['auto','opaque','transparent']}}
    if edit: properties['artifact_id']={'type':'string','minLength':1,'maxLength':256,'x-ai2apps-asset':{'storage':'artifact','accept':'image/png,image/jpeg,image/webp'}}
    return {'type':'object','properties':properties,'required':['prompt']+(['artifact_id'] if edit else []),'additionalProperties':False}


def from_options(model_id, label, options, *, source='cloud', ready=True):
    return {'id':model_id,'label':label,'ready':ready,'source':source,
            'size':deepcopy(options.get('size') or {'mode':'fixed','default':'1024x1024','presets':['1024x1024','1536x1024','1024x1536']}),
            'formats':options.get('outputFormat') or ['png','jpeg','webp'],
            'qualities':options.get('quality') or ['auto'], 'backgrounds':options.get('background') or []}


async def models(runtime, principal, edit):
    from ai2apps.model_providers import list_package_models
    operation='image_edit' if edit else 'image_generation'
    result=[]
    for model in list_package_models(runtime,model_type='image_generation'):
        if operation not in model.capabilities or model.metadata.get('internal'): continue
        c=model.image_capabilities or {};g=c.get('geometry',{});d=c.get('defaults',{})
        minimum=g.get('minimum',{'width':64,'height':64});maximum=g.get('maximum',{'width':2048,'height':2048})
        ratios=[tuple(map(float,r.split(':'))) for r in g.get('ratios',['1:1'])]
        size={'mode':'bounded-custom','default':f"{d.get('width',1024)}x{d.get('height',1024)}",'presets':[],
              'width':{'min':minimum['width'],'max':maximum['width'],'multipleOf':g.get('multiple_of',1)},
              'height':{'min':minimum['height'],'max':maximum['height'],'multipleOf':g.get('multiple_of',1)},
              'maxAspectRatio':max(max(a/b,b/a) for a,b in ratios)}
        item=from_options(model.id,model.display_name,{'size':size,'outputFormat':c.get('formats',{}).get('output',['png']),
            'quality':['auto','low','medium','high']},source='local',ready=model.checkpoint_ready)
        item['referenceLimits']=c.get('inputs',{}).get('reference_images',{'minimum':1,'maximum':1})
        result.append(item)
    from ai2apps.images.byok_capabilities import byok_contract
    store=runtime.model_manager
    for m in store.enabled_cloud_models():
        contract=byok_contract(m)
        if m.get('protocol') != 'openai' or operation not in contract['capabilities']: continue
        item=from_options(m['gateway_id'],m.get('name') or m['id'],contract['imageOptions'],source='byok')
        item['referenceLimits']=contract['referenceLimits']
        result.append(item)
    warnings=[f"{m['id']}: custom size is forwarded for provider validation; no verified model-specific geometry contract is available. Local limits are transport safety bounds, not provider capability claims."
              for m in result if m['size'].get('validation') == 'provider']
    cloud=getattr(runtime,'cloud',None)
    if cloud:
        try:
            response=await cloud.request('GET','/v1/ai/models',headers=runtime.cloud_ai_authorization_headers(principal))
            try:
                response.raise_for_status()
                for m in response.json().get('items',[]):
                    caps=m.get('capabilities',{})
                    if not caps.get('imageEdit' if edit else 'imageGeneration'): continue
                    result.append(from_options('cloud/ai2apps/'+m['id'],m.get('displayName') or m['id'],m.get('imageOptions',{})))
            finally: await response.aclose()
        except Exception:
            warnings.append('Cloud model catalog unavailable; select an available model or retry when the catalog recovers.')
    return result,warnings


def effective_schema(model, edit=False):
    schema=base_schema(edit);p=schema['properties'];p['model']={'const':model['id'],'default':model['id'],'type':'string'}
    size=model['size'];p['size']={'type':'string','default':size.get('default','1024x1024')}
    if size.get('mode')=='fixed':p['size']['enum']=list(size.get('presets',[]))+(['auto'] if size.get('auto') else [])
    else:p['size']['pattern']=r'^(auto|[1-9][0-9]*x[1-9][0-9]*)$' if size.get('auto') else r'^[1-9][0-9]*x[1-9][0-9]*$'
    p['quality']={'enum':model['qualities'],'default':model['qualities'][0]}
    p['format']={'enum':model['formats'],'default':model['formats'][0]}
    if model.get('backgrounds'):
        p['background_mode']={'type':'string','enum':model['backgrounds']}
    else:
        p.pop('background_mode',None)
    return schema


def validate_size(value, constraint):
    if value=='auto' and constraint.get('auto'):return
    match=re.fullmatch(r'([1-9][0-9]*)x([1-9][0-9]*)',value)
    if not match:raise ValueError('Invalid image size')
    w,h=map(int,match.groups())
    if constraint.get('mode')=='fixed':
        if value not in constraint.get('presets',[]):raise ValueError('Size not supported by selected model')
        return
    for key,n in [('width',w),('height',h)]:
        bounds=constraint.get(key,{})
        if n<bounds.get('min',1) or n>bounds.get('max',16384):raise ValueError(f"{key} must be between {bounds.get('min',1)} and {bounds.get('max',16384)} pixels")
        if n%bounds.get('multipleOf',1):raise ValueError(f"{key} must be a multiple of {bounds.get('multipleOf',1)}")
    pixels=w*h
    if pixels<constraint.get('minPixels',1) or pixels>constraint.get('maxPixels',268435456):raise ValueError(f"Pixel count must be between {constraint.get('minPixels',1)} and {constraint.get('maxPixels',268435456)}")
    if max(w/h,h/w)>constraint.get('maxAspectRatio',float('inf')):raise ValueError(f"Long/short edge ratio must not exceed {constraint['maxAspectRatio']}:1")


async def describe(runtime, principal, edit=False, model_id=None):
    from ai2apps.images.service import _default_image_model
    choices,warnings=await models(runtime,principal,edit)
    from ai2apps.model_preferences import choose, scope
    from ai2apps.task_llm import effective_profile
    profile=effective_profile(runtime)
    # Resolve the actual system fallback independently of the remembered route.
    # The operation catalog below is the fresh authority for model readiness.
    with scope(None,profile=profile):
        default=(runtime.model_manager.resolve_default_model('image_generation',profile='privacy')
                 if profile=='privacy' else _default_image_model(runtime.model_manager))
    selected, selection=choose(runtime,'image_generation',default,explicit=model_id,choices=choices,profile=profile)
    selected=selected or ''
    model=next((m for m in choices if m['id']==selected),None)
    # Legacy Cloud defaults omit the account-route segment. Match exactly the
    # same model using the gateway's existing routing rule, never another model.
    if model is None and selected.startswith('cloud/') and not selected.startswith('cloud/ai2apps/'):
        provider_id=selected.split('/',2)[1]
        local=next((p for p in runtime.model_manager.list_cloud() if p['id']==provider_id),None)
        if local is None or not local['configured']:
            canonical='cloud/ai2apps/'+selected[len('cloud/'):]
            model=next((m for m in choices if m['id']==canonical),None)
    if model is None or not model['ready']:
        schema=base_schema(edit)
        schema['properties']['model']={'type':'string','enum':[m['id'] for m in choices if m['ready']]}
        schema['required'].append('model')
        reason='Configured or selected model is unavailable or does not support this operation: '+selected
        return {'install':{'appId':'ai2apps.imagine-studio','capability':'image.edit' if edit else 'image.generation','requirements':{'operations':['image_edit' if edit else 'image_generation']}},'version':1,'schema':base_schema(edit),'models':choices,'model':None,
            'effective_schema':schema,'fields':form_fields(schema),'constraints':{},'model_selection':selection,'selection_required':True,
            'warnings':warnings+[reason]}

    return {'install':{'appId':'ai2apps.imagine-studio','capability':'image.edit' if edit else 'image.generation','requirements':{'operations':['image_edit' if edit else 'image_generation']}},'version':1,'schema':base_schema(edit),'models':choices,'model':model['id'],
            'effective_schema':effective_schema(model,edit),'fields':form_fields(effective_schema(model,edit)),'constraints':{'size':model['size']},'model_selection':selection,'warnings':warnings}


async def prepare(runtime, principal, arguments, edit=False):
    from ai2apps.services.capability_routing import ProviderIncompatible
    try:
        descriptor=await describe(runtime,principal,edit,arguments.get('model'))
    except ValueError as error:raise ProviderIncompatible(str(error)) from error
    if descriptor.get('selection_required'):
        raise ProviderIncompatible('Model selection required. Use app.collect_parameters with the current capability and known values; ask the user to select a model. '+ '; '.join(descriptor['warnings']))
    values=deepcopy(arguments)
    for key,p in descriptor['effective_schema']['properties'].items():
        if key not in values and 'default' in p:values[key]=deepcopy(p['default'])
    try:
        from ai2apps.images.background import validate_background
        selected_model=next(m for m in descriptor['models'] if m['id']==values['model'])
        validate_background(values.get('background_mode'), values['format'], selected_model.get('backgrounds',[]))
        Draft202012Validator(descriptor['effective_schema']).validate(values)
        validate_size(values['size'],descriptor['constraints']['size'])
    except ValueError as error:raise ProviderIncompatible(str(error)) from error
    except Exception as error:
        from jsonschema import ValidationError
        if isinstance(error,ValidationError):raise ProviderIncompatible(error.message) from error
        raise
    selected=next(m for m in descriptor['models'] if m['id']==values['model'])
    if not selected['ready']:raise ProviderIncompatible('Selected model requires installation')
    return values
