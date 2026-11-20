"""Trusted composition of built-in business event owners."""
from .business import BusinessEvents, EventType
import logging

CHANNEL = 'intelligence.channel.refresh_finished'
VIDEO = 'studio.video_output.published'
VOICE = 'readaloud.voice_profile.created'
MESSAGE = 'messager.message.received'


def schema(properties):
    return {'type':'object','properties':properties,'required':list(properties),'additionalProperties':False}


def install(runtime):
    service = BusinessEvents(runtime.events)
    runtime.business_events = service
    from .hooks import HookSubscriptions
    runtime.event_hooks = HookSubscriptions(service)
    runtime.events.business_publishers = {}
    def channel_access(actor, subject):
        from ai2apps.intelligence.store import IntelligenceStore
        try:
            IntelligenceStore(runtime.config.paths.artifacts_path/'intelligence').get('channels',actor,subject)
            return True
        except KeyError:
            return False
    def video_access(actor, subject):
        with runtime.database.transaction() as db:
            return db.execute("SELECT 1 FROM video_generation_tasks WHERE artifact_id=? AND actor_id=? AND status='succeeded'",(subject,actor)).fetchone() is not None
    def voice_access(actor, subject):
        with runtime.database.transaction() as db:
            return db.execute('SELECT 1 FROM readaloud_voice_profiles WHERE id=? AND owner_user_id=?',(subject,actor)).fetchone() is not None
    def message_access(actor,subject):
        with runtime.database.transaction() as db:
            return db.execute("SELECT 1 FROM messager_messages WHERE id=? AND owner_user_id=? AND direction='incoming'",(subject,actor)).fetchone() is not None
    text={'type':'string','minLength':1,'maxLength':300}
    types = (
        EventType(MESSAGE,'ai2apps.messager','Friend message received','message',schema({'transport':{'enum':['local_e2ee','cloud_offline']},'origin':{'enum':['live','offline_import']}}),('transport','origin'),'New Local incoming text and Cloud offline imports, not WeChat or historical replay.',message_access,authorize_collection=lambda actor:bool(actor),details=('messager.event_details','ai2apps.messager.messager.event_details','1')),
        EventType(CHANNEL,'ai2apps.intelligence','Channel refresh finished','channel',schema({
            'run_id':text, 'status':{'enum':['completed','partial','failed','cancelled']},
            'added_count':{'type':'integer','minimum':0}}),('status','added_count'),
            'Terminal runs written by IntelligenceStore; counts cover new saved article IDs, not updated articles.',channel_access,details=('intelligence.event_details','ai2apps.intelligence.intelligence.event_details','1')),
        EventType(VIDEO,'ai2apps.video-studio','Video output published','video_output',schema({
            'task_id':text,'output_id':text,'production_kind':{'const':'generation'}}),('production_kind',),
            'VideoTaskManager generated artifacts only; import, edit/export and Package outputs are not yet covered.',video_access,authorize_collection=lambda actor:bool(actor),details=('video.event_details','ai2apps.video-studio.video.event_details','1')),
        EventType(VOICE,'ai2apps.readaloud','Voice character created','voice_profile',schema({
            'source_type':{'type':'string'},'status':{'type':'string'},'has_reference_asset':{'type':'boolean'}}),('source_type','status'),
            'ReadAloudRepository profile creation; created does not imply ready.',voice_access,authorize_collection=lambda actor:bool(actor),details=('voice.event_details','ai2apps.readaloud.voice.event_details','1')),
    )
    logging.getLogger(__name__).info("Business event catalog loaded; source=%s types=%d", __file__, len(types))
    for definition in types:
        runtime.events.business_publishers[definition.name] = service.register(definition)


def install_relays(runtime):
    from ai2apps.intelligence.store import IntelligenceStore
    store = IntelligenceStore(runtime.config.paths.artifacts_path/'intelligence')
    runtime.business_event_relay.register(lambda: store.flush_business_events(runtime.events.business_publishers[CHANNEL]))


def install_hook_scanner(runtime):
    def scan():
        runtime.event_hooks.scan()
        return 0
    runtime.business_event_relay.register(scan)
