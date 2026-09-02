"""Single-flight job adapter for embedding the MLX pipeline in AI2Apps."""

from __future__ import annotations

import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from .config import GenerationRequest
from .memory_profiles import MemoryProfile, select_memory_profile
from .pipeline import AvatarPipeline, CancellationToken, GenerationCancelled


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class AvatarJobRequest:
    """Stable, JSON-compatible request owned by a service adapter."""

    job_id: str
    image_path: str
    audio_path: str
    output_path: str
    prompt: str = "A person is speaking."
    width: int = 512
    height: int = 512
    seed: int = 43
    fast: bool = False
    long: bool = False
    checkpoint_path: str | None = None

    def __post_init__(self) -> None:
        allowed = "-_abcdefghijklmnopqrstuvwxyz0123456789"
        if not self.job_id or any(character not in allowed for character in self.job_id):
            raise ValueError("job_id must use lowercase letters, digits, '-' or '_'")
        if self.long and self.checkpoint_path is not None:
            raise ValueError("checkpoint_path is not supported for long jobs")
        if self.fast and self.checkpoint_path is not None:
            raise ValueError("checkpoint_path requires exact mode")

    def generation_request(self) -> GenerationRequest:
        return GenerationRequest(
            self.image_path,
            self.audio_path,
            prompt=self.prompt,
            width=self.width,
            height=self.height,
            seed=self.seed,
            teacache_threshold=0.15 if self.fast else 0.0,
            teacache_skip_start_steps=2 if self.fast else 5,
            use_fused_norms=self.fast,
        )


@dataclass(frozen=True, slots=True)
class JobSnapshot:
    job_id: str
    status: JobStatus
    phase: str | None = None
    current: int = 0
    total: int = 0
    output_path: str | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["status"] = self.status.value
        return result


class _Pipeline(Protocol):
    def generate_to_file(
        self,
        request: GenerationRequest,
        output_path: str | Path,
        *,
        progress: Callable[[str, int, int], None] | None = None,
        cancellation: CancellationToken | None = None,
        checkpoint_path: str | Path | None = None,
    ) -> Path: ...

    def generate_long_to_file(
        self,
        request: GenerationRequest,
        output_path: str | Path,
        *,
        progress: Callable[[str, int, int], None] | None = None,
        cancellation: CancellationToken | None = None,
    ) -> Path: ...


@dataclass(slots=True)
class _Job:
    request: AvatarJobRequest
    token: CancellationToken
    snapshot: JobSnapshot
    future: Future[None] | None = None


class AvatarJobService:
    """Serialize MLX work while exposing thread-safe submit/status/cancel primitives."""

    def __init__(
        self,
        pipeline: _Pipeline,
        *,
        storage_root: str | Path,
        memory_profile: MemoryProfile | None = None,
    ) -> None:
        self._pipeline = pipeline
        self.memory_profile = memory_profile or select_memory_profile()
        if isinstance(pipeline, AvatarPipeline):
            pipeline.cache_conditions = self.memory_profile.cache_conditions
        self._storage_root = Path(storage_root).expanduser().resolve()
        self._storage_root.mkdir(parents=True, exist_ok=True)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="echomimic-mlx")
        self._lock = threading.RLock()
        self._jobs: dict[str, _Job] = {}
        self._closed = False

    def _contained_path(self, value: str, *, must_exist: bool) -> Path:
        path = Path(value).expanduser().resolve()
        if not path.is_relative_to(self._storage_root):
            raise ValueError("job paths must remain inside storage_root")
        if must_exist and not path.is_file():
            raise FileNotFoundError(path)
        return path

    def submit(self, request: AvatarJobRequest) -> JobSnapshot:
        image = self._contained_path(request.image_path, must_exist=True)
        audio = self._contained_path(request.audio_path, must_exist=True)
        output = self._contained_path(request.output_path, must_exist=False)
        checkpoint = (
            None
            if request.checkpoint_path is None
            else self._contained_path(request.checkpoint_path, must_exist=False)
        )
        normalized = AvatarJobRequest(
            request.job_id,
            str(image),
            str(audio),
            str(output),
            request.prompt,
            request.width,
            request.height,
            request.seed,
            request.fast,
            request.long,
            None if checkpoint is None else str(checkpoint),
        )
        self.memory_profile.validate(normalized.generation_request())
        with self._lock:
            if self._closed:
                raise RuntimeError("job service is closed")
            existing = self._jobs.get(normalized.job_id)
            if existing is not None:
                if existing.request != normalized:
                    raise ValueError("job_id already belongs to a different request")
                return existing.snapshot
            job = _Job(
                normalized,
                CancellationToken(),
                JobSnapshot(normalized.job_id, JobStatus.QUEUED),
            )
            self._jobs[normalized.job_id] = job
            job.future = self._executor.submit(self._run, job)
            return job.snapshot

    def _set_snapshot(self, job: _Job, **changes: object) -> None:
        with self._lock:
            values = asdict(job.snapshot)
            values.update(changes)
            job.snapshot = JobSnapshot(**values)

    def _run(self, job: _Job) -> None:
        if job.token.cancelled:
            self._set_snapshot(job, status=JobStatus.CANCELLED)
            return
        self._set_snapshot(job, status=JobStatus.RUNNING)

        def progress(phase: str, current: int, total: int) -> None:
            self._set_snapshot(job, phase=phase, current=current, total=total)

        try:
            request = job.request.generation_request()
            if job.request.long:
                destination = self._pipeline.generate_long_to_file(
                    request,
                    job.request.output_path,
                    progress=progress,
                    cancellation=job.token,
                )
            else:
                destination = self._pipeline.generate_to_file(
                    request,
                    job.request.output_path,
                    progress=progress,
                    cancellation=job.token,
                    checkpoint_path=job.request.checkpoint_path,
                )
            self._set_snapshot(
                job,
                status=JobStatus.SUCCEEDED,
                output_path=str(destination),
                error=None,
            )
        except GenerationCancelled:
            self._set_snapshot(job, status=JobStatus.CANCELLED)
        except Exception as error:
            self._set_snapshot(
                job, status=JobStatus.FAILED, error=f"{type(error).__name__}: {error}"
            )

    def status(self, job_id: str) -> JobSnapshot:
        with self._lock:
            try:
                return self._jobs[job_id].snapshot
            except KeyError as error:
                raise KeyError(f"unknown job_id: {job_id}") from error

    def cancel(self, job_id: str) -> JobSnapshot:
        with self._lock:
            try:
                job = self._jobs[job_id]
            except KeyError as error:
                raise KeyError(f"unknown job_id: {job_id}") from error
            if job.snapshot.status in {JobStatus.QUEUED, JobStatus.RUNNING}:
                job.token.cancel()
            return job.snapshot

    def wait(self, job_id: str, timeout: float | None = None) -> JobSnapshot:
        with self._lock:
            try:
                future = self._jobs[job_id].future
            except KeyError as error:
                raise KeyError(f"unknown job_id: {job_id}") from error
        assert future is not None
        future.result(timeout=timeout)
        return self.status(job_id)

    def close(self, *, wait: bool = True) -> None:
        with self._lock:
            self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=False)

    def __enter__(self) -> AvatarJobService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
