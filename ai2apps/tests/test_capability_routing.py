from types import SimpleNamespace
import pytest
from ai2apps.storage import PlatformDatabase
from ai2apps.services.capability_routing import CapabilityRouter, CapabilityProvider, ProviderUnavailable

@pytest.fixture
def database(tmp_path):
    db=PlatformDatabase(tmp_path/'routing.sqlite3');db.initialize();return db

def context(actor='u',installation='i'):
    async def progress(*args,**kwargs):pass
    return SimpleNamespace(actor_user_id=actor,installation_id=installation,report_progress=progress)

@pytest.mark.asyncio
async def test_fallback_preference_restart_and_owner_isolation(database):
    calls=[]
    async def broken(a,c):calls.append('app');raise ProviderUnavailable('offline before submission')
    async def mini(a,c):calls.append('mini');return {'artifact':{'id':'actual-test-result'}}
    def make(clock):
        router=CapabilityRouter(database,clock=lambda:clock)
        router.register(CapabilityProvider('app','image.generate','app',broken,priority=10))
        router.register(CapabilityProvider('mini','image.generate','studio',mini,mini_app_id='text-to-image'))
        return router
    result=await make(1000).invoke('image.generate',{},context())
    assert calls==['app','mini'];assert result['provider']=='mini'
    calls.clear()
    # Past cooldown and a newly constructed router: successful Mini-App still wins.
    await make(2000).invoke('image.generate',{},context());assert calls==['mini']
    calls.clear();await make(2000).invoke('image.generate',{},context('other'));assert calls==['app','mini']
    calls.clear();await make(2000).invoke('image.generate',{},context(installation='other'));assert calls==['app','mini']

@pytest.mark.asyncio
@pytest.mark.parametrize('error',[TimeoutError('unknown outcome'),PermissionError('denied'),ValueError('missing input')])
async def test_unsafe_failures_do_not_fallback_or_poison_health(database,error):
    calls=[]
    async def first(a,c):raise error
    async def second(a,c):calls.append('called');return {}
    r=CapabilityRouter(database)
    r.register(CapabilityProvider('a','image.edit','app',first,priority=10))
    r.register(CapabilityProvider('b','image.edit','app',second))
    from ai2apps.services.capability_routing import CapabilityInvocationError
    with pytest.raises(CapabilityInvocationError) as caught:await r.invoke('image.edit',{},context())
    assert caught.value.__cause__ is error
    assert caught.value.details['phase']=='execute'
    assert not caught.value.retryable
    assert not calls
    with database.transaction() as db:assert db.execute('select count(*) from capability_provider_health').fetchone()[0]==0

@pytest.mark.asyncio
async def test_cooldown_and_capability_boundary(database):
    calls=[]
    async def unavailable(a,c):calls.append(1);raise ProviderUnavailable('no model')
    r=CapabilityRouter(database,clock=lambda:100)
    r.register(CapabilityProvider('generate','image.generate','app',unavailable))
    for _ in range(2):
        with pytest.raises(Exception,match='No available provider'):await r.invoke('image.generate',{},context())
    assert calls==[1]
    with pytest.raises(Exception,match='No available provider'):await r.invoke('image.edit',{},context())
    assert calls==[1]

@pytest.mark.asyncio
async def test_inspection_matches_routing_and_is_scoped(database):
    async def unavailable(a,c): raise ProviderUnavailable('offline')
    async def ok(a,c): return {}
    r=CapabilityRouter(database,clock=lambda:1000)
    r.register(CapabilityProvider('app','image.generate','app',unavailable,priority=100))
    r.register(CapabilityProvider('mini','image.generate','studio',ok,mini_app_id='mini',priority=50))
    await r.invoke('image.generate',{},context())
    rows=r.inspect('u','i')
    assert rows[0]['id']=='mini' and rows[0]['rank']==1
    assert rows[1]['status']=='cooldown' and rows[1]['rank'] is None
    assert rows[1]['cooldown_seconds']==300
    assert r.inspect('other','i')[0]['id']=='app'
    r.clock=lambda:1400
    assert r.inspect('u','i')[1]['rank']==2

@pytest.mark.asyncio
async def test_preflight_rejection_reports_provider_owner_and_stage(database):
    from ai2apps.services.capability_routing import ProviderIncompatible, CapabilityInvocationError
    calls=[]
    async def prepare(args,ctx):raise ProviderIncompatible('Reference roles conflict')
    async def execute(args,ctx):calls.append(args)
    router=CapabilityRouter(database)
    router.register(CapabilityProvider('mini','image.group_photo','studio',execute,mini_app_id='group-photo',prepare=prepare))
    with pytest.raises(CapabilityInvocationError) as caught:
        await router.invoke('image.group_photo',{'person_artifact_ids':['a','b']},context())
    error=caught.value
    assert error.code=='provider_incompatible'
    assert 'No available provider' not in str(error)
    assert error.details['app_id']=='studio'
    assert error.details['mini_app_id']=='group-photo'
    assert error.details['phase']=='prepare'
    assert error.details['provider_attempts'][0]['reason']=='Reference roles conflict'
    assert not error.retryable and calls==[]

@pytest.mark.asyncio
async def test_execution_failure_preserves_owner_without_fallback(database):
    from ai2apps.services.capability_routing import CapabilityInvocationError
    async def execute(args,ctx):raise RuntimeError('upstream disconnected')
    router=CapabilityRouter(database)
    router.register(CapabilityProvider('mini','image.edit','studio',execute,mini_app_id='edit'))
    with pytest.raises(CapabilityInvocationError) as caught:
        await router.invoke('image.edit',{},context())
    assert caught.value.details['phase']=='execute'
    assert caught.value.details['provider']=='mini'
    assert caught.value.details['provider_attempts'][0]['status']=='failed'
    assert not caught.value.retryable

@pytest.mark.asyncio
@pytest.mark.parametrize('identity',['provider.alpha','package.beta'])
@pytest.mark.parametrize('arguments',[
    {'query':'same','parameters':{'query':'same'}},
    {'parameters':[]},
    {'parameters':{'provider':'invented'}},
])
async def test_invalid_envelope_is_preflight_no_provider_runs(database,identity,arguments):
    from ai2apps.services.capability_routing import CapabilityInvocationError
    calls=[]
    async def prepare(args,ctx):calls.append('prepare');return args
    async def execute(args,ctx):calls.append('execute');return {}
    router=CapabilityRouter(database)
    router.register(CapabilityProvider(identity,'test.envelope',identity,execute,prepare=prepare))
    with pytest.raises(CapabilityInvocationError) as caught:
        await router.invoke('test.envelope',arguments,context())
    assert caught.value.code=='invalid_tool_arguments'
    assert caught.value.details['phase']=='prepare'
    assert not caught.value.retryable and calls==[]
    with database.transaction() as db:
        assert db.execute('select count(*) from capability_provider_health').fetchone()[0]==0

@pytest.mark.asyncio
@pytest.mark.parametrize('phase',['prepare','execute'])
async def test_schema_error_before_handler_distinguished_from_after_submit(database,phase):
    from ai2apps.services.capability_routing import CapabilityInvocationError
    from jsonschema import ValidationError
    calls=[]
    async def prepare(args,ctx):
        if phase=='prepare':raise ValidationError('input rejected')
        return args
    async def execute(args,ctx):calls.append('submitted');raise ValidationError('output rejected')
    router=CapabilityRouter(database)
    router.register(CapabilityProvider('arbitrary','test.schema','arbitrary',execute,prepare=prepare))
    with pytest.raises(CapabilityInvocationError) as caught:await router.invoke('test.schema',{},context())
    assert caught.value.code==('invalid_tool_arguments' if phase=='prepare' else 'provider_error')
    assert caught.value.details['phase']==phase
    assert calls==([] if phase=='prepare' else ['submitted'])
