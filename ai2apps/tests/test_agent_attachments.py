import io

import pytest

from ai2apps.agent_builder.attachments import (
    add_attachment_parameters,
    attachment_context,
    attachment_model_content,
    enrich_file_inputs,
)
from ai2apps.config import PlatformConfig
from ai2apps.core import RepositoryError
from ai2apps.gallery import GalleryRepository
from ai2apps.platform_runtime import PlatformRuntime


def test_attachment_context_is_owner_bound_and_file_parameters_are_durable(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    repository = GalleryRepository(
        runtime.database,
        runtime.config.paths.artifacts_path / "gallery",
        runtime.events,
    )
    asset, _ = repository.import_stream(
        "alice",
        io.BytesIO("参考查询：旧金山".encode()),
        name="reference.txt",
        media_type="text/plain",
        source_app_id="ai2apps.agents",
    )
    context = attachment_context(runtime, "alice", [asset["id"]])
    assert "旧金山" in context[0]["text"]
    assert context[0]["file"]["url"].endswith(asset["id"] + "/content")
    with pytest.raises(RepositoryError):
        attachment_context(runtime, "bob", [asset["id"]])
    source = {"inputs": {"type": "object", "properties": {"query": {"type": "string"}}}}
    add_attachment_parameters(source, context)
    parameter = source["inputs"]["properties"]["file_1"]
    assert parameter["x-ai2apps-file"] is True
    assert parameter["default"]["asset_id"] == asset["id"]
    assert "text" not in parameter["default"]
    assert "query" in source["inputs"]["properties"]
    supplied = {"file_1": {"asset_id": asset["id"], "url": "/forged/path"}}
    enriched = enrich_file_inputs(runtime, "alice", source["inputs"], supplied)
    assert enriched["file_1"]["url"] == context[0]["file"]["url"]
    assert "旧金山" in enriched["file_1"]["text"]
    with pytest.raises(RepositoryError):
        enrich_file_inputs(runtime, "bob", source["inputs"], supplied)
    runtime.stop()


def test_image_model_content_keeps_bytes_out_of_prompt_and_parameters():
    attached = [
        {
            "parameter": "file_1",
            "file": {"url": "/protected/image", "name": "sample.png"},
            "image_data_url": "data:image/png;base64,cGl4ZWxz",
        }
    ]
    content = attachment_model_content("Read reference", attached)
    assert content[0]["type"] == "text"
    assert "base64" not in content[0]["text"]
    assert content[1]["image_url"]["url"] == attached[0]["image_data_url"]
    source = {}
    add_attachment_parameters(source, attached)
    assert "image_data_url" not in source["inputs"]["properties"]["file_1"]["default"]


def test_distillation_persists_file_parameter_and_rejects_foreign_attachment(tmp_path):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from ai2apps.api.router import create_ai2apps_router
    from ai2apps.identity import MemberRole, RequestPrincipal

    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    principal = RequestPrincipal(
        actor_user_id="alice",
        installation_id="test",
        organization_id="test",
        billing_account_id="test",
        role=MemberRole.MEMBER,
        membership_epoch=1,
    )
    app = FastAPI()
    app.include_router(
        create_ai2apps_router(
            runtime_provider=lambda: runtime, principal_provider=lambda: principal
        )
    )
    repository = GalleryRepository(
        runtime.database,
        runtime.config.paths.artifacts_path / "gallery",
        runtime.events,
    )
    asset, _ = repository.import_stream(
        "alice",
        io.BytesIO(b"Reference"),
        name="reference.txt",
        media_type="text/plain",
        source_app_id="ai2apps.agents",
    )
    payload = {
        "name": "Read references",
        "goal": "Extract results",
        "page": {"url": "https://example.com"},
        "attachments": [asset["id"]],
        "attempts": [
            {
                "outcome": "success",
                "source_step": {
                    "name": "read",
                    "description": "Extract page results",
                    "operation": "extract_list",
                    "arguments": {"fields": ["title", "url"]},
                    "on": {"success": "done", "failed": "failed"},
                },
                "evidence": {"result": {"items": []}},
            }
        ],
    }
    with TestClient(app) as client:
        response = client.post("/v1/platform/agent-explorations/distill", json=payload)
        assert response.status_code == 201, response.text
        source = response.json()["recipe"]["source"]
        assert (
            source["inputs"]["properties"]["file_1"]["default"]["asset_id"]
            == asset["id"]
        )
        recipe = response.json()["recipe"]
        inferred = client.post(
            f"/v1/platform/agent-recipes/{recipe['id']}/parameters/infer",
            json={"expected_revision": recipe["revision"]},
        )
        assert inferred.status_code == 200, inferred.text
        inferred_source = inferred.json()["recipe"]["source"]
        assert inferred_source["provenance"]["attachments"][0]["asset_id"] == asset["id"]
        # This read-only recipe has no upload step, so unused legacy file
        # parameters are removed while its original attachment evidence stays.
        assert "file_1" not in inferred_source["inputs"]["properties"]
        foreign, _ = repository.import_stream(
            "bob",
            io.BytesIO(b"Private"),
            name="private.txt",
            media_type="text/plain",
            source_app_id="ai2apps.agents",
        )
        response = client.post(
            "/v1/platform/agent-explorations/distill",
            json={**payload, "attachments": [foreign["id"]]},
        )
        assert response.status_code == 404, response.text
    runtime.stop()


def test_file_upload_asset_binding_tracks_reusable_parameter():
    from ai2apps.agent_builder.attachments import add_attachment_parameters
    source = {"steps": [{"arguments": {"asset_ids": ["asset-original"]}}]}
    add_attachment_parameters(source, [{"parameter": "file_1", "file": {"asset_id": "asset-original", "url": "/file/original", "name": "image.png"}}])
    assert source["steps"][0]["arguments"]["asset_ids"] == "${input.attachments}"
    assert source["inputs"]["properties"]["attachments"]["type"] == "array"
    assert source["inputs"]["properties"]["attachments"]["items"]["x-ai2apps-file"] is True
    assert source["provenance"]["attachments"][0]["asset_id"] == "asset-original"


def test_upload_array_preserves_other_reference_bindings():
    attached = [{"parameter": "file_1", "file": {"asset_id": "a", "url": "/owned/a", "name": "a.png"}}]
    source = {"steps": [{"arguments": {"asset_ids": ["a"]}}, {"arguments": {"url": "/owned/a"}}]}
    add_attachment_parameters(source, attached)
    assert source["steps"][0]["arguments"]["asset_ids"] == "${input.attachments}"
    assert source["steps"][1]["arguments"]["url"] == "${input.file_1.url}"
    assert "file_1" in source["inputs"]["properties"]


def test_file_array_checks_each_owner_and_metadata(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    repository = GalleryRepository(runtime.database, runtime.config.paths.artifacts_path / "gallery", runtime.events)
    asset, _ = repository.import_stream("alice", io.BytesIO(b"Reference"), name="a.txt", media_type="text/plain", source_app_id="ai2apps.agents")
    schema = {"properties": {"attachments": {"type": "array", "x-ai2apps-file": True}}}
    values = {"attachments": [{"asset_id": asset["id"], "url": "/forged"}]}
    result = enrich_file_inputs(runtime, "alice", schema, values)
    assert result["attachments"][0]["url"].endswith(asset["id"] + "/content")
    with pytest.raises(RepositoryError):
        enrich_file_inputs(runtime, "bob", schema, values)
    with pytest.raises(ValueError):
        enrich_file_inputs(runtime, "alice", schema, {"attachments": ["filename.png"]})
    runtime.stop()
