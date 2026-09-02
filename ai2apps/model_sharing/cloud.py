"""Narrow Account-authenticated Cloud client for Compute contracts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from uuid import UUID

import httpx

from ai2apps.cloud_client import AI2AppsCloudClient

from .pricing import MultimodalComputeQuote, validate_pricing_input


class ComputeCloudError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.retryable = retryable


class ComputeCloudClient:
    def __init__(self, cloud: AI2AppsCloudClient) -> None:
        self.cloud = cloud

    @staticmethod
    async def _payload(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json() if response.content else {}
        except ValueError:
            payload = None
        if response.status_code >= 400:
            detail = payload.get("error", {}) if isinstance(payload, dict) else {}
            raise ComputeCloudError(
                str(detail.get("code") or "COMPUTE_CLOUD_REQUEST_FAILED"),
                str(detail.get("message") or "Cloud rejected the Compute request."),
                status_code=response.status_code,
                retryable=response.status_code == 429 or response.status_code >= 500,
            )
        if not isinstance(payload, dict):
            raise ComputeCloudError("COMPUTE_CLOUD_RESPONSE_INVALID", "Cloud returned invalid JSON.", status_code=502)
        return payload

    async def request(self, method: str, path: str, *, json: Mapping[str, Any] | None = None,
                      params: Mapping[str, Any] | None = None,
                      headers: Mapping[str, str] | None = None) -> dict[str, Any]:
        response = await self.cloud.request(method, path, json=json, params=params, headers=headers)
        try:
            return await self._payload(response)
        finally:
            await response.aclose()

    async def get_contract(self, contract_id: str) -> dict[str, Any]:
        return await self.request("GET", f"/v1/compute/contracts/{contract_id}")

    async def create_quote(
        self, *, model_id: str, model_revision: str, runtime: str,
        calculator_type: str, pricing_input: Mapping[str, Any],
        buyer_maximum_minor: str, priority_tier: str = "standard",
        rate_card_id: str | None = None, idempotency_key: str,
    ) -> MultimodalComputeQuote:
        validated = validate_pricing_input(calculator_type, pricing_input)
        payload: dict[str, Any] = {
            "modelId": model_id, "modelRevision": model_revision,
            "runtime": runtime, "assetCode": "PROMO_POINTS",
            "priorityTier": priority_tier,
            "buyerMaximumMinor": buyer_maximum_minor,
            "pricingInput": validated,
        }
        if rate_card_id is not None:
            payload["rateCardId"] = rate_card_id
        response = await self.request(
            "POST", "/v1/compute/quotes", json=payload,
            headers={"Idempotency-Key": idempotency_key},
        )
        try:
            quote = MultimodalComputeQuote.parse(response)
        except ValueError as error:
            raise ComputeCloudError(
                "COMPUTE_CLOUD_RESPONSE_INVALID", str(error), status_code=502,
            ) from error
        if (quote.calculator_type != calculator_type
                or quote.pricing_input != validated
                or quote.buyer_maximum_minor != buyer_maximum_minor
                or rate_card_id is not None and quote.rate_card_id != rate_card_id):
            raise ComputeCloudError(
                "COMPUTE_CLOUD_RESPONSE_INVALID",
                "Cloud returned a quote that does not match the requested pricing terms.",
                status_code=502,
            )
        return quote

    async def list_provider_rate_cards(
        self, *, model_id: str, model_revision: str, runtime: str,
    ) -> list[dict[str, Any]]:
        payload = await self.request("GET", "/v1/compute/provider-rate-cards", params={
            "modelId": model_id, "modelRevision": model_revision, "runtime": runtime,
        })
        values = payload.get("data")
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ComputeCloudError(
                "COMPUTE_CLOUD_RESPONSE_INVALID",
                "Cloud returned an invalid Provider Rate Card list.",
                status_code=502,
            )
        result: list[dict[str, Any]] = []
        for item in values:
            try:
                rate_card_id = str(UUID(str(item.get("id") or "")))
            except ValueError as error:
                raise ComputeCloudError(
                    "COMPUTE_CLOUD_RESPONSE_INVALID",
                    "Cloud returned an invalid Provider Rate Card.",
                    status_code=502,
                ) from error
            if (
                rate_card_id != item.get("id")
                or item.get("modelId") != model_id
                or item.get("modelRevision") != model_revision
                or item.get("runtime") != runtime
                or item.get("status") != "active"
                or item.get("assetCode") != "PROMO_POINTS"
                or item.get("calculatorType", "legacy_units_v1") not in {
                    "legacy_units_v1", "tts_v1", "image_v1", "video_v1"
                }
                or not isinstance(item.get("version"), str)
                or not item["version"]
            ):
                raise ComputeCloudError(
                    "COMPUTE_CLOUD_RESPONSE_INVALID",
                    "Cloud returned a mismatched Provider Rate Card.",
                    status_code=502,
                )
            result.append(item)
        return result

    async def publish_offer(
        self, *, provider_installation_id: str, rate_card_id: str,
        max_concurrency: int, estimated_tokens_per_second: int,
    ) -> dict[str, Any]:
        return await self.request("POST", "/v1/compute/offers", json={
            "providerInstallationId": provider_installation_id,
            "rateCardId": rate_card_id,
            "maxConcurrency": max_concurrency,
            "estimatedTokensPerSecond": estimated_tokens_per_second,
        })

    async def heartbeat_offer(self, offer_id: str) -> dict[str, Any]:
        return await self.request("POST", f"/v1/compute/offers/{offer_id}/heartbeat")

    async def drain_offer(self, offer_id: str) -> dict[str, Any]:
        return await self.request("POST", f"/v1/compute/offers/{offer_id}/drain")

    async def disable_offer(self, offer_id: str) -> dict[str, Any]:
        return await self.request("POST", f"/v1/compute/offers/{offer_id}/disable")

    async def list_soft_offers(self) -> list[dict[str, Any]]:
        payload = await self.request("GET", "/v1/compute/soft-offers")
        values = payload.get("data")
        if not isinstance(values, list) or any(not isinstance(item, dict) for item in values):
            raise ComputeCloudError("COMPUTE_CLOUD_RESPONSE_INVALID", "Cloud returned an invalid SoftOffer list.", status_code=502)
        return values

    async def accept_soft_offer(self, soft_offer_id: str) -> dict[str, Any]:
        return await self.request("POST", f"/v1/compute/soft-offers/{soft_offer_id}/accept")

    async def input_acceptance(self, contract_id: str, commitment: Mapping[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/v1/compute/contracts/{contract_id}/input-acceptance", json=commitment)

    async def result_commitment(self, contract_id: str, commitment: Mapping[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/v1/compute/contracts/{contract_id}/result-commitment", json=commitment)

    async def delivery_receipt(self, contract_id: str, commitment: Mapping[str, Any]) -> dict[str, Any]:
        return await self.request("POST", f"/v1/compute/contracts/{contract_id}/delivery-receipt", json=commitment)
