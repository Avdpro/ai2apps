#!/usr/bin/env python3
"""Exercise the public model-adapter catalog through a clean installation."""

from __future__ import annotations

import asyncio
import json
import tempfile

from omlx.model_adapters.catalog import ModelAdapterCatalog
from omlx.model_adapters.packages import ModelAdapterPackageManager


async def main() -> None:
    root = tempfile.mkdtemp(prefix="omlx-model-adapter-public-smoke-")
    manager = ModelAdapterPackageManager(root)
    catalog = ModelAdapterCatalog(manager)
    trusted = await catalog.trusted_catalog()
    matches = [
        item
        for item in trusted["items"]
        if item["package_id"] == "omlx-model-qwen38"
        and item["version"] == "0.1.0"
    ]
    if len(matches) != 1:
        raise RuntimeError("published Qwen3.8 adapter release was not found")
    installed = await catalog.install("omlx-model-qwen38", "0.1.0")
    print(
        json.dumps(
            {
                "catalog": "trusted",
                "metadata_version": trusted["metadata_version"],
                "checkpoint": matches[0]["checkpoints"][0],
                "installed": installed,
                "test_root": root,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
