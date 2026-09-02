"""Authenticated API for the system-wide, model-free Knowledge Core."""

from __future__ import annotations

import asyncio
import ipaddress
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from pydantic import BaseModel, Field, HttpUrl

from ai2apps.api.errors import platform_error_response
from ai2apps.api.health import PlatformRuntimeProvider
from ai2apps.api.identity import PrincipalProvider, resolve_request_principal
from ai2apps.browser import BrowserControlState, BrowserError
from ai2apps.chat import ChatRepository
from ai2apps.config import DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES
from ai2apps.core import MessageRole, ResourceConflictError
from ai2apps.events import EventStore
from ai2apps.identity import RequestPrincipal, user_singleton_key
from ai2apps.managed_browser import managed_browser_broker
from ai2apps.knowledge import (
    KnowledgeAccessError,
    KnowledgeConflictError,
    KnowledgeNotFoundError,
    KnowledgeScope,
    KnowledgeStore,
)
from ai2apps.storage import MessagePartInput
from ai2apps.storage.repositories import (
    AppRepository,
    MessageRepository,
    SessionRepository,
)


class KnowledgeItemCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=2_000_000)
    scope: Literal["private", "installation"] = "private"
    kind: Literal[
        "webpage", "document", "image", "audio", "video", "chat", "artifact", "note"
    ] = "note"
    source_app_id: str | None = Field(default=None, max_length=255)
    source_session_id: str | None = Field(default=None, max_length=255)
    source_url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)
    bucket_id: str | None = None
    extraction_method: str | None = Field(default=None, max_length=100)
    capture_mode: Literal["page", "selection"] = "page"


class KnowledgeItemUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    text: str = Field(min_length=1, max_length=2_000_000)
    revision: int = Field(ge=1)
    extraction_method: str | None = Field(default=None, max_length=100)
    capture_mode: Literal["page", "selection"] = "page"


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    scope: Literal["private", "installation"] | None = None
    kind: (
        Literal[
            "webpage", "document", "image", "audio", "video", "chat", "artifact", "note"
        ]
        | None
    ) = None
    tags: list[str] = Field(default_factory=list, max_length=50)
    limit: int = Field(default=20, ge=1, le=100)
    bucket_ids: list[str] = Field(default_factory=list, max_length=100)
    source_app_id: str | None = Field(default=None, max_length=255)
    source_session_id: str | None = Field(default=None, max_length=255)
    source_after: datetime | None = None
    source_before: datetime | None = None


class KnowledgeBucketCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    scope: Literal["private", "installation"] = "private"
    imported: bool = False


class KnowledgeContextRequest(BaseModel):
    bucket_ids: list[str] = Field(default_factory=list, max_length=100)


class KnowledgeContextSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4_000)
    session_id: str | None = Field(default=None, min_length=1, max_length=128)
    limit: int = Field(default=8, ge=1, le=20)


class KnowledgeWebImportRequest(BaseModel):
    url: HttpUrl
    bucket_id: str
    title: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=50)
    fetch_mode: Literal["auto", "acefox", "static"] = "auto"
    auto_accept_cookies: bool = True


class KnowledgeChatImportRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    start_index: int = Field(ge=0)
    end_index: int = Field(ge=0)
    bucket_id: str
    title: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=50)
    include_attachments: bool = True
    selection_text: str | None = Field(default=None, max_length=100_000)
    link_url: HttpUrl | None = None
    artifact_ids: list[str] = Field(default_factory=list, max_length=20)


class KnowledgeAskSaveRequest(BaseModel):
    request_id: str = Field(min_length=1, max_length=128)
    question: str = Field(min_length=1, max_length=20_000)
    answer: str = Field(min_length=1, max_length=100_000)
    model: str | None = Field(default=None, max_length=500)
    bucket_ids: list[str] = Field(default_factory=list, max_length=100)
    citations: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    retrieval: dict[str, Any] | None = None


def _public_web_url(value: str) -> str:
    parsed = urllib.parse.urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only public http/https webpage URLs are supported")
    if parsed.username or parsed.password:
        raise ValueError("webpage URLs must not contain credentials")
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port or 443)
    except socket.gaierror as error:
        raise ValueError("webpage host could not be resolved") from error
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("webpage URL resolves to a non-public address")
    return urllib.parse.urlunsplit(parsed)


class _PublicRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return super().redirect_request(
            req, fp, code, msg, headers, _public_web_url(newurl)
        )


def _validate_public_peer(response: Any) -> None:
    """Fail closed if the connected peer changed to a non-public address."""

    try:
        peer = response.fp.raw._sock.getpeername()[0]
        address = ipaddress.ip_address(peer)
    except (AttributeError, IndexError, TypeError, ValueError, OSError) as error:
        raise ValueError("webpage connection peer could not be verified") from error
    if not address.is_global:
        raise ValueError("webpage connection reached a non-public address")


def _clean_web_node(node: Any) -> None:
    for child in node.select(
        "script,style,noscript,template,svg,canvas,nav,header,footer,aside,form,dialog"
    ):
        child.decompose()
    for child in list(node.find_all(True)):
        marker = " ".join(
            [str(child.get("id") or ""), *[str(value) for value in child.get("class", ())]]
        ).casefold()
        if re.search(r"(?:^|[-_ ])(?:cookie|consent|gdpr|advert|newsletter|paywall)(?:[-_ ]|$)", marker):
            child.decompose()


def _web_node_text(node: Any) -> str:
    blocks = []
    for child in node.select("h1,h2,h3,h4,h5,h6,p,blockquote,pre,li,figcaption,td,th"):
        if child.find_parent(["p", "li", "blockquote", "pre", "td", "th"]):
            continue
        value = re.sub(r"\s+", " ", child.get_text(" ", strip=True)).strip()
        if value and (not blocks or blocks[-1] != value):
            blocks.append(value)
    if not blocks:
        value = re.sub(r"\s+", " ", node.get_text(" ", strip=True)).strip()
        return value
    return "\n\n".join(blocks)


def _extract_static_webpage(source: str, final_url: str) -> tuple[str, str]:
    """Run a local Readability-style main-content pass with cleaned-DOM fallback."""

    from bs4 import BeautifulSoup

    document = BeautifulSoup(source, "html.parser")
    title = document.title.get_text(" ", strip=True) if document.title else final_url
    for node in document(["script", "style", "noscript", "template", "svg", "canvas"]):
        node.decompose()

    candidates = list(document.select("article,main,[role='main']"))
    candidates.extend(
        node
        for node in document.select("section,div")
        if len(node.find_all("p", recursive=True)) >= 2
    )
    best = None
    best_score = float("-inf")
    for candidate in candidates:
        text = re.sub(r"\s+", " ", candidate.get_text(" ", strip=True)).strip()
        if len(text) < 300:
            continue
        link_characters = sum(
            len(re.sub(r"\s+", " ", link.get_text(" ", strip=True)))
            for link in candidate.find_all("a")
        )
        link_density = link_characters / max(1, len(text))
        paragraphs = [
            re.sub(r"\s+", " ", value.get_text(" ", strip=True)).strip()
            for value in candidate.find_all("p")
        ]
        long_paragraphs = sum(len(value) >= 120 for value in paragraphs)
        punctuation = len(re.findall(r"[.!?。！？,，]", text))
        marker = " ".join(
            [str(candidate.get("id") or ""), *candidate.get("class", ())]
        ).casefold()
        score = (
            len(text)
            + punctuation * 18
            + long_paragraphs * 240
            - link_density * len(text) * 2.5
        )
        if candidate.name == "article":
            score += 1_000
        elif candidate.name == "main" or candidate.get("role") == "main":
            score += 650
        if re.search(r"article|content|entry|post|story", marker):
            score += 500
        if re.search(r"nav|menu|sidebar|related|comment", marker):
            score -= 1_500
        if score > best_score:
            best, best_score = candidate, score

    if best is not None:
        extracted = BeautifulSoup(str(best), "html.parser")
        _clean_web_node(extracted)
        text = _web_node_text(extracted)
        if len(text) >= 400:
            return title[:500], text[:2_000_000]

    fallback = document.body or document
    _clean_web_node(fallback)
    text = _web_node_text(fallback)
    if not text:
        raise ValueError("webpage did not contain readable text")
    return title[:500], text[:2_000_000]


def _web_content_sufficient(text: str) -> bool:
    if len(text.strip()) < 600:
        return False
    paragraphs = [value.strip() for value in re.split(r"\n{2,}", text) if value.strip()]
    sentence_marks = len(re.findall(r"[.!?。！？](?:\s|$)", text))
    return len(paragraphs) >= 2 and sentence_marks >= 2


def _fetch_webpage(value: str) -> tuple[str, str, str]:
    url = _public_web_url(value)
    # Fetch directly so the connected peer remains the destination that was
    # validated above. urllib otherwise inherits HTTP(S)_PROXY from the Local
    # runtime; a loopback proxy then looks like a private destination and makes
    # every public import fail. Trusting that proxy peer would weaken the SSRF
    # check because it can resolve a public hostname to a private address.
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({}),
        _PublicRedirectHandler(),
    )
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "AI2Apps-Knowledge/1.0",
            "Accept": "text/html,application/xhtml+xml,text/plain;q=0.8",
        },
    )
    try:
        with opener.open(request, timeout=20) as response:
            _validate_public_peer(response)
            content_type = response.headers.get_content_type()
            if content_type not in {
                "text/html",
                "application/xhtml+xml",
                "text/plain",
            }:
                raise ValueError("webpage returned an unsupported content type")
            data = response.read(4_000_001)
            if len(data) > 4_000_000:
                raise ValueError("webpage exceeds the 4 MB import limit")
            final_url = _public_web_url(response.geturl())
            charset = response.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise ValueError(f"webpage fetch failed: {error}") from error
    source = data.decode(charset, errors="replace")
    if content_type == "text/plain":
        return final_url, final_url, source[:2_000_000]
    try:
        title, text = _extract_static_webpage(source, final_url)
    except ImportError:
        title_match = re.search(r"(?is)<title[^>]*>(.*?)</title>", source)
        title = (
            re.sub(r"\s+", " ", title_match.group(1)).strip()
            if title_match
            else final_url
        )
        text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", source)
        text = re.sub(r"(?s)<[^>]+>", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise ValueError("webpage did not contain readable text")
    return final_url, title[:500], text[:2_000_000]


def create_knowledge_router(
    runtime_provider: PlatformRuntimeProvider,
    principal_provider: PrincipalProvider = resolve_request_principal,
) -> APIRouter:
    router = APIRouter(prefix="/knowledge", tags=["platform-knowledge"])
    principal_dependency = Depends(principal_provider)

    def store() -> KnowledgeStore | JSONResponse:
        runtime = runtime_provider()
        database = None if runtime is None else getattr(runtime, "database", None)
        if database is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Knowledge persistence is not ready.",
                retryable=True,
            )
        paths = None if runtime is None else getattr(runtime.config, "paths", None)
        blob_root = None if paths is None else paths.artifacts_path / "knowledge"
        active = None if runtime is None else getattr(runtime, "knowledge", None)
        return active or KnowledgeStore(database, blob_root=blob_root)

    def guarded(call):
        try:
            return call()
        except KnowledgeNotFoundError as error:
            return platform_error_response(
                status_code=404, code="not_found", message=str(error)
            )
        except KnowledgeAccessError as error:
            return platform_error_response(
                status_code=403, code="knowledge_access_denied", message=str(error)
            )
        except KnowledgeConflictError as error:
            return platform_error_response(
                status_code=409, code="knowledge_conflict", message=str(error)
            )
        except ValueError as error:
            return platform_error_response(
                status_code=422, code="knowledge_invalid", message=str(error)
            )

    def platform_runtime():
        return runtime_provider()

    async def acefox_webpage(
        url: str,
        principal: RequestPrincipal,
        *,
        auto_accept_cookies: bool,
    ) -> tuple[str, str, str, tuple[tuple[str, str], ...]]:
        runtime = platform_runtime()
        browser = None if runtime is None else getattr(runtime, "browser", None)
        if browser is None:
            raise BrowserError(
                "browser_unavailable", "AceFox WebAgent is not available."
            )
        validated_url = _public_web_url(url)
        status = await browser.get_status()
        initial_state = status.get("state")
        close_agent_after_read = initial_state in {
            BrowserControlState.STOPPED.value,
            BrowserControlState.USER_CONTROL.value,
        }
        import_tab_id: str | None = None
        if status.get("state") == BrowserControlState.USER_REQUIRED.value:
            await browser.begin_user_control()
            raise BrowserError(
                "knowledge_web_login_required",
                "Complete sign-in in AceFox, then choose Save and index again.",
            )
        if status.get("state") == BrowserControlState.USER_CONTROL.value:
            completion = await browser.complete_user_control()
            if not completion.get("completed"):
                raise BrowserError(
                    "knowledge_web_login_required",
                    "Complete sign-in in AceFox, then choose Save and index again.",
                )
        await browser.start(session_id=None, actor_user_id=principal.actor_user_id)
        if initial_state == BrowserControlState.AGENT_CONTROL.value:
            navigation = await browser.open_tab(
                session_id=None, url=validated_url
            )
            import_tab_id = str(navigation.get("opened_tab") or "") or None
        else:
            navigation = await browser.navigate(validated_url, session_id=None)
        if navigation.get("user_action_required"):
            await browser.begin_user_control()
            raise BrowserError(
                "knowledge_web_login_required",
                "Complete sign-in in AceFox, then choose Save and index again.",
            )
        await browser.wait_for(
            session_id=None,
            condition="page_stable",
            timeout_ms=12_000,
            stable_ms=800,
        )
        cookie_result: dict[str, Any] = {}
        if auto_accept_cookies:
            consent = await browser.accept_cookie_consent(
                session_id=None, policy="all"
            )
            cookie_result = dict(consent.get("cookie_consent") or {})
            if cookie_result.get("handled"):
                await browser.wait_for(
                    session_id=None,
                    condition="page_stable",
                    timeout_ms=8_000,
                    stable_ms=600,
                )
        result = await browser.read_article(
            session_id=None,
            output_format="markdown",
            mode="auto",
            include_images=False,
            include_links=True,
            max_chars=2_000_000,
            char_threshold=400,
            max_elements=100_000,
        )
        if result.get("user_action_required"):
            await browser.begin_user_control()
            raise BrowserError(
                "knowledge_web_login_required",
                "Complete sign-in in AceFox, then choose Save and index again.",
            )
        article = result.get("article") or {}
        text = str(article.get("content") or "").strip()
        if len(text) < 100:
            raise BrowserError(
                "article_not_found", "AceFox could not find readable page content."
            )
        final_url = _public_web_url(str(article.get("url") or validated_url))
        title = str(article.get("title") or final_url)[:500]
        facets = [
            ("source.fetch", "acefox"),
            (
                "source.extractor",
                str(article.get("extraction_method") or "readability"),
            ),
        ]
        if cookie_result.get("handled"):
            facets.append(("source.cookie_consent", "accepted"))
        if import_tab_id is not None:
            try:
                await browser.close_tab(import_tab_id, session_id=None)
            except BrowserError:
                pass
        elif close_agent_after_read:
            try:
                await browser.close()
            except BrowserError:
                pass
        return final_url, title, text[:2_000_000], tuple(facets)

    def ensure_ask_session(principal: RequestPrincipal):
        runtime = platform_runtime()
        database = None if runtime is None else getattr(runtime, "database", None)
        if database is None:
            raise RuntimeError("Knowledge persistence is not ready")
        events = getattr(runtime, "events", None) or EventStore(database)
        singleton_key = user_singleton_key(
            "ai2apps.knowledge", principal.actor_user_id, principal.client_scope
        )
        with database.transaction() as connection:
            definition = connection.execute(
                """
                SELECT * FROM app_definitions
                WHERE package_id='ai2apps.knowledge' AND status='enabled'
                ORDER BY created_at DESC LIMIT 1
                """
            ).fetchone()
            instance = connection.execute(
                "SELECT * FROM app_instances WHERE singleton_key=?",
                (singleton_key,),
            ).fetchone()
        if definition is None:
            raise RuntimeError("Knowledge App definition is not installed")
        if instance is None:
            try:
                created = AppRepository(database, events).create_instance(
                    app_definition_id=str(definition["id"]),
                    singleton_key=singleton_key,
                    owner_user_id=principal.actor_user_id,
                )
                instance_id = created.id
            except ResourceConflictError:
                with database.transaction() as connection:
                    row = connection.execute(
                        "SELECT id FROM app_instances WHERE singleton_key=?",
                        (singleton_key,),
                    ).fetchone()
                if row is None:
                    raise
                instance_id = str(row["id"])
        else:
            if instance["owner_user_id"] != principal.actor_user_id:
                raise KnowledgeAccessError(
                    "Knowledge Ask session is not owned by actor"
                )
            instance_id = str(instance["id"])
        with database.transaction() as connection:
            row = connection.execute(
                """
                SELECT id FROM sessions
                WHERE app_instance_id=? AND is_home=1 AND status='active'
                ORDER BY created_at LIMIT 1
                """,
                (instance_id,),
            ).fetchone()
        if row is not None:
            return database, events, instance_id, str(row["id"])
        session = SessionRepository(database, events).create(
            app_instance_id=instance_id,
            title="Knowledge Ask",
            is_home=True,
            metadata={"surface": "knowledge.ask", "schema": 1},
        )
        return database, events, instance_id, session.id

    @staticmethod
    def message_payload(record) -> dict[str, Any]:
        text_parts = []
        for part in record.parts:
            content = part.content
            if part.kind == "text" and isinstance(content, dict):
                text_parts.append(str(content.get("text") or ""))
        return {
            "id": record.message.id,
            "role": record.message.role.value,
            "content": "\n".join(value for value in text_parts if value),
            "metadata": record.message.metadata,
            "created_at": record.message.created_at.isoformat(),
        }

    @staticmethod
    def chat_message_text(message) -> tuple[str, tuple[str, ...]]:
        if message.role not in {MessageRole.USER, MessageRole.ASSISTANT}:
            return "", ()
        metadata = message.metadata if isinstance(message.metadata, dict) else {}
        if metadata.get("_ui") is False or metadata.get("hidden") is True:
            return "", ()
        content = message.content
        attachments: list[str] = []
        if isinstance(content, str):
            text = content
            text = re.sub(r"(?is)<think(?:ing)?\b[^>]*>.*?</think(?:ing)?>", "", text)
            return text.strip(), ()
        if not isinstance(content, list):
            return str(content or "").strip(), ()
        values = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                values.append(str(part.get("text") or ""))
            elif part.get("type") in {
                "reasoning",
                "thinking",
                "tool_call",
                "tool_result",
            }:
                continue
            elif part.get("type") == "file" and isinstance(part.get("file"), dict):
                file = part["file"]
                filename = str(file.get("filename") or "Attachment")
                values.append(f"[Attachment: {filename}]")
                if file.get("file_id"):
                    attachments.append(str(file["file_id"]))
            elif part.get("type") == "image_url":
                values.append("[Image attachment]")
        text = "\n".join(value for value in values if value)
        text = re.sub(r"(?is)<think(?:ing)?\b[^>]*>.*?</think(?:ing)?>", "", text)
        return text.strip(), tuple(attachments)

    def search_result(selected, principal, query, search_arguments):
        package_runtime = getattr(runtime_provider(), "knowledge_package_runtime", None)
        semantic_error = None
        retriever = None
        if package_runtime is not None:
            try:
                retriever = package_runtime.ready_retriever()
            except Exception as error:
                semantic_error = str(error)[:500]
        if retriever is None:
            result = guarded(
                lambda: selected.search(principal, query, **search_arguments)
            )
            retrieval = {"mode": "fts5", "semantic_error": semantic_error}
        else:
            result = guarded(
                lambda: retriever.search(principal, query, **search_arguments)
            )
            if not isinstance(result, JSONResponse):
                result, diagnostics = result
                retrieval = {
                    "mode": diagnostics.mode,
                    "profile_id": diagnostics.profile_id,
                    "lexical_candidates": diagnostics.lexical_candidates,
                    "semantic_candidates": diagnostics.semantic_candidates,
                    "semantic_error": diagnostics.semantic_error,
                }
            else:
                retrieval = {"mode": "fts5", "semantic_error": None}
        return (
            result
            if isinstance(result, JSONResponse)
            else {"items": list(result), "retrieval": retrieval}
        )

    @router.get("/spaces")
    def list_spaces(principal: RequestPrincipal = principal_dependency):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(lambda: selected.ensure_builtin_spaces(principal))
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.get("/buckets")
    def list_buckets(principal: RequestPrincipal = principal_dependency):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(lambda: selected.list_buckets(principal))
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.post("/buckets", status_code=201)
    def create_bucket(
        request: KnowledgeBucketCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.create_bucket(
                principal,
                name=request.name,
                scope=KnowledgeScope(request.scope),
                imported=request.imported,
            )
        )

    @router.delete("/buckets/{bucket_id}", status_code=204)
    def delete_bucket(
        bucket_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(lambda: selected.delete_bucket(principal, bucket_id))
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.get("/items")
    def list_items(
        scope: Literal["private", "installation"] | None = None,
        kind: str | None = None,
        bucket_id: str | None = Query(default=None, alias="bucketId"),
        limit: int = Query(default=100, ge=1, le=500),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.list_items(
                principal,
                scope=KnowledgeScope(scope) if scope else None,
                kind=kind,
                bucket_id=bucket_id,
                limit=limit,
            )
        )
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.post("/items", status_code=201)
    def create_item(
        request: KnowledgeItemCreateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.create_text_item(
                principal,
                scope=KnowledgeScope(request.scope),
                kind=request.kind,
                title=request.title,
                text=request.text,
                source_app_id=request.source_app_id,
                source_session_id=request.source_session_id,
                source_url=str(request.source_url) if request.source_url else None,
                user_tags=request.tags,
                bucket_id=request.bucket_id,
                trusted_source_facets=tuple(
                    value
                    for value in (
                        ("source.extractor", request.extraction_method),
                        ("source.capture", request.capture_mode),
                    )
                    if request.source_app_id == "ai2apps.browser-sidebar" and value[1]
                ),
            )
        )

    @router.patch("/items/{item_id}")
    def update_item(
        item_id: str,
        request: KnowledgeItemUpdateRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.update_text_item(
                principal,
                item_id,
                expected_revision=request.revision,
                title=request.title,
                text=request.text,
                trusted_source_facets=tuple(
                    value
                    for value in (
                        ("source.extractor", request.extraction_method),
                        ("source.capture", request.capture_mode),
                    )
                    if value[1]
                ),
            )
        )

    @router.get("/items/by-source")
    def items_by_source(
        url: HttpUrl,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        records = guarded(
            lambda: selected.items_by_source_url(principal, str(url))
        )
        if isinstance(records, JSONResponse):
            return records
        return {
            "items": [
                {
                    "item": item,
                    "bucket_ids": list(selected.bucket_ids_for_item(principal, item.id)),
                    "source_facets": [
                        {"key": key, "value": value}
                        for key, value in selected.source_facets(principal, item.id)
                    ],
                }
                for item in records
            ]
        }

    @router.post("/items/import", status_code=201)
    def import_item(
        file: Annotated[UploadFile, File()],
        bucket_id: Annotated[str, Form(alias="bucketId")],
        source_app_id: Annotated[str | None, Form(alias="sourceAppId")] = None,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.import_stream(
                principal,
                file.file,
                name=file.filename or "Untitled",
                media_type=file.content_type,
                bucket_id=bucket_id,
                source_app_id=source_app_id,
                max_bytes=DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES,
            )
        )
        if isinstance(result, JSONResponse):
            return result
        item, asset = result
        return {"item": item, "asset": asset}

    @router.post("/items/import-batch", status_code=202)
    def import_item_batch(
        files: Annotated[list[UploadFile], File()],
        bucket_id: Annotated[str, Form(alias="bucketId")],
        source_app_id: Annotated[str | None, Form(alias="sourceAppId")] = None,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        if not files or len(files) > 500:
            return platform_error_response(
                status_code=422,
                code="knowledge_invalid_import_batch",
                message="An import batch requires between 1 and 500 files.",
            )
        job = guarded(
            lambda: selected.create_import_job(
                principal,
                bucket_id=bucket_id,
                filenames=[file.filename or "Untitled" for file in files],
                source_app_id=source_app_id,
            )
        )
        if isinstance(job, JSONResponse):
            return job
        for ordinal, file in enumerate(files):
            try:
                selected.stage_import_entry(
                    principal,
                    str(job["id"]),
                    ordinal,
                    file.file,
                    media_type=file.content_type,
                    max_bytes=DEFAULT_RESOURCE_IMPORT_LIMIT_BYTES,
                )
            except Exception as error:
                selected.update_import_entry(
                    principal,
                    str(job["id"]),
                    ordinal,
                    status="failed",
                    error=str(error),
                )
        manager = getattr(platform_runtime(), "knowledge_import_manager", None)
        scheduled = bool(manager and manager.enqueue(str(job["id"])))
        if manager is None:
            selected.process_import_job(str(job["id"]))
        return {
            "job": selected.get_import_job(principal, str(job["id"])),
            "accepted": True,
            "scheduled": scheduled,
        }

    @router.get("/imports")
    def list_imports(
        limit: int = Query(default=20, ge=1, le=100),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(lambda: selected.list_import_jobs(principal, limit=limit))
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.get("/imports/{job_id}")
    def get_import(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: selected.get_import_job(principal, job_id))

    @router.post("/imports/{job_id}/retry", status_code=202)
    def retry_import(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        job = guarded(lambda: selected.retry_import_job(principal, job_id))
        if isinstance(job, JSONResponse):
            return job
        manager = getattr(platform_runtime(), "knowledge_import_manager", None)
        scheduled = bool(manager and manager.enqueue(job_id))
        if manager is None:
            selected.process_import_job(job_id)
        return {
            "accepted": True,
            "scheduled": scheduled,
            "job": selected.get_import_job(principal, job_id),
        }

    def control_import(
        job_id: str, action: Literal["pause", "resume", "cancel"], principal: RequestPrincipal
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        job = guarded(
            lambda: selected.control_import_job(principal, job_id, action=action)
        )
        if isinstance(job, JSONResponse):
            return job
        scheduled = False
        if action == "resume":
            manager = getattr(platform_runtime(), "knowledge_import_manager", None)
            scheduled = bool(manager and manager.enqueue(job_id))
            if manager is None:
                selected.process_import_job(job_id)
                job = selected.get_import_job(principal, job_id)
        return {"accepted": True, "scheduled": scheduled, "job": job}

    @router.post("/imports/{job_id}/pause", status_code=202)
    def pause_import(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        return control_import(job_id, "pause", principal)

    @router.post("/imports/{job_id}/resume", status_code=202)
    def resume_import(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        return control_import(job_id, "resume", principal)

    @router.post("/imports/{job_id}/cancel", status_code=202)
    def cancel_import(
        job_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        return control_import(job_id, "cancel", principal)

    @router.get("/tag-suggestions")
    def list_tag_suggestions(
        item_id: str | None = Query(default=None, alias="itemId"),
        bucket_id: str | None = Query(default=None, alias="bucketId"),
        status: Literal["suggested", "confirmed", "rejected"] = "suggested",
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.list_tag_suggestions(
                principal, item_id=item_id, bucket_id=bucket_id, status=status
            )
        )
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.get("/item-tags")
    def list_item_tags(
        bucket_id: str = Query(alias="bucketId"),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.list_item_tags(principal, bucket_id=bucket_id)
        )
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.post("/items/{item_id}/tag-suggestions")
    def suggest_item_tags(
        item_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(lambda: selected.suggest_tags(principal, item_id))
        return result if isinstance(result, JSONResponse) else {"items": list(result)}

    @router.post("/tag-suggestions/{suggestion_id}/confirm")
    def confirm_tag_suggestion(
        suggestion_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.decide_tag_suggestion(
                principal, suggestion_id, decision="confirm"
            )
        )

    @router.post("/tag-suggestions/{suggestion_id}/reject")
    def reject_tag_suggestion(
        suggestion_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(
            lambda: selected.decide_tag_suggestion(
                principal, suggestion_id, decision="reject"
            )
        )

    @router.get("/items/{item_id}")
    def get_item(
        item_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        return guarded(lambda: selected.get_item(principal, item_id))

    @router.get("/items/{item_id}/source")
    def item_source(
        item_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        item = guarded(lambda: selected.get_item(principal, item_id))
        if isinstance(item, JSONResponse):
            return item
        facets = guarded(lambda: selected.source_facets(principal, item_id))
        if isinstance(facets, JSONResponse):
            return facets
        facet_map: dict[str, list[str]] = {}
        for key, value in facets:
            facet_map.setdefault(key, []).append(value)
        if item.source_url:
            return {"kind": "webpage", "url": item.source_url, "item_id": item.id}
        if item.source_session_id:
            return {
                "kind": "chat",
                "app_id": item.source_app_id,
                "session_id": item.source_session_id,
                "message_start": (facet_map.get("source.message.start") or [None])[0],
                "message_end": (facet_map.get("source.message.end") or [None])[0],
                "item_id": item.id,
            }
        try:
            selected.asset_path(principal, item_id)
        except KnowledgeNotFoundError:
            return {"kind": "knowledge", "item_id": item.id}
        return {
            "kind": "file",
            "url": f"/v1/platform/knowledge/items/{item.id}/content",
            "item_id": item.id,
        }

    @router.post("/items/web", status_code=201)
    async def import_webpage(
        request: KnowledgeWebImportRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        buckets = guarded(lambda: selected.list_buckets(principal))
        if isinstance(buckets, JSONResponse):
            return buckets
        bucket = next((item for item in buckets if item.id == request.bucket_id), None)
        if bucket is None:
            return platform_error_response(
                status_code=404, code="not_found", message="knowledge bucket not found"
            )
        static_result: tuple[str, str, str] | None = None
        static_error: ValueError | None = None
        if request.fetch_mode != "acefox":
            try:
                static_result = await asyncio.to_thread(
                    _fetch_webpage, str(request.url)
                )
            except ValueError as error:
                static_error = error
            if request.fetch_mode == "static" and static_result is None:
                return platform_error_response(
                    status_code=422,
                    code="knowledge_web_import_failed",
                    message=str(static_error or "static webpage fetch failed"),
                )
        use_acefox = request.fetch_mode == "acefox" or (
            request.fetch_mode == "auto"
            and (
                static_result is None
                or not _web_content_sufficient(static_result[2])
            )
        )
        try:
            if use_acefox:
                final_url, fetched_title, text, source_facets = await acefox_webpage(
                    str(request.url),
                    principal,
                    auto_accept_cookies=request.auto_accept_cookies,
                )
            else:
                assert static_result is not None
                final_url, fetched_title, text = static_result
                source_facets = (
                    ("source.fetch", "server"),
                    ("source.extractor", "readability-static"),
                )
        except BrowserError as error:
            retryable = error.code in {
                "browser_unavailable",
                "helper_unavailable",
                "knowledge_web_login_required",
            }
            details: dict[str, Any] = {}
            if error.code == "knowledge_web_login_required":
                runtime = platform_runtime()
                try:
                    await runtime.browser.close()
                except (AttributeError, BrowserError):
                    pass

                def complete_managed_import(article: dict[str, Any]) -> str:
                    item = selected.create_text_item(
                        principal,
                        scope=bucket.visibility,
                        kind="webpage",
                        title=request.title or str(article["title"])[:500],
                        text=str(article["text"])[:2_000_000],
                        source_app_id="ai2apps.knowledge",
                        source_url=_public_web_url(str(article["url"])),
                        user_tags=request.tags,
                        bucket_id=bucket.id,
                        trusted_source_facets=(
                            ("source.fetch", "managed-browser"),
                            (
                                "source.extractor",
                                str(article.get("extraction_method") or "readability"),
                            ),
                            ("source.user_assisted", "true"),
                        ),
                    )
                    return item.id

                details["managed_request_id"] = managed_browser_broker.enqueue(
                    url=str(request.url),
                    actor_user_id=principal.actor_user_id,
                    complete=complete_managed_import,
                )
            return platform_error_response(
                status_code=(
                    409
                    if error.code == "knowledge_web_login_required"
                    else 503
                    if retryable
                    else 422
                ),
                code=error.code,
                message=str(error),
                retryable=retryable,
                details=details,
            )
        return guarded(
            lambda: selected.create_text_item(
                principal,
                scope=bucket.visibility,
                kind="webpage",
                title=request.title or fetched_title,
                text=text,
                source_app_id="ai2apps.knowledge",
                source_url=final_url,
                user_tags=request.tags,
                bucket_id=bucket.id,
                trusted_source_facets=source_facets,
            )
        )

    @router.get("/web-imports/{request_id}")
    async def managed_web_import_status(
        request_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        try:
            return managed_browser_broker.status(request_id, principal.actor_user_id)
        except KeyError:
            return platform_error_response(
                status_code=404,
                code="not_found",
                message="managed webpage import not found",
            )

    @router.post("/items/chat", status_code=201)
    def import_chat_selection(
        request: KnowledgeChatImportRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        runtime = platform_runtime()
        if runtime is None or getattr(runtime, "database", None) is None:
            return platform_error_response(
                status_code=503,
                code="platform_not_ready",
                message="Chat persistence is not ready.",
                retryable=True,
            )
        try:
            content = ChatRepository(
                runtime.database, runtime.events, principal=principal
            ).get_content(request.session_id)
        except Exception as error:
            return platform_error_response(
                status_code=404, code="chat_not_found", message=str(error)
            )
        if request.end_index < request.start_index or request.end_index >= len(
            content.messages
        ):
            return platform_error_response(
                status_code=422,
                code="knowledge_invalid_chat_range",
                message="Chat message range is invalid.",
            )
        buckets = selected.list_buckets(principal)
        bucket = next((item for item in buckets if item.id == request.bucket_id), None)
        if bucket is None:
            return platform_error_response(
                status_code=404, code="not_found", message="knowledge bucket not found"
            )
        rendered = []
        content_values = []
        attachment_ids = []
        authenticated_artifact_ids = []
        selected_messages = content.messages[
            request.start_index : request.end_index + 1
        ]
        for message in selected_messages:
            value, attachments = chat_message_text(message)
            attachment_ids.extend(attachments)
            metadata = message.metadata if isinstance(message.metadata, dict) else {}
            if metadata.get("artifact_id"):
                authenticated_artifact_ids.append(str(metadata["artifact_id"]))
            image_generation = (
                metadata.get("meta", {}).get("image_generation", {})
                if isinstance(metadata.get("meta"), dict)
                else {}
            )
            if isinstance(image_generation, dict) and image_generation.get(
                "artifact_id"
            ):
                authenticated_artifact_ids.append(str(image_generation["artifact_id"]))
            if isinstance(metadata.get("artifact_ids"), list):
                authenticated_artifact_ids.extend(
                    str(value) for value in metadata["artifact_ids"] if value
                )
            if value:
                rendered.append(f"{message.role.value.title()}: {value}")
                content_values.append(value)
        text = "\n\n".join(rendered).strip()
        if not text:
            return platform_error_response(
                status_code=422,
                code="knowledge_empty_chat_selection",
                message="Selected Chat messages do not contain saveable content.",
            )
        source_facets = [
            ("source.message.start", str(request.start_index)),
            ("source.message.end", str(request.end_index)),
        ]
        if request.artifact_ids:
            requested_artifacts = tuple(dict.fromkeys(request.artifact_ids))
            if not set(requested_artifacts).issubset(set(authenticated_artifact_ids)):
                return platform_error_response(
                    status_code=422,
                    code="knowledge_invalid_chat_artifact",
                    message="Artifact is not attached to the authenticated Chat range.",
                )
            workspace = getattr(runtime, "workspace", None)
            if workspace is None:
                return platform_error_response(
                    status_code=503,
                    code="workspace_runtime_not_ready",
                    message="Workspace artifacts are not ready.",
                    retryable=True,
                )
            imported_artifacts = []
            for artifact_id in requested_artifacts:
                try:
                    artifact = workspace.get_artifact(request.session_id, artifact_id)
                    path = workspace.artifact_path(artifact)
                    with path.open("rb") as stream:
                        artifact_item, _asset = selected.import_stream(
                            principal,
                            stream,
                            name=artifact.name,
                            media_type=artifact.media_type,
                            bucket_id=bucket.id,
                            source_app_id="ai2apps.general-chat",
                            source_session_id=request.session_id,
                            trusted_source_facets=tuple(
                                source_facets
                                + [
                                    ("source.selection", "artifact"),
                                    ("source.artifact", artifact.id),
                                ]
                            ),
                        )
                    imported_artifacts.append(artifact_item)
                except Exception as error:
                    return platform_error_response(
                        status_code=422,
                        code="knowledge_artifact_import_failed",
                        message=str(error),
                    )
            return {
                "item": imported_artifacts[0],
                "artifacts": imported_artifacts,
                "attachments": [],
            }
        if request.selection_text:
            selection = request.selection_text.strip()
            normalized_selection = re.sub(r"\s+", " ", selection)
            normalized_content = re.sub(r"\s+", " ", "\n\n".join(content_values))
            if not selection or normalized_selection not in normalized_content:
                return platform_error_response(
                    status_code=422,
                    code="knowledge_invalid_chat_selection",
                    message="Selected text is not present in the authenticated Chat range.",
                )
            text = selection
            source_facets.append(("source.selection", "text"))
        if request.link_url is not None:
            requested_url = _public_web_url(str(request.link_url))
            authenticated_urls = set()
            for candidate in re.findall(
                r"https?://[^\s<>\"']+", "\n".join(content_values)
            ):
                try:
                    authenticated_urls.add(_public_web_url(candidate.rstrip(".,);]")))
                except ValueError:
                    continue
            if requested_url not in authenticated_urls:
                return platform_error_response(
                    status_code=422,
                    code="knowledge_invalid_chat_link",
                    message="Link is not present in the authenticated Chat range.",
                )
            try:
                final_url, fetched_title, webpage_text = _fetch_webpage(requested_url)
            except ValueError as error:
                return platform_error_response(
                    status_code=422,
                    code="knowledge_web_import_failed",
                    message=str(error),
                )
            source_facets.append(("source.selection", "link"))
            item = guarded(
                lambda: selected.create_text_item(
                    principal,
                    scope=bucket.visibility,
                    kind="webpage",
                    title=request.title or fetched_title,
                    text=webpage_text,
                    source_app_id="ai2apps.general-chat",
                    source_session_id=request.session_id,
                    source_url=final_url,
                    user_tags=request.tags,
                    bucket_id=bucket.id,
                    trusted_source_facets=tuple(source_facets),
                )
            )
            return (
                item
                if isinstance(item, JSONResponse)
                else {"item": item, "attachments": []}
            )
        item = guarded(
            lambda: selected.create_text_item(
                principal,
                scope=bucket.visibility,
                kind="chat",
                title=request.title or content.thread.session.title or "Chat excerpt",
                text=text,
                source_app_id="ai2apps.general-chat",
                source_session_id=request.session_id,
                user_tags=request.tags,
                bucket_id=bucket.id,
                trusted_source_facets=tuple(source_facets),
            )
        )
        if isinstance(item, JSONResponse):
            return item
        imported_attachments = []
        documents = getattr(runtime, "documents", None)
        if request.include_attachments and documents is not None:
            for attachment_id in dict.fromkeys(attachment_ids):
                try:
                    attachment = documents.get(request.session_id, attachment_id)
                    digest = attachment.sha256
                    path = documents.root / f"{digest[:2]}/{digest[2:4]}/{digest}"
                    with path.open("rb") as stream:
                        attachment_item, _asset = selected.import_stream(
                            principal,
                            stream,
                            name=attachment.filename,
                            media_type=attachment.media_type,
                            bucket_id=bucket.id,
                            source_app_id="ai2apps.general-chat",
                            source_session_id=request.session_id,
                            trusted_source_facets=(
                                ("source.selection", "attachment"),
                                ("source.message.start", str(request.start_index)),
                                ("source.message.end", str(request.end_index)),
                            ),
                        )
                    imported_attachments.append(attachment_item)
                except Exception:
                    continue
        return {"item": item, "attachments": imported_attachments}

    @router.delete("/items/{item_id}", status_code=204)
    def delete_item(
        item_id: str,
        revision: int = Query(ge=1),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.delete_item(principal, item_id, expected_revision=revision)
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.get("/items/{item_id}/content")
    def item_content(
        item_id: str,
        download: bool = False,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(lambda: selected.asset_path(principal, item_id))
        if isinstance(result, JSONResponse):
            return result
        asset, path = result
        return FileResponse(
            path,
            media_type=asset.media_type,
            filename=asset.filename if download else None,
            content_disposition_type="attachment" if download else "inline",
            headers={"ETag": asset.content_hash, "X-Content-Type-Options": "nosniff"},
        )

    @router.post("/buckets/{bucket_id}/items/{item_id}", status_code=204)
    def add_to_bucket(
        bucket_id: str,
        item_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.add_item_to_bucket(principal, bucket_id, item_id)
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.delete("/buckets/{bucket_id}/items/{item_id}", status_code=204)
    def remove_from_bucket(
        bucket_id: str,
        item_id: str,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.remove_item_from_bucket(principal, bucket_id, item_id)
        )
        return result if isinstance(result, JSONResponse) else Response(status_code=204)

    @router.post("/search")
    def search(
        request: KnowledgeSearchRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        search_arguments = {
            "scope": KnowledgeScope(request.scope) if request.scope else None,
            "kind": request.kind,
            "tags": request.tags,
            "bucket_ids": request.bucket_ids,
            "source_app_id": request.source_app_id,
            "source_session_id": request.source_session_id,
            "source_after": request.source_after,
            "source_before": request.source_before,
            "limit": request.limit,
        }
        return search_result(selected, principal, request.query, search_arguments)

    @router.get("/index/status")
    def index_status(principal: RequestPrincipal = principal_dependency):
        del principal
        runtime = runtime_provider()
        package_runtime = getattr(runtime, "knowledge_package_runtime", None)
        if package_runtime is None:
            return {"status": "disabled", "retryable": False}
        status = package_runtime.status()
        return {
            "profile_id": status.profile_id,
            "generation": status.generation,
            "sequence": status.sequence,
            "target_sequence": status.target_sequence,
            "status": status.status,
            "processed_changes": status.processed_changes,
            "indexed_chunks": status.indexed_chunks,
            "last_error": status.last_error,
            "started_at": status.started_at,
            "completed_at": status.completed_at,
            "updated_at": status.updated_at,
            "retryable": status.status == "error",
        }

    @router.post("/index/retry", status_code=202)
    def retry_index(principal: RequestPrincipal = principal_dependency):
        del principal
        runtime = runtime_provider()
        package_runtime = getattr(runtime, "knowledge_package_runtime", None)
        if package_runtime is None:
            return platform_error_response(
                status_code=503,
                code="knowledge_runtime_unavailable",
                message="Knowledge semantic runtime is not installed.",
                retryable=True,
            )
        started = package_runtime.retry()
        return {"accepted": True, "started": started}

    @router.post("/index/rebuild", status_code=202)
    def rebuild_index(principal: RequestPrincipal = principal_dependency):
        del principal
        runtime = runtime_provider()
        package_runtime = getattr(runtime, "knowledge_package_runtime", None)
        if package_runtime is None:
            return platform_error_response(
                status_code=503,
                code="knowledge_runtime_unavailable",
                message="Knowledge semantic runtime is not installed.",
                retryable=True,
            )
        started = package_runtime.rebuild()
        return {"accepted": True, "started": started}

    @router.get("/ask")
    def get_ask(principal: RequestPrincipal = principal_dependency):
        try:
            database, events, _instance_id, session_id = ensure_ask_session(principal)
            records = MessageRepository(database, events).list_for_session(
                session_id, limit=500
            )
        except Exception as error:
            return platform_error_response(
                status_code=503,
                code="knowledge_ask_unavailable",
                message=str(error),
                retryable=True,
            )
        return {
            "session_id": session_id,
            "messages": [message_payload(record) for record in records],
        }

    @router.post("/ask", status_code=201)
    def save_ask(
        request: KnowledgeAskSaveRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        try:
            visible_bucket_ids = {
                bucket.id for bucket in selected.list_buckets(principal)
            }
            if not set(request.bucket_ids).issubset(visible_bucket_ids):
                raise KnowledgeAccessError("Knowledge Ask bucket is not visible")
            canonical_citations = []
            seen_markers = set()
            answer_markers = set(re.findall(r"\[(K[1-9]\d{0,2})\]", request.answer))
            for citation in request.citations:
                marker = str(citation.get("marker") or "")
                item_id = str(citation.get("item_id") or "")
                if not re.fullmatch(r"K[1-9]\d{0,2}", marker) or marker in seen_markers:
                    raise ValueError("Knowledge Ask citation marker is invalid")
                if marker not in answer_markers:
                    raise ValueError(
                        "Knowledge Ask answer does not reference its citation"
                    )
                item = selected.get_item(principal, item_id)
                item_buckets = set(selected.bucket_ids_for_item(principal, item.id))
                if request.bucket_ids and item_buckets.isdisjoint(request.bucket_ids):
                    raise KnowledgeAccessError(
                        "Knowledge Ask citation is outside the selected buckets"
                    )
                location = citation.get("location")
                if not isinstance(location, dict):
                    location = None
                if location:
                    allowed_location_keys = {
                        "kind",
                        "page",
                        "section",
                        "sheet",
                        "slide",
                        "cell_range",
                    }
                    if not set(location).issubset(allowed_location_keys):
                        raise ValueError("Knowledge Ask citation location is invalid")
                    known_locations = selected.chunk_locations_for_item(
                        principal, item.id
                    )
                    if not any(
                        all(
                            candidate.get(key) == value
                            for key, value in location.items()
                        )
                        for candidate in known_locations
                    ):
                        raise ValueError(
                            "Knowledge Ask citation location is not authoritative"
                        )
                canonical_citations.append(
                    {
                        "marker": marker,
                        "uri": f"knowledge://item/{item.id}",
                        "item_id": item.id,
                        "revision": item.revision,
                        "title": item.title,
                        "source_url": item.source_url,
                        "location": location,
                    }
                )
                seen_markers.add(marker)
            if answer_markers != seen_markers:
                raise ValueError(
                    "Knowledge Ask answer contains an unknown citation marker"
                )
            database, events, instance_id, session_id = ensure_ask_session(principal)
            messages = MessageRepository(database, events)
            user = messages.append(
                session_id=session_id,
                app_instance_id=instance_id,
                role=MessageRole.USER,
                parts=(
                    MessagePartInput(kind="text", content={"text": request.question}),
                ),
                idempotency_key=f"knowledge-ask:{request.request_id}:user",
                metadata={
                    "surface": "knowledge.ask",
                    "bucket_ids": request.bucket_ids,
                },
            ).value
            assistant = messages.append(
                session_id=session_id,
                app_instance_id=instance_id,
                role=MessageRole.ASSISTANT,
                parts=(
                    MessagePartInput(kind="text", content={"text": request.answer}),
                ),
                idempotency_key=f"knowledge-ask:{request.request_id}:assistant",
                metadata={
                    "surface": "knowledge.ask",
                    "model": request.model,
                    "bucket_ids": request.bucket_ids,
                    "citations": canonical_citations,
                    "retrieval": request.retrieval,
                },
            ).value
        except KnowledgeNotFoundError as error:
            return platform_error_response(
                status_code=404,
                code="knowledge_ask_citation_not_found",
                message=str(error),
            )
        except KnowledgeAccessError as error:
            return platform_error_response(
                status_code=403,
                code="knowledge_ask_citation_denied",
                message=str(error),
            )
        except ValueError as error:
            return platform_error_response(
                status_code=422,
                code="knowledge_ask_citation_invalid",
                message=str(error),
            )
        except Exception as error:
            return platform_error_response(
                status_code=409,
                code="knowledge_ask_save_failed",
                message=str(error),
            )
        return {
            "session_id": session_id,
            "messages": [message_payload(user), message_payload(assistant)],
        }

    @router.get("/contexts/{consumer_app_id}")
    def get_context(
        consumer_app_id: str,
        session_id: str | None = Query(default=None, alias="sessionId"),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.context_buckets(
                principal, consumer_app_id, session_id=session_id
            )
        )
        if isinstance(result, JSONResponse):
            return result
        response: dict[str, object] = {"bucket_ids": list(result)}
        if session_id is not None:
            response["session_id"] = session_id
        return response

    @router.put("/contexts/{consumer_app_id}")
    def set_context(
        consumer_app_id: str,
        request: KnowledgeContextRequest,
        session_id: str | None = Query(default=None, alias="sessionId"),
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        result = guarded(
            lambda: selected.set_context_buckets(
                principal,
                consumer_app_id,
                request.bucket_ids,
                session_id=session_id,
            )
        )
        if isinstance(result, JSONResponse):
            return result
        response: dict[str, object] = {"bucket_ids": list(result)}
        if session_id is not None:
            response["session_id"] = session_id
        return response

    @router.post("/contexts/{consumer_app_id}/search")
    def search_context(
        consumer_app_id: str,
        request: KnowledgeContextSearchRequest,
        principal: RequestPrincipal = principal_dependency,
    ):
        selected = store()
        if isinstance(selected, JSONResponse):
            return selected
        bucket_ids = guarded(
            lambda: selected.context_buckets(
                principal,
                consumer_app_id,
                session_id=request.session_id,
            )
        )
        if isinstance(bucket_ids, JSONResponse):
            return bucket_ids
        if not bucket_ids:
            return {
                "items": [],
                "bucket_ids": [],
                "retrieval": {"mode": "disabled", "semantic_error": None},
            }
        result = search_result(
            selected,
            principal,
            request.query,
            {"bucket_ids": bucket_ids, "limit": request.limit},
        )
        if isinstance(result, dict):
            result["bucket_ids"] = list(bucket_ids)
        return result

    return router
