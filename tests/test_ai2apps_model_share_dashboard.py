"""Dashboard Compute-sharing preferences and UI contracts."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.model_share import create_model_share_router
from ai2apps.events import EventStore
from ai2apps.identity import RequestPrincipal
from ai2apps.model_sharing.cloud import ComputeCloudClient, ComputeCloudError
from ai2apps.model_sharing.controller import ModelShareProviderConfiguration
from ai2apps.model_sharing.manager import ModelShareProviderManager
from ai2apps.model_sharing.preferences import ModelSharePreferencesRepository
from ai2apps.storage import PlatformDatabase


def _preferences(tmp_path) -> ModelSharePreferencesRepository:
    database = PlatformDatabase(tmp_path / "platform.sqlite3")
    database.initialize()
    return ModelSharePreferencesRepository(database, EventStore(database))


def test_last_model_selection_turns_device_sharing_off(tmp_path):
    preferences = _preferences(tmp_path)
    model_id = "ai2apps.qwen35/qwen3.5-0.8b-4bit"

    assert preferences.device_enabled() is False
    with pytest.raises(ValueError, match="Select at least one model"):
        preferences.set_device_enabled(True)

    saved = preferences.save_model(
        model_id=model_id,
        service_key="ai2apps.qwen35",
        model_revision="a" * 40,
        runtime="omlx",
        rate_card_id=str(uuid4()),
        rate_card_version="compute-qwen35-v1",
        max_concurrency=2,
        estimated_tokens_per_second=8,
        enabled=True,
    )
    assert saved.enabled is True
    assert preferences.selected_count() == 1
    assert preferences.set_device_enabled(True) is True
    assert preferences.device_enabled() is True

    disabled = preferences.set_model_enabled(model_id, False)
    assert disabled.enabled is False
    assert preferences.selected_count() == 0
    assert preferences.device_enabled() is False


def test_model_preferences_preserve_selection_when_capacity_changes(tmp_path):
    preferences = _preferences(tmp_path)
    model_id = "ai2apps.qwen35/qwen3.5-0.8b-4bit"
    rate_card_id = str(uuid4())
    preferences.save_model(
        model_id=model_id,
        service_key="ai2apps.qwen35",
        model_revision="b" * 40,
        runtime="omlx",
        rate_card_id=rate_card_id,
        rate_card_version="compute-qwen35-v1",
        max_concurrency=1,
        estimated_tokens_per_second=4,
        enabled=True,
    )
    updated = preferences.save_model(
        model_id=model_id,
        service_key="ai2apps.qwen35",
        model_revision="b" * 40,
        runtime="omlx",
        rate_card_id=rate_card_id,
        rate_card_version="compute-qwen35-v1",
        max_concurrency=3,
        estimated_tokens_per_second=12,
    )
    assert updated.enabled is True
    assert updated.max_concurrency == 3
    assert updated.estimated_tokens_per_second == 12


def test_dashboard_exposes_device_and_per_model_sharing_controls():
    root = Path(__file__).parents[1]
    template = (root / "ai2apps/web/templates/dashboard/_status.html").read_text()
    script = (root / "ai2apps/web/static/js/dashboard.js").read_text()

    assert "Share this Device's compute" in template
    assert "Sharing preferences" in template
    assert "Cloud Rate Card ID" not in template
    assert 'role="switch"' in template
    assert "modelShareWorkerModels(worker)" in template
    assert "modelShareStandaloneModels()" in template
    assert "Compatible provider" in template
    assert "modelShareStandaloneModels()" in script
    assert "/v1/platform/model-share/provider/device-preference" in script
    assert "/v1/platform/model-share/provider/model-selection" in script
    assert "/v1/platform/model-share/provider/model-preferences" in script
    assert "/v1/platform/model-share/provider/activate" in script


@pytest.mark.asyncio
async def test_compute_cloud_client_validates_discovered_rate_card_identity():
    rate_card_id = str(uuid4())
    seen = []

    class Cloud:
        async def request(self, method, path, **values):
            seen.append((method, path, values))
            return httpx.Response(200, json={"data": [{
                "id": rate_card_id,
                "version": "compute-model-v1",
                "modelId": "local/model",
                "modelRevision": "immutable-revision",
                "runtime": "omlx",
                "status": "active",
                "assetCode": "PROMO_POINTS",
            }]})

    client = ComputeCloudClient(Cloud())
    cards = await client.list_provider_rate_cards(
        model_id="local/model", model_revision="immutable-revision", runtime="omlx"
    )

    assert cards[0]["id"] == rate_card_id
    assert seen[0][0:2] == ("GET", "/v1/compute/provider-rate-cards")
    assert seen[0][2]["params"] == {
        "modelId": "local/model",
        "modelRevision": "immutable-revision",
        "runtime": "omlx",
    }

    class MismatchedCloud(Cloud):
        async def request(self, method, path, **values):
            response = await super().request(method, path, **values)
            payload = response.json()
            payload["data"][0]["modelRevision"] = "other-revision"
            return httpx.Response(200, json=payload)

    with pytest.raises(ComputeCloudError, match="mismatched"):
        await ComputeCloudClient(MismatchedCloud()).list_provider_rate_cards(
            model_id="local/model",
            model_revision="immutable-revision",
            runtime="omlx",
        )


@pytest.mark.asyncio
async def test_compute_cloud_client_creates_and_validates_multimodal_quote():
    quote_id, rate_card_id = str(uuid4()), str(uuid4())

    class Cloud:
        async def request(self, method, path, **values):
            assert (method, path) == ("POST", "/v1/compute/quotes")
            assert values["headers"]["Idempotency-Key"].startswith("quote-")
            pricing = values["json"]["pricingInput"]
            return httpx.Response(201, json={
                "id": quote_id, "rateCardId": rate_card_id,
                "calculatorType": "tts_v1", "pricingInput": pricing,
                "boundedUsage": {"maximumDurationMs": 2000},
                "minimumChargeMinor": "1", "maximumChargeMinor": "5",
                "buyerMaximumMinor": "10",
                "expiresAt": "2026-09-02T12:00:00.000Z", "consumedAt": None,
            })

    quote = await ComputeCloudClient(Cloud()).create_quote(
        model_id="local/tts", model_revision="a" * 40, runtime="omlx",
        calculator_type="tts_v1",
        pricing_input={"unicodeScalarCount": 5, "speedBps": 10_000,
                       "customSampleUsed": False, "quality": "mid"},
        buyer_maximum_minor="10", idempotency_key="quote-test-1",
    )
    assert quote.maximum_charge_minor == "5"


@pytest.mark.asyncio
async def test_manager_reconciles_selected_model_with_device_master_switch(
    tmp_path, monkeypatch
):
    preferences = _preferences(tmp_path)
    model_id = "ai2apps.qwen35/qwen3.5-0.8b-4bit"
    model = SimpleNamespace(
        id=model_id,
        display_name="Qwen 3.5 0.8B",
        service_key="ai2apps.qwen35",
        checkpoint_ready=True,
        model_type="llm",
        endpoints={"chat_completions": "/v1/chat/completions"},
        weights={"revision": "c" * 40},
    )
    invocations = SimpleNamespace(runtime=object(), model=lambda value: model if value == model_id else None)
    lifecycle = []

    class Controller:
        def __init__(self, **values):
            self.config = values["config"]
            self.offer_id = None

        async def startup(self):
            lifecycle.append(("started", self.config.model_id))

        async def shutdown(self):
            lifecycle.append(("stopped", self.config.model_id))

        def status(self):
            return {"running": True, "offerId": self.offer_id, "lastError": None}

        def bind_compute(self, _compute):
            return None

    monkeypatch.setattr("ai2apps.model_sharing.manager.list_package_models", lambda _runtime: (model,))
    monkeypatch.setattr("ai2apps.model_sharing.manager.ModelShareProviderController", Controller)
    manager = ModelShareProviderManager(
        preferences=preferences,
        principal=object(),
        broker=object(),
        compute=object(),
        peer_sessions=object(),
        jobs=object(),
        signer_factory=object(),
        invocations=invocations,
        environment_config=ModelShareProviderConfiguration(enabled=False),
    )

    await manager.startup()
    assert manager.status()["canEnable"] is False
    preferences.save_model(
        model_id=model_id,
        service_key=model.service_key,
        model_revision=model.weights["revision"],
        runtime="omlx",
        rate_card_id=str(uuid4()),
        rate_card_version="compute-qwen35-v1",
        max_concurrency=1,
        estimated_tokens_per_second=8,
    )
    await manager.save_model_preferences(
        model_id,
        max_concurrency=2,
        estimated_tokens_per_second=9,
    )
    await manager.set_model_enabled(model_id, True)
    assert manager.status()["canEnable"] is True
    assert lifecycle == []

    enabled = await manager.set_device_enabled(True)
    assert enabled["enabled"] is True
    assert enabled["runningModelCount"] == 1
    assert lifecycle == [("started", model_id)]

    disabled = await manager.set_model_enabled(model_id, False)
    assert disabled["enabled"] is False
    assert disabled["canEnable"] is False
    assert lifecycle[-1] == ("stopped", model_id)


@pytest.mark.asyncio
async def test_device_sharing_starts_remote_before_provider_offer(
    tmp_path, monkeypatch
):
    preferences = _preferences(tmp_path)
    model_id = "ai2apps.qwen35/qwen3.5-0.8b-4bit"
    model = SimpleNamespace(
        id=model_id,
        display_name="Qwen 3.5 0.8B",
        service_key="ai2apps.qwen35",
        checkpoint_ready=True,
        model_type="llm",
        endpoints={"chat_completions": "/v1/chat/completions"},
        weights={"revision": "e" * 40},
    )
    invocations = SimpleNamespace(
        runtime=object(), model=lambda value: model if value == model_id else None
    )
    lifecycle = []

    class Controller:
        def __init__(self, **values):
            self.config = values["config"]

        async def startup(self):
            lifecycle.append("provider-started")

        async def shutdown(self):
            lifecycle.append("provider-stopped")

        def status(self):
            return {"running": True, "offerId": None, "lastError": None}

        def bind_compute(self, _compute):
            return None

    class Frpc:
        available = True
        running = False

        def status(self):
            return {
                "running": self.running,
                "deviceId": "cloud-device" if self.running else None,
            }

    frpc = Frpc()

    class Remote:
        async def start(self, device_id, *, cloud):
            assert device_id == "cloud-device"
            assert cloud == "browser-cloud"
            lifecycle.append("remote-started")
            frpc.running = True

    remote = Remote()
    remote.frpc = frpc
    monkeypatch.setattr(
        "ai2apps.model_sharing.manager.list_package_models", lambda _runtime: (model,)
    )
    monkeypatch.setattr(
        "ai2apps.model_sharing.manager.ModelShareProviderController", Controller
    )
    preferences.save_model(
        model_id=model_id,
        service_key=model.service_key,
        model_revision=model.weights["revision"],
        runtime="omlx",
        rate_card_id=str(uuid4()),
        rate_card_version="compute-qwen35-v1",
        max_concurrency=1,
        estimated_tokens_per_second=8,
        enabled=True,
    )
    manager = ModelShareProviderManager(
        preferences=preferences,
        principal=object(),
        broker=object(),
        compute=object(),
        peer_sessions=object(),
        jobs=object(),
        signer_factory=object(),
        invocations=invocations,
        environment_config=ModelShareProviderConfiguration(enabled=False),
        remote=remote,
        cloud_device_id="cloud-device",
    )
    manager.bind_remote_cloud("browser-cloud")

    status = await manager.set_device_enabled(True)

    assert lifecycle == ["remote-started", "provider-started"]
    assert status["enabled"] is True
    assert status["transport"]["running"] is True


@pytest.mark.asyncio
async def test_manager_discovers_exact_cloud_rate_card_without_user_uuid(
    tmp_path, monkeypatch
):
    preferences = _preferences(tmp_path)
    model_id = "ai2apps.qwen35/qwen3.5-0.8b-4bit"
    revision = "d" * 40
    rate_card_id = str(uuid4())
    model = SimpleNamespace(
        id=model_id,
        display_name="Qwen 3.5 0.8B",
        service_key="ai2apps.qwen35",
        checkpoint_ready=True,
        model_type="llm",
        endpoints={"chat_completions": "/v1/chat/completions"},
        weights={"revision": revision},
    )
    invocations = SimpleNamespace(
        runtime=object(), model=lambda value: model if value == model_id else None
    )

    class Compute:
        async def list_provider_rate_cards(self, **values):
            assert values == {
                "model_id": model_id,
                "model_revision": revision,
                "runtime": "omlx",
            }
            return [{"id": rate_card_id, "version": "compute-qwen35-v1"}]

    monkeypatch.setattr(
        "ai2apps.model_sharing.manager.list_package_models", lambda _runtime: (model,)
    )
    manager = ModelShareProviderManager(
        preferences=preferences,
        principal=object(),
        broker=object(),
        compute=Compute(),
        peer_sessions=object(),
        jobs=object(),
        signer_factory=object(),
        invocations=invocations,
        environment_config=ModelShareProviderConfiguration(enabled=False),
    )

    status = await manager.refresh_rate_cards()

    saved = preferences.model(model_id)
    assert saved is not None
    assert saved.rate_card_id == rate_card_id
    assert saved.enabled is False
    assert status["models"][0]["shareable"] is True
    assert status["canEnable"] is False
    assert status["rateCardDiscoveryAvailable"] is True


@pytest.mark.asyncio
async def test_manager_tolerates_cloud_without_rate_card_discovery(
    tmp_path, monkeypatch
):
    preferences = _preferences(tmp_path)
    model = SimpleNamespace(
        id="local/model",
        display_name="Local Model",
        service_key="local.worker",
        checkpoint_ready=True,
        model_type="llm",
        endpoints={"chat_completions": "/v1/chat/completions"},
        weights={"revision": "e" * 40},
    )

    class LegacyCloud:
        async def list_provider_rate_cards(self, **_values):
            raise ComputeCloudError("NOT_FOUND", "not found", status_code=404)

    monkeypatch.setattr(
        "ai2apps.model_sharing.manager.list_package_models", lambda _runtime: (model,)
    )
    manager = ModelShareProviderManager(
        preferences=preferences,
        principal=object(),
        broker=object(),
        compute=LegacyCloud(),
        peer_sessions=object(),
        jobs=object(),
        signer_factory=object(),
        invocations=SimpleNamespace(
            runtime=object(), model=lambda value: model if value == model.id else None
        ),
        environment_config=ModelShareProviderConfiguration(enabled=False),
    )

    status = await manager.refresh_rate_cards()

    assert status["rateCardDiscoveryAvailable"] is False
    assert status["lastError"] is None


@pytest.mark.asyncio
async def test_manager_discovers_reviewed_tts_rate_card_with_audio_units(
    tmp_path, monkeypatch
):
    preferences = _preferences(tmp_path)
    model_id = "ai2apps.model.qwen3-tts-0.6b/custom-voice-6bit"
    revision = "f" * 40
    model = SimpleNamespace(
        id=model_id, display_name="Qwen3 TTS 0.6B",
        service_key="ai2apps.model.qwen3-tts-0.6b", checkpoint_ready=True,
        model_type="audio_tts", endpoints={"audio_speech": "/v1/audio/speech"},
        weights={"revision": revision},
    )
    invocations = SimpleNamespace(
        runtime=object(), model=lambda value: model if value == model_id else None
    )

    class Compute:
        async def list_provider_rate_cards(self, **_values):
            return [{
                "id": str(uuid4()), "version": "compute-qwen3-tts-v2",
                "modality": "audio_tts", "inputUnit": "unicode_scalar",
                "outputUnit": "audio_millisecond",
            }]

    monkeypatch.setattr(
        "ai2apps.model_sharing.manager.list_package_models", lambda _runtime: (model,)
    )
    manager = ModelShareProviderManager(
        preferences=preferences, principal=object(), broker=object(),
        compute=Compute(), peer_sessions=object(), jobs=object(),
        signer_factory=object(), invocations=invocations,
        environment_config=ModelShareProviderConfiguration(enabled=False),
    )

    status = await manager.refresh_rate_cards()

    assert status["models"][0]["modality"] == "audio_tts"
    assert status["models"][0]["shareable"] is True


@pytest.mark.asyncio
async def test_dashboard_preference_api_updates_manager():
    calls = []

    class Manager:
        def bind_compute(self, _compute):
            calls.append(("bind",))

        def bind_remote_cloud(self, _cloud):
            calls.append(("bind-remote",))

        async def ensure_transport_ready(self):
            calls.append(("ensure-transport",))

        def status(self):
            return {"enabled": False, "canEnable": False, "models": []}

        async def set_device_enabled(self, enabled):
            calls.append(("device", enabled))
            return {"enabled": enabled, "canEnable": True, "models": []}

        async def set_model_enabled(self, model_id, enabled):
            calls.append(("model", model_id, enabled))
            return {"enabled": False, "canEnable": enabled, "models": []}

        async def save_model_preferences(self, model_id, **values):
            calls.append(("preferences", model_id, values))
            return {"enabled": False, "canEnable": False, "models": []}

        async def refresh_rate_cards(self):
            calls.append(("refresh",))
            return {"enabled": False, "canEnable": False, "models": []}

    manager = Manager()
    runtime = SimpleNamespace(
        model_share_controller=manager,
        cloud_browser_session_from_cookies=lambda _cookies: object(),
        cloud_for_browser=lambda _session: object(),
    )

    async def principal():
        return RequestPrincipal.legacy_local()

    app = FastAPI()
    app.include_router(
        create_model_share_router(lambda: runtime, principal), prefix="/v1/platform"
    )
    model_id = "ai2apps.qwen35/qwen3.5-0.8b-4bit"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        preferences = await client.post(
            "/v1/platform/model-share/provider/model-preferences",
            json={
                "modelId": model_id,
                "maxConcurrency": 2,
                "estimatedTokensPerSecond": 8,
            },
        )
        selection = await client.post(
            "/v1/platform/model-share/provider/model-selection",
            json={"modelId": model_id, "enabled": True},
        )
        device = await client.post(
            "/v1/platform/model-share/provider/device-preference",
            json={"enabled": True},
        )
        activation = await client.post(
            "/v1/platform/model-share/provider/activate",
        )

    assert preferences.status_code == 200
    assert selection.status_code == 200
    assert device.status_code == 200
    assert activation.status_code == 200
    assert ("preferences", model_id, {
        "max_concurrency": 2,
        "estimated_tokens_per_second": 8,
    }) in calls
    assert ("model", model_id, True) in calls
    assert ("device", True) in calls
    assert ("refresh",) in calls
