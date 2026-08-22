"""Core-only management API for downstream connections to upstream Locals."""

from __future__ import annotations

from datetime import datetime
import json
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr

from ai2apps.identity import RequestPrincipal
from ai2apps.qr import svg_qr_data_url
from ai2apps.sharing import CapabilityKind
from ai2apps.sharing.agent_connector import agent_connector_tools
from ai2apps.upstream import UpstreamGateway, UpstreamGatewayError, UpstreamRouting

from .health import PlatformRuntimeProvider
from .identity import PrincipalProvider, resolve_request_principal


def _manager(runtime_provider):
    runtime = runtime_provider()
    manager = None if runtime is None else getattr(runtime, "upstreams", None)
    if manager is None:
        raise HTTPException(status_code=503, detail={"code": "upstreams_not_ready"})
    return manager


def _require_core(principal_provider: PrincipalProvider):
    dependency = Depends(principal_provider)

    def authorize(principal: RequestPrincipal = dependency) -> RequestPrincipal:
        if not principal.is_core:
            raise HTTPException(
                status_code=403,
                detail={"code": "core_account_required", "message": "Only the device Core account can manage upstream gateways."},
            )
        return principal

    return authorize


def _error(error: UpstreamGatewayError) -> HTTPException:
    return HTTPException(status_code=error.status_code, detail={"code": error.code, "message": str(error)})


class UpstreamCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=200)
    openai_base_url: str = Field(min_length=1, max_length=2000)
    mcp_url: str = Field(min_length=1, max_length=2000)
    token: SecretStr
    remote_node_id: str | None = Field(default=None, min_length=8, max_length=128)
    ancestor_node_ids: list[str] = Field(default_factory=list, max_length=64)
    is_parent: bool = True
    priority: int = Field(default=100, ge=1, le=1000)
    route_models: bool = True
    route_mcp: bool = True


class UpstreamStatusRequest(BaseModel):
    expected_revision: int = Field(ge=1)
    status: str | None = None
    is_default: bool | None = None
    priority: int | None = Field(default=None, ge=1, le=1000)
    route_models: bool | None = None
    route_mcp: bool | None = None


class UpstreamRoutingRequest(BaseModel):
    model_policy: str
    expected_revision: int = Field(ge=1)


class CloudPairingAcceptRequest(BaseModel):
    pairing_code: SecretStr
    owner_password: SecretStr = Field(min_length=12, max_length=128)


class CloudPairingExchangeRequest(BaseModel):
    label: str = Field(default="Cloud parent", min_length=1, max_length=200)
    priority: int = Field(default=100, ge=1, le=1000)
    route_models: bool = True
    route_mcp: bool = True


class CloudNodeGrantRequest(BaseModel):
    export_ids: list[str] = Field(default_factory=list, max_length=200)
    concurrency_limit: int = Field(default=3, ge=1, le=100)
    monthly_point_limit: str | None = Field(default=None, max_length=100)
    expires_at: datetime | None = None
    owner_password: SecretStr = Field(min_length=12, max_length=128)


class CloudLinkOwnerRequest(BaseModel):
    owner_password: SecretStr = Field(min_length=12, max_length=128)


class CloudCredentialImportRequest(BaseModel):
    credential: SecretStr = Field(min_length=16, max_length=1000)


class UpstreamRoutingResponse(BaseModel):
    model_policy: str
    revision: int
    updated_by_user_id: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, item: UpstreamRouting):
        return cls(**{name: getattr(item, name) for name in cls.model_fields})


class UpstreamResponse(BaseModel):
    id: str
    label: str
    openai_base_url: str
    mcp_url: str
    transport_kind: str
    downstream_installation_id: str | None
    node_link_id: str | None
    remote_node_id: str | None
    ancestor_node_ids: list[str]
    is_parent: bool
    is_default: bool
    priority: int
    route_models: bool
    route_mcp: bool
    status: str
    health_status: str
    capabilities: dict[str, Any]
    last_error: str | None
    last_checked_at: datetime | None
    revision: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_record(cls, item: UpstreamGateway):
        return cls(
            id=item.id, label=item.label, openai_base_url=item.openai_base_url,
            mcp_url=item.mcp_url, status=item.status,
            transport_kind=item.transport_kind,
            downstream_installation_id=item.downstream_installation_id,
            node_link_id=item.node_link_id,
            remote_node_id=item.remote_node_id,
            ancestor_node_ids=list(item.ancestor_node_ids),
            is_parent=item.is_parent, is_default=item.is_default,
            priority=item.priority, route_models=item.route_models,
            route_mcp=item.route_mcp,
            health_status=item.health_status, capabilities=item.capabilities,
            last_error=item.last_error, last_checked_at=item.last_checked_at,
            revision=item.revision, created_at=item.created_at, updated_at=item.updated_at,
        )


def create_upstream_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/upstreams", tags=["upstreams"])
    core_dependency = Depends(_require_core(principal_provider))

    def runtime_or_error():
        runtime = runtime_provider()
        if runtime is None or runtime.cloud is None:
            raise HTTPException(status_code=503, detail={"code": "cloud_client_not_ready"})
        return runtime

    async def cloud_json(method: str, path: str, *, headers=None, payload=None):
        runtime = runtime_or_error()
        try:
            response = await runtime.cloud.request(method, path, headers=headers, json=payload)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise HTTPException(status_code=503, detail={"code": "cloud_unavailable", "message": str(exc)}) from exc
        try:
            try:
                value = response.json()
            except Exception:
                value = {"message": response.text[:500]}
            if response.status_code >= 400:
                detail = value if isinstance(value, dict) else {"message": "Cloud request failed"}
                raise HTTPException(status_code=response.status_code, detail=detail)
            if not isinstance(value, dict):
                raise HTTPException(status_code=502, detail={"code": "cloud_invalid_response"})
            return value
        finally:
            await response.aclose()

    async def owner_grant(installation_id: str, purpose: str, password: str) -> str:
        value = await cloud_json("POST", "/v1/owner-reauth/grants", payload={
            "purpose": purpose, "resourceType": "installation",
            "resourceId": installation_id, "password": password,
        })
        grant = value.get("grant")
        if not isinstance(grant, str) or not grant:
            raise HTTPException(status_code=502, detail={"code": "owner_reauth_invalid_response"})
        return grant

    @router.get("")
    def list_upstreams(_: RequestPrincipal = core_dependency):
        return {"items": [UpstreamResponse.from_record(item) for item in _manager(runtime_provider).list()]}

    @router.get("/activity")
    def list_upstream_activity(gateway_id: str | None = None, limit: int = 50, _: RequestPrincipal = core_dependency):
        try:
            return {"items": list(_manager(runtime_provider).list_activity(gateway_id=gateway_id, limit=limit))}
        except UpstreamGatewayError as error:
            raise _error(error) from error

    @router.get("/routing", response_model=UpstreamRoutingResponse)
    def get_routing(_: RequestPrincipal = core_dependency):
        return UpstreamRoutingResponse.from_record(_manager(runtime_provider).routing())

    @router.patch("/routing", response_model=UpstreamRoutingResponse)
    def update_routing(payload: UpstreamRoutingRequest, principal: RequestPrincipal = core_dependency):
        try:
            return UpstreamRoutingResponse.from_record(_manager(runtime_provider).update_routing(
                model_policy=payload.model_policy,
                expected_revision=payload.expected_revision,
                updated_by_user_id=principal.actor_user_id,
            ))
        except UpstreamGatewayError as error:
            raise _error(error) from error

    @router.post("", response_model=UpstreamResponse, status_code=201)
    def create_upstream(payload: UpstreamCreateRequest, principal: RequestPrincipal = core_dependency):
        try:
            return UpstreamResponse.from_record(_manager(runtime_provider).create(
                label=payload.label,
                openai_base_url=payload.openai_base_url,
                mcp_url=payload.mcp_url,
                token=payload.token.get_secret_value(),
                created_by_user_id=principal.actor_user_id,
                remote_node_id=payload.remote_node_id,
                ancestor_node_ids=tuple(payload.ancestor_node_ids),
                is_parent=payload.is_parent,
                priority=payload.priority,
                route_models=payload.route_models,
                route_mcp=payload.route_mcp,
            ))
        except UpstreamGatewayError as error:
            raise _error(error) from error

    @router.post("/cloud/pairings", status_code=201)
    async def create_cloud_pairing(principal: RequestPrincipal = core_dependency):
        runtime = runtime_or_error()
        try:
            headers = runtime.cloud_ai_authorization_headers(principal)
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "installation_device_not_ready", "message": str(exc)}) from exc
        value = await cloud_json("POST", "/v1/federation/pairings", headers=headers)
        try:
            pairing_id = str(value["pairingId"])
            pairing_code = str(value["pairingCode"])
            expires_at = str(value["expiresAt"])
        except (KeyError, TypeError) as exc:
            raise HTTPException(status_code=502, detail={"code": "federation_pairing_invalid_response"}) from exc
        _manager(runtime_provider).save_cloud_pairing(
            pairing_id=pairing_id, pairing_code=pairing_code,
            expires_at=expires_at, created_by_user_id=principal.actor_user_id,
        )
        connection = {"schema": "ai2apps.federation-pairing/v1", "pairingCode": pairing_code}
        return {
            "pairingId": pairing_id, "pairingCode": pairing_code,
            "expiresAt": expires_at,
            "pairingQr": svg_qr_data_url(json.dumps(connection, separators=(",", ":"))),
        }

    @router.get("/cloud/pairings")
    def list_cloud_pairings(_: RequestPrincipal = core_dependency):
        items = []
        for item in _manager(runtime_provider).list_cloud_pairings():
            connection = {"schema": "ai2apps.federation-pairing/v1", "pairingCode": item["pairingCode"]}
            items.append({**item, "pairingQr": svg_qr_data_url(json.dumps(connection, separators=(",", ":")))})
        return {"items": items}

    @router.post("/cloud/pairings/accept")
    async def accept_cloud_pairing(payload: CloudPairingAcceptRequest, principal: RequestPrincipal = core_dependency):
        pairing_code = payload.pairing_code.get_secret_value()
        pairing_id = pairing_code.split(".", 1)[0]
        grant = await owner_grant(
            principal.installation_id, "federation.link.accept",
            payload.owner_password.get_secret_value(),
        )
        return await cloud_json(
            "POST", f"/v1/federation/pairings/{pairing_id}/accept",
            headers={"X-Owner-Reauth-Grant": grant},
            payload={"upstreamInstallationId": principal.installation_id, "pairingCode": pairing_code},
        )

    @router.post("/cloud/pairings/{pairing_id}/exchange", response_model=UpstreamResponse)
    async def exchange_cloud_pairing(
        pairing_id: str, payload: CloudPairingExchangeRequest,
        principal: RequestPrincipal = core_dependency,
    ):
        runtime = runtime_or_error()
        manager = _manager(runtime_provider)
        try:
            code = manager.load_cloud_pairing(pairing_id)
            headers = runtime.cloud_ai_authorization_headers(principal)
        except UpstreamGatewayError as error:
            raise _error(error) from error
        except Exception as exc:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "installation_device_not_ready",
                    "message": str(exc),
                },
            ) from exc
        value = await cloud_json(
            "POST",
            f"/v1/internal/federation/pairings/{pairing_id}/exchange",
            headers=headers,
            payload={"pairingCode": code},
        )
        try:
            gateway = manager.create_cloud_relay(
                label=payload.label,
                cloud_base_url=runtime.cloud.base_url,
                credential=str(value["credential"]),
                node_link_id=str(value["nodeLinkId"]),
                upstream_installation_id=str(value["upstreamInstallationId"]),
                downstream_installation_id=str(value["downstreamInstallationId"]),
                created_by_user_id=principal.actor_user_id,
                priority=payload.priority,
                route_models=payload.route_models,
                route_mcp=payload.route_mcp,
            )
            manager.complete_cloud_pairing(pairing_id)
            gateway = await manager.probe(gateway.id)
            return UpstreamResponse.from_record(gateway)
        except (KeyError, TypeError) as error:
            raise HTTPException(
                status_code=502,
                detail={"code": "federation_pairing_invalid_response"},
            ) from error
        except UpstreamGatewayError as error:
            raise _error(error) from error

    @router.get("/cloud/links")
    async def list_cloud_links(principal: RequestPrincipal = core_dependency):
        value = await cloud_json(
            "GET", f"/v1/installations/{principal.installation_id}/federation/links"
        )
        items = value.get("items", [])
        if not isinstance(items, list):
            raise HTTPException(status_code=502, detail={"code": "federation_links_invalid_response"})
        _manager(runtime_provider).apply_cloud_link_states(items)
        enriched = []
        for item in items:
            if not isinstance(item, dict):
                continue
            direction = "upstream" if item.get("upstreamInstallationId") == principal.installation_id else "downstream"
            enriched.append({**item, "direction": direction})
        return {"items": enriched}

    @router.put("/cloud/links/{node_link_id}/grant")
    async def update_cloud_node_grant(
        node_link_id: str, payload: CloudNodeGrantRequest,
        principal: RequestPrincipal = core_dependency,
    ):
        runtime = runtime_or_error()
        sharing = runtime.sharing
        if sharing is None:
            raise HTTPException(status_code=503, detail={"code": "sharing_not_ready"})
        selected_ids = set(payload.export_ids)
        models: list[str] = []
        connector_ids: list[str] = []
        capabilities: set[str] = set()
        found: set[str] = set()
        for export in sharing.list_exports():
            if export.id not in selected_ids or export.status != "active":
                continue
            found.add(export.id)
            if export.kind is CapabilityKind.MODEL:
                capabilities.add("model.chat@1")
                models.append(export.target_id)
            elif export.kind in {CapabilityKind.TOOL, CapabilityKind.SERVICE}:
                capabilities.add("mcp@1")
                connector_ids.extend(tool.qualified_name for tool in sharing.tools_for_export(export))
            elif export.kind is CapabilityKind.AGENT:
                capabilities.add("mcp@1")
                connector_ids.extend(tool["name"] for tool in agent_connector_tools(export))
        if found != selected_ids:
            raise HTTPException(status_code=409, detail={"code": "federation_export_not_active"})
        grant = await owner_grant(
            principal.installation_id, "federation.grant.change",
            payload.owner_password.get_secret_value(),
        )
        return await cloud_json(
            "PUT", f"/v1/installations/{principal.installation_id}/federation/links/{node_link_id}/grant",
            headers={"X-Owner-Reauth-Grant": grant},
            payload={
                "allowedCapabilities": sorted(capabilities),
                "allowedModelIds": sorted(set(models)),
                "allowedExportIds": sorted(set(connector_ids)),
                "concurrencyLimit": payload.concurrency_limit,
                "monthlyPointLimit": payload.monthly_point_limit or None,
                "expiresAt": None if payload.expires_at is None else payload.expires_at.isoformat(),
            },
        )

    @router.post("/cloud/links/{node_link_id}/rotate")
    async def rotate_cloud_link(
        node_link_id: str, payload: CloudLinkOwnerRequest,
        principal: RequestPrincipal = core_dependency,
    ):
        grant = await owner_grant(
            principal.installation_id, "federation.link.rotate",
            payload.owner_password.get_secret_value(),
        )
        value = await cloud_json(
            "POST", f"/v1/installations/{principal.installation_id}/federation/links/{node_link_id}/credentials/rotate",
            headers={"X-Owner-Reauth-Grant": grant},
        )
        credential = value.get("credential")
        if not isinstance(credential, str) or not credential.startswith(node_link_id + "."):
            raise HTTPException(status_code=502, detail={"code": "federation_credential_invalid_response"})
        connection = {"schema": "ai2apps.federation-credential/v1", "nodeLinkId": node_link_id, "credential": credential}
        return {**value, "credentialQr": svg_qr_data_url(json.dumps(connection, separators=(",", ":")))}

    @router.post("/cloud/links/{node_link_id}/revoke")
    async def revoke_cloud_link(
        node_link_id: str, payload: CloudLinkOwnerRequest,
        principal: RequestPrincipal = core_dependency,
    ):
        grant = await owner_grant(
            principal.installation_id, "federation.link.revoke",
            payload.owner_password.get_secret_value(),
        )
        return await cloud_json(
            "POST", f"/v1/installations/{principal.installation_id}/federation/links/{node_link_id}/revoke",
            headers={"X-Owner-Reauth-Grant": grant},
        )

    @router.post("/cloud/links/{node_link_id}/credential", response_model=UpstreamResponse)
    async def import_cloud_link_credential(
        node_link_id: str, payload: CloudCredentialImportRequest,
        _: RequestPrincipal = core_dependency,
    ):
        manager = _manager(runtime_provider)
        try:
            gateway = manager.replace_cloud_credential(node_link_id, payload.credential.get_secret_value())
            return UpstreamResponse.from_record(await manager.probe(gateway.id))
        except UpstreamGatewayError as error:
            raise _error(error) from error
        except Exception as exc:
            raise HTTPException(status_code=409, detail={"code": "installation_device_not_ready", "message": str(exc)}) from exc

    @router.post("/{gateway_id}/probe", response_model=UpstreamResponse)
    async def probe_upstream(gateway_id: str, _: RequestPrincipal = core_dependency):
        try:
            return UpstreamResponse.from_record(await _manager(runtime_provider).probe(gateway_id))
        except UpstreamGatewayError as error:
            raise _error(error) from error

    @router.patch("/{gateway_id}", response_model=UpstreamResponse)
    def set_upstream_status(gateway_id: str, payload: UpstreamStatusRequest, _: RequestPrincipal = core_dependency):
        try:
            return UpstreamResponse.from_record(_manager(runtime_provider).update(
                gateway_id,
                expected_revision=payload.expected_revision,
                status=payload.status,
                is_default=payload.is_default,
                priority=payload.priority,
                route_models=payload.route_models,
                route_mcp=payload.route_mcp,
            ))
        except UpstreamGatewayError as error:
            raise _error(error) from error

    @router.delete("/{gateway_id}", status_code=204)
    def delete_upstream(gateway_id: str, _: RequestPrincipal = core_dependency):
        try:
            _manager(runtime_provider).delete(gateway_id)
        except UpstreamGatewayError as error:
            raise _error(error) from error

    return router
