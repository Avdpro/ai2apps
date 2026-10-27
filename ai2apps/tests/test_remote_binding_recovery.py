"""Recovery repairs only a Cloud-authorized existing Installation, never data."""
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from ai2apps.identity import IdentityRepository, MemberRole, OrganizationType
from ai2apps.remote.manager import RemoteAccessManager, RemoteAccessError
from ai2apps.remote.repository import RemoteDeviceRepository
from ai2apps.storage import PlatformDatabase


@pytest.fixture
def recovery(tmp_path):
    db = PlatformDatabase(tmp_path/'platform.sqlite3'); db.initialize()
    identities = IdentityRepository(db)
    identities.bind_installation(installation_id='install-1', cloud_device_id='device-1',
        organization_id='org-1', organization_type=OrganizationType.HOUSEHOLD,
        core_user_id='owner-1', billing_account_id='billing-1', access_epoch=2,
        local_session_epoch=3, core_role=MemberRole.CORE)
    identities.deactivate_installation('suspended')
    detail = dict(installationId='install-1', cloudDeviceId='device-1', organizationId='org-1',
        organizationType='household', coreUserId='owner-1', billingAccountId='billing-1',
        accessEpoch=2, localSessionEpoch=3, membershipEpoch=2, role='core')
    device = dict(id='device-1', status='active')
    manager = RemoteAccessManager(cloud=NS(), repository=RemoteDeviceRepository(db), secret_backend=NS(),
        client_version='test', identity_repository=identities)
    async def request(method, path, **kw):
        assert method=='GET'
        return detail if path=='/v1/installations/install-1' else device
    manager._request=AsyncMock(side_effect=request)
    manager.rotate=AsyncMock()
    async def sync(**kw):
        assert kw['device_id']=='device-1' and kw['installation_id']=='install-1'
        identities.bind_installation(installation_id='install-1', cloud_device_id='device-1',
            organization_id='org-1', organization_type=OrganizationType.HOUSEHOLD,
            core_user_id='owner-1', billing_account_id='billing-1', access_epoch=2,
            local_session_epoch=3, core_role=MemberRole.CORE)
    manager.sync_installation_identity=AsyncMock(side_effect=sync)
    manager._refresh_access_projection=AsyncMock(return_value=True)
    return manager, identities, detail, device


@pytest.mark.asyncio
async def test_recovery_retains_installation_identity_and_verifies_device(recovery):
    manager, identities, _, _ = recovery
    before=identities.get_installation()
    await manager._recover_suspended_binding(cloud=manager.cloud)
    after=identities.get_installation()
    assert after.id==before.id and after.core_user_id==before.core_user_id and after.status=='active'
    manager.rotate.assert_awaited_once_with('device-1',cloud=manager.cloud)
    manager._refresh_access_projection.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize('field,value', [('cloudDeviceId','other'),('coreUserId','other'),
    ('organizationId','other'),('role','member'),('accessEpoch',1),('localSessionEpoch',2),('status','revoked')])
async def test_recovery_rejects_changed_authority_or_inactive_installation(recovery,field,value):
    manager, identities, detail, _ = recovery
    detail[field]=value
    with pytest.raises(RemoteAccessError):await manager._recover_suspended_binding(cloud=manager.cloud)
    assert identities.get_installation().status=='suspended'
    manager.rotate.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('status',['revoked','suspended'])
async def test_recovery_does_not_revive_cloud_device(recovery,status):
    manager, identities, _, device = recovery
    device['status']=status
    with pytest.raises(RemoteAccessError):await manager._recover_suspended_binding(cloud=manager.cloud)
    assert identities.get_installation().status=='suspended'
    manager.rotate.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_device_verification_fails_closed(recovery):
    manager, identities, _, _ = recovery
    manager._refresh_access_projection.side_effect=RemoteAccessError(403,'REMOTE_DEVICE_AUTHORIZATION_DENIED','denied')
    with pytest.raises(RemoteAccessError):await manager._recover_suspended_binding(cloud=manager.cloud)
    assert identities.get_installation().status=='suspended'


@pytest.mark.asyncio
async def test_parallel_recovery_rotates_only_once(recovery):
    manager, identities, _, _ = recovery
    await asyncio.gather(*(manager._recover_suspended_binding(cloud=manager.cloud) for _ in range(3)))
    manager.rotate.assert_awaited_once()
    assert identities.get_installation().status=='active'


@pytest.mark.asyncio
async def test_normal_core_activation_recovers_before_handoff(recovery):
    import httpx
    manager, identities, _, _ = recovery
    browser = NS(request=AsyncMock(return_value=httpx.Response(201, json={
        'redirectUrl':'ai2apps://auth/complete#handoff=existing-installation-once-only-handoff'})))
    manager.exchange_member_handoff=AsyncMock(return_value=('cookie','verified-principal'))
    assert await manager.activate_current_cloud_member(cloud=browser)==('cookie','verified-principal')
    assert identities.get_installation().status=='active'
    manager.rotate.assert_awaited_once_with('device-1',cloud=browser)
    manager.exchange_member_handoff.assert_awaited_once_with(handoff='existing-installation-once-only-handoff')


@pytest.mark.asyncio
async def test_revoked_local_binding_is_not_auto_recovered(recovery):
    manager, identities, _, _ = recovery
    identities.deactivate_installation('revoked')
    with pytest.raises(RemoteAccessError) as error:
        await manager.activate_current_cloud_member(cloud=manager.cloud)
    assert error.value.code=='INSTALLATION_NOT_BOUND'
    manager._request.assert_not_awaited()
    manager.rotate.assert_not_awaited()
