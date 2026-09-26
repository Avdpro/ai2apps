from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai2apps.api.cloud import create_cloud_router, PasswordChangeRequest
from ai2apps.identity import RequestPrincipal


@pytest.mark.parametrize("status,expected,cleared", [(200,200,True),(400,400,False),(401,401,False),(404,503,False),(405,503,False),(429,429,False)])
def test_password_change_proxies_current_session(status, expected, cleared):
    cloud=SimpleNamespace(request=AsyncMock(return_value=httpx.Response(status,json={"changed":status==200})), clear_session=AsyncMock())
    runtime=SimpleNamespace(cloud=cloud)
    app=FastAPI()
    app.include_router(create_cloud_router(lambda:runtime, RequestPrincipal.legacy_local))
    payload={"currentPassword":"old-pass-123", "newPassword":"new-pass-456"}
    with TestClient(app) as client:
        response=client.post("/cloud/auth/password/change",json=payload)
    assert response.status_code==expected
    assert cloud.request.call_args.args==("POST","/v1/auth/password/change")
    assert cloud.request.call_args.kwargs["json"]==payload
    assert cloud.clear_session.await_count==int(cleared)
    if status in (404,405):
        assert response.json()["error"]["code"]=="PASSWORD_CHANGE_UNAVAILABLE"


def test_password_change_secrets_redacted_and_utf8_policy():
    from pydantic import ValidationError
    request=PasswordChangeRequest(currentPassword="old-pass-123",newPassword="new-pass-456")
    assert "old-pass-123" not in repr(request)
    assert "new-pass-456" not in request.model_dump_json()
    for value in ("short", "密"*43):
        with pytest.raises(ValidationError):
            PasswordChangeRequest(currentPassword="old-pass-123",newPassword=value)
