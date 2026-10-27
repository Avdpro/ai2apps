import asyncio
import json
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from ai2apps.browser.background_page import BackgroundPage,NativeInputNotDispatched
from ai2apps.browser.background_bidi import BackgroundBiDi,BrowserTransportError,BrowserCommandTimeout

ACTIONS=[{'type':'key','id':'fixture','actions':[{'type':'keyDown','value':'private-value'}]}]

def page_for(command):
    p=BackgroundPage(NS(command=command),'owned')
    p.call_json=AsyncMock(return_value={'visible':True,'document_focus':False})
    p.mode=AsyncMock(return_value='fast');p.pause=AsyncMock()
    return p

@pytest.mark.asyncio
async def test_visible_unfocused_page_uses_directed_input_without_activate():
    command=AsyncMock(return_value={});p=page_for(command)
    await p.pointer_to({'rect':{'x':0,'y':0,'width':20,'height':20}})
    await p.type_text('abc')
    assert all(c.args[0]=='input.performActions' for c in command.await_args_list)
    assert p.input_diagnostics.snapshot()['focus']['activate_requests']==0
    assert p.input_diagnostics.snapshot()['focus']['document_focus_before'] is False
    assert p.input_diagnostics.snapshot()['focus']['system_foreground_observed'] is None

@pytest.mark.asyncio
async def test_pre_send_transport_failure_is_definitively_not_dispatched():
    c=BackgroundBiDi();p=BackgroundPage(c,'owned')
    with pytest.raises(NativeInputNotDispatched):await p.dispatch_input(ACTIONS)
    d=p.input_diagnostics.snapshot()
    assert not d['input_dispatched'] and d['state']=='not_dispatched'
    assert not c._pending

@pytest.mark.asyncio
async def test_partial_composite_input_never_becomes_a_whole_action_not_dispatched():
    error=BrowserTransportError('not connected');error.command_dispatched=False
    command=AsyncMock(side_effect=[{},error]);p=page_for(command)
    await p.dispatch_input(ACTIONS)
    with pytest.raises(BrowserTransportError):await p.dispatch_input(ACTIONS)
    d=p.input_diagnostics.snapshot()
    assert d['input_dispatched'] and d['state']=='partial' and d['commands_acknowledged']==1
    assert command.await_count==2
    assert 'private-value' not in json.dumps(d)

@pytest.mark.asyncio
@pytest.mark.parametrize('failure',['timeout','send_error'])
async def test_sent_input_failures_are_unknown_and_never_replayed(failure):
    c=BackgroundBiDi();c._reader=asyncio.current_task();writes=[]
    async def send(value):
        writes.append(value)
        if failure=='send_error':raise OSError('lost write acknowledgement')
    c._upstream=NS(send=send);p=BackgroundPage(c,'owned')
    with pytest.raises((BrowserCommandTimeout,OSError)) as e:
        await p.dispatch_input(ACTIONS,timeout=.001)
    assert e.value.command_dispatched is True
    assert len(writes)==1 and not c._pending
    d=p.input_diagnostics.snapshot();assert d['input_dispatched'] and d['state']=='uncertain'

@pytest.mark.asyncio
async def test_cancel_queued_transport_write_reports_no_dispatch():
    c=BackgroundBiDi();c._reader=asyncio.current_task();send=AsyncMock();c._upstream=NS(send=send);p=BackgroundPage(c,'owned')
    async with c._send_lock:
        task=asyncio.create_task(p.dispatch_input(ACTIONS));await asyncio.sleep(0);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
    send.assert_not_awaited();assert not p.input_diagnostics.snapshot()['input_dispatched'] and not c._pending

@pytest.mark.asyncio
async def test_cancel_after_send_retains_unknown_input_state():
    c=BackgroundBiDi();c._reader=asyncio.current_task();sent=asyncio.Event()
    async def send(value):sent.set()
    c._upstream=NS(send=send);p=BackgroundPage(c,'owned');task=asyncio.create_task(p.dispatch_input(ACTIONS))
    await sent.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert p.input_diagnostics.snapshot()['state']=='uncertain' and not c._pending

@pytest.mark.asyncio
async def test_preparation_retry_is_bounded_before_input_only():
    p=page_for(AsyncMock(return_value={}))
    p.activate_for_input=AsyncMock(side_effect=[RuntimeError('temporarily unavailable'),None])
    await p.pointer_to({'rect':{'x':0,'y':0,'width':20,'height':20}})
    assert p.activate_for_input.await_count==2 and p.connection.command.await_count==1
    p.activate_for_input=AsyncMock(side_effect=RuntimeError('unavailable'))
    # Earlier successful input prohibits retrying the whole composite operation.
    with pytest.raises(RuntimeError):await p.pointer_to({'rect':{'x':0,'y':0,'width':20,'height':20}})
    assert p.activate_for_input.await_count==1

@pytest.mark.asyncio
async def test_bulk_editor_effects_are_tracked_without_logging_text():
    p=page_for(AsyncMock(return_value={}));p.helper=AsyncMock(return_value=True)
    await p.type_text('private-text'*100)
    d=p.input_diagnostics.snapshot()
    assert d['input_dispatched'] and any(e['kind']=='editor' for e in d['events'])
    assert 'private-text' not in json.dumps(d)

@pytest.mark.asyncio
async def test_failed_preparation_respects_zero_recovery_budget():
    from ai2apps.browser.execution_budget import TaskExecutionBudget
    p=page_for(AsyncMock());p.execution_budget=TaskExecutionBudget({'max_recovery_attempts':0})
    p.activate_for_input=AsyncMock(side_effect=RuntimeError('not ready'))
    with pytest.raises(NativeInputNotDispatched):await p.prepare_native_input()
    assert p.activate_for_input.await_count==1
    p.connection.command.assert_not_awaited()
