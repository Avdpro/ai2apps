"""Online scope selection and resident-bank activation for DeepSeek V4 Flesh."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScopeCatalog:
    """Validated, dynamically-sized scope profile used by the online runtime."""

    profile_path: Path
    scope_ids: tuple[str, ...]
    experts_by_scope: dict[str, tuple[tuple[int, ...], ...]]
    selection_experts_by_scope: dict[str, tuple[tuple[int, ...], ...]]

    @classmethod
    def load(
        cls, profile_path: str | Path, resident_experts: int = 60
    ) -> "ScopeCatalog":
        path = Path(profile_path).expanduser().resolve()
        payload = json.loads(path.read_text())
        if payload.get("format") != "dmoe-deepseek-tiered-policy":
            raise ValueError(f"unsupported DeepSeek scope profile: {path}")
        raw_scopes = payload.get("scopes") or {}
        if not raw_scopes:
            raise ValueError(f"scope profile contains no scopes: {path}")

        scopes: dict[str, tuple[tuple[int, ...], ...]] = {}
        selection_scopes: dict[str, tuple[tuple[int, ...], ...]] = {}
        for scope_id, raw_layers in raw_scopes.items():
            layers: list[tuple[int, ...]] = []
            selection_layers: list[tuple[int, ...]] = []
            for layer in range(43):
                if layer < 3:
                    experts = tuple(range(256))
                else:
                    try:
                        experts = tuple(int(value) for value in raw_layers[str(layer)])
                    except KeyError as exc:
                        raise ValueError(
                            f"scope {scope_id!r} is missing layer {layer}"
                        ) from exc
                    if len(experts) < resident_experts:
                        raise ValueError(
                            f"scope {scope_id!r} layer {layer} must contain "
                            f"at least {resident_experts} experts"
                        )
                    if len(set(experts)) != len(experts):
                        raise ValueError(
                            f"scope {scope_id!r} layer {layer} contains duplicate experts"
                        )
                    if min(experts) < 0 or max(experts) >= 256:
                        raise ValueError(
                            f"scope {scope_id!r} layer {layer} has invalid IDs"
                        )
                selection_layers.append(experts)
                layers.append(
                    experts if layer < 3 else experts[:resident_experts]
                )
            scopes[str(scope_id)] = tuple(layers)
            selection_scopes[str(scope_id)] = tuple(selection_layers)
        return cls(path, tuple(sorted(scopes)), scopes, selection_scopes)

    def experts(self, scope_id: str, layer: int) -> tuple[int, ...]:
        try:
            return self.experts_by_scope[scope_id][layer]
        except KeyError as exc:
            raise ValueError(
                f"unknown scope {scope_id!r}; available={list(self.scope_ids)}"
            ) from exc

    def masks(self) -> list[list[list[int]]]:
        result = []
        for scope_id in self.scope_ids:
            scope_layers = []
            for layer in range(3, 43):
                mask = [0] * 256
                for expert in self.selection_experts_by_scope[scope_id][layer]:
                    mask[expert] = 1
                scope_layers.append(mask)
            result.append(scope_layers)
        return result


@dataclass(frozen=True)
class ScopeSelection:
    scope: str
    margin: float
    top3: tuple[str, ...]
    scores: tuple[float, ...]
    depth: int
    tokens: int
    seconds: float


class _Top6Collector:
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
                f"expected {self.expected_layers} probe routers, "
                f"got {[layer for layer, _, _ in self.pending]}"
            )
        scores = mx.zeros((self.masks.shape[0],), dtype=mx.float32)
        mass = mx.array(0.0, dtype=mx.float32)
        for layer, inds, weights in self.pending:
            covered = mx.take(self.masks[:, layer - 3, :], inds, axis=1)
            scores = scores + mx.sum(
                covered * weights[None, ...].astype(mx.float32),
                axis=(1, 2, 3),
            )
            mass = mass + mx.sum(weights.astype(mx.float32))
        scores = scores / (mass + 1e-20)
        mx.eval(scores)
        return [float(value) for value in scores.tolist()]


class _SharedOnlyFFN:
    def __init__(self, inner: Any, layer: int, collector: _Top6Collector):
        self.inner = inner
        self.layer = layer
        self.collector = collector

    def __call__(self, x: Any, input_ids: Any) -> Any:
        if self.inner.sharding_group is not None:
            raise RuntimeError("DeepSeek V4 Flesh probe does not support sharding")
        shared = self.inner.shared_experts(x)
        inds, weights = self.inner.gate(x, input_ids)
        self.collector.capture(self.layer, inds, weights)
        return shared


class DeepseekV4ScopeSelector:
    """Run a truncated target-backbone/shared-expert Top6 scope probe."""

    window_tokens = 128

    def __init__(
        self,
        model: Any,
        catalog: ScopeCatalog,
        *,
        depth: int,
        max_tokens: int = 1024,
        stream: Any = None,
    ) -> None:
        import mlx.core as mx

        if not 4 <= depth <= 43:
            raise ValueError("scope probe depth must be 4..43")
        if max_tokens < 8:
            raise ValueError("scope probe max tokens must be at least 8")
        self.model = model
        self.catalog = catalog
        self.depth = depth
        self.max_tokens = max_tokens
        self.stream = stream
        self.masks = mx.array(catalog.masks(), dtype=mx.float32)
        mx.eval(self.masks)
        self.calls = 0
        self.total_seconds = 0.0

    def _truncate(self, token_ids: list[int]) -> list[int]:
        if len(token_ids) <= self.max_tokens:
            return token_ids
        # Preserve enough of the system/initial instructions while biasing the
        # sample toward the most recent user turn. At the serving default this
        # keeps 128 leading tokens and 896 trailing tokens.
        prefix = min(128, self.max_tokens // 8)
        return token_ids[:prefix] + token_ids[-(self.max_tokens - prefix) :]

    def select(self, token_ids: list[int]) -> ScopeSelection:
        import mlx.core as mx

        ids = self._truncate(token_ids)
        target = getattr(self.model, "model", self.model)
        all_layers = target.layers
        originals: list[tuple[Any, Any]] = []
        wrappers: list[_SharedOnlyFFN] = []
        started = time.perf_counter()
        try:
            target.layers = all_layers[: self.depth]
            for layer, block in enumerate(target.layers):
                if layer < 3:
                    continue
                originals.append((block, block.ffn))
                wrapper = _SharedOnlyFFN(
                    block.ffn,
                    layer,
                    _Top6Collector(self.masks, self.depth - 3),
                )
                wrappers.append(wrapper)
                block.ffn = wrapper

            windows = [
                ids[offset : offset + self.window_tokens]
                for offset in range(0, len(ids), self.window_tokens)
            ]
            score_sums = [0.0] * len(self.catalog.scope_ids)

            def probe_windows() -> None:
                for window in windows:
                    collector = _Top6Collector(self.masks, self.depth - 3)
                    for wrapper in wrappers:
                        wrapper.collector = collector
                    cache = self.model.make_cache()
                    hidden = target(mx.array([window], dtype=mx.int32), cache=cache)
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
            for block, ffn in originals:
                block.ffn = ffn
            target.layers = all_layers

        ranked = sorted(range(len(scores)), key=lambda index: -scores[index])
        elapsed = time.perf_counter() - started
        self.calls += 1
        self.total_seconds += elapsed
        return ScopeSelection(
            scope=self.catalog.scope_ids[ranked[0]],
            margin=scores[ranked[0]] - scores[ranked[1]],
            top3=tuple(self.catalog.scope_ids[index] for index in ranked[:3]),
            scores=tuple(scores),
            depth=self.depth,
            tokens=len(ids),
            seconds=elapsed,
        )

    def stats(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "depth": self.depth,
            "max_tokens": self.max_tokens,
            "total_seconds": self.total_seconds,
            "mean_seconds": self.total_seconds / self.calls if self.calls else 0.0,
        }


class DeepseekV4ScopeBank:
    """Replace the physical Top60 bank at a quiescent request boundary."""

    def __init__(
        self,
        model: Any,
        catalog: ScopeCatalog,
        loader: Any,
        current_scope: str,
    ) -> None:
        if current_scope not in catalog.experts_by_scope:
            raise ValueError(f"initial scope {current_scope!r} is not in profile")
        self.model = model
        self.catalog = catalog
        self.loader = loader
        self.current_scope = current_scope
        self.switches = 0
        self.total_seconds = 0.0
        self.adaptive_commits = 0
        self.adaptive_layers_rebuilt = 0
        self.adaptive_seconds = 0.0
        self.adaptive_sync_seconds = 0.0
        self.adaptive_backend = os.environ.get(
            "OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND", "patch"
        ).strip().lower()
        if self.adaptive_backend not in ("atomic", "stream", "patch"):
            raise ValueError(
                "OMLX_DEEPSEEK_V4_L1_UPDATE_BACKEND must be atomic, stream, or patch"
            )
        self.adaptive_stream_layers = int(os.environ.get(
            "OMLX_DEEPSEEK_V4_L1_STREAM_LAYERS", "4"
        ))
        if not 1 <= self.adaptive_stream_layers <= 40:
            raise ValueError("OMLX_DEEPSEEK_V4_L1_STREAM_LAYERS must be 1..40")

    @staticmethod
    def _publish_layer(ffn: Any, switch: Any, expert_ids: tuple[int, ...]) -> None:
        lookup = [-1] * ffn.config.n_routed_experts
        for slot, expert_id in enumerate(expert_ids):
            lookup[expert_id] = slot
        # Publish the complete switch before its lookup. Inference is serialized
        # on the MLX executor, so no forward can observe this intermediate state.
        ffn.switch_mlp = switch
        ffn.scope_expert_ids = expert_ids
        ffn.scope_expert_to_slot_values = tuple(lookup)

    def activate(self, scope_id: str) -> bool:
        import mlx.core as mx

        if scope_id == self.current_scope:
            return False
        if scope_id not in self.catalog.experts_by_scope:
            raise ValueError(f"unknown scope {scope_id!r}")
        started = time.perf_counter()
        target = getattr(self.model, "model", self.model)
        self.loader.clear_hot()
        for layer, block in enumerate(target.layers):
            if layer < 3:
                continue
            ffn = block.ffn
            expert_ids = self.catalog.experts(scope_id, layer)
            if tuple(ffn.scope_expert_ids or ()) == expert_ids:
                continue
            switch, loaded_ids = self.loader.build_transient_switch(
                layer,
                list(expert_ids),
                ffn.switch_mlp,
            )
            if loaded_ids != expert_ids:
                raise RuntimeError(f"scope bank load mismatch at layer {layer}")
            self._publish_layer(ffn, switch, expert_ids)
        self.loader.clear_hot()
        mx.clear_cache()
        self.current_scope = scope_id
        self.switches += 1
        self.total_seconds += time.perf_counter() - started
        return True

    def activate_layout(
        self,
        scope_id: str,
        experts_by_layer: list[tuple[int, ...]],
        *,
        adaptive: bool = False,
    ) -> int:
        """Atomically publish only L1 layers whose logical layout changed."""

        import mlx.core as mx

        if scope_id not in self.catalog.experts_by_scope:
            raise ValueError(f"unknown scope {scope_id!r}")
        if len(experts_by_layer) != 43:
            raise ValueError("adaptive L1 layout must contain 43 layers")
        target = getattr(self.model, "model", self.model)
        changed: list[tuple[int, Any, tuple[int, ...], tuple[int, ...]]] = []
        started = time.perf_counter()
        for layer, block in enumerate(target.layers):
            if layer < 3:
                continue
            ffn = block.ffn
            desired = tuple(experts_by_layer[layer])
            current = tuple(ffn.scope_expert_ids or ())
            if current == desired:
                continue
            changed.append((layer, ffn, current, desired))

        if self.adaptive_backend == "atomic":
            prepared: list[tuple[Any, Any, tuple[int, ...]]] = []
            for layer, ffn, _, desired in changed:
                switch, loaded_ids = self.loader.rebuild_resident_switch(
                    layer, list(desired), ffn.switch_mlp
                )
                if loaded_ids != desired:
                    raise RuntimeError(
                        f"adaptive L1 load mismatch at layer {layer}"
                    )
                prepared.append((ffn, switch, loaded_ids))
            # The baseline backend preserves the original all-layer transaction.
            for ffn, switch, expert_ids in prepared:
                self._publish_layer(ffn, switch, expert_ids)
        elif changed:
            sync_started = time.perf_counter()
            mx.synchronize()
            self.adaptive_sync_seconds += time.perf_counter() - sync_started
            self.loader.clear_hot()
            mx.clear_cache()
            if self.adaptive_backend == "stream":
                self._activate_layout_stream(changed)
            else:
                self._activate_layout_patch(changed)

        if changed:
            self.loader.clear_hot()
            mx.clear_cache()
        elapsed = time.perf_counter() - started
        self.current_scope = scope_id
        if adaptive and changed:
            self.adaptive_commits += 1
            self.adaptive_layers_rebuilt += len(changed)
            self.adaptive_seconds += elapsed
        elif changed:
            self.switches += 1
            self.total_seconds += elapsed
        return len(changed)

    def _activate_layout_stream(
        self,
        changed: list[tuple[int, Any, tuple[int, ...], tuple[int, ...]]],
    ) -> None:
        """Bound replacement memory by publishing a few complete layers at once."""

        import mlx.core as mx

        published: list[tuple[int, Any, tuple[int, ...]]] = []
        try:
            size = self.adaptive_stream_layers
            for offset in range(0, len(changed), size):
                prepared: list[tuple[int, Any, Any, tuple[int, ...], tuple[int, ...]]] = []
                for layer, ffn, current, desired in changed[offset : offset + size]:
                    switch, loaded_ids = self.loader.rebuild_resident_switch(
                        layer, list(desired), ffn.switch_mlp
                    )
                    if loaded_ids != desired:
                        raise RuntimeError(
                            f"adaptive L1 load mismatch at layer {layer}"
                        )
                    prepared.append((layer, ffn, switch, current, loaded_ids))
                for layer, ffn, switch, current, expert_ids in prepared:
                    self._publish_layer(ffn, switch, expert_ids)
                    published.append((layer, ffn, current))
                prepared.clear()
                mx.synchronize()
                mx.clear_cache()
        except Exception:
            self._rollback_rebuilt_layers(published)
            raise

    def _activate_layout_patch(
        self,
        changed: list[tuple[int, Any, tuple[int, ...], tuple[int, ...]]],
    ) -> None:
        """Rewrite only changed slots while keeping each SwitchGLU allocation."""

        attempted: list[tuple[int, Any, tuple[int, ...], list[int]]] = []
        try:
            for layer, ffn, current, desired in changed:
                slots = [
                    slot
                    for slot, (old, new) in enumerate(
                        zip(current, desired, strict=True)
                    )
                    if old != new
                ]
                attempted.append((layer, ffn, current, slots))
                switch, loaded_ids = self.loader.patch_resident_switch(
                    layer,
                    slots,
                    [desired[slot] for slot in slots],
                    ffn.switch_mlp,
                )
                if loaded_ids != tuple(desired[slot] for slot in slots):
                    raise RuntimeError(
                        f"adaptive L1 patch mismatch at layer {layer}"
                    )
                self._publish_layer(ffn, switch, desired)
        except Exception:
            self._rollback_patched_layers(attempted)
            raise

    def _rollback_rebuilt_layers(
        self, published: list[tuple[int, Any, tuple[int, ...]]]
    ) -> None:
        import mlx.core as mx

        for layer, ffn, original in reversed(published):
            switch, loaded_ids = self.loader.rebuild_resident_switch(
                layer, list(original), ffn.switch_mlp
            )
            self._publish_layer(ffn, switch, loaded_ids)
            mx.synchronize()
            mx.clear_cache()

    def _rollback_patched_layers(
        self,
        attempted: list[tuple[int, Any, tuple[int, ...], list[int]]],
    ) -> None:
        import mlx.core as mx

        for layer, ffn, original, slots in reversed(attempted):
            switch, _ = self.loader.patch_resident_switch(
                layer,
                slots,
                [original[slot] for slot in slots],
                ffn.switch_mlp,
            )
            self._publish_layer(ffn, switch, original)
        mx.synchronize()
        mx.clear_cache()

    def stats(self) -> dict[str, Any]:
        return {
            "current_scope": self.current_scope,
            "switches": self.switches,
            "switch_seconds": self.total_seconds,
            "adaptive_commits": self.adaptive_commits,
            "adaptive_layers_rebuilt": self.adaptive_layers_rebuilt,
            "adaptive_seconds": self.adaptive_seconds,
            "adaptive_backend": self.adaptive_backend,
            "adaptive_stream_layers": self.adaptive_stream_layers,
            "adaptive_sync_seconds": self.adaptive_sync_seconds,
        }
