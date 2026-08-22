"""Role-to-capability policy for entering and controlling AI2Apps Apps."""

from __future__ import annotations

from typing import Any

from ai2apps.identity import MemberRole, RequestPrincipal

APP_USE = "app.use"
APP_CHAT_USE = "app.chat.use"
APP_CODER_USE = "app.coder.use"
APP_SYSTEM_MANAGE = "app.system.manage"
APP_SHARING_MANAGE = "app.sharing.manage"

_ROLE_CAPABILITIES: dict[MemberRole, frozenset[str]] = {
    MemberRole.CORE: frozenset({"*"}),
    MemberRole.OWNER: frozenset({"*"}),
    MemberRole.ADMIN: frozenset(
        {APP_USE, APP_CHAT_USE, APP_CODER_USE, APP_SYSTEM_MANAGE}
    ),
    MemberRole.DEVELOPER: frozenset({APP_USE, APP_CHAT_USE, APP_CODER_USE}),
    MemberRole.MEMBER: frozenset({APP_USE, APP_CHAT_USE}),
    MemberRole.CHILD: frozenset({APP_USE, APP_CHAT_USE}),
    MemberRole.GUEST: frozenset({APP_USE, APP_CHAT_USE}),
}


def required_app_capabilities(manifest: dict[str, Any]) -> frozenset[str]:
    """Read fail-closed App access requirements; third-party Apps default open."""

    access = manifest.get("access")
    if access is None:
        return frozenset({APP_USE})
    if not isinstance(access, dict):
        return frozenset({"app.invalid-access-contract"})
    values = access.get("capabilities")
    if not isinstance(values, list) or not values:
        return frozenset({"app.invalid-access-contract"})
    capabilities = frozenset(
        value for value in values if isinstance(value, str) and value
    )
    if len(capabilities) != len(values):
        return frozenset({"app.invalid-access-contract"})
    return capabilities


def can_access_app(principal: RequestPrincipal, manifest: dict[str, Any]) -> bool:
    granted = _ROLE_CAPABILITIES[principal.role]
    required = required_app_capabilities(manifest)
    return "*" in granted or required.issubset(granted)


def has_app_capability(principal: RequestPrincipal, capability: str) -> bool:
    """Return whether a principal may invoke a protected App backend surface."""

    granted = _ROLE_CAPABILITIES[principal.role]
    return "*" in granted or capability in granted
