import pytest
from ai2apps.intelligence.images import weibo_image
from ai2apps.intelligence import images
from ai2apps.tests.test_intelligence_api import client,channel_and_source, legacy_run
from ai2apps.intelligence import service


def test_cdn_boundary():
    assert weibo_image('https://wx4.sinaimg.cn/orj480/a.jpg')
    for url in ['http://wx4.sinaimg.cn/a','https://tvax4.sinaimg.cn/a','https://wx4.sinaimg.cn.evil.test/a','https://wx4.sinaimg.cn:444/a','https://user@wx4.sinaimg.cn/a','http://127.0.0.1/a']:
        assert not weibo_image(url)


def test_image_requires_owned_saved_reference(client,monkeypatch):
    c,s=channel_and_source(client)
    url='https://wx4.sinaimg.cn/orj480/photo.jpg'
    async def digest(*args):
        return [{'title':'图片','summary':'摘要','body':'正文','sources':[], 'images':[{'url':url}]}]
    monkeypatch.setattr(service,'digest',digest)
    run=legacy_run(client,c['id'])
    client.post('/intelligence/runs/'+run['id']+'/finish',json={'pages':[{'url':'https://example.com/a','source_id':s['id'],'text':'正文'}],'logs':[]})
    article=client.get('/intelligence').json()['articles'][0]
    called=[]
    async def load(value):
        called.append(value);return b'\xff\xd8\xfftest','image/jpeg'
    monkeypatch.setattr(images,'load_public_image',load)
    base='/intelligence/articles/'+article['id']+'/image'
    assert client.get(base,params={'url':'https://example.com/private'}).status_code==404
    assert client.get('/intelligence/articles/not-owned/image',params={'url':url}).status_code==404
    assert called==[]
    response=client.get(base,params={'url':url})
    assert response.status_code==200 and response.headers['content-type']=='image/jpeg'
    assert response.headers['cache-control'].startswith('private')
