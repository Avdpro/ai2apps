"""Desktop-only backend for the built-in ComApps App."""

from __future__ import annotations

import logging
from ipaddress import ip_address
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai2apps.comapps import APP_ID
from ai2apps.comapps.proxy_workers import Entry, Key
from ai2apps.comapps.weixin import ConnectorError
from ai2apps.core import RepositoryError
from ai2apps.extensions import ExtensionError
from ai2apps.http_security import (
    enforce_same_origin_cookie_request,
    has_local_session_cookie,
)
from ai2apps.secrets.backends import SecretBackendError

Operation = Literal[
    "state",
    "ilink-start",
    "ilink-poll",
    "ilink-auto-enable",
    "ilink-auto-disable",
    "ilink-inbox",
    "ilink-reply",
    "ilink-disconnect",
    "ilink-logoff",
    "cli-configure",
    "cli-profiles",
    "cli-profile-create",
    "cli-profile-launch",
    "cli-bind",
    "cli-friends",
    "cli-groups",
    "cli-conversations",
    "cli-messages",
    "cli-search",
    "cli-disconnect",
    "cli-workers",
    "cli-worker-save",
    "cli-worker-delete",
    "cli-worker-image-test",
    "cli-image-monitor-start",
    "cli-image-monitor-stop",
    "cli-image-monitor-status",
    "cli-recall-status",
    "cli-draft-poll",
    "cli-draft-models",
    "cli-draft-model-save",
]


class Arguments(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: int | None = Field(default=None, ge=0)
    worker: Entry | None = None
    worker_id: Key | None = None
    work_id: Key | None = None
    database: str | None = Field(default=None, pattern=r"^message_[0-9]{1,6}\.db$")
    local_id: int | None = Field(default=None, ge=1, le=2**53 - 1)
    server_id: str | None = Field(default=None, pattern=r"^-?[1-9][0-9]{0,18}$")
    variant: Literal["thumbnail", "large"] | None = None
    classify: bool | None = None
    watch: bool | None = None
    model_id: str | None = Field(default=None, max_length=512, pattern=r"^[^\x00-\x1f\x7f]*$")
    workspace: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    path: str | None = Field(default=None, min_length=1, max_length=1024)
    profile: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9-]{0,31}$")
    login_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{24}$")
    verify_code: str | None = Field(default=None, pattern=r"^[0-9]{1,12}$")
    chat: str | None = Field(default=None, min_length=1, max_length=180)
    query: str | None = Field(default=None, max_length=180)
    directory: Literal["all", "conversations", "friends", "groups"] | None = None
    reply_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{24}$")
    text: str | None = Field(default=None, min_length=1, max_length=1800)


REQUIRED = {
    "ilink-poll": {"login_id"},
    "cli-configure": {"path"},
    "cli-bind": {"profile"},
    "cli-profile-create": {"profile"},
    "cli-profile-launch": {"profile"},
    "cli-messages": {"chat"},
    "cli-search": {"query", "directory", "workspace"},
    "cli-worker-save": {"workspace", "revision", "worker"},
    "cli-worker-delete": {"workspace", "revision", "worker_id"},
    "cli-image-monitor-start": {"workspace", "worker_id", "work_id", "revision"},
    "cli-image-monitor-stop": {"workspace", "worker_id", "work_id"},
    "cli-image-monitor-status": {"workspace", "worker_id", "work_id"},
    "cli-recall-status": {"workspace", "worker_id", "work_id"},
    "cli-draft-poll": {"workspace"},
    "cli-draft-models": {"workspace"},
    "cli-draft-model-save": {"workspace", "model_id"},
    "cli-worker-image-test": {
        "workspace",
        "worker_id",
        "work_id",
        "database",
        "local_id",
        "server_id",
    },
    "ilink-reply": {"reply_id", "text"},
}
OPTIONAL = {
    "ilink-poll": {"verify_code"},
    "cli-worker-image-test": {"variant", "classify", "watch"},
}


def create_comapps_router(runtime_provider, principal_provider):
    router = APIRouter(prefix="/comapps", tags=["comapps"])
    actor = Depends(principal_provider)
    logging.getLogger(__name__).info("ComApps Local API loaded; source=%s", __file__)

    @router.post("/instances/{instance_id}/{operation}")
    async def invoke(
        instance_id: str,
        operation: Operation,
        request: Request,
        response: Response,
        principal=actor,
    ):
        try:
            loopback = (
                ip_address(request.client.host).is_loopback
                and ip_address(request.url.hostname).is_loopback
            )
        except (AttributeError, TypeError, ValueError):
            loopback = False
        if (
            not loopback
            or not has_local_session_cookie(request)
            or principal.authentication_type != "cloud_session"
            or principal.client_scope != "desktop"
            or (operation.startswith("cli-") and not principal.is_core)
        ):
            raise HTTPException(403, "comapps_local_desktop_required")
        enforce_same_origin_cookie_request(request)
        if request.headers.get("sec-fetch-site") not in {
            "same-origin",
            None,
        } or not request.headers.get("origin"):
            raise HTTPException(403, "comapps_same_origin_required")
        runtime = runtime_provider()
        read_token = getattr(runtime, "local_session_token_from_cookies", None)
        authorize = getattr(runtime, "authorize_local_session", None)
        if (
            not read_token
            or not authorize
            or authorize(read_token(request.cookies)) != principal
        ):
            raise HTTPException(403, "comapps_local_session_required")
        service = getattr(runtime, "comapps", None)
        if service is None:
            raise HTTPException(503, "comapps_not_ready")
        try:
            entry = runtime.extension_manager.instance_entry(
                instance_id, principal=principal
            )
        except (RepositoryError, ExtensionError):
            raise HTTPException(404, "comapps_instance_unavailable") from None
        if entry["app_key"] != APP_ID or entry["renderer"] != "sandbox":
            raise HTTPException(404, "comapps_instance_unavailable")
        if entry["source"] != "builtin":
            raise HTTPException(403, "comapps_builtin_required")
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            raise HTTPException(415, "comapps_json_required")
        body = bytearray()
        limit = 100_000 if operation == "cli-worker-save" else 16_000
        async for chunk in request.stream():
            if len(body) + len(chunk) > limit:
                raise HTTPException(413, "comapps_request_too_large")
            body.extend(chunk)
        try:
            args = Arguments.model_validate_json(body).model_dump(exclude_unset=True)
        except ValidationError:
            raise HTTPException(422, "comapps_invalid_arguments") from None
        required = REQUIRED.get(operation, set())
        if (
            operation == "cli-worker-image-test"
            and args.get("watch")
            and not ({"local_id", "server_id"} & args.keys())
        ):
            required = required - {"local_id", "server_id"}
        if (
            not required <= args.keys()
            or args.keys() - required - OPTIONAL.get(operation, set())
            or any(value is None for value in args.values())
        ):
            raise HTTPException(422, "comapps_invalid_arguments")
        response.headers["Cache-Control"] = "no-store"
        from starlette.concurrency import run_in_threadpool

        try:
            if operation in {"cli-draft-models", "cli-draft-model-save"}:
                from ai2apps.comapps.reply_drafts import model_settings

                return await model_settings(runtime, service, principal, **args)
            if operation == "cli-draft-poll":
                from ai2apps.comapps.reply_drafts import poll

                return await poll(runtime, service, principal, instance_id, args["workspace"])
            if operation in {"ilink-auto-enable", "cli-worker-save", "cli-worker-delete",
                             "cli-recall-status"} or operation.startswith(
                "cli-image-monitor-"
            ):
                args["instance_id"] = instance_id
            if operation == "cli-worker-image-test" and args.pop("classify", False):
                import asyncio

                from anyio import from_thread

                from ai2apps.comapps.image_judgment import classify

                async def judge(content, mime, instruction):
                    async with asyncio.timeout(90):
                        return await classify(
                            runtime,
                            principal,
                            instance_id,
                            args["worker_id"],
                            content,
                            mime,
                            instruction,
                        )

                args["judge"] = lambda content, mime, instruction: from_thread.run(
                    judge, content, mime, instruction
                )
            return await run_in_threadpool(service.invoke, principal, operation, **args)
        except ConnectorError as error:
            raise HTTPException(409, str(error)) from None
        except SecretBackendError:
            raise HTTPException(503, "comapps_secret_unavailable") from None

    return router
