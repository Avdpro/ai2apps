"""Task policy/budgets: real compilation/SQLite, controlled time and no network."""
import asyncio
import json
import time
from datetime import datetime, UTC
from types import SimpleNamespace as NS
from copy import deepcopy
import pytest
from ai2apps.agent_builder.execution_policy import resolve_policy, inherit_policy, combine_minimum
from ai2apps.agent_builder.compiler import compile_source
from ai2apps.browser.execution_budget import TaskExecutionBudget, RecoveryBudgetExceeded
from ai2apps.agents.browser_builder import browser_builder_executor
from ai2apps.agents.models import FailAction, InteractionAction, InteractionStatus
from test_web_agent_mini_apps import broker


def test_defaults_add_no_caps_and_do_not_disable_existing_guards():
    p=resolve_policy()
    assert p['allow_user_intervention'] and p['visual_locating'] and p['readback']
    assert p['visual_review']=='on_recovery'
    assert all(p[k] is None for k in ('timeout_seconds','recovery_timeout_seconds','max_recovery_attempts'))

@pytest.mark.parametrize('value',[
    {'timeout_seconds':0},{'timeout_seconds':True},{'timeout_seconds':float('inf')},
    {'recovery_timeout_seconds':-1},{'recovery_timeout_seconds':float('nan')},
    {'max_recovery_attempts':1.5},{'max_recovery_attempts':True},{'allow_user_intervention':'no'}])
def test_invalid_budgets_fail_preflight(value):
    with pytest.raises(ValueError):resolve_policy(value)
    assert not compile_source({'agent_type':'web','execution_policy':value,'steps':[{'name':'x','operation':'inspect'}]}).valid

@pytest.mark.parametrize('provider',['arbitrary.alpha','another.vendor'])
def test_nested_tasks_cannot_reset_caps_or_enable_interaction_and_vision(provider):
    parent={'allow_user_intervention':False,'visual_locating':False,'visual_review':'off',
        'timeout_seconds':10,'recovery_timeout_seconds':2,'max_recovery_attempts':1}
    child=compile_source({'name':provider,'agent_type':'web','steps':[{'name':'x','operation':'inspect'}]}).ir
    p=inherit_policy(parent,child['execution_policy'])
    assert all(p[k]==v for k,v in parent.items())
    assert inherit_policy(parent,{'timeout_seconds':3})['timeout_seconds']==3
    assert combine_minimum({'timeout_seconds':8},{'timeout_seconds':12})['timeout_seconds']==8
    with pytest.raises(ValueError):inherit_policy(parent,child['execution_policy'],{'visual_review':'always'})

@pytest.mark.asyncio
async def test_recovery_accounting_is_cumulative_persisted_and_nested_not_double_charged():
    now=[10.0];saved=[]
    p={'recovery_timeout_seconds':5,'max_recovery_attempts':2}
    b=TaskExecutionBudget(p,clock=lambda:now[0],checkpoint=lambda s:saved.append(deepcopy(s)))
    async with b.recovery():
        assert saved[-1]['attempts']==1 and saved[-1]['active_since']==10
        async with b.recovery():now[0]+=2
    assert saved[-1]=={'attempts':1,'used_seconds':2}
    resumed=TaskExecutionBudget(p,state=saved[-1],clock=lambda:now[0],checkpoint=lambda s:saved.append(deepcopy(s)))
    async with resumed.recovery():now[0]+=1
    with pytest.raises(RecoveryBudgetExceeded):
        async with resumed.recovery():raise AssertionError('Third recovery must not run')
    assert saved[-1]=={'attempts':2,'used_seconds':3}

@pytest.mark.asyncio
async def test_restart_does_not_refund_inflight_recovery_or_its_time():
    saved=[]
    b=TaskExecutionBudget({'recovery_timeout_seconds':4,'max_recovery_attempts':2},
        state={'attempts':1,'used_seconds':1,'active_since':10},clock=lambda:14,checkpoint=saved.append)
    assert saved[-1]=={'attempts':1,'used_seconds':5}
    with pytest.raises(RecoveryBudgetExceeded):
        async with b.recovery():raise AssertionError('Budget exhausted before restart')

@pytest.mark.asyncio
async def test_recovery_time_limit_cancels_work_without_replay():
    calls=[];b=TaskExecutionBudget({'recovery_timeout_seconds':.01})
    with pytest.raises(RecoveryBudgetExceeded) as error:
        async with b.recovery():calls.append('once');await asyncio.sleep(1)
    assert calls==['once'] and error.value.uncertain
    assert 'active_since' not in b.state and b.state['used_seconds']>=.009

@pytest.mark.asyncio
@pytest.mark.parametrize('policy',[{'max_recovery_attempts':0},{'recovery_timeout_seconds':0}])
async def test_zero_budget_disables_recovery(policy):
    with pytest.raises(RecoveryBudgetExceeded):
        async with TaskExecutionBudget(policy).recovery():raise AssertionError('Disabled')


def context(source,interactions=()):
    ir=compile_source(source).ir
    return NS(run=NS(input={'parameters':{'ir':ir}},created_at=datetime.now(UTC)),
        definition=NS(max_steps=20),interactions=interactions,step=lambda key:None)

@pytest.mark.parametrize('allowed',[True,False])
def test_no_intervention_policy_prevents_approval_form_without_approving(allowed):
    c=context({'agent_type':'web','execution_policy':{'allow_user_intervention':allowed},
        'steps':[{'name':'approval','operation':'approval','on':{'success':'done','failed':'failed'}}]})
    a=browser_builder_executor(c)
    assert isinstance(a,InteractionAction if allowed else FailAction)
    if not allowed:assert a.code=='browser_user_intervention_disabled'

@pytest.mark.parametrize('reason',['authentication','captcha','legal_consent','unknown'])
def test_no_intervention_policy_prevents_browser_assistance_form(reason):
    c=context({'agent_type':'web','execution_policy':{'allow_user_intervention':False},
        'steps':[{'name':'read','operation':'inspect','on':{'success':'done','failed':'failed'}}]})
    first=browser_builder_executor(c)
    c.interactions=[NS(id='i',request=first.request,status=InteractionStatus.SUBMITTED,
        response={'outcome':'needs_user','evidence':{'reason':reason}})]
    a=browser_builder_executor(c)
    assert isinstance(a,FailAction) and a.code=='browser_user_intervention_disabled'


def test_total_deadline_includes_queue_and_idempotent_retry_cannot_reset_it(broker,monkeypatch):
    from ai2apps.browser.tasks import BrowserTaskRepository
    from ai2apps.browser.task_monitor import reconcile_browser_tasks
    service,mounted,principal=broker
    task=service.submit('mount',principal,capability='list',parameters={'count':1},profile='default',request_id='deadline',
        execution_policy={'timeout_seconds':10,'allow_user_intervention':False})
    deadline=task['browser_context']['task_deadline_at']
    assert deadline==pytest.approx(task['created_at']+10)
    same=service.submit('mount',principal,capability='list',parameters={'count':1},profile='default',request_id='deadline',
        execution_policy={'timeout_seconds':10,'allow_user_intervention':False})
    assert same['browser_context']['task_deadline_at']==deadline
    monkeypatch.setattr('ai2apps.browser.task_monitor.time.time',lambda:deadline+1)
    reconcile_browser_tasks(service.runtime,BrowserTaskRepository(service.runtime.database),'owner')
    assert BrowserTaskRepository(service.runtime.database).get('owner',task['id'])['status']=='failed'

@pytest.mark.asyncio
async def test_total_deadline_covers_page_setup_and_not_only_browser_action():
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    run=NS(id='r',created_at=datetime.now(UTC),input={'parameters':{'ir':{'execution_policy':{'timeout_seconds':.01}}}})
    runner=BackgroundBrowserRunner(NS(database=object(),events=None,agents=NS(get_run=lambda id:run)))
    calls=[]
    async def stalled(item):calls.append('page_setup');await asyncio.sleep(1)
    runner._execute_interaction=stalled
    runner.deliver_failure=lambda *a,**k:calls.append(k['reason'])
    await runner.execute_interaction({'run_id':'r','id':'i'})
    assert calls==['page_setup','browser_task_timeout']


@pytest.mark.asyncio
async def test_recovery_reservation_is_saved_in_real_run_json_and_survives_new_runner(tmp_path):
    import json
    from test_browser_background import JournalDatabase
    from ai2apps.browser.background_runner import BackgroundBrowserRunner
    db=JournalDatabase(tmp_path/'budget.sqlite')
    policy={'max_recovery_attempts':1}
    with db.transaction(write=True) as c:
        c.execute('UPDATE agent_runs SET input_json=? WHERE id=?',
            (json.dumps({'parameters':{'owner_user_id':'alice','ir':{'execution_policy':policy}}}),'run'))
    def run():
        with db.transaction() as c:data=json.loads(c.execute('SELECT input_json FROM agent_runs WHERE id=?',('run',)).fetchone()['input_json'])
        return NS(id='run',input=data,created_at=datetime.now(UTC))
    first=BackgroundBrowserRunner(NS(database=db,events=None)).execution_budget(run())
    async with first.recovery():
        stored=run().input['parameters']['browser_context']['recovery_budget']
        assert stored['attempts']==1 and stored.get('active_since') is not None
    second=BackgroundBrowserRunner(NS(database=db,events=None)).execution_budget(run())
    with pytest.raises(RecoveryBudgetExceeded):
        async with second.recovery():raise AssertionError('New runner cannot refund recovery')


def test_required_shopping_review_is_not_waived_by_zero_recovery_budget():
    from ai2apps.browser.shopping import cart_source
    source=cart_source({},[])
    p=resolve_policy({'max_recovery_attempts':0,'recovery_timeout_seconds':0,'visual_review':'off'},source['minimum_execution_policy'])
    assert p['visual_review']=='always' and p['readback']


def test_no_intervention_policy_blocks_ai_classification_assistance():
    from ai2apps.agents.models import RunStepStatus
    c=context({'agent_type':'web','execution_policy':{'allow_user_intervention':False},
        'steps':[{'name':'classify','operation':'ai.classify','ai':{'tier':'standard','instruction':'Classify',
            'output_schema':{'type':'object','properties':{'outcome':{'enum':['success','needs_user']}},'required':['outcome']}},
            'on':{'success':'done','needs_user':'pause','failed':'failed'}}]})
    c.run.input['parameters']['ai_model_routes']={'standard':'model'}
    c.step=lambda key:NS(status=RunStepStatus.COMPLETED,output={'choices':[{'message':{'content':json.dumps({'outcome':'needs_user','reason':'captcha'})}}]})
    a=browser_builder_executor(c)
    assert isinstance(a,FailAction) and a.code=='browser_user_intervention_disabled'

@pytest.mark.asyncio
async def test_declared_interpreted_execution_does_not_spend_recovery_budget_but_fallback_does():
    from unittest.mock import AsyncMock
    from ai2apps.browser.background_executor import BackgroundExecutor
    page=NS(context_id='c',execution_budget=TaskExecutionBudget({'max_recovery_attempts':0}),
        observation=AsyncMock(return_value={'url':'https://arbitrary.test/'}),related_windows=AsyncMock(return_value=[]))
    executor=BackgroundExecutor(NS());executor.planner.next=AsyncMock(return_value={'decision':'complete'})
    request={'step':{'operation':'inspect'},'site_scope':['https://arbitrary.test/**']}
    assert (await executor.adaptive(page,request,NS()))['outcome']=='success'
    assert page.execution_budget.state=={}
    with pytest.raises(RecoveryBudgetExceeded):
        await executor.adaptive(page,request,NS(),failure={'outcome':'not_found'})
    assert executor.planner.next.await_count==1
