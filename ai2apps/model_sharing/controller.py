"""Opt-in Provider offer, matching, and Peer Session lifecycle."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from ai2apps.identity import RequestPrincipal
from ai2apps.peer.broker import PeerBrokerClient
from ai2apps.peer.identity import PeerProtocol

from .cloud import ComputeCloudClient, ComputeCloudError
from .provider import ModelShareProviderService

logger = logging.getLogger(__name__)


def _uuid(value: str, name: str) -> str:
    try:
        parsed = UUID(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a UUID") from error
    if str(parsed) != value:
        raise ValueError(f"{name} must be canonical")
    return value


@dataclass(frozen=True, slots=True)
class ModelShareProviderConfiguration:
    enabled: bool
    rate_card_id: str = ""
    rate_card_version: str = ""
    model_id: str = ""
    model_revision: str = ""
    runtime: str = "omlx"
    modality: str = "text"
    max_concurrency: int = 1
    estimated_tokens_per_second: int = 1

    @classmethod
    def from_environment(cls) -> "ModelShareProviderConfiguration":
        enabled = os.environ.get("AI2APPS_MODEL_SHARE_PROVIDER_ENABLED", "").strip() == "1"
        if not enabled:
            return cls(enabled=False)
        config = cls(
            enabled=True,
            rate_card_id=os.environ.get("AI2APPS_MODEL_SHARE_RATE_CARD_ID", "").strip(),
            rate_card_version=os.environ.get("AI2APPS_MODEL_SHARE_RATE_CARD_VERSION", "").strip(),
            model_id=os.environ.get("AI2APPS_MODEL_SHARE_MODEL_ID", "").strip(),
            model_revision=os.environ.get("AI2APPS_MODEL_SHARE_MODEL_REVISION", "").strip(),
            runtime=os.environ.get("AI2APPS_MODEL_SHARE_RUNTIME", "omlx").strip(),
            modality=os.environ.get("AI2APPS_MODEL_SHARE_MODALITY", "text").strip(),
            max_concurrency=int(os.environ.get("AI2APPS_MODEL_SHARE_MAX_CONCURRENCY", "1")),
            estimated_tokens_per_second=int(os.environ.get("AI2APPS_MODEL_SHARE_ESTIMATED_TPS", "1")),
        )
        _uuid(config.rate_card_id, "AI2APPS_MODEL_SHARE_RATE_CARD_ID")
        if not all((config.rate_card_version, config.model_id, config.model_revision, config.runtime)):
            raise ValueError("Enabled Model Share Provider configuration is incomplete")
        if config.modality not in {"text", "audio_tts"}:
            raise ValueError("AI2APPS_MODEL_SHARE_MODALITY is invalid")
        if not re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", config.model_id):
            raise ValueError("AI2APPS_MODEL_SHARE_MODEL_ID is invalid")
        if not 1 <= config.max_concurrency <= 32 or config.estimated_tokens_per_second < 1:
            raise ValueError("Model Share Provider capacity is invalid")
        return config


class ModelShareProviderController:
    """Runs only when explicitly enabled; failures never take Local down."""

    def __init__(
        self, *, config: ModelShareProviderConfiguration, principal: RequestPrincipal,
        broker: PeerBrokerClient, compute: ComputeCloudClient,
        provider: ModelShareProviderService, ready: Callable[[], bool],
    ) -> None:
        self.config = config
        self.principal = principal
        self.broker = broker
        self.compute = compute
        self.provider = provider
        self.ready = ready
        self.offer_id: str | None = None
        self.last_error: str | None = None
        self.accepted_contract_ids: set[str] = set()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def status(self) -> dict[str, object]:
        return {
            "enabled": self.config.enabled,
            "running": self._task is not None and not self._task.done(),
            "offerId": self.offer_id,
            "modelId": self.config.model_id or None,
            "modelRevision": self.config.model_revision or None,
            "runtime": self.config.runtime if self.config.enabled else None,
            "acceptedContracts": len(self.accepted_contract_ids),
            "lastError": self.last_error,
        }

    def bind_compute(self, compute: ComputeCloudClient) -> None:
        """Bind the explicitly activated browser-scoped Account session."""

        self.compute = compute
        self.provider.compute = compute
        self.last_error = None

    async def startup(self) -> None:
        if not self.config.enabled or self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="ai2apps-model-share-provider")

    async def shutdown(self) -> None:
        self._stop.set()
        if self._task is not None:
            await self._task
            self._task = None
        if self.offer_id is not None:
            try:
                await self.compute.drain_offer(self.offer_id)
                await self.compute.disable_offer(self.offer_id)
            except Exception:
                logger.exception("Failed to disable Model Share Provider offer")
            self.offer_id = None

    def _matches(self, value: dict) -> bool:
        return all((
            value.get("modelId") == self.config.model_id,
            value.get("modelRevision") == self.config.model_revision,
            value.get("runtime") == self.config.runtime,
            value.get("modality", "text") == self.config.modality,
            value.get("assetCode") == "PROMO_POINTS",
            value.get("rateCardVersion") == self.config.rate_card_version,
        ))

    async def _publish(self) -> None:
        if not self.ready():
            raise RuntimeError("Reviewed Local model is not ready")
        await self.broker.ensure_registered(self.principal, PeerProtocol.MODEL_SHARE_V1)
        offer = await self.compute.publish_offer(
            provider_installation_id=self.principal.installation_id,
            rate_card_id=self.config.rate_card_id,
            max_concurrency=self.config.max_concurrency,
            estimated_tokens_per_second=self.config.estimated_tokens_per_second,
        )
        offer_id = offer.get("id")
        self.offer_id = _uuid(offer_id, "Cloud Offer ID")

    async def _run(self) -> None:
        backoff = 1.0
        heartbeat_at = 0.0
        while not self._stop.is_set():
            try:
                if self.offer_id is None:
                    await self._publish()
                    heartbeat_at = time.monotonic() + 50
                if time.monotonic() >= heartbeat_at:
                    await self.compute.heartbeat_offer(self.offer_id)
                    heartbeat_at = time.monotonic() + 50
                if self.ready():
                    for soft_offer in await self.compute.list_soft_offers():
                        if not self._matches(soft_offer):
                            continue
                        result = await self.compute.accept_soft_offer(str(soft_offer["id"]))
                        contract = result.get("contract")
                        if isinstance(contract, dict) and isinstance(contract.get("id"), str):
                            self.accepted_contract_ids.add(contract["id"])
                await self.provider.accept_pending_sessions(self.principal)
                self.last_error = None
                backoff = 1.0
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=1.5)
                except TimeoutError:
                    pass
            except ComputeCloudError as error:
                self.last_error = error.code
                if not error.retryable:
                    logger.warning("Model Share Provider paused: %s", error.code)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)
            except Exception as error:
                self.last_error = type(error).__name__
                logger.exception("Model Share Provider loop failed")
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=backoff)
                except TimeoutError:
                    pass
                backoff = min(backoff * 2, 30.0)
