import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image
from pydantic import ValidationError

from ai2apps.studio import image_workflow as workflow
from ai2apps.studio.extended_jobs import submit
from ai2apps.studio.repository import StudioRepository
from test_studio_extended_jobs import setup, finish, png
from test_studio_background_jobs import principal


def plan(**changes):
    return dict(key='fixture-key', title='Sequence', model='fixture/model', size='1024x1024',
        steps=[{'prompt': 'one', 'previous': 0}, {'prompt': 'two', 'previous': 2}], **changes)


@pytest.mark.parametrize('change', [dict(steps=[]), dict(steps=[{'prompt':'x'}]*7),
    dict(size='4096x4096'), dict(reference_limit=5), dict(steps=[{'prompt':'x','references':['../x']}]),
    dict(steps=[{'prompt':'x','previous':3}]), dict(extra='unsafe')])
def test_bounds(change):
    body=plan();body.update(change)
    with pytest.raises(ValidationError):workflow.Plan.model_validate(body)


def test_asset_scope_and_normalization(tmp_path):
    runtime=SimpleNamespace(config=SimpleNamespace(paths=SimpleNamespace(artifacts_path=tmp_path)))
    a=workflow.asset_root(runtime,principal(),'provider-a');b=workflow.asset_root(runtime,principal(),'provider-b')
    identifier=workflow.save_asset(a,png())
    assert identifier==workflow.save_asset(a,png())
    assert workflow.read_asset(a,identifier)==png()
    with pytest.raises(FileNotFoundError):workflow.read_asset(b,identifier)
    with pytest.raises(ValueError):workflow.read_asset(a,'../secrets')


def test_caption_overflow_rejected_before_any_inference():
    body=plan();body['steps'][0]['caption']='字'*600
    with pytest.raises(ValidationError,match='Caption too long'):workflow.Plan.model_validate(body)


async def test_sequence_private_references_and_reexport_without_inference(tmp_path,monkeypatch):
    m,app,scope,run=setup(tmp_path,mini='fixture.sequence');calls=[]
    root=workflow.asset_root(m.runtime,principal(),'fixture.provider')
    reference=workflow.save_asset(root,png('green',(900,600)))
    async def generate(runtime, actor, job, payload, request_id):
        calls.append(payload)
        return png('red' if len(calls)==1 else 'blue',(800,600)),{}
    monkeypatch.setattr(workflow,'generate_image',generate)
    body=plan();body['steps'][0]['references']=[reference]
    job=submit(m.runtime,principal(),app,scope['studio_id'],'fixture.sequence','image-workflow',
        {'plan':body,'provider':'fixture.provider'},files={reference:workflow.read_asset(root,reference)},run_id=run['id'])
    try:
        await finish(m,job)
        result=m.get(job['id'],principal())['result'];ids=result['assetIds']
        assert len(ids)==2 and len(calls)==2
        with m.database.transaction() as db:
            payload=json.loads(db.execute('SELECT request_json FROM studio_background_jobs WHERE id=?',(job['id'],)).fetchone()[0])
        assert not Path(payload['input_root']).exists()
        assert len(calls[0]['imageDataUrls'])==1 and len(calls[1]['imageDataUrls'])==1
        thumbnail=base64.b64decode(calls[1]['imageDataUrls'][0].split(',')[1])
        with Image.open(io.BytesIO(thumbnail)) as image:assert image.size==(512,384)
        assert len(StudioRepository(m.database).get_run(run['id'],**scope)['artifacts'])==1
        export=plan();export.update(key='export-key',publish=False)
        export['steps']=[{'image':identifier,'caption':'changed','previous':0} for identifier in ids]
        job2=submit(m.runtime,principal(),app,scope['studio_id'],'fixture.sequence','image-workflow',
            {'plan':export,'provider':'fixture.provider'},files={i:workflow.read_asset(root,i) for i in ids})
        await finish(m,job2)
        assert len(calls)==2
        assert m.get(job2['id'],principal())['result']=={'assetIds':ids}
        assert len(StudioRepository(m.database).get_run(run['id'],**scope)['artifacts'])==1
    finally:await m.shutdown()


async def test_uncertain_submission_is_never_replayed(tmp_path,monkeypatch):
    m,app,scope,run=setup(tmp_path);body=plan();job=submit(m.runtime,principal(),app,scope['studio_id'],run['miniAppId'],
        'image-workflow',{'plan':body,'provider':'fixture.provider'})
    directory=m.root/job['id'];directory.mkdir();(directory/'0.submitted').write_text('uncertain')
    async def forbidden(*a,**k):pytest.fail('must not replay inference')
    monkeypatch.setattr(workflow,'generate_image',forbidden)
    try:
        await finish(m,job,'failed')
        assert 'uncertain' in str(m.get(job['id'],principal())['error'])
    finally:await m.shutdown()


def test_contact_sheet_preserves_aspect_and_wraps_title():
    data=workflow.compose([png('red',(120,60)),png('blue',(120,60))],['Hello','世界'],'A'*160,2)
    with Image.open(io.BytesIO(data)) as image:
        assert image.width==1608
        assert image.height>384
        assert image.getpixel((50,image.height-100))[0]>200


def test_development_package_loads():
    from ai2apps.extensions.development import DevelopmentPackageLoader
    root=Path(__file__).resolve().parents[1]
    package=DevelopmentPackageLoader(root)._load(root/'packages/ai2apps-comic-studio')
    assert package.package_id=='ai2apps.comic-studio'
    assert {'web/comic.js','web/core.js','web/asset_slot.js'}.issubset(package.files)


@pytest.mark.parametrize('provider,mini',[('fixture.provider','fixture.sequence'),('other.vendor','unrelated.pages')])
def test_mount_api_ownership_validation_and_duplicate_key(tmp_path,monkeypatch,provider,mini):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.studio_image_workflow import create_image_workflow_router
    from ai2apps.studio.capability_broker import StudioCapabilityBroker, StudioCapabilityError
    m,app,scope,run=setup(tmp_path,mini=mini)
    actor=[principal()]
    def mounted(self,studio,mount,*,principal):
        if mount!='valid' or principal.actor_user_id!='owner':raise StudioCapabilityError('not_found','Mount unavailable',status_code=404)
        return SimpleNamespace(capabilities=['image.workflow'],mount={'app_key':provider,'context':{'studioInstanceId':app}},declaration={'id':mini,'version':'1'})
    monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',mounted)
    async def models(*a,**k):return ([{'id':'fixture/model','ready':True,'label':'Fixture','source':'cloud','size':{'mode':'fixed','presets':['1024x1024']},'formats':['png'],'qualities':['auto']}],[])
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    monkeypatch.setattr('ai2apps.model_providers.list_package_models',lambda r:[])
    server=FastAPI();server.include_router(create_image_workflow_router(lambda:m.runtime,lambda:actor[0]))
    client=TestClient(server);base=f"/{scope['studio_id']}/mini-app-mounts/valid/image-workflow"
    assert client.get(base+'/models').status_code==200
    body=plan();first=client.post(base+'/jobs',json=body);assert first.status_code==200,first.text
    duplicate=client.post(base+'/jobs',json=body);assert duplicate.json()['id']==first.json()['id']
    body['title']='changed';assert client.post(base+'/jobs',json=body).status_code==409
    body=plan();body.update(key='unsupported-size',size='768x1024');assert client.post(base+'/jobs',json=body).status_code==422
    assert client.get(base+'/submissions/fixture-key').json()['id']==first.json()['id']
    assert client.post(base+'/jobs/'+first.json()['id']+'/retry-publication').status_code==409
    assert client.get(base+'/assets/'+'a'*32).status_code==404
    actor[0]=principal('other')
    assert client.get(base+'/jobs/'+first.json()['id']).status_code==404


async def test_publication_retry_does_not_redraw(tmp_path,monkeypatch):
    m,app,scope,run=setup(tmp_path,mini='fixture.sequence');calls=[]
    async def generate(*a,**k):calls.append(1);return png(),{}
    monkeypatch.setattr(workflow,'generate_image',generate)
    job=submit(m.runtime,principal(),app,scope['studio_id'],'fixture.sequence','image-workflow',
        {'plan':plan(),'provider':'fixture.provider'},run_id=run['id'])
    publish=m.publish;m.publish=lambda *a,**k:(_ for _ in ()).throw(OSError('disk full'))
    try:
        await finish(m,job,'publish_failed');assert len(calls)==2
        m.publish=publish;m.retry(job['id'],principal());await finish(m,job)
        assert len(calls)==2 and len(m.get(job['id'],principal())['result']['assetIds'])==2
    finally:await m.shutdown()
