"""Cross-provider durable output contracts; fixture media, no model calls."""
from types import SimpleNamespace as NS
from pathlib import Path
from ai2apps.agents.artifact_outputs import output_artifacts, artifact_reference
from legacy_package_backend_fixture import runtime
from ai2apps.chat import ChatRepository


def step(output,status='completed'):
    return NS(kind='tool',status=NS(value=status),output=output)


def test_arbitrary_providers_types_ownership_and_dedup(runtime,tmp_path):
    sid=ChatRepository(runtime.database,runtime.events).create_thread(title='Outputs')[0].session.id
    records=[]
    for i,mime in enumerate(('audio/wav','video/mp4','application/pdf','text/plain','application/vnd.openxmlformats-officedocument.wordprocessingml.document','image/png')):
        p=tmp_path/str(i);p.write_bytes(b'fixture')
        a=runtime.workspace.import_artifact(sid,p,name=f'file-{i}',media_type=mime)
        url=f'/v1/platform/sessions/{sid}/artifacts/{a.id}/download'
        records.append(step({'files':[{'url':url,'filename':'untrusted'}]}))
    result=output_artifacts(records+records,runtime.workspace,sid)
    assert len(result)==6 and all(r['filename'].startswith('file-') for r in result)
    assert not output_artifacts(records,runtime.workspace,'foreign')
    assert not output_artifacts([step(records[0].output,'failed')],runtime.workspace,sid)
    assert len(output_artifacts(records,runtime.workspace,'foreign',allow_session=lambda s:s==sid))==6
    assert not output_artifacts(records,runtime.workspace,'foreign',allow_session=lambda s:False)
    assert not output_artifacts([step({'result':records[0].output})],runtime.workspace,sid)
    assert len(output_artifacts([step({'result':{**records[0].output,'executed_in_app':True}})],runtime.workspace,sid))==1
    assert not artifact_reference(url+'?token=x')
    assert not artifact_reference('https://evil.invalid'+url)
    assert not artifact_reference(url+'#fragment')


def test_cards_use_shared_renderer_and_no_untrusted_html():
    root=Path(__file__).resolve().parents[1]/'web'
    script=(root/'static/js/chat_artifacts.js').read_text()
    for tag in ('audio','video','iframe','textContent','sandbox','signedFetch','import-artifact','revokeObjectURL'):
        assert tag in script
    assert 'innerHTML' not in script and 'autoplay' not in script
    assert 'AI2AppsChatArtifacts.render' in (root/'templates/chat.html').read_text()
    assert 'AI2AppsChatArtifacts.render' in (root/'static/js/mobile_chat.js').read_text()


def test_exported_files_take_precedence_over_legacy_studio_reference(runtime,tmp_path):
    sid=ChatRepository(runtime.database,runtime.events).create_thread(title='Exports')[0].session.id
    p=tmp_path/'sound';p.write_bytes(b'fixture')
    a=runtime.workspace.import_artifact(sid,p,name='sound.wav',media_type='audio/wav')
    url=f'/v1/platform/sessions/{sid}/artifacts/{a.id}/download'
    result=output_artifacts([step({'files':[{'url':url}],'downloadUrl':'/v1/platform/sessions/older/artifacts/old/download'})],runtime.workspace,sid,allow_session=lambda s: (_ for _ in ()).throw(AssertionError('legacy output should not be read')))
    assert len(result)==1 and result[0]['artifact_id']==a.id
