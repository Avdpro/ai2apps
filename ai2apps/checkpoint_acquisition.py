"""Source-agnostic checkpoint acquisition orchestration."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from ai2apps.checkpoint_distribution import (
    CheckpointCache,
    CheckpointDistributionManifest,
    CheckpointDownloadError,
    HubSourceResolver,
    PieceDownloadScheduler,
    require_checkpoint_license_consent,
)
from ai2apps.checkpoint_paths import checkpoint_distribution_cache_key


@dataclass(frozen=True)
class CheckpointAcquisitionResult:
    manifest: CheckpointDistributionManifest
    snapshot: Path
    cache_hit: bool
    source_bytes: dict[str, int]


class CheckpointAcquisitionService:
    """Acquire one Registry distribution without exposing unverified files."""

    def __init__(
        self,
        *,
        registry: Any,
        cache: CheckpointCache,
        transport: httpx.AsyncBaseTransport | None = None,
        huggingface_endpoint: str = "https://huggingface.co",
        modelscope_endpoint: str = "https://modelscope.cn",
        concurrency: int = 4,
    ) -> None:
        self.registry = registry
        self.cache = cache
        self.transport = transport
        self.huggingface_endpoint = huggingface_endpoint
        self.modelscope_endpoint = modelscope_endpoint
        self.concurrency = concurrency

    async def acquire(
        self,
        distribution_id: str,
        *,
        hf_token: str | None = None,
        disabled_sources: frozenset[str] = frozenset(),
        local_snapshot: str | Path | None = None,
        license_consent: dict[str, Any] | None = None,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> CheckpointAcquisitionResult:
        manifest = await self.registry.distribution(distribution_id)
        # This gate intentionally precedes cache lookup, local import, source
        # probing, and every checkpoint byte read. Conditional terms therefore
        # cannot be bypassed by another acquisition path or an existing cache.
        require_checkpoint_license_consent(manifest, license_consent)
        cached = self.cache.verified_snapshot(manifest)
        if cached is not None:
            return CheckpointAcquisitionResult(
                manifest=manifest,
                snapshot=cached,
                cache_hit=True,
                source_bytes={},
            )
        if local_snapshot is not None:
            imported = await asyncio.to_thread(
                self.cache.import_local_snapshot, manifest, local_snapshot
            )
            return CheckpointAcquisitionResult(
                manifest=manifest,
                snapshot=imported,
                cache_hit=True,
                source_bytes={},
            )
        enabled = [
            source
            for source in manifest.sources
            if source.provider not in disabled_sources
        ]
        if not enabled:
            raise CheckpointDownloadError("all checkpoint sources are disabled")
        timeout = httpx.Timeout(connect=10, read=120, write=30, pool=30)
        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=timeout,
            follow_redirects=False,
        ) as client:
            resolver = HubSourceResolver(
                client,
                huggingface_endpoint=self.huggingface_endpoint,
                modelscope_endpoint=self.modelscope_endpoint,
            )
            adapters = [
                resolver.resolve(
                    source,
                    user_token=hf_token if source.provider == "huggingface" else None,
                )
                for source in enabled
            ]
            scheduler = PieceDownloadScheduler(
                manifest,
                self.cache,
                adapters,
                concurrency=self.concurrency,
                progress=progress,
            )
            blobs = await scheduler.download()
        snapshot = self.cache.materialize_snapshot(manifest, blobs)
        return CheckpointAcquisitionResult(
            manifest=manifest,
            snapshot=snapshot,
            cache_hit=False,
            source_bytes=dict(scheduler.source_bytes),
        )

    def materialize_worker_snapshot(
        self,
        result: CheckpointAcquisitionResult,
        hub_cache: str | Path,
    ) -> Path:
        """Publish a verified distribution in the Worker-owned HF cache tree."""

        manifest = result.manifest
        hub_root = Path(hub_cache).expanduser().resolve()
        repo_root = (hub_root / ("models--" + manifest.repo_id.replace("/", "--"))).resolve()
        try:
            repo_root.relative_to(hub_root)
        except ValueError as error:
            raise CheckpointDownloadError(
                "Worker checkpoint repository escapes the configured cache"
            ) from error
        distributions = repo_root / "distributions"
        distributions.mkdir(parents=True, exist_ok=True)
        distributions = distributions.resolve()
        try:
            distributions.relative_to(repo_root)
        except ValueError as error:
            raise CheckpointDownloadError(
                "Worker checkpoint distribution directory escapes its repository"
            ) from error
        destination = (
            distributions / checkpoint_distribution_cache_key(manifest.distribution_id)
        )
        return self.cache.materialize_snapshot_view(
            manifest, result.snapshot, destination
        )
