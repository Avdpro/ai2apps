"""Opt-in local Knowledge Core with no model or App runtime dependency.

The package is intentionally not registered with the platform API yet.  It can
be developed and tested while other release work continues, then wired into
the App behind an explicit feature gate.
"""

from .models import (
    KnowledgeItem,
    KnowledgeScope,
    KnowledgeSearchHit,
    KnowledgeSpace,
    KnowledgeTag,
)
from .store import (
    KnowledgeAccessError,
    KnowledgeConflictError,
    KnowledgeNotFoundError,
    KnowledgeStore,
)

__all__ = [
    "KnowledgeAccessError",
    "KnowledgeConflictError",
    "KnowledgeItem",
    "KnowledgeNotFoundError",
    "KnowledgeScope",
    "KnowledgeSearchHit",
    "KnowledgeSpace",
    "KnowledgeStore",
    "KnowledgeTag",
]
