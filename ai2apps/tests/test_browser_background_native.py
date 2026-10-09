"""Opt-in acceptance against the fixed App Dev native BiDi host.

Uses a disposable native userContext and an in-process HTTP fixture; never uses
an account Profile, external website, or user content.
"""
import asyncio
import functools
import http.server
import os
import threading
import time
from pathlib import Path

import pytest

from ai2apps.browser.background_bidi import BackgroundBiDi
from ai2apps.browser.background_page import BackgroundPage

pytestmark = pytest.mark.skipif(not os.environ.get('AI2APPS_NATIVE_ACCEPTANCE'), reason='requires App Dev native host')


@pytest.mark.asyncio
async def test_native_background_actions(tmp_path):
    html = '''<!doctype html><meta charset="utf-8"><title>Backend acceptance</title>
<div id="cookie" role="dialog" aria-label="Cookie consent" style="position:fixed;top:0;left:0;z-index:99;background:white;width:500px;height:150px">We use cookies to improve your experience.<button onclick="document.querySelector('#cookie').remove()">关闭</button></div>
<label for="text">Test text</label><textarea id="text" aria-label="Test text"></textarea>
<button onclick="document.querySelector('#file').click()">Upload fixture</button><input id="file" type="file" hidden>
<article><h2><a href="/one.html">Fixture article one</a></h2></article>
<article><h2><a href="/two.html">Fixture article two</a></h2></article>
'''
    (tmp_path/'index.html').write_text(html)
    (tmp_path/'fixture.txt').write_text('disposable upload fixture')
    class QuietHandler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args): pass
    server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(tmp_path)))
    thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
    connection = await BackgroundBiDi().connect()
    user_context = (await connection.command('browser.createUserContext', {}))['userContext']
    context = None
    try:
        context = (await connection.command('browsingContext.create', {'type':'window', 'userContext':user_context, 'background':True}))['context']
        page = BackgroundPage(connection, context)
        result = await page.navigate(f'http://127.0.0.1:{server.server_port}/', delay_ms=100)
        assert result['stable']
        assert (await page.snapshot())['title']=='Backend acceptance'
        access = await page.handle_access()
        assert access['dismissed'], {'access': access, 'dom': await page.call_json("function(){return {text:document.body.innerText, width:innerWidth,height:innerHeight, rect:document.querySelector('#cookie')?.getBoundingClientRect().toJSON()};}")}
        target = await page.find_target('Test text', 'input')
        assert target, (await page.snapshot())['items']
        await page.pointer_to(target)
        started = time.monotonic()
        text = '后台分段输入Abc123\n' * 16667
        text = text[:200000]
        await page.type_text(text, replace=True)
        assert await page.call_json("function(){return document.querySelector('#text').value;}") == text
        assert time.monotonic()-started < 45
        upload = await page.upload('Upload fixture', [str(tmp_path/'fixture.txt')])
        assert upload['method']=='clicked-file-chooser'
        assert await page.call_json("function(){return document.querySelector('#file').files[0].name;}")=='fixture.txt'
        listing = await page.extract_list({'arguments': {'limit':20}})
        assert len(listing['items'])==2
        assert all(item['title'] and item['url'] for item in listing['items'])
        # Run a real durable queued capability after its HTTP client is closed.
        # Only Profile binding is substituted with this disposable native context.
        import runpy
        helpers = runpy.run_path(str(Path(__file__).resolve().parents[2]/'tests/test_ai2apps_agent_builder.py'))
        runtime = helpers['_runtime'](tmp_path/'platform')
        client = helpers['_client'](runtime, helpers['_principal']('native-test-owner'))
        origin = f'http://127.0.0.1:{server.server_port}'
        source = {'name':'Native acceptance', 'site_scope':[origin+'/**'], 'capabilities':[{
            'id':'read','name':'site.read','title':'Read fixture', 'steps':[
                {'name':'open','operation':'open','desc':'Open fixture', 'arguments':{'url':origin+'/', 'delay_ms':100},
                 'execution':{'mode':'compiled'}, 'on':{'success':'extract','failed':'failed'}},
                {'name':'extract','operation':'extract_list','desc':'Extract fixture articles',
                 'execution':{'mode':'compiled'}, 'on':{'success':'done','failed':'failed'}}]}]}
        draft = client.post('/v1/platform/agent-drafts', json={'name':source['name'],'source':source,'site_scope':source['site_scope']}).json()
        generation = client.post('/v1/platform/agent-drafts/'+draft['id']+'/compile').json()
        assert client.post('/v1/platform/agent-drafts/'+draft['id']+'/generations/'+generation['id']+'/activate').status_code==200
        queued = client.post('/v1/platform/browser-workspace/tasks',json={
            'profile_key':'default','agent_id':draft['id'],'capability':'site.read','name':'Native fixture','input':{}})
        assert queued.status_code==201,queued.text
        task_id=queued.json()['id'];client.close()
        runner = runtime.background_browser_runner
        async def fixture_page(run):
            page.owner = 'native-test-owner'
            return page
        runner.page_for = fixture_page
        await runtime.agent_runtime.start()
        await runner.startup()
        await runtime.browser_task_monitor.startup()
        try:
            async with asyncio.timeout(30):
                while True:
                    task = runner.tasks.get('native-test-owner',task_id)
                    if task['status'] in ('completed','failed','interrupted'):
                        break
                    await asyncio.sleep(.1)
            assert task['status']=='completed',task
            run = runtime.agents.get_run(task['run_id'])
            assert run.input['parameters']['execution_owner']=='local'
            assert len(run.output['result']['items'])==2
            assert len(runner.journal.lookup(runtime.agents.list_interactions(run.id)[0].id)['response_json'])>0
        finally:
            await runtime.browser_task_monitor.shutdown()
            await runner.shutdown()
            await runtime.agent_runtime.stop()
        # Queue navigation deliberately reloaded the fixture. Restore the long
        # text to check transport detach independently from navigation behavior.
        await page.handle_access()
        target = await page.find_target('Test text', 'input')
        await page.pointer_to(target)
        await page.type_text(text, replace=True)
        # Attachment detach and reconnect must not destroy the tab or its Profile.
        await connection.close()
        connection = await BackgroundBiDi().connect()
        page.connection = connection
        await page.validate_context()
        assert await page.call_json("function(){return document.querySelector('#text').value.length;}")==len(text)
    finally:
        if context:
            await connection.command('browsingContext.close', {'context':context})
        await connection.command('browser.removeUserContext', {'userContext':user_context})
        await connection.close()
        server.shutdown();server.server_close()
