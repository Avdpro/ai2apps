import pytest
from ai2apps.browser.site_boundary import registrable_site
from ai2apps.browser.background_executor import scope_allows, BackgroundExecutor


@pytest.mark.parametrize('host,expected',[
    ('news.example.com','example.com'),('www.example.co.uk','example.co.uk'),
    ('a.github.io','a.github.io'),('news.a.github.io','a.github.io'),
    ('www.city.kawasaki.jp','city.kawasaki.jp'),('a.b.ck','a.b.ck'),
    ('www.ck','www.ck'),('co.uk',None),('github.io',None),
    ('localhost',None),('127.0.0.1',None),('::1',None),('bad..com',None),
])
def test_registrable_site(host,expected):
    assert registrable_site(host)==expected


@pytest.mark.parametrize('target,scope,expected',[
    ('https://le.hodinkee.com/paulin2026','https://www.hodinkee.com/**',True),
    ('https://news.example.co.uk/a','https://www.example.co.uk/**',True),
    ('https://example.com/a','https://news.example.com/**',True),
    ('https://news.other.co.uk/a','https://www.example.co.uk/**',False),
    ('https://b.github.io/a','https://a.github.io/**',False),
    ('https://news.a.github.io/a','https://www.a.github.io/**',True),
    ('https://example.com.evil.com/a','https://www.example.com/**',False),
    ('https://evil-example.com/a','https://www.example.com/**',False),
    ('http://news.example.com/a','https://www.example.com/**',False),
    ('https://news.example.com:444/a','https://www.example.com/**',False),
    ('https://user@news.example.com/a','https://www.example.com/**',False),
    ('https://news.example.com/other','https://www.example.com/articles/**',False),
    ('https://news.example.com/articles/a','https://www.example.com/articles/**',True),
    ('https://b.co.uk/a','https://co.uk/**',False),
])
def test_same_site_scope(target,scope,expected):
    assert scope_allows(target,[scope]) is expected


@pytest.mark.asyncio
async def test_hodinkee_open_redirect_then_read_with_existing_scope():
    class Page:
        url='about:blank'
        async def snapshot(self):return {'url':self.url}
        async def navigate(self,url,delay):
            self.url='https://le.hodinkee.com/paulin2026'
            return {'url':url}
        async def read_page(self,args):return {'outcome':'success','url':self.url,'text':'Paulin launch'}
    page=Page();executor=BackgroundExecutor(None);scope=['https://www.hodinkee.com/**']
    result=await executor.compiled(page,{'operation':'open','arguments':{'url':'https://www.hodinkee.com/articles/paulin-hodinkee'}},scope)
    assert result['outcome']=='success'
    result=await executor.compiled(page,{'operation':'read_page','arguments':{'url':page.url}},scope)
    assert result['outcome']=='success'
