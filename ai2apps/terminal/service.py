"""Register the interactive terminal as a built-in AI2Apps Service."""

from __future__ import annotations

from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
)

from .manager import TerminalManager


def install_terminal_service(
    manager: TerminalManager,
    repository: ServiceRepository,
    registry: ServiceRegistry,
) -> None:
    service = repository.ensure_service(
        service_key="ai2apps.terminal",
        package_id="ai2apps.terminal",
        package_version="1.0.0",
        display_name="AI2Apps Terminal Service",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("terminal", "pty", "host-shell"),
        config={
            "transport": "websocket",
            "session_limit": manager.max_sessions,
            "backlog_bytes": manager.backlog_limit,
        },
    )
    repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:terminal",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/admin/api/terminal/sessions",
        health={"status": "ok", "pty": True},
    )
