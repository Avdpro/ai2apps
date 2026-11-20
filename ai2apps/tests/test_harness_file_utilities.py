"""Real files/SQLite and owner boundaries; Finder launch is a fixture only."""
from dataclasses import replace
from pathlib import Path
import io
import zipfile
import pytest
from fastapi import HTTPException

from ai2apps.app_chat.service import AppChatOwner
from ai2apps.processes.local_files import LocalFiles
from ai2apps.processes.harness_materials import Materials
from ai2apps.processes.local_directories import LocalDirectories
from test_app_chat_durable import P, bind_identity
from test_app_interactions import runtime


def setup(runtime, tmp_path, owner_name='fixture.files'):
    root=tmp_path/'output';root.mkdir(exist_ok=True)
    runtime.app_chat.register(AppChatOwner(owner_name,'ai2apps.gallery' if owner_name=='different.beta' else 'ai2apps.knowledge','1',(),lambda actor,scope:scope,lambda *args:None,
        {'type':'object'},exports=lambda scope:(),source_user_requests=lambda actor,scope,run:[f'Save to "{root}"']))
    sid=runtime.app_chat.open(P(),owner_name,{}, {})
    run=runtime.agents.create_run(session_id=sid,agent_key='ai2apps.app-chat-agent',input={'prompt':'fixture','model':'fixture'})[0]
    context=replace(runtime.tools.context_for_session(caller_id='fixture',session_id=sid),trace_id=run.id,actor_user_id="local",installation_id="local")
    return root,context,LocalFiles(runtime,LocalDirectories(runtime))


def artifact(runtime,context,tmp_path,name='image.png',data=b'image bytes'):
    p=tmp_path/name;p.write_bytes(data)
    return runtime.workspace.import_artifact(context.session_id,p,name=name,run_id=context.trace_id)


@pytest.mark.asyncio
@pytest.mark.parametrize('owner_name',['fixture.alpha','different.beta'])
async def test_export_batch_verified_collision_and_scope(runtime,tmp_path,owner_name):
    root,c,files=setup(runtime,tmp_path,owner_name)
    a=artifact(runtime,c,tmp_path)
    args={'root':str(root),'files':[{'artifact_id':a.id,'path':'image.png'}]}
    await files.prepare(args,c)
    first=files.export(args,c)
    assert first['saved']==1 and first['files'][0]['verified']
    assert Path(first['files'][0]['path']).read_bytes()==b'image bytes'
    assert files.export(args,c)['files'][0]['path'].endswith('image (1).png')
    assert files.export({**args,'collision':'skip'},c)['files'][0]['status']=='skipped'
    with pytest.raises(PermissionError):await files.prepare({**args,'collision':'replace'},c)
    with pytest.raises(Exception):await files.prepare({**args,'root':str(tmp_path)},c)
    with pytest.raises(HTTPException):files.export(args,replace(c,session_id='foreign'))
    assert (root/'image.png').read_bytes()==b'image bytes'


@pytest.mark.asyncio
async def test_mkdir_copy_move_inspect_and_symlink_denial(runtime,tmp_path):
    root,c,files=setup(runtime,tmp_path)
    files.mkdir({'root':str(root),'path':'en/nested'},c)
    (root/'source').write_bytes(b'original')
    copied=files.transfer({'root':str(root),'source':'source','destination':'en/copy'},c)
    assert copied['verified'] and (root/'source').exists()
    moved=files.transfer({'root':str(root),'source':'en/copy','destination':'en/nested/renamed'},c,move=True)
    assert moved['source_removed'] and not (root/'en/copy').exists()
    info=files.inspect({'root':str(root),'path':'en/nested/renamed'},c)
    assert len(info['sha256'])==64 and info['free_bytes']>0
    (root/'link').symlink_to(tmp_path,target_is_directory=True)
    for action,args in [(files.mkdir,{'path':'link/sub'}),(files.inspect,{'path':'link'}),
                        (files.transfer,{'source':'source','destination':'link/leak'})]:
        with pytest.raises((OSError,ValueError)):action({'root':str(root),**args},c)
    assert not (tmp_path/'leak').exists()


@pytest.mark.asyncio
async def test_batch_partial_receipts_and_overwrite_precondition(runtime,tmp_path):
    root,c,files=setup(runtime,tmp_path);a=artifact(runtime,c,tmp_path)
    args={'root':str(root),'files':[{'artifact_id':a.id,'path':'ok.png'},{'artifact_id':a.id,'path':'missing/no.png'}]}
    result=files.export(args,c)
    assert result['status']=='partial' and result['saved']==1 and result['failed']==1
    (root/'ok.png').write_bytes(b'keep')
    item={'artifact_id':a.id,'path':'ok.png','expected_sha256':'a'*64}
    assert files.export({'root':str(root),'files':[item],'collision':'replace'},c)['failed']==1
    assert (root/'ok.png').read_bytes()==b'keep'
    item['expected_sha256']=files.inspect({'root':str(root),'path':'ok.png'},c)['sha256']
    assert files.export({'root':str(root),'files':[item],'collision':'replace'},c)['saved']==1
    assert not list(root.glob('.ai2apps-*'))


@pytest.mark.asyncio
async def test_artifact_materialize_pack_unpack_and_quota(runtime,tmp_path):
    root,c,_=setup(runtime,tmp_path);a=artifact(runtime,c,tmp_path)
    result=runtime.workspace.materialize_artifact(c.session_id,a.id,'stage/image.png')
    assert result['verified'] and runtime.workspace.read(c.session_id,'stage/image.png')['content']=='image bytes'
    with pytest.raises(FileExistsError):runtime.workspace.materialize_artifact(c.session_id,a.id,'stage/image.png')
    with pytest.raises(Exception):runtime.workspace.materialize_artifact(c.session_id,a.id,'../escape')
    owner=Materials(runtime)
    packed=owner.pack({'artifact_ids':[a.id]},c)
    unpacked=owner.unpack({'artifact_id':packed['artifact_id']},c)
    assert unpacked['file_count']==1
    restored=runtime.workspace.get_artifact(c.session_id,unpacked['files'][0]['artifact_id'])
    assert runtime.workspace.artifact_path(restored).read_bytes()==b'image bytes'


@pytest.mark.asyncio
@pytest.mark.parametrize('entry,mode',[('../escape',None),('/absolute',None),('link',0o120777)])
async def test_unsafe_zip_does_not_publish_outputs(runtime,tmp_path,entry,mode):
    root,c,_=setup(runtime,tmp_path)
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as archive:
        archive.writestr('valid.txt','valid')
        info=zipfile.ZipInfo(entry)
        if mode:info.external_attr=mode<<16
        archive.writestr(info,'bad')
    a=artifact(runtime,c,tmp_path,'input.zip',data.getvalue())
    before=len(runtime.workspace.list_artifacts(c.session_id))
    with pytest.raises((ValueError,PermissionError)):Materials(runtime).unpack({'artifact_id':a.id},c)
    assert len(runtime.workspace.list_artifacts(c.session_id))==before


@pytest.mark.asyncio
async def test_document_artifact_ingestion_and_discovery(runtime,tmp_path):
    root,c,_=setup(runtime,tmp_path)
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr('word/document.xml','<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Hello document</w:t></w:r></w:p></w:body></w:document>')
    a=artifact(runtime,c,tmp_path,'notes.docx',data.getvalue())
    result=Materials(runtime).document({'artifact_id':a.id},c)
    assert result['status']=='ready'
    assert 'Hello document' in ' '.join(b.text for b in runtime.documents.blocks(c.session_id,result['attachment_id']))
    for capability in ('document.read','document.search','document.info','artifact.list','artifact.export','host.directory.export','artifact.pack'):
        assert 'ai2apps.harness.'+capability in runtime.app_capability_router.providers


@pytest.mark.asyncio
async def test_finder_uses_fixed_executable_without_shell(runtime,tmp_path,monkeypatch):
    root,c,files=setup(runtime,tmp_path);(root/'a ; command.png').write_bytes(b'x')
    import ai2apps.processes.local_files as module
    monkeypatch.setattr(module.sys,'platform','darwin')
    calls=[];monkeypatch.setattr(module.subprocess,'run',lambda argv,**kw:calls.append((argv,kw)))
    result=files.reveal({'root':str(root),'path':'a ; command.png'},c)
    assert result['status']=='requested'
    assert calls[0][0]==['/usr/bin/open','-R',str(root/'a ; command.png')]
    assert 'shell' not in calls[0][1]


@pytest.mark.asyncio
async def test_pdf_content_is_readable_via_actual_aaat_handler(runtime,tmp_path):
    from ai2apps.documents import PdfGenerator
    root,c,_=setup(runtime,tmp_path)
    data=PdfGenerator().generate("# Example report\n\nThe answer is forty two.",title="PDF fixture").data
    a=artifact(runtime,c,tmp_path,'report.pdf',data)
    importer=runtime.app_capability_router.providers['ai2apps.harness.document.import_artifact']
    result=await importer.handler({'artifact_id':a.id},c)
    assert result['status']=='ready'
    reader=runtime.app_capability_router.providers['ai2apps.harness.document.read']
    text=await reader.handler({'attachment_id':result['attachment_id'],'limit':50},c)
    assert 'forty two' in ' '.join(b['text'] for b in text['items'])
    assert any(b.get('page') for b in text['items'])


@pytest.mark.asyncio
async def test_bot_imports_then_saves_real_files_with_normal_access_guards(runtime,tmp_path):
    import asyncio,json
    from ai2apps.messager.bots import REGISTRATION
    from test_app_chat_durable import response
    from test_app_interactions import wait
    from test_bot_dialogue import job_wait
    root=tmp_path/'Comic';root.mkdir();(root/'source.png').write_bytes(b'actual fixture pixels')
    bot=runtime.messager_bots.create('local','File workflow fixture','Use Harness for requested local file work')
    sid=runtime.app_chat.open(P(),REGISTRATION,{'bot_id':bot['id']},{})
    async def model(request):
        system=request['messages'][0]['content']
        if 'Decide quickly' in system:
            return response(text=json.dumps({'kind':'task','title':'Save file fixture','step_label':'Saving files','text':'Queued'}))
        if 'Review a proposed Tool invocation' in system:
            return response(text=json.dumps({'risk':'low','necessary':True,'reason':'fixture requested file work'}))
        results=[json.loads(m['content']) for m in request['messages'] if m['role']=='tool']
        if any(r.get('saved')==1 for r in results):return response(text='Saved output.png with verified bytes')
        imported=next((r for r in results if r.get('source_read_only') and r.get('files')),None)
        if imported:
            if not any(p.get('capability')=='host.directory.export' for r in results for p in r.get('providers',[])):
                return response('app.describe',{'capability':'host.directory.export'})
            return response('host.directory.export',{'root':str(root),'files':[{'artifact_id':imported['files'][0]['artifact_id'],'path':'output.png'}]})
        if not any(p.get('capability')=='host.directory.import' for r in results for p in r.get('providers',[])):
            return response('app.describe',{'capability':'host.directory.import'})
        return response('host.directory.import',{'root':str(root),'files':['source.png']})
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        source=runtime.messager_dialogue.submit(P(),bot['id'],sid,'save-fixture',f'Copy source.png to output.png in "{root}"','fixture',[])
        await wait(runtime,source,'completed');job=await job_wait(runtime,source,'running');worker=job['worker_run']
        for attempt in range(500):
            state=runtime.agents.get_run(worker)
            if state.status.value=='completed':break
            if state.status.value=='failed':raise AssertionError(state.error)
            for pending in runtime.agents.list_interactions(worker):
                if pending.status.value!='pending':continue
                access=runtime.messager_bot_app_access
                review=access.request('local',bot['id'],worker,pending.id)
                assert review['app']['app_id']=='ai2apps.harness'
                admitted=access.allow('local',bot['id'],worker,pending.id,review['request_hash'])
                if not admitted['continued']:
                    runtime.agents.respond_interaction(worker,pending.id,response_id='approve-'+pending.id,
                        response={'decision':'approve','scope':'once'})
                    runtime.agent_runtime.wake()
            await asyncio.sleep(.02)
        else:raise AssertionError(runtime.agents.get_run(worker).status)
        assert (root/'output.png').read_bytes()==b'actual fixture pixels'
        steps=runtime.agents.list_steps(worker)
        assert sum(s.tool_name=='host.directory.export' and s.status.value=='completed' for s in steps)==1
    finally:await runtime.stop_background_tasks()


@pytest.mark.asyncio
async def test_materialize_respects_workspace_quota_and_zip_expansion_cap(runtime,tmp_path,monkeypatch):
    root,c,_=setup(runtime,tmp_path);a=artifact(runtime,c,tmp_path,data=b'0123456789')
    runtime.workspace.ensure_sandbox(c.session_id)
    with runtime.database.transaction(write=True) as db:
        db.execute('UPDATE session_sandboxes SET quota_bytes=3 WHERE session_id=?',(c.session_id,))
    with pytest.raises(Exception,match='quota'):runtime.workspace.materialize_artifact(c.session_id,a.id,'blocked.png')
    assert not (runtime.workspace._root(c.session_id)/'blocked.png').exists()
    packed=Materials(runtime).pack({'artifact_ids':[a.id]},c)
    import ai2apps.processes.harness_materials as module
    monkeypatch.setattr(module,'MAX_BYTES',1)
    with pytest.raises(ValueError,match='exceeds'):Materials(runtime).unpack({'artifact_id':packed['artifact_id']},c)


@pytest.mark.asyncio
async def test_export_rejects_corrupted_artifact_before_publishing(runtime,tmp_path):
    root,c,files=setup(runtime,tmp_path);a=artifact(runtime,c,tmp_path)
    runtime.workspace.artifact_path(a).write_bytes(b'corrupted')
    result=files.export({'root':str(root),'files':[{'artifact_id':a.id,'path':'output.png'}]},c)
    assert result['failed']==1 and 'hash mismatch' in result['files'][0]['error']
    assert not (root/'output.png').exists() and not list(root.glob('.ai2apps-*'))


@pytest.mark.asyncio
async def test_move_failure_preserves_saved_destination_receipt(runtime,tmp_path,monkeypatch):
    import ai2apps.processes.local_files as module
    root,c,files=setup(runtime,tmp_path);(root/'source').write_bytes(b'keep both')
    original=module.os.unlink
    def fail_source(path,*args,**kw):
        if path=='source':raise PermissionError('fixture removal denied')
        return original(path,*args,**kw)
    monkeypatch.setattr(module.os,'unlink',fail_source)
    result=files.transfer({'root':str(root),'source':'source','destination':'target'},c,move=True)
    assert result['status']=='partial' and result['verified'] and result['source_removed'] is False
    assert (root/'source').read_bytes()==(root/'target').read_bytes()==b'keep both'
