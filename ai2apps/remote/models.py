"""Local-only records for AI2Apps Remote Access v1."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class RemoteDeviceRecord:
    device_id: str
    display_name: str
    platform: str
    client_version: str
    status: str
    suspension_reason: str | None
    access_epoch: int
    public_origin: str
    credential_version: int
    credential_expires_at: datetime
    server_addr: str
    server_port: int
    proxy_name: str
    subdomain: str
    secret_backend_key: str
    enabled: bool
    online: bool
    proxy_connected: bool
    last_seen_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class RemoteMobileSession:
    token_digest: str
    device_id: str
    owner_user_id: str
    access_epoch: int
    created_at: datetime
    expires_at: datetime
    last_access_check_at: datetime
