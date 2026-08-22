"""Records exposed by a downstream Local for configured upstream gateways."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class UpstreamGateway:
    id: str
    label: str
    openai_base_url: str
    mcp_url: str
    transport_kind: str
    downstream_installation_id: str | None
    node_link_id: str | None
    remote_node_id: str | None
    ancestor_node_ids: tuple[str, ...]
    is_parent: bool
    is_default: bool
    priority: int
    route_models: bool
    route_mcp: bool
    status: str
    health_status: str
    capabilities: dict[str, Any]
    last_error: str | None
    last_checked_at: datetime | None
    created_by_user_id: str
    revision: int
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class UpstreamRouting:
    model_policy: str
    revision: int
    updated_by_user_id: str
    created_at: datetime
    updated_at: datetime
