import io
import json
import zipfile
import pytest
from test_app_interactions import runtime
from PIL import Image
from ai2apps.studio import portable_archive as arc
from ai2apps.gallery import GalleryRepository
from ai2apps.gallery.characters import Characters, CharacterInput
from ai2apps.gallery.character_archive import export_character, import_character, preview_character


def png(color='red'):
    out=io.BytesIO();Image.new('RGB',(32,32),color).save(out,'PNG');return out.getvalue()


def test_archive_roundtrip_dedup_and_checksum():
    data=arc.encode({'title':'中文'}, {'a':png(),'b':png()})
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        assert len(z.namelist())==2
    document,images=arc.decode(data)
    assert document=={'title':'中文'} and images['a']==images['b']==png()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        files={n:z.read(n) for n in z.namelist()}
    key=next(n for n in files if n.startswith('images/'));files[key]=png('blue')
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for n,v in files.items():z.writestr(n,v)
    with pytest.raises(ValueError,match='checksum'):arc.decode(out.getvalue())


@pytest.mark.parametrize('name',['../escape','/absolute','images/script.js','manifest.json'])
def test_archive_rejects_unsafe_or_duplicate_entries(name):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        z.writestr('manifest.json','{}');z.writestr(name,'bad')
    with pytest.raises(ValueError):arc.decode(out.getvalue())


def test_character_cross_owner_copy_all_appearances_generated_and_independent_refs(runtime):
    repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery')
    a,_=repo.import_stream('alice',io.BytesIO(png()),name='a.png',media_type='image/png')
    b,_=repo.import_stream('alice',io.BytesIO(png('blue')),name='b.png',media_type='image/png')
    source=Characters(repo,'alice')
    c=source.save(CharacterInput(name='Hero',description='Identity',appearances=[dict(id='one',name='Chibi',reference_ids=[a['id']],definition_image_id=b['id'],summary='Chibi guide',approved=True),dict(id='two',name='Photo',reference_ids=[b['id']],definition_image_id=a['id'],summary='Photo guide',approved=True)],default_appearance_id='one'))
    source.attach_generated(c['id'],'one',b,appearance_revision=1,run_id='source-run',artifact_id='source-artifact')
    data=export_character(source,c['id'])
    info=preview_character(data)
    assert info['appearance_count']==2 and info['image_count']==2 and len(info['thumbnails'])==2
    target=Characters(repo,'bob');first=import_character(target,data);second=import_character(target,data)
    assert first['id']!=c['id'] and second['name']=='Hero (2)'
    one,two=first['appearances'];assert one['id']!='one' and one['reference_ids']!=two['reference_ids']
    assert one['approved'] and one['summary']=='Chibi guide' and one['generated_images'][0]['asset_id']==one['definition_image_id']
    assert one['generated_images'][0]['run_id']=='portable-import'
    assert source.get(c['id'])['name']=='Hero'
    with pytest.raises(Exception):Characters(repo,'outsider').get(first['id'])
    _,path=repo.asset_path('bob',one['reference_ids'][0]);assert path.read_bytes()==png()
    selected=import_character(target,export_character(source,c['id'],'two'))
    assert len(selected['appearances'])==1 and selected['appearances'][0]['name']=='Photo'


def test_invalid_character_import_does_not_create_assets(runtime):
    repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery');store=Characters(repo,'local')
    data=arc.encode({'schema':'ai2apps.character-backup/v1','character':{'name':'Bad','appearances':[{'id':'a','name':'A','reference_ids':['missing']}] }},{})
    before=repo.list_assets('local')
    with pytest.raises(ValueError):import_character(store,data)
    assert repo.list_assets('local')==before


@pytest.mark.asyncio
async def test_scoped_project_archive_and_character_http(runtime,monkeypatch):
    from types import SimpleNamespace
    from fastapi import FastAPI
    import httpx
    from ai2apps.api.studio_image_workflow import create_image_workflow_router
    from ai2apps.api.gallery import create_gallery_router
    from ai2apps.studio.capability_broker import StudioCapabilityBroker
    from ai2apps.identity import RequestPrincipal
    from ai2apps.studio.image_workflow import asset_root,save_asset,read_asset
    p=RequestPrincipal.legacy_local();instance,_,_=runtime.extension_manager.launch_app('ai2apps.imagine-studio',principal=p)
    capabilities=['image.workflow']
    monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',lambda *a,**k:SimpleNamespace(capabilities=capabilities,mount={'app_key':'example.package','context':{'studioInstanceId':instance.id}},declaration={'id':'example.mini'}))
    key=save_asset(asset_root(runtime,p,'example.package'),png());foreign=save_asset(asset_root(runtime,p,'another.package'),png('blue'))
    app=FastAPI();app.include_router(create_image_workflow_router(lambda:runtime,lambda:p));app.include_router(create_gallery_router(lambda:runtime,lambda:p))
    root='/ai2apps.imagine-studio/mini-app-mounts/mount/image-workflow/archives'
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://fixture') as client:
        r=await client.post(root+'/export',json={'document':{'schema':'example'},'assets':[key]});assert r.status_code==200,r.text
        data=r.content
        preview=await client.post(root+'/inspect',files={'file':('project.zip',data)});assert preview.json()['asset_count']==1
        imported=await client.post(root+'/import',files={'file':('project.zip',data)});assert imported.json()['mapping'][key]==key
        denied=await client.post(root+'/export',json={'document':{},'assets':[foreign]});assert denied.status_code==422
        capabilities.clear();denied=await client.post(root+'/inspect',files={'file':('project.zip',data)});assert denied.status_code==403
        repo=GalleryRepository(runtime.database,runtime.config.paths.artifacts_path/'gallery');c=Characters(repo,p.actor_user_id).save(CharacterInput(name='Portable'))
        data=(await client.get('/gallery/characters/'+c['id']+'/archive')).content
        r=await client.post('/gallery/characters/archive/inspect',files={'file':('x.zip',data)});assert r.status_code==200 and r.json()['name']=='Portable'
        r=await client.post('/gallery/characters/archive/import',files={'file':('x.zip',data)});assert r.status_code==200 and r.json()['name']=='Portable (2)'
