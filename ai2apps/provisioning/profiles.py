"""Trusted, declarative ACPF App recommendation profiles."""

from __future__ import annotations

import platform
from pathlib import Path
from typing import Any

import psutil
import yaml

_PRESENTATION_FIELDS = {
    "eyebrow",
    "title",
    "description",
    "icon",
    "confirm_label",
    "ready_label",
}
_STEP_IDS = {"runtime", "provider", "checkpoint", "verify"}
_COMPONENT_PHASES = _STEP_IDS
_COMPONENT_FIELDS = {
    "package": {
        "id",
        "kind",
        "phase",
        "package_id",
        "service_key",
        "version",
    },
    "checkpoint": {"id", "kind", "phase", "model_id"},
    "verify": {"id", "kind", "phase", "service_key", "capabilities"},
}


class CapabilityProfileError(ValueError):
    """A trusted App shipped an invalid provisioning profile."""


def _validated_presentation(value: Any, path: Path) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise CapabilityProfileError(f"Invalid ACPF presentation: {path}")
    unknown = set(value) - (_PRESENTATION_FIELDS | {"steps"})
    if unknown:
        raise CapabilityProfileError(
            f"Unknown ACPF presentation fields {sorted(unknown)}: {path}"
        )
    result: dict[str, Any] = {}
    for field in _PRESENTATION_FIELDS:
        item = value.get(field)
        if item is None:
            continue
        if not isinstance(item, str) or not item.strip() or len(item) > 240:
            raise CapabilityProfileError(
                f"Invalid ACPF presentation field {field}: {path}"
            )
        if field == "icon" and not all(
            character.isalnum() or character == "-" for character in item
        ):
            raise CapabilityProfileError(f"Invalid ACPF presentation icon: {path}")
        result[field] = item.strip()
    steps = value.get("steps")
    if steps is not None:
        if not isinstance(steps, dict) or set(steps) - _STEP_IDS:
            raise CapabilityProfileError(f"Invalid ACPF presentation steps: {path}")
        normalized_steps: dict[str, str] = {}
        for step_id, label in steps.items():
            if not isinstance(label, str) or not label.strip() or len(label) > 160:
                raise CapabilityProfileError(
                    f"Invalid ACPF presentation step {step_id}: {path}"
                )
            normalized_steps[step_id] = label.strip()
        result["steps"] = normalized_steps
    return result


def _validated_component_profile(value: dict[str, Any], path: Path) -> dict[str, Any]:
    stack = value.get("stack")
    if not isinstance(stack, dict) or "components" not in stack:
        return value
    if set(stack) != {"components"}:
        raise CapabilityProfileError(
            f"Generic ACPF stack only accepts components: {path}"
        )
    components = stack["components"]
    if not isinstance(components, list) or not 1 <= len(components) <= 16:
        raise CapabilityProfileError(f"Invalid ACPF component stack: {path}")
    seen: set[str] = set()
    normalized = []
    for component in components:
        if not isinstance(component, dict):
            raise CapabilityProfileError(f"Invalid ACPF component: {path}")
        kind = component.get("kind")
        allowed = _COMPONENT_FIELDS.get(kind)
        if allowed is None or set(component) - allowed:
            raise CapabilityProfileError(f"Invalid ACPF {kind} component: {path}")
        component_id = component.get("id")
        phase = component.get("phase", kind)
        if (
            not isinstance(component_id, str)
            or not component_id
            or component_id in seen
            or phase not in _COMPONENT_PHASES
        ):
            raise CapabilityProfileError(f"Invalid ACPF component identity: {path}")
        seen.add(component_id)
        required_strings = {
            "package": ("package_id", "service_key", "version"),
            "checkpoint": ("model_id",),
            "verify": ("service_key",),
        }[kind]
        if any(
            not isinstance(component.get(field), str) or not component[field]
            for field in required_strings
        ):
            raise CapabilityProfileError(f"Incomplete ACPF {kind} component: {path}")
        capabilities = component.get("capabilities", ())
        if kind == "verify" and (
            not isinstance(capabilities, list)
            or not capabilities
            or not all(isinstance(item, str) and item for item in capabilities)
        ):
            raise CapabilityProfileError(f"Invalid ACPF verify capabilities: {path}")
        normalized.append({**component, "phase": phase})
    return {**value, "stack": {"components": normalized}}


def device_profile() -> dict[str, Any]:
    """Return stable capacity facts without using momentary free memory."""

    system = platform.system().lower()
    os_family = {"darwin": "macos"}.get(system, system)
    machine = platform.machine().lower()
    total = int(psutil.virtual_memory().total)
    if os_family == "macos" and machine == "arm64":
        accelerator = {
            "vendor": "apple",
            "api": "metal",
            "unified_memory_gib": total / (1024**3),
        }
    else:
        accelerator = {"vendor": "unknown", "api": "unknown"}
    return {
        "schema": "ai2apps.device-profile/v1",
        "os": os_family,
        "architecture": machine,
        "system_memory_gib": total / (1024**3),
        "accelerator": accelerator,
    }


def _memory_matches(value: float | None, bounds: Any) -> bool:
    if not isinstance(bounds, dict) or value is None:
        return not isinstance(bounds, dict)
    minimum = bounds.get("minimum")
    maximum = bounds.get("maximum_exclusive")
    return not (
        (minimum is not None and value < float(minimum))
        or (maximum is not None and value >= float(maximum))
    )


def profile_matches_device(
    profile: dict[str, Any], device: dict[str, Any], *, recommended: bool
) -> bool:
    if recommended and profile.get("recommended") is False:
        return False
    rule = profile.get("device", {})
    if device.get("os") not in rule.get("os", (device.get("os"),)):
        return False
    if device.get("architecture") not in rule.get(
        "architectures", (device.get("architecture"),)
    ):
        return False
    wanted = rule.get("accelerator", {})
    actual = device.get("accelerator", {})
    for field in ("vendor", "api"):
        if wanted.get(field) is not None and wanted[field] != actual.get(field):
            return False
    if not _memory_matches(
        actual.get("unified_memory_gib"), wanted.get("unified_memory_gib")
    ):
        return False
    return not recommended or _memory_matches(
        actual.get("unified_memory_gib"), profile.get("recommendation_memory_gib")
    )


def profile_device_compatibility(
    profile: dict[str, Any], device: dict[str, Any]
) -> tuple[bool, tuple[str, ...]]:
    """Explain hard device constraints independently from recommendation bands."""

    reasons: list[str] = []
    rule = profile.get("device", {})
    if device.get("os") not in rule.get("os", (device.get("os"),)):
        reasons.append("当前操作系统不受支持")
    if device.get("architecture") not in rule.get(
        "architectures", (device.get("architecture"),)
    ):
        reasons.append("当前处理器架构不受支持")
    wanted = rule.get("accelerator", {})
    actual = device.get("accelerator", {})
    if wanted.get("vendor") is not None and wanted["vendor"] != actual.get("vendor"):
        reasons.append(f"需要 {wanted['vendor']} 加速器")
    if wanted.get("api") is not None and wanted["api"] != actual.get("api"):
        reasons.append(f"需要 {wanted['api']} 加速 API")
    bounds = wanted.get("unified_memory_gib")
    memory = actual.get("unified_memory_gib")
    if isinstance(bounds, dict) and memory is None:
        reasons.append("无法确认设备统一内存")
    elif isinstance(bounds, dict):
        minimum = bounds.get("minimum")
        maximum = bounds.get("maximum_exclusive")
        if minimum is not None and float(memory) < float(minimum):
            reasons.append(f"至少需要 {float(minimum):g} GiB 统一内存")
        if maximum is not None and float(memory) >= float(maximum):
            reasons.append(f"仅支持低于 {float(maximum):g} GiB 统一内存的设备")
    return not reasons, tuple(reasons)


class CapabilityProfileRegistry:
    """Load signed-equivalent built-in profiles through one strict parser."""

    def __init__(self, roots: tuple[Path, ...] | None = None) -> None:
        self.roots = roots or (Path(__file__).with_name("profiles"),)
        self._capabilities: dict[tuple[str, str], dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        capabilities: dict[tuple[str, str], dict[str, Any]] = {}
        for root in self.roots:
            if not root.exists():
                continue
            for path in sorted(root.glob("*.yaml")):
                try:
                    document = yaml.safe_load(path.read_text(encoding="utf-8"))
                except (OSError, yaml.YAMLError) as exc:
                    raise CapabilityProfileError(
                        f"Invalid ACPF profile: {path}"
                    ) from exc
                if (
                    not isinstance(document, dict)
                    or document.get("schema") != "ai2apps.capability-profiles/v1"
                ):
                    raise CapabilityProfileError(f"Unsupported ACPF schema: {path}")
                app_id = document.get("app_id")
                entries = document.get("capabilities")
                if not isinstance(app_id, str) or not isinstance(entries, dict):
                    raise CapabilityProfileError(f"Incomplete ACPF profile: {path}")
                for capability, value in entries.items():
                    if not isinstance(capability, str) or not isinstance(value, dict):
                        raise CapabilityProfileError(f"Invalid ACPF capability: {path}")
                    profiles = value.get("profiles")
                    if not isinstance(profiles, list) or not profiles:
                        raise CapabilityProfileError(
                            f"ACPF capability has no profiles: {path}"
                        )
                    normalized_profiles = [
                        _validated_component_profile(profile, path)
                        if isinstance(profile, dict)
                        else profile
                        for profile in profiles
                    ]
                    key = (app_id, capability)
                    if key in capabilities:
                        raise CapabilityProfileError(
                            f"Duplicate ACPF capability: {key}"
                        )
                    capabilities[key] = {
                        **value,
                        "profiles": normalized_profiles,
                        "presentation": _validated_presentation(
                            value.get("presentation"), path
                        ),
                        "app_id": app_id,
                        "capability": capability,
                    }
        self._capabilities = capabilities

    def capability(self, app_id: str, capability: str) -> dict[str, Any] | None:
        value = self._capabilities.get((app_id, capability))
        return None if value is None else dict(value)

    def candidates(
        self,
        app_id: str,
        capability: str,
        device: dict[str, Any],
        *,
        recommended: bool,
    ) -> tuple[dict[str, Any], ...]:
        entry = self.capability(app_id, capability)
        if entry is None:
            return ()
        result = [
            dict(profile)
            for profile in entry["profiles"]
            if isinstance(profile, dict)
            and profile_matches_device(profile, device, recommended=recommended)
        ]
        return tuple(
            sorted(result, key=lambda item: int(item.get("priority", 0)), reverse=True)
        )
