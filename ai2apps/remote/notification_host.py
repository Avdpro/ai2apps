"""Trusted host boundary for custom notifications and registered, read-only routes."""
from __future__ import annotations
import json
from .custom_notifications import fields, target as validate_target


class NotificationRoutes:
    """Host Python registrations, never callbacks or code supplied by a notification."""
    def __init__(self, runtime):
        self.runtime = runtime
        self.handlers = {}
        self.register('ai2apps.intelligence','channel',self._channel)
        self.register('ai2apps.intelligence','article',self._article)
        self.register('ai2apps.general-chat','conversation',self._conversation)
        self.register('ai2apps.general-chat','interaction',self._interaction)

    def register(self, app_id, route, authorize):
        key = (app_id,route)
        if key in self.handlers:
            raise ValueError('Notification route already registered')
        self.handlers[key] = authorize

    def definition(self, app_id, principal):
        manager = self.runtime.extension_manager
        definition = manager._active_app_definition(app_id)
        if definition is None:
            raise ValueError('Notification App unavailable')
        manager._require_app_access(definition,principal)
        manifest=json.loads(definition['manifest_json'])
        navigation=manifest.get('navigation',{})
        if isinstance(navigation,dict) and navigation.get('status','active')!='active':
            raise ValueError('Notification App not active')
        return manifest

    def resolve(self, principal, destination):
        destination = validate_target(destination)
        self.definition(destination['app_id'],principal)
        if destination['type']=='https_url':
            return {'type':'https_url','url':destination['url']}
        handler = self.handlers.get((destination['app_id'],destination['route']))
        if not handler:
            raise ValueError('Notification route not registered')
        # Handler must enforce resource ACL and return only query data for its App.
        params = handler(principal,destination['id'])
        if not isinstance(params,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in params.items()):
            raise ValueError('Invalid registered notification route')
        if any(k in ('app','notification-id') for k in params):
            raise ValueError('Reserved notification route parameter')
        return {'type':'app_route','app_id':destination['app_id'],'parameters':params}

    def _channel(self, principal, id):
        self.runtime.intelligence_collector.store.get('channels',principal.actor_user_id,id)
        return {'intelligence-channel':id}

    def _conversation(self, principal, id):
        from ai2apps.chat.notifications import authorize_conversation
        return authorize_conversation(self.runtime, principal, id)

    def _interaction(self, principal, id):
        from ai2apps.chat.notifications import authorize_interaction
        return authorize_interaction(self.runtime, principal, id)

    def _article(self, principal, id):
        article = self.runtime.intelligence_collector.store.get('articles',principal.actor_user_id,id)
        self.runtime.intelligence_collector.store.get('channels',principal.actor_user_id,article['channel_id'])
        return {'intelligence-channel':article['channel_id'],'intelligence-article':id}


def routes(runtime):
    if not hasattr(runtime,'notification_routes'):
        runtime.notification_routes = NotificationRoutes(runtime)
    return runtime.notification_routes


class NotificationHost:
    def __init__(self,runtime):
        self.runtime=runtime
        self.producer=runtime.remote.notifications

    def _owner(self,principal):
        identity=self.producer.identity()
        if principal.actor_user_id!=identity['owner_id'] or principal.installation_id!=identity['installation_id'] or not principal.is_core:
            raise ValueError('Only the Installation Owner can publish notifications')

    def send_mounted(self,principal,studio_id,mount_id,data):
        from ai2apps.studio.capability_broker import StudioCapabilityBroker
        self._owner(principal)
        mounted=StudioCapabilityBroker(self.runtime).mounted_mini_app(studio_id,mount_id,principal=principal)
        if 'notifications.send' not in mounted.capabilities:
            raise ValueError('Mini-App notification capability not declared')
        return self._send(principal,mounted.mount['app_key'],mounted.mount['app_instance_id'],
                          mounted.declaration.get('id'),mounted.declaration.get('notifications',{}),data)

    def send_for_instance(self,principal,app_instance_id,data):
        """Trusted Python App service API; never accepts a caller App ID in JSON."""
        self._owner(principal)
        manager=self.runtime.extension_manager
        manager._require_instance_access(app_instance_id,principal)
        with self.runtime.database.transaction() as c:
            row=c.execute('SELECT d.package_id,d.manifest_json FROM app_instances i JOIN app_definitions d ON d.id=i.app_definition_id WHERE i.id=? AND d.status=\'enabled\'',(app_instance_id,)).fetchone()
        if not row:
            raise ValueError('Notification caller App unavailable')
        settings=json.loads(row['manifest_json']).get('notifications',{})
        if not isinstance(settings,dict) or settings.get('send') is not True:
            raise ValueError('App notification permission not declared')
        return self._send(principal,row['package_id'],app_instance_id,None,settings,data)

    def _send(self,principal,caller_app,instance,mini_app,settings,data):
        if not isinstance(data,dict) or set(data)-{'event_id','content','target','group_key','metadata'}:
            raise ValueError('Invalid custom notification request')
        normalized=fields(data.get('content'),data.get('target'),data.get('group_key'),data.get('metadata'))
        target_app=normalized['target']['app_id']
        routes(self.runtime).definition(caller_app,principal)
        # App ID in target never becomes proof of caller identity.
        if target_app!=caller_app and (not isinstance(settings,dict) or target_app not in settings.get('targets',[])):
            raise ValueError('Cross-App notification target not authorized')
        routes(self.runtime).resolve(principal,normalized['target'])
        event_id=data.get('event_id')
        audit={'caller_app_id':caller_app,'caller_mini_app_id':mini_app,'target_app_id':target_app,
               'owner_id':principal.actor_user_id}
        with self.runtime.database.transaction(write=True) as c:
            previous=c.execute("SELECT payload_json FROM events WHERE type='notification.custom.enqueued' AND subject_id=? ORDER BY sequence LIMIT 1",(event_id,)).fetchone()
            if previous and json.loads(previous['payload_json'])!=audit:
                raise ValueError('Notification event belongs to another caller')
            result=self.producer.enqueue_custom(event_id=event_id,**normalized,connection=c,expected_owner_id=principal.actor_user_id)
            if not previous:
                self.runtime.events.append_in_transaction(c,event_type='notification.custom.enqueued',subject_id=result,
                                                          app_instance_id=instance,payload=audit)
        return {'event_id':result,'status':'queued'}
