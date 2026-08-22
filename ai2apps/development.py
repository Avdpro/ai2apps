"""Fail-closed detection for source-checkout-only developer surfaces."""

from __future__ import annotations

from pathlib import Path


def is_source_development_runtime(root: Path | None = None) -> bool:
    """Return whether AI2Apps is executing from its Git source checkout.

    Wheel/pip and macOS client installations intentionally return ``False``.
    The check is structural rather than account-based so production installs
    cannot expose internal model/runtime tools merely because the device owner
    signed in.
    """

    project_root = (
        Path(root).resolve()
        if root is not None
        else Path(__file__).resolve().parents[1]
    )
    return all(
        (
            (project_root / ".git").exists(),
            (project_root / "pyproject.toml").is_file(),
            (project_root / "ai2apps").is_dir(),
            (project_root / "omlx").is_dir(),
        )
    )


def can_access_developer_surfaces(principal: object, root: Path | None = None) -> bool:
    """Allow internal surfaces only to this checkout's unique Core identity."""

    if not is_source_development_runtime(root):
        return False
    if isinstance(principal, bool):
        return principal
    role = getattr(principal, "role", None)
    return getattr(role, "value", role) == "core"
