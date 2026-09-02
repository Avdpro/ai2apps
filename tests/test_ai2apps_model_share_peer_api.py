from types import SimpleNamespace
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.model_share import create_model_share_router
from ai2apps.api.model_share_peer import create_model_share_peer_ingress_router
from ai2apps.identity import MemberRole, RequestPrincipal


def test_model_share_ingress_is_fail_closed_until_provider_is_enabled():
    runtime = SimpleNamespace(
        model_share_provider=None,
        model_share_provider_principal=None,
    )
    app = FastAPI()
    app.include_router(create_model_share_peer_ingress_router(lambda: runtime))

    response = TestClient(app).post(
        "/v1/model-share/peer/v1/inference",
        json={},
    )

    assert response.status_code == 503
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "error": {
            "code": "MODEL_SHARE_NOT_READY",
            "message": "Model Share Provider is not enabled.",
            "retryable": True,
        }
    }


def test_model_share_buyer_rejects_boolean_token_count_before_cloud_use():
    principal = RequestPrincipal(
        actor_user_id=str(uuid4()), installation_id=str(uuid4()),
        organization_id=str(uuid4()), billing_account_id=str(uuid4()),
        role=MemberRole.CORE, membership_epoch=1,
    )
    runtime = SimpleNamespace(peer_transport=object(), cloud=object(), database=object())
    app = FastAPI()
    app.include_router(create_model_share_router(lambda: runtime, lambda: principal))

    response = TestClient(app).post("/model-share/inference", json={
        "modelId": "local/model",
        "modelRevision": "a" * 40,
        "runtime": "omlx",
        "expectedRateCardVersion": "pilot-v1",
        "maximumAmountMinor": "10",
        "estimatedInputTokens": True,
        "maximumOutputTokens": 64,
        "prompt": "hello",
        "systemPrompt": None,
        "temperature": 0,
    })

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "MODEL_SHARE_REQUEST_INVALID"


def test_model_share_buyer_requires_browser_cloud_session_before_compute_use():
    principal = RequestPrincipal(
        actor_user_id=str(uuid4()), installation_id=str(uuid4()),
        organization_id=str(uuid4()), billing_account_id=str(uuid4()),
        role=MemberRole.CORE, membership_epoch=1,
    )
    runtime = SimpleNamespace(
        peer_transport=SimpleNamespace(broker_for=lambda _principal: object()),
        cloud=object(), database=object(),
        cloud_browser_session_from_cookies=lambda _cookies: None,
    )
    app = FastAPI()
    app.include_router(create_model_share_router(lambda: runtime, lambda: principal))

    response = TestClient(app).post("/model-share/inference", json={
        "modelId": "local/model",
        "modelRevision": "a" * 40,
        "runtime": "omlx",
        "expectedRateCardVersion": "pilot-v1",
        "maximumAmountMinor": "10",
        "estimatedInputTokens": 8,
        "maximumOutputTokens": 16,
        "prompt": "hello",
        "systemPrompt": None,
        "temperature": 0,
    })

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CLOUD_BROWSER_SESSION_REQUIRED"


def test_model_share_tts_requires_browser_cloud_session_before_compute_use():
    principal = RequestPrincipal(
        actor_user_id=str(uuid4()), installation_id=str(uuid4()),
        organization_id=str(uuid4()), billing_account_id=str(uuid4()),
        role=MemberRole.CORE, membership_epoch=1,
    )
    runtime = SimpleNamespace(
        peer_transport=SimpleNamespace(broker_for=lambda _principal: object()),
        cloud=object(), database=object(),
        cloud_browser_session_from_cookies=lambda _cookies: None,
    )
    app = FastAPI()
    app.include_router(create_model_share_router(lambda: runtime, lambda: principal))

    response = TestClient(app).post("/model-share/tts", json={
        "modelId": "local/tts", "modelRevision": "b" * 40,
        "runtime": "omlx", "expectedRateCardVersion": "tts-v2",
        "maximumAmountMinor": "10", "maximumAudioMilliseconds": 30_000,
        "text": "hello", "voice": "serena", "language": "en",
        "instructions": None, "speed": 1.0,
    })

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CLOUD_BROWSER_SESSION_REQUIRED"
