"""Platform-owned model invocation boundary shared by every business feature."""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import json
import os
from collections.abc import Callable, Mapping
from contextlib import ExitStack, suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi.responses import Response

from ai2apps.identity import (
    IdentityBindingError,
    IdentityRepository,
    RequestPrincipal,
)
from ai2apps.model_providers import (
    PackageModel,
    ensure_package_model_ready,
    estimate_model_resident_bytes,
    proxy_package_json,
    proxy_package_multipart,
    resolve_package_model,
)
from ai2apps.storage.database import PlatformDatabase
from ai2apps.worker_resources import MIB, estimate_request_transient_bytes
from ai2apps.worker_scheduler import WorkloadClass


@dataclass(frozen=True, slots=True)
class ModelInvocationContext:
    """Server-derived actor, payer, and device-local model cache boundary."""

    actor_user_id: str
    installation_id: str
    organization_id: str
    billing_account_id: str
    membership_epoch: int
    session_id: str
    authentication_type: str
    app_instance_id: str | None = None
    consumer_app_id: str | None = None

    @classmethod
    def from_principal(
        cls,
        principal: RequestPrincipal,
        *,
        session_id: str,
        app_instance_id: str | None = None,
        consumer_app_id: str | None = None,
    ) -> ModelInvocationContext:
        return cls(
            actor_user_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            organization_id=principal.organization_id,
            billing_account_id=principal.billing_account_id,
            membership_epoch=principal.membership_epoch,
            session_id=session_id,
            authentication_type=principal.authentication_type,
            app_instance_id=app_instance_id,
            consumer_app_id=consumer_app_id,
        )

    @classmethod
    def for_session(
        cls,
        database: PlatformDatabase,
        session_id: str,
    ) -> ModelInvocationContext:
        """Resolve identity from Session ownership, never from model payload."""

        with database.transaction() as connection:
            row = connection.execute(
                """
                SELECT i.owner_user_id, i.id AS app_instance_id
                FROM sessions s
                JOIN app_instances i ON i.id=s.app_instance_id
                WHERE s.id=? AND s.status='active'
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise ValueError(f"Active Session not found: {session_id}")
        owner_user_id = row["owner_user_id"]
        if owner_user_id is not None:
            try:
                principal = IdentityRepository(database).principal_for(owner_user_id)
            except IdentityBindingError as error:
                raise ValueError(
                    "Session owner is not an active installation member"
                ) from error
        else:
            principal = RequestPrincipal.legacy_local()
        return cls.from_principal(
            principal,
            session_id=session_id,
            app_instance_id=row["app_instance_id"],
        )

    @property
    def cache_namespace(self) -> str:
        """Opaque, stable namespace unique to actor + installation + Session."""

        material = "\0".join(
            (
                "ai2apps-model-cache-v1",
                self.installation_id,
                self.actor_user_id,
                str(self.membership_epoch),
                self.session_id,
            )
        ).encode("utf-8")
        return "a2c-" + hashlib.sha256(material).hexdigest()[:40]

    def audit_payload(self) -> dict[str, str | int]:
        return {
            "actor_user_id": self.actor_user_id,
            "installation_id": self.installation_id,
            "organization_id": self.organization_id,
            "billing_account_id": self.billing_account_id,
            "membership_epoch": self.membership_epoch,
            "authentication_type": self.authentication_type,
            "cache_namespace": self.cache_namespace,
        }


class ModelInvocationError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _worker_url(model: PackageModel, path: str) -> str:
    endpoint = model.endpoint or ""
    parsed = urlparse(endpoint)
    try:
        local = ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        local = False
    if parsed.scheme != "http" or not local or parsed.username or parsed.password:
        raise ModelInvocationError(
            "unsafe_worker_endpoint",
            "Model Worker must use a Host-managed loopback HTTP endpoint",
        )
    return endpoint.rstrip("/") + "/" + path.lstrip("/")


class ModelInvocationService:
    """Hide Worker endpoints, leases, resource estimates, and startup from Apps."""

    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime

    _QUEUE_TIMEOUT_SECONDS = {
        WorkloadClass.LOCAL_INTERACTIVE: 30.0,
        WorkloadClass.LOCAL_FOREGROUND: 120.0,
        WorkloadClass.LOCAL_BACKGROUND: 300.0,
    }

    def model(self, model_id: str) -> PackageModel | None:
        return resolve_package_model(self.runtime, model_id)

    def context_for_actor(
        self,
        actor_user_id: str,
        *,
        session_id: str,
        app_instance_id: str | None = None,
        consumer_app_id: str | None = None,
    ) -> ModelInvocationContext:
        """Resolve trusted scheduling identity for a durable business record."""

        if actor_user_id == "local":
            principal = RequestPrincipal.legacy_local()
        else:
            principal = IdentityRepository(self.runtime.database).principal_for(
                actor_user_id
            )
        return ModelInvocationContext.from_principal(
            principal,
            session_id=session_id,
            app_instance_id=app_instance_id,
            consumer_app_id=consumer_app_id,
        )

    @staticmethod
    def _scheduler_identity(
        context: ModelInvocationContext | None,
    ) -> dict[str, str | None]:
        return {
            "actor_id": None if context is None else context.actor_user_id,
            "app_id": (
                None
                if context is None
                else context.consumer_app_id or context.app_instance_id
            ),
            "session_id": None if context is None else context.session_id,
        }

    async def invoke_interactive_json(
        self,
        model_id: str,
        operation: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None = None,
        context: ModelInvocationContext | None = None,
    ) -> Response:
        return await self._invoke_json(
            model_id,
            operation,
            payload,
            workload_class=WorkloadClass.LOCAL_INTERACTIVE,
            request_id=request_id,
            context=context,
        )

    async def invoke_foreground_json(
        self,
        model_id: str,
        operation: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None = None,
        context: ModelInvocationContext | None = None,
    ) -> Response:
        return await self._invoke_json(
            model_id,
            operation,
            payload,
            workload_class=WorkloadClass.LOCAL_FOREGROUND,
            request_id=request_id,
            context=context,
        )

    async def invoke_background_json(
        self,
        model_id: str,
        operation: str,
        payload: Mapping[str, Any],
        *,
        request_id: str | None = None,
        context: ModelInvocationContext | None = None,
    ) -> Response:
        return await self._invoke_json(
            model_id,
            operation,
            payload,
            workload_class=WorkloadClass.LOCAL_BACKGROUND,
            request_id=request_id,
            context=context,
        )

    async def _invoke_json(
        self,
        model_id: str,
        operation: str,
        payload: Mapping[str, Any],
        *,
        workload_class: WorkloadClass,
        request_id: str | None,
        context: ModelInvocationContext | None,
    ) -> Response:
        return await proxy_package_json(
            self._require_model(model_id),
            operation,
            payload,
            workload_class=workload_class,
            request_id=request_id,
            queue_timeout_seconds=self._QUEUE_TIMEOUT_SECONDS[workload_class],
            **self._scheduler_identity(context),
        )

    async def invoke_foreground_multipart(
        self,
        model_id: str,
        operation: str,
        *,
        data: Mapping[str, Any],
        files: Mapping[str, tuple[str, bytes, str]],
        request_id: str | None = None,
        context: ModelInvocationContext | None = None,
    ) -> Response:
        return await self._invoke_multipart(
            model_id,
            operation,
            data=data,
            files=files,
            workload_class=WorkloadClass.LOCAL_FOREGROUND,
            request_id=request_id,
            context=context,
        )

    async def invoke_background_multipart(
        self,
        model_id: str,
        operation: str,
        *,
        data: Mapping[str, Any],
        files: Mapping[str, tuple[str, bytes, str]],
        request_id: str | None = None,
        context: ModelInvocationContext | None = None,
    ) -> Response:
        return await self._invoke_multipart(
            model_id,
            operation,
            data=data,
            files=files,
            workload_class=WorkloadClass.LOCAL_BACKGROUND,
            request_id=request_id,
            context=context,
        )

    async def _invoke_multipart(
        self,
        model_id: str,
        operation: str,
        *,
        data: Mapping[str, Any],
        files: Mapping[str, tuple[str, bytes, str]],
        workload_class: WorkloadClass,
        request_id: str | None,
        context: ModelInvocationContext | None,
    ) -> Response:
        return await proxy_package_multipart(
            self._require_model(model_id),
            operation,
            data=data,
            files=files,
            workload_class=workload_class,
            request_id=request_id,
            queue_timeout_seconds=self._QUEUE_TIMEOUT_SECONDS[workload_class],
            **self._scheduler_identity(context),
        )

    async def run_background_sync(
        self,
        model_id: str,
        callback: Callable[[], Any],
        *,
        request_id: str | None = None,
        transient_bytes: int = 256 * MIB,
        on_admitted: Callable[[], None] | None = None,
        context: ModelInvocationContext | None = None,
    ) -> Any:
        """Run one bounded synchronous model work unit under a background lease."""

        model = self._require_model(model_id)
        scheduler = getattr(self.runtime, "worker_scheduler", None)
        lease = None
        failed = True
        if scheduler is not None:
            lease = await scheduler.acquire(
                model.service_key,
                WorkloadClass.LOCAL_BACKGROUND,
                request_id=request_id,
                timeout_seconds=300,
                estimated_resident_bytes=(
                    estimate_model_resident_bytes(model.model_type, model.metadata)
                    if model.endpoint is None
                    else 0
                ),
                estimated_transient_bytes=transient_bytes,
                **self._scheduler_identity(context),
            )
        try:
            await ensure_package_model_ready(model)
            if on_admitted is not None:
                on_admitted()
            result = await asyncio.to_thread(callback)
            failed = False
            return result
        finally:
            if lease is not None:
                await lease.release(failed=failed)

    async def invoke_background_to_file(
        self,
        model_id: str,
        operation: str,
        payload: Mapping[str, Any],
        target: Path,
        *,
        files: Mapping[str, tuple[str, Path, str]] | None = None,
        request_id: str,
        cancel_requested: Callable[[], bool] | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
        on_admitted: Callable[[], None] | None = None,
        context: ModelInvocationContext | None = None,
    ) -> PackageModel:
        """Stream a long generation to disk without exposing its Worker to Apps."""

        model = self._require_model(model_id)
        path = model.endpoints.get(operation)
        if not path:
            raise ModelInvocationError(
                "operation_not_supported", f"Model does not support {operation}"
            )
        body = {**dict(payload), "model": model.upstream_id}
        scheduler = getattr(self.runtime, "worker_scheduler", None)
        lease = None
        failed = True
        if scheduler is not None:
            lease = await scheduler.acquire(
                model.service_key,
                WorkloadClass.LOCAL_BACKGROUND,
                request_id=request_id,
                timeout_seconds=300,
                estimated_resident_bytes=(
                    estimate_model_resident_bytes(model.model_type, model.metadata)
                    if model.endpoint is None
                    else 0
                ),
                estimated_transient_bytes=estimate_request_transient_bytes(
                    operation,
                    body,
                    file_bytes=sum(
                        item[1].stat().st_size for item in (files or {}).values()
                    ),
                ),
                **self._scheduler_identity(context),
            )
        temporary = target.with_name(f".{target.name}.part")
        opened = ExitStack()
        client = None
        response = None
        response_task: asyncio.Task[httpx.Response] | None = None
        try:
            model = await ensure_package_model_ready(model)
            url = _worker_url(model, path)
            if on_admitted is not None:
                on_admitted()
            client = httpx.AsyncClient(
                timeout=httpx.Timeout(3600.0, connect=15.0), trust_env=False
            )
            headers = {**dict(model.internal_headers or {}), "X-Request-Id": request_id}
            if files:
                upload = {
                    name: (filename, opened.enter_context(source.open("rb")), media_type)
                    for name, (filename, source, media_type) in files.items()
                }
                outbound = client.build_request(
                    "POST",
                    url,
                    data={
                        key: str(value).lower() if isinstance(value, bool) else str(value)
                        for key, value in body.items()
                        if value is not None
                    },
                    files=upload,
                    headers=headers,
                )
            else:
                outbound = client.build_request("POST", url, json=body, headers=headers)
            response_task = asyncio.create_task(client.send(outbound, stream=True))
            while not response_task.done():
                await asyncio.sleep(0.5)
                snapshot = await self.request_progress(model.id, request_id)
                value = None if snapshot is None else snapshot.get("progress")
                if progress is not None and isinstance(value, dict):
                    progress(value)
                if cancel_requested is not None and cancel_requested():
                    await self.cancel_request(model.id, request_id)
            response = await response_task
            if cancel_requested is not None and cancel_requested():
                raise ModelInvocationError(
                    "generation_cancelled", "Model generation was cancelled"
                )
            if response.status_code >= 400:
                detail = (await response.aread())[:64 * 1024].decode(
                    "utf-8", errors="replace"
                )
                code = "generation_failed"
                with suppress(ValueError, KeyError, TypeError):
                    code = json.loads(detail)["error"]["code"]
                raise ModelInvocationError(
                    code, f"Model Worker returned HTTP {response.status_code}: {detail}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            with temporary.open("xb") as output:
                async for chunk in response.aiter_bytes():
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, target)
            failed = False
            return model
        finally:
            if response_task is not None and not response_task.done():
                response_task.cancel()
                with suppress(asyncio.CancelledError):
                    await response_task
            if response is not None:
                await response.aclose()
            if client is not None:
                await client.aclose()
            opened.close()
            with suppress(FileNotFoundError):
                temporary.unlink()
            if lease is not None:
                await lease.release(failed=failed)

    async def request_progress(
        self, model_id: str, request_id: str
    ) -> dict[str, Any] | None:
        try:
            model = self._require_running_model(model_id)
            async with httpx.AsyncClient(timeout=2.0, trust_env=False) as client:
                response = await client.get(
                    _worker_url(model, f"/v1/requests/{request_id}"),
                    headers=dict(model.internal_headers or {}),
                )
            if response.status_code == 200:
                value = response.json()
                return value if isinstance(value, dict) else None
        except (httpx.HTTPError, ModelInvocationError, ValueError):
            return None
        return None

    async def cancel_request(self, model_id: str, request_id: str) -> None:
        model = self.model(model_id)
        if model is None or model.endpoint is None:
            return
        try:
            async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
                await client.delete(
                    _worker_url(model, f"/v1/requests/{request_id}"),
                    headers=dict(model.internal_headers or {}),
                )
        except httpx.HTTPError:
            return

    def _require_model(self, model_id: str) -> PackageModel:
        model = self.model(model_id)
        if model is None:
            raise ModelInvocationError(
                "model_not_found", f"Model provider not found: {model_id}"
            )
        return model

    def _require_running_model(self, model_id: str) -> PackageModel:
        model = self._require_model(model_id)
        if model.endpoint is None:
            raise ModelInvocationError(
                "model_unavailable", f"Model Worker is not running: {model_id}"
            )
        return model
