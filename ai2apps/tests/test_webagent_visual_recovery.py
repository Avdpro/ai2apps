import base64
import io
import json
from copy import deepcopy
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
import pytest
from PIL import Image
from ai2apps.browser.visual_recovery import VisualControlRecovery, VisualRecoveryUnavailable, VisualActionUncertain, annotated_image, visual_model, VALIDATE_TARGET

def png():
    stream=io.BytesIO();Image.new('RGB',(400,200),'white').save(stream,format='PNG')
    return base64.b64encode(stream.getvalue()).decode()

class Page:
    context_id='owned'
    def __init__(self):
        self.rows=[{'ref':'e1','text':'Increase widget X','tag':'button','role':'button','rect':[20,20,40,20]},
                   {'ref':'e2','text':'Delete widget X','tag':'button','role':'button','rect':[80,20,40,20]}]
        self.viewport={'width':200,'height':100,'scroll_x':0,'scroll_y':0,'document_token':'document-1'}
        self.connection=NS(command=AsyncMock(return_value={'data':png()}))
        self.pointer_to=AsyncMock();self.validate_context=AsyncMock();self.pause=AsyncMock()
    async def snapshot(self,**kwargs):return {'url':'https://arbitrary.test/cart','items':deepcopy(self.rows)}
    async def call_json(self,source,args=()):
        if source==VALIDATE_TARGET:return {'valid':True}
        return deepcopy(self.viewport)

def setup(decisions=None,*,image=True):
    payloads=[];decisions=iter(decisions or [{'ref':'e1'},{'confirmed':True},{'confirmed':True}])
    async def invoke(payload,**kwargs):
        payloads.append(payload);value=next(decisions)
        if isinstance(value,Exception):raise value
        return {'choices':[{'message':{'content':json.dumps(value)}}]}
    manager=NS(default_models=lambda profile:{},resolve_default_model=lambda purpose,**kw:'cloud/provider/model',
               list_cloud=lambda:[{'id':'provider','models':[{'id':'model','enabled':True,'capabilities':{'imageInput':image}}]}])
    runtime=NS(model_manager=manager,model_invocations=NS(context_for_actor=lambda *a,**kw:'actor',invoke_agent_cloud_json=invoke))
    run=NS(session_id='session',input={'parameters':{'owner_user_id':'owner','model_profile':'privacy'}})
    return runtime,run,payloads

@pytest.mark.asyncio
@pytest.mark.parametrize('scope',['https://arbitrary.test/**','https://arbitrary.test/cart*'])
async def test_visual_dom_red_box_then_single_input_and_readback(scope):
    runtime,run,payloads=setup();page=Page();readback=AsyncMock(return_value={'observed_quantity':2,'verified':True})
    result=await VisualControlRecovery(runtime,run,[scope]).click(page,'Increase only widget X once',allowed_refs={'e1'},readback=readback)
    assert result['performed'] and result['visually_verified'] and result['readback']['verified']
    page.pointer_to.assert_awaited_once();readback.assert_awaited_once()
    assert [e['phase'] for e in result['evidence']]==['select','review','after']
    assert len(payloads)==3 and all(p['model']=='cloud/provider/model' for p in payloads)
    assert 'data:image' not in json.dumps(result['evidence'])
    assert 'e2' not in payloads[0]['messages'][1]['content'][0]['text']
    review=payloads[1]['messages'][1]['content'][1]['image_url']['url']
    im=Image.open(io.BytesIO(base64.b64decode(review.split(',')[1])))
    red,green,blue=im.getpixel((40,40));assert red>150 and green<120 and blue<120
    assert 'owner_readback' in payloads[-1]['messages'][1]['content'][0]['text']

@pytest.mark.asyncio
@pytest.mark.parametrize('decisions',[[{'ref':'invented'}],[{'ref':'e1'},{'confirmed':False}]])
async def test_unobserved_or_rejected_control_never_clicks(decisions):
    runtime,run,_=setup(decisions);page=Page()
    with pytest.raises(VisualRecoveryUnavailable):await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action',allowed_refs={'e1'})
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_missing_declared_vision_does_not_capture():
    runtime,run,payloads=setup(image=False);page=Page()
    with pytest.raises(VisualRecoveryUnavailable,match='image-input'):await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action')
    assert not payloads;page.connection.command.assert_not_called();page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_changed_geometry_after_review_prevents_input():
    runtime,run,payloads=setup();page=Page();original=runtime.model_invocations.invoke_agent_cloud_json
    async def invoke(payload,**kwargs):
        result=await original(payload,**kwargs)
        if len(payloads)==2:page.rows[0]['rect'][0]+=10
        return result
    runtime.model_invocations.invoke_agent_cloud_json=invoke
    with pytest.raises(VisualRecoveryUnavailable,match='changed after'):await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action')
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_after_click_model_failure_is_uncertain_not_locate_failure():
    runtime,run,_=setup([{'ref':'e1'},{'confirmed':True},RuntimeError('model unavailable')]);page=Page()
    with pytest.raises(VisualActionUncertain):await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action')
    page.pointer_to.assert_awaited_once()

@pytest.mark.asyncio
async def test_window_preparation_failure_is_not_uncertain_input():
    from ai2apps.browser.background_page import NativeInputNotDispatched
    runtime,run,payloads=setup();page=Page();readback=AsyncMock()
    page.pointer_to.side_effect=NativeInputNotDispatched('window not visible; no input dispatched')
    with pytest.raises(NativeInputNotDispatched):
        await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action',readback=readback)
    page.pointer_to.assert_awaited_once();readback.assert_not_called()
    assert len(payloads)==2  # locate/review only; no false post-input verification


@pytest.mark.asyncio
async def test_unlabeled_icon_requires_visual_review_even_with_an_exact_ref():
    from ai2apps.browser.background_executor import BackgroundExecutor
    runtime,run,payloads=setup([{'confirmed':True},{'confirmed':True}]);page=Page()
    page.rows[0].update(tag='i',role=None,text='')
    page.pointer_to.return_value={}
    target={**page.rows[0],'name':'','rect':{'x':20,'y':20,'width':40,'height':20}}
    page.find_target=AsyncMock(return_value=target);page.related_windows=AsyncMock(return_value=[])
    page.visual_recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    result=await BackgroundExecutor(runtime).compiled(page,
        {'id':'adjust','operation':'click','target':{'ref':'e1'},'arguments':{},'description':'Decrease visible counter once'},
        ['https://arbitrary.test/**'])
    assert result['outcome']=='success'
    assert [e['phase'] for e in page.visual_recovery.evidence]==['review','after']
    page.pointer_to.assert_awaited_once()
    assert len(payloads)==2
    assert 'Decrease visible counter once' in payloads[0]['messages'][1]['content'][0]['text']

@pytest.mark.asyncio
async def test_scope_and_sensitive_page_fail_before_screenshot():
    runtime,run,payloads=setup();page=Page()
    with pytest.raises(VisualRecoveryUnavailable,match='scope'):await VisualControlRecovery(runtime,run,['https://different.test/**']).click(page,'one action')
    page.rows[0]['sensitive']=True
    with pytest.raises(VisualRecoveryUnavailable,match='Sensitive'):await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action')
    assert not payloads;page.pointer_to.assert_not_called()

def test_image_bounds():
    assert annotated_image(png(),{'width':200,'height':100},{'x':20,'y':20,'width':40,'height':20}).startswith('data:image/jpeg;base64,')
    with pytest.raises(VisualRecoveryUnavailable):annotated_image(png(),{'width':200,'height':100},{'x':195,'y':20,'width':40,'height':20})

def test_private_route_cannot_inherit_normal_recognition():
    runtime,run,_=setup(image=False);profiles=[]
    runtime.model_manager.default_models=lambda profile:profiles.append(profile) or ({'image_recognition':'cloud/provider/model'} if profile=='normal' else {})
    with pytest.raises(VisualRecoveryUnavailable):visual_model(runtime,run)
    assert profiles==['privacy']  # Never inspect/inherit normal recognition defaults.

@pytest.mark.asyncio
@pytest.mark.parametrize('after_quantity',[1,2])
@pytest.mark.parametrize('dom_located',[False,True,'offscreen'])
async def test_shopping_owner_requires_exact_readback_even_if_vision_says_yes(after_quantity,monkeypatch,dom_located):
    from ai2apps.browser.shopping import top_up_cart,CART_SCRIPT
    runtime,run,_=setup([{'confirmed':True},{'confirmed':True}] if dom_located else None);page=Page();original=page.call_json
    row={'id':'B000000001','quantity':1,'channel':'fresh','controls':[{'ref':'e1','label':'Add observed product','rect':{'x':20,'y':20,'width':40,'height':20}}]}
    if dom_located:row['increment']={'x':20,'y':20,'width':40,'height':20}
    if dom_located=='offscreen':
        row['increment']['y']=200
        async def scroll(_):row['increment']['y']=20
        page.scroll=AsyncMock(side_effect=scroll)
    reads=0
    async def call(source,args=()):
        nonlocal reads
        if source!=CART_SCRIPT:return await original(source,args)
        reads+=1
        return {'recognized':True,'items':[{**row,'quantity':1 if reads<=2+int(dom_located=='offscreen') else after_quantity}]}
    page.call_json=call
    page.visual_recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'],policy={'visual_review':'always'})
    monkeypatch.setattr('ai2apps.browser.shopping.asyncio.sleep',AsyncMock())
    result=await top_up_cart(page,{'recognized':True,'items':[row]},'B000000001',2,{'title':'observed product','preferred_channel':'fresh'})
    page.pointer_to.assert_awaited_once()
    if dom_located=='offscreen':page.scroll.assert_awaited_once_with(160)
    if after_quantity==2:
        assert result['outcome']=='success' and result['evidence']['result']['quantity']==2
        assert [e['phase'] for e in result['evidence']['visual_recovery']]==(['review','after'] if dom_located else ['reobserve','repair','rule_validated','review','after'])
    else:
        assert result['outcome']=='needs_user' and result['evidence']['observed_quantity']==1
        assert result['evidence']['action_outcome_unknown']

@pytest.mark.asyncio
async def test_covered_control_blocks_native_input():
    runtime,run,_=setup();page=Page();original=page.call_json
    async def call(source,args=()):return {'valid':False} if source==VALIDATE_TARGET else await original(source,args)
    page.call_json=call
    with pytest.raises(VisualRecoveryUnavailable,match='no longer valid'):
        await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action')
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_owner_changed_state_during_model_review_prevents_click():
    runtime,run,_=setup();page=Page()
    with pytest.raises(VisualRecoveryUnavailable,match='Owner state changed'):
        await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'one action',preflight=AsyncMock(return_value=False))
    page.pointer_to.assert_not_called()


def test_current_model_not_replaced_by_unverified_model_or_another_tier():
    runtime,run,_=setup(image=False);calls=[]
    def resolve(purpose,**kwargs):calls.append((purpose,kwargs));return 'cloud/provider/model'
    runtime.model_manager.resolve_default_model=resolve
    runtime.model_manager.default_models=lambda profile:{'image_recognition':'other-vision'}
    runtime.model_invocations.model=lambda identifier:None
    with pytest.raises(VisualRecoveryUnavailable):visual_model(runtime,run)
    assert calls==[('work_standard',{'profile':'privacy'})]

@pytest.mark.asyncio
async def test_shared_executor_missing_target_uses_same_three_stage_recovery():
    from ai2apps.browser.background_executor import BackgroundExecutor
    runtime,run,payloads=setup();page=Page()
    page.find_target=AsyncMock(return_value=None)
    page.related_windows=AsyncMock(return_value=[])
    page.pointer_to.return_value={'x':40,'y':30}
    request={'step':{'operation':'click','target':{'intent':'Increase widget X'},'arguments':{}},'site_scope':['https://arbitrary.test/**']}
    result=await BackgroundExecutor(runtime).execute(page,request,run)
    assert result['outcome']=='success'
    assert [e['phase'] for e in result['evidence']['result']['visual_recovery']]==['reobserve','repair','rule_validated','review','after']
    page.pointer_to.assert_awaited_once()
    assert len(payloads)==3 and page.visual_recovery is None

@pytest.mark.asyncio
async def test_shopping_target_satisfied_while_model_thinks_never_clicks(monkeypatch):
    from ai2apps.browser.shopping import top_up_cart,CART_SCRIPT
    runtime,run,_=setup();page=Page();original=page.call_json;reads=0
    row={'id':'B000000001','quantity':1,'channel':'fresh','controls':[{'ref':'e1','label':'Add observed product','rect':{'x':20,'y':20,'width':40,'height':20}}]}
    async def call(source,args=()):
        nonlocal reads
        if source!=CART_SCRIPT:return await original(source,args)
        reads+=1
        return {'recognized':True,'items':[{**row,'quantity':1 if reads==1 else 2}]}
    page.call_json=call;page.visual_recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    result=await top_up_cart(page,{'recognized':True,'items':[row]},'B000000001',2,{'title':'observed product','preferred_channel':'fresh'})
    assert result['outcome']=='success' and result['evidence']['result']['already_present']
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_read_only_visual_json_repair_never_dispatches_input():
    runtime,run,payloads=setup(['not a JSON object',{'confirmed':True}]);page=Page()
    result=await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).verify(page,'Read observed state',{'verified':True})
    assert result['visually_verified'] and len(payloads)==2
    assert 'failed JSON parsing or validation' in payloads[1]['messages'][-1]['content']
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_read_only_visual_response_is_unavailable_not_unknown_action():
    runtime,run,payloads=setup(['invalid']*3);page=Page()
    with pytest.raises(VisualRecoveryUnavailable,match='bounded JSON repair'):
        await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).verify(page,'Read only',{'verified':True})
    assert len(payloads)==3
    page.pointer_to.assert_not_called()


@pytest.mark.asyncio
async def test_invalid_post_click_json_keeps_unknown_effect_and_never_replays():
    runtime,run,payloads=setup([{'ref':'e1'},{'confirmed':True},'invalid','invalid','invalid']);page=Page()
    with pytest.raises(VisualActionUncertain):
        await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'One input',allowed_refs={'e1'},readback=AsyncMock(return_value={'verified':True}))
    page.pointer_to.assert_awaited_once()
    assert len(payloads)==5


@pytest.mark.asyncio
async def test_read_only_review_requests_visible_state_without_inventing_a_change():
    runtime,run,payloads=setup([{'confirmed':True}]);page=Page()
    await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).verify(page,'Read only; existing quantity two',{'verified':True})
    instruction=payloads[0]['messages'][0]['content']
    assert 'already-present state can be confirmed without any change' in instruction
    assert 'visibly supported' in instruction
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_cart_quantity_menu_is_never_an_increment_candidate():
    from ai2apps.browser.shopping import top_up_cart,CART_SCRIPT
    runtime,run,payloads=setup();page=Page();original=page.call_json
    row={'id':'B000000001','quantity':1,'channel':'fresh','controls':[{'ref':'e1','label':'Add to Cart, observed product. Click to change quantity','rect':{'x':20,'y':20,'width':40,'height':20}}]}
    async def read(source,args=()):
        return {'recognized':True,'items':[row]} if source==CART_SCRIPT else await original(source,args)
    page.call_json=read;page.visual_recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    result=await top_up_cart(page,{'recognized':True,'items':[row]},'B000000001',2,{'title':'observed product','preferred_channel':'fresh'})
    assert result['outcome']=='needs_user'
    assert result['evidence']['visual_recovery_reason']=='No scoped DOM increment refs'
    page.pointer_to.assert_not_called();assert not payloads

@pytest.mark.parametrize('profile',['normal','privacy'])
@pytest.mark.parametrize('provider',['vision-alpha','vision-beta'])
def test_visual_recovery_uses_only_configured_same_profile_image_route(profile,provider):
    runtime,run,_=setup(image=False)
    run.input['parameters']['model_profile']=profile
    selected=[]
    def defaults(p):
        selected.append(p);return {'image_recognition':f'cloud/{provider}/camera-model'}
    runtime.model_manager.default_models=defaults
    runtime.model_manager.list_cloud=lambda:[{'id':provider,'models':[{'id':'camera-model','enabled':True,'capabilities':{'imageInput':True}}]}]
    assert visual_model(runtime,run)==f'cloud/{provider}/camera-model'
    assert selected==[profile]


def test_visual_route_respects_system_privacy_upgrade_without_normal_fallback():
    runtime,run,_=setup(image=False);runtime.privacy_mode=True
    selected=[]
    def defaults(p):
        selected.append(p);return {'image_recognition':'cloud/private/camera'} if p=='normal' else {}
    runtime.model_manager.default_models=defaults
    runtime.model_manager.list_cloud=lambda:[{'id':'private','models':[{'id':'camera','enabled':True,'capabilities':{'imageInput':True}}]}]
    with pytest.raises(VisualRecoveryUnavailable):visual_model(runtime,run)
    assert selected==['privacy']

@pytest.mark.asyncio
@pytest.mark.parametrize('provider',['camera-alpha','camera-beta'])
@pytest.mark.parametrize('blocked_phase',['select','review','after'])
async def test_visual_model_wait_never_owns_profile_input_lock(provider,blocked_phase):
    import asyncio
    from ai2apps.browser.processing_pool import InputLock
    runtime,run,_=setup();page=Page();page.input_lock=InputLock()
    runtime.model_manager.resolve_default_model=lambda *a,**kw:f'cloud/{provider}/image'
    runtime.model_manager.list_cloud=lambda:[{'id':provider,'models':[{'id':'image','enabled':True,'capabilities':{'imageInput':True}}]}]
    entered=asyncio.Event();release=asyncio.Event();phases=iter(['select','review','after'])
    original=runtime.model_invocations.invoke_agent_cloud_json
    async def invoke(payload,**kw):
        phase=next(phases)
        assert page.input_lock.owner is not asyncio.current_task()
        if phase==blocked_phase:
            entered.set();await release.wait()
        return await original(payload,**kw)
    runtime.model_invocations.invoke_agent_cloud_json=invoke
    task=asyncio.create_task(VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'One permitted action'))
    try:
        await asyncio.wait_for(entered.wait(),1)
        async def other_task():
            async with page.input_lock:return 'admitted'
        assert await asyncio.wait_for(other_task(),1)=='admitted'
        release.set();result=await asyncio.wait_for(task,1)
        assert result['performed'] and result['input_section']['dispatch_state']=='acknowledged'
        assert page.input_lock.owner is None and page.input_lock.depth==0
        page.pointer_to.assert_awaited_once()
    finally:
        release.set()
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)

@pytest.mark.asyncio
async def test_native_dispatch_and_owner_readback_remain_serial_and_post_review_is_frozen():
    import asyncio
    from ai2apps.browser.processing_pool import InputLock
    runtime,run,_=setup();page=Page();page.input_lock=InputLock()
    read_started=asyncio.Event();release_read=asyncio.Event();after_started=asyncio.Event();release_after=asyncio.Event()
    observed={'observed_quantity':2,'verified':True};original=runtime.model_invocations.invoke_agent_cloud_json
    async def input_once(target):
        assert page.input_lock.owner is asyncio.current_task()
    page.pointer_to=AsyncMock(side_effect=input_once)
    async def readback():
        assert page.input_lock.owner is asyncio.current_task()
        read_started.set();await release_read.wait();return observed
    calls=0
    async def invoke(payload,**kw):
        nonlocal calls
        calls+=1
        if calls==3:
            assert page.input_lock.owner is None
            after_started.set();await release_after.wait()
            frozen=json.loads(payload['messages'][1]['content'][0]['text'])['observation']
            assert frozen['owner_readback']['observed_quantity']==2
            assert frozen['controls'][0]['rect']==[20,20,40,20]
        return await original(payload,**kw)
    runtime.model_invocations.invoke_agent_cloud_json=invoke
    task=asyncio.create_task(VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'One action',readback=readback))
    competitor_started=asyncio.Event()
    async def competitor():
        competitor_started.set()
        async with page.input_lock:
            observed['observed_quantity']=99;page.rows[0]['rect'][0]=99
    competitor_task=None
    try:
        await asyncio.wait_for(read_started.wait(),1)
        competitor_task=asyncio.create_task(competitor());await competitor_started.wait()
        assert not competitor_task.done()
        release_read.set();await asyncio.wait_for(after_started.wait(),1)
        await asyncio.wait_for(competitor_task,1)
        release_after.set();result=await asyncio.wait_for(task,1)
        assert result['readback']['observed_quantity']==2
        assert result['state_verified'] is True
        page.pointer_to.assert_awaited_once()
    finally:
        release_read.set();release_after.set()
        for item in (task,competitor_task):
            if item is not None and not item.done():item.cancel()
        await asyncio.gather(*(t for t in (task,competitor_task) if t is not None),return_exceptions=True)

@pytest.mark.asyncio
async def test_binding_is_rechecked_after_waiting_for_profile_input_admission():
    import asyncio
    from ai2apps.browser.processing_pool import InputLock
    runtime,run,_=setup();page=Page();page.input_lock=InputLock();recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    target=await recovery.locate(page,'One action');queued=asyncio.Event()
    async def click():
        queued.set();return await recovery.click(page,'One action',target=target)
    async with page.input_lock:
        task=asyncio.create_task(click());await queued.wait()
        page.rows[0]['text']='Different entity'
    with pytest.raises(VisualRecoveryUnavailable,match='changed after marked review'):
        await task
    page.pointer_to.assert_not_called();assert page.input_lock.owner is None

@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['model_before','input','readback','model_after'])
async def test_visual_cancellation_releases_profile_input_without_replay(phase):
    import asyncio
    from ai2apps.browser.processing_pool import InputLock
    runtime,run,_=setup();page=Page();page.input_lock=InputLock();entered=asyncio.Event();block=asyncio.Event();calls=0
    original=runtime.model_invocations.invoke_agent_cloud_json
    async def invoke(payload,**kw):
        nonlocal calls
        calls+=1
        if (phase=='model_before' and calls==1) or (phase=='model_after' and calls==3):
            entered.set();await block.wait()
        return await original(payload,**kw)
    runtime.model_invocations.invoke_agent_cloud_json=invoke
    async def pointer(target):
        if phase=='input':entered.set();await block.wait()
    page.pointer_to=AsyncMock(side_effect=pointer)
    async def readback():
        if phase=='readback':entered.set();await block.wait()
        return {'verified':True}
    task=asyncio.create_task(VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(page,'One action',readback=readback))
    try:
        await asyncio.wait_for(entered.wait(),1);task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert page.input_lock.owner is None and page.input_lock.depth==0
        assert page.pointer_to.await_count==(0 if phase=='model_before' else 1)
        async def next_task():
            async with page.input_lock:return True
        assert await asyncio.wait_for(next_task(),1)
    finally:
        if not task.done():task.cancel()
        await asyncio.gather(task,return_exceptions=True)

@pytest.mark.asyncio
async def test_cancel_while_queued_does_not_release_another_tasks_input_lock():
    import asyncio
    from ai2apps.browser.processing_pool import InputLock
    runtime,run,_=setup();page=Page();page.input_lock=InputLock();recovery=VisualControlRecovery(runtime,run,['https://arbitrary.test/**'])
    target=await recovery.locate(page,'One action');queued=asyncio.Event()
    async def queued_click():
        queued.set();return await recovery.click(page,'One action',target=target)
    async with page.input_lock:
        owner=asyncio.current_task();task=asyncio.create_task(queued_click());await queued.wait();task.cancel()
        with pytest.raises(asyncio.CancelledError):await task
        assert page.input_lock.owner is owner and page.input_lock.depth==1
    assert page.input_lock.owner is None
    page.pointer_to.assert_not_called()

@pytest.mark.asyncio
async def test_input_section_diagnostics_never_log_goal_or_readback_values(caplog):
    from ai2apps.browser.processing_pool import InputLock
    runtime,run,_=setup();page=Page();page.input_lock=InputLock();run.id='fixture-run'
    with caplog.at_level('INFO',logger='ai2apps.browser.visual_recovery'):
        result=await VisualControlRecovery(runtime,run,['https://arbitrary.test/**']).click(
            page,'private-goal-value',readback=AsyncMock(return_value={'verified':True,'private':'private-readback-value'}))
    assert 'WebAgent input section run=fixture-run context=owned' in caplog.text
    assert 'dispatch_state=acknowledged' in caplog.text
    assert 'private-goal-value' not in caplog.text and 'private-readback-value' not in caplog.text
    assert result['input_section']['wait_ms']>=0 and result['input_section']['hold_ms']>=0
