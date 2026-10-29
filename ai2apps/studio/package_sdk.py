"""Native Studio SDK protocols; no Mini-App identities or public Tool schemas.

Package declarations select a supported typed SDK operation. SDK implementation
modules are imported only on a call/description for an installed binding.
"""
from ai2apps.packages.mini_app_exports import HostProtocol

VOICE='ai2apps.readaloud'
VIDEO='ai2apps.video-studio'
IMAGINE='ai2apps.imagine-studio'

async def audio(runtime,args,context,mini,spec):
    from .package_generation_aaat import audio as generate
    capability=spec['options'].get('capability')
    if capability not in mini.get('requirements',{}).get('capabilities',[]):
        raise ValueError('SDK operation is not required by this Mini-App')
    return await generate(runtime,args,context,mini['id'],capability)

async def audio_descriptor(runtime,principal,model,mini,spec):
    from .audio_generation import generation_models
    models=generation_models(runtime,spec['options'].get('capability'))
    return {'models':[{'id':m.id,'label':m.display_name,'ready':m.checkpoint_ready} for m in models],
        'configuration_required':not any(m.checkpoint_ready for m in models),
        'install':{'appId':spec['host'],'capability':spec['options'].get('capability'),'requirements':{}}}

async def avatar(runtime,args,context,mini,spec):
    from .package_generation_aaat import avatar as generate
    return await generate(runtime,args,context,mini_app_id=mini['id'])

async def avatar_descriptor(runtime,principal,model,mini,spec):
    from .package_generation_aaat import avatar_descriptor as describe
    return await describe(runtime,principal,model)

async def camera(runtime,args,context,mini,spec):
    from .package_generation_aaat import frozen
    return await frozen(runtime,args,context,mini_app_id=mini['id'])

async def camera_descriptor(runtime,principal,model,mini,spec):
    from .package_generation_aaat import frozen_descriptor
    return await frozen_descriptor(runtime,principal,model)

async def media(runtime,args,context,mini,spec):
    from .voice_aaat import execute
    mode=spec['options'].get('mode')
    if mode not in ('separate','replace_audio','replace_video'):raise ValueError('Unsupported SDK media operation')
    return await execute(runtime,args,context,replacement=mode!='separate',video=mode=='replace_video',host_app=spec['host'],mini_app_id=mini['id'])

async def media_descriptor(runtime,principal,model,mini,spec):
    from .voice_aaat import descriptor
    return await descriptor(runtime,principal,replacement=spec['options'].get('mode')!='separate')

async def dub(runtime,args,context,mini,spec):
    from .video_localization_aaat import dub
    return await dub(runtime,args,context,mini_app_id=mini['id'])

async def dub_descriptor(runtime,principal,model,mini,spec):
    from .video_localization_aaat import descriptor
    return await descriptor(runtime,principal,model)

async def subtitles(runtime,args,context,mini,spec):
    from .subtitle_aaat import execute
    return await execute(runtime,args,context,mini_app_id=mini['id'])

async def subtitle_descriptor(runtime,principal,model,mini,spec):
    from .subtitle_aaat import descriptor
    return await descriptor(runtime,principal,model)

async def transcription(runtime,args,context,mini,spec):
    from ai2apps.services.builtin_apps import detailed_transcription
    return await detailed_transcription(runtime,args,context,host_app=spec['host'],mini_app_id=mini['id'])

async def transcription_descriptor(runtime,principal,model,mini,spec):
    from .capability_broker import StudioCapabilityBroker
    broker=StudioCapabilityBroker(runtime)
    return {'configuration_required':not any(broker._detailed_model_for_profile(p) for p in ('compact','quality')),
        'install':{'appId':spec['host'],'capability':'audio.detailed_transcription','requirements':{}}}

def install(binder):
    for key,hosts,execute,describe in (
        ('studio.audio-generation/v1',(VOICE,),audio,audio_descriptor),
        ('studio.talking-portrait/v1',(VIDEO,),avatar,avatar_descriptor),
        ('studio.camera-motion/v1',(IMAGINE,),camera,camera_descriptor),
        ('studio.media-audio/v1',(VOICE,VIDEO),media,media_descriptor),
        ('studio.narration-translation/v1',(VIDEO,),dub,dub_descriptor),
        ('studio.video-subtitles/v1',(VIDEO,),subtitles,subtitle_descriptor),
        ('studio.detailed-transcription/v1',(VOICE,VIDEO),transcription,transcription_descriptor)):
        binder.register_protocol(HostProtocol(key,hosts,execute,describe,effects=('artifact.create',),timeout_ms=86400000))
