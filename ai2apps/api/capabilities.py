"""Capability policy and revocable GrantLease management APIs."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.capabilities import (
    CapabilityPolicyRecord,
    GrantLeaseRecord,
    PolicyEffect,
)
from ai2apps.core import RepositoryError


class PolicyResponse(BaseModel):
    id: str
    policy_key: str
    effect: str
    capability_pattern: str
    agent_pattern: str
    tool_pattern: str
    priority: int
    enabled: bool
    source: str
    conditions: dict[str, Any]
    revision: int

    @classmethod
    def from_record(cls, value: CapabilityPolicyRecord):
        return cls(**{key: getattr(value, key) for key in cls.model_fields})


class PolicyListResponse(BaseModel):
    items: list[PolicyResponse]


class PolicyPutRequest(BaseModel):
    effect: PolicyEffect
    capability_pattern: str = Field(min_length=1)
    agent_pattern: str = Field(default="*", min_length=1)
    tool_pattern: str = Field(default="*", min_length=1)
    priority: int = Field(default=0, ge=-10_000, le=10_000)
    conditions: dict[str, Any] = Field(default_factory=dict)


class GrantLeaseResponse(BaseModel):
    id: str
    scope: str
    scope_id: str
    agent_definition_id: str | None
    session_id: str
    app_instance_id: str
    capabilities: list[str]
    tool_pattern: str
    tool_service_digest: str | None
    resource_selector: dict[str, Any]
    issued_by: str
    evidence: dict[str, Any]
    expires_at: datetime | None
    revoked_at: datetime | None
    revoke_reason: str | None
    created_at: datetime

    @classmethod
    def from_record(cls, value: GrantLeaseRecord):
        data = {key: getattr(value, key) for key in cls.model_fields}
        data["capabilities"] = list(value.capabilities)
        return cls(**data)


class GrantLeaseListResponse(BaseModel):
    items: list[GrantLeaseResponse]


class RevokeRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


def create_capability_router(runtime_provider: PlatformRuntimeProvider) -> APIRouter:
    router = APIRouter()

    def repository_or_error():
        runtime = runtime_provider()
        if runtime is None or runtime.capabilities is None:
            return platform_error_response(
                status_code=503,
                code="capability_runtime_not_ready",
                message="AI2Apps Capability Runtime is not ready.",
                retryable=True,
            )
        return runtime.capabilities

    @router.get("/capability-policies", response_model=PolicyListResponse)
    def list_policies():
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        return PolicyListResponse(
            items=[PolicyResponse.from_record(x) for x in repository.list_policies()]
        )

    @router.put("/capability-policies/{policy_key}", response_model=PolicyResponse)
    def put_policy(policy_key: str, request: PolicyPutRequest):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            record = repository.upsert_policy(
                policy_key=policy_key,
                effect=request.effect,
                capability_pattern=request.capability_pattern,
                agent_pattern=request.agent_pattern,
                tool_pattern=request.tool_pattern,
                priority=request.priority,
                source="local",
                conditions=request.conditions,
            )
            return PolicyResponse.from_record(record)
        except ValueError as error:
            return platform_error_response(
                status_code=422, code="invalid_capability_policy", message=str(error)
            )

    @router.get("/grant-leases", response_model=GrantLeaseListResponse)
    def list_grants(include_inactive: bool = Query(default=False)):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        return GrantLeaseListResponse(
            items=[
                GrantLeaseResponse.from_record(x)
                for x in repository.list_leases(include_inactive=include_inactive)
            ]
        )

    @router.post("/grant-leases/{lease_id}/revoke", response_model=GrantLeaseResponse)
    def revoke_grant(lease_id: str, request: RevokeRequest):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            return GrantLeaseResponse.from_record(
                repository.revoke_lease(lease_id, reason=request.reason)
            )
        except RepositoryError as error:
            return repository_error_response(error)

    return router
