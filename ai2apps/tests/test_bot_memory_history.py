"""M1/M2 owner behavior with real SQLite, resources and API; no model effects."""
import json
import pytest
import httpx
from fastapi import FastAPI
from ai2apps.messager.history import BotHistory
from ai2apps.api.messager import create_messager_router
from test_app_chat_durable import bind_identity
from test_app_interactions import runtime
from test_bot_capability_discovery import setup,P


def seed(r,bot,sid,ref,title,summary='',outputs=()):
    with r.database.transaction(write=True) as db:
        db.execute("INSERT INTO messager_dialogue_jobs VALUES(?,?,?,?,?,?,'completed',NULL,NULL,NULL)",(ref,'local',bot['id'],sid,'source-'+ref,title))
        db.execute('INSERT INTO messager_job_labels VALUES(?,?)',(ref,title))
        db.execute('INSERT INTO messager_job_presentations VALUES(?,?,?,?)',(ref,'[]',json.dumps({'artifacts':list(outputs)}),summary))
    r.messager_dialogue.sessions.link(r.messager_dialogue.row(ref))
    r.messager_dialogue.sessions.summarize(ref,summary)


def remember(r,bot,key,value='老王',**kwargs):
    return r.messager_bots.memory.records.apply('local',bot['id'],request_id=key,subject='user',predicate='preferred_name',value=value,text=value,**kwargs)


def test_history_search_beyond_twenty_is_scoped_and_cjk_literal(runtime):
    bot,sid,_,_=setup(runtime);h=BotHistory(runtime.messager_bots)
    for n in range(27):seed(runtime,bot,sid,'history-'+str(n),'熊猫戴帽子' if n==0 else 'Task '+str(n),'草帽版本' if n==0 else '')
    assert len(runtime.messager_dialogue.sessions.recent('local',bot['id'],sid))==20
    result=h.search('local',bot['id'],'熊猫 帽子')
    assert [v['id'] for v in result['items']]==['history-0']
    assert h.detail('local',bot['id'],'history-0')['steps'][0]['summary']=='草帽版本'
    assert h.search('local',bot['id'],'" OR * --')['items']==[]
    assert h.search('local',bot['id'],'',limit=5)['has_more']
    other=runtime.messager_bots.create('local','Other','Help')
    assert h.search('local',other['id'],'熊猫')['items']==[]
    with pytest.raises(PermissionError):h.detail('local',other['id'],'history-0')
    with pytest.raises(PermissionError):h.search('foreign',bot['id'],'熊猫')
    runtime.messager_dialogue.sessions.manage('local',bot['id'],'history-0','archive')
    assert h.search('local',bot['id'],'熊猫')['items']==[]
    assert len(h.search('local',bot['id'],'熊猫',archived=True)['items'])==1
    manager=runtime.messager_bot_lifecycle
    import asyncio
    asyncio.run(manager.apply('local',bot['id'],'clear_dialogue',manager.review('local',bot['id'])['review_hash']))
    assert h.search('local',bot['id'],'熊猫',archived=True)['items']==[]
    with pytest.raises(PermissionError):h.detail('local',bot['id'],'history-0',archived=True)


def test_history_artifact_availability_and_no_invented_ancestry(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);h=BotHistory(runtime.messager_bots)
    path=tmp_path/'panda.png';path.write_bytes(b'fixture image')
    asset=runtime.workspace.import_artifact(sid,path,name='panda-with-hat.png',media_type='image/png')
    seed(runtime,bot,sid,'output-history','戴帽子的熊猫','实际生成结果',outputs=[{'session_id':sid,'artifact_id':asset.id}])
    detail=h.detail('local',bot['id'],'output-history');assert detail['steps'][0]['outputs'][0]['available']
    assert 'no inferred' in detail['coverage']
    runtime.workspace.artifact_path(asset).unlink()
    assert h.detail('local',bot['id'],'output-history')['steps'][0]['outputs'][0]['available'] is False
    with pytest.raises(ValueError):h.resource('local',bot['id'],{'path':'/private/file'})


def test_merge_versions_evidence_and_stale_undo(runtime):
    bot,sid,_,_=setup(runtime);m=runtime.messager_bots.memory.records
    seed(runtime,bot,sid,'source-one','Task one');seed(runtime,bot,sid,'source-two','Task two')
    first=remember(runtime,bot,'remember-first',source={'task_id':'source-one'})
    assert remember(runtime,bot,'remember-first',source={'task_id':'source-one'})==first
    merged=remember(runtime,bot,'remember-second',source={'task_id':'source-two'})
    assert merged['memory_id']==first['memory_id'] and merged['kind']=='merged'
    assert len(m.detail('local',bot['id'],merged['change_id'])['evidence'])==2
    duplicate=remember(runtime,bot,'remember-again',source={'task_id':'source-two'})
    assert duplicate['kind']=='unchanged'
    with pytest.raises(ValueError):remember(runtime,bot,'conflict-name','王老师')
    changed=remember(runtime,bot,'replace-name','王老师',mode='replace',expected_revision=merged['revision'])
    with pytest.raises(ValueError):m.undo('local',bot['id'],first['change_id'],request_id='undo-too-old')
    undone=m.undo('local',bot['id'],changed['change_id'],request_id='undo-current')
    assert m.undo('local',bot['id'],changed['change_id'],request_id='undo-current')==undone
    assert runtime.messager_bots.memory.context('local',bot['id'])[0]['text']=='老王'
    assert m.detail('local',bot['id'],changed['change_id'])['undone_by']==undone['change_id']
    with pytest.raises(PermissionError):m.detail('foreign',bot['id'],changed['change_id'])
    other=runtime.messager_bots.create('local','Other','Help')
    with pytest.raises(PermissionError):m.undo('local',other['id'],changed['change_id'],request_id='undo-foreign')


def test_manual_note_journal_projection_restore_and_cleanup_guard(runtime):
    bot,sid,_,_=setup(runtime);notes=runtime.messager_bots.memory;m=notes.records
    note=notes.save('local',bot['id'],'A manual preference')
    changes=m.changes('local',bot['id'],sid=sid)['items'];assert len(changes)==1 and changes[0]['message_id']
    m.project('local',bot['id'],changes[0]['change_id']);assert len(m.changes('local',bot['id'],sid=sid)['items'])==1
    page=runtime.app_chat.message_page(P(),sid);assert sum('Memory saved' in i['content'] for i in page['items'])==1
    undo=m.undo('local',bot['id'],changes[0]['change_id'],request_id='manual-undo')
    assert notes.context('local',bot['id'])==[]
    restored=notes.save('local',bot['id'],note['text'],ref=note['id'],revision=undo['revision'])
    latest=m.changes('local',bot['id'])['items'][0]
    notes.clear('local',bot['id'])
    with pytest.raises(ValueError):m.undo('local',bot['id'],latest['change_id'],request_id='after-cleanup')
    assert restored['revision']<notes.list('local',bot['id'])['items'][0]['revision']


def test_resource_memory_persists_bytes_and_merges_identical_photos(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);m=runtime.messager_bots.memory.records;h=BotHistory(runtime.messager_bots)
    p=tmp_path/'me.png';p.write_bytes(b'fixture user selected photo')
    attachment=runtime.documents.create_reference(sid,p,filename='me.png',media_type='image/png')
    command=dict(subject='user',predicate='portrait',text='本人合影参考',kind='resource')
    a=m.apply('local',bot['id'],request_id='first-portrait',value={'session_id':sid,'attachment_id':attachment.id},**command)
    b=m.apply('local',bot['id'],request_id='second-portrait',value={'session_id':sid,'attachment_id':attachment.id},**command)
    assert a['memory_id']==b['memory_id'] and b['kind']=='merged'
    p.unlink()
    metadata=m.detail('local',bot['id'],b['change_id'])['metadata'];ref={k:metadata['value'][k] for k in ('session_id','artifact_id')}
    assert h.resource('local',bot['id'],ref)['available']
    other=runtime.messager_bots.create('local','Other','Help')
    with pytest.raises(PermissionError):m.apply('local',other['id'],request_id='steal-portrait',value=ref,**command)


@pytest.mark.asyncio
async def test_knowledge_api_origin_scopes_and_versioned_undo(runtime):
    bot,sid,_,_=setup(runtime);app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    base='/messager/bots/'+bot['id']
    body={'request_id':'api-remember','subject':'user','predicate':'nickname','value':'老王','text':'称呼我老王'}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        assert (await c.post(base+'/memory-records',json=body)).status_code==403
        saved=await c.post(base+'/memory-records',json=body,headers={'Origin':'http://test'});assert saved.status_code==200,saved.text
        result=saved.json();assert (await c.get(base+'/memory-changes/'+result['change_id'])).json()['can_undo']
        assert (await c.get(base+'/memory-changes',params={'session_id':sid})).json()['items'][0]['message_id']
        undone=await c.post(base+'/memory-changes/'+result['change_id']+'/undo',json={'request_id':'api-undo'},headers={'Origin':'http://test'})
        assert undone.status_code==200,undone.text
        assert (await c.get('/messager/bots/foreign/memory-changes/'+result['change_id'])).status_code==404


def test_configuration_receipt_is_linked_without_duplicate_notification(runtime):
    from test_bot_configuration import setup as configuration_setup
    from dataclasses import replace
    bot,sid,rid,ctx,service=configuration_setup(runtime)
    service.propose({'kind':'memory','text':'Fixture preference'},replace(ctx,invocation_id='memory-history'))
    row=service.pending('local',bot['id'])[0]
    service.decide('local',bot['id'],row['id'],row['review_hash'],'approve')
    changes=runtime.messager_bots.memory.records.changes('local',bot['id'],sid=sid)['items']
    assert len(changes)==1 and changes[0]['message_id']
    with runtime.database.transaction() as db:
        assert db.execute("SELECT count(*) FROM messages WHERE session_id=? AND idempotency_key LIKE 'bot-memory-change:%'",(sid,)).fetchone()[0]==0
        assert db.execute('SELECT idempotency_key FROM messages WHERE id=?',(changes[0]['message_id'],)).fetchone()[0]=='bot-configuration-result:'+row['id']


def test_projection_recovery_is_idempotent_and_never_replays_cleared_context(runtime,monkeypatch):
    bot,sid,_,_=setup(runtime);notes=runtime.messager_bots.memory;m=notes.records
    original=m.project
    monkeypatch.setattr(m,'project',lambda *a:None)
    notes.save('local',bot['id'],'First fact')
    monkeypatch.setattr(m,'project',original)
    first=m.changes('local',bot['id'],sid=sid)['items'][0]
    assert first['message_id']
    m.project('local',bot['id'],first['change_id'])
    assert len(m.changes('local',bot['id'],sid=sid,message_ids=[first['message_id']])['items'])==1
    monkeypatch.setattr(m,'project',lambda *a:None)
    notes.save('local',bot['id'],'Delayed fact')
    with runtime.database.transaction(write=True) as db:
        db.execute("UPDATE app_chat_sessions SET registration=registration||'.archived' WHERE session_id=?",(sid,))
    monkeypatch.setattr(m,'project',original)
    latest=m.changes('local',bot['id'])['items'][0]
    assert latest['message_id']==''
    with runtime.database.transaction() as db:
        assert db.execute("SELECT count(*) FROM messages WHERE session_id=? AND idempotency_key LIKE 'bot-memory-change:%'",(sid,)).fetchone()[0]==1


def test_merge_undo_preserves_independent_evidence_and_rollback(runtime,monkeypatch):
    bot,sid,_,_=setup(runtime);m=runtime.messager_bots.memory.records
    seed(runtime,bot,sid,'evidence-one','One');seed(runtime,bot,sid,'evidence-two','Two')
    first=remember(runtime,bot,'evidence-first',source={'task_id':'evidence-one'})
    merged=remember(runtime,bot,'evidence-second',source={'task_id':'evidence-two'})
    undo=m.undo('local',bot['id'],merged['change_id'],request_id='undo-evidence')
    detail=m.detail('local',bot['id'],undo['change_id'])
    assert len(detail['evidence'])==1 and detail['evidence'][0]['task_id']=='evidence-one'
    before=runtime.messager_bots.memory.context('local',bot['id'])
    def fail(*args,**kwargs):raise RuntimeError('Injected journal failure')
    monkeypatch.setattr(m,'track',fail)
    with pytest.raises(RuntimeError):remember(runtime,bot,'atomic-update','New name',mode='replace',expected_revision=undo['revision'])
    assert runtime.messager_bots.memory.context('local',bot['id'])==before


@pytest.mark.asyncio
async def test_history_tools_require_bot_authorization_and_copy_exact_output(runtime,tmp_path,bind_identity):
    bot,sid,_,_=setup(runtime);access=runtime.messager_bot_app_access
    c=access.catalog('local',bot['id'])
    access.save('local',bot['id'],c['revision'],c['review_hash'],[{'app_id':'ai2apps.messager','enabled':True}])
    runtime.app_chat.open(P(), 'ai2apps.messager.bots', {'bot_id':bot['id']},{})
    p=tmp_path/'result.txt';p.write_text('fixture result')
    asset=runtime.workspace.import_artifact(sid,p,name='result.txt',media_type='text/plain')
    seed(runtime,bot,sid,'tool-history','Old result',outputs=[{'session_id':sid,'artifact_id':asset.id}])
    rid=runtime.app_chat.submit(P(),sid,'history-tools','Find earlier work','fixture')
    ctx=runtime.tools.context_for_session(caller_id='fixture',session_id=sid,trace_id=rid)
    result=await runtime.tools.execute('messager.history.search',{'q':'Old result'},context=ctx)
    assert 'tool-history' in json.dumps(result.output),result
    result=await runtime.tools.execute('messager.history.attach',{'task_id':'tool-history','artifact_id':asset.id},context=ctx)
    assert result.output['status']=='attached',result
    copied=result.output['artifact']['artifact_id']
    again=await runtime.tools.execute('messager.history.attach',{'task_id':'tool-history','artifact_id':asset.id},context=ctx)
    assert again.output['artifact']['artifact_id']==copied
    from ai2apps.services.models import ToolGatewayError
    with pytest.raises(ToolGatewayError,match='exact task'):
        await runtime.tools.execute('messager.history.attach',{'task_id':'tool-history','artifact_id':'foreign'},context=ctx)


@pytest.mark.asyncio
async def test_memory_resource_endpoint_is_owned_live_and_survives_source_archive(runtime,tmp_path):
    bot,sid,_,_=setup(runtime);m=runtime.messager_bots.memory.records
    p=tmp_path/'portrait.png';p.write_bytes(b'fixture portrait bytes')
    a=runtime.workspace.import_artifact(sid,p,name='portrait.png',media_type='image/png')
    note=m.apply('local',bot['id'],request_id='endpoint-photo',subject='user',predicate='portrait',kind='resource',value={'session_id':sid,'artifact_id':a.id},text='Portrait')
    app=FastAPI();app.include_router(create_messager_router(lambda:runtime,P))
    route='/messager/bots/'+bot['id']+'/memory-records/'+note['memory_id']+'/resource'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as c:
        value=await c.get(route);assert value.status_code==200 and value.content==b'fixture portrait bytes'
        assert value.headers['x-content-type-options']=='nosniff'
        assert (await c.get(route.replace(bot['id'],'foreign'))).status_code==404
        with runtime.database.transaction(write=True) as db:db.execute("UPDATE app_chat_sessions SET registration=registration||'.archived' WHERE session_id=?",(sid,))
        assert (await c.get(route)).status_code==200
        runtime.messager_bots.memory.clear('local',bot['id'])
        assert (await c.get(route)).status_code==404


def test_old_removed_field_cannot_be_restored_over_fresh_evidence(runtime):
    bot,sid,_,_=setup(runtime);records=runtime.messager_bots.memory.records;notes=runtime.messager_bots.memory
    a=remember(runtime,bot,'old-record','Old')
    removed=notes.save('local',bot['id'],'Old',ref=a['memory_id'],revision=a['revision'],deleted=True)
    removal=records.changes('local',bot['id'])['items'][0]
    fresh=records.apply('local',bot['id'],request_id='fresh-field',subject='user',predicate='preferred_name',value='New',text='New',_restore=True)
    with pytest.raises(ValueError,match='newer memory'):records.undo('local',bot['id'],removal['change_id'],request_id='undo-stale-removal')
    with pytest.raises(ValueError,match='newer memory'):notes.save('local',bot['id'],'Old',ref=removed['id'],revision=removed['revision'])
    assert [m['text'] for m in notes.context('local',bot['id'])]==['New']
