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
    CheckpointManifestError,
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
        concurrency: int = 8,
        legacy_caches: tuple[CheckpointCache, ...] = (),
    ) -> None:
        if not 1 <= concurrency <= 32:
            raise ValueError("concurrency must be between 1 and 32")
        self.registry = registry
        self.cache = cache
        self.transport = transport
        self.huggingface_endpoint = huggingface_endpoint
        self.modelscope_endpoint = modelscope_endpoint
        self.concurrency = concurrency
        self.legacy_caches = legacy_caches

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
        descriptor = None
        while descriptor is None:
            descriptor = self.cache.try_acquire_distribution_lock(manifest)
            if descriptor is None:
                await asyncio.sleep(0.05)
        try:
            # Recheck after taking the machine-wide lock. Another AI2Apps
            # instance may have completed this checkpoint while we waited.
            # A large Cached-MoE snapshot can take minutes to hash. Keep that
            # work off the event loop so a provisioning cancellation can
            # promptly cancel this acquisition instead of leaving the UI
            # closed while range downloads continue in the background.
            cached = await asyncio.to_thread(
                self.cache.verified_snapshot, manifest
            )
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
            for legacy_cache in self.legacy_caches:
                legacy_snapshot = await asyncio.to_thread(
                    legacy_cache.verified_snapshot, manifest
                )
                if legacy_snapshot is None:
                    continue
                try:
                    imported = await asyncio.to_thread(
                        self.cache.import_local_snapshot, manifest, legacy_snapshot
                    )
                except CheckpointManifestError:
                    continue
                return CheckpointAcquisitionResult(
                    manifest=manifest,
                    snapshot=imported,
                    cache_hit=True,
                    source_bytes={},
                )
            cached_blobs = await asyncio.to_thread(
                self.cache.verified_blobs, manifest
            )
            if len(cached_blobs) == len(manifest.files):
                await asyncio.to_thread(self.cache.write_manifest, manifest)
                snapshot = await asyncio.to_thread(
                    self.cache.materialize_snapshot, manifest, cached_blobs
                )
                return CheckpointAcquisitionResult(
                    manifest=manifest,
                    snapshot=snapshot,
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
                limits=httpx.Limits(
                    max_connections=max(16, self.concurrency * 2),
                    max_keepalive_connections=max(16, self.concurrency * 2),
                    keepalive_expiry=60,
                ),
                follow_redirects=False,
            ) as client:
                resolver = HubSourceResolver(
                    client,
                    huggingface_endpoint=self.huggingface_endpoint,
                    modelscope_endpoint=self.modelscope_endpoint,
                )
                file_sizes = {item.path: item.size for item in manifest.files}
                adapters = [
                    resolver.resolve(
                        source,
                        user_token=(
                            hf_token if source.provider == "huggingface" else None
                        ),
                        expected_size=file_sizes[source.path],
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
            snapshot = await asyncio.to_thread(
                self.cache.materialize_snapshot, manifest, blobs
            )
            return CheckpointAcquisitionResult(
                manifest=manifest,
                snapshot=snapshot,
                cache_hit=False,
                source_bytes=dict(scheduler.source_bytes),
            )
        finally:
            self.cache.release_distribution_lock(descriptor)

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
