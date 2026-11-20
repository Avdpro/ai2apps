"""Actual Service handlers/files/processes; no model or production data."""
from dataclasses import replace
import shutil

import pytest
from fastapi import HTTPException
from ai2apps.processes import TestSandboxAdapter as SandboxFixture
from ai2apps.services import ToolProviderError
from test_harness_file_utilities import setup
from test_app_chat_durable import bind_identity
from test_app_interactions import runtime


@pytest.mark.asyncio
@pytest.mark.parametrize('count,max_chars,expected,next_offset',[(3,8000,False,None),(25,8000,True,20),(3,100,True,0)])
async def test_document_preview_reports_both_text_and_block_truncation(runtime,tmp_path,count,max_chars,expected,next_offset):
    _,c,_=setup(runtime,tmp_path)
    body='\n\n'.join(f'Paragraph {i:02d}: '+ 'text '*12 for i in range(count))
    item=runtime.documents.create(c.session_id,filename='notes.txt',media_type='text/plain',data=body.encode())
    runtime.documents.parse(c.session_id,item.id)
    provider=runtime.app_capability_router.providers['ai2apps.harness.document.preview']
    result=await provider.handler({'attachment_id':item.id,'max_chars':max_chars},c)
    assert result['truncated'] is expected and result['next_offset']==next_offset
    assert result['has_more_blocks'] is (count>20)
    assert len(result['text'])<=max_chars
    if next_offset is not None:
        read=runtime.app_capability_router.providers['ai2apps.harness.document.read']
        remainder=await read.handler({'attachment_id':item.id,'offset':next_offset,'limit':50},c)
        assert remainder['items']
    with pytest.raises(HTTPException):await provider.handler({'attachment_id':item.id},replace(c,session_id='foreign'))


@pytest.mark.asyncio
async def test_pdf_creation_aaat_preserves_workspace_and_artifact_ownership(runtime,tmp_path):
    _,c,_=setup(runtime,tmp_path)
    provider=runtime.app_capability_router.providers['ai2apps.harness.document.create_pdf']
    result=await provider.handler({'content':'# Report\n\nPDF generation fixture.', 'title':'Report',
        'output_path':'output/fixture.pdf'},c)
    assert result['pages']==1
    a=runtime.workspace.get_artifact(c.session_id,result['artifact']['id'])
    assert a.media_type=='application/pdf' and runtime.workspace.artifact_path(a).read_bytes().startswith(b'%PDF-')
    with pytest.raises(Exception):await provider.handler({'content':'bad','output_path':'../escape.pdf'},c)
    assert not (tmp_path.parent/'escape.pdf').exists()
    for name in ('process.write_stdin','document.preview','document.create_pdf'):
        p=runtime.app_capability_router.providers['ai2apps.harness.'+name]
        assert p.agent_context['schema']=='ai2apps.aaat-declaration/v1'
        assert runtime.service_registry.bound_tool(name) and runtime.service_registry.visible_to_agent(name,'builtin:app-chat')


@pytest.mark.asyncio
async def test_process_stdin_aaat_uses_real_process_and_keeps_run_scope(runtime,tmp_path):
    if not shutil.which('cat'):pytest.skip('cat not available')
    _,c,_=setup(runtime,tmp_path)
    runtime.processes.sandbox=SandboxFixture()
    proc=await runtime.processes.start(session_id=c.session_id,run_id=c.trace_id,caller_id='fixture',argv=[shutil.which('cat')])
    provider=runtime.app_capability_router.providers['ai2apps.harness.process.write_stdin']
    try:
        with pytest.raises(ToolProviderError):
            await provider.handler({'process_id':proc.id,'data':'wrong'},replace(c,trace_id='run_other'))
        with pytest.raises(ToolProviderError,match='64 KiB'):
            await provider.handler({'process_id':proc.id,'data':'x'*65537},c)
        result=await provider.handler({'process_id':proc.id,'data':'你好 stdin\n','close':True},c)
        assert result['stdin_open'] is False
        done=await runtime.processes.wait(proc.id,session_id=c.session_id,run_id=c.trace_id,timeout_ms=3000)
        assert done.exit_code==0
        logs=runtime.processes.logs(proc.id,session_id=c.session_id,run_id=c.trace_id)
        assert '你好 stdin' in ''.join(x.content for x in logs if x.stream=='stdout')
        with pytest.raises(ToolProviderError):await provider.handler({'process_id':proc.id,'data':'late'},c)
    finally:
        await runtime.processes.cancel(proc.id,session_id=c.session_id,run_id=c.trace_id)
