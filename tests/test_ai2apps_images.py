# SPDX-License-Identifier: Apache-2.0
"""Image generation service and Agent Tool contracts."""

from __future__ import annotations

import pytest

from ai2apps.chat import ChatRepository
from ai2apps.config import PlatformConfig
from ai2apps.model_manager import ModelManagerStore
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.services import ToolCallContext


@pytest.mark.asyncio
async def test_image_tool_uses_default_model_and_creates_session_artifact(
    tmp_path, monkeypatch
):
    async def fake_image_request(payload, **_kwargs):
        assert payload["model"] == "cloud/ai2apps/openai/gpt-image-2"
        assert payload["prompt"] == "a tiny blue robot"
        assert payload["idempotencyKey"].startswith("agent-image-tinv_")
        return {
            "requestId": "req-image-settlement",
            "model": "openai/gpt-image-2",
            "status": "completed",
            "usage": {"imageOutputTokens": 196},
            "points": {"reserved": "7", "charged": "6"},
            "pointsReleased": "1",
            "balance": "994",
            "pricingVersion": "image-v1",
            "image": {
                "dataUrl": "data:image/png;base64,aW1hZ2U=",
                "size": "1024x1024",
                "quality": "auto",
                "format": "png",
            }
        }

    monkeypatch.setattr("ai2apps.images.service.request_cloud_image", fake_image_request)
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    ModelManagerStore(tmp_path).put_default_models(
        {"image_generation": "cloud/ai2apps/openai/gpt-image-2"}
    )
    session_id = (
        ChatRepository(runtime.database, runtime.events)
        .create_thread(title="Image tool")[0]
        .session.id
    )

    result = await runtime.tools.execute(
        "image.generate",
        {"prompt": "a tiny blue robot"},
        context=ToolCallContext(
            caller_id="agent:ai2apps.general-agent",
            session_id=session_id,
            trace_id="run-image",
            granted_capabilities=frozenset(
                {"image.generate", "workspace.write", "artifact.create"}
            ),
        ),
    )

    artifact = result.output["artifact"]
    assert result.output["ai2apps_cloud"] == [{
        "requestId": "req-image-settlement",
        "model": "openai/gpt-image-2",
        "status": "completed",
        "usage": {"imageOutputTokens": 196},
        "points": {"reserved": "7", "charged": "6"},
        "pointsReleased": "1",
        "balance": "994",
        "pricingVersion": "image-v1",
        "phase": "completed",
    }]
    assert artifact["media_type"] == "image/png"
    assert artifact["download_url"].endswith(f"/{artifact['id']}/download")
    stored = runtime.workspace.read(session_id, f"generated-images/{artifact['name']}")
    assert stored["content"] == "image"
    record = runtime.workspace.get_artifact(session_id, artifact["id"])
    assert "prompt" not in record.metadata
