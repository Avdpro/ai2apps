"""Cloud-managed work defaults, independent of explicit user model selections."""

from __future__ import annotations

import asyncio
import logging
import re
import time

logger = logging.getLogger(__name__)
WORK_PURPOSES = frozenset({"work_simple", "work_standard", "work_complex"})
POLICY_SCHEMA = "ai2apps.ai-defaults/v1"
REFRESH_SECONDS = 300
CACHE_SECONDS = 86400


def validate_policy(payload: object) -> dict:
    if not isinstance(payload, dict) or payload.get("schema") != POLICY_SCHEMA:
        raise ValueError("Unsupported Cloud defaults policy")
    revision = payload.get("revision")
    if not isinstance(revision, str) or not revision or len(revision) > 128:
        raise ValueError("Invalid Cloud defaults revision")
    model = payload.get("apiDefault")
    if model is None and "apiDefault" in payload:
        return {"schema": POLICY_SCHEMA, "revision": revision, "apiDefault": None}
    if not isinstance(model, dict):
        raise ValueError("Missing Cloud API default")
    model_id = model.get("modelId")
    name = model.get("displayName")
    if (
        not isinstance(model_id, str)
        or len(model_id) > 480
        or re.fullmatch(r"[A-Za-z0-9._-]+/[A-Za-z0-9._/-]+", model_id) is None
        or any(part in {"", ".", ".."} for part in model_id.split("/"))
        or model_id.startswith(("cloud/", "gateway/"))
        or not isinstance(name, str)
        or not name.strip()
        or len(name) > 256
        or any(ord(char) < 32 for char in name)
    ):
        raise ValueError("Invalid Cloud API default model")
    return {
        "schema": POLICY_SCHEMA,
        "revision": revision,
        "apiDefault": {"modelId": model_id, "displayName": name.strip()},
    }


async def refresh_cloud_defaults(store, cloud) -> bool:
    """A failed/old server cannot overwrite the last valid policy."""
    try:
        async with asyncio.timeout(3):
            response = await cloud.request("GET", "/v1/ai/defaults")
            try:
                if response.status_code != 200:
                    return False
                policy = validate_policy(response.json())
            finally:
                await response.aclose()
        store.put_cloud_default_policy(policy, fetched_at=time.time())
        return True
    except Exception:
        logger.debug("Cloud model defaults refresh unavailable", exc_info=True)
        return False


async def run_cloud_defaults_refresh(store, cloud) -> None:
    while True:
        await asyncio.sleep(REFRESH_SECONDS)
        await refresh_cloud_defaults(store, cloud)
