"""Actor-authenticated adaptive browser planning with no HTTP or page session."""
from __future__ import annotations

import json
import re
import uuid
from types import SimpleNamespace

from ai2apps.agent_builder.compiler import compile_source
from ai2apps.agent_builder.exploration_prompt import _exploration_prompt
from ai2apps.agents.json_output import JsonRepairBudget, parse_model_json, repair_json_request


def validate_completion(step, attempts):
    successful = [item for item in attempts if item.get('outcome') == 'success']
    if not successful:
        raise ValueError('Completion requires successful evidence')
    # Evaluate the current step, not the whole capability: opening an editor
    # can finish its navigation step, but cannot finish a publish/send step.
    target = step.get('target') or {}
    requested = target.get('accessible_name') or target.get('intent') or step.get('description', '')
    if step.get('operation') in ('click', 'delete') and re.search(r'发布|发送|publish|post|send', requested, re.I):
        if not any((item.get('source_step') or {}).get('operation') == 'click' and
            re.search(r'发布|发送|publish|post|send', json.dumps(
                (item.get('source_step') or {}).get('target') or {}, ensure_ascii=False), re.I) and
            not re.search(r'登录|注册|login|sign.?in|register', json.dumps(
                (item.get('source_step') or {}).get('target') or {}, ensure_ascii=False), re.I)
            for item in successful):
            raise ValueError('Publishing requires successful execution of the publish/send control')


class BackgroundPlanner:
    def __init__(self, runtime):
        self.runtime = runtime

    async def next(self, *, run, step, observation, attempts, scopes):
        parameters = run.input['parameters']
        tier = step.get('ai', {}).get('tier', 'standard')
        model_id = parameters.get('ai_model_routes', {}).get(tier)
        if not model_id:
            model_id = self.runtime.model_manager.resolve_default_model('work_' + tier)
        invocations = self.runtime.model_invocations
        model = invocations.model(model_id)
        if model is None or 'chat_completions' not in model.endpoints:
            raise RuntimeError('No task model available for backend browser planning')
        context = invocations.context_for_actor(parameters['owner_user_id'], session_id=run.session_id,
                                                consumer_app_id='ai2apps.agents')
        goal = ('Capability work goal / guidance:\n' + str(step.get('working_goal', '')) +
                '\nComplete only this Agent step: ' + str(step.get('description', step.get('id', ''))) +
                '\nResolved arguments: ' + json.dumps(step.get('arguments', {}), ensure_ascii=False) +
                '\nPrior failed actions may have partially succeeded. Never repeat a completed send, publish, delete or upload. Do not perform later Agent steps.')
        prompt = _exploration_prompt(SimpleNamespace(goal=goal, observation=observation, attempts=attempts))
        prompt += ('\nUse browser primitives only for this step. Do not delegate to another Agent. '
                   'No executable scripts, selectors, or caller-supplied IR. Existing agent.call steps are executed separately by the durable runtime.')
        payload = dict(model=model.id, max_tokens=2400, messages=[
            {'role': 'system', 'content': 'Plan one browser action or evaluate completion. Return JSON only.'},
            {'role': 'user', 'content': prompt}])
        budget = JsonRepairBudget()
        while True:
            raw = await invocations.invoke_background_json(model.id, 'chat_completions', payload,
                request_id='browser-plan-' + uuid.uuid4().hex, context=context)
            if raw.status_code >= 400:
                raise RuntimeError('Task model invocation failed')
            try:
                decision = parse_model_json(json.loads(bytes(raw.body)))
                if not isinstance(decision, dict):
                    raise ValueError('Planner must return an object')
                kind = decision.get('decision')
                if kind == 'complete':
                    validate_completion(step, attempts)
                    return decision
                if kind == 'needs_user':
                    if decision.get('assistance_kind') not in ('authentication', 'captcha', 'sensitive_input', 'legal_consent', 'missing_information', 'unsupported_interaction'):
                        raise ValueError('Assistance must identify an actual user blocker')
                    return decision
                if kind != 'act' or not isinstance(decision.get('step'), dict):
                    raise ValueError('Planner must return act with one step, complete, or needs_user')
                action = decision['step']
                if action.get('operation') not in ('open', 'page_access', 'inspect', 'extract_list', 'click', 'input', 'hover', 'scroll'):
                    raise ValueError('Unsupported browser primitive')
                source = {'agent_type': 'web', 'site_scope': scopes, 'steps': [{**action,
                    'name': action.get('name') or 'action', 'execution': {'mode': 'compiled'},
                    'on': {'success': 'done', 'failed': 'failed'}}]}
                compiled = compile_source(source)
                if not compiled.valid or len(compiled.ir.get('steps', [])) != 1:
                    raise ValueError('Browser action failed compilation preflight: ' + str(compiled.report))
                action = compiled.ir['steps'][0]
                action['mode'] = 'compiled'
                selected = decision.get('browser_context') or observation['context']
                permitted = {observation['context'], *(item['context'] for item in observation.get('windows', []))}
                if selected not in permitted:
                    raise ValueError('Planner selected an unrelated browser context')
                action['browser_context'] = selected
                decision['compiled_step'] = action
                return decision
            except (ValueError, TypeError, KeyError) as error:
                if not budget.consume(error, model=model.id, stage='parse'):
                    raise
                payload = repair_json_request(payload, bytes(raw.body).decode(), error)
