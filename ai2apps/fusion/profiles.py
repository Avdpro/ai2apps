"""Serializable Fusion profiles and an in-process oMLX engine factory."""

from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Mapping

from .types import FailurePolicy, FusionConfig

if TYPE_CHECKING:
    from .omlx_engine import FusionEngine


@dataclass(frozen=True)
class RoleConfig:
    backend: str
    model: str
    base_url: str | None = None
    credential_ref: str | None = None
    max_tokens: int = 384
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        if self.backend not in {"local", "openai-compatible"}:
            raise ValueError("role backend must be local or openai-compatible")
        if not self.model:
            raise ValueError("role model is required")
        if self.backend == "openai-compatible" and (
            not self.base_url or not self.credential_ref
        ):
            raise ValueError(
                "openai-compatible role requires base_url and credential_ref"
            )
        if self.max_tokens < 1 or self.timeout_seconds <= 0:
            raise ValueError("role token limit and timeout must be positive")


@dataclass(frozen=True)
class ResolverConfig:
    enabled: bool = False
    role: RoleConfig | None = None
    triggers: tuple[str, ...] = (
        "reviewer_escalate",
        "reviewer_uncertain",
        "patch_failed",
    )
    failure_policy: FailurePolicy = FailurePolicy.LOCAL_REBUILD

    def __post_init__(self) -> None:
        if self.enabled and self.role is None:
            raise ValueError("enabled resolver requires a role configuration")


@dataclass(frozen=True)
class FusionProfile:
    model_id: str
    generator: RoleConfig
    reviewer: RoleConfig
    resolver: ResolverConfig = field(default_factory=ResolverConfig)
    gate: Mapping[str, Any] = field(default_factory=dict)
    max_changed_ratio: float = 0.30
    ordinary_failure_policy: FailurePolicy = FailurePolicy.RETURN_DRAFT
    high_risk_failure_policy: FailurePolicy = FailurePolicy.ERROR

    def __post_init__(self) -> None:
        if not self.model_id:
            raise ValueError("Fusion profile model_id is required")
        if self.generator.backend != "local":
            raise ValueError("Fusion generator must use the local backend")
        if self.resolver.enabled and self.reviewer.backend != "local":
            raise ValueError(
                "three-stage Fusion requires a local reviewer before the resolver"
            )
        if not 0 < self.max_changed_ratio <= 1:
            raise ValueError("max_changed_ratio must be in (0, 1]")

    @property
    def fingerprint(self) -> str:
        payload = profile_to_mapping(self)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def engine_config(self) -> FusionConfig:
        allowed = {item.name for item in fields(FusionConfig)}
        explicit = {
            "model_id",
            "resolver_enabled",
            "resolver_triggers",
            "resolver_timeout_seconds",
            "resolver_unavailable_policy",
            "reviewer_timeout_seconds",
            "reviewer_failure_policy",
            "high_risk_failure_policy",
            "max_changed_ratio",
        }
        unknown = set(self.gate) - allowed
        if unknown:
            raise ValueError(f"unknown Fusion gate settings: {sorted(unknown)}")
        gate = {key: value for key, value in self.gate.items() if key in allowed}
        gate = {key: value for key, value in gate.items() if key not in explicit}
        return FusionConfig(
            model_id=self.model_id,
            resolver_enabled=self.resolver.enabled,
            resolver_triggers=self.resolver.triggers,
            resolver_timeout_seconds=(
                self.resolver.role.timeout_seconds
                if self.resolver.role is not None
                else 30.0
            ),
            resolver_unavailable_policy=self.resolver.failure_policy,
            reviewer_timeout_seconds=self.reviewer.timeout_seconds,
            reviewer_failure_policy=self.ordinary_failure_policy,
            high_risk_failure_policy=self.high_risk_failure_policy,
            max_changed_ratio=self.max_changed_ratio,
            **gate,
        )


def _role_from_mapping(value: Mapping[str, Any]) -> RoleConfig:
    return RoleConfig(
        backend=str(value.get("backend", "")),
        model=str(value.get("model", "")),
        base_url=value.get("base_url"),
        credential_ref=value.get("credential_ref"),
        max_tokens=int(value.get("max_tokens", 384)),
        timeout_seconds=float(value.get("timeout_seconds", 30.0)),
    )


def fusion_profile_from_mapping(value: Mapping[str, Any]) -> FusionProfile:
    root = value.get("fusion", value)
    if not isinstance(root, Mapping):
        raise ValueError("Fusion profile must be an object")
    generator = root.get("generator")
    reviewer = root.get("reviewer")
    if not isinstance(generator, Mapping) or not isinstance(reviewer, Mapping):
        raise ValueError("Fusion profile requires generator and reviewer objects")

    raw_resolver = root.get("resolver") or {}
    if not isinstance(raw_resolver, Mapping):
        raise ValueError("Fusion resolver must be an object")
    resolver_enabled = bool(raw_resolver.get("enabled", False))
    resolver_role = _role_from_mapping(raw_resolver) if resolver_enabled else None
    raw_triggers = raw_resolver.get("triggers") or ResolverConfig.triggers
    if not isinstance(raw_triggers, (list, tuple)):
        raise ValueError("resolver triggers must be a list")

    gate = root.get("gate") or {}
    if not isinstance(gate, Mapping):
        raise ValueError("Fusion gate must be an object")
    return FusionProfile(
        model_id=str(root.get("model_id", "")),
        generator=_role_from_mapping(generator),
        reviewer=_role_from_mapping(reviewer),
        resolver=ResolverConfig(
            enabled=resolver_enabled,
            role=resolver_role,
            triggers=tuple(str(item) for item in raw_triggers),
            failure_policy=FailurePolicy(
                str(raw_resolver.get("failure_policy", "local_rebuild"))
            ),
        ),
        gate=dict(gate),
        max_changed_ratio=float(root.get("max_changed_ratio", 0.30)),
        ordinary_failure_policy=FailurePolicy(
            str(root.get("ordinary_failure_policy", "return_draft"))
        ),
        high_risk_failure_policy=FailurePolicy(
            str(root.get("high_risk_failure_policy", "error"))
        ),
    )


def load_fusion_profile(path: str | Path) -> FusionProfile:
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        import yaml

        value = yaml.safe_load(text)
    else:
        value = json.loads(text)
    if not isinstance(value, Mapping):
        raise ValueError("Fusion profile root must be an object")
    return fusion_profile_from_mapping(value)


def _role_to_mapping(role: RoleConfig) -> dict[str, Any]:
    return {
        "backend": role.backend,
        "model": role.model,
        "base_url": role.base_url,
        "credential_ref": role.credential_ref,
        "max_tokens": role.max_tokens,
        "timeout_seconds": role.timeout_seconds,
    }


def profile_to_mapping(profile: FusionProfile) -> dict[str, Any]:
    resolver = {
        "enabled": profile.resolver.enabled,
        "triggers": list(profile.resolver.triggers),
        "failure_policy": profile.resolver.failure_policy.value,
    }
    if profile.resolver.role is not None:
        resolver.update(_role_to_mapping(profile.resolver.role))
    return {
        "fusion": {
            "model_id": profile.model_id,
            "generator": _role_to_mapping(profile.generator),
            "reviewer": _role_to_mapping(profile.reviewer),
            "resolver": resolver,
            "gate": dict(profile.gate),
            "max_changed_ratio": profile.max_changed_ratio,
            "ordinary_failure_policy": profile.ordinary_failure_policy.value,
            "high_risk_failure_policy": profile.high_risk_failure_policy.value,
        }
    }


LocalEngineLoader = Callable[[str], Any | Awaitable[Any]]
CredentialResolver = Callable[[str], str]


async def _load_local(loader: LocalEngineLoader, model: str) -> Any:
    value = loader(model)
    return await value if inspect.isawaitable(value) else value


def _remote_backend(role: RoleConfig, credentials: CredentialResolver):
    from .adapters import OpenAICompatibleReviewBackend

    assert role.base_url is not None and role.credential_ref is not None
    return OpenAICompatibleReviewBackend(
        base_url=role.base_url,
        model=role.model,
        api_key=credentials(role.credential_ref),
        max_tokens=role.max_tokens,
        timeout_seconds=role.timeout_seconds,
    )


async def build_omlx_fusion_engine(
    profile: FusionProfile,
    *,
    load_local_engine: LocalEngineLoader,
    resolve_credential: CredentialResolver | None = None,
) -> FusionEngine:
    from .adapters import (
        OMLXGeneratorBackend,
        OMLXReviewerBackend,
    )
    from .engine import FusionOrchestrator
    from .omlx_engine import FusionEngine

    generator_engine = await _load_local(load_local_engine, profile.generator.model)
    generator = OMLXGeneratorBackend(generator_engine)
    owned = [generator_engine]

    if profile.reviewer.backend == "local":
        reviewer_engine = await _load_local(load_local_engine, profile.reviewer.model)
        reviewer = OMLXReviewerBackend(
            reviewer_engine, max_tokens=profile.reviewer.max_tokens
        )
        owned.append(reviewer_engine)
    else:
        if resolve_credential is None:
            raise ValueError("remote reviewer requires a credential resolver")
        reviewer = _remote_backend(profile.reviewer, resolve_credential)

    resolver = None
    if profile.resolver.enabled:
        role = profile.resolver.role
        assert role is not None
        if role.backend == "local":
            resolver_engine = await _load_local(load_local_engine, role.model)
            resolver = OMLXReviewerBackend(
                resolver_engine, max_tokens=role.max_tokens
            )
            owned.append(resolver_engine)
        else:
            if resolve_credential is None:
                raise ValueError("remote resolver requires a credential resolver")
            resolver = _remote_backend(role, resolve_credential)

    orchestrator = FusionOrchestrator(
        profile.engine_config(), generator, reviewer, resolver
    )
    return FusionEngine(
        orchestrator, generator_engine, owned_engines=tuple(owned[1:])
    )
