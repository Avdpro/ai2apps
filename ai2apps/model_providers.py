"""Installable Service-backed model provider contracts and routing helpers.

Model weights deliberately remain outside the Package archive.  An installed
Service owns its runtime and may advertise one or more OpenAI-compatible model
IDs through ``service.yaml``.  The platform keeps model selection and default
role routing independent from the provider implementation.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import psutil
from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse

from ai2apps.model_worker.audio_capabilities import (
    AudioCapabilitiesError,
    default_audio_capabilities,
    validate_audio_capabilities,
)
from ai2apps.model_worker.image_capabilities import (
    ImageCapabilitiesError,
    default_image_capabilities,
    validate_image_capabilities,
)
from ai2apps.model_worker.video_capabilities import (
    VideoCapabilitiesError,
    validate_video_capabilities,
)
from ai2apps.services import ServiceInstanceStatus, ServiceStatus
from ai2apps.video_policy import is_temporarily_disabled_video_model
from ai2apps.worker_resources import GIB, MIB, estimate_request_transient_bytes
from ai2apps.worker_scheduler import SchedulerLease, WorkerJobScheduler, WorkloadClass

MODEL_TYPES = frozenset(
    {
        "llm",
        "vlm",
        "image_generation",
        "audio_stt",
        "audio_tts",
        "audio_processing",
        "video_generation",
        "embedding",
    }
)

DEFAULT_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "llm": ("work", "conversation"),
    "vlm": ("work", "conversation", "image_recognition"),
    "image_generation": ("image_generation",),
    "audio_stt": ("speech_recognition",),
    "audio_tts": ("speech_generation",),
    "audio_processing": ("audio_processing",),
    "video_generation": ("video_generation",),
    "embedding": ("text_embeddings",),
}

DEFAULT_PATHS = {
    "chat_completions": "/v1/chat/completions",
    "responses": "/v1/responses",
    "image_generation": "/v1/images/generations",
    "image_edit": "/v1/images/edits",
    "audio_transcription": "/v1/audio/transcriptions",
    "audio_speech": "/v1/audio/speech",
    "audio_process": "/v1/audio/process",
    "video_generation": "/v1/videos/generations",
    "embeddings": "/v1/embeddings",
}

_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
_CAPABILITY = re.compile(r"^[a-z][a-z0-9._-]{0,127}$")
_HF_REPOSITORY = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}/[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)
_IMMUTABLE_REVISION = re.compile(r"^[0-9a-fA-F]{40,64}$")
_PREPARATION_RECIPE = re.compile(r"^[a-z][a-z0-9._/-]{0,127}$")
_DISTRIBUTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


class ModelProviderContractError(ValueError):
    pass


def _validate_model_weights(value: Any, *, field: str) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) - {
        "provider",
        "repo_id",
        "revision",
        "preparation",
        "distribution_id",
    }:
        raise ModelProviderContractError(f"{field} is invalid")
    provider = value.get("provider")
    repo_id = value.get("repo_id")
    revision = value.get("revision")
    if provider != "huggingface":
        raise ModelProviderContractError(f"{field}.provider must be 'huggingface'")
    if not isinstance(repo_id, str) or not _HF_REPOSITORY.fullmatch(repo_id):
        raise ModelProviderContractError(f"{field}.repo_id is invalid")
    if not isinstance(revision, str) or not _IMMUTABLE_REVISION.fullmatch(revision):
        raise ModelProviderContractError(
            f"{field}.revision must be an immutable 40-64 character commit digest"
        )
    preparation = value.get("preparation", {"recipe": "native"})
    if not isinstance(preparation, dict):
        raise ModelProviderContractError(f"{field}.preparation is invalid")
    recipe = preparation.get("recipe", "native")
    if not isinstance(recipe, str) or not _PREPARATION_RECIPE.fullmatch(recipe):
        raise ModelProviderContractError(f"{field}.preparation.recipe is invalid")
    try:
        normalized_preparation = json.loads(json.dumps(preparation))
    except (TypeError, ValueError) as exc:
        raise ModelProviderContractError(
            f"{field}.preparation must contain JSON values"
        ) from exc
    normalized_preparation["recipe"] = recipe
    normalized = {
        "provider": provider,
        "repo_id": repo_id,
        "revision": revision.lower(),
        "preparation": normalized_preparation,
    }
    distribution_id = value.get("distribution_id")
    if distribution_id is not None:
        if not isinstance(distribution_id, str) or not _DISTRIBUTION_ID.fullmatch(
            distribution_id
        ):
            raise ModelProviderContractError(f"{field}.distribution_id is invalid")
        normalized["distribution_id"] = distribution_id
    return normalized


def validate_package_models(
    service_key: str,
    models: Any,
    *,
    runtime_mode: str,
    protocol: str,
) -> tuple[dict[str, Any], ...]:
    """Validate and normalize the ``service.yaml.models`` declaration."""

    if models is None:
        return ()
    if not isinstance(models, list) or len(models) > 128:
        raise ModelProviderContractError("models must be an array of at most 128 entries")
    if models and runtime_mode in {"embedded", "in_process"}:
        raise ModelProviderContractError(
            "Model providers must use a managed_process or external HTTP runtime"
        )
    if models and protocol not in {
        "openai-compatible",
        "http-json",
        "ai2apps-model-worker/v1",
    }:
        raise ModelProviderContractError(
            "Model providers require openai-compatible or http-json protocol"
        )

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    prefix = service_key + "/"
    for index, raw in enumerate(models):
        if not isinstance(raw, dict):
            raise ModelProviderContractError(f"models[{index}] must be an object")
        model_id = raw.get("id")
        if (
            not isinstance(model_id, str)
            or not _MODEL_ID.fullmatch(model_id)
            or not model_id.startswith(prefix)
        ):
            raise ModelProviderContractError(
                f"models[{index}].id must start with {prefix!r}"
            )
        if model_id in seen:
            raise ModelProviderContractError(f"Duplicate model id: {model_id}")
        seen.add(model_id)
        model_type = raw.get("model_type", raw.get("type"))
        if model_type not in MODEL_TYPES:
            raise ModelProviderContractError(
                f"models[{index}].model_type is unsupported: {model_type!r}"
            )
        display_name = raw.get("display_name", raw.get("name", model_id))
        if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 160:
            raise ModelProviderContractError(f"models[{index}].display_name is invalid")
        upstream_id = raw.get("upstream_id", model_id)
        if not isinstance(upstream_id, str) or not upstream_id or len(upstream_id) > 512:
            raise ModelProviderContractError(f"models[{index}].upstream_id is invalid")
        capabilities = raw.get("capabilities", DEFAULT_CAPABILITIES[model_type])
        if (
            not isinstance(capabilities, (list, tuple))
            or not capabilities
            or not all(isinstance(value, str) and _CAPABILITY.fullmatch(value) for value in capabilities)
        ):
            raise ModelProviderContractError(f"models[{index}].capabilities is invalid")
        paths = raw.get("endpoints", raw.get("paths", {}))
        if not isinstance(paths, dict) or set(paths) - set(DEFAULT_PATHS):
            raise ModelProviderContractError(f"models[{index}].endpoints is invalid")
        normalized_paths = dict(DEFAULT_PATHS)
        for operation, path in paths.items():
            if (
                not isinstance(path, str)
                or not path.startswith("/")
                or "//" in path
                or ".." in path.split("/")
                or len(path) > 240
            ):
                raise ModelProviderContractError(
                    f"models[{index}].endpoints.{operation} is invalid"
                )
            normalized_paths[operation] = path
        context_window = raw.get("context_window")
        if context_window is not None and (
            not isinstance(context_window, int)
            or isinstance(context_window, bool)
            or context_window <= 0
        ):
            raise ModelProviderContractError(f"models[{index}].context_window is invalid")
        weights = _validate_model_weights(
            raw.get("weights"), field=f"models[{index}].weights"
        )
        audio_capabilities = None
        if model_type.startswith("audio_"):
            try:
                audio_capabilities = validate_audio_capabilities(
                    raw.get("audio_capabilities")
                    or default_audio_capabilities(model_type),
                    model_type=model_type,
                )
            except AudioCapabilitiesError as exc:
                raise ModelProviderContractError(
                    f"models[{index}].audio_capabilities is invalid: {exc}"
                ) from exc
        video_capabilities = None
        if model_type == "video_generation":
            try:
                video_capabilities = validate_video_capabilities(
                    raw.get("video_capabilities")
                )
            except VideoCapabilitiesError as exc:
                raise ModelProviderContractError(
                    f"models[{index}].video_capabilities is invalid: {exc}"
                ) from exc
        image_capabilities = None
        if model_type == "image_generation":
            try:
                image_capabilities = validate_image_capabilities(
                    raw.get("image_capabilities") or default_image_capabilities()
                )
            except ImageCapabilitiesError as exc:
                raise ModelProviderContractError(
                    f"models[{index}].image_capabilities is invalid: {exc}"
                ) from exc
        normalized.append(
            {
                "id": model_id,
                "display_name": display_name.strip(),
                "model_type": model_type,
                "upstream_id": upstream_id,
                "capabilities": sorted(set(capabilities)),
                "endpoints": normalized_paths,
                "context_window": context_window,
                "weights": weights,
                "audio_capabilities": audio_capabilities,
                "video_capabilities": video_capabilities,
                "image_capabilities": image_capabilities,
                "metadata": raw.get("metadata", {}) if isinstance(raw.get("metadata", {}), dict) else {},
            }
        )
    return tuple(normalized)


@dataclass(frozen=True, slots=True)
class PackageModel:
    id: str
    display_name: str
    model_type: str
    upstream_id: str
    capabilities: tuple[str, ...]
    endpoints: Mapping[str, str]
    context_window: int | None
    metadata: Mapping[str, Any]
    audio_capabilities: Mapping[str, Any] | None
    video_capabilities: Mapping[str, Any] | None
    image_capabilities: Mapping[str, Any] | None
    service_key: str
    provider_key: str
    endpoint: str | None
    checkpoint_ready: bool = True
    weights: Mapping[str, Any] | None = None
    internal_headers: Mapping[str, str] | None = None
    scheduler: WorkerJobScheduler | None = None
    runtime: Any | None = None

    def public_catalog_entry(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "display_name": self.display_name,
            "model_path": f"package://{self.service_key}/{self.id}",
            "loaded": self.checkpoint_ready,
            "is_loading": False,
            "estimated_size": 0,
            "estimated_size_formatted": "0 B",
            "actual_size": 0,
            "actual_size_formatted": None,
            "pinned": False,
            "is_default": False,
            # An installed provider is not usable until its exact pinned
            # checkpoint has been prepared by the trusted Host.
            "is_hidden": not self.checkpoint_ready or bool(self.metadata.get("internal")),
            "is_favorite": False,
            "is_helper": False,
            "engine_type": "package",
            "model_type": self.model_type,
            "config_model_type": "package_provider",
            "capabilities": list(self.capabilities),
            "cache_moe": False,
            "source_type": "package",
            "source_repo_id": (self.weights or {}).get("repo_id"),
            "virtual": True,
            "owned_by": self.service_key,
            "model_context_length": self.context_window,
            "max_context_window": self.context_window,
            "package_service": self.service_key,
            "package_weights": dict(self.weights or {}),
            "checkpoint_ready": self.checkpoint_ready,
            "worker_running": self.endpoint is not None,
            "audio_capabilities": dict(self.audio_capabilities or {}),
            "video_capabilities": dict(self.video_capabilities or {}),
            "image_capabilities": dict(self.image_capabilities or {}),
        }


def list_package_models(runtime: Any | None) -> tuple[PackageModel, ...]:
    if runtime is None or getattr(runtime, "services", None) is None:
        return ()
    result: list[PackageModel] = []
    for service in runtime.services.list_services():
        if service.source != "installed" or service.status is not ServiceStatus.ENABLED:
            continue
        try:
            instance = runtime.services.get_instance_for_service(service.id)
        except Exception:
            continue
        running = instance.status in {
            ServiceInstanceStatus.RUNNING,
            ServiceInstanceStatus.DEGRADED,
        } and bool(instance.endpoint)
        internal_headers: Mapping[str, str] | None = None
        package_manager = getattr(runtime, "package_manager", None)
        if not running:
            if instance.status is not ServiceInstanceStatus.STOPPED:
                continue
            package = (
                package_manager.packages.active(service.service_key)
                if package_manager is not None
                else None
            )
            if package is None or package.protocol != "ai2apps-model-worker/v1":
                continue
        if package_manager is not None:
            internal_headers = package_manager.supervisor.internal_headers(
                service.service_key
            )
        checkpoint_rows, _roots = package_manager.supervisor._model_worker_checkpoints(
            service.config,
            package_manager.supervisor._huggingface_hub_cache(),
            package_manager.supervisor.model_root,
        ) if package_manager is not None else ((), ())
        checkpoints = {row["model_id"]: row for row in checkpoint_rows}
        for raw in service.config.get("models", []):
            checkpoint = checkpoints.get(raw["id"])
            result.append(
                PackageModel(
                    id=raw["id"],
                    display_name=raw["display_name"],
                    model_type=raw["model_type"],
                    upstream_id=raw["upstream_id"],
                    capabilities=tuple(raw["capabilities"]),
                    endpoints=dict(raw["endpoints"]),
                    context_window=raw.get("context_window"),
                    metadata=dict(raw.get("metadata", {})),
                    audio_capabilities=(
                        dict(raw["audio_capabilities"])
                        if isinstance(raw.get("audio_capabilities"), dict)
                        else None
                    ),
                    video_capabilities=(
                        dict(raw["video_capabilities"])
                        if isinstance(raw.get("video_capabilities"), dict)
                        else None
                    ),
                    image_capabilities=(
                        dict(raw["image_capabilities"])
                        if isinstance(raw.get("image_capabilities"), dict)
                        else None
                    ),
                    service_key=service.service_key,
                    provider_key=instance.provider_key,
                    endpoint=(
                        instance.endpoint.rstrip("/")
                        if running and instance.endpoint
                        else None
                    ),
                    checkpoint_ready=(
                        checkpoint is None or checkpoint.get("path") is not None
                    ),
                    weights=dict(raw.get("weights") or {}),
                    internal_headers=internal_headers,
                    scheduler=getattr(runtime, "worker_scheduler", None),
                    runtime=runtime,
                )
            )
    return tuple(sorted(result, key=lambda item: item.id))


def resolve_package_model(runtime: Any | None, model_id: str) -> PackageModel | None:
    return next((model for model in list_package_models(runtime) if model.id == model_id), None)


async def _ensure_package_model_ready(model: PackageModel) -> PackageModel:
    if model.endpoint is not None:
        return model
    runtime = model.runtime
    package_manager = getattr(runtime, "package_manager", None)
    if package_manager is None:
        raise HTTPException(status_code=503, detail="Model Worker is not running")
    try:
        await package_manager.start(model.service_key)
    except Exception as error:
        raise HTTPException(
            status_code=503,
            detail={
                "code": getattr(error, "code", "worker_start_failed"),
                "message": str(error),
            },
        ) from error
    resources = getattr(runtime, "worker_resources", None)
    if resources is not None:
        resources.mark_started(model.service_key)
    refreshed = resolve_package_model(runtime, model.id)
    if (
        refreshed is None
        or refreshed.endpoint is None
    ):
        raise HTTPException(status_code=503, detail="Model Worker did not become ready")
    return refreshed


async def ensure_package_model_ready(model: PackageModel) -> PackageModel:
    """Start a dormant Package Model Worker and return its refreshed contract."""

    return await _ensure_package_model_ready(model)


def estimate_model_resident_bytes(
    model_type: str, metadata: Mapping[str, Any] | None = None
) -> int:
    """Return a bounded Host-owned cold-start estimate for one model."""

    value = (metadata or {}).get("estimated_resident_bytes")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return min(value, 256 * GIB)
    return {
        "llm": 2 * GIB,
        "vlm": 3 * GIB,
        "image_generation": 2 * GIB,
        "video_generation": 4 * GIB,
        "audio_stt": 1 * GIB,
        "audio_tts": 1 * GIB,
        "audio_processing": 1 * GIB,
        "embedding": 512 * MIB,
    }.get(model_type, 2 * GIB)


def estimate_service_models_resident_bytes(models: Any) -> int:
    """Estimate a Service cold start using its largest declared model."""

    if not isinstance(models, (list, tuple)):
        return 512 * MIB
    estimates = [
        estimate_model_resident_bytes(
            raw.get("model_type", raw.get("type", "")),
            raw.get("metadata") if isinstance(raw.get("metadata"), dict) else None,
        )
        for raw in models
        if isinstance(raw, dict)
    ]
    return max(estimates, default=512 * MIB)


def recommended_model_configuration_id(
    models: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    total_memory_bytes: int | None = None,
) -> str | None:
    """Choose the highest-fidelity variant that is a practical device default.

    Packages opt in through ``metadata.device_recommendation``.  Minimum memory
    describes an expert-only lower bound; preferred memory is deliberately more
    conservative and controls the automatic recommendation.
    """

    weighted = [
        model
        for model in models
        if isinstance(model, dict)
        and isinstance(model.get("id"), str)
        and isinstance(model.get("weights"), dict)
        and not is_temporarily_disabled_video_model(model)
    ]
    if not weighted:
        return None
    profiles: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for model in weighted:
        metadata = model.get("metadata")
        recommendation = (
            metadata.get("device_recommendation")
            if isinstance(metadata, dict)
            else None
        )
        if isinstance(recommendation, dict):
            profiles.append((model, recommendation))
    if not profiles:
        return weighted[0]["id"]

    memory_gib = (
        total_memory_bytes
        if total_memory_bytes is not None
        else int(psutil.virtual_memory().total)
    ) / (1024**3)
    preferred = [
        item
        for item in profiles
        if memory_gib >= float(item[1].get("preferred_memory_gib", float("inf")))
    ]
    if preferred:
        chosen = max(
            preferred,
            key=lambda item: (
                float(item[1].get("quality_rank", 0)),
                float(item[1].get("preferred_memory_gib", 0)),
            ),
        )
    else:
        chosen = min(
            profiles,
            key=lambda item: (
                float(item[1].get("minimum_memory_gib", float("inf"))),
                float(item[1].get("quality_rank", 0)),
            ),
        )
    return chosen[0]["id"]


def installed_model_preparation_recipes(runtime: Any | None) -> tuple[dict[str, Any], ...]:
    """Build trusted Host preparation recipes from active Worker manifests.

    This function interprets static data only. It never imports Package code.
    """

    repository = None if runtime is None else getattr(runtime, "package_repository", None)
    if repository is None:
        return ()
    recipes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for package in repository.installed():
        if (
            getattr(package.status, "value", package.status) != "active"
            or not package.manifest.get("models")
        ):
            continue
        package_root = Path(package.store_path).resolve(strict=True)
        from ai2apps.packages.supervisor import ManagedServiceSupervisor

        checkpoint_rows, _roots = ManagedServiceSupervisor._model_worker_checkpoints(
            package.manifest,
            ManagedServiceSupervisor._huggingface_hub_cache(),
        )
        checkpoints = {row["model_id"]: row for row in checkpoint_rows}
        for model in package.manifest.get("models", []):
            weights = model.get("weights", {}) if isinstance(model, dict) else {}
            preparation = weights.get("preparation", {})
            recipe_kind = preparation.get("recipe", "native")
            if recipe_kind == "native":
                checkpoint = checkpoints.get(model.get("id"), {})
                recipe_id = model.get("id")
                metadata = model.get("metadata", {})
                if not isinstance(metadata, dict):
                    raise ModelProviderContractError(
                        "Native model metadata must be an object"
                    )
                required_model_ids = metadata.get("required_model_ids", ())
                if not isinstance(required_model_ids, (list, tuple)) or any(
                    not isinstance(item, str) or not item
                    for item in required_model_ids
                ):
                    raise ModelProviderContractError(
                        "Native model metadata.required_model_ids must be model IDs"
                    )
                if not isinstance(recipe_id, str) or not recipe_id or recipe_id in seen:
                    raise ModelProviderContractError("Invalid or duplicate native model ID")
                recipes.append(
                    {
                        "id": recipe_id,
                        "name": model.get("display_name", recipe_id),
                        "description": package.manifest.get("description", ""),
                        "recipe": "native",
                        "service_key": package.service_key,
                        "family": metadata.get("family", "native"),
                        "internal": bool(metadata.get("internal", False)),
                        "required_model_ids": tuple(required_model_ids),
                        "execution_modes": ("full",),
                        "storage_policies": ("keep_source",),
                        "storage_estimates": {},
                        "engine": {},
                        "sources": (
                            {
                                "id": "huggingface",
                                "label": "HuggingFace",
                                "repo_id": weights["repo_id"],
                                "revision": weights["revision"],
                                "mirrors": (
                                    {
                                        "provider": "modelscope",
                                        "repo_id": metadata["modelscope"]["repo_id"],
                                        "revision": metadata["modelscope"].get("revision", "master"),
                                        "preferred": metadata["modelscope"].get("preferred", True) is True,
                                        "allow_patterns": tuple(
                                            item
                                            for item in metadata["modelscope"].get("allow_patterns", ())
                                            if isinstance(item, str) and item
                                        ),
                                    },
                                ) if isinstance(metadata.get("modelscope"), dict) else (),
                            },
                        ),
                        **(
                            {"distribution_id": weights["distribution_id"]}
                            if "distribution_id" in weights
                            else {}
                        ),
                        "memory_tiers": (),
                        "device_recommendation": dict(
                            metadata.get("device_recommendation")
                            if isinstance(metadata.get("device_recommendation"), dict)
                            else {}
                        ),
                        "installed": checkpoint.get("path") is not None,
                    }
                )
                seen.add(recipe_id)
                continue
            if recipe_kind != "ai2apps/cache-moe/v1":
                continue
            recipe_id = preparation.get("install_id")
            if not isinstance(recipe_id, str) or not recipe_id or recipe_id in seen:
                raise ModelProviderContractError("Invalid or duplicate preparation install_id")
            engine = dict(preparation.get("engine", {}))
            for field in ("scope_asset", "scope_pack"):
                relative = engine.get(field)
                if (
                    not isinstance(relative, str)
                    or relative.startswith("/")
                    or ".." in relative.split("/")
                ):
                    raise ModelProviderContractError(
                        f"Preparation engine.{field} must be Package-relative"
                    )
                candidate = (package_root / relative).resolve(strict=True)
                try:
                    candidate.relative_to(package_root)
                except ValueError as exc:
                    raise ModelProviderContractError(
                        f"Preparation engine.{field} escapes the Package"
                    ) from exc
                if not candidate.is_file():
                    raise ModelProviderContractError(
                        f"Preparation engine.{field} is missing"
                    )
                engine[field] = str(candidate)
            recipes.append(
                {
                    "id": recipe_id,
                    "name": model.get("display_name", recipe_id),
                    "description": package.manifest.get("description", ""),
                    "family": preparation["family"],
                    "execution_modes": tuple(preparation.get("execution_modes", ())),
                    "storage_policies": tuple(preparation.get("storage_policies", ())),
                    "storage_estimates": dict(preparation.get("storage_estimates", {})),
                    "engine": engine,
                    "sources": (
                        {
                            "id": "huggingface",
                            "label": "HuggingFace",
                            "repo_id": weights["repo_id"],
                            "revision": weights["revision"],
                        },
                    ),
                    **(
                        {"distribution_id": weights["distribution_id"]}
                        if "distribution_id" in weights
                        else {}
                    ),
                    "scope_name": preparation.get("scope_name", "general"),
                    "conversion": dict(preparation.get("conversion", {})),
                    "memory_tiers": tuple(preparation.get("memory_tiers", ())),
                    **(
                        {"arena_tail_slots": int(preparation["arena_tail_slots"])}
                        if "arena_tail_slots" in preparation
                        else {}
                    ),
                }
            )
            seen.add(recipe_id)
    recipes_by_id = {recipe["id"]: recipe for recipe in recipes}
    resolving: set[str] = set()

    def dependencies_ready(recipe: dict[str, Any]) -> bool:
        recipe_id = recipe["id"]
        if recipe_id in resolving:
            return False
        resolving.add(recipe_id)
        try:
            return bool(recipe.get("installed")) and all(
                required is not None and dependencies_ready(required)
                for required_id in recipe.get("required_model_ids", ())
                for required in (recipes_by_id.get(required_id),)
            )
        finally:
            resolving.remove(recipe_id)

    # A model that promises a required helper checkpoint is not ready merely
    # because its own weights are cached.  This is especially important after
    # a Package upgrade adds a new dependency to an already-downloaded model.
    for recipe in recipes:
        if recipe.get("recipe") == "native":
            recipe["installed"] = dependencies_ready(recipe)
    recommended_ids: set[str] = set()
    for package in repository.installed():
        models = package.manifest.get("models", [])
        has_profiles = isinstance(models, list) and any(
            isinstance(model, dict)
            and isinstance(model.get("metadata"), dict)
            and isinstance(model["metadata"].get("device_recommendation"), dict)
            for model in models
        )
        if has_profiles and (
            recommended := recommended_model_configuration_id(models)
        ):
            recommended_ids.add(recommended)
    for recipe in recipes:
        recipe["recommended"] = recipe["id"] in recommended_ids
    return tuple(sorted(recipes, key=lambda item: (not item["recommended"], item["name"])))


def _response_headers(response: httpx.Response) -> dict[str, str]:
    accepted = {"content-type", "content-disposition", "cache-control", "x-request-id"}
    return {
        key: value
        for key, value in response.headers.items()
        if key.lower() in accepted
        or key.lower().startswith("x-ai2apps-audio-")
        or key.lower().startswith("x-ai2apps-feature-")
    }


async def proxy_package_json(
    model: PackageModel,
    operation: str,
    payload: Mapping[str, Any],
    *,
    workload_class: WorkloadClass = WorkloadClass.LOCAL_FOREGROUND,
    request_id: str | None = None,
    actor_id: str | None = None,
    app_id: str | None = None,
    session_id: str | None = None,
    queue_timeout_seconds: float | None = None,
) -> Response:
    if model.runtime is not None:
        model = resolve_package_model(model.runtime, model.id) or model
    path = model.endpoints.get(operation)
    if not path:
        raise HTTPException(status_code=400, detail=f"Model does not support {operation}")
    body = dict(payload)
    body["model"] = model.upstream_id
    lease: SchedulerLease | None = None
    if model.scheduler is not None:
        try:
            lease = await model.scheduler.acquire(
                model.service_key,
                workload_class,
                request_id=request_id or body.get("idempotencyKey"),
                timeout_seconds=queue_timeout_seconds,
                actor_id=actor_id,
                app_id=app_id,
                session_id=session_id,
                estimated_resident_bytes=(
                    estimate_model_resident_bytes(model.model_type, model.metadata)
                    if model.endpoint is None
                    else 0
                ),
                estimated_transient_bytes=estimate_request_transient_bytes(
                    operation, body
                ),
            )
        except TimeoutError as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "worker_resource_unavailable",
                    "message": "Worker resources are temporarily unavailable",
                },
                headers={"Retry-After": "5"},
            ) from error
    # Provider endpoints are platform-managed loopback addresses. Inheriting
    # HTTP_PROXY/HTTPS_PROXY can send these private calls to a system proxy,
    # producing synthetic 502/503 responses that never reach the Service.
    client: httpx.AsyncClient | None = None
    try:
        model = await _ensure_package_model_ready(model)
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=15.0), trust_env=False
        )
        request = client.build_request(
            "POST",
            model.endpoint + path,
            json=body,
            headers=dict(model.internal_headers or {}),
        )
        response = await client.send(request, stream=bool(body.get("stream")))
    except httpx.HTTPError as exc:
        if client is not None:
            await client.aclose()
        if lease is not None:
            await lease.release(failed=True)
        raise HTTPException(status_code=502, detail=f"Model provider request failed: {exc}") from exc
    except BaseException:
        if client is not None:
            await client.aclose()
        if lease is not None:
            await lease.release(failed=True)
        raise
    if body.get("stream"):
        async def chunks():
            failed = response.status_code >= 400
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            except BaseException:
                failed = True
                raise
            finally:
                await response.aclose()
                await client.aclose()
                if lease is not None:
                    await lease.release(failed=failed)

        return StreamingResponse(
            chunks(),
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers=_response_headers(response),
        )
    status = response.status_code
    try:
        content = await response.aread()
        headers = _response_headers(response)
    except BaseException:
        await response.aclose()
        await client.aclose()
        if lease is not None:
            await lease.release(failed=True)
        raise
    await response.aclose()
    await client.aclose()
    if lease is not None:
        await lease.release(failed=status >= 400)
    return Response(content=content, status_code=status, headers=headers)


async def proxy_package_multipart(
    model: PackageModel,
    operation: str,
    *,
    data: Mapping[str, Any],
    files: Mapping[str, tuple[str, bytes, str]],
    workload_class: WorkloadClass = WorkloadClass.LOCAL_FOREGROUND,
    request_id: str | None = None,
    actor_id: str | None = None,
    app_id: str | None = None,
    session_id: str | None = None,
    queue_timeout_seconds: float | None = None,
) -> Response:
    if model.runtime is not None:
        model = resolve_package_model(model.runtime, model.id) or model
    path = model.endpoints.get(operation)
    if not path:
        raise HTTPException(status_code=400, detail=f"Model does not support {operation}")
    fields = {key: str(value) for key, value in data.items() if value is not None}
    fields["model"] = model.upstream_id
    lease: SchedulerLease | None = None
    if model.scheduler is not None:
        try:
            lease = await model.scheduler.acquire(
                model.service_key,
                workload_class,
                request_id=request_id or fields.get("idempotencyKey"),
                timeout_seconds=queue_timeout_seconds,
                actor_id=actor_id,
                app_id=app_id,
                session_id=session_id,
                estimated_resident_bytes=(
                    estimate_model_resident_bytes(model.model_type, model.metadata)
                    if model.endpoint is None
                    else 0
                ),
                estimated_transient_bytes=estimate_request_transient_bytes(
                    operation,
                    fields,
                    file_bytes=sum(len(value[1]) for value in files.values()),
                ),
            )
        except TimeoutError as error:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "worker_resource_unavailable",
                    "message": "Worker resources are temporarily unavailable",
                },
                headers={"Retry-After": "5"},
            ) from error
    stream = fields.get("stream", "").lower() == "true"
    client: httpx.AsyncClient | None = None
    try:
        model = await _ensure_package_model_ready(model)
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(300.0, connect=15.0), trust_env=False
        )
        request = client.build_request(
            "POST",
            model.endpoint + path,
            data=fields,
            files=files,
            headers=dict(model.internal_headers or {}),
        )
        response = await client.send(request, stream=stream)
    except httpx.HTTPError as exc:
        if client is not None:
            await client.aclose()
        if lease is not None:
            await lease.release(failed=True)
        raise HTTPException(status_code=502, detail=f"Model provider request failed: {exc}") from exc
    except BaseException:
        if client is not None:
            await client.aclose()
        if lease is not None:
            await lease.release(failed=True)
        raise
    if stream:
        async def chunks():
            failed = response.status_code >= 400
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            except BaseException:
                failed = True
                raise
            finally:
                await response.aclose()
                await client.aclose()
                if lease is not None:
                    await lease.release(failed=failed)

        return StreamingResponse(
            chunks(),
            status_code=response.status_code,
            media_type=response.headers.get("content-type"),
            headers=_response_headers(response),
        )
    status = response.status_code
    try:
        content = await response.aread()
        headers = _response_headers(response)
    except BaseException:
        await response.aclose()
        await client.aclose()
        if lease is not None:
            await lease.release(failed=True)
        raise
    await response.aclose()
    await client.aclose()
    if lease is not None:
        await lease.release(failed=status >= 400)
    return Response(
        content=content,
        status_code=status,
        headers=headers,
    )
