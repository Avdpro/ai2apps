"""Installation binding and authoritative member-principal tests."""

from __future__ import annotations

from datetime import timedelta

import pytest

from ai2apps.config import PlatformConfig
from ai2apps.identity import (
    IdentityBindingError,
    IdentityRepository,
    MemberRole,
    OrganizationType,
    local_session_cookie_name,
)
from ai2apps.platform_runtime import PlatformRuntime


@pytest.fixture
def identity_repository(tmp_path):
    runtime = PlatformRuntime(PlatformConfig.from_base_path(tmp_path))
    runtime.start()
    assert runtime.database is not None
    return runtime, IdentityRepository(runtime.database)


def _bind(repository: IdentityRepository):
    return repository.bind_installation(
        installation_id="installation-1",
        cloud_device_id="device-1",
        organization_id="household-1",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="user-core",
        billing_account_id="billing-core",
        access_epoch=3,
    )


def test_binding_is_single_authority_and_seeds_core_membership(identity_repository):
    _, repository = identity_repository
    first = _bind(repository)
    replay = _bind(repository)
    core = repository.principal_for("user-core")

    assert replay.id == first.id
    assert replay.access_epoch == 3
    assert core.actor_user_id == "user-core"
    assert core.billing_account_id == "billing-core"
    assert core.role is MemberRole.CORE
    assert core.is_core is True

    with pytest.raises(IdentityBindingError, match="another Cloud authority"):
        repository.bind_installation(
            installation_id="installation-2",
            cloud_device_id="device-2",
            organization_id="household-2",
            organization_type=OrganizationType.HOUSEHOLD,
            core_user_id="other-core",
            billing_account_id="other-billing",
            access_epoch=1,
        )


def test_active_member_resolves_to_core_billing_and_revoke_fails_closed(
    identity_repository,
):
    _, repository = identity_repository
    _bind(repository)
    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=7,
    )
    principal = repository.principal_for("user-member")

    assert principal.actor_user_id == "user-member"
    assert principal.billing_account_id == "billing-core"
    assert principal.installation_id == "installation-1"
    assert principal.membership_epoch == 7
    assert principal.is_core is False

    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="revoked",
        membership_epoch=8,
    )
    with pytest.raises(IdentityBindingError, match="not an active"):
        repository.principal_for("user-member")


def test_identity_schema_adds_session_and_app_owner_boundaries(identity_repository):
    runtime, _ = identity_repository
    with runtime.database.transaction() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(app_instances)")
        }

    assert {
        "installations",
        "installation_memberships",
        "local_login_sessions",
    }.issubset(tables)
    assert "owner_user_id" in columns


def test_local_session_is_opaque_and_membership_epoch_revokes_it(
    identity_repository,
):
    runtime, repository = identity_repository
    _bind(repository)
    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=4,
    )

    token, session = repository.create_local_session("user-member")

    assert token != session.token_digest
    assert repository.authorize_local_session(token).actor_user_id == "user-member"
    with runtime.database.transaction() as connection:
        stored = connection.execute(
            "SELECT token_digest FROM local_login_sessions"
        ).fetchone()[0]
    assert stored == session.token_digest
    assert token not in stored

    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=5,
    )
    assert repository.authorize_local_session(token) is None


def test_local_session_preserves_client_scope(identity_repository):
    _, repository = identity_repository
    _bind(repository)

    token, session = repository.create_local_session(
        "user-core",
        client_scope="mobile-browser-one",
    )
    principal = repository.authorize_local_session(token)

    assert session.client_scope == "mobile-browser-one"
    assert principal is not None
    assert principal.client_scope == "mobile-browser-one"


def test_local_session_explicit_revoke(identity_repository):
    _, repository = identity_repository
    _bind(repository)
    token, _ = repository.create_local_session("user-core")

    repository.revoke_local_session(token)

    assert repository.authorize_local_session(token) is None


def test_local_session_expires_after_thirty_days_without_activity(identity_repository):
    runtime, repository = identity_repository
    _bind(repository)
    token, session = repository.create_local_session("user-core")
    stale = (session.last_access_check_at - timedelta(days=31)).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ"
    )
    with runtime.database.transaction(write=True) as connection:
        connection.execute(
            "UPDATE local_login_sessions SET last_access_check_at=? WHERE token_digest=?",
            (stale, session.token_digest),
        )

    assert repository.authorize_local_session(token) is None


def test_local_session_rotates_near_expiry_and_preserves_scope(identity_repository):
    _, repository = identity_repository
    _bind(repository)
    token, _ = repository.create_local_session(
        "user-core", lifetime=timedelta(days=1), client_scope="desktop"
    )

    refreshed = repository.refresh_local_session(token)

    assert refreshed is not None
    new_token, principal, rotated = refreshed
    assert rotated is True
    assert new_token != token
    assert principal.client_scope == "desktop"
    assert repository.authorize_local_session(token) is None
    assert repository.authorize_local_session(new_token) == principal


def test_two_installations_use_distinct_cookies_and_reject_each_others_sessions(
    tmp_path,
):
    runtime_a = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "a"))
    runtime_b = PlatformRuntime(PlatformConfig.from_base_path(tmp_path / "b"))
    runtime_a.start()
    runtime_b.start()
    try:
        assert runtime_a.database is not None
        assert runtime_b.database is not None
        repository_a = IdentityRepository(runtime_a.database)
        repository_b = IdentityRepository(runtime_b.database)
        _bind(repository_a)
        repository_b.bind_installation(
            installation_id="installation-2",
            cloud_device_id="device-2",
            organization_id="household-2",
            organization_type=OrganizationType.HOUSEHOLD,
            core_user_id="other-core",
            billing_account_id="other-billing",
            access_epoch=1,
        )
        token_a, _ = repository_a.create_local_session("user-core")
        token_b, _ = repository_b.create_local_session("other-core")

        assert runtime_a.security_identity is not None
        assert runtime_b.security_identity is not None
        assert runtime_a.local_session_cookie_name() == local_session_cookie_name(
            runtime_a.security_identity.security_instance_id
        )
        assert runtime_b.local_session_cookie_name() == local_session_cookie_name(
            runtime_b.security_identity.security_instance_id
        )
        assert runtime_a.local_session_cookie_name() != runtime_b.local_session_cookie_name()
        shared_browser_cookies = {
            runtime_a.local_session_cookie_name(): token_a,
            runtime_b.local_session_cookie_name(): token_b,
        }
        assert runtime_a.local_session_token_from_cookies(shared_browser_cookies) == token_a
        assert runtime_b.local_session_token_from_cookies(shared_browser_cookies) == token_b
        assert repository_a.authorize_local_session(token_b) is None
        assert repository_b.authorize_local_session(token_a) is None
    finally:
        runtime_a.stop()
        runtime_b.stop()


def test_access_projection_revokes_only_changed_member_sessions(identity_repository):
    _, repository = identity_repository
    _bind(repository)
    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=4,
    )
    repository.upsert_membership(
        cloud_user_id="user-other",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=2,
    )
    core_token, _ = repository.create_local_session("user-core")
    member_token, _ = repository.create_local_session("user-member")
    other_token, _ = repository.create_local_session("user-other")

    repository.apply_access_projection(
        installation_id="installation-1",
        cloud_device_id="device-1",
        organization_id="household-1",
        device_status="active",
        access_epoch=3,
        memberships=[
            {
                "user_id": "user-core",
                "role": "core",
                "status": "active",
                "membership_epoch": 3,
            },
            {
                "user_id": "user-member",
                "role": "guest",
                "status": "active",
                "membership_epoch": 5,
            },
            {
                "user_id": "user-other",
                "role": "member",
                "status": "active",
                "membership_epoch": 2,
            },
        ],
    )

    assert repository.authorize_local_session(core_token) is not None
    assert repository.authorize_local_session(member_token) is None
    assert repository.authorize_local_session(other_token) is not None
    assert repository.principal_for("user-member").role is MemberRole.GUEST


def test_access_epoch_change_revokes_every_local_session(identity_repository):
    _, repository = identity_repository
    _bind(repository)
    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=4,
    )
    core_token, _ = repository.create_local_session("user-core")
    member_token, _ = repository.create_local_session("user-member")

    repository.apply_access_projection(
        installation_id="installation-1",
        cloud_device_id="device-1",
        organization_id="household-1",
        device_status="active",
        access_epoch=4,
        memberships=[
            {
                "user_id": "user-core",
                "role": "core",
                "status": "active",
                "membership_epoch": 3,
            },
            {
                "user_id": "user-member",
                "role": "member",
                "status": "active",
                "membership_epoch": 4,
            },
        ],
    )

    assert repository.authorize_local_session(core_token) is None
    assert repository.authorize_local_session(member_token) is None


def test_local_session_epoch_change_revokes_every_local_session(identity_repository):
    _, repository = identity_repository
    _bind(repository)
    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=4,
    )
    core_token, _ = repository.create_local_session("user-core")
    member_token, _ = repository.create_local_session("user-member")

    repository.apply_access_projection(
        installation_id="installation-1",
        cloud_device_id="device-1",
        organization_id="household-1",
        device_status="active",
        access_epoch=3,
        local_session_epoch=2,
        memberships=[
            {
                "user_id": "user-core",
                "role": "core",
                "status": "active",
                "membership_epoch": 3,
                "account_session_epoch": 1,
            },
            {
                "user_id": "user-member",
                "role": "member",
                "status": "active",
                "membership_epoch": 4,
                "account_session_epoch": 1,
            },
        ],
    )

    assert repository.authorize_local_session(core_token) is None
    assert repository.authorize_local_session(member_token) is None


def test_account_session_epoch_change_revokes_only_that_user(identity_repository):
    _, repository = identity_repository
    _bind(repository)
    repository.upsert_membership(
        cloud_user_id="user-member",
        role=MemberRole.MEMBER,
        status="active",
        membership_epoch=4,
    )
    core_token, _ = repository.create_local_session("user-core")
    member_token, _ = repository.create_local_session("user-member")

    repository.apply_access_projection(
        installation_id="installation-1",
        cloud_device_id="device-1",
        organization_id="household-1",
        device_status="active",
        access_epoch=3,
        local_session_epoch=1,
        memberships=[
            {
                "user_id": "user-core",
                "role": "core",
                "status": "active",
                "membership_epoch": 3,
                "account_session_epoch": 1,
            },
            {
                "user_id": "user-member",
                "role": "member",
                "status": "active",
                "membership_epoch": 4,
                "account_session_epoch": 2,
            },
        ],
    )

    assert repository.authorize_local_session(core_token) is not None
    assert repository.authorize_local_session(member_token) is None


def test_binding_refresh_revokes_sessions_when_access_epoch_changes(
    identity_repository,
):
    _, repository = identity_repository
    _bind(repository)
    token, _ = repository.create_local_session("user-core")

    repository.bind_installation(
        installation_id="installation-1",
        cloud_device_id="device-1",
        organization_id="household-1",
        organization_type=OrganizationType.HOUSEHOLD,
        core_user_id="user-core",
        billing_account_id="billing-core",
        access_epoch=4,
        core_membership_epoch=3,
    )

    assert repository.authorize_local_session(token) is None
