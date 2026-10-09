import pytest
from ai2apps.intelligence.models import Page, cover_url, ChannelInput
from ai2apps.intelligence.store import IntelligenceStore
from ai2apps.intelligence import service


def test_cover_url_rejects_private_and_preserves_signed_query():
    for value in ['javascript:alert(1)','data:image/png;base64,x','http://127.0.0.1/x','http://10.0.0.1/x','https://user:pass@example.com/x']:
        assert cover_url(value)==''
    signed='https://cdn.example.com/photo.jpg?sig=a%2Fb&utm_source=required'
    assert Page(source_id='s',url='https://example.com/a',text='body',image_url=signed).image_url==signed


@pytest.mark.asyncio
async def test_cover_comes_from_cited_evidence_only(monkeypatch):
    async def model(runtime,request,principal,id,instruction,data,validate):
        return validate({'articles':[{'title':'title','summary':'summary','body':'facts [2]','evidence_ids':[2]}]})
    monkeypatch.setattr(service,'model_json',model)
    pages=[{'url':'https://example.com/'+str(i),'title':'title','source_name':'source','retrieved_at':'now','text':'text','source_id':'s','image_url':'https://cdn.example.com/'+str(i)+'.jpg','images':[{'url':'https://cdn.example.com/detail'+str(i)+'.jpg','alt':'detail'}]} for i in range(2)]
    pages[1].update(content_type='video',duration_seconds=125,page_count=None)
    article=(await service.digest(None,None,None,{'id':'c'},pages,[]))[0]
    assert article['sources'][0]['content_type']=='video'
    assert article['sources'][0]['duration_seconds']==125
    assert article['cover_image']=={'url':pages[1]['image_url'],'source_url':pages[1]['url']}
    assert article['sources'][0]['source_id']=='s'
    assert [i['url'] for i in article['images']]==[pages[1]['image_url'],pages[1]['images'][0]['url']]


def test_existing_cover_update_is_scoped_and_does_not_modify_article_text(tmp_path):
    import json
    s=IntelligenceStore(tmp_path)
    c=s.save_channel('a',ChannelInput(name='频道',interests='新闻').model_dump())
    article={'title':'title','body':'original','sources':[{'url':'https://example.com/a'}]}
    with s.connect() as db:db.execute('INSERT INTO articles VALUES(?,?,?,?)',('article','a',c['id'],json.dumps(article)))
    with pytest.raises(KeyError):s.save_cover('b','article','https://example.com/a','https://cdn.example.com/a.jpg')
    with pytest.raises(ValueError):s.save_cover('a','article','https://other.example.com/a','https://cdn.example.com/a.jpg')
    result=s.save_cover('a','article','https://example.com/a','https://cdn.example.com/a.jpg')
    assert result['body']=='original' and result['cover_image']['source_url']=='https://example.com/a'


def test_remote_image_policy_is_limited_to_intelligence_html():
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse
    from fastapi.testclient import TestClient
    from ai2apps.http_security import LocalBrowserSecurityHeadersMiddleware
    app=FastAPI();app.add_middleware(LocalBrowserSecurityHeadersMiddleware)
    @app.get('/{path:path}')
    def html(path):
        return HTMLResponse('ok',headers={'Content-Security-Policy':"default-src 'none'"} if path.endswith('explicit') else {})
    client=TestClient(app)
    for path in ['/admin/app-content/ai2apps.intelligence','/mobile/app-content/ai2apps.intelligence']:
        policy=client.get(path).headers['content-security-policy']
        assert "img-src 'self' data: blob: https:;" in policy
        assert "connect-src 'self' ws: wss:;" in policy
    for path in ['/','/admin/app-content/ai2apps.knowledge','/admin/app-content/ai2apps.intelligence/other']:
        assert "img-src 'self' data: blob:;" in client.get(path).headers['content-security-policy']
    assert client.get('/explicit').headers['content-security-policy']=="default-src 'none'"


def test_article_images_are_scoped_deduplicated_and_validated(tmp_path):
    import json
    from ai2apps.intelligence.models import ArticleImages
    s=IntelligenceStore(tmp_path)
    c=s.save_channel('a',ChannelInput(name='频道',interests='新闻').model_dump())
    with s.connect() as db:db.execute('INSERT INTO articles VALUES(?,?,?,?)',('article','a',c['id'],json.dumps({'title':'title','body':'body','sources':[{'url':'https://example.com/a'}]})))
    valid=ArticleImages(source_url='https://example.com/a',images=[{'url':'http://127.0.0.1/a'},{'url':'https://cdn.example.com/a.jpg'}])
    images=[i.model_dump() for i in valid.images]
    with pytest.raises(KeyError):s.save_images('b','article',valid.source_url,images)
    with pytest.raises(ValueError):s.save_images('a','article','https://else.example.com/',images)
    result=s.save_images('a','article',valid.source_url,images,'https://cdn.example.com/a.jpg')
    assert len(result['images'])==1 and result['cover_image']['url']==result['images'][0]['url']
    assert result['body']=='body'
    result=s.save_images('a','article',valid.source_url,[{'url':'https://cdn.example.com/detail.jpg','alt':'detail'}])
    assert len(result['images'])==2
    with pytest.raises(ValueError):s.save_images('a','article',valid.source_url,[])
    assert len(s.get('articles','a','article')['images'])==2
