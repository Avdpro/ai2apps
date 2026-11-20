"""Owner-only settings UI and narrowly authenticated native callbacks."""
import asyncio
import logging
from dataclasses import replace
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ai2apps.api.client import _require_helper_authorization
from ai2apps.credential_import import CredentialImportError, service
from ai2apps.helper_control import HelperControlClient, HelperControlError


class ImportAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: str = Field(pattern="^(list|import)$")
    source: str | None = Field(default=None, max_length=100)
    offer_id: str | None = Field(default=None, max_length=100)
    selected: list[str] = Field(default_factory=list, max_length=16)
    replace_existing: bool = False
    language: Literal["zh", "zh-TW", "en", "es", "fr", "ja", "ko", "pt-BR", "ru"] = "en"


def create_credential_import_router(runtime_provider, principal_provider):
    logging.getLogger(__name__).info("Local API-Key import routes loaded from %s", __file__)
    router = APIRouter(prefix="/credential-import", tags=["model-settings"])

    @router.post("/action")
    async def action(body: ImportAction, request: Request, principal=Depends(principal_provider)):
        from ai2apps.http_security import enforce_same_origin_cookie_request
        enforce_same_origin_cookie_request(request)
        ticket = None
        current = None
        try:
            current = service(runtime_provider())
            ticket = current.begin(principal, body.model_dump())
            helper = HelperControlClient.from_environment()
            if helper is None:
                raise CredentialImportError("This feature requires the macOS desktop Helper")
            result = await asyncio.to_thread(replace(helper, timeout_seconds=180).import_credentials,
                                             actor_user_id=principal.actor_user_id, ticket=ticket)
            return result
        except (CredentialImportError, HelperControlError) as error:
            raise HTTPException(409, str(error)) from None
        finally:
            if ticket and current is not None:
                with current.lock:
                    current.tickets.pop(ticket, None)

    @router.post("/native/context")
    async def context(body: dict, request: Request, response: Response):
        _require_helper_authorization(request)
        response.headers["Cache-Control"] = "no-store"
        try:
            return await service(runtime_provider()).native_context(body.get("ticket"))
        except CredentialImportError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/native/export")
    async def export(body: dict, request: Request, response: Response):
        _require_helper_authorization(request)
        response.headers["Cache-Control"] = "no-store"
        try:
            return await service(runtime_provider()).native_export(body)
        except CredentialImportError as error:
            raise HTTPException(409, str(error)) from None

    @router.post("/native/install")
    async def install(body: dict, request: Request, response: Response):
        _require_helper_authorization(request)
        response.headers["Cache-Control"] = "no-store"
        try:
            return await service(runtime_provider()).native_install(body)
        except CredentialImportError as error:
            raise HTTPException(409, str(error)) from None

    return router
