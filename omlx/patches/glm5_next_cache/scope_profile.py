"""Aggregate exact GLM5 router observations into reusable Scope profiles."""

from __future__ import annotations

from collections import defaultdict
from typing import Any


TRANSITION_TARGET_LIMIT = 32


class Glm5ScopeCollector:
    """Collect aggregate routes plus exact per-pack decode transition traces."""

    def __init__(self, *, num_experts: int = 288, capacity: int = 80) -> None:
        self.num_experts = num_experts
        self.capacity = capacity
        self.pending: list[tuple[int, Any, Any, str]] = []
        self._counts: dict[str, dict[str, dict[int, list[int]]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._mass: dict[str, dict[str, dict[int, list[float]]]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self._current_decode: dict[str, dict[int, list[list[int]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._decode_sequences: dict[str, list[dict[str, Any]]] = defaultdict(list)
        self._transition_counts: dict[
            str, dict[int, dict[int, dict[int, int]]]
        ] = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))
        self._transition_observations: dict[str, dict[int, dict[int, int]]] = (
            defaultdict(lambda: defaultdict(dict))
        )
        self._transition_steps: dict[str, dict[int, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self.sample_counts: dict[str, int] = defaultdict(int)
        self.pack_counts: dict[str, int] = defaultdict(int)
        self.token_counts: dict[str, int] = defaultdict(int)

    def capture(self, layer: int, inds: Any, scores: Any, phase: str) -> None:
        if phase not in {"prefill", "decode"}:
            raise ValueError(f"unsupported GLM5 Scope phase: {phase}")
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
        counts = self._counts[scope][phase].setdefault(layer, [0] * self.num_experts)
        mass = self._mass[scope][phase].setdefault(layer, [0.0] * self.num_experts)
        for expert, weight in zip(ids, weights, strict=True):
            if not 0 <= expert < self.num_experts:
                raise ValueError(f"invalid GLM5 expert ID: {expert}")
            counts[expert] += 1
            mass[expert] += float(weight)

    def add_decode_step(self, scope: str, layer: int, ids: list[int]) -> None:
        """Append one exact Top-K decode route and update adjacent-token pairs."""

        if not ids:
            raise ValueError("decode route cannot be empty")
        if any(not 0 <= expert < self.num_experts for expert in ids):
            raise ValueError(f"invalid GLM5 decode route: {ids}")
        sequence = self._current_decode[scope][layer]
        if sequence:
            previous = sequence[-1]
            self._transition_steps[scope][layer] += 1
            for source in dict.fromkeys(previous):
                observations = self._transition_observations[scope][layer]
                observations[source] = observations.get(source, 0) + 1
                targets = self._transition_counts[scope][layer][source]
                for target in dict.fromkeys(ids):
                    targets[target] = targets.get(target, 0) + 1
        sequence.append(list(ids))

    def drain(self, scope: str) -> None:
        """Materialize pending MLX arrays after the associated forward completes."""

        if not self.pending:
            return
        import mlx.core as mx

        mx.eval(*(array for item in self.pending for array in item[1:3]))
        for layer, inds, scores, phase in self.pending:
            ids = [int(value) for value in inds.reshape(-1).tolist()]
            weights = [float(value) for value in scores.reshape(-1).tolist()]
            self.add_rows(scope, layer, phase, ids, weights)
            if phase == "decode":
                shape = tuple(int(value) for value in inds.shape)
                top_k = shape[-1]
                if len(ids) % top_k:
                    raise RuntimeError(f"invalid decode route shape: {shape}")
                for offset in range(0, len(ids), top_k):
                    self.add_decode_step(scope, layer, ids[offset : offset + top_k])
        self.pending.clear()

    def finish_sample(
        self,
        scope: str,
        prompt_tokens: int,
        *,
        source_samples: int = 1,
    ) -> None:
        current = self._current_decode.pop(scope, {})
        self._decode_sequences[scope].append(
            {
                "prompt_tokens": int(prompt_tokens),
                "source_samples": int(source_samples),
                "layers": {
                    str(layer): sequence for layer, sequence in sorted(current.items())
                },
            }
        )
        self.sample_counts[scope] += int(source_samples)
        self.pack_counts[scope] += 1
        self.token_counts[scope] += int(prompt_tokens)

    @staticmethod
    def _phase_scores(counts: list[int], mass: list[float]) -> list[float]:
        count_total = max(sum(counts), 1)
        mass_total = max(sum(mass), 1e-12)
        return [
            0.75 * count / count_total + 0.25 * weight / mass_total
            for count, weight in zip(counts, mass, strict=True)
        ]

    def build(
        self,
        *,
        metadata: dict[str, Any],
        prefill_weight: float = 0.35,
        decode_weight: float = 0.65,
    ) -> dict[str, Any]:
        if prefill_weight < 0 or decode_weight < 0:
            raise ValueError("phase weights cannot be negative")
        scopes: dict[str, Any] = {}
        for scope in sorted(self._counts):
            observed_layers = sorted(
                set(self._counts[scope]["prefill"]) | set(self._counts[scope]["decode"])
            )
            layers: dict[str, list[int]] = {}
            stats: dict[str, Any] = {}
            for layer in observed_layers:
                phase_scores: dict[str, list[float]] = {}
                phase_weights: dict[str, float] = {}
                for phase, configured_weight in (
                    ("prefill", prefill_weight),
                    ("decode", decode_weight),
                ):
                    counts = self._counts[scope][phase].get(
                        layer, [0] * self.num_experts
                    )
                    mass = self._mass[scope][phase].get(layer, [0.0] * self.num_experts)
                    if sum(counts):
                        phase_scores[phase] = self._phase_scores(counts, mass)
                        phase_weights[phase] = configured_weight
                denominator = sum(phase_weights.values())
                if denominator <= 0:
                    raise RuntimeError(f"scope {scope} layer {layer} has no routes")
                scores = [0.0] * self.num_experts
                for phase, values in phase_scores.items():
                    weight = phase_weights[phase] / denominator
                    for expert, value in enumerate(values):
                        scores[expert] += weight * value
                ranking = sorted(
                    range(self.num_experts),
                    key=lambda expert: (-scores[expert], expert),
                )
                selected = ranking[: self.capacity]
                layers[str(layer)] = selected
                phase_stats = {}
                for phase in ("prefill", "decode"):
                    counts = self._counts[scope][phase].get(
                        layer, [0] * self.num_experts
                    )
                    mass = self._mass[scope][phase].get(layer, [0.0] * self.num_experts)
                    routes = sum(counts)
                    routed_mass = sum(mass)
                    phase_stats[phase] = {
                        "routes": routes,
                        "selected_route_coverage": (
                            sum(counts[expert] for expert in selected) / routes
                            if routes
                            else None
                        ),
                        "selected_mass_coverage": (
                            sum(mass[expert] for expert in selected) / routed_mass
                            if routed_mass
                            else None
                        ),
                        "counts_by_expert": counts,
                        "mass_by_expert": mass,
                    }
                stats[str(layer)] = {
                    "rank16_score": scores[ranking[self.capacity - 1]],
                    "rank17_score": scores[ranking[self.capacity]],
                    "phases": phase_stats,
                }
            scopes[scope] = {
                "layers": layers,
                "samples": self.sample_counts[scope],
                "packs": self.pack_counts[scope],
                "prompt_tokens": self.token_counts[scope],
                "layer_stats": stats,
                "decode_sequences": self._decode_sequences[scope],
                "decode_transitions": self._build_transitions(scope),
            }
        return refine_glm5_scope_profile(
            {
                "format": "omlx-glm5-dynamic-scope-profile",
                "version": 2,
                "capacity": self.capacity,
                "num_experts": self.num_experts,
                "phase_weights": {
                    "prefill": prefill_weight,
                    "decode": decode_weight,
                },
                "scopes": scopes,
                "metadata": metadata,
            }
        )

    def _build_transitions(self, scope: str) -> dict[str, Any]:
        """Serialize sparse same-layer transitions in deterministic rank order."""

        result: dict[str, Any] = {}
        observed_layers = sorted(self._transition_counts[scope])
        for layer in observed_layers:
            sources: dict[str, Any] = {}
            pair_count = 0
            for source in sorted(self._transition_counts[scope][layer]):
                target_counts = self._transition_counts[scope][layer][source]
                ranked = sorted(
                    target_counts.items(), key=lambda item: (-item[1], item[0])
                )
                pair_count += sum(target_counts.values())
                sources[str(source)] = {
                    "observations": self._transition_observations[scope][layer].get(
                        source, 0
                    ),
                    "targets": [
                        [target, count]
                        for target, count in ranked[:TRANSITION_TARGET_LIMIT]
                    ],
                }
            result[str(layer)] = {
                "steps": self._transition_steps[scope][layer],
                "pair_count": pair_count,
                "target_limit_per_source": TRANSITION_TARGET_LIMIT,
                "sources": sources,
            }
        return result


def refine_glm5_scope_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Derive phase-specific banks from the raw aggregate arrays in a profile."""

    capacity = int(profile["capacity"])
    num_experts = int(profile["num_experts"])
    phase_weights = profile["phase_weights"]
    for scope in profile["scopes"].values():
        phase_layers = {"prefill": {}, "decode": {}}
        for layer, stats in scope["layer_stats"].items():
            for phase in ("prefill", "decode"):
                phase_stats = stats["phases"][phase]
                counts = phase_stats["counts_by_expert"]
                mass = phase_stats["mass_by_expert"]
                if phase_stats["routes"]:
                    scores = Glm5ScopeCollector._phase_scores(counts, mass)
                    ranking = sorted(
                        range(num_experts),
                        key=lambda expert: (-scores[expert], expert),
                    )
                    selected = ranking[:capacity]
                else:
                    selected = list(scope["layers"][layer])
                phase_layers[phase][layer] = selected
                routes = sum(counts)
                routed_mass = sum(mass)
                phase_stats["phase_bank_route_coverage"] = (
                    sum(counts[expert] for expert in selected) / routes
                    if routes
                    else None
                )
                phase_stats["phase_bank_mass_coverage"] = (
                    sum(mass[expert] for expert in selected) / routed_mass
                    if routed_mass
                    else None
                )
        scope["phase_layers"] = phase_layers
    profile["metadata"]["bank_policy"] = {
        "initial": f"scope prefill Top-{capacity}",
        "after_first_token": f"scope decode Top-{capacity}, then dynamic SLRU",
        "mixed_phase_weights": phase_weights,
    }
    return profile


__all__ = [
    "Glm5ScopeCollector",
    "TRANSITION_TARGET_LIMIT",
    "refine_glm5_scope_profile",
]
