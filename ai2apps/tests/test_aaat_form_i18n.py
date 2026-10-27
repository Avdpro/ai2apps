"""Owner form presentation coverage; all descriptors use isolated runtime data."""
import pytest
from ai2apps.identity import RequestPrincipal
from ai2apps.agents.parameter_forms import present_fields
from test_app_interactions import runtime


def test_presentation_preserves_values_and_plain_legacy_declarations():
    fields=[{'key':'choice','type':'select','label':'Legacy','options':[{'value':'one','label':'one'}]}]
    result=present_fields(fields,{'choice':{'zh':'选择','en':'Choice'}},{'choice':{'one':{'zh':'一','en':'One'}}})
    assert result[0]['key']=='choice' and result[0]['options'][0]['value']=='one'
    assert result[0]['label']=={'zh':'选择','en':'Choice'}
    assert fields[0]['label']=='Legacy' and fields[0]['options'][0]['label']=='one'


@pytest.mark.asyncio
async def test_installed_first_party_provider_fields_have_owner_translations(runtime,monkeypatch):
    import json
    from pathlib import Path
    original=runtime.extension_manager._studio_mini_app_definition
    declarations={}
    for package in ('ai2apps-shopping-pro','ai2apps-search-all','ai2apps-web-reader'):
        data=json.loads((Path(__file__).resolve().parents[2]/'packages'/package/'app.yaml').read_text())
        for mini in data['mini_apps']:declarations[mini['id']]=mini
    monkeypatch.setattr(runtime.extension_manager,'_studio_mini_app_definition',lambda app,mini,principal:(None,declarations[mini]) if mini in declarations else original(app,mini,principal))
    checked=[]
    for provider in runtime.app_capability_router.providers.values():
        if not provider.describe:continue
        assert isinstance(provider.display_name,dict) and {'zh','en'}<=provider.display_name.keys(),provider.id
        assert isinstance(provider.summary,dict) and {'zh','en'}<=provider.summary.keys(),provider.id
        descriptor=await provider.describe(RequestPrincipal.legacy_local())
        for field in descriptor.get('fields',[]):
            assert isinstance(field['label'],dict) and all(field['label'].get(k) for k in ('zh','en')), (provider.id,field)
        checked.append(provider.id)
    assert any('shopping' in p for p in checked)
    assert any('todo' in p for p in checked)
    assert any('knowledge' in p for p in checked)
    assert any('imagine' in p for p in checked)
