import pytest
from ai2apps.remote.visitor_html_ai import messages,extract_document

def test_rules_current_code_and_followup():
    result=messages({'prompt':'改成蓝色','history':['星空文字'],'height':420},'<html>old</html>')
    assert result[0]['role']=='system'
    assert '420px' in result[0]['content'] and 'allow-scripts' in result[0]['content']
    assert result[-1]['content']=='改成蓝色'
    assert '<html>old</html>' in result[-2]['content']

@pytest.mark.parametrize('body,current',[({'prompt':''},''),({'prompt':'x','height':1},''),({'prompt':'x','history':[{}]},''),({'prompt':'x'},'x'*131073)])
def test_context_limits(body,current):
    with pytest.raises(ValueError):messages(body,current)

def test_extract_accepts_code_fence_and_blocks():
    assert extract_document({'choices':[{'message':{'content':'```html\n<!doctype html><html>hi</html>\n```'}}]}).startswith('<!doctype')
    assert extract_document({'choices':[{'message':{'content':[{'type':'text','text':'<html>hi</html>'}]}}]})=='<html>hi</html>'

@pytest.mark.parametrize('content',['','解释一下','<html>truncated','<script>alert(1)</script>'])
def test_incomplete_output_never_replaces_original(content):
    with pytest.raises(ValueError):extract_document({'choices':[{'message':{'content':content}}]})

def test_authoring_route_reuses_authenticated_model_and_saves_html(tmp_path):
    from types import SimpleNamespace
    from fastapi import FastAPI,Request
    from fastapi.testclient import TestClient
    from ai2apps.storage import PlatformDatabase
    from ai2apps.api.remote import create_remote_router
    from ai2apps.identity import RequestPrincipal
    from ai2apps.remote.visitor_assets import VisitorAssets
    from dataclasses import replace
    db=PlatformDatabase(tmp_path/'db.sqlite');db.initialize()
    principal=RequestPrincipal.legacy_local()
    runtime=SimpleNamespace(database=db,model_manager=SimpleNamespace(resolve_default_model=lambda _: 'test-model'))
    app=FastAPI();app.include_router(create_remote_router(lambda:runtime,lambda:principal))
    seen=[]
    @app.post('/v1/chat/completions')
    async def completion(request:Request):
        seen.append((await request.json(),request.headers.get('authorization')))
        return {'choices':[{'message':{'content':'<!doctype html><html><body>Stars</body></html>'}}]}
    with TestClient(app) as client:
        r=client.post('/remote/visitor-space/html-ai',json={'prompt':'星空文字'},headers={'Authorization':'Bearer test-only'})
        assert r.status_code==200
        assert seen[0][1]=='Bearer test-only'
        assert seen[0][0]['model']=='test-model'
        assert seen[0][0]['messages'][0]['role']=='system'
        meta,path=VisitorAssets(db,principal.installation_id).get(r.json()['asset']['id'])
        assert meta['kind']=='html' and b'Stars' in path.read_bytes()
        principal=replace(principal,authentication_type='owner_home_lease')
        assert client.post('/remote/visitor-space/html-ai',json={'prompt':'x'}).status_code==403
        assert len(seen)==1
