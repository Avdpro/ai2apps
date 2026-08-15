"""Typed failures shared by platform repositories and future API adapters."""

from __future__ import annotations


class RepositoryError(RuntimeError):
    """Base class for expected persistence-layer failures."""


class ResourceNotFoundError(RepositoryError):
    def __init__(self, resource_type: str, resource_id: str) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(f"{resource_type} not found: {resource_id}")


class RevisionConflictError(RepositoryError):
    def __init__(self, resource_id: str, expected: int, actual: int) -> None:
        self.resource_id = resource_id
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"Revision conflict for {resource_id}: expected {expected}, actual {actual}"
        )


class IdempotencyConflictError(RepositoryError):
    def __init__(self, session_id: str, idempotency_key: str) -> None:
        self.session_id = session_id
        self.idempotency_key = idempotency_key
        super().__init__(
            "Idempotency key was already used for a different message in "
            f"{session_id}: {idempotency_key}"
        )


class ResourceConflictError(RepositoryError):
    """A relational uniqueness or lifecycle rule rejected the operation."""
