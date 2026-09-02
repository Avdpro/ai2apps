"""Filesystem-safe identities shared by checkpoint control-plane modules."""

from __future__ import annotations

import hashlib
import re

_DISTRIBUTION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,254}$")


def checkpoint_distribution_cache_key(distribution_id: str) -> str:
    """Map a Registry identifier to one filesystem-safe opaque directory."""

    if not isinstance(distribution_id, str) or not _DISTRIBUTION_ID.fullmatch(
        distribution_id
    ):
        raise ValueError("distributionId is invalid")
    return hashlib.sha256(distribution_id.encode("utf-8")).hexdigest()
