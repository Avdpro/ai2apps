import pytest
from ai2apps.todo.aaat import Projects,normalize,query_projects,store
from ai2apps.todo.models import TaskInput
from test_app_interactions import runtime
from test_builtin_app_aaat import context


def tree():
    def task(id,title,parent=None,priority='A',status='not_started',**kw):
        return {'id':id,'title':title,'directory_id':'d','parent_id':parent,'priority':priority,'status':status,'completed':status=='completed','revision':1,**kw}
    return {'directories':[{'id':'d','title':'Development'}], 'tasks':[
        task('root','🎥 Video Studio 增强'),task('a','统一行为：生成进度','root',status='in_progress'),
        task('b','婴儿视频制作','root',priority='B'),task('c','完成的细项','a',status='completed'),
        task('unrelated','Video unrelated',priority='A',status='completed'),
        task('trash','Deleted','root',deleted_at='now'),task('archive','Archived','root',archived_at='now')]}


@pytest.mark.parametrize('query',['Video Studio','🎥 Video Studio','VIDEO   STUDIO','Ｖｉｄｅｏ　Ｓｔｕｄｉｏ'])
def test_normalized_partial_title_resolves_parent_not_directory(query):
    result=query_projects(tree(),'todo.project_stats',{'query':query})
    assert result['project']['id']=='root' and result['project']['path']==['Development','🎥 Video Studio 增强']
    assert result['direct']['total']==2 and result['recursive']['total']==3
    assert result['stats']['by_priority']['A']==2 and result['stats']['completed']==1
    assert result['counting_basis']['include_project'] is False
    assert result['aaat_context']['coverage']['complete']


def test_ambiguous_candidates_do_not_produce_statistics_or_pick_first():
    data=tree();data['tasks'].append({**data['tasks'][0],'id':'root2','title':'Video Studio Bug 修复'})
    result=query_projects(data,'todo.project_stats',{'query':'Video Studio'})
    assert result['status']=='ambiguous' and result['project'] is None and 'stats' not in result
    assert {x['id'] for x in result['candidates']}=={'root','root2'}
    # An exact complete title is stronger than a partial prefix.
    data['tasks'][-1]['title']='Video Studio'
    assert Projects(data).resolve('Video Studio')['project']['id']=='root2'


def test_nonexistent_name_is_not_reported_as_zero_and_foreign_id_fails():
    assert query_projects(tree(),'todo.project_stats',{'query':'missing'})['status']=='not_found'
    with pytest.raises(KeyError):query_projects(tree(),'todo.project_stats',{'project_id':'foreign'})
    with pytest.raises(ValueError):Projects(tree()).resolve('🎥')


def test_counts_cover_completed_descendants_independent_of_page_limit():
    data=tree()
    for i in range(150):data['tasks'].append({**data['tasks'][2],'id':'extra'+str(i),'status':'completed','completed':True})
    page=query_projects(data,'todo.children',{'project_id':'root','scope':'recursive','limit':1})
    assert len(page['members'])==1 and page['total']==153 and page['next_offset']==1
    assert page['aaat_context']['status']=='partial'
    stats=query_projects(data,'todo.project_stats',{'project_id':'root'})
    assert stats['stats']['total']==153 and stats['stats']['completed']==151
    assert stats['stats']['by_priority']['B']==151
    assert query_projects(data,'todo.project_stats',{'project_id':'root','scope':'direct'})['stats']['total']==152


@pytest.mark.asyncio
async def test_router_owned_hierarchy_and_app_api_share_same_business_result(runtime):
    import httpx
    from fastapi import FastAPI
    from types import SimpleNamespace
    from ai2apps.identity import RequestPrincipal
    from ai2apps.api.todo import create_todo_router
    ctx=context(runtime);s=store(runtime);d=s.directory('local','Development')
    root=s.save('local',{'title':'🎥 Video Studio 增强','directory_id':d['id']})
    s.save('local',{'title':'不含项目名称的子项','directory_id':d['id'],'parent_id':root['id'],'priority':'A','status':'completed'})
    other=s.directory('other','private');s.save('other',{'title':'Video Studio','directory_id':other['id']})
    result=await runtime.app_capability_router.invoke('todo.project_stats',{'query':'Video Studio'},ctx)
    assert result['project']['id']==root['id'] and result['stats']['completed']==1
    runtime.todo=SimpleNamespace(store=s)
    app=FastAPI();app.include_router(create_todo_router(lambda:runtime,RequestPrincipal.legacy_local))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
        r=await client.get('/todo/projects/'+root['id']+'/stats')
        assert r.status_code==200,r.text
        assert r.json()['stats']==result['stats']
        assert (await client.get('/todo/projects/foreign/stats')).status_code==404
    with pytest.raises(Exception):await runtime.app_capability_router.invoke('todo.project_stats',{'query':'Video Studio','project_id':root['id']},ctx)


@pytest.mark.asyncio
async def test_search_progress_filters_before_pagination_and_excludes_foreign(runtime):
    s=store(runtime);d=s.directory('local','Work');other=s.directory('other','Private')
    for i,value in enumerate([0,10,11,60,90]):
        s.save('local',{'directory_id':d['id'],'title':'Progress '+str(i),'status':'in_progress','progress':value})
    s.save('local',{'directory_id':d['id'],'title':'Paused','status':'paused','progress':50})
    s.save('other',{'directory_id':other['id'],'title':'Private','status':'in_progress','progress':80})
    invoke=runtime.app_capability_router.invoke;ctx=context(runtime)
    args={'status':'in_progress','progress_gt':10,'limit':2}
    first=await invoke('todo.search',args,ctx)
    assert first['total']==3 and [t['progress'] for t in first['tasks']]==[11,60]
    assert first['next_offset']==2 and first['aaat_context']['coverage']['truncated']
    second=await invoke('todo.search',{**args,'offset':2},ctx)
    assert [t['progress'] for t in second['tasks']]==[90] and second['next_offset'] is None
    bounded=await invoke('todo.search',{'status':'in_progress','progress_gte':10,'progress_lte':60},ctx)
    assert [t['progress'] for t in bounded['tasks']]==[10,11,60]
    strict=await invoke('todo.search',{'status':'in_progress','progress_lt':10},ctx)
    assert [t['progress'] for t in strict['tasks']]==[0]
    assert all('path' in t and 'priority' in t for t in bounded['tasks'])
    assert first['provider_version']=='2'


@pytest.mark.asyncio
@pytest.mark.parametrize('bound',[-1,101,True,'10'])
async def test_search_progress_bounds_are_validated(runtime,bound):
    with pytest.raises(Exception):
        await runtime.app_capability_router.invoke('todo.search',{'progress_gt':bound},context(runtime))


def test_progress_projection_has_historical_defaults_and_excludes_archived():
    data=tree();data['tasks'][0]['progress']=None
    projects=Projects(data)
    assert projects.entity('root')['progress']==0
    assert projects.entity('c')['progress']==100
    assert 'trash' not in projects.tasks and 'archive' not in projects.tasks
