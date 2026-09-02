"""Offline full-resident route collection for Qwen3.6/Ornith Scope banks."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


class Qwen36ScopeCollector:
    """Aggregate exact Top-K route frequency and probability mass by phase."""

    def __init__(self, *, num_layers: int = 40, num_experts: int = 256) -> None:
        self.num_layers = num_layers
        self.num_experts = num_experts
        self.pending: list[tuple[int, Any, Any, str]] = []
        self._counts = defaultdict(
            lambda: defaultdict(
                lambda: {
                    layer: [0] * num_experts for layer in range(num_layers)
                }
            )
        )
        self._mass = defaultdict(
            lambda: defaultdict(
                lambda: {
                    layer: [0.0] * num_experts for layer in range(num_layers)
                }
            )
        )
        self.samples = defaultdict(int)
        self.prompt_tokens = defaultdict(int)
        self.decode_tokens = defaultdict(int)

    def capture(self, layer: int, inds: Any, scores: Any, phase: str) -> None:
        if not 0 <= layer < self.num_layers:
            raise ValueError(f"invalid Qwen3.6 profile layer: {layer}")
        if phase not in ("prefill", "decode"):
            raise ValueError(f"invalid Qwen3.6 profile phase: {phase}")
        self.pending.append((layer, inds, scores, phase))

    def add_rows(
        self,
        scope: str,
        layer: int,
        phase: str,
        ids: list[int],
        weights: list[float],
    ) -> None:
        if len(ids) != len(weights):
            raise ValueError("route IDs and weights must have equal length")
        counts = self._counts[scope][phase][layer]
        mass = self._mass[scope][phase][layer]
        for expert, weight in zip(ids, weights, strict=True):
            if not 0 <= expert < self.num_experts:
                raise ValueError(f"invalid Qwen3.6 expert ID: {expert}")
            counts[expert] += 1
            mass[expert] += weight

    def drain(self, scope: str) -> None:
        if not self.pending:
            return
        import mlx.core as mx

        mx.eval(*(value for row in self.pending for value in row[1:3]))
        for layer, inds, scores, phase in self.pending:
            ids = [int(value) for value in inds.reshape(-1).tolist()]
            weights = [float(value) for value in scores.reshape(-1).tolist()]
            self.add_rows(scope, layer, phase, ids, weights)
        self.pending.clear()

    def finish(
        self, scope: str, *, samples: int, prompt_tokens: int, decode_tokens: int
    ) -> None:
        self.samples[scope] += samples
        self.prompt_tokens[scope] += prompt_tokens
        self.decode_tokens[scope] += decode_tokens

    @staticmethod
    def _scores(counts: list[int], mass: list[float]) -> list[float]:
        count_total = max(sum(counts), 1)
        mass_total = max(sum(mass), 1e-12)
        return [
            0.75 * count / count_total + 0.25 * weight / mass_total
            for count, weight in zip(counts, mass, strict=True)
        ]

    def build(self, *, metadata: dict[str, Any]) -> dict[str, Any]:
        phases: dict[str, dict[str, dict[str, list[int]]]] = {
            "prefill": {},
            "decode": {},
        }
        stats: dict[str, Any] = {}
        for scope in sorted(self._counts):
            stats[scope] = {
                "samples": self.samples[scope],
                "prompt_tokens": self.prompt_tokens[scope],
                "decode_tokens": self.decode_tokens[scope],
                "phases": {},
            }
            for phase in ("prefill", "decode"):
                layers: dict[str, list[int]] = {}
                layer_stats: dict[str, Any] = {}
                for layer in range(self.num_layers):
                    counts = self._counts[scope][phase][layer]
                    mass = self._mass[scope][phase][layer]
                    if not sum(counts):
                        raise RuntimeError(
                            f"scope {scope!r} has no {phase} routes at layer {layer}"
                        )
                    scores = self._scores(counts, mass)
                    ranking = sorted(
                        range(self.num_experts),
                        key=lambda expert: (-scores[expert], expert),
                    )
                    layers[str(layer)] = ranking
                    routes = sum(counts)
                    routed_mass = sum(mass)
                    layer_stats[str(layer)] = {
                        "routes": routes,
                        "counts_by_expert": counts,
                        "mass_by_expert": mass,
                        "coverage": {
                            str(limit): {
                                "routes": sum(counts[e] for e in ranking[:limit])
                                / routes,
                                "mass": sum(mass[e] for e in ranking[:limit])
                                / routed_mass,
                            }
                            for limit in (80, 96, 120, 160, 192, 224)
                        },
                    }
                phases[phase][scope] = layers
                stats[scope]["phases"][phase] = layer_stats
        return {
            "format": "ai2apps-qwen36-scope-policy",
            "version": 1,
            "num_layers": self.num_layers,
            "num_experts": self.num_experts,
            "ranking_length": self.num_experts,
            "ranking_score": "0.75*route_frequency+0.25*router_mass",
            "phases": phases,
            "stats": stats,
            "metadata": metadata,
        }


__all__ = ["Qwen36ScopeCollector"]
