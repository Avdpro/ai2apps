"""No real uploads/accounts: owner, publication and CLI fixtures only."""
import asyncio
import io
import json
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from PIL import Image
from ai2apps.share_works.cli import CLI,PublishError
from ai2apps.share_works.artifacts import normalize
from ai2apps.share_works.service import ShareWorks,register,HOST,KIND
from ai2apps.storage import PlatformDatabase
from ai2apps.events import EventStore,EventNotificationBus
from ai2apps.system_tasks import SystemTaskService


def archive(files):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,data in files.items():z.writestr(name,data)
    return out.getvalue()

@pytest.fixture
def service(tmp_path):
    database=PlatformDatabase(tmp_path/'main.db');database.initialize()
    runtime=NS(database=database,events=EventStore(database),notifications=EventNotificationBus(),
        config=NS(paths=NS(artifacts_path=tmp_path)),legacy_api_key_principal=lambda:NS(actor_user_id='alice'))
    runtime.system_tasks=SystemTaskService(runtime)
    register(runtime)
    svc=runtime.share_works
    class FakeCLI:
        uploaded=[]
        def __init__(self,provider):self.provider=provider
        async def account(self):return 'alice'
        async def inspect(self,repo):return {'provider':self.provider,'account':'alice','repo':repo}
        async def upload(self,*args):self.uploaded.append(args)
        async def deploy(self,*args):pass
    svc.cli_factory=FakeCLI
    return svc

async def prepared(service,provider='hf'):
    return await service.prepare('alice',b'<html><head></head><body>test</body></html>','site.html','Fixture',provider,'alice/site',
        'https://alice-site.'+('hf.space' if provider=='hf' else 'ms.show'))

@pytest.mark.parametrize('name',['../escape.txt','/tmp/file.txt','.env','functions/index.js','_worker.js','assets/../../bad.js'])
def test_reject_unsafe_site(name):
    with pytest.raises(PublishError):normalize(archive({'index.html':b'ok',name:b'bad'}),'site.zip','a'*32)

@pytest.mark.parametrize('html,code',[(b'<img src="https://x.test/a.jpg">','external_resource'),(b'<img src="no.png">','missing_resource'),(b'<img srcset="a.png 2x">','unsupported_srcset')])
def test_missing_resources(html,code):
    with pytest.raises(PublishError,match=code):normalize(html,'a.html','a'*32)

@pytest.mark.parametrize('kind',['html','zip'])
def test_embedded_images_stay_in_original_html(kind):
    import base64,hashlib
    image=io.BytesIO();Image.new('RGB',(2,2),'red').save(image,'PNG')
    original=b'<!doctype html>\n<html><head></head><body><img src="data:image/png;base64,'+base64.b64encode(image.getvalue())+b'"></body></html>\n'
    data=original if kind=='html' else archive({'index.html':original})
    files,manifest,digest=normalize(data,'a.html' if kind=='html' else 'a.zip','a'*32)
    assert files=={'index.html':original} and len(digest)==64
    assert manifest=={'index.html':hashlib.sha256(original).hexdigest()}


def test_zip_keeps_existing_assets_without_extracting_embedded_images():
    import base64
    image=io.BytesIO();Image.new('RGB',(2,2),'red').save(image,'PNG');png=image.getvalue()
    original=b'<img src="photo.png"><img src="data:image/png;base64,'+base64.b64encode(png)+b'">'
    files,_,_=normalize(archive({'index.html':original,'photo.png':png}),'site.zip','a'*32)
    assert files=={'index.html':original,'photo.png':png}


def test_invalid_embedded_images_still_rejected():
    with pytest.raises(PublishError,match='invalid_embedded_image'):
        normalize(b'<img src="data:image/png;base64,aGVsbG8=">','a.html','a'*32)

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['hf','ms'])
async def test_confirmation_idempotency_owner_immutable(service,provider):
    snap=await prepared(service,provider)
    with pytest.raises(PublishError,match='public_confirmation_required'):service.publish('alice',snap['id'],'request1234567890',False)
    assert not service.store.recent('alice')
    first=service.publish('alice',snap['id'],'request1234567890',True)
    assert first['task_id']==service.publish('alice',snap['id'],'request1234567890',True)['task_id']
    with pytest.raises(PermissionError):service.status('bob','request1234567890')
    with pytest.raises(PermissionError):await service.check('bob','hf','alice/site')
    (service.store.path('alice',snap['id'])/'index.html').write_text('changed')
    with pytest.raises(PublishError,match='snapshot_changed'):service.snapshot('alice',snap['id'])

@pytest.mark.asyncio
async def test_restart_dispatch_never_reuploads(service):
    snap=await prepared(service)
    service.publish('alice',snap['id'],'request1234567890',True)
    row=service.store.get('publications','alice','request1234567890');row['dispatched']=True
    service.store.save('publications','alice',row['request_id'],row)
    service.verify=AsyncMock(return_value={'url':'https://fixture.hf.space/'})
    ctx=NS(owner='alice',id=row['task_id'],payload={'request_id':row['request_id']},report=lambda **kw:None)
    before=len(service.cli_factory.uploaded)
    await service.execute(ctx)
    assert len(service.cli_factory.uploaded)==before
    service.verify.assert_awaited_once()

@pytest.mark.asyncio
async def test_reconcile_intent_before_queue_submission(service):
    snap=await prepared(service)
    row={'request_id':'request1234567890','snapshot_id':snap['id'],'title':'fixture','dispatched':False,'task_id':''}
    service.store.save('publications','alice',row['request_id'],row)
    result=service.publish('alice',snap['id'],row['request_id'],True)
    assert result['task_id'].startswith('stask_')

@pytest.mark.asyncio
async def test_account_change_prevents_upload(service):
    snap=await prepared(service);row=service.publish('alice',snap['id'],'request1234567890',True)
    service.cli_factory.inspect=AsyncMock(return_value={'account':'mallory'})
    with pytest.raises(PublishError,match='cli_account_changed'):
        await service.execute(NS(owner='alice',id=row['task_id'],payload={'request_id':row['request_id']},report=lambda **kw:None))
    assert not service.store.get('publications','alice',row['request_id'])['dispatched']

@pytest.mark.parametrize('url',['http://x.hf.space','https://x.hf.space.evil.test','https://u:p@x.hf.space','https://x.hf.space:443','https://x.hf.space/?token=secret','https://127.0.0.1'])
def test_target_url_boundaries(url):
    with pytest.raises(PublishError):ShareWorks.base_url('hf',url)

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['hf','ms'])
async def test_cli_fixed_grammar_and_private_space_rejected(tmp_path,provider):
    exe=tmp_path/('hf' if provider=='hf' else 'ms-hub');exe.write_text('#!/bin/sh\nexit 0\n');exe.chmod(0o700)
    cli=CLI(provider,search_path=str(tmp_path));cli.account=AsyncMock(return_value='alice')
    cli.run=AsyncMock(return_value=json.dumps({'sdk':'static','private':True})) if provider=='hf' else AsyncMock(side_effect=['--repo-type {model,dataset,studio}','alice/site | private | static | CPU | running'])
    with pytest.raises(PublishError,match='space_must_be_public_static'):await cli.inspect('alice/site')
    cli.run.reset_mock();cli.run.side_effect=None;cli.run.return_value='ok';await cli.upload('alice/site',tmp_path,'shares/'+'a'*32,'request1234567890')
    args=cli.run.call_args.args[0]
    assert args[:2]==['upload','alice/site'] and '--token' not in args and '--repo-type' in args
    assert 'space' in args if provider=='hf' else 'studio' in args
    with pytest.raises(PublishError):await cli.upload('alice/../../evil',tmp_path,'shares/'+'a'*32,'request1234567890')

def test_cli_missing_has_no_install_or_login(tmp_path):
    with pytest.raises(PublishError,match='cli_missing'):CLI('hf',search_path=str(tmp_path))

@pytest.mark.asyncio
async def test_cli_hides_secret_errors_and_kills_cancelled_process(tmp_path):
    exe=tmp_path/'hf';exe.write_text('#!/bin/sh\necho "401 token=secret" >&2\nexit 1\n');exe.chmod(0o700)
    cli=CLI('hf',search_path='/bin:'+str(tmp_path))
    with pytest.raises(PublishError) as caught:await cli.run(['auth','whoami'])
    assert str(caught.value)=='cli_not_logged_in'
    exe.write_text('#!/bin/sh\necho $$ > "'+str(tmp_path/'pid')+'"\nsleep 60\n')
    job=asyncio.create_task(cli.run(['auth','whoami']))
    while not (tmp_path/'pid').exists():await asyncio.sleep(.01)
    pid=int((tmp_path/'pid').read_text());job.cancel()
    with pytest.raises(asyncio.CancelledError):await job
    with pytest.raises(ProcessLookupError):os.kill(pid,0)

@pytest.mark.asyncio
async def test_anonymous_verification_requires_exact_bytes(service,monkeypatch):
    from ai2apps.research.provider import SafeHttpClient
    snap=await prepared(service);row=service.publish('alice',snap['id'],'request1234567890',True)
    folder=service.store.path('alice',snap['id'])
    def get(client,url):return NS(url=url,truncated=False,body=(folder/'index.html').read_bytes())
    monkeypatch.setattr(SafeHttpClient,'get',get)
    result=await service.verify('alice',row)
    assert result['anonymous'] and result['verified_files']==1
    monkeypatch.setattr(SafeHttpClient,'get',lambda _,url:NS(url=url,truncated=False,body=b'login page'))
    with pytest.raises(PublishError,match='public_content_mismatch'):await service.verify('alice',row)

@pytest.mark.parametrize('scope',['desktop','mobile'])
def test_api_same_owner_and_mount_scope(service,monkeypatch,scope):
    from dataclasses import replace
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from ai2apps.api.share_works import create_share_works_router
    from ai2apps.identity import RequestPrincipal
    from ai2apps.studio import StudioCapabilityBroker
    principal=replace(RequestPrincipal.legacy_local(),actor_user_id='alice',client_scope=scope)
    monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',lambda *a,**kw:NS(declaration={'id':'ai2apps.share-works'},mount={'app_key':HOST}))
    service.runtime.extension_manager=NS()
    app=FastAPI();app.include_router(create_share_works_router(lambda:service.runtime,lambda:principal))
    with TestClient(app) as client:
        base='/studios/ai2apps.ai-browser/mini-app-mounts/mnt_fixture/share-works'
        assert client.get(base+'/preferences').status_code==200
        assert client.post(base+'/check',json={'provider':'hf'}).json()['account']=='alice'
        original=b'<h1>Fixture</h1><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==">'+b' '*(17*1024*1024+1)
        response=client.post(base+'/prepare',data={'provider':'hf','repo':'alice/site','title':'Fixture','application_url':'https://alice-site.hf.space'},files={'file':('test.html',original,'text/html')})
        assert response.status_code==200,response.text
        snap=response.json()
        assert snap['files']==1
        preview=client.get(base+'/snapshots/'+snap['id']+'/preview')
        assert preview.status_code==200
        assert preview.json()['html'].encode()==original
        with monkeypatch.context() as limits:
            limits.setattr('ai2apps.api.share_works.MAX_INPUT',len(original)-1)
            limited=client.get(base+'/snapshots/'+snap['id']+'/preview')
            assert limited.status_code==413
            assert limited.json()['detail']=='preview_size_limit'
        assert client.post(base+'/publish',json={'snapshot_id':snap['id'],'request_id':'request1234567890','confirmed':False}).status_code==422
        assert client.post(base+'/publish',json={'snapshot_id':snap['id'],'request_id':'request1234567890','confirmed':True}).status_code==200
        assert len(client.get(base+'/history').json()['items'])==1
        monkeypatch.setattr(StudioCapabilityBroker,'mounted_mini_app',lambda *a,**kw:NS(declaration={'id':'other.mini'},mount={'app_key':HOST}))
        assert client.get(base+'/history').status_code==403

@pytest.mark.parametrize('css',[b'@import "https://evil.test/x.css";',b'.x{background:url(https://evil.test/x.png)}'])
def test_external_css_rejected(css):
    with pytest.raises(PublishError):normalize(archive({'index.html':b'<link href="a.css">','a.css':css}),'site.zip','a'*32)

def test_builtin_declaration_and_empty_probe_catalog():
    from ai2apps.browser.builtin_mini_apps import definitions
    from ai2apps.browser.mini_apps import capability_catalog
    minis,resources=definitions()
    mini=next(item for item in minis if item['id']=='ai2apps.share-works')
    assert mini['owner_service']=={'schema':'ai2apps.mini-app-owner-service/v1','host':HOST}
    assert 'builtin_mini_apps/share-works/web/share.js' in resources

@pytest.fixture
def sdk_api():
    class Session:
        def __init__(self):self.adapters=[]
        def mount(self,*args):self.adapters.append(args)
    class Legacy:
        def __init__(self):self._session=Session();self.calls=[]
        def create_commit(self,*args,**kwargs):self.calls.append((args,kwargs))
    return NS(whoami=lambda:NS(username='alice'),legacy=Legacy(),openapi=NS(_max_retries=5,get_studio=lambda *a:{'sdk_type':'static','visibility':5}))


def test_ms_sdk_reuses_identity_no_create_and_no_uncertain_retry(service,sdk_api):
    from ai2apps.share_works.ms_worker import inspect,upload,WorkerError
    assert inspect(sdk_api,'alice/site')['transport']=='official-sdk-existing-login'
    folder=service.store.path('alice','a'*32);folder.mkdir(parents=True);(folder/'index.html').write_text('test')
    import hashlib
    manifest={'index.html':hashlib.sha256(b'test').hexdigest()}
    manifest_path=folder.parent/(folder.name+'.manifest.json');manifest_path.write_text(json.dumps(manifest))
    body={'repo':'alice/site','remote_path':'shares/'+'a'*32,'directory':str(folder),'manifest_path':str(manifest_path),'request_id':'r'*16}
    assert upload(sdk_api,body)=={'files':1,'commits':1}
    call=sdk_api.legacy.calls[0]
    assert call[0][1]=='studio' and call[0][2][0]['action']=='create'
    assert call[0][2][0]['path']=='shares/'+'a'*32+'/index.html'
    assert all(adapter.max_retries.total==0 for _,adapter in sdk_api.legacy._session.adapters)
    assert sdk_api.openapi._max_retries==1
    before=len(sdk_api.legacy.calls);(folder/'index.html').write_text('changed')
    with pytest.raises(WorkerError,match='snapshot_changed'):upload(sdk_api,body)
    assert len(sdk_api.legacy.calls)==before
    with pytest.raises(WorkerError,match='space_account_mismatch'):inspect(sdk_api,'other/site')


def test_ms_sdk_unknown_commit_reply_not_retried(service,sdk_api):
    from ai2apps.share_works.ms_worker import upload
    import hashlib
    folder=service.store.path('alice','b'*32);folder.mkdir(parents=True);(folder/'index.html').write_text('test')
    manifest_path=folder.parent/(folder.name+'.manifest.json');manifest_path.write_text(json.dumps({'index.html':hashlib.sha256(b'test').hexdigest()}))
    called=[]
    def commit(*a,**kw):called.append(a);raise TimeoutError('unknown response')
    sdk_api.legacy.create_commit=commit
    with pytest.raises(TimeoutError):upload(sdk_api,{'repo':'alice/site','remote_path':'shares/'+'b'*32,'directory':str(folder),'manifest_path':str(manifest_path),'request_id':'r'*16})
    assert len(called)==1

@pytest.mark.parametrize('owner',['arbitrary.studio','unrelated.owner'])
def test_owner_service_declaration_is_generic_and_does_not_delegate(owner):
    from ai2apps.studio.owner_services import validate_owner_service
    validate_owner_service({'schema':'ai2apps.mini-app-owner-service/v1','host':owner},owner,[{'studio':owner}])
    with pytest.raises(ValueError):validate_owner_service({'schema':'ai2apps.mini-app-owner-service/v1','host':'foreign.owner'},owner,[{'studio':owner}])
    with pytest.raises(ValueError):validate_owner_service({'schema':'ai2apps.mini-app-owner-service/v1','host':owner},owner,[{'studio':'foreign.owner'}])


def test_external_cli_does_not_inherit_local_model_credential_overrides(tmp_path,monkeypatch):
    from ai2apps.share_works import environment
    monkeypatch.setenv('AI2APPS_SUPERVISED','helper')
    monkeypatch.setenv('HF_HOME','/app/isolated/hf')
    monkeypatch.setenv('HF_TOKEN_PATH','/app/isolated/hf/token')
    monkeypatch.setenv('HF_TOKEN','never-forward')
    monkeypatch.setattr(environment,'terminal_config',lambda:{'HF_HOME':'/terminal/hf'})
    exe=tmp_path/'hf';exe.write_text('#!/bin/sh\nexit 0');exe.chmod(0o700)
    cli=CLI('hf',search_path=str(tmp_path))
    assert cli.env['HF_HOME']=='/terminal/hf'
    assert 'HF_TOKEN_PATH' not in cli.env and 'HF_TOKEN' not in cli.env
    assert os.environ['HF_HOME']=='/app/isolated/hf'

@pytest.mark.parametrize('where',['start','end','implicit'])
def test_hf_static_additive_metadata_preserves_exact_original(where):
    from ai2apps.share_works.hf_public import matches_static_html
    original=b'<html><head><meta charset="utf-8"></head><body>Unchanged body</body></html>'
    injection=b'<script>window.huggingface={variables:{"SPACE_CREATOR_USER_ID":"test"}};</script><meta property="og:title" content="Fixture"><meta name="twitter:card" content="summary_large_image">'
    if where=='implicit':original=original.replace(b'<head>',b'').replace(b'</head>',b'')
    public=injection+original if where=='implicit' else (original.replace(b'<head>',b'<head>'+injection) if where=='start' else original.replace(b'</head>',injection+b'</head>'))
    assert matches_static_html(original,public)==(True,True)
    assert matches_static_html(original,original)==(True,False)
    assert matches_static_html(original,public.replace(b'Unchanged body',b'Changed body'))==(False,False)

@pytest.mark.parametrize('extra',[
 b'<script>window.huggingface={variables:{}};alert(1)</script>',
 b'<script src="https://evil.test/x"></script>',
 b'<script>window.huggingface={variables:{}};</script><meta http-equiv="refresh" content="0;url=https://evil.test">',
 b'<script>window.huggingface={variables:{}};</script><script>alert(1)</script>',
 b'<script>window.huggingface={variables:{"X":()=>alert(1)}};</script>',
])
def test_hf_static_metadata_never_allows_arbitrary_edits(extra):
    from ai2apps.share_works.hf_public import matches_static_html
    original=b'<html><head></head><body>Original</body></html>'
    assert matches_static_html(original,original.replace(b'</head>',extra+b'</head>'))==(False,False)


def test_verification_failures_are_not_all_deployment_waits():
    from ai2apps.share_works.service import verification_failure
    from ai2apps.research.provider import WebProviderError
    import ssl
    assert verification_failure(PublishError('public_content_mismatch'))==('public_content_mismatch',False)
    assert verification_failure(WebProviderError('Web request failed with HTTP 404'))==('public_http_404',True)
    assert verification_failure(WebProviderError('Web request failed with HTTP 403'))==('public_http_403',False)
    assert verification_failure(ssl.SSLCertVerificationError('certificate verify failed'))==('public_tls_error',False)

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['hf','ms'])
async def test_platform_html_policy_only_applies_to_hf(service,monkeypatch,provider):
    from ai2apps.research.provider import SafeHttpClient
    snap=await prepared(service,provider)
    row=service.publish('alice',snap['id'],'request1234567890',True)
    original=(service.store.path('alice',snap['id'])/'index.html').read_bytes()
    body=original.replace(b'</head>',b'<script>window.huggingface={variables:{"SPACE_CREATOR_USER_ID":"fixture"}};</script></head>')
    monkeypatch.setattr(SafeHttpClient,'get',lambda _,url:NS(url=url,truncated=False,body=body))
    if provider=='ms':
        with pytest.raises(PublishError,match='public_content_mismatch'):await service.verify('alice',row)
    else:
        result=await service.verify('alice',row)
        assert result['html_platform_metadata_added'] is True and result['anonymous'] is True
        assert result['public_html_sha256']!=snap['digest']

@pytest.mark.asyncio
async def test_permanent_mismatch_fails_without_waiting_or_reupload(service):
    snap=await prepared(service)
    row=service.publish('alice',snap['id'],'request1234567890',True)
    service.verify=AsyncMock(side_effect=PublishError('public_content_mismatch'))
    ctx=NS(owner='alice',id=row['task_id'],payload={'request_id':row['request_id']},report=lambda **kw:None)
    with pytest.raises(PublishError,match='public_content_mismatch'):await service.execute(ctx)
    service.verify.assert_awaited_once()
    assert service.store.get('publications','alice',row['request_id'])['last_verification_error']=='public_content_mismatch'

@pytest.mark.asyncio
async def test_public_resources_verify_with_bounded_concurrency(service,monkeypatch):
    from ai2apps.research.provider import SafeHttpClient
    from urllib.parse import unquote
    import threading,time
    files={'index.html':b'<html><head></head><body>Fixture</body></html>',**{f'file{i}.txt':str(i).encode() for i in range(7)}}
    snap=await service.prepare('alice',archive(files),'site.zip','Fixture','hf','alice/site','https://alice-site.hf.space')
    row=service.publish('alice',snap['id'],'request1234567890',True)
    folder=service.store.path('alice',snap['id']);lock=threading.Lock();active=0;peak=0
    def get(_,url):
        nonlocal active,peak
        with lock:active+=1;peak=max(peak,active)
        try:
            time.sleep(.02)
            name=unquote(url.split('/shares/'+snap['id']+'/',1)[1])
            return NS(url=url,truncated=False,body=(folder/name).read_bytes())
        finally:
            with lock:active-=1
    monkeypatch.setattr(SafeHttpClient,'get',get)
    result=await service.verify('alice',row)
    assert result['verified_files']==8 and 1<peak<=4

@pytest.mark.parametrize('url,accepted',[
 ('https://us.aws.cdn.hf.co/opaque?signature=fixture',True),
 ('https://eu.aws.cdn.hf.co/opaque',True),
 ('https://evil.test/opaque',False),('https://us.aws.cdn.hf.co.evil.test/opaque',False),
 ('http://us.aws.cdn.hf.co/opaque',False),('https://user:secret@us.aws.cdn.hf.co/opaque',False),
 ('https://us.aws.cdn.hf.co:8080/opaque',False),
])
def test_hf_static_official_cdn_scope(url,accepted):
    from ai2apps.share_works.hf_public import is_static_cdn_url
    assert is_static_cdn_url(url) is accepted

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['hf','ms'])
async def test_cdn_redirect_requires_provider_scope_and_original_bytes(service,monkeypatch,provider):
    from ai2apps.research.provider import SafeHttpClient
    snap=await prepared(service,provider);row=service.publish('alice',snap['id'],'request1234567890',True)
    body=(service.store.path('alice',snap['id'])/'index.html').read_bytes()
    monkeypatch.setattr(SafeHttpClient,'get',lambda _,url:NS(url='https://us.aws.cdn.hf.co/opaque?signature=fixture',truncated=False,body=body))
    if provider=='hf':
        result=await service.verify('alice',row)
        assert result['anonymous'] and result['resource_origins']==['us.aws.cdn.hf.co']
        monkeypatch.setattr(SafeHttpClient,'get',lambda _,url:NS(url='https://us.aws.cdn.hf.co/opaque',truncated=False,body=b'wrong'))
        with pytest.raises(PublishError,match='public_content_mismatch'):await service.verify('alice',row)
    else:
        with pytest.raises(PublishError,match='public_redirect_outside_snapshot'):await service.verify('alice',row)

@pytest.mark.asyncio
async def test_target_preferences_restore_history_and_keep_providers_isolated(service):
    hf=await prepared(service,'hf')
    # Existing snapshots seed preferences without migration or publication.
    with service.store.connect() as db:db.execute('DELETE FROM preferences')
    assert service.preferences('alice')['targets']['hf']['application_url']==hf['application_url']
    await service.check('alice','ms','alice/studio')
    result=service.preferences('alice')['targets']
    assert result['hf']['repo']=='alice/site' and result['ms']['repo']=='alice/studio'
    from ai2apps.share_works.store import Store
    reopened=Store(service.store.root)
    assert reopened.get('preferences','alice','ms')['repo']=='alice/studio'
    with pytest.raises(PermissionError):service.preferences('bob')
    with pytest.raises(KeyError):reopened.get('preferences','bob','ms')

@pytest.mark.asyncio
async def test_hf_target_uses_official_host_not_repo_guess(service,monkeypatch):
    cli=object.__new__(CLI);cli.provider='hf';cli.account=AsyncMock(return_value='alice')
    cli.run=AsyncMock(return_value=json.dumps({'sdk':'static','private':False,'host':'https://official-site.static.hf.space'}))
    service.cli_factory=lambda provider:cli
    result=await service.check('alice','hf','alice/site')
    assert result['application_url']=='https://official-site.static.hf.space/'
    assert service.preferences('alice')['targets']['hf']['application_url']==result['application_url']
    cli.run=AsyncMock(return_value=json.dumps({'sdk':'static','private':False,'host':'https://evil.test'}))
    with pytest.raises(PublishError,match='invalid_application_url'):await service.check('alice','hf','alice/site')

def test_preferences_in_mobile_curated_routes():
    rows=json.loads((Path(__file__).parents[1]/'web/owner_studio_routes.json').read_text())
    assert {'module':'share_works','method':'GET','path':'/v1/platform/studios/{studio_id}/mini-app-mounts/{mount_id}/share-works/preferences'} in rows

@pytest.mark.parametrize('host,code,message,accepted',[
 ('ai2apps-shares.ms.show','PreconditionFailed','function is pending state, please try later',True),
 ('evil.test','PreconditionFailed','function is pending state, please try later',False),
 ('ai2apps-shares.ms.show','PreconditionFailed','permission denied',False),
 ('ai2apps-shares.ms.show','Other','function is pending state, please try later',False),
])
def test_ms_explicit_pending_reply_only(host,code,message,accepted):
    from urllib.error import HTTPError
    from ai2apps.share_works.service import ms_deployment_pending,verification_failure
    raw=json.dumps({'Code':code,'Message':message}).encode()
    cause=HTTPError('https://'+host+'/shares/id/index.html',412,'Precondition Failed',{},io.BytesIO(raw))
    error=RuntimeError('Web request failed with HTTP 412');error.__cause__=cause
    assert ms_deployment_pending(error) is accepted
    assert verification_failure(PublishError('deployment_pending'))==('deployment_pending',True)
    assert verification_failure(error)==('public_http_412',False)

def test_ms_canonical_reader_preserves_file_evidence_and_legacy_records():
    row={'provider':'ms','repo':'alice/site','snapshot_id':'a'*32}
    original={'anonymous':True,'url':'https://alice-site.ms.show/shares/'+'a'*32+'/index.html','digest':'fixture'}
    result=ShareWorks.reader_result(row,original)
    assert result['url']=='https://modelscope.cn/studios/alice/site?mode=full&app_path=%2Fshares%2F'+'a'*32+'%2Findex.html'
    assert result['content_url']==original['url'] and result['digest']=='fixture'
    assert ShareWorks.reader_result(row,result)==result
    assert original['url'].startswith('https://alice-site.ms.show/')
    assert ShareWorks.reader_result({**row,'provider':'hf'},original)==original
    with pytest.raises(PublishError):ShareWorks.reader_result({**row,'snapshot_id':'../../bad'},original)


@pytest.mark.asyncio
async def test_social_cover_materializes_only_in_reviewed_snapshot(service):
    import base64,re
    out=io.BytesIO();Image.new('RGB',(800,500),'blue').save(out,'PNG')
    uri='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
    original=('<html><head><meta property="og:image" content="'+uri+'"><meta name="twitter:image" content="'+uri+'"></head><body><img src="'+uri+'"></body></html>').encode()
    snap=await service.prepare('alice',original,'work.html','Work','hf','alice/site','https://alice-site.hf.space')
    assert snap['files']==2
    folder=service.store.path('alice',snap['id']);text=(folder/'index.html').read_text()
    links=re.findall(r'<meta[^>]+content="([^"]+)"',text)
    assert len(set(links))==1 and links[0].startswith('https://alice-site.hf.space/shares/'+snap['id']+'/share-cover-')
    assert '<img src="'+uri+'">' in text
    name=links[0].rsplit('/',1)[1]
    with Image.open(folder/name) as cover:assert max(cover.size)==600
    assert len(service.snapshot('alice',snap['id'])['manifest'])==2
    assert not service.store.recent('alice')  # preparation is not publication
