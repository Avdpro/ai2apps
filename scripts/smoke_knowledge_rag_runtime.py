#!/usr/bin/env python3
"""Exercise an installed Knowledge vector Runtime without model weights."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from ai2apps.config import PlatformConfig
from ai2apps.identity import MemberRole, RequestPrincipal
from ai2apps.knowledge import KnowledgeScope
from ai2apps.knowledge.backends import (
    ServiceEmbeddingProvider,
    ServiceEndpoint,
    ServiceVectorIndexBackend,
    VectorRecord,
    VectorSearchRequest,
)
from ai2apps.model_providers import resolve_package_model
from ai2apps.platform_runtime import PlatformRuntime
from ai2apps.provisioning.profiles import device_profile


def _acpf_diagnostics(runtime) -> dict:
    provisioner = runtime.provisioning
    profiles = provisioner.profiles.candidates(
        "ai2apps.knowledge",
        "knowledge.semantic_retrieval",
        device_profile(),
        recommended=False,
    )
    components = []
    for profile in profiles:
        for component in profile.get("stack", {}).get("components", ()):
            kind = component.get("kind")
            if kind == "package":
                fact = provisioner._package_fact(component)
            elif kind == "checkpoint":
                model = resolve_package_model(runtime, component.get("model_id"))
                fact = {
                    "modelId": component.get("model_id"),
                    "discovered": model is not None,
                    "checkpointReady": bool(model and model.checkpoint_ready),
                }
            elif kind == "verify":
                fact = {
                    "serviceKey": component.get("service_key"),
                    "ready": provisioner._service_component_ready(component),
                }
            else:
                fact = {"ready": False}
            components.append({"id": component.get("id"), "kind": kind, **fact})
    return {"profiles": [profile.get("id") for profile in profiles], "components": components}


async def smoke(base_path, *, with_embedding: bool = False) -> dict:
    # Keep the Package registry, checkpoints and derived index in the same
    # isolated smoke root unless the caller deliberately selects another cache.
    os.environ.setdefault("HF_HUB_CACHE", str(Path(base_path) / "hf-hub"))
    runtime = PlatformRuntime(PlatformConfig.from_base_path(base_path))
    status = runtime.start()
    if status.status != "ready" or runtime.package_manager is None:
        raise RuntimeError("Platform Runtime did not start")
    try:
        await runtime.package_manager.startup()
        assert runtime.services is not None
        assert runtime.provisioning is not None
        backend = ServiceVectorIndexBackend(
            ServiceEndpoint(runtime.services, "ai2apps.knowledge-vector.lancedb"),
            generation="smoke_v1",
            dimension=3,
        )
        record = VectorRecord(
            chunk_id="smoke-chunk",
            item_id="smoke-item",
            installation_id="smoke-installation",
            owner_user_id="smoke-owner",
            visibility="private",
            bucket_ids=("smoke-bucket",),
            text="local semantic knowledge",
            vector=(1.0, 0.0, 0.0),
        )
        backend.upsert((record,))
        allowed = backend.search(
            VectorSearchRequest(
                vector=(1.0, 0.0, 0.0),
                installation_id="smoke-installation",
                actor_user_id="smoke-owner",
                bucket_ids=("smoke-bucket",),
                limit=10,
            )
        )
        wrong_bucket = backend.search(
            VectorSearchRequest(
                vector=(1.0, 0.0, 0.0),
                installation_id="smoke-installation",
                actor_user_id="smoke-owner",
                bucket_ids=("different-bucket",),
                limit=10,
            )
        )
        denied = backend.search(
            VectorSearchRequest(
                vector=(1.0, 0.0, 0.0),
                installation_id="smoke-installation",
                actor_user_id="different-owner",
                limit=10,
            )
        )
        if (
            [item.item_id for item in allowed] != ["smoke-item"]
            or wrong_bucket
            or denied
        ):
            raise RuntimeError("Vector Worker ACL search smoke failed")
        count_before_delete = backend.count()
        backend.delete_items(("smoke-item",))
        count_after_delete = backend.count()
        if count_before_delete != 1 or count_after_delete != 0:
            raise RuntimeError("Vector Worker mutation smoke failed")
        result = {
            "status": "ready",
            "backend": backend.health().backend,
            "allowed": len(allowed),
            "wrongBucket": len(wrong_bucket),
            "denied": len(denied),
            "countBeforeDelete": count_before_delete,
            "countAfterDelete": count_after_delete,
        }
        if with_embedding:
            capability = runtime.provisioning.resolve_ready(
                "ai2apps.knowledge",
                "knowledge.semantic_retrieval",
                {"operations": ["semantic_search"]},
                profile_id="local-lancedb-e5-small-384",
            )
            if capability is None:
                raise RuntimeError(
                    "ACPF did not resolve the installed Knowledge stack: "
                    + json.dumps(_acpf_diagnostics(runtime), sort_keys=True)
                )
            embedding = ServiceEmbeddingProvider(
                ServiceEndpoint(
                    runtime.services, "ai2apps.model.multilingual-e5-small"
                ),
                model_id="ai2apps.model.multilingual-e5-small/default",
                dimension=384,
            )
            query_vector = embedding.embed(("一周能在家工作几天",))[0]
            passage_vectors = embedding.for_passages().embed(
                (
                    "员工每周可申请两天居家办公，需要提前报备。",
                    "今天阳光很好，适合去公园散步。",
                )
            )
            related = sum(
                a * b for a, b in zip(query_vector, passage_vectors[0], strict=True)
            )
            unrelated = sum(
                a * b for a, b in zip(query_vector, passage_vectors[1], strict=True)
            )
            if related <= unrelated:
                raise RuntimeError("Embedding semantic similarity smoke failed")

            assert runtime.knowledge is not None
            assert runtime.knowledge_package_runtime is not None
            principal = RequestPrincipal(
                actor_user_id="knowledge-smoke-user",
                installation_id="knowledge-smoke-installation",
                organization_id="local",
                billing_account_id="local",
                role=MemberRole.MEMBER,
                membership_epoch=1,
            )
            runtime.knowledge.create_text_item(
                principal,
                scope=KnowledgeScope.PRIVATE,
                title="远程办公政策",
                text="员工每周可申请两天居家办公，需要提前向负责人报备。",
            )
            runtime.knowledge.create_text_item(
                principal,
                scope=KnowledgeScope.PRIVATE,
                title="公园天气",
                text="今天阳光很好，适合去公园散步。",
            )
            retriever = runtime.knowledge_package_runtime.ready_retriever()
            hits, diagnostics = retriever.search(
                principal, "一周能在家工作几天", limit=5
            )
            if (
                diagnostics.mode != "hybrid"
                or not hits
                or hits[0].item.title != "远程办公政策"
            ):
                raise RuntimeError("End-to-end Knowledge hybrid retrieval smoke failed")
            result["embedding"] = {
                "dimension": len(query_vector),
                "relatedSimilarity": related,
                "unrelatedSimilarity": unrelated,
            }
            result["retrieval"] = {
                "mode": diagnostics.mode,
                "topItem": hits[0].item.title,
                "semanticCandidates": diagnostics.semantic_candidates,
            }
            result["acpf"] = {
                "profileId": capability["profileId"],
                "status": "ready",
            }
        return result
    finally:
        await runtime.package_manager.shutdown()
        runtime.stop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-path", required=True)
    parser.add_argument("--with-embedding", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            asyncio.run(smoke(args.base_path, with_embedding=args.with_embedding)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
