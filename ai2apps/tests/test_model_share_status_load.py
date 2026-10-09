import asyncio
import threading
import time
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI

from ai2apps.api.model_share import create_model_share_router
from ai2apps.model_sharing.manager import ModelShareProviderManager
from ai2apps.loop_diagnostics import LoopDiagnostics


def test_status_scans_catalog_once_and_keeps_eligibility(monkeypatch):
    models = tuple(SimpleNamespace(
        id=f"model-{i}", display_name=f"Model {i}", service_key="worker",
        model_type="llm", endpoints={"chat_completions": "/chat"},
        checkpoint_ready=True,
        weights={"revision": "a" * 40},
    ) for i in range(30))
    scans = []
    monkeypatch.setattr("ai2apps.model_sharing.manager.list_package_models",
                        lambda runtime: scans.append(runtime) or models)
    manager = ModelShareProviderManager(
        preferences=SimpleNamespace(models=lambda: [], device_enabled=lambda: False),
        principal=object(), broker=object(), compute=object(), peer_sessions=object(),
        jobs=object(), signer_factory=object(),
        invocations=SimpleNamespace(runtime=object(), model=lambda _: pytest.fail("Repeated catalog lookup")),
        environment_config=object(),
    )
    result = manager.status()
    assert len(scans) == 1
    assert len(result["models"]) == 30
    assert all(model["eligible"] for model in result["models"])
    models[0].weights = {}
    assert manager.status()["models"][0]["eligible"] is False


@pytest.mark.asyncio
async def test_slow_provider_status_does_not_block_health():
    entered, release = threading.Event(), threading.Event()

    def status():
        entered.set()
        assert release.wait(2)
        return {"enabled": False}

    app = FastAPI()
    app.include_router(create_model_share_router(
        runtime_provider=lambda: SimpleNamespace(model_share_controller=SimpleNamespace(status=status)),
        principal_provider=lambda: object(),
    ))

    @app.get("/health")
    async def health():
        return {"healthy": True}

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        pending = asyncio.create_task(client.get("/model-share/provider"))
        try:
            assert await asyncio.to_thread(entered.wait, 1)
            response = await asyncio.wait_for(client.get("/health"), .5)
            assert response.json() == {"healthy": True}
        finally:
            release.set()
            await pending


@pytest.mark.asyncio
async def test_watchdog_reports_blocked_function_without_local_values(caplog):
    watchdog = LoopDiagnostics(threshold=.05, report_interval=30)
    with caplog.at_level("WARNING", logger="ai2apps.loop_diagnostics"):
        watchdog.start()
        await asyncio.sleep(.01)
        private_payload = "DO_NOT_LOG_THIS_VALUE"
        time.sleep(.35)
        await watchdog.stop()
    assert "Local event loop stalled" in caplog.text
    assert "test_watchdog_reports_blocked_function" in caplog.text
    assert private_payload not in caplog.text
