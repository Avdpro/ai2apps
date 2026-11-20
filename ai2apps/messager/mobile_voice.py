"""Owner-scoped Mobile media adapter for the same Bot voice and task services."""
import asyncio
import json
from fastapi import HTTPException
from fastapi.responses import Response
from ai2apps.audio_codecs import decode_audio_to_wav, infer_audio_format
from ai2apps.model_invocation import ModelInvocationContext, ModelInvocationError
from ai2apps.model_providers import list_package_models
from ai2apps.readaloud.speech import invoke_speech

MAX_AUDIO = 4 * 1024 * 1024


def catalog(runtime, principal, bot_id):
    runtime.messager_bots.scope(principal.actor_user_id, {'bot_id':bot_id})
    result={'stt':[], 'tts':[]}
    for m in list_package_models(runtime):
        if m.model_type not in ('audio_stt','audio_tts') or not m.checkpoint_ready or getattr(m,'is_hidden',False):continue
        result['stt' if m.model_type=='audio_stt' else 'tts'].append({'id':m.id,'name':m.display_name,
            'voices':((getattr(m,'audio_capabilities',None) or {}).get('tts',{}).get('named_voices',{}).get('voices',[]))})
    return result


def settings(runtime, principal, bot_id, sid, voice_id=None, controller=None):
    owner=runtime.messager_dialogue.realtime
    runtime.messager_dialogue.realtime_inputs._scope(principal,bot_id,sid)
    if voice_id:
        row=owner._session(principal,bot_id,voice_id,controller)
        if row['session_id']!=sid:raise PermissionError('Voice conversation unavailable')
        return json.loads(row['config_json'])
    return owner.get(principal.actor_user_id,bot_id)


def context(runtime, principal, sid):
    binding=runtime.app_chat.access(principal,sid)
    return ModelInvocationContext.from_principal(principal,session_id=sid,
        app_instance_id=binding.get('app_instance_id'),consumer_app_id='ai2apps.messager')


async def transcribe(runtime, principal, bot_id, sid, upload, voice_id=None, controller=None):
    config=settings(runtime,principal,bot_id,sid,voice_id,controller)
    choices=catalog(runtime,principal,bot_id)['stt']
    model=config.get('stt_model_id') or (choices[0]['id'] if choices else None)
    if not model or not any(m['id']==model for m in choices):raise HTTPException(409,'Install and configure a speech recognition model on Desktop')
    data=await upload.read(MAX_AUDIO+1)
    if not data or len(data)>MAX_AUDIO:raise HTTPException(413,'Recording must be under 4 MiB')
    try:
        wav=await asyncio.to_thread(decode_audio_to_wav,data,input_format=infer_audio_format(upload.filename,upload.content_type),sample_rate=16000,max_duration_seconds=30)
        response=await runtime.model_invocations.invoke_foreground_multipart(model,'audio_transcription',
            data={'response_format':'json','stream':'false'},files={'file':('speech.wav',wav,'audio/wav')},context=context(runtime,principal,sid))
        if response.status_code>=400:raise HTTPException(503,'Speech recognition failed; recording retained for retry')
        value=json.loads(response.body);text=value.get('text')
        if not isinstance(text,str) or len(text)>16000:raise ValueError('Invalid transcript')
        return {'text':text}
    except (ValueError,ModelInvocationError) as error:raise HTTPException(422,'Recording cannot be transcribed') from error


async def speak(runtime,principal,bot_id,sid,voice_id,controller,text):
    config=settings(runtime,principal,bot_id,sid,voice_id,controller)
    return await speak_config(runtime,principal,sid,config,text)


async def speak_config(runtime,principal,sid,config,text):
    if not config.get('tts_model_id') or config.get('speech_ready') is False:raise HTTPException(409,'Speech output is not configured; input-only mode remains available')
    ctx=context(runtime,principal,sid)
    if config.get('profile_id'):
        from ai2apps.readaloud.repository import ReadAloudRepository
        from ai2apps.api.readaloud import render_quick_read,QuickReadRequest
        profile=ReadAloudRepository(runtime.database,runtime.events).get_voice_profile(principal.actor_user_id,config['profile_id'])
        if profile['model_id']!=config['tts_model_id'] or profile['updated_at']!=config['profile_updated_at']:raise HTTPException(409,'Voice changed; restart the conversation')
        response=await render_quick_read(runtime,QuickReadRequest(text=text,model_id=config['tts_model_id'],voice_profile_id=config['profile_id']),principal,transient=True,snapshot={'profile':profile})
    else:
        payload={'model':config['tts_model_id'],'input':text,'response_format':'wav'}
        if config.get('voice'):payload['voice']=config['voice']
        try:response=await invoke_speech(runtime.model_invocations.invoke_foreground_json,config['tts_model_id'],'audio_speech',payload,context=ctx)
        except ModelInvocationError as error:raise HTTPException(503,'Speech playback unavailable') from error
    if response.status_code>=400:raise HTTPException(503,'Speech playback failed')
    if not response.body or len(response.body)>4*1024*1024:raise HTTPException(502,'Speech segment exceeds Mobile media limit')
    return Response(response.body,media_type='audio/wav',headers={'Cache-Control':'no-store'})


async def read_reply(runtime,principal,bot_id,sid,text):
    """Manual narration does not require ASR or a microphone lease."""
    from ai2apps.messager.voice import BotVoice
    from ai2apps.core import RepositoryError
    if not text.strip():raise HTTPException(422,'Reply has no text to read')
    owner=BotVoice(runtime.messager_bots,runtime)
    candidates=[]
    for item in owner.playback(principal.actor_user_id,bot_id)['candidates']:
        chosen=item['settings']
        if chosen['mode']!='default':
            candidates.append(chosen)
            continue
        conversation=runtime.messager_dialogue.realtime.get(principal.actor_user_id,bot_id)
        if conversation.get('tts_model_id'):
            candidates.append({'mode':'profile' if conversation.get('profile_id') else 'model',
                'model_id':None if conversation.get('profile_id') else conversation['tts_model_id'],
                'voice':conversation.get('voice'),'profile_id':conversation.get('profile_id')})
        for model in catalog(runtime,principal,bot_id)['tts']:
            candidates.append({'mode':'model','model_id':model['id'],
                'voice':next(iter(model['voices']),None),'profile_id':None})
    config=None
    for candidate in candidates:
        try:
            valid=owner.validate(principal.actor_user_id,candidate)
            if valid['mode']=='profile':
                from ai2apps.readaloud.repository import ReadAloudRepository
                profile=ReadAloudRepository(runtime.database,runtime.events).get_voice_profile(principal.actor_user_id,valid['profile_id'])
                config={'tts_model_id':profile['model_id'],'profile_id':profile['id'],
                    'profile_updated_at':profile['updated_at'],'voice':None}
            else:
                config={'tts_model_id':valid['model_id'],'profile_id':None,'voice':valid['voice']}
            break
        except (ValueError,KeyError,RepositoryError):continue
    if config is None:raise HTTPException(409,'Install or configure a speech synthesis model on Desktop')
    return await speak_config(runtime,principal,sid,config,text)
