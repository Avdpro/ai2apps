"""Verify that the owner only dispatches a reviewed X draft once."""
from io import BytesIO
import json

import httpx
import pytest

from ai2apps.share_works.cli import PublishError
from ai2apps.share_works.service import HOST
from ai2apps.share_works.social import REDNOTE, XClient
from test_app_interactions import runtime
from test_share_works_aaat import context


@pytest.mark.parametrize('suffix,drop_post', [('png', False), ('mp4', True)])
async def test_approved_draft_only_dispatches_once(runtime, suffix, drop_post):
    ctx = context(runtime)
    owner = ctx.actor_user_id
    service = runtime.share_works.social
    calls = []

    def handle(request):
        name = request.method, request.url.path
        calls.append(name)
        replies = {
            ('GET', '/2/users/me'): {'id': '123', 'username': 'fixture'},
            ('POST', '/2/media/upload/initialize'): {'id': '456'},
            ('POST', '/2/media/upload/456/append'): {},
            ('POST', '/2/media/upload/456/finalize'): {},
            ('POST', '/2/tweets'): {'id': '789'},
        }
        if name == ('POST', '/2/media/upload/initialize'):
            assert json.loads(request.content)['media_category'] == ('tweet_video' if suffix == 'mp4' else 'tweet_image')
        if name == ('POST', '/2/tweets'):
            assert json.loads(request.content) == {'text': 'Reviewed text', 'media': {'media_ids': ['456']}}
            if drop_post:
                raise httpx.ReadTimeout('fixture lost receipt', request=request)
        return httpx.Response(200, json={'data': replies[name]})

    def factory():
        client = object.__new__(XClient)
        client.http = httpx.AsyncClient(base_url='https://api.x.com/2/', transport=httpx.MockTransport(handle))
        return client

    service.x_client = factory
    draft = await service.prepare(owner, 'x', '', 'Reviewed text', [(f'fixture.{suffix}', BytesIO(b'fixture'))])
    assert calls == [('GET', '/2/users/me')]
    with pytest.raises(PublishError, match='public_confirmation_required'):
        service.publish_x(owner, draft['id'], draft['digest'], approved=False)
    with pytest.raises(PublishError, match='social_draft_changed'):
        service.publish_x(owner, draft['id'], '0'*64, approved=True)
    with pytest.raises(Exception):
        await runtime.app_capability_router.invoke('share.x_publish', draft['approval_parameters'], ctx)
    assert len(calls) == 1
    await runtime.system_tasks.startup()
    try:
        row = service.publish_x(owner, draft['id'], draft['digest'], approved=True)
        replay = service.publish_x(owner, draft['id'], draft['digest'], approved=True)
        assert replay['task_id'] == row['task_id']
        await runtime.system_tasks.follow(owner, row['task_id'], ctx, app_id=HOST, timeout=10)
        result = service.publish_x(owner, draft['id'], draft['digest'], approved=True)
        assert result['status'] == ('outcome_unknown' if drop_post else 'published')
        assert result['url'] == (None if drop_post else 'https://x.com/fixture/status/789')
        assert calls.count(('POST', '/2/tweets')) == 1
    finally:
        await runtime.system_tasks.shutdown()


@pytest.mark.parametrize('suffix', ['jpg', 'mov'])
async def test_rednote_handoff_is_local(runtime, suffix):
    ctx = context(runtime)
    service = runtime.share_works.social
    draft = await service.prepare(ctx.actor_user_id, 'rednote', 'Title', 'Body',
                                  [(f'fixture.{suffix}', BytesIO(b'media'))])
    assert draft['editor_url'] == REDNOTE
    assert draft['status'] == 'pending_manual_publish'
    assert not draft['url']
    with pytest.raises(PublishError, match='social_draft_changed'):
        service.publish_x(ctx.actor_user_id, draft['id'], draft['digest'], approved=True)


@pytest.mark.parametrize('caller', ['aaat', 'bot'])
async def test_x_real_aaat_form_approves_only_the_frozen_draft(runtime, caller):
    from fastapi import FastAPI
    from ai2apps.agents import CompleteAction, ToolCallAction
    from ai2apps.agents.parameter_forms import form_action
    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.services.aaat import principal_for
    from ai2apps.share_works.service import MINI
    from test_app_interactions import wait

    ctx = context(runtime)
    service = runtime.share_works.social
    posts = []

    def handle(request):
        if request.url.path == '/2/users/me':
            return httpx.Response(200, json={'data': {'id': '123', 'username': 'fixture'}})
        assert request.url.path == '/2/tweets'
        posts.append(json.loads(request.content))
        return httpx.Response(201, json={'data': {'id': '789'}})

    def factory():
        client = object.__new__(XClient)
        client.http = httpx.AsyncClient(base_url='https://api.x.com/2/', transport=httpx.MockTransport(handle))
        return client

    service.x_client = factory
    draft = await runtime.app_capability_router.invoke('share.social_prepare', {
        'destination': 'x', 'body': 'Reviewed text'}, ctx)
    args = draft['approval_parameters']
    provider = MINI+'.x_publish'
    form_args = {'request_id': 'x-confirm', 'capability': 'share.x_publish',
                 'provider': provider, 'initial_values': args}
    runtime.agents.ensure_definition(agent_key='fixture.x', package_version='1', display_name='X fixture',
        executor_key='fixture.x', max_steps=10, timeout_seconds=120)

    def executor(c):
        action = form_action(c, form_args)
        if action:
            return action
        if not c.step('publish'):
            return ToolCallAction('publish', 'share.x_publish', {'provider': provider, **args})
        return CompleteAction(c.step('publish').output)

    runtime.agent_runtime.bind_executor('fixture.x', executor)
    principal = principal_for(runtime, ctx)
    if caller == 'bot':
        from ai2apps.messager.bots import install, REGISTRATION
        from test_app_chat_durable import response

        install(runtime)
        bot = runtime.messager_bots.create(ctx.actor_user_id, 'Fixture Bot', 'Publish a reviewed X draft')
        access = runtime.messager_bot_app_access
        target = access.target(runtime.app_capability_router.providers[provider])
        with runtime.database.transaction(write=True) as db:
            access.grant_targets(ctx.actor_user_id, bot['id'], {target}, db)
        session = runtime.app_chat.open(principal, REGISTRATION, {'bot_id': bot['id']}, {})

        async def model(request):
            results = [json.loads(m['content']) for m in request['messages'] if m.get('role') == 'tool']
            if any(r.get('status') == 'published' for r in results):
                return response(text='Published')
            if any(r.get('status') == 'completed' and 'result' in r for r in results):
                return response('share.x_publish', {'provider': provider, **args})
            if any(r.get('providers') for r in results):
                return response('app.collect_parameters', {'request_id': 'x-confirm',
                    'capability': 'share.x_publish', 'provider': provider, 'values': args})
            return response('app.describe', {'capability': 'share.x_publish'})

        runtime.agent_runtime.bind_model_provider(model)
        run_id = runtime.app_chat.submit(principal, session, 'fixture-x-bot', 'Publish the reviewed draft', 'fixture')
    else:
        run, _ = runtime.agents.create_run(session_id=ctx.session_id, agent_key='fixture.x', input={})
        run_id = run.id
    app = FastAPI()
    app.include_router(create_ai2apps_router(runtime_provider=lambda:runtime,
        principal_provider=lambda:principal_for(runtime, ctx)))
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        runtime.agent_runtime.wake()
        await wait(runtime, run_id, 'waiting_input')
        item = runtime.agents.list_interactions(run_id)[0]
        route = f'/v1/platform/agent-runs/{run_id}/interactions/{item.id}/parameters'
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            state = await client.get(route)
            assert state.json()['values'] == args
            assert not posts
            approved = await client.post(route+'/submit', json={'revision': 0, 'values': args})
            assert approved.status_code == 200, approved.text
            await wait(runtime, run_id, 'waiting_capability')
            assert not posts
            item = next(i for i in runtime.agents.list_interactions(run_id) if i.status.value == 'pending')
            assert item.ui_hints['scopes'] == ['once']
            assert item.ui_hints['auto_approve_seconds'] is None
            approval = await client.post(f'/v1/platform/agent-runs/{run_id}/approve/{item.id}',
                                         json={'response_id': 'fixture-x-approval', 'scope': 'once'})
            assert approval.status_code == 200, approval.text
        await wait(runtime, run_id, 'completed')
        assert posts == [{'text': 'Reviewed text'}]
    finally:
        await runtime.stop_background_tasks()
