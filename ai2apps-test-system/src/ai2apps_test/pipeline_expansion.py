"""Resolve Pipeline references once, before any Run side effects."""
from copy import deepcopy
from hashlib import sha256
import json

from .catalog_validation import require_valid, validate_pipeline


def expand_pipeline(pipeline, store, case_ids):
    steps, sources = [], {}

    def visit(value, stack, path, enabled):
        identity = value['id']
        if identity in stack:
            raise ValueError('Pipeline reference cycle: ' + ' -> '.join((*stack, identity)))
        if len(stack) >= 16:
            raise ValueError('Pipeline nesting exceeds 16 levels')
        require_valid(validate_pipeline(value, case_ids))
        if stack and not value.get('enabled', True):
            raise ValueError('Referenced pipeline is disabled: ' + identity)
        sources[identity] = deepcopy(value)
        for original in value['steps']:
            chain = path + [original['id']]
            active = enabled and original.get('enabled', True)
            if original.get('type') == 'action' and original.get('action') == 'include-pipeline':
                target = original['pipelineId']
                try:
                    child = sources.get(target) or store.get('pipelines', target)
                except (KeyError, FileNotFoundError) as error:
                    raise ValueError('Referenced pipeline not found: ' + target) from error
                visit(child, (*stack, identity), chain, active)
                continue
            if len(steps) >= 1000:
                raise ValueError('Expanded pipeline exceeds 1000 steps')
            step = deepcopy(original)
            if path:
                step['id'] = 'include-' + sha256(json.dumps(chain).encode()).hexdigest()
            if not active:
                step['enabled'] = False
                if step['type'] == 'case':
                    step['executionMode'] = 'skip'
            step['_origin'] = {'sourcePipelineId': identity,
                               'sourcePipelineName': value['name'],
                               'sourcePipelineStepId': original['id'],
                               'pipelineStepPath': chain}
            steps.append(step)

    visit(pipeline, (), [], True)
    return steps, sources
