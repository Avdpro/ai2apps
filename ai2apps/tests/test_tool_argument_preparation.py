from ai2apps.agents.tool_arguments import prepare_arguments
from ai2apps.agents.tool_recovery import recoverable


def test_extra_fields_are_schema_driven_and_keep_original():
    schema={'type':'object','properties':{'prompt':{'type':'string'}},'required':['prompt'],'additionalProperties':False}
    original={'prompt':'keep me','request_id':'one','request_key':'two'}
    fixed,error=prepare_arguments(schema,original)
    assert fixed==original and error is not None
    assert original['request_key']=='two'
    fixed,error=prepare_arguments(schema,{'prompt':'keep me','model':'explicit-user-choice'})
    assert error is not None and fixed['model']=='explicit-user-choice'


def test_declared_open_and_conditional_fields_preserved():
    for schema in [
        {'type':'object','properties':{'request_id':{'type':'string'}},'additionalProperties':False},
        {'type':'object'},
        {'allOf':[{'type':'object','properties':{'request_id':{'type':'string'}},'required':['request_id'],'additionalProperties':False}]},
    ]:
        fixed,error=prepare_arguments(schema,{'request_id':'actual-business-id'})
        assert fixed['request_id']=='actual-business-id'


def test_schema_errors_recover_before_effectful_execution_with_limit():
    schema={'type':'object','properties':{'size':{'enum':['1024x1024']}},'required':['size'],'additionalProperties':False}
    for args in [{},{'size':'999x999'}]:
        fixed,error=prepare_arguments(schema,args)
        assert error and fixed==args
    assert recoverable('invalid_tool_arguments',effects=['billing'],prior_errors=0,enabled=True,preflight=True)
    assert not recoverable('invalid_tool_arguments',effects=['billing'],prior_errors=3,enabled=True,preflight=True)
    assert not recoverable('provider_error',effects=['billing'],prior_errors=0,enabled=True)


def test_group_photo_schema_accepts_metadata_repair():
    from ai2apps.images.mini_parameters import schema
    fixed,error=prepare_arguments(schema("ai2apps.imagine.group-photo"), {"person_artifact_ids":["art_a","art_b"],"background":"park","request_id":"call-1"})
    assert error is not None and fixed["request_id"]=="call-1"


def test_nested_arrays_refs_and_patterns():
    schema={'type':'object','properties':{'items':{'type':'array','items':{'$ref':'#/$defs/item'}}},
            'additionalProperties':False,'$defs':{'item':{'type':'object','properties':{'name':{'type':'string'}},
            'patternProperties':{'^x_':{'type':'integer'}},'additionalProperties':False}}}
    args={'items':[{'name':'A','x_option':2,'arbitrary_extra':3}], 'anything':True}
    fixed,error=prepare_arguments(schema,args)
    assert error is not None and fixed==args
    assert args['items'][0]['arbitrary_extra']==3
    fixed,error=prepare_arguments(schema,{'items':[{'name':3,'x_option':'wrong'}]})
    assert error and fixed['items'][0]['x_option']=='wrong'


def test_ambiguous_union_is_not_guessed():
    schema={'oneOf':[{'type':'object','properties':{'a':{'type':'string'}},'required':['a'],'additionalProperties':False},
                     {'type':'object','properties':{'b':{'type':'string'}},'required':['b'],'additionalProperties':False}]}
    args={'a':'one','b':'two'}
    fixed,error=prepare_arguments(schema,args)
    assert error and fixed==args
