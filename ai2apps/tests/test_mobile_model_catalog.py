from ai2apps.web.mobile_model_catalog import merge_catalog


def test_safe_projection_merges_managed_and_aliases_without_private_settings():
    data = merge_catalog([{'id':'alias','model_type':'llm'}, {'id':'alias','model_type':'llm'}], [
        {'id':'stable','settings':{'model_alias':'alias','api_key':'SECRET'},'model_path':'private', 'is_favorite':True,'model_type':'llm','identity':{'displayName':'Friendly'}},
        {'id':'fusion/team','source_type':'fusion','fusion_config':{'secret':'private'}},
        {'id':'cloud/new','source_type':'cloud'},
        {'id':'unlisted-local','source_type':'local'},
    ])
    assert [m['id'] for m in data] == ['stable','fusion/team','cloud/new']
    assert data[0]['display_name'] == 'Friendly'
    assert data[0]['is_favorite'] is True
    assert 'SECRET' not in str(data) and 'private' not in str(data)
