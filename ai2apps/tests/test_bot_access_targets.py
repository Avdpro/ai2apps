"""Default App policy and independent component grant identities."""
import json
from dataclasses import replace
import pytest
from ai2apps.messager.bots import install
from ai2apps.messager.app_access import DEFAULT_APPS
from ai2apps.services.capability_routing import CapabilityProvider
from test_app_interactions import runtime


def create(runtime):
    install(runtime)
    bot=runtime.messager_bots.create('local','Defaults','Help')
    return bot,runtime.messager_bot_app_access


def test_new_bot_has_only_four_defaults_and_removal_never_reseeds(runtime):
    bot,access=create(runtime)
    assert {k for k,v in access.current('local',bot['id'])[1].items() if v['enabled']}==set(DEFAULT_APPS)
    selected=[x for x in access.catalog('local',bot['id'])['items'] if x['selected']]
    assert {x['app_id'] for x in selected}==set(DEFAULT_APPS)
    assert all(x['kind']=='app' for x in selected)
    c=access.catalog('local',bot['id']);access.save('local',bot['id'],c['revision'],c['review_hash'],[])
    access.ensure('local',bot['id'])
    assert not access.current('local',bot['id'])[1]
    assert not any(x['selected'] for x in access.catalog('local',bot['id'])['items'])
    with pytest.raises(PermissionError):access.catalog('foreign',bot['id'])


def mini_providers(runtime):
    app='ai2apps.gallery'
    row=runtime.extension_manager._active_app_definition(app);manifest=json.loads(row['manifest_json']);manifest['mini_apps']=[{'id':'fixture.one','name':'First component','icon':'sparkles','placements':[]},{'id':'fixture.two','name':'Second component','icon':'music','placements':[]}]
    with runtime.database.transaction(write=True) as db:db.execute('UPDATE app_definitions SET manifest_json=? WHERE id=?',(json.dumps(manifest),row['id']))
    base=next(p for p in runtime.app_capability_router.providers.values() if p.app_id=='ai2apps.todo' and p.mini_app_id is None and runtime.messager_bot_app_access.classification(p)==('read',False))
    first=replace(base,id='component-a',app_id=app,mini_app_id='fixture.one')
    second=replace(base,id='component-b',app_id=app,mini_app_id='fixture.two')
    runtime.app_capability_router.register(first);runtime.app_capability_router.register(second)
    return first,second


def test_parent_app_does_not_grant_mini_apps_and_siblings_are_independent(runtime):
    bot,access=create(runtime);first,second=mini_providers(runtime)
    assert not access.granted('local',bot['id'],first)
    c=access.catalog('local',bot['id']);minis=[p for p in c['items'] if p['kind']=='mini-app']
    assert {p['name'] for p in minis if p['owner_app_id']=='ai2apps.gallery'}=={'First component','Second component'}
    choices=[{'app_id':p['app_id'],'enabled':p['enabled']} for p in c['items'] if p['selected']]
    choices.append({'app_id':access.target(first),'enabled':True})
    access.save('local',bot['id'],c['revision'],c['review_hash'],choices)
    assert access.granted('local',bot['id'],first)
    assert not access.granted('local',bot['id'],second)
    before=runtime.messager_bot_permissions.capture('local',{'bot_id':bot['id']},'hook')
    c=access.catalog('local',bot['id']);access.save('local',bot['id'],c['revision'],c['review_hash'],[p for p in choices if p['app_id']!=access.target(first)])
    assert not access.granted('local',bot['id'],first)
    with pytest.raises(PermissionError):runtime.messager_bot_permissions.validate('local',{'bot_id':bot['id']},before,None,{})


def test_removed_mini_app_keeps_readable_revocation_entry_but_no_authority(runtime):
    bot,access=create(runtime);first,_=mini_providers(runtime)
    c=access.catalog('local',bot['id']);access.save('local',bot['id'],c['revision'],c['review_hash'],[{'app_id':access.target(first),'enabled':True}])
    row=runtime.extension_manager._active_app_definition('ai2apps.gallery');manifest=json.loads(row['manifest_json']);manifest['mini_apps']=[]
    with runtime.database.transaction(write=True) as db:db.execute('UPDATE app_definitions SET manifest_json=? WHERE id=?',(json.dumps(manifest),row['id']))
    entry=next(x for x in access.catalog('local',bot['id'])['items'] if x['app_id']==access.target(first))
    assert entry['kind']=='mini-app' and entry['name']=='First component' and not entry['available']
    assert not access.granted('local',bot['id'],first)
    assert first.id not in {p.id for p in access.exported('local',bot['id'])}
    c=access.catalog('local',bot['id']);access.save('local',bot['id'],c['revision'],c['review_hash'],[])
    assert not any(x['selected'] for x in access.catalog('local',bot['id'])['items'])


def test_native_component_metadata_resolves_without_manifest_but_never_replaces_package_manifest(runtime):
    bot,access=create(runtime)
    base=next(p for p in runtime.app_capability_router.providers.values() if p.app_id=='ai2apps.todo' and p.mini_app_id is None)
    provider=replace(base,id='arbitrary.native',mini_app_id='arbitrary.native.component',component_identity={'id':'arbitrary.native.component','name':{'zh':'本地组件','en':'Native component'},'icon':'pencil'})
    runtime.app_capability_router.register(provider)
    identity=access.identity(access.target(provider));assert identity['name']=='Native component' and identity['kind']=='mini-app' and identity['icon']=='pencil'
    assert identity['names']['zh']=='本地组件'
    assert not access.granted('local',bot['id'],provider)
    row=runtime.extension_manager._active_app_definition(provider.app_id)
    with runtime.database.transaction(write=True) as db:db.execute("UPDATE app_definitions SET source='installed' WHERE id=?",(row['id'],))
    assert access.identity(access.target(provider)) is None


def test_builtin_image_provider_has_its_owner_component_identity(runtime):
    bot,access=create(runtime)
    provider=runtime.app_capability_router.providers['ai2apps.images.generate']
    identity=access.identity(access.target(provider))
    assert identity['mini_app_id']=='ai2apps.imagine.text-to-image'
    assert identity['name']=='Text to image' and identity['icon']=='image'

def test_image_usage_is_routine_write_but_still_mutating_and_requires_access(runtime):
    from ai2apps.agents.tool_recovery import has_mutating_effects
    bot,access=create(runtime)
    providers=[p for p in runtime.app_capability_router.providers.values() if p.app_id=='ai2apps.imagine-studio' and p.capability.startswith('image.')]
    assert providers
    for provider in providers:
        tool=runtime.services.get_tool(provider.capability)
        assert 'ai.usage' in tool.effects and 'billing' not in tool.effects
        assert access.classification(provider)==('write',False)
        assert has_mutating_effects(tool.effects)
        assert not access.granted('local',bot['id'],provider)
