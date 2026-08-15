"""Session-owned planning for a model-global adaptive DeepSeek V4 L1 bank."""

from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AdaptiveL1Config:
    enabled: bool = False
    interval_tokens: int = 256
    early_check_tokens: int = 128
    pinned_slots: int = 20
    max_promotions_per_layer: int = 40
    max_layers_per_commit: int = 40
    min_observations: int = 8
    min_ssd_layer_rate: float = 0.20
    early_min_ssd_layer_rate: float = 0.55
    min_tps_ratio: float = 0.90
    decay: float = 0.5
    payback_ratio: float = 1.5
    post_commit_miss_multiplier: float = 1.35
    post_commit_payback_multiplier: float = 1.50
    bank_size: int = 60
    layer_start: int = 3
    layer_count: int = 40
    # Experimental long-Prefill adaptation. Route histograms stay on device
    # and are read only at existing Prefill chunk boundaries.
    prefill_enabled: bool = False
    prefill_min_prompt_tokens: int = 1024
    prefill_min_remaining_tokens: int = 512
    prefill_min_miss_route_rate: float = 0.20
    prefill_max_promotions_per_layer: int = 8
    prefill_max_layers_per_commit: int = 20
    prefill_payback_ratio: float = 1.25
    prefill_recheck_tokens: int = 2048
    prefill_recheck_max_promotions_per_layer: int = 4
    prefill_recheck_max_layers_per_commit: int = 10
    prefill_recheck_miss_multiplier: float = 1.15

    @classmethod
    def from_env(cls) -> "AdaptiveL1Config":
        enabled = os.environ.get(
            "OMLX_DEEPSEEK_V4_ADAPTIVE_L1", ""
        ).strip().lower() in ("1", "true", "yes", "on")
        return cls(
            enabled=enabled,
            interval_tokens=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_INTERVAL", "256"
            )),
            early_check_tokens=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_EARLY_CHECK", "128"
            )),
            pinned_slots=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_PINNED", "20"
            )),
            max_promotions_per_layer=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_MAX_PER_LAYER", "40"
            )),
            max_layers_per_commit=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_MAX_LAYERS", "40"
            )),
            min_observations=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_MIN_OBSERVATIONS", "8"
            )),
            min_ssd_layer_rate=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_MIN_SSD_RATE", "0.20"
            )),
            early_min_ssd_layer_rate=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_EARLY_MIN_SSD_RATE", "0.55"
            )),
            min_tps_ratio=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_MIN_TPS_RATIO", "0.90"
            )),
            decay=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_DECAY", "0.5"
            )),
            payback_ratio=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_PAYBACK_RATIO", "1.5"
            )),
            post_commit_miss_multiplier=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_POST_MISS_MULTIPLIER", "1.35"
            )),
            post_commit_payback_multiplier=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_ADAPTIVE_L1_POST_PAYBACK_MULTIPLIER", "1.50"
            )),
            prefill_enabled=os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_ADAPTIVE_L1", ""
            ).strip().lower() in ("1", "true", "yes", "on"),
            prefill_min_prompt_tokens=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_MIN_PROMPT", "1024"
            )),
            prefill_min_remaining_tokens=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_MIN_REMAINING", "512"
            )),
            prefill_min_miss_route_rate=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_MIN_MISS_RATE", "0.20"
            )),
            prefill_max_promotions_per_layer=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_MAX_PER_LAYER", "8"
            )),
            prefill_max_layers_per_commit=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_MAX_LAYERS", "20"
            )),
            prefill_payback_ratio=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_PAYBACK_RATIO", "1.25"
            )),
            prefill_recheck_tokens=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_RECHECK_TOKENS", "2048"
            )),
            prefill_recheck_max_promotions_per_layer=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_RECHECK_MAX_PER_LAYER", "4"
            )),
            prefill_recheck_max_layers_per_commit=int(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_RECHECK_MAX_LAYERS", "10"
            )),
            prefill_recheck_miss_multiplier=float(os.environ.get(
                "OMLX_DEEPSEEK_V4_PREFILL_L1_RECHECK_MISS_MULTIPLIER", "1.15"
            )),
        )

    def validate(self) -> None:
        if self.interval_tokens < 32:
            raise ValueError("adaptive L1 interval must be at least 32 tokens")
        if not 8 <= self.early_check_tokens <= self.interval_tokens:
            raise ValueError("adaptive L1 early check must be 8..interval tokens")
        if self.bank_size < 1:
            raise ValueError("adaptive L1 bank size must be positive")
        if self.layer_start < 0 or self.layer_count < 1:
            raise ValueError("adaptive L1 layer range is invalid")
        if not 0 <= self.pinned_slots < self.bank_size:
            raise ValueError("adaptive L1 pinned slots exceed the bank")
        if not 1 <= self.max_promotions_per_layer <= self.bank_size - self.pinned_slots:
            raise ValueError(
                "adaptive L1 max promotions per layer exceeds mutable slots"
            )
        if not 1 <= self.max_layers_per_commit <= self.layer_count:
            raise ValueError("adaptive L1 max layers per commit exceeds layer count")
        if self.min_observations < 1:
            raise ValueError("adaptive L1 min observations must be positive")
        if not 0.0 <= self.min_ssd_layer_rate <= 1.0:
            raise ValueError("adaptive L1 minimum SSD rate must be in [0, 1]")
        if not self.min_ssd_layer_rate <= self.early_min_ssd_layer_rate <= 1.0:
            raise ValueError(
                "adaptive L1 early minimum SSD rate must be between the "
                "regular minimum and 1"
            )
        if not 0.0 < self.min_tps_ratio <= 1.0:
            raise ValueError("adaptive L1 TPS ratio must be in (0, 1]")
        if not 0.0 <= self.decay <= 1.0:
            raise ValueError("adaptive L1 decay must be in [0, 1]")
        if self.payback_ratio < 1.0:
            raise ValueError("adaptive L1 payback ratio must be at least 1")
        if self.post_commit_miss_multiplier < 1.0:
            raise ValueError("post-commit miss multiplier must be at least 1")
        if self.post_commit_payback_multiplier < 1.0:
            raise ValueError("post-commit payback multiplier must be at least 1")
        if self.prefill_min_prompt_tokens < 32:
            raise ValueError("Prefill adaptive L1 minimum prompt must be at least 32")
        if self.prefill_min_remaining_tokens < 1:
            raise ValueError("Prefill adaptive L1 minimum remaining must be positive")
        if not 0.0 <= self.prefill_min_miss_route_rate <= 1.0:
            raise ValueError("Prefill adaptive L1 miss rate must be in [0, 1]")
        if not 1 <= self.prefill_max_promotions_per_layer <= self.bank_size - self.pinned_slots:
            raise ValueError("Prefill adaptive L1 per-layer promotion limit is invalid")
        if not 1 <= self.prefill_max_layers_per_commit <= self.layer_count:
            raise ValueError("Prefill adaptive L1 layer limit is invalid")
        if self.prefill_payback_ratio < 1.0:
            raise ValueError("Prefill adaptive L1 payback ratio must be at least 1")
        if self.prefill_recheck_tokens < 512:
            raise ValueError("Prefill adaptive L1 recheck must be at least 512 tokens")
        if not 1 <= self.prefill_recheck_max_promotions_per_layer <= self.prefill_max_promotions_per_layer:
            raise ValueError("Prefill adaptive L1 recheck promotion limit is invalid")
        if not 1 <= self.prefill_recheck_max_layers_per_commit <= self.prefill_max_layers_per_commit:
            raise ValueError("Prefill adaptive L1 recheck layer limit is invalid")
        if self.prefill_recheck_miss_multiplier < 1.0:
            raise ValueError("Prefill adaptive L1 recheck miss multiplier must be at least 1")


@dataclass(frozen=True)
class L1Promotion:
    layer: int
    promote: int
    evict: int
    observations: int


@dataclass
class SessionL1State:
    session_id: str
    scope: str
    layout: list[tuple[int, ...]]
    epoch: int = 0
    turns: int = 0
    observations: dict[int, Counter[int]] = field(default_factory=dict)
    utility: dict[int, dict[int, float]] = field(default_factory=dict)
    total_promotions: int = 0
    last_reason: str | None = None
    last_optimize_seconds: float = 0.0
    mode: str = "auto"
    auto_cooldown_checks: int = 0
    auto_strict_checks: int = 0
    route_windows: int = 0
    baseline_tps: float | None = None

    def fingerprint(self) -> str:
        digest = hashlib.sha256()
        for layer in range(len(self.layout)):
            if not self.layout[layer]:
                continue
            digest.update(bytes(self.layout[layer]))
        return digest.hexdigest()[:16]


class AdaptiveL1Manager:
    """Collect existing miss-path IDs and plan bounded Session promotions."""

    def __init__(self, catalog: Any, config: AdaptiveL1Config) -> None:
        config.validate()
        self.catalog = catalog
        self.config = config
        self.sessions: dict[str, SessionL1State] = {}
        self.active_session_id: str | None = None
        self._manual: set[str] = set()
        self._lock = threading.Lock()
        self.interval_checks = 0
        self.interval_triggers = 0
        self.early_triggers = 0
        self.prefill_triggers = 0
        self.manual_triggers = 0
        self.turn_triggers = 0

    def _base_layout(self, scope: str) -> list[tuple[int, ...]]:
        end = self.config.layer_start + self.config.layer_count
        layout = [tuple() for _ in range(end)]
        for layer in range(self.config.layer_start, end):
            layout[layer] = self.catalog.experts(scope, layer)[: self.config.bank_size]
        return layout

    def begin(
        self, session_id: str, scope: str, mode: str | None = None
    ) -> SessionL1State:
        with self._lock:
            state = self.sessions.get(session_id)
            if state is None or state.scope != scope:
                state = SessionL1State(session_id, scope, self._base_layout(scope))
                self.sessions[session_id] = state
            if mode is not None:
                if mode not in ("auto", "off"):
                    raise ValueError("adaptive L1 mode must be auto or off")
                state.mode = mode
            self.active_session_id = session_id
            return state

    def active(self) -> SessionL1State | None:
        with self._lock:
            return self.sessions.get(self.active_session_id or "")

    def session_scope(self, session_id: str) -> str | None:
        """Return the scope established for a session, if it has started."""
        with self._lock:
            state = self.sessions.get(session_id)
            return state.scope if state is not None else None

    def observe_decode_miss(self, layer: int, expert_ids: list[int]) -> None:
        """Called only at the pre-existing miss CPU boundary; adds no sync."""
        with self._lock:
            state = self.sessions.get(self.active_session_id or "")
            if state is None or not (
                self.config.layer_start
                <= layer
                < self.config.layer_start + self.config.layer_count
            ):
                return
            counts = state.observations.setdefault(layer, Counter())
            counts.update(dict.fromkeys((int(value) for value in expert_ids), 1))

    def observe_route_window(
        self,
        state: SessionL1State,
        histograms: dict[int, list[int]],
    ) -> None:
        """Merge one GPU route-frequency window into Session policy state."""

        with self._lock:
            for layer, histogram in histograms.items():
                if not (
                    self.config.layer_start
                    <= layer
                    < self.config.layer_start + self.config.layer_count
                ):
                    continue
                current = set(state.layout[layer])
                misses = state.observations.setdefault(layer, Counter())
                utilities = state.utility.setdefault(layer, {})
                for expert, count in enumerate(histogram):
                    if count <= 0:
                        continue
                    if expert in current:
                        utilities[expert] = utilities.get(expert, 0.0) + float(count)
                    else:
                        misses[expert] += int(count)
            state.route_windows += 1

    def observe_routes(self, layer: int, expert_ids: list[int]) -> None:
        """Collect a host-visible Top-K route set at an existing miss boundary."""

        with self._lock:
            state = self.sessions.get(self.active_session_id or "")
            if state is None or not (
                self.config.layer_start
                <= layer
                < self.config.layer_start + self.config.layer_count
            ):
                return
            resident = set(state.layout[layer])
            misses = state.observations.setdefault(layer, Counter())
            utilities = state.utility.setdefault(layer, {})
            for expert in (int(value) for value in expert_ids):
                if expert in resident:
                    utilities[expert] = utilities.get(expert, 0.0) + 1.0
                else:
                    misses[expert] += 1

    def request_manual(self, session_id: str) -> None:
        with self._lock:
            self._manual.add(session_id)

    def consume_manual(self, session_id: str) -> bool:
        with self._lock:
            if session_id not in self._manual:
                return False
            self._manual.remove(session_id)
            self.manual_triggers += 1
            return True

    def cancel_manual(self, session_id: str) -> bool:
        """Discard a queued manual request without counting it as a trigger."""

        with self._lock:
            if session_id not in self._manual:
                return False
            self._manual.remove(session_id)
            return True

    def manual_pending(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._manual

    def record_turn(self, state: SessionL1State) -> None:
        with self._lock:
            state.turns += 1

    def plan(
        self,
        state: SessionL1State,
        *,
        min_observations: int | None = None,
        max_promotions: int | None = None,
    ) -> list[L1Promotion]:
        layer_candidates: list[tuple[int, list[L1Promotion]]] = []
        pinned = self.config.pinned_slots
        for layer, counts in state.observations.items():
            current = state.layout[layer]
            resident = set(current)
            minimum = (
                self.config.min_observations
                if min_observations is None else min_observations
            )
            ranked = [
                (count, expert)
                for expert, count in counts.items()
                if expert not in resident and count >= minimum
            ]
            if not ranked:
                continue
            ranked.sort(key=lambda item: (-item[0], item[1]))
            mutable = current[pinned:]
            if not mutable:
                continue
            utilities = state.utility.setdefault(layer, {})
            victims = sorted(
                mutable,
                key=lambda value: (utilities.get(value, 0.0), -current.index(value)),
            )
            promotion_limit = (
                self.config.max_promotions_per_layer
                if max_promotions is None
                else max(1, min(int(max_promotions), len(victims)))
            )
            count = min(len(ranked), len(victims), promotion_limit)
            promotions = [
                L1Promotion(layer, expert, victim, observations)
                for (observations, expert), victim in zip(
                    ranked[:count], victims[:count], strict=True
                )
            ]
            layer_candidates.append(
                (sum(item.observations for item in promotions), promotions)
            )
        layer_candidates.sort(
            key=lambda item: (-item[0], item[1][0].layer)
        )
        return [
            promotion
            for _, promotions in layer_candidates[: self.config.max_layers_per_commit]
            for promotion in promotions
        ]

    def commit(
        self,
        state: SessionL1State,
        promotions: list[L1Promotion],
        *,
        reason: str,
        seconds: float,
    ) -> None:
        with self._lock:
            for item in promotions:
                layout = list(state.layout[item.layer])
                layout[layout.index(item.evict)] = item.promote
                state.layout[item.layer] = tuple(layout)
                utilities = state.utility.setdefault(item.layer, {})
                utilities.pop(item.evict, None)
                utilities[item.promote] = float(item.observations)
            for utilities in state.utility.values():
                for expert in list(utilities):
                    utilities[expert] *= self.config.decay
            state.observations.clear()
            state.epoch += int(bool(promotions))
            state.total_promotions += len(promotions)
            state.last_reason = reason
            state.last_optimize_seconds = seconds
            if reason in (
                "early", "interval", "turn_end_auto", "manual", "prefill"
            ) and promotions:
                state.auto_cooldown_checks = 1
                state.auto_strict_checks = 1
            if reason == "turn_end":
                state.turns += 1
                self.turn_triggers += 1
            elif reason == "turn_end_auto":
                state.turns += 1
                self.turn_triggers += 1
            elif reason == "interval":
                self.interval_triggers += 1
            elif reason == "early":
                self.early_triggers += 1
            elif reason == "prefill":
                self.prefill_triggers += 1

    def should_interval_optimize(
        self,
        *,
        tokens: int,
        seconds: float,
        ssd_publish_calls: int,
        baseline_tps: float | None,
        predicted_savings_seconds: float,
        switch_cost_seconds: float,
        remaining_tokens: int,
        allow_without_tps: bool = False,
        min_ssd_layer_rate: float | None = None,
        strict: bool = False,
    ) -> bool:
        self.interval_checks += 1
        layer_steps = max(tokens * self.config.layer_count, 1)
        ssd_rate = ssd_publish_calls / layer_steps
        tps = tokens / max(seconds, 1e-9)
        slow = baseline_tps is not None and tps < baseline_tps * self.config.min_tps_ratio
        required_ssd_rate = (
            self.config.min_ssd_layer_rate
            if min_ssd_layer_rate is None else min_ssd_layer_rate
        )
        required_payback = self.config.payback_ratio
        if strict:
            required_ssd_rate = min(
                required_ssd_rate * self.config.post_commit_miss_multiplier,
                1.0,
            )
            required_payback *= self.config.post_commit_payback_multiplier
        pays_back = (
            remaining_tokens > 0
            and predicted_savings_seconds >= switch_cost_seconds * required_payback
        )
        return (
            pays_back
            and ssd_rate >= required_ssd_rate
            and (allow_without_tps or slow or ssd_rate >= 0.5)
        )

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": self.config.enabled,
                "active_session_id": self.active_session_id,
                "sessions": len(self.sessions),
                "interval_tokens": self.config.interval_tokens,
                "early_check_tokens": self.config.early_check_tokens,
                "interval_checks": self.interval_checks,
                "interval_triggers": self.interval_triggers,
                "early_triggers": self.early_triggers,
                "prefill_enabled": self.config.prefill_enabled,
                "prefill_triggers": self.prefill_triggers,
                "manual_triggers": self.manual_triggers,
                "turn_triggers": self.turn_triggers,
                "session_states": {
                    session_id: {
                        "scope": state.scope,
                        "epoch": state.epoch,
                        "turns": state.turns,
                        "fingerprint": state.fingerprint(),
                        "total_promotions": state.total_promotions,
                        "pending_observation_layers": len(state.observations),
                        "last_reason": state.last_reason,
                        "last_optimize_seconds": state.last_optimize_seconds,
                        "mode": state.mode,
                        "auto_cooldown_checks": state.auto_cooldown_checks,
                        "auto_strict_checks": state.auto_strict_checks,
                        "route_windows": state.route_windows,
                        "baseline_tps": state.baseline_tps,
                    }
                    for session_id, state in self.sessions.items()
                },
            }
