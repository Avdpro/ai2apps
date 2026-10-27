"""Explicit Studio composition for Mini-Apps placed in multiple hosts."""
from dataclasses import replace

def install(runtime):
 from . import voice_aaat
 from ai2apps.services.builtin_apps import detailed_transcription
 router=runtime.app_capability_router
 exports=[
  ('ai2apps.readaloud.voice.separate','ai2apps.video-studio',lambda a,c:voice_aaat.execute(runtime,a,c,host_app='ai2apps.video-studio')),
  ('ai2apps.readaloud.voice.detailed_transcription','ai2apps.video-studio',lambda a,c:detailed_transcription(runtime,a,c,host_app='ai2apps.video-studio')),
  ('ai2apps.video-studio.video.replace_speaker','ai2apps.readaloud',lambda a,c:voice_aaat.execute(runtime,a,c,replacement=True,video=True,host_app='ai2apps.readaloud'))]
 for source,host,handler in exports:
  provider=router.providers[source]
  router.register(replace(provider,id=host+'.'+provider.capability,app_id=host,handler=handler))
