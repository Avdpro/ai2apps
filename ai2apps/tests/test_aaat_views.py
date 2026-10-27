from copy import deepcopy
from types import SimpleNamespace as NS
import json
import pytest
from ai2apps.services.aaat import validate_view
from ai2apps.services.capability_routing import CapabilityProvider
from test_aaat_declaration_context import runtime,wait


def view():
    return {'schema':'ai2apps.aaat-view/v1','id':'items','layout':'table','title':'<b>Data</b>',
            'columns':[{'key':'n','label':'Count'}],'items':[{'id':'one','title':'<script>untrusted</script>',
            'image':{'url':'https://cdn.example/image.jpg'},'url':'https://example.org/original','fields':{'n':'2'}}]}

@pytest.mark.parametrize('url',['javascript:alert(1)','data:image/svg+xml,evil','//evil.example/a','https://user:pw@example.com/a','/\\evil.example/a','https://example.com/\nx'])
def test_unsafe_view_urls_rejected(url):
    data=view();data['items'][0]['image']['url']=url
    with pytest.raises(ValueError):validate_view(data)


def test_view_bounds_and_plain_text():
    data=view();assert validate_view(data)==data
    for mutate in [lambda d:d.update(html='<div>'),lambda d:d['items'].append(d['items'][0]),lambda d:d['items'][0]['fields'].update(hidden='x')]:
        candidate=deepcopy(data);mutate(candidate)
        with pytest.raises(Exception):validate_view(candidate)

@pytest.mark.asyncio
@pytest.mark.parametrize('identity',['sample.inventory','other.media'])
async def test_arbitrary_provider_view_is_persisted_and_restored_without_execution(runtime,identity):
    from ai2apps.chat import ChatRepository
    from ai2apps.agents.general import _tool_alias
    calls=[]
    async def execute(args,context):calls.append(args);return {'aaat_view':view()}
    runtime.app_capability_router.register(CapabilityProvider(identity,'gallery.search',identity,execute))
    async def model(request):
        if calls:return {'choices':[{'message':{'role':'assistant','content':'Done'},'finish_reason':'stop'}]}
        return {'choices':[{'message':{'role':'assistant','tool_calls':[{'id':'read','type':'function','function':{'name':_tool_alias('gallery.search'),'arguments':json.dumps({'query':'items','provider':identity})}}]},'finish_reason':'tool_calls'}]}
    runtime.agent_runtime.bind_model_provider(model)
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        from test_aaat_execution_flow import new_run
        run=new_run(runtime,['gallery.search'],prompt='items')
        runtime.agent_runtime.wake();result=await wait(runtime,run.id,'completed')
        records=result.output['aaat_views'];assert records[0]['view']==view() and records[0]['provider']==identity
        with runtime.database.transaction() as db:
            row=db.execute('SELECT metadata_json FROM messages WHERE id=?',(result.output['message_id'],)).fetchone()
        assert json.loads(row['metadata_json'])['aaat_views']==records
        assert runtime.agents.get_run(run.id).output['aaat_views']==records
        assert len(calls)==1
        failed=NS(id='failed',kind='tool',tool_name='gallery.search',status=NS(value='failed'),output={'provider':identity,'aaat_view':view()})
        assert runtime.app_capability_router.project_result_views([failed])==[]
    finally:await runtime.stop_background_tasks()

@pytest.mark.asyncio
async def test_rejected_view_preserves_executed_business_result_without_retry(runtime):
    from test_builtin_app_aaat import context
    calls=[]
    async def execute(args,scope):
        calls.append(args);bad=view();bad['items'][0]['image']['url']='javascript:alert(1)'
        return {'actual_result':'completed','aaat_view':bad}
    runtime.app_capability_router.register(CapabilityProvider('test.bad-view','gallery.search','test.owner',execute))
    scope=context(runtime)
    result=await runtime.app_capability_router.invoke('gallery.search',{'query':'items','provider':'test.bad-view'},scope)
    assert result['actual_result']=='completed' and 'aaat_view' not in result
    assert result['aaat_view_error']['code']=='invalid_result_view' and len(calls)==1
