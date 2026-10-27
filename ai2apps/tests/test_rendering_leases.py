import asyncio
import pytest
from ai2apps.browser.background_page import BackgroundPage, NativeInputNotDispatched
from ai2apps.browser.rendering_leases import RenderingLeases

class Native:
    def __init__(self):
        self.host_pid=1;self.calls=[];self.count=0;self.ids=set();self.fail_release=False
        self.rendering_leases=RenderingLeases(self)
    async def command(self,method,params,**kw):
        self.calls.append((method,params))
        if method.endswith('Capabilities'):return {'version':1,'scope':'window','permanentSafeguard':True}
        if method.endswith('acquireRenderingLease'):
            self.count+=1;lease=str(len(self.calls));self.ids.add(lease)
            return dict(lease=lease,context=params['context'],scope='window')
        if method.endswith('releaseRenderingLease'):
            if self.fail_release:raise OSError('transport lost')
            if params['lease'] in self.ids:self.ids.remove(params['lease']);self.count-=1
            return {'released':True}
        if method=='script.callFunction':return {'result':{'type':'string','value':'"fixture"'}}
        if method=='browsingContext.captureScreenshot':return {'data':'pixels'}
        return {}

@pytest.mark.asyncio
async def test_nested_same_task_context_and_purpose_refcounts():
    c=Native();p=BackgroundPage(c,'A')
    async with p.rendering_lease('input'):
        async with p.rendering_lease('input'):
            assert c.count==1
            async with p.rendering_lease('capture'):assert c.count==2
        assert c.count==1
    assert c.count==0 and not c.rendering_leases.active

@pytest.mark.asyncio
@pytest.mark.parametrize('reason',['failure','cancel','pause'])
async def test_exit_failure_cancel_and_manual_pause_release(reason):
    c=Native();p=BackgroundPage(c,'A');entered=asyncio.Event()
    async def work():
        async with p.rendering_lease('capture'):
            entered.set()
            if reason=='failure':raise ValueError('fixture')
            if reason=='pause':return {'needs_user':True}
            await asyncio.Future()
    task=asyncio.create_task(work());await entered.wait()
    if reason=='cancel':task.cancel()
    try:await task
    except (ValueError,asyncio.CancelledError):pass
    assert c.count==0 and not c.rendering_leases.active

@pytest.mark.asyncio
async def test_read_no_lease_and_capture_released_before_model_wait():
    c=Native();p=BackgroundPage(c,'A')
    await p.call_json('()=>document.title')
    assert c.count==0 and not c.rendering_leases.events
    assert (await p.capture_screenshot({'context':'A'}))['data']=='pixels'
    assert c.count==0

@pytest.mark.asyncio
async def test_separate_contexts_and_tasks_not_coalesced():
    c=Native();a=BackgroundPage(c,'A');b=BackgroundPage(c,'B');ready=asyncio.Event();release=asyncio.Event()
    async def other():
        async with a.rendering_lease('input'):ready.set();await release.wait()
    t=asyncio.create_task(other());await ready.wait()
    async with a.rendering_lease('input'):
        async with b.rendering_lease('input'):assert c.count==3
    release.set();await t;assert c.count==0

@pytest.mark.asyncio
async def test_disconnect_cleanup_never_claims_release():
    c=Native();p=BackgroundPage(c,'A');c.fail_release=True
    async with p.rendering_lease('capture'):pass
    assert not c.rendering_leases.active
    assert c.rendering_leases.events[-1]['event']=='release_unconfirmed_ttl'

@pytest.mark.asyncio
async def test_transport_detach_releases_only_own_leases():
    c=Native();p=BackgroundPage(c,'A')
    async with p.rendering_lease('input'):
        await c.rendering_leases.close();assert c.count==0
    assert c.count==0 and not any(m=='session.end' for m,_ in c.calls)

@pytest.mark.asyncio
async def test_explicit_legacy_only_and_preparation_failure():
    c=Native();p=BackgroundPage(c,'A')
    async def unsupported(*a,**kw):raise RuntimeError('unknown command')
    c.command=unsupported
    async with p.rendering_lease('capture'):pass
    assert c.rendering_leases.capability['version']==0
    c.rendering_leases.capability=None
    async def broken(*a,**kw):raise OSError('disconnected')
    c.command=broken
    with pytest.raises(NativeInputNotDispatched):await p.dispatch_input([])
    assert not p.input_diagnostics.attempted

@pytest.mark.asyncio
async def test_capture_quota_cancellation_does_not_block_input():
    c=Native();p=BackgroundPage(c,'A');hold=asyncio.Event();ready=asyncio.Queue()
    async def work():
        async with p.rendering_lease('capture'):await ready.put(True);await hold.wait()
    tasks=[asyncio.create_task(work()) for _ in range(3)]
    await ready.get();await ready.get();await asyncio.sleep(0);assert c.count==2
    tasks[-1].cancel()
    with pytest.raises(asyncio.CancelledError):await tasks[-1]
    async with p.rendering_lease('input'):assert c.count==3
    hold.set();await asyncio.gather(*tasks[:2]);assert c.count==0

@pytest.mark.asyncio
async def test_invalid_native_receipt_still_releases_known_handle():
    c=Native();p=BackgroundPage(c,'A');original=c.command
    async def command(method,params,**kw):
        result=await original(method,params,**kw)
        if method.endswith('acquireRenderingLease'):result['context']='wrong'
        return result
    c.command=command
    with pytest.raises(NativeInputNotDispatched):await p.dispatch_input([])
    assert c.count==0 and not c.rendering_leases.active
    assert not any(m=='input.performActions' for m,_ in c.calls)
