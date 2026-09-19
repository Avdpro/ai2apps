from pathlib import Path

import pytest
from pydantic import ValidationError

from ai2apps.api.auth import CoreBootstrapRequest
from ai2apps.api.cloud import (
    AdminReauthRequest,
    CoreDeviceRevokeRequest,
    LoginRequest,
    MemberChangeRequest,
    MemberQuotaChangeRequest,
    OrganizationPolicyChangeRequest,
    PasswordResetRequest,
    RegisterRequest,
)
from ai2apps.api.packages import CloudAdminReauthRequest
from ai2apps.api.upstreams import (
    CloudLinkOwnerRequest,
    CloudNodeGrantRequest,
    CloudPairingAcceptRequest,
)
from ai2apps.password_policy import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH

PASSWORD_FIELDS = (
    (RegisterRequest, "password"),
    (LoginRequest, "password"),
    (AdminReauthRequest, "password"),
    (CoreDeviceRevokeRequest, "ownerPassword"),
    (PasswordResetRequest, "newPassword"),
    (MemberChangeRequest, "ownerPassword"),
    (OrganizationPolicyChangeRequest, "ownerPassword"),
    (MemberQuotaChangeRequest, "ownerPassword"),
    (CoreBootstrapRequest, "ownerPassword"),
    (CloudPairingAcceptRequest, "owner_password"),
    (CloudNodeGrantRequest, "owner_password"),
    (CloudLinkOwnerRequest, "owner_password"),
    (CloudAdminReauthRequest, "password"),
)


def _password_string_schema(field_schema):
    if "minLength" in field_schema:
        return field_schema
    if field_schema.get("type") == "string":
        return field_schema
    for candidate in field_schema.get("anyOf", ()):  # Optional password fields.
        if candidate.get("type") == "string":
            return candidate
    raise AssertionError(f"No string schema found in {field_schema!r}")


@pytest.mark.parametrize(("model", "field_name"), PASSWORD_FIELDS)
def test_account_password_request_schema_uses_shared_policy(model, field_name):
    field_schema = _password_string_schema(
        model.model_json_schema(by_alias=True)["properties"][field_name]
    )

    assert field_schema["minLength"] == PASSWORD_MIN_LENGTH
    assert field_schema["maxLength"] == PASSWORD_MAX_LENGTH


def test_registration_and_login_accept_eight_characters_and_reject_seven():
    RegisterRequest(displayName="User", email="u@example.com", password="12345678")
    LoginRequest(email="u@example.com", password="12345678")

    with pytest.raises(ValidationError):
        RegisterRequest(displayName="User", email="u@example.com", password="1234567")
    with pytest.raises(ValidationError):
        LoginRequest(email="u@example.com", password="1234567")


def test_password_length_is_measured_as_utf8_bytes():
    RegisterRequest(displayName="User", email="u@example.com", password="密码密码")

    with pytest.raises(ValidationError):
        RegisterRequest(displayName="User", email="u@example.com", password="密码")
    with pytest.raises(ValidationError):
        RegisterRequest(displayName="User", email="u@example.com", password="密" * 43)


def test_account_ui_has_no_legacy_twelve_character_gate():
    repository = Path(__file__).resolve().parents[1]
    paths = (
        repository / "ai2apps/web/templates/system_apps/account.html",
        repository / "ai2apps/web/templates/system_apps/discover.html",
        repository / "ai2apps/web/templates/login.html",
        repository / "ai2apps/web/static/js/account.js",
        repository / "ai2apps/web/static/js/discover.js",
        repository / "ai2apps/web/static/js/login.js",
    )
    combined = "\n".join(path.read_text(encoding="utf-8") for path in paths)

    assert 'minlength="12"' not in combined
    assert "adminPassword.length<12" not in combined
    assert "adminPassword.length < 12" not in combined
    assert "new TextEncoder()" in combined
    assert "bytes >= 8" in combined
    assert "bytes <= 128" in combined
