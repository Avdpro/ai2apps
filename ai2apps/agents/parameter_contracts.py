"""Exact read-only Provider input contracts; references never confer authority."""
from copy import deepcopy
import hashlib
import json
from jsonschema import Draft202012Validator

PREFIX = "Trusted selected parameter contracts: "

async def resolve_contract(provider, principal, values=None):
    values=values or {}
    descriptor=await provider.describe(principal,values.get('model'))
    field=descriptor.get('model_field')
    if isinstance(field,str) and field!='model' and values.get(field):
        descriptor=await provider.describe(principal,values[field])
    schema=descriptor.get('effective_schema')
    if not isinstance(schema,dict):raise ValueError('Provider has not supplied a resolved parameter schema')
    Draft202012Validator.check_schema(schema)
    contract={'provider':provider.id,'provider_version':provider.version,'schema':deepcopy(schema),
        'fields':deepcopy(descriptor.get('fields',[])),
        'models':deepcopy(descriptor.get('models',[])),
        'constraints':deepcopy(descriptor.get('constraints',{})),
        'model_field':descriptor.get('model_field','model'),
        'configuration_required':bool(descriptor.get('configuration_required')),
        'selection_required':bool(descriptor.get('selection_required')),
        'install':deepcopy(descriptor.get('install')),
        'collection_tool':'app.collect_parameters'}
    contract['contract_version']=hashlib.sha256(json.dumps(contract,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return contract


def problems(schema,values,*,partial=False):
    # Partial form drafts may omit required inputs, but may never rename/drop them.
    result=[]
    for error in Draft202012Validator(schema).iter_errors(values):
        if partial and error.validator not in ('additionalProperties','unevaluatedProperties','type'):continue
        result.append({'validator':error.validator,'path':list(error.absolute_path),
            'schema_path':list(error.absolute_schema_path)})
        if len(result)==32:break
    return result


def rejection(contract,values,*,partial=False,required=False):
    errors=problems(contract['schema'],values,partial=partial)
    if not errors and not required:return None
    return json.dumps({'code':'parameter_contract_required' if required else 'parameter_contract_mismatch',
        'submitted':False,'side_effects':False,'original_values_preserved':True,
        'errors':errors,'parameter_contract':contract,
        'message':'No operation or form was submitted. This receipt supplies the exact current contract; do not read it again unless it changes. Correct and reissue the original call using declared names and preserved known values. For missing inputs or an empty/unready model list, use app.collect_parameters; its owner-bound form offers configuration when declared. Do not substitute app.interact unless an actual handoff is registered. Never invent IDs or repeat completed operations.'},ensure_ascii=False)


def reviewed_request(request,contract):
    for message in request.get("messages",[]):
        content=message.get("content")
        if message.get("role")=="system" and isinstance(content,str) and content.startswith(PREFIX):
            try:items=json.loads(content[len(PREFIX):])
            except (ValueError,TypeError):continue
            if any(isinstance(item,dict) and item.get("contract_version")==contract["contract_version"] for item in items):return True
    return False


def reviewed(steps,contract):
    fingerprint=contract['contract_version']
    for step in steps:
        if step.kind!='tool':continue
        if step.status.value=='completed' and step.tool_name=='app.describe' and isinstance(step.output,dict):
            if any(f.get('contract_version')==fingerprint for f in step.output.get('forms',[]) if isinstance(f,dict)):return True
        error=getattr(step,'error',None) or {}
        if error.get('code') in ('parameter_contract_required','parameter_contract_mismatch','invalid_app_interaction'):
            observed=error.get('parameter_contract')
            if not isinstance(observed,dict):
                try:observed=json.loads(error.get('message','')).get('parameter_contract',{})
                except (ValueError,TypeError):continue
            if observed.get('contract_version')==fingerprint:return True
    return False
