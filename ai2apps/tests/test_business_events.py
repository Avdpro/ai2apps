"""Business owner transactions and recovery; no external models or accounts."""
import json
import pytest
from ai2apps.events.business import BusinessEvents, EventType
from ai2apps.events.builtin import CHANNEL, VOICE, VIDEO
from test_app_interactions import runtime


def test_arbitrary_producers_transaction_identity_and_projection(runtime):
    service=runtime.business_events
    for name in ('fixture','unrelated'):
        publisher=service.register(EventType(name+'.created','ai2apps.'+name,'Created','thing',
            {'type':'object','properties':{'n':{'type':'integer'}},'required':['n'],'additionalProperties':False},
            ('n',),'test',lambda actor,subject: actor=='local'))
        with pytest.raises(RuntimeError):
            with runtime.database.transaction(write=True) as db:
                publisher.publish(db,owner='local',subject_id='x',occurrence_key='one',data={'n':1})
                raise RuntimeError('rollback')
        assert not service.list('local',event_type=name+'.created')['items']
        with runtime.database.transaction(write=True) as db:
            eid=publisher.publish(db,owner='local',subject_id='x',occurrence_key='one',data={'n':1})
        with runtime.database.transaction(write=True) as db:
            assert publisher.publish(db,owner='local',subject_id='x',occurrence_key='one',data={'n':1})==eid
            with pytest.raises(ValueError,match='conflict'):
                publisher.publish(db,owner='local',subject_id='x',occurrence_key='one',data={'n':2})
        assert service.read('local',eid)['data']=={'n':1}
        with pytest.raises(KeyError):service.read('other',eid)
        with pytest.raises(Exception):
            with runtime.database.transaction(write=True) as db:
                publisher.publish(db,owner='local',subject_id='x',occurrence_key='two',data={'n':1,'secret':'no'})


def test_channel_terminal_outbox_crash_replay(runtime):
    from ai2apps.intelligence.store import IntelligenceStore
    store=IntelligenceStore(runtime.config.paths.artifacts_path/'intelligence')
    # Use the actual owner tables/terminal transition. Model and browser are absent.
    with store.connect() as db:
        db.execute('INSERT INTO channels VALUES(?,?,?)',('c','local','{}'))
        db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',('r','local','c','running',0,json.dumps({'pending_status':'completed','result_message':'done','new_article_ids':['a','a','b']})))
    store.complete_pending('local','r')
    pub=runtime.events.business_publishers[CHANNEL]
    assert store.flush_business_events(pub)==1
    first=runtime.business_events.list('local',event_type=CHANNEL)['items']
    assert len(first)==1 and first[0]['data']['added_count']==2
    # Simulate platform commit before the source outbox ack; repeat terminal call.
    with store.connect() as db:db.execute('UPDATE business_event_outbox SET event_id=NULL')
    store.complete_pending('local','r')
    assert store.flush_business_events(pub)==1
    assert runtime.business_events.list('local',event_type=CHANNEL)['items']==first
    assert runtime.business_events.list('other')['items']==[]


def test_voice_created_is_indexed_without_duplicate_raw_event(runtime):
    from ai2apps.readaloud.repository import ReadAloudRepository
    repo=ReadAloudRepository(runtime.database,runtime.events)
    profile=repo.create_voice_profile('local',name='Fixture voice',source_type='synthetic_designed',
        model_id=None,provider_voice_id=None,reference_transcript='',rights_scope={})
    items=runtime.business_events.list('local',event_type=VOICE)['items']
    assert len(items)==1 and items[0]['subject']['id']==profile['id']
    assert 'owner_user_id' not in items[0]['data']
    with runtime.database.transaction() as db:
        assert db.execute('SELECT count(*) FROM events WHERE type=? AND subject_id=?',(VOICE,profile['id'])).fetchone()[0]==1

@pytest.mark.asyncio
async def test_video_actual_materialization_and_publish(runtime, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from ai2apps.core import utc_now_text
    from test_video_processing_aaat import video
    output=tmp_path/'render.mp4'
    video(output)
    task='test-video-event'
    now=utc_now_text()
    with runtime.database.transaction(write=True) as db:
        db.execute('''INSERT INTO video_generation_tasks(id,actor_id,model_id,model_revision,status,
            request_json,request_hash,created_at,updated_at) VALUES(?,?,?,?,'running','{}','hash',?,?)''',
            (task,'local','fixture','1',now,now))
    manager=runtime.video_tasks
    model=SimpleNamespace(service_key='fixture.video',id='fixture')
    def owned_model(identifier,actor):
        assert identifier=='fixture' and actor=='local'
        return model
    monkeypatch.setattr(manager,'_model',owned_model)
    async def invoke(*_):return output
    monkeypatch.setattr(manager,'_invoke',invoke)
    await manager._run(task)
    row=manager._row(task)
    assert row['status']=='succeeded'
    fact=runtime.business_events.list('local',event_type=VIDEO)['items']
    assert len(fact)==1 and fact[0]['data']['output_id']==row['artifact_id']
    assert runtime.workspace.get_artifact(row['artifact_session_id'],row['artifact_id']).id==row['artifact_id']
    manager._update(task,status='succeeded')
    assert runtime.business_events.list('local',event_type=VIDEO)['items']==fact

@pytest.mark.asyncio
async def test_http_catalog_actor_scope_and_no_raw_event_access(runtime):
    from fastapi import FastAPI
    from httpx import AsyncClient, ASGITransport
    from ai2apps.api.business_events import create_business_event_router
    from ai2apps.identity import RequestPrincipal
    principal = RequestPrincipal.legacy_local()
    app = FastAPI()
    app.include_router(create_business_event_router(lambda:runtime,lambda:principal))
    with runtime.database.transaction(write=True) as db:
        # An arbitrary raw event is never queryable at this endpoint.
        raw=runtime.events.append_in_transaction(db,event_type='private.progress',subject_id='secret',payload={'secret':1})
    async with AsyncClient(transport=ASGITransport(app=app),base_url='http://fixture') as client:
        catalog=await client.get('/business-events/catalog')
        assert catalog.status_code==200
        assert {item['type'] for item in catalog.json()['items']} == {
            CHANNEL,
            VIDEO,
            VOICE,
            'messager.message.received',
            'messager.collaboration.accepted',
            'messager.collaboration.completed',
        }
        assert (await client.get('/business-events/'+raw.id)).status_code==404
        assert (await client.get('/business-events?after=-1')).status_code==422
        assert (await client.get('/business-events?event_type=private.progress')).status_code==422


def test_owner_voice_transaction_rollback_leaves_no_fact(runtime, monkeypatch):
    from ai2apps.readaloud.repository import ReadAloudRepository
    repo=ReadAloudRepository(runtime.database,runtime.events)
    append=repo._append_event
    def fail_after_append(*args,**kwargs):
        append(*args,**kwargs)
        raise RuntimeError('business rollback')
    monkeypatch.setattr(repo,'_append_event',fail_after_append)
    with pytest.raises(RuntimeError):
        repo.create_voice_profile('local',name='Rolled back',source_type='synthetic_designed',
            model_id=None,provider_voice_id=None,reference_transcript='',rights_scope={})
    assert not runtime.business_events.list('local',event_type=VOICE)['items']
