"""Public metadata records for secrets; secret values are deliberately absent."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class SecretRecord:
    id: str
    name: str
    purpose: str
    allowed_tools: tuple[str, ...]
    status: str
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None

    @property
    def uri(self) -> str:
        return f"secret://{self.id}"


@dataclass(frozen=True, slots=True)
class SecretInjection:
    arguments: dict[str, Any]
    sensitive_values: tuple[str, ...]
    secret_ids: tuple[str, ...]
