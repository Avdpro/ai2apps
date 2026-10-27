# SPDX-License-Identifier: Apache-2.0
"""Image Tool uses the same durable Studio owner as the UI."""
import base64
import io
import asyncio
import httpx
import pytest
from PIL import Image
from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.model_manager import ModelManagerStore
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ToolCallContext

@pytest.mark.asyncio
async def test_image_tool_uses_default_model_and_creates_session_artifact(tmp_path, monkeypatch):
    image = io.BytesIO()
    Image.new("RGB", (16, 16), "blue").save(image, format="PNG")
    calls = []
    async def fake_image_request(payload, **kwargs):
        assert payload["model"] == "cloud/ai2apps/openai/gpt-image-2"
        assert payload["prompt"] == "a tiny blue robot"
        assert kwargs["cloud_headers"] == {"X-Test-Actor": "local"}
        assert payload["idempotencyKey"].startswith("imagine-run-strun_")
        calls.append(payload)
        return {"image": {"dataUrl": "data:image/png;base64," + base64.b64encode(image.getvalue()).decode(), "format": "png"}}
    monkeypatch.setattr("ai2apps.cloud_gateway.request_cloud_image", fake_image_request)
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    async def catalog_request(method, path, **kwargs):
        assert (method, path) == ("GET", "/v1/ai/models")
        return httpx.Response(200, request=httpx.Request(method, "https://cloud.invalid"+path), json={"items":[{
            "id":"openai/gpt-image-2", "capabilities":{"imageGeneration":True},
            "imageOptions":{"size":{"mode":"fixed","default":"1024x1024","presets":["1024x1024"]},
                            "quality":["auto"],"outputFormat":["png"]}
        }]})
    monkeypatch.setattr(runtime.cloud, "request", catalog_request)
    monkeypatch.setattr(runtime, "cloud_ai_authorization_headers", lambda principal: {"X-Test-Actor": principal.actor_user_id})
    ModelManagerStore(tmp_path).put_default_models({"image_generation": "cloud/ai2apps/openai/gpt-image-2"})
    session_id = ChatRepository(runtime.database, runtime.events).create_thread(title="Image tool")[0].session.id
    await runtime.start_background_tasks(retention_interval_seconds=60)
    try:
        result = await asyncio.wait_for(runtime.tools.execute(
            "image.generate", {"prompt": "a tiny blue robot"},
            context=ToolCallContext(caller_id="agent:ai2apps.general-agent", session_id=session_id,
                actor_user_id="local", installation_id="local", trace_id="run-image",
                granted_capabilities=frozenset({"image.generate","workspace.write","artifact.create"}))
        ), timeout=15)
        assert len(calls) == 1
        assert result.output["studio_job_id"] and result.output["studio_run_id"]
        assert result.output["mini_app_id"] == "ai2apps.imagine.text-to-image"
        artifact = result.output["artifact"]
        assert artifact["media_type"] == "image/png"
        assert artifact["download_url"].endswith(f"/{artifact['id']}/download")
        record = runtime.workspace.get_artifact(session_id, artifact["id"])
        assert runtime.workspace.artifact_path(record).read_bytes() == image.getvalue()
        assert "prompt" not in record.metadata
    finally:
        await runtime.stop_background_tasks()
        runtime.stop()
