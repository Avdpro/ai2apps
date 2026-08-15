"""Built-in App definitions shared by the runtime and WebUI Shell."""

from .system import SYSTEM_APP_MANIFESTS, ensure_system_apps

__all__ = ["SYSTEM_APP_MANIFESTS", "ensure_system_apps"]
