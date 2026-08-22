"""Secret metadata API. No endpoint ever returns a secret value."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, SecretStr

from ai2apps.api.errors import platform_error_response, repository_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.apps.access import APP_SYSTEM_MANAGE
from ai2apps.core import RepositoryError
from ai2apps.secrets import SecretRecord


class SecretResponse(BaseModel):
    id: str
    uri: str
    name: str
    purpose: str
    allowed_tools: list[str]
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    last_used_at: datetime | None = None
    last_used_by_tool: str | None = None

    @classmethod
    def from_record(
        cls,
        record: SecretRecord,
        *,
        last_use: tuple[datetime | None, str | None] = (None, None),
    ):
        return cls(
            id=record.id, uri=record.uri, name=record.name,
            purpose=record.purpose, allowed_tools=list(record.allowed_tools),
            status=record.status, metadata=record.metadata,
            created_at=record.created_at, updated_at=record.updated_at,
            deleted_at=record.deleted_at,
            last_used_at=last_use[0], last_used_by_tool=last_use[1],
        )


class SecretListResponse(BaseModel):
    items: list[SecretResponse]


class SecretBackendResponse(BaseModel):
    provider: str
    portable: bool


class SecretCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    value: SecretStr
    purpose: str = Field(default="", max_length=500)
    allowed_tools: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SecretReplaceRequest(BaseModel):
    value: SecretStr


def create_secret_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(
        dependencies=[
            Depends(require_app_capability(principal_provider, APP_SYSTEM_MANAGE))
        ]
    )

    def repository_or_error():
        runtime = runtime_provider()
        if runtime is None or runtime.secrets is None:
            return platform_error_response(
                status_code=503, code="secret_runtime_not_ready",
                message="AI2Apps Secret Store is not ready.", retryable=True,
            )
        return runtime.secrets

    @router.get("/secrets/backend", response_model=SecretBackendResponse)
    def get_secret_backend():
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        provider = repository.backend.provider_name
        return SecretBackendResponse(
            provider=provider,
            portable=provider == "encrypted-file",
        )

    @router.get("/secrets", response_model=SecretListResponse)
    def list_secrets():
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        return SecretListResponse(
            items=[
                SecretResponse.from_record(
                    item, last_use=repository.last_use(item.id)
                )
                for item in repository.list()
            ]
        )

    @router.post("/secrets", response_model=SecretResponse, status_code=201)
    def create_secret(request: SecretCreateRequest):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            return SecretResponse.from_record(repository.create(
                name=request.name, value=request.value.get_secret_value(),
                purpose=request.purpose, allowed_tools=tuple(request.allowed_tools),
                metadata=request.metadata,
            ))
        except (ValueError, RuntimeError) as error:
            return platform_error_response(
                status_code=422, code="secret_create_failed", message=str(error)
            )

    @router.put("/secrets/{secret_id}/value", response_model=SecretResponse)
    def replace_secret(secret_id: str, request: SecretReplaceRequest):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            return SecretResponse.from_record(
                repository.replace(secret_id, request.value.get_secret_value())
            )
        except RepositoryError as error:
            return repository_error_response(error)

    @router.delete("/secrets/{secret_id}", response_model=SecretResponse)
    def delete_secret(secret_id: str):
        repository = repository_or_error()
        if isinstance(repository, JSONResponse):
            return repository
        try:
            return SecretResponse.from_record(repository.delete(secret_id))
        except RepositoryError as error:
            return repository_error_response(error)

    return router
