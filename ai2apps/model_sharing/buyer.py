"""Buyer control-plane orchestration for the text Model Share Pilot."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import UTC, datetime

from ai2apps.core import parse_utc
from ai2apps.identity import RequestPrincipal
from ai2apps.peer.broker import PeerBrokerError

from .cloud import ComputeCloudClient, ComputeCloudError
from .commitments import ComputeCommitmentSigner
from .manifests import AudioTTSRequestManifest, ComputeRequestManifest, MultimodalRequestManifest
from .protocol import ModelShareEvent
from .requester import (
    AudioTTSRequestConfiguration,
    ComputeRequestConfiguration,
    MultimodalRequestConfiguration,
    ModelShareRequesterService,
)

logger = logging.getLogger(__name__)


class ModelShareBuyerError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 409, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class ModelShareBuyerService:
    def __init__(self, *, requester: ModelShareRequesterService, compute: ComputeCloudClient) -> None:
        self.requester = requester
        self.compute = compute

    async def prepare(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        config: ComputeRequestConfiguration, prompt: str, system_prompt: str | None,
        temperature: int | float,
    ) -> tuple[ComputeRequestManifest, object]:
        try:
            manifest, created = await self.requester.create_request(
                principal=principal, signer=signer, config=config, prompt=prompt,
                system_prompt=system_prompt, temperature=temperature,
            )
        except ComputeCloudError as error:
            raise ModelShareBuyerError(error.code, str(error), status_code=error.status_code, retryable=error.retryable) from error
        if created.get("status") == "no_match":
            raise ModelShareBuyerError("COMPUTE_NO_MATCH", "No eligible Model Share Provider is available.", retryable=True)
        expires_at = parse_utc(created.get("expiresAt"))
        contract_id = str(created["contractId"])
        contract = await self._wait_contract(contract_id, expires_at)
        try:
            contract_expires_at = parse_utc(contract.get("expiresAt"))
        except (TypeError, ValueError) as error:
            raise ModelShareBuyerError(
                "COMPUTE_CLOUD_RESPONSE_INVALID",
                "Cloud Compute Contract omitted a valid expiry.",
                status_code=502,
            ) from error
        try:
            session = await self.requester.open_session(principal=principal, contract=contract)
        except PeerBrokerError as error:
            raise ModelShareBuyerError(error.code, str(error), status_code=error.status_code, retryable=error.retryable) from error
        return manifest, await self._wait_session(principal, session, contract_expires_at)

    async def prepare_audio_tts(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        config: AudioTTSRequestConfiguration, text: str, voice: str,
        language: str | None, instructions: str | None, speed: int | float,
    ) -> tuple[AudioTTSRequestManifest, object]:
        try:
            manifest, created = await self.requester.create_audio_tts_request(
                principal=principal, signer=signer, config=config, text=text,
                voice=voice, language=language, instructions=instructions,
                speed=speed,
            )
        except ComputeCloudError as error:
            raise ModelShareBuyerError(
                error.code, str(error), status_code=error.status_code,
                retryable=error.retryable,
            ) from error
        if created.get("status") == "no_match":
            raise ModelShareBuyerError(
                "COMPUTE_NO_MATCH",
                "No eligible TTS Provider is available.", retryable=True,
            )
        expires_at = parse_utc(created.get("expiresAt"))
        contract = await self._wait_contract(str(created["contractId"]), expires_at)
        contract_expires_at = parse_utc(contract.get("expiresAt"))
        try:
            session = await self.requester.open_session(
                principal=principal, contract=contract,
            )
        except PeerBrokerError as error:
            raise ModelShareBuyerError(
                error.code, str(error), status_code=error.status_code,
                retryable=error.retryable,
            ) from error
        return manifest, await self._wait_session(
            principal, session, contract_expires_at,
        )

    async def synthesize_audio_tts(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        manifest: AudioTTSRequestManifest, session,
    ) -> bytes:
        try:
            return await self.requester.fetch_audio(
                principal=principal, signer=signer,
                manifest=manifest, session=session,
            )
        finally:
            try:
                await self.requester.broker.close_session(
                    principal, session.session_id,
                )
            except PeerBrokerError:
                logger.warning(
                    "Could not close TTS Model Share Peer Session %s",
                    session.session_id, exc_info=True,
                )

    async def prepare_multimodal(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        config: MultimodalRequestConfiguration, request_payload: dict,
    ) -> tuple[MultimodalRequestManifest, dict, object]:
        try:
            manifest, quote, created = await self.requester.create_multimodal_request(
                principal=principal, signer=signer, config=config,
                request_payload=request_payload,
            )
        except ComputeCloudError as error:
            raise ModelShareBuyerError(
                error.code, str(error), status_code=error.status_code,
                retryable=error.retryable,
            ) from error
        if created.get("status") == "no_match":
            raise ModelShareBuyerError(
                "COMPUTE_NO_MATCH", "No eligible multimodal Provider is available.",
                retryable=True,
            )
        contract = await self._wait_contract(
            str(created["contractId"]), parse_utc(created.get("expiresAt")),
        )
        if (contract.get("calculatorType") != config.calculator_type
                or contract.get("pricingInput") != quote.pricing_input
                or contract.get("boundedUsage") != quote.bounded_usage
                or contract.get("maximumChargeMinor") != quote.maximum_charge_minor):
            raise ModelShareBuyerError(
                "COMPUTE_CONTRACT_MISMATCH",
                "Cloud Contract does not match the accepted quote.", status_code=502,
            )
        try:
            session = await self.requester.open_session(
                principal=principal, contract=contract,
            )
        except PeerBrokerError as error:
            raise ModelShareBuyerError(
                error.code, str(error), status_code=error.status_code,
                retryable=error.retryable,
            ) from error
        session = await self._wait_session(
            principal, session, parse_utc(contract.get("expiresAt")),
        )
        return manifest, {"id": quote.id, "calculatorType": quote.calculator_type,
                          "maximumChargeMinor": quote.maximum_charge_minor,
                          "boundedUsage": quote.bounded_usage}, session

    async def fetch_multimodal(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        manifest: MultimodalRequestManifest, request_payload: dict, session,
        maximum_charge_minor: str | None = None,
    ) -> tuple[bytes, dict]:
        try:
            return await self.requester.fetch_multimodal_artifact(
                principal=principal, signer=signer, manifest=manifest,
                request_payload=request_payload, session=session,
                maximum_charge_minor=maximum_charge_minor,
            )
        finally:
            try:
                await self.requester.broker.close_session(
                    principal, session.session_id,
                )
            except PeerBrokerError:
                logger.warning(
                    "Could not close multimodal Model Share Peer Session %s",
                    session.session_id, exc_info=True,
                )

    async def _wait_contract(self, contract_id: str, expires_at: datetime) -> dict:
        while datetime.now(UTC) < expires_at:
            try:
                contract = await self.compute.get_contract(contract_id)
            except ComputeCloudError as error:
                if error.status_code != 404:
                    raise ModelShareBuyerError(error.code, str(error), status_code=error.status_code, retryable=error.retryable) from error
            else:
                if contract.get("status") == "held":
                    return contract
                if contract.get("status") not in {"created", "held"}:
                    raise ModelShareBuyerError("COMPUTE_CONTRACT_UNAVAILABLE", "Compute Contract is no longer available.")
            await asyncio.sleep(0.5)
        raise ModelShareBuyerError("COMPUTE_MATCH_TIMEOUT", "Compute Provider matching timed out.", retryable=True)

    async def _wait_session(self, principal: RequestPrincipal, session, request_expires_at: datetime):
        deadline = min(session.expires_at, request_expires_at)
        while datetime.now(UTC) < deadline:
            try:
                current = await self.requester.broker.get_session(principal, session.session_id)
            except PeerBrokerError as error:
                raise ModelShareBuyerError(error.code, str(error), status_code=error.status_code, retryable=error.retryable) from error
            if current.status == "active":
                return current
            if current.status != "pending":
                raise ModelShareBuyerError("PEER_SESSION_UNAVAILABLE", "Peer Session is no longer available.")
            await asyncio.sleep(0.5)
        raise ModelShareBuyerError("PEER_SESSION_TIMEOUT", "Provider did not accept the Peer Session.", retryable=True)

    async def stream(
        self, *, principal: RequestPrincipal, signer: ComputeCommitmentSigner,
        manifest: ComputeRequestManifest, session,
    ) -> AsyncIterator[ModelShareEvent]:
        try:
            async for event in self.requester.stream(
                principal=principal, signer=signer, manifest=manifest, session=session,
            ):
                yield event
        finally:
            try:
                await self.requester.broker.close_session(principal, session.session_id)
            except PeerBrokerError:
                logger.warning(
                    "Could not close Model Share Peer Session %s",
                    session.session_id,
                    exc_info=True,
                )
