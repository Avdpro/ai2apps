"""Imagine-owned portable settings, excluding prompts, materials and executions."""
from ai2apps.apps.app_state import StateContract

APP='ai2apps.imagine-studio'
MINI='ai2apps.imagine.style-transfer'
MINIS=(MINI,'ai2apps.imagine.text-to-image','ai2apps.imagine.image-edit','ai2apps.imagine.reference-creation','ai2apps.imagine.group-photo','ai2apps.imagine.extract-items','ai2apps.imagine.try-on','ai2apps.imagine.product-poster','ai2apps.imagine.character-design')


def field(type,**values):return {'type':type,'x-app-state':'portable',**values}


def register(service):
    layout={'left_panel':field('string',enum=['mini-apps','assets']),
            'left_collapsed':field('boolean'),'right_collapsed':field('boolean')}
    style={'model_id':field('string',minLength=1,maxLength=256,pattern=r'^[A-Za-z0-9][A-Za-z0-9._/-]*$'),
           'style_id':field('string',maxLength=100,pattern=r'^[a-z0-9._-]*$'),
           'width':field(['integer','null'],minimum=64,maximum=8192),'height':field(['integer','null'],minimum=64,maximum=8192),
           'quality':field('string',minLength=1,maxLength=32,pattern=r'^[A-Za-z0-9._-]+$'),
           'format':field('string',enum=['png','jpeg','webp'])}
    for mini,name,props in [(None,'Imagine Studio layout',layout),*((mini,'Image settings',style) for mini in MINIS)]:
        service.register(StateContract(APP,mini,1,name,{'type':'object','properties':props,'required':list(props),'additionalProperties':False,**({'oneOf':[{'properties':{'width':{'type':'integer'},'height':{'type':'integer'}}},{'properties':{'width':{'type':'null'},'height':{'type':'null'}}}]} if mini else {})},
            excluded_fields=('prompt','referenceFiles','assetReferences','run_id','parameterHandoffInteractionId','credentials','permissions')))


    conversation = {
        'theme': field('string', enum=['wechat','whatsapp','telegram','imessage']),
        'ratio': field('string', enum=['9:16','3:4','16:9']),
        'status_os': field('string', enum=['ios','samsung']),
        'composer_mode': field('string', enum=['text','voice']),
        'battery': field('integer', minimum=0, maximum=100),
        'interval': field('number', enum=[0.5,1,1.5,2,2.5,3]),
    }
    service.register(StateContract(APP,'ai2apps.imagine.fantasy-feed',1,'Fantasy Feed settings',
        {'type':'object','properties':conversation,'required':list(conversation),'additionalProperties':False},
        clients=('desktop',), excluded_fields=('participants','profiles','avatars','messages','title','footerText','start','clock')))

    from ai2apps.images.comic_translation import LANGUAGES, MINI_ID
    comic = {
        'language': field('string', enum=list(LANGUAGES)),
        'direction': field('string', enum=['auto', 'vertical', 'horizontal']),
        'model_id': field('string', maxLength=255),
        'profile': field('string', maxLength=80),
        'auto_crop': field('boolean'),
        'page_context': field('boolean'),
    }
    service.register(StateContract(APP, MINI_ID, 1, 'Comic Translation settings',
        {'type':'object','properties':comic,'required':list(comic),'additionalProperties':False},
        excluded_fields=('pages', 'regions', 'translations', 'glossary', 'runs')))

    service.register(StateContract(APP,'ai2apps.imagine.comic-studio',1,'Comic Studio settings',
        {'type':'object','properties':{'model_id':field('string',maxLength=255),
         'ratio':field('string',enum=['1:1','4:3','3:4','16:9','9:16']),
         'panel_count':field('integer',minimum=2,maximum=6),
         'previous':field('integer',minimum=0,maximum=2)},
         'required':['model_id','ratio','panel_count','previous'],'additionalProperties':False},
        excluded_fields=('series','characters','panels','prompt','references','episodes','schedule','runs')))
