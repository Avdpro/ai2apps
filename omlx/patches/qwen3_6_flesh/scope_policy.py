"""Qwen3.6-specific scope policy and memory-tier validation."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any


NUM_LAYERS = 40
NUM_EXPERTS = 256
TOP_K = 8

PROFILE_ENV = "OMLX_QWEN36_SCOPE_PROFILE"
SCOPE_ENV = "OMLX_QWEN36_SCOPE_NAME"
STORE_ENV = "OMLX_QWEN36_EXPERT_STORE"
RESIDENT_ENV = "OMLX_QWEN36_RESIDENT_EXPERTS"

# These are Qwen-specific working points found by the existing DMoE scope
# sweep. They must not inherit DeepSeek's Top20/40/60 tiers.
MEMORY_TIER_EXPERTS = {
    "lean": 80,
    "compact": 96,
    "optimal": 120,
}

_policy_override: tuple[str, str, str, int, str, int] | None = None
_policy_disabled = False


def _validate_resident_experts(count: int) -> int:
    if not 8 <= count <= NUM_EXPERTS:
        raise ValueError("Qwen3.6 resident experts must be between 8 and 256")
    return count


@dataclass(frozen=True)
class Qwen36ScopeCatalog:
    """Validated Qwen prefill/decode rankings for every scope and layer."""

    profile_path: Path
    scope_ids: tuple[str, ...]
    prefill_by_scope: dict[str, tuple[tuple[int, ...], ...]]
    decode_by_scope: dict[str, tuple[tuple[int, ...], ...]]

    @classmethod
    def load(cls, profile_path: str | Path) -> "Qwen36ScopeCatalog":
        path = Path(profile_path).expanduser().resolve()
        payload = json.loads(path.read_text())

        # Native AI2Apps Scope Packs and the earlier DMoE joint-hotset output
        # have the same phase/scopes/layers payload; only the format marker is
        # different. Accepting the artifact directly keeps the repositories
        # separate and avoids copying DMoE runtime modules.
        format_name = payload.get("format")
        if format_name not in (None, "ai2apps-qwen36-scope-policy"):
            raise ValueError(f"unsupported Qwen3.6 scope profile: {path}")
        phases = payload.get("phases")
        if not isinstance(phases, dict):
            raise ValueError(f"Qwen3.6 scope profile has no phases: {path}")
        raw_prefill = phases.get("prefill")
        raw_decode = phases.get("decode")
        if not isinstance(raw_prefill, dict) or not isinstance(raw_decode, dict):
            raise ValueError("Qwen3.6 scope profile requires prefill and decode phases")
        if set(raw_prefill) != set(raw_decode) or not raw_prefill:
            raise ValueError("Qwen3.6 prefill/decode scope sets must match")

        def parse_phase(
            phase_name: str, raw_scopes: dict[str, Any]
        ) -> dict[str, tuple[tuple[int, ...], ...]]:
            parsed = {}
            for scope_id, raw_layers in raw_scopes.items():
                if not isinstance(raw_layers, dict):
                    raise ValueError(f"scope {scope_id!r} {phase_name} is not layered")
                layers = []
                for layer in range(NUM_LAYERS):
                    try:
                        experts = tuple(int(value) for value in raw_layers[str(layer)])
                    except (KeyError, TypeError, ValueError) as exc:
                        raise ValueError(
                            f"scope {scope_id!r} {phase_name} is missing layer {layer}"
                        ) from exc
                    if len(experts) < TOP_K:
                        raise ValueError(
                            f"scope {scope_id!r} layer {layer} has fewer than Top-{TOP_K} experts"
                        )
                    if len(set(experts)) != len(experts):
                        raise ValueError(
                            f"scope {scope_id!r} {phase_name} layer {layer} has duplicates"
                        )
                    if min(experts) < 0 or max(experts) >= NUM_EXPERTS:
                        raise ValueError(
                            f"scope {scope_id!r} {phase_name} layer {layer} has invalid IDs"
                        )
                    layers.append(experts)
                parsed[str(scope_id)] = tuple(layers)
            return parsed

        return cls(
            profile_path=path,
            scope_ids=tuple(sorted(str(value) for value in raw_prefill)),
            prefill_by_scope=parse_phase("prefill", raw_prefill),
            decode_by_scope=parse_phase("decode", raw_decode),
        )

    def experts(
        self,
        scope_id: str,
        layer: int,
        *,
        phase: str = "decode",
        limit: int | None = None,
    ) -> tuple[int, ...]:
        source = self.decode_by_scope if phase == "decode" else self.prefill_by_scope
        if phase not in ("prefill", "decode"):
            raise ValueError("Qwen3.6 scope phase must be prefill or decode")
        try:
            experts = source[scope_id][layer]
        except KeyError as exc:
            raise ValueError(
                f"unknown Qwen3.6 scope {scope_id!r}; available={list(self.scope_ids)}"
            ) from exc
        return experts if limit is None else experts[:limit]

    def masks(
        self, resident_experts: int, *, phase: str = "decode"
    ) -> list[list[list[int]]]:
        """Return scope × layer × expert masks for the actual L1 size."""

        resident_experts = _validate_resident_experts(resident_experts)
        result = []
        for scope_id in self.scope_ids:
            layers = []
            for layer in range(NUM_LAYERS):
                mask = [0] * NUM_EXPERTS
                for expert in self.experts(
                    scope_id, layer, phase=phase, limit=resident_experts
                ):
                    mask[expert] = 1
                layers.append(mask)
            result.append(layers)
        return result


@dataclass(frozen=True)
class Qwen36ScopePolicy:
    profile_path: Path
    scope_name: str
    store_path: Path
    resident_experts: int
    backend: str
    arena_tail_slots: int
    catalog: Qwen36ScopeCatalog

    @property
    def physical_experts(self) -> int:
        return self.resident_experts + (
            self.arena_tail_slots if self.backend in ("arena", "tiered") else 0
        )

    @property
    def execution_experts(self) -> int:
        return self.arena_tail_slots if self.backend == "tiered" else self.physical_experts

    def experts(self, layer: int, *, phase: str = "decode") -> tuple[int, ...]:
        experts = self.catalog.experts(self.scope_name, layer, phase=phase)
        if len(experts) < self.resident_experts:
            raise ValueError(
                f"scope {self.scope_name!r} {phase} layer {layer} has only "
                f"{len(experts)} experts; Top-{self.resident_experts} requested"
            )
        return experts[: self.resident_experts]


def configure_qwen36_scope_policy(
    profile_path: str | Path,
    scope_name: str,
    store_path: str | Path,
    resident_experts: int,
    *,
    backend: str = "flesh",
    arena_tail_slots: int = 24,
) -> None:
    global _policy_disabled, _policy_override
    _policy_disabled = False
    backend = str(backend).strip().lower()
    if backend not in ("flesh", "arena", "tiered"):
        raise ValueError("Qwen3.6 backend must be 'flesh', 'arena', or 'tiered'")
    if not 1 <= int(arena_tail_slots) <= 64:
        raise ValueError("Qwen3.6 arena tail slots must be 1..64")
    resident_experts = _validate_resident_experts(int(resident_experts))
    if resident_experts + (
        int(arena_tail_slots) if backend in ("arena", "tiered") else 0
    ) > NUM_EXPERTS:
        raise ValueError("Qwen3.6 arena exceeds the model expert count")
    _policy_override = (
        str(Path(profile_path).expanduser()),
        str(scope_name),
        str(Path(store_path).expanduser()),
        resident_experts,
        backend,
        int(arena_tail_slots),
    )
    load_qwen36_scope_policy.cache_clear()


def clear_qwen36_scope_policy() -> None:
    global _policy_disabled, _policy_override
    _policy_disabled = False
    _policy_override = None
    load_qwen36_scope_policy.cache_clear()


def disable_qwen36_scope_policy() -> None:
    """Force full-resident execution even when legacy env vars are present."""

    global _policy_disabled, _policy_override
    _policy_disabled = True
    _policy_override = None
    load_qwen36_scope_policy.cache_clear()


@cache
def load_qwen36_scope_policy() -> Qwen36ScopePolicy | None:
    if _policy_disabled:
        return None
    if _policy_override is not None:
        (
            raw_profile,
            raw_scope,
            raw_store,
            resident_experts,
            backend,
            arena_tail_slots,
        ) = _policy_override
    else:
        raw_profile = os.environ.get(PROFILE_ENV, "").strip()
        raw_scope = os.environ.get(SCOPE_ENV, "").strip()
        raw_store = os.environ.get(STORE_ENV, "").strip()
        raw_resident = os.environ.get(RESIDENT_ENV, "96").strip()
        configured = [bool(raw_profile), bool(raw_scope), bool(raw_store)]
        if not any(configured):
            return None
        if not all(configured):
            raise ValueError(
                f"{PROFILE_ENV}, {SCOPE_ENV}, and {STORE_ENV} must be set together"
            )
        try:
            resident_experts = int(raw_resident)
        except ValueError as exc:
            raise ValueError(f"{RESIDENT_ENV} must be an integer") from exc
        resident_experts = _validate_resident_experts(resident_experts)
        backend = "flesh"
        arena_tail_slots = 24

    profile_path = Path(raw_profile).expanduser().resolve()
    store_path = Path(raw_store).expanduser().resolve()
    if not store_path.is_dir():
        raise FileNotFoundError(f"Qwen3.6 expert-major store not found: {store_path}")
    catalog = Qwen36ScopeCatalog.load(profile_path)
    if raw_scope not in catalog.scope_ids:
        raise ValueError(
            f"scope {raw_scope!r} not present in {profile_path}; "
            f"available={list(catalog.scope_ids)}"
        )
    policy = Qwen36ScopePolicy(
        profile_path=profile_path,
        scope_name=raw_scope,
        store_path=store_path,
        resident_experts=resident_experts,
        backend=backend,
        arena_tail_slots=arena_tail_slots,
        catalog=catalog,
    )
    # Validate every layer and both phases at configuration time rather than
    # failing halfway through model construction.
    for phase in ("prefill", "decode"):
        for layer in range(NUM_LAYERS):
            policy.experts(layer, phase=phase)
    return policy


def estimated_resident_bytes(
    resident_experts: int,
    *,
    expert_record_bytes: int = 1_769_472,
    layers: int = NUM_LAYERS,
) -> int:
    """Return Qwen routed-L1 bytes, excluding backbone and runtime buffers."""

    return _validate_resident_experts(resident_experts) * layers * expert_record_bytes


__all__ = [
    "MEMORY_TIER_EXPERTS",
    "NUM_EXPERTS",
    "NUM_LAYERS",
    "PROFILE_ENV",
    "Qwen36ScopeCatalog",
    "Qwen36ScopePolicy",
    "RESIDENT_ENV",
    "SCOPE_ENV",
    "STORE_ENV",
    "TOP_K",
    "clear_qwen36_scope_policy",
    "configure_qwen36_scope_policy",
    "disable_qwen36_scope_policy",
    "estimated_resident_bytes",
    "load_qwen36_scope_policy",
]
