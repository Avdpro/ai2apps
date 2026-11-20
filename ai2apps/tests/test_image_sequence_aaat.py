"""Package SDK reuses bounded workflow admission; external image calls are fixtures."""
from types import SimpleNamespace
from pathlib import Path
import json
import pytest,yaml
from test_app_interactions import runtime
from ai2apps.apps.access import RequestPrincipal
from ai2apps.studio import image_sequence_aaat as sdk
from ai2apps.packages.mini_app_exports import declarations

@pytest.mark.parametrize('identity',['publisher.sequence','unrelated.cards'])
@pytest.mark.asyncio
async def test_sequence_uses_owner_scope_and_durable_receipt(runtime,monkeypatch,identity):
    scope=RequestPrincipal.legacy_local();context=SimpleNamespace(session_id='session',invocation_id=identity)
    mini={'id':identity,'version':'1.0.0'};spec={'host':'ai2apps.imagine-studio'}
    monkeypatch.setattr(sdk,'principal_for',lambda *_:scope)
    mounted=SimpleNamespace(capabilities=('image.workflow',),mount={'app_instance_id':'provider-instance'})
    checks=[];broker=SimpleNamespace(mounted_mini_app=lambda *a,**k:checks.append(a))
    monkeypatch.setattr(sdk,'owner',lambda *a:(SimpleNamespace(id='host-instance'),mounted,broker))
    monkeypatch.setattr(runtime.extension_manager,'instance_entry',lambda *a,**k:{'app_key':identity})
    async def catalog(*a):return {'preferred':'fixture/model','items':[{'id':'fixture/model','ready':True,'referenceLimit':4,'qualities':['auto'],'formats':['png'],'size':{'mode':'fixed','presets':['1024x1024']}}]}
    monkeypatch.setattr(sdk,'model_catalog',catalog)
    calls=[]
    async def submit(*a,**k):calls.append(a);return {'id':'job','status':'succeeded'}
    async def follow(*a):return {'status':'completed','studio_job_id':'job','shared_output':True,'result':{'downloadUrl':'actual-fixture-result'}}
    monkeypatch.setattr(sdk,'submit_plan',submit);monkeypatch.setattr(sdk,'follow',follow)
    monkeypatch.setattr(sdk,'deliver',lambda runtime,context,host,result:result|{'files':[{'artifact_id':'fixture-output'}]})
    args={'title':'A supplied episode','steps':[{'prompt':'one','caption':'Hello'},{'prompt':'two'}]}
    result=await sdk.execute(runtime,args,context,mini,spec)
    assert result['status']=='completed' and calls[0][2]['provider']==identity
    assert len(calls[0][4].steps)==2 and calls[0][4].model=='fixture/model'
    assert await sdk.execute(runtime,args,context,mini,spec)==result and len(calls)==1
    with pytest.raises(Exception,match='changed'):await sdk.execute(runtime,args|{'title':'different'},context,mini,spec)

@pytest.mark.asyncio
async def test_package_comic_export_declaration_and_discovery():
    root=Path(__file__).resolve().parents[2]/'packages/ai2apps-comic-studio'
    mini=yaml.safe_load((root/'app.yaml').read_text())['mini_apps'][0]
    catalog=json.loads((root/'ai2apps.json').read_text())['capabilityCatalog']
    exports=declarations(mini,catalog)
    export=next(x for x in exports if x['name']=='imagine.create_comic')
    assert {x['name'] for x in exports}=={'imagine.create_comic','imagine.comic_series','imagine.create_series_episode'}
    assert export['name']=='imagine.create_comic' and export['sdk']=='studio.image-sequence/v1'
    assert export['selectionRequired'] is False
    assert export['inputSchema']['properties']['steps']['maxItems']==6
    assert '生成短篇漫画' in catalog['entries'][0]['tasks']

def test_delivery_checks_host_and_projects_png():
    artifact=SimpleNamespace(id='art_source',name='sequence.png',media_type='image/png')
    copied=SimpleNamespace(id='art_copy',name=artifact.name,media_type=artifact.media_type)
    imports=[]
    workspace=SimpleNamespace(get_artifact=lambda *a:artifact,artifact_path=lambda a:Path('/fixture.png'),
        import_artifact=lambda *a,**k:(imports.append((a,k)) or copied))
    runtime=SimpleNamespace(workspace=workspace,extension_manager=SimpleNamespace(
        sessions=SimpleNamespace(get=lambda sid:SimpleNamespace(app_instance_id='host'))))
    context=SimpleNamespace(session_id='caller');host=SimpleNamespace(id='host')
    result={'result':{'downloadUrl':'/v1/platform/sessions/source/artifacts/art_source/download'}}
    output=sdk.deliver(runtime,context,host,result)
    assert output['files'][0]['artifact_id']=='art_copy' and imports[0][0][0]=='caller'
    with pytest.raises(Exception,match='Host'):sdk.deliver(runtime,context,SimpleNamespace(id='other'),result)
    with pytest.raises(Exception,match='valid output'):sdk.deliver(runtime,context,host,{'result':{'downloadUrl':'https://example.com/image.png'}})
