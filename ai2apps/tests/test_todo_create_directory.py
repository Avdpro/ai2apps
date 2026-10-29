"""Todo owner supplies directory choices/defaults; shared Agent has no Todo branch."""
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
import pytest
from ai2apps.identity import RequestPrincipal
from ai2apps.todo.aaat import store
from test_app_interactions import runtime
from test_builtin_app_aaat import context


def provider(runtime):
    return next(p for p in runtime.app_capability_router.providers.values() if p.capability == 'todo.create')


@pytest.mark.asyncio
async def test_empty_owner_descriptor_is_read_only_and_confirmed_create_is_replay_safe(runtime):
    s=store(runtime)
    d=await provider(runtime).describe(RequestPrincipal.legacy_local())
    field=next(f for f in d['fields'] if f['key']=='directory_id')
    assert field['type']=='select' and field['default']=='__todo_inbox__'
    assert 'Inbox' in next(x for x in field['options'] if x['value']=='__todo_inbox__')['label']['en']
    assert s.snapshot('local')['directories']==[]
    ctx=replace(context(runtime),invocation_id='empty-owner-create')
    invoke=runtime.app_capability_router.invoke
    first=await invoke('todo.create',{'title':'Buy eggs'},ctx)
    again=await invoke('todo.create',{'title':'Buy eggs','directory_id':'__todo_inbox__'},ctx)
    assert first['task']['id']==again['task']['id']
    snapshot=s.snapshot('local')
    assert len(snapshot['directories'])==len(snapshot['tasks'])==1
    assert first['task']['directory_id']==snapshot['directories'][0]['id']


@pytest.mark.asyncio
async def test_named_choices_are_owner_scoped_and_only_single_directory_is_preselected(runtime):
    s=store(runtime);one=s.directory('local','Personal');foreign=s.directory('other','Private')
    d=await provider(runtime).describe(RequestPrincipal.legacy_local())
    field=next(f for f in d['fields'] if f['key']=='directory_id')
    assert field['default']==one['id']
    assert {'value':one['id'],'label':'Personal'} in field['options']
    assert all(x['value']!=foreign['id'] for x in field['options'])
    two=s.directory('local','Work')
    d=await provider(runtime).describe(RequestPrincipal.legacy_local())
    field=next(f for f in d['fields'] if f['key']=='directory_id')
    assert 'default' not in field
    assert {one['id'],two['id']} <= {x['value'] for x in field['options']}
    with pytest.raises(Exception):
        await runtime.app_capability_router.invoke('todo.create',{'title':'Needs choice'},replace(context(runtime),invocation_id='ambiguous'))
    assert s.snapshot('local')['tasks']==[]


def test_inbox_task_write_is_atomic_idempotent_and_owner_scoped(runtime):
    s=store(runtime);args={'title':'Eggs','directory_id':'__todo_inbox__'}
    with pytest.raises(KeyError):
        s.save('local',{**args,'parent_id':'missing'},creation_key='bad',create_inbox=True)
    assert s.snapshot('local')['directories']==[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks=list(pool.map(lambda _:store(runtime).save('local',args,creation_key='same',create_inbox=True),range(8)))
    assert len({t['id'] for t in tasks})==1
    a=s.snapshot('local');assert len(a['directories'])==len(a['tasks'])==1
    other=s.save('other',args,creation_key='same',create_inbox=True)
    assert other['directory_id']!=tasks[0]['directory_id']
    with pytest.raises(Exception):
        s.save('local',{**args,'title':'changed'},creation_key='same',create_inbox=True)


@pytest.mark.asyncio
async def test_explicit_directory_name_resolution_never_falls_back_or_leaks_other_owner(runtime):
    s=store(runtime);personal=s.directory('local','🏠 个人');s.directory('local','工作')
    s.directory('other','隐私')
    invoke=runtime.app_capability_router.invoke;ctx=context(runtime)
    result=await invoke('todo.resolve_directory',{'query':'个人'},ctx)
    assert result['status']=='resolved' and result['directory']['id']==personal['id']
    task=await invoke('todo.create',{'title':'买黄瓜','directory_id':result['directory']['id']},replace(ctx,invocation_id='cucumber'))
    assert task['task']['directory_id']==personal['id']
    assert (await invoke('todo.resolve_directory',{'query':'隐私'},ctx))['status']=='not_found'
    s.directory('local','个人')
    result=await invoke('todo.resolve_directory',{'query':'个人'},ctx)
    assert result['status']=='ambiguous' and result['directory'] is None and len(result['candidates'])==2
    result=await invoke('todo.resolve_directory',{'query':'工'},ctx)
    assert result['status']=='ambiguous' and result['directory'] is None


@pytest.mark.asyncio
async def test_missing_explicit_name_creates_requested_directory_only_on_confirmed_write(runtime):
    s=store(runtime);ctx=replace(context(runtime),invocation_id='new-named-directory')
    invoke=runtime.app_capability_router.invoke
    result=await invoke('todo.resolve_directory',{'query':'个人'},ctx)
    assert result['status']=='not_found'
    assert result['creation']=={'directory_id':'__todo_new__','directory_name':'个人'}
    d=await provider(runtime).describe(RequestPrincipal.legacy_local())
    assert s.list_directories('local')==[]
    from ai2apps.agents.parameter_forms import required_fields
    assert 'directory_name' in required_fields(d['effective_schema'],{'directory_id':'__todo_new__'})
    args={**result['creation'],'title':'买黄瓜'}
    first=await invoke('todo.create',args,ctx)
    again=await invoke('todo.create',args,ctx)
    assert first['task']['id']==again['task']['id']
    assert s.list_directories('local')==[{'id':first['task']['directory_id'],'title':'个人'}]
    assert len(s.snapshot('local')['tasks'])==1
    s.rename_directory('local',first['task']['directory_id'],'个人新名','个人')
    assert (await invoke('todo.create',args,ctx))['task']['id']==first['task']['id']
    assert len(s.list_directories('local'))==1


def test_named_directory_transaction_rollback_concurrency_and_conflict(runtime):
    s=store(runtime);args={'title':'买黄瓜','directory_id':'__todo_new__'}
    with pytest.raises(KeyError):
        s.save('local',{**args,'parent_id':'missing'},creation_key='invalid',directory_name='个人')
    assert s.list_directories('local')==[]
    with ThreadPoolExecutor(max_workers=4) as pool:
        tasks=list(pool.map(lambda i:store(runtime).save('local',args,creation_key='named-'+str(i),directory_name='个人'),range(8)))
    assert len({t['directory_id'] for t in tasks})==1 and len(s.list_directories('local'))==1
    assert len(s.snapshot('local')['tasks'])==8
    s.directory('local','🏠 个人')
    with pytest.raises(ValueError,match='ambiguous'):
        s.save('local',args,creation_key='ambiguous',directory_name='个人')
