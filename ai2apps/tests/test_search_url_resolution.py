from email.message import Message
from urllib.error import HTTPError
from types import SimpleNamespace
import pytest
from ai2apps.research.provider import SafeHttpClient, WebProviderError
from ai2apps.research.search_urls import resolve_google_url

class Response:
    def __init__(self,url):
        self.url=url;self.headers=Message();self.headers['Content-Type']='text/html'
        self.headers['Content-Length']='999999999'
    def geturl(self):return self.url
    def __enter__(self):return self
    def __exit__(self,*_):pass
    def read(self,*_):raise AssertionError('Redirect resolution must never download the body')

def client(mapping):
    seen=[]
    def resolve(host,port,**_):return [(2,1,6,'',('127.0.0.1' if host in ('private.example','127.0.0.1') else '93.184.216.34',port))]
    def open(request,**_):
        url=request.full_url;seen.append(url)
        target=mapping.get(url)
        if target:
            headers=Message();headers['Location']=target
            raise HTTPError(url,302,'redirect',headers,None)
        return Response(url)
    return SafeHttpClient(resolver=resolve,opener=SimpleNamespace(open=open)),seen

def test_opaque_google_link_resolves_every_hop_without_reading_body():
    original='https://www.google.com/goto?url=opaque'
    http,seen=client({original:'https://example.com/start','https://example.com/start':'https://www.example.com/article'})
    result=resolve_google_url(original,http)
    assert result['url']=='https://www.example.com/article'
    assert result['search_url']==original
    assert result['redirect_chain']==seen

@pytest.mark.parametrize('target',['http://127.0.0.1/admin','http://private.example/admin','file:///etc/passwd','https://user:pass@example.com/a'])
def test_redirect_cannot_reach_private_non_http_or_credential_targets(target):
    original='https://www.google.com/goto?url=opaque'
    http,seen=client({original:target})
    with pytest.raises(WebProviderError):resolve_google_url(original,http)
    assert seen==[original]

def test_plain_google_url_is_validated_before_any_request():
    http,seen=client({})
    with pytest.raises(WebProviderError):resolve_google_url('https://www.google.com/url?q=http://127.0.0.1/admin',http)
    assert seen==[]

def test_redirect_loop_and_unresolved_google_page_are_rejected():
    original='https://www.google.com/goto?url=opaque'
    http,_=client({original:original})
    with pytest.raises(WebProviderError,match='loop'):resolve_google_url(original,http)
    http,_=client({})
    with pytest.raises(WebProviderError,match='did not resolve'):resolve_google_url(original,http)
