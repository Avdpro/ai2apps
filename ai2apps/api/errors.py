"""Stable error envelope for AI2Apps platform APIs."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ai2apps.core import (
    IdempotencyConflictError,
    RepositoryError,
    ResourceConflictError,
    ResourceNotFoundError,
    RevisionConflictError,
)


class PlatformError(BaseModel):
    """Machine-readable platform error detail."""

    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class PlatformErrorEnvelope(BaseModel):
    """Top-level error response shared by AI2Apps resource APIs."""

    error: PlatformError


def platform_error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    """Build a JSON response using the stable platform error envelope."""

    envelope = PlatformErrorEnvelope(
        error=PlatformError(
            code=code,
            message=message,
            retryable=retryable,
            details=details or {},
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=envelope.model_dump(mode="json"),
    )


def repository_error_response(error: RepositoryError) -> JSONResponse:
    """Map typed Repository failures to the stable platform API envelope."""

    if isinstance(error, ResourceNotFoundError):
        return platform_error_response(
            status_code=404,
            code="not_found",
            message=str(error),
            details={
                "resource_id": error.resource_id,
                "resource_type": error.resource_type,
            },
        )
    if isinstance(error, RevisionConflictError):
        return platform_error_response(
            status_code=409,
            code="revision_conflict",
            message=str(error),
            details={
                "actual_revision": error.actual,
                "expected_revision": error.expected,
                "resource_id": error.resource_id,
            },
        )
    if isinstance(error, IdempotencyConflictError):
        return platform_error_response(
            status_code=409,
            code="idempotency_conflict",
            message=str(error),
            details={
                "idempotency_key": error.idempotency_key,
                "session_id": error.session_id,
            },
        )
    if isinstance(error, ResourceConflictError):
        return platform_error_response(
            status_code=409,
            code="resource_conflict",
            message=str(error),
        )
    return platform_error_response(
        status_code=500,
        code="repository_error",
        message="Platform persistence operation failed.",
    )
