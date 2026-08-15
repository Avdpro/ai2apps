"""Backend protocols for local and remote Fusion roles."""

from __future__ import annotations

from typing import AsyncIterator, Mapping, Protocol, runtime_checkable

from .types import (
    CheckpointDecision,
    DraftChunk,
    FusionRequest,
    ReviewDecision,
    StructuredPatch,
    FusionToolCall,
    ToolReviewDecision,
)


@runtime_checkable
class GeneratorTurn(Protocol):
    async def stream_draft(self) -> AsyncIterator[DraftChunk]: ...

    async def resume_from_checkpoint(
        self, draft: str, decision: CheckpointDecision
    ) -> AsyncIterator[DraftChunk]: ...

    async def revise(
        self, draft: str, decision: ReviewDecision
    ) -> tuple[StructuredPatch, ...]: ...

    async def replan_tool_calls(
        self, draft: str, decision: ToolReviewDecision
    ) -> AsyncIterator[DraftChunk]: ...

    async def realize(self, draft: str, blueprint: Mapping[str, object]) -> str: ...

    async def commit_draft(self) -> None: ...

    async def commit_final(self, text: str) -> None: ...

    async def abort(self) -> None: ...


@runtime_checkable
class GeneratorBackend(Protocol):
    async def begin_turn(self, request: FusionRequest) -> GeneratorTurn: ...


@runtime_checkable
class ReviewerBackend(Protocol):
    async def review_tool_calls(
        self,
        request: FusionRequest,
        draft: str,
        tool_calls: tuple[FusionToolCall, ...],
        validation_errors: tuple[str, ...],
        *,
        final: bool = False,
    ) -> ToolReviewDecision: ...

    async def review_checkpoint(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> CheckpointDecision: ...

    async def review(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> ReviewDecision: ...


@runtime_checkable
class ResolverBackend(Protocol):
    async def review(
        self,
        request: FusionRequest,
        draft: str,
        draft_sha256: str,
        signals: object,
    ) -> ReviewDecision: ...

    async def resolve(
        self,
        request: FusionRequest,
        draft: str,
        review: ReviewDecision,
    ) -> ReviewDecision: ...
