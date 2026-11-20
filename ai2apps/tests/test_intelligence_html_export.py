import asyncio
import base64
import io
import json
import re
import pytest
from PIL import Image
from ai2apps.tests.test_intelligence_transfer import seed
from ai2apps.intelligence.transfer import selected_rows
from ai2apps.intelligence.html_export import build_html, image_bytes


def png():
    out=io.BytesIO();Image.new('RGB',(16,16),'red').save(out,format='PNG');return out.getvalue()


@pytest.mark.asyncio
async def test_safe_inline_offline_content_and_dedup(tmp_path):
    s,c,a=seed(tmp_path/'s');selected=selected_rows(s,'alice',c['id'])
    article=selected['articles'][0]['data'];article['title']='</script><img src=x onerror=alert(1)>'
    article['cover_image']=article['images'][0]
    article['images'].append({'url':'https://example.org/alias.jpg','alt':'alias'})
    calls=[]
    def loader(store,owner,url,quality):calls.append(url);return png(),'image/png'
    payload,info=await build_html(s,'alice',selected,loader=loader)
    text=payload.decode()
    assert len(calls)==2 and info['images']==1
    assert '<img src=x' not in text and '&lt;/script&gt;' in text
    assert text.index('Paragraph [1]')<text.index('<section><h3>来源')
    assert 'data:image/png;base64,' in text
    assert 'src="https:' not in text and 'src="http:' not in text
    assert 'src="data:image/png;base64,' in text and 'Content-Security-Policy' in text
    assert '<input' not in text and '<select' not in text and '<script>' not in text
    assert "script-src &#x27;none&#x27;" in text
    assert 'data-image=' not in text
    assert '_transfer_origin' not in text and 'feedback' not in text


@pytest.mark.asyncio
async def test_missing_images_are_explicit_and_not_remote_loaded(tmp_path):
    s,c,a=seed(tmp_path/'s')
    def failed(*args):raise ValueError('cannot read')
    data,info=await build_html(s,'alice',selected_rows(s,'alice',c['id']),loader=failed)
    assert info['images_failed']==1 and info['images']==0
    assert 'Image not embedded' not in data.decode()
    assert 'Missing images' not in data.decode()
    assert 'missing</p>' not in data.decode()
    assert info['missing_images'][0]['reason']
    assert '<img' not in data.decode()


@pytest.mark.asyncio
async def test_cancel_in_flight_does_not_continue_to_render(tmp_path):
    s,c,a=seed(tmp_path/'s')
    import threading
    event=threading.Event();started=threading.Event()
    def loader(*args):started.set();event.wait(2);return png(),'image/png'
    task=asyncio.create_task(build_html(s,'alice',selected_rows(s,'alice',c['id']),loader=loader))
    while not started.is_set():await asyncio.sleep(.01)
    task.cancel();event.set()
    with pytest.raises(asyncio.CancelledError):await task


def test_local_image_quality_and_owner_scoping(tmp_path):
    import hashlib
    from ai2apps.intelligence.manual_import import asset_path
    s,c,a=seed(tmp_path/'s');raw=png();token=hashlib.sha256(raw).hexdigest();path=asset_path(s,'alice',token);path.parent.mkdir(parents=True);path.write_bytes(raw)
    url='/v1/platform/intelligence/imports/'+token+'/image.png'
    assert image_bytes(s,'alice',url,'original')==(raw,'image/png')
    compressed,mime=image_bytes(s,'alice',url,'reading');assert mime=='image/jpeg'
    with pytest.raises(FileNotFoundError):image_bytes(s,'bob',url,'reading')


@pytest.mark.parametrize('url',['http://127.0.0.1/picture','http://localhost/picture','file:///etc/passwd','javascript:alert(1)','/v1/platform/intelligence/imports/../secrets/picture'])
def test_image_loader_rejects_untrusted_targets_without_network(tmp_path,monkeypatch,url):
    from ai2apps.research.provider import SafeHttpClient
    def fail(*args,**kwargs):raise AssertionError('network must not be called')
    monkeypatch.setattr(SafeHttpClient,'get',fail)
    s,c,a=seed(tmp_path/'s')
    with pytest.raises(ValueError):image_bytes(s,'alice',url,'reading')


@pytest.mark.asyncio
@pytest.mark.parametrize('include_toc',[True,False])
async def test_contents_option_and_native_collapsed_cards(tmp_path,include_toc):
    s,c,a=seed(tmp_path/'s')
    payload,info=await build_html(s,'alice',selected_rows(s,'alice',c['id']),loader=lambda *args:(png(),'image/png'),include_toc=include_toc)
    text=payload.decode()
    assert ('<nav>' in text)==include_toc
    assert ('返回目录' in text)==include_toc
    assert info['include_toc']==include_toc
    if not include_toc:
        assert '<span class="read-ribbon">' in text
        assert '<img class="card-cover" src="data:' in text
        assert '<details class="article-card" open' not in text
        assert '<div class="article-content">' in text
        assert text.index('</summary>')<text.index('Paragraph [1]')


@pytest.mark.asyncio
@pytest.mark.parametrize('language,expected',[('zh','由 &lt;Alice&gt; 的 AI2Apps 总结'),('en','Summarized by &lt;Alice&gt;’s AI2Apps')])
async def test_export_credit_replaces_channel_interests(tmp_path,language,expected):
    s,c,a=seed(tmp_path/'s');selected=selected_rows(s,'alice',c['id'])
    selected['channels'][0]['data'].update(output_language=language,interests='PRIVATE CHANNEL INTERESTS')
    payload,_=await build_html(s,'alice',selected,loader=lambda *args:(png(),'image/png'),author_name='<Alice>')
    text=payload.decode()
    assert 'PRIVATE CHANNEL INTERESTS' not in text
    assert '<a href="https://ai2apps.com/" target="_blank" rel="noopener noreferrer">'+expected+'</a>' in text

@pytest.mark.asyncio
@pytest.mark.parametrize('actor,offline,expected',[('alice',False,'Alice'),('bob',False,None),('alice',True,None)])
async def test_export_credit_name_is_owner_bound(actor,offline,expected):
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    import httpx
    from ai2apps.intelligence.export_jobs import export_author_name
    response=httpx.Response(200,json={'user':{'id':actor,'displayName':'Alice','email':'private@example.org'}})
    cloud=SimpleNamespace(request=AsyncMock(return_value=response))
    result=await export_author_name(SimpleNamespace(cloud=cloud,offline_mode=offline),'alice')
    assert result==expected
    if offline:cloud.request.assert_not_called()
    else:assert response.is_closed


def test_image_proxy_candidates_are_bounded_and_do_not_invent_paths():
    from ai2apps.intelligence.html_export import image_candidates
    original='https://example.org/wp-content/uploads/watch.jpg'
    assert image_candidates('https://i0.wp.com/example.org/cdn-cgi/image/anim%3Dfalse/wp-content/uploads/watch.jpg?w=329')==[
        'https://i0.wp.com/example.org/cdn-cgi/image/anim%3Dfalse/wp-content/uploads/watch.jpg?w=329',
        'https://example.org/cdn-cgi/image/anim%3Dfalse/wp-content/uploads/watch.jpg',original]
    for url in ('https://evil.test/example.org/watch.jpg','https://i0.wp.com/localhost/watch.jpg','https://i0.wp.com/user@evil.test/watch.jpg'):
        assert image_candidates(url)==[url]


@pytest.mark.asyncio
async def test_failed_proxy_recovers_original_and_keeps_offline_image(tmp_path):
    s,c,a=seed(tmp_path/'s');selected=selected_rows(s,'alice',c['id'])
    proxy='https://i0.wp.com/example.org/cdn-cgi/image/width=300/photo.jpg?w=300'
    selected['articles'][0]['data']['images']=[{'url':proxy}]
    calls=[]
    def loader(store,owner,url,quality):
        calls.append(url)
        if url!='https://example.org/photo.jpg':raise ValueError('Web request failed with HTTP 404')
        return png(),'image/png'
    payload,info=await build_html(s,'alice',selected,loader=loader)
    assert len(calls)==3 and info['images_recovered']==1 and info['images_failed']==0
    assert b'src="data:image/png;base64,' in payload
    assert b'Missing images' not in payload


@pytest.mark.asyncio
async def test_no_fake_username_when_verified_name_unavailable(tmp_path):
    s,c,a=seed(tmp_path/'s')
    payload,_=await build_html(s,'alice',selected_rows(s,'alice',c['id']),loader=lambda *args:(png(),'image/png'))
    assert '本地用户' not in payload.decode() and '由 AI2Apps 总结' in payload.decode()


@pytest.mark.asyncio
@pytest.mark.parametrize('include_toc',[True,False])
async def test_large_reading_html_compacts_body_but_preserves_cover(tmp_path,monkeypatch,include_toc):
    import ai2apps.intelligence.html_export as export
    s,c,a=seed(tmp_path/'s');selected=selected_rows(s,'alice',c['id'])
    article=selected['articles'][0]['data']
    article['cover_image']={'url':'https://example.org/cover.jpg'}
    article['images']=[article['cover_image'],{'id':'body','url':'https://example.org/body.jpg'}]
    image=Image.effect_noise((1200,1000),80).convert('RGB');out=io.BytesIO();image.save(out,format='JPEG',quality=90);raw=out.getvalue()
    cover=png();calls=[]
    def loader(store,owner,url,quality):
        calls.append(url)
        return (cover,'image/png') if 'cover' in url else (raw,'image/jpeg')
    monkeypatch.setattr(export,'COMPACT_THRESHOLD',1_000_000_000)
    normal,info=await build_html(s,'alice',selected,loader=loader,include_toc=include_toc)
    assert info['images_compacted']==0
    monkeypatch.setattr(export,'COMPACT_THRESHOLD',len(normal))
    exact,info=await build_html(s,'alice',selected,loader=loader,include_toc=include_toc)
    assert info['images_compacted']==0  # strictly greater than the threshold
    calls.clear();monkeypatch.setattr(export,'COMPACT_THRESHOLD',len(normal)-1)
    compact,info=await build_html(s,'alice',selected,loader=loader,include_toc=include_toc)
    assert info['images_compacted']==1 and info['initial_size']==len(normal)
    assert len(compact)<len(normal) and len(calls)==2
    assert base64.b64encode(cover) in compact and base64.b64encode(raw) not in compact
    encoded=re.search(rb'data:image/webp;base64,([^"\s]+)',compact)[1]
    with Image.open(io.BytesIO(base64.b64decode(encoded))) as body:
        assert max(body.size)==720
    original,info=await build_html(s,'alice',selected,loader=loader,quality='original')
    assert info['images_compacted']==0 and base64.b64encode(raw) in original


def test_compact_image_does_not_enlarge_small_image_and_keeps_alpha():
    from ai2apps.intelligence.html_export import compact_image
    raw=png();encoded='data:image/png;base64,'+base64.b64encode(raw).decode()
    assert len(compact_image(encoded))<=len(encoded)
    out=io.BytesIO();Image.new('RGBA',(1200,900),(255,0,0,100)).save(out,format='PNG')
    value=compact_image('data:image/png;base64,'+base64.b64encode(out.getvalue()).decode())
    with Image.open(io.BytesIO(base64.b64decode(value.split(',',1)[1]))) as result:
        assert result.mode=='RGBA' and max(result.size)==720


@pytest.mark.asyncio
async def test_collapsed_cards_show_excerpt_only_without_available_cover(tmp_path):
    s,c,a=seed(tmp_path/'s');selected=selected_rows(s,'alice',c['id'])
    article=selected['articles'][0]['data'];article['summary']='Safe <summary> '+('Long preview. '*40)
    with_image,_=await build_html(s,'alice',selected,loader=lambda *args:(png(),'image/png'),include_toc=False)
    assert b'article-card has-cover' in with_image and b'<p class="card-excerpt">' not in with_image
    article['images']=[];article['cover_image']=None
    without,_=await build_html(s,'alice',selected,include_toc=False)
    assert b'article-card no-cover' in without and b'<p class="card-excerpt">Safe &lt;summary&gt;' in without
    assert b'-webkit-line-clamp:3' in without
    article['summary']='';article['body']='Body fallback'
    fallback,_=await build_html(s,'alice',selected,include_toc=False)
    assert b'<p class="card-excerpt">Body fallback</p>' in fallback


@pytest.mark.asyncio
async def test_social_metadata_cover_priority_and_logo(tmp_path):
    from html.parser import HTMLParser
    class Meta(HTMLParser):
        def __init__(self):super().__init__();self.values={}
        def handle_starttag(self,tag,attrs):
            attrs=dict(attrs)
            if tag=='meta':self.values[attrs.get('property') or attrs.get('name')]=attrs.get('content')
    s,c,a=seed(tmp_path/'s');selected=selected_rows(s,'alice',c['id']);article=selected['articles'][0]['data']
    selected['channels'][0]['data']['name']='News <safe>'
    article['cover_image']={'url':'https://example.org/red.jpg'};article['images']=[]
    custom='/v1/platform/intelligence/imports/'+'a'*64+'/share-cover.jpg'
    def loader(store,owner,url,quality):
        out=io.BytesIO();Image.new('RGB',(900,700),'blue' if url==custom else 'red').save(out,format='PNG');return out.getvalue(),'image/png'
    async def metadata(**kwargs):
        payload,_=await build_html(s,'alice',selected,loader=loader,**kwargs);meta=Meta();meta.feed(payload.decode());return payload,meta.values
    payload,meta=await metadata(share_cover=custom)
    assert b'<head>' in payload and b'</head><body>' in payload
    assert meta['og:title']=='News <safe>' and meta['description']==meta['og:description']
    assert meta['twitter:image']==meta['og:image'] and meta['twitter:card']=='summary_large_image'
    with Image.open(io.BytesIO(base64.b64decode(meta['og:image'].split(',')[1]))) as image:
        assert max(image.size)==600 and image.getpixel((0,0))[2]>240
    _,meta=await metadata()
    with Image.open(io.BytesIO(base64.b64decode(meta['og:image'].split(',')[1]))) as image:assert image.getpixel((0,0))[0]>240
    article['cover_image']=None
    _,meta=await metadata()
    with Image.open(io.BytesIO(base64.b64decode(meta['og:image'].split(',')[1]))) as logo:
        assert logo.size==(600,600) and logo.convert('L').getextrema()[0]<100
