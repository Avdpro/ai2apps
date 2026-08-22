"""AI2Apps Remote Access v1 client integration."""

from .frpc import PINNED_FRP_VERSION, RemoteFrpcConfig, RemoteFrpcSupervisor
from .manager import RemoteAccessError, RemoteAccessManager
from .models import RemoteDeviceRecord, RemoteMobileSession
from .repository import RemoteDeviceRepository
from .security import (
    RemoteTokenError,
    verify_federation_relay_token,
    verify_installation_member_token,
    verify_remote_token,
)

__all__ = [
    "RemoteAccessError", "RemoteAccessManager", "RemoteDeviceRecord",
    "RemoteDeviceRepository", "RemoteMobileSession", "RemoteTokenError",
    "verify_federation_relay_token", "verify_installation_member_token", "verify_remote_token",
    "PINNED_FRP_VERSION", "RemoteFrpcConfig", "RemoteFrpcSupervisor",
]
