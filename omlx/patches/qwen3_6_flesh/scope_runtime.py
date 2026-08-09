"""Online target-backbone scope selection for Qwen3.6 Cache-MoE."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Qwen36ScopeSelection:
    scope: str
    margin: float
    top3: tuple[str, ...]
    scores: tuple[float, ...]
    depth: int
    tokens: int
    seconds: float
    method: str = "shared"
    shared_margin: float | None = None


class _Top8Collector:
    def __init__(self, masks: Any, expected_layers: int) -> None:
        self.masks = masks
        self.expected_layers = expected_layers
        self.pending: list[tuple[int, Any, Any]] = []

    def capture(self, layer: int, inds: Any, weights: Any) -> None:
        self.pending.append((layer, inds, weights))

    def finish(self) -> list[float]:
        import mlx.core as mx

        if len(self.pending) != self.expected_layers:
            raise RuntimeError(
                f"expected {self.expected_layers} Qwen probe routers, "
                f"got {[layer for layer, _, _ in self.pending]}"
            )
        scores = mx.zeros((self.masks.shape[0],), dtype=mx.float32)
        mass = mx.array(0.0, dtype=mx.float32)
        for layer, inds, weights in self.pending:
            covered = mx.take(self.masks[:, layer, :], inds, axis=1)
            scores = scores + mx.sum(
                covered * weights[None, ...].astype(mx.float32),
                axis=(1, 2, 3),
            )
            mass = mass + mx.sum(weights.astype(mx.float32))
        scores = scores / (mass + 1e-20)
        mx.eval(scores)
        return [float(value) for value in scores.tolist()]


class _SharedOnlyQwenMoE:
    def __init__(self, inner: Any, layer: int, collector: _Top8Collector) -> None:
        self.inner = inner
        self.layer = layer
        self.collector = collector

    def __call__(self, x: Any) -> Any:
        import mlx.core as mx

        if self.inner.sharding_group is not None:
            raise RuntimeError("Qwen3.6 scope probe does not support sharding")
        gates = mx.softmax(self.inner.gate(x), axis=-1, precise=True)
        inds = mx.argpartition(
            gates, kth=-self.inner.top_k, axis=-1
        )[..., -self.inner.top_k :]
        weights = mx.take_along_axis(gates, inds, axis=-1)
        if self.inner.norm_topk_prob:
            weights = weights / weights.sum(axis=-1, keepdims=True)
        self.collector.capture(self.layer, inds, weights)
        return mx.sigmoid(self.inner.shared_expert_gate(x)) * self.inner.shared_expert(x)


class Qwen36ScopeSelector:
    """Run a truncated Qwen backbone with shared experts and Top-8 routers."""

    window_tokens = 128

    def __init__(
        self,
        model: Any,
        catalog: Any,
        *,
        resident_experts: int,
        depth: int = 16,
        max_tokens: int = 1024,
        stream: Any = None,
    ) -> None:
        import mlx.core as mx

        if not 4 <= depth <= 40:
            raise ValueError("Qwen scope probe depth must be 4..40")
        if max_tokens < 8:
            raise ValueError("Qwen scope probe max tokens must be at least 8")
        self.model = model
        self.catalog = catalog
        self.depth = depth
        self.max_tokens = max_tokens
        self.stream = stream
        self.masks = mx.array(
            catalog.masks(resident_experts, phase="decode"), dtype=mx.float32
        )
        mx.eval(self.masks)
        self.calls = 0
        self.exact_calls = 0
        self.total_seconds = 0.0
        self.exact_seconds = 0.0

    def _truncate(self, token_ids: list[int]) -> list[int]:
        if len(token_ids) <= self.max_tokens:
            return token_ids
        # Preserve enough of the system/initial instructions while biasing the
        # sample toward the most recent user turn. At the serving default this
        # keeps 128 leading tokens and 896 trailing tokens.
        prefix = min(128, self.max_tokens // 8)
        return token_ids[:prefix] + token_ids[-(self.max_tokens - prefix) :]

    def select(self, token_ids: list[int]) -> Qwen36ScopeSelection:
        import mlx.core as mx

        ids = self._truncate(token_ids)
        target = self.model.language_model.model
        all_layers = target.layers
        originals: list[tuple[Any, Any]] = []
        wrappers: list[_SharedOnlyQwenMoE] = []
        started = time.perf_counter()
        try:
            target.layers = all_layers[: self.depth]
            for layer, decoder in enumerate(target.layers):
                block = decoder.mlp
                if not hasattr(block, "scope_policy"):
                    raise RuntimeError(
                        f"Qwen scope probe layer {layer} is not a routed block"
                    )
                originals.append((decoder, block))
                wrapper = _SharedOnlyQwenMoE(
                    block, layer, _Top8Collector(self.masks, self.depth)
                )
                wrappers.append(wrapper)
                decoder.mlp = wrapper

            windows = [
                ids[offset : offset + self.window_tokens]
                for offset in range(0, len(ids), self.window_tokens)
            ]
            score_sums = [0.0] * len(self.catalog.scope_ids)

            def probe_windows() -> None:
                for window in windows:
                    collector = _Top8Collector(self.masks, self.depth)
                    for wrapper in wrappers:
                        wrapper.collector = collector
                    hidden = target(mx.array([window], dtype=mx.int32), cache=None)
                    mx.eval(hidden)
                    window_scores = collector.finish()
                    for index, value in enumerate(window_scores):
                        score_sums[index] += value * len(window)

            context = mx.stream(self.stream) if self.stream is not None else None
            if context is None:
                probe_windows()
            else:
                with context:
                    probe_windows()
            scores = [value / len(ids) for value in score_sums]
        finally:
            for decoder, block in originals:
                decoder.mlp = block
            target.layers = all_layers

        ranked = sorted(range(len(scores)), key=lambda index: -scores[index])
        elapsed = time.perf_counter() - started
        self.calls += 1
        self.total_seconds += elapsed
        return Qwen36ScopeSelection(
            scope=self.catalog.scope_ids[ranked[0]],
            margin=scores[ranked[0]] - scores[ranked[1]],
            top3=tuple(self.catalog.scope_ids[index] for index in ranked[:3]),
            scores=tuple(scores),
            depth=self.depth,
            tokens=len(ids),
            seconds=elapsed,
            method="shared",
            shared_margin=None,
        )

    def select_exact(self, token_ids: list[int]) -> Qwen36ScopeSelection:
        """Use the exact routed trajectory as the low-confidence refinement."""

        import mlx.core as mx

        from .model_patch import set_qwen36_parity_observer

        ids = self._truncate(token_ids)
        collector = _Top8Collector(self.masks, 40)

        def observe(block, _x, inds, scores, _routed, _output):
            collector.capture(block.scope_layer, inds, scores)

        started = time.perf_counter()
        set_qwen36_parity_observer(observe)
        try:
            context = mx.stream(self.stream) if self.stream is not None else None
            if context is None:
                hidden = self.model.language_model.model(
                    mx.array([ids], dtype=mx.int32), cache=None
                )
                mx.eval(hidden)
                scores = collector.finish()
            else:
                with context:
                    hidden = self.model.language_model.model(
                        mx.array([ids], dtype=mx.int32), cache=None
                    )
                    mx.eval(hidden)
                    scores = collector.finish()
        finally:
            set_qwen36_parity_observer(None)
        ranked = sorted(range(len(scores)), key=lambda index: -scores[index])
        elapsed = time.perf_counter() - started
        self.exact_calls += 1
        self.exact_seconds += elapsed
        return Qwen36ScopeSelection(
            scope=self.catalog.scope_ids[ranked[0]],
            margin=scores[ranked[0]] - scores[ranked[1]],
            top3=tuple(self.catalog.scope_ids[index] for index in ranked[:3]),
            scores=tuple(scores),
            depth=40,
            tokens=len(ids),
            seconds=elapsed,
            method="exact-refine",
            shared_margin=None,
        )

    def select_cascade(
        self, token_ids: list[int], *, margin_threshold: float = 0.010
    ) -> Qwen36ScopeSelection:
        shared = self.select(token_ids)
        if shared.margin >= margin_threshold:
            return shared
        exact = self.select_exact(token_ids)
        return Qwen36ScopeSelection(
            scope=exact.scope,
            margin=exact.margin,
            top3=exact.top3,
            scores=exact.scores,
            depth=exact.depth,
            tokens=exact.tokens,
            seconds=shared.seconds + exact.seconds,
            method=exact.method,
            shared_margin=shared.margin,
        )

    def stats(self) -> dict[str, float | int]:
        return {
            "calls": self.calls,
            "exact_calls": self.exact_calls,
            "depth": self.depth,
            "max_tokens": self.max_tokens,
            "total_seconds": self.total_seconds,
            "exact_seconds": self.exact_seconds,
            "mean_seconds": self.total_seconds / self.calls if self.calls else 0.0,
        }


__all__ = ["Qwen36ScopeSelection", "Qwen36ScopeSelector"]
