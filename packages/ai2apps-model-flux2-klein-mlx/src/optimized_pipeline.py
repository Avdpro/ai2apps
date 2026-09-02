"""AI2Apps optimizations layered on the audited mflux FLUX.2 graph."""

from __future__ import annotations

import copy
import os
from collections import OrderedDict

import mlx.core as mx
from mflux.models.flux2.variants import Flux2Klein, Flux2KleinEdit

from flux2_metal_optimizations import install_flux2_metal_fusions


_METAL_FUSIONS_ENABLED = (
    os.environ.get("AI2APPS_FLUX2_METAL_FUSIONS", "0").strip().lower()
    not in {"0", "false", "off", "no"}
    and install_flux2_metal_fusions()
)


class _PromptEmbeddingCache:
    """Small evaluated LRU cache shared by generation and edit pipelines."""

    _prompt_cache_limit = 8

    def _cached_prompt_pair(self, key, factory):
        self._ai2apps_prompt_cache_requests = getattr(self, "_ai2apps_prompt_cache_requests", 0) + 1
        cache = getattr(self, "_ai2apps_prompt_cache", None)
        if cache is None:
            cache = OrderedDict()
            self._ai2apps_prompt_cache = cache
        if key in cache:
            self._ai2apps_prompt_cache_hits = getattr(self, "_ai2apps_prompt_cache_hits", 0) + 1
            value = cache.pop(key)
            cache[key] = value
            return value
        value = factory()
        mx.eval(*[item for item in value if item is not None])
        cache[key] = value
        while len(cache) > self._prompt_cache_limit:
            cache.popitem(last=False)
        return value


class _Flux2OptimizationMixin(_PromptEmbeddingCache):
    """Caches expensive immutable graph objects for the life of a worker."""

    def _predict(self, transformer):
        # mflux constructs a fresh mx.compile wrapper for every image. Retaining
        # the callable lets MLX reuse its per-shape compiled executables across
        # regenerate requests instead of rebuilding the wrapper each time.
        predict = getattr(self, "_ai2apps_compiled_predict", None)
        if predict is None:
            predict = super()._predict(transformer)
            self._ai2apps_compiled_predict = predict
            self._ai2apps_predict_builds = getattr(self, "_ai2apps_predict_builds", 0) + 1
        return predict

    def _cached_predict(self, transformer):
        predict = getattr(self, "_ai2apps_kv_cached_predict", None)
        if predict is None:
            predict = super()._cached_predict(transformer)
            self._ai2apps_kv_cached_predict = predict
            self._ai2apps_kv_predict_builds = getattr(
                self, "_ai2apps_kv_predict_builds", 0
            ) + 1
        return predict

    def ai2apps_optimization_stats(self):
        requests = getattr(self, "_ai2apps_prompt_cache_requests", 0)
        hits = getattr(self, "_ai2apps_prompt_cache_hits", 0)
        return {
            "prompt_cache_requests": requests,
            "prompt_cache_hits": hits,
            "prompt_cache_hit_rate": hits / requests if requests else 0.0,
            "prompt_cache_entries": len(getattr(self, "_ai2apps_prompt_cache", ())),
            "compiled_predict_builds": getattr(self, "_ai2apps_predict_builds", 0),
            "kv_cached_predict_builds": getattr(
                self, "_ai2apps_kv_predict_builds", 0
            ),
            "metal_fusions_enabled": _METAL_FUSIONS_ENABLED,
        }


class OptimizedFlux2Klein(_Flux2OptimizationMixin, Flux2Klein):
    def _encode_prompt_pair(self, *, prompt, negative_prompt, guidance):
        key = (prompt, negative_prompt, float(guidance))
        return self._cached_prompt_pair(
            key,
            lambda: super(OptimizedFlux2Klein, self)._encode_prompt_pair(
                prompt=prompt, negative_prompt=negative_prompt, guidance=guidance
            ),
        )


class OptimizedFlux2KleinEdit(_Flux2OptimizationMixin, Flux2KleinEdit):
    def __init__(self, *args, model_config=None, **kwargs):
        if model_config is None:
            super().__init__(*args, **kwargs)
        else:
            # mflux 0.19 ships FLUX.2's extract/cached implementation but its
            # shared model configs leave the feature flag false. A private copy
            # selects that existing non-compiled path; the original lru-cached
            # config is never mutated.
            model_config = copy.copy(model_config)
            model_config.supports_kv_cache = True
            super().__init__(*args, model_config=model_config, **kwargs)

    def _encode_prompt_pair(self, *, prompt, negative_prompt, guidance):
        key = (prompt, negative_prompt, float(guidance))
        return self._cached_prompt_pair(
            key,
            lambda: super(OptimizedFlux2KleinEdit, self)._encode_prompt_pair(
                prompt=prompt, negative_prompt=negative_prompt, guidance=guidance
            ),
        )
