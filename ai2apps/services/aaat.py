"""Versioned AaAT declaration/result context. Only trusted registrations supply policy."""
from __future__ import annotations
from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Callable
from jsonschema import Draft202012Validator

DECLARATION_SCHEMA = {
    'type':'object','additionalProperties':False,'required':['schema','instructions'],
    'properties':{
        'schema':{'const':'ai2apps.aaat-declaration/v1'},
        'instructions':{'type':'array','maxItems':16,'items':{'type':'string','minLength':1,'maxLength':1500}},
        'entities':{'type':'array','maxItems':16,'items':{'type':'object','additionalProperties':False,'required':['type','id_field','label_field'],
            'properties':{k:{'type':'string','maxLength':128} for k in ('type','id_field','label_field','parent_field')}}},
        'workflows':{'type':'array','maxItems':16,'items':{'type':'object','additionalProperties':False,'required':['intent','capabilities'],
            'properties':{'intent':{'type':'string','maxLength':500},'capabilities':{'type':'array','maxItems':16,'items':{'type':'string','maxLength':256}}}}},
        'result_semantics':{'type':'object','maxProperties':24,'additionalProperties':{'type':'string','maxLength':1000}},
    }}
RESULT_SCHEMA = {'type':'object','additionalProperties':False,'required':['schema','status','data_trust'],
    'properties':{
        'schema':{'const':'ai2apps.aaat-result-context/v1'},
        'status':{'enum':['resolved','ambiguous','not_found','complete','partial']},
        'data_trust':{'const':'untrusted'},
        'scope':{'type':'object'},'coverage':{'type':'object'},
        'next_actions':{'type':'array','maxItems':8,'items':{'type':'object','additionalProperties':False,
            'required':['capability','arguments'],'properties':{'capability':{'type':'string','maxLength':256},'arguments':{'type':'object'}}}},
    }}


def validate_declaration(value):
    if value is None:return None
    Draft202012Validator(DECLARATION_SCHEMA).validate(value)
    if len(json.dumps(value,ensure_ascii=False).encode())>8192:raise ValueError('AaAT declaration exceeds 8 KiB')
    return deepcopy(value)


def validate_result(value, provider, providers):
    Draft202012Validator(RESULT_SCHEMA).validate(value)
    if len(json.dumps(value,ensure_ascii=False).encode())>16384:raise ValueError('AaAT result context exceeds 16 KiB')
    allowed={p.capability for p in providers.values() if (p.app_id,p.mini_app_id)==(provider.app_id,provider.mini_app_id)}
    if any(a['capability'] not in allowed for a in value.get('next_actions',[])):
        raise ValueError('AaAT next action is outside the declaring App/Mini-App')


@dataclass(frozen=True)
class AgentResultPolicy:
    """Trusted App hooks; callbacks are never accepted from model/result JSON."""
    id: str
    instruction: Callable
    finalize: Callable
    preview: Callable | None = None
    capabilities: tuple[str, ...] = ()


class InvocationPolicyError(ValueError):
    def __init__(self,code,message):
        self.code=code
        super().__init__(message)


def principal_for(runtime, context):
    from ai2apps.identity import IdentityRepository, RequestPrincipal
    from ai2apps.services import ToolProviderError
    principal=(RequestPrincipal.legacy_local() if context.actor_user_id=='local'
        else IdentityRepository(runtime.database).local_principal_for(context.actor_user_id))
    if principal.installation_id!=context.installation_id:raise ToolProviderError('Installation mismatch')
    # Tool context is host-owned. Restore its persisted Session scope before
    # provider preparation and execution, not only inside a downstream executor.
    if context.session_id and principal.actor_user_id != 'local':
        from ai2apps.identity import workload_session_principal
        principal = workload_session_principal(runtime.database, principal, context.session_id)
    return principal


# Data-only result views: no business identity, executable templates or model hooks.
VIEW_SCHEMA = {'type':'object','additionalProperties':False,'required':['schema','id','layout','title','items'],
 'properties':{'schema':{'const':'ai2apps.aaat-view/v1'},'id':{'type':'string','minLength':1,'maxLength':128},
 'layout':{'enum':['table','cards']},'title':{'type':'string','maxLength':300},'summary':{'type':'string','maxLength':1500},
 'columns':{'type':'array','maxItems':8,'items':{'type':'object','additionalProperties':False,'required':['key','label'],
 'properties':{'key':{'type':'string','maxLength':80},'label':{'type':'string','maxLength':100}}}},
 'items':{'type':'array','maxItems':30,'items':{'type':'object','additionalProperties':False,'required':['id','title'],
 'properties':{'id':{'type':'string','maxLength':256},'title':{'type':'string','maxLength':500},'summary':{'type':'string','maxLength':1500},
 'url':{'type':'string','maxLength':4096},'image':{'type':'object','additionalProperties':False,'required':['url'],
 'properties':{'url':{'type':'string','maxLength':4096},'alt':{'type':'string','maxLength':500}}},
 'fields':{'type':'object','maxProperties':8,'additionalProperties':{'type':'string','maxLength':500}}}}}}}


def validate_view(value):
    from urllib.parse import urlsplit
    Draft202012Validator(VIEW_SCHEMA).validate(value)
    if len(json.dumps(value,ensure_ascii=False).encode())>65536:raise ValueError('AaAT view exceeds 64 KiB')
    keys=[c['key'] for c in value.get('columns',[])]
    if len(set(keys))!=len(keys):raise ValueError('Duplicate AaAT view column')
    if value['layout']=='table' and not keys:raise ValueError('Table requires columns')
    ids=[i['id'] for i in value['items']]
    if len(set(ids))!=len(ids):raise ValueError('Duplicate AaAT view item')
    for item in value['items']:
        if set(item.get('fields',{}))-set(keys):raise ValueError('Undeclared AaAT view field')
        for url in [item.get('url'),(item.get('image') or {}).get('url')]:
            if not url:continue
            if any(ord(c)<33 or c=='\\' for c in url):raise ValueError('Invalid AaAT view URL')
            parsed=urlsplit(url)
            local=url.startswith('/') and not url.startswith('//') and not parsed.netloc
            if not local and (parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password):raise ValueError('Unsafe AaAT view URL')
    return deepcopy(value)
