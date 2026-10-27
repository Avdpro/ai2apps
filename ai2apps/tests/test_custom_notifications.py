import json
import time
from types import SimpleNamespace
from uuid import uuid4
import httpx
import pytest
from ai2apps.remote.custom_notifications import fields, https_url, supports, CUSTOM_LIMITS
from ai2apps.remote.notification_host import NotificationRoutes, NotificationHost
from ai2apps.remote.notifications import NotificationProducer
from ai2apps.events.store import EventStore
from test_ai2apps_notification_producer import setup

CAPABILITY={'kind':'app.custom','version':1,'content_schema_version':1,
            'content_fields':['title','body','locale'],'target_types':['app_route','https_url'],
            'privacy_policy':'system_preview_v1','grouping':True,'app_authorization':'trusted_host_v1',
            'limits':CUSTOM_LIMITS}


def ready(p):
    p._policy_identity=p._encoded(p.identity());p._policy_checked=time.time()
    p._policy_value={'enabled':True,'event_capabilities':[CAPABILITY]}


def event():
    return dict(event_id='custom-test',content={'title':'A < B','body':'One\r\n\r\n\r\nTwo 👩\u200d💻'},
                target={'type':'https_url','app_id':'example.app','url':'https://example.com/news'},group_key='updates')


def test_normalization_and_capability():
    e=event();f=fields(e['content'],e['target'],e['group_key'])
    assert f['content']=={'title':'A < B','body':'One\n\nTwo 👩\u200d💻'}
    assert supports(CAPABILITY,'https_url')
    for bad in [{'version':True},{'content_schema_version':2},{'privacy_policy':'unsafe'},
                {'app_authorization':'caller_reported'}, {'limits':{}}, {'target_types':[]}]:
        assert not supports({**CAPABILITY,**bad},'https_url')
    with pytest.raises(ValueError): fields({'title':'x','body':'\ud800'},event()['target'])
    with pytest.raises(ValueError): fields({'title':'x'*161,'body':'x'},event()['target'])
    with pytest.raises(ValueError): fields({'title':'x','body':'x','force_rich':True},event()['target'])


@pytest.mark.parametrize('url',['javascript:alert(1)','http://example.com','https://a:b@example.com',
    'https://example.com/?token=secret','https://example.com/#handoff=secret','https://example.com/%GG',
    'https://example.com/%FF','https://example.com/%0a','https://example.com/a b',
    'https://device-abc.ai2apps.com/mobile','https://coder.ai2apps.com/%61pi/x'])
def test_reject_unsafe_targets(url):
    with pytest.raises(ValueError): https_url(url)


@pytest.mark.asyncio
async def test_custom_frozen_retry_and_conflict(tmp_path):
    bodies=[]
    def handler(request):
        bodies.append(request.content)
        if len(bodies)==1:raise httpx.ReadTimeout('ambiguous',request=request)
        return httpx.Response(202,json={'notification_id':str(uuid4())})
    p,remote,_,cloud,_=setup(tmp_path,handler)
    with pytest.raises(ValueError,match='capability'): p.enqueue_custom(**event())
    ready(p);p.enqueue_custom(**event());await p.drain_once()
    with p.database.transaction(write=True) as c:c.execute('UPDATE notification_producer_outbox SET next_attempt=0')
    restored=NotificationProducer(remote)
    restored.enqueue_custom(**event())
    await restored.drain_once()
    assert bodies[0]==bodies[1]
    assert json.loads(bodies[0])['content']['body']=='One\n\nTwo 👩\u200d💻'
    assert 'template' not in json.loads(bodies[0])
    with pytest.raises(ValueError): restored.enqueue_custom(**{**event(),'content':{'title':'changed','body':'changed'}})
    await cloud.close()


def test_route_registry_checks_app_and_resource_before_return():
    manager=SimpleNamespace(_active_app_definition=lambda app:{'manifest_json':'{}'} if app=='example.app' else None,
                            _require_app_access=lambda *_:None)
    registry=NotificationRoutes(SimpleNamespace(extension_manager=manager))
    def resource(principal,id):
        if id!='owned':raise ValueError('not owned')
        return {'notification-route':'detail','notification-resource':id}
    registry.register('example.app','detail',resource)
    target={'type':'app_route','app_id':'example.app','route':'detail','id':'owned'}
    assert registry.resolve(object(),target)['parameters']['notification-resource']=='owned'
    for bad in [{'id':'other'},{'route':'unknown'},{'app_id':'unregistered'}]:
        with pytest.raises(ValueError):registry.resolve(object(),{**target,**bad})


@pytest.mark.asyncio
async def test_trusted_host_sender_audit_owner_and_cross_app(tmp_path):
    p,remote,_,cloud,_=setup(tmp_path,lambda _:httpx.Response(500));ready(p)
    identity=p.identity()
    principal=SimpleNamespace(actor_user_id=identity['owner_id'],installation_id=identity['installation_id'],is_core=True)
    manager=SimpleNamespace(_active_app_definition=lambda app:{'manifest_json':'{}'},_require_app_access=lambda *_:None)
    runtime=SimpleNamespace(remote=remote,database=p.database,events=EventStore(p.database),extension_manager=manager)
    host=NotificationHost(runtime)
    host._owner(principal)
    for changed in [{'actor_user_id':'other'},{'installation_id':'other'},{'is_core':False}]:
        with pytest.raises(ValueError):host._owner(SimpleNamespace(**{**vars(principal),**changed}))
    # No fixture App instance required for a host service; the real mount supplies it.
    value=host._send(principal,'example.app',None,'mini.real',{},event())
    assert value['status']=='queued'
    assert host._send(principal,'example.app',None,'mini.real',{},event())==value
    with p.database.transaction() as c:
        rows=c.execute("SELECT payload_json FROM events WHERE type='notification.custom.enqueued'").fetchall()
    assert len(rows)==1 and json.loads(rows[0]['payload_json'])['caller_mini_app_id']=='mini.real'
    with pytest.raises(ValueError):host._send(principal,'spoof.app',None,'mini.spoof',{},event())
    with pytest.raises(ValueError):host._send(principal,'example.app',None,'mini.other',{},event())
    with pytest.raises(ValueError):host._send(principal,'example.app',None,'mini.real',{}, {**event(),'source_app_id':'spoof'})
    await cloud.close()


@pytest.mark.asyncio
async def test_local_route_identity_and_owner_acl(tmp_path):
    from fastapi import FastAPI
    from ai2apps.api.notifications import create_notification_router
    p,remote,identities,cloud,ids=setup(tmp_path,lambda _:httpx.Response(500))
    holder={'principal':identities.local_principal_for(ids['core_user_id'])}
    manager=SimpleNamespace(_active_app_definition=lambda app:{'manifest_json':'{}'},_require_app_access=lambda *_:None)
    runtime=SimpleNamespace(remote=remote,extension_manager=manager)
    runtime.notification_routes=NotificationRoutes(runtime)
    runtime.notification_routes.register('example.app','detail',lambda principal,id: {'notification-route':'detail','notification-resource':id} if id=='owned' else (_ for _ in ()).throw(ValueError('denied')))
    app=FastAPI();app.include_router(create_notification_router(lambda:runtime,lambda:holder['principal']))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url='http://local') as client:
        destination={'type':'app_route','app_id':'example.app','route':'detail','id':'owned'}
        result=await client.post('/notifications/resolve-target',json={'target':destination})
        assert result.status_code==200
        assert result.json()['source_device_id']==ids['device_id']
        assert result.json()['parameters']['notification-resource']=='owned'
        assert (await client.post('/notifications/resolve-target',json={'target':{**destination,'id':'other'}})).status_code==403
        holder['principal']=identities.local_principal_for(ids['member_user_id'])
        assert (await client.post('/notifications/resolve-target',json={'target':destination})).status_code==403
    await cloud.close()


@pytest.mark.asyncio
async def test_mini_app_binding_and_permission_are_host_derived(tmp_path,monkeypatch):
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    p,remote,identities,cloud,ids=setup(tmp_path,lambda _:httpx.Response(500));ready(p)
    manager=SimpleNamespace(_active_app_definition=lambda app:{'manifest_json':'{}'},_require_app_access=lambda *_:None)
    runtime=SimpleNamespace(remote=remote,database=p.database,events=EventStore(p.database),extension_manager=manager)
    host=NotificationHost(runtime);principal=identities.local_principal_for(ids['core_user_id'])
    binding=SimpleNamespace(capabilities=frozenset(),mount={'app_key':'example.app','app_instance_id':None},declaration={'id':'real.mini'})
    calls=[]
    def mounted(self,studio,mount,*,principal):
        calls.append((studio,mount));return binding
    monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',mounted)
    with pytest.raises(ValueError,match='capability'):host.send_mounted(principal,'studio','host-bound-mount',event())
    binding.capabilities=frozenset({'notifications.send'})
    assert host.send_mounted(principal,'studio','host-bound-mount',event())['status']=='queued'
    assert calls[-1]==('studio','host-bound-mount')
    with pytest.raises(ValueError):host.send_mounted(principal,'studio','host-bound-mount',{**event(),'caller_app_id':'spoof'})
    await cloud.close()
