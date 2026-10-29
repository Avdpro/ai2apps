"""Strict deterministic validation; never silently discard model arguments."""
from copy import deepcopy
import json
from jsonschema import Draft202012Validator

def prepare_arguments(schema, arguments):
    values=deepcopy(arguments)
    errors=list(Draft202012Validator(schema).iter_errors(values))
    if not errors:return values,None
    # Do not echo argument values (which may contain credentials or private text).
    details=[{'validator':e.validator,'path':list(e.absolute_path),'schema_path':list(e.absolute_schema_path)} for e in errors[:32]]
    return values,json.dumps({'code':'parameter_contract_mismatch','submitted':False,'side_effects':False,
        'original_values_preserved':True,'errors':details,'parameter_contract':{'schema':schema},
        'message':'Tool has not executed. Correct the arguments using the exact schema; do not drop requested constraints, invent IDs or repeat completed operations.'},ensure_ascii=False)
