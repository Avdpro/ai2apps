"""Desktop-backed Chat speech through the shared model invocation boundary."""
from fastapi import HTTPException
from fastapi.responses import Response
from ai2apps.model_providers import list_package_models
from ai2apps.model_invocation import ModelInvocationContext, ModelInvocationError
from ai2apps.readaloud.speech import invoke_speech

CONFIGURE = 'Desktop 没有可用的 TTS 模型，请在 Desktop 安装并配置语音合成模型后重试。'


async def synthesize(runtime, principal, thread, text):
    models = [m for m in list_package_models(runtime) if m.model_type=='audio_tts' and m.checkpoint_ready]
    if not models or not getattr(runtime,'model_invocations',None):
        raise HTTPException(409, CONFIGURE)
    # Only installed Desktop providers, never a client-selected endpoint or model.
    model = models[0]
    payload = {'model':model.id,'input':text.strip(),'response_format':'wav'}
    voices = (model.audio_capabilities or {}).get('tts',{}).get('named_voices',{}).get('voices',[])
    if voices:payload['voice']=voices[0]
    context = ModelInvocationContext.from_principal(principal,session_id=thread.session.id,
        app_instance_id=thread.session.app_instance_id,consumer_app_id='ai2apps.general-chat')
    try:
        result=await invoke_speech(runtime.model_invocations.invoke_foreground_json,model.id,'audio_speech',payload,context=context)
    except (ModelInvocationError,ValueError) as error:
        raise HTTPException(503,'Desktop TTS 暂不可用，请在 Desktop 检查语音合成模型配置。') from error
    if result.status_code>=400:
        raise HTTPException(503,'Desktop TTS 生成失败，请在 Desktop 检查模型和音色配置。')
    if not result.body or len(result.body)>32*1024*1024:
        raise HTTPException(502,'Desktop TTS 返回了无效音频。')
    return Response(result.body,media_type='audio/wav',headers={'Cache-Control':'no-store'})
