from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest
from ai2apps.shared_model_cache import (
    list_shared_model_references,
    publish_shared_model_reference,
)


@pytest.mark.asyncio
async def test_delete_committed_model_releases_current_instance_reference(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    import omlx.admin.routes as routes_module
    from omlx.admin.routes import delete_hf_model

    model_root = tmp_path / "shared" / "model-weights"
    hub = model_root / "huggingface" / "hub"
    model_dir = tmp_path / "models"
    model_path = model_dir / "owner" / "converted"
    model_path.mkdir(parents=True)
    (model_path / "config.json").write_text("{}")
    revision = "a" * 40
    (model_path / "ai2apps-model.json").write_text(
        json.dumps(
            {
                "format": "ai2apps-cache-moe-model",
                "version": 2,
                "source": {
                    "provider": "huggingface",
                    "repo_id": "owner/converted",
                    "revision": revision,
                },
            }
        )
    )
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_MODE", "shared")
    monkeypatch.setenv("AI2APPS_INSTANCE_ID", "app-one")
    monkeypatch.setenv("AI2APPS_MODEL_CACHE_ROOT", str(model_root))
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    publish_shared_model_reference(
        hub,
        instance_id="app-one",
        repo_id="owner/converted",
        revision=revision,
    )
    publish_shared_model_reference(
        hub,
        instance_id="app-two",
        repo_id="owner/converted",
        revision=revision,
    )

    settings = MagicMock()
    settings.model.get_model_dirs.return_value = [model_dir]
    settings.get_effective_model_dirs.return_value = [model_dir]
    pool = MagicMock()
    pool.get_loaded_model_ids.return_value = []
    pool._entries = {}
    manager = MagicMock()
    manager.get_pinned_model_ids.return_value = []
    monkeypatch.setattr(routes_module, "_get_global_settings", lambda: settings)
    monkeypatch.setattr(routes_module, "_get_engine_pool", lambda: pool)
    monkeypatch.setattr(routes_module, "_get_settings_manager", lambda: manager)

    result = await delete_hf_model(model_name="converted", is_admin=True)

    assert result["success"] is True
    assert not model_path.exists()
    references = list_shared_model_references(hub)
    assert [(item.instance_id, item.repo_id) for item in references] == [
        ("app-two", "owner/converted")
    ]
