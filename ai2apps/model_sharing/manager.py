"""Reconciles durable Dashboard preferences with per-model Provider offers."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from ai2apps.identity import RequestPrincipal
from ai2apps.model_invocation import ModelInvocationService
from ai2apps.model_providers import list_package_models
from ai2apps.peer.broker import PeerBrokerClient
from ai2apps.peer.core import PeerTransportCore
from ai2apps.peer.repository import PeerSessionRepository
from ai2apps.peer.transports import PeerTransportStream
from ai2apps.remote import RemoteAccessManager

from .cloud import ComputeCloudClient, ComputeCloudError
from .controller import ModelShareProviderConfiguration, ModelShareProviderController
from .preferences import ModelShareModelPreference, ModelSharePreferencesRepository
from .protocol import InferenceRequest, ModelShareProtocolError
from .provider import ModelShareProviderError, ModelShareProviderService, SignerFactory
from .repository import ModelShareRepository
from .runtime_adapter import (
    OmlxAudioTtsInferenceHandler,
    OmlxTextInferenceHandler,
    supports_audio_tts,
    supports_text_conversation,
)


def _request_model_id(request: InferenceRequest) -> str:
    """Resolve the reviewed model from either legacy or multimodal manifests."""

    manifest = request.request_manifest.value
    model_id = manifest.get("modelId")
    if isinstance(model_id, str) and model_id:
        return model_id
    model = manifest.get("model")
    if isinstance(model, dict):
        model_id = model.get("id")
        if isinstance(model_id, str) and model_id:
            return model_id
    raise ModelShareProviderError(
        "MODEL_SHARE_REQUEST_INVALID",
        "Request manifest does not identify a model.",
        status_code=422,
    )


class ModelShareProviderManager:
    """Own one independently drainable Offer for every selected reviewed model."""

    def __init__(
        self,
        *,
        preferences: ModelSharePreferencesRepository,
        principal: RequestPrincipal,
        broker: PeerBrokerClient,
        compute: ComputeCloudClient,
        peer_sessions: PeerSessionRepository,
        jobs: ModelShareRepository,
        signer_factory: SignerFactory,
        invocations: ModelInvocationService,
        environment_config: ModelShareProviderConfiguration,
        peer_core: PeerTransportCore | None = None,
        remote: RemoteAccessManager | None = None,
        cloud_device_id: str | None = None,
    ) -> None:
        self.preferences = preferences
        self.principal = principal
        self.broker = broker
        self.compute = compute
        self.peer_sessions = peer_sessions
        self.jobs = jobs
        self.signer_factory = signer_factory
        self.invocations = invocations
        self.environment_config = environment_config
        self.peer_core = peer_core
        self.remote = remote
        self.cloud_device_id = cloud_device_id
        self.remote_cloud = None
        self.controllers: dict[str, ModelShareProviderController] = {}
        self.providers: dict[str, ModelShareProviderService] = {}
        self.approved_rate_cards: dict[str, tuple[str, str]] = {}
        self.approved_calculators: dict[str, str] = {}
        self.discovery_complete = False
        self.discovery_available = False
        self.last_error: str | None = None

    def _eligible_model(self, model_id: str):
        model = self.invocations.model(model_id)
        if model is None or not (
            supports_text_conversation(model) or supports_audio_tts(model)
        ):
            return None
        revision = str(dict(model.weights or {}).get("revision") or "")
        if not revision:
            return None
        return model

    @staticmethod
    def _modality(model: Any) -> str:
        return "audio_tts" if supports_audio_tts(model) else "text"

    def _config(self, preference: ModelShareModelPreference) -> ModelShareProviderConfiguration:
        model = self._eligible_model(preference.model_id)
        return ModelShareProviderConfiguration(
            enabled=True,
            rate_card_id=preference.rate_card_id,
            rate_card_version=preference.rate_card_version,
            model_id=preference.model_id,
            model_revision=preference.model_revision,
            runtime=preference.runtime,
            modality="text" if model is None else self._modality(model),
            max_concurrency=preference.max_concurrency,
            estimated_tokens_per_second=preference.estimated_tokens_per_second,
        )

    def _shareable_preference(
        self, preference: ModelShareModelPreference
    ) -> ModelShareModelPreference | None:
        model = self._eligible_model(preference.model_id)
        if model is None:
            return None
        revision = str(dict(model.weights or {}).get("revision") or "")
        if preference.model_revision != revision or preference.runtime != "omlx":
            return None
        if self.discovery_complete and self.approved_rate_cards.get(preference.model_id) != (
            preference.rate_card_id, preference.rate_card_version,
        ):
            return None
        return preference

    def _bootstrap_environment_preference(self) -> None:
        config = self.environment_config
        if not config.enabled or self.preferences.models():
            return
        model = self._eligible_model(config.model_id)
        if model is None:
            return
        self.preferences.save_model(
            model_id=config.model_id,
            service_key=model.service_key,
            model_revision=config.model_revision,
            runtime=config.runtime,
            rate_card_id=config.rate_card_id,
            rate_card_version=config.rate_card_version,
            max_concurrency=config.max_concurrency,
            estimated_tokens_per_second=config.estimated_tokens_per_second,
            enabled=True,
        )
        self.preferences.set_device_enabled(True)

    async def startup(self) -> None:
        self._bootstrap_environment_preference()
        await self.reconcile()

    def _remote_connector_status(self) -> dict[str, Any]:
        if self.remote is None or self.cloud_device_id is None:
            return {
                "required": False,
                "available": True,
                "running": True,
                "deviceId": None,
            }
        connector = self.remote.frpc.status()
        running = bool(
            connector.get("running")
            and connector.get("deviceId") == self.cloud_device_id
        )
        return {
            "required": True,
            "available": bool(self.remote.frpc.available),
            "running": running,
            "deviceId": self.cloud_device_id,
            "diagnostic": connector.get("diagnostic"),
        }

    async def ensure_transport_ready(self) -> None:
        """Start the reviewed Device connector before publishing any Offer."""

        status = self._remote_connector_status()
        if not status["required"] or status["running"]:
            return
        if not status["available"]:
            raise ValueError("Remote Connector is unavailable on this Device")
        if self.remote_cloud is None:
            raise ValueError(
                "Sign in to AI2Apps Cloud before starting Compute sharing"
            )
        assert self.remote is not None
        assert self.cloud_device_id is not None
        await self.remote.start(self.cloud_device_id, cloud=self.remote_cloud)
        if not self._remote_connector_status()["running"]:
            raise ValueError("Remote Connector did not start for this Device")

    async def shutdown(self) -> None:
        for model_id in tuple(self.controllers):
            await self._stop(model_id)

    async def _stop(self, model_id: str) -> None:
        controller = self.controllers.pop(model_id, None)
        self.providers.pop(model_id, None)
        if controller is not None:
            await controller.shutdown()

    def _make(self, preference: ModelShareModelPreference) -> None:
        model_id = preference.model_id
        config = self._config(preference)
        handler_type = (
            OmlxAudioTtsInferenceHandler
            if supports_audio_tts(self._eligible_model(model_id))
            else OmlxTextInferenceHandler
        )
        handler = handler_type(
            invocations=self.invocations,
            principal=self.principal,
            model_id=model_id,
            model_revision=preference.model_revision,
            runtime=preference.runtime,
        )

        def ready() -> bool:
            model = self._eligible_model(model_id)
            return bool(
                model is not None
                and dict(model.weights or {}).get("revision") == preference.model_revision
            )

        provider = ModelShareProviderService(
            broker=self.broker,
            peer_sessions=self.peer_sessions,
            jobs=self.jobs,
            compute=self.compute,
            signer_factory=self.signer_factory,
            inference_handler=handler,
            peer_core=self.peer_core,
        )
        controller = ModelShareProviderController(
            config=config,
            principal=self.principal,
            broker=self.broker,
            compute=self.compute,
            provider=provider,
            ready=ready,
        )
        self.providers[model_id] = provider
        self.controllers[model_id] = controller

    async def direct_inference(self, grant: str, payload: bytes) -> PeerTransportStream:
        try:
            value = json.loads(payload)
            request = InferenceRequest.parse(value)
        except (UnicodeDecodeError, ValueError, ModelShareProtocolError) as error:
            raise ModelShareProviderError("MODEL_SHARE_REQUEST_INVALID", str(error)) from error
        model_id = _request_model_id(request)
        provider = self.providers.get(model_id)
        if provider is None:
            raise ModelShareProviderError(
                "MODEL_SHARE_NOT_READY", "Requested model is not shared by this Device.",
                status_code=503, retryable=True,
            )
        body = await provider.inference(
            principal=self.principal, bearer_grant=grant, request=request,
        )
        return PeerTransportStream(
            200, {"content-type": "text/event-stream"}, body,
        )

    async def reconcile(self) -> None:
        desired: dict[str, ModelShareModelPreference] = {}
        if self.preferences.device_enabled():
            selected = {
                item.model_id: item
                for item in self.preferences.models()
                if item.enabled and self._shareable_preference(item) is not None
            }
            if not selected:
                self.preferences.set_device_enabled(False)
            elif self._remote_connector_status()["running"]:
                desired = selected
                if self.last_error == "REMOTE_CONNECTOR_NOT_RUNNING":
                    self.last_error = None
            else:
                self.last_error = "REMOTE_CONNECTOR_NOT_RUNNING"
        for model_id in tuple(self.controllers):
            current = self.controllers[model_id]
            preference = desired.get(model_id)
            if preference is None or current.config != self._config(preference):
                await self._stop(model_id)
        for model_id, preference in desired.items():
            if model_id not in self.controllers:
                self._make(preference)
                await self.controllers[model_id].startup()

    async def set_device_enabled(self, enabled: bool) -> dict[str, Any]:
        if enabled:
            if not any(
                item.enabled and self._shareable_preference(item) is not None
                for item in self.preferences.models()
            ):
                raise ValueError("Select at least one shareable model first")
            await self.ensure_transport_ready()
        self.preferences.set_device_enabled(enabled)
        await self.reconcile()
        return self.status()

    async def set_model_enabled(self, model_id: str, enabled: bool) -> dict[str, Any]:
        preference = self.preferences.model(model_id)
        if preference is None or self._shareable_preference(preference) is None:
            raise ValueError("This model does not have a matching Cloud Rate Card")
        self.preferences.set_model_enabled(model_id, enabled)
        await self.reconcile()
        return self.status()

    async def save_model_preferences(
        self,
        model_id: str,
        *,
        max_concurrency: int,
        estimated_tokens_per_second: int,
    ) -> dict[str, Any]:
        preference = self.preferences.model(model_id)
        if preference is None or self._shareable_preference(preference) is None:
            raise ValueError("This model does not have a matching Cloud Rate Card")
        self.preferences.save_model(
            model_id=model_id,
            service_key=preference.service_key,
            model_revision=preference.model_revision,
            runtime=preference.runtime,
            rate_card_id=preference.rate_card_id,
            rate_card_version=preference.rate_card_version,
            max_concurrency=max_concurrency,
            estimated_tokens_per_second=estimated_tokens_per_second,
        )
        await self.reconcile()
        return self.status()

    async def refresh_rate_cards(self) -> dict[str, Any]:
        """Synchronize Cloud-approved cards for exact installed model revisions."""

        discovered: dict[str, tuple[Any, dict[str, Any]]] = {}
        try:
            for model in list_package_models(self.invocations.runtime):
                eligible = self._eligible_model(model.id)
                if eligible is None:
                    continue
                revision = str(dict(eligible.weights or {}).get("revision") or "")
                cards = await self.compute.list_provider_rate_cards(
                    model_id=model.id, model_revision=revision, runtime="omlx",
                )
                modality = self._modality(eligible)
                expected_units = (
                    ("unicode_scalar", "audio_millisecond")
                    if modality == "audio_tts" else ("token", "token")
                )
                compatible = [item for item in cards if (
                    item.get("modality", "text") == modality
                    and item.get("inputUnit", "token") == expected_units[0]
                    and item.get("outputUnit", "token") == expected_units[1]
                )]
                preferred_calculator = "tts_v1" if modality == "audio_tts" else "legacy_units_v1"
                card = next((item for item in compatible
                             if item.get("calculatorType", "legacy_units_v1") == preferred_calculator),
                            compatible[0] if compatible else None)
                if card is not None:
                    discovered[model.id] = (eligible, card)
        except ComputeCloudError as error:
            if error.status_code == 404:
                self.discovery_available = False
                self.last_error = None
                return self.status()
            self.last_error = str(error)
            raise

        approved: dict[str, tuple[str, str]] = {}
        for model_id, (model, card) in discovered.items():
            rate_card_id = str(card["id"])
            rate_card_version = str(card["version"])
            approved[model_id] = (rate_card_id, rate_card_version)
            current = self.preferences.model(model_id)
            revision = str(dict(model.weights or {}).get("revision") or "")
            if (
                current is not None
                and current.model_revision == revision
                and current.runtime == "omlx"
                and current.rate_card_id == rate_card_id
                and current.rate_card_version == rate_card_version
            ):
                continue
            preserve_selection = bool(
                current is not None
                and current.model_revision == revision
                and current.runtime == "omlx"
                and current.enabled
            )
            self.preferences.save_model(
                model_id=model_id,
                service_key=model.service_key,
                model_revision=revision,
                runtime="omlx",
                rate_card_id=rate_card_id,
                rate_card_version=rate_card_version,
                max_concurrency=current.max_concurrency if current is not None else 1,
                estimated_tokens_per_second=(
                    current.estimated_tokens_per_second if current is not None else 1
                ),
                enabled=preserve_selection,
            )
        self.approved_rate_cards = approved
        self.approved_calculators = {
            model_id: str(card.get("calculatorType", "legacy_units_v1"))
            for model_id, (_model, card) in discovered.items()
        }
        self.discovery_complete = True
        self.discovery_available = True
        self.last_error = None
        await self.reconcile()
        return self.status()

    def bind_compute(self, compute: ComputeCloudClient) -> None:
        self.compute = compute
        for controller in self.controllers.values():
            controller.bind_compute(compute)

    def bind_remote_cloud(self, cloud: Any) -> None:
        """Bind the browser-scoped Cloud session used to start Remote safely."""

        self.remote_cloud = cloud

    def status(self) -> dict[str, Any]:
        configured = {item.model_id: item for item in self.preferences.models()}
        models: list[dict[str, Any]] = []
        catalog = {model.id: model for model in list_package_models(self.invocations.runtime)}
        for model_id in sorted(set(configured) | set(catalog)):
            item = configured.get(model_id)
            model = catalog.get(model_id)
            controller = self.controllers.get(model_id)
            runtime_status = controller.status() if controller is not None else {}
            shareable = item is not None and self._shareable_preference(item) is not None
            models.append(
                {
                    "modelId": model_id,
                    "displayName": getattr(model, "display_name", model_id),
                    "serviceKey": item.service_key if item is not None else getattr(model, "service_key", ""),
                    "modelRevision": item.model_revision if item is not None else str(dict(getattr(model, "weights", {}) or {}).get("revision") or ""),
                    "runtime": item.runtime if item is not None else "omlx",
                    "modality": None if model is None else self._modality(model),
                    "calculatorType": self.approved_calculators.get(model_id, "legacy_units_v1"),
                    "selected": bool(item.enabled) if item is not None else False,
                    "eligible": self._eligible_model(model_id) is not None,
                    "shareable": shareable,
                    "configured": item is not None,
                    "maxConcurrency": item.max_concurrency if item is not None else 1,
                    "estimatedTokensPerSecond": item.estimated_tokens_per_second if item is not None else 1,
                    "running": bool(runtime_status.get("running")),
                    "offerId": runtime_status.get("offerId"),
                    "lastError": runtime_status.get("lastError"),
                }
            )
        owner_user_id = getattr(self.principal, "actor_user_id", None)
        recent_jobs = []
        if isinstance(owner_user_id, str):
            recent_jobs = [
                {
                    "contractId": item.contract_id,
                    "role": item.role,
                    "status": item.status,
                    "calculatorType": item.calculator_type,
                    "maximumChargeMinor": item.maximum_charge_minor,
                    "actualUsage": item.actual_usage,
                    "chargedMinor": item.charged_minor,
                    "releasedMinor": item.released_minor,
                }
                for item in self.jobs.recent(owner_user_id)
            ]
        return {
            "enabled": self.preferences.device_enabled(),
            "canEnable": any(
                item.enabled and self._shareable_preference(item) is not None
                for item in configured.values()
            ),
            "selectedModelCount": sum(
                1
                for item in configured.values()
                if item.enabled and self._shareable_preference(item) is not None
            ),
            "runningModelCount": sum(1 for item in models if item["running"]),
            "rateCardDiscoveryAvailable": self.discovery_available,
            "transport": self._remote_connector_status(),
            "models": models,
            "recentJobs": recent_jobs,
            "lastError": self.last_error,
        }

    async def inference(
        self, *, principal: RequestPrincipal, bearer_grant: str, request: Any
    ) -> AsyncIterator[bytes]:
        model_id = _request_model_id(request)
        provider = self.providers.get(model_id)
        if provider is None:
            raise ModelShareProviderError(
                "MODEL_NOT_OFFERED",
                "This Device is not sharing the requested model.",
                status_code=403,
            )
        return await provider.inference(
            principal=principal, bearer_grant=bearer_grant, request=request
        )
