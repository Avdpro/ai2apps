"""Register Knowledge Core as first-party Tools shared by Apps and Agents."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ai2apps.core import parse_utc
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.services import (
    ServiceInstanceStatus,
    ServiceRegistry,
    ServiceRepository,
    ServiceRuntimeMode,
    ToolCallContext,
    ToolProviderError,
)

from .models import KnowledgeItem, KnowledgeScope, KnowledgeSearchHit
from .store import KnowledgeError, KnowledgeStore

if TYPE_CHECKING:
    from .retrieval import HybridKnowledgeRetriever


def _principal(context: ToolCallContext) -> RequestPrincipal:
    if context.actor_user_id is None or context.installation_id is None:
        raise ToolProviderError(
            "Knowledge Tools require an authenticated actor and installation"
        )
    return RequestPrincipal(
        actor_user_id=context.actor_user_id,
        installation_id=context.installation_id,
        organization_id=context.organization_id or "local",
        billing_account_id=context.billing_account_id or "local",
        role=MemberRole.MEMBER,
        membership_epoch=context.membership_epoch or 1,
    )


def _item_json(item: KnowledgeItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "space_id": item.space_id,
        "visibility": item.visibility.value,
        "kind": item.kind,
        "title": item.title,
        "text": item.text,
        "source_time": item.source_time.isoformat() if item.source_time else None,
        "source_app_id": item.source_app_id,
        "source_session_id": item.source_session_id,
        "source_url": item.source_url,
        "status": item.status,
        "revision": item.revision,
        "created_at": item.created_at.isoformat(),
        "updated_at": item.updated_at.isoformat(),
        "citation": {
            "uri": f"knowledge://item/{item.id}",
            "item_id": item.id,
            "revision": item.revision,
            "title": item.title,
        },
    }


def _hit_json(hit: KnowledgeSearchHit) -> dict[str, Any]:
    item = _item_json(hit.item)
    if hit.location:
        item["citation"]["location"] = hit.location
    return {
        "item": item,
        "excerpt": hit.excerpt,
        "rank": hit.rank,
        "tags": [tag.display_name for tag in hit.tags],
        "source_facets": [
            {"key": key, "value": value} for key, value in hit.source_facets
        ],
        "location": hit.location,
    }


def install_knowledge_service(
    store: KnowledgeStore,
    repository: ServiceRepository,
    registry: ServiceRegistry,
    *,
    retriever: HybridKnowledgeRetriever | None = None,
    retriever_provider: Callable[[], HybridKnowledgeRetriever] | None = None,
) -> None:
    """Expose one authority through stable Tool contracts, not backend internals."""

    service = repository.ensure_service(
        service_key="ai2apps.knowledge-service",
        package_id="ai2apps.knowledge",
        package_version="0.1.0",
        display_name="AI2Apps Knowledge Core",
        runtime_mode=ServiceRuntimeMode.IN_PROCESS,
        capabilities=("knowledge.ingest", "knowledge.search", "knowledge.manage"),
        config={"authority": "platform-sqlite", "retrieval": "fts5"},
    )
    instance = repository.ensure_instance(
        service_id=service.id,
        provider_key="builtin:knowledge-core",
        status=ServiceInstanceStatus.RUNNING,
        endpoint="/v1/platform/knowledge",
        health={"status": "ok", "retrieval": "fts5"},
    )

    async def invoke(operation, *args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except (KnowledgeError, ValueError) as error:
            raise ToolProviderError(str(error)) from error

    async def search(arguments: dict[str, Any], context: ToolCallContext):
        principal = _principal(context)
        bucket_ids = tuple(arguments.get("bucket_ids", ()))
        if not bucket_ids:
            consumer_app_id = context.caller_id
            if context.session_id is not None:
                with store.transaction() as connection:
                    row = connection.execute(
                        """
                        SELECT d.package_id FROM sessions s
                        JOIN app_instances i ON i.id=s.app_instance_id
                        JOIN app_definitions d ON d.id=i.app_definition_id
                        WHERE s.id=?
                        """,
                        (context.session_id,),
                    ).fetchone()
                if row is not None:
                    consumer_app_id = row["package_id"]
            bucket_ids = store.context_buckets(
                principal,
                consumer_app_id,
                session_id=context.session_id,
            )
        search_arguments = {
            "scope": (
                KnowledgeScope(arguments["scope"]) if arguments.get("scope") else None
            ),
            "kind": arguments.get("kind"),
            "tags": arguments.get("tags", ()),
            "bucket_ids": bucket_ids,
            "source_app_id": arguments.get("source_app_id"),
            "source_session_id": arguments.get("source_session_id"),
            "source_after": (
                parse_utc(arguments["source_after"])
                if arguments.get("source_after")
                else None
            ),
            "source_before": (
                parse_utc(arguments["source_before"])
                if arguments.get("source_before")
                else None
            ),
            "limit": arguments.get("limit", 20),
        }
        active_retriever = retriever
        if active_retriever is None and retriever_provider is not None:
            try:
                active_retriever = retriever_provider()
            except Exception:
                # Semantic indexing is optional and disposable. Never let a
                # missing/broken Package take down authoritative FTS search.
                active_retriever = None
        if active_retriever is None:
            hits = await invoke(
                store.search,
                principal,
                arguments["query"],
                **search_arguments,
            )
            retrieval = {"mode": "fts5"}
        else:
            hits, diagnostics = await invoke(
                active_retriever.search,
                principal,
                arguments["query"],
                **search_arguments,
            )
            retrieval = {
                "profile_id": diagnostics.profile_id,
                "mode": diagnostics.mode,
                "lexical_candidates": diagnostics.lexical_candidates,
                "semantic_candidates": diagnostics.semantic_candidates,
                "semantic_error": diagnostics.semantic_error,
            }
        return {
            "items": [_hit_json(hit) for hit in hits],
            "query": arguments["query"],
            "retrieval": retrieval,
        }

    async def get(arguments: dict[str, Any], context: ToolCallContext):
        item = await invoke(store.get_item, _principal(context), arguments["item_id"])
        return _item_json(item)

    async def add(arguments: dict[str, Any], context: ToolCallContext):
        item = await invoke(
            store.create_text_item,
            _principal(context),
            scope=KnowledgeScope(arguments.get("scope", "private")),
            kind=arguments.get("kind", "note"),
            title=arguments["title"],
            text=arguments["text"],
            source_app_id=context.caller_id,
            source_session_id=context.session_id,
            source_url=arguments.get("source_url"),
            user_tags=arguments.get("tags", ()),
        )
        return _item_json(item)

    async def delete(arguments: dict[str, Any], context: ToolCallContext):
        await invoke(
            store.delete_item,
            _principal(context),
            arguments["item_id"],
            expected_revision=arguments["revision"],
        )
        return {"deleted": True, "item_id": arguments["item_id"]}

    definitions = (
        (
            "knowledge.search",
            "Search local knowledge",
            "Search the authenticated user's private and Local shared knowledge. Return bounded excerpts and stable citations; use knowledge.get only when full saved text is needed.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "minLength": 1, "maxLength": 4000},
                    "scope": {"enum": ["private", "installation"]},
                    "kind": {
                        "enum": [
                            "webpage",
                            "document",
                            "image",
                            "audio",
                            "video",
                            "chat",
                            "artifact",
                            "note",
                        ]
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 100},
                        "maxItems": 50,
                    },
                    "bucket_ids": {
                        "type": "array",
                        "items": {"type": "string", "minLength": 1},
                        "maxItems": 100,
                    },
                    "source_app_id": {"type": "string", "maxLength": 255},
                    "source_session_id": {"type": "string", "maxLength": 255},
                    "source_after": {"type": "string", "format": "date-time"},
                    "source_before": {"type": "string", "format": "date-time"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
            (),
            (),
            search,
        ),
        (
            "knowledge.get",
            "Read saved knowledge",
            "Read one visible Knowledge item by stable ID and return its citation identity.",
            {
                "type": "object",
                "properties": {"item_id": {"type": "string", "minLength": 1}},
                "required": ["item_id"],
                "additionalProperties": False,
            },
            (),
            (),
            get,
        ),
        (
            "knowledge.add_text",
            "Save text to Knowledge",
            "Save user-approved text in the system Knowledge Core. Defaults to Private and records the calling App or Agent as the trusted source.",
            {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "minLength": 1, "maxLength": 500},
                    "text": {"type": "string", "minLength": 1, "maxLength": 2000000},
                    "scope": {"enum": ["private", "installation"]},
                    "kind": {
                        "enum": ["webpage", "document", "chat", "artifact", "note"]
                    },
                    "source_url": {
                        "type": "string",
                        "format": "uri",
                        "maxLength": 8192,
                    },
                    "tags": {
                        "type": "array",
                        "items": {"type": "string", "maxLength": 100},
                        "maxItems": 50,
                    },
                },
                "required": ["title", "text"],
                "additionalProperties": False,
            },
            ("write",),
            ("knowledge.write",),
            add,
        ),
        (
            "knowledge.delete",
            "Delete saved knowledge",
            "Soft-delete one owned Knowledge item using optimistic revision control.",
            {
                "type": "object",
                "properties": {
                    "item_id": {"type": "string", "minLength": 1},
                    "revision": {"type": "integer", "minimum": 1},
                },
                "required": ["item_id", "revision"],
                "additionalProperties": False,
            },
            ("delete",),
            ("knowledge.manage",),
            delete,
        ),
    )
    for name, title, description, schema, effects, capabilities, handler in definitions:
        repository.ensure_tool(
            service_id=service.id,
            qualified_name=name,
            display_name=title,
            description=description,
            input_schema=schema,
            output_schema={"type": "object"},
            effects=effects,
            required_capabilities=capabilities,
            timeout_ms=30_000,
        )
        registry.bind_tool(name, provider_key=instance.provider_key, handler=handler)
