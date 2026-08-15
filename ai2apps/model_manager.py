"""Persistent Fusion profiles and cloud model providers for Model Manager."""

from __future__ import annotations

import json
import os
import re
import time
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

from ai2apps.fusion.profiles import (
    FusionProfile,
    fusion_profile_from_mapping,
    profile_to_mapping,
)

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")

DEFAULT_MODEL_PURPOSES: tuple[str, ...] = (
    "work_simple",
    "work_standard",
    "work_complex",
    "speech_recognition",
    "speech_generation",
    "audio_processing",
    "image_recognition",
    "image_generation",
    "video_generation",
)

BUILTIN_CLOUD_PROVIDERS: tuple[dict[str, Any], ...] = (
    {
        "id": "openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "protocol": "openai",
        "builtin": True,
    },
    {
        "id": "anthropic",
        "name": "Anthropic",
        "base_url": "https://api.anthropic.com",
        "protocol": "anthropic",
        "builtin": True,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "protocol": "openai",
        "builtin": True,
    },
)


def _safe_id(value: str, label: str) -> str:
    value = value.strip()
    if not _ID_RE.fullmatch(value):
        raise ValueError(f"{label} must use letters, numbers, dot, dash, or underscore")
    return value


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
    temporary.replace(path)
    path.chmod(0o600)


class ModelManagerStore:
    """Small file-backed registry whose API never returns secret values."""

    def __init__(self, base_path: str | Path):
        self.base_path = Path(base_path)
        self.fusion_dir = self.base_path / "fusion"
        self.cloud_path = self.base_path / "ai2apps" / "cloud-providers.json"
        self.defaults_path = self.base_path / "ai2apps" / "default-models.json"

    def default_models(self) -> dict[str, str]:
        """Return the complete system model routing table without stale keys."""

        try:
            value = json.loads(self.defaults_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, TypeError, json.JSONDecodeError):
            value = {}
        routes = value.get("routes", {}) if isinstance(value, dict) else {}
        if not isinstance(routes, dict):
            routes = {}
        return {
            purpose: str(routes.get(purpose) or "").strip()
            for purpose in DEFAULT_MODEL_PURPOSES
        }

    def put_default_models(
        self,
        routes: Mapping[str, Any],
        *,
        available_model_ids: set[str] | None = None,
    ) -> dict[str, str]:
        """Atomically replace system defaults after validating every model id."""

        unknown = set(routes) - set(DEFAULT_MODEL_PURPOSES)
        if unknown:
            raise ValueError(f"Unknown default model purpose: {sorted(unknown)[0]}")
        normalized: dict[str, str] = {}
        for purpose in DEFAULT_MODEL_PURPOSES:
            raw = routes.get(purpose)
            model_id = "" if raw is None else str(raw).strip()
            if len(model_id) > 512 or any(ord(char) < 32 for char in model_id):
                raise ValueError(f"Invalid model id for {purpose}")
            if (
                model_id
                and available_model_ids is not None
                and model_id not in available_model_ids
            ):
                raise ValueError(f"Model is not available: {model_id}")
            normalized[purpose] = model_id
        _atomic_json(
            self.defaults_path,
            {
                "schema": "ai2apps.model-defaults/v1",
                "routes": normalized,
            },
        )
        return normalized

    def resolve_default_model(self, purpose: str, fallback: str | None = None) -> str | None:
        """Resolve one purpose for runtime consumers, with an explicit fallback."""

        if purpose not in DEFAULT_MODEL_PURPOSES:
            raise ValueError(f"Unknown default model purpose: {purpose}")
        return self.default_models()[purpose] or fallback

    def list_fusion(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        if not self.fusion_dir.is_dir():
            return result
        for path in sorted(self.fusion_dir.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                profile = fusion_profile_from_mapping(value)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                result.append(
                    {"id": path.stem, "name": path.stem, "valid": False, "error": str(exc)}
                )
                continue
            mapping = profile_to_mapping(profile)["fusion"]
            raw_root = value.get("fusion", value) if isinstance(value, dict) else {}
            alias = str(raw_root.get("alias") or "").strip() if isinstance(raw_root, dict) else ""
            result.append(
                {
                    "id": profile.model_id,
                    "alias": alias,
                    "name": alias or profile.model_id,
                    "valid": True,
                    "generator": mapping["generator"],
                    "reviewer": mapping["reviewer"],
                    "resolver": mapping["resolver"],
                    "gate": mapping["gate"],
                    "cache_moe": mapping.get("cache_moe", {}),
                    "max_changed_ratio": mapping["max_changed_ratio"],
                    "ordinary_failure_policy": mapping["ordinary_failure_policy"],
                    "high_risk_failure_policy": mapping["high_risk_failure_policy"],
                }
            )
        return result

    def put_fusion(self, model_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
        model_id = _safe_id(model_id, "Fusion model id")
        root = dict(value.get("fusion", value))
        root["model_id"] = model_id
        alias = str(root.get("alias") or "").strip()
        if len(alias) > 128:
            raise ValueError("Fusion model alias must be 128 characters or fewer")
        profile = fusion_profile_from_mapping({"fusion": root})
        stored = profile_to_mapping(profile)
        if alias:
            stored["fusion"]["alias"] = alias
        _atomic_json(self.fusion_dir / f"{model_id}.json", stored)
        return next(item for item in self.list_fusion() if item["id"] == model_id)

    def delete_fusion(self, model_id: str) -> bool:
        path = self.fusion_dir / f"{_safe_id(model_id, 'Fusion model id')}.json"
        if not path.is_file():
            return False
        path.unlink()
        return True

    def resolve_fusion_profile(self, model_id: str) -> FusionProfile | None:
        """Return the validated private profile behind a Fusion API model id."""
        try:
            path = self.fusion_dir / f"{_safe_id(model_id, 'Fusion model id')}.json"
        except ValueError:
            return None
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            profile = fusion_profile_from_mapping(value)
        except (FileNotFoundError, OSError, ValueError, TypeError, json.JSONDecodeError):
            return None
        # Do not allow a renamed/corrupt file to impersonate another API id.
        return profile if profile.model_id == model_id else None

    def resolve_credential(self, credential_ref: str) -> str:
        """Resolve an internal credential reference without exposing it to APIs."""
        prefix = "ai2apps-cloud:"
        if not credential_ref.startswith(prefix):
            raise ValueError("Unsupported Fusion credential reference")
        provider_id = _safe_id(
            credential_ref[len(prefix) :], "Cloud provider id"
        )
        provider = self._cloud_data().get(provider_id)
        if (
            not provider
            or not provider.get("enabled", True)
            or not provider.get("api_key")
        ):
            raise ValueError("Fusion cloud provider is unavailable or not configured")
        return str(provider["api_key"])

    def _cloud_data(self) -> dict[str, dict[str, Any]]:
        try:
            value = json.loads(self.cloud_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, TypeError, json.JSONDecodeError):
            return {}
        providers = value.get("providers", {}) if isinstance(value, dict) else {}
        return providers if isinstance(providers, dict) else {}

    def list_cloud(self) -> list[dict[str, Any]]:
        saved = self._cloud_data()
        defaults = {item["id"]: dict(item) for item in BUILTIN_CLOUD_PROVIDERS}
        ids = list(defaults) + sorted(set(saved) - set(defaults))
        result = []
        for provider_id in ids:
            raw = saved.get(provider_id, {})
            default = defaults.get(provider_id, {})
            raw_models = raw.get("models", [])
            enabled_ids = {
                str(item) for item in raw.get("enabled_model_ids", []) if item
            }
            models = []
            for item in raw_models if isinstance(raw_models, list) else []:
                if isinstance(item, str):
                    models.append(
                        {"id": item, "name": item, "enabled": item in enabled_ids}
                    )
                elif isinstance(item, dict) and item.get("id"):
                    models.append(
                        {
                            "id": str(item["id"]),
                            "name": str(item.get("name") or item["id"]),
                            "owned_by": str(item.get("owned_by") or ""),
                            "created": item.get("created"),
                            "capabilities": item.get("capabilities") or {},
                            "enabled": str(item["id"]) in enabled_ids,
                        }
                    )
            # Provider APIs commonly return an arbitrary order.  Keep the
            # newest dated models first and place legacy/undated entries last.
            # Sorting here also upgrades already-cached provider inventories,
            # so users do not need to send their credential over the network
            # again merely to get the new ordering.
            models.sort(
                key=lambda model: (
                    -self._created_sort_value(model.get("created")),
                    str(model.get("name") or model["id"]).casefold(),
                    str(model["id"]).casefold(),
                )
            )
            result.append(
                {
                    "id": provider_id,
                    "name": raw.get("name") or default.get("name") or provider_id,
                    "base_url": raw.get("base_url") or default.get("base_url") or "",
                    "protocol": raw.get("protocol") or default.get("protocol") or "openai",
                    "models": models,
                    "model_count": len(models),
                    "enabled_model_count": sum(
                        1 for model in models if model.get("enabled")
                    ),
                    "models_synced_at": raw.get("models_synced_at"),
                    "models_error": raw.get("models_error") or "",
                    "enabled": bool(raw.get("enabled", True)),
                    "configured": bool(raw.get("api_key")),
                    "builtin": bool(default),
                }
            )
        return result

    @staticmethod
    def gateway_model_id(provider_id: str, model_id: str) -> str:
        return f"cloud/{provider_id}/{model_id}"

    def enabled_cloud_models(self) -> list[dict[str, Any]]:
        result = []
        for provider in self.list_cloud():
            if not provider["enabled"] or not provider["configured"]:
                continue
            for model in provider["models"]:
                if not model.get("enabled"):
                    continue
                result.append(
                    {
                        **model,
                        "gateway_id": self.gateway_model_id(provider["id"], model["id"]),
                        "provider_id": provider["id"],
                        "provider_name": provider["name"],
                        "protocol": provider["protocol"],
                    }
                )
        return result

    def resolve_cloud_model(self, gateway_id: str) -> dict[str, Any] | None:
        if not gateway_id.startswith("cloud/"):
            return None
        try:
            _, provider_id, model_id = gateway_id.split("/", 2)
        except ValueError:
            return None
        data = self._cloud_data()
        raw = data.get(provider_id)
        if not raw or not raw.get("enabled", True) or not raw.get("api_key"):
            return None
        if model_id not in {str(item) for item in raw.get("enabled_model_ids", [])}:
            return None
        return {
            "gateway_id": gateway_id,
            "provider_id": provider_id,
            "model_id": model_id,
            "base_url": str(raw.get("base_url") or "").rstrip("/"),
            "api_key": str(raw["api_key"]),
            "protocol": str(raw.get("protocol") or "openai"),
        }

    def set_cloud_model_enabled(
        self, provider_id: str, model_id: str, enabled: bool
    ) -> dict[str, Any]:
        provider_id = _safe_id(provider_id, "Provider id")
        data = self._cloud_data()
        raw = data.get(provider_id)
        if raw is None:
            raise ValueError("Cloud provider is not configured")
        available = {
            str(item.get("id") if isinstance(item, dict) else item)
            for item in raw.get("models", [])
        }
        if model_id not in available:
            raise ValueError("Cloud model is not available from this provider")
        selected = {
            str(item) for item in raw.get("enabled_model_ids", []) if item
        }
        if enabled:
            selected.add(model_id)
        else:
            selected.discard(model_id)
        raw["enabled_model_ids"] = sorted(selected)
        data[provider_id] = raw
        _atomic_json(self.cloud_path, {"version": 1, "providers": data})
        return next(item for item in self.list_cloud() if item["id"] == provider_id)

    @staticmethod
    def _created_sort_value(value: Any) -> float:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
            except ValueError:
                return 0.0
        return 0.0

    @staticmethod
    def _models_url(base_url: str, protocol: str) -> str:
        root = base_url.rstrip("/")
        if root.endswith("/v1"):
            return f"{root}/models"
        if protocol == "anthropic":
            return f"{root}/v1/models"
        return f"{root}/models"

    def sync_cloud(self, provider_id: str, *, timeout: float = 20.0) -> dict[str, Any]:
        """Fetch the models available to one configured provider credential."""

        provider_id = _safe_id(provider_id, "Provider id")
        data = self._cloud_data()
        raw = data.get(provider_id)
        if not raw or not raw.get("api_key"):
            raise ValueError("Configure the provider API key before refreshing models")
        protocol = str(raw.get("protocol") or "openai")
        headers = {"Accept": "application/json"}
        if protocol == "anthropic":
            headers.update(
                {
                    "x-api-key": str(raw["api_key"]),
                    "anthropic-version": "2023-06-01",
                }
            )
        else:
            headers["Authorization"] = f"Bearer {raw['api_key']}"
        url = self._models_url(str(raw["base_url"]), protocol)
        try:
            response = requests.get(
                url,
                headers=headers,
                params={"limit": 1000} if protocol == "anthropic" else None,
                timeout=timeout,
            )
            response.raise_for_status()
            payload = response.json()
            values = payload.get("data", []) if isinstance(payload, dict) else []
            if not isinstance(values, list):
                raise ValueError("Provider models response has no data list")
            models = []
            for item in values:
                if not isinstance(item, dict) or not item.get("id"):
                    continue
                model_id = str(item["id"])
                models.append(
                    {
                        "id": model_id,
                        "name": str(item.get("display_name") or item.get("name") or model_id),
                        "owned_by": str(item.get("owned_by") or ""),
                        "created": item.get("created_at", item.get("created")),
                        "capabilities": item.get("capabilities") or {},
                    }
                )
            models.sort(
                key=lambda item: (
                    -self._created_sort_value(item.get("created")),
                    item["name"].lower(),
                    item["id"].lower(),
                )
            )
            raw["models"] = models
            raw["models_synced_at"] = time.time()
            raw["models_error"] = ""
        except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError) as exc:
            raw["models_error"] = str(exc)
            data[provider_id] = raw
            _atomic_json(self.cloud_path, {"version": 1, "providers": data})
            raise ValueError(f"Could not list models from {provider_id}: {exc}") from exc
        data[provider_id] = raw
        _atomic_json(self.cloud_path, {"version": 1, "providers": data})
        return next(item for item in self.list_cloud() if item["id"] == provider_id)

    def put_cloud(self, provider_id: str, value: Mapping[str, Any]) -> dict[str, Any]:
        provider_id = _safe_id(provider_id, "Provider id")
        data = self._cloud_data()
        current = data.get(provider_id, {})
        default = next(
            (item for item in BUILTIN_CLOUD_PROVIDERS if item["id"] == provider_id), {}
        )
        protocol = str(value.get("protocol") or current.get("protocol") or default.get("protocol") or "openai")
        if protocol not in {"openai", "anthropic"}:
            raise ValueError("Cloud provider protocol must be openai or anthropic")
        base_url = str(value.get("base_url") or current.get("base_url") or default.get("base_url") or "").strip()
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("Cloud provider base_url must be an HTTP(S) URL")
        models = value.get("models", current.get("models", []))
        if isinstance(models, str):
            models = [item.strip() for item in models.split(",") if item.strip()]
        if not isinstance(models, list) or not all(isinstance(item, str) for item in models):
            raise ValueError("Cloud provider models must be a list of model ids")
        current_models = current.get("models", [])
        current_ids = [
            str(item.get("id") if isinstance(item, dict) else item)
            for item in current_models
        ]
        # The editor submits the visible IDs.  If they did not change, retain
        # the richer synchronized records (created date, owner, capabilities).
        if models == current_ids and any(isinstance(item, dict) for item in current_models):
            models = current_models
        api_key = value.get("api_key")
        record = {
            "name": str(value.get("name") or current.get("name") or default.get("name") or provider_id).strip(),
            "base_url": base_url.rstrip("/"),
            "protocol": protocol,
            "models": models,
            "enabled": bool(value.get("enabled", current.get("enabled", True))),
            "api_key": current.get("api_key", ""),
            "models_synced_at": current.get("models_synced_at"),
            "models_error": current.get("models_error", ""),
            "enabled_model_ids": current.get("enabled_model_ids", []),
        }
        if api_key is not None:
            record["api_key"] = str(api_key).strip()
        data[provider_id] = record
        _atomic_json(self.cloud_path, {"version": 1, "providers": data})
        return next(item for item in self.list_cloud() if item["id"] == provider_id)

    def delete_cloud(self, provider_id: str) -> bool:
        provider_id = _safe_id(provider_id, "Provider id")
        data = self._cloud_data()
        existed = provider_id in data
        data.pop(provider_id, None)
        _atomic_json(self.cloud_path, {"version": 1, "providers": data})
        return existed
