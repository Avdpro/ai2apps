"""Selection-scoped trusted declarations, independent of App business semantics."""
from __future__ import annotations
import json

PREFIX = 'Trusted selected AaAT declarations: '
REVIEW_CODE = 'tool_declaration_required'


def selected_capabilities(steps, aliases, interactions=()):
    selected = set()
    def add(value):
        if isinstance(value,str):selected.add(value)
    for step in steps:
        if step.kind == 'tool':
            selected.add(step.tool_name)
            arguments = step.input or {}
            name = step.tool_name
            if name in {'app.describe', 'app.collect_parameters', 'app.interact'}:
                add(arguments.get('capability'))
                if name == 'app.describe' and arguments.get('capability') and step.status.value == 'completed' and isinstance(step.output,dict):
                    for item in [*step.output.get('forms',[]),*step.output.get('providers',[])]:
                        if isinstance(item,dict):add(item.get('capability'))
        elif step.kind == 'model' and isinstance(step.output, dict):
            for choice in step.output.get('choices', []) or []:
                if not isinstance(choice,dict) or not isinstance(choice.get('message'),dict):continue
                for call in choice['message'].get('tool_calls', []) or []:
                    if not isinstance(call,dict) or not isinstance(call.get('function'),dict):continue
                    function = call['function']
                    alias=function.get('name')
                    tool = aliases.get(alias) if isinstance(alias,str) else None
                    if tool is None:
                        continue
                    selected.add(tool.qualified_name)
                    arguments = function.get('arguments', {})
                    try:
                        if isinstance(arguments, str):arguments = json.loads(arguments)
                    except (ValueError, TypeError):continue
                    if tool.qualified_name in {'app.describe','app.collect_parameters','app.interact'} and isinstance(arguments,dict):
                        add(arguments.get('capability'))
    for item in interactions:
        add((item.request or {}).get('capability'))
        result=(item.response or {}).get('result',{})
        if isinstance(result,dict):add(result.get('capability'))
    return {value for value in selected if isinstance(value,str)}


def declarations_for(router, tools, scope, selected):
    """Only registered, enabled targets; never trust text from a Tool result."""
    from .parameter_forms import FORMS
    from .app_interactions import CAPABILITIES
    entries = router.agent_contexts(tools,scope.actor_user_id,scope.installation_id,
        selected_capabilities=selected, session_id=scope.session_id)
    projected={provider['id'] for entry in entries for provider in entry['providers']}
    available={tool.qualified_name for tool in tools}
    disabled=router.disabled(scope.actor_user_id,scope.installation_id)
    for descriptor in (*FORMS.values(),*CAPABILITIES.values()):
        capability=getattr(descriptor,'capability',None) or descriptor.key
        if capability not in selected or not descriptor.agent_context or descriptor.key in disabled:
            continue
        if descriptor.key in projected:continue  # already projected with provider version
        control='app.collect_parameters' if descriptor.key in FORMS else 'app.interact'
        if control not in available:continue
        entries.append({'app_id':descriptor.app_id,'mini_app_id':descriptor.mini_app_id,
            'trust':'trusted_app_declaration','declaration':descriptor.agent_context,
            'providers':[{'id':descriptor.key,'capability':capability,'version':str(getattr(descriptor,'provider_version',None) or descriptor.version)}]})
    return entries


def reviewed(request, declarations):
    """The exact current registration must have reached the deciding model call."""
    supplied=[]
    for message in request.get('messages',[]):
        content=message.get('content')
        if message.get('role')=='system' and isinstance(content,str) and content.startswith(PREFIX):
            try:supplied.extend(json.loads(content[len(PREFIX):]))
            except (ValueError,TypeError):continue
    def contains(required):
        for entry in supplied:
            if not isinstance(entry,dict):continue
            if any(entry.get(key)!=required.get(key) for key in ('app_id','mini_app_id','trust','declaration')):continue
            if all(provider in entry.get('providers',[]) for provider in required['providers']):return True
        return False
    return all(contains(entry) for entry in declarations)


def workflow_selection(router, tools, scope, selected):
    """Owner-declared workflow dependencies, bounded to that same App/Mini-App."""
    from .parameter_forms import FORMS
    from .app_interactions import CAPABILITIES
    expanded=set(selected)
    for entry in declarations_for(router,tools,scope,selected):
        owner=(entry['app_id'],entry.get('mini_app_id'))
        permitted={p.capability for p in router.providers.values()
            if (p.app_id,p.mini_app_id)==owner}
        permitted.update((getattr(d,'capability',None) or d.key) for d in (*FORMS.values(),*CAPABILITIES.values())
            if (d.app_id,d.mini_app_id)==owner)
        for workflow in entry['declaration'].get('workflows',[]):
            expanded.update(c for c in workflow.get('capabilities',[]) if c in permitted)
    return expanded
