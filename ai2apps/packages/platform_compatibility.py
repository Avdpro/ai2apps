"""OS release identity shared by Registry and Service variant checks."""
import platform


def normalized_architecture(value: str) -> str:
    value = value.lower()
    return {"aarch64": "arm64", "amd64": "x64", "x86_64": "x64"}.get(value, value)


def local_os_version(local_platform: str) -> str:
    if local_platform in {"darwin", "macos"}:
        return platform.mac_ver()[0]
    if local_platform == "linux":
        # Compare userland release (Ubuntu 24.04), not a vendor kernel suffix.
        try:
            return platform.freedesktop_os_release().get("VERSION_ID", "")
        except OSError:
            return ""
    return platform.release()
