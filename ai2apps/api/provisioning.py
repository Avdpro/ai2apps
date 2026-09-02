"""Public App-facing API for the AI2Apps Capability Provisioning Framework."""

from __future__ import annotations

from typing import Any, Literal
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import (
    PrincipalProvider,
    require_app_capability,
    resolve_request_principal,
)
from ai2apps.api.ownership import authorize_app_instance
from ai2apps.apps.access import APP_USE
from ai2apps.identity import RequestPrincipal
from ai2apps.provisioning.profiles import device_profile


class CapabilityIntent(BaseModel):
    """Content-free return metadata safe for durable ACPF storage."""

    # Ignore legacy App-only fields defensively so they can never enter the
    # platform Session. Apps must still migrate to sending only this contract.
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    return_to: str | None = Field(default=None, alias="returnTo", max_length=500)
    resume_token: str | None = Field(
        default=None, alias="resumeToken", min_length=1, max_length=500
    )
    completion_policy: Literal["configure_only", "resume_action"] = Field(
        default="configure_only", alias="completionPolicy"
    )
    idempotency_key: str | None = Field(
        default=None, alias="idempotencyKey", min_length=1, max_length=240
    )

    @model_validator(mode="after")
    def validate_completion_policy(self):
        if self.return_to is not None and self.resume_token is None:
            raise ValueError("resumeToken is required when returnTo is set")
        if self.completion_policy == "resume_action" and self.idempotency_key is None:
            raise ValueError("resume_action requires idempotencyKey")
        if self.completion_policy == "configure_only" and self.idempotency_key is not None:
            raise ValueError("configure_only must not carry idempotencyKey")
        return self


class CapabilityRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    app_id: str = Field(alias="appId", min_length=1, max_length=200)
    app_instance_id: str = Field(
        alias="appInstanceId", min_length=1, max_length=200
    )
    capability: str = Field(min_length=1, max_length=200)
    action_id: str = Field(alias="actionId", min_length=1, max_length=120)
    requirements: dict[str, Any] = Field(default_factory=dict)
    intent: CapabilityIntent = Field(default_factory=CapabilityIntent)


class AcknowledgeReturnRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    idempotency_key: str | None = Field(
        default=None, alias="idempotencyKey", min_length=1, max_length=240
    )


class ProfileSelectionRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    profile_id: str = Field(alias="profileId", min_length=1, max_length=200)


class CheckpointLicenseConsentRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    distribution_id: str = Field(alias="distributionId", min_length=1, max_length=255)
    manifest_digest: str = Field(
        alias="manifestDigest", pattern=r"^sha256:[0-9a-f]{64}$"
    )
    terms_hash: str = Field(alias="termsHash", pattern=r"^sha256:[0-9a-f]{64}$")
    decision: Literal["accepted_license_terms", "obtained_separate_license"]
    confirmed: Literal[True]


class ProvisioningConfirmRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    license_consents: list[CheckpointLicenseConsentRequest] = Field(
        default_factory=list, alias="licenseConsents", max_length=20
    )


def create_provisioning_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(tags=["platform-provisioning"])
    principal_dependency = Depends(require_app_capability(principal_provider, APP_USE))

    def provisioner():
        runtime = runtime_provider()
        value = None if runtime is None else runtime.provisioning
        if value is None:
            raise HTTPException(status_code=503, detail="ACPF is not initialized")
        return value

    def trusted_app(
        body: CapabilityRequest, principal: RequestPrincipal
    ) -> tuple[str, str]:
        runtime = runtime_provider()
        if runtime is None or runtime.extension_manager is None:
            raise HTTPException(status_code=503, detail="App identity is not initialized")
        authorize_app_instance(runtime, principal, body.app_instance_id)
        entry = runtime.extension_manager.instance_entry(
            body.app_instance_id, principal=principal
        )
        trusted_app_id = str(entry["app_key"])
        if body.app_id != trusted_app_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "app_identity_mismatch",
                    "message": "The requested appId does not match the trusted App instance",
                },
            )
        return trusted_app_id, body.app_instance_id

    def normalized_intent(body: CapabilityRequest) -> dict[str, Any]:
        intent = body.intent.model_dump(by_alias=True, exclude_none=True)
        return_to = intent.get("returnTo")
        if return_to is not None:
            target = urlsplit(return_to)
            expected_path = f"/apps/{body.app_id}"
            if target.scheme or target.netloc or target.path.rstrip("/") != expected_path:
                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "invalid_return_target",
                        "message": "returnTo must target the requesting App",
                    },
                )
        return intent

    def owned_session(
        session_id: str,
        principal: RequestPrincipal,
        app_instance_id: str | None = None,
    ):
        session = provisioner().repository.get(session_id)
        if session is None:
            raise HTTPException(
                status_code=404, detail="Provisioning session not found"
            )
        if (
            session["actorId"] != principal.actor_user_id
            or session["installationId"] != principal.installation_id
            or (
                app_instance_id is not None
                and session["appInstanceId"] != app_instance_id
            )
        ):
            raise HTTPException(
                status_code=404, detail="Provisioning session not found"
            )
        return session

    @router.post("/capabilities/probe")
    def probe(
        body: CapabilityRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        trusted_app_id, _ = trusted_app(body, principal)
        engine = provisioner()
        plan = engine.plan(trusted_app_id, body.capability, body.requirements)
        ready = None if plan is None else engine.resolve_plan_ready(plan)
        return {
            "status": "ready"
            if ready is not None
            else ("setup_required" if plan else "unsupported"),
            "device": device_profile(),
            "provider": ready,
            "plan": plan,
        }

    @router.post("/capabilities/ensure")
    def ensure(
        body: CapabilityRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        trusted_app_id, app_instance_id = trusted_app(body, principal)
        return provisioner().ensure(
            actor_id=principal.actor_user_id,
            installation_id=principal.installation_id,
            app_instance_id=app_instance_id,
            app_id=trusted_app_id,
            capability=body.capability,
            action_id=body.action_id,
            requirements=body.requirements,
            intent=normalized_intent(body),
        )

    @router.get("/provisioning/sessions")
    def active_sessions(
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str | None = Header(
            default=None, alias="X-AI2Apps-App-Instance"
        ),
    ):
        sessions = provisioner().repository.list_returnable(
            actor_id=principal.actor_user_id
        )
        return {
            "items": [
                item
                for item in sessions
                if item["installationId"] == principal.installation_id
                and (
                    app_instance_id is None
                    or item["appInstanceId"] == app_instance_id
                )
            ]
        }

    @router.post("/provisioning/sessions/{session_id}/acknowledge-return")
    def acknowledge_return(
        session_id: str,
        body: AcknowledgeReturnRequest | None = None,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        session = owned_session(session_id, principal, app_instance_id)
        intent = session["intent"]
        if (
            intent.get("completionPolicy") == "resume_action"
            and (body is None or body.idempotency_key != intent.get("idempotencyKey"))
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "resume_idempotency_key_mismatch",
                    "message": "The completed action idempotency key is required",
                },
            )
        return provisioner().repository.acknowledge_return(session_id)

    @router.get("/provisioning/sessions/{session_id}")
    async def get_session(
        session_id: str,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        owned_session(session_id, principal, app_instance_id)
        return await provisioner().resume_if_possible(session_id)

    @router.post("/provisioning/sessions/{session_id}/confirm")
    async def confirm(
        session_id: str,
        body: ProvisioningConfirmRequest | None = None,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        owned_session(session_id, principal, app_instance_id)
        if not principal.is_core:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "owner_required",
                    "message": "Only the Installation owner can install this stack",
                },
            )
        return await provisioner().confirm(
            session_id,
            []
            if body is None
            else [
                item.model_dump(by_alias=True)
                for item in body.license_consents
            ],
        )

    @router.post("/provisioning/sessions/{session_id}/select-profile")
    def select_profile(
        session_id: str,
        body: ProfileSelectionRequest,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        owned_session(session_id, principal, app_instance_id)
        try:
            return provisioner().select_profile(session_id, body.profile_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @router.post("/provisioning/sessions/{session_id}/retry")
    async def retry(
        session_id: str,
        body: ProvisioningConfirmRequest | None = None,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        session = owned_session(session_id, principal, app_instance_id)
        if not principal.is_core:
            raise HTTPException(status_code=403, detail="Installation owner required")
        if session["status"] != "failed":
            raise HTTPException(
                status_code=409, detail="Only failed sessions can retry"
            )
        return await provisioner().confirm(
            session_id,
            []
            if body is None
            else [
                item.model_dump(by_alias=True)
                for item in body.license_consents
            ],
        )

    @router.post("/provisioning/sessions/{session_id}/cancel")
    async def cancel(
        session_id: str,
        principal: RequestPrincipal = principal_dependency,
        app_instance_id: str = Header(alias="X-AI2Apps-App-Instance"),
    ):
        owned_session(session_id, principal, app_instance_id)
        return await provisioner().cancel(session_id)

    return router
