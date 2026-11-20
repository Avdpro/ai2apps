"""Public PDF owner contract, with real parsing and fixture network bytes."""
from dataclasses import replace
from io import BytesIO
import socket

import pytest
from jsonschema import Draft202012Validator, ValidationError
from reportlab.pdfgen.canvas import Canvas

from ai2apps.chat import ChatRepository
from ai2apps.documents import public_pdf
from ai2apps.identity import RequestPrincipal
from ai2apps.research.pdf_reader import SCHEMA
from ai2apps.services import ToolCallContext, ToolProviderError
from ai2apps.core import ResourceNotFoundError
from test_app_interactions import runtime
from test_bot_capability_discovery import setup


@pytest.mark.parametrize('url', ['file:///tmp/paper.pdf','https://u:p@public.test/a',
                                  'https://public.test:8080/a','https://public.test/a\n'])
def test_rejects_non_public_url_forms(url):
    with pytest.raises(ValueError):
        public_pdf.public_url(url)


def test_rejects_private_dns_peer_before_request(monkeypatch):
    monkeypatch.setattr(socket, 'getaddrinfo', lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 0, '', ('127.0.0.1', 443))])
    with pytest.raises(ValueError, match='non-public'):
        public_pdf.download('https://somewhere.test/a')


def test_each_redirect_is_checked_and_login_html_is_not_pdf(monkeypatch):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def getheader(self, key, default=None): return self.headers.get(key, default)

    class Connection:
        def request(self, *_args, **_kwargs): pass
        def close(self): pass
        def getresponse(self):
            response = Response()
            response.status, response.headers = next(responses)
            return response

    hosts = []
    def connect(host, *args):
        hosts.append(host)
        return Connection()
    monkeypatch.setattr(public_pdf, '_pinned_connection', connect)
    responses = iter([(302, {'Location': 'https://publisher.test/login'}),
                      (200, {'Content-Type': 'text/html'})])
    with pytest.raises(ValueError, match='did not return a PDF'):
        public_pdf.download('https://papers.test/a')
    assert hosts == ['papers.test', 'publisher.test']


@pytest.mark.asyncio
async def test_paper_attached_once_and_read_with_page_numbers(runtime, monkeypatch):
    setup(runtime)
    from ai2apps.messager.creation import ensure_research
    ensure_research(runtime, 'local')
    bot, = [b for b in runtime.messager_bots.list('local') if b['template_id'] == 'research']
    provider, = [p for p in runtime.messager_bot_app_access.exported('local', bot['id'])
                 if p.capability == 'web.read_pdf']
    assert provider.mini_app_id == 'ai2apps.web-reader'

    paper = BytesIO()
    writer = Canvas(paper)
    for text in ('First page and abstract', 'Second page and actual experiment'):
        writer.drawString(90, 700, text)
        writer.showPage()
    writer.save()
    requests = []
    def download(url):
        requests.append(url)
        return 'https://papers.test/final.pdf', paper.getvalue()
    monkeypatch.setattr(public_pdf, 'download', download)

    repo = ChatRepository(runtime.database, runtime.events)
    first, _ = repo.create_thread(title='Paper A')
    second, _ = repo.create_thread(title='Paper B')
    ctx = ToolCallContext.from_principal(RequestPrincipal.legacy_local(),
        caller_id='builtin:app-chat', session_id=first.session.id)
    args = {'url':'https://papers.test/preprint', 'limit':1}
    first_page = await provider.handler(args, ctx)
    assert first_page['pdf_pages'] == 2
    assert first_page['source_url'] == 'https://papers.test/final.pdf'
    assert first_page['items'] == [{'page':1, 'text':'First page and abstract'}]
    more = {'attachment_id':first_page['attachment_id'], 'offset':first_page['next_offset']}
    second_page = await provider.handler(more, ctx)
    assert second_page['items'] == [{'page':2, 'text':'Second page and actual experiment'}]
    assert second_page['next_offset'] is None
    assert (await provider.handler(args, ctx))['attachment_id'] == first_page['attachment_id']
    assert requests == ['https://papers.test/preprint']
    assert len(runtime.documents.list(first.session.id)) == 1
    with pytest.raises((ToolProviderError, ResourceNotFoundError)):
        await provider.handler(more, replace(ctx, session_id=second.session.id))
    with pytest.raises(ValidationError):
        Draft202012Validator(SCHEMA).validate({**args, **more})
