"""Desktop Mail API. Credential payloads never go through tool or form storage."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool
from typing import Annotated, Literal

from ai2apps.api.identity import require_app_capability
from ai2apps.mail.ai_assist import assist
from ai2apps.mail.drafts import MAX_ATTACHMENT_REQUEST, MAX_ATTACHMENTS
from ai2apps.mail.imap import MailError
from ai2apps.mail.service import is_mobile_mail_owner
from ai2apps.secrets.backends import SecretBackendError
from ai2apps.task_llm import resolve_task_model


class Credential(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    password: str = Field(min_length=1, max_length=1024, repr=False)


class LoadRemoteImages(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageMarker(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    kind: Literal["pin", "flag", "todo"]
    enabled: bool
    language: Literal["zh", "en"] = "en"


class MailAttachment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    name: str = Field(min_length=1, max_length=255)
    data: str


class SendMail(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    recipients: list[str] = Field(min_length=1, max_length=20)
    subject: str = Field(max_length=500)
    body: str = Field(max_length=32000)
    attachments: list[MailAttachment] = Field(default_factory=list, max_length=MAX_ATTACHMENTS)


class DraftReply(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    validity: int = Field(gt=0)
    uid: int = Field(gt=0)


class SaveDraft(SendMail):
    account_id: str = Field(min_length=1, max_length=64)
    recipients: list[str] = Field(max_length=20)
    reply: DraftReply | None = None
    revision: int | None = Field(default=None, ge=1)


class DraftRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    revision: int = Field(ge=1)


class ReviewDraft(LoadRemoteImages):
    decision: Literal["confirmed", "cancelled"]
    revision: int = Field(ge=1)


class StartGmail(LoadRemoteImages):
    account_id: str | None = Field(default=None, min_length=1, max_length=64)


class AnalyzeMail(StartGmail):
    language: Literal["zh", "en"] = "en"


class WritingAssist(LoadRemoteImages):
    action: Literal["directions", "write"]
    instruction: str = Field(default="", max_length=2000)
    direction: str = Field(default="", max_length=120)
    subject: str = Field(default="", max_length=500)
    body: str = Field(default="", max_length=32000)
    language: Literal["zh", "en"] = "en"


class SmartFolderRule(LoadRemoteImages):
    name: str = Field(min_length=1, max_length=60)
    rule: str = Field(min_length=1, max_length=800)
    excluded_senders: list[Annotated[str, Field(min_length=1, max_length=254)]] | None = Field(default=None, max_length=30)
    guidance: str | None = Field(default=None, max_length=800)


class PreviewSmartFolder(AnalyzeMail, SmartFolderRule):
    pass


class UpdateSmartFolder(SmartFolderRule):
    revision: int = Field(ge=1)


class ClassificationFeedback(LoadRemoteImages):
    folder_id: str = Field(min_length=1, max_length=64)
    included: bool


class BlockFolderSender(LoadRemoteImages):
    folder_id: str = Field(min_length=1, max_length=64)
    kind: Literal["address", "domain"]
    preview: bool = False
    expected_sender: str | None = Field(default=None, min_length=1, max_length=500)


class UpdateViewFilters(LoadRemoteImages):
    excluded_senders: list[Annotated[str, Field(min_length=1, max_length=254)]] = Field(max_length=30)
    revision: int = Field(ge=0)


class Connect(Credential):
    provider: Literal["imap", "gmail", "icloud"]
    address: str = Field(min_length=3, max_length=254)
    display_name: str = Field(default="", max_length=100)
    host: str = Field(default="", max_length=253)
    port: int = Field(default=993, ge=1, le=65535)
    username: str = Field(default="", max_length=254)
    smtp_host: str = Field(default="", max_length=253)
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = Field(default="", max_length=254)
    smtp_tls: Literal["implicit", "starttls"] = "starttls"


async def _parse(request, model, *, limit=8192, invalid="invalid_account_settings",
                 too_large="account_settings_too_large"):
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415, "json_required")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > limit:
            raise HTTPException(413, too_large)
        data.extend(chunk)
    try:
        return model.model_validate_json(data)
    except ValidationError:
        raise HTTPException(422, invalid) from None


def create_mail_router(runtime_provider, principal_provider, *, mobile=False):
    guard = Depends(require_app_capability(principal_provider, "app.use"))
    router = APIRouter(prefix="/mail", tags=["mail"])

    def mail_service(principal):
        if not (is_mobile_mail_owner(principal) if mobile else principal.client_scope == "desktop"):
            raise HTTPException(403, "desktop_mail_only")
        service = getattr(runtime_provider(), "mail", None)
        if service is None:
            raise HTTPException(503, "mail_not_ready")
        return service

    def translate(error):
        status = {
            "invalid_smart_folder": 422, "smart_folder_limit": 422,
            "invalid_smart_folder_sender": 422, "smart_folder_sender_excluded": 409,
            "smart_folder_sender_unavailable": 422, "smart_folder_sender_limit": 422,
            "smart_folder_sender_changed": 409,
            "duplicate_smart_folder": 409, "smart_folders_changed": 409,
            "mail_privacy_model_required": 503, "mail_analysis_failed": 502,
            "inbox_changed": 409, "mail_busy": 429, "reconnect_required": 409,
        }.get(error.code, 502)
        return HTTPException(status, error.code)

    def call(name, principal, *args, **kwargs):
        service = mail_service(principal)
        try:
            section, _, method = name.rpartition(".")
            target = getattr(service, section) if section else service
            return getattr(target, method)(principal, *args, **kwargs)
        except PermissionError:
            raise HTTPException(403, "desktop_mail_only") from None
        except KeyError:
            raise HTTPException(404, "mail_item_not_found") from None
        except SecretBackendError:
            raise HTTPException(503, "mail_secret_unavailable") from None
        except MailError as error:
            status = {
                "invalid_host": 422, "invalid_address": 422, "invalid_credentials_format": 422,
                "gmail_app_password_required": 422, "authentication_failed": 409,
                "reconnect_required": 409, "account_changed": 409, "inbox_changed": 409,
                "gmail_oauth_unconfigured": 503, "gmail_oauth_expired": 410,
                "gmail_oauth_denied": 409, "gmail_oauth_scope_missing": 409,
                "gmail_oauth_account_mismatch": 409, "gmail_oauth_account_exists": 409,
                "gmail_oauth_required": 409,
                "mail_busy": 429,
                "mail_pin_limit": 409, "mail_todo_unavailable": 503,
                "mail_invalid_recipient": 422, "mail_invalid_draft": 422,
                "mail_smtp_unconfigured": 409, "mail_smtp_auth_failed": 409,
                "mail_reply_target_changed": 409, "mail_reply_unavailable": 409,
                "mail_send_uncertain": 502, "mail_send_connection": 502,
                "mail_send_rejected": 502, "mail_recipient_rejected": 502,
                "mail_attachments_too_large": 413, "mail_invalid_attachment": 422, "mail_draft_changed": 409,
            }.get(error.code)
            raise (HTTPException(status, error.code) if status else translate(error)) from None

    @router.get("/smart-folders")
    def smart_folders(response: Response, language: Literal["zh", "en"] = "en", principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("smart.folders", principal, language)

    @router.get("/smart-folders/unread-counts")
    def smart_unread_counts(response: Response, account_id: str | None = None, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("smart.unread_counts", principal, account_id)

    @router.get("/smart-folders/{folder_id}/sender-filters")
    def sender_filters(folder_id: str, response: Response, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("smart.view_filters", principal, folder_id)

    @router.put("/smart-folders/{folder_id}/sender-filters", status_code=204)
    async def save_sender_filters(folder_id: str, request: Request, principal=guard):
        body = await _parse(request, UpdateViewFilters, limit=32768, invalid="invalid_smart_folder_sender")
        await run_in_threadpool(call, "smart.save_view_filters", principal, folder_id,
                                body.excluded_senders, body.revision)
        return Response(status_code=204)

    @router.get("/analysis/model")
    def analysis_model(response: Response, principal=guard):
        mail_service(principal)
        response.headers["Cache-Control"] = "private, no-store"
        return {"model": resolve_task_model(runtime_provider(), "standard", "privacy")}

    @router.post("/smart-folders", status_code=201)
    async def create_smart_folder(request: Request, principal=guard):
        body = await _parse(request, SmartFolderRule, limit=32768, invalid="invalid_smart_folder")
        return await run_in_threadpool(call, "smart.save", principal, body.name, body.rule,
                                       excluded_senders=body.excluded_senders, guidance=body.guidance)

    @router.put("/smart-folders/{folder_id}")
    async def update_smart_folder(folder_id: str, request: Request, principal=guard):
        body = await _parse(request, UpdateSmartFolder, limit=32768, invalid="invalid_smart_folder")
        return await run_in_threadpool(call, "smart.save", principal, body.name, body.rule, folder_id, body.revision,
                                       excluded_senders=body.excluded_senders, guidance=body.guidance)

    @router.delete("/smart-folders/{folder_id}", status_code=204)
    def delete_smart_folder(folder_id: str, revision: int = Query(ge=1), principal=guard):
        call("smart.delete", principal, folder_id, revision)
        return Response(status_code=204)

    @router.get("/smart-folders/{folder_id}/messages")
    def smart_messages(folder_id: str, response: Response, account_id: str | None = None,
                       limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                       principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("smart.view", principal, folder_id, account_id, limit, offset)

    async def analyze(request, response, principal, mode):
        model = PreviewSmartFolder if mode == "preview" else AnalyzeMail
        body = (await _parse(request, model, limit=32768, invalid="invalid_smart_folder")
                if mode == "preview" else await _parse(request, model))
        smart = mail_service(principal).smart
        response.headers["Cache-Control"] = "private, no-store"
        try:
            if mode == "suggest":
                return await smart.suggest(runtime_provider(), principal, body.account_id, body.language)
            rule = {"name": body.name, "rule": body.rule, "excluded_senders": body.excluded_senders,
                    "guidance": (body.guidance or "").strip()} if mode == "preview" else None
            return await smart.classify(runtime_provider(), principal, body.account_id, rule, body.language)
        except KeyError:
            raise HTTPException(404, "mail_item_not_found") from None
        except MailError as error:
            raise translate(error) from None
        except SecretBackendError:
            raise HTTPException(503, "mail_secret_unavailable") from None

    @router.post("/analysis")
    async def classify(request: Request, response: Response, principal=guard):
        return await analyze(request, response, principal, "classify")

    @router.post("/analysis/suggestions")
    async def suggest(request: Request, response: Response, principal=guard):
        return await analyze(request, response, principal, "suggest")

    @router.post("/analysis/preview")
    async def preview_rule(request: Request, response: Response, principal=guard):
        return await analyze(request, response, principal, "preview")

    async def writing_assist(request, response, principal, account_id, reply=None):
        mail = mail_service(principal)
        body = await _parse(request, WritingAssist, limit=256 * 1024, invalid="mail_invalid_assist")
        response.headers["Cache-Control"] = "private, no-store"
        try:
            return await assist(runtime_provider(), mail, principal, account_id, body, reply)
        except KeyError:
            raise HTTPException(404, "mail_item_not_found") from None
        except SecretBackendError:
            raise HTTPException(503, "mail_secret_unavailable") from None
        except MailError as error:
            if error.code == "mail_invalid_assist":
                raise HTTPException(422, error.code) from None
            raise translate(error) from None

    @router.post("/accounts/{account_id}/writing-assist")
    async def assist_new(account_id: str, request: Request, response: Response, principal=guard):
        return await writing_assist(request, response, principal, account_id)

    @router.post("/accounts/{account_id}/messages/{validity}/{uid}/writing-assist")
    async def assist_reply(account_id: str, validity: int, uid: int, request: Request,
                           response: Response, principal=guard):
        return await writing_assist(request, response, principal, account_id, (validity, uid))

    @router.post("/accounts/{account_id}/messages/{validity}/{uid}/classification", status_code=204)
    async def feedback(account_id: str, validity: int, uid: int, request: Request, principal=guard):
        body = await _parse(request, ClassificationFeedback)
        await run_in_threadpool(call, "smart.feedback", principal, account_id, validity, uid,
                                body.folder_id, body.included)
        return Response(status_code=204)

    @router.post("/accounts/{account_id}/messages/{validity}/{uid}/block-sender")
    async def block_sender(account_id: str, validity: int, uid: int, request: Request, principal=guard):
        body = await _parse(request, BlockFolderSender, invalid="invalid_smart_folder_sender")
        return await run_in_threadpool(call, "smart.block_sender", principal, account_id, validity, uid,
                                       body.folder_id, body.kind, preview=body.preview,
                                       expected_sender=body.expected_sender)

    @router.get("/accounts")
    def accounts(response: Response, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("accounts", principal)

    @router.post("/accounts", status_code=201)
    async def connect(request: Request, principal=guard):
        if principal.client_scope != "desktop":
            raise HTTPException(403, "desktop_mail_only")
        body = await _parse(request, Connect)
        return await run_in_threadpool(call, "connect", principal, body.model_dump())

    @router.post("/accounts/{account_id}/reconnect")
    async def reconnect(account_id: str, request: Request, principal=guard):
        if principal.client_scope != "desktop":
            raise HTTPException(403, "desktop_mail_only")
        body = await _parse(request, Credential)
        return await run_in_threadpool(call, "reconnect", principal, account_id, body.password)

    @router.post("/gmail/oauth")
    async def start_gmail(request: Request, response: Response, principal=guard):
        body = await _parse(request, StartGmail)
        response.headers["Cache-Control"] = "no-store"
        return await run_in_threadpool(call, "start_gmail", principal, body.account_id)

    @router.post("/gmail/oauth/{flow_id}")
    async def finish_gmail(flow_id: str, request: Request, response: Response, principal=guard):
        await _parse(request, LoadRemoteImages)
        response.headers["Cache-Control"] = "no-store"
        return await run_in_threadpool(call, "finish_gmail", principal, flow_id)

    @router.delete("/gmail/oauth/{flow_id}", status_code=204)
    def cancel_gmail(flow_id: str, principal=guard):
        call("cancel_gmail", principal, flow_id)
        return Response(status_code=204)

    @router.delete("/accounts/{account_id}", status_code=204)
    def disconnect(account_id: str, principal=guard):
        call("disconnect", principal, account_id)
        return Response(status_code=204)

    @router.post("/accounts/{account_id}/sync")
    def sync(account_id: str, principal=guard):
        return call("sync", principal, account_id)

    @router.get("/messages")
    def messages(response: Response, account_id: str | None = None,
                 limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0, le=10000),
                 q: str = Query("", max_length=200), principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("messages", principal, account_id, limit, offset, q)

    @router.get("/accounts/{account_id}/messages/{validity}/{uid}")
    def preview(account_id: str, validity: int, uid: int, response: Response, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("preview", principal, account_id, validity, uid)

    @router.post("/accounts/{account_id}/messages/{validity}/{uid}/read", status_code=204)
    async def mark_read(account_id: str, validity: int, uid: int, request: Request, principal=guard):
        await _parse(request, LoadRemoteImages)
        await run_in_threadpool(call, "mark_read", principal, account_id, validity, uid)
        return Response(status_code=204)

    @router.put("/accounts/{account_id}/messages/{validity}/{uid}/marker", status_code=204)
    async def set_marker(account_id: str, validity: int, uid: int, request: Request, principal=guard):
        body = await _parse(request, MessageMarker)
        await run_in_threadpool(call, "set_marker", principal, account_id, validity, uid,
                                body.kind, body.enabled, body.language)
        return Response(status_code=204)

    @router.get("/todo-state")
    def todo_state(response: Response, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("todo_state", principal)

    @router.get("/accounts/{account_id}/messages/{validity}/{uid}/reply")
    def reply_info(account_id: str, validity: int, uid: int, response: Response, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("reply_info", principal, account_id, validity, uid)

    async def submit_mail(request, principal, account_id, reply=None):
        body = await _parse(request, SendMail, limit=MAX_ATTACHMENT_REQUEST, invalid="mail_invalid_draft",
                            too_large="mail_attachments_too_large")
        return await run_in_threadpool(call, "send", principal, account_id,
                                       body.recipients, body.subject, body.body, reply,
                                       [attachment.model_dump() for attachment in body.attachments])

    @router.post("/accounts/{account_id}/send")
    async def send_mail(account_id: str, request: Request, principal=guard):
        return await submit_mail(request, principal, account_id)

    @router.post("/accounts/{account_id}/messages/{validity}/{uid}/reply")
    async def send_reply(account_id: str, validity: int, uid: int, request: Request, principal=guard):
        return await submit_mail(request, principal, account_id, (validity, uid))

    @router.get("/drafts")
    def list_drafts(response: Response, account_id: str | None = None, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("drafts.list", principal, account_id)

    @router.get("/drafts/{draft_id}")
    def get_draft(draft_id: str, response: Response, principal=guard):
        response.headers["Cache-Control"] = "private, no-store"
        return call("drafts.get", principal, draft_id)

    async def store_draft(request, principal, draft_id=None):
        body = await _parse(request, SaveDraft, limit=MAX_ATTACHMENT_REQUEST, invalid="mail_invalid_draft",
                            too_large="mail_attachments_too_large")
        if bool(draft_id) != bool(body.revision):
            raise HTTPException(422, "mail_invalid_draft")
        return await run_in_threadpool(call, "drafts.save", principal, body.account_id,
                                       body.model_dump(exclude={"account_id", "revision"}), draft_id, body.revision)

    @router.post("/drafts", status_code=201)
    async def create_draft(request: Request, principal=guard):
        return await store_draft(request, principal)

    @router.put("/drafts/{draft_id}")
    async def update_draft(draft_id: str, request: Request, principal=guard):
        return await store_draft(request, principal, draft_id)

    @router.delete("/drafts/{draft_id}", status_code=204)
    def delete_draft(draft_id: str, revision: int = Query(ge=1), principal=guard):
        call("drafts.delete", principal, draft_id, revision)
        return Response(status_code=204)

    @router.post("/drafts/{draft_id}/send")
    async def send_draft(draft_id: str, request: Request, principal=guard):
        body = await _parse(request, DraftRevision, invalid="mail_invalid_draft")
        return await run_in_threadpool(call, "drafts.send", principal, draft_id, body.revision)

    def review_target(runtime, principal, run_id, interaction_id):
        from ai2apps.agents.app_interactions import require_handoff
        from ai2apps.api.ownership import authorize_agent_run
        from ai2apps.core import RepositoryError
        from ai2apps.mail.aaat import REVIEW

        authorize_agent_run(runtime, principal, run_id)
        try:
            run, interaction, _ = require_handoff(runtime.agents, run_id, interaction_id, capability=REVIEW)
        except RepositoryError:
            raise HTTPException(409, "mail_review_unavailable") from None
        return run, interaction

    def review_draft(principal, run, interaction):
        draft = call("drafts.get", principal, interaction.request["parameters"]["draft_id"])
        origin = draft.pop("agent_origin", {})
        if origin.get("session_id") != run.session_id or origin.get("run_id") != run.id or draft["status"] != "draft":
            raise HTTPException(404, "mail_item_not_found")
        return draft

    @router.get("/reviews/{run_id}/{interaction_id}")
    def read_review(run_id: str, interaction_id: str, response: Response, principal=guard):
        mail_service(principal)
        run, interaction = review_target(runtime_provider(), principal, run_id, interaction_id)
        if interaction.status.value != "pending":
            raise HTTPException(409, "mail_review_unavailable")
        response.headers["Cache-Control"] = "private, no-store"
        return review_draft(principal, run, interaction)

    @router.post("/reviews/{run_id}/{interaction_id}")
    async def complete_review(run_id: str, interaction_id: str, request: Request, principal=guard):
        from ai2apps.core import RepositoryError
        from ai2apps.mail.aaat import REVIEW

        mail_service(principal)
        body = await _parse(request, ReviewDraft, invalid="mail_review_unavailable")
        runtime = runtime_provider()

        def finish():
            run, interaction = review_target(runtime, principal, run_id, interaction_id)
            status = "completed" if body.decision == "confirmed" else "cancelled"
            if interaction.status.value == "submitted":
                if interaction.response["status"] == status and (
                    status == "cancelled" or interaction.response["result"]["revision"] == body.revision
                ):
                    return interaction.response
                raise HTTPException(409, "mail_review_unavailable")
            if interaction.status.value != "pending":
                raise HTTPException(409, "mail_review_unavailable")
            result = {}
            if status == "completed":
                draft = review_draft(principal, run, interaction)
                if draft["revision"] != body.revision:
                    raise HTTPException(409, "mail_draft_changed")
                result = {"draft_id": draft["id"], "revision": draft["revision"], "sent": False}
            response = {"status": status, "result": result}
            try:
                runtime.agents.respond_interaction(
                    run_id, interaction_id, response=response, response_id="mail-review:" + interaction_id,
                    app_interaction_capability=REVIEW,
                )
            except RepositoryError:
                raise HTTPException(409, "mail_review_unavailable") from None
            return response

        response = await run_in_threadpool(finish)
        runtime.agent_runtime.wake()
        return response

    @router.post("/accounts/{account_id}/messages/{validity}/{uid}/remote-images")
    async def remote_images(account_id: str, validity: int, uid: int, request: Request,
                            response: Response, principal=guard):
        await _parse(request, LoadRemoteImages)
        response.headers["Cache-Control"] = "private, no-store"
        return await run_in_threadpool(call, "preview", principal, account_id, validity, uid, True)

    if mobile:
        # Keep mailbox credentials, Desktop OAuth and account removal off the
        # phone. Newly added desktop routes require an explicit mobile review.
        allowed = {
            "GET": {
                "/accounts", "/messages", "/analysis/model", "/smart-folders",
                "/smart-folders/unread-counts", "/smart-folders/{folder_id}/messages",
                "/smart-folders/{folder_id}/sender-filters",
                "/accounts/{account_id}/messages/{validity}/{uid}",
                "/accounts/{account_id}/messages/{validity}/{uid}/reply",
                "/todo-state", "/drafts", "/drafts/{draft_id}",
            },
            "POST": {
                "/accounts/{account_id}/sync", "/analysis", "/analysis/suggestions",
                "/analysis/preview", "/smart-folders",
                "/accounts/{account_id}/messages/{validity}/{uid}/read",
                "/accounts/{account_id}/messages/{validity}/{uid}/classification",
                "/accounts/{account_id}/messages/{validity}/{uid}/block-sender",
                "/accounts/{account_id}/messages/{validity}/{uid}/remote-images",
                "/accounts/{account_id}/messages/{validity}/{uid}/reply",
                "/accounts/{account_id}/send", "/drafts", "/drafts/{draft_id}/send",
                "/accounts/{account_id}/writing-assist",
                "/accounts/{account_id}/messages/{validity}/{uid}/writing-assist",
            },
            "PUT": {"/smart-folders/{folder_id}", "/smart-folders/{folder_id}/sender-filters", "/drafts/{draft_id}",
                    "/accounts/{account_id}/messages/{validity}/{uid}/marker"},
            "DELETE": {"/smart-folders/{folder_id}", "/drafts/{draft_id}"},
        }
        router.routes[:] = [
            route for route in router.routes
            if any(route.path.removeprefix("/mail") in allowed.get(method, ())
                   for method in route.methods)
        ]
    return router


def create_mobile_mail_router(runtime_provider, principal_provider):
    return create_mail_router(runtime_provider, principal_provider, mobile=True)
