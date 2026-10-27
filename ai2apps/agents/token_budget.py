"""Durable, user-controlled cumulative model-token allowances."""
import os
from .models import CompleteAction, InteractionAction, InteractionKind, InteractionStatus, RunStepStatus

DEFAULT_MODEL_TOKENS = 500_000
CONTINUE = '继续 / Continue'
STOP = '结束并保留结果 / Finish with results'

def default_model_tokens():
    try:
        value = int(os.environ.get('AI2APPS_AGENT_MAX_MODEL_TOKENS', DEFAULT_MODEL_TOKENS))
        return value if value > 0 else DEFAULT_MODEL_TOKENS
    except (ValueError, TypeError):
        return DEFAULT_MODEL_TOKENS

def token_allowance(context):
    base = context.definition.manifest.get('max_total_model_tokens', default_model_tokens())
    requested = context.run.input.get('run_budget', {}).get('max_model_tokens', base)
    base = requested if type(requested) is int and requested > 0 else default_model_tokens()
    delegated = context.run.delegation.get('budget', {}).get('max_model_tokens')
    if type(delegated) is int and delegated > 0:
        base = min(base, delegated)
    # Step-round renewals also reset the token allowance, without erasing the
    # immutable cumulative usage/steps. Only persisted server requests grant it.
    floor = max([base, *[i.request.get('used_tokens',0)+base for i in context.interactions
        if i.request_key.startswith('step-budget:') and i.status is InteractionStatus.SUBMITTED
        and (i.response or {}).get('answer')==CONTINUE]])
    limit = base
    while True:
        item = context.interaction('token-budget:' + str(limit))
        if item is None or item.status is not InteractionStatus.SUBMITTED:
            if floor>limit:
                limit=floor
                continue
            return base, limit
        if (item.response or {}).get('answer') != CONTINUE:
            return base, limit
        # Derive the grant from the server-owned request, never response fields.
        used = item.request['used_tokens']
        limit = max(limit, used) + base

def budget_decision(context, used):
    base, limit = token_allowance(context)
    if used < limit:
        return None
    key = 'token-budget:' + str(limit)
    item = context.interaction(key)
    if item is not None and item.status is InteractionStatus.SUBMITTED:
        return CompleteAction({'content': '已按你的选择结束；已完成的结果保留在任务中。', 'budget_stopped': True})
    return InteractionAction(
        request_key=key, kind=InteractionKind.MENU,
        prompt=f'本任务累计已使用 {used:,} token，当前预算 {limit:,}。是否继续？继续将重置本轮步骤额度及 {base:,} token 额度（从当前用量起算），可能产生模型费用；已完成的报告会保留。',
        response_schema={'type':'object','properties':{'answer':{'enum':[CONTINUE,STOP]}},'required':['answer'],'additionalProperties':False},
        ui_hints={'control':'menu','options':[CONTINUE,STOP],'allow_other':False},
        request={'control':'agent_budget','used_tokens':used,'used_steps':getattr(context.run,'current_step',0),'limit':limit,'additional_tokens':base},
    )


def total_model_tokens(steps):
    return sum(value for step in steps if step.kind=='model' and step.status is RunStepStatus.COMPLETED
        if isinstance(step.output,dict) and isinstance(step.output.get('usage'),dict)
        if type(value:=step.output['usage'].get('total_tokens')) is int and value>0)


def step_allowance(context):
    base=context.definition.max_steps
    configured=context.run.input.get('run_budget',{}).get('max_steps')
    delegated=context.run.delegation.get('budget',{}).get('max_steps')
    for limit in (configured,delegated):
        if type(limit) is int and limit>0:base=min(base,limit)
    limit=base
    for item in context.interactions:
        if (item.request_key.startswith(('step-budget:','token-budget:'))
            and item.status is InteractionStatus.SUBMITTED
            and (item.response or {}).get('answer')==CONTINUE):
            used=item.request.get('used_steps')
            if type(used) is int and used>=0:limit=max(limit,used+base)
    return base,limit


def step_budget_decision(context):
    base,limit=step_allowance(context);used=context.run.current_step
    if used<limit:return None
    key='step-budget:'+str(limit);item=context.interaction(key)
    if item is not None and item.status is InteractionStatus.SUBMITTED:
        return CompleteAction({'content':'已按你的选择结束；已完成的结果保留在任务中。','budget_stopped':True})
    tokens=total_model_tokens(context.steps)
    return InteractionAction(request_key=key,kind=InteractionKind.MENU,
        prompt=f'本轮 Agent 已达到 {base} 步额度（累计 {used} 步、{tokens:,} token）。是否继续？继续将重置本轮步骤与 Token 额度，可能产生模型费用；已完成的操作不会重新执行。',
        response_schema={'type':'object','properties':{'answer':{'enum':[CONTINUE,STOP]}},'required':['answer'],'additionalProperties':False},
        ui_hints={'control':'menu','options':[CONTINUE,STOP],'allow_other':False},
        request={'control':'agent_budget','used_steps':used,'used_tokens':tokens,'limit':limit,'additional_steps':base})


def execution_budget_decision(context):
    return budget_decision(context,total_model_tokens(context.steps)) or step_budget_decision(context)
