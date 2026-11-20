import time
from types import SimpleNamespace
import pytest
from ai2apps.cloud_defaults import validate_policy, CACHE_SECONDS
from ai2apps.model_manager import ModelManagerStore
from ai2apps.images.service import _default_image_model
from ai2apps.secrets import MemorySecretBackend


def policy(chat='vendor/chat', image='vendor/picture'):
    return {'schema':'ai2apps.ai-defaults/v1','revision':'fixture',
            'apiDefault':{'modelId':chat,'displayName':'Chat'} if chat else None,
            'imageApiDefault':{'modelId':image,'displayName':'Picture'} if image else None}


def test_image_default_tracks_cloud_without_pinning_or_using_chat(tmp_path):
    store=ModelManagerStore(tmp_path,secret_backend=MemorySecretBackend())
    store.put_cloud_default_policy(policy(),fetched_at=time.time())
    assert _default_image_model(store)=='cloud/ai2apps/vendor/picture'
    assert store.resolve_default_model('work_standard')=='cloud/ai2apps/vendor/chat'
    assert not store.defaults_path.exists()
    store.put_cloud_default_policy(policy(image='other/replacement'),fetched_at=time.time())
    assert _default_image_model(store)=='cloud/ai2apps/other/replacement'
    store.put_default_models({'image_generation':'my-explicit-model'})
    before=store.defaults_path.read_bytes()
    store.put_cloud_default_policy(policy(image='third/model'),fetched_at=time.time())
    assert _default_image_model(store)=='my-explicit-model' and store.defaults_path.read_bytes()==before


def test_null_old_cloud_stale_origin_and_privacy_have_no_drawing_fallback(tmp_path):
    store=ModelManagerStore(tmp_path,secret_backend=MemorySecretBackend())
    assert _default_image_model(store)==''
    assert validate_policy(policy(chat=None))['imageApiDefault']['modelId']=='vendor/picture'
    old=policy();old.pop('imageApiDefault');store.put_cloud_default_policy(old,fetched_at=time.time())
    assert _default_image_model(store)==''
    store.put_cloud_default_policy(policy(image=None),fetched_at=time.time())
    assert _default_image_model(store)==''
    store.put_cloud_default_policy(policy(),fetched_at=time.time()-CACHE_SECONDS-1)
    assert _default_image_model(store)==''
    store.put_cloud_default_policy(policy(),fetched_at=time.time())
    assert store.resolve_default_model('image_generation',profile='privacy') is None
    store.cloud_defaults_origin='https://different.example'
    assert _default_image_model(store)==''


@pytest.mark.parametrize('value',[{},'vendor/model',{'modelId':'cloud/vendor/model','displayName':'x'}, {'modelId':'../model','displayName':'x'}, {'modelId':'vendor/model','displayName':''}])
def test_invalid_image_defaults_are_rejected(value):
    with pytest.raises(ValueError):validate_policy({**policy(),'imageApiDefault':value})


@pytest.mark.asyncio
async def test_invalid_image_refresh_preserves_cache_and_null_clears_only_image(tmp_path):
    import httpx
    from ai2apps.cloud_defaults import refresh_cloud_defaults
    store=ModelManagerStore(tmp_path,secret_backend=MemorySecretBackend())
    store.put_cloud_default_policy(policy(),fetched_at=time.time());before=store.cloud_defaults_path.read_bytes()
    async def invalid(*args):return httpx.Response(200,json={**policy(),'imageApiDefault':{'modelId':'../bad','displayName':'Bad'}})
    assert not await refresh_cloud_defaults(store,SimpleNamespace(request=invalid))
    assert store.cloud_defaults_path.read_bytes()==before
    async def clear(*args):return httpx.Response(200,json=policy(image=None))
    assert await refresh_cloud_defaults(store,SimpleNamespace(request=clear))
    assert _default_image_model(store)=='' and store.resolve_default_model('work_standard')=='cloud/ai2apps/vendor/chat'


@pytest.mark.asyncio
async def test_bot_memory_and_real_cloud_image_default_priority_and_fallback(tmp_path,monkeypatch):
    from ai2apps.model_preferences import scope
    from ai2apps.images.parameters import from_options,describe
    store=ModelManagerStore(tmp_path,secret_backend=MemorySecretBackend())
    store.put_cloud_default_policy(policy(),fetched_at=time.time())
    runtime=SimpleNamespace(model_manager=store,privacy_mode=False)
    rows=[from_options(id,id,{}) for id in ('remembered','explicit','cloud/ai2apps/vendor/picture','cloud/ai2apps/other/new')]
    async def models(*args):return rows,[]
    monkeypatch.setattr('ai2apps.images.parameters.models',models)
    snapshot={'schema':'ai2apps.model-preferences/v1','routes':[
        {'purpose':'image_generation','profile':'normal','model':'remembered','memory_id':'memory-1','revision':1,'bot_id':'bot'},
        {'purpose':'work_standard','profile':'normal','model':'chat-memory','memory_id':'memory-2','revision':1,'bot_id':'bot'}]}
    with scope(snapshot):
        assert (await describe(runtime,None))['model']=='remembered'
        assert (await describe(runtime,None,model_id='explicit'))['model']=='explicit'
        assert store.resolve_default_model('work_standard')=='chat-memory'
        store.put_cloud_default_policy(policy(image='other/new'),fetched_at=time.time())
        assert (await describe(runtime,None))['model']=='remembered'
        rows[:]=[r for r in rows if r['id']!='remembered']
        fallback=await describe(runtime,None)
        assert fallback['model']=='cloud/ai2apps/other/new'
        assert fallback['model_selection']['fallback_reason']=='preferred_model_unavailable_or_incompatible'
        runtime.privacy_mode=True
        private=await describe(runtime,None)
        assert private['selection_required'] and private['model'] is None
    runtime.privacy_mode=False
    assert (await describe(runtime,None))['model']=='cloud/ai2apps/other/new'
