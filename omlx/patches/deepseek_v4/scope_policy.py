"""Explicit DeepSeek V4 scope-policy configuration.

The first cache implementation intentionally requires an explicit profile path
and scope name.  Scope classification and multi-scope engine sharing are
separate concerns and must not silently change expert residency.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path


PROFILE_ENV = "OMLX_DEEPSEEK_V4_SCOPE_PROFILE"
SCOPE_ENV = "OMLX_DEEPSEEK_V4_SCOPE_NAME"
STORE_ENV = "OMLX_DEEPSEEK_V4_EXPERT_STORE"
LOSSY_MODE_ENV = "OMLX_DEEPSEEK_V4_SCOPE_LOSSY_MODE"
LOSSY_THRESHOLD_ENV = "OMLX_DEEPSEEK_V4_SCOPE_LOSSY_THRESHOLD"
PROBE_DEPTH_ENV = "OMLX_DEEPSEEK_V4_SCOPE_PROBE_DEPTH"
DEFAULT_PROBE_DEPTH = 16
MAX_PROBE_DEPTH = 43
_resident_experts_override = 60
_scope_policy_override: tuple[str, str, str] | None = None
_scope_policy_disabled = False


def configure_scope_resident_experts(count: int) -> None:
    """Configure the physical scope bank before constructing a model."""

    if count not in (20, 40, 60, 256):
        raise ValueError(
            "DeepSeek scope resident experts must be 20, 40, 60, or 256"
        )
    global _resident_experts_override
    _resident_experts_override = count
    load_scope_policy_from_env.cache_clear()


def configure_scope_policy(
    profile_path: str | Path,
    scope_name: str,
    store_path: str | Path,
    resident_experts: int,
) -> None:
    """Select a model-local Scope Pack without mutating process environment."""

    configure_scope_resident_experts(resident_experts)
    global _scope_policy_disabled, _scope_policy_override
    _scope_policy_disabled = False
    _scope_policy_override = (
        str(Path(profile_path).expanduser()),
        str(scope_name),
        str(Path(store_path).expanduser()),
    )
    load_scope_policy_from_env.cache_clear()


def clear_scope_policy_override() -> None:
    """Return policy selection to the legacy environment configuration."""

    global _scope_policy_disabled, _scope_policy_override
    _scope_policy_disabled = False
    _scope_policy_override = None
    load_scope_policy_from_env.cache_clear()


def disable_scope_policy() -> None:
    """Force full-resident execution even when legacy env vars are present."""

    global _scope_policy_disabled, _scope_policy_override
    _scope_policy_disabled = True
    _scope_policy_override = None
    load_scope_policy_from_env.cache_clear()


@cache
def load_scope_probe_depth_from_env() -> int:
    """Return the shared-only scope probe depth, defaulting to 16 layers."""

    raw = os.environ.get(PROBE_DEPTH_ENV, str(DEFAULT_PROBE_DEPTH)).strip()
    try:
        depth = int(raw)
    except ValueError as exc:
        raise ValueError(f"{PROBE_DEPTH_ENV} must be an integer") from exc
    if not 4 <= depth <= MAX_PROBE_DEPTH:
        raise ValueError(
            f"{PROBE_DEPTH_ENV} must be between 4 and {MAX_PROBE_DEPTH}; "
            f"got {depth}"
        )
    return depth


@dataclass(frozen=True)
class ScopeLossyPolicy:
    """Device-side approximation policy for low-priority Decode routes."""

    mode: str
    tail_count: int
    max_weight_share: float | None


@cache
def load_scope_lossy_policy_from_env() -> ScopeLossyPolicy | None:
    """Parse the opt-in lossy policy without changing Exact defaults.

    ``conservative`` considers the two lowest-weight Top-K routes and only
    replaces misses whose normalized routing share is at most the configured
    threshold. ``tail1`` and ``tail2`` replace the lowest one or two misses
    without a weight threshold. ``head2`` protects only the two highest-weight
    routes and replaces misses in the remaining four.
    """

    raw = os.environ.get(LOSSY_MODE_ENV, "")
    threshold = os.environ.get(LOSSY_THRESHOLD_ENV, "0.10")
    return scope_lossy_policy_for_mode(raw, threshold=threshold)


def scope_lossy_policy_for_mode(
    raw: str | None,
    *,
    threshold: str | float = "0.10",
) -> ScopeLossyPolicy | None:
    """Parse a lossy policy without mutating process-global environment."""

    raw = (raw or "").strip().lower().replace("_", "-")
    if raw in ("", "0", "off", "false", "exact"):
        return None
    aliases = {
        "safe": "conservative",
        "aggressive-1": "tail1",
        "aggressive1": "tail1",
        "aggressive-2": "tail2",
        "aggressive2": "tail2",
        "protect2": "head2",
    }
    mode = aliases.get(raw, raw)
    if mode not in ("conservative", "tail1", "tail2", "head2"):
        raise ValueError(
            f"{LOSSY_MODE_ENV} must be exact, conservative, tail1, tail2, "
            f"or head2; got {raw!r}"
        )
    if mode == "conservative":
        try:
            threshold_value = float(threshold)
        except ValueError as exc:
            raise ValueError(
                f"{LOSSY_THRESHOLD_ENV} must be a floating-point value"
            ) from exc
        if not 0.0 <= threshold_value <= 1.0:
            raise ValueError(f"{LOSSY_THRESHOLD_ENV} must be between 0 and 1")
        return ScopeLossyPolicy(
            mode, tail_count=2, max_weight_share=threshold_value
        )
    return ScopeLossyPolicy(
        mode,
        tail_count={"tail1": 1, "tail2": 2, "head2": 4}[mode],
        max_weight_share=None,
    )


@dataclass(frozen=True)
class ScopePolicy:
    profile_path: Path
    scope_name: str
    store_path: Path
    experts_by_layer: tuple[tuple[int, ...], ...]
    resident_experts: int

    def experts(self, layer: int) -> tuple[int, ...]:
        return self.experts_by_layer[layer]


@cache
def load_scope_policy_from_env() -> ScopePolicy | None:
    if _scope_policy_disabled:
        return None
    if _scope_policy_override is not None:
        raw_profile, raw_scope, raw_store = _scope_policy_override
    else:
        raw_profile = os.environ.get(PROFILE_ENV, "").strip()
        raw_scope = os.environ.get(SCOPE_ENV, "").strip()
        raw_store = os.environ.get(STORE_ENV, "").strip()
    configured = [bool(raw_profile), bool(raw_scope), bool(raw_store)]
    if not any(configured):
        return None
    if not all(configured):
        raise ValueError(
            f"{PROFILE_ENV}, {SCOPE_ENV}, and {STORE_ENV} must be set together"
        )

    profile_path = Path(raw_profile).expanduser().resolve()
    store_path = Path(raw_store).expanduser().resolve()
    profile = json.loads(profile_path.read_text())
    if profile.get("format") != "dmoe-deepseek-tiered-policy":
        raise ValueError(f"unsupported DeepSeek scope profile: {profile_path}")
    scopes = profile.get("scopes", {})
    if raw_scope not in scopes:
        raise ValueError(
            f"scope {raw_scope!r} not present in {profile_path}; "
            f"available={sorted(scopes)}"
        )
    if not store_path.is_dir():
        raise FileNotFoundError(f"expert-major store not found: {store_path}")

    experts_by_layer: list[tuple[int, ...]] = []
    scope_layers = scopes[raw_scope]
    for layer in range(43):
        if _resident_experts_override == 256 or layer < 3:
            experts = tuple(range(256))
        else:
            try:
                experts = tuple(int(value) for value in scope_layers[str(layer)])
            except KeyError as exc:
                raise ValueError(
                    f"scope profile is missing score layer {layer}"
                ) from exc
            if len(experts) < _resident_experts_override:
                raise ValueError(
                    f"scope layer {layer} has fewer than "
                    f"{_resident_experts_override} experts"
                )
            experts = experts[:_resident_experts_override]
            if len(set(experts)) != len(experts):
                raise ValueError(f"scope layer {layer} contains duplicate experts")
            if min(experts) < 0 or max(experts) >= 256:
                raise ValueError(f"scope layer {layer} has invalid expert IDs")
        experts_by_layer.append(experts)

    return ScopePolicy(
        profile_path=profile_path,
        scope_name=raw_scope,
        store_path=store_path,
        experts_by_layer=tuple(experts_by_layer),
        resident_experts=_resident_experts_override,
    )


def parse_expert_key(key: str) -> tuple[int, int] | None:
    marker = ".ffn.experts."
    if marker not in key:
        return None
    prefix, tail = key.split(marker, 1)
    try:
        layer = int(prefix.rsplit(".", 1)[1])
        expert = int(tail.split(".", 1)[0])
    except (IndexError, ValueError):
        return None
    return layer, expert
